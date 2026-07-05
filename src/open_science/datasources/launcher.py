"""stdio 启动器 —— 复刻 operon 的 bio-tools/run_server.py。

用法（OpenHands 的 MCPConfig 会这样拉起）：
    python -m open_science.datasources.launcher <server_pkg>
例：
    python -m open_science.datasources.launcher mcp_rna

与 operon 一致：把 vendor/lib 放到 sys.path（那些包扁平互 import），
importlib 加载 `<pkg>.server` 再调 `main()`（main 里自带 apply_gate_* +
mcp.run() / Tier1Server.run()，走 stdio）。可启动集从磁盘推导——
只认 lib/ 下带 server.py 的 mcp_* 包，排除 mcp_servers_common 这类 helper。
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from .vendor import LIB_DIR


def launchable_servers() -> list[str]:
    """lib/ 下真正带 server.py 的 mcp_* 包（= 可 stdio 启动的聚合 server）。"""
    return sorted(
        p.name
        for p in LIB_DIR.iterdir()
        if p.name.startswith("mcp_") and (p / "server.py").is_file()
    )


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    servers = launchable_servers()
    if len(argv) != 1 or argv[0] not in servers:
        sys.stderr.write(
            "usage: python -m open_science.datasources.launcher <server package>\n"
            f"valid: {', '.join(servers)}\n"
        )
        raise SystemExit(2)

    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    mod = importlib.import_module(f"{argv[0]}.server")
    mod.main()


if __name__ == "__main__":
    main()
