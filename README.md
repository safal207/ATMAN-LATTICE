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
Revocation != History erasure
Valid signature != Valid authority
Historical authority != Current authority
Granted role != Required operation role
Verified proof != Executed permission unless checked before use
Caller claim != Runtime authority
Caller mutation != Runtime mutation
```

## v1.0 — ATMAN Runtime

v1.0 introduces a process-separated reference runtime for the privileged observer plane.

```text
client process
    |
    | ATMAN-RUNTIME/1.0 JSON
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
    |
    v
ObserverReceipt
```

The worker currently exposes:

```text
observe_space       -> A1_OBSERVER
observe_time        -> A2_OBSERVER
cross_axis_bind     -> A3_BINDER
global_coherence    -> A4_KEEPER
```

The runtime request cannot replace the worker's trusted root set, current policy generation, or verification clock. Canonical actions are reconstructed from decoded runtime inputs before authority verification.

The central v1.0 rule is:

> **Client permission claims do not become privileged execution until the runtime process independently verifies the exact authority.**

The test suite also verifies process isolation at the reference boundary: monkeypatching the caller's in-memory enforcement function does not modify a fresh `python -m model.runtime_worker` process.

This is a **reference process boundary**, not a hostile-host sandbox. The non-bypassability claim applies only when callers do not control the worker process, worker package, or server trust configuration. Production deployment still needs suitable OS/container isolation, authenticated transport, protected configuration, and durable audit storage.

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

[`model/replay.py`](model/replay.py) formalizes:

> **Restore is not continuation.**

Restoring an old checkpoint creates a new branch, generation, and lineage root while preserving exact ancestry evidence.

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

[`model/enforcement.py`](model/enforcement.py) reconstructs the exact action from runtime inputs and gates A1/A2/A3/A4, token issuance/revocation, and branch merge before the privileged primitive is called.

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

## Run

```bash
python -m pip install -e . pytest
python -m pytest -q
```

The reference runtime worker is invoked as:

```bash
python -m model.runtime_worker
```

It consumes one `ATMAN-RUNTIME/1.0` JSON request from stdin and writes one JSON response to stdout. See the v1.0 protocol document for the trust-boundary assumptions.

## Status

**v1.0.0 — ATMAN Runtime research core.**

The project now spans identity continuity, cryptographic lineage, freshness, restore/fork semantics, branch reconciliation, one-time authorization, asymmetric signer authority, pre-execution enforcement, and a process-separated privileged observer runtime.

Next targets: move token/merge operations behind the runtime boundary, authenticated transport, root-key rotation and quorum governance, durable atomic authorization storage, compensation receipts, generalized ancestry proofs, and integration with real agent memory/checkpoint/tool systems.
