# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity as linked projections across state, space, time, lineage, execution context, branching, and reconciliation.

> What must remain invariant when representation changes, so that we can still prove that the resulting state belongs to the same identity?

The repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, or Atman. Those terms are conceptual labels for nodes and observer roles inside a formal model. The engineering goal is testable continuity, provenance, observer independence, freshness, branching, reconciliation, and global coherence.

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

The shape is:

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

Every declared conflict must have exactly one explicit `ConflictResolution` using one of:

```text
LEFT
RIGHT
SYNTHESIZED
```

The canonical resolution set is hashed into `resolution_digest` and committed by the merge genesis and `MergeReceipt`.

Therefore:

> **Compatible ancestry is necessary for merge; resolved contradiction is necessary for coherence.**

Machine-readable contracts:

- [`schemas/merge-receipt.schema.json`](schemas/merge-receipt.schema.json)
- [`schemas/conflict-resolution.schema.json`](schemas/conflict-resolution.schema.json)

Protocol: [`docs/v0.6-merge-reconciliation.md`](docs/v0.6-merge-reconciliation.md).

Additional invariants: [`docs/v0.6-invariants.md`](docs/v0.6-invariants.md).

## Why this matters for AI systems

The same identity problem appears when agents move through:

- working and compressed memory;
- simulations and replays;
- checkpoints and restore operations;
- forked planning branches;
- reconciliation of competing plans or memories;
- tool and policy context changes;
- long-horizon execution across multiple generations.

An agent may preserve identity ancestry while producing multiple valid but incompatible futures. ATMAN-LATTICE distinguishes ancestry, history, current authorization, and reconciliation instead of collapsing them into one notion of "same agent".

## Documents

- [THEORY.md](THEORY.md) — conceptual/formal model
- [INVARIANTS.md](INVARIANTS.md) — v0.4 core invariant set
- [v0.4 signed freshness](docs/v0.4-signed-freshness.md)
- [v0.5 replay/restore](docs/v0.5-replay-restore.md)
- [v0.5 additional invariants](docs/v0.5-invariants.md)
- [v0.6 merge/reconciliation](docs/v0.6-merge-reconciliation.md)
- [v0.6 additional invariants](docs/v0.6-invariants.md)

## Run

```bash
python -m pip install pytest
python -m pytest -q
```

The suite also runs in GitHub Actions on pushes to `main` and pull requests.

## Status

`v0.6` — branch-reconciliation research core. ATMAN-LATTICE now models identity continuity, history continuity, use-time freshness, branch restoration, and explicit reconciliation of divergent futures. Merge decisions are ancestry-bound, conflict-complete, provenance-preserving, tamper-evident, and executable in the test harness.

Next targets: one-time token consumption, revocation, asymmetric signer identities, generalized ancestry proofs beyond restore-created branches, and integration with real agent checkpoint/memory systems.
