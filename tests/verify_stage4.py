"""阶段 4 验证：4 个 agent 角色 + 工具裁剪（AgentSettings 对齐）。

运行：
    cd open-science
    OPENHANDS_SUPPRESS_BANNER=1 PYTHONUTF8=1 python tests/verify_stage4.py

五关（对齐 docs/ROADMAP.md 阶段 4，核心关卡＝"bookmarker 调不动 python/bash"）：
  1. 四角色齐备：operon/reviewer/bookmarker/onboarding 都能从 verbatim metadata 解析。
  2. 核心裁剪（ROADMAP 指名）：bookmarker + onboarding 在 operon 命名空间 denies
     python/bash/repl；reviewer denies python/bash 但**保留 repl**（其 metadata 只排除
     python/bash/r，repl 是它唯一的 SDK 通道）。
  3. 真过滤生效：把每个 profile 的 filter_tools_regex 按 OpenHands 源码同款
     （`pattern.match(tool.name)`）作用到**真实注册**的 OpenHands 工具名上——
     裁剪 agent 的 `terminal`（=bash 执行工具）被真正滤掉；operon 全保留。
  4. thinking 开关：enable_thinking:false 的三个角色 include_default_tools 不含
     ThinkTool；operon 含。
  5. 真造 Agent：build_agent(llm) 对四角色都产出合法 OpenHands Agent，且其
     filter_tools_regex / include_default_tools 与 profile 声明一致。

设计说明：operon 的 read_file/edit_file 在 OpenHands 合成一个 file_editor（读改一体），
无法只留读半边——本关卡不因此判失败，只在关 2 检查 operon 命名空间契约（denies
edit_file 为真），file_editor 的读改一体落差在 agents.py 文档中已标注。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from open_science.agents import AgentProfiles  # noqa: E402

EXPECTED = {"operon", "reviewer", "bookmarker", "onboarding"}


def _apply_regex(regex: str | None, tool_names: list[str]) -> list[str]:
    """完全照 OpenHands base.py:714-716 的语义：正则匹配 = 保留。"""
    if regex is None:
        return list(tool_names)
    pat = re.compile(regex)
    return [t for t in tool_names if pat.match(t)]


def check_roster(p: AgentProfiles) -> bool:
    ok = set(p.names()) == EXPECTED
    print(f"[1] roster: {p.names()} == 4 expected -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_core_trim(p: AgentProfiles) -> bool:
    """ROADMAP 核心关：bookmarker/onboarding 调不动代码；reviewer 留 repl。"""
    bm, ob, rv, op = (p.get(n) for n in ("bookmarker", "onboarding", "reviewer", "operon"))

    bm_ok = bm.denies("python") and bm.denies("bash") and bm.denies("repl")
    ob_ok = ob.denies("python") and ob.denies("bash") and ob.denies("repl")
    # reviewer：禁 python/bash，但 repl 是它保留的唯一 SDK 通道。
    rv_ok = rv.denies("python") and rv.denies("bash") and rv.allows("repl")
    # operon：全放行。
    op_ok = op.allows("python") and op.allows("bash") and op.allows("repl")

    ok = bm_ok and ob_ok and rv_ok and op_ok
    print(
        f"[2] core trim: bookmarker_no_code={bm_ok} onboarding_no_code={ob_ok} "
        f"reviewer(no py/bash, keeps repl)={rv_ok} operon_full={op_ok} "
        f"-> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def check_real_filter(p: AgentProfiles) -> bool:
    """关 3：真实注册工具名 + 各 profile 正则，terminal(=bash) 该滤的被滤掉。"""
    from openhands.tools import register_default_tools
    from openhands.sdk import list_registered_tools

    register_default_tools()
    real = list(list_registered_tools())  # 真实内置：terminal/file_editor/browser_tool_set...
    # 混入我们自建工具名，模拟解析后的完整工具集。
    resolved = real + ["get_family", "search_skills", "submit_output"]

    assert "terminal" in real, f"没找到 terminal 内置工具: {real}"

    results = {}
    for n in ("operon", "reviewer", "bookmarker", "onboarding"):
        a = p.get(n)
        kept = _apply_regex(a.filter_tools_regex(), resolved)
        results[n] = "terminal" not in kept

    # operon 必须保留 terminal；三个裁剪角色必须滤掉。
    ok = (
        ("terminal" in _apply_regex(p.get("operon").filter_tools_regex(), resolved))
        and results["reviewer"]
        and results["bookmarker"]
        and results["onboarding"]
    )
    print(
        f"[3] real filter: operon_keeps_terminal={not results['operon']} "
        f"trimmed_drop_terminal(rv={results['reviewer']},bm={results['bookmarker']},"
        f"ob={results['onboarding']}) -> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def check_thinking(p: AgentProfiles) -> bool:
    """关 4：enable_thinking:false → include_default_tools 无 ThinkTool。"""
    op = "ThinkTool" in p.get("operon").include_default_tools()
    trimmed = all(
        "ThinkTool" not in p.get(n).include_default_tools()
        for n in ("reviewer", "bookmarker", "onboarding")
    )
    ok = op and trimmed
    print(
        f"[4] thinking: operon_has_think={op} trimmed_no_think={trimmed} "
        f"-> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def check_build_agent(p: AgentProfiles) -> bool:
    """关 5：四角色都能真造出 OpenHands Agent，字段与声明一致。"""
    from openhands.sdk import LLM
    from pydantic import SecretStr

    llm = LLM(
        model="openai/dummy",
        api_key=SecretStr("verify-only"),
        base_url="http://localhost:1",
        usage_id="verify-stage4",
    )
    all_ok = True
    for n in ("operon", "reviewer", "bookmarker", "onboarding"):
        a = p.get(n)
        try:
            ag = a.build_agent(llm)
        except Exception as exc:  # noqa: BLE001
            print(f"    build {n} FAIL: {type(exc).__name__}: {exc}")
            all_ok = False
            continue
        match = (
            ag.filter_tools_regex == a.filter_tools_regex()
            and list(ag.include_default_tools) == a.include_default_tools()
        )
        all_ok = all_ok and match
    print(f"[5] build_agent: all 4 built & fields match -> {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def main() -> int:
    p = AgentProfiles()
    results = [
        check_roster(p),
        check_core_trim(p),
        check_real_filter(p),
        check_thinking(p),
        check_build_agent(p),
    ]
    passed = all(results)
    print("=" * 44)
    print("STAGE 4:", "ALL PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
