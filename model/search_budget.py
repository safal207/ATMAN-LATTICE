from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from model.calibration import DependencyPairSample
from model.dependency_graph_revision import DependencyGraphState
from model.structural_validation import (
    HeldOutStructuralValidationReceipt,
    StructuralValidationCandidate,
    StructuralValidationPolicy,
    ValidatedDependencyGraphRevisionReceipt,
    apply_validated_structural_selection,
    review_structural_selection,
    select_structural_candidate,
    validate_structural_candidate,
)

SearchEvaluationStatus = Literal[
    "UNDERLYING_HELDOUT_REJECTED",
    "MULTIPLICITY_REJECTED",
    "SEARCH_CORRECTED_IMPROVED",
]
SearchSelectionStatus = Literal["SELECTED", "NO_SEARCH_CORRECTED_CANDIDATE"]
SearchReviewDecision = Literal["APPROVE", "HOLD", "REJECT"]


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class HeldOutSearchBudgetPolicy:
    policy_ref: str
    subject_identity_ref: str
    max_unique_evaluations: int
    base_min_regularized_improvement_ppm: int
    multiplicity_penalty_ppm: int
    registered_at: int
    policy_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/heldout-search-budget-policy/v1.16",
            "policy_ref": self.policy_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "max_unique_evaluations": self.max_unique_evaluations,
            "base_min_regularized_improvement_ppm": self.base_min_regularized_improvement_ppm,
            "multiplicity_penalty_ppm": self.multiplicity_penalty_ppm,
            "registered_at": self.registered_at,
        }

    def validate(self) -> None:
        if not self.policy_ref or not self.subject_identity_ref:
            raise ValueError("search budget policy refs are required")
        if self.max_unique_evaluations < 1:
            raise ValueError("max_unique_evaluations must be >= 1")
        if self.base_min_regularized_improvement_ppm < 0 or self.multiplicity_penalty_ppm < 0 or self.registered_at < 0:
            raise ValueError("search budget thresholds/time must be non-negative")
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match search budget policy")


def make_search_budget_policy(
    *,
    policy_ref: str,
    subject_identity_ref: str,
    max_unique_evaluations: int = 8,
    base_min_regularized_improvement_ppm: int = 0,
    multiplicity_penalty_ppm: int = 10_000,
    registered_at: int,
) -> HeldOutSearchBudgetPolicy:
    fields = {
        "policy_ref": policy_ref,
        "subject_identity_ref": subject_identity_ref,
        "max_unique_evaluations": max_unique_evaluations,
        "base_min_regularized_improvement_ppm": base_min_regularized_improvement_ppm,
        "multiplicity_penalty_ppm": multiplicity_penalty_ppm,
        "registered_at": registered_at,
    }
    provisional = HeldOutSearchBudgetPolicy(**fields, policy_hash="0" * 64)
    result = HeldOutSearchBudgetPolicy(**fields, policy_hash=_digest(provisional.material()))
    result.validate()
    return result


def search_family_hash(candidate: StructuralValidationCandidate, policy: HeldOutSearchBudgetPolicy) -> str:
    candidate.validate()
    policy.validate()
    if candidate.subject_identity_ref != policy.subject_identity_ref:
        raise ValueError("search budget policy/candidate subject mismatch")
    return _digest({
        "domain": "ATMAN-LATTICE/heldout-search-family/v1.16",
        "subject_identity_ref": candidate.subject_identity_ref,
        "pair_key": candidate.pair_key,
        "structural_policy_hash": candidate.policy_hash,
        "search_policy_hash": policy.policy_hash,
    })


def search_context_hash(candidate: StructuralValidationCandidate) -> str:
    candidate.validate()
    return _digest({
        "domain": "ATMAN-LATTICE/heldout-search-context/v1.16",
        "subject_identity_ref": candidate.subject_identity_ref,
        "pair_key": candidate.pair_key,
        "base_graph_hash": candidate.proposal.base_graph_hash,
        "structural_policy_hash": candidate.policy_hash,
        "history_hash": candidate.history_hash,
        "split_hash": candidate.split_hash,
    })


@dataclass(frozen=True)
class HeldOutSearchReservation:
    candidate_hash: str
    family_hash: str
    context_hash: str
    search_policy_hash: str
    ordinal: int
    max_unique_evaluations: int
    effective_min_regularized_improvement_ppm: int
    budget_keeper_ref: str
    reserved_at: int
    reservation_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/heldout-search-reservation/v1.16",
            "candidate_hash": self.candidate_hash,
            "family_hash": self.family_hash,
            "context_hash": self.context_hash,
            "search_policy_hash": self.search_policy_hash,
            "ordinal": self.ordinal,
            "max_unique_evaluations": self.max_unique_evaluations,
            "effective_min_regularized_improvement_ppm": self.effective_min_regularized_improvement_ppm,
            "budget_keeper_ref": self.budget_keeper_ref,
            "reserved_at": self.reserved_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("family_hash", self.family_hash),
            ("context_hash", self.context_hash),
            ("search_policy_hash", self.search_policy_hash),
            ("reservation_hash", self.reservation_hash),
        ):
            _require_digest(name, value)
        if self.ordinal < 1 or self.max_unique_evaluations < 1 or self.ordinal > self.max_unique_evaluations:
            raise ValueError("invalid held-out search reservation ordinal")
        if self.effective_min_regularized_improvement_ppm < 0 or not self.budget_keeper_ref or self.reserved_at < 0:
            raise ValueError("invalid held-out search reservation metadata")
        if self.reservation_hash != _digest(self.material()):
            raise ValueError("reservation_hash does not match held-out search reservation")


def reserve_heldout_search(
    *,
    candidate: StructuralValidationCandidate,
    policy: HeldOutSearchBudgetPolicy,
    prior_reservations: tuple[HeldOutSearchReservation, ...],
    budget_keeper_ref: str,
    reserved_at: int,
) -> HeldOutSearchReservation:
    candidate.validate()
    policy.validate()
    family_hash = search_family_hash(candidate, policy)
    context_hash = search_context_hash(candidate)
    for item in prior_reservations:
        item.validate()
        if item.family_hash != family_hash or item.search_policy_hash != policy.policy_hash:
            raise ValueError("prior search reservations must share one search family")
    existing = next((item for item in prior_reservations if item.candidate_hash == candidate.candidate_hash), None)
    if existing is not None:
        return existing
    ordinals = sorted(item.ordinal for item in prior_reservations)
    if ordinals != list(range(1, len(ordinals) + 1)):
        raise ValueError("search reservation ordinals must be contiguous")
    if len(prior_reservations) >= policy.max_unique_evaluations:
        raise ValueError("held-out search budget exhausted")
    if not budget_keeper_ref or budget_keeper_ref == candidate.proposer_ref:
        raise ValueError("search budget keeper must be independent from candidate proposer")
    ordinal = len(prior_reservations) + 1
    threshold = policy.base_min_regularized_improvement_ppm + policy.multiplicity_penalty_ppm * (ordinal - 1)
    fields = {
        "candidate_hash": candidate.candidate_hash,
        "family_hash": family_hash,
        "context_hash": context_hash,
        "search_policy_hash": policy.policy_hash,
        "ordinal": ordinal,
        "max_unique_evaluations": policy.max_unique_evaluations,
        "effective_min_regularized_improvement_ppm": threshold,
        "budget_keeper_ref": budget_keeper_ref,
        "reserved_at": reserved_at,
    }
    provisional = HeldOutSearchReservation(**fields, reservation_hash="0" * 64)
    result = HeldOutSearchReservation(**fields, reservation_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class SearchAdjustedValidationReceipt:
    candidate_hash: str
    reservation_hash: str
    underlying_validation_hash: str
    family_hash: str
    context_hash: str
    ordinal: int
    effective_min_regularized_improvement_ppm: int
    underlying_status: str
    regularized_improvement_ppm: int | None
    search_adjusted_margin_ppm: int | None
    status: SearchEvaluationStatus
    proposer_ref: str
    budget_keeper_ref: str
    evaluator_ref: str
    evaluated_at: int
    evaluation_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/search-adjusted-validation/v1.16",
            "candidate_hash": self.candidate_hash,
            "reservation_hash": self.reservation_hash,
            "underlying_validation_hash": self.underlying_validation_hash,
            "family_hash": self.family_hash,
            "context_hash": self.context_hash,
            "ordinal": self.ordinal,
            "effective_min_regularized_improvement_ppm": self.effective_min_regularized_improvement_ppm,
            "underlying_status": self.underlying_status,
            "regularized_improvement_ppm": self.regularized_improvement_ppm,
            "search_adjusted_margin_ppm": self.search_adjusted_margin_ppm,
            "status": self.status,
            "proposer_ref": self.proposer_ref,
            "budget_keeper_ref": self.budget_keeper_ref,
            "evaluator_ref": self.evaluator_ref,
            "evaluated_at": self.evaluated_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("reservation_hash", self.reservation_hash),
            ("underlying_validation_hash", self.underlying_validation_hash),
            ("family_hash", self.family_hash),
            ("context_hash", self.context_hash),
            ("evaluation_hash", self.evaluation_hash),
        ):
            _require_digest(name, value)
        if self.ordinal < 1 or self.effective_min_regularized_improvement_ppm < 0:
            raise ValueError("invalid search-adjusted evaluation ordinal/threshold")
        if not self.proposer_ref or not self.budget_keeper_ref or not self.evaluator_ref:
            raise ValueError("search-adjusted evaluation actors are required")
        if self.evaluator_ref in {self.proposer_ref, self.budget_keeper_ref}:
            raise ValueError("search evaluator must be independent from proposer and budget keeper")
        if self.evaluated_at < 0:
            raise ValueError("evaluated_at must be non-negative")
        if self.status == "UNDERLYING_HELDOUT_REJECTED":
            if self.underlying_status == "HELDOUT_IMPROVED":
                raise ValueError("underlying rejection cannot wrap HELDOUT_IMPROVED")
        elif self.status == "MULTIPLICITY_REJECTED":
            if self.underlying_status != "HELDOUT_IMPROVED" or self.regularized_improvement_ppm is None or self.search_adjusted_margin_ppm is None or self.search_adjusted_margin_ppm > 0:
                raise ValueError("multiplicity rejection requires non-positive adjusted margin")
        elif self.status == "SEARCH_CORRECTED_IMPROVED":
            if self.underlying_status != "HELDOUT_IMPROVED" or self.regularized_improvement_ppm is None or self.search_adjusted_margin_ppm is None or self.search_adjusted_margin_ppm <= 0:
                raise ValueError("search-corrected improvement requires positive adjusted margin")
        else:
            raise ValueError("invalid search-adjusted validation status")
        if self.regularized_improvement_ppm is not None:
            if self.search_adjusted_margin_ppm != self.regularized_improvement_ppm - self.effective_min_regularized_improvement_ppm:
                raise ValueError("search-adjusted margin mismatch")
        elif self.search_adjusted_margin_ppm is not None:
            raise ValueError("search-adjusted margin requires underlying improvement")
        if self.evaluation_hash != _digest(self.material()):
            raise ValueError("evaluation_hash does not match search-adjusted validation")


def evaluate_reserved_candidate(
    *,
    candidate: StructuralValidationCandidate,
    reservation: HeldOutSearchReservation,
    base_graph: DependencyGraphState,
    samples: tuple[DependencyPairSample, ...],
    structural_policy: StructuralValidationPolicy,
    search_policy: HeldOutSearchBudgetPolicy,
    evaluator_ref: str,
    evaluated_at: int,
) -> tuple[tuple[object, ...], HeldOutStructuralValidationReceipt, SearchAdjustedValidationReceipt]:
    candidate.validate()
    reservation.validate()
    base_graph.validate()
    structural_policy.validate()
    search_policy.validate()
    if reservation.candidate_hash != candidate.candidate_hash:
        raise ValueError("search reservation/candidate mismatch")
    if reservation.family_hash != search_family_hash(candidate, search_policy) or reservation.context_hash != search_context_hash(candidate):
        raise ValueError("search reservation context is stale")
    if reservation.search_policy_hash != search_policy.policy_hash:
        raise ValueError("search reservation policy mismatch")
    if evaluator_ref in {candidate.proposer_ref, reservation.budget_keeper_ref}:
        raise ValueError("search evaluator must be independent from proposer and budget keeper")
    cases, underlying = validate_structural_candidate(
        candidate=candidate,
        base_graph=base_graph,
        samples=samples,
        policy=structural_policy,
        validator_ref=evaluator_ref,
        validated_at=evaluated_at,
    )
    improvement = underlying.regularized_improvement_ppm
    margin = None if improvement is None else improvement - reservation.effective_min_regularized_improvement_ppm
    if underlying.status != "HELDOUT_IMPROVED":
        status: SearchEvaluationStatus = "UNDERLYING_HELDOUT_REJECTED"
    elif margin is None or margin <= 0:
        status = "MULTIPLICITY_REJECTED"
    else:
        status = "SEARCH_CORRECTED_IMPROVED"
    fields = {
        "candidate_hash": candidate.candidate_hash,
        "reservation_hash": reservation.reservation_hash,
        "underlying_validation_hash": underlying.validation_hash,
        "family_hash": reservation.family_hash,
        "context_hash": reservation.context_hash,
        "ordinal": reservation.ordinal,
        "effective_min_regularized_improvement_ppm": reservation.effective_min_regularized_improvement_ppm,
        "underlying_status": underlying.status,
        "regularized_improvement_ppm": improvement,
        "search_adjusted_margin_ppm": margin,
        "status": status,
        "proposer_ref": candidate.proposer_ref,
        "budget_keeper_ref": reservation.budget_keeper_ref,
        "evaluator_ref": evaluator_ref,
        "evaluated_at": evaluated_at,
    }
    provisional = SearchAdjustedValidationReceipt(**fields, evaluation_hash="0" * 64)
    receipt = SearchAdjustedValidationReceipt(**fields, evaluation_hash=_digest(provisional.material()))
    receipt.validate()
    return tuple(cases), underlying, receipt


@dataclass(frozen=True)
class SearchBudgetSelectionReceipt:
    selection_ref: str
    subject_identity_ref: str
    pair_key: str
    base_graph_hash: str
    structural_policy_hash: str
    search_policy_hash: str
    history_hash: str
    context_hash: str
    family_hash: str
    family_reservation_hashes: tuple[str, ...]
    current_candidate_hashes: tuple[str, ...]
    current_evaluation_hashes: tuple[str, ...]
    budget_used: int
    budget_remaining: int
    selected_candidate_hash: str | None
    selected_evaluation_hash: str | None
    selected_search_adjusted_margin_ppm: int | None
    status: SearchSelectionStatus
    selector_ref: str
    selected_at: int
    selection_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/search-budget-selection/v1.16",
            "selection_ref": self.selection_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "pair_key": self.pair_key,
            "base_graph_hash": self.base_graph_hash,
            "structural_policy_hash": self.structural_policy_hash,
            "search_policy_hash": self.search_policy_hash,
            "history_hash": self.history_hash,
            "context_hash": self.context_hash,
            "family_hash": self.family_hash,
            "family_reservation_hashes": list(self.family_reservation_hashes),
            "current_candidate_hashes": list(self.current_candidate_hashes),
            "current_evaluation_hashes": list(self.current_evaluation_hashes),
            "budget_used": self.budget_used,
            "budget_remaining": self.budget_remaining,
            "selected_candidate_hash": self.selected_candidate_hash,
            "selected_evaluation_hash": self.selected_evaluation_hash,
            "selected_search_adjusted_margin_ppm": self.selected_search_adjusted_margin_ppm,
            "status": self.status,
            "selector_ref": self.selector_ref,
            "selected_at": self.selected_at,
        }

    def validate(self) -> None:
        if not self.selection_ref or not self.subject_identity_ref or not self.selector_ref:
            raise ValueError("search budget selection refs are required")
        for name, value in (
            ("pair_key", self.pair_key),
            ("base_graph_hash", self.base_graph_hash),
            ("structural_policy_hash", self.structural_policy_hash),
            ("search_policy_hash", self.search_policy_hash),
            ("history_hash", self.history_hash),
            ("context_hash", self.context_hash),
            ("family_hash", self.family_hash),
            ("selection_hash", self.selection_hash),
        ):
            _require_digest(name, value)
        for value in self.family_reservation_hashes + self.current_candidate_hashes + self.current_evaluation_hashes:
            _require_digest("search_selection_component", value)
        if tuple(sorted(set(self.family_reservation_hashes))) != self.family_reservation_hashes:
            raise ValueError("family reservation hashes must be unique and sorted")
        if tuple(sorted(set(self.current_candidate_hashes))) != self.current_candidate_hashes or tuple(sorted(set(self.current_evaluation_hashes))) != self.current_evaluation_hashes:
            raise ValueError("current search candidate/evaluation hashes must be unique and sorted")
        if len(self.current_candidate_hashes) != len(self.current_evaluation_hashes) or not self.current_candidate_hashes:
            raise ValueError("search selection requires complete current candidate/evaluation coverage")
        if self.budget_used != len(self.family_reservation_hashes) or self.budget_used < 1 or self.budget_remaining < 0:
            raise ValueError("invalid search budget usage")
        if self.status == "SELECTED":
            if self.selected_candidate_hash is None or self.selected_evaluation_hash is None or self.selected_search_adjusted_margin_ppm is None or self.selected_search_adjusted_margin_ppm <= 0:
                raise ValueError("SELECTED requires positive search-adjusted winner")
            _require_digest("selected_candidate_hash", self.selected_candidate_hash)
            _require_digest("selected_evaluation_hash", self.selected_evaluation_hash)
            if self.selected_candidate_hash not in self.current_candidate_hashes or self.selected_evaluation_hash not in self.current_evaluation_hashes:
                raise ValueError("selected search winner must belong to current set")
        elif self.status == "NO_SEARCH_CORRECTED_CANDIDATE":
            if self.selected_candidate_hash is not None or self.selected_evaluation_hash is not None or self.selected_search_adjusted_margin_ppm is not None:
                raise ValueError("no-winner search selection cannot name a winner")
        else:
            raise ValueError("invalid search budget selection status")
        if self.selected_at < 0 or self.selection_hash != _digest(self.material()):
            raise ValueError("invalid search budget selection material")


def select_search_budget_candidate(
    *,
    selection_ref: str,
    current_candidates: tuple[StructuralValidationCandidate, ...],
    current_evaluations: tuple[SearchAdjustedValidationReceipt, ...],
    all_family_reservations: tuple[HeldOutSearchReservation, ...],
    search_policy: HeldOutSearchBudgetPolicy,
    selector_ref: str,
    selected_at: int,
) -> SearchBudgetSelectionReceipt:
    if not current_candidates or len(current_candidates) != len(current_evaluations):
        raise ValueError("search selection requires matched current candidates/evaluations")
    search_policy.validate()
    for item in current_candidates:
        item.validate()
    for item in current_evaluations:
        item.validate()
    for item in all_family_reservations:
        item.validate()
    first = current_candidates[0]
    family_hash = search_family_hash(first, search_policy)
    context_hash = search_context_hash(first)
    if any(
        item.subject_identity_ref != first.subject_identity_ref
        or item.pair_key != first.pair_key
        or item.policy_hash != first.policy_hash
        or item.history_hash != first.history_hash
        or item.proposal.base_graph_hash != first.proposal.base_graph_hash
        or search_context_hash(item) != context_hash
        for item in current_candidates
    ):
        raise ValueError("current search candidates must share exact structural context")
    if any(item.family_hash != family_hash or item.search_policy_hash != search_policy.policy_hash for item in all_family_reservations):
        raise ValueError("family reservation set mismatch")
    ordinals = sorted(item.ordinal for item in all_family_reservations)
    if ordinals != list(range(1, len(ordinals) + 1)) or len(ordinals) > search_policy.max_unique_evaluations:
        raise ValueError("invalid cumulative search budget state")
    by_candidate = {item.candidate_hash: item for item in current_evaluations}
    if set(by_candidate) != {item.candidate_hash for item in current_candidates}:
        raise ValueError("search evaluation set must exactly cover current candidate set")
    current_reservations = {item.candidate_hash: item for item in all_family_reservations if item.context_hash == context_hash}
    if set(current_reservations) != {item.candidate_hash for item in current_candidates}:
        raise ValueError("current search selection must include every reserved candidate in context")
    eligible: list[tuple[int, str, str]] = []
    for candidate in current_candidates:
        evaluation = by_candidate[candidate.candidate_hash]
        reservation = current_reservations[candidate.candidate_hash]
        if evaluation.reservation_hash != reservation.reservation_hash or evaluation.context_hash != context_hash or evaluation.family_hash != family_hash:
            raise ValueError("search evaluation/reservation context mismatch")
        if evaluation.status == "SEARCH_CORRECTED_IMPROVED":
            eligible.append((int(evaluation.search_adjusted_margin_ppm), candidate.candidate_hash, evaluation.evaluation_hash))
    if eligible:
        margin, candidate_hash, evaluation_hash = sorted(eligible, key=lambda item: (-item[0], item[1]))[0]
        status: SearchSelectionStatus = "SELECTED"
        selected_candidate_hash = candidate_hash
        selected_evaluation_hash = evaluation_hash
        selected_margin = margin
    else:
        status = "NO_SEARCH_CORRECTED_CANDIDATE"
        selected_candidate_hash = selected_evaluation_hash = None
        selected_margin = None
    fields = {
        "selection_ref": selection_ref,
        "subject_identity_ref": first.subject_identity_ref,
        "pair_key": first.pair_key,
        "base_graph_hash": first.proposal.base_graph_hash,
        "structural_policy_hash": first.policy_hash,
        "search_policy_hash": search_policy.policy_hash,
        "history_hash": first.history_hash,
        "context_hash": context_hash,
        "family_hash": family_hash,
        "family_reservation_hashes": tuple(sorted(item.reservation_hash for item in all_family_reservations)),
        "current_candidate_hashes": tuple(sorted(item.candidate_hash for item in current_candidates)),
        "current_evaluation_hashes": tuple(sorted(item.evaluation_hash for item in current_evaluations)),
        "budget_used": len(all_family_reservations),
        "budget_remaining": search_policy.max_unique_evaluations - len(all_family_reservations),
        "selected_candidate_hash": selected_candidate_hash,
        "selected_evaluation_hash": selected_evaluation_hash,
        "selected_search_adjusted_margin_ppm": selected_margin,
        "status": status,
        "selector_ref": selector_ref,
        "selected_at": selected_at,
    }
    provisional = SearchBudgetSelectionReceipt(**fields, selection_hash="0" * 64)
    receipt = SearchBudgetSelectionReceipt(**fields, selection_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class SearchBudgetSelectionReviewReceipt:
    selection_hash: str
    selected_candidate_hash: str | None
    decision: SearchReviewDecision
    rationale_ref: str
    selector_ref: str
    proposer_ref: str | None
    reviewer_ref: str
    reviewed_at: int
    review_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/search-budget-selection-review/v1.16",
            "selection_hash": self.selection_hash,
            "selected_candidate_hash": self.selected_candidate_hash,
            "decision": self.decision,
            "rationale_ref": self.rationale_ref,
            "selector_ref": self.selector_ref,
            "proposer_ref": self.proposer_ref,
            "reviewer_ref": self.reviewer_ref,
            "reviewed_at": self.reviewed_at,
        }

    def validate(self) -> None:
        _require_digest("selection_hash", self.selection_hash)
        _require_digest("review_hash", self.review_hash)
        if self.selected_candidate_hash is not None:
            _require_digest("selected_candidate_hash", self.selected_candidate_hash)
        if self.decision not in {"APPROVE", "HOLD", "REJECT"} or not self.rationale_ref or not self.selector_ref or not self.reviewer_ref:
            raise ValueError("invalid search budget selection review")
        if self.reviewer_ref == self.selector_ref or (self.proposer_ref is not None and self.reviewer_ref == self.proposer_ref):
            raise ValueError("search selection reviewer must be independent from selector and proposer")
        if self.reviewed_at < 0 or self.review_hash != _digest(self.material()):
            raise ValueError("invalid search budget selection review material")


def review_search_budget_selection(
    *,
    selection: SearchBudgetSelectionReceipt,
    selected_candidate: StructuralValidationCandidate | None,
    decision: SearchReviewDecision,
    rationale_ref: str,
    reviewer_ref: str,
    reviewed_at: int,
) -> SearchBudgetSelectionReviewReceipt:
    selection.validate()
    if decision == "APPROVE" and selection.status != "SELECTED":
        raise ValueError("search selection approval requires a selected corrected winner")
    if selection.status == "SELECTED":
        if selected_candidate is None or selected_candidate.candidate_hash != selection.selected_candidate_hash:
            raise ValueError("search review requires exact selected candidate")
        selected_candidate.validate()
        proposer_ref = selected_candidate.proposer_ref
    else:
        if selected_candidate is not None:
            raise ValueError("no-winner search selection cannot have selected candidate")
        proposer_ref = None
    fields = {
        "selection_hash": selection.selection_hash,
        "selected_candidate_hash": selection.selected_candidate_hash,
        "decision": decision,
        "rationale_ref": rationale_ref,
        "selector_ref": selection.selector_ref,
        "proposer_ref": proposer_ref,
        "reviewer_ref": reviewer_ref,
        "reviewed_at": reviewed_at,
    }
    provisional = SearchBudgetSelectionReviewReceipt(**fields, review_hash="0" * 64)
    result = SearchBudgetSelectionReviewReceipt(**fields, review_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class SearchBudgetedGraphRevisionReceipt:
    selection_hash: str
    review_hash: str
    candidate_hash: str
    reservation_hash: str
    evaluation_hash: str
    underlying_validation_hash: str
    underlying_validated_revision_hash: str
    base_graph_hash: str
    new_graph_hash: str
    base_generation: int
    new_generation: int
    applier_ref: str
    applied_at: int
    revision_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/search-budgeted-graph-revision/v1.16",
            "selection_hash": self.selection_hash,
            "review_hash": self.review_hash,
            "candidate_hash": self.candidate_hash,
            "reservation_hash": self.reservation_hash,
            "evaluation_hash": self.evaluation_hash,
            "underlying_validation_hash": self.underlying_validation_hash,
            "underlying_validated_revision_hash": self.underlying_validated_revision_hash,
            "base_graph_hash": self.base_graph_hash,
            "new_graph_hash": self.new_graph_hash,
            "base_generation": self.base_generation,
            "new_generation": self.new_generation,
            "applier_ref": self.applier_ref,
            "applied_at": self.applied_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("selection_hash", self.selection_hash),
            ("review_hash", self.review_hash),
            ("candidate_hash", self.candidate_hash),
            ("reservation_hash", self.reservation_hash),
            ("evaluation_hash", self.evaluation_hash),
            ("underlying_validation_hash", self.underlying_validation_hash),
            ("underlying_validated_revision_hash", self.underlying_validated_revision_hash),
            ("base_graph_hash", self.base_graph_hash),
            ("new_graph_hash", self.new_graph_hash),
            ("revision_hash", self.revision_hash),
        ):
            _require_digest(name, value)
        if self.new_generation != self.base_generation + 1 or not self.applier_ref or self.applied_at < 0:
            raise ValueError("invalid search-budgeted graph revision metadata")
        if self.revision_hash != _digest(self.material()):
            raise ValueError("revision_hash does not match search-budgeted graph revision")


def apply_search_budgeted_selection(
    *,
    current_graph: DependencyGraphState,
    candidate: StructuralValidationCandidate,
    reservation: HeldOutSearchReservation,
    underlying_validation: HeldOutStructuralValidationReceipt,
    evaluation: SearchAdjustedValidationReceipt,
    selection: SearchBudgetSelectionReceipt,
    review: SearchBudgetSelectionReviewReceipt,
    applier_ref: str,
    applied_at: int,
) -> tuple[DependencyGraphState, SearchBudgetedGraphRevisionReceipt]:
    current_graph.validate()
    candidate.validate()
    reservation.validate()
    underlying_validation.validate()
    evaluation.validate()
    selection.validate()
    review.validate()
    if selection.status != "SELECTED" or selection.selected_candidate_hash != candidate.candidate_hash or selection.selected_evaluation_hash != evaluation.evaluation_hash:
        raise ValueError("search-budgeted structural selection chain mismatch")
    if evaluation.status != "SEARCH_CORRECTED_IMPROVED" or evaluation.reservation_hash != reservation.reservation_hash:
        raise ValueError("search-budgeted apply requires corrected held-out improvement")
    if evaluation.underlying_validation_hash != underlying_validation.validation_hash or underlying_validation.status != "HELDOUT_IMPROVED":
        raise ValueError("search-budgeted apply underlying held-out validation mismatch")
    if review.selection_hash != selection.selection_hash or review.selected_candidate_hash != candidate.candidate_hash or review.decision != "APPROVE":
        raise ValueError("search-budgeted apply requires APPROVE review")
    v15_selection = select_structural_candidate(
        selection_ref=f"{selection.selection_ref}:v1.15",
        candidates=(candidate,),
        validations=(underlying_validation,),
        selector_ref=selection.selector_ref,
        selected_at=selection.selected_at,
    )
    v15_review = review_structural_selection(
        selection=v15_selection,
        selected_candidate=candidate,
        decision="APPROVE",
        rationale_ref=review.rationale_ref,
        reviewer_ref=review.reviewer_ref,
        reviewed_at=review.reviewed_at,
    )
    new_graph, underlying_revision = apply_validated_structural_selection(
        current_graph=current_graph,
        candidate=candidate,
        validation=underlying_validation,
        selection=v15_selection,
        review=v15_review,
        applier_ref=applier_ref,
        applied_at=applied_at,
    )
    fields = {
        "selection_hash": selection.selection_hash,
        "review_hash": review.review_hash,
        "candidate_hash": candidate.candidate_hash,
        "reservation_hash": reservation.reservation_hash,
        "evaluation_hash": evaluation.evaluation_hash,
        "underlying_validation_hash": underlying_validation.validation_hash,
        "underlying_validated_revision_hash": underlying_revision.revision_hash,
        "base_graph_hash": current_graph.graph_hash,
        "new_graph_hash": new_graph.graph_hash,
        "base_generation": current_graph.generation,
        "new_generation": new_graph.generation,
        "applier_ref": applier_ref,
        "applied_at": applied_at,
    }
    provisional = SearchBudgetedGraphRevisionReceipt(**fields, revision_hash="0" * 64)
    receipt = SearchBudgetedGraphRevisionReceipt(**fields, revision_hash=_digest(provisional.material()))
    receipt.validate()
    return new_graph, receipt
