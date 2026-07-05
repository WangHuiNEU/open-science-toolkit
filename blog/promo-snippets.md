# Promotion Kit — ready-to-post snippets

Copy-paste blurbs tailored per platform. **You post these** (I don't have your logins, and
mass-posting identical text from an automated agent is spam that gets accounts banned). Space
them out over a few days; reply to comments to keep momentum.

Repo: https://github.com/WangHuiNEU/open-science-toolkit

---

## Hacker News (Show HN)

**Title:**
```
Show HN: Open Science Toolkit – an open-source "science agent" (skills + MCP + kernel)
```

**Body (first comment):**
```
I built a set of reusable components for a Claude-Science-style research agent on a
fully open stack. It ships 29 research skills (AlphaFold2, Boltz, ESMFold2, ProteinMPNN,
Evo 2, scGPT, scVI, literature review…), 24 domain MCP servers wrapping 62 public science
APIs (PubMed, ChEMBL, clinical trials, genomes, variants…), 4 agent profiles, a stateful
IPython kernel where variables persist across cells, and a self-contained browser chat UI
with 3D structure viewing.

The thesis: the hard part of these systems isn't the model, it's the scaffolding — skill
loading with progressive disclosure, aggregating dozens of APIs without a tool-definition
tax, keeping state across steps, and separating an agent's identity from its capabilities.
Every piece is meant to be lifted out and reused independently.

Runs on the OpenHands V1 SDK with no Docker to start; the brain is any OpenAI-compatible
endpoint. Apache-2.0. There's a docs/design-teardown/ folder explaining the patterns so you
can steal the ideas even if you never run the code.

Would love feedback on the architecture, especially the MCP aggregation and the skill loader.
```
*Tip: post Tue–Thu, ~9am ET. Don't editorialize the title. Answer every comment.*

---

## Reddit

Subreddits that fit: **r/bioinformatics**, **r/MachineLearning** (use the `[P]` Project tag),
**r/LocalLLaMA**, **r/LLMDevs**, **r/comp_chem**. Tailor the first line to each sub.

**Title (r/bioinformatics):**
```
[Open-source] A reusable "science agent" toolkit: 29 skills (AlphaFold2/Boltz/ProteinMPNN/scGPT…) + 24 MCP servers over public bio APIs
```

**Title (r/MachineLearning):**
```
[P] Open Science Toolkit — open-source science-agent scaffolding (skills, MCP aggregation, stateful kernel)
```

**Body:**
```
I open-sourced a set of reusable components for building a research agent on an open stack.

- 29 skills as self-contained SKILL.md files, loaded on demand (progressive disclosure):
  structure prediction (AlphaFold2, Boltz, Chai-1, ESMFold2, OpenFold3, DiffDock), protein
  design (ProteinMPNN/LigandMPNN/SolubleMPNN, ESM-2), genomics/single-cell (Borzoi, Evo 2,
  scGPT, scVI), figures, literature, and remote GPU compute (Modal/SSH).
- 24 domain MCP servers wrapping 62 public science APIs behind one rate-limited/retrying
  common layer, injected on demand — usable standalone in any MCP client.
- A stateful IPython kernel (variables persist across cells).
- 4 agent profiles with identity/working-style separation and denylist→regex tool trimming.
- Self-contained browser chat UI with 3Dmol.js structure viewing (no external CDN).

OpenHands V1 SDK, no Docker to start, any OpenAI-compatible endpoint as the brain. Apache-2.0.
Each component is meant to be reused independently — clone it and take just the piece you need.

Repo: https://github.com/WangHuiNEU/open-science-toolkit
Happy to answer questions about the design.
```
*Tip: read each sub's self-promotion rules first. Engage, don't drive-by.*

---

## Twitter / X (thread)

```
1/ I open-sourced Open Science Toolkit: reusable components for a Claude-Science-style
research agent on a fully open stack.

29 skills · 24 MCP servers (62 APIs) · a stateful kernel · a 3D-structure chat UI.

Apache-2.0 🧵
https://github.com/WangHuiNEU/open-science-toolkit

2/ The hard part of a "science agent" isn't the model — it's the scaffolding.

How does it know AlphaFold2 exists? Call 62 bio APIs without drowning? Keep a variable alive
across 8 steps? Render a .pdb so a human can look at it?

3/ Skills = progressive disclosure. The agent sees a compact menu of 29 skills; the full body
is injected only when one matches the task. Lazy loading for capabilities. Standard Agent-Skills
format, so they drop into any harness.

4/ Data = 24 domain MCP servers wrapping 62 public science APIs (PubMed, ChEMBL, trials,
genomes, variants…) behind ONE rate-limited/retrying layer, injected on demand. Works standalone
in any MCP client too.

5/ State = a real IPython kernel. Variables persist across cells. Load a dataframe once, keep
working on it. This is what lets multi-step analysis actually work.

6/ Agents = identity ⟂ working style. 4 profiles (operon/onboarding/reviewer/bookmarker).
Tool trimming compiles an excluded_tools denylist into a negative-lookahead regex. You write
"exclude these"; the harness enforces "allow the rest."

7/ Runs on OpenHands V1 SDK, no Docker to start, any OpenAI-compatible endpoint as the brain.
There's a design-teardown doc so you can steal the ideas even if you never run it.

⭐ https://github.com/WangHuiNEU/open-science-toolkit
```

---

## LinkedIn

```
I just open-sourced Open Science Toolkit — reusable components for building a
Claude-Science-style research agent on a fully open-source stack.

The insight behind it: the hard part of an AI "science agent" isn't the model, it's the
scaffolding. Giving a language model a real bench to work at means solving four problems —
how it discovers its own capabilities, how it reaches dozens of scientific APIs without being
overwhelmed, how it keeps state across a multi-step analysis, and how it renders results a
human can actually inspect.

What's inside:
• 29 research skills (AlphaFold2, Boltz, ProteinMPNN, ESM-2, Evo 2, scGPT, scVI, literature
  review, and more), loaded on demand via progressive disclosure
• 24 domain MCP servers wrapping 62 public science APIs behind one rate-limited layer
• A stateful IPython kernel where variables persist across steps
• 4 agent profiles with identity/working-style separation
• A self-contained chat UI with 3D structure viewing

Runs on the OpenHands V1 SDK with no Docker to start, and any OpenAI-compatible endpoint as
the brain. Apache-2.0 — every component is designed to be lifted out and reused.

https://github.com/WangHuiNEU/open-science-toolkit

#AI #Bioinformatics #OpenSource #LLM #MCP #AIAgents #ComputationalBiology
```

---

## dev.to / Hashnode / Medium

Post the full English blog (`blog-en.md`). Suggested tags: `ai`, `opensource`, `python`,
`bioinformatics`, `llm`. Add a canonical link back to the GitHub repo.

---

## 掘金 / 知乎 / CSDN

发中文全文(`blog-zh.md`)。

- **掘金**:标签选 `人工智能` `开源` `Python`。
- **知乎**:可发到"大模型""生物信息学""开源项目"话题下,或写成想法+文章。
- **CSDN**:分类选"人工智能/大模型"。

标题备选:
```
我用开源栈复刻了一个"科研 Agent":29 技能 + 24 MCP 服务 + 有状态内核(全可复用)
给大模型配一张实验台:一套开源的科研 Agent 脚手架拆解
```

---

## Others worth a post

- **awesome-mcp-servers** lists (GitHub) — submit a PR adding the 24 MCP servers.
- **r/LocalLLaMA** — angle it as "runs on any OpenAI-compatible endpoint, no Docker."
- **Lobsters** (if you have an invite) — tags: `ai`, `python`, `science`.
- **OpenHands community** (Discord/GitHub Discussions) — it's built on their SDK; they may amplify.
- **Bluesky / Mastodon** (fosstodon.org) — the FOSS crowd; reuse the X thread.
- **Hugging Face** — if you publish a Space or model card, cross-link the repo.

---

## Posting hygiene (so this doesn't backfire)

1. **Stagger** posts over several days; don't blast everything in one hour.
2. **Customize the opening line** per community — copy-pasting identical text reads as spam.
3. **Reply to every comment** in the first few hours; engagement drives ranking.
4. **Read each platform's self-promotion rules** before posting.
5. Lead with the **problem/insight**, not "please star my repo."
