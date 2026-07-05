# Building an Open-Source "Science Agent": 29 Skills, 24 MCP Servers, and a Stateful Kernel — All Reusable

*What it takes to give an LLM a real laboratory bench — and why every piece of it should be a component you can lift out and reuse.*

---

## TL;DR

**[Open Science Toolkit](https://github.com/WangHuiNEU/open-science-toolkit)** is a set of reusable components for building a Claude-Science-style research agent on a fully open-source stack. It ships:

- **29 research skills** — AlphaFold2, Boltz, Chai-1, ESMFold2, OpenFold3, DiffDock, ProteinMPNN, ESM-2, Evo 2, Borzoi, scGPT, scVI, and more, each as a self-contained `SKILL.md` loaded on demand.
- **24 domain MCP servers** wrapping 62 public science APIs (PubMed, ChEMBL, clinical trials, genomes, variants, expression, ontologies…).
- **4 agent profiles** with identity/working-style separation and per-role tool trimming.
- **A stateful Python kernel** where variables persist across cells, like a notebook the agent controls.
- **A self-contained browser chat UI** with **3D structure viewing** (3Dmol.js, no external CDN).

Runs on the OpenHands V1 SDK with **no Docker to start**, and any **OpenAI-compatible endpoint** as the brain. Apache-2.0.

```bash
pip install -e . --no-deps
cp .env.example .env          # set LLM_BASE_URL / LLM_MODEL / LLM_API_KEY
python -m open_science.server --serve --port 8000
```

Repo: **https://github.com/WangHuiNEU/open-science-toolkit**

---

## Why I built this

There's a growing class of AI products that don't just *chat about* science — they *do* science: fold a protein, design a sequence, pull the literature, run the numbers, and hand you a figure. They're impressive. They're also closed.

The interesting thing is that the *hard* part of these systems isn't the model. It's the **scaffolding**: how you give a language model a bench to work at. How does it know AlphaFold2 exists and when to reach for it? How does it call twenty different bioinformatics APIs without drowning in tool definitions? How does a variable computed in step 3 survive to step 8? How do you render a `.pdb` file so a human can actually look at the fold?

Open Science Toolkit is my attempt to build every one of those pieces on an open stack — and, crucially, to make each piece **liftable**. You don't have to adopt the whole thing. Clone it, take the skill loader, or just the MCP aggregation layer, or just the stateful kernel, and wire it into your own agent.

---

## The four hard problems, and how the toolkit solves them

### 1. Skills: how does the agent know what it can do?

Dumping 29 tool definitions into a system prompt is how you burn a context window and confuse a model. Instead, each capability is a **skill** — a directory with a `SKILL.md` (YAML frontmatter + instructions) and any helper scripts it needs.

The loader uses **progressive disclosure**: the agent first sees a compact *menu* of skill names and one-line descriptions. Only when a skill matches the task at hand does its full body get injected. It's lazy loading for agent capabilities.

```
skills_assets/
  alphafold2/SKILL.md        ← monomer & multimer structure prediction
  proteinmpnn/SKILL.md       ← inverse-fold a backbone into sequence
  evo2/SKILL.md              ← score / embed / generate DNA
  literature-review/SKILL.md ← find, verify & synthesize papers
  ... 29 total
```

29 skills across six themes: **structure prediction & docking** (6), **protein design & embedding** (4), **genomics & single-cell** (4), **figures & visualization** (2), **literature & writing** (4), and **compute & workflow** (9). The last group is the meta-layer: remote GPU execution on Modal or SSH/SLURM, a `skill-creator` for authoring new skills, and `self-awareness` for introspecting the session.

Because the format is the standard Agent Skills convention, these drop into any compatible harness.

### 2. Data sources: 62 APIs without the tool-definition tax

Science lives behind APIs — PubMed, bioRxiv, ChEMBL, ZINC, clinical trials, genome assemblies, variant databases, expression atlases, ontologies. Wire all of them in naively and you get an unusable tool list.

The toolkit wraps them as **24 domain MCP servers** — standard [Model Context Protocol](https://modelcontextprotocol.io) servers grouped by domain (literature, genomics, variants, chemistry, trials…), aggregating **62 HTTP clients** behind one common layer that handles rate limiting, retries, and gating. Servers are **injected on demand** by query domain, so the agent only ever sees the tools relevant to what it's doing.

And because they're plain MCP servers, they work standalone in **any** MCP client — Claude Desktop, Cursor, whatever you use.

### 3. State: a kernel, not a calculator

Most agent "code execution" is stateless: each snippet runs in a vacuum. Real analysis isn't like that — you load a dataset once and keep working on it.

`KernelSession` wraps `jupyter_client` + `ipykernel` so the agent gets a **persistent IPython kernel**. Variables live across cells. Load your dataframe in one step, transform it three steps later, plot it at the end — exactly like a human at a notebook. This one component changes what kinds of multi-step analyses are even possible.

### 4. Identity vs. capability: four agents from shared parts

An agent profile is a `metadata.yaml` with an **identity prompt** (who it is), **working-style rules** (how it behaves), and **capability switches**. The toolkit ships four:

- **operon** — the main scientific-computing agent, full tools.
- **onboarding** — first-run guided setup, ask-only.
- **reviewer** — reviews transcripts for hallucination / fabrication.
- **bookmarker** — extracts key points from a conversation.

A neat engineering detail: tool trimming. OpenHands filters tools with a *positive-match* regex (`filter_tools_regex`), but profiles are authored as an `excluded_tools` **denylist** — which reads far more naturally. The bridge compiles the denylist into a **negative-lookahead regex**, so you write "exclude these" and the harness enforces "allow everything else." Small thing; big quality-of-life win when authoring agents.

---

## The architecture, briefly

| Layer | Implementation |
|---|---|
| Runtime | OpenHands V1 SDK (MIT), `LocalWorkspace` — no Docker to start |
| Brain | any OpenAI-compatible endpoint, credentials via env only |
| Kernel | `KernelSession` (`jupyter_client` + `ipykernel`), variables persist |
| Skills | loader with search-based lazy injection (menu first, body on match) |
| Agents | OpenHands `Agent` + `filter_tools_regex` tool trimming |
| 3D viewer | 3Dmol.js embedded in a self-contained web UI |

The brain is deliberately model-agnostic: point it at any OpenAI-compatible endpoint via three env vars and go. Credentials live in the environment only — never in a committed file.

---

## What's actually in the box

- **Assembly code** — `src/open_science/` (~340 Python files): the FastAPI server, agent loader, kernel, brain, skill loader, datasource registry, provenance layer, artifact rendering, remote-compute glue, and the web UI.
- **29 skills** — `skills_assets/` (29 `SKILL.md` + 79 helper scripts).
- **4 agent profiles** — `agents_assets/`.
- **24 MCP data sources** — `src/open_science/datasources/vendor/` (62 API clients).
- **Design teardown** — `docs/design-teardown/` (9 chapters explaining the patterns: config-as-tuning-log, identity/working-style separation, retrieve-don't-recompute, progressive disclosure, MCP aggregation, self-knowledge).
- **Verification scripts** — `tests/` (per-stage smoke tests for brain round-trip, stateful kernel, MCP sources, skill loading, agent trimming).

Everything is designed to be **reusable**. The design-teardown chapters exist specifically so you can steal the *ideas*, not just the code.

---

## Design principles worth stealing even if you never touch the repo

1. **Progressive disclosure over big prompts.** Show the menu, load the body on match. Context is a budget.
2. **Retrieve, don't recompute.** A read-only provenance layer means the agent looks up prior artifacts instead of redoing expensive work.
3. **Separate identity from working style.** Who the agent *is* and how it *behaves* are different axes — keep them in different fields so custom profiles can override one without losing the other.
4. **Aggregate APIs behind one gated layer.** Rate limiting, retries, and gating belong in a shared common layer, not copy-pasted into 62 clients.
5. **State is a feature.** A persistent kernel unlocks analyses a stateless executor simply can't do.

---

## Try it

```bash
git clone https://github.com/WangHuiNEU/open-science-toolkit
cd open-science-toolkit
pip install -e . --no-deps
cp .env.example .env          # set LLM_BASE_URL / LLM_MODEL / LLM_API_KEY
python -m open_science.server --serve --port 8000
# http://localhost:8000/        chat UI
# http://localhost:8000/docs    API panel
```

It's **Apache-2.0**, built on [OpenHands](https://github.com/All-Hands-AI/OpenHands) (MIT) and 3Dmol.js (BSD). Model weights carry their own licenses.

If any single component is useful to you — the skill loader, the MCP aggregation, the stateful kernel, the denylist→regex tool-trimming bridge — take it. That's what it's for.

**⭐ Repo: https://github.com/WangHuiNEU/open-science-toolkit**

Issues, PRs, and questions welcome.
