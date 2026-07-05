# Third-Party Licenses

Open Science Toolkit is licensed under Apache-2.0. It builds on and integrates the following
third-party components, each governed by its own license.

## Core dependencies

| Component | License | Notes |
|---|---|---|
| [OpenHands](https://github.com/All-Hands-AI/OpenHands) | MIT | Agent runtime / V1 SDK |
| [3Dmol.js](https://3dmol.csb.pitt.edu/) | BSD-3-Clause | Bundled in the web UI for 3D structure viewing |
| [jupyter_client](https://github.com/jupyter/jupyter_client) | BSD-3-Clause | Stateful kernel |
| [ipykernel](https://github.com/ipython/ipykernel) | BSD-3-Clause | Stateful kernel |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | HTTP server |

## Model weights and scientific tools

The skills in this repository orchestrate external models and tools that are **not
redistributed here**. Each carries its own license, which you must review and comply with
before use. Non-exhaustive:

| Tool / model | Typical license |
|---|---|
| AlphaFold2 | Apache-2.0 (code); weights per DeepMind terms |
| ESMFold2 / ESM-2 | MIT |
| Boltz | MIT |
| Chai-1 | Apache-2.0 (see upstream) |
| OpenFold3 | per upstream |
| DiffDock | MIT |
| ProteinMPNN / LigandMPNN / SolubleMPNN | MIT |
| Evo 2 | Apache-2.0 (see upstream) |
| Borzoi | Apache-2.0 (see upstream) |
| scGPT | MIT |
| scVI (scvi-tools) | BSD-3-Clause |

Licenses listed above are indicative and may change upstream. **Always verify the current
license of any model weight or tool at its source before downloading or using it.**

## Public data APIs

The MCP servers call public science APIs (PubMed / NCBI E-utilities, ChEMBL, ClinicalTrials.gov,
Ensembl, UniProt, and others). These are accessed over the network and not redistributed.
Respect each provider's terms of service and rate limits. Some (e.g. NCBI E-utilities) require
a contact email — see `.env.example`.
