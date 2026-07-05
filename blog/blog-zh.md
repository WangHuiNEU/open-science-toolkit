# 我用开源栈复刻了一个"科研 Agent":29 个技能、24 个 MCP 服务、一个有状态的内核——全都可复用

*给大模型配一张真正的实验台,难的从来不是模型,而是脚手架。*

---

## 一句话概括

**[Open Science Toolkit](https://github.com/WangHuiNEU/open-science-toolkit)** 是一套在**全开源栈**上搭建 Claude-Science 风格科研 Agent 的可复用组件。它包含:

- **29 个科研技能**——AlphaFold2、Boltz、Chai-1、ESMFold2、OpenFold3、DiffDock、ProteinMPNN、ESM-2、Evo 2、Borzoi、scGPT、scVI……每个都是自包含的 `SKILL.md`,按需加载;
- **24 个领域 MCP 服务**,封装了 62 个公开科学 API(PubMed、ChEMBL、临床试验、基因组、变异、表达、本体……);
- **4 个 Agent 画像**,身份与工作风格解耦,按角色裁剪工具;
- **一个有状态的 Python 内核**,变量跨 cell 存活,就像 Agent 自己操作的一个 notebook;
- **一个自包含的浏览器聊天 UI**,内置 **3D 结构查看**(3Dmol.js,不依赖外部 CDN)。

跑在 OpenHands V1 SDK 上,**开箱无需 Docker**;大脑可接**任意 OpenAI 兼容端点**。Apache-2.0 许可。

```bash
pip install -e . --no-deps
cp .env.example .env          # 填 LLM_BASE_URL / LLM_MODEL / LLM_API_KEY
python -m open_science.server --serve --port 8000
```

仓库地址:**https://github.com/WangHuiNEU/open-science-toolkit**

---

## 为什么做这个

现在有一类 AI 产品,不只是"聊科学",而是**真的在做科学**:折叠蛋白、设计序列、检索文献、跑数据、出图。它们很惊艳,但也都是闭源的。

有意思的是,这类系统**最难的部分并不是模型本身,而是脚手架**——你怎么给一个语言模型配一张能干活的实验台?它怎么知道 AlphaFold2 存在、什么时候该调用它?怎么在不被二十几个生信 API 的工具定义淹没的前提下把它们都接进来?第 3 步算出的变量怎么活到第 8 步?一个 `.pdb` 文件怎么渲染成人能看的结构?

Open Science Toolkit 就是我在开源栈上把这些零件逐一造出来的尝试——而且关键在于,每个零件都**可以单独拆出来用**。你不必整套照搬:clone 下来,只取技能加载器,或只取 MCP 聚合层,或只取有状态内核,接到你自己的 Agent 上即可。

---

## 四个硬骨头,以及它们怎么被解决

### 1. 技能:Agent 怎么知道自己会什么?

把 29 个工具定义一股脑塞进系统提示,是烧穿上下文窗口、把模型搞晕的经典做法。这里换个思路:每个能力是一个**技能(skill)**——一个目录,含一个 `SKILL.md`(YAML 头 + 指令)和它需要的辅助脚本。

加载器采用**渐进式披露**:Agent 先看到一份精简的技能"菜单"(名字 + 一行描述),只有当某个技能与当前任务匹配时,才注入它的完整正文。相当于给 Agent 能力做懒加载。

29 个技能分六大主题:**结构预测与对接**(6)、**蛋白设计与嵌入**(4)、**基因组与单细胞**(4)、**图表与可视化**(2)、**文献与写作**(4)、**计算与工作流**(9)。最后一组是元层:Modal / SSH-SLURM 上的远程 GPU 执行、用来写新技能的 `skill-creator`、用来自省会话的 `self-awareness`。

因为格式遵循标准的 Agent Skills 约定,这些技能能直接放进任何兼容的框架。

### 2. 数据源:接 62 个 API 而不付"工具定义税"

科学都藏在 API 后面——PubMed、bioRxiv、ChEMBL、ZINC、临床试验、基因组装配、变异库、表达图谱、本体。全都朴素地接进来,工具列表就废了。

工具箱把它们封装成 **24 个领域 MCP 服务**——标准的 [Model Context Protocol](https://modelcontextprotocol.io) 服务,按领域分组(文献、基因组、变异、化学、试验……),把 **62 个 HTTP 客户端**收在一个公共层之后,统一处理限流、重试、门控。服务按查询领域**按需注入**,所以 Agent 永远只看到与当前任务相关的工具。

而且因为它们就是普通的 MCP 服务,可以独立用在**任何** MCP 客户端里——Claude Desktop、Cursor,随你。

### 3. 状态:要的是内核,不是计算器

大多数 Agent 的"代码执行"是无状态的:每段代码在真空里跑。真实分析不是这样——你加载一次数据集,然后一直在它上面干活。

`KernelSession` 封装了 `jupyter_client` + `ipykernel`,给 Agent 一个**持久的 IPython 内核**。变量跨 cell 存活:第一步加载 DataFrame,三步之后变换它,最后画出来——和人在 notebook 前一模一样。就这一个组件,直接改变了"多步分析"能做到什么程度。

### 4. 身份 vs. 能力:用共享零件拼出四个 Agent

一个 Agent 画像就是一份 `metadata.yaml`,含**身份提示**(它是谁)、**工作风格规则**(它怎么做事)、**能力开关**。工具箱自带四个:

- **operon**——主科研计算 Agent,全套工具;
- **onboarding**——首次运行的引导设置,只问不做;
- **reviewer**——审查对话记录中的幻觉/编造;
- **bookmarker**——从对话里抽取要点。

一个漂亮的工程细节是**工具裁剪**:OpenHands 用**正向匹配**的正则(`filter_tools_regex`)过滤工具,但画像是用 `excluded_tools`**黑名单**来写的——这样读起来自然得多。中间的桥把黑名单编译成**负向先行断言(negative-lookahead)正则**,于是你写"排除这几个",框架执行"其余全放行"。小细节,但写 Agent 时体验提升很大。

---

## 架构一览

| 层 | 实现 |
|---|---|
| 运行时 | OpenHands V1 SDK(MIT),`LocalWorkspace`——开箱无需 Docker |
| 大脑 | 任意 OpenAI 兼容端点,凭据仅走环境变量 |
| 内核 | `KernelSession`(`jupyter_client` + `ipykernel`),变量持久 |
| 技能 | 基于检索的懒注入加载器(先菜单,匹配后注入正文) |
| Agent | OpenHands `Agent` + `filter_tools_regex` 工具裁剪 |
| 3D 查看器 | 3Dmol.js 内嵌在自包含 Web UI 里 |

大脑刻意做成模型无关:三个环境变量指向任意 OpenAI 兼容端点即可。凭据只存在于环境中,绝不进任何提交的文件。

---

## 盒子里到底有什么

- **装配代码**——`src/open_science/`(约 340 个 Python 文件):FastAPI 服务、Agent 加载器、内核、大脑、技能加载器、数据源注册表、溯源层、产物渲染、远程计算胶水、Web UI;
- **29 个技能**——`skills_assets/`(29 个 `SKILL.md` + 79 个辅助脚本);
- **4 个 Agent 画像**——`agents_assets/`;
- **24 个 MCP 数据源**——`src/open_science/datasources/vendor/`(62 个 API 客户端);
- **设计拆解**——`docs/design-teardown/`(9 章,讲清背后的模式:配置即调优记录、身份/工作风格分离、追溯而非重算、渐进式披露、MCP 聚合、自省与自知);
- **验证脚本**——`tests/`(分阶段冒烟测试:大脑往返、有状态内核、MCP 源、技能加载、Agent 裁剪)。

一切都为**可复用**而设计。那 9 章设计拆解就是专门写来让你偷**思路**的,而不只是偷代码。

---

## 五条值得偷走的设计原则(哪怕你永远不碰这个仓库)

1. **用渐进式披露替代大提示词。** 先给菜单,匹配后注入正文。上下文是预算。
2. **追溯,别重算。** 一个只读的溯源层,让 Agent 查历史产物,而不是重跑昂贵计算。
3. **身份与工作风格分离。** "它是谁"和"它怎么做事"是两个轴,放在不同字段里,自定义画像才能只改一个而不丢另一个。
4. **把 API 聚合到一个带门控的公共层后面。** 限流、重试、门控属于共享层,而不是复制粘贴进 62 个客户端。
5. **状态本身就是特性。** 持久内核能解锁无状态执行器根本做不到的分析。

---

## 上手

```bash
git clone https://github.com/WangHuiNEU/open-science-toolkit
cd open-science-toolkit
pip install -e . --no-deps
cp .env.example .env          # 填 LLM_BASE_URL / LLM_MODEL / LLM_API_KEY
python -m open_science.server --serve --port 8000
# http://localhost:8000/        聊天 UI
# http://localhost:8000/docs    API 面板
```

**Apache-2.0** 许可,基于 [OpenHands](https://github.com/All-Hands-AI/OpenHands)(MIT)与 3Dmol.js(BSD)。模型权重各自遵循自身许可。

如果这里面任何一个组件对你有用——技能加载器、MCP 聚合、有状态内核、黑名单→正则的工具裁剪桥——拿去用就好。它就是为此而生的。

**⭐ 仓库:https://github.com/WangHuiNEU/open-science-toolkit**

欢迎提 Issue、PR 和问题。
