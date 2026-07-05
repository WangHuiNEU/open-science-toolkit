"""运行时内核：真·有状态 Jupyter kernel（跨 cell 保留变量）+ 溯源钩子。

设计依据（operon 为准）：
    operon 的代码执行是一个常驻 IPython/Jupyter 内核——变量、导入、
    打开的文件句柄都跨 cell 存活。OpenHands V1 默认给的是常驻 *bash*
    终端：shell 状态活，但每次 `python` 都是新进程，Python 变量不保留。
    按 1:1 原则不降级，这里直接用 operon 同款机制：jupyter_client 拉起
    一个 ipykernel 子进程，通过 ZMQ 收发 execute 请求。

阶段 1 增量（溯源 by construction）：
    传入 db_path/workspace_dir 后，KernelSession 会
      1) 把内核 cwd 固定到 workspace_dir；
      2) 往内核里注入 `host` 对象（provenance.Host），代码里可直接
         host.query / host.save_artifact / host.get_artifact；
      3) 每个 cell 执行后自动往 execution_log 记一行，files_written
         靠 cell 前后 workspace 目录快照 diff + sha256 得出。

对外接口保持最小：
    ks = KernelSession(db_path=..., workspace_dir=...).start()
    r = ks.run("x = 41; x += 1")     # r.stdout / r.result / r.error
"""

from __future__ import annotations

import hashlib
import json
import queue
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from jupyter_client.manager import KernelManager


@dataclass
class CellResult:
    """一次 cell 执行的结果。"""

    stdout: str = ""
    stderr: str = ""
    result: str | None = None          # 最后一个表达式的 repr（execute_result / text/plain）
    error: str | None = None           # 异常名: 值（有异常才非空）
    traceback: list[str] = field(default_factory=list)
    cell_id: str | None = None         # execution_log.id（开启溯源时非空）
    files_written: list[dict] = field(default_factory=list)  # [{path, sha256}]

    @property
    def ok(self) -> bool:
        return self.error is None


def _now_ms() -> int:
    return int(time.time() * 1000)


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class KernelSession:
    """常驻 IPython 内核，跨 cell 保留状态；可选溯源落库。"""

    def __init__(
        self,
        kernel_name: str = "python3",
        *,
        db_path: str | Path | None = None,
        workspace_dir: str | Path | None = None,
        frame_id: str | None = None,
    ) -> None:
        self._km = KernelManager(kernel_name=kernel_name)
        self._kc = None
        self.db_path = str(db_path) if db_path else None
        self.workspace_dir = Path(workspace_dir) if workspace_dir else None
        self.frame_id = frame_id
        self._cell_index = 0
        self._kernel_id = uuid.uuid4().hex[:12]
        if self.workspace_dir:
            self.workspace_dir.mkdir(parents=True, exist_ok=True)

    @property
    def provenance_on(self) -> bool:
        return self.db_path is not None and self.workspace_dir is not None

    def start(self) -> KernelSession:
        cwd = str(self.workspace_dir) if self.workspace_dir else None
        self._km.start_kernel(cwd=cwd)
        self._kc = self._km.client()
        self._kc.start_channels()
        self._kc.wait_for_ready(timeout=60)
        if self.provenance_on:
            self._inject_host()
        return self

    def _inject_host(self) -> None:
        """把 provenance.Host 注入内核，暴露为 `host`。"""
        src_root = Path(__file__).resolve().parents[1]  # .../src
        boot = (
            "import sys as _sys\n"
            f"_sys.path.insert(0, {str(src_root)!r})\n"
            "from open_science.provenance.host import Host as _Host\n"
            f"host = _Host({self.db_path!r}, "
            f"{str(self.workspace_dir)!r}, frame_id={self.frame_id!r})\n"
        )
        r = self.run(boot, _log=False)
        if not r.ok:
            raise RuntimeError(f"host 注入失败: {r.error}\n{''.join(r.traceback)}")

    def run(self, code: str, *, timeout: float = 120.0, _log: bool = True) -> CellResult:
        """执行一段代码，收集 stdout / 结果 / 异常，并（可选）落 execution_log。"""
        if self._kc is None:
            raise RuntimeError("kernel 未启动，先调用 start()")

        do_log = _log and self.provenance_on
        before = self._snapshot() if do_log else {}

        msg_id = self._kc.execute(code)
        res = CellResult()

        # 1) 在 iopub 上收集输出，直到 kernel 回到 idle 且是本请求触发的
        while True:
            try:
                msg = self._kc.get_iopub_msg(timeout=timeout)
            except queue.Empty as exc:
                raise TimeoutError(f"cell 执行超时（{timeout}s）") from exc

            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue

            mtype = msg["msg_type"]
            content = msg["content"]

            if mtype == "stream":
                if content["name"] == "stdout":
                    res.stdout += content["text"]
                else:
                    res.stderr += content["text"]
            elif mtype in ("execute_result", "display_data"):
                res.result = content.get("data", {}).get("text/plain")
            elif mtype == "error":
                res.error = f"{content['ename']}: {content['evalue']}"
                res.traceback = content.get("traceback", [])
            elif mtype == "status" and content["execution_state"] == "idle":
                break

        # 2) 排空 shell 回复通道（execute_reply），保持通道干净
        try:
            self._kc.get_shell_msg(timeout=timeout)
        except queue.Empty:
            pass

        if do_log:
            after = self._snapshot()
            res.files_written = self._diff(before, after)
            res.cell_id = self._write_execution_log(code, res)

        return res

    # ── 溯源辅助 ────────────────────────────────────────────
    def _snapshot(self) -> dict[str, float]:
        """workspace 目录下所有文件的 mtime 快照。"""
        snap: dict[str, float] = {}
        for p in self.workspace_dir.rglob("*"):
            if p.is_file():
                snap[str(p)] = p.stat().st_mtime
        return snap

    def _diff(self, before: dict, after: dict) -> list[dict]:
        """算出本 cell 新增/改动的文件，附 sha256。"""
        changed = []
        for path, mtime in after.items():
            if path not in before or before[path] != mtime:
                changed.append({"path": path, "sha256": _sha256_file(Path(path))})
        return sorted(changed, key=lambda d: d["path"])

    def _write_execution_log(self, source: str, res: CellResult) -> str:
        cell_id = f"cell_{uuid.uuid4().hex}"
        self._cell_index += 1
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO execution_log("
                "id, frame_id, cell_index, kernel_id, kernel_kind, language, "
                "source, stdout, stderr, exit_status, files_written, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    cell_id, self.frame_id, self._cell_index, self._kernel_id,
                    "analysis", "python", source, res.stdout, res.stderr,
                    "ok" if res.ok else "error",
                    json.dumps(res.files_written), _now_ms(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return cell_id

    def shutdown(self) -> None:
        if self._kc is not None:
            self._kc.stop_channels()
            self._kc = None
        if self._km.is_alive():
            self._km.shutdown_kernel(now=True)


if __name__ == "__main__":
    ks = KernelSession().start()
    try:
        print("A:", ks.run("x = 41; x += 1"))
        print("B:", ks.run("print(x)"))
        print("C:", ks.run("import math; math.sqrt(x)"))
    finally:
        ks.shutdown()
