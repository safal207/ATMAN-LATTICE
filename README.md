# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Governance, Verification, Economy, Active Selection, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, possibility, reconciliation, authorization, privileged execution, trust-root evolution, transition geometry, geometric coherence, finite verification capacity, durable verification debt, adaptive verification cost, and active uncertainty reduction.

> What must remain invariant when representation changes, futures branch, paths become order-sensitive, verification capacity saturates, or scarce attention must be allocated — so that identity, ancestry, uncertainty, path dependence, cost evidence, verification state, and permission remain provable rather than merely asserted?

The repository does **not** claim to prove metaphysical statements about the soul, consciousness, Atman, quantum worlds, physical multiverses, or physical torsion fields. Those terms are conceptual labels and thought experiments inside a formal engineering model.

## Core geometry

```text
Spatial axis:   S1 <----> S3 / A1 <----> S2
Temporal axis:  S4 <----> S6 / A2 <----> S5

A3 = cross-axis identity + path geometry
A4 = global coherence + commit/finalization gate
```

## Accumulated executable warnings

```text
Local PASS != Global Coherence
Historical PASS != Current Authorization
Same identity != Same history
Valid parents != Automatically coherent merge
Valid token != Reusable capability
Valid signature != Valid authority
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
ExpectedInformationGain != Truth
SELECTED != VERIFIED
UNMODELED != INVALID
LowExpectedGain != FAIL
```

# v1.9 — Information Gain / Active Verification

v1.9 adds a fifth process-separated plane:

```text
ATMAN-RUNTIME/1.1  privileged execution
ATMAN-TRUST/1.2    trust-root governance
ATMAN-VERIFY/1.7   durable verification / completion / finalization
ATMAN-ECONOMY/1.8  measured verification cost / finite budget
ATMAN-ACTIVE/1.9   uncertainty model / expected information gain / next-check selection
```

The core question becomes:

> Given the current explicit uncertainty model and current estimated verification cost, which check is expected to reduce uncertainty most per unit of scarce verification attention?

The central laws are:

```text
ExpectedInformationGain != Truth
SELECTED != VERIFIED
LowExpectedGain != FAIL
UNMODELED != PRUNED
```

## Explicit hypothesis state

`HypothesisState` binds:

```text
hypothesis_ref
subject_identity_ref
true_probability_bps
evidence_state_hash
generation
hypothesis_hash
```

A probability is therefore a versioned model input tied to an exact evidence-state digest, not ambient truth.

## Exact likelihood binding

`VerificationLikelihoodModel` commits:

```text
candidate_hash
hypothesis_hash
positive_if_true_bps
positive_if_false_bps
model_ref
model_generation
```

If the hypothesis changes from H1 to H2, the old likelihood remains bound to H1 and cannot be silently reused:

```text
Likelihood(H1) != Likelihood(H2)
```

The runtime consequently classifies the candidate as unmodeled until a current model is registered.

## Expected information gain

The binary reference core uses Shannon entropy:

\[
H(p)=-p\log_2 p-(1-p)\log_2(1-p)
\]

and computes:

\[
EIG = H(prior)-E[H(posterior\mid outcome)].
\]

The receipt preserves prior entropy, expected posterior entropy, expected information gain, current v1.8 estimated verification cost, and information-per-cost ratio.

The entropy result is quantized into integer microbits for receipt material. It is a calculation over explicit probabilistic assumptions; it is **not** evidence that those assumptions are empirically calibrated.

## Active selection

Modeled candidates may be classified as:

```text
SELECTED
DEFERRED_BUDGET
DEFERRED_OVERSIZED
DEFERRED_LOW_INFORMATION
```

Candidates without a current hypothesis/likelihood pair are preserved by the runtime as:

```text
UNMODELED
```

The active plane selects attention only. It cannot directly write a verification completion, A4 PASS, or privileged execution permission.

```text
MODEL   -> expected information
ACTIVE  -> next-check selection
VERIFY  -> evidence verdict
A4      -> coherence finalization
```

## Active-state use-time binding

The runtime state digest commits current:

```text
incomplete economic candidates
v1.8 estimator state
hypothesis hashes
likelihood-model hashes
active policy
economy policy
```

So:

```text
preview K0
knowledge/economy state -> K1
finalize(K0)
    X
stale active verification state
```

This extends the project's use-time principle to the state of knowledge itself.

Protocol: [`docs/v1.9-active-verification.md`](docs/v1.9-active-verification.md)

Invariants: [`docs/v1.9-invariants.md`](docs/v1.9-invariants.md)

Machine-readable contracts:

- [`schemas/hypothesis-state.schema.json`](schemas/hypothesis-state.schema.json)
- [`schemas/verification-likelihood-model.schema.json`](schemas/verification-likelihood-model.schema.json)
- [`schemas/expected-information-gain.schema.json`](schemas/expected-information-gain.schema.json)
- [`schemas/active-verification-policy.schema.json`](schemas/active-verification-policy.schema.json)
- [`schemas/active-verification-plan.schema.json`](schemas/active-verification-plan.schema.json)

# Prior layers

## v1.8 — Adaptive Verification Economy

Observed completion-bound cost evidence feeds estimator snapshots and finite-budget allocation.

```text
DeclaredCost != AccountingCost
FUNDED != VERIFIED
DeferredBudget != FAIL
```

Protocol: [`docs/v1.8-adaptive-verification-economy.md`](docs/v1.8-adaptive-verification-economy.md) · Invariants: [`docs/v1.8-invariants.md`](docs/v1.8-invariants.md)

## v1.7 — Runtime Verification Plane

Durable verification debt, admission, completion receipts, `PASS/HOLD/FAIL`, and authority-bound current-state finalization.

```text
COMPLETED != PASS
Preview != Finalization
```

Protocol: [`docs/v1.7-runtime-verification-plane.md`](docs/v1.7-runtime-verification-plane.md) · Invariants: [`docs/v1.7-invariants.md`](docs/v1.7-invariants.md)

## v1.6 — Verification Pressure / Temporal Loom

Finite verifier capacity without converting overload into semantic failure.

```text
UNVERIFIED != INVALID
ADMITTED != VERIFIED
DEFERRED != PRUNED
```

## v1.5 — Geometric Coherence Gate

Torsion and curvature evidence enter A3/A4 under explicit `PASS < HOLD < FAIL` policy semantics.

## v1.4 — Transition Geometry

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

## v1.3 — Multiverse Semantics

```text
Potentiality != History
Valid(A) + Valid(B) != Coexist(A,B)
Composite(C) => Parents(C) preserved
Preserve(Worlds) != AuthorityToRewrite(Worlds)
```

## v1.2 — Trust-Root Evolution

Trust mutation requires quorum approval from the current persisted root policy.

## v1.1 — Full Runtime Plane

Privileged observer, capability, consumption/revocation, and merge operations execute behind a process/database boundary.

## v1.0 and earlier

- **v1.0** — process-separated observer runtime.
- **v0.9** — exact pre-execution authority enforcement.
- **v0.8** — Ed25519 signer identity, roles, scopes, policy generation.
- **v0.7** — one-time consumption/revocation ledger.
- **v0.6** — explicit branch merge/reconciliation.
- **v0.5** — restore creates a new lineage fork.
- **v0.4** — freshness/context/use binding.
- **v0.3** — cryptographic identity lineage.
- **v0.2** — executable A1/A2/A3/A4 observers.
- **v0.1** — conceptual identity/coherence foundation.

## Why this matters for AI systems

Long-running agents can have alternative plans, restored memories, path-dependent operations, changing authority, more verification work than available capacity, checks with very different real costs, and multiple possible tests that reveal very different amounts of information.

ATMAN-LATTICE keeps the questions separate:

- Is this still the same identity?
- Is this the same history?
- Was a future considered or committed?
- Can valid branches coexist?
- Did operation order change the result?
- Is path dependence acceptable or reconciliation-worthy?
- Was required verification actually completed?
- Was work deferred only because capacity/budget ran out?
- What verification cost was observed rather than declared?
- Which check is expected to reduce uncertainty most?
- Is its uncertainty model still current?
- Did the verifier return PASS/HOLD/FAIL?
- Is finalization still bound to the current state?
- Who had authority at each layer?

## Run

```bash
python -m pip install -e . pytest
python -m pytest -q
```

Workers:

```bash
python -m model.runtime_worker
python -m model.verification_worker
python -m model.economy_worker
python -m model.active_worker
```

Reference protocols:

```text
ATMAN-RUNTIME/1.1
ATMAN-TRUST/1.2
ATMAN-VERIFY/1.7
ATMAN-ECONOMY/1.8
ATMAN-ACTIVE/1.9
```

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox and not a claim about physical multiverses/torsion. Production use additionally requires protected keys, authenticated transport, rollback-resistant storage/backups, protected resource telemetry, empirically calibrated uncertainty/likelihood models, database/file permissions, and operational governance.

## Status

**v1.9.0 — Information Gain / Active Verification research core.**

The project now spans identity continuity, cryptographic lineage, branching/restore/reconciliation, transition torsion and curvature, geometric A3/A4 coherence, finite-capacity verification, durable verification debt, authority-bound completion/finalization, observation-derived cost estimation, adaptive budget allocation, explicit probabilistic hypothesis state, exact likelihood binding, expected information gain, stale-safe active selection, process-separated execution, and quorum-governed trust evolution.

Next targets: posterior updates from completed evidence, multi-hypothesis information gain, model calibration receipts, automatic handoff from active selection into the verification scheduler, protected runtime telemetry, rollback-resistant active/economy state, and concurrency stress tests.
