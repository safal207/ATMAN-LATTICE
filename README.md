# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Governance, Verification, Economy, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, possibility, reconciliation, authorization, privileged execution, trust-root evolution, transition geometry, geometric coherence, finite verification capacity, durable verification debt, and adaptive verification-budget allocation.

> What must remain invariant when representation changes, futures branch, paths become order-sensitive, verification capacity saturates, or scarce attention must be allocated — so that identity, ancestry, uncertainty, path dependence, verification state, cost evidence, and permission remain provable rather than merely asserted?

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
DeclaredCost != AccountingCost
FUNDED != VERIFIED
FUNDED != PASS
DeferredBudget != FAIL
```

# v1.8 — Adaptive Verification Economy

v1.8 adds an economic plane for allocating finite verification attention without letting a submitter's declared verification cost become accounting truth.

```text
existing verification debt
        |
        v
EconomicVerificationCandidate
        |
        +-- value
        +-- risk
        +-- priority
        +-- age
        +-- estimator class
        |
        v
ATMAN-ECONOMY/1.8
        |
        +-- observed-cost estimator
        +-- uncertainty premium
        +-- finite budget
        +-- deterministic allocation
        |
        +-- FUNDED
        +-- DEFERRED_BUDGET
        +-- DEFERRED_OVERSIZED
```

The four process-level protocol planes are now:

```text
ATMAN-RUNTIME/1.1  privileged execution
ATMAN-TRUST/1.2    trust-root governance
ATMAN-VERIFY/1.7   durable verification/debt/finalization
ATMAN-ECONOMY/1.8  adaptive verification-budget allocation
```

## Declared cost is provenance, not accounting truth

An economic candidate must reference existing v1.7 verification work. Its original `cost_units` is preserved as `declared_cost_units`, but the allocator does not trust that field as the cost used for budget decisions.

```text
DeclaredCost != AccountingCost
```

If there is no observed history for an estimator class, the reference runtime uses:

```text
bootstrap cost + uncertainty premium
```

not the caller's declared number.

## Completion-bound observed cost

A `CostObservationReceipt` is accepted only when:

- the work exists;
- the economic candidate already exists;
- the v1.7 work is completed;
- the observation binds the exact `completion_hash`;
- the estimator key matches the candidate;
- `VERIFICATION_COST_METER` authority is current;
- the meter identity comes from the authority grant;
- no conflicting observation already exists for the same work hash.

Cost observations feed a hash-bound `CostEstimatorSnapshot` with sample count, total observed cost, ceiling arithmetic mean, and the exact observation hashes.

The reference implementation authenticates accounting measurements; it does **not** claim to automatically measure CPU cycles, energy, API spend, or wall-clock cost. Production should bind the meter to protected resource telemetry or billing evidence.

## Adaptive allocation

The reference allocator ranks by utility per estimated cost:

```text
utility =
    value * value_weight
  + risk * risk_weight
  + priority * priority_weight
  + floor(wait_time / aging_quantum)
```

Historical observed cost can therefore reorder future verification attention. Low-sample estimators receive an explicit uncertainty premium.

Every candidate is accounted for exactly once:

```text
CANDIDATES = FUNDED ∪ DEFERRED_BUDGET ∪ DEFERRED_OVERSIZED
```

with disjoint dispositions.

And the semantic separation remains load-bearing:

```text
FUNDED != VERIFIED
FUNDED != PASS
DEFERRED != FAIL
```

The economy plane decides where scarce verification resource goes. It does not decide the verification result or A4 truth/coherence result.

## Economy preview vs finalization

`preview_budget_allocation` returns a state hash and deterministic allocation. Finalization requires `VERIFICATION_BUDGET_KEEPER` authority over the exact current economy state, policy, allocation, next generation, and runtime time.

If candidates or estimator evidence change after preview:

```text
preview E0
state -> E1
finalize(E0)
    X
stale verification economy state
```

So:

```text
OldEconomicPreview != CurrentBudgetAuthority
```

Protocol: [`docs/v1.8-adaptive-verification-economy.md`](docs/v1.8-adaptive-verification-economy.md)

Invariants: [`docs/v1.8-invariants.md`](docs/v1.8-invariants.md)

Machine-readable contracts:

- [`schemas/verification-cost-observation.schema.json`](schemas/verification-cost-observation.schema.json)
- [`schemas/verification-cost-estimator.schema.json`](schemas/verification-cost-estimator.schema.json)
- [`schemas/verification-economic-candidate.schema.json`](schemas/verification-economic-candidate.schema.json)
- [`schemas/verification-economy-policy.schema.json`](schemas/verification-economy-policy.schema.json)
- [`schemas/verification-budget-allocation.schema.json`](schemas/verification-budget-allocation.schema.json)

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

```text
UNVERIFIED != INVALID
DEFERRED != PRUNED
```

## Completion is an explicit verdict

`VerificationCompletionReceipt` binds exact work, identity, geometry gate, schedule generation, pressure receipt, PASS/HOLD/FAIL result, evidence digest, verifier actor, and runtime completion time.

Only work admitted in the current pressure window can be completed.

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

Otherwise pending/deferred/HOLD results remain `HOLD`, and any completed `FAIL` yields `FAIL`.

## Preview vs authoritative finalization

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

If verification state changes between preview and finalization, the old preview is rejected.

Protocol: [`docs/v1.7-runtime-verification-plane.md`](docs/v1.7-runtime-verification-plane.md)

Invariants: [`docs/v1.7-invariants.md`](docs/v1.7-invariants.md)

# Prior layers

## v1.6 — Verification Pressure / Temporal Loom

Finite A3/A4 capacity is modeled without converting overload into a semantic verdict.

```text
OFFERED = ADMITTED ∪ DEFERRED_CAPACITY ∪ DEFERRED_OVERSIZED
ADMITTED != VERIFIED
```

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

Long-running agents can have valid alternative plans, restored memories, order-sensitive operations, changing authority, more verification work than available capacity, and verification checks with very different real resource costs.

ATMAN-LATTICE keeps different questions separate:

- Is this still the same identity?
- Is this the same history?
- Was this future merely considered or actually committed?
- Can two valid branches coexist?
- Did operation order change the result?
- Is path dependence acceptable, HOLD-worthy, or rejected?
- Was verification actually completed?
- Was it only deferred because capacity or budget ran out?
- What cost was merely declared, and what cost was independently accounted?
- Which verification debt receives scarce budget now?
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

Verification economy worker:

```bash
python -m model.economy_worker
```

Reference protocols:

```text
ATMAN-RUNTIME/1.1
ATMAN-TRUST/1.2
ATMAN-VERIFY/1.7
ATMAN-ECONOMY/1.8
```

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox or a claim about physical multiverses/torsion. Production use additionally requires protected keys, authenticated transport, rollback-resistant durable storage/backups, operating-system/tool-bound resource metering, database/file permissions, and operational governance.

## Status

**v1.8.0 — Adaptive Verification Economy research core.**

The project now spans identity continuity, cryptographic lineage, potential-vs-committed futures, restore/fork semantics, narrative-preserving reconciliation, transition torsion/curvature, policy-bound A3/A4 geometric coherence, finite verification-pressure scheduling, durable verification debt, authority-bound completion/finalization, authenticated cost observations, observation-derived adaptive cost estimation, stale-safe budget finalization, one-time authorization, asymmetric signer authority, process-separated execution, serialized runtime state, and quorum-governed trust-root evolution.

Next targets: bind cost meters to actual protected runtime telemetry, automatically apply funded allocations into the verification scheduler, decompose oversized verification work, persist budget-finalization history, rollback-resistant economy state, compensation receipts, concurrency stress tests, and real agent planning/memory/tool integrations.
