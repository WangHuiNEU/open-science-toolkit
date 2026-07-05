"""阶段 2 验证：数据源层（vendor 87 源 + OpenHands MCP 包装 + 按需注入）。

运行（需能出网访问 rfam.org / rest.uniprot.org / eutils.ncbi.nlm.nih.gov）：
    cd open-science
    PYTHONUTF8=1 python tests/verify_stage2.py

五关（对齐 docs/ROADMAP.md 阶段 2）：
  1. 试点三源真实取数：
       rfam   get_family RF00001         → 含 rfam_acc / description
       uniprot get_uniprot_entries P69905 → 含序列（FASTA）
       pubmed  get_article_metadata PMID  → 含 title
     三源都经 OpenHands create_mcp_tools 拉起 vendor 的 stdio server，真打公网 API。
  2. 与原版字段一致：rfam get_family 的返回 key 集合 ⊇ 原版核心字段
     （rfam_acc/rfam_id/description）——vendor 逻辑未改，字段本就同源。
  3. 限流生效：mcp_servers_common.pace 连发 N 次有节流（累计耗时 ≳ (N-1)*间隔）。
  4. 按需注入：问 RNA 问题 → 只有 rna 域 server 进 config（非 87 全量）；
     无关问题 → 不注入任何源。
  5. registry 完整性：domains.json 23 域全部能解析到可启动的 mcp_* server。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from open_science.datasources.launcher import LIB_DIR, launchable_servers  # noqa: E402
from open_science.datasources.registry import (  # noqa: E402
    all_domains,
    mcp_config_for,
    servers_for,
)
from open_science.datasources.inject import (  # noqa: E402
    mcp_config_for_query,
    select_domains,
)

# vendor 的 lib 放上 path，好在本进程里直接测限流基建。
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


def _tool(client, name):
    return next(t for t in client.tools if t.name == name)


def _call(client, name, args) -> str:
    t = _tool(client, name)
    return str(t(t.action_from_arguments(args)))


def check_pilot_fetch() -> bool:
    """关卡 1：试点三源经 OpenHands MCP 真实取数。"""
    from openhands.sdk import create_mcp_tools

    ok_rfam = ok_uni = ok_pub = False

    # rfam（RNA 域）
    with create_mcp_tools(mcp_config_for(["rna"]), timeout=90) as c:
        txt = _call(c, "get_family", {"family": "RF00001"})
        ok_rfam = "RF00001" in txt and "description" in txt.lower()

    # uniprot（genes-ontologies 域）
    with create_mcp_tools(mcp_config_for(["genes-ontologies"]), timeout=90) as c:
        txt = _call(c, "get_uniprot_entries", {"accessions": ["P69905"]})
        # FASTA header 以 >sp|P69905 起，或 flatfile 含 accession
        ok_uni = "P69905" in txt and (">" in txt or "sp|" in txt or "SEQUENCE" in txt.upper())

    # pubmed（pubmed 域）。NCBI etiquette 要求 contact email——operon 也读同名
    # 环境变量（Y12 sweep 去掉了硬编码默认）。测试环境若没设，给个占位；
    # 生产务必换成真实邮箱，否则 NCBI 可能限流/封禁。
    import os

    os.environ.setdefault("NCBI_EMAIL", "open-science-verify@example.org")
    with create_mcp_tools(mcp_config_for(["pubmed"]), timeout=90) as c:
        txt = _call(c, "get_article_metadata", {"pmids": ["31452104"]})
        ok_pub = "title" in txt.lower() and "is_error=True" not in txt

    ok = ok_rfam and ok_uni and ok_pub
    print(
        f"[1] pilot fetch: rfam={ok_rfam} uniprot={ok_uni} pubmed={ok_pub} "
        f"-> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def check_field_parity() -> bool:
    """关卡 2：rfam get_family 返回 ⊇ 原版核心字段集合。"""
    from openhands.sdk import create_mcp_tools

    core = {"rfam_acc", "rfam_id", "description"}
    with create_mcp_tools(mcp_config_for(["rna"]), timeout=90) as c:
        txt = _call(c, "get_family", {"family": "RF00001"}).lower()
    ok = all(f in txt for f in core)
    print(f"[2] field parity: core⊆output={ok} ({sorted(core)}) -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_ratelimit() -> bool:
    """关卡 3：mcp_servers_common.pace 连发 N 次产生节流。"""
    from mcp_servers_common.ratelimit import pace

    host = "https://verify-stage2.example.invalid"
    interval = 0.15
    n = 5
    t0 = time.perf_counter()
    for _ in range(n):
        pace(host, interval)
    elapsed = time.perf_counter() - t0
    # 首发不等待，其后 N-1 次各 ≥ interval；给点抖动余量。
    expected = (n - 1) * interval
    ok = elapsed >= expected * 0.8
    print(
        f"[3] ratelimit: {n} calls took {elapsed:.3f}s (≥~{expected:.3f}s) "
        f"-> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def check_on_demand_injection() -> bool:
    """关卡 4：RNA 问题只注入 rna 域；无关问题不注入。"""
    rna_cfg = mcp_config_for_query("给我 5S rRNA 这个 Rfam 家族的信息")
    rna_servers = set(rna_cfg["mcpServers"])
    only_rna = rna_servers == {"mcp_rna"}

    none_cfg = mcp_config_for_query("今天中午吃什么")
    none_injected = none_cfg["mcpServers"] == {}

    # 反证：不是把 87/24 全塞进去
    not_flooded = len(rna_servers) < len(launchable_servers())

    ok = only_rna and none_injected and not_flooded
    print(
        f"[4] on-demand inject: rna_only={only_rna} "
        f"unrelated_empty={none_injected} not_flooded={not_flooded} "
        f"-> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def check_registry_completeness() -> bool:
    """关卡 5：23 域全部映射到可启动的 mcp_* server。"""
    launch = set(launchable_servers())
    domains = all_domains()
    resolved = []
    for d in domains:
        srv = servers_for([d])
        resolved.append(all(s in launch for s in srv))
    ok = len(domains) == 23 and all(resolved)
    print(
        f"[5] registry: {len(domains)} domains all→launchable={all(resolved)} "
        f"-> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def main() -> int:
    # 先跑不联网的关卡（快、稳），联网关卡放后面。
    offline = [
        check_ratelimit(),
        check_on_demand_injection(),
        check_registry_completeness(),
    ]
    online = []
    try:
        online = [
            check_pilot_fetch(),
            check_field_parity(),
        ]
    except Exception as exc:  # 网络/上游问题单独标注，不误判成逻辑错
        print(f"[NET] 联网关卡异常（可能是网络/上游）: {type(exc).__name__}: {exc}")
        online = [False, False]

    results = offline + online
    passed = all(results)
    print("=" * 44)
    print("STAGE 2:", "ALL PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
