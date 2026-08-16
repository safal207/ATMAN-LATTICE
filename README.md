# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Governance, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, possibility, reconciliation, authorization, signer authority, privileged execution, and trust-root evolution.

> What must remain invariant when representation changes, futures branch, worlds reconcile, or authority itself changes — so that identity, ancestry, and permission remain provable rather than merely asserted?

The repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, Atman, quantum worlds, or a physical multiverse. Those terms are conceptual labels and thought experiments inside a formal model. The engineering target is testable continuity, provenance, freshness, authority, governance, compatibility, and globally coherent execution.

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
```

## v1.3 — Multiverse Semantics

v1.3 turns science-fiction-inspired branching ideas into explicit engineering contracts for planning and agent state.

### Potentiality before history

A planner may represent several futures without mutating committed lineage:

```text
Committed State
      |
      +-- Potential A
      +-- Potential B
      +-- Potential C
```

A `PotentialBranch` is not a historical branch. Only an explicit `BranchCommitReceipt` may create committed lineage:

```text
Potential B
     |
 explicit commit
     v
Committed Branch B
```

The committed payload must match the payload digest that was proposed. A system cannot obtain approval for one future and silently commit another.

### Incursion / coexistence semantics

Two branches may both be individually valid while still being incompatible in one execution context:

```text
Valid(A) = true
Valid(B) = true

but

Coexist(A, B) = false
```

`IncursionReceipt` records compatibility over exact branch heads and exact lineage roots:

```text
COEXIST      -> resolution_mode = NONE
INCOMPATIBLE -> explicit ISOLATE / FORK / RECONCILE / MERGE / REJECT / COMPENSATE
```

Silent overwrite is not a resolution strategy.

### Anti-Doom narrative preservation

A merged or composite reality must preserve both parent histories.

`CompositeRealityReceipt` binds:

```text
left head + left root
right head + right root
incursion receipt
merge receipt
new target genesis + target root
```

The verifier compares the composite receipt with the actual parent receipts and `MergeReceipt`. Rehashing a rewritten narrative envelope cannot make erased ancestry valid.

The rule is:

```text
Composite(C) => Parents(C) preserved
```

### Keeper, not sovereign

Global coherence does not grant narrative ownership:

```text
Preserve(Worlds) != AuthorityToRewrite(Worlds)
```

A4 may classify or preserve valid histories under explicit policy; it does not gain the right to rewrite their ancestry simply because it is the highest coherence layer.

Protocol: [`docs/v1.3-multiverse-semantics.md`](docs/v1.3-multiverse-semantics.md)

Invariants: [`docs/v1.3-invariants.md`](docs/v1.3-invariants.md)

Machine-readable contracts:

- [`schemas/potential-branch.schema.json`](schemas/potential-branch.schema.json)
- [`schemas/branch-commit-receipt.schema.json`](schemas/branch-commit-receipt.schema.json)
- [`schemas/incursion-receipt.schema.json`](schemas/incursion-receipt.schema.json)
- [`schemas/composite-reality-receipt.schema.json`](schemas/composite-reality-receipt.schema.json)

## v1.2 — Trust-Root Evolution

v1.2 adds a separate governance plane for changing the source of authority itself.

```text
execution plane:   ATMAN-RUNTIME/1.1
governance plane:  ATMAN-TRUST/1.2
```

A normal `AuthorityGrant` is already derived from the current trust policy, so it is not sufficient by itself to replace that policy. Trust-root mutation requires a quorum of distinct **currently trusted roots** over the exact transition.

```text
Current Policy N
  roots = A, B, C
  threshold = 2

A signs exact transition ----\
                              +--> Policy N+1
B signs exact transition ----/
```

Trust policy is persisted in SQLite. Bootstrap environment roots initialize an empty database once; after initialization, persisted trust state is authoritative. Restarting a worker with stale bootstrap roots cannot silently roll a rotated policy backward.

Rotation is committed under `BEGIN IMMEDIATE`, so the current-policy quorum check and successor write occur against one serialized state.

Most importantly, after rotation:

```text
old root + new-generation grant -> REJECT
new root + new-generation grant -> eligible for verification
```

Protocol: [`docs/v1.2-trust-root-evolution.md`](docs/v1.2-trust-root-evolution.md)

Invariants: [`docs/v1.2-invariants.md`](docs/v1.2-invariants.md)

## v1.1 — Full Runtime Plane

v1.1 closes the privileged lifecycle inside one reference runtime plane.

```text
client
  |
  | ATMAN-RUNTIME/1.1
  v
ATMAN Runtime
  |
  +-- server-owned trust policy
  +-- server-owned verification clock
  +-- server-owned capability/event secrets
  +-- server-owned SQLite authorization state
  |
  +-> A1 / A2 / A3 / A4
  +-> issue_use_token
  +-> consume_use_token
  +-> revoke_use_token
  +-> merge_branches
```

`CONSUMED` / `REVOKED` state is loaded from SQLite and mutated inside a `BEGIN IMMEDIATE` transaction.

> **At most one terminal authorization event may commit for an exact token digest.**

Possessing a valid token is not sufficient to consume it: consumption also requires current exact `USE_TOKEN_CONSUMER` authority over the runtime-reconstructed action.

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

The same integrity problem appears when agents move through working memory, simulations, alternative plans, checkpoints, restored branches, reconciled memories, changing tool contexts, delegated capabilities, revocation, long-horizon execution, and governance changes.

ATMAN-LATTICE keeps these questions separate:

- Is this still the same identity?
- Is this the same history?
- Is this merely a possible future, or was it actually committed?
- Can two individually valid branches coexist in one execution context?
- If they cannot coexist, was the resolution explicit?
- Did a composite result preserve every parent history?
- Is this representation fresh?
- Is this authorization still available?
- Did this signer actually have authority?
- Was authority checked against the exact action?
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

The v1.3 multiverse semantics currently live as explicit executable model primitives rather than a new wire protocol.

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox or a claim about physical multiverses. Production use additionally requires protected keys, protected durable storage, authenticated transport, rollback-resistant backups, database/file permissions, and operational governance.

## Status

**v1.3.0 — Multiverse Semantics research core.**

The project now spans identity continuity, cryptographic lineage, potential-vs-committed futures, restore/fork semantics, cross-branch compatibility, narrative-preserving composition, one-time authorization, asymmetric signer authority, runtime enforcement, atomically serialized authorization state, and quorum-governed trust-root evolution.

Next targets: branch-capacity / verification-pressure semantics, rollback-resistant trust recovery, emergency governance, compensation receipts, generalized ancestry proofs, concurrency stress tests, and integration with real agent planning/memory/tool systems.
