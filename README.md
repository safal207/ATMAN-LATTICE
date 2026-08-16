# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, signer authority, and privileged execution boundaries.

> What must remain invariant when representation changes, so that we can still prove that the resulting state belongs to the same identity — and that the actor changing it had authority to do so?

The repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, or Atman. Those terms are conceptual labels for nodes and observer roles inside a formal model. The engineering target is testable continuity, provenance, freshness, authority, and globally coherent execution.

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
```

## v1.1 — Full Runtime Plane

v1.1 closes the privileged lifecycle inside one reference runtime plane.

```text
client
  |
  | ATMAN-RUNTIME/1.1
  v
ATMAN Runtime
  |
  +-- server-owned trusted roots
  +-- server-owned policy generation
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

The governed role map is now:

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

A caller can reference a configured `key_id`, but token and authorization-event MAC secrets are loaded by the runtime deployment and are not taken from request fields.

### Atomic terminal authorization

`CONSUMED` / `REVOKED` state is no longer accepted from a client-provided ledger snapshot. The runtime loads the current ledger from SQLite and mutates it inside a `BEGIN IMMEDIATE` transaction.

```text
process A                 process B
   |                         |
BEGIN IMMEDIATE              |
load generation N            |
validate + append             |
COMMIT -> N+1                 |
                             BEGIN IMMEDIATE
                             load generation N+1
                             stale N proof/request -> REJECT
```

This gives the reference implementation an actual cross-process serialization point:

> **At most one terminal authorization event may commit for an exact token digest.**

Possessing a cryptographically valid token is still not sufficient to consume it. Consumption additionally requires a current exact `USE_TOKEN_CONSUMER` authority proof over the runtime-reconstructed action.

### Runtime-mediated reconciliation

Branch merge is also executed inside the worker. The runtime verifies exact ancestry, both branch lineages, restore proofs, resolution completeness, target branch/generation, merged payload digest, and `BRANCH_MERGER` authority before producing the merge lineage and receipt.

Protocol: [`docs/v1.1-full-runtime-plane.md`](docs/v1.1-full-runtime-plane.md)

Invariants: [`docs/v1.1-invariants.md`](docs/v1.1-invariants.md)

## v1.0 — ATMAN Runtime

v1.0 introduced the first process-separated privileged observer plane.

```text
client process
    |
    | grant + proof + exact inputs
    v
runtime worker process
    |
    +-- server-owned trusted roots
    +-- server-owned policy generation
    +-- server-owned verification time
    |
    v
v0.9 authority enforcement
    |
    v
A1 / A2 / A3 / A4
```

The central v1.0 rule remains:

> **Client permission claims do not become privileged execution until the runtime process independently verifies the exact authority.**

The process-boundary regression verifies that monkeypatching the caller's in-memory enforcement function does not modify a fresh `python -m model.runtime_worker` process.

Protocol: [`docs/v1.0-atman-runtime.md`](docs/v1.0-atman-runtime.md)

Invariants: [`docs/v1.0-invariants.md`](docs/v1.0-invariants.md)

## Evolution

### v0.2 — executable observers

[`model/lattice.py`](model/lattice.py) implements A1/A2/A3/A4 and rejects local observer agreement when identity, branch, generation, or lineage root disagree.

### v0.3 — cryptographic lineage

`IdentityReceipt` forms a SHA-256 parent-linked history. Matching human-readable metadata is insufficient when cryptographic lineage roots differ.

### v0.4 — freshness + use binding

[`model/freshness.py`](model/freshness.py) separates historical observer verdicts from use-time authorization through attestations, context digests, expiry, and `UseToken` binding.

Protocol: [`docs/v0.4-signed-freshness.md`](docs/v0.4-signed-freshness.md)

### v0.5 — replay / restore

[`model/replay.py`](model/replay.py) formalizes **Restore is not continuation.** Restoring an old checkpoint creates a new branch, generation, and lineage root while preserving exact ancestry evidence.

Protocol: [`docs/v0.5-replay-restore.md`](docs/v0.5-replay-restore.md)

Invariants: [`docs/v0.5-invariants.md`](docs/v0.5-invariants.md)

### v0.6 — branch merge / reconciliation

[`model/merge.py`](model/merge.py) requires exact common ancestry, both parent histories, complete explicit conflict resolution, and a new merge lineage.

> **Valid parents do not imply a valid merge.**

Protocol: [`docs/v0.6-merge-reconciliation.md`](docs/v0.6-merge-reconciliation.md)

Invariants: [`docs/v0.6-invariants.md`](docs/v0.6-invariants.md)

### v0.7 — one-time consumption + revocation

[`model/consumption.py`](model/consumption.py) records terminal `CONSUMED` or `REVOKED` events in an authenticated hash-linked authorization ledger with generation-bound append semantics.

> **Authorization validity is not authorization availability.**

Protocol: [`docs/v0.7-consumption-revocation.md`](docs/v0.7-consumption-revocation.md)

Invariants: [`docs/v0.7-invariants.md`](docs/v0.7-invariants.md)

### v0.8 — authority / signer identity

[`model/authority.py`](model/authority.py) uses Ed25519 grants and proofs to bind exact keys to roles, scopes, policy generations, validity windows, and action digests.

> **A valid signature does not imply valid authority.**

Protocol: [`docs/v0.8-authority-signers.md`](docs/v0.8-authority-signers.md)

Invariants: [`docs/v0.8-invariants.md`](docs/v0.8-invariants.md)

### v0.9 — pre-execution enforcement

[`model/enforcement.py`](model/enforcement.py) reconstructs the exact action from runtime inputs and gates observer, token lifecycle, and branch-merge operations before the privileged primitive is called.

> **Gate before execution.**

Protocol: [`docs/v0.9-authority-enforcement.md`](docs/v0.9-authority-enforcement.md)

Invariants: [`docs/v0.9-invariants.md`](docs/v0.9-invariants.md)

## Machine-readable contracts

Schemas live in [`schemas/`](schemas/) and cover identity receipts, observer receipts/attestations, use tokens, restore/merge receipts, conflict resolutions, authorization ledgers/events, and authority grants/proofs.

## Why this matters for AI systems

The same identity problem appears when agents move through working memory, compressed memory, simulations, checkpoints, restore operations, planning branches, reconciled memories, changing tool/policy contexts, delegated capabilities, revocation, and long-horizon execution.

ATMAN-LATTICE keeps these questions separate:

- Is this still the same identity?
- Is this the same history?
- Is this representation fresh?
- Is this branch compatible with that branch?
- Is this authorization still available?
- Did this signer actually have authority?
- Was authority checked against the exact action?
- Did privileged execution occur inside the intended trust boundary?
- Did terminal authorization state come from the current runtime store rather than a stale client projection?

## Run

```bash
python -m pip install -e . pytest
python -m pytest -q
```

The reference worker is invoked as:

```bash
python -m model.runtime_worker
```

It consumes one `ATMAN-RUNTIME/1.1` JSON request from stdin and writes one JSON response to stdout.

Reference deployment configuration includes:

```text
ATMAN_TRUSTED_ISSUER_KEYS
ATMAN_POLICY_GENERATION
ATMAN_RUNTIME_NOW
ATMAN_ATTESTATION_KEYS
ATMAN_TOKEN_KEYS
ATMAN_EVENT_KEYS
ATMAN_RUNTIME_DB
```

This remains a **reference process boundary**, not a hostile-host sandbox. Production use additionally requires protected secrets/configuration, OS/container isolation, authenticated transport, database/file permissions, rollback protection, and operational auditing.

## Status

**v1.1.0 — Full Runtime Plane research core.**

The project now spans identity continuity, cryptographic lineage, freshness, restore/fork semantics, branch reconciliation, one-time authorization, asymmetric signer authority, pre-execution enforcement, process-separated privileged execution, server-owned capability keys, and atomically serialized terminal authorization state.

Next targets: authenticated runtime transport, root-key rotation and quorum governance, rollback-resistant durable storage, compensation receipts, generalized ancestry proofs, multi-process concurrency stress tests, and integration with real agent memory/checkpoint/tool systems.
