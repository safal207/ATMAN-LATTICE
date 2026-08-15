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

Two locally valid observer results can still be globally incompatible when they bind to different identities, branches, generations, or cryptographic lineage roots.

## v0.2 executable core

Version `0.2.0` turned the first invariants into executable contracts.

- [`schemas/identity-receipt.schema.json`](schemas/identity-receipt.schema.json) defines the identity receipt envelope.
- [`schemas/observer-receipt.schema.json`](schemas/observer-receipt.schema.json) defines inspectable observer verdicts.
- [`model/lattice.py`](model/lattice.py) implements `A1`, `A2`, `A3`, and `A4`.
- [`tests/test_lattice.py`](tests/test_lattice.py) contains positive and deliberate collision cases.

The first executable counterexample was:

> `A1 = PASS` and `A2 = PASS`, while `A1.branch_ref != A2.branch_ref` or `A1.generation != A2.generation`; therefore `A3 = FAIL` and global coherence must not be accepted.

## v0.3 cryptographic lineage

Version `0.3.0` makes lineage tamper-evident.

Each `IdentityReceipt` now commits to:

```text
identity_ref
state_ref
branch_ref
generation
sequence
payload_digest
parent_receipt_hash
lineage_root_hash
provenance_refs
        ↓
   receipt_hash
```

A genesis receipt creates a deterministic `lineage_root_hash`. Every successor receipt commits to the exact hash of its parent while preserving the same root commitment.

The chain therefore has the form:

```text
Genesis
  receipt_hash = H(R0)
        ↓
R1.parent_receipt_hash = H(R0)
R1.receipt_hash = H(R1)
        ↓
R2.parent_receipt_hash = H(R1)
        ↓
       ...
```

`verify_lineage_chain()` rejects altered receipts, sequence gaps, parent splices, root changes, identity changes, branch changes, and generation changes.

Observer receipts now also bind to `lineage_root_hash`, which creates a stronger counterexample:

```text
identity(A1)   == identity(A2)
branch(A1)     == branch(A2)
generation(A1) == generation(A2)
A1 = PASS
A2 = PASS

but

lineage_root(A1) != lineage_root(A2)

therefore

A3 = FAIL
A4 = FAIL
```

This means matching metadata is no longer sufficient evidence that two observer results belong to the same history.

Run locally with:

```bash
python -m pip install pytest
python -m pytest -q
```

The invariant suite also runs in GitHub Actions on pushes to `main` and on pull requests.

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

If each representation looks locally valid but their lineage is not preserved, a system can silently confuse different generations, branches, roots, or identities.

ATMAN-LATTICE explores formal contracts that make this detectable.

## Documents

- [THEORY.md](THEORY.md) — conceptual and formal model
- [INVARIANTS.md](INVARIANTS.md) — invariant set

## Status

`v0.3` — cryptographic lineage research core. Identity receipts now form a SHA-256 hash chain, observer proofs bind to a common lineage root, deliberate tamper/splice/root-collision fixtures are executable, and the invariant suite is CI-backed. No empirical metaphysical claims are made.

Next targets: signed receipts, use-time observer freshness, replay/restore proofs, branch-fork semantics, and integration experiments with agent checkpoint/memory systems.
