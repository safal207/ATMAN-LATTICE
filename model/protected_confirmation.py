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

ConfirmationStatus = Literal["INSUFFICIENT_CONFIRMATION", "CONFIRMED", "CONFIRMATION_REJECTED"]
ConfirmationReviewDecision = Literal["APPROVE", "HOLD", "REJECT"]


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
class ProtectedConfirmationPolicy:
    policy_ref: str
    subject_identity_ref: str
    min_confirmation_samples: int
    min_regularized_improvement_ppm: int
    registered_at: int
    policy_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/protected-confirmation-policy/v1.17",
            "policy_ref": self.policy_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "min_confirmation_samples": self.min_confirmation_samples,
            "min_regularized_improvement_ppm": self.min_regularized_improvement_ppm,
            "registered_at": self.registered_at,
        }

    def validate(self) -> None:
        if not self.policy_ref or not self.subject_identity_ref:
            raise ValueError("confirmation policy refs are required")
        if self.min_confirmation_samples < 1 or self.min_regularized_improvement_ppm < 0 or self.registered_at < 0:
            raise ValueError("invalid confirmation policy thresholds/time")
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match confirmation policy")


def make_confirmation_policy(*, policy_ref: str, subject_identity_ref: str, min_confirmation_samples: int = 4, min_regularized_improvement_ppm: int = 0, registered_at: int) -> ProtectedConfirmationPolicy:
    fields = {
        "policy_ref": policy_ref,
        "subject_identity_ref": subject_identity_ref,
        "min_confirmation_samples": min_confirmation_samples,
        "min_regularized_improvement_ppm": min_regularized_improvement_ppm,
        "registered_at": registered_at,
    }
    provisional = ProtectedConfirmationPolicy(**fields, policy_hash="0" * 64)
    result = ProtectedConfirmationPolicy(**fields, policy_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ProtectedConfirmationBatch:
    batch_ref: str
    subject_identity_ref: str
    pair_key: str
    source_ref: str
    sample_hashes: tuple[str, ...]
    resolution_hashes: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    sample_count: int
    batch_keeper_ref: str
    sealed_at: int
    batch_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/protected-confirmation-batch/v1.17",
            "batch_ref": self.batch_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "pair_key": self.pair_key,
            "source_ref": self.source_ref,
            "sample_hashes": list(self.sample_hashes),
            "resolution_hashes": list(self.resolution_hashes),
            "evidence_hashes": list(self.evidence_hashes),
            "sample_count": self.sample_count,
            "batch_keeper_ref": self.batch_keeper_ref,
            "sealed_at": self.sealed_at,
        }

    def validate(self) -> None:
        if not self.batch_ref or not self.subject_identity_ref or not self.source_ref or not self.batch_keeper_ref:
            raise ValueError("confirmation batch refs are required")
        _require_digest("pair_key", self.pair_key)
        _require_digest("batch_hash", self.batch_hash)
        for name, values in (("sample_hash", self.sample_hashes), ("resolution_hash", self.resolution_hashes), ("evidence_hash", self.evidence_hashes)):
            for value in values:
                _require_digest(name, value)
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{name} values must be unique and sorted")
        if self.sample_count != len(self.sample_hashes) or self.sample_count < 1 or self.sealed_at < 0:
            raise ValueError("invalid confirmation batch count/time")
        if len(self.resolution_hashes) != self.sample_count or len(self.evidence_hashes) != self.sample_count * 2:
            raise ValueError("confirmation batch provenance accounting mismatch")
        if self.batch_hash != _digest(self.material()):
            raise ValueError("batch_hash does not match confirmation batch")


def make_confirmation_batch(*, batch_ref: str, subject_identity_ref: str, pair_key: str, source_ref: str, samples: tuple[DependencyPairSample, ...], batch_keeper_ref: str, sealed_at: int) -> ProtectedConfirmationBatch:
    if not samples:
        raise ValueError("confirmation batch requires samples")
    for item in samples:
        item.validate()
    if any(item.pair_key != pair_key for item in samples):
        raise ValueError("confirmation batch samples must share pair key")
    sample_hashes = tuple(sorted(item.sample_hash for item in samples))
    resolution_hashes = tuple(sorted(item.resolution_hash for item in samples))
    evidence_hashes = tuple(sorted([value for item in samples for value in (item.left_evidence_hash, item.right_evidence_hash)]))
    fields = {
        "batch_ref": batch_ref,
        "subject_identity_ref": subject_identity_ref,
        "pair_key": pair_key,
        "source_ref": source_ref,
        "sample_hashes": sample_hashes,
        "resolution_hashes": resolution_hashes,
        "evidence_hashes": evidence_hashes,
        "sample_count": len(samples),
        "batch_keeper_ref": batch_keeper_ref,
        "sealed_at": sealed_at,
    }
    provisional = ProtectedConfirmationBatch(**fields, batch_hash="0" * 64)
    result = ProtectedConfirmationBatch(**fields, batch_hash=_digest(provisional.material()))
    result.validate()
    return result


def assert_confirmation_freshness(*, batch: ProtectedConfirmationBatch, search_samples: tuple[DependencyPairSample, ...], prior_batches: tuple[ProtectedConfirmationBatch, ...]) -> None:
    batch.validate()
    for item in search_samples:
        item.validate()
        if item.pair_key != batch.pair_key:
            raise ValueError("search samples must share confirmation pair key")
    for prior in prior_batches:
        prior.validate()
        if prior.subject_identity_ref != batch.subject_identity_ref or prior.pair_key != batch.pair_key:
            raise ValueError("prior confirmation batches must share subject/pair")
    search_sample_hashes = {item.sample_hash for item in search_samples}
    search_resolution_hashes = {item.resolution_hash for item in search_samples}
    search_evidence_hashes = {value for item in search_samples for value in (item.left_evidence_hash, item.right_evidence_hash)}
    if search_sample_hashes & set(batch.sample_hashes):
        raise ValueError("confirmation batch reuses search sample hash")
    if search_resolution_hashes & set(batch.resolution_hashes):
        raise ValueError("confirmation batch reuses search resolution provenance")
    if search_evidence_hashes & set(batch.evidence_hashes):
        raise ValueError("confirmation batch reuses search evidence provenance")
    prior_sample_hashes = {value for prior in prior_batches for value in prior.sample_hashes}
    prior_resolution_hashes = {value for prior in prior_batches for value in prior.resolution_hashes}
    prior_evidence_hashes = {value for prior in prior_batches for value in prior.evidence_hashes}
    if prior_sample_hashes & set(batch.sample_hashes) or prior_resolution_hashes & set(batch.resolution_hashes) or prior_evidence_hashes & set(batch.evidence_hashes):
        raise ValueError("confirmation rotation requires genuinely fresh provenance")


@dataclass(frozen=True)
class ConfirmationExposureReceipt:
    selection_hash: str
    candidate_hash: str
    search_review_hash: str
    batch_hash: str
    confirmation_policy_hash: str
    search_history_hash: str
    base_graph_hash: str
    proposer_ref: str
    selector_ref: str
    batch_keeper_ref: str
    exposure_keeper_ref: str
    authorized_at: int
    exposure_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/confirmation-exposure/v1.17",
            "selection_hash": self.selection_hash,
            "candidate_hash": self.candidate_hash,
            "search_review_hash": self.search_review_hash,
            "batch_hash": self.batch_hash,
            "confirmation_policy_hash": self.confirmation_policy_hash,
            "search_history_hash": self.search_history_hash,
            "base_graph_hash": self.base_graph_hash,
            "proposer_ref": self.proposer_ref,
            "selector_ref": self.selector_ref,
            "batch_keeper_ref": self.batch_keeper_ref,
            "exposure_keeper_ref": self.exposure_keeper_ref,
            "authorized_at": self.authorized_at,
        }

    def validate(self) -> None:
        for name, value in (("selection_hash", self.selection_hash), ("candidate_hash", self.candidate_hash), ("search_review_hash", self.search_review_hash), ("batch_hash", self.batch_hash), ("confirmation_policy_hash", self.confirmation_policy_hash), ("search_history_hash", self.search_history_hash), ("base_graph_hash", self.base_graph_hash), ("exposure_hash", self.exposure_hash)):
            _require_digest(name, value)
        actors = (self.proposer_ref, self.selector_ref, self.batch_keeper_ref, self.exposure_keeper_ref)
        if any(not actor for actor in actors) or self.exposure_keeper_ref in {self.proposer_ref, self.selector_ref, self.batch_keeper_ref}:
            raise ValueError("confirmation exposure keeper must be independent from proposer, selector, and batch keeper")
        if self.authorized_at < 0 or self.exposure_hash != _digest(self.material()):
            raise ValueError("invalid confirmation exposure material")


def authorize_confirmation_exposure(*, selection: SearchBudgetSelectionReceipt, search_review: SearchBudgetSelectionReviewReceipt, candidate: StructuralValidationCandidate, batch: ProtectedConfirmationBatch, policy: ProtectedConfirmationPolicy, prior_exposures: tuple[ConfirmationExposureReceipt, ...], exposure_keeper_ref: str, authorized_at: int) -> ConfirmationExposureReceipt:
    selection.validate(); search_review.validate(); candidate.validate(); batch.validate(); policy.validate()
    if selection.status != "SELECTED" or selection.selected_candidate_hash != candidate.candidate_hash:
        raise ValueError("confirmation requires exact selected search-budget candidate")
    if search_review.selection_hash != selection.selection_hash or search_review.selected_candidate_hash != candidate.candidate_hash or search_review.decision != "APPROVE":
        raise ValueError("confirmation requires approved search-budget selection")
    if candidate.subject_identity_ref != policy.subject_identity_ref or batch.subject_identity_ref != candidate.subject_identity_ref or batch.pair_key != candidate.pair_key:
        raise ValueError("confirmation subject/pair binding mismatch")
    if batch.batch_keeper_ref in {candidate.proposer_ref, selection.selector_ref}:
        raise ValueError("confirmation batch keeper must be independent from proposer and selector")
    if any(item.selection_hash == selection.selection_hash for item in prior_exposures):
        raise ValueError("search selection already consumed a confirmation exposure")
    if any(item.batch_hash == batch.batch_hash for item in prior_exposures):
        raise ValueError("confirmation batch already exposed to another selection")
    fields = {
        "selection_hash": selection.selection_hash,
        "candidate_hash": candidate.candidate_hash,
        "search_review_hash": search_review.review_hash,
        "batch_hash": batch.batch_hash,
        "confirmation_policy_hash": policy.policy_hash,
        "search_history_hash": selection.history_hash,
        "base_graph_hash": selection.base_graph_hash,
        "proposer_ref": candidate.proposer_ref,
        "selector_ref": selection.selector_ref,
        "batch_keeper_ref": batch.batch_keeper_ref,
        "exposure_keeper_ref": exposure_keeper_ref,
        "authorized_at": authorized_at,
    }
    provisional = ConfirmationExposureReceipt(**fields, exposure_hash="0" * 64)
    result = ConfirmationExposureReceipt(**fields, exposure_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ConfirmationCase:
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
            "domain": "ATMAN-LATTICE/confirmation-case/v1.17",
            "sample_hash": self.sample_hash,
            "parent_positive": self.parent_positive,
            "child_positive": self.child_positive,
            "base_predicted_positive_bps": self.base_predicted_positive_bps,
            "proposed_predicted_positive_bps": self.proposed_predicted_positive_bps,
            "base_brier_score_ppm": self.base_brier_score_ppm,
            "proposed_brier_score_ppm": self.proposed_brier_score_ppm,
        }

    def validate(self) -> None:
        _require_digest("sample_hash", self.sample_hash); _require_digest("case_hash", self.case_hash)
        for value in (self.base_predicted_positive_bps, self.proposed_predicted_positive_bps):
            if value < 0 or value > 10_000:
                raise ValueError("confirmation prediction must be 0..10000 basis points")
        for value in (self.base_brier_score_ppm, self.proposed_brier_score_ppm):
            if value < 0 or value > 1_000_000:
                raise ValueError("confirmation Brier score must be 0..1000000 ppm")
        if self.case_hash != _digest(self.material()):
            raise ValueError("case_hash does not match confirmation case")


def _edge_present(graph: DependencyGraphState, parent: str, child: str) -> bool:
    return any(edge.parent_model_ref == parent and edge.child_model_ref == child for edge in graph.edges)


def _prediction(training: tuple[tuple[bool, bool], ...], *, conditional: bool, parent_positive: bool) -> int | None:
    population = tuple(child for parent, child in training if (not conditional or parent == parent_positive))
    if not population:
        return None
    return _round_ratio(10_000 * sum(1 for child in population if child), len(population))


@dataclass(frozen=True)
class ConfirmationEvaluationReceipt:
    selection_hash: str
    candidate_hash: str
    batch_hash: str
    exposure_hash: str
    confirmation_policy_hash: str
    case_hashes: tuple[str, ...]
    evaluated_case_count: int
    min_confirmation_samples: int
    base_mean_brier_ppm: int | None
    proposed_mean_brier_ppm: int | None
    raw_improvement_ppm: int | None
    base_regularized_brier_ppm: int | None
    proposed_regularized_brier_ppm: int | None
    regularized_improvement_ppm: int | None
    required_min_regularized_improvement_ppm: int
    status: ConfirmationStatus
    proposer_ref: str
    selector_ref: str
    batch_keeper_ref: str
    exposure_keeper_ref: str
    evaluator_ref: str
    evaluated_at: int
    evaluation_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/confirmation-evaluation/v1.17",
            "selection_hash": self.selection_hash,
            "candidate_hash": self.candidate_hash,
            "batch_hash": self.batch_hash,
            "exposure_hash": self.exposure_hash,
            "confirmation_policy_hash": self.confirmation_policy_hash,
            "case_hashes": list(self.case_hashes),
            "evaluated_case_count": self.evaluated_case_count,
            "min_confirmation_samples": self.min_confirmation_samples,
            "base_mean_brier_ppm": self.base_mean_brier_ppm,
            "proposed_mean_brier_ppm": self.proposed_mean_brier_ppm,
            "raw_improvement_ppm": self.raw_improvement_ppm,
            "base_regularized_brier_ppm": self.base_regularized_brier_ppm,
            "proposed_regularized_brier_ppm": self.proposed_regularized_brier_ppm,
            "regularized_improvement_ppm": self.regularized_improvement_ppm,
            "required_min_regularized_improvement_ppm": self.required_min_regularized_improvement_ppm,
            "status": self.status,
            "proposer_ref": self.proposer_ref,
            "selector_ref": self.selector_ref,
            "batch_keeper_ref": self.batch_keeper_ref,
            "exposure_keeper_ref": self.exposure_keeper_ref,
            "evaluator_ref": self.evaluator_ref,
            "evaluated_at": self.evaluated_at,
        }

    def validate(self) -> None:
        for name, value in (("selection_hash", self.selection_hash), ("candidate_hash", self.candidate_hash), ("batch_hash", self.batch_hash), ("exposure_hash", self.exposure_hash), ("confirmation_policy_hash", self.confirmation_policy_hash), ("evaluation_hash", self.evaluation_hash)):
            _require_digest(name, value)
        for value in self.case_hashes:
            _require_digest("case_hash", value)
        if self.evaluated_case_count != len(self.case_hashes) or self.min_confirmation_samples < 1 or self.required_min_regularized_improvement_ppm < 0:
            raise ValueError("invalid confirmation evaluation counts/threshold")
        actors = {self.proposer_ref, self.selector_ref, self.batch_keeper_ref, self.exposure_keeper_ref}
        if not self.evaluator_ref or self.evaluator_ref in actors:
            raise ValueError("confirmation evaluator must be independent from search/exposure actors")
        if self.evaluated_at < 0:
            raise ValueError("invalid confirmation evaluation time")
        metrics = (self.base_mean_brier_ppm, self.proposed_mean_brier_ppm, self.raw_improvement_ppm, self.base_regularized_brier_ppm, self.proposed_regularized_brier_ppm, self.regularized_improvement_ppm)
        if self.status == "INSUFFICIENT_CONFIRMATION":
            if self.evaluated_case_count >= self.min_confirmation_samples or any(value is not None for value in metrics):
                raise ValueError("insufficient confirmation requires too few scored cases and no aggregate metrics")
        else:
            if self.evaluated_case_count < self.min_confirmation_samples or any(value is None for value in metrics):
                raise ValueError("complete confirmation requires metrics")
            if self.raw_improvement_ppm != self.base_mean_brier_ppm - self.proposed_mean_brier_ppm:
                raise ValueError("confirmation raw improvement mismatch")
            if self.regularized_improvement_ppm != self.base_regularized_brier_ppm - self.proposed_regularized_brier_ppm:
                raise ValueError("confirmation regularized improvement mismatch")
            if self.status == "CONFIRMED" and self.regularized_improvement_ppm <= self.required_min_regularized_improvement_ppm:
                raise ValueError("CONFIRMED requires improvement above confirmation threshold")
            if self.status == "CONFIRMATION_REJECTED" and self.regularized_improvement_ppm > self.required_min_regularized_improvement_ppm:
                raise ValueError("confirmation rejection requires improvement at or below threshold")
        if self.evaluation_hash != _digest(self.material()):
            raise ValueError("evaluation_hash does not match confirmation evaluation")


def evaluate_confirmation(*, selection: SearchBudgetSelectionReceipt, candidate: StructuralValidationCandidate, batch: ProtectedConfirmationBatch, exposure: ConfirmationExposureReceipt, confirmation_samples: tuple[DependencyPairSample, ...], search_samples: tuple[DependencyPairSample, ...], current_graph: DependencyGraphState, structural_policy: StructuralValidationPolicy, confirmation_policy: ProtectedConfirmationPolicy, evaluator_ref: str, evaluated_at: int) -> tuple[tuple[ConfirmationCase, ...], ConfirmationEvaluationReceipt]:
    selection.validate(); candidate.validate(); batch.validate(); exposure.validate(); current_graph.validate(); structural_policy.validate(); confirmation_policy.validate()
    if exposure.selection_hash != selection.selection_hash or exposure.candidate_hash != candidate.candidate_hash or exposure.batch_hash != batch.batch_hash:
        raise ValueError("confirmation exposure chain mismatch")
    if selection.selected_candidate_hash != candidate.candidate_hash or selection.base_graph_hash != current_graph.graph_hash:
        raise ValueError("confirmation selection/base graph is stale")
    if candidate.policy_hash != structural_policy.policy_hash or confirmation_policy.policy_hash != exposure.confirmation_policy_hash:
        raise ValueError("confirmation policy binding mismatch")
    if tuple(sorted(item.sample_hash for item in confirmation_samples)) != batch.sample_hashes:
        raise ValueError("confirmation sample set does not match sealed batch")
    for item in confirmation_samples + search_samples:
        item.validate()
        if item.pair_key != candidate.pair_key:
            raise ValueError("confirmation/search samples must share candidate pair key")
    training_by_hash = {item.sample_hash: item for item in search_samples}
    if any(value not in training_by_hash for value in candidate.selection_sample_hashes):
        raise ValueError("candidate selection training samples missing")
    training_samples = tuple(training_by_hash[value] for value in candidate.selection_sample_hashes)
    if candidate.proposal.direction == "LEFT_TO_RIGHT":
        parent_ref, child_ref = training_samples[0].left_model_ref, training_samples[0].right_model_ref
        training = tuple((item.left_positive, item.right_positive) for item in training_samples)
        rows = tuple((item.left_positive, item.right_positive, item.sample_hash) for item in confirmation_samples)
    else:
        parent_ref, child_ref = training_samples[0].right_model_ref, training_samples[0].left_model_ref
        training = tuple((item.right_positive, item.left_positive) for item in training_samples)
        rows = tuple((item.right_positive, item.left_positive, item.sample_hash) for item in confirmation_samples)
    if parent_ref != candidate.proposal.parent_model_ref or child_ref != candidate.proposal.child_model_ref:
        raise ValueError("confirmation candidate orientation mismatch")
    base_conditional = _edge_present(current_graph, parent_ref, child_ref)
    proposed_conditional = any(edge.parent_model_ref == parent_ref and edge.child_model_ref == child_ref for edge in candidate.proposal.proposed_edges)
    cases: list[ConfirmationCase] = []
    for parent_positive, child_positive, sample_hash in rows:
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
        provisional = ConfirmationCase(**fields, case_hash="0" * 64)
        case = ConfirmationCase(**fields, case_hash=_digest(provisional.material()))
        case.validate(); cases.append(case)
    cases_tuple = tuple(sorted(cases, key=lambda item: item.case_hash))
    n = len(cases_tuple)
    if n < confirmation_policy.min_confirmation_samples:
        base_mean = proposed_mean = raw = base_reg = proposed_reg = regularized = None
        status: ConfirmationStatus = "INSUFFICIENT_CONFIRMATION"
    else:
        base_mean = _round_ratio(sum(item.base_brier_score_ppm for item in cases_tuple), n)
        proposed_mean = _round_ratio(sum(item.proposed_brier_score_ppm for item in cases_tuple), n)
        raw = base_mean - proposed_mean
        base_reg = base_mean + structural_policy.edge_penalty_ppm * len(current_graph.edges)
        proposed_reg = proposed_mean + structural_policy.edge_penalty_ppm * len(candidate.proposal.proposed_edges)
        regularized = base_reg - proposed_reg
        status = "CONFIRMED" if regularized > confirmation_policy.min_regularized_improvement_ppm else "CONFIRMATION_REJECTED"
    fields = {
        "selection_hash": selection.selection_hash,
        "candidate_hash": candidate.candidate_hash,
        "batch_hash": batch.batch_hash,
        "exposure_hash": exposure.exposure_hash,
        "confirmation_policy_hash": confirmation_policy.policy_hash,
        "case_hashes": tuple(item.case_hash for item in cases_tuple),
        "evaluated_case_count": n,
        "min_confirmation_samples": confirmation_policy.min_confirmation_samples,
        "base_mean_brier_ppm": base_mean,
        "proposed_mean_brier_ppm": proposed_mean,
        "raw_improvement_ppm": raw,
        "base_regularized_brier_ppm": base_reg,
        "proposed_regularized_brier_ppm": proposed_reg,
        "regularized_improvement_ppm": regularized,
        "required_min_regularized_improvement_ppm": confirmation_policy.min_regularized_improvement_ppm,
        "status": status,
        "proposer_ref": candidate.proposer_ref,
        "selector_ref": selection.selector_ref,
        "batch_keeper_ref": batch.batch_keeper_ref,
        "exposure_keeper_ref": exposure.exposure_keeper_ref,
        "evaluator_ref": evaluator_ref,
        "evaluated_at": evaluated_at,
    }
    provisional = ConfirmationEvaluationReceipt(**fields, evaluation_hash="0" * 64)
    receipt = ConfirmationEvaluationReceipt(**fields, evaluation_hash=_digest(provisional.material()))
    receipt.validate()
    return cases_tuple, receipt


@dataclass(frozen=True)
class ConfirmationReviewReceipt:
    evaluation_hash: str
    selection_hash: str
    candidate_hash: str
    status: str
    decision: ConfirmationReviewDecision
    rationale_ref: str
    proposer_ref: str
    selector_ref: str
    evaluator_ref: str
    reviewer_ref: str
    reviewed_at: int
    review_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/confirmation-review/v1.17",
            "evaluation_hash": self.evaluation_hash,
            "selection_hash": self.selection_hash,
            "candidate_hash": self.candidate_hash,
            "status": self.status,
            "decision": self.decision,
            "rationale_ref": self.rationale_ref,
            "proposer_ref": self.proposer_ref,
            "selector_ref": self.selector_ref,
            "evaluator_ref": self.evaluator_ref,
            "reviewer_ref": self.reviewer_ref,
            "reviewed_at": self.reviewed_at,
        }

    def validate(self) -> None:
        for name, value in (("evaluation_hash", self.evaluation_hash), ("selection_hash", self.selection_hash), ("candidate_hash", self.candidate_hash), ("review_hash", self.review_hash)):
            _require_digest(name, value)
        if self.decision not in {"APPROVE", "HOLD", "REJECT"} or not self.rationale_ref or not self.reviewer_ref:
            raise ValueError("invalid confirmation review")
        if self.reviewer_ref in {self.proposer_ref, self.selector_ref, self.evaluator_ref}:
            raise ValueError("confirmation reviewer must be independent from proposer, selector, and evaluator")
        if self.decision == "APPROVE" and self.status != "CONFIRMED":
            raise ValueError("confirmation approval requires CONFIRMED evaluation")
        if self.reviewed_at < 0 or self.review_hash != _digest(self.material()):
            raise ValueError("invalid confirmation review material")


def review_confirmation(*, evaluation: ConfirmationEvaluationReceipt, decision: ConfirmationReviewDecision, rationale_ref: str, reviewer_ref: str, reviewed_at: int) -> ConfirmationReviewReceipt:
    evaluation.validate()
    fields = {
        "evaluation_hash": evaluation.evaluation_hash,
        "selection_hash": evaluation.selection_hash,
        "candidate_hash": evaluation.candidate_hash,
        "status": evaluation.status,
        "decision": decision,
        "rationale_ref": rationale_ref,
        "proposer_ref": evaluation.proposer_ref,
        "selector_ref": evaluation.selector_ref,
        "evaluator_ref": evaluation.evaluator_ref,
        "reviewer_ref": reviewer_ref,
        "reviewed_at": reviewed_at,
    }
    provisional = ConfirmationReviewReceipt(**fields, review_hash="0" * 64)
    result = ConfirmationReviewReceipt(**fields, review_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ConfirmedGraphRevisionReceipt:
    selection_hash: str
    search_review_hash: str
    exposure_hash: str
    confirmation_evaluation_hash: str
    confirmation_review_hash: str
    candidate_hash: str
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
            "domain": "ATMAN-LATTICE/confirmed-graph-revision/v1.17",
            "selection_hash": self.selection_hash,
            "search_review_hash": self.search_review_hash,
            "exposure_hash": self.exposure_hash,
            "confirmation_evaluation_hash": self.confirmation_evaluation_hash,
            "confirmation_review_hash": self.confirmation_review_hash,
            "candidate_hash": self.candidate_hash,
            "underlying_search_revision_hash": self.underlying_search_revision_hash,
            "base_graph_hash": self.base_graph_hash,
            "new_graph_hash": self.new_graph_hash,
            "base_generation": self.base_generation,
            "new_generation": self.new_generation,
            "applier_ref": self.applier_ref,
            "applied_at": self.applied_at,
        }

    def validate(self) -> None:
        for name, value in (("selection_hash", self.selection_hash), ("search_review_hash", self.search_review_hash), ("exposure_hash", self.exposure_hash), ("confirmation_evaluation_hash", self.confirmation_evaluation_hash), ("confirmation_review_hash", self.confirmation_review_hash), ("candidate_hash", self.candidate_hash), ("underlying_search_revision_hash", self.underlying_search_revision_hash), ("base_graph_hash", self.base_graph_hash), ("new_graph_hash", self.new_graph_hash), ("revision_hash", self.revision_hash)):
            _require_digest(name, value)
        if self.new_generation != self.base_generation + 1 or not self.applier_ref or self.applied_at < 0:
            raise ValueError("invalid confirmed graph revision metadata")
        if self.revision_hash != _digest(self.material()):
            raise ValueError("revision_hash does not match confirmed graph revision")


def apply_confirmed_selection(*, current_graph: DependencyGraphState, candidate: StructuralValidationCandidate, reservation: HeldOutSearchReservation, underlying_validation: HeldOutStructuralValidationReceipt, search_evaluation: SearchAdjustedValidationReceipt, search_selection: SearchBudgetSelectionReceipt, search_review: SearchBudgetSelectionReviewReceipt, exposure: ConfirmationExposureReceipt, confirmation_evaluation: ConfirmationEvaluationReceipt, confirmation_review: ConfirmationReviewReceipt, applier_ref: str, applied_at: int) -> tuple[DependencyGraphState, ConfirmedGraphRevisionReceipt]:
    confirmation_evaluation.validate(); confirmation_review.validate(); exposure.validate()
    if confirmation_evaluation.status != "CONFIRMED" or confirmation_review.decision != "APPROVE":
        raise ValueError("confirmed apply requires CONFIRMED evaluation and APPROVE review")
    if confirmation_review.evaluation_hash != confirmation_evaluation.evaluation_hash or confirmation_evaluation.exposure_hash != exposure.exposure_hash:
        raise ValueError("confirmation apply chain mismatch")
    if exposure.selection_hash != search_selection.selection_hash or exposure.search_review_hash != search_review.review_hash:
        raise ValueError("confirmation exposure/search chain mismatch")
    new_graph, underlying = apply_search_budgeted_selection(
        current_graph=current_graph,
        candidate=candidate,
        reservation=reservation,
        underlying_validation=underlying_validation,
        evaluation=search_evaluation,
        selection=search_selection,
        review=search_review,
        applier_ref=applier_ref,
        applied_at=applied_at,
    )
    fields = {
        "selection_hash": search_selection.selection_hash,
        "search_review_hash": search_review.review_hash,
        "exposure_hash": exposure.exposure_hash,
        "confirmation_evaluation_hash": confirmation_evaluation.evaluation_hash,
        "confirmation_review_hash": confirmation_review.review_hash,
        "candidate_hash": candidate.candidate_hash,
        "underlying_search_revision_hash": underlying.revision_hash,
        "base_graph_hash": current_graph.graph_hash,
        "new_graph_hash": new_graph.graph_hash,
        "base_generation": current_graph.generation,
        "new_generation": new_graph.generation,
        "applier_ref": applier_ref,
        "applied_at": applied_at,
    }
    provisional = ConfirmedGraphRevisionReceipt(**fields, revision_hash="0" * 64)
    receipt = ConfirmedGraphRevisionReceipt(**fields, revision_hash=_digest(provisional.material()))
    receipt.validate()
    return new_graph, receipt
