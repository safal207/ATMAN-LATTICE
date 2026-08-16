# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Governance, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, possibility, reconciliation, authorization, signer authority, privileged execution, trust-root evolution, transition geometry, and geometric coherence.

> What must remain invariant when representation changes, futures branch, worlds reconcile, transition order changes outcomes, or authority itself changes — so that identity, ancestry, path dependence, and permission remain provable rather than merely asserted?

The repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, Atman, quantum worlds, physical multiverses, or physical torsion fields. Those terms are conceptual labels and thought experiments inside a formal model. The engineering target is testable continuity, provenance, freshness, authority, governance, compatibility, path dependence, and globally coherent execution.

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
```

## v1.5 — Geometric Coherence Gate

v1.5 connects the v1.4 transition-geometry evidence directly to the A3/A4 coherence hierarchy.

```text
A1 + A2
   |
   v
  A3  ---- exact lineage consistency
   |
   +---- torsion evidence
   +---- curvature evidence
   +---- geometric policy
   |
   v
A3-GEOMETRY
PASS / HOLD / FAIL
   |
   v
A4-GEOMETRY
```

The new decision space intentionally contains `HOLD`:

```text
PASS  -> geometry is acceptable under current policy
HOLD  -> local steps may be valid, but global commit requires reconciliation/review
FAIL  -> evidence/binding is invalid or policy rejects the geometry
```

The default reference policy is:

```text
CLOSED                                  -> PASS
SEMANTICALLY_CLOSED_HISTORY_DIVERGENT   -> PASS + preserved evidence
TORSION_DETECTED                        -> HOLD
FLAT_LOOP                               -> PASS
SEMANTICALLY_CLOSED_WITH_HOLONOMY       -> PASS + preserved evidence
CURVATURE_DETECTED                      -> HOLD
```

A deployment may explicitly make the policy stricter or more permissive. The exact policy is hash-bound into every geometric observer receipt.

A3 re-verifies the exact v1.4 path evidence and additionally binds the geometry to the same `subject_identity_ref`. A self-consistent torsion receipt from another path or another identity is not accepted as evidence for this A3 decision.

A4 aggregates geometric decisions monotonically:

```text
PASS < HOLD < FAIL
```

Therefore a `HOLD` cannot silently become `PASS`, and a `FAIL` cannot be downgraded by another successful path. A4 also rejects A3 geometry evaluated for another identity or under another policy hash.

The central rule is:

```text
Torsion is evidence about path dependence.
Incursion is evidence about coexistence.
Neither artifact is execution authority.
```

Protocol: [`docs/v1.5-geometric-coherence-gate.md`](docs/v1.5-geometric-coherence-gate.md)

Invariants: [`docs/v1.5-invariants.md`](docs/v1.5-invariants.md)

Machine-readable contracts:

- [`schemas/geometric-coherence-policy.schema.json`](schemas/geometric-coherence-policy.schema.json)
- [`schemas/geometric-observer-receipt.schema.json`](schemas/geometric-observer-receipt.schema.json)

## v1.4 — Transition Geometry

v1.4 introduces a discrete, executable geometry of transition order and closed-loop drift.

This is an engineering analogue, not a claim about physical torsion or curvature.

### Torsion: does order matter?

For two valid transitions `A` and `B`:

```text
        A
   X -------> XA
   |           |
 B |           | B
   v           v
  XB -------> ?
        A
```

The model measures:

\[
\tau_X(A,B)=\Delta(B\circ A(X),A\circ B(X)).
\]

A `TransitionEndpoint` separates a semantic vector from a history vector:

```text
semantic:
  identity_ref
  payload_digest
  context_digest
  authority_digest
  effect_digest

history:
  lineage_root_hash
  branch_ref
  generation
  receipt_hash
```

This produces three torsion classifications:

```text
CLOSED
SEMANTICALLY_CLOSED_HISTORY_DIVERGENT
TORSION_DETECTED
```

So the system can represent an important case explicitly:

```text
same operational result
!=
same causal path
```

### Curvature: did a loop really return?

For a loop `L` intended to return to the same semantic point:

\[
\kappa_X(L)=\Delta(X,L(X)).
\]

The classifications are:

```text
FLAT_LOOP
SEMANTICALLY_CLOSED_WITH_HOLONOMY
CURVATURE_DETECTED
```

A loop may return to the same semantic state while preserving evidence that history advanced. The journey is not erased merely because the current operational state matches the origin.

### Torsion is evidence, not automatic failure

```text
TORSION_DETECTED
      |
      v
compatibility / policy evaluation
      |
      +-- compatible -> preserve path dependence
      +-- incompatible -> incursion / reconciliation
```

Therefore:

```text
Torsion != Invalidity
```

`TransitionTorsionReceipt` and `TransitionCurvatureReceipt` bind exact endpoints, exact transition operators, ordering, semantic deltas, historical deltas/holonomy, and measurement time. Verification recomputes the geometry from actual evidence rather than trusting a self-consistent envelope from another path.

Protocol: [`docs/v1.4-transition-geometry.md`](docs/v1.4-transition-geometry.md)

Invariants: [`docs/v1.4-invariants.md`](docs/v1.4-invariants.md)

Machine-readable contracts:

- [`schemas/transition-operator.schema.json`](schemas/transition-operator.schema.json)
- [`schemas/transition-endpoint.schema.json`](schemas/transition-endpoint.schema.json)
- [`schemas/transition-torsion-receipt.schema.json`](schemas/transition-torsion-receipt.schema.json)
- [`schemas/transition-curvature-receipt.schema.json`](schemas/transition-curvature-receipt.schema.json)

## v1.3 — Multiverse Semantics

v1.3 turns science-fiction-inspired branching ideas into explicit engineering contracts for planning and agent state.

A planner may represent several futures without mutating committed lineage. A `PotentialBranch` is not history; only an explicit `BranchCommitReceipt` creates committed lineage, and the committed payload must match the proposed payload digest.

Two branches may both be individually valid while still being incompatible in one execution context:

```text
Valid(A) = true
Valid(B) = true
Coexist(A, B) = false
```

`IncursionReceipt` records compatibility over exact branch heads and lineage roots. Incompatible worlds require an explicit `ISOLATE / FORK / RECONCILE / MERGE / REJECT / COMPENSATE` strategy; silent overwrite is not a strategy.

A merged `CompositeRealityReceipt` preserves both parent histories:

```text
Composite(C) => Parents(C) preserved
```

And the keeper rule remains:

```text
Preserve(Worlds) != AuthorityToRewrite(Worlds)
```

Protocol: [`docs/v1.3-multiverse-semantics.md`](docs/v1.3-multiverse-semantics.md)

Invariants: [`docs/v1.3-invariants.md`](docs/v1.3-invariants.md)

## v1.2 — Trust-Root Evolution

v1.2 adds a separate governance plane for changing the source of authority itself.

```text
execution plane:   ATMAN-RUNTIME/1.1
governance plane:  ATMAN-TRUST/1.2
```

A normal `AuthorityGrant` is already derived from the current trust policy, so it is not sufficient by itself to replace that policy. Trust-root mutation requires a quorum of distinct currently trusted roots over the exact transition.

Trust policy is persisted in SQLite. Bootstrap environment roots initialize an empty database once; after initialization, persisted trust state is authoritative. Restarting a worker with stale bootstrap roots cannot silently roll a rotated policy backward.

Protocol: [`docs/v1.2-trust-root-evolution.md`](docs/v1.2-trust-root-evolution.md)

Invariants: [`docs/v1.2-invariants.md`](docs/v1.2-invariants.md)

## v1.1 — Full Runtime Plane

v1.1 closes the privileged lifecycle inside one reference runtime plane, including observer execution, token issue/consume/revoke, merge, server-owned capability secrets, and atomically serialized authorization state.

> **At most one terminal authorization event may commit for an exact token digest.**

Protocol: [`docs/v1.1-full-runtime-plane.md`](docs/v1.1-full-runtime-plane.md)

Invariants: [`docs/v1.1-invariants.md`](docs/v1.1-invariants.md)

## v1.0 — ATMAN Runtime

v1.0 introduced the process-separated privileged observer plane and the rule:

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

See [`docs/`](docs/) for the detailed progression.

## Why this matters for AI systems

The same integrity problem appears when agents move through working memory, simulations, alternative plans, checkpoints, restored branches, reconciled memories, changing tool contexts, delegated capabilities, revocation, long-horizon execution, governance changes, and order-sensitive tool workflows.

ATMAN-LATTICE keeps these questions separate:

- Is this still the same identity?
- Is this the same history?
- Is this merely a possible future, or was it actually committed?
- Can two individually valid branches coexist in one execution context?
- Did two individually valid transitions commute, or did order change the result?
- Did a closed loop return semantically while still advancing history?
- Does path dependence require HOLD/reconciliation under current policy?
- Did a composite result preserve every parent history?
- Is this authorization still available?
- Did this signer actually have authority?
- Did privileged execution occur inside the intended trust boundary?
- Who had authority to change the set that defines authority?

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

The v1.3 multiverse semantics, v1.4 transition geometry, and v1.5 geometric coherence gate currently live as explicit executable model primitives rather than new wire protocols.

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox or a claim about physical multiverses/torsion. Production use additionally requires protected keys, protected durable storage, authenticated transport, rollback-resistant backups, database/file permissions, and operational governance.

## Status

**v1.5.0 — Geometric Coherence Gate research core.**

The project now spans identity continuity, cryptographic lineage, potential-vs-committed futures, restore/fork semantics, cross-branch compatibility, narrative-preserving composition, order-sensitive transition geometry, closed-loop drift/holonomy evidence, policy-bound A3/A4 geometric coherence with PASS/HOLD/FAIL semantics, one-time authorization, asymmetric signer authority, runtime enforcement, atomically serialized authorization state, and quorum-governed trust-root evolution.

Next targets: branch-capacity / verification-pressure semantics, runtime wire integration for geometric gates, rollback-resistant trust recovery, emergency governance, compensation receipts, generalized ancestry proofs, concurrency stress tests, and integration with real agent planning/memory/tool systems.
