# ATMAN-LATTICE — research index

Snapshot: 2026-09-05. [Start](README.md) · [Lifecycle](REPOSITORY_GUIDE.md)

Selected-track navigation, not a complete audit of all branches. Baseline main source: `e62c279b9148a7ae9dd1a4654f6ddeea6add4a3f`. Documentation publication changes no executable source or measured status.

| Track | Entry | Boundary |
|---|---|---|
| Identity and authority | [model](model), [invariants](INVARIANTS.md) | Formal/runtime engineering model, not metaphysical proof |
| v1.19 governed remediation | [Protocol](docs/v1.19-drift-governed-remediation.md), [invariants](docs/v1.19-invariants.md) | Proposal, assessment, selection, review and fresh apply remain distinct |
| v1.18 replication monitoring | [Protocol](docs/v1.18-temporal-external-replication.md) | Monitoring is not direct mutation authority |
| Earlier protocol layers | [Complete prior introduction](README.previous.md) | Historical contracts remain visible; later names do not silently replace them |
| CaPU process recovery v1 | [CaPU PR #103](https://github.com/safal207/CaPU/pull/103), source `977864167c65f161e6db87b3d14257a11a67516f` | Separate draft; uses only pinned authority.py |
| CaPU loopback HTTP v2 | [CaPU PR #104](https://github.com/safal207/CaPU/pull/104), source `8a2f2a37023a50aeac52cb8c8aed84b2eeceec88` | Separate draft; no full ATMAN integration or independent-device trust proof |

## Exact-source reproduction

```sh
git fetch origin
git worktree add --detach ../ATMAN-reference e62c279b9148a7ae9dd1a4654f6ddeea6add4a3f
cd ../ATMAN-reference
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -e . pytest
python -m pytest -q
```

These commands are provided from the pinned project instructions; no runtime tests were rerun during this organization pass.

## Research questions, not shipped capabilities

Evaluate the operational cost of governance, completion under continuously changing evidence, independently rooted external evidence and restricted real-world mutation. Protected keys, authenticated transport and rollback-resistant storage remain deployment requirements, not features inferred from local tests.

## Evidence and promotion

Use full source SHAs, not only branch names. Keep observed results, negative controls and commands with the experiment. Linked CaPU reviews remain quota-blocked, not approved. This documentation does not approve or merge their code. Existing branch names, source files and PR bases are unchanged; no branch retirement is performed.
