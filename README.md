# ATMAN-LATTICE

**Identity, authority and governed recovery — an executable research reference, not a production trust system.**

ATMAN models how evidence and authority can change over time without erasing earlier decisions. Its v1.19 research core separates proposals, assessments, selection, review and application. Historical PASS is not current authorization; drift is not automatic rollback authority.

## Start here

| Your goal | Entry point |
|---|---|
| Начать по-русски | [START_HERE.md](START_HERE.md) |
| Find a runnable reference | Reproduction below |
| Find experiments, dependencies and evidence | [RESEARCH_INDEX.md](RESEARCH_INDEX.md) |
| Check readiness and exact revisions | [PROJECT_STATUS.json](PROJECT_STATUS.json) |
| Preserve research and work consistently | [REPOSITORY_GUIDE.md](REPOSITORY_GUIDE.md) |
| Record the next experiment | [EXPERIMENT_RECORD_TEMPLATE.md](EXPERIMENT_RECORD_TEMPLATE.md) |

## What can be used today

| Track | Intended use | Boundary |
|---|---|---|
| v1.19 model and workers | Reproduce identity, authority and remediation rules | Research model; deployment safeguards remain necessary |
| Schemas and invariants | Inspect and test explicit contracts | A valid receipt is not proof of external-world truth |
| CaPU × ATMAN v1/v2 | Reproduce a separate bounded recovery composition | Uses a pinned authority module, not the full ATMAN runtime |

## Reproduce the reference

From an existing clone, keep the documentation checkout and the reference separate:

```sh
git fetch origin
git worktree add --detach ../ATMAN-LATTICE-reference e62c279b9148a7ae9dd1a4654f6ddeea6add4a3f
cd ../ATMAN-LATTICE-reference
python -m venv .venv
# Activate .venv for your shell before installing dependencies.
python -m pip install -e . pytest
python -m pytest -q
```

This organization pass did not rerun the model suite. For protocols and worker commands see the [preserved full reference guide](README.previous.md), [invariants](INVARIANTS.md), [theory](THEORY.md), [model](model/) and [schemas](schemas/).

## Research and evidence

The [research index](RESEARCH_INDEX.md) distinguishes available code, bounded composition evidence and unresolved deployment work. Documentation publication does not approve linked code PRs. Production use still requires protected keys, authenticated transport, rollback-resistant storage, trustworthy external provenance and deployment-specific safeguards.

## Architecture family

[BardoCompute](https://github.com/safal207/BardoCompute): transition representation · [COSMIC-ORGANICS](https://github.com/safal207/COSMIC-ORGANICS): sparse execution · [ATMAN-LATTICE](https://github.com/safal207/ATMAN-LATTICE): authority and governed revision · [CaPU](https://github.com/safal207/CaPU): effect admission and recovery.

These roles are an integration map, not a verified four-repository system. No metaphysical or physical-causality claim is made.

## History and license

The previous README is preserved byte-for-byte at [README.previous.md](README.previous.md), keeping its relative links in the repository root. Existing code and Apache-2.0 licensing are unchanged. Snapshot: **2026-09-05**.
