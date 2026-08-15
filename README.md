# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity as linked projections across state, space, time, lineage, and execution context.

> What must remain invariant when representation changes, so that we can still prove that the resulting state belongs to the same identity?

The repository does **not** claim to prove metaphysical statements about the soul, sleep, consciousness, or Atman. Those terms are conceptual labels for nodes and observer roles inside a formal model. The engineering goal is testable continuity, provenance, observer independence, freshness, branching, and global coherence.

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

And the executable warning:

```text
Local PASS != Global Coherence
Historical PASS != Current Authorization
Same identity != Same history
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

The central TOCTOU rule is:

> **Historical PASS is not current authorization.**

A context change, stale attestation, expired token, or authenticated-field mutation makes execution fail.

## v0.5 — replay, restore, and branch identity

Version `0.5.0` formalizes restoration from a historical checkpoint.

The central rule is:

> **Restore is not continuation.**

Returning to an old checkpoint must create a new branch, a higher generation, and a new cryptographic lineage root while preserving an explicit proof edge to the source checkpoint.

```text
old branch

R0 -> R1 -> R2 -> R3 -> R4
            |
            | RestoreReceipt
            v
            R0' -> new future
            new branch
            new generation
            new lineage root
```

A valid restore therefore preserves:

```text
same identity ancestry
+ exact source checkpoint provenance
```

while requiring:

```text
new branch_ref
new generation
new lineage_root_hash
```

This yields another invariant:

> **Same identity does not imply same history.**

[`model/replay.py`](model/replay.py) implements `RestoreReceipt`, `restore_checkpoint()`, and `verify_restore()`.

Executable negative cases prove that a restore cannot:

- reuse the source branch;
- reuse the old generation;
- silently preserve the old lineage root;
- substitute a different restored target;
- mutate the committed source checkpoint without detection.

Machine-readable contract: [`schemas/restore-receipt.schema.json`](schemas/restore-receipt.schema.json).

Protocol note: [`docs/v0.5-replay-restore.md`](docs/v0.5-replay-restore.md).

## Why this matters for AI systems

The same identity problem appears when agents move through:

- working and compressed memory;
- simulations and replays;
- checkpoints and restore operations;
- forked planning branches;
- tool and policy context changes;
- long-horizon execution across multiple generations.

A restored agent may be descended from the same prior identity while no longer belonging to the same execution history. ATMAN-LATTICE makes that distinction explicit and testable.

## Documents

- [THEORY.md](THEORY.md) — conceptual/formal model
- [INVARIANTS.md](INVARIANTS.md) — invariant set
- [v0.4 signed freshness](docs/v0.4-signed-freshness.md)
- [v0.5 replay/restore](docs/v0.5-replay-restore.md)

## Run

```bash
python -m pip install pytest
python -m pytest -q
```

The suite also runs in GitHub Actions on pushes to `main` and pull requests.

## Status

`v0.5` — replay/restore research core. ATMAN-LATTICE now models identity continuity separately from history continuity: restored checkpoints preserve explicit ancestry but must begin a distinct branch, generation, and cryptographic lineage root. Deliberate replay/restore collision fixtures are executable and CI-backed.

Next targets: branch merge semantics, one-time token consumption, revocation, asymmetric signer identities, and integration with real agent checkpoint/memory systems.
