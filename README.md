# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity as a set of linked projections across state, space, and time.

The project starts from a philosophical intuition — that a person or agent can be represented through multiple experiential or operational views — and turns that intuition into a formal systems question:

> What must remain invariant when representation changes, so that we can still prove that the resulting state belongs to the same identity?

This repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, or Atman. Those terms are used as names for nodes and observer roles inside a formal model. The engineering goal is to study continuity, provenance, observer independence, projection, and global coherence.

## v0.1 model

We begin with eight conceptual nodes:

- `S1` — waking-space identity projection
- `S2` — dream-space identity projection
- `S3 / A1` — Atman-1, observer/bridge of spatial projections
- `S4` — past identity projection
- `S5` — future identity projection
- `S6 / A2` — Atman-2, observer/bridge of temporal projections
- `S7 / A3` — observer of spatial-temporal consistency
- `S8 / A4` — coherence keeper for the observer system itself

### Spatial axis

```text
S1  <------>  S3 / A1  <------>  S2
waking        bridge             dream
```

### Temporal axis

```text
S4  <------>  S6 / A2  <------>  S5
past          bridge             future
```

### Observer hierarchy

```text
A1 = Observer(space)
A2 = Observer(time)
A3 = Observer(A1, A2)
A4 = Coherence(A1, A2, A3)
```

The central idea is that identity is not equated with one coordinate or representation. It is treated as something that must remain **traceably coherent across transformations**.

## Core invariant

> **Representation may change across state, space, and time; identity must remain coherently traceable across the transformation.**

A transition is therefore not accepted merely because its local output is valid. It must also preserve enough provenance, continuity, and cross-view consistency to establish that the before-state and after-state belong to one coherent lineage.

A compact engineering form is:

```text
A1 = PASS
A2 = PASS
          does not imply
A3 = PASS
A4 = PASS
```

Two locally valid observer results can still be globally incompatible when they bind to different identities, branches, or generations.

## v0.2 executable core

Version `0.2.0` turns the first invariants into executable contracts.

- [`schemas/identity-receipt.schema.json`](schemas/identity-receipt.schema.json) defines the identity/state/generation/branch/provenance envelope.
- [`schemas/observer-receipt.schema.json`](schemas/observer-receipt.schema.json) defines inspectable observer verdicts.
- [`model/lattice.py`](model/lattice.py) implements `A1`, `A2`, `A3`, and `A4`.
- [`tests/test_lattice.py`](tests/test_lattice.py) contains positive and deliberate collision cases.

The first executable counterexample is:

> `A1 = PASS` and `A2 = PASS`, while `A1.branch_ref != A2.branch_ref` or `A1.generation != A2.generation`; therefore `A3 = FAIL` and global coherence must not be accepted.

Run locally with:

```bash
python -m pip install pytest
python -m pytest -q
```

The same invariant suite runs in GitHub Actions on pushes to `main` and on pull requests.

## Why this may matter for AI systems

The same abstract problem appears in agent systems when one agent is represented as different runtime states:

- prompt or policy state;
- working memory;
- compressed memory;
- simulation;
- replay;
- execution trace;
- restored checkpoint;
- forked planning branch.

If each representation looks locally valid but their lineage is not preserved, a system can silently confuse different generations, branches, or identities.

ATMAN-LATTICE explores formal contracts that make this detectable.

## Documents

- [THEORY.md](THEORY.md) — conceptual and formal model
- [INVARIANTS.md](INVARIANTS.md) — invariant set

## Status

`v0.2` — executable research core. The conceptual model now has machine-readable receipt schemas, executable observer layers, deliberate failure fixtures, and CI-backed invariant tests. No empirical metaphysical claims are made.

Next targets: stronger provenance binding, signed/hashed receipts, use-time observer freshness, replay fixtures, and integration experiments with agent checkpoint/memory systems.
