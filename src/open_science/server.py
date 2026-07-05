"""B1 · Web 接入层 —— 把咱们的大脑 + 12 技能 + operon agent 接进官方 agent-server。

operon 的运行时是闭源二进制；OpenHands 的 `openhands-agent-server` 是 MIT 的
FastAPI REST/WebSocket 服务，天然带 `/docs` 交互面板。本模块做三件事，且**只做
装配**（不改 agent-server 源）：

  1. make_llm()            —— 从 .env（LLM_BASE_URL/LLM_MODEL/LLM_API_KEY）造一个
                              openhands.sdk.LLM（金山云 OpenAI 兼容端点，model 加
                              `openai/` 前缀，凭据只走环境变量）。
  2. build_operon_agent()  —— 复用阶段 4 的 AgentProfiles.get("operon").build_agent，
                              把阶段 3 的 12 模型技能菜单拼进 system_prompt，按 query
                              命中阶段 2 的数据源域挂 MCP。产物就是 agent-server
                              StartConversationRequest 里那个 inline `agent: AgentBase`。
  3. build_start_request() / seed_conversation()
                           —— 造一个 StartConversationRequest（inline agent +
                              LocalWorkspace + 首条消息），POST 到运行中的 server。
                              用户在浏览器 http://localhost:8000/docs 就能自己发。

启动（一条命令，见 scripts/serve.py 或 `python -m open_science.server --serve`）：
  Config 走 OH_* 环境变量（agent-server 的 load_config 读它们），我们只设 workspace
  路径、关掉 VNC。LLM 不在 server Config 里——它活在**每个会话的 agent 内部**，
  所以正确的接法是 inline agent，而不是给 server 配一个全局 LLM。
"""

from __future__ import annotations

import os
from pathlib import Path

from .agents import AgentProfiles
from .datasources.inject import mcp_config_for_query
from .skills.loader import SkillLoader

# 项目根（.../src/open_science/server.py → parents[2]）。
_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_WORKSPACE = _ROOT / "workspace"
# 自包含聊天页目录（不依赖任何国外 CDN，纯本地静态资源）。
_WEB_DIR = Path(__file__).resolve().parent / "web"

# 装配好的 FastAPI app（供 uvicorn 直接吃）。见 build_app()。
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


# ── 大脑 → OpenHands LLM ────────────────────────────────────────────
def make_llm(
    *,
    usage_id: str = "luca-brain",
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
):
    """造 openhands.sdk.LLM。凭据默认从 .env 读，绝不硬编码。

    与 brain.py 同源（同三个变量），只是换成 OpenHands 的 LLM 类（底层 LiteLLM），
    model 按 .env.example 说明加 `openai/` 前缀走 OpenAI 兼容协议。

    base_url/model/api_key: 用户在网页「API 设置」里填的覆盖值（每会话临时生效，
    不落盘、不写 .env）。任一为空则回落到 .env 对应变量，默认零配置也能跑。
    """
    from dotenv import load_dotenv
    from openhands.sdk import LLM
    from pydantic import SecretStr

    load_dotenv(_ROOT / ".env")
    base_url = (base_url or os.environ.get("LLM_BASE_URL", "")).strip()
    model = (model or os.environ.get("LLM_MODEL", "")).strip()
    api_key = (api_key or os.environ.get("LLM_API_KEY", "")).strip()
    if not (base_url and model and api_key):
        raise RuntimeError(
            "缺少 LLM 配置：请在网页右上「API 设置」里填 base_url / model / api_key，"
            "或在 .env 里配好 LLM_BASE_URL / LLM_MODEL / LLM_API_KEY。"
        )
    # 已带 provider 前缀就不重复加（openai/、litellm_proxy/ 等）。
    if "/" not in model:
        model = f"openai/{model}"
    return LLM(
        model=model,
        base_url=base_url,
        api_key=SecretStr(api_key),
        usage_id=usage_id,
    )


# ── 技能菜单 → 拼进 system_prompt ───────────────────────────────────
def _skills_menu_block(loader: SkillLoader) -> str:
    """把技能 description 菜单包成一段 system_prompt 附录（= operon 平时暴露的菜单）。

    只喂一行一技能的 description（progressive disclosure），正文由 search_skills
    命中才注入——这里不塞正文，保持 context 轻。
    """
    menu = loader.menu()
    return (
        "\n\n## Available skills (progressive disclosure)\n"
        "以下技能平时只暴露一行描述；需要某技能时，按其名调用 search_skills "
        "载入正文与脚本目录后再执行。生物模型技能（biomodels）跑开源权重，"
        "遵循各自 SKILL.md。\n\n" + menu
    )


# ── operon agent（inline，喂给 StartConversationRequest.agent）─────────
def build_operon_agent(
    llm=None,
    *,
    profile: str = "operon",
    query: str | None = None,
    with_skills_menu: bool = True,
    fallback_all_mcp: bool = False,
    llm_settings: dict | None = None,
):
    """造一个可直接 inline 进会话的 OpenHands Agent（大脑 + 技能 + 按需 MCP）。

    llm            : 不给则 make_llm() 从 .env（或 llm_settings 覆盖）造。
    profile        : 4 个角色之一（operon/reviewer/bookmarker/onboarding）。
    query          : 首条问题；命中阶段 2 的数据源域就只挂那些 MCP server
                     （渐进暴露，不全量撑爆）。None → 不挂 MCP。
    with_skills_menu: 把 12+ 技能菜单拼进 system_prompt。
    fallback_all_mcp: query 没命中任何域时是否挂全域（默认否，宁缺勿滥）。
    llm_settings   : 用户网页「API 设置」传来的 {base_url, model, api_key} 覆盖，
                     空则回落 .env。凭据只在进程内用于造 LLM，不落盘。
    """
    llm = llm or make_llm(**(llm_settings or {}))
    profiles = AgentProfiles()
    prof = profiles.get(profile)
    if prof is None:
        raise KeyError(f"未知 agent profile: {profile}；可用 {profiles.names()}")

    # 技能菜单拼进系统提示（不动 profile 对象，临时造一份加了菜单的）。
    system_prompt = prof.system_prompt
    if with_skills_menu and not prof.skills_locked:
        system_prompt = system_prompt + _skills_menu_block(SkillLoader())

    # 按 query 选数据源域 → MCPConfig（未命中且不 fallback 则为空，不挂）。
    mcp_config = None
    if query:
        cfg = mcp_config_for_query(query, fallback_all=fallback_all_mcp)
        if cfg.get("mcpServers"):
            mcp_config = cfg

    # build_agent 只认 profile.system_prompt；这里临时替换后造，再还原。
    original = prof.system_prompt
    try:
        prof.system_prompt = system_prompt
        return prof.build_agent(llm, mcp_config=mcp_config)
    finally:
        prof.system_prompt = original


# ── 会话请求（inline agent + LocalWorkspace + 首条消息）────────────────
def build_start_request(
    message: str,
    *,
    profile: str = "operon",
    working_dir: str | Path | None = None,
    llm=None,
    max_iterations: int = 500,
    run: bool = True,
    llm_settings: dict | None = None,
):
    """造一个 StartConversationRequest —— 就是 POST /api/conversations 的 body。

    message      : 首条用户消息（也用于按需选数据源域）。
    working_dir  : agent 的工作目录（LocalWorkspace），默认 workspace/project。
    run          : True → 建会话即后台跑（对应 SendMessageRequest.run）。
    llm_settings : 用户网页「API 设置」传来的 {base_url, model, api_key} 覆盖。
    """
    from openhands.agent_server.models import (
        SendMessageRequest,
        StartConversationRequest,
    )
    from openhands.sdk import TextContent
    from openhands.sdk.workspace.local import LocalWorkspace

    wd = Path(working_dir) if working_dir else (_DEFAULT_WORKSPACE / "project")
    wd.mkdir(parents=True, exist_ok=True)

    agent = build_operon_agent(
        llm, profile=profile, query=message, llm_settings=llm_settings
    )
    return StartConversationRequest(
        workspace=LocalWorkspace(working_dir=str(wd)),
        agent=agent,
        max_iterations=max_iterations,
        initial_message=SendMessageRequest(
            role="user",
            content=[TextContent(text=message)],
            run=run,
        ),
    )


def seed_conversation(
    message: str,
    *,
    base_url: str = f"http://127.0.0.1:{DEFAULT_PORT}",
    profile: str = "operon",
    working_dir: str | Path | None = None,
    session_api_key: str | None = None,
    timeout: float = 60.0,
    llm_settings: dict | None = None,
) -> dict:
    """把一条会话 POST 到**运行中**的 agent-server，返回 ConversationInfo(JSON)。

    便捷入口：起好 server 后，`python -m open_science.server --ask "..."` 就能
    建一个跑起来的会话，再去 /docs 看事件流 / 拉 agent_final_response。

    llm_settings：用户网页「API 设置」传来的 {base_url, model, api_key} 覆盖。
    """
    import httpx

    req = build_start_request(
        message, profile=profile, working_dir=working_dir, llm_settings=llm_settings
    )
    headers = {}
    key = session_api_key or os.environ.get("OH_SESSION_API_KEYS_0")
    if key:
        headers["X-Session-API-Key"] = key
    # expose_secrets：默认 dump 会把 LLM.api_key 掩成 "**********"，POST 过去 server
    # 无法认证。本地可信回环，按 SDK 设计的 context 开关放出真实 key（key 本就在
    # .env，只经 localhost 到自家 server，不落任何提交文件）。
    body = req.model_dump(mode="json", context={"expose_secrets": True})
    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        resp = client.post("/api/conversations", json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


# ── 聊天页 + 服务端 /chat/send（api_key 只在进程内，浏览器永远拿不到）──
def build_app():
    """造「官方 agent-server + 咱们的聊天页」的合体 app（不改 agent-server 源）。

    要点：不能用 module-level 的 `api`——它在 import 时就 `create_app()` 过、`/`
    已绑给 server_info，后加的 `/` 会被它遮住。改为：先把静态目录写进
    `OH_STATIC_FILES_PATH`（agent-server 官方的静态挂载入口），再**重新**
    `create_app()`——它会自动把 `/static` 挂上、并让 `/` 302 到我们的 index.html。
    然后只补一个建会话的便捷路由：

      POST /chat/send  → 服务端造 StartConversationRequest（LLM api_key 只在进程内，
                         经内部回环 POST 给 agent-server），回 {conversation_id}

    读事件 / 拉最终答案，浏览器直接打 agent-server 现成的只读端点。
    """
    import asyncio

    from fastapi import Body
    from fastapi.responses import JSONResponse
    from openhands.agent_server.api import create_app
    from openhands.agent_server.config import load_config

    # 让官方 _setup_static_files 挂上咱们的聊天页（/ → /static/index.html）。
    # 注意：import api 时 module-level `api = create_app()` 已把默认 config 缓存
    # （不含静态路径），所以不能靠 get_default_config()；这里设好 env 后**显式**
    # load_config() 现造一份带 static_files_path 的 config 传进去。
    os.environ["OH_STATIC_FILES_PATH"] = str(_WEB_DIR)
    config = load_config()
    app = create_app(config)

    @app.post("/chat/send", tags=["Open Science"])
    async def _chat_send(payload: dict = Body(...)):
        """浏览器发一句话 → 服务端建一个 inline-operon 会话并跑起来。

        body: {"message": "...", "profile": "operon",
               "llm_settings"?: {"base_url", "model", "api_key"}}。
        「API 设置」里填的三个值随请求带上，只在本进程内用于造 LLM、经内部回环
        POST，浏览器/日志都不落密钥；任一为空则回落 .env。seed_conversation 是同步
        httpx，会阻塞；丢线程池跑，别把事件循环堵死（否则它内部那条 POST 排不上号
        → 死锁）。
        """
        payload = payload or {}
        message = (payload.get("message") or "").strip()
        profile = payload.get("profile") or "operon"
        if not message:
            return JSONResponse({"detail": "message 不能为空"}, status_code=400)
        # 兼容两种传法：顶层 base_url/model/api_key，或嵌套 llm_settings。
        raw = payload.get("llm_settings") or payload
        llm_settings = {
            k: (raw.get(k) or "").strip()
            for k in ("base_url", "model", "api_key")
            if (raw.get(k) or "").strip()
        } or None
        try:
            info = await asyncio.to_thread(
                seed_conversation,
                message,
                base_url=_self_base_url(),
                profile=profile,
                llm_settings=llm_settings,
            )
        except RuntimeError as e:
            # make_llm 缺配置：把中文提示原样回给前端弹「API 设置」。
            return JSONResponse({"detail": str(e)}, status_code=400)
        cid = info.get("id") or info.get("conversation_id")
        return {"conversation_id": cid}

    return app


# 服务端自呼地址（/chat/send 内部回环到本进程的 agent-server）。
_SELF_PORT = DEFAULT_PORT


def _self_base_url() -> str:
    return f"http://127.0.0.1:{_SELF_PORT}"


# ── 启动配置（OH_* 环境变量，agent-server 的 load_config 读）──────────
def apply_server_env(*, workspace: str | Path | None = None, port: int = DEFAULT_PORT) -> None:
    """设好 agent-server 需要的 OH_* 环境变量（在起 uvicorn 前调）。

    只碰服务级配置：workspace 路径、关 VNC/浏览器重活。LLM 不在这里——它在
    每个会话的 inline agent 内部。
    """
    ws = Path(workspace) if workspace else _DEFAULT_WORKSPACE
    (ws / "conversations").mkdir(parents=True, exist_ok=True)
    (ws / "project").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("OH_WORKSPACE_PATH", str(ws / "project"))
    os.environ.setdefault("OH_CONVERSATIONS_PATH", str(ws / "conversations"))
    os.environ.setdefault("OH_ENABLE_VNC", "false")
    # Windows + 无显示环境：别在启动时探浏览器。
    os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")
    os.environ.setdefault("PYTHONUTF8", "1")


def serve(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, workspace: str | Path | None = None) -> None:
    """一条命令起服务：配好 env → uvicorn 跑「官方 app + 咱们的聊天页」。

    浏览器打开 http://localhost:{port}/  就是聊天界面（纯本地，无外部 CDN）；
    http://localhost:{port}/docs 仍是原来的 API 面板。
    """
    import uvicorn

    global _SELF_PORT
    _SELF_PORT = port
    apply_server_env(workspace=workspace, port=port)
    app = build_app()
    print(f"Open Science · Luca → 聊天界面 http://{host}:{port}/   （API 面板 /docs）")
    print("  大脑：", os.environ.get("LLM_BASE_URL", "(未配 .env)"))
    uvicorn.run(app, host=host, port=port, ws="wsproto")


def _ensure_utf8_runtime() -> None:
    """Windows 默认 GBK：agent-server 把含 emoji/中文的会话状态写盘时会
    `UnicodeEncodeError` 崩（🎉 GBK 编不了）→ 建会话 500。

    UTF-8 模式是解释器**启动时**定的，进程内改 os.environ 对自己无效，只能
    带 `-X utf8` 重新 exec 自己一次。用一个环境标记防止无限重启。
    """
    import sys

    if sys.flags.utf8_mode or os.environ.get("_OS_UTF8_REEXEC") == "1":
        return
    # 非 UTF-8 模式 → 带 -X utf8 重启自己，把原参数原样带上。
    os.environ["_OS_UTF8_REEXEC"] = "1"
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.execv(sys.executable, [sys.executable, "-X", "utf8", "-m", "open_science.server", *sys.argv[1:]])


def _cli() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Open Science B1 · operon agent server")
    p.add_argument("--serve", action="store_true", help="起 agent-server（/docs 可交互）")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--workspace", default=None)
    p.add_argument("--ask", metavar="MESSAGE", help="向运行中的 server 建一个会话并跑起来")
    p.add_argument("--profile", default="operon")
    args = p.parse_args()

    if args.ask:
        info = seed_conversation(
            args.ask,
            base_url=f"http://127.0.0.1:{args.port}",
            profile=args.profile,
            working_dir=args.workspace,
        )
        cid = info.get("id") or info.get("conversation_id")
        print("conversation created:", cid)
        print(f"  事件流 / 结果见 http://127.0.0.1:{args.port}/docs")
        return 0
    if args.serve:
        serve(host=args.host, port=args.port, workspace=args.workspace)
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    _ensure_utf8_runtime()
    raise SystemExit(_cli())
