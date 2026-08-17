# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Verification, Active Learning, Calibration, Governed Revision, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, transition geometry, finite verification capacity, evidence-bound learning, competing hypotheses, correlated-evidence provenance, observer calibration, and governed correction of the observer's own models.

> What must remain invariant when representation changes, futures branch, paths become order-sensitive, evidence changes beliefs, later outcomes reveal that the observer was wrong, and the observer then proposes to change itself?

The repository does **not** claim to prove metaphysical statements about the soul, consciousness, Atman, quantum worlds, physical multiverses, or physical torsion fields. Those terms are conceptual labels and thought experiments inside a formal engineering model.

## Core geometry

```text
Spatial axis:   S1 <----> S3 / A1 <----> S2
Temporal axis:  S4 <----> S6 / A2 <----> S5

A3 = cross-axis identity + path/evidence geometry
A4 = global coherence + commit/finalization gate
```

## Accumulated executable warnings

```text
Local PASS != Global Coherence
Historical PASS != Current Authorization
Same identity != Same history
Potentiality != History
Keeper != Sovereign
Valid(A) + Valid(B) != Commute(A,B)
Same result != Same journey
Torsion != Invalidity
HOLD != FAIL
Unverified != Invalid
Deferred != Pruned
COMPLETED != PASS
Preview != Finalization
VerifierCapacity != RealityCapacity
DeclaredCost != AccountingCost
FUNDED != VERIFIED
ExpectedInformationGain != Truth
SELECTED != VERIFIED
Completion != EvidenceInterpretation
Interpretation != Posterior
Posterior != Truth
SameSourceEvent != IndependentEvidenceTwice
DifferentDerivation != IndependentSource
DuplicateEvidence != NewKnowledge
ConditionalEvidence != IndependentEvidence
Resolution != OntologicalTruth
Confidence != Calibration
NoDependencySignal != ProvenIndependence
DependencySignal != ProvenCausality
CalibrationSignal != RewriteAuthority
Proposal != Mutation
ReplayImprovement != Approval
Review != Apply
OldReplay != CurrentRevisionAuthority
LearningFromError != ErasingError
HistoricalFit != FutureTruth
```

# v1.13 — Calibration-Governed Model Revision

v1.13 creates a governed correction path from historical model error to a new model generation without allowing the observer to hide or silently overwrite its earlier mistake.

```text
historical calibration
        |
MISCALIBRATION_SIGNAL
        |
        v
ModelRevisionProposal
        |
        v
CounterfactualReplay
        |
        v
Independent Review
        |
        v
APPROVE / HOLD / REJECT
        |
        v
use-time revalidation
        |
        v
Model N -> Model N+1

old Model N remains preserved
```

The nine process-level planes are now:

```text
ATMAN-RUNTIME/1.1       privileged execution
ATMAN-TRUST/1.2         trust-root governance
ATMAN-VERIFY/1.7        durable verification / completion / finalization
ATMAN-ECONOMY/1.8       measured verification cost / finite budget
ATMAN-ACTIVE/1.9        expected information gain / next-check selection
ATMAN-BAYES/1.10        evidence interpretation / posterior update
ATMAN-MULTI/1.11        competing hypotheses / correlated-evidence provenance
ATMAN-CALIBRATION/1.12  historical observer audit
ATMAN-REVISION/1.13     governed model revision
```

## Calibration can trigger a proposal, not a mutation

The revision runtime reconstructs the current v1.12 calibration-family snapshot from persisted observations.

A proposal is accepted only when the snapshot says:

```text
MISCALIBRATION_SIGNAL
```

It binds the exact:

```text
current distribution hash
current likelihood model hash
calibration snapshot hash
current model generation
proposed next-generation likelihood vector
conditioning evidence context
proposer
reason
```

So:

```text
CalibrationSignal != RewriteAuthority
Proposal != Mutation
```

## Counterfactual replay

A proposal is replayed on the same persisted, resolved historical observations.

Every replay case records:

```text
historical calibration hash
resolved hypothesis
observed POSITIVE / NEGATIVE
old predicted probability
proposed predicted probability
old Brier score
proposed Brier score
```

The replay receipt binds the exact case set and reports:

```text
INSUFFICIENT_SCORABLE_CASES
IMPROVED
NO_IMPROVEMENT
```

`IMPROVED` requires strictly lower mean Brier score on the bound history.

```text
ReplayImprovement != Approval
HistoricalFit != FutureTruth
```

Historical improvement is evidence for review, not proof of future correctness.

## Independent review

A proposal cannot approve itself:

```text
proposer_ref != reviewer_ref
```

Review outcomes:

```text
APPROVE
HOLD
REJECT
```

`APPROVE` is structurally forbidden unless the replay is `IMPROVED`.

```text
Replay != Review
Review != Apply
```

## Apply is revalidated at use time

Before mutation the runtime checks again that:

- current model hash still equals the proposal base model;
- current distribution still equals the proposal base distribution;
- proposal, replay, and review hashes match exactly;
- replay is `IMPROVED`;
- review is `APPROVE`;
- all currently persisted relevant calibration observations still produce the same replay state.

If new calibration evidence appeared after review:

```text
old replay
   |
new resolved case
   |
apply old replay
   X

stale counterfactual replay
```

Therefore:

```text
OldReplay != CurrentRevisionAuthority
```

A new proposal/replay/review cycle is required.

## Learning does not erase the mistake

Successful apply creates:

```text
MultiLikelihoodModel generation N+1
```

and moves the current model pointer to it.

But `model_revision_history` preserves both:

```text
base model JSON
new model JSON
proposal
replay
review
revision receipt
```

All earlier calibration targets, resolutions, and scores remain untouched.

```text
NewModel != RewrittenOldModel
LearningFromError != ErasingError
```

## Authority separation

v1.13 adds:

```text
MODEL_REVISION_PROPOSER
MODEL_REVISION_REPLAY_KEEPER
MODEL_REVISION_REVIEWER
MODEL_REVISION_APPLIER
```

These are independent permissions.

```text
Diagnose != Propose != Replay != Review != Apply
```

## Scope boundary: numeric revision, not causal rewrite

v1.13 revises likelihood **values** while preserving the current hypothesis set and the model's exact conditioning-evidence context.

It does not automatically convert:

```text
INDEPENDENCE_CHALLENGED
```

into a new conditional dependency graph.

That would change the semantic structure of the evidence model, not merely its calibration parameters.

```text
DependencyChallenge != DependencyRewriteAuthority
```

Protocol: [`docs/v1.13-calibration-governed-model-revision.md`](docs/v1.13-calibration-governed-model-revision.md)

Invariants: [`docs/v1.13-invariants.md`](docs/v1.13-invariants.md)

Machine-readable contracts:

- [`schemas/model-revision-proposal.schema.json`](schemas/model-revision-proposal.schema.json)
- [`schemas/model-revision-replay-case.schema.json`](schemas/model-revision-replay-case.schema.json)
- [`schemas/model-revision-counterfactual-replay.schema.json`](schemas/model-revision-counterfactual-replay.schema.json)
- [`schemas/model-revision-review.schema.json`](schemas/model-revision-review.schema.json)
- [`schemas/model-revision-receipt.schema.json`](schemas/model-revision-receipt.schema.json)

# Prior executable layers

## v1.12 — Calibration / Dependency Learning

Freeze pre-outcome assumptions, register later resolution, score forecasts/likelihoods with deterministic Brier metrics, and challenge historical independence assumptions without automatically rewriting the model.

```text
PosthocModel != HistoricalForecast
Confidence != Calibration
NoDependencySignal != ProvenIndependence
DependencySignal != ProvenCausality
CalibrationSignal != RewriteAuthority
```

Protocol: [`docs/v1.12-calibration-dependency-learning.md`](docs/v1.12-calibration-dependency-learning.md) · Invariants: [`docs/v1.12-invariants.md`](docs/v1.12-invariants.md)

## v1.11 — Multi-Hypothesis / Correlated Evidence Geometry

```text
PosteriorDistribution != Truth
SameSourceEvent != IndependentEvidenceTwice
DifferentDerivation != IndependentSource
ConditionalEvidence != IndependentEvidence
DuplicateEvidence != NewKnowledge
```

## v1.10 — Bayesian Evidence Loop

```text
Completion != EvidenceInterpretation
Interpretation != Posterior
Posterior != Truth
OneCompletion != InfiniteEvidence
```

## v1.9 — Information Gain / Active Verification

```text
ExpectedInformationGain != Truth
SELECTED != VERIFIED
UNMODELED != INVALID
```

## v1.8 — Adaptive Verification Economy

```text
DeclaredCost != AccountingCost
FUNDED != VERIFIED
DeferredBudget != FAIL
```

## v1.7 — Runtime Verification Plane

```text
COMPLETED != PASS
Preview != Finalization
```

## v1.6 — Verification Pressure / Temporal Loom

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

## v1.1 and earlier

- **v1.1** — full privileged runtime plane and atomically serialized authorization state.
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
python -m model.multi_worker
python -m model.calibration_worker
python -m model.revision_worker
```

Reference protocols:

```text
ATMAN-RUNTIME/1.1
ATMAN-TRUST/1.2
ATMAN-VERIFY/1.7
ATMAN-ECONOMY/1.8
ATMAN-ACTIVE/1.9
ATMAN-BAYES/1.10
ATMAN-MULTI/1.11
ATMAN-CALIBRATION/1.12
ATMAN-REVISION/1.13
```

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox and not a claim about physical multiverses/torsion. Counterfactual replay is historical evaluation, not proof of out-of-distribution performance. Production use additionally requires protected keys, authenticated transport, rollback-resistant storage, protected resolution provenance, held-out evaluation, drift monitoring, database/file permissions, and operational governance.

## Status

**v1.13.0 — Calibration-Governed Model Revision research core.**

The project now spans identity continuity, cryptographic lineage, branching/reconciliation, transition torsion and curvature, geometric A3/A4 coherence, finite verification capacity, durable verification debt, adaptive cost allocation, active information gain, evidence-bound Bayesian learning, multi-hypothesis distributions, correlated-evidence provenance, observer calibration, frozen historical model audit, governed counterfactual revision, independent review, use-time replay freshness, append-only old/new model history, process-separated execution, and quorum-governed trust evolution.

Next targets: **structural dependency-graph revision**, held-out/cross-validation replay partitions, resolver correction receipts, rollback-resistant learning history, and concurrency stress across calibration/revision races.
