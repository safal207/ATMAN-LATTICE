# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Verification, Active Learning, Calibration, Governed Revision, Structural Evidence Graphs, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, transition geometry, finite verification capacity, evidence-bound learning, competing hypotheses, correlated-evidence provenance, observer calibration, governed parameter correction, and governed revision of the observer's own statistical dependency graph.

> What must remain invariant when representation changes, futures branch, paths become order-sensitive, evidence changes beliefs, later outcomes reveal observer error, and the observer then proposes to change both its parameters and its map of statistical dependencies?

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
CorrelationChallenge != CausalityProof
GraphEdge != PhysicalCause
StructuralProposal != StructuralMutation
OldStructuralReplay != CurrentStructuralRevisionAuthority
LearningStructure != ErasingPriorStructure
```

# v1.14 — Structural Dependency-Graph Revision

v1.14 moves from changing likelihood numbers to changing the **structure of the observer's statistical dependency model** while keeping causality claims outside what the protocol can prove.

```text
historical dependency calibration
              |
     INDEPENDENCE_CHALLENGED
              |
              v
 competing structural proposals
        /             \
      L -> R         R -> L
        \             /
         \           /
      leave-one-out replay
              |
      independent review
              |
       APPROVE/HOLD/REJECT
              |
        use-time replay
        + graph freshness
              |
              v
        Graph N -> N+1

Graph N remains preserved
```

The ten process-level planes are now:

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
```

## Statistical conditioning is not causality

A v1.14 dependency edge has exactly one relation:

```text
STATISTICAL_CONDITIONING
```

There is deliberately no `CAUSES` relation in the reference protocol.

```text
GraphEdge != PhysicalCause
ValidGraphReceipt != ProvenPhysicalCausality
```

A graph receipt proves what statistical structure the system committed and how that structure changed. It does not prove a physical mechanism.

## Direction is not inferred from correlation

When v1.12 reports:

```text
INDEPENDENCE_CHALLENGED
```

v1.14 does not silently choose a direction.

The same historical challenge may generate competing proposals:

```text
L -> R
R -> L
```

Both bind the same exact base graph generation and calibration challenge.

```text
CorrelationChallenge != DirectionProof
CorrelationChallenge != CausalityProof
```

## Graph state is versioned and acyclic

`DependencyGraphState` binds:

```text
graph_ref
subject_identity_ref
generation
canonical edge set
evidence_state_hash
graph_hash
```

The reference graph is a DAG. A proposal that would create a cycle is rejected before issuance.

```text
A -> B -> C
C -> A   # rejected in v1.14
```

This is a constraint of this reference model, not a claim that feedback systems cannot exist. Cyclic/dynamic graphical models require a later explicit model.

## Structural replay uses leave-one-out history

A structural proposal is not approved because a correlation statistic looks large.

It must replay on the persisted `DependencyPairSample` history.

For every historical case `i`:

```text
remove i from the training counts
score base structure on i
score proposed structure on i
```

An independent structure predicts from the remaining marginal child-positive rate.

A conditional structure predicts from the remaining child-positive rate among observations with the same parent outcome.

Both are scored with deterministic Brier score.

Replay outcomes:

```text
INSUFFICIENT_REPLAY
STRUCTURE_IMPROVED
NO_STRUCTURE_IMPROVEMENT
```

Only `STRUCTURE_IMPROVED` can be approved.

```text
ReplayImprovement != CausalityProof
HistoricalStructuralFit != FutureTruth
```

## Review and apply remain separate

The structural revision chain is:

```text
DependencyCalibrationSnapshot
 -> StructuralGraphRevisionProposal
 -> StructuralGraphReplayReceipt
 -> StructuralGraphReviewReceipt
 -> DependencyGraphRevisionReceipt
```

The reviewer must be distinct from the proposer.

```text
Proposal != Replay != Review != Apply
APPROVE != Mutation
```

## Apply revalidates current evidence

At apply time, the runtime recomputes structural replay from current dependency-pair history.

If a new resolved sample appeared after review, the old replay is rejected:

```text
OldStructuralReplay != CurrentStructuralRevisionAuthority
```

The current graph hash and generation must also still match the proposal base.

This gives competing proposals useful semantics: several alternatives may coexist against Graph N, but after one becomes Graph N+1 the others remain preserved and become stale rather than silently applying to a different world.

## Learning structure does not erase the old map

Successful apply stores complete old and new graph JSON in append-only history:

```text
Graph N
  |
proposal -> replay -> review
  |
Graph N+1
```

Both generations remain inspectable.

```text
LearningStructure != ErasingPriorStructure
```

Historical v1.11 evidence dependency receipts are not rewritten. Event-level source hashes, derivations, dependency declarations, and parent evidence hashes remain historical facts.

## Authority separation

v1.14 adds:

```text
DEPENDENCY_GRAPH_BOOTSTRAP_KEEPER
STRUCTURAL_GRAPH_REVISION_PROPOSER
STRUCTURAL_GRAPH_REPLAY_KEEPER
STRUCTURAL_GRAPH_REVISION_REVIEWER
STRUCTURAL_GRAPH_REVISION_APPLIER
```

The bootstrap permission initializes generation 0 only and cannot overwrite an existing graph.

```text
Bootstrap != OngoingRewriteAuthority
Propose != Replay != Review != Apply
```

## Runtime

Worker:

```bash
python -m model.graph_worker
```

Protocol operations:

```text
register_dependency_graph
register_graph_revision_proposal
record_graph_revision_replay
record_graph_revision_review
apply_graph_revision
get_graph_revision_state
```

Protocol: [`docs/v1.14-structural-dependency-graph-revision.md`](docs/v1.14-structural-dependency-graph-revision.md)

Invariants: [`docs/v1.14-invariants.md`](docs/v1.14-invariants.md)

Machine-readable contracts:

- [`schemas/dependency-graph-state.schema.json`](schemas/dependency-graph-state.schema.json)
- [`schemas/structural-graph-revision-proposal.schema.json`](schemas/structural-graph-revision-proposal.schema.json)
- [`schemas/structural-graph-replay.schema.json`](schemas/structural-graph-replay.schema.json)
- [`schemas/structural-graph-review.schema.json`](schemas/structural-graph-review.schema.json)
- [`schemas/dependency-graph-revision.schema.json`](schemas/dependency-graph-revision.schema.json)

# Prior executable layers

## v1.13 — Calibration-Governed Model Revision

Historical model error can produce a parameter revision proposal, but mutation requires counterfactual replay, independent review, and use-time replay freshness.

```text
CalibrationSignal != RewriteAuthority
Proposal != Mutation
ReplayImprovement != Approval
Review != Apply
OldReplay != CurrentRevisionAuthority
LearningFromError != ErasingError
HistoricalFit != FutureTruth
```

Protocol: [`docs/v1.13-calibration-governed-model-revision.md`](docs/v1.13-calibration-governed-model-revision.md) · Invariants: [`docs/v1.13-invariants.md`](docs/v1.13-invariants.md)

## v1.12 — Calibration / Dependency Learning

```text
PosthocModel != HistoricalForecast
Confidence != Calibration
NoDependencySignal != ProvenIndependence
DependencySignal != ProvenCausality
CalibrationSignal != RewriteAuthority
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
python -m model.graph_worker
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
```

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox and not a claim about physical multiverses, physical torsion, or real-world causality. Structural replay is historical predictive evaluation, not causal identification and not proof of out-of-distribution performance. Production use additionally requires protected keys, authenticated transport, rollback-resistant storage, protected resolution provenance, held-out evaluation, drift monitoring, causal-identification methodology where causal claims matter, database/file permissions, and operational governance.

## Status

**v1.14.0 — Structural Dependency-Graph Revision research core.**

The project now spans identity continuity, cryptographic lineage, branching/reconciliation, transition torsion and curvature, geometric A3/A4 coherence, finite verification capacity, durable verification debt, adaptive cost allocation, active information gain, evidence-bound Bayesian learning, multi-hypothesis distributions, correlated-evidence provenance, observer calibration, governed parameter revision, versioned statistical dependency DAGs, competing orientation proposals, leave-one-out structural replay, independent review, use-time structural freshness, append-only old/new graph history, process-separated execution, and quorum-governed trust evolution.

Next targets: held-out structural evaluation partitions, graph-complexity penalties, resolver correction receipts, rollback-resistant learning history, dynamic/cyclic dependency models, causal-identification interfaces that remain explicitly separate from correlation-based structure learning, and concurrency stress across calibration/revision/graph races.
