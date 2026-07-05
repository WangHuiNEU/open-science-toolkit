"""阶段 4 · agent 角色（profile）加载与工具裁剪。

operon 有 4 个 agent profile，各带一份 metadata.yaml：
  - OPERON      —— 通用科研 agent，全量工具（无 excluded_tools）。
  - REVIEWER    —— 转录审阅，只留 {repl, read_file, submit_output}，禁 thinking/plan/delegation/web。
  - BOOKMARKER  —— 打书签，几乎只留 submit_output。
  - ONBOARDING  —— 新用户引导，只用 ask_user，不碰代码/环境/文件/compute。

裁剪机制对齐（已核实 OpenHands SDK 1.31.0 源码）：
  operon `excluded_tools`（黑名单，operon 工具名）
    → OpenHands `Agent.filter_tools_regex`：负向前瞻正则，在 tools+MCP 解析后按
      **工具名**过滤（base.py:714-717，`pattern.match(tool.name)`）。
  operon `enable_thinking: false`
    → OpenHands `Agent.include_default_tools`：内置只有 {FinishTool, ThinkTool}
      （base.py BUILT_IN_TOOLS）；关思考就从中去掉 ThinkTool。

命名空间问题——operon 的工具名（python/bash/repl/save_artifacts…）与 OpenHands
内置名（terminal/file_editor/browser_tool_set…）不同。本层以 **operon 命名空间为
权威契约**（metadata 就是用它写的），两条实现臂：
  (a) OpenHands 内置工具：经 _OPERON_TO_OPENHANDS 映射后，进 filter_tools_regex；
  (b) 我们自建的工具（kernel=python/repl/r、host artifact=save/get、阶段 2 的 MCP
      数据源、阶段 3 的 search_skills 等）：组装工具清单时逐个问 profile.denies(name)。
两条臂都覆盖"禁代码执行"——denies('python')=True 挡自建 kernel，正则挡内置 terminal。

用法：
    profiles = AgentProfiles()            # 扫 agents_assets/
    bm = profiles.get("bookmarker")
    bm.denies("python")                   # True —— 书签 agent 调不动代码
    bm.filter_tools_regex()               # 负向前瞻，喂给 OpenHands Agent
    bm.include_default_tools()            # ['FinishTool'] —— thinking 关了
    agent = bm.build_agent(llm)           # 真造一个裁剪过的 OpenHands Agent
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import yaml

# agents_assets/ 在项目根下。本文件在 .../src/open_science/agents.py：
# parents[0]=open_science, parents[1]=src, parents[2]=项目根。
_DEFAULT_ASSETS = Path(__file__).resolve().parents[2] / "agents_assets"

# operon 工具名 → OpenHands **内置/我们注册的** 工具名。只列在 OpenHands 侧真实
# 存在、需靠 filter_tools_regex 名字过滤的那些；其余 operon 工具（save_artifacts /
# manage_* / fetch_article_fulltext / list_compute / remote_compute_* / search_skills /
# render_* 等）都是我们自建工具，靠 denies() 在组装时挡，不进正则。
#
# 已知粒度落差：operon 把 read_file 与 edit_file 分成两个工具，OpenHands 合成一个
# file_editor（读+改）。REVIEWER 留 read_file、禁 edit_file——OpenHands 无法只留
# "读"半边。故 edit_file 不映射进内置正则（否则会连 read 一起毙），edit 能力的收敛
# 在自建工具臂用 denies("edit_file") 处理（若我们自建独立 editor），或接受 file_editor
# 读改一体并在文档标注。这里选择：只映射能干净对应的内置工具。
_OPERON_TO_OPENHANDS: dict[str, tuple[str, ...]] = {
    "bash": ("terminal",),
    "web_search": ("browser_tool_set",),
    "web_fetch": ("browser_tool_set",),
}


def _to_regex_denylist(openhands_names: set[str]) -> str | None:
    """把要禁的 OpenHands 工具名做成负向前瞻正则：匹配 = 名字**不在**黑名单里。

    OpenHands 用 `pattern.match(tool.name)` 保留匹配项，所以"允许 = 匹配"。
    形如 ^(?!(?:terminal|browser_tool_set)$).*$ —— 任何不等于这些名字的工具放行。
    黑名单空 → 返回 None（不设过滤，全放行）。
    """
    if not openhands_names:
        return None
    alt = "|".join(re.escape(n) for n in sorted(openhands_names))
    return rf"^(?!(?:{alt})$).*$"


@dataclass
class AgentProfile:
    """一个 agent 角色。以 operon 命名空间为权威契约。"""

    name: str                              # 目录名（operon/reviewer/bookmarker/onboarding）
    agent_name: str                        # metadata 里的 AGENT_NAME
    description: str
    excluded_tools: frozenset[str]         # operon 命名空间的工具黑名单
    enable_thinking: bool
    enable_plan_mode: bool
    enable_subtask_delegation: bool
    enable_web_search: bool
    skills_locked: bool
    internal: bool
    max_tool_result_chars: int | None
    system_prompt: str                     # 组装好的完整系统提示
    greeting: str | None
    raw: dict = field(default_factory=dict, repr=False)

    # ── operon 命名空间的契约 ────────────────────────────────
    def denies(self, operon_tool: str) -> bool:
        """该角色是否禁用某 operon 工具（组装自建工具清单时逐个问它）。"""
        return operon_tool in self.excluded_tools

    def allows(self, operon_tool: str) -> bool:
        return not self.denies(operon_tool)

    # ── OpenHands 侧实现臂 ──────────────────────────────────
    def _openhands_denylist(self) -> set[str]:
        """把 operon 黑名单里能映射到 OpenHands 内置名的那些收集起来。"""
        out: set[str] = set()
        for t in self.excluded_tools:
            out.update(_OPERON_TO_OPENHANDS.get(t, ()))
        # skills_locked → 连技能调用工具一起禁（OpenHands 侧若注册为 InvokeSkillTool）。
        if self.skills_locked:
            out.add("InvokeSkillTool")
        return out

    def filter_tools_regex(self) -> str | None:
        """喂给 OpenHands Agent(filter_tools_regex=...) 的负向前瞻正则。"""
        return _to_regex_denylist(self._openhands_denylist())

    def include_default_tools(self) -> list[str]:
        """OpenHands 内置工具白名单。enable_thinking:false → 去掉 ThinkTool。"""
        tools = ["FinishTool", "ThinkTool"]
        if not self.enable_thinking:
            tools.remove("ThinkTool")
        return tools

    def build_agent(self, llm, *, mcp_config: dict | None = None, tools: list | None = None):
        """据本 profile 造一个裁剪过的 OpenHands Agent。

        llm: openhands.sdk.LLM。tools: 额外的自建工具 spec 列表（调用方应已用
        denies() 过滤过）。延迟 import，避免非 agent 场景强依赖 SDK。
        """
        from openhands.sdk import Agent

        kwargs = dict(
            llm=llm,
            include_default_tools=self.include_default_tools(),
            system_prompt=self.system_prompt,
        )
        rgx = self.filter_tools_regex()
        if rgx is not None:
            kwargs["filter_tools_regex"] = rgx
        if mcp_config is not None:
            kwargs["mcp_config"] = mcp_config
        if tools is not None:
            kwargs["tools"] = tools
        return Agent(**kwargs)


def _bool(d: dict, key: str, default: bool) -> bool:
    v = d.get(key, default)
    return bool(v)


def _assemble_prompt(meta: dict) -> str:
    """operon = identity_prompt + working_style_prompt；其余 = system_prompt。"""
    if meta.get("system_prompt"):
        return meta["system_prompt"].strip()
    ident = (meta.get("identity_prompt") or "").strip()
    style = (meta.get("working_style_prompt") or "").strip()
    return (ident + "\n\n" + style).strip() if (ident or style) else ""


class AgentProfiles:
    """扫 agents_assets/，把每份 metadata.yaml 解析成 AgentProfile。"""

    def __init__(self, assets_dir: str | Path | None = None) -> None:
        self.assets_dir = Path(assets_dir) if assets_dir else _DEFAULT_ASSETS
        self._profiles: dict[str, AgentProfile] = {}
        self._load()

    def _load(self) -> None:
        for meta_path in sorted(self.assets_dir.glob("*/metadata.yaml")):
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
            name = meta_path.parent.name
            excluded = frozenset(meta.get("excluded_tools") or [])
            mtr = meta.get("max_tool_result_chars")
            self._profiles[name] = AgentProfile(
                name=name,
                agent_name=meta.get("agent_name", name.upper()),
                description=(meta.get("description") or "").strip(),
                excluded_tools=excluded,
                # 默认值取"能力最全"一侧；trimmed agent 在 metadata 里显式关掉。
                enable_thinking=_bool(meta, "enable_thinking", True),
                enable_plan_mode=_bool(meta, "enable_plan_mode", True),
                enable_subtask_delegation=_bool(meta, "enable_subtask_delegation", True),
                enable_web_search=_bool(meta, "enable_web_search", True),
                skills_locked=_bool(meta, "skills_locked", False),
                internal=_bool(meta, "internal", False),
                max_tool_result_chars=int(mtr) if mtr else None,
                system_prompt=_assemble_prompt(meta),
                greeting=(meta.get("greeting") or None),
                raw=meta,
            )

    def __len__(self) -> int:
        return len(self._profiles)

    def names(self) -> list[str]:
        return sorted(self._profiles)

    def get(self, name: str) -> AgentProfile | None:
        return self._profiles.get(name)

    @cached_property
    def operon(self) -> AgentProfile | None:
        return self._profiles.get("operon")


__all__ = ["AgentProfile", "AgentProfiles"]
