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
- [INVARIANTS.md](INVARIANTS.md) — initial invariant set

## Status

`v0.1` — conceptual foundation. No empirical claims are made yet. The next stages are formalization, diagrams, executable state-transition models, and falsifiable experiments.
