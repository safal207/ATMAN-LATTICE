# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Verification, Active Learning, Evidence Geometry, Calibration, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, transition geometry, finite verification capacity, evidence-bound learning, competing hypotheses, correlated-evidence provenance, and historical observer calibration.

> What must remain invariant when representation changes, futures branch, paths become order-sensitive, verification capacity saturates, evidence changes beliefs, and later outcomes reveal that the observer itself may have been systematically wrong?

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
Completion != EvidenceInterpretation
Interpretation != Posterior
Posterior != Truth
OneCompletion != InfiniteEvidence
LikelihoodRebase != LikelihoodReEstimation
PosteriorDistribution != Truth
SameSourceEvent != IndependentEvidenceTwice
DifferentDerivation != IndependentSource
DuplicateEvidence != NewKnowledge
ConditionalEvidence != IndependentEvidence
ValidDependencyReceipt != ProvenRealWorldIndependence
CalibrationTarget != PosthocModel
Resolution != OntologicalTruth
Confidence != Calibration
NoDependencySignal != ProvenIndependence
DependencySignal != ProvenCausality
CalibrationSignal != RewriteAuthority
```

# v1.12 — Calibration / Dependency Learning

v1.12 audits the observer itself.

The eight process-level planes are now:

```text
ATMAN-RUNTIME/1.1       privileged execution
ATMAN-TRUST/1.2         trust-root governance
ATMAN-VERIFY/1.7        durable verification / completion / finalization
ATMAN-ECONOMY/1.8       measured verification cost / finite budget
ATMAN-ACTIVE/1.9        expected information gain / next-check selection
ATMAN-BAYES/1.10        binary evidence interpretation / posterior update
ATMAN-MULTI/1.11        competing hypotheses / correlated-evidence provenance
ATMAN-CALIBRATION/1.12  historical forecast, likelihood, and dependency audit
```

## Freeze assumptions before the outcome

Calibration is meaningless if the model can be changed after the answer is known.

Before verification completion, `CalibrationTargetReceipt` freezes the exact:

```text
distribution hash + probability vector
likelihood model hash + likelihood vector
dependency hash + mode + parent evidence
source / derivation provenance
candidate / identity
calibration family
commit time
```

So:

```text
PosthocModel != HistoricalForecast
Calibration requires frozen pre-outcome assumptions.
```

The runtime rejects target registration after the verification result or after a case has already been resolved.

## Resolution is separate from truth

`ResolvedOutcomeReceipt` binds a distribution/case to a resolved hypothesis and to a provenance digest for the resolution source.

```text
Resolution != OntologicalTruth
```

The resolution is the current authoritative calibration label. The reference model does not claim the resolver is infallible or that the hypothesis set contains every possible real-world explanation.

A resolution is immutable once registered in v1.12; correction requires a later explicit protocol rather than silent history replacement.

## Forecast calibration with Brier score

For categorical probabilities:

\[
Brier=\sum_i(p_i-y_i)^2
\]

where `y_i=1` for the resolved hypothesis and `0` otherwise.

The implementation stores deterministic integer parts-per-million scores.

A binary intuition:

```text
A=100%, A resolves -> 0 ppm
A=50%,  A resolves -> 500000 ppm
A=0%,   A resolves -> 2000000 ppm
```

Therefore:

```text
Confidence != Calibration
```

A confident miss is worse than an uncertain miss.

## Likelihood calibration

A v1.11 likelihood model claims:

```text
P(positive evidence | H_i)
```

After the case resolves to `H_k`, v1.12 compares the frozen `P(+|H_k)` with the evidence outcome actually observed.

Conclusive positive/negative evidence receives a binary Brier score.

`INCONCLUSIVE` is preserved but not forced into a binary calibration label:

```text
INCONCLUSIVE != POSITIVE
INCONCLUSIVE != NEGATIVE
```

## Family-level observer audit

Stable `calibration_family_ref` values allow repeated historical observations to be aggregated into:

```text
forecast count
mean categorical Brier
likelihood scored count
mean likelihood Brier
mean predicted positive rate
observed positive rate
marginal calibration gap
```

The reference diagnostic status is:

```text
INSUFFICIENT_SAMPLES
NO_MARGINAL_MISCALIBRATION_SIGNAL
MISCALIBRATION_SIGNAL
```

Minimum samples and alert thresholds are explicit policy inputs.

```text
DiagnosticPolicy != EvidenceHistory
```

Changing a threshold may change the label, but it does not change the underlying historical receipts.

## Dependency learning

v1.11 records dependency assumptions before evidence is known:

```text
INDEPENDENT
CONDITIONAL
DUPLICATE
```

v1.12 can accumulate repeated resolved pair samples for the same signal families.

For binary signals `L` and `R`, the reference statistic compares:

```text
observed P(L+ and R+)
```

with the empirical joint rate expected under independence:

```text
P(L+) * P(R+)
```

The signed difference is stored as `independence_gap_bps`.

For a declared independent pair:

```text
large historical gap -> INDEPENDENCE_CHALLENGED
small historical gap -> NO_DEPENDENCY_SIGNAL
```

For a declared conditional pair:

```text
large historical gap -> CONDITIONAL_DEPENDENCY_SUPPORTED
small historical gap -> CONDITIONAL_DEPENDENCY_NOT_OBSERVED
```

The names are deliberately cautious:

```text
NoDependencySignal != ProvenIndependence
DependencySignal != ProvenCausality
```

## Why duplicate evidence is different

`DUPLICATE` is already structurally proven at the provenance level in v1.11 by preserving the same source-event lineage and granting zero new posterior updates.

It is therefore not promoted into an ordinary statistical dependency sample in v1.12.

```text
DuplicateEvidence != NewKnowledge
```

## Calibration authority is separated

v1.12 adds:

```text
CALIBRATION_TARGET_KEEPER
CALIBRATION_RESOLVER
CALIBRATION_RECORDER
```

and preserves:

```text
FreezeModel != ResolveOutcome
ResolveOutcome != ScoreModel
ScoreModel != RewriteModel
```

The calibration plane is diagnostic and append-only. It cannot directly mutate priors, likelihoods, dependency declarations, A4 decisions, execution permissions, or trust roots.

```text
CalibrationSignal != RewriteAuthority
```

## Durable calibration history

The reference SQLite plane stores:

```text
calibration targets
resolved outcomes
forecast calibration receipts
likelihood calibration receipts
dependency pair samples
```

Targets are immutable after precommit. Resolutions are immutable in v1.12. Calibration observations are unique by frozen target/evidence binding, and dependency pair samples are unique by `(pair_key, resolution_hash)`.

Protocol: [`docs/v1.12-calibration-dependency-learning.md`](docs/v1.12-calibration-dependency-learning.md)

Invariants: [`docs/v1.12-invariants.md`](docs/v1.12-invariants.md)

Machine-readable contracts:

- [`schemas/calibration-target.schema.json`](schemas/calibration-target.schema.json)
- [`schemas/resolved-outcome.schema.json`](schemas/resolved-outcome.schema.json)
- [`schemas/forecast-calibration.schema.json`](schemas/forecast-calibration.schema.json)
- [`schemas/likelihood-calibration.schema.json`](schemas/likelihood-calibration.schema.json)
- [`schemas/dependency-pair-sample.schema.json`](schemas/dependency-pair-sample.schema.json)
- [`schemas/dependency-calibration-snapshot.schema.json`](schemas/dependency-calibration-snapshot.schema.json)
- [`schemas/calibration-family-snapshot.schema.json`](schemas/calibration-family-snapshot.schema.json)

# Prior layers

## v1.11 — Multi-Hypothesis / Correlated Evidence Geometry

v1.11 extends the binary Bayesian loop to competing explanations and makes evidence dependence first-class.

```text
             H:A      H:B      H:C
               \       |       /
             HypothesisDistribution
                       |
              Evidence Dependency Gate
               /          |           \
       INDEPENDENT   CONDITIONAL    DUPLICATE
             |            |             |
       posterior      posterior      NO UPDATE
```

Key laws:

```text
PosteriorDistribution != Truth
SameSourceEvent != IndependentEvidenceTwice
DifferentDerivation != IndependentSource
ConditionalEvidence != IndependentEvidence
DuplicateEvidence != NewKnowledge
```

Protocol: [`docs/v1.11-multi-hypothesis-correlated-evidence.md`](docs/v1.11-multi-hypothesis-correlated-evidence.md) · Invariants: [`docs/v1.11-invariants.md`](docs/v1.11-invariants.md)

## v1.10 — Bayesian Evidence Loop

```text
completion
 -> precommitted interpretation
 -> Bayesian posterior
 -> cohort propagation
 -> likelihood freshness rebind
 -> next active question
```

```text
Completion != EvidenceInterpretation
Interpretation != Posterior
Posterior != Truth
OneCompletion != InfiniteEvidence
```

## v1.9 — Information Gain / Active Verification

Explicit uncertainty/likelihood models rank the next useful verification question under finite cost.

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

Torsion/curvature evidence enters A3/A4 under explicit `PASS < HOLD < FAIL` policy semantics.

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

## Why this matters for AI systems

Long-running agents do not only need to reason under uncertainty. They also need to discover when their own uncertainty model is bad.

ATMAN-LATTICE now keeps these questions separate:

- What competing explanations are alive?
- What source produced each observation?
- Was evidence independent, conditional, or duplicate under the declared model?
- Which exact prior and likelihood existed before the result was known?
- What later outcome was used as the calibration reference?
- Was the model historically overconfident or underconfident?
- Do allegedly independent signal families repeatedly co-move more than the independence model predicts?
- Is there enough data to say anything at all?
- Does a diagnostic signal justify review without granting automatic rewrite authority?
- Who had authority to freeze, resolve, score, verify, execute, or govern?

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
```

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox and not a claim about physical multiverses/torsion. Production use additionally requires protected keys, authenticated transport, rollback-resistant storage/backups, protected provenance and resolution sources, empirically justified hypothesis sets, calibration monitoring, database/file permissions, and operational governance.

## Status

**v1.12.0 — Calibration / Dependency Learning research core.**

The project now spans identity continuity, cryptographic lineage, branching/restore/reconciliation, transition torsion and curvature, geometric A3/A4 coherence, finite verification capacity, durable verification debt, adaptive cost allocation, information-gain selection, evidence-bound Bayesian learning, competing hypothesis distributions, correlated-evidence provenance, duplicate suppression, conditional evidence contexts, frozen pre-outcome calibration targets, immutable resolution receipts, deterministic Brier scoring, historical likelihood audit, empirical dependency challenge signals, process-separated execution, and quorum-governed trust evolution.

Next targets: calibration-driven model revision proposals with explicit human/governance approval, reliability diagrams / subgroup calibration, protected resolver provenance, rollback-resistant calibration history, learned dependency-graph proposals, and concurrency stress tests across all learning planes.
