from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from model.calibration import DependencyPairSample, binary_brier_score_ppm
from model.dependency_graph_revision import DependencyGraphState
from model.search_budget import (
    HeldOutSearchReservation,
    SearchAdjustedValidationReceipt,
    SearchBudgetSelectionReceipt,
    SearchBudgetSelectionReviewReceipt,
    SearchBudgetedGraphRevisionReceipt,
    apply_search_budgeted_selection,
)
from model.structural_validation import HeldOutStructuralValidationReceipt, StructuralValidationCandidate, StructuralValidationPolicy

FinalConfirmationStatus = Literal["INSUFFICIENT_FINAL_HOLDOUT", "FINAL_REJECTED", "FINAL_CONFIRMED"]


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _round_ratio(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be > 0")
    return (numerator + denominator // 2) // denominator


@dataclass(frozen=True)
class ProtectedFinalHoldoutPolicy:
    policy_ref: str
    subject_identity_ref: str
    min_final_samples: int
    min_final_regularized_improvement_ppm: int
    registered_at: int
    policy_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/protected-final-holdout-policy/v1.17",
            "policy_ref": self.policy_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "min_final_samples": self.min_final_samples,
            "min_final_regularized_improvement_ppm": self.min_final_regularized_improvement_ppm,
            "registered_at": self.registered_at,
        }

    def validate(self) -> None:
        if not self.policy_ref or not self.subject_identity_ref:
            raise ValueError("protected final holdout policy refs are required")
        if self.min_final_samples < 1 or self.min_final_regularized_improvement_ppm < 0 or self.registered_at < 0:
            raise ValueError("invalid protected final holdout policy")
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match protected final holdout policy")


def make_protected_final_holdout_policy(
    *,
    policy_ref: str,
    subject_identity_ref: str,
    min_final_samples: int = 4,
    min_final_regularized_improvement_ppm: int = 0,
    registered_at: int,
) -> ProtectedFinalHoldoutPolicy:
    fields = {
        "policy_ref": policy_ref,
        "subject_identity_ref": subject_identity_ref,
        "min_final_samples": min_final_samples,
        "min_final_regularized_improvement_ppm": min_final_regularized_improvement_ppm,
        "registered_at": registered_at,
    }
    provisional = ProtectedFinalHoldoutPolicy(**fields, policy_hash="0" * 64)
    result = ProtectedFinalHoldoutPolicy(**fields, policy_hash=_digest(provisional.material()))
    result.validate()
    return result


def protected_sample_commitment(samples: tuple[DependencyPairSample, ...]) -> str:
    if not samples:
        raise ValueError("protected final holdout requires samples")
    for sample in samples:
        sample.validate()
    pair_key = samples[0].pair_key
    if any(sample.pair_key != pair_key for sample in samples):
        raise ValueError("protected final holdout samples must share one pair key")
    hashes = tuple(sorted(sample.sample_hash for sample in samples))
    if len(set(hashes)) != len(hashes):
        raise ValueError("protected final holdout samples must be unique")
    return _digest({
        "domain": "ATMAN-LATTICE/protected-final-sample-commitment/v1.17",
        "pair_key": pair_key,
        "sample_hashes": list(hashes),
    })


@dataclass(frozen=True)
class ProtectedFinalHoldoutSeal:
    pool_ref: str
    subject_identity_ref: str
    pair_key: str
    policy_hash: str
    generation: int
    sample_count: int
    sample_commitment: str
    previous_pool_hash: str | None
    keeper_ref: str
    sealed_at: int
    pool_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/protected-final-holdout-seal/v1.17",
            "pool_ref": self.pool_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "pair_key": self.pair_key,
            "policy_hash": self.policy_hash,
            "generation": self.generation,
            "sample_count": self.sample_count,
            "sample_commitment": self.sample_commitment,
            "previous_pool_hash": self.previous_pool_hash,
            "keeper_ref": self.keeper_ref,
            "sealed_at": self.sealed_at,
        }

    def validate(self) -> None:
        if not self.pool_ref or not self.subject_identity_ref or not self.keeper_ref:
            raise ValueError("protected final holdout seal refs are required")
        for name, value in (("pair_key", self.pair_key), ("policy_hash", self.policy_hash), ("sample_commitment", self.sample_commitment), ("pool_hash", self.pool_hash)):
            _require_digest(name, value)
        if self.previous_pool_hash is not None:
            _require_digest("previous_pool_hash", self.previous_pool_hash)
        if self.generation < 0 or self.sample_count < 1 or self.sealed_at < 0:
            raise ValueError("invalid protected final holdout generation/count/time")
        if self.pool_hash != _digest(self.material()):
            raise ValueError("pool_hash does not match protected final holdout seal")


def make_protected_final_holdout_seal(
    *,
    pool_ref: str,
    subject_identity_ref: str,
    samples: tuple[DependencyPairSample, ...],
    policy: ProtectedFinalHoldoutPolicy,
    generation: int,
    previous_pool: ProtectedFinalHoldoutSeal | None,
    keeper_ref: str,
    sealed_at: int,
) -> ProtectedFinalHoldoutSeal:
    policy.validate()
    if subject_identity_ref != policy.subject_identity_ref:
        raise ValueError("protected pool policy/subject mismatch")
    if not samples:
        raise ValueError("protected final holdout requires samples")
    for sample in samples:
        sample.validate()
    if any(sample.pair_key != samples[0].pair_key for sample in samples):
        raise ValueError("protected final holdout samples must share one pair key")
    if previous_pool is None:
        if generation != 0:
            raise ValueError("first protected holdout pool must be generation 0")
        previous_hash = None
    else:
        previous_pool.validate()
        if previous_pool.subject_identity_ref != subject_identity_ref or previous_pool.pair_key != samples[0].pair_key or previous_pool.policy_hash != policy.policy_hash:
            raise ValueError("protected holdout rotation lineage mismatch")
        if generation != previous_pool.generation + 1:
            raise ValueError("protected holdout generation must advance exactly once")
        previous_hash = previous_pool.pool_hash
    if sealed_at < policy.registered_at:
        raise ValueError("protected final pool cannot predate policy")
    fields = {
        "pool_ref": pool_ref,
        "subject_identity_ref": subject_identity_ref,
        "pair_key": samples[0].pair_key,
        "policy_hash": policy.policy_hash,
        "generation": generation,
        "sample_count": len(samples),
        "sample_commitment": protected_sample_commitment(samples),
        "previous_pool_hash": previous_hash,
        "keeper_ref": keeper_ref,
        "sealed_at": sealed_at,
    }
    provisional = ProtectedFinalHoldoutSeal(**fields, pool_hash="0" * 64)
    result = ProtectedFinalHoldoutSeal(**fields, pool_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class FinalConfirmationCase:
    sample_hash: str
    parent_positive: bool
    child_positive: bool
    base_predicted_positive_bps: int
    proposed_predicted_positive_bps: int
    base_brier_score_ppm: int
    proposed_brier_score_ppm: int
    case_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/final-confirmation-case/v1.17",
            "sample_hash": self.sample_hash,
            "parent_positive": self.parent_positive,
            "child_positive": self.child_positive,
            "base_predicted_positive_bps": self.base_predicted_positive_bps,
            "proposed_predicted_positive_bps": self.proposed_predicted_positive_bps,
            "base_brier_score_ppm": self.base_brier_score_ppm,
            "proposed_brier_score_ppm": self.proposed_brier_score_ppm,
        }

    def validate(self) -> None:
        _require_digest("sample_hash", self.sample_hash)
        _require_digest("case_hash", self.case_hash)
        for value in (self.base_predicted_positive_bps, self.proposed_predicted_positive_bps):
            if value < 0 or value > 10_000:
                raise ValueError("final confirmation prediction must be 0..10000 basis points")
        for value in (self.base_brier_score_ppm, self.proposed_brier_score_ppm):
            if value < 0 or value > 1_000_000:
                raise ValueError("final confirmation Brier score must be 0..1000000 ppm")
        if self.case_hash != _digest(self.material()):
            raise ValueError("case_hash does not match final confirmation case")


@dataclass(frozen=True)
class EvaluationExposureLineageReceipt:
    candidate_hash: str
    discovery_sample_hashes: tuple[str, ...]
    validation_sample_hashes: tuple[str, ...]
    search_reservation_hash: str
    search_evaluation_hash: str
    search_selection_hash: str
    search_family_reservation_hashes: tuple[str, ...]
    final_pool_hash: str
    final_case_hashes: tuple[str, ...]
    lineage_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/evaluation-exposure-lineage/v1.17",
            "candidate_hash": self.candidate_hash,
            "discovery_sample_hashes": list(self.discovery_sample_hashes),
            "validation_sample_hashes": list(self.validation_sample_hashes),
            "search_reservation_hash": self.search_reservation_hash,
            "search_evaluation_hash": self.search_evaluation_hash,
            "search_selection_hash": self.search_selection_hash,
            "search_family_reservation_hashes": list(self.search_family_reservation_hashes),
            "final_pool_hash": self.final_pool_hash,
            "final_case_hashes": list(self.final_case_hashes),
        }

    def validate(self) -> None:
        for name, value in (("candidate_hash", self.candidate_hash), ("search_reservation_hash", self.search_reservation_hash), ("search_evaluation_hash", self.search_evaluation_hash), ("search_selection_hash", self.search_selection_hash), ("final_pool_hash", self.final_pool_hash), ("lineage_hash", self.lineage_hash)):
            _require_digest(name, value)
        for value in self.discovery_sample_hashes + self.validation_sample_hashes + self.search_family_reservation_hashes + self.final_case_hashes:
            _require_digest("exposure_lineage_hash_component", value)
        if set(self.discovery_sample_hashes) & set(self.validation_sample_hashes):
            raise ValueError("discovery and validation exposure sets must be disjoint")
        if (set(self.discovery_sample_hashes) | set(self.validation_sample_hashes)) & set(self.final_case_hashes):
            raise ValueError("final confirmation cannot reuse discovery/validation evidence")
        if self.lineage_hash != _digest(self.material()):
            raise ValueError("lineage_hash does not match evaluation exposure lineage")


@dataclass(frozen=True)
class FinalConfirmationReceipt:
    selection_hash: str
    review_hash: str
    candidate_hash: str
    search_evaluation_hash: str
    pool_hash: str
    pool_generation: int
    lineage_hash: str
    evaluated_case_count: int
    min_final_samples: int
    base_mean_brier_ppm: int | None
    proposed_mean_brier_ppm: int | None
    base_edge_count: int
    proposed_edge_count: int
    edge_penalty_ppm: int
    base_regularized_brier_ppm: int | None
    proposed_regularized_brier_ppm: int | None
    regularized_improvement_ppm: int | None
    min_final_regularized_improvement_ppm: int
    status: FinalConfirmationStatus
    pool_keeper_ref: str
    confirmer_ref: str
    confirmed_at: int
    confirmation_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/final-confirmation/v1.17",
            "selection_hash": self.selection_hash,
            "review_hash": self.review_hash,
            "candidate_hash": self.candidate_hash,
            "search_evaluation_hash": self.search_evaluation_hash,
            "pool_hash": self.pool_hash,
            "pool_generation": self.pool_generation,
            "lineage_hash": self.lineage_hash,
            "evaluated_case_count": self.evaluated_case_count,
            "min_final_samples": self.min_final_samples,
            "base_mean_brier_ppm": self.base_mean_brier_ppm,
            "proposed_mean_brier_ppm": self.proposed_mean_brier_ppm,
            "base_edge_count": self.base_edge_count,
            "proposed_edge_count": self.proposed_edge_count,
            "edge_penalty_ppm": self.edge_penalty_ppm,
            "base_regularized_brier_ppm": self.base_regularized_brier_ppm,
            "proposed_regularized_brier_ppm": self.proposed_regularized_brier_ppm,
            "regularized_improvement_ppm": self.regularized_improvement_ppm,
            "min_final_regularized_improvement_ppm": self.min_final_regularized_improvement_ppm,
            "status": self.status,
            "pool_keeper_ref": self.pool_keeper_ref,
            "confirmer_ref": self.confirmer_ref,
            "confirmed_at": self.confirmed_at,
        }

    def validate(self) -> None:
        for name, value in (("selection_hash", self.selection_hash), ("review_hash", self.review_hash), ("candidate_hash", self.candidate_hash), ("search_evaluation_hash", self.search_evaluation_hash), ("pool_hash", self.pool_hash), ("lineage_hash", self.lineage_hash), ("confirmation_hash", self.confirmation_hash)):
            _require_digest(name, value)
        if self.pool_generation < 0 or self.evaluated_case_count < 0 or self.min_final_samples < 1:
            raise ValueError("invalid final confirmation counts")
        if self.base_edge_count < 0 or self.proposed_edge_count < 0 or self.edge_penalty_ppm < 0 or self.min_final_regularized_improvement_ppm < 0:
            raise ValueError("invalid final confirmation thresholds")
        if not self.pool_keeper_ref or not self.confirmer_ref or self.pool_keeper_ref == self.confirmer_ref or self.confirmed_at < 0:
            raise ValueError("final confirmer must be independent from protected pool keeper")
        if self.status == "INSUFFICIENT_FINAL_HOLDOUT":
            if self.evaluated_case_count >= self.min_final_samples:
                raise ValueError("insufficient final holdout requires too few cases")
        else:
            values = (self.base_mean_brier_ppm, self.proposed_mean_brier_ppm, self.base_regularized_brier_ppm, self.proposed_regularized_brier_ppm, self.regularized_improvement_ppm)
            if self.evaluated_case_count < self.min_final_samples or any(value is None for value in values):
                raise ValueError("complete final confirmation requires metrics")
            if self.base_regularized_brier_ppm != self.base_mean_brier_ppm + self.edge_penalty_ppm * self.base_edge_count:
                raise ValueError("final base regularized score mismatch")
            if self.proposed_regularized_brier_ppm != self.proposed_mean_brier_ppm + self.edge_penalty_ppm * self.proposed_edge_count:
                raise ValueError("final proposed regularized score mismatch")
            if self.regularized_improvement_ppm != self.base_regularized_brier_ppm - self.proposed_regularized_brier_ppm:
                raise ValueError("final regularized improvement mismatch")
            if self.status == "FINAL_CONFIRMED" and self.regularized_improvement_ppm <= self.min_final_regularized_improvement_ppm:
                raise ValueError("FINAL_CONFIRMED requires improvement above final threshold")
            if self.status == "FINAL_REJECTED" and self.regularized_improvement_ppm > self.min_final_regularized_improvement_ppm:
                raise ValueError("FINAL_REJECTED cannot exceed final threshold")
        if self.confirmation_hash != _digest(self.material()):
            raise ValueError("confirmation_hash does not match final confirmation")


def _edge_present(graph: DependencyGraphState, parent: str, child: str) -> bool:
    return any(edge.parent_model_ref == parent and edge.child_model_ref == child for edge in graph.edges)


def _prediction(training: tuple[tuple[bool, bool], ...], *, conditional: bool, parent_positive: bool) -> int | None:
    population = tuple(child for parent, child in training if (not conditional or parent == parent_positive))
    if not population:
        return None
    return _round_ratio(10_000 * sum(1 for child in population if child), len(population))


def confirm_on_protected_holdout(
    *,
    candidate: StructuralValidationCandidate,
    reservation: HeldOutSearchReservation,
    search_evaluation: SearchAdjustedValidationReceipt,
    selection: SearchBudgetSelectionReceipt,
    review: SearchBudgetSelectionReviewReceipt,
    base_graph: DependencyGraphState,
    exposed_samples: tuple[DependencyPairSample, ...],
    protected_samples: tuple[DependencyPairSample, ...],
    structural_policy: StructuralValidationPolicy,
    final_policy: ProtectedFinalHoldoutPolicy,
    pool: ProtectedFinalHoldoutSeal,
    confirmer_ref: str,
    confirmed_at: int,
) -> tuple[tuple[FinalConfirmationCase, ...], EvaluationExposureLineageReceipt, FinalConfirmationReceipt]:
    candidate.validate(); reservation.validate(); search_evaluation.validate(); selection.validate(); review.validate(); base_graph.validate(); structural_policy.validate(); final_policy.validate(); pool.validate()
    if selection.status != "SELECTED" or selection.selected_candidate_hash != candidate.candidate_hash or selection.selected_evaluation_hash != search_evaluation.evaluation_hash:
        raise ValueError("final confirmation requires exact selected search-budget winner")
    if search_evaluation.status != "SEARCH_CORRECTED_IMPROVED" or search_evaluation.reservation_hash != reservation.reservation_hash:
        raise ValueError("final confirmation requires search-corrected held-out improvement")
    if review.selection_hash != selection.selection_hash or review.selected_candidate_hash != candidate.candidate_hash or review.decision != "APPROVE":
        raise ValueError("final confirmation requires approved search selection")
    if candidate.proposal.base_graph_hash != base_graph.graph_hash or selection.base_graph_hash != base_graph.graph_hash:
        raise ValueError("final confirmation base graph is stale")
    if pool.subject_identity_ref != candidate.subject_identity_ref or pool.pair_key != candidate.pair_key or pool.policy_hash != final_policy.policy_hash:
        raise ValueError("protected final pool context mismatch")
    if pool.sealed_at > selection.selected_at:
        raise ValueError("protected final pool must be sealed before model selection")
    if confirmer_ref in {pool.keeper_ref, candidate.proposer_ref, selection.selector_ref, review.reviewer_ref, search_evaluation.evaluator_ref}:
        raise ValueError("final confirmer must be independent from search/model actors")
    if protected_sample_commitment(protected_samples) != pool.sample_commitment or len(protected_samples) != pool.sample_count:
        raise ValueError("protected final samples do not match sealed pool")
    for sample in exposed_samples + protected_samples:
        sample.validate()
    if not exposed_samples or any(sample.pair_key != candidate.pair_key for sample in exposed_samples):
        raise ValueError("exposed training history must match candidate pair")
    if any(sample.pair_key != candidate.pair_key for sample in protected_samples):
        raise ValueError("protected final samples must match candidate pair")
    exposed_hashes = {sample.sample_hash for sample in exposed_samples}
    protected_hashes = {sample.sample_hash for sample in protected_samples}
    if exposed_hashes & protected_hashes:
        raise ValueError("new split is not fresh evidence: final holdout reuses exposed samples")
    candidate_exposed = set(candidate.selection_sample_hashes) | set(candidate.evaluation_sample_hashes)
    if candidate_exposed != exposed_hashes:
        raise ValueError("final confirmation training history must exactly match candidate exposure history")
    left_ref = exposed_samples[0].left_model_ref
    right_ref = exposed_samples[0].right_model_ref
    if candidate.proposal.direction == "LEFT_TO_RIGHT":
        parent_ref, child_ref = left_ref, right_ref
        training = tuple((item.left_positive, item.right_positive) for item in exposed_samples)
        final_rows = tuple((item.left_positive, item.right_positive, item.sample_hash) for item in protected_samples)
    else:
        parent_ref, child_ref = right_ref, left_ref
        training = tuple((item.right_positive, item.left_positive) for item in exposed_samples)
        final_rows = tuple((item.right_positive, item.left_positive, item.sample_hash) for item in protected_samples)
    if parent_ref != candidate.proposal.parent_model_ref or child_ref != candidate.proposal.child_model_ref:
        raise ValueError("final confirmation orientation mismatch")
    base_conditional = _edge_present(base_graph, parent_ref, child_ref)
    proposed_conditional = any(edge.parent_model_ref == parent_ref and edge.child_model_ref == child_ref for edge in candidate.proposal.proposed_edges)
    cases: list[FinalConfirmationCase] = []
    for parent_positive, child_positive, sample_hash in final_rows:
        base_prediction = _prediction(training, conditional=base_conditional, parent_positive=parent_positive)
        proposed_prediction = _prediction(training, conditional=proposed_conditional, parent_positive=parent_positive)
        if base_prediction is None or proposed_prediction is None:
            continue
        fields = {
            "sample_hash": sample_hash,
            "parent_positive": parent_positive,
            "child_positive": child_positive,
            "base_predicted_positive_bps": base_prediction,
            "proposed_predicted_positive_bps": proposed_prediction,
            "base_brier_score_ppm": binary_brier_score_ppm(base_prediction, child_positive),
            "proposed_brier_score_ppm": binary_brier_score_ppm(proposed_prediction, child_positive),
        }
        provisional = FinalConfirmationCase(**fields, case_hash="0" * 64)
        case = FinalConfirmationCase(**fields, case_hash=_digest(provisional.material()))
        case.validate(); cases.append(case)
    cases_tuple = tuple(sorted(cases, key=lambda item: item.case_hash))
    lineage_fields = {
        "candidate_hash": candidate.candidate_hash,
        "discovery_sample_hashes": candidate.selection_sample_hashes,
        "validation_sample_hashes": candidate.evaluation_sample_hashes,
        "search_reservation_hash": reservation.reservation_hash,
        "search_evaluation_hash": search_evaluation.evaluation_hash,
        "search_selection_hash": selection.selection_hash,
        "search_family_reservation_hashes": selection.family_reservation_hashes,
        "final_pool_hash": pool.pool_hash,
        "final_case_hashes": tuple(item.sample_hash for item in cases_tuple),
    }
    lineage_provisional = EvaluationExposureLineageReceipt(**lineage_fields, lineage_hash="0" * 64)
    lineage = EvaluationExposureLineageReceipt(**lineage_fields, lineage_hash=_digest(lineage_provisional.material()))
    lineage.validate()
    n = len(cases_tuple)
    if n < final_policy.min_final_samples:
        base_mean = proposed_mean = base_reg = proposed_reg = improvement = None
        status: FinalConfirmationStatus = "INSUFFICIENT_FINAL_HOLDOUT"
    else:
        base_mean = _round_ratio(sum(item.base_brier_score_ppm for item in cases_tuple), n)
        proposed_mean = _round_ratio(sum(item.proposed_brier_score_ppm for item in cases_tuple), n)
        base_reg = base_mean + structural_policy.edge_penalty_ppm * len(base_graph.edges)
        proposed_reg = proposed_mean + structural_policy.edge_penalty_ppm * len(candidate.proposal.proposed_edges)
        improvement = base_reg - proposed_reg
        status = "FINAL_CONFIRMED" if improvement > final_policy.min_final_regularized_improvement_ppm else "FINAL_REJECTED"
    fields = {
        "selection_hash": selection.selection_hash,
        "review_hash": review.review_hash,
        "candidate_hash": candidate.candidate_hash,
        "search_evaluation_hash": search_evaluation.evaluation_hash,
        "pool_hash": pool.pool_hash,
        "pool_generation": pool.generation,
        "lineage_hash": lineage.lineage_hash,
        "evaluated_case_count": n,
        "min_final_samples": final_policy.min_final_samples,
        "base_mean_brier_ppm": base_mean,
        "proposed_mean_brier_ppm": proposed_mean,
        "base_edge_count": len(base_graph.edges),
        "proposed_edge_count": len(candidate.proposal.proposed_edges),
        "edge_penalty_ppm": structural_policy.edge_penalty_ppm,
        "base_regularized_brier_ppm": base_reg,
        "proposed_regularized_brier_ppm": proposed_reg,
        "regularized_improvement_ppm": improvement,
        "min_final_regularized_improvement_ppm": final_policy.min_final_regularized_improvement_ppm,
        "status": status,
        "pool_keeper_ref": pool.keeper_ref,
        "confirmer_ref": confirmer_ref,
        "confirmed_at": confirmed_at,
    }
    provisional = FinalConfirmationReceipt(**fields, confirmation_hash="0" * 64)
    receipt = FinalConfirmationReceipt(**fields, confirmation_hash=_digest(provisional.material()))
    receipt.validate()
    return cases_tuple, lineage, receipt


@dataclass(frozen=True)
class FinalConfirmedGraphRevisionReceipt:
    selection_hash: str
    confirmation_hash: str
    lineage_hash: str
    underlying_search_revision_hash: str
    base_graph_hash: str
    new_graph_hash: str
    base_generation: int
    new_generation: int
    applier_ref: str
    applied_at: int
    revision_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/final-confirmed-graph-revision/v1.17",
            "selection_hash": self.selection_hash,
            "confirmation_hash": self.confirmation_hash,
            "lineage_hash": self.lineage_hash,
            "underlying_search_revision_hash": self.underlying_search_revision_hash,
            "base_graph_hash": self.base_graph_hash,
            "new_graph_hash": self.new_graph_hash,
            "base_generation": self.base_generation,
            "new_generation": self.new_generation,
            "applier_ref": self.applier_ref,
            "applied_at": self.applied_at,
        }

    def validate(self) -> None:
        for name, value in (("selection_hash", self.selection_hash), ("confirmation_hash", self.confirmation_hash), ("lineage_hash", self.lineage_hash), ("underlying_search_revision_hash", self.underlying_search_revision_hash), ("base_graph_hash", self.base_graph_hash), ("new_graph_hash", self.new_graph_hash), ("revision_hash", self.revision_hash)):
            _require_digest(name, value)
        if self.new_generation != self.base_generation + 1 or not self.applier_ref or self.applied_at < 0:
            raise ValueError("invalid final-confirmed graph revision metadata")
        if self.revision_hash != _digest(self.material()):
            raise ValueError("revision_hash does not match final-confirmed graph revision")


def apply_final_confirmed_selection(
    *,
    current_graph: DependencyGraphState,
    candidate: StructuralValidationCandidate,
    reservation: HeldOutSearchReservation,
    underlying_validation: HeldOutStructuralValidationReceipt,
    search_evaluation: SearchAdjustedValidationReceipt,
    selection: SearchBudgetSelectionReceipt,
    review: SearchBudgetSelectionReviewReceipt,
    confirmation: FinalConfirmationReceipt,
    applier_ref: str,
    applied_at: int,
) -> tuple[DependencyGraphState, FinalConfirmedGraphRevisionReceipt]:
    confirmation.validate()
    if confirmation.status != "FINAL_CONFIRMED":
        raise ValueError("final-confirmed apply requires FINAL_CONFIRMED receipt")
    if confirmation.selection_hash != selection.selection_hash or confirmation.review_hash != review.review_hash or confirmation.candidate_hash != candidate.candidate_hash or confirmation.search_evaluation_hash != search_evaluation.evaluation_hash:
        raise ValueError("final-confirmed apply chain mismatch")
    if applier_ref in {confirmation.confirmer_ref, confirmation.pool_keeper_ref}:
        raise ValueError("final applier must be independent from holdout keeper and confirmer")
    new_graph, underlying = apply_search_budgeted_selection(
        current_graph=current_graph,
        candidate=candidate,
        reservation=reservation,
        underlying_validation=underlying_validation,
        evaluation=search_evaluation,
        selection=selection,
        review=review,
        applier_ref=applier_ref,
        applied_at=applied_at,
    )
    fields = {
        "selection_hash": selection.selection_hash,
        "confirmation_hash": confirmation.confirmation_hash,
        "lineage_hash": confirmation.lineage_hash,
        "underlying_search_revision_hash": underlying.revision_hash,
        "base_graph_hash": current_graph.graph_hash,
        "new_graph_hash": new_graph.graph_hash,
        "base_generation": current_graph.generation,
        "new_generation": new_graph.generation,
        "applier_ref": applier_ref,
        "applied_at": applied_at,
    }
    provisional = FinalConfirmedGraphRevisionReceipt(**fields, revision_hash="0" * 64)
    receipt = FinalConfirmedGraphRevisionReceipt(**fields, revision_hash=_digest(provisional.material()))
    receipt.validate()
    return new_graph, receipt
