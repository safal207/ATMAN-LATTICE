# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Governance, Verification, Economy, Active Learning, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, possibility, reconciliation, authorization, privileged execution, trust-root evolution, transition geometry, geometric coherence, finite verification capacity, durable verification debt, adaptive verification cost, active uncertainty reduction, and evidence-bound Bayesian learning.

> What must remain invariant when representation changes, futures branch, paths become order-sensitive, verification capacity saturates, scarce attention must be allocated, and new evidence changes the system's uncertainty model — so that identity, ancestry, uncertainty, path dependence, evidence, cost, verification state, and permission remain provable rather than merely asserted?

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
Completion != EvidenceInterpretation
Interpretation != Posterior
Posterior != Truth
OneCompletion != InfiniteEvidence
LikelihoodRebase != LikelihoodReEstimation
```

# v1.10 — Bayesian Evidence Loop

v1.10 closes the learning loop started by v1.9.

```text
uncertainty
   |
ATMAN-ACTIVE/1.9 selects next question
   |
ATMAN-VERIFY/1.7 completes verification
   |
VerificationCompletionReceipt
   |
precommitted interpretation
   |
EvidenceInterpretationReceipt
   |
ATMAN-BAYES/1.10
   |
Bayesian posterior
   |
new HypothesisState
   |
cohort propagation + likelihood freshness rebind
   |
recalculate expected information gain
   |
next question
```

The six process-level protocol planes are now:

```text
ATMAN-RUNTIME/1.1  privileged execution
ATMAN-TRUST/1.2    trust-root governance
ATMAN-VERIFY/1.7   durable verification / completion / finalization
ATMAN-ECONOMY/1.8  measured verification cost / finite budget
ATMAN-ACTIVE/1.9   expected information gain / next-check selection
ATMAN-BAYES/1.10   evidence interpretation / posterior knowledge update
```

## Completion is not evidence interpretation

A verification result (`PASS`, `HOLD`, `FAIL`) does not directly become a Bayesian positive/negative observation.

An `EvidenceInterpretationRule` maps those decisions into:

```text
POSITIVE
NEGATIVE
INCONCLUSIVE
```

and binds the exact candidate and exact likelihood-model hash.

```text
Completion != EvidenceInterpretation
```

## Interpretation is precommitted

The runtime requires the interpretation rule to exist before the referenced verification completes.

```text
CommittedSemantics -> observe result   OK
Observe result -> choose semantics     X
```

This prevents hindsight remapping of a result after it is known.

## Bayesian evidence update

For binary hypothesis prior `p`, sensitivity `s=P(+|H)`, and false-positive probability `f=P(+|not H)`:

```text
P(H|+) = p*s / (p*s + (1-p)*f)
P(H|-) = p*(1-s) / (p*(1-s) + (1-p)*(1-f))
```

`INCONCLUSIVE` preserves the numerical probability but still advances evidence state and generation because an evidence event occurred.

An impossible observation under the declared model is rejected instead of being normalized into an invented posterior.

```text
Posterior != Truth
```

The posterior is an explicit model state conditioned on the prior, likelihood model, interpretation rule, and verification evidence.

## Exact cohort propagation

Multiple active candidates may reference the same exact `HypothesisState` hash.

When one completed verification advances that prior, every candidate still on that exact prior advances atomically to the same posterior. Candidates already on another hypothesis state are untouched.

```text
A --\
B ----> H(N)
C --/

A produces evidence
      |
      v
    H(N+1)
      |
B and C now use H(N+1)
```

## Likelihood freshness rebind

v1.9 binds likelihood models to exact hypothesis hashes. v1.10 mechanically rebinds current cohort models to the new posterior while preserving their conditional test characteristics.

The model generation advances and a `LikelihoodRebaseReceipt` records old/new model hashes.

```text
LikelihoodRebase != LikelihoodReEstimation
```

If test sensitivity/specificity actually changed, that requires an explicit new model rather than silently changing it during posterior update.

## One completion, one knowledge transition

The runtime persists interpretation/update history and prevents reuse of the same completed verification as an infinite evidence generator.

```text
OneCompletion != InfiniteEvidence
```

## Stale Bayesian previews cannot commit

A preview binds the exact:

- candidate;
- completion hash;
- prior hypothesis;
- likelihood model;
- precommitted interpretation rule;
- shared hypothesis cohort;
- cohort model hashes.

If any of those change before apply:

```text
preview B0
state -> B1
apply(B0)
    X
stale Bayesian evidence state
```

## Authority separation

v1.10 introduces:

```text
BAYESIAN_INTERPRETATION_RULE_KEEPER
BAYESIAN_UPDATE_KEEPER
```

The right to precommit result semantics is not the right to advance knowledge state.

And Bayesian update authority does not grant verification, A4 finalization, execution, or trust-governance authority.

Protocol: [`docs/v1.10-bayesian-evidence-loop.md`](docs/v1.10-bayesian-evidence-loop.md)

Invariants: [`docs/v1.10-invariants.md`](docs/v1.10-invariants.md)

Machine-readable contracts:

- [`schemas/evidence-interpretation-rule.schema.json`](schemas/evidence-interpretation-rule.schema.json)
- [`schemas/evidence-interpretation-receipt.schema.json`](schemas/evidence-interpretation-receipt.schema.json)
- [`schemas/bayesian-update-receipt.schema.json`](schemas/bayesian-update-receipt.schema.json)
- [`schemas/likelihood-rebase-receipt.schema.json`](schemas/likelihood-rebase-receipt.schema.json)

# Prior layers

## v1.9 — Information Gain / Active Verification

Explicit hypothesis state and likelihood models produce expected information gain:

\[
EIG = H(prior)-E[H(posterior\mid outcome)]
\]

and active selection ranks useful uncertainty reduction under finite cost.

```text
ExpectedInformationGain != Truth
SELECTED != VERIFIED
UNMODELED != INVALID
```

Protocol: [`docs/v1.9-active-verification.md`](docs/v1.9-active-verification.md) · Invariants: [`docs/v1.9-invariants.md`](docs/v1.9-invariants.md)

## v1.8 — Adaptive Verification Economy

Observation-derived cost estimates allocate finite verification budget.

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

Long-running agents can branch, restore state, encounter path-dependent operations, change authority, accumulate more verification work than available capacity, choose among tests with different costs/information value, and learn from completed evidence.

ATMAN-LATTICE keeps the questions separate:

- Is this still the same identity and lineage?
- Was a future considered or committed?
- Can valid branches coexist or merge without ancestry erasure?
- Did operation order change the result?
- Was required verification actually completed?
- Was work deferred only because capacity or budget ran out?
- What verification cost was observed rather than declared?
- Which check is expected to reduce uncertainty most?
- How was a completed result interpreted as evidence?
- Was that interpretation committed before the result was known?
- What posterior follows from the explicit prior and likelihood model?
- Is the posterior state still current at use time?
- Did any layer have the authority required for its own action — and only that action?

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
python -m model.bayes_worker
```

Reference protocols:

```text
ATMAN-RUNTIME/1.1
ATMAN-TRUST/1.2
ATMAN-VERIFY/1.7
ATMAN-ECONOMY/1.8
ATMAN-ACTIVE/1.9
ATMAN-BAYES/1.10
```

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox and not a claim about physical multiverses/torsion. Production use additionally requires protected keys, authenticated transport, rollback-resistant storage/backups, protected resource telemetry, empirically calibrated priors/likelihood models, calibration monitoring, database/file permissions, and operational governance.

## Status

**v1.10.0 — Bayesian Evidence Loop research core.**

The project now spans identity continuity, cryptographic lineage, branching/restore/reconciliation, transition torsion and curvature, geometric A3/A4 coherence, finite-capacity verification, durable verification debt, authority-bound completion/finalization, observation-derived cost estimation, adaptive budget allocation, expected-information-gain active selection, precommitted evidence interpretation, Bayesian posterior transitions, exact cohort propagation, likelihood freshness rebinds, process-separated execution, and quorum-governed trust evolution.

Next targets: multi-hypothesis / categorical posterior state, calibration receipts for priors and likelihoods, automatic selected-work handoff into the verification scheduler, rollback-resistant evidence history, protected runtime telemetry, correlated-evidence handling, and concurrency stress tests.
