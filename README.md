# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Verification, Active Learning, Calibration, Governed Revision, Structural Evidence Graphs, Held-Out Validation, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, transition geometry, finite verification capacity, evidence-bound learning, competing hypotheses, correlated-evidence provenance, observer calibration, governed parameter correction, structural dependency-graph revision, and held-out validation of structural learning.

> What must remain invariant when representation changes, futures branch, evidence changes beliefs, the observer discovers that its model was wrong, proposes a new map of statistical dependencies, and then must prove that the new map generalizes beyond the data that suggested it?

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
```

# v1.15 — Held-Out Structural Validation / Complexity-Regularized Graph Selection

v1.14 gave the observer a governed way to propose and replay changes to its statistical dependency graph. v1.15 adds a stricter question:

> Did the structural hypothesis improve only the history used to discover it, or does it also improve a separate held-out partition after paying an explicit complexity cost?

```text
full dependency history
          |
 deterministic split
      /         \
selection      evaluation
   |               |
proposal            |
selection replay    |
   |                |
STRUCTURE_IMPROVED  |
      \             /
       held-out validation
              |
      raw Brier improvement
              +
      explicit edge penalty
              |
    HELDOUT_IMPROVED
              |
complete competing-candidate selection
              |
independent review
              |
use-time history/base/candidate-set freshness
              |
        Graph N -> N+1

Graph N, rejected candidates, and evaluation receipts remain preserved.
```

## Eleven process-level planes

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
```

## Selection data and evaluation data are different objects

A `StructuralValidationPolicy` fixes the held-out split policy and the structural complexity penalty.

For every persisted dependency-pair sample, v1.15 derives a deterministic bucket from the immutable `sample_hash`. Evaluation uses bucket `0`; all other buckets are selection.

```text
History = Selection union Evaluation
Selection intersection Evaluation = empty
```

The split has no client-supplied per-run random salt.

A `StructuralValidationCandidate` is built using **selection data only**. Its embedded v1.14 replay must bind exactly the selection sample hashes.

```text
SelectionData != EvaluationData
```

## Better replay is not better generalization

A candidate can pass selection replay and still fail held-out evaluation.

Statuses:

```text
INSUFFICIENT_HELDOUT
HELDOUT_IMPROVED
OVERFIT_SIGNAL
COMPLEXITY_REJECTED
```

`OVERFIT_SIGNAL` means:

```text
selection replay improved
held-out raw prediction did not improve
```

Therefore:

```text
BetterReplay != BetterGeneralization
```

The failed candidate remains preserved as evidence of a hypothesis that looked good in selection but did not generalize under the bound evaluation procedure.

## Complexity is charged explicitly

v1.15 scores both predictive fit and graph size:

```text
base_regularized_brier = base_mean_brier + edge_penalty_ppm * base_edge_count
proposed_regularized_brier = proposed_mean_brier + edge_penalty_ppm * proposed_edge_count
regularized_improvement = base_regularized_brier - proposed_regularized_brier
```

A new edge that improves raw held-out Brier but not enough to pay its configured complexity penalty becomes:

```text
COMPLEXITY_REJECTED
```

```text
MoreEdges != MoreKnowledge
```

The penalty is governance policy, not truth. It changes selection preference, not historical observations.

## Selection cannot hide competing validated candidates

`finalize_structural_selection` does not accept a client-curated candidate list.

The runtime automatically loads every held-out-validated candidate sharing the exact:

```text
subject identity
pair key
base graph hash
validation policy hash
dependency-history hash
```

Only `HELDOUT_IMPROVED` candidates are eligible. The winner is the largest positive regularized improvement with deterministic hash tie breaking.

If none passes:

```text
NO_ELIGIBLE_CANDIDATE
```

This is a statement about the current candidate set and evaluation policy, not about reality:

```text
NO_ELIGIBLE_CANDIDATE != NoRealDependency
```

## Selection has use-time freshness

A selection binds the complete candidate and validation set.

If a new held-out-validated competitor appears after selection:

```text
OldCandidateSet != CurrentSelectionAuthority
```

If new dependency-pair evidence appears:

```text
OldHistory != CurrentSelectionAuthority
```

If the base graph changed:

```text
OldBaseGraph != CurrentSelectionAuthority
```

The runtime recomputes the current deterministic selection before apply. A stale receipt cannot mutate the current graph.

## Independent authority

v1.15 adds:

```text
STRUCTURAL_VALIDATION_POLICY_KEEPER
STRUCTURAL_CANDIDATE_PROPOSER
HELDOUT_STRUCTURAL_VALIDATOR
STRUCTURAL_MODEL_SELECTOR
STRUCTURAL_SELECTION_REVIEWER
VALIDATED_STRUCTURAL_SELECTION_APPLIER
```

The held-out validator cannot be the candidate proposer. The reviewer cannot be the selector or the selected candidate proposer.

```text
Propose != Validate != Select != Review != Apply
```

## Held-out fit is still not causality

The underlying v1.14 graph relation remains exactly:

```text
STATISTICAL_CONDITIONING
```

A held-out improvement means the proposed statistical structure performed better under the bound evaluation and regularization policy.

It does not establish a physical mechanism or causal direction.

```text
HeldOutImprovement != CausalityProof
RegularizedSelection != Truth
```

## Runtime

Worker:

```bash
python -m model.structure_worker
```

Protocol operations:

```text
register_structural_validation_policy
register_structural_candidate
record_heldout_validation
finalize_structural_selection
record_structural_selection_review
apply_validated_structural_selection
get_structural_validation_state
```

Protocol: [`docs/v1.15-heldout-structural-validation.md`](docs/v1.15-heldout-structural-validation.md)

Invariants: [`docs/v1.15-invariants.md`](docs/v1.15-invariants.md)

Machine-readable contracts:

- [`schemas/structural-validation-policy.schema.json`](schemas/structural-validation-policy.schema.json)
- [`schemas/structural-validation-candidate.schema.json`](schemas/structural-validation-candidate.schema.json)
- [`schemas/heldout-structural-validation.schema.json`](schemas/heldout-structural-validation.schema.json)
- [`schemas/structural-selection.schema.json`](schemas/structural-selection.schema.json)
- [`schemas/structural-selection-review.schema.json`](schemas/structural-selection-review.schema.json)
- [`schemas/validated-dependency-graph-revision.schema.json`](schemas/validated-dependency-graph-revision.schema.json)

# Prior executable layers

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
```

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox and not a claim about physical multiverses, physical torsion, or real-world causality. Held-out validation reduces one form of structural overfitting but does not guarantee out-of-distribution performance. Production use additionally requires protected evaluation data, leakage controls, multiple-comparison correction when many structures are searched, temporal/external validation where appropriate, protected keys, authenticated transport, rollback-resistant storage, causal-identification methodology where causal claims matter, and operational governance.

## Status

**v1.15.0 — Held-Out Structural Validation / Complexity-Regularized Graph Selection research core.**

The project now spans identity continuity, cryptographic lineage, branching/reconciliation, transition geometry, geometric A3/A4 coherence, finite verification capacity, durable verification debt, adaptive cost allocation, active information gain, evidence-bound Bayesian learning, competing hypotheses, correlated-evidence provenance, observer calibration, governed parameter revision, versioned statistical dependency DAGs, competing structural proposals, selection-only replay, deterministic held-out evaluation, explicit graph-complexity penalties, complete-candidate-set selection, independent review, use-time evidence/candidate/base freshness, append-only old/new graph history, process-separated execution, and quorum-governed trust evolution.

Next targets: multiple-comparison / search-budget correction across large graph proposal spaces, nested or temporal structural validation, resolver correction receipts, rollback-resistant learning history, dynamic/cyclic dependency models, and causal-identification interfaces that remain explicitly separate from correlation-based structure learning.
