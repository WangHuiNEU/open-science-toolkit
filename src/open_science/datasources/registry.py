"""数据源 registry —— 域→server 映射 + OpenHands MCPConfig 生成。

单一事实源是 vendor 的 `mcp_bio/domains.json`（23 个域 → 各自工具名册），
域名到聚合 server 包名的映射就是 `mcp_` + 域名把连字符换下划线
（rna→mcp_rna, genes-ontologies→mcp_genes_ontologies, ...）。第 24 个可启动
server `mcp_bio` 是全域聚合（不在 domains.json 里，作为 "all" 特例）。

用法：
    from open_science.datasources.registry import mcp_config_for
    cfg = mcp_config_for(["rna"])          # 只挂 RNA 域
    # cfg = {"mcpServers": {"mcp_rna": {"command":"python","args":[...]}}}
    from openhands.sdk import create_mcp_tools
    with create_mcp_tools(cfg) as client:
        tools = client.tools                # 只有 rna 域 9 个工具

按 operon 一致：每个域是一个独立 stdio 子进程（launcher 拉起对应 server），
server 的 main() 自带 apply_gate_*（照 deferred.json 关掉受限工具）。
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

from .vendor import LIB_DIR

_DOMAINS_JSON = LIB_DIR / "mcp_bio" / "domains.json"

# open_science 包所在的 src 根（launcher 子进程未安装本包，需显式上 path）。
_SRC_ROOT = Path(__file__).resolve().parents[2]  # .../src

# vendor 的 lib/ 是 GBK 系统上非 UTF-8 默认会读挂的（deferred.json 有花引号）。
# 子进程统一用 UTF-8 模式跑，等价 operon 的 Linux/UTF-8 运行环境。
_UTF8_ENV = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _domain_to_server(domain: str) -> str:
    return "mcp_" + domain.replace("-", "_")


@lru_cache(maxsize=1)
def domain_tools() -> dict[str, list[str]]:
    """域名 → 该域工具名册（读 domains.json）。"""
    return json.loads(_DOMAINS_JSON.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def domain_to_server() -> dict[str, str]:
    """域名 → 聚合 server 包名；外加 'all' → mcp_bio 全域聚合。"""
    mapping = {d: _domain_to_server(d) for d in domain_tools()}
    mapping["all"] = "mcp_bio"
    return mapping


def servers_for(domains: list[str]) -> list[str]:
    """把域名列表解析为去重、稳定排序的 server 包名列表。"""
    m = domain_to_server()
    unknown = [d for d in domains if d not in m]
    if unknown:
        raise KeyError(
            f"未知数据源域: {unknown}；可用: {sorted(domain_to_server())}"
        )
    return sorted({m[d] for d in domains})


def _server_entry(server_pkg: str) -> dict:
    """单个 stdio server 的 MCPConfig 条目。

    子进程 env：继承当前环境（Windows 下需保留 PATH/SystemRoot），叠加
    UTF-8 强制 + 把 src 根塞进 PYTHONPATH（本包未安装，子进程靠它找 open_science）。
    """
    import os

    env = dict(os.environ)
    env.update(_UTF8_ENV)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{_SRC_ROOT}{os.pathsep}{existing}" if existing else str(_SRC_ROOT)
    )
    return {
        "command": sys.executable,
        "args": ["-m", "open_science.datasources.launcher", server_pkg],
        "env": env,
    }


def mcp_config_for(domains: list[str]) -> dict:
    """按域名列表生成 OpenHands `create_mcp_tools` 吃的 MCPConfig。"""
    return {
        "mcpServers": {srv: _server_entry(srv) for srv in servers_for(domains)}
    }


def all_domains() -> list[str]:
    return sorted(domain_tools())
