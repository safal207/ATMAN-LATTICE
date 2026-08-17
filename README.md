# ATMAN-LATTICE

**A Projective Spacetime Architecture for Identity, Authority, Verification, Active Learning, Evidence Geometry, and Coherence**

ATMAN-LATTICE is an exploratory research repository for modeling identity across state, space, time, lineage, branching, reconciliation, authorization, transition geometry, finite verification capacity, evidence-bound learning, competing hypotheses, and correlated-evidence provenance.

> What must remain invariant when representation changes, futures branch, paths become order-sensitive, verification capacity saturates, and new evidence changes a system's beliefs — so that identity, ancestry, uncertainty, dependence, evidence, cost, and permission remain provable rather than merely asserted?

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
```

# v1.11 — Multi-Hypothesis / Correlated Evidence Geometry

v1.11 extends the closed Bayesian loop from a binary `H / not-H` model to a categorical distribution over competing explanations and makes evidence dependence a first-class runtime contract.

```text
                 competing explanations
             H:A      H:B      H:C
               \       |       /
                \      |      /
             HypothesisDistribution
                       |
                 verification result
                       |
              precommitted semantics
                       |
              Evidence Dependency Gate
               /          |           \
       INDEPENDENT   CONDITIONAL    DUPLICATE
             |            |             |
       posterior      posterior      NO UPDATE
             \            /             |
              \          /       preserve receipt
               Distribution N+1
```

The seven process-level protocol planes are now:

```text
ATMAN-RUNTIME/1.1  privileged execution
ATMAN-TRUST/1.2    trust-root governance
ATMAN-VERIFY/1.7   durable verification / completion / finalization
ATMAN-ECONOMY/1.8  measured verification cost / finite budget
ATMAN-ACTIVE/1.9   expected information gain / next-check selection
ATMAN-BAYES/1.10   binary evidence interpretation / posterior update
ATMAN-MULTI/1.11   competing hypotheses / correlated-evidence provenance
```

## Competing hypotheses stay explicit

`HypothesisDistribution` binds a canonical probability vector:

```text
H:A = 0.40
H:B = 0.35
H:C = 0.25
sum = 1.00
```

A likelihood model must cover the **exact same hypothesis set**. Positive or negative evidence redistributes mass across the whole set:

```text
Posterior(H_i) proportional to Prior(H_i) * P(observation | H_i)
```

Alternative explanations are not silently deleted merely because one becomes more likely.

```text
PosteriorDistribution != Truth
```

It is a versioned belief state under explicit prior, likelihood, interpretation, and dependency assumptions.

## Evidence has provenance geometry

Before completion, `EVIDENCE_DEPENDENCY_KEEPER` must classify the evidence path as one of:

```text
INDEPENDENT
CONDITIONAL
DUPLICATE
```

The declaration binds:

```text
source_event_hash
  = underlying observed event

derivation_hash
  = this transformation / summary / projection of the source

dependency_group_ref
  = declared dependency context

parent_evidence_hashes
  = exact already accepted evidence this signal depends on
```

This makes a critical distinction load-bearing:

```text
DifferentDerivationHash != IndependentSource
```

A translation, summary, repost, dashboard projection, or second agent's retelling can have a different derivation while still originating from the same event.

## Echo-chamber protection

One source event cannot become several accepted independent Bayesian updates just because it appears through several paths:

```text
source S
  |-- summary A
  |-- summary B
  |-- copied alert
  `-- derived dashboard row

SameSourceEvent != FourEvidenceUnits
```

Accepted evidence is stored with a SQLite uniqueness constraint on `source_event_hash`.

Apply runs under `BEGIN IMMEDIATE`, so racing runtime processes cannot both commit the same source event as fresh accepted evidence inside the reference SQLite deployment boundary.

## Duplicate evidence is preserved, not counted again

`DUPLICATE` must reference exactly one accepted parent evidence receipt and preserve the same `source_event_hash`.

It produces a `DuplicateEvidenceReceipt` but no posterior transition:

```text
DuplicateEvidence -> PreserveHistory
DuplicateEvidence -/> PosteriorAdvance
```

So:

```text
DuplicateEvidence != NewKnowledge
```

## Conditional evidence uses conditional likelihood

If evidence B depends on accepted evidence A, v1.11 refuses to reuse an unconditional likelihood as if B were independent.

The model must bind the exact parent evidence set:

```text
Dependency.parents
        ==
ConditionalLikelihood.conditioning_evidence_hashes
```

This prevents naive multiplication such as:

```text
P(A | H) * P(B | H)
```

when the declared model actually requires something shaped like:

```text
P(A | H) * P(B | H, A)
```

## Multi-hypothesis information gain

v1.11 computes Shannon entropy over the complete distribution:

\[
H(P)=-\sum_i P(H_i)\log_2P(H_i)
\]

and expected information gain:

\[
EIG=H(Prior)-E[H(Posterior\mid outcome)].
\]

An uninformative test whose outcome distribution is identical under every hypothesis produces zero expected information gain.

```text
ExpectedInformationGain != EmpiricalCalibration
```

## Shared-distribution freshness

Several verification candidates may bind the same distribution. Accepted non-duplicate evidence advances:

```text
Distribution N -> Distribution N+1
```

and cohort likelihood models still bound to N are mechanically rebound to N+1 while preserving their likelihood values **and their conditioning parent set**.

```text
MultiLikelihoodRebase != MultiLikelihoodReEstimation
```

Changing actual likelihood values requires an explicit new model.

## Authority separation

v1.11 introduces distinct roles:

```text
MULTI_HYPOTHESIS_MODEL_KEEPER
EVIDENCE_DEPENDENCY_KEEPER
MULTI_EVIDENCE_RULE_KEEPER
MULTI_HYPOTHESIS_UPDATE_KEEPER
```

Therefore:

```text
ModelAuthority
  != DependencyAuthority
  != InterpretationAuthority
  != UpdateAuthority
```

The right to define competing explanations is not automatically the right to declare evidence independent.

## Epistemic boundary

A valid dependency receipt proves **which dependency assumption the runtime committed and used**. It does not prove that the real-world signals are truly independent, conditional, or duplicated.

```text
ValidDependencyReceipt != ProvenPhysicalCausality
ValidLikelihoodModel != EmpiricalCalibration
PosteriorDistribution != Truth
```

Protocol: [`docs/v1.11-multi-hypothesis-correlated-evidence.md`](docs/v1.11-multi-hypothesis-correlated-evidence.md)

Invariants: [`docs/v1.11-invariants.md`](docs/v1.11-invariants.md)

Machine-readable contracts:

- [`schemas/hypothesis-distribution.schema.json`](schemas/hypothesis-distribution.schema.json)
- [`schemas/multi-likelihood-model.schema.json`](schemas/multi-likelihood-model.schema.json)
- [`schemas/evidence-dependency.schema.json`](schemas/evidence-dependency.schema.json)
- [`schemas/multi-evidence-rule.schema.json`](schemas/multi-evidence-rule.schema.json)
- [`schemas/multi-evidence-receipt.schema.json`](schemas/multi-evidence-receipt.schema.json)
- [`schemas/multi-hypothesis-update.schema.json`](schemas/multi-hypothesis-update.schema.json)
- [`schemas/duplicate-evidence.schema.json`](schemas/duplicate-evidence.schema.json)
- [`schemas/multi-likelihood-rebase.schema.json`](schemas/multi-likelihood-rebase.schema.json)
- [`schemas/multi-expected-information-gain.schema.json`](schemas/multi-expected-information-gain.schema.json)

# Prior layers

## v1.10 — Bayesian Evidence Loop

```text
completion
 -> precommitted interpretation
 -> Bayesian posterior
 -> cohort propagation
 -> likelihood freshness rebind
 -> next active question
```

Key laws:

```text
Completion != EvidenceInterpretation
Interpretation != Posterior
Posterior != Truth
OneCompletion != InfiniteEvidence
```

Protocol: [`docs/v1.10-bayesian-evidence-loop.md`](docs/v1.10-bayesian-evidence-loop.md) · Invariants: [`docs/v1.10-invariants.md`](docs/v1.10-invariants.md)

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

Long-running agents can receive many apparently distinct observations that actually share one source, or evidence whose meaning changes after previous evidence is known. Naively treating every message as independent can make confidence rise far faster than evidence warrants.

ATMAN-LATTICE now keeps these questions separate:

- What competing explanations are still alive?
- What exact probability model is current?
- What source event produced this evidence?
- Is this a new source or merely a different derivation?
- Is this evidence independent, conditional, or duplicate under the declared model?
- If conditional, which exact prior evidence does its likelihood condition on?
- Was that dependency classification committed before the result was known?
- Has this source already affected the posterior?
- What posterior follows from the explicit assumptions?
- Who had authority to define the model, dependency, interpretation, and update?

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
```

This remains a **reference process/database and formal-model boundary**, not a hostile-host sandbox and not a claim about physical multiverses/torsion. Production use additionally requires protected keys, authenticated transport, rollback-resistant storage/backups, protected provenance/telemetry, empirically calibrated priors and likelihood/dependency models, database/file permissions, and operational governance.

## Status

**v1.11.0 — Multi-Hypothesis / Correlated Evidence Geometry research core.**

The project now spans identity continuity, cryptographic lineage, branching/restore/reconciliation, transition torsion and curvature, geometric A3/A4 coherence, finite verification capacity, durable verification debt, adaptive cost allocation, information-gain selection, evidence-bound Bayesian learning, competing hypothesis distributions, explicit source/derivation provenance, duplicate suppression, conditional evidence contexts, multi-hypothesis entropy, process-separated execution, and quorum-governed trust evolution.

Next targets: empirical calibration receipts for priors/likelihood/dependency assumptions, learned dependency graphs from protected provenance, rollback-resistant evidence history, automated active-selection-to-verification handoff, and concurrency stress tests across all learning planes.
