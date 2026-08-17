from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Iterable, Mapping, Literal

from model.verification_economy import (
    CostEstimatorSnapshot,
    EconomicVerificationCandidate,
    VerificationEconomyPolicy,
    estimated_cost_units,
)

Disposition = Literal[
    "SELECTED",
    "DEFERRED_BUDGET",
    "DEFERRED_OVERSIZED",
    "DEFERRED_LOW_INFORMATION",
]


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _entropy_bits(probability: float) -> float:
    if probability <= 0.0 or probability >= 1.0:
        return 0.0
    return -probability * math.log2(probability) - (1.0 - probability) * math.log2(1.0 - probability)


def entropy_microbits(true_probability_bps: int) -> int:
    if true_probability_bps < 0 or true_probability_bps > 10_000:
        raise ValueError("probability must be in basis points 0..10000")
    p = true_probability_bps / 10_000.0
    return int(round(_entropy_bits(p) * 1_000_000))


@dataclass(frozen=True)
class HypothesisState:
    hypothesis_ref: str
    subject_identity_ref: str
    true_probability_bps: int
    evidence_state_hash: str
    generation: int
    hypothesis_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/hypothesis-state/v1.9",
            "hypothesis_ref": self.hypothesis_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "true_probability_bps": self.true_probability_bps,
            "evidence_state_hash": self.evidence_state_hash,
            "generation": self.generation,
        }

    def validate(self) -> None:
        if not self.hypothesis_ref or not self.subject_identity_ref:
            raise ValueError("hypothesis_ref and subject_identity_ref are required")
        if self.true_probability_bps < 0 or self.true_probability_bps > 10_000:
            raise ValueError("true_probability_bps must be 0..10000")
        if self.generation < 0:
            raise ValueError("generation must be >= 0")
        _require_digest("evidence_state_hash", self.evidence_state_hash)
        _require_digest("hypothesis_hash", self.hypothesis_hash)
        if self.hypothesis_hash != _digest(self.material()):
            raise ValueError("hypothesis_hash does not match hypothesis material")


def make_hypothesis_state(
    hypothesis_ref: str,
    *,
    subject_identity_ref: str,
    true_probability_bps: int,
    evidence_state_hash: str,
    generation: int,
) -> HypothesisState:
    fields = {
        "hypothesis_ref": hypothesis_ref,
        "subject_identity_ref": subject_identity_ref,
        "true_probability_bps": true_probability_bps,
        "evidence_state_hash": evidence_state_hash,
        "generation": generation,
    }
    provisional = HypothesisState(**fields, hypothesis_hash="0" * 64)
    result = HypothesisState(**fields, hypothesis_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class VerificationLikelihoodModel:
    candidate_hash: str
    hypothesis_hash: str
    positive_if_true_bps: int
    positive_if_false_bps: int
    model_ref: str
    model_generation: int
    model_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-likelihood-model/v1.9",
            "candidate_hash": self.candidate_hash,
            "hypothesis_hash": self.hypothesis_hash,
            "positive_if_true_bps": self.positive_if_true_bps,
            "positive_if_false_bps": self.positive_if_false_bps,
            "model_ref": self.model_ref,
            "model_generation": self.model_generation,
        }

    def validate(self) -> None:
        _require_digest("candidate_hash", self.candidate_hash)
        _require_digest("hypothesis_hash", self.hypothesis_hash)
        _require_digest("model_hash", self.model_hash)
        if not self.model_ref or self.model_generation < 0:
            raise ValueError("model_ref is required and generation must be >= 0")
        for value in (self.positive_if_true_bps, self.positive_if_false_bps):
            if value < 0 or value > 10_000:
                raise ValueError("likelihoods must be 0..10000 basis points")
        if self.model_hash != _digest(self.material()):
            raise ValueError("model_hash does not match likelihood material")


def make_likelihood_model(
    *,
    candidate_hash: str,
    hypothesis_hash: str,
    positive_if_true_bps: int,
    positive_if_false_bps: int,
    model_ref: str,
    model_generation: int,
) -> VerificationLikelihoodModel:
    fields = {
        "candidate_hash": candidate_hash,
        "hypothesis_hash": hypothesis_hash,
        "positive_if_true_bps": positive_if_true_bps,
        "positive_if_false_bps": positive_if_false_bps,
        "model_ref": model_ref,
        "model_generation": model_generation,
    }
    provisional = VerificationLikelihoodModel(**fields, model_hash="0" * 64)
    result = VerificationLikelihoodModel(**fields, model_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ExpectedInformationGainReceipt:
    candidate_hash: str
    hypothesis_hash: str
    likelihood_model_hash: str
    prior_entropy_microbits: int
    expected_posterior_entropy_microbits: int
    expected_information_gain_microbits: int
    estimated_cost_units: int
    information_per_cost_scaled: int
    computed_at: int
    information_gain_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/expected-information-gain/v1.9",
            "candidate_hash": self.candidate_hash,
            "hypothesis_hash": self.hypothesis_hash,
            "likelihood_model_hash": self.likelihood_model_hash,
            "prior_entropy_microbits": self.prior_entropy_microbits,
            "expected_posterior_entropy_microbits": self.expected_posterior_entropy_microbits,
            "expected_information_gain_microbits": self.expected_information_gain_microbits,
            "estimated_cost_units": self.estimated_cost_units,
            "information_per_cost_scaled": self.information_per_cost_scaled,
            "computed_at": self.computed_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("hypothesis_hash", self.hypothesis_hash),
            ("likelihood_model_hash", self.likelihood_model_hash),
            ("information_gain_hash", self.information_gain_hash),
        ):
            _require_digest(name, value)
        if min(
            self.prior_entropy_microbits,
            self.expected_posterior_entropy_microbits,
            self.expected_information_gain_microbits,
            self.information_per_cost_scaled,
            self.computed_at,
        ) < 0:
            raise ValueError("information accounting must be >= 0")
        if self.estimated_cost_units <= 0:
            raise ValueError("estimated_cost_units must be > 0")
        if self.expected_posterior_entropy_microbits > self.prior_entropy_microbits:
            raise ValueError("expected posterior entropy cannot exceed prior entropy")
        if self.expected_information_gain_microbits != self.prior_entropy_microbits - self.expected_posterior_entropy_microbits:
            raise ValueError("expected information gain must equal entropy reduction")
        expected_ratio = self.expected_information_gain_microbits * 1_000_000 // self.estimated_cost_units
        if self.information_per_cost_scaled != expected_ratio:
            raise ValueError("information_per_cost_scaled mismatch")
        if self.information_gain_hash != _digest(self.material()):
            raise ValueError("information_gain_hash does not match material")


def expected_information_gain(
    candidate: EconomicVerificationCandidate,
    hypothesis: HypothesisState,
    likelihood: VerificationLikelihoodModel,
    *,
    estimated_cost: int,
    computed_at: int,
) -> ExpectedInformationGainReceipt:
    candidate.validate()
    hypothesis.validate()
    likelihood.validate()
    if candidate.subject_identity_ref != hypothesis.subject_identity_ref:
        raise ValueError("candidate/hypothesis identity mismatch")
    if likelihood.candidate_hash != candidate.candidate_hash:
        raise ValueError("likelihood candidate mismatch")
    if likelihood.hypothesis_hash != hypothesis.hypothesis_hash:
        raise ValueError("likelihood hypothesis mismatch")
    if estimated_cost <= 0 or computed_at < 0:
        raise ValueError("invalid information-gain accounting")

    p = hypothesis.true_probability_bps / 10_000.0
    sensitivity = likelihood.positive_if_true_bps / 10_000.0
    false_positive = likelihood.positive_if_false_bps / 10_000.0
    positive_probability = p * sensitivity + (1.0 - p) * false_positive

    prior = entropy_microbits(hypothesis.true_probability_bps)
    expected_posterior_bits = 0.0
    if positive_probability > 0.0:
        posterior_true_positive = p * sensitivity / positive_probability
        expected_posterior_bits += positive_probability * _entropy_bits(posterior_true_positive)
    negative_probability = 1.0 - positive_probability
    if negative_probability > 0.0:
        posterior_true_negative = p * (1.0 - sensitivity) / negative_probability
        expected_posterior_bits += negative_probability * _entropy_bits(posterior_true_negative)

    posterior = int(round(expected_posterior_bits * 1_000_000))
    posterior = min(prior, max(0, posterior))
    gain = prior - posterior
    ratio = gain * 1_000_000 // estimated_cost
    fields = {
        "candidate_hash": candidate.candidate_hash,
        "hypothesis_hash": hypothesis.hypothesis_hash,
        "likelihood_model_hash": likelihood.model_hash,
        "prior_entropy_microbits": prior,
        "expected_posterior_entropy_microbits": posterior,
        "expected_information_gain_microbits": gain,
        "estimated_cost_units": estimated_cost,
        "information_per_cost_scaled": ratio,
        "computed_at": computed_at,
    }
    provisional = ExpectedInformationGainReceipt(**fields, information_gain_hash="0" * 64)
    result = ExpectedInformationGainReceipt(**fields, information_gain_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ActiveVerificationPolicy:
    policy_ref: str
    budget_units: int
    max_selected_items: int
    minimum_information_gain_microbits: int
    aging_quantum: int
    aging_weight: int
    risk_weight: int
    policy_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/active-verification-policy/v1.9",
            "policy_ref": self.policy_ref,
            "budget_units": self.budget_units,
            "max_selected_items": self.max_selected_items,
            "minimum_information_gain_microbits": self.minimum_information_gain_microbits,
            "aging_quantum": self.aging_quantum,
            "aging_weight": self.aging_weight,
            "risk_weight": self.risk_weight,
        }

    def validate(self) -> None:
        if not self.policy_ref:
            raise ValueError("policy_ref is required")
        if min(self.budget_units, self.max_selected_items, self.minimum_information_gain_microbits, self.aging_weight, self.risk_weight) < 0:
            raise ValueError("active policy numeric fields must be >= 0")
        if self.aging_quantum <= 0:
            raise ValueError("aging_quantum must be > 0")
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match active policy material")


def make_active_verification_policy(
    policy_ref: str = "atman:active-verification:default:v1.9",
    *,
    budget_units: int,
    max_selected_items: int,
    minimum_information_gain_microbits: int = 1,
    aging_quantum: int = 60,
    aging_weight: int = 1,
    risk_weight: int = 0,
) -> ActiveVerificationPolicy:
    fields = {
        "policy_ref": policy_ref,
        "budget_units": budget_units,
        "max_selected_items": max_selected_items,
        "minimum_information_gain_microbits": minimum_information_gain_microbits,
        "aging_quantum": aging_quantum,
        "aging_weight": aging_weight,
        "risk_weight": risk_weight,
    }
    provisional = ActiveVerificationPolicy(**fields, policy_hash="0" * 64)
    result = ActiveVerificationPolicy(**fields, policy_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ActiveVerificationPlanReceipt:
    policy_hash: str
    economy_policy_hash: str
    measured_at: int
    candidate_hashes: tuple[str, ...]
    information_gain_hashes: tuple[str, ...]
    ranked_candidate_hashes: tuple[str, ...]
    selected_candidate_hashes: tuple[str, ...]
    deferred_budget_candidate_hashes: tuple[str, ...]
    deferred_oversized_candidate_hashes: tuple[str, ...]
    deferred_low_information_candidate_hashes: tuple[str, ...]
    used_budget_units: int
    budget_units: int
    plan_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/active-verification-plan/v1.9",
            "policy_hash": self.policy_hash,
            "economy_policy_hash": self.economy_policy_hash,
            "measured_at": self.measured_at,
            "candidate_hashes": list(self.candidate_hashes),
            "information_gain_hashes": list(self.information_gain_hashes),
            "ranked_candidate_hashes": list(self.ranked_candidate_hashes),
            "selected_candidate_hashes": list(self.selected_candidate_hashes),
            "deferred_budget_candidate_hashes": list(self.deferred_budget_candidate_hashes),
            "deferred_oversized_candidate_hashes": list(self.deferred_oversized_candidate_hashes),
            "deferred_low_information_candidate_hashes": list(self.deferred_low_information_candidate_hashes),
            "used_budget_units": self.used_budget_units,
            "budget_units": self.budget_units,
        }

    def validate(self) -> None:
        _require_digest("policy_hash", self.policy_hash)
        _require_digest("economy_policy_hash", self.economy_policy_hash)
        _require_digest("plan_hash", self.plan_hash)
        if min(self.measured_at, self.used_budget_units, self.budget_units) < 0 or self.used_budget_units > self.budget_units:
            raise ValueError("invalid active budget accounting")
        for collection in (
            self.candidate_hashes,
            self.information_gain_hashes,
            self.ranked_candidate_hashes,
            self.selected_candidate_hashes,
            self.deferred_budget_candidate_hashes,
            self.deferred_oversized_candidate_hashes,
            self.deferred_low_information_candidate_hashes,
        ):
            for value in collection:
                _require_digest("digest", value)
            if len(set(collection)) != len(collection):
                raise ValueError("duplicate digest in active plan")
        candidates = set(self.candidate_hashes)
        if set(self.ranked_candidate_hashes) != candidates:
            raise ValueError("active ranking must exactly cover candidates")
        dispositions = (
            set(self.selected_candidate_hashes),
            set(self.deferred_budget_candidate_hashes),
            set(self.deferred_oversized_candidate_hashes),
            set(self.deferred_low_information_candidate_hashes),
        )
        for index, left in enumerate(dispositions):
            for right in dispositions[index + 1:]:
                if left & right:
                    raise ValueError("active dispositions must be disjoint")
        if set().union(*dispositions) != candidates:
            raise ValueError("active dispositions must exactly cover candidates")
        if self.plan_hash != _digest(self.material()):
            raise ValueError("plan_hash does not match active plan material")


def plan_active_verification(
    candidates: Iterable[EconomicVerificationCandidate],
    hypotheses: Mapping[str, HypothesisState],
    likelihood_models: Mapping[str, VerificationLikelihoodModel],
    estimators: Mapping[str, CostEstimatorSnapshot],
    economy_policy: VerificationEconomyPolicy,
    active_policy: ActiveVerificationPolicy,
    *,
    measured_at: int,
) -> tuple[ActiveVerificationPlanReceipt, tuple[ExpectedInformationGainReceipt, ...]]:
    economy_policy.validate()
    active_policy.validate()
    if measured_at < 0:
        raise ValueError("measured_at must be >= 0")
    items = tuple(candidates)
    if len({item.candidate_hash for item in items}) != len(items):
        raise ValueError("duplicate active candidate")

    insights: list[ExpectedInformationGainReceipt] = []
    costs: dict[str, int] = {}
    by_hash = {item.candidate_hash: item for item in items}
    for item in items:
        item.validate()
        hypothesis = hypotheses.get(item.candidate_hash)
        likelihood = likelihood_models.get(item.candidate_hash)
        if hypothesis is None or likelihood is None:
            raise ValueError("every active candidate requires hypothesis and likelihood model")
        cost = estimated_cost_units(item, estimators.get(item.estimator_key), economy_policy)
        costs[item.candidate_hash] = cost
        insights.append(expected_information_gain(item, hypothesis, likelihood, estimated_cost=cost, computed_at=measured_at))

    insight_by_candidate = {item.candidate_hash: item for item in insights}

    def ranking_key(candidate: EconomicVerificationCandidate) -> tuple[int, int, int, int, str]:
        insight = insight_by_candidate[candidate.candidate_hash]
        waited = max(0, measured_at - candidate.submitted_at)
        age_bonus = (waited // active_policy.aging_quantum) * active_policy.aging_weight
        risk_bonus = candidate.risk_units * active_policy.risk_weight
        active_score = insight.information_per_cost_scaled + age_bonus + risk_bonus
        return (
            -active_score,
            -insight.expected_information_gain_microbits,
            -candidate.risk_units,
            candidate.submitted_at,
            candidate.candidate_hash,
        )

    ranked = tuple(sorted(items, key=ranking_key))
    selected: list[str] = []
    deferred_budget: list[str] = []
    deferred_oversized: list[str] = []
    deferred_low_information: list[str] = []
    used = 0
    for candidate in ranked:
        insight = insight_by_candidate[candidate.candidate_hash]
        cost = costs[candidate.candidate_hash]
        if insight.expected_information_gain_microbits < active_policy.minimum_information_gain_microbits:
            deferred_low_information.append(candidate.candidate_hash)
            continue
        if cost > active_policy.budget_units:
            deferred_oversized.append(candidate.candidate_hash)
            continue
        if len(selected) >= active_policy.max_selected_items or used + cost > active_policy.budget_units:
            deferred_budget.append(candidate.candidate_hash)
            continue
        selected.append(candidate.candidate_hash)
        used += cost

    fields = {
        "policy_hash": active_policy.policy_hash,
        "economy_policy_hash": economy_policy.policy_hash,
        "measured_at": measured_at,
        "candidate_hashes": tuple(sorted(by_hash)),
        "information_gain_hashes": tuple(sorted(item.information_gain_hash for item in insights)),
        "ranked_candidate_hashes": tuple(item.candidate_hash for item in ranked),
        "selected_candidate_hashes": tuple(selected),
        "deferred_budget_candidate_hashes": tuple(deferred_budget),
        "deferred_oversized_candidate_hashes": tuple(deferred_oversized),
        "deferred_low_information_candidate_hashes": tuple(deferred_low_information),
        "used_budget_units": used,
        "budget_units": active_policy.budget_units,
    }
    provisional = ActiveVerificationPlanReceipt(**fields, plan_hash="0" * 64)
    plan = ActiveVerificationPlanReceipt(**fields, plan_hash=_digest(provisional.material()))
    plan.validate()
    return plan, tuple(sorted(insights, key=lambda item: item.candidate_hash))
