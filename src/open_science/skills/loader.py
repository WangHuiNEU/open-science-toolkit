"""skill loader —— frontmatter 索引 + description 菜单 + search_skills 注入正文。

对齐 operon 的 progressive disclosure：
  - 启动时只解析每个 SKILL.md 的 YAML frontmatter，暴露一行 description（菜单）。
  - search_skills(query) 关键词打分命中后，才 lazy 读该技能的**正文**注入 context。
  - 带脚本的技能，正文里引用的是相对路径（如 `python protein_mpnn_run.py`），
    所以注入时同时给出该技能的绝对目录 dir，让 agent 能定位脚本。

刻意不做重的语义向量检索——保持与 operon 一致的轻量关键词匹配，稳定可测；
上层若要接 embedding，可在 search_skills 外面再包一层。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import yaml

# skills_assets/ 在项目根下（src 的上一级）。
_DEFAULT_ASSETS = Path(__file__).resolve().parents[3] / "skills_assets"

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WORD = re.compile(r"[a-z0-9]+")

# 中↔英 别名桥：operon 的 SKILL.md description 全是英文，而弱大脑 + 中文 query
# 时纯关键词匹配跨不了语言。这是 ROADMAP 风险清单（line 290）明确认可的缓解
# 手段——"把 search_skills 匹配更准"。query 预处理时把这些中文词扩展成英文
# 关键词，再参与打分。只放高价值、低歧义的词。
_QUERY_ALIASES: dict[str, str] = {
    "图": "figure plot",
    "多面板": "multi panel figure",
    "出版级": "publication grade figure",
    "配图": "figure",
    "蛋白": "protein",
    "序列": "sequence",
    "反向折叠": "inverse fold",
    "折叠": "fold structure",
    "结构": "structure",
    "对接": "docking",
    "文献": "literature paper",
    "综述": "literature review",
    "论文": "paper narrative manuscript",
    "叙事": "narrative",
    "会话": "session",
    "令牌": "token",
    "用量": "usage cost",
    "溯源": "self awareness provenance",
    "远程": "remote compute",
    "算力": "compute",
    "端点": "endpoint",
}


def _expand_aliases(text: str) -> str:
    extra = [en for zh, en in _QUERY_ALIASES.items() if zh in text]
    return text + " " + " ".join(extra) if extra else text


# 英文停用词：无信息量却会误命中（如 description 里的 "there"/"can"/"run"）。
# 打分前从 query 与索引双侧剔除，保证"无关 query 不注入"。
_STOPWORDS = frozenset(
    """a an and are as at be by can do for from have how i in is it of on or so that the
    their there they this to up us use used using want with you your me my we our""".split()
)


def _tokens(text: str) -> list[str]:
    """英文按词、中文按字，混合切分（关键词匹配用）；剔除英文停用词。"""
    text = text.lower()
    toks = [w for w in _WORD.findall(text) if w not in _STOPWORDS]
    toks += re.findall(r"[一-鿿]", text)  # 每个汉字单独成 token
    return toks


@dataclass
class Skill:
    """一个技能。平时只用到 name/description/dir；正文 lazy 读。"""

    name: str
    description: str
    dir: Path
    category: str | None = None
    metadata: dict = field(default_factory=dict)
    _body_cache: str | None = field(default=None, repr=False, compare=False)

    @property
    def skill_md(self) -> Path:
        return self.dir / "SKILL.md"

    def body(self) -> str:
        """SKILL.md 去掉 frontmatter 后的正文（命中才读）。"""
        if self._body_cache is None:
            raw = self.skill_md.read_text(encoding="utf-8")
            self._body_cache = _FRONTMATTER.sub("", raw, count=1).strip()
        return self._body_cache

    def inject(self) -> dict:
        """命中后注入 context 的载荷：正文 + 绝对目录（定位脚本）。"""
        return {
            "name": self.name,
            "dir": str(self.dir),
            "body": self.body(),
        }

    def menu_line(self) -> str:
        # description 可能含换行（YAML 折叠/多行块）——压成一行，保证
        # "一技能一行" 的菜单不虚胖。
        desc = " ".join(self.description.split())
        return f"- {self.name}: {desc}"


class SkillLoader:
    """扫 skills_assets/，建 description 索引，提供菜单 + search_skills。"""

    def __init__(self, assets_dir: str | Path | None = None) -> None:
        self.assets_dir = Path(assets_dir) if assets_dir else _DEFAULT_ASSETS
        self._skills: dict[str, Skill] = {}
        self.skipped: dict[str, str] = {}  # 目录名 → 跳过原因（如上游资产损坏）
        self._load()

    def _load(self) -> None:
        for skill_md in sorted(self.assets_dir.glob("*/SKILL.md")):
            try:
                raw = skill_md.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                # 上游资产损坏（如 diffdock/SKILL.md 是二进制乱码）——跳过并记录，
                # 不让一个坏文件搞垮整个菜单。
                self.skipped[skill_md.parent.name] = f"{type(exc).__name__}: {exc}"
                continue
            m = _FRONTMATTER.match(raw)
            if not m:
                self.skipped[skill_md.parent.name] = "无 YAML frontmatter"
                continue
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError as exc:
                self.skipped[skill_md.parent.name] = f"frontmatter 解析失败: {exc}"
                continue
            name = fm.get("name") or skill_md.parent.name
            desc = (fm.get("description") or "").strip()
            self._skills[name] = Skill(
                name=name,
                description=desc,
                dir=skill_md.parent,
                category=fm.get("category"),
                metadata=fm.get("metadata") or {},
            )

    # ── 平时暴露：菜单 ──────────────────────────────────────
    def __len__(self) -> int:
        return len(self._skills)

    def names(self) -> list[str]:
        return sorted(self._skills)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def menu(self) -> str:
        """一行一技能的 description 菜单（平时喂给 agent，不含正文）。"""
        return "\n".join(s.menu_line() for s in self._sorted())

    def _sorted(self) -> list[Skill]:
        return [self._skills[n] for n in sorted(self._skills)]

    @cached_property
    def _index(self) -> dict[str, set[str]]:
        """name → (name+description) 的 token 集合，供匹配打分。"""
        idx = {}
        for s in self._skills.values():
            idx[s.name] = set(_tokens(f"{s.name} {s.description}"))
        return idx

    # ── 命中才注入：search_skills ───────────────────────────
    def search_skills(self, query: str, *, top_k: int = 3, min_score: int = 1) -> list[Skill]:
        """关键词打分匹配，返回命中的技能（含可注入正文），按分降序。

        打分 = query token 命中该技能 (name+description) token 的个数，
        技能名整体作为短语命中额外加权（避免"figure"泛化误伤）。
        min_score=1 时至少要命中一个词，未命中返回 []。
        """
        expanded = _expand_aliases(query)
        q_tokens = set(_tokens(expanded))
        q_lower = expanded.lower()
        scored: list[tuple[int, Skill]] = []
        for s in self._skills.values():
            score = len(q_tokens & self._index[s.name])
            if s.name.lower() in q_lower or s.name.replace("-", " ") in q_lower:
                score += 3
            if score >= min_score:
                scored.append((score, s))
        scored.sort(key=lambda t: (-t[0], t[1].name))
        return [s for _, s in scored[:top_k]]


__all__ = ["Skill", "SkillLoader"]
