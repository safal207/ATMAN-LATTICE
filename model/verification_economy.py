from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping, Literal

BudgetStatus = Literal["NORMAL", "PRESSURED", "SATURATED"]


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class CostObservationReceipt:
    work_hash: str
    completion_hash: str
    estimator_key: str
    observed_cost_units: int
    measured_at: int
    meter_ref: str
    observation_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-cost-observation/v1.8",
            "work_hash": self.work_hash,
            "completion_hash": self.completion_hash,
            "estimator_key": self.estimator_key,
            "observed_cost_units": self.observed_cost_units,
            "measured_at": self.measured_at,
            "meter_ref": self.meter_ref,
        }

    def validate(self) -> None:
        _require_digest("work_hash", self.work_hash)
        _require_digest("completion_hash", self.completion_hash)
        _require_digest("observation_hash", self.observation_hash)
        if not self.estimator_key or not self.meter_ref:
            raise ValueError("estimator_key and meter_ref are required")
        if self.observed_cost_units <= 0:
            raise ValueError("observed_cost_units must be > 0")
        if self.measured_at < 0:
            raise ValueError("measured_at must be >= 0")
        if self.observation_hash != _digest(self.material()):
            raise ValueError("observation_hash does not match observation material")


def record_cost_observation(
    *,
    work_hash: str,
    completion_hash: str,
    estimator_key: str,
    observed_cost_units: int,
    measured_at: int,
    meter_ref: str,
) -> CostObservationReceipt:
    fields = {
        "work_hash": work_hash,
        "completion_hash": completion_hash,
        "estimator_key": estimator_key,
        "observed_cost_units": observed_cost_units,
        "measured_at": measured_at,
        "meter_ref": meter_ref,
    }
    provisional = CostObservationReceipt(**fields, observation_hash="0" * 64)
    receipt = CostObservationReceipt(**fields, observation_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class CostEstimatorSnapshot:
    estimator_key: str
    sample_count: int
    total_observed_cost_units: int
    mean_cost_units: int
    observation_hashes: tuple[str, ...]
    snapshot_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-cost-estimator/v1.8",
            "estimator_key": self.estimator_key,
            "sample_count": self.sample_count,
            "total_observed_cost_units": self.total_observed_cost_units,
            "mean_cost_units": self.mean_cost_units,
            "observation_hashes": list(self.observation_hashes),
        }

    def validate(self) -> None:
        if not self.estimator_key:
            raise ValueError("estimator_key is required")
        if self.sample_count < 0 or self.total_observed_cost_units < 0 or self.mean_cost_units < 0:
            raise ValueError("invalid estimator accounting")
        if self.sample_count != len(self.observation_hashes):
            raise ValueError("sample_count must match observation_hashes")
        for value in self.observation_hashes:
            _require_digest("observation_hash", value)
        if len(set(self.observation_hashes)) != len(self.observation_hashes):
            raise ValueError("duplicate observation hash")
        if self.sample_count == 0:
            if self.total_observed_cost_units != 0 or self.mean_cost_units != 0:
                raise ValueError("empty estimator must have zero cost")
        else:
            expected_mean = (self.total_observed_cost_units + self.sample_count - 1) // self.sample_count
            if self.mean_cost_units != expected_mean:
                raise ValueError("mean_cost_units must be ceiling arithmetic mean")
        _require_digest("snapshot_hash", self.snapshot_hash)
        if self.snapshot_hash != _digest(self.material()):
            raise ValueError("snapshot_hash does not match estimator material")


def build_cost_estimator(
    estimator_key: str,
    observations: Iterable[CostObservationReceipt],
) -> CostEstimatorSnapshot:
    selected: list[CostObservationReceipt] = []
    seen_work: set[str] = set()
    for observation in observations:
        observation.validate()
        if observation.estimator_key != estimator_key:
            continue
        if observation.work_hash in seen_work:
            raise ValueError("multiple cost observations for the same work_hash")
        seen_work.add(observation.work_hash)
        selected.append(observation)
    selected.sort(key=lambda item: item.observation_hash)
    total = sum(item.observed_cost_units for item in selected)
    count = len(selected)
    mean = 0 if count == 0 else (total + count - 1) // count
    fields = {
        "estimator_key": estimator_key,
        "sample_count": count,
        "total_observed_cost_units": total,
        "mean_cost_units": mean,
        "observation_hashes": tuple(item.observation_hash for item in selected),
    }
    provisional = CostEstimatorSnapshot(**fields, snapshot_hash="0" * 64)
    snapshot = CostEstimatorSnapshot(**fields, snapshot_hash=_digest(provisional.material()))
    snapshot.validate()
    return snapshot


@dataclass(frozen=True)
class EconomicVerificationCandidate:
    work_hash: str
    subject_identity_ref: str
    estimator_key: str
    declared_cost_units: int
    value_units: int
    risk_units: int
    priority: int
    submitted_at: int
    candidate_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-economic-candidate/v1.8",
            "work_hash": self.work_hash,
            "subject_identity_ref": self.subject_identity_ref,
            "estimator_key": self.estimator_key,
            "declared_cost_units": self.declared_cost_units,
            "value_units": self.value_units,
            "risk_units": self.risk_units,
            "priority": self.priority,
            "submitted_at": self.submitted_at,
        }

    def validate(self) -> None:
        _require_digest("work_hash", self.work_hash)
        _require_digest("candidate_hash", self.candidate_hash)
        if not self.subject_identity_ref or not self.estimator_key:
            raise ValueError("subject_identity_ref and estimator_key are required")
        if self.declared_cost_units <= 0:
            raise ValueError("declared_cost_units must be > 0")
        if min(self.value_units, self.risk_units, self.priority, self.submitted_at) < 0:
            raise ValueError("candidate numeric fields must be >= 0")
        if self.candidate_hash != _digest(self.material()):
            raise ValueError("candidate_hash does not match candidate material")


def make_economic_candidate(
    *,
    work_hash: str,
    subject_identity_ref: str,
    estimator_key: str,
    declared_cost_units: int,
    value_units: int,
    risk_units: int,
    priority: int,
    submitted_at: int,
) -> EconomicVerificationCandidate:
    fields = {
        "work_hash": work_hash,
        "subject_identity_ref": subject_identity_ref,
        "estimator_key": estimator_key,
        "declared_cost_units": declared_cost_units,
        "value_units": value_units,
        "risk_units": risk_units,
        "priority": priority,
        "submitted_at": submitted_at,
    }
    provisional = EconomicVerificationCandidate(**fields, candidate_hash="0" * 64)
    candidate = EconomicVerificationCandidate(**fields, candidate_hash=_digest(provisional.material()))
    candidate.validate()
    return candidate


@dataclass(frozen=True)
class VerificationEconomyPolicy:
    policy_ref: str
    budget_units: int
    max_funded_items: int
    bootstrap_cost_units: int
    min_samples_for_confidence: int
    uncertainty_premium_units: int
    value_weight: int
    risk_weight: int
    priority_weight: int
    aging_quantum: int
    policy_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-economy-policy/v1.8",
            "policy_ref": self.policy_ref,
            "budget_units": self.budget_units,
            "max_funded_items": self.max_funded_items,
            "bootstrap_cost_units": self.bootstrap_cost_units,
            "min_samples_for_confidence": self.min_samples_for_confidence,
            "uncertainty_premium_units": self.uncertainty_premium_units,
            "value_weight": self.value_weight,
            "risk_weight": self.risk_weight,
            "priority_weight": self.priority_weight,
            "aging_quantum": self.aging_quantum,
        }

    def validate(self) -> None:
        if not self.policy_ref:
            raise ValueError("policy_ref is required")
        if self.budget_units < 0 or self.max_funded_items < 0:
            raise ValueError("budget limits must be >= 0")
        if self.bootstrap_cost_units <= 0 or self.min_samples_for_confidence < 0 or self.uncertainty_premium_units < 0:
            raise ValueError("invalid estimator policy")
        if min(self.value_weight, self.risk_weight, self.priority_weight) < 0:
            raise ValueError("weights must be >= 0")
        if self.aging_quantum <= 0:
            raise ValueError("aging_quantum must be > 0")
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match economy policy material")


def make_verification_economy_policy(
    policy_ref: str = "atman:verification-economy:default:v1.8",
    *,
    budget_units: int,
    max_funded_items: int,
    bootstrap_cost_units: int = 10,
    min_samples_for_confidence: int = 3,
    uncertainty_premium_units: int = 2,
    value_weight: int = 1,
    risk_weight: int = 2,
    priority_weight: int = 1,
    aging_quantum: int = 60,
) -> VerificationEconomyPolicy:
    fields = {
        "policy_ref": policy_ref,
        "budget_units": budget_units,
        "max_funded_items": max_funded_items,
        "bootstrap_cost_units": bootstrap_cost_units,
        "min_samples_for_confidence": min_samples_for_confidence,
        "uncertainty_premium_units": uncertainty_premium_units,
        "value_weight": value_weight,
        "risk_weight": risk_weight,
        "priority_weight": priority_weight,
        "aging_quantum": aging_quantum,
    }
    provisional = VerificationEconomyPolicy(**fields, policy_hash="0" * 64)
    policy = VerificationEconomyPolicy(**fields, policy_hash=_digest(provisional.material()))
    policy.validate()
    return policy


def estimated_cost_units(
    candidate: EconomicVerificationCandidate,
    estimator: CostEstimatorSnapshot | None,
    policy: VerificationEconomyPolicy,
) -> int:
    candidate.validate()
    policy.validate()
    if estimator is None or estimator.sample_count == 0:
        base = policy.bootstrap_cost_units
        samples = 0
    else:
        estimator.validate()
        if estimator.estimator_key != candidate.estimator_key:
            raise ValueError("estimator key mismatch")
        base = estimator.mean_cost_units
        samples = estimator.sample_count
    premium = policy.uncertainty_premium_units if samples < policy.min_samples_for_confidence else 0
    return max(1, base + premium)


def _utility(candidate: EconomicVerificationCandidate, policy: VerificationEconomyPolicy, measured_at: int) -> int:
    waited = max(0, measured_at - candidate.submitted_at)
    age_bonus = waited // policy.aging_quantum
    return (
        candidate.value_units * policy.value_weight
        + candidate.risk_units * policy.risk_weight
        + candidate.priority * policy.priority_weight
        + age_bonus
    )


@dataclass(frozen=True)
class VerificationBudgetAllocationReceipt:
    policy_hash: str
    measured_at: int
    candidate_hashes: tuple[str, ...]
    estimator_snapshot_hashes: tuple[str, ...]
    estimated_costs: tuple[tuple[str, int], ...]
    ranked_candidate_hashes: tuple[str, ...]
    funded_candidate_hashes: tuple[str, ...]
    deferred_budget_candidate_hashes: tuple[str, ...]
    deferred_oversized_candidate_hashes: tuple[str, ...]
    used_budget_units: int
    budget_units: int
    budget_status: BudgetStatus
    allocation_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-budget-allocation/v1.8",
            "policy_hash": self.policy_hash,
            "measured_at": self.measured_at,
            "candidate_hashes": list(self.candidate_hashes),
            "estimator_snapshot_hashes": list(self.estimator_snapshot_hashes),
            "estimated_costs": [[key, value] for key, value in self.estimated_costs],
            "ranked_candidate_hashes": list(self.ranked_candidate_hashes),
            "funded_candidate_hashes": list(self.funded_candidate_hashes),
            "deferred_budget_candidate_hashes": list(self.deferred_budget_candidate_hashes),
            "deferred_oversized_candidate_hashes": list(self.deferred_oversized_candidate_hashes),
            "used_budget_units": self.used_budget_units,
            "budget_units": self.budget_units,
            "budget_status": self.budget_status,
        }

    def validate(self) -> None:
        _require_digest("policy_hash", self.policy_hash)
        _require_digest("allocation_hash", self.allocation_hash)
        if self.measured_at < 0 or self.used_budget_units < 0 or self.budget_units < 0 or self.used_budget_units > self.budget_units:
            raise ValueError("invalid budget accounting")
        if self.budget_status not in {"NORMAL", "PRESSURED", "SATURATED"}:
            raise ValueError("invalid budget_status")
        for collection in (
            self.candidate_hashes,
            self.estimator_snapshot_hashes,
            self.ranked_candidate_hashes,
            self.funded_candidate_hashes,
            self.deferred_budget_candidate_hashes,
            self.deferred_oversized_candidate_hashes,
        ):
            for value in collection:
                _require_digest("digest", value)
            if len(set(collection)) != len(collection):
                raise ValueError("duplicate digest in allocation receipt")
        candidate_set = set(self.candidate_hashes)
        funded = set(self.funded_candidate_hashes)
        deferred_budget = set(self.deferred_budget_candidate_hashes)
        deferred_oversized = set(self.deferred_oversized_candidate_hashes)
        if set(self.ranked_candidate_hashes) != candidate_set:
            raise ValueError("ranking must exactly cover candidates")
        if funded & deferred_budget or funded & deferred_oversized or deferred_budget & deferred_oversized:
            raise ValueError("allocation dispositions must be disjoint")
        if funded | deferred_budget | deferred_oversized != candidate_set:
            raise ValueError("allocation dispositions must exactly cover candidates")
        estimated_keys = [key for key, value in self.estimated_costs]
        if set(estimated_keys) != candidate_set or len(estimated_keys) != len(candidate_set):
            raise ValueError("estimated costs must exactly cover candidates")
        if any(value <= 0 for _, value in self.estimated_costs):
            raise ValueError("estimated cost must be > 0")
        expected_status: BudgetStatus
        if not deferred_budget and not deferred_oversized:
            expected_status = "NORMAL"
        elif funded:
            expected_status = "PRESSURED"
        else:
            expected_status = "SATURATED"
        if self.budget_status != expected_status:
            raise ValueError("budget_status does not match allocation")
        if self.allocation_hash != _digest(self.material()):
            raise ValueError("allocation_hash does not match allocation material")


def allocate_verification_budget(
    candidates: Iterable[EconomicVerificationCandidate],
    estimators: Mapping[str, CostEstimatorSnapshot],
    policy: VerificationEconomyPolicy,
    *,
    measured_at: int,
) -> VerificationBudgetAllocationReceipt:
    policy.validate()
    if measured_at < 0:
        raise ValueError("measured_at must be >= 0")
    items = tuple(candidates)
    seen_work: set[str] = set()
    seen_candidates: set[str] = set()
    for item in items:
        item.validate()
        if item.work_hash in seen_work or item.candidate_hash in seen_candidates:
            raise ValueError("duplicate economic candidate")
        seen_work.add(item.work_hash)
        seen_candidates.add(item.candidate_hash)
    for key, estimator in estimators.items():
        estimator.validate()
        if key != estimator.estimator_key:
            raise ValueError("estimator mapping key mismatch")

    costs = {
        item.candidate_hash: estimated_cost_units(item, estimators.get(item.estimator_key), policy)
        for item in items
    }

    def ranking_key(item: EconomicVerificationCandidate) -> tuple[int, int, int, str]:
        cost = costs[item.candidate_hash]
        utility = _utility(item, policy, measured_at)
        efficiency_scaled = utility * 1_000_000 // cost
        return (-efficiency_scaled, -utility, item.submitted_at, item.candidate_hash)

    ranked = tuple(sorted(items, key=ranking_key))
    funded: list[str] = []
    deferred_budget: list[str] = []
    deferred_oversized: list[str] = []
    used = 0
    for item in ranked:
        cost = costs[item.candidate_hash]
        if cost > policy.budget_units:
            deferred_oversized.append(item.candidate_hash)
            continue
        if len(funded) >= policy.max_funded_items or used + cost > policy.budget_units:
            deferred_budget.append(item.candidate_hash)
            continue
        funded.append(item.candidate_hash)
        used += cost

    if not deferred_budget and not deferred_oversized:
        status: BudgetStatus = "NORMAL"
    elif funded:
        status = "PRESSURED"
    else:
        status = "SATURATED"

    used_estimator_hashes = tuple(sorted({
        estimators[item.estimator_key].snapshot_hash
        for item in items
        if item.estimator_key in estimators
    }))
    fields = {
        "policy_hash": policy.policy_hash,
        "measured_at": measured_at,
        "candidate_hashes": tuple(sorted(item.candidate_hash for item in items)),
        "estimator_snapshot_hashes": used_estimator_hashes,
        "estimated_costs": tuple(sorted(costs.items())),
        "ranked_candidate_hashes": tuple(item.candidate_hash for item in ranked),
        "funded_candidate_hashes": tuple(funded),
        "deferred_budget_candidate_hashes": tuple(deferred_budget),
        "deferred_oversized_candidate_hashes": tuple(deferred_oversized),
        "used_budget_units": used,
        "budget_units": policy.budget_units,
        "budget_status": status,
    }
    provisional = VerificationBudgetAllocationReceipt(**fields, allocation_hash="0" * 64)
    receipt = VerificationBudgetAllocationReceipt(**fields, allocation_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt
