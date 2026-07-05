"""ProteinMPNN 反向折叠 runner —— 阶段 5 的「最小模型真跑」证明。

对齐 operon 的 proteinmpnn SKILL.md：clone 仓库 → 跑 `protein_mpnn_run.py` →
解析 `out/seqs/<stem>.fa` → 取设计序列。ProteinMPNN 小到 CPU 秒级可跑、权重随仓库
自带、不依赖 hf.co，所以是「模型技能能真跑」这一关最诚实的本地证明（不必等 GPU 节点）。

溯源贯通（对齐阶段 1）：每条 shell 命令经 `_shell` 执行，若给了 db_path 就按
execution_log schema 落一行（kernel_kind='local'/'remote'）；设计产物 `.fa` 经
Host.save_artifact 归档成 artifact，与本地 DAG 在同一张溯源库可查。

本地跑用 subprocess；远程 GPU 跑把同一条命令交给 [[remote]].RemoteCompute.run，
两条路都进 execution_log——命名空间与记法一致。
"""

from __future__ import annotations

import json
import subprocess
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

_REPO_URL = "https://github.com/dauparas/ProteinMPNN.git"


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class ShellResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    cell_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class DesignRecord:
    """一条 FASTA 记录。第一条是输入序列，其余为设计序列。"""

    header: str
    sequence: str
    score: float | None = None
    global_score: float | None = None
    seq_recovery: float | None = None
    is_input: bool = False


@dataclass
class DesignResult:
    input_sequence: str
    designs: list[DesignRecord] = field(default_factory=list)
    fasta_path: str | None = None
    artifact_version_id: str | None = None
    cell_ids: list[str] = field(default_factory=list)

    @property
    def chain_length(self) -> int:
        return len(self.input_sequence)


class ProteinMPNNRunner:
    """在本地（或经远程 executor）跑 ProteinMPNN 并贯通溯源。"""

    def __init__(
        self,
        workdir: str | Path,
        *,
        db_path: str | Path | None = None,
        frame_id: str | None = None,
        repo_dir: str | Path | None = None,
        kernel_kind: str = "local",
    ) -> None:
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.repo_dir = Path(repo_dir) if repo_dir else self.workdir / "proteinmpnn"
        self.db_path = str(db_path) if db_path else None
        self.frame_id = frame_id
        self.kernel_kind = kernel_kind
        self._cell_index = 0
        self._runner_id = f"pmpnn_{uuid.uuid4().hex[:8]}"

    # ── shell 执行 + 溯源 ──────────────────────────────────
    def _shell(
        self,
        command: str,
        *,
        cwd: str | Path | None = None,
        timeout: float = 600.0,
        _log: bool = True,
    ) -> ShellResult:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        res = ShellResult(
            command=command,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
        if _log and self.db_path:
            res.cell_id = self._write_execution_log(command, res)
        return res

    def _write_execution_log(self, source: str, res: ShellResult) -> str:
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
                    cell_id, self.frame_id, self._cell_index, self._runner_id,
                    self.kernel_kind, "shell", source, res.stdout, res.stderr,
                    "ok" if res.ok else "error", json.dumps([]), _now_ms(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return cell_id

    # ── 仓库准备 ──────────────────────────────────────────
    def ensure_repo(self) -> Path:
        """幂等 clone（权重随仓库自带，无 PyPI dist）。"""
        script = self.repo_dir / "protein_mpnn_run.py"
        if script.exists():
            return self.repo_dir
        res = self._shell(
            f'git clone --depth 1 {_REPO_URL} "{self.repo_dir}"',
            cwd=self.workdir,
            timeout=300.0,
        )
        if not res.ok or not script.exists():
            raise RuntimeError(
                f"clone ProteinMPNN 失败 (exit={res.exit_code}):\n{res.stderr[:500]}"
            )
        return self.repo_dir

    # ── 设计 ──────────────────────────────────────────────
    def design(
        self,
        pdb_path: str | Path,
        *,
        chains: str = "A",
        num_seq_per_target: int = 4,
        sampling_temp: str = "0.1",
        model_name: str = "v_48_020",
        out_folder: str | Path | None = None,
        host=None,  # provenance.Host —— 若给则把 .fa 存成 artifact
        timeout: float = 600.0,
    ) -> DesignResult:
        """对一个 PDB backbone 反向折叠，返回设计序列（含溯源）。"""
        self.ensure_repo()
        pdb_path = Path(pdb_path).resolve()
        out = Path(out_folder).resolve() if out_folder else (self.workdir / "out").resolve()
        out.mkdir(parents=True, exist_ok=True)

        # 权重目录：脚本自身用 __file__.rfind("/") 推导，Windows 反斜杠下会算错——
        # 显式传 --path_to_model_weights（脚本 line 37 分支），绕过而不改 vendored 源。
        # 同理 parse_PDB 用 rfind("/") 从 pdb_path 抽 stem、输出路径靠字符串拼接——
        # 一律用 POSIX 正斜杠路径喂给脚本，Windows 下才切得对（不改 vendored 源）。
        weights_dir = (self.repo_dir / "vanilla_model_weights").resolve().as_posix()
        pdb_arg = pdb_path.as_posix()
        out_arg = out.as_posix()

        # SKILL.md 踩坑：--sampling_temp / --pdb_path_chains 都是空格分隔、需引号；逗号会挂。
        cmd = (
            f'python protein_mpnn_run.py '
            f'--path_to_model_weights "{weights_dir}" '
            f'--pdb_path "{pdb_arg}" --pdb_path_chains "{chains}" '
            f'--out_folder "{out_arg}" --num_seq_per_target {int(num_seq_per_target)} '
            f'--sampling_temp "{sampling_temp}" --model_name {model_name}'
        )
        res = self._shell(cmd, cwd=self.repo_dir, timeout=timeout)
        cell_ids = [c for c in (res.cell_id,) if c]
        if not res.ok:
            raise RuntimeError(
                f"protein_mpnn_run.py 失败 (exit={res.exit_code}):\n"
                f"stdout:\n{res.stdout[-800:]}\nstderr:\n{res.stderr[-800:]}"
            )

        stem = pdb_path.stem
        fa = out / "seqs" / f"{stem}.fa"
        if not fa.exists():
            raise FileNotFoundError(f"未找到设计输出 {fa}（out/seqs 下应有 {stem}.fa）")

        records = self.parse_fasta(fa.read_text())
        if not records:
            raise RuntimeError(f"设计输出为空: {fa}")
        input_seq = records[0].sequence

        result = DesignResult(
            input_sequence=input_seq,
            designs=records,
            fasta_path=str(fa),
            cell_ids=cell_ids,
        )

        if host is not None:
            result.artifact_version_id = host.save_artifact(
                f"{stem}.fa",
                fa.read_bytes(),
                content_type="text/x-fasta",
                description=f"ProteinMPNN {model_name} 设计 ({num_seq_per_target} seq, T={sampling_temp})",
                producing_cell_id=cell_ids[0] if cell_ids else None,
            )
        return result

    # ── FASTA 解析 ────────────────────────────────────────
    @staticmethod
    def parse_fasta(text: str) -> list[DesignRecord]:
        """解析 ProteinMPNN 输出 fasta。首条=输入序列；设计头带 score=/global_score=/seq_recovery=。"""
        records: list[DesignRecord] = []
        header: str | None = None
        seq_parts: list[str] = []

        def _flush(is_first: bool) -> None:
            if header is None:
                return
            seq = "".join(seq_parts).strip()
            meta = _parse_header_meta(header)
            records.append(
                DesignRecord(
                    header=header,
                    sequence=seq,
                    score=meta.get("score"),
                    global_score=meta.get("global_score"),
                    seq_recovery=meta.get("seq_recovery"),
                    is_input=is_first,
                )
            )

        first = True
        for line in text.splitlines():
            if line.startswith(">"):
                _flush(first)
                if header is not None:
                    first = False
                header = line[1:].strip()
                seq_parts = []
            else:
                seq_parts.append(line.strip())
        _flush(first)
        return records


def _parse_header_meta(header: str) -> dict[str, float]:
    """从 fasta 头抽 key=value 浮点（score= / global_score= / seq_recovery=）。"""
    meta: dict[str, float] = {}
    for chunk in header.replace(",", " ").split():
        if "=" in chunk:
            k, _, v = chunk.partition("=")
            try:
                meta[k.strip()] = float(v)
            except ValueError:
                pass
    return meta
