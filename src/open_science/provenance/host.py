"""host SDK —— 注入 kernel 的 in-process 溯源接口。

对齐 operon：operon 的 `host.query` / `host.save_artifact` 不是 MCP server，
而是注入到 repl 内核里的一个 `host` 对象（host-side RPC 支撑）。本项目本地跑，
内核是 jupyter 子进程，SQLite 又是文件——所以内核直接打开同一个 db 文件即可，
无需 RPC，且语义与 operon 一致（host 就是那个库的读写面）。

同一个 Host 类既可在编排侧用，也可在内核里 `from ... import Host` 后实例化。

安全红线（对齐 operon 的只读 host.query）：
    query() 只允许 SELECT / WITH / PRAGMA / EXPLAIN，单条语句，
    且用 `file:db?mode=ro` 只读连接——DROP / DELETE / UPDATE 一律打不进去。
"""

from __future__ import annotations

import hashlib
import mimetypes
import re
import sqlite3
import time
import uuid
from pathlib import Path

# query() 白名单：只读起手词
_READONLY_HEAD = re.compile(r"^\s*(SELECT|WITH|PRAGMA|EXPLAIN)\b", re.IGNORECASE)

_DEFAULT_LIMIT = 200
_MAX_LIMIT = 1000


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ReadOnlyViolation(RuntimeError):
    """query() 收到非只读语句时抛出。"""


class Host:
    """注入内核的溯源 SDK。"""

    def __init__(
        self,
        db_path: str | Path,
        artifacts_dir: str | Path,
        frame_id: str | None = None,
    ) -> None:
        self.db_path = str(db_path)
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.frame_id = frame_id

    # ── 只读查询 ────────────────────────────────────────────
    def query(
        self,
        sql: str,
        params: list | None = None,
        limit: int | None = None,
        df: bool = False,
    ) -> dict:
        """只读 SQL。拒绝一切非 SELECT/WITH/PRAGMA/EXPLAIN 与多语句。"""
        if not _READONLY_HEAD.match(sql):
            raise ReadOnlyViolation(
                "query() 只接受 SELECT / WITH / PRAGMA / EXPLAIN 语句"
            )
        # 单语句：去掉尾部 ; 后不得再含 ;
        stripped = sql.strip().rstrip(";")
        if ";" in stripped:
            raise ReadOnlyViolation("query() 一次只允许一条语句")

        # PRAGMA 只允许introspection 形式（PRAGMA table_info(...)）——
        # 拒绝 setter 形式（PRAGMA foo=bar）。mode=ro 已在引擎层挡写，这是纵深防御。
        if re.match(r"^\s*PRAGMA\b", stripped, re.IGNORECASE) and "=" in stripped:
            raise ReadOnlyViolation("query() 不允许 PRAGMA 赋值（setter）")

        cap = _DEFAULT_LIMIT if limit is None else min(int(limit), _MAX_LIMIT)

        # 只读连接：即便语句能绕过正则，mode=ro 也让写操作在引擎层失败。
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        try:
            cur = conn.execute(stripped, params or [])
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(cap + 1)
            truncated = len(rows) > cap
            rows = rows[:cap]
        finally:
            conn.close()

        rows = [list(r) for r in rows]
        if df:  # operon 的 df=True 在 repl 里返回原始 dict，这里保持一致
            return {"columns": columns, "rows": rows, "truncated": truncated}
        return {"columns": columns, "rows": rows, "truncated": truncated}

    # ── 写 artifact ────────────────────────────────────────
    def save_artifact(
        self,
        name: str,
        data: bytes | str,
        *,
        content_type: str | None = None,
        description: str | None = None,
        depends_on: list[str] | None = None,
        producing_cell_id: str | None = None,
        is_intermediate: bool = False,
    ) -> str:
        """保存一个 artifact 版本，返回 version_id。

        - data 为 str 时按 utf-8 编码。
        - content_type 缺省按后缀推断（渲染层据此分派 Mol* / 内联图 / 链接）。
        - depends_on 传上游 version_id 列表 → 落 artifact_dependencies（DAG 边）。
        """
        blob = data.encode("utf-8") if isinstance(data, str) else bytes(data)
        checksum = _sha256(blob)
        ctype = content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"

        conn = sqlite3.connect(self.db_path)
        try:
            now = _now_ms()

            # 1) 内容寻址去重
            conn.execute(
                "INSERT OR IGNORE INTO content_snapshots(hash, content, size_bytes) "
                "VALUES (?,?,?)",
                (checksum, blob, len(blob)),
            )

            # 2) 找/建 artifact 行（同 frame + 同文件名视为同一 artifact 的多版本）
            row = conn.execute(
                "SELECT id FROM artifacts WHERE filename=? AND "
                "(frame_id IS ? OR frame_id=?)",
                (name, self.frame_id, self.frame_id),
            ).fetchone()
            if row:
                artifact_id = row[0]
                vn = conn.execute(
                    "SELECT COALESCE(MAX(version_number),0)+1 FROM artifact_versions "
                    "WHERE artifact_id=?",
                    (artifact_id,),
                ).fetchone()[0]
            else:
                artifact_id = _new_id("art")
                vn = 1
                conn.execute(
                    "INSERT INTO artifacts(id, frame_id, filename, is_ephemeral, created_at) "
                    "VALUES (?,?,?,0,?)",
                    (artifact_id, self.frame_id, name, now),
                )

            # 3) 落盘 + 版本行
            version_id = _new_id("ver")
            storage_path = str(self.artifacts_dir / f"{version_id}__{name}")
            Path(storage_path).write_bytes(blob)

            conn.execute(
                "INSERT INTO artifact_versions("
                "id, artifact_id, version_number, frame_id, content_type, size_bytes, "
                "checksum, storage_path, code_description, producing_cell_id, "
                "is_intermediate, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    version_id, artifact_id, vn, self.frame_id, ctype, len(blob),
                    checksum, storage_path, description, producing_cell_id,
                    1 if is_intermediate else 0, now,
                ),
            )
            conn.execute(
                "UPDATE artifacts SET latest_version_id=? WHERE id=?",
                (version_id, artifact_id),
            )

            # 4) DAG 边
            for up in depends_on or []:
                conn.execute(
                    "INSERT OR IGNORE INTO artifact_dependencies("
                    "artifact_version_id, depends_on_version_id) VALUES (?,?)",
                    (version_id, up),
                )

            conn.commit()
            return version_id
        finally:
            conn.close()

    def get_artifact(self, version_id: str) -> bytes:
        """按 version_id 取回字节（优先落盘文件，回退 content_snapshots）。"""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT storage_path, checksum FROM artifact_versions WHERE id=?",
                (version_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"未知 version_id: {version_id}")
            storage_path, checksum = row
            if storage_path and Path(storage_path).exists():
                return Path(storage_path).read_bytes()
            blob = conn.execute(
                "SELECT content FROM content_snapshots WHERE hash=?", (checksum,)
            ).fetchone()
            if blob is None:
                raise FileNotFoundError(f"artifact 内容缺失: {version_id}")
            return bytes(blob[0])
        finally:
            conn.close()

    def artifact_marker(self, version_id: str) -> str:
        """operon 的内联占位符协议。"""
        return f"{{{{artifact:{version_id}}}}}"
