# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Verification, Active Learning, Calibration, Governed Revision, Structural Evidence Graphs, Held-Out Validation, Finite Search Governance, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, transition geometry, finite verification capacity, evidence-bound learning, competing hypotheses, correlated-evidence provenance, observer calibration, governed parameter correction, structural dependency-graph revision, held-out structural validation, and finite governance of repeated model search against held-out evidence.

> What must remain invariant when representation changes, futures branch, evidence changes beliefs, the observer changes its model, validates that change on held-out history, and then must avoid learning the held-out set itself by looking at it too many times?

The repository does **not** claim to prove metaphysical statements about the soul, consciousness, Atman, quantum worlds, physical multiverses, physical torsion fields, or real-world causal structure. Those terms are conceptual labels and thought experiments inside a formal engineering model.

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
LearningFromError != ErasingError
HistoricalFit != FutureTruth
CorrelationChallenge != CausalityProof
GraphEdge != PhysicalCause
LearningStructure != ErasingPriorStructure
SelectionData != EvaluationData
BetterReplay != BetterGeneralization
MoreEdges != MoreKnowledge
HeldOutImprovement != CausalityProof
RegularizedSelection != Truth
Selected != Applied
OneHeldOutSet != InfiniteSelectionBudget
RepeatedEvaluation != FreshEvidence
SearchMultiplicity != Knowledge
HeldOutImproved != SearchCorrectedImproved
BudgetExhausted != CandidateInvalid
AlreadyObserved != FreshHeldOutEvidence
OldExposureSet != CurrentSelectionAuthority
```

# v1.16 — Multiple-Comparison / Search-Budget Governance

v1.15 separates structure discovery from held-out evaluation. v1.16 adds the next boundary:

> A held-out set is a finite information resource. Repeatedly searching against it gradually turns evaluation into training unless exposure itself is governed.

```text
structural candidate
        |
        v
search reservation   <--- consumes unique look
        |
        v
v1.15 held-out validation
        |
        v
multiplicity threshold
        |
   +----+----------------+
   |                     |
SEARCH_CORRECTED      MULTIPLICITY /
IMPROVED              HELDOUT REJECTED
   |
   v
complete current search set
   |
   v
search-budget selection
   |
independent review
   |
use-time exposure/history/base freshness
   |
Graph N -> Graph N+1
```

## Twelve process-level planes

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
ATMAN-STRUCTURE/1.15    held-out structural validation / regularized selection
ATMAN-SEARCH/1.16       finite held-out search / multiplicity governance
```

## Reservation must happen before held-out exposure

A v1.16 candidate cannot first inspect evaluation results and later decide whether that inspection should count.

`HeldOutSearchReservation` is committed before the held-out partition is evaluated.

It binds:

```text
candidate hash
search family
exact structural context
unique ordinal
maximum search capacity
effective minimum improvement
budget keeper
```

```text
Reserve(candidate) -> Evaluate(candidate)
```

not the reverse.

If a candidate was already evaluated through the unbudgeted v1.15 runtime, the v1.16 reference runtime rejects it as fresh held-out evidence:

```text
AlreadyObserved != FreshHeldOutEvidence
```

## Repeated looks do not create new evidence

One exact `candidate_hash` can own only one reservation in a search family.

Re-requesting the same candidate returns the same immutable reservation and does not increase the search ordinal.

```text
RepeatedEvaluation != FreshEvidence
```

## Search budget is cumulative across history and graph changes

The v1.16 search family binds:

```text
subject identity
pair key
structural validation policy
search budget policy
```

It intentionally does not include one particular `history_hash` or base graph generation.

So this is forbidden conceptually:

```text
History H0: candidate A -> look #1
new sample arrives
History H1: candidate B -> look #1 again
```

Instead:

```text
candidate A -> ordinal 1
candidate B -> ordinal 2
```

under the same family.

```text
NewHistory != SearchBudgetReset
```

## Multiplicity raises the required improvement

`HeldOutSearchBudgetPolicy` defines:

```text
max_unique_evaluations
base_min_regularized_improvement_ppm
multiplicity_penalty_ppm
```

For unique look `n`:

```text
required_improvement_n =
    base_min_regularized_improvement_ppm
    + multiplicity_penalty_ppm * (n - 1)
```

The ordinary v1.15 held-out receipt is preserved. v1.16 adds a separate search-adjusted receipt.

Possible search outcomes:

```text
UNDERLYING_HELDOUT_REJECTED
MULTIPLICITY_REJECTED
SEARCH_CORRECTED_IMPROVED
```

Therefore a candidate may honestly have:

```text
v1.15: HELDOUT_IMPROVED
v1.16: MULTIPLICITY_REJECTED
```

The first statement is about one held-out comparison. The second is about that comparison after accounting for prior search exposure.

This linear multiplicity penalty is an explicit governance regularizer. It is not presented as a p-value or formal family-wise error theorem.

## Search selection binds cumulative exposure

Selection considers candidates in the current exact structural context, but records the **entire cumulative family reservation set**.

Every currently reserved candidate must have a completed search-adjusted evaluation before selection can finalize.

Eligible candidates require:

```text
SEARCH_CORRECTED_IMPROVED
```

The winner maximizes:

```text
search_adjusted_margin =
    regularized_heldout_improvement
    - multiplicity_threshold
```

A new reservation after selection changes the exposure state. Apply recomputes selection and rejects the stale receipt:

```text
OldExposureSet != CurrentSelectionAuthority
```

Current history and base graph must also still match.

## Budget exhaustion is not invalidity

When the configured unique-look budget is exhausted, another evaluation is forbidden under that search policy.

That means only:

```text
no more held-out looks under this policy
```

not:

```text
unevaluated candidate is false
```

```text
BudgetExhausted != CandidateInvalid
```

## Authority separation

v1.16 adds:

```text
HELDOUT_SEARCH_POLICY_KEEPER
HELDOUT_SEARCH_BUDGET_KEEPER
HELDOUT_SEARCH_EVALUATOR
SEARCH_BUDGET_MODEL_SELECTOR
SEARCH_BUDGET_SELECTION_REVIEWER
SEARCH_BUDGETED_STRUCTURAL_APPLIER
```

The core requires proposer != budget keeper, proposer != evaluator, budget keeper != evaluator, and review independence from selector/selected proposer.

```text
Propose != Reserve != Evaluate != Select != Review != Apply
```

## Runtime

Worker:

```bash
python -m model.search_worker
```

Protocol operations:

```text
register_search_budget_policy
reserve_heldout_evaluation
evaluate_reserved_candidate
finalize_search_budget_selection
record_search_budget_selection_review
apply_search_budgeted_selection
get_search_budget_state
```

Protocol: [`docs/v1.16-multiple-comparison-search-budget.md`](docs/v1.16-multiple-comparison-search-budget.md)

Invariants: [`docs/v1.16-invariants.md`](docs/v1.16-invariants.md)

Machine-readable contracts:

- [`schemas/heldout-search-budget-policy.schema.json`](schemas/heldout-search-budget-policy.schema.json)
- [`schemas/heldout-search-reservation.schema.json`](schemas/heldout-search-reservation.schema.json)
- [`schemas/search-adjusted-validation.schema.json`](schemas/search-adjusted-validation.schema.json)
- [`schemas/search-budget-selection.schema.json`](schemas/search-budget-selection.schema.json)
- [`schemas/search-budget-selection-review.schema.json`](schemas/search-budget-selection-review.schema.json)
- [`schemas/search-budgeted-graph-revision.schema.json`](schemas/search-budgeted-graph-revision.schema.json)

# Prior executable layers

## v1.15 — Held-Out Structural Validation / Complexity-Regularized Graph Selection

v1.15 separates graph discovery data from deterministic held-out evaluation and charges explicit edge complexity.

```text
History = Selection union Evaluation
Selection intersection Evaluation = empty
SelectionData != EvaluationData
BetterReplay != BetterGeneralization
MoreEdges != MoreKnowledge
```

Candidate statuses:

```text
INSUFFICIENT_HELDOUT
HELDOUT_IMPROVED
OVERFIT_SIGNAL
COMPLEXITY_REJECTED
```

`finalize_structural_selection` loads every held-out-validated candidate sharing the exact subject/pair/base/policy/history context. A new validated competitor, new history, or new base graph makes an old selection stale.

```text
OldCandidateSet != CurrentSelectionAuthority
OldHistory != CurrentSelectionAuthority
OldBaseGraph != CurrentSelectionAuthority
HeldOutImprovement != CausalityProof
RegularizedSelection != Truth
```

Protocol: [`docs/v1.15-heldout-structural-validation.md`](docs/v1.15-heldout-structural-validation.md) · Invariants: [`docs/v1.15-invariants.md`](docs/v1.15-invariants.md)

## v1.14 — Structural Dependency-Graph Revision

Correlation challenges can produce competing directed `STATISTICAL_CONDITIONING` proposals. Structural mutation requires versioned DAG state, leave-one-out replay, independent review, use-time replay freshness, and append-only old/new graph history.

```text
CorrelationChallenge != CausalityProof
GraphEdge != PhysicalCause
StructuralProposal != StructuralMutation
OldStructuralReplay != CurrentStructuralRevisionAuthority
LearningStructure != ErasingPriorStructure
```

Protocol: [`docs/v1.14-structural-dependency-graph-revision.md`](docs/v1.14-structural-dependency-graph-revision.md) · Invariants: [`docs/v1.14-invariants.md`](docs/v1.14-invariants.md)

## v1.13 — Calibration-Governed Model Revision

```text
CalibrationSignal != RewriteAuthority
Proposal != Mutation
ReplayImprovement != Approval
Review != Apply
OldReplay != CurrentRevisionAuthority
LearningFromError != ErasingError
HistoricalFit != FutureTruth
```

## v1.12 — Calibration / Dependency Learning

```text
PosthocModel != HistoricalForecast
Confidence != Calibration
NoDependencySignal != ProvenIndependence
DependencySignal != ProvenCausality
```

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

```text
Same result != Same journey
Torsion != Invalidity
Semantic closure != History erasure
```

## v1.3 — Multiverse Semantics

```text
Potentiality != History
Valid(A) + Valid(B) != Coexist(A,B)
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
python -m model.graph_worker
python -m model.structure_worker
python -m model.search_worker
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
ATMAN-GRAPH/1.14
ATMAN-STRUCTURE/1.15
ATMAN-SEARCH/1.16
```

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox and not a claim about physical multiverses, physical torsion, or real-world causality. Held-out validation and finite search governance reduce specific forms of structural overfitting but do not guarantee out-of-distribution performance. The v1.16 linear multiplicity threshold is governance regularization, not a formal multiple-testing significance guarantee. Production use additionally requires protected evaluation data, leakage controls, statistically justified multiple-comparison procedures where needed, temporal/external validation, protected keys, authenticated transport, rollback-resistant storage, causal-identification methodology where causal claims matter, and operational governance.

## Status

**v1.16.0 — Multiple-Comparison / Search-Budget Governance research core.**

The project now spans identity continuity, cryptographic lineage, branching/reconciliation, transition geometry, geometric A3/A4 coherence, finite verification capacity, durable verification debt, adaptive cost allocation, active information gain, evidence-bound Bayesian learning, competing hypotheses, correlated-evidence provenance, observer calibration, governed parameter revision, versioned statistical dependency DAGs, selection-only replay, deterministic held-out evaluation, graph-complexity penalties, finite cumulative held-out search budgets, pre-exposure reservations, multiplicity-aware improvement thresholds, search-adjusted model selection, use-time exposure/history/base freshness, append-only old/new graph history, process-separated execution, and quorum-governed trust evolution.

Next targets: protected/nested fresh holdout rotation, sequential-testing or alpha-spending research variants with explicit statistical assumptions, temporal/external structural validation, resolver correction receipts, rollback-resistant learning history, dynamic/cyclic dependency models, and causal-identification interfaces that remain explicitly separate from correlation-based structure learning.
