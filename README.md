# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Verification, Active Learning, Calibration, Governed Revision, Structural Evidence Graphs, Finite Search, Protected Confirmation, Replication Drift, Remediation, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, transition geometry, finite verification capacity, evidence-bound learning, competing hypotheses, correlated-evidence provenance, observer calibration, governed model revision, held-out validation, finite model search, protected confirmation, temporal/external replication, drift monitoring, and governed recovery.

> What must remain invariant when an observer can discover that a once-confirmed model has drifted — and must decide what to do without erasing the fact that the model was once supported?

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
governed parameter / graph revision
          ↓
held-out validation + complexity regularization
          ↓
finite multiple-comparison search budget
          ↓
protected provenance-fresh confirmation
          ↓
confirmed graph revision
          ↓
temporal / external replication
          ↓
PERSISTENT_DRIFT_SIGNAL
          ↓
GOVERNED REMEDIATION
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
SearchHoldout != ConfirmationHoldout
CONFIRMED != ProvenCausality
Confirmation != Truth
CONFIRMED != APPLIED
OneConfirmation != PermanentGeneralization
InternalFreshHoldout != ExternalReplication
Confirmed_t != Confirmed_t+1
DifferentSourceRef != ProvenIndependence
Replication != Retraining
DriftSignal != RollbackAuthority
PersistentDrift != AutomaticRollback
Drift != EvidenceForRollback
RemediationApproval != RevisionApproval
ForwardRollback != HistoryRewrite
RecoveryChoice != ErasureOfFormerValidity
```

# v1.19 — Drift-Governed Remediation / Safe Rollback

v1.18 deliberately stops at `PERSISTENT_DRIFT_SIGNAL`. v1.19 turns that signal into a governed decision surface rather than an automatic mutation.

```text
PERSISTENT_DRIFT_SIGNAL
        ↓
┌───────────────┬───────────────────┬────────────────────┬─────────────────────┬───────────────┐
│               │                   │                    │                     │
HOLD       COLLECT_MORE_DATA   PARAMETER_REVISION   STRUCTURAL_REVISION   SAFE_ROLLBACK
│               │                   │                    │                     │
└───────────────┴───────────────────┴────────────────────┴─────────────────────┴───────────────┘
                                        ↓
                              independent assessment
                                        ↓
                              complete-set selection
                                        ↓
                                independent review
                                        ↓
                                   fresh apply
```

## Persistent drift is not rollback authority

```text
PersistentDriftSignal != RemediationDecision
PersistentDrift != AutomaticRollback
```

Every remediation proposal binds the exact current:

```text
replication target
persistent-drift snapshot
latest replication evaluation
confirmed revision
current graph hash + generation
pre-confirmation graph hash + generation
```

New replication evidence stales the old remediation snapshot.

## Five explicit recovery paths

### HOLD

Preserve the current model while recording a deliberate governed non-mutation.

### COLLECT_MORE_DATA

Keep the model unchanged and ask the replication plane for more evidence.

### PARAMETER_REVISION

Emit `DOWNSTREAM_GOVERNANCE_REQUIRED` and route to:

```text
ATMAN-REVISION/1.13
```

### STRUCTURAL_REVISION

Emit `DOWNSTREAM_GOVERNANCE_REQUIRED` and route to:

```text
ATMAN-GRAPH/1.14
```

### SAFE_ROLLBACK

Available only after a separate rollback assessment. In the strict reference policy the latest replication comparison must show:

```text
regularized_improvement(current confirmed graph over pre-confirmation base) <= 0
```

Therefore:

```text
Drift != EvidenceForRollback
PerformanceDrift != RollbackJustification
```

A model may have degraded relative to its old performance while still outperforming its base graph; that does not justify rollback.

## Rollback moves forward

v1.19 does not rewind history:

```text
Graph N-1
   ↓ v1.17 confirmed revision
Graph N
   ↓ later persistent drift
Graph N+1  ← topology(Graph N-1) + new remediation evidence
```

`Graph N+1` is a new state, not a resurrection of `Graph N-1`.

```text
ForwardRollback != HistoryRewrite
RecoveryChoice != ErasureOfFormerValidity
```

The execution receipt preserves both the former confirmed graph and the rollback-source graph.

## Competing recovery choices are preserved

Multiple remediation proposals may coexist for one exact snapshot. Before selection, the runtime requires one independent assessment for every current proposal. The selection receipt binds the complete current proposal/assessment set.

If another proposal appears after selection, or v1.18 receives another replication epoch, the old recovery choice becomes stale.

```text
OldRecoveryChoice != CurrentRecoveryAuthority
```

One exact persistent-drift snapshot gets at most one remediation execution.

## Existing governance cannot be bypassed

Choosing parameter or structural revision does not directly rewrite a model.

```text
RemediationApproval != ParameterRevisionApproval
RemediationApproval != StructuralRevisionApproval
```

Those paths must still satisfy the existing v1.13 or v1.14 proposal/replay/review/apply contracts.

## Authority separation

v1.19 adds:

```text
REMEDIATION_POLICY_KEEPER
REMEDIATION_PROPOSER
REMEDIATION_ASSESSOR
REMEDIATION_SELECTOR
REMEDIATION_REVIEWER
REMEDIATION_APPLIER
```

Core separations:

```text
proposer != assessor
latest replication evaluator != assessor
selected proposer / assessor != selector
proposer / assessor / selector != reviewer
proposer / assessor / selector / reviewer != applier
```

## Runtime

Worker:

```bash
python -m model.remediation_worker
```

Protocol:

```text
ATMAN-REMEDIATE/1.19
```

Operations:

```text
register_remediation_policy
register_remediation_proposal
assess_remediation_proposal
select_remediation
record_remediation_review
apply_remediation
get_remediation_state
```

Protocol document: [`docs/v1.19-drift-governed-remediation.md`](docs/v1.19-drift-governed-remediation.md)

Invariants: [`docs/v1.19-invariants.md`](docs/v1.19-invariants.md)

Machine-readable contracts:

- [`schemas/remediation-policy.schema.json`](schemas/remediation-policy.schema.json)
- [`schemas/drift-remediation-proposal.schema.json`](schemas/drift-remediation-proposal.schema.json)
- [`schemas/remediation-assessment.schema.json`](schemas/remediation-assessment.schema.json)
- [`schemas/remediation-selection.schema.json`](schemas/remediation-selection.schema.json)
- [`schemas/remediation-review.schema.json`](schemas/remediation-review.schema.json)
- [`schemas/remediation-execution.schema.json`](schemas/remediation-execution.schema.json)

## Epistemic boundary

A v1.19 decision is an engineering/governance response to bound replication evidence. It does not discover the real-world cause of drift or prove causality.

```text
DriftKind != DriftCause
Remediation != CausalityProof
```

A rolled-back graph must earn future confidence again through the appropriate verification, confirmation, and replication lifecycle.

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
ATMAN-REPLICATE/1.18    temporal/external replication + drift monitoring
ATMAN-REMEDIATE/1.19    persistent-drift recovery governance + forward rollback
```

## Backward compatibility

v1.19 does not change the v1.18 wire contract. `ATMAN-REPLICATE/1.18` remains a monitoring plane with no graph-mutation authority. v1.19 consumes persisted v1.18 snapshots and adds a separate recovery protocol.

A strict deployment profile should keep legacy direct structural mutation endpoints restricted and require the appropriate downstream governance lane for any model revision.

# Historical layers

- **v1.18** — temporal/external replication and confirmation drift. [`protocol`](docs/v1.18-temporal-external-replication.md) · [`invariants`](docs/v1.18-invariants.md)
- **v1.17** — protected one-shot provenance-fresh confirmation. [`protocol`](docs/v1.17-protected-fresh-holdout.md) · [`invariants`](docs/v1.17-invariants.md)
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
python -m model.replication_worker
python -m model.remediation_worker
```

## Status

**v1.19.0 — Drift-Governed Remediation / Safe Rollback research core.**

The project now preserves a traceable chain from identity and authority through verification, Bayesian learning, calibration, structural search, protected confirmation, temporal/external replication, persistent drift detection, competing remediation choices, and forward-only recovery with immutable evidence history.

Production work still requires protected keys, authenticated transport, rollback-resistant storage, signed/external dataset provenance where externality claims matter, leakage detection, formal statistical testing where statistical error guarantees are claimed, causal-identification/transportability methods where causal claims matter, operational incident governance, rollback blast-radius controls, and deployment-specific safeguards around any real model or system mutation.
