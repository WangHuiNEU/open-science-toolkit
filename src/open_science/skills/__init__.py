"""阶段 3 · 技能 + 渐进暴露（progressive disclosure）。

operon 机制：平时只把每个技能的一行 `description` 放进 context（技能菜单），
`search_skills(query)` 命中后才把该 SKILL.md **正文**注入。这样 29（乃至更多）
技能不会一次性撑爆 context。本层照搬这套：

    from open_science.skills.loader import SkillLoader
    sl = SkillLoader()                       # 扫 skills_assets/，只读 frontmatter
    print(sl.menu())                         # 29 行 description（平时喂给 agent）
    hits = sl.search_skills("多面板出版级图")  # 命中 → 返回带正文的 Skill
"""
