"""byoc 远程执行 —— 把 GPU 任务派到远程 workspace（对齐 operon 的 remote-compute-*）。

operon 有 `remote-compute-ssh` / `remote-compute-modal`：声明式描述远程算力，
把命令派到远程盒子跑。OpenHands 的对应物是 `RemoteWorkspace`（工厂
`Workspace(host=...)` 返回它），它暴露一个 `execute_command(command, cwd, timeout)
-> CommandResult` 的 HTTP/WS 执行面。本模块在其上薄薄包一层，做两件 operon 也做的事：

  1. **凭据只走环境变量**——连接信息（host/api_key）绝不入库，从
     `OS_REMOTE_HOST` / `OS_REMOTE_API_KEY` / `OS_REMOTE_WORKDIR` 读。
  2. **远程执行贯通溯源**——每次 `run()` 把这条远程命令按阶段 1 的 schema 落一行
     `execution_log`（kernel_kind='remote'），与本地 KernelSession 记法一致，
     使「远程跑的东西」和本地 artifact/DAG 在同一张溯源库里可查。

设计取舍（对齐首要原则）：远程盒子未必装 jupyter，最小可用面是 shell 执行
（nvidia-smi / python 脚本 / proteinmpnn），故这里以 `execute_command` 为原语，
不强求远程有状态 IPython 核——proteinmpnn 这类「跑一个脚本出结果」的模型技能，
shell 执行即行为等价。若远程也需跨 cell 保变量，再在远端起 KernelSession。
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


def _now_ms() -> int:
    return int(time.time() * 1000)


class RemoteNotConfigured(RuntimeError):
    """未配置远程连接信息（缺 OS_REMOTE_HOST）时抛出。"""


@dataclass
class RemoteResult:
    """一次远程执行的结果（贴合 CommandResult，附溯源 cell_id）。"""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    timeout_occurred: bool
    cell_id: str | None = None  # execution_log.id（开启溯源时非空）

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timeout_occurred


class RemoteCompute:
    """远程 workspace 的薄封装：连接 + 执行 + 溯源落库。

    用法：
        rc = RemoteCompute.from_env(db_path=..., frame_id=...)   # 读环境变量
        res = rc.run("nvidia-smi")
        assert res.ok
    """

    def __init__(
        self,
        host: str,
        *,
        api_key: str | None = None,
        working_dir: str = "workspace/project",
        db_path: str | Path | None = None,
        frame_id: str | None = None,
    ) -> None:
        if not host:
            raise RemoteNotConfigured(
                "缺少远程 host——设置 OS_REMOTE_HOST 或显式传 host="
            )
        # 延迟导入：本地阶段跑测试时不必装/连远程侧。
        from openhands.sdk import Workspace

        self.host = host
        self.working_dir = working_dir
        self.db_path = str(db_path) if db_path else None
        self.frame_id = frame_id
        self._cell_index = 0
        self._ws_id = f"remote_{uuid.uuid4().hex[:8]}"
        # Workspace(host=...) 工厂 → RemoteWorkspace
        self._ws = Workspace(
            host=host,
            working_dir=working_dir,
            api_key=api_key,
        )

    @classmethod
    def from_env(
        cls,
        *,
        db_path: str | Path | None = None,
        frame_id: str | None = None,
    ) -> RemoteCompute:
        """从环境变量装配（凭据绝不入库）。

        OS_REMOTE_HOST     远程 agent-server 的 URL（必需）
        OS_REMOTE_API_KEY  远程鉴权 key（可选）
        OS_REMOTE_WORKDIR  远程工作目录（默认 workspace/project）
        """
        host = os.environ.get("OS_REMOTE_HOST", "").strip()
        if not host:
            raise RemoteNotConfigured(
                "未配置 OS_REMOTE_HOST——远程算力关（如 nvidia-smi）将 SKIP"
            )
        return cls(
            host=host,
            api_key=os.environ.get("OS_REMOTE_API_KEY") or None,
            working_dir=os.environ.get("OS_REMOTE_WORKDIR", "workspace/project"),
            db_path=db_path,
            frame_id=frame_id,
        )

    @staticmethod
    def configured() -> bool:
        """环境里是否配了远程连接信息（用于验证关卡优雅 SKIP）。"""
        return bool(os.environ.get("OS_REMOTE_HOST", "").strip())

    @property
    def provenance_on(self) -> bool:
        return self.db_path is not None

    def run(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout: float = 600.0,
        _log: bool = True,
    ) -> RemoteResult:
        """在远程执行一条命令，收集输出并（可选）落 execution_log。"""
        cr = self._ws.execute_command(command, cwd=cwd, timeout=timeout)
        res = RemoteResult(
            command=cr.command,
            exit_code=cr.exit_code,
            stdout=cr.stdout,
            stderr=cr.stderr,
            timeout_occurred=cr.timeout_occurred,
        )
        if _log and self.provenance_on:
            res.cell_id = self._write_execution_log(command, res)
        return res

    def _write_execution_log(self, source: str, res: RemoteResult) -> str:
        """按阶段 1 schema 记一行远程执行（kernel_kind='remote'）。"""
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
                    cell_id, self.frame_id, self._cell_index, self._ws_id,
                    "remote", "shell", source, res.stdout, res.stderr,
                    "ok" if res.ok else "error",
                    json.dumps([]), _now_ms(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return cell_id

    def file_download(self, remote_path: str, local_path: str | Path) -> None:
        """把远程产物取回本地（供 save_artifact 归档）。"""
        self._ws.file_download(str(remote_path), str(local_path))

    def file_upload(self, local_path: str | Path, remote_path: str) -> None:
        """把本地输入（如 backbone.pdb）推到远程。"""
        self._ws.file_upload(str(local_path), str(remote_path))
