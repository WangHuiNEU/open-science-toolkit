# 第七章 MCP 聚合架构

> 代表文件：`mcp-servers/bio-tools/run_server.py`（服务器分发入口）、`lib/` 目录结构
> 核心命题：几十个生物信息学数据源，不是拍平成一个巨型工具面，也不是散成上百个独立
> 服务器，而是**按领域聚成 24 个 MCP server 包，共享一个 ~87 模块的底层 lib**——
> 这是「工具规模化」的一个折中范式。

---

## 7.1 先纠正一个容易犯的误读

初看 bio-tools，很容易得出「一个 MCP server 暴露 87 个数据源」的结论。读 `run_server.py` 后必须纠正：**它是 24 个按领域分组的 MCP server 包，架在一个约 87 模块的扁平 `lib/` 之上。** 这个区分不是细节，它正是本章要讲的核心架构决策——**「聚合的粒度」**。

`run_server.py` 的分发逻辑把这一点讲得很清楚：

```python
def discover_servers():
    # a server = a package under lib/ whose name starts with "mcp_"
    # and that contains a server.py
    …
def main(server_name):
    module = importlib.import_module(f"{server_name}.server")
    module.mcp.run()
```

即：**一个 server = `lib/` 下一个以 `mcp_` 开头、且含 `server.py` 的包。** 磁盘上 `lib/` 有 25 个 `mcp_` 目录——24 个真实 server + 1 个 `mcp_servers_common`（共享辅助，不是 server）。每个 server 是一个领域分组（如 `mcp_structure`、`mcp_sequence`、`mcp_literature`……），它内部再调用扁平 `lib/` 里那 ~87 个功能模块。

**三层结构因此是：**
```
调度入口 (run_server.py)
   └── 24 个领域 server 包 (lib/mcp_*/server.py)   ← MCP 暴露面 / 聚合粒度
          └── ~87 个功能模块 (lib/*.py)             ← 实际数据源实现
```

---

## 7.2 为什么是「24 个领域服务器」，而不是两个极端

工具规模化有两个诱人但都错的极端：

### 极端 A：一个巨型 server 暴露全部 87 个工具

坏处：**工具描述会挤爆上下文，且模型选错工具的概率随工具数线性上升。** MCP 的每个工具都要把 name + description + schema 常驻在模型可见的工具面里。87 个工具的 schema 是巨大的常驻成本，而且模型在 87 个里挑一个，误选率高。这与第五章 skill 的「渐进式披露」要解决的是同一个问题——**上下文是稀缺资源，不能让所有能力同时全量常驻。**

### 极端 B：87 个独立 server，一个数据源一个

坏处：**运维与连接开销爆炸，且共享逻辑无处安放。** 每个 server 要独立启动、独立握手；而像「HTTP 重试」「accession 校验」「速率限制」这种跨数据源的通用逻辑，会在 87 处重复。

### 折中：按领域聚成 24 个

`mcp_structure` 把所有结构相关的数据源（PDB、AlphaFold DB、结构比对……）聚在一个 server 里；`mcp_literature` 把文献相关的（PubMed、arXiv、bioRxiv……）聚在一起。这样：
- **模型面对的是「领域」这个它天然会用的分类维度**——要查结构就去 structure server，选择成本低。
- **同一领域的数据源能共享 `mcp_servers_common` 里的辅助**（HTTP 客户端、错误封装、通用解析）。
- **24 个 server 可以按需启动**——不做结构分析的会话根本不必拉起 `mcp_structure`。

**可迁移原则**：工具聚合的粒度应该对齐「用户/模型的心智分类」（这里是科学领域），而不是对齐「实现单元」（一个数据源）或「一锅端」（全塞一个 server）。聚合粒度 = 选择成本与复用收益的平衡点。

---

## 7.3 server 与 lib 的分离——暴露面 vs 实现

`run_server.py` 只认「`mcp_` 开头 + 有 `server.py`」的包为 server，这个约定造就了一个干净的分层：

- **`lib/mcp_*/server.py`（暴露层）**：定义 MCP 工具、写工具 description、组织参数 schema。这是模型看得见的部分。
- **`lib/*.py`（实现层）**：~87 个功能模块，是实际去调 NCBI / EBI / PDB 等的代码。模型看不见它们，只通过 server 层间接使用。

这个分离的价值在于：**同一个底层实现模块可以被多个领域 server 复用，而每个 server 可以为自己的领域裁剪、命名、描述工具。** 一个「序列比对」的底层实现，既可能被 `mcp_sequence` 暴露成「align two sequences」，也可能被别的领域 server 以不同措辞暴露。暴露面（怎么呈现给模型）和实现（怎么真正做）解耦了。

这与第二章「identity/working_style 分离」、第四章「artifact/artifact_versions 分离」是同一种设计直觉——**把「对外呈现的东西」和「稳定的底层实体」拆开，让两者能各自独立演化。** 整个 Claude Science 反复运用这个模式。

---

## 7.4 discover-from-disk：约定优于配置

`run_server.py` 的 `discover_servers()` 不维护一份「服务器清单」配置文件，而是**从磁盘扫描推导**——凡是符合命名约定（`mcp_` 前缀 + `server.py`）的包，自动就是一个 server。

这是「约定优于配置」（convention over configuration）的实践：
- **加一个新领域 server**：只需在 `lib/` 建一个 `mcp_newdomain/` 目录、放个 `server.py`，无需改任何注册表。
- **没有「清单和实际不一致」的漂移风险**：因为清单**就是**磁盘现状，不存在第二份需要同步的真相。

这与第五章 skill 系统的自动发现（skill 靠 metadata 被发现、`host.skills.list()` 列出磁盘上所有 skill）异曲同工——**Claude Science 倾向于让「系统的能力集」从文件系统结构自动涌现，而不是维护一份易腐的中心注册表。**

---

## 7.5 MCP 只在 repl 里调——回顾第二章的拓扑约束

MCP 架构必须和第二章讲过的 kernel 拓扑一起理解。operon 的 working_style 规定：

```
MCP calls happen in the `repl` tool — never in `python`/`r` (those kernels
have no MCP surface). Looping over samples or records? Write the loop in a
`repl` cell — `[host.mcp("server", "method", id=x) for x in ids]` is one
`repl` call with N host round-trips inside it…
```

把这个和本章的 24-server 架构拼起来，就能看清一次真实的 MCP 调用长什么样：

```python
# 在 repl cell 里，一次调用打到某个领域 server 的某个 method：
host.mcp("mcp_structure", "fetch_pdb", id="1ABC")
```

`host.mcp(server, method, **kwargs)` 的第一个参数正是 24 个领域 server 之一，第二个是该 server 暴露的工具方法。**领域聚合让这个调用的第一个参数是可读的领域名，而不是一个 87 选 1 的扁平方法名。** 循环多个数据源调用要写成 repl cell 里的 list comprehension（一次 repl 回合、内部 N 次 host round-trip），再 `json.dump` 到 `./handoff/` 交给 python kernel——这是第二章「回合经济学 + kernel 拓扑」在 MCP 场景的直接落地。

---

## 7.6 「反 confabulate」在数据源层的意义

第二章和第九章反复出现的「compute, don't confabulate」，在 MCP 架构这里有了物理载体。working_style 说：

```
When you fetch via `host.mcp()`, the result is the source of truth — cite the
identifiers it returns…
```

bio-tools 的 24 个 server 存在的**根本理由**就是这句话：模型的训练记忆里「记得」很多基因、通路、accession、临床试验号，但这些记忆可能过时、可能张冠李戴、可能纯属编造。MCP server 提供了**权威的实时来源**——去 NCBI 查这个 accession、去 PubMed 查这篇文献、去 PDB 取这个结构。**取回来的标识符才是真相之源，凭记忆写出来的不是。**

所以 MCP 聚合架构不只是「工具很多」的工程问题，它是**反幻觉哲学的基础设施**：只有当「去查真实数据」比「凭记忆瞎编」更方便时，模型才会真的去查。24 个按领域组织、可在 repl 里一行调用的 server，就是把「查真实数据」的成本压到足够低，让正确行为成为默认路径。

---

## 7.7 这一章的可迁移原则

1. **聚合粒度对齐心智分类**：几十个工具别拍平成一个巨型面（选择成本 + 上下文成本爆炸），也别散成一堆独立 server（运维 + 复用成本爆炸）。按用户/模型天然会用的维度（这里是科学领域）聚成中等数量的分组。
2. **暴露面与实现分离**：`server.py`（模型可见的工具定义）与 `lib/*.py`（底层数据源实现）解耦，让同一实现能被多领域复用、各自裁剪呈现。
3. **约定优于配置的发现机制**：从磁盘命名约定推导服务器集合，消灭「注册表 vs 实际」的漂移。
4. **工具架构要服务于行为哲学**：MCP server 的终极目的不是「功能多」，而是把「获取权威真实数据」的成本压低到成为默认路径——这是反幻觉的物理基础。

> 收尾：bio-tools 表面上是「一堆生物信息学 API 的封装」，但它的架构选择——24 个领域 server 架在 ~87 模块 lib 之上、从磁盘自动发现、只在 repl 暴露——回答的是一个通用问题：**当一个 agent 需要接触几十上百个外部能力时，怎么组织它们才能既不淹没模型、又不拖垮运维、还能沉淀共享逻辑。** 答案是「按心智维度中等聚合 + 暴露/实现分离 + 约定发现」。

下一章进入反幻觉哲学的大脑：[自省与自知](08_自省与自知.md)。
