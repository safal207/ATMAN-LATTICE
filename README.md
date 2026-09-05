# ATMAN-LATTICE

**Identity, authority, evidence and governed recovery — a research runtime.**

ATMAN-LATTICE models how a system can revise decisions after new evidence without erasing the history that supported its earlier state. Historical validation is not current execution authority; a drift signal is not permission to roll back.

## Start here

| Your goal | Entry point |
|---|---|
| Start in Russian / начать по-русски | [START_HERE.md](START_HERE.md) |
| Run the existing research core | Commands below |
| Find protocols and integration boundaries | [RESEARCH_INDEX.md](RESEARCH_INDEX.md) |
| Inspect readiness and exact source | [PROJECT_STATUS.json](PROJECT_STATUS.json) |
| Preserve experiments and manage branches | [REPOSITORY_GUIDE.md](REPOSITORY_GUIDE.md) |
| Read the complete technical introduction | [README.previous.md](README.previous.md) |

## What can be used today

| Track | Use | Boundary |
|---|---|---|
| v1.19 research runtime on main | Study and test authority, evidence, revision and remediation contracts | Research reference; not a production deployment |
| Protocols, schemas and invariants | Inspect exact assumptions and design integrations | A model invariant is not proof about arbitrary external systems |
| CaPU × ATMAN recovery laboratory | Reproduce the separately pinned authority-module composition | Lives in CaPU draft PRs; not an integration of the full ATMAN runtime |

## Run the research core

From a checkout in an activated virtual environment:

```sh
python -m pip install -e . pytest
python -m pytest -q
```

The declared commands and source layout are unchanged. This documentation pass did not rerun the runtime suite. Baseline source: `e62c279b9148a7ae9dd1a4654f6ddeea6add4a3f`.

Start with [invariants](INVARIANTS.md), then the [v1.19 remediation protocol](docs/v1.19-drift-governed-remediation.md) and its [invariants](docs/v1.19-invariants.md). The previous README preserves all worker commands and earlier protocol routes.

## Research and readiness

The current reference separates proposal, assessment, selection, review and application. Forward rollback creates a new state; it does not erase the old one. Production use still needs protected keys, authenticated transport, rollback-resistant storage, trustworthy data provenance and deployment-specific mutation safeguards.

No metaphysical, physical-multiverse or real-world causal-identification proof is claimed. Conceptual labels are not empirical evidence.

## Architecture family

[BardoCompute](https://github.com/safal207/BardoCompute): transition representation · [COSMIC-ORGANICS](https://github.com/safal207/COSMIC-ORGANICS): sparse execution · [ATMAN-LATTICE](https://github.com/safal207/ATMAN-LATTICE): authority and governed revision · [CaPU](https://github.com/safal207/CaPU): effect admission and recovery.

This is a map of intended roles, not a verified four-repository composition.

## History and license

Readiness snapshot: **2026-09-05**. Existing code, workflows, branches, schemas and Apache-2.0 [license](LICENSE) are unchanged. The previous README is preserved byte-for-byte at [README.previous.md](README.previous.md).
