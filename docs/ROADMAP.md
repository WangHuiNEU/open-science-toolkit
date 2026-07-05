# ROADMAP —— Open Science 分阶段施工图

本文件是施工图：每阶段的**产出文件清单**、**关键命令**、**验证脚本**。
配合根目录 [README.md](../README.md) 阅读。总工期约 3 个月（单人），阶段 2 最耗时。

- 资产源：`../extracted/`（只读参照，别改它）
- 代码根：`X:\claude_science\open-science\`（下称 `$ROOT`）
- 大脑：OpenAI 兼容端点，key 走环境变量 `LLM_API_KEY`，端点走 `LLM_BASE_URL` / `LLM_MODEL`
- 沙箱：阶段 0–4 用 `LocalWorkspace`（无 Docker），阶段 5 用 `RemoteAPIWorkspace`

## 目标目录结构（完工时）

```
open-science/
├── README.md
├── docs/
│   ├── ROADMAP.md              ← 本文件
│   └── VERIFY.md               ← 各阶段验证清单汇总（阶段推进时补）
├── .env.example                ← 环境变量模板（key 不入库）
├── pyproject.toml
├── src/open_science/
│   ├── brain.py                ← LLM 封装（LiteLLM / OpenAI 兼容）
│   ├── runtime.py              ← OpenHands Workspace + kernel 封装
│   ├── provenance/             ← 阶段 1：溯源 DB + MCP
│   │   ├── schema.sql
│   │   └── server.py
│   ├── datasources/            ← 阶段 2：87 源包装
│   │   ├── common/             ← 搬 mcp_servers_common
│   │   └── <每个源>/
│   ├── skills/                 ← 阶段 3：skill loader
│   │   └── loader.py
│   └── agents/                 ← 阶段 4：4 份 AgentSettings
│       ├── operon.py
│       ├── reviewer.py
│       ├── bookmarker.py
│       └── onboarding.py
├── skills_assets/              ← 从 ../extracted/skills 拷入的 29 SKILL.md
├── tests/                      ← 各阶段验证脚本
│   ├── verify_stage0.py
│   ├── verify_stage1.py
│   ├── verify_stage2.py
│   ├── verify_stage3.py
│   ├── verify_stage4.py
│   └── verify_stage5.py
└── config.toml                 ← OpenHands 应用模式配置（可选）
```

---

# 阶段 0 · 地基（1 周）

**目标**：装好 OpenHands，接通大脑，验证有状态 kernel。这一阶段不碰任何资产，只证明"底座能转"。

## 产出文件
- `pyproject.toml`（依赖：`openhands-sdk` 或 `openhands-ai`、`litellm`、`python-dotenv`）
- `.env.example` + 本地 `.env`（`.env` 加入 `.gitignore`，永不提交）
- `src/open_science/brain.py` —— LLM 封装
- `src/open_science/runtime.py` —— LocalWorkspace + kernel 封装
- `tests/verify_stage0.py`

## .env.example
```bash
# 大脑端点（OpenAI 兼容）。真实值写进 .env，勿提交
LLM_BASE_URL=https://kspmas.ksyun.com/v1
LLM_MODEL=openai/ep-20260613040107-bimti
LLM_API_KEY=__在_.env_里填_勿入库__
```

## 关键命令
```bash
cd "$ROOT"
python -m venv .venv && source .venv/bin/activate
pip install openhands-sdk litellm python-dotenv   # 包名以 OpenHands V1 SDK 文档为准
cp .env.example .env    # 然后编辑 .env 填真实 key
```

## brain.py 骨架（伪代码级，落地时对齐 OpenHands `LLM` 类）
```python
import os
from dotenv import load_dotenv
load_dotenv()

# OpenHands 底层是 LiteLLM；openai/ 前缀启用 OpenAI 兼容 Chat Completions
LLM_KW = dict(
    model=os.environ["LLM_MODEL"],
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
)
# from openhands.sdk import LLM
# llm = LLM(**LLM_KW)
```

## 验证关卡（verify_stage0.py）
1. **大脑收发**：给端点发一句 "reply with the single word: pong"，断言返回含 `pong`。
2. **kernel 跨 cell 保留状态**：在 LocalWorkspace 的 kernel 里
   - cell A：`x = 41; x += 1`
   - cell B：`print(x)` → 断言输出 `42`
   - cell C：`import math; math.sqrt(x)` → 断言 ≈ 6.48（证明 import 也跨 cell 存活）
3. **装包能力**：kernel 里 `!pip install cowsay -q` 后 `import cowsay` 成功。

**过关标准**：三条全绿。过不了先别往下走——底座不稳后面全白搭。

---

# 阶段 1 · 溯源底座（1 周）

**目标**：照搬 `self-awareness` 的 SQLite schema，把 `host` 做成**注入内核的 in-process SDK**（不是 MCP server——operon 的 self-awareness 文档明确 `host` 是注入 repl 内核的对象，MCP 只用于阶段 2 的 87 数据源），暴露 `host.query(sql)`（只读）+ `save_artifact` / `get_artifact`。这是 operon "provenance by construction" 的核心。

> 实现说明：本地跑时内核是 jupyter 子进程、SQLite 是文件，所以 `host` 直接打开同一个 db 文件即可，无需 RPC，语义与 operon 一致。

## 参照资产
- `../extracted/skills/self-awareness/SKILL.md` —— 完整表结构在这（frames / artifact_versions / artifact_dependencies / execution_log / host_call_log 等）

## 产出文件
- `src/open_science/provenance/schema.sql` —— 照搬表结构
- `src/open_science/provenance/host.py` —— 注入内核的 host SDK：`query(sql)` 只读、`save_artifact(name, data, ...)`、`get_artifact(version_id)`
- `src/open_science/provenance/db.py` —— 按 schema.sql 建库（幂等）
- `src/open_science/render/__init__.py` —— 渲染层（结构→Mol* / 图→内联 / 文档→链接）
- `tests/verify_stage1.py`

## 关键实现点
- `query` **必须只读**：拒绝非 `SELECT` 语句（正则 + 只读连接 `file:db?mode=ro`）。这对应 operon 的只读 host.query。
- `execution_log` 每次 kernel 执行自动记：`source`（代码）、`stdout`、`files_written`（含 sha256）。用 OpenHands 的 kernel 执行 hook 落库。
- artifact 用 `{{artifact:VERSION_ID}}` 占位符协议；`artifact_versions` 存 checksum + environment_snapshot + lineage；`artifact_dependencies` 存 DAG。

## artifact 渲染层（operon 对齐项 —— OpenHands 不自带，必需自建）
operon 里 artifact 不只是"存"，还按类型**自动渲染**给用户看。以 operon 为准，本项目必须补齐同样的按类型渲染：

| artifact 类型 | operon 行为 | 本项目实现 |
|---|---|---|
| 图片（.png/.svg…） | `{{artifact:ID}}` 内联显示在对话里 | 前端解析占位符 → 内联 `<img>` |
| **结构文件（.pdb/.cif/.mmcif）** | **自动挂 Mol\* 3D 交互查看器**（operon metadata 第 38–39 行原文） | **嵌 Mol\*（molstar.org，MIT）web 组件**；kernel 内快速预览可用 py3dmol |
| 文档（.md/.tex/.html） | 作为可打开链接 `[名]({{artifact:ID}})` | 前端渲染为可点链接 |

- **触发条件与 operon 一致**：不是手动选可视化方式，而是"**后缀匹配 + 已 save_artifact**"自动触发。只在 kernel 生成 pdb 但没 save_artifact → 用户看不到（对齐 operon「不 save 不可见」语义）。
- 产出文件补充：`src/open_science/render/`（占位符解析 + Mol\* 组件挂载）。

## 验证关卡（verify_stage1.py）
1. **自动溯源**：让 agent 跑一段 `open('out.txt','w').write('hi')`，断言 `execution_log` 新增一行且 `files_written` 里 out.txt 的 sha256 正确。
2. **artifact 往返**：`save_artifact("fig1", b"...")` → 拿到 VERSION_ID → `get_artifact(id)` 取回字节一致。
3. **只读防线**：对 `query("DROP TABLE execution_log")` 断言被拒绝、表还在。
4. **DAG**：存 artifact B 声明依赖 A，查 `artifact_dependencies` 能走出 A→B。
5. **结构渲染触发**：save 一个 `.pdb` artifact → 断言渲染层识别为结构类型并生成 Mol\* 查看器挂载点（不是当纯文本）；save 一个 `.png` → 断言走内联图片路径。

**过关标准**：跑一步代码 → 溯源自动落库 + artifact 可取回 + 只读防线生效 + 结构文件走 Mol\* 渲染路径。

---

# 阶段 2 · 数据源层（3–4 周，最大块）

**目标**：把 87 个数据源包成 OpenHands MCP server，且**按需注入**不全量进 context。

## 参照资产
- `../extracted/mcp-servers/bio-tools/lib/`（41,775 行）
  - `mcp_servers_common/`（ratelimit/errors/ua/gate/tier1）—— **第一个搬**，所有源都依赖它
  - 62 个 client 型 + 24 个 `mcp_*` 聚合 server

## 施工顺序（关键：不要一次搬 87 个）
1. **先搬 `mcp_servers_common`** → `src/open_science/datasources/common/`，跑通限流/错误基建。
2. **搬 3 个试点源**验证包装模式：`rfam_families`（RNA，你本行）、`uniprot_fetch`（蛋白）、`pubmed_fetch`（文献）。
   - 每个源逻辑**不用改**（本就是打公共 API 的 HTTP 客户端），只需外面套一层 OpenHands MCP server 壳。
3. 模式跑通后**批量搬剩余**，按领域分批（RNA/基因组组 → 蛋白/结构组 → 药物/临床组 → 文献组）。
4. 用 microagent `trigger_type` 按关键词注入某组源，避免 87 server 全量撑爆 context（= operon 渐进暴露）。

## 产出文件
- `src/open_science/datasources/common/`（搬 mcp_servers_common）
- `src/open_science/datasources/<源名>/`（每源一个 MCP server 壳 + 原逻辑）
- `microagents/` 下按领域分组的 trigger 配置
- `tests/verify_stage2.py`

## 验证关卡（verify_stage2.py）
1. **试点三源真实取数**：
   - rfam：取一个家族（如 RF00001 5S rRNA）→ 断言返回含 rfam_acc / description。
   - uniprot：取一个 accession（如 P69905 血红蛋白）→ 断言含序列。
   - pubmed：搜一个 PMID → 断言含 title。
2. **与原版比对**：同一 query 在原版 operon（若可跑）与本项目输出**字段一致**（至少 key 集合一致）。
3. **限流生效**：连发 N 次，断言 `mcp_servers_common` 的 ratelimit 有节流行为（不被上游封）。
4. **按需注入**：问一个 RNA 问题，断言只有 RNA 组 MCP 工具进了 context，不是全部 87。

**过关标准**：试点三源输出与原版一致 + 限流生效 + 按需注入生效。之后批量搬是重复劳动。

> ⚠️ 联网前提：本项目本地跑要能访问 rfam.org / uniprot.org / ncbi 等公网。BAAI 节点若这些被墙，数据源阶段建议放在能出网的机器上测。

---

# 阶段 3 · 技能 + 渐进暴露（2 周）

**目标**：写一个 skill loader，平时只喂 SKILL.md 的 `description`，`search_skills` 命中才注入正文。这就是 operon 的 progressive disclosure。

## 参照资产
- `../extracted/skills/*/SKILL.md`（29 个，全齐）
- frontmatter 格式：`name / description / category / requirements / metadata`

## 产出文件
- `skills_assets/`（从 ../extracted/skills 拷贝 29 个 SKILL.md + 附带脚本）
- `src/open_science/skills/loader.py` —— 解析 frontmatter、建 description 索引、`search_skills(query)` 返回命中并注入正文
- `tests/verify_stage3.py`

## 关键实现点
- 启动时只把每个技能的 `description`（一行）放进 agent 可见的"技能菜单"。
- `search_skills(query)` 做关键词/语义匹配 → 命中后把该 SKILL.md **正文**注入 context。
- 纯说明型技能（figure-style / literature-review / paper-narrative）注入即可用；带脚本的（skill-creator）正文里引用的脚本路径指向 `skills_assets/<name>/`。

## 验证关卡（verify_stage3.py）
1. **菜单不撑爆**：启动后 context 里只有 29 行 description，不是 29 篇全文。
2. **按需加载**：问"帮我做一张出版级的多面板图" → 断言 agent 触发 `search_skills` 且加载了 `figure-composer`/`figure-style` 正文。
3. **未命中不注入**：问一个无关问题，断言没有技能正文被注入。

**过关标准**：agent 能自己 `search_skills` 找到并加载正确技能正文，且平时菜单不膨胀。

---

# 阶段 4 · 4 个 agent 角色（1 周）

**目标**：用 OpenHands `AgentSettings` 复现 operon 的 4 个 profile，靠工具裁剪定义角色。

## 参照资产
- `../extracted/agents/{operon,reviewer,bookmarker,onboarding}/metadata.yaml`

## 角色 → AgentSettings 映射
| 角色 | operon 配置 | OpenHands AgentSettings |
|---|---|---|
| operon | 全能力，artifact-first | 全工具，注入 working_style 系统提示 |
| reviewer | enable_thinking:false、skills_locked、关 web/plan | `enable_think=false`、`disabled_microagents=[...]`、去掉 search 工具 |
| bookmarker | excluded_tools 砍到只剩 submit_output | 只 include submit 工具，其余全不 enable |
| onboarding | internal:true，只留 ask_user | 只 include ask_user |

## 产出文件
- `src/open_science/agents/{operon,reviewer,bookmarker,onboarding}.py` —— 每个生成一份 AgentSettings
- `tests/verify_stage4.py`

## 验证关卡（verify_stage4.py）
1. **bookmarker 裁剪生效**：给 bookmarker 一个"跑段 python"的请求，断言它**没有** python/bash 工具可调（工具集里不存在）。
2. **reviewer 关 thinking**：断言 reviewer 的 settings `enable_think == False`。
3. **operon 全能**：断言 operon 能调 python + MCP + save_artifact。
4. **onboarding 最小**：断言只有 ask_user 一个工具。

**过关标准**：四角色的工具集与 metadata.yaml 声明一致，裁剪真实生效（不是提示词层面装装样子）。

---

# 阶段 5 · 模型技能 + byoc 远程（2–3 周）

**目标**：12 个模型技能照搬；`remote-compute-*` 接 OpenHands `RemoteAPIWorkspace`，把 GPU 任务派到 BAAI 节点。

## 参照资产
- `../extracted/skills/{proteinmpnn,ligandmpnn,solublempnn,evo2,esmfold2,fair-esm2,alphafold2,boltz,chai1,openfold3,scgpt,scvi-tools,borzoi,diffdock}/SKILL.md`
- `../extracted/skills/{remote-compute-ssh,remote-compute-modal,compute-env-setup}/`

## 施工顺序
1. **先接远程 workspace**：`RemoteAPIWorkspace` 连 BAAI 节点，验证能在远程起 kernel、跑 `nvidia-smi`。
2. **先跑最小模型 proteinmpnn**（几十 MB，CPU 都能跑，无需 hf.co）——验证"模型技能能真跑"。
3. 再上需要拉权重的（evo2 等）——**此处撞 BAAI 节点两个坑**：
   - hf.co 被墙 → 配 `HF_ENDPOINT=https://hf-mirror.com` 或预挂权重到 `HF_HOME`
   - CUDA 11.4 / 驱动 470 → evo2 的 `flash-attn` 大概率装不上，挑不依赖它的模型，或降级实现
4. alphafold2 的 MSA 走 `api.colabfold.com`（在线）——节点要能出网；敏感序列注意出境。

## 产出文件
- `src/open_science/agents/operon.py` 挂载 12 个模型技能
- 远程 provider 配置（SSH 到 BAAI 节点的连接信息，凭据走环境变量/密钥文件，不入库）
- `tests/verify_stage5.py`

## 验证关卡（verify_stage5.py）
1. **远程 kernel**：`RemoteAPIWorkspace` 上跑 `nvidia-smi` 返回 GPU 信息。
2. **最小模型真跑**：proteinmpnn 对一个 PDB 反向折叠出一条氨基酸序列，断言长度 == 链长。
3. **溯源贯通**：该次远程执行在阶段 1 的 `execution_log` 里有记录 + 结果存成 artifact。
4. **结构可视化端到端**：跑一个结构预测（如 boltz/openfold3）输出 `.cif` → save_artifact → 断言前端用 Mol\* 查看器渲染（复用阶段 1 渲染层，对齐 operon）。

**过关标准**：proteinmpnn 在 BAAI 节点上真跑出序列，且执行被溯源、结果成 artifact。至此整套架构端到端打通。

---

# 里程碑总览

| 里程碑 | 完成即证明 |
|---|---|
| M0（阶段0） | 开源大脑 + 有状态 kernel 能转 |
| M1（阶段1） | 溯源 by construction 成立 |
| M2（阶段2） | 数据 grounding：真打公共 API、按需注入 |
| M3（阶段3） | 渐进暴露：海量技能可管理 |
| M4（阶段4） | 角色裁剪：安全/成本从工具集长出来 |
| M5（阶段5） | 自备算力端到端：模型在你节点真跑 + 全程溯源 |

**M5 达成 = 一个开源、自托管、行为等价于 Claude Science 的科研 agent 系统**（唯一落差：编排大脑智力弱于 Claude）。

---

# 现实风险清单

- **大脑智力落差**（不可消除）：较弱模型会挑错技能、调错参。缓解：把 SKILL.md 的 description 写得更硬、search_skills 匹配更准、关键步骤加 inline assert。
- **OpenHands 容器冷启**：本项目用 LocalWorkspace 规避；真上 Docker 再压测复用。
- **BAAI 节点网络/CUDA**：hf.co 墙 + CUDA 11.4，见阶段 5。数据源阶段也要能出网。
- **API key 泄露**：一切凭据走环境变量，`.env` 入 `.gitignore`，已泄露的即时轮换。
- **上游 API 变更/限流**：`mcp_servers_common` 已含礼貌限流；上游 schema 变了要跟着改对应源。
