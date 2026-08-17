# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Governance, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, possibility, reconciliation, authorization, signer authority, privileged execution, trust-root evolution, transition geometry, geometric coherence, and finite verification capacity.

> What must remain invariant when representation changes, futures branch, paths become order-sensitive, verification capacity saturates, or authority itself changes — so that identity, ancestry, path dependence, uncertainty, and permission remain provable rather than merely asserted?

The repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, Atman, quantum worlds, physical multiverses, or physical torsion fields. Those terms are conceptual labels and thought experiments inside a formal model. The engineering target is testable continuity, provenance, freshness, authority, governance, compatibility, path dependence, verification coverage, and globally coherent execution.

## Core geometry

```text
Spatial axis:   S1 <----> S3 / A1 <----> S2
                waking     observer       dream

Temporal axis:  S4 <----> S6 / A2 <----> S5
                past       observer       future

A3 = Observer(A1, A2)
A4 = Coherence(A1, A2, A3)
```

The accumulated executable warnings are:

```text
Local PASS != Global Coherence
Historical PASS != Current Authorization
Same identity != Same history
Valid parents != Automatically coherent merge
Valid token != Reusable capability
Valid token != Authorized consumption
Revocation != History erasure
Valid signature != Valid authority
Historical authority != Current authority
Granted role != Required operation role
Verified proof != Executed permission unless checked before use
Caller claim != Runtime authority
Caller mutation != Runtime mutation
Client ledger != Runtime authorization state
Execution authority != Trust-governance authority
Bootstrap trust != Ongoing trust authority
Potentiality != History
Valid(A) + Valid(B) != Coexist(A,B)
Composite state != Permission to erase parent histories
Keeper != Sovereign
Valid(A) + Valid(B) != Commute(A,B)
Same result != Same journey
Torsion != Invalidity
Semantic return != History erasure
HOLD != FAIL
A3 local consistency != A4 global commit permission
Unverified != Invalid
Capacity admission != Semantic verdict
ADMITTED != VERIFIED
Deferred != Pruned
```

## v1.6 — Verification Pressure / Temporal Loom

v1.6 models finite A3/A4 verification capacity without converting overload into a semantic verdict.

```text
branch/path evidence
  |   |   |   |   |   |
  v   v   v   v   v   v
       verifier
   finite capacity
       |
       +-- ADMITTED
       +-- DEFERRED_CAPACITY
       +-- DEFERRED_OVERSIZED
```

The central law is:

```text
UNVERIFIED != INVALID
```

A work item that cannot be processed in the current capacity window remains explicit evidence. It is deferred, not silently dropped and not labeled FAIL.

### Deterministic pressure accounting

`VerificationWorkItem` binds the exact subject, evidence digest, declared cost, priority, submission time, and work hash.

`VerificationCapacityPolicy` binds:

```text
capacity_units
max_admitted_items
aging_quantum
```

The deterministic scheduler uses an aging-aware effective priority:

```text
effective_priority = priority + floor(wait_time / aging_quantum)
```

so old work can rise above continuously arriving fresh work.

Every offered item must appear exactly once:

```text
OFFERED = ADMITTED ∪ DEFERRED_CAPACITY ∪ DEFERRED_OVERSIZED
```

with pairwise-disjoint dispositions. Overload may defer verification; it may not erase the need to verify.

Pressure states are:

```text
NORMAL     -> everything admitted
PRESSURED  -> some admitted, some deferred
SATURATED  -> nothing offered can be admitted now
```

### Admission is not completion

A second gate tracks verification coverage:

```text
ADMITTED
   |
   +-- completed
   +-- pending

DEFERRED
   |
   +-- preserved as unresolved verification debt
```

Therefore:

```text
ADMITTED != VERIFIED
```

A base `PASS` survives only when every required item was admitted **and** completed.

```text
all required work completed  -> base decision may survive
pending admitted work        -> HOLD
deferred required work       -> HOLD
invalid pressure evidence    -> FAIL
claim deferred work complete -> FAIL
```

This is the operational version of the Temporal Loom lesson: finite throughput is a property of the verifier, not evidence that excess branches are wrong.

Protocol: [`docs/v1.6-verification-pressure.md`](docs/v1.6-verification-pressure.md)

Invariants: [`docs/v1.6-invariants.md`](docs/v1.6-invariants.md)

Machine-readable contracts:

- [`schemas/verification-work-item.schema.json`](schemas/verification-work-item.schema.json)
- [`schemas/verification-capacity-policy.schema.json`](schemas/verification-capacity-policy.schema.json)
- [`schemas/verification-pressure-receipt.schema.json`](schemas/verification-pressure-receipt.schema.json)
- [`schemas/verification-coverage-receipt.schema.json`](schemas/verification-coverage-receipt.schema.json)

## v1.5 — Geometric Coherence Gate

v1.5 connects transition-geometry evidence directly to the A3/A4 hierarchy.

```text
A1 + A2
   |
   v
  A3
   +-- torsion evidence
   +-- curvature evidence
   +-- geometric policy
   v
A3-GEOMETRY
PASS / HOLD / FAIL
   |
   v
A4-GEOMETRY
```

The default policy preserves history-only torsion/holonomy as evidence, places semantic torsion/curvature on `HOLD`, and allows explicit policy to escalate to `FAIL`.

A4 aggregates monotonically:

```text
PASS < HOLD < FAIL
```

Protocol: [`docs/v1.5-geometric-coherence-gate.md`](docs/v1.5-geometric-coherence-gate.md)

Invariants: [`docs/v1.5-invariants.md`](docs/v1.5-invariants.md)

## v1.4 — Transition Geometry

v1.4 introduces discrete engineering analogues of torsion and curvature. These are not claims about physical torsion fields.

For two valid transitions:

\[
\tau_X(A,B)=\Delta(B\circ A(X),A\circ B(X)).
\]

Torsion classifications:

```text
CLOSED
SEMANTICALLY_CLOSED_HISTORY_DIVERGENT
TORSION_DETECTED
```

For a closed loop:

\[
\kappa_X(L)=\Delta(X,L(X)).
\]

Curvature classifications:

```text
FLAT_LOOP
SEMANTICALLY_CLOSED_WITH_HOLONOMY
CURVATURE_DETECTED
```

The core rules are:

```text
Same result != Same journey
Torsion != Invalidity
Semantic closure != History erasure
```

Protocol: [`docs/v1.4-transition-geometry.md`](docs/v1.4-transition-geometry.md)

Invariants: [`docs/v1.4-invariants.md`](docs/v1.4-invariants.md)

## v1.3 — Multiverse Semantics

v1.3 separates potential futures from committed history, adds explicit branch coexistence/incursion semantics, and requires narrative-preserving composition.

```text
Potentiality != History
Valid(A) + Valid(B) != Coexist(A,B)
Composite(C) => Parents(C) preserved
Preserve(Worlds) != AuthorityToRewrite(Worlds)
```

Protocol: [`docs/v1.3-multiverse-semantics.md`](docs/v1.3-multiverse-semantics.md)

Invariants: [`docs/v1.3-invariants.md`](docs/v1.3-invariants.md)

## v1.2 — Trust-Root Evolution

v1.2 separates execution and trust governance:

```text
execution plane:   ATMAN-RUNTIME/1.1
governance plane:  ATMAN-TRUST/1.2
```

Trust-root mutation requires a quorum of distinct currently trusted roots over the exact transition, and persisted trust policy outranks stale bootstrap configuration after initialization.

Protocol: [`docs/v1.2-trust-root-evolution.md`](docs/v1.2-trust-root-evolution.md)

Invariants: [`docs/v1.2-invariants.md`](docs/v1.2-invariants.md)

## v1.1 — Full Runtime Plane

v1.1 closes the privileged lifecycle inside one reference runtime plane, including observer execution, token issue/consume/revoke, merge, server-owned capability secrets, and atomically serialized authorization state.

> **At most one terminal authorization event may commit for an exact token digest.**

Protocol: [`docs/v1.1-full-runtime-plane.md`](docs/v1.1-full-runtime-plane.md)

Invariants: [`docs/v1.1-invariants.md`](docs/v1.1-invariants.md)

## v1.0 — ATMAN Runtime

v1.0 introduced the process-separated privileged observer plane:

> **Client permission claims do not become privileged execution until the runtime process independently verifies the exact authority.**

Protocol: [`docs/v1.0-atman-runtime.md`](docs/v1.0-atman-runtime.md)

Invariants: [`docs/v1.0-invariants.md`](docs/v1.0-invariants.md)

## Earlier evolution

- **v0.2** — executable A1/A2/A3/A4 observers.
- **v0.3** — SHA-256 parent-linked identity lineage.
- **v0.4** — freshness, context binding, and `UseToken`.
- **v0.5** — restore creates a new branch; restore is not continuation.
- **v0.6** — branch merge with exact ancestry and explicit conflict resolution.
- **v0.7** — one-time consumption/revocation and authenticated authorization ledger.
- **v0.8** — Ed25519 signer identity, roles, scopes, and policy generations.
- **v0.9** — exact pre-execution authority enforcement.

## Why this matters for AI systems

The same integrity problem appears when agents move through working memory, simulations, alternative plans, checkpoints, restored branches, reconciled memories, changing tool contexts, delegated capabilities, long-horizon execution, governance changes, order-sensitive tool workflows, and verification backlogs.

ATMAN-LATTICE keeps these questions separate:

- Is this still the same identity?
- Is this the same history?
- Is this merely a possible future, or was it committed?
- Can two individually valid branches coexist?
- Did transition order change the result?
- Does path dependence require HOLD/reconciliation?
- Was required verification actually completed?
- Was work merely deferred because verifier capacity was exhausted?
- Did a composite result preserve every parent history?
- Is authorization still current?
- Did this signer have authority?
- Did privileged execution occur inside the intended trust boundary?
- Who had authority to change the roots that define authority?

## Run

```bash
python -m pip install -e . pytest
python -m pytest -q
```

Reference runtime worker:

```bash
python -m model.runtime_worker
```

It accepts:

```text
ATMAN-RUNTIME/1.1  — privileged execution plane
ATMAN-TRUST/1.2    — trust governance plane
```

The v1.3 multiverse semantics, v1.4 transition geometry, v1.5 geometric coherence gate, and v1.6 verification-pressure model currently live as explicit executable model primitives rather than new wire protocols.

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox or a claim about physical multiverses/torsion. Production use additionally requires protected keys, protected durable storage, authenticated transport, measured server-owned resource accounting, rollback-resistant backups, database/file permissions, and operational governance.

## Status

**v1.6.0 — Verification Pressure / Temporal Loom research core.**

The project now spans identity continuity, cryptographic lineage, potential-vs-committed futures, restore/fork semantics, cross-branch compatibility, narrative-preserving composition, transition torsion/curvature, policy-bound A3/A4 geometric coherence, explicit finite-capacity verification scheduling, preserved verification debt, PASS/HOLD/FAIL coverage semantics, one-time authorization, asymmetric signer authority, runtime enforcement, atomically serialized authorization state, and quorum-governed trust-root evolution.

Next targets: runtime wire integration for geometric/pressure gates, adaptive verification budgeting, measured server-owned work cost, rollback-resistant trust recovery, emergency governance, compensation receipts, generalized ancestry proofs, concurrency stress tests, and real agent planning/memory/tool integration.
