# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Verification, Active Learning, Calibration, Governed Revision, Structural Evidence Graphs, Finite Search, Protected Confirmation, Replication Drift, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, transition geometry, finite verification capacity, evidence-bound learning, competing hypotheses, correlated-evidence provenance, observer calibration, governed parameter and structural revision, held-out validation, finite model search, protected one-shot confirmation, and temporal/external replication monitoring.

> What must remain invariant when an observer can search, confirm, deploy a model, and then discover that time or environment may have changed underneath a previously valid conclusion?

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
protected fresh confirmation
          ↓
confirmed graph revision
          ↓
TEMPORAL / EXTERNAL REPLICATION
          ↓
replication review + drift series
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
OneConfirmation != PermanentGeneralization
InternalFreshHoldout != ExternalReplication
Confirmed_t != Confirmed_t+1
DifferentSourceRef != ProvenIndependence
Replication != Retraining
DriftSignal != RollbackAuthority
REPLICATED != UniversalValidity
```

# v1.18 — Temporal / External Replication & Confirmation Drift

v1.18 adds a monitoring plane **after** a graph has passed v1.17 protected confirmation and has been applied.

```text
v1.17 CONFIRMED graph revision
        ↓
ReplicationTargetReceipt
        ↓
   ┌────┴───────────────┐
   │                    │
TEMPORAL             EXTERNAL
   │                    │
   └────────┬───────────┘
            ↓
   TEMPORAL_EXTERNAL
            ↓
fresh replication batch
            ↓
frozen-model scoring
            ↓
REPLICATED / DRIFT_SIGNAL
            ↓
independent review
            ↓
replication series
            ↓
PERSISTENT_DRIFT_SIGNAL
```

## One confirmation is not permanent generalization

v1.17 answers:

> Did this selected structure generalize to one protected provenance-fresh final confirmation batch?

v1.18 asks:

> Does the **same frozen confirmed structure** continue to generalize later, elsewhere, or both?

```text
OneConfirmation != PermanentGeneralization
Confirmed_t != Confirmed_t+1
```

A replication target binds the exact historical baseline:

```text
v1.17 confirmed revision hash
candidate hash
confirmed graph hash + generation
confirmation evaluation + review
confirmation batch + source
baseline confirmed-model Brier score
baseline regularized structural improvement
```

The baseline is immutable.

## Three replication modes

```text
TEMPORAL
EXTERNAL
TEMPORAL_EXTERNAL
```

### Temporal

Temporal replication enforces:

```text
collected_from - confirmation_evaluated_at >= min_temporal_gap
```

and later replication generations form a strict lineage with non-overlapping collection windows:

```text
R0 -> R1 -> R2 -> ...
```

### External

`EXTERNAL` and `TEMPORAL_EXTERNAL` require a `source_ref` different from the source used by the original v1.17 confirmation batch.

That prevents an internal rerun from being labeled external.

It does **not** prove that the sources are genuinely independent in every scientific or institutional sense:

```text
DifferentSourceRef != ProvenIndependence
ExternalReplication != OntologicalIndependence
```

## Freshness remains provenance-based

Replication evidence must be disjoint from:

```text
search / discovery history
v1.17 confirmation batches
prior replication batches
```

using exact:

```text
sample_hash
resolution_hash
left_evidence_hash
right_evidence_hash
```

Therefore:

```text
NewSampleHash != FreshProvenance
NewDerivation != NewEvidenceSource
ReusedResolution != Replication
```

## Replication does not retrain

The selected structure is evaluated using the original frozen candidate selection/training samples.

Replication data is **score-only**.

```text
Replication != Retraining
ReplicationData != TrainingData
```

This keeps drift observable instead of immediately fitting it away.

## Drift has two dimensions

### Structural drift

The confirmed graph no longer beats its original base graph by more than the configured threshold.

### Performance drift

The confirmed model's Brier score degrades beyond the allowed amount relative to its original v1.17 confirmation baseline.

`drift_kind` is explicit:

```text
NONE
STRUCTURAL
PERFORMANCE
BOTH
```

and evaluation status is:

```text
INSUFFICIENT_REPLICATION
REPLICATED
DRIFT_SIGNAL
```

A drift signal is monitoring evidence only:

```text
DriftSignal != ModelFalsehood
DriftSignal != DriftCause
DriftSignal != RollbackAuthority
```

No v1.18 role can mutate the dependency graph.

## Persistent drift

Acknowledged replication epochs can be summarized into `ReplicationSeriesSnapshot`.

When:

```text
consecutive_drift_count >= persistent_drift_epochs
```

the snapshot emits:

```text
PERSISTENT_DRIFT_SIGNAL
```

This remains a governance input rather than an automatic rollback.

## Current-model binding

The runtime evaluates a replication target only while its `confirmed_graph_hash` still matches the current graph.

After a newer governed graph revision, the old target remains historical evidence but no longer describes current model status.

```text
HistoricalReplicationTarget != CurrentModelStatus
OldConfirmedGraph != CurrentReplicationAuthority
```

## Authority separation

v1.18 adds:

```text
REPLICATION_POLICY_KEEPER
REPLICATION_TARGET_KEEPER
REPLICATION_BATCH_KEEPER
REPLICATION_EVALUATOR
REPLICATION_REVIEWER
REPLICATION_MONITOR_KEEPER
```

Important separations include:

```text
replication batch keeper != candidate proposer
replication batch keeper != original confirmation evaluator
replication evaluator != batch keeper / candidate proposer / original confirmation evaluator
replication reviewer != batch keeper / evaluator
monitoring authority != mutation authority
```

## Runtime

Worker:

```bash
python -m model.replication_worker
```

Protocol:

```text
ATMAN-REPLICATE/1.18
```

Operations:

```text
register_replication_policy
register_replication_target
seal_replication_batch
evaluate_replication
record_replication_review
finalize_replication_snapshot
get_replication_state
```

Protocol document: [`docs/v1.18-temporal-external-replication.md`](docs/v1.18-temporal-external-replication.md)

Invariants: [`docs/v1.18-invariants.md`](docs/v1.18-invariants.md)

Machine-readable contracts:

- [`schemas/replication-policy.schema.json`](schemas/replication-policy.schema.json)
- [`schemas/replication-target.schema.json`](schemas/replication-target.schema.json)
- [`schemas/replication-batch.schema.json`](schemas/replication-batch.schema.json)
- [`schemas/replication-evaluation.schema.json`](schemas/replication-evaluation.schema.json)
- [`schemas/replication-review.schema.json`](schemas/replication-review.schema.json)
- [`schemas/replication-series-snapshot.schema.json`](schemas/replication-series-snapshot.schema.json)

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
```

## Backward compatibility

v1.18 does not change the v1.17 wire contract. `ATMAN-CONFIRM/1.17` remains the strongest structural mutation path; `ATMAN-REPLICATE/1.18` is deliberately read/append-only with respect to graph state.

A strict deployment profile should:

1. route structural mutation through `ATMAN-CONFIRM/1.17`;
2. create a new v1.18 target for each newly confirmed current graph;
3. use replication signals as inputs to a separate future governance/remediation workflow rather than silently rolling back state.

# Historical layers

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
```

## Status

**v1.18.0 — Temporal / External Replication & Confirmation Drift research core.**

The project now preserves a traceable chain from identity and authority through verification, Bayesian learning, calibration, structural search, protected confirmation, and post-confirmation temporal/external replication with explicit drift history.

Production work still requires protected keys, authenticated transport, rollback-resistant storage, signed/external dataset provenance where externality claims matter, leakage detection, robust source-independence procedures, formal statistical testing where statistical error guarantees are claimed, causal-identification/transportability methodology where causal claims matter, and explicit operational governance for any remediation or rollback action.