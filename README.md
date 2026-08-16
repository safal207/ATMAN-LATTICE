# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity as linked projections across state, space, time, lineage, execution context, branching, reconciliation, authorization history, signer authority, and governed execution.

> What must remain invariant when representation changes, so that we can still prove that the resulting state belongs to the same identity?

The repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, or Atman. Those terms are conceptual labels for nodes and observer roles inside a formal model. The engineering goal is testable continuity, provenance, observer independence, freshness, branching, reconciliation, one-time authorization, signer authority, authority enforcement, and global coherence.

## Core model

```text
Spatial axis:   S1 <----> S3 / A1 <----> S2
                waking     observer       dream

Temporal axis:  S4 <----> S6 / A2 <----> S5
                past       observer       future

A3 = Observer(A1, A2)
A4 = Coherence(A1, A2, A3)
```

Core invariant:

> **Representation may change across state, space, and time; identity must remain coherently traceable across the transformation.**

Executable warnings accumulated so far:

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
```

## v0.2 — executable observers

[`model/lattice.py`](model/lattice.py) implements `A1`, `A2`, `A3`, and `A4`. Local spatial and temporal PASS results are rejected when identity, branch, or generation bindings disagree.

## v0.3 — cryptographic lineage

`IdentityReceipt` forms a SHA-256 parent-linked chain. Observer proofs bind to `lineage_root_hash`, so matching human-readable metadata is not enough to fuse independently originated histories.

```text
identity(A1) == identity(A2)
branch(A1) == branch(A2)
generation(A1) == generation(A2)
A1 = PASS
A2 = PASS

but root(A1) != root(A2)

=> A3 = FAIL
=> A4 = FAIL
```

## v0.4 — signed freshness + use binding

[`model/freshness.py`](model/freshness.py) separates historical observer verdicts from current authorization:

```text
ObserverReceipt
      ↓ exact digest
ObserverAttestation(context_digest, verified_at, HMAC)
      ↓ freshness + PASS
UseToken(context_digest, expiry, HMAC)
      ↓ checked at actual use
Execution
```

> **Historical PASS is not current authorization.**

A context change, stale attestation, expired token, or authenticated-field mutation makes execution fail.

## v0.5 — replay, restore, and branch identity

[`model/replay.py`](model/replay.py) formalizes restoration from a historical checkpoint.

> **Restore is not continuation.**

Returning to an old checkpoint must create a new branch, higher generation, and new cryptographic lineage root while preserving an exact proof edge to the source checkpoint.

```text
R0 -> R1 -> R2 -> R3 -> R4
            |
            | RestoreReceipt
            v
            R0' -> new future
            new branch / generation / root
```

This yields:

> **Same identity does not imply same history.**

Machine-readable contract: [`schemas/restore-receipt.schema.json`](schemas/restore-receipt.schema.json).

Protocol: [`docs/v0.5-replay-restore.md`](docs/v0.5-replay-restore.md).

Additional invariants: [`docs/v0.5-invariants.md`](docs/v0.5-invariants.md).

## v0.6 — branch merge / reconciliation

[`model/merge.py`](model/merge.py) defines how two independently valid future branches may be reconciled without erasing either history.

```text
                -> L0 -> L1 -> L2 --\
Ancestor ------<                    +-> M0 -> M1 ...
                -> R0 -> R1 -> R2 --/
```

The merge target `M0` is a **third lineage**, not a mutation of `L` or `R`.

A valid merge requires:

```text
same exact ancestor proof
+ valid left branch chain
+ valid right branch chain
+ distinct parent branches and roots
+ complete conflict-resolution set
+ new target branch
+ target generation > both parents
+ new target lineage root
+ provenance binding to ancestor + both parent heads
```

Every declared conflict must have exactly one explicit `ConflictResolution` using `LEFT`, `RIGHT`, or `SYNTHESIZED`. The canonical resolution set is hashed into `resolution_digest` and committed by the merge genesis and `MergeReceipt`.

> **Compatible ancestry is necessary for merge; resolved contradiction is necessary for coherence.**

Machine-readable contracts:

- [`schemas/merge-receipt.schema.json`](schemas/merge-receipt.schema.json)
- [`schemas/conflict-resolution.schema.json`](schemas/conflict-resolution.schema.json)

Protocol: [`docs/v0.6-merge-reconciliation.md`](docs/v0.6-merge-reconciliation.md).

Additional invariants: [`docs/v0.6-invariants.md`](docs/v0.6-invariants.md).

## v0.7 — one-time consumption + revocation

[`model/consumption.py`](model/consumption.py) turns a valid `UseToken` into a one-time capability whose lifecycle is recorded in an append-only authorization ledger.

```text
UseToken
   ↓ exact authenticated digest
AuthorizationLedger
   ↓
terminal event = CONSUMED or REVOKED
```

A token may have at most one terminal authorization event.

```text
CONSUMED(token X) -> later use of X = REJECT
REVOKED(token X)  -> later use of X = REJECT
```

Consumption still requires the v0.4 use-time checks: token MAC, current execution context, and expiry. Revocation instead targets the exact authentic token independent of whether its original execution context is still current.

Authorization events are HMAC-authenticated and hash-linked:

```text
E1 -> E2 -> E3
      ^
      previous_event_hash
```

Each append also binds to the ledger generation observed by the caller:

```text
expected_ledger_generation == current_ledger_generation
```

This is an optimistic-concurrency contract. A production distributed store must enforce that comparison atomically via transaction, compare-and-swap, conditional write, or an equivalent serialization primitive.

> **Authorization validity is not authorization availability.**

Machine-readable contracts:

- [`schemas/authorization-event.schema.json`](schemas/authorization-event.schema.json)
- [`schemas/authorization-ledger.schema.json`](schemas/authorization-ledger.schema.json)

Protocol: [`docs/v0.7-consumption-revocation.md`](docs/v0.7-consumption-revocation.md).

Additional invariants: [`docs/v0.7-invariants.md`](docs/v0.7-invariants.md).

## v0.8 — authority / signer identity

[`model/authority.py`](model/authority.py) introduces asymmetric signer identity and separates cryptographic authenticity from authorization.

```text
Trusted root public key
        |
        | Ed25519
        v
AuthorityGrant
  exact subject key
  roles[]
  scopes[]
  policy_generation
  validity window
        |
        | grant_hash
        v
AuthorityProof
  role
  scope
  action_digest
  signed_at
  Ed25519 signature
        |
        v
use-time authority verification
```

The central rule is:

> **A valid signature does not imply valid authority.**

A proof is rejected when the signature is correct but the requested role or scope is not present in the grant. It is also rejected when the governing policy generation changed, the grant expired, the action was substituted after signing, the grant issuer is not trusted, or the proof was signed by a different key than the one bound by the grant.

Machine-readable contracts:

- [`schemas/authority-grant.schema.json`](schemas/authority-grant.schema.json)
- [`schemas/authority-proof.schema.json`](schemas/authority-proof.schema.json)

Protocol: [`docs/v0.8-authority-signers.md`](docs/v0.8-authority-signers.md).

Additional invariants: [`docs/v0.8-invariants.md`](docs/v0.8-invariants.md).

## v0.9 — authority enforcement

[`model/enforcement.py`](model/enforcement.py) moves authority verification into the governed execution path.

The new execution rule is:

> **A privileged primitive may execute only after the exact runtime action passes the exact operation role, exact runtime scope, current policy, grant, and signer checks.**

The governed role map is:

```text
observe_space       -> A1_OBSERVER
observe_time        -> A2_OBSERVER
cross_axis_bind     -> A3_BINDER
global_coherence    -> A4_KEEPER
issue_use_token     -> USE_TOKEN_ISSUER
revoke_use_token    -> USE_TOKEN_REVOKER
merge_branches      -> BRANCH_MERGER
```

Scopes are reconstructed from the actual runtime subject:

```text
observer / merge       -> identity:<identity_ref>
authorization lifecycle -> authorization:<identity_ref>
```

The gate reconstructs the canonical action from the actual runtime inputs before validating the proof. The proof therefore cannot authorize merely a caller-provided description of what it intends to execute.

```text
runtime inputs
      |
      v
canonical action reconstruction
      |
      v
root -> grant -> proof verification
      |
      +-- exact required role
      +-- exact required scope
      +-- current policy generation
      +-- exact action digest
      +-- current validity window
      |
   FAIL -> no primitive call
      |
      v
privileged primitive
```

The test suite contains a gate-before-execution regression: `observe_space()` is replaced with a function that would fail if called; a cryptographically valid proof using a wrong but granted role is rejected before that primitive is reached.

The separation remains explicit:

```text
mechanism != permission
```

Low-level primitives remain pure and importable for formal testing. `model.enforcement` is the governed boundary. This research package therefore proves enforcement semantics at that boundary, not hostile-code process isolation. Production non-bypassability requires a real service/process/capability/storage boundary around the privileged primitive.

Protocol: [`docs/v0.9-authority-enforcement.md`](docs/v0.9-authority-enforcement.md).

Additional invariants: [`docs/v0.9-invariants.md`](docs/v0.9-invariants.md).

## Why this matters for AI systems

The same identity problem appears when agents move through:

- working and compressed memory;
- simulations and replays;
- checkpoints and restore operations;
- forked planning branches;
- reconciliation of competing plans or memories;
- tool and policy context changes;
- one-time permissions and delegated capabilities;
- explicit revocation before tool execution;
- independently signed observer or tool decisions;
- role- and scope-bounded authority across multiple agents;
- governed invocation of verification, merge, authorization, and execution primitives;
- long-horizon execution across multiple generations.

An agent may preserve identity ancestry while producing multiple valid but incompatible futures, hold an authorization artifact that is cryptographically valid but no longer consumable, or produce a perfectly valid signature without having authority for the requested action. ATMAN-LATTICE keeps those relations separate and testable, and v0.9 ensures the governed runtime checks them before privileged execution.

## Documents

- [THEORY.md](THEORY.md) — conceptual/formal model
- [INVARIANTS.md](INVARIANTS.md) — v0.4 core invariant set
- [v0.4 signed freshness](docs/v0.4-signed-freshness.md)
- [v0.5 replay/restore](docs/v0.5-replay-restore.md)
- [v0.5 additional invariants](docs/v0.5-invariants.md)
- [v0.6 merge/reconciliation](docs/v0.6-merge-reconciliation.md)
- [v0.6 additional invariants](docs/v0.6-invariants.md)
- [v0.7 consumption/revocation](docs/v0.7-consumption-revocation.md)
- [v0.7 additional invariants](docs/v0.7-invariants.md)
- [v0.8 authority/signers](docs/v0.8-authority-signers.md)
- [v0.8 additional invariants](docs/v0.8-invariants.md)
- [v0.9 authority enforcement](docs/v0.9-authority-enforcement.md)
- [v0.9 additional invariants](docs/v0.9-invariants.md)

## Run

```bash
python -m pip install -e . pytest
python -m pytest -q
```

The suite also runs in GitHub Actions on pushes to `main` and pull requests.

## Status

`v0.9` — governed authority-enforcement research core. ATMAN-LATTICE now models identity continuity, history continuity, use-time freshness, branch restoration, branch reconciliation, one-time authorization state, signer authority, and pre-execution authority gates. A1/A2/A3/A4, use-token issuance/revocation, and branch merge now have explicit role/scope/action bindings in the governed API.

Next targets: non-bypassable service/runtime isolation, root-key rotation and quorum governance, durable database-backed atomic authorization ledgers, identity/policy-wide revocation, compensating-action receipts, generalized ancestry proofs, and integration with real agent checkpoint/memory/tool systems.
