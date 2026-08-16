# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Governance, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, signer authority, privileged execution, and trust-root evolution.

> What must remain invariant when representation changes, so that we can still prove that the resulting state belongs to the same identity — and that the actor changing it, or changing who is trusted to act, had authority to do so?

The repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, or Atman. Those terms are conceptual labels for nodes and observer roles inside a formal model. The engineering target is testable continuity, provenance, freshness, authority, governance, and globally coherent execution.

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
```

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

C optional
```

Each approval binds:

```text
current_policy_hash
next root set
next threshold
reason
transition time
```

The next policy is hash-linked to the previous one:

```text
Policy N
   |
   | previous_policy_hash
   v
Policy N+1
```

Trust policy is persisted in SQLite. Bootstrap environment roots initialize an empty database once; after initialization, persisted trust state is authoritative. Restarting a worker with stale bootstrap roots cannot silently roll a rotated policy backward.

Rotation is committed under `BEGIN IMMEDIATE`, so the current-policy quorum check and successor write occur against one serialized state.

A successful transition emits a `TrustTransitionReceipt` binding predecessor, successor, required quorum, exact approvals, reason, and time.

Most importantly, after rotation:

```text
old root + new-generation grant -> REJECT
new root + new-generation grant -> eligible for verification
```

Protocol: [`docs/v1.2-trust-root-evolution.md`](docs/v1.2-trust-root-evolution.md)

Invariants: [`docs/v1.2-invariants.md`](docs/v1.2-invariants.md)

Machine-readable contracts:

- [`schemas/trust-policy.schema.json`](schemas/trust-policy.schema.json)
- [`schemas/trust-approval.schema.json`](schemas/trust-approval.schema.json)
- [`schemas/trust-transition-receipt.schema.json`](schemas/trust-transition-receipt.schema.json)

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

The governed role map is:

```text
observe_space       -> A1_OBSERVER
observe_time        -> A2_OBSERVER
cross_axis_bind     -> A3_BINDER
global_coherence    -> A4_KEEPER
issue_use_token     -> USE_TOKEN_ISSUER
consume_use_token   -> USE_TOKEN_CONSUMER
revoke_use_token    -> USE_TOKEN_REVOKER
merge_branches      -> BRANCH_MERGER
```

`CONSUMED` / `REVOKED` state is loaded from SQLite and mutated inside a `BEGIN IMMEDIATE` transaction. A stale client snapshot cannot become current authorization state.

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

See [`docs/`](docs/) and [`INVARIANTS.md`](INVARIANTS.md) for the detailed progression.

## Why this matters for AI systems

The same integrity problem appears when agents move through working memory, compressed memory, simulations, checkpoints, restored branches, reconciled plans, changing tool contexts, delegated capabilities, revocation, long-horizon execution, and governance changes.

ATMAN-LATTICE keeps these questions separate:

- Is this still the same identity?
- Is this the same history?
- Is this representation fresh?
- Is this branch compatible with that branch?
- Is this authorization still available?
- Did this signer actually have authority?
- Was authority checked against the exact action?
- Did privileged execution occur inside the intended trust boundary?
- Did terminal authorization state come from the current runtime store?
- Who had authority to change the set that defines authority?
- Can that governance transition itself be replayed, rolled back, or silently replaced?

## Run

```bash
python -m pip install -e . pytest
python -m pytest -q
```

Reference runtime worker:

```bash
python -m model.runtime_worker
```

It accepts both:

```text
ATMAN-RUNTIME/1.1  — privileged execution plane
ATMAN-TRUST/1.2    — trust governance plane
```

Reference deployment configuration includes:

```text
ATMAN_TRUSTED_ISSUER_KEYS
ATMAN_POLICY_GENERATION
ATMAN_TRUST_THRESHOLD
ATMAN_TRUST_BOOTSTRAP_ACTIVATED_AT
ATMAN_RUNTIME_NOW
ATMAN_ATTESTATION_KEYS
ATMAN_TOKEN_KEYS
ATMAN_EVENT_KEYS
ATMAN_RUNTIME_DB
```

This remains a **reference process/database boundary**, not a hostile-host sandbox. Production use additionally requires protected private keys, protected durable storage, authenticated transport, OS/container isolation, rollback-resistant backups, database/file permissions, and operational governance.

## Status

**v1.2.0 — Trust-Root Evolution research core.**

The project now spans identity continuity, cryptographic lineage, freshness, restore/fork semantics, branch reconciliation, one-time authorization, asymmetric signer authority, pre-execution enforcement, process-separated privileged execution, atomically serialized authorization state, and quorum-governed trust-root evolution with persisted policy generations.

Next targets: authenticated runtime transport, rollback-resistant trust-state checkpoints, emergency recovery governance, compensation receipts, generalized ancestry proofs, concurrency stress tests, and integration with real agent memory/checkpoint/tool systems.
