# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Verification, Active Learning, Calibration, Governed Revision, Structural Evidence Graphs, Finite Search, Protected Confirmation, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, transition geometry, finite verification capacity, evidence-bound learning, competing hypotheses, correlated-evidence provenance, observer calibration, governed parameter and structural revision, held-out validation, finite model search, and one-shot confirmation on provenance-fresh evidence.

> What must remain invariant when an observer can search many models, learn from held-out feedback, and therefore needs a final control surface that search itself cannot repeatedly consume?

The repository does **not** claim to prove metaphysical statements about the soul, consciousness, Atman, quantum worlds, physical multiverses, physical torsion fields, or real-world causal structure. These are conceptual labels and thought experiments inside a formal engineering model.

## Core geometry

```text
Spatial axis:   S1 <----> S3 / A1 <----> S2
Temporal axis:  S4 <----> S6 / A2 <----> S5

A3 = cross-axis identity + path/evidence geometry
A4 = global coherence + commit/finalization gate
```

## Current epistemic pipeline

```text
Possibility / identity lineage
          ↓
transition geometry + coherence
          ↓
verification debt + finite capacity
          ↓
verification economy
          ↓
active information-gain selection
          ↓
Bayesian evidence update
          ↓
multi-hypothesis + correlated evidence
          ↓
observer calibration
          ↓
governed parameter revision
          ↓
governed dependency-graph revision
          ↓
selection-only replay
          ↓
held-out structural validation
          ↓
finite multiple-comparison search budget
          ↓
PROTECTED FRESH CONFIRMATION
          ↓
independent review
          ↓
confirmed graph revision
```

## Accumulated executable warnings

```text
Local PASS != Global Coherence
Historical PASS != Current Authorization
Same identity != Same history
Potentiality != History
Keeper != Sovereign
Same result != Same journey
HOLD != FAIL
Unverified != Invalid
Deferred != Pruned
COMPLETED != PASS
Preview != Finalization
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
Resolution != OntologicalTruth
Confidence != Calibration
DependencySignal != ProvenCausality
CalibrationSignal != RewriteAuthority
Proposal != Mutation
ReplayImprovement != Approval
Review != Apply
LearningFromError != ErasingError
CorrelationChallenge != CausalityProof
GraphEdge != PhysicalCause
SelectionData != EvaluationData
BetterReplay != BetterGeneralization
MoreEdges != MoreKnowledge
OneHeldOutSet != InfiniteSelectionBudget
RepeatedEvaluation != FreshEvidence
SearchMultiplicity != Knowledge
NewSplit != FreshEvidence
RepartitionedOldData != FreshHoldout
SearchHoldout != ConfirmationHoldout
CONFIRMED != ProvenCausality
Confirmation != Truth
CONFIRMED != APPLIED
```

# v1.17 — Protected Fresh Holdout Rotation

v1.17 introduces a final confirmation plane **after** v1.16 has already searched, multiplicity-corrected, selected, and independently reviewed a structural candidate.

```text
DISCOVERY
   ↓
selection-only model construction
   ↓
v1.15 held-out validation
   ↓
v1.16 finite-search correction
   ↓
selected model + APPROVE review
   ↓
sealed provenance-fresh confirmation batch
   ↓
one-shot exposure authorization
   ↓
final confirmation scoring
   ↓
independent confirmation review
   ↓
confirmed apply
```

## Freshness means new provenance

v1.17 deliberately does not create another bucket from the same calibration/search dataset.

A protected confirmation batch must be disjoint from search history by:

```text
sample_hash
resolution_hash
left_evidence_hash
right_evidence_hash
```

It must also be disjoint from every prior confirmation batch for the same subject/pair.

Therefore:

```text
NewSplit != FreshEvidence
NewBatchName != NewEvidence
RepartitionedOldData != FreshHoldout
```

A caller cannot wrap the same resolved event in a different sample object and call it fresh.

## Confirmation data is not a search surface

Protected batch sample JSON lives in separate confirmation runtime state.

The search and structural protocol surfaces do not expose an operation that enumerates confirmation samples.

The reference implementation provides a logical/process/database boundary. It is **not** a hostile-host data room; production deployment additionally needs protected storage, ACLs, leakage controls, and audit logging.

## One selection, one final look

A `ConfirmationExposureReceipt` binds one exact:

```text
v1.16 selection
selected candidate
v1.16 review
confirmation batch
confirmation policy
search history
base graph
```

Rules:

```text
OneSelection -> AtMostOneConfirmationExposure
OneBatch -> AtMostOneSelection
```

If the final confirmation rejects the model, the same search selection does not get another final batch until it passes. The workflow returns to discovery/search instead.

## Confirmation does not train on confirmation

Predictions are fitted from the candidate's already-bound selection/training samples.

The protected final batch is used only for scoring.

The reference score retains v1.15 graph-complexity regularization:

```text
base_regularized_brier = base_mean_brier + edge_penalty * base_edges
proposed_regularized_brier = proposed_mean_brier + edge_penalty * proposed_edges
regularized_improvement = base_regularized_brier - proposed_regularized_brier
```

Statuses:

```text
INSUFFICIENT_CONFIRMATION
CONFIRMATION_REJECTED
CONFIRMED
```

`CONFIRMED` requires enough scoreable fresh cases and regularized improvement above the explicit confirmation-policy threshold.

## Confirmation is still not truth

The graph relation remains:

```text
STATISTICAL_CONDITIONING
```

Passing a protected final holdout strengthens evidence that the selected statistical structure generalized beyond its search surfaces.

It does not prove a physical mechanism, universal validity, causal direction, or ontological truth.

```text
CONFIRMED != ProvenCausality
Confirmation != Truth
```

## Freshness is checked again at use time

Before confirmation evaluation and again before apply, the runtime reconstructs the current v1.16 search state.

New search evidence, changed candidate exposure, a changed winner, or a changed base graph makes the old confirmation chain stale.

The runtime also rechecks that protected confirmation provenance did not later leak into search history.

```text
OldSearchSelection != CurrentConfirmationAuthority
LaterLeakage != ProtectedHoldout
```

## Authority separation

v1.17 adds:

```text
CONFIRMATION_POLICY_KEEPER
CONFIRMATION_BATCH_KEEPER
CONFIRMATION_EXPOSURE_KEEPER
CONFIRMATION_EVALUATOR
CONFIRMATION_REVIEWER
CONFIRMED_STRUCTURAL_APPLIER
```

Core separations include:

```text
candidate proposer != batch keeper
search selector != batch keeper
exposure keeper != proposer / selector / batch keeper
evaluator != proposer / selector / batch keeper / exposure keeper
reviewer != proposer / selector / evaluator
CONFIRMED != APPLIED
```

## Runtime

Worker:

```bash
python -m model.confirm_worker
```

Protocol:

```text
ATMAN-CONFIRM/1.17
```

Operations:

```text
register_confirmation_policy
seal_confirmation_batch
authorize_confirmation_exposure
evaluate_confirmation
record_confirmation_review
apply_confirmed_structural_selection
get_confirmation_state
```

Protocol document: [`docs/v1.17-protected-fresh-holdout.md`](docs/v1.17-protected-fresh-holdout.md)

Invariants: [`docs/v1.17-invariants.md`](docs/v1.17-invariants.md)

Machine-readable contracts:

- [`schemas/protected-confirmation-policy.schema.json`](schemas/protected-confirmation-policy.schema.json)
- [`schemas/protected-confirmation-batch.schema.json`](schemas/protected-confirmation-batch.schema.json)
- [`schemas/confirmation-exposure.schema.json`](schemas/confirmation-exposure.schema.json)
- [`schemas/confirmation-evaluation.schema.json`](schemas/confirmation-evaluation.schema.json)
- [`schemas/confirmation-review.schema.json`](schemas/confirmation-review.schema.json)
- [`schemas/confirmed-graph-revision.schema.json`](schemas/confirmed-graph-revision.schema.json)

## Process planes

```text
ATMAN-RUNTIME/1.1       privileged execution
ATMAN-TRUST/1.2         trust-root governance
ATMAN-VERIFY/1.7        durable verification / completion / finalization
ATMAN-ECONOMY/1.8       measured verification cost / finite budget
ATMAN-ACTIVE/1.9        expected information gain / next-check selection
ATMAN-BAYES/1.10        evidence interpretation / posterior update
ATMAN-MULTI/1.11        competing hypotheses / correlated-evidence provenance
ATMAN-CALIBRATION/1.12  historical observer audit
ATMAN-REVISION/1.13     governed likelihood-parameter revision
ATMAN-GRAPH/1.14        governed structural dependency-graph revision
ATMAN-STRUCTURE/1.15    held-out structural validation / regularization
ATMAN-SEARCH/1.16       finite multiple-comparison search governance
ATMAN-CONFIRM/1.17      protected one-shot fresh confirmation
```

## Backward compatibility

v1.17 is the stronger structural-confirmation path. v1.16 remains available as a historical/backward-compatible protocol rather than silently changing the semantics of an existing wire contract.

A strict deployment profile should route final structural mutation through `ATMAN-CONFIRM/1.17` after installing its policy and disable/directly restrict legacy structural-apply endpoints at the deployment boundary.

# Historical layers

- **v1.16** — finite held-out search budget and multiplicity-aware thresholding. [`protocol`](docs/v1.16-multiple-comparison-search-budget.md) · [`invariants`](docs/v1.16-invariants.md)
- **v1.15** — held-out structural validation and graph-complexity regularization. [`protocol`](docs/v1.15-heldout-structural-validation.md) · [`invariants`](docs/v1.15-invariants.md)
- **v1.14** — governed statistical dependency-DAG revision. [`protocol`](docs/v1.14-structural-dependency-graph-revision.md) · [`invariants`](docs/v1.14-invariants.md)
- **v1.13** — calibration-governed likelihood revision. [`protocol`](docs/v1.13-calibration-governed-model-revision.md) · [`invariants`](docs/v1.13-invariants.md)
- **v1.12** — observer calibration and dependency challenge signals.
- **v1.11** — multi-hypothesis distributions and correlated-evidence provenance.
- **v1.10** — evidence interpretation and Bayesian posterior loop.
- **v1.9** — expected information gain / active verification.
- **v1.8** — adaptive verification economy.
- **v1.7** — runtime verification debt, completion, and finalization.
- **v1.6** — verification pressure / finite observer capacity.
- **v1.5** — geometric coherence gate.
- **v1.4** — transition torsion / curvature analogues.
- **v1.3** — multiverse semantics as formal branching/reality-composition labels.
- **v1.2** — trust-root evolution.
- **v1.1** — full privileged runtime plane.
- **v1.0 and earlier** — process isolation, authority, one-time authorization, merge, restore, freshness, cryptographic lineage, executable observer model, conceptual foundation.

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
python -m model.graph_worker
python -m model.structure_worker
python -m model.search_worker
python -m model.confirm_worker
```

## Status

**v1.17.0 — Protected Fresh Holdout Rotation research core.**

The project now preserves a traceable chain from identity and authority through verification, Bayesian learning, calibration, structural search, held-out evaluation, finite search exposure, and one-shot provenance-fresh final confirmation before the strongest structural apply path.

Production work still requires protected keys, authenticated transport, rollback-resistant storage, protected confirmation data, leakage detection, external/temporal validation where appropriate, formal statistical testing where statistical error guarantees are claimed, causal-identification methodology where causal claims matter, and operational governance.
