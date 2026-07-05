# Open Science Toolkit

![license](https://img.shields.io/badge/license-Apache--2.0-blue)

Reusable components for building a Claude-Science-style research agent on an open-source
stack — 29 skills, 4 agent profiles, 24 domain MCP servers, a stateful Python kernel, and
a browser chat UI with 3D structure viewing.

```bash
pip install -e . --no-deps
cp .env.example .env          # set LLM_BASE_URL / LLM_MODEL / LLM_API_KEY
python -m open_science.server --serve --port 8000
# http://localhost:8000/        chat UI
# http://localhost:8000/docs    API panel
```

---

## 📦 Skills — 29 research skills

Task instructions for the agent, grouped by theme. Each skill is a `SKILL.md` with
YAML frontmatter, loaded on demand ([Agent Skills format](https://docs.claude.com/en/docs/agents-and-tools/agent-skills)).

| Theme | Count | Examples |
|---|---|---|
| 🧬 Structure prediction & docking | 6 | AlphaFold2, Boltz, Chai-1, ESMFold2, OpenFold3, DiffDock |
| ✏️ Protein design & embedding | 4 | ProteinMPNN, LigandMPNN, SolubleMPNN, ESM-2 |
| 🔬 Genomics & single-cell | 4 | Borzoi, Evo-2, scGPT, scVI |
| 📊 Figures & visualization | 2 | figure-composer, figure-style |
| 📝 Literature & writing | 4 | literature-review, paper-narrative, indication-dossier, pdf-explore |
| ⚙️ Compute & workflow | 9 | remote-compute (Modal/SSH), skill-creator, customize, self-awareness |

### 🧬 Structure prediction & docking (6)

| Skill | Purpose |
|---|---|
| [alphafold2](skills_assets/alphafold2/SKILL.md) | Monomer & multimer structure prediction with AlphaFold2 |
| [boltz](skills_assets/boltz/SKILL.md) | Protein / nucleic-acid / small-molecule complex prediction |
| [chai1](skills_assets/chai1/SKILL.md) | Protein / nucleic-acid / small-molecule complex prediction |
| [esmfold2](skills_assets/esmfold2/SKILL.md) | All-atom co-folding with ESMFold2 / ESMFold2-Fast |
| [openfold3](skills_assets/openfold3/SKILL.md) | Structure prediction with the open-weights OpenFold3 |
| [diffdock](skills_assets/diffdock/SKILL.md) | Diffusion-based protein–ligand docking |

### ✏️ Protein design & embedding (4)

| Skill | Purpose |
|---|---|
| [proteinmpnn](skills_assets/proteinmpnn/SKILL.md) | Inverse-fold a backbone into sequence |
| [ligandmpnn](skills_assets/ligandmpnn/SKILL.md) | Inverse-fold with ligand / nucleic-acid / metal context |
| [solublempnn](skills_assets/solublempnn/SKILL.md) | Inverse-fold biased toward soluble sequences |
| [fair-esm2](skills_assets/fair-esm2/SKILL.md) | Protein embeddings with Meta's ESM-2 |

### 🔬 Genomics & single-cell (4)

| Skill | Purpose |
|---|---|
| [borzoi](skills_assets/borzoi/SKILL.md) | Predict genome-wide functional tracks from DNA |
| [evo2](skills_assets/evo2/SKILL.md) | Score / embed / generate DNA with Evo 2 |
| [scgpt](skills_assets/scgpt/SKILL.md) | Embed & annotate single-cell expression with scGPT |
| [scvi-tools](skills_assets/scvi-tools/SKILL.md) | Probabilistic single-cell RNA-seq with scVI |

### 📊 Figures & visualization (2)

| Skill | Purpose |
|---|---|
| [figure-composer](skills_assets/figure-composer/SKILL.md) | Compose a publication-grade multi-panel figure |
| [figure-style](skills_assets/figure-style/SKILL.md) | Figure correctness & legibility rules |

### 📝 Literature & writing (4)

| Skill | Purpose |
|---|---|
| [literature-review](skills_assets/literature-review/SKILL.md) | Find, verify & synthesize scientific literature |
| [paper-narrative](skills_assets/paper-narrative/SKILL.md) | Judge & reshape the story a paper's figures tell |
| [indication-dossier](skills_assets/indication-dossier/SKILL.md) | Generate a therapeutic indication dossier |
| [pdf-explore](skills_assets/pdf-explore/SKILL.md) | Locate / compare / extract across whole PDFs |

### ⚙️ Compute & workflow (9)

| Skill | Purpose |
|---|---|
| [compute-env-setup](skills_assets/compute-env-setup/SKILL.md) | Set up a runtime on remote compute |
| [remote-compute-modal](skills_assets/remote-compute-modal/SKILL.md) | Run GPU jobs on your own Modal account |
| [remote-compute-ssh](skills_assets/remote-compute-ssh/SKILL.md) | Submit → wait → harvest on SSH / SLURM hosts |
| [managed-model-endpoints](skills_assets/managed-model-endpoints/SKILL.md) | Register local / remote model service endpoints |
| [using-model-endpoint](skills_assets/using-model-endpoint/SKILL.md) | Call a registered endpoint over its HTTP API |
| [skill-creator](skills_assets/skill-creator/SKILL.md) | Create, improve & benchmark skills |
| [customize](skills_assets/customize/SKILL.md) | Author custom agent profiles & new skills |
| [self-awareness](skills_assets/self-awareness/SKILL.md) | Introspect the session DB / SDK via `host.query()` |
| [product-self-knowledge](skills_assets/product-self-knowledge/SKILL.md) | Ground product facts in authoritative sources |

---

## 🤖 Agents — 4 profiles

Each agent is a `metadata.yaml` defining an identity prompt, working-style rules, and
capability switches (`excluded_tools`, `enable_thinking`, …).

| Agent | Role |
|---|---|
| [operon](agents_assets/operon/metadata.yaml) | Main scientific-computing agent (full tools) |
| [onboarding](agents_assets/onboarding/metadata.yaml) | First-run guided setup (ask-only) |
| [reviewer](agents_assets/reviewer/metadata.yaml) | Transcript hallucination / fabrication review |
| [bookmarker](agents_assets/bookmarker/metadata.yaml) | Extract key points from a conversation |

Tool trimming maps an `excluded_tools` denylist to OpenHands' `filter_tools_regex`
(a positive-match filter) via a negative-lookahead regex —
see [`src/open_science/agents.py`](src/open_science/agents.py).

---

## 🔌 MCP Servers — 24 domain servers

Standard [Model Context Protocol](https://modelcontextprotocol.io) servers wrapping public
science APIs, injected on demand by query domain.

| Server | Domain |
|---|---|
| mcp_bio | General bio lookups |
| mcp_literature / mcp_pubmed / mcp_biorxiv | Literature & preprints |
| mcp_genomes / mcp_genomics | Genome assemblies |
| mcp_variants / mcp_human_genetics / mcp_clinical_genomics | Variants & clinical genetics |
| mcp_expression / mcp_regulation / mcp_rna | Expression & regulation |
| mcp_protein_annotation / mcp_structures_interactions | Proteins & structures |
| mcp_chembl / mcp_chemistry / mcp_zinc | Chemistry & compounds |
| mcp_clinical_trials / mcp_drug_regulatory | Trials & regulatory |
| mcp_cellguide / mcp_cancer_models | Cell & cancer models |
| mcp_genes_ontologies / mcp_omics_archives / mcp_biomart / mcp_research_resources | Ontologies & archives |

All share `mcp_servers_common` (rate limiting, retries, gating). Compatible with any MCP
client (Claude Desktop, Cursor, …).

---

## 🏗️ Architecture

| Layer | Implementation |
|---|---|
| Runtime | OpenHands V1 SDK (MIT), `LocalWorkspace` — no Docker to start |
| Brain | any OpenAI-compatible endpoint, credentials via env only |
| Kernel | `KernelSession` (`jupyter_client` + `ipykernel`), variables persist across cells |
| Skills | loader with search-based lazy injection (menu first, body on match) |
| Agents | OpenHands `Agent` + `filter_tools_regex` tool trimming |
| 3D viewer | 3Dmol.js embedded in the self-contained web UI |

See [`docs/design-teardown/`](docs/design-teardown/) for the design patterns explained,
and [`docs/ROADMAP.md`](docs/ROADMAP.md) for the phased build and sandbox notes.

---

## 📁 What's inside

Everything here is reusable — clone it and wire the pieces into your own agent.

**1. Assembly code** — `src/open_science/` (~340 Python files)

| Module | What it does |
|---|---|
| `server.py` | FastAPI wiring: mounts the chat UI on OpenHands agent-server, adds `POST /chat/send` |
| `agents.py` | Agent profile loader + the `excluded_tools` → `filter_tools_regex` trimming bridge |
| `runtime.py` | `KernelSession` — stateful IPython kernel (variables persist across cells) |
| `brain.py` | Builds an `LLM` from any OpenAI-compatible endpoint (env-only credentials) |
| `skills/` | Skill loader — menu-first, lazy body injection on `search_skills` match |
| `datasources/` | MCP source registry + on-demand injection (`inject.py`, `registry.py`, `launcher.py`) |
| `provenance/` | Read-only SQLite schema + `host.query()` surface for artifacts / self-introspection |
| `render/` | Artifact rendering (structure files → 3D viewer) |
| `remote.py` | Remote GPU compute (Modal / SSH byoc) glue |
| `web/` | Self-contained chat UI: `index.html` + `3Dmol-min.js` (no external CDN) |

**2. Skills** — `skills_assets/` (29 `SKILL.md` + 79 helper scripts)

The full skill catalog above, each a directory with a `SKILL.md` and its scripts. Drop-in
for any Agent-Skills-compatible harness.

**3. Agent profiles** — `agents_assets/` (4 `metadata.yaml`)

`operon` / `onboarding` / `reviewer` / `bookmarker` — identity prompt, working-style rules,
and capability switches per role.

**4. MCP data sources** — `src/open_science/datasources/vendor/` (24 domain servers, 62 API clients)

24 `mcp_*` servers aggregating 62 HTTP clients over public science APIs, all sharing one
common layer (`mcp_servers_common`: rate limiting, retries, gating). Usable standalone with
any MCP client.

**5. Design teardown** — `docs/design-teardown/` (9 chapters)

The design patterns behind the above, explained: config-as-tuning-log, identity/working-style
separation, retrieve-don't-recompute, progressive disclosure, MCP aggregation, self-knowledge,
and a transferable-principles table.

**6. Verification scripts** — `tests/` (6 stage checks)

Per-stage smoke tests (`verify_stage0..5.py`) covering brain round-trip, stateful kernel, MCP
sources, skill loading, and agent trimming.

---

## 🔒 Security

- API keys via environment variables only (`.env` is gitignored)
- Conversation content passes through the brain endpoint — send sensitive data as artifact pointers, not raw
- Data sources call public APIs; respect their rate limits and ToS
- Model weights carry their own licenses

## 📄 License

Apache-2.0 — see [LICENSE](LICENSE) and [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
Built on [OpenHands](https://github.com/All-Hands-AI/OpenHands) (MIT), 3Dmol.js (BSD).
