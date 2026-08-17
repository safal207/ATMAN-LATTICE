# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Governance, Verification, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, possibility, reconciliation, authorization, privileged execution, trust-root evolution, transition geometry, geometric coherence, finite verification capacity, and durable verification debt.

> What must remain invariant when representation changes, futures branch, paths become order-sensitive, verification capacity saturates, or authority itself changes — so that identity, ancestry, uncertainty, path dependence, verification state, and permission remain provable rather than merely asserted?

The repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, Atman, quantum worlds, physical multiverses, or physical torsion fields. Those terms are conceptual labels and thought experiments inside a formal engineering model.

## Core geometry

```text
Spatial axis:   S1 <----> S3 / A1 <----> S2
                waking     observer       dream

Temporal axis:  S4 <----> S6 / A2 <----> S5
                past       observer       future

A3 = Observer(A1, A2) + path geometry
A4 = Global coherence + commit gate
```

## Accumulated executable warnings

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
Caller claim != Runtime authority
Client ledger != Runtime authorization state
Execution authority != Trust-governance authority
Potentiality != History
Valid(A) + Valid(B) != Coexist(A,B)
Keeper != Sovereign
Valid(A) + Valid(B) != Commute(A,B)
Same result != Same journey
Torsion != Invalidity
HOLD != FAIL
Unverified != Invalid
ADMITTED != VERIFIED
Deferred != Pruned
COMPLETED != PASS
Preview != Finalization
VerifierCapacity != RealityCapacity
```

# v1.7 — Runtime Verification Plane

v1.7 moves geometric verification pressure from an in-memory formal model into a durable process/database plane.

```text
A3/A4 geometry
      |
      v
ATMAN-VERIFY/1.7
      |
      +-- submit verification debt
      +-- schedule under server-owned capacity
      +-- preserve deferred / oversized work
      +-- complete admitted work with PASS/HOLD/FAIL
      +-- preview current runtime decision
      +-- finalize with VERIFICATION_KEEPER authority
```

The three process-level protocol planes are now:

```text
ATMAN-RUNTIME/1.1  privileged execution
ATMAN-TRUST/1.2    trust-root governance
ATMAN-VERIFY/1.7   durable verification/debt/finalization
```

## Durable verification debt

Work is persisted in SQLite as:

```text
SUBMITTED
ADMITTED
DEFERRED_CAPACITY
DEFERRED_OVERSIZED
COMPLETED
```

A process restart does not erase deferred verification work while the runtime database survives.

The scheduler uses server-owned capacity configuration. Client claims about capacity do not replace runtime policy.

```text
UNVERIFIED != INVALID
DEFERRED != PRUNED
```

## Completion is an explicit verdict

`VerificationCompletionReceipt` binds the exact:

- work hash;
- subject identity;
- target geometry gate;
- schedule generation;
- pressure receipt;
- PASS/HOLD/FAIL result;
- evidence digest;
- verifier actor;
- runtime completion time.

Only work admitted in the **current** pressure window can be completed.

```text
COMPLETED != PASS
```

A completed `FAIL` dominates complete coverage.

## Geometric HOLD discharge

A geometric `HOLD` may become runtime `PASS` only through explicit completed verification:

```text
base geometry = HOLD
required verification work exists
all required work completed
all results = PASS
---------------------------
runtime decision = PASS
```

Otherwise:

```text
pending work        -> HOLD
deferred work       -> HOLD
completion HOLD     -> HOLD
completion FAIL     -> FAIL
base geometry FAIL  -> FAIL
HOLD + no work      -> HOLD
```

## Preview vs authoritative finalization

`evaluate_geometric_verification` returns a diagnostic runtime decision plus a stable `decision_state_hash`.

The time-stamped decision receipt may change as time advances; the state digest does not change merely because the clock changed.

Authoritative finalization requires:

```text
VERIFICATION_KEEPER
+
exact current decision_state_hash
+
current schedule generation
+
current pressure hash
```

If verification state changes between preview and finalization:

```text
preview S0
state -> S1
finalize(S0)
    X
stale verification decision
```

This is the v1.7 use-time binding for global verification state.

Protocol: [`docs/v1.7-runtime-verification-plane.md`](docs/v1.7-runtime-verification-plane.md)

Invariants: [`docs/v1.7-invariants.md`](docs/v1.7-invariants.md)

Machine-readable contracts:

- [`schemas/verification-completion-receipt.schema.json`](schemas/verification-completion-receipt.schema.json)
- [`schemas/runtime-verification-decision.schema.json`](schemas/runtime-verification-decision.schema.json)
- [`schemas/verification-finalization-receipt.schema.json`](schemas/verification-finalization-receipt.schema.json)

# Prior layers

## v1.6 — Verification Pressure / Temporal Loom

Finite A3/A4 capacity is modeled without converting overload into a semantic verdict.

```text
OFFERED = ADMITTED ∪ DEFERRED_CAPACITY ∪ DEFERRED_OVERSIZED
ADMITTED != VERIFIED
```

Aging raises old work over time so continuous fresh arrivals do not automatically starve older evidence.

Protocol: [`docs/v1.6-verification-pressure.md`](docs/v1.6-verification-pressure.md) · Invariants: [`docs/v1.6-invariants.md`](docs/v1.6-invariants.md)

## v1.5 — Geometric Coherence Gate

Torsion/curvature evidence enters A3/A4 under explicit `PASS < HOLD < FAIL` policy semantics.

Protocol: [`docs/v1.5-geometric-coherence-gate.md`](docs/v1.5-geometric-coherence-gate.md) · Invariants: [`docs/v1.5-invariants.md`](docs/v1.5-invariants.md)

## v1.4 — Transition Geometry

Discrete engineering analogues of torsion and curvature:

\[
\tau_X(A,B)=\Delta(B\circ A(X),A\circ B(X))
\]

\[
\kappa_X(L)=\Delta(X,L(X))
\]

```text
Same result != Same journey
Torsion != Invalidity
Semantic closure != History erasure
```

Protocol: [`docs/v1.4-transition-geometry.md`](docs/v1.4-transition-geometry.md) · Invariants: [`docs/v1.4-invariants.md`](docs/v1.4-invariants.md)

## v1.3 — Multiverse Semantics

```text
Potentiality != History
Valid(A) + Valid(B) != Coexist(A,B)
Composite(C) => Parents(C) preserved
Preserve(Worlds) != AuthorityToRewrite(Worlds)
```

Protocol: [`docs/v1.3-multiverse-semantics.md`](docs/v1.3-multiverse-semantics.md) · Invariants: [`docs/v1.3-invariants.md`](docs/v1.3-invariants.md)

## v1.2 — Trust-Root Evolution

Trust-root mutation requires a quorum of distinct currently trusted roots over the exact transition. Persisted trust policy outranks stale bootstrap configuration.

Protocol: [`docs/v1.2-trust-root-evolution.md`](docs/v1.2-trust-root-evolution.md) · Invariants: [`docs/v1.2-invariants.md`](docs/v1.2-invariants.md)

## v1.1 — Full Runtime Plane

Observer execution, token issue/consume/revoke, merge, server-owned secrets, and atomically serialized authorization state live behind `ATMAN-RUNTIME/1.1`.

Protocol: [`docs/v1.1-full-runtime-plane.md`](docs/v1.1-full-runtime-plane.md) · Invariants: [`docs/v1.1-invariants.md`](docs/v1.1-invariants.md)

## v1.0 — ATMAN Runtime

Client permission claims do not become privileged execution until a separate runtime process independently verifies exact authority.

Protocol: [`docs/v1.0-atman-runtime.md`](docs/v1.0-atman-runtime.md) · Invariants: [`docs/v1.0-invariants.md`](docs/v1.0-invariants.md)

## Earlier evolution

- **v0.2** — executable A1/A2/A3/A4 observers.
- **v0.3** — SHA-256 parent-linked identity lineage.
- **v0.4** — freshness/context binding and `UseToken`.
- **v0.5** — restore creates a new branch; restore is not continuation.
- **v0.6** — branch reconciliation with explicit conflict resolution.
- **v0.7** — one-time consumption/revocation ledger.
- **v0.8** — Ed25519 signer identity and scoped authority.
- **v0.9** — exact pre-execution authority enforcement.

## Why this matters for AI systems

Long-running agents can have valid alternative plans, restored memories, order-sensitive operations, changing authority, and more verification work than available capacity.

ATMAN-LATTICE keeps different questions separate:

- Is this still the same identity?
- Is this the same history?
- Was this future merely considered or actually committed?
- Can two valid branches coexist?
- Did operation order change the result?
- Is path dependence acceptable, HOLD-worthy, or rejected?
- Was verification actually completed?
- Was it only deferred because capacity ran out?
- Did the verifier return PASS/HOLD/FAIL?
- Is the preview still current at finalization time?
- Did the finalizer have authority?
- Who had authority to change the roots that define authority?

## Run

```bash
python -m pip install -e . pytest
python -m pytest -q
```

Execution/trust worker:

```bash
python -m model.runtime_worker
```

Verification worker:

```bash
python -m model.verification_worker
```

Reference protocols:

```text
ATMAN-RUNTIME/1.1
ATMAN-TRUST/1.2
ATMAN-VERIFY/1.7
```

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox or a claim about physical multiverses/torsion. Production use additionally requires protected keys, authenticated transport, rollback-resistant durable storage/backups, measured resource accounting, database/file permissions, and operational governance.

## Status

**v1.7.0 — Runtime Verification Plane research core.**

The project now spans identity continuity, cryptographic lineage, potential-vs-committed futures, restore/fork semantics, narrative-preserving reconciliation, transition torsion/curvature, policy-bound A3/A4 geometric coherence, finite verification-pressure scheduling, durable verification debt, authority-bound completion/finalization, one-time authorization, asymmetric signer authority, process-separated execution, serialized runtime state, and quorum-governed trust-root evolution.

Next targets: adaptive verification budgeting from measured runtime cost, automatic work decomposition for oversized checks, persistent finalization/audit history, rollback-resistant verification state, compensation receipts, generalized ancestry proofs, concurrency stress tests, and real agent planning/memory/tool integrations.
