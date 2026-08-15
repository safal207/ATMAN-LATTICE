# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity as a set of linked projections across state, space, and time.

The project starts from a philosophical intuition — that a person or agent can be represented through multiple experiential or operational views — and turns that intuition into a formal systems question:

> What must remain invariant when representation changes, so that we can still prove that the resulting state belongs to the same identity?

This repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, or Atman. Those terms are used as names for nodes and observer roles inside a formal model. The engineering goal is to study continuity, provenance, observer independence, projection, freshness, and global coherence.

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

Two locally valid observer results can still be globally incompatible when they bind to different identities, branches, generations, cryptographic lineage roots, or execution contexts.

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

Each `IdentityReceipt` commits to:

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

`verify_lineage_chain()` rejects altered receipts, sequence gaps, parent splices, root changes, identity changes, branch changes, and generation changes.

Observer receipts also bind to `lineage_root_hash`, producing a stronger counterexample:

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

Matching metadata is therefore not sufficient evidence that two observer results belong to the same history.

## v0.4 signed freshness and use binding

Version `0.4.0` closes the next gap: a verdict can be historically correct and still be unsafe to use later.

The model now separates three artifacts:

```text
ObserverReceipt
      ↓ exact digest
ObserverAttestation(context_digest, verified_at, HMAC)
      ↓ freshness + PASS required
UseToken(context_digest, expiry, HMAC)
      ↓ checked again at actual use
Execution
```

[`model/freshness.py`](model/freshness.py) implements:

- canonical execution-context digests;
- exact `ObserverReceipt` digests;
- authenticated `ObserverAttestation` envelopes;
- freshness checking with `verified_at` and caller-defined maximum age;
- short-lived `UseToken` issuance;
- use-time context revalidation;
- token expiry and tamper detection.

Machine-readable contracts are defined in:

- [`schemas/observer-attestation.schema.json`](schemas/observer-attestation.schema.json)
- [`schemas/use-token.schema.json`](schemas/use-token.schema.json)

The core TOCTOU counterexample is:

```text
verify under context C1 -> PASS
context changes to C2
old PASS is still authentic
but use under C2 -> FAIL(context_mismatch)
```

The v0.4 executable rule is therefore:

> **Historical PASS is not current authorization.**

Authorization is valid only for the exact observer result, lineage, execution context, and bounded time window to which it was cryptographically bound.

The research harness currently uses HMAC-SHA256 from the Python standard library. This is an authenticated MAC, not an asymmetric public-key signature. See [`docs/v0.4-signed-freshness.md`](docs/v0.4-signed-freshness.md) for the protocol and explicit non-goals.

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
- forked planning branch;
- a previously verified action used after policy, tool, or environment state changed.

If each representation looks locally valid but lineage or freshness is not preserved, a system can silently confuse different generations, branches, roots, identities, or authorization contexts.

ATMAN-LATTICE explores formal contracts that make this detectable.

## Documents

- [THEORY.md](THEORY.md) — conceptual and formal model
- [INVARIANTS.md](INVARIANTS.md) — invariant set
- [v0.4 signed freshness](docs/v0.4-signed-freshness.md) — verification-to-use protocol

## Status

`v0.4` — signed-freshness research core. Identity lineage is hash-linked, observer results can be authenticated under an explicit context and verification time, and short-lived use tokens require that the same context still holds at the actual use boundary. Deliberate stale-context, expiry, receipt-tamper, and token-tamper fixtures are executable and CI-backed. No empirical metaphysical claims are made.

Next targets: asymmetric signer identities, replay/one-time consumption protection, revocation, explicit branch-fork/merge semantics, and integration experiments with real agent checkpoint/memory/tool systems.
