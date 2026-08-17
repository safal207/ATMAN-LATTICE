from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Literal

from model.bayesian_evidence import CompletionDecision, EvidenceOutcome

DependencyMode = Literal["INDEPENDENT", "CONDITIONAL", "DUPLICATE"]


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _entropy_bits(probabilities: tuple[int, ...]) -> float:
    result = 0.0
    for value in probabilities:
        if value <= 0:
            continue
        probability = value / 10_000.0
        result -= probability * math.log2(probability)
    return result


def _normalize_weights(weights: tuple[tuple[str, int], ...]) -> tuple[tuple[str, int], ...]:
    total = sum(weight for _, weight in weights)
    if total <= 0:
        raise ValueError("impossible observation under multi-hypothesis likelihood model")
    floors: dict[str, int] = {}
    remainders: list[tuple[int, str]] = []
    for hypothesis_ref, weight in weights:
        scaled = weight * 10_000
        floors[hypothesis_ref] = scaled // total
        remainders.append((scaled % total, hypothesis_ref))
    remaining = 10_000 - sum(floors.values())
    for _, hypothesis_ref in sorted(remainders, key=lambda item: (-item[0], item[1]))[:remaining]:
        floors[hypothesis_ref] += 1
    return tuple(sorted(floors.items()))


@dataclass(frozen=True)
class HypothesisDistribution:
    distribution_ref: str
    subject_identity_ref: str
    probability_bps: tuple[tuple[str, int], ...]
    evidence_state_hash: str
    generation: int
    distribution_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/hypothesis-distribution/v1.11",
            "distribution_ref": self.distribution_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "probability_bps": [[key, value] for key, value in self.probability_bps],
            "evidence_state_hash": self.evidence_state_hash,
            "generation": self.generation,
        }

    def validate(self) -> None:
        if not self.distribution_ref or not self.subject_identity_ref:
            raise ValueError("distribution_ref and subject_identity_ref are required")
        if self.generation < 0:
            raise ValueError("generation must be >= 0")
        if len(self.probability_bps) < 2:
            raise ValueError("multi-hypothesis distribution requires at least two hypotheses")
        refs = [key for key, _ in self.probability_bps]
        if refs != sorted(refs) or len(set(refs)) != len(refs):
            raise ValueError("hypothesis refs must be unique and canonically sorted")
        if any(not key or value < 0 or value > 10_000 for key, value in self.probability_bps):
            raise ValueError("invalid hypothesis probability")
        if sum(value for _, value in self.probability_bps) != 10_000:
            raise ValueError("hypothesis probabilities must sum to 10000 basis points")
        _require_digest("evidence_state_hash", self.evidence_state_hash)
        _require_digest("distribution_hash", self.distribution_hash)
        if self.distribution_hash != _digest(self.material()):
            raise ValueError("distribution_hash does not match distribution material")


def make_hypothesis_distribution(
    distribution_ref: str,
    *,
    subject_identity_ref: str,
    probability_bps: dict[str, int] | tuple[tuple[str, int], ...],
    evidence_state_hash: str,
    generation: int,
) -> HypothesisDistribution:
    entries = tuple(sorted(dict(probability_bps).items()))
    fields = {
        "distribution_ref": distribution_ref,
        "subject_identity_ref": subject_identity_ref,
        "probability_bps": entries,
        "evidence_state_hash": evidence_state_hash,
        "generation": generation,
    }
    provisional = HypothesisDistribution(**fields, distribution_hash="0" * 64)
    result = HypothesisDistribution(**fields, distribution_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class MultiLikelihoodModel:
    candidate_hash: str
    distribution_hash: str
    positive_likelihood_bps: tuple[tuple[str, int], ...]
    conditioning_evidence_hashes: tuple[str, ...]
    model_ref: str
    model_generation: int
    model_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/multi-likelihood-model/v1.11",
            "candidate_hash": self.candidate_hash,
            "distribution_hash": self.distribution_hash,
            "positive_likelihood_bps": [[key, value] for key, value in self.positive_likelihood_bps],
            "conditioning_evidence_hashes": list(self.conditioning_evidence_hashes),
            "model_ref": self.model_ref,
            "model_generation": self.model_generation,
        }

    def validate(self) -> None:
        _require_digest("candidate_hash", self.candidate_hash)
        _require_digest("distribution_hash", self.distribution_hash)
        _require_digest("model_hash", self.model_hash)
        if not self.model_ref or self.model_generation < 0:
            raise ValueError("model_ref is required and generation must be >= 0")
        refs = [key for key, _ in self.positive_likelihood_bps]
        if refs != sorted(refs) or len(set(refs)) != len(refs) or len(refs) < 2:
            raise ValueError("likelihood hypotheses must be unique, sorted, and plural")
        if any(not key or value < 0 or value > 10_000 for key, value in self.positive_likelihood_bps):
            raise ValueError("likelihoods must be 0..10000 basis points")
        for value in self.conditioning_evidence_hashes:
            _require_digest("conditioning_evidence_hash", value)
        if tuple(sorted(set(self.conditioning_evidence_hashes))) != self.conditioning_evidence_hashes:
            raise ValueError("conditioning evidence hashes must be unique and sorted")
        if self.model_hash != _digest(self.material()):
            raise ValueError("model_hash does not match multi-likelihood material")


def make_multi_likelihood_model(
    *,
    candidate_hash: str,
    distribution: HypothesisDistribution,
    positive_likelihood_bps: dict[str, int] | tuple[tuple[str, int], ...],
    conditioning_evidence_hashes: tuple[str, ...] = (),
    model_ref: str,
    model_generation: int,
) -> MultiLikelihoodModel:
    distribution.validate()
    entries = tuple(sorted(dict(positive_likelihood_bps).items()))
    if tuple(key for key, _ in entries) != tuple(key for key, _ in distribution.probability_bps):
        raise ValueError("likelihood model must exactly cover distribution hypotheses")
    fields = {
        "candidate_hash": candidate_hash,
        "distribution_hash": distribution.distribution_hash,
        "positive_likelihood_bps": entries,
        "conditioning_evidence_hashes": tuple(sorted(set(conditioning_evidence_hashes))),
        "model_ref": model_ref,
        "model_generation": model_generation,
    }
    provisional = MultiLikelihoodModel(**fields, model_hash="0" * 64)
    result = MultiLikelihoodModel(**fields, model_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class EvidenceDependencyDeclaration:
    candidate_hash: str
    source_event_hash: str
    derivation_hash: str
    dependency_group_ref: str
    mode: DependencyMode
    parent_evidence_hashes: tuple[str, ...]
    declaration_ref: str
    declaration_generation: int
    declared_at: int
    dependency_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/evidence-dependency/v1.11",
            "candidate_hash": self.candidate_hash,
            "source_event_hash": self.source_event_hash,
            "derivation_hash": self.derivation_hash,
            "dependency_group_ref": self.dependency_group_ref,
            "mode": self.mode,
            "parent_evidence_hashes": list(self.parent_evidence_hashes),
            "declaration_ref": self.declaration_ref,
            "declaration_generation": self.declaration_generation,
            "declared_at": self.declared_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("source_event_hash", self.source_event_hash),
            ("derivation_hash", self.derivation_hash),
            ("dependency_hash", self.dependency_hash),
        ):
            _require_digest(name, value)
        if not self.dependency_group_ref or not self.declaration_ref:
            raise ValueError("dependency group and declaration ref are required")
        if self.mode not in {"INDEPENDENT", "CONDITIONAL", "DUPLICATE"}:
            raise ValueError("invalid dependency mode")
        if self.declaration_generation < 0 or self.declared_at < 0:
            raise ValueError("invalid dependency declaration metadata")
        for value in self.parent_evidence_hashes:
            _require_digest("parent_evidence_hash", value)
        if tuple(sorted(set(self.parent_evidence_hashes))) != self.parent_evidence_hashes:
            raise ValueError("parent evidence hashes must be unique and sorted")
        if self.mode == "INDEPENDENT" and self.parent_evidence_hashes:
            raise ValueError("independent evidence cannot declare parents")
        if self.mode == "CONDITIONAL" and not self.parent_evidence_hashes:
            raise ValueError("conditional evidence requires parent evidence")
        if self.mode == "DUPLICATE" and len(self.parent_evidence_hashes) != 1:
            raise ValueError("duplicate evidence requires exactly one parent evidence")
        if self.dependency_hash != _digest(self.material()):
            raise ValueError("dependency_hash does not match dependency material")


def make_evidence_dependency(
    *,
    candidate_hash: str,
    source_event_hash: str,
    derivation_hash: str,
    dependency_group_ref: str,
    mode: DependencyMode,
    parent_evidence_hashes: tuple[str, ...] = (),
    declaration_ref: str,
    declaration_generation: int,
    declared_at: int,
) -> EvidenceDependencyDeclaration:
    fields = {
        "candidate_hash": candidate_hash,
        "source_event_hash": source_event_hash,
        "derivation_hash": derivation_hash,
        "dependency_group_ref": dependency_group_ref,
        "mode": mode,
        "parent_evidence_hashes": tuple(sorted(set(parent_evidence_hashes))),
        "declaration_ref": declaration_ref,
        "declaration_generation": declaration_generation,
        "declared_at": declared_at,
    }
    provisional = EvidenceDependencyDeclaration(**fields, dependency_hash="0" * 64)
    result = EvidenceDependencyDeclaration(**fields, dependency_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class MultiEvidenceRule:
    candidate_hash: str
    likelihood_model_hash: str
    pass_outcome: EvidenceOutcome
    hold_outcome: EvidenceOutcome
    fail_outcome: EvidenceOutcome
    rule_ref: str
    rule_generation: int
    registered_at: int
    rule_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/multi-evidence-rule/v1.11",
            "candidate_hash": self.candidate_hash,
            "likelihood_model_hash": self.likelihood_model_hash,
            "pass_outcome": self.pass_outcome,
            "hold_outcome": self.hold_outcome,
            "fail_outcome": self.fail_outcome,
            "rule_ref": self.rule_ref,
            "rule_generation": self.rule_generation,
            "registered_at": self.registered_at,
        }

    def validate(self) -> None:
        _require_digest("candidate_hash", self.candidate_hash)
        _require_digest("likelihood_model_hash", self.likelihood_model_hash)
        _require_digest("rule_hash", self.rule_hash)
        allowed = {"POSITIVE", "NEGATIVE", "INCONCLUSIVE"}
        if self.pass_outcome not in allowed or self.hold_outcome not in allowed or self.fail_outcome not in allowed:
            raise ValueError("invalid multi evidence outcome mapping")
        if not self.rule_ref or self.rule_generation < 0 or self.registered_at < 0:
            raise ValueError("invalid multi evidence rule metadata")
        if self.rule_hash != _digest(self.material()):
            raise ValueError("rule_hash does not match multi evidence rule material")


def make_multi_evidence_rule(
    *,
    candidate_hash: str,
    likelihood_model_hash: str,
    pass_outcome: EvidenceOutcome,
    hold_outcome: EvidenceOutcome,
    fail_outcome: EvidenceOutcome,
    rule_ref: str,
    rule_generation: int,
    registered_at: int,
) -> MultiEvidenceRule:
    fields = {
        "candidate_hash": candidate_hash,
        "likelihood_model_hash": likelihood_model_hash,
        "pass_outcome": pass_outcome,
        "hold_outcome": hold_outcome,
        "fail_outcome": fail_outcome,
        "rule_ref": rule_ref,
        "rule_generation": rule_generation,
        "registered_at": registered_at,
    }
    provisional = MultiEvidenceRule(**fields, rule_hash="0" * 64)
    result = MultiEvidenceRule(**fields, rule_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class MultiEvidenceReceipt:
    candidate_hash: str
    work_hash: str
    completion_hash: str
    completion_decision: CompletionDecision
    prior_distribution_hash: str
    likelihood_model_hash: str
    dependency_hash: str
    rule_hash: str
    source_event_hash: str
    derivation_hash: str
    dependency_group_ref: str
    dependency_mode: DependencyMode
    parent_evidence_hashes: tuple[str, ...]
    outcome: EvidenceOutcome
    interpreted_at: int
    evidence_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/multi-evidence-receipt/v1.11",
            "candidate_hash": self.candidate_hash,
            "work_hash": self.work_hash,
            "completion_hash": self.completion_hash,
            "completion_decision": self.completion_decision,
            "prior_distribution_hash": self.prior_distribution_hash,
            "likelihood_model_hash": self.likelihood_model_hash,
            "dependency_hash": self.dependency_hash,
            "rule_hash": self.rule_hash,
            "source_event_hash": self.source_event_hash,
            "derivation_hash": self.derivation_hash,
            "dependency_group_ref": self.dependency_group_ref,
            "dependency_mode": self.dependency_mode,
            "parent_evidence_hashes": list(self.parent_evidence_hashes),
            "outcome": self.outcome,
            "interpreted_at": self.interpreted_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("work_hash", self.work_hash),
            ("completion_hash", self.completion_hash),
            ("prior_distribution_hash", self.prior_distribution_hash),
            ("likelihood_model_hash", self.likelihood_model_hash),
            ("dependency_hash", self.dependency_hash),
            ("rule_hash", self.rule_hash),
            ("source_event_hash", self.source_event_hash),
            ("derivation_hash", self.derivation_hash),
            ("evidence_hash", self.evidence_hash),
        ):
            _require_digest(name, value)
        if self.completion_decision not in {"PASS", "HOLD", "FAIL"}:
            raise ValueError("invalid completion decision")
        if self.outcome not in {"POSITIVE", "NEGATIVE", "INCONCLUSIVE"}:
            raise ValueError("invalid evidence outcome")
        if self.dependency_mode not in {"INDEPENDENT", "CONDITIONAL", "DUPLICATE"}:
            raise ValueError("invalid dependency mode")
        if not self.dependency_group_ref or self.interpreted_at < 0:
            raise ValueError("invalid multi evidence metadata")
        if self.evidence_hash != _digest(self.material()):
            raise ValueError("evidence_hash does not match evidence material")


def interpret_multi_completion(
    *,
    candidate_hash: str,
    work_hash: str,
    completion_hash: str,
    completion_decision: CompletionDecision,
    distribution: HypothesisDistribution,
    likelihood_model: MultiLikelihoodModel,
    dependency: EvidenceDependencyDeclaration,
    rule: MultiEvidenceRule,
    completion_completed_at: int,
    interpreted_at: int,
) -> MultiEvidenceReceipt:
    distribution.validate()
    likelihood_model.validate()
    dependency.validate()
    rule.validate()
    if likelihood_model.candidate_hash != candidate_hash or dependency.candidate_hash != candidate_hash or rule.candidate_hash != candidate_hash:
        raise ValueError("multi evidence candidate binding mismatch")
    if likelihood_model.distribution_hash != distribution.distribution_hash:
        raise ValueError("multi likelihood/distribution mismatch")
    if rule.likelihood_model_hash != likelihood_model.model_hash:
        raise ValueError("multi evidence rule likelihood mismatch")
    if dependency.declared_at > completion_completed_at or rule.registered_at > completion_completed_at:
        raise ValueError("dependency and interpretation semantics must be precommitted before completion")
    if interpreted_at < completion_completed_at:
        raise ValueError("interpretation cannot precede completion")
    if dependency.mode == "INDEPENDENT" and likelihood_model.conditioning_evidence_hashes:
        raise ValueError("independent evidence requires unconditional likelihood model")
    if dependency.mode == "CONDITIONAL" and likelihood_model.conditioning_evidence_hashes != dependency.parent_evidence_hashes:
        raise ValueError("conditional likelihood must bind exact parent evidence")
    mapping = {"PASS": rule.pass_outcome, "HOLD": rule.hold_outcome, "FAIL": rule.fail_outcome}
    fields = {
        "candidate_hash": candidate_hash,
        "work_hash": work_hash,
        "completion_hash": completion_hash,
        "completion_decision": completion_decision,
        "prior_distribution_hash": distribution.distribution_hash,
        "likelihood_model_hash": likelihood_model.model_hash,
        "dependency_hash": dependency.dependency_hash,
        "rule_hash": rule.rule_hash,
        "source_event_hash": dependency.source_event_hash,
        "derivation_hash": dependency.derivation_hash,
        "dependency_group_ref": dependency.dependency_group_ref,
        "dependency_mode": dependency.mode,
        "parent_evidence_hashes": dependency.parent_evidence_hashes,
        "outcome": mapping[completion_decision],
        "interpreted_at": interpreted_at,
    }
    provisional = MultiEvidenceReceipt(**fields, evidence_hash="0" * 64)
    result = MultiEvidenceReceipt(**fields, evidence_hash=_digest(provisional.material()))
    result.validate()
    return result


def posterior_distribution_bps(
    distribution: HypothesisDistribution,
    likelihood_model: MultiLikelihoodModel,
    outcome: EvidenceOutcome,
) -> tuple[tuple[str, int], ...]:
    distribution.validate()
    likelihood_model.validate()
    if likelihood_model.distribution_hash != distribution.distribution_hash:
        raise ValueError("multi likelihood/distribution mismatch")
    likelihoods = dict(likelihood_model.positive_likelihood_bps)
    if tuple(likelihoods) != tuple(key for key, _ in distribution.probability_bps):
        raise ValueError("likelihood model does not exactly cover hypotheses")
    if outcome == "INCONCLUSIVE":
        return distribution.probability_bps
    weights: list[tuple[str, int]] = []
    for hypothesis_ref, prior in distribution.probability_bps:
        positive = likelihoods[hypothesis_ref]
        factor = positive if outcome == "POSITIVE" else 10_000 - positive
        weights.append((hypothesis_ref, prior * factor))
    return _normalize_weights(tuple(weights))


@dataclass(frozen=True)
class MultiHypothesisUpdateReceipt:
    candidate_hash: str
    prior_distribution_hash: str
    posterior_distribution_hash: str
    evidence_hash: str
    likelihood_model_hash: str
    dependency_hash: str
    prior_probability_bps: tuple[tuple[str, int], ...]
    posterior_probability_bps: tuple[tuple[str, int], ...]
    prior_generation: int
    posterior_generation: int
    evidence_state_hash: str
    applied_at: int
    updater_ref: str
    update_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/multi-hypothesis-update/v1.11",
            "candidate_hash": self.candidate_hash,
            "prior_distribution_hash": self.prior_distribution_hash,
            "posterior_distribution_hash": self.posterior_distribution_hash,
            "evidence_hash": self.evidence_hash,
            "likelihood_model_hash": self.likelihood_model_hash,
            "dependency_hash": self.dependency_hash,
            "prior_probability_bps": [[key, value] for key, value in self.prior_probability_bps],
            "posterior_probability_bps": [[key, value] for key, value in self.posterior_probability_bps],
            "prior_generation": self.prior_generation,
            "posterior_generation": self.posterior_generation,
            "evidence_state_hash": self.evidence_state_hash,
            "applied_at": self.applied_at,
            "updater_ref": self.updater_ref,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("prior_distribution_hash", self.prior_distribution_hash),
            ("posterior_distribution_hash", self.posterior_distribution_hash),
            ("evidence_hash", self.evidence_hash),
            ("likelihood_model_hash", self.likelihood_model_hash),
            ("dependency_hash", self.dependency_hash),
            ("evidence_state_hash", self.evidence_state_hash),
            ("update_hash", self.update_hash),
        ):
            _require_digest(name, value)
        if self.posterior_generation != self.prior_generation + 1:
            raise ValueError("posterior generation must advance exactly once")
        if sum(value for _, value in self.prior_probability_bps) != 10_000 or sum(value for _, value in self.posterior_probability_bps) != 10_000:
            raise ValueError("probability vectors must normalize to 10000 basis points")
        if not self.updater_ref or self.applied_at < 0:
            raise ValueError("invalid multi update metadata")
        if self.update_hash != _digest(self.material()):
            raise ValueError("update_hash does not match multi update material")


def build_multi_hypothesis_update(
    *,
    distribution: HypothesisDistribution,
    likelihood_model: MultiLikelihoodModel,
    evidence: MultiEvidenceReceipt,
    applied_at: int,
    updater_ref: str,
) -> tuple[HypothesisDistribution, MultiHypothesisUpdateReceipt]:
    distribution.validate()
    likelihood_model.validate()
    evidence.validate()
    if evidence.dependency_mode == "DUPLICATE":
        raise ValueError("duplicate evidence cannot advance hypothesis distribution")
    if evidence.prior_distribution_hash != distribution.distribution_hash:
        raise ValueError("evidence prior distribution mismatch")
    if evidence.likelihood_model_hash != likelihood_model.model_hash:
        raise ValueError("evidence likelihood mismatch")
    posterior_probabilities = posterior_distribution_bps(distribution, likelihood_model, evidence.outcome)
    evidence_state_hash = _digest({
        "domain": "ATMAN-LATTICE/multi-evidence-state/v1.11",
        "prior_evidence_state_hash": distribution.evidence_state_hash,
        "evidence_hash": evidence.evidence_hash,
        "source_event_hash": evidence.source_event_hash,
        "dependency_hash": evidence.dependency_hash,
    })
    posterior = make_hypothesis_distribution(
        distribution.distribution_ref,
        subject_identity_ref=distribution.subject_identity_ref,
        probability_bps=posterior_probabilities,
        evidence_state_hash=evidence_state_hash,
        generation=distribution.generation + 1,
    )
    fields = {
        "candidate_hash": evidence.candidate_hash,
        "prior_distribution_hash": distribution.distribution_hash,
        "posterior_distribution_hash": posterior.distribution_hash,
        "evidence_hash": evidence.evidence_hash,
        "likelihood_model_hash": likelihood_model.model_hash,
        "dependency_hash": evidence.dependency_hash,
        "prior_probability_bps": distribution.probability_bps,
        "posterior_probability_bps": posterior.probability_bps,
        "prior_generation": distribution.generation,
        "posterior_generation": posterior.generation,
        "evidence_state_hash": evidence_state_hash,
        "applied_at": applied_at,
        "updater_ref": updater_ref,
    }
    provisional = MultiHypothesisUpdateReceipt(**fields, update_hash="0" * 64)
    receipt = MultiHypothesisUpdateReceipt(**fields, update_hash=_digest(provisional.material()))
    receipt.validate()
    return posterior, receipt


@dataclass(frozen=True)
class DuplicateEvidenceReceipt:
    evidence_hash: str
    parent_evidence_hash: str
    source_event_hash: str
    derivation_hash: str
    observed_at: int
    duplicate_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/duplicate-evidence/v1.11",
            "evidence_hash": self.evidence_hash,
            "parent_evidence_hash": self.parent_evidence_hash,
            "source_event_hash": self.source_event_hash,
            "derivation_hash": self.derivation_hash,
            "observed_at": self.observed_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("evidence_hash", self.evidence_hash),
            ("parent_evidence_hash", self.parent_evidence_hash),
            ("source_event_hash", self.source_event_hash),
            ("derivation_hash", self.derivation_hash),
            ("duplicate_hash", self.duplicate_hash),
        ):
            _require_digest(name, value)
        if self.observed_at < 0:
            raise ValueError("observed_at must be >= 0")
        if self.duplicate_hash != _digest(self.material()):
            raise ValueError("duplicate_hash does not match duplicate material")


def build_duplicate_evidence_receipt(
    evidence: MultiEvidenceReceipt,
    *,
    parent_source_event_hash: str,
    observed_at: int,
) -> DuplicateEvidenceReceipt:
    evidence.validate()
    if evidence.dependency_mode != "DUPLICATE" or len(evidence.parent_evidence_hashes) != 1:
        raise ValueError("duplicate receipt requires DUPLICATE evidence")
    if evidence.source_event_hash != parent_source_event_hash:
        raise ValueError("duplicate evidence must preserve the same source_event_hash")
    fields = {
        "evidence_hash": evidence.evidence_hash,
        "parent_evidence_hash": evidence.parent_evidence_hashes[0],
        "source_event_hash": evidence.source_event_hash,
        "derivation_hash": evidence.derivation_hash,
        "observed_at": observed_at,
    }
    provisional = DuplicateEvidenceReceipt(**fields, duplicate_hash="0" * 64)
    result = DuplicateEvidenceReceipt(**fields, duplicate_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class MultiExpectedInformationGainReceipt:
    candidate_hash: str
    distribution_hash: str
    likelihood_model_hash: str
    prior_entropy_microbits: int
    expected_posterior_entropy_microbits: int
    expected_information_gain_microbits: int
    computed_at: int
    information_gain_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/multi-expected-information-gain/v1.11",
            "candidate_hash": self.candidate_hash,
            "distribution_hash": self.distribution_hash,
            "likelihood_model_hash": self.likelihood_model_hash,
            "prior_entropy_microbits": self.prior_entropy_microbits,
            "expected_posterior_entropy_microbits": self.expected_posterior_entropy_microbits,
            "expected_information_gain_microbits": self.expected_information_gain_microbits,
            "computed_at": self.computed_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("distribution_hash", self.distribution_hash),
            ("likelihood_model_hash", self.likelihood_model_hash),
            ("information_gain_hash", self.information_gain_hash),
        ):
            _require_digest(name, value)
        if min(self.prior_entropy_microbits, self.expected_posterior_entropy_microbits, self.expected_information_gain_microbits, self.computed_at) < 0:
            raise ValueError("invalid information accounting")
        if self.expected_posterior_entropy_microbits > self.prior_entropy_microbits:
            raise ValueError("expected posterior entropy cannot exceed prior entropy")
        if self.expected_information_gain_microbits != self.prior_entropy_microbits - self.expected_posterior_entropy_microbits:
            raise ValueError("information gain must equal entropy reduction")
        if self.information_gain_hash != _digest(self.material()):
            raise ValueError("information_gain_hash does not match multi information material")


def multi_expected_information_gain(
    distribution: HypothesisDistribution,
    likelihood_model: MultiLikelihoodModel,
    *,
    computed_at: int,
) -> MultiExpectedInformationGainReceipt:
    distribution.validate()
    likelihood_model.validate()
    if likelihood_model.distribution_hash != distribution.distribution_hash:
        raise ValueError("multi likelihood/distribution mismatch")
    prior_entropy = int(round(_entropy_bits(tuple(value for _, value in distribution.probability_bps)) * 1_000_000))
    likelihoods = dict(likelihood_model.positive_likelihood_bps)
    positive_numerator = sum(prior * likelihoods[key] for key, prior in distribution.probability_bps)
    positive_probability = positive_numerator / 100_000_000.0
    negative_probability = 1.0 - positive_probability
    positive = posterior_distribution_bps(distribution, likelihood_model, "POSITIVE") if positive_probability > 0 else distribution.probability_bps
    negative = posterior_distribution_bps(distribution, likelihood_model, "NEGATIVE") if negative_probability > 0 else distribution.probability_bps
    expected_bits = (
        positive_probability * _entropy_bits(tuple(value for _, value in positive))
        + negative_probability * _entropy_bits(tuple(value for _, value in negative))
    )
    expected_entropy = min(prior_entropy, max(0, int(round(expected_bits * 1_000_000))))
    fields = {
        "candidate_hash": likelihood_model.candidate_hash,
        "distribution_hash": distribution.distribution_hash,
        "likelihood_model_hash": likelihood_model.model_hash,
        "prior_entropy_microbits": prior_entropy,
        "expected_posterior_entropy_microbits": expected_entropy,
        "expected_information_gain_microbits": prior_entropy - expected_entropy,
        "computed_at": computed_at,
    }
    provisional = MultiExpectedInformationGainReceipt(**fields, information_gain_hash="0" * 64)
    result = MultiExpectedInformationGainReceipt(**fields, information_gain_hash=_digest(provisional.material()))
    result.validate()
    return result
