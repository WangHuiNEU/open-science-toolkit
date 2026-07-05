"""阶段 3 验证：技能 + 渐进暴露（progressive disclosure）。

运行：
    cd open-science
    PYTHONUTF8=1 python tests/verify_stage3.py

三关（对齐 docs/ROADMAP.md 阶段 3）：
  1. 菜单不撑爆：SkillLoader.menu() 每技能只有**一行 description**（不是整篇
     SKILL.md 正文）；行数 == 载入技能数；平时不触碰任何技能正文（body 未读）。
  2. 按需加载：问"帮我做一张出版级的多面板图" → search_skills 命中
     figure-composer / figure-style，且 .inject() 能取到该技能**正文**与绝对
     目录（agent 借此定位相对路径脚本）。
       —— operon 的 description 全是英文，弱大脑 + 中文 query 跨不了语言，
          loader 内置中↔英别名桥（ROADMAP line 290 认可的"匹配更准"缓解）。
  3. 未命中不注入：无关 query（"今天天气如何"）→ search_skills 返回 []，
     不把任何正文塞进 context。

附：上游资产 diffdock/SKILL.md 是二进制乱码（extracted 源即损坏，非拷贝错），
loader 跳过并记入 .skipped——本测试断言"只跳它一个"，防止静默漏掉更多技能。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from open_science.skills.loader import SkillLoader  # noqa: E402


def check_menu_not_flooded(sl: SkillLoader) -> bool:
    """关卡 1：菜单一技能一行 description，且平时不读正文。"""
    menu = sl.menu()
    lines = menu.splitlines()

    # 行数正好 == 载入技能数（无换行撑破、无技能漏行）。
    one_line_each = len(lines) == len(sl)

    # 每行都是 "- name: desc" 形状，且不含正文里才有的 markdown 标题/代码块。
    well_formed = all(l.startswith("- ") and ": " in l for l in lines)
    no_body_leak = not any(("```" in l or l.lstrip().startswith("#")) for l in lines)

    # 平时不该碰任何技能正文（progressive disclosure 的核心）。
    no_body_read = all(s._body_cache is None for s in sl._skills.values())

    # 菜单体量应远小于所有正文之和（抽样估算，防止有人把正文塞进 description）。
    menu_chars = len(menu)
    sample = list(sl._skills.values())[:5]
    body_chars = sum(len(s.body()) for s in sample)  # 这几个会被读，但仅抽样
    much_smaller = menu_chars < body_chars * 2  # 5 篇正文都比整个菜单还长

    ok = one_line_each and well_formed and no_body_leak and no_body_read and much_smaller
    print(
        f"[1] menu: lines={len(lines)}==skills={len(sl)}? {one_line_each} "
        f"well_formed={well_formed} no_body_leak={no_body_leak} "
        f"lazy_body={no_body_read} compact={much_smaller} -> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def check_on_demand_load(sl: SkillLoader) -> bool:
    """关卡 2：中文出版级配图 query 命中 figure 技能，且能注入正文+目录。"""
    query = "帮我做一张出版级的多面板图"
    hits = sl.search_skills(query)
    names = {s.name for s in hits}

    # ROADMAP 指名要命中的两个（作为 top 结果）。
    want = {"figure-composer", "figure-style"}
    hit_both = want <= names

    # 命中后 inject() 应给出正文 + 绝对目录（相对脚本靠它定位）。
    payload_ok = False
    if hit_both:
        comp = sl.get("figure-composer")
        inj = comp.inject()
        body_nonempty = len(inj["body"]) > 100  # 真的是正文，不是空壳
        dir_abs = Path(inj["dir"]).is_absolute() and Path(inj["dir"]).exists()
        payload_ok = body_nonempty and dir_abs

    ok = hit_both and payload_ok
    print(
        f"[2] on-demand load: hits={sorted(names)} want⊆hits={hit_both} "
        f"inject(body+dir)={payload_ok} -> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def check_no_hit_no_inject(sl: SkillLoader) -> bool:
    """关卡 3：无关 query 不注入任何技能。"""
    empties = []
    for q in ["今天天气如何", "帮我订一张明天去上海的高铁票", "hello there"]:
        empties.append(sl.search_skills(q) == [])
    ok = all(empties)
    print(f"[3] no-hit no-inject: all_empty={ok} -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_asset_integrity(sl: SkillLoader) -> bool:
    """附加：只跳过已知损坏的 diffdock，其余全部载入。"""
    only_diffdock = set(sl.skipped) == {"diffdock"}
    enough = len(sl) >= 28
    ok = only_diffdock and enough
    print(
        f"[+] asset integrity: loaded={len(sl)} skipped={list(sl.skipped)} "
        f"(仅 diffdock 上游损坏) -> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def main() -> int:
    sl = SkillLoader()
    results = [
        check_menu_not_flooded(sl),
        check_on_demand_load(sl),
        check_no_hit_no_inject(sl),
        check_asset_integrity(sl),
    ]
    passed = all(results)
    print("=" * 44)
    print("STAGE 3:", "ALL PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
