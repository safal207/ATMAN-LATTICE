from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from model.calibration import DependencyPairSample, summarize_dependency_samples
from model.dependency_graph_revision import (
    DependencyGraphRevisionReceipt,
    DependencyGraphState,
    StructuralGraphReplayReceipt,
    StructuralGraphRevisionProposal,
    apply_structural_graph_revision,
    make_structural_graph_revision_proposal,
    replay_structural_graph_revision,
    review_structural_graph_revision,
)
from model.calibration import binary_brier_score_ppm

ValidationStatus = Literal[
    "INSUFFICIENT_HELDOUT",
    "HELDOUT_IMPROVED",
    "OVERFIT_SIGNAL",
    "COMPLEXITY_REJECTED",
]
SelectionStatus = Literal["SELECTED", "NO_ELIGIBLE_CANDIDATE"]
SelectionReviewDecision = Literal["APPROVE", "HOLD", "REJECT"]


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


def dependency_history_hash(samples: tuple[DependencyPairSample, ...]) -> str:
    if not samples:
        raise ValueError("structural validation requires dependency history")
    for sample in samples:
        sample.validate()
    pair_key = samples[0].pair_key
    if any(sample.pair_key != pair_key for sample in samples):
        raise ValueError("structural validation history must share one pair key")
    return _digest({
        "domain": "ATMAN-LATTICE/structural-validation-history/v1.15",
        "pair_key": pair_key,
        "sample_hashes": sorted(sample.sample_hash for sample in samples),
    })


@dataclass(frozen=True)
class StructuralValidationPolicy:
    policy_ref: str
    subject_identity_ref: str
    evaluation_modulus: int
    min_selection_samples: int
    min_evaluation_samples: int
    dependency_threshold_bps: int
    edge_penalty_ppm: int
    registered_at: int
    policy_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/structural-validation-policy/v1.15",
            "policy_ref": self.policy_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "evaluation_modulus": self.evaluation_modulus,
            "evaluation_bucket": 0,
            "min_selection_samples": self.min_selection_samples,
            "min_evaluation_samples": self.min_evaluation_samples,
            "dependency_threshold_bps": self.dependency_threshold_bps,
            "edge_penalty_ppm": self.edge_penalty_ppm,
            "registered_at": self.registered_at,
        }

    def validate(self) -> None:
        if not self.policy_ref or not self.subject_identity_ref:
            raise ValueError("structural validation policy refs are required")
        if self.evaluation_modulus < 2:
            raise ValueError("evaluation_modulus must be >= 2")
        if self.min_selection_samples < 2 or self.min_evaluation_samples < 1:
            raise ValueError("structural validation sample minima are invalid")
        if self.dependency_threshold_bps < 0 or self.dependency_threshold_bps > 10_000:
            raise ValueError("dependency_threshold_bps must be 0..10000")
        if self.edge_penalty_ppm < 0 or self.registered_at < 0:
            raise ValueError("structural validation penalty/time must be non-negative")
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match structural validation policy")


def make_structural_validation_policy(
    *,
    policy_ref: str,
    subject_identity_ref: str,
    evaluation_modulus: int = 5,
    min_selection_samples: int = 6,
    min_evaluation_samples: int = 2,
    dependency_threshold_bps: int = 1000,
    edge_penalty_ppm: int = 10_000,
    registered_at: int,
) -> StructuralValidationPolicy:
    fields = {
        "policy_ref": policy_ref,
        "subject_identity_ref": subject_identity_ref,
        "evaluation_modulus": evaluation_modulus,
        "min_selection_samples": min_selection_samples,
        "min_evaluation_samples": min_evaluation_samples,
        "dependency_threshold_bps": dependency_threshold_bps,
        "edge_penalty_ppm": edge_penalty_ppm,
        "registered_at": registered_at,
    }
    provisional = StructuralValidationPolicy(**fields, policy_hash="0" * 64)
    result = StructuralValidationPolicy(**fields, policy_hash=_digest(provisional.material()))
    result.validate()
    return result


def _evaluation_bucket(sample_hash: str, modulus: int) -> int:
    _require_digest("sample_hash", sample_hash)
    digest = sha256(("ATMAN-LATTICE/heldout-split/v1.15:" + sample_hash).encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % modulus


def partition_dependency_samples(
    samples: tuple[DependencyPairSample, ...],
    policy: StructuralValidationPolicy,
) -> tuple[tuple[DependencyPairSample, ...], tuple[DependencyPairSample, ...], str]:
    policy.validate()
    history_hash = dependency_history_hash(samples)
    selection = tuple(sorted((sample for sample in samples if _evaluation_bucket(sample.sample_hash, policy.evaluation_modulus) != 0), key=lambda item: item.sample_hash))
    evaluation = tuple(sorted((sample for sample in samples if _evaluation_bucket(sample.sample_hash, policy.evaluation_modulus) == 0), key=lambda item: item.sample_hash))
    if set(item.sample_hash for item in selection) & set(item.sample_hash for item in evaluation):
        raise ValueError("selection and evaluation samples must be disjoint")
    if sorted(item.sample_hash for item in selection + evaluation) != sorted(item.sample_hash for item in samples):
        raise ValueError("held-out partition must account for every dependency sample")
    split_hash = _digest({
        "domain": "ATMAN-LATTICE/heldout-split/v1.15",
        "policy_hash": policy.policy_hash,
        "history_hash": history_hash,
        "selection_sample_hashes": [item.sample_hash for item in selection],
        "evaluation_sample_hashes": [item.sample_hash for item in evaluation],
    })
    return selection, evaluation, split_hash


@dataclass(frozen=True)
class StructuralValidationCandidate:
    candidate_ref: str
    subject_identity_ref: str
    pair_key: str
    policy_hash: str
    history_hash: str
    split_hash: str
    selection_sample_hashes: tuple[str, ...]
    evaluation_sample_hashes: tuple[str, ...]
    proposal: StructuralGraphRevisionProposal
    selection_replay: StructuralGraphReplayReceipt
    proposer_ref: str
    created_at: int
    candidate_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/structural-validation-candidate/v1.15",
            "candidate_ref": self.candidate_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "pair_key": self.pair_key,
            "policy_hash": self.policy_hash,
            "history_hash": self.history_hash,
            "split_hash": self.split_hash,
            "selection_sample_hashes": list(self.selection_sample_hashes),
            "evaluation_sample_hashes": list(self.evaluation_sample_hashes),
            "proposal_hash": self.proposal.proposal_hash,
            "selection_replay_hash": self.selection_replay.replay_hash,
            "proposer_ref": self.proposer_ref,
            "created_at": self.created_at,
        }

    def validate(self) -> None:
        if not self.candidate_ref or not self.subject_identity_ref or not self.proposer_ref:
            raise ValueError("structural validation candidate refs are required")
        for name, value in (("pair_key", self.pair_key), ("policy_hash", self.policy_hash), ("history_hash", self.history_hash), ("split_hash", self.split_hash), ("candidate_hash", self.candidate_hash)):
            _require_digest(name, value)
        for value in self.selection_sample_hashes + self.evaluation_sample_hashes:
            _require_digest("partition_sample_hash", value)
        if tuple(sorted(set(self.selection_sample_hashes))) != self.selection_sample_hashes or tuple(sorted(set(self.evaluation_sample_hashes))) != self.evaluation_sample_hashes:
            raise ValueError("candidate partition hashes must be unique and sorted")
        if set(self.selection_sample_hashes) & set(self.evaluation_sample_hashes):
            raise ValueError("selection and evaluation data must be disjoint")
        self.proposal.validate()
        self.selection_replay.validate()
        if self.proposal.pair_key != self.pair_key or self.proposal.subject_identity_ref != self.subject_identity_ref:
            raise ValueError("candidate proposal binding mismatch")
        if self.selection_replay.proposal_hash != self.proposal.proposal_hash:
            raise ValueError("candidate replay/proposal mismatch")
        if self.selection_replay.sample_hashes != self.selection_sample_hashes:
            raise ValueError("selection replay must use selection data only")
        if self.selection_replay.status != "STRUCTURE_IMPROVED":
            raise ValueError("structural candidate requires improved selection replay")
        if self.proposal.proposer_ref != self.proposer_ref or self.created_at < 0:
            raise ValueError("invalid structural candidate metadata")
        if self.candidate_hash != _digest(self.material()):
            raise ValueError("candidate_hash does not match structural candidate material")


def make_structural_validation_candidate(
    *,
    candidate_ref: str,
    base_graph: DependencyGraphState,
    samples: tuple[DependencyPairSample, ...],
    policy: StructuralValidationPolicy,
    direction: str,
    reason_ref: str,
    proposer_ref: str,
    created_at: int,
) -> StructuralValidationCandidate:
    base_graph.validate()
    policy.validate()
    if base_graph.subject_identity_ref != policy.subject_identity_ref:
        raise ValueError("structural validation policy/graph subject mismatch")
    selection, evaluation, split_hash = partition_dependency_samples(samples, policy)
    if len(selection) < policy.min_selection_samples:
        raise ValueError("insufficient selection data for structural candidate")
    snapshot = summarize_dependency_samples(
        selection,
        min_samples=policy.min_selection_samples,
        dependency_threshold_bps=policy.dependency_threshold_bps,
        measured_at=created_at,
    )
    proposal = make_structural_graph_revision_proposal(
        proposal_ref=f"{candidate_ref}:proposal",
        base_graph=base_graph,
        calibration_snapshot=snapshot,
        samples=selection,
        direction=direction,
        reason_ref=reason_ref,
        proposer_ref=proposer_ref,
        proposed_at=created_at,
    )
    _, replay = replay_structural_graph_revision(
        proposal,
        base_graph,
        selection,
        min_cases=policy.min_selection_samples,
        replayed_at=created_at,
    )
    if replay.status != "STRUCTURE_IMPROVED":
        raise ValueError("candidate structure does not improve selection replay")
    history_hash = dependency_history_hash(samples)
    fields = {
        "candidate_ref": candidate_ref,
        "subject_identity_ref": base_graph.subject_identity_ref,
        "pair_key": proposal.pair_key,
        "policy_hash": policy.policy_hash,
        "history_hash": history_hash,
        "split_hash": split_hash,
        "selection_sample_hashes": tuple(item.sample_hash for item in selection),
        "evaluation_sample_hashes": tuple(item.sample_hash for item in evaluation),
        "proposal": proposal,
        "selection_replay": replay,
        "proposer_ref": proposer_ref,
        "created_at": created_at,
    }
    provisional = StructuralValidationCandidate(**fields, candidate_hash="0" * 64)
    result = StructuralValidationCandidate(**fields, candidate_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class HeldOutStructuralCase:
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
            "domain": "ATMAN-LATTICE/heldout-structural-case/v1.15",
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
                raise ValueError("held-out prediction must be 0..10000 basis points")
        for value in (self.base_brier_score_ppm, self.proposed_brier_score_ppm):
            if value < 0 or value > 1_000_000:
                raise ValueError("held-out Brier score must be 0..1000000 ppm")
        if self.case_hash != _digest(self.material()):
            raise ValueError("case_hash does not match held-out structural case")


def _edge_present(graph: DependencyGraphState, parent: str, child: str) -> bool:
    return any(edge.parent_model_ref == parent and edge.child_model_ref == child for edge in graph.edges)


def _prediction(training: tuple[tuple[bool, bool], ...], *, conditional: bool, parent_positive: bool) -> int | None:
    population = tuple(child for parent, child in training if (not conditional or parent == parent_positive))
    if not population:
        return None
    return _round_ratio(10_000 * sum(1 for child in population if child), len(population))


@dataclass(frozen=True)
class HeldOutStructuralValidationReceipt:
    candidate_hash: str
    proposal_hash: str
    selection_replay_hash: str
    policy_hash: str
    history_hash: str
    split_hash: str
    selection_sample_hashes: tuple[str, ...]
    evaluation_sample_hashes: tuple[str, ...]
    case_hashes: tuple[str, ...]
    evaluated_case_count: int
    min_evaluation_samples: int
    base_mean_brier_ppm: int | None
    proposed_mean_brier_ppm: int | None
    raw_improvement_ppm: int | None
    base_edge_count: int
    proposed_edge_count: int
    edge_penalty_ppm: int
    base_regularized_brier_ppm: int | None
    proposed_regularized_brier_ppm: int | None
    regularized_improvement_ppm: int | None
    status: ValidationStatus
    proposer_ref: str
    validator_ref: str
    validated_at: int
    validation_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/heldout-structural-validation/v1.15",
            "candidate_hash": self.candidate_hash,
            "proposal_hash": self.proposal_hash,
            "selection_replay_hash": self.selection_replay_hash,
            "policy_hash": self.policy_hash,
            "history_hash": self.history_hash,
            "split_hash": self.split_hash,
            "selection_sample_hashes": list(self.selection_sample_hashes),
            "evaluation_sample_hashes": list(self.evaluation_sample_hashes),
            "case_hashes": list(self.case_hashes),
            "evaluated_case_count": self.evaluated_case_count,
            "min_evaluation_samples": self.min_evaluation_samples,
            "base_mean_brier_ppm": self.base_mean_brier_ppm,
            "proposed_mean_brier_ppm": self.proposed_mean_brier_ppm,
            "raw_improvement_ppm": self.raw_improvement_ppm,
            "base_edge_count": self.base_edge_count,
            "proposed_edge_count": self.proposed_edge_count,
            "edge_penalty_ppm": self.edge_penalty_ppm,
            "base_regularized_brier_ppm": self.base_regularized_brier_ppm,
            "proposed_regularized_brier_ppm": self.proposed_regularized_brier_ppm,
            "regularized_improvement_ppm": self.regularized_improvement_ppm,
            "status": self.status,
            "proposer_ref": self.proposer_ref,
            "validator_ref": self.validator_ref,
            "validated_at": self.validated_at,
        }

    def validate(self) -> None:
        for name, value in (("candidate_hash", self.candidate_hash), ("proposal_hash", self.proposal_hash), ("selection_replay_hash", self.selection_replay_hash), ("policy_hash", self.policy_hash), ("history_hash", self.history_hash), ("split_hash", self.split_hash), ("validation_hash", self.validation_hash)):
            _require_digest(name, value)
        for value in self.selection_sample_hashes + self.evaluation_sample_hashes + self.case_hashes:
            _require_digest("heldout_hash_component", value)
        if set(self.selection_sample_hashes) & set(self.evaluation_sample_hashes):
            raise ValueError("held-out validation cannot reuse selection samples")
        if self.evaluated_case_count != len(self.case_hashes) or self.min_evaluation_samples < 1:
            raise ValueError("invalid held-out evaluation counts")
        if self.base_edge_count < 0 or self.proposed_edge_count < 0 or self.edge_penalty_ppm < 0:
            raise ValueError("invalid structural complexity metadata")
        if not self.proposer_ref or not self.validator_ref or self.proposer_ref == self.validator_ref:
            raise ValueError("held-out validator must be independent from proposer")
        if self.validated_at < 0:
            raise ValueError("validated_at must be non-negative")
        if self.status == "INSUFFICIENT_HELDOUT":
            if self.evaluated_case_count >= self.min_evaluation_samples:
                raise ValueError("insufficient held-out status requires too few cases")
        else:
            values = (
                self.base_mean_brier_ppm,
                self.proposed_mean_brier_ppm,
                self.raw_improvement_ppm,
                self.base_regularized_brier_ppm,
                self.proposed_regularized_brier_ppm,
                self.regularized_improvement_ppm,
            )
            if self.evaluated_case_count < self.min_evaluation_samples or any(value is None for value in values):
                raise ValueError("complete held-out validation requires metrics")
            if self.raw_improvement_ppm != self.base_mean_brier_ppm - self.proposed_mean_brier_ppm:
                raise ValueError("raw held-out improvement mismatch")
            if self.base_regularized_brier_ppm != self.base_mean_brier_ppm + self.edge_penalty_ppm * self.base_edge_count:
                raise ValueError("base regularized score mismatch")
            if self.proposed_regularized_brier_ppm != self.proposed_mean_brier_ppm + self.edge_penalty_ppm * self.proposed_edge_count:
                raise ValueError("proposed regularized score mismatch")
            if self.regularized_improvement_ppm != self.base_regularized_brier_ppm - self.proposed_regularized_brier_ppm:
                raise ValueError("regularized held-out improvement mismatch")
            if self.status == "HELDOUT_IMPROVED" and self.regularized_improvement_ppm <= 0:
                raise ValueError("HELDOUT_IMPROVED requires positive regularized improvement")
            if self.status == "OVERFIT_SIGNAL" and self.raw_improvement_ppm > 0:
                raise ValueError("OVERFIT_SIGNAL requires non-positive held-out raw improvement")
            if self.status == "COMPLEXITY_REJECTED" and not (self.raw_improvement_ppm > 0 and self.regularized_improvement_ppm <= 0):
                raise ValueError("COMPLEXITY_REJECTED requires raw improvement erased by complexity penalty")
        if self.validation_hash != _digest(self.material()):
            raise ValueError("validation_hash does not match held-out structural validation")


def validate_structural_candidate(
    *,
    candidate: StructuralValidationCandidate,
    base_graph: DependencyGraphState,
    samples: tuple[DependencyPairSample, ...],
    policy: StructuralValidationPolicy,
    validator_ref: str,
    validated_at: int,
) -> tuple[tuple[HeldOutStructuralCase, ...], HeldOutStructuralValidationReceipt]:
    candidate.validate()
    base_graph.validate()
    policy.validate()
    if validator_ref == candidate.proposer_ref:
        raise ValueError("held-out validator must be independent from proposer")
    if candidate.policy_hash != policy.policy_hash or candidate.proposal.base_graph_hash != base_graph.graph_hash:
        raise ValueError("held-out candidate policy/base graph mismatch")
    selection, evaluation, split_hash = partition_dependency_samples(samples, policy)
    if dependency_history_hash(samples) != candidate.history_hash or split_hash != candidate.split_hash:
        raise ValueError("held-out candidate history/split is stale")
    if tuple(item.sample_hash for item in selection) != candidate.selection_sample_hashes or tuple(item.sample_hash for item in evaluation) != candidate.evaluation_sample_hashes:
        raise ValueError("held-out candidate partition mismatch")
    left_ref = samples[0].left_model_ref
    right_ref = samples[0].right_model_ref
    if candidate.proposal.direction == "LEFT_TO_RIGHT":
        parent_ref, child_ref = left_ref, right_ref
        training = tuple((item.left_positive, item.right_positive) for item in selection)
        eval_rows = tuple((item.left_positive, item.right_positive, item.sample_hash) for item in evaluation)
    else:
        parent_ref, child_ref = right_ref, left_ref
        training = tuple((item.right_positive, item.left_positive) for item in selection)
        eval_rows = tuple((item.right_positive, item.left_positive, item.sample_hash) for item in evaluation)
    if parent_ref != candidate.proposal.parent_model_ref or child_ref != candidate.proposal.child_model_ref:
        raise ValueError("held-out candidate orientation mismatch")
    base_conditional = _edge_present(base_graph, parent_ref, child_ref)
    proposed_conditional = any(edge.parent_model_ref == parent_ref and edge.child_model_ref == child_ref for edge in candidate.proposal.proposed_edges)
    cases: list[HeldOutStructuralCase] = []
    for parent_positive, child_positive, sample_hash in eval_rows:
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
        provisional = HeldOutStructuralCase(**fields, case_hash="0" * 64)
        case = HeldOutStructuralCase(**fields, case_hash=_digest(provisional.material()))
        case.validate()
        cases.append(case)
    cases_tuple = tuple(sorted(cases, key=lambda item: item.case_hash))
    n = len(cases_tuple)
    if n < policy.min_evaluation_samples:
        base_mean = proposed_mean = raw_improvement = None
        base_reg = proposed_reg = regularized_improvement = None
        status: ValidationStatus = "INSUFFICIENT_HELDOUT"
    else:
        base_mean = _round_ratio(sum(item.base_brier_score_ppm for item in cases_tuple), n)
        proposed_mean = _round_ratio(sum(item.proposed_brier_score_ppm for item in cases_tuple), n)
        raw_improvement = base_mean - proposed_mean
        base_reg = base_mean + policy.edge_penalty_ppm * len(base_graph.edges)
        proposed_reg = proposed_mean + policy.edge_penalty_ppm * len(candidate.proposal.proposed_edges)
        regularized_improvement = base_reg - proposed_reg
        if raw_improvement <= 0:
            status = "OVERFIT_SIGNAL"
        elif regularized_improvement <= 0:
            status = "COMPLEXITY_REJECTED"
        else:
            status = "HELDOUT_IMPROVED"
    fields = {
        "candidate_hash": candidate.candidate_hash,
        "proposal_hash": candidate.proposal.proposal_hash,
        "selection_replay_hash": candidate.selection_replay.replay_hash,
        "policy_hash": policy.policy_hash,
        "history_hash": candidate.history_hash,
        "split_hash": candidate.split_hash,
        "selection_sample_hashes": candidate.selection_sample_hashes,
        "evaluation_sample_hashes": candidate.evaluation_sample_hashes,
        "case_hashes": tuple(item.case_hash for item in cases_tuple),
        "evaluated_case_count": n,
        "min_evaluation_samples": policy.min_evaluation_samples,
        "base_mean_brier_ppm": base_mean,
        "proposed_mean_brier_ppm": proposed_mean,
        "raw_improvement_ppm": raw_improvement,
        "base_edge_count": len(base_graph.edges),
        "proposed_edge_count": len(candidate.proposal.proposed_edges),
        "edge_penalty_ppm": policy.edge_penalty_ppm,
        "base_regularized_brier_ppm": base_reg,
        "proposed_regularized_brier_ppm": proposed_reg,
        "regularized_improvement_ppm": regularized_improvement,
        "status": status,
        "proposer_ref": candidate.proposer_ref,
        "validator_ref": validator_ref,
        "validated_at": validated_at,
    }
    provisional = HeldOutStructuralValidationReceipt(**fields, validation_hash="0" * 64)
    receipt = HeldOutStructuralValidationReceipt(**fields, validation_hash=_digest(provisional.material()))
    receipt.validate()
    return cases_tuple, receipt


@dataclass(frozen=True)
class StructuralSelectionReceipt:
    selection_ref: str
    subject_identity_ref: str
    pair_key: str
    base_graph_hash: str
    policy_hash: str
    history_hash: str
    candidate_hashes: tuple[str, ...]
    validation_hashes: tuple[str, ...]
    selected_candidate_hash: str | None
    selected_validation_hash: str | None
    selected_regularized_improvement_ppm: int | None
    status: SelectionStatus
    selector_ref: str
    selected_at: int
    selection_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/structural-selection/v1.15",
            "selection_ref": self.selection_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "pair_key": self.pair_key,
            "base_graph_hash": self.base_graph_hash,
            "policy_hash": self.policy_hash,
            "history_hash": self.history_hash,
            "candidate_hashes": list(self.candidate_hashes),
            "validation_hashes": list(self.validation_hashes),
            "selected_candidate_hash": self.selected_candidate_hash,
            "selected_validation_hash": self.selected_validation_hash,
            "selected_regularized_improvement_ppm": self.selected_regularized_improvement_ppm,
            "status": self.status,
            "selector_ref": self.selector_ref,
            "selected_at": self.selected_at,
        }

    def validate(self) -> None:
        if not self.selection_ref or not self.subject_identity_ref or not self.selector_ref:
            raise ValueError("structural selection refs are required")
        for name, value in (("pair_key", self.pair_key), ("base_graph_hash", self.base_graph_hash), ("policy_hash", self.policy_hash), ("history_hash", self.history_hash), ("selection_hash", self.selection_hash)):
            _require_digest(name, value)
        for value in self.candidate_hashes + self.validation_hashes:
            _require_digest("selection_hash_component", value)
        if tuple(sorted(set(self.candidate_hashes))) != self.candidate_hashes or tuple(sorted(set(self.validation_hashes))) != self.validation_hashes:
            raise ValueError("selection candidate/validation hashes must be unique and sorted")
        if len(self.candidate_hashes) != len(self.validation_hashes) or not self.candidate_hashes:
            raise ValueError("structural selection requires matched candidate/validation sets")
        if self.status == "SELECTED":
            if self.selected_candidate_hash is None or self.selected_validation_hash is None or self.selected_regularized_improvement_ppm is None or self.selected_regularized_improvement_ppm <= 0:
                raise ValueError("SELECTED requires a positive held-out winner")
            _require_digest("selected_candidate_hash", self.selected_candidate_hash)
            _require_digest("selected_validation_hash", self.selected_validation_hash)
            if self.selected_candidate_hash not in self.candidate_hashes or self.selected_validation_hash not in self.validation_hashes:
                raise ValueError("selected winner must belong to candidate set")
        elif self.status == "NO_ELIGIBLE_CANDIDATE":
            if self.selected_candidate_hash is not None or self.selected_validation_hash is not None or self.selected_regularized_improvement_ppm is not None:
                raise ValueError("no-eligible selection cannot name a winner")
        else:
            raise ValueError("invalid structural selection status")
        if self.selected_at < 0 or self.selection_hash != _digest(self.material()):
            raise ValueError("invalid structural selection material")


def select_structural_candidate(
    *,
    selection_ref: str,
    candidates: tuple[StructuralValidationCandidate, ...],
    validations: tuple[HeldOutStructuralValidationReceipt, ...],
    selector_ref: str,
    selected_at: int,
) -> StructuralSelectionReceipt:
    if not candidates or len(candidates) != len(validations):
        raise ValueError("selection requires matched candidates and validations")
    for candidate in candidates:
        candidate.validate()
    for validation in validations:
        validation.validate()
    by_candidate = {item.candidate_hash: item for item in validations}
    if set(by_candidate) != {item.candidate_hash for item in candidates}:
        raise ValueError("validation set must exactly cover candidate set")
    first = candidates[0]
    if any(
        item.subject_identity_ref != first.subject_identity_ref
        or item.pair_key != first.pair_key
        or item.policy_hash != first.policy_hash
        or item.history_hash != first.history_hash
        or item.proposal.base_graph_hash != first.proposal.base_graph_hash
        for item in candidates
    ):
        raise ValueError("structural candidates must share one base/history/policy context")
    eligible: list[tuple[int, str, str]] = []
    for candidate in candidates:
        validation = by_candidate[candidate.candidate_hash]
        if validation.policy_hash != candidate.policy_hash or validation.history_hash != candidate.history_hash:
            raise ValueError("candidate validation context mismatch")
        if validation.status == "HELDOUT_IMPROVED":
            eligible.append((int(validation.regularized_improvement_ppm), candidate.candidate_hash, validation.validation_hash))
    if eligible:
        improvement, candidate_hash, validation_hash = sorted(eligible, key=lambda item: (-item[0], item[1]))[0]
        status: SelectionStatus = "SELECTED"
        selected_candidate_hash = candidate_hash
        selected_validation_hash = validation_hash
        selected_improvement = improvement
    else:
        status = "NO_ELIGIBLE_CANDIDATE"
        selected_candidate_hash = selected_validation_hash = None
        selected_improvement = None
    candidate_hashes = tuple(sorted(item.candidate_hash for item in candidates))
    validation_hashes = tuple(sorted(item.validation_hash for item in validations))
    fields = {
        "selection_ref": selection_ref,
        "subject_identity_ref": first.subject_identity_ref,
        "pair_key": first.pair_key,
        "base_graph_hash": first.proposal.base_graph_hash,
        "policy_hash": first.policy_hash,
        "history_hash": first.history_hash,
        "candidate_hashes": candidate_hashes,
        "validation_hashes": validation_hashes,
        "selected_candidate_hash": selected_candidate_hash,
        "selected_validation_hash": selected_validation_hash,
        "selected_regularized_improvement_ppm": selected_improvement,
        "status": status,
        "selector_ref": selector_ref,
        "selected_at": selected_at,
    }
    provisional = StructuralSelectionReceipt(**fields, selection_hash="0" * 64)
    receipt = StructuralSelectionReceipt(**fields, selection_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class StructuralSelectionReviewReceipt:
    selection_hash: str
    selected_candidate_hash: str | None
    decision: SelectionReviewDecision
    rationale_ref: str
    selector_ref: str
    proposer_ref: str | None
    reviewer_ref: str
    reviewed_at: int
    review_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/structural-selection-review/v1.15",
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
            raise ValueError("invalid structural selection review")
        if self.reviewer_ref == self.selector_ref or (self.proposer_ref is not None and self.reviewer_ref == self.proposer_ref):
            raise ValueError("structural selection reviewer must be independent from selector and proposer")
        if self.reviewed_at < 0 or self.review_hash != _digest(self.material()):
            raise ValueError("invalid structural selection review material")


def review_structural_selection(
    *,
    selection: StructuralSelectionReceipt,
    selected_candidate: StructuralValidationCandidate | None,
    decision: SelectionReviewDecision,
    rationale_ref: str,
    reviewer_ref: str,
    reviewed_at: int,
) -> StructuralSelectionReviewReceipt:
    selection.validate()
    if decision == "APPROVE" and selection.status != "SELECTED":
        raise ValueError("structural selection approval requires a selected held-out winner")
    if selection.status == "SELECTED":
        if selected_candidate is None or selected_candidate.candidate_hash != selection.selected_candidate_hash:
            raise ValueError("selection review requires exact selected candidate")
        selected_candidate.validate()
        proposer_ref = selected_candidate.proposer_ref
    else:
        if selected_candidate is not None:
            raise ValueError("no-eligible selection cannot have selected candidate")
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
    provisional = StructuralSelectionReviewReceipt(**fields, review_hash="0" * 64)
    receipt = StructuralSelectionReviewReceipt(**fields, review_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class ValidatedDependencyGraphRevisionReceipt:
    selection_hash: str
    validation_hash: str
    review_hash: str
    candidate_hash: str
    underlying_graph_revision_hash: str
    base_graph_hash: str
    new_graph_hash: str
    base_generation: int
    new_generation: int
    applier_ref: str
    applied_at: int
    revision_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/validated-dependency-graph-revision/v1.15",
            "selection_hash": self.selection_hash,
            "validation_hash": self.validation_hash,
            "review_hash": self.review_hash,
            "candidate_hash": self.candidate_hash,
            "underlying_graph_revision_hash": self.underlying_graph_revision_hash,
            "base_graph_hash": self.base_graph_hash,
            "new_graph_hash": self.new_graph_hash,
            "base_generation": self.base_generation,
            "new_generation": self.new_generation,
            "applier_ref": self.applier_ref,
            "applied_at": self.applied_at,
        }

    def validate(self) -> None:
        for name, value in (("selection_hash", self.selection_hash), ("validation_hash", self.validation_hash), ("review_hash", self.review_hash), ("candidate_hash", self.candidate_hash), ("underlying_graph_revision_hash", self.underlying_graph_revision_hash), ("base_graph_hash", self.base_graph_hash), ("new_graph_hash", self.new_graph_hash), ("revision_hash", self.revision_hash)):
            _require_digest(name, value)
        if self.new_generation != self.base_generation + 1 or not self.applier_ref or self.applied_at < 0:
            raise ValueError("invalid validated dependency graph revision metadata")
        if self.revision_hash != _digest(self.material()):
            raise ValueError("revision_hash does not match validated structural revision")


def apply_validated_structural_selection(
    *,
    current_graph: DependencyGraphState,
    candidate: StructuralValidationCandidate,
    validation: HeldOutStructuralValidationReceipt,
    selection: StructuralSelectionReceipt,
    review: StructuralSelectionReviewReceipt,
    applier_ref: str,
    applied_at: int,
) -> tuple[DependencyGraphState, ValidatedDependencyGraphRevisionReceipt]:
    current_graph.validate()
    candidate.validate()
    validation.validate()
    selection.validate()
    review.validate()
    if current_graph.graph_hash != selection.base_graph_hash or current_graph.graph_hash != candidate.proposal.base_graph_hash:
        raise ValueError("stale validated structural base graph")
    if selection.status != "SELECTED" or selection.selected_candidate_hash != candidate.candidate_hash or selection.selected_validation_hash != validation.validation_hash:
        raise ValueError("validated structural selection chain mismatch")
    if validation.status != "HELDOUT_IMPROVED" or validation.regularized_improvement_ppm is None or validation.regularized_improvement_ppm <= 0:
        raise ValueError("validated structural apply requires held-out regularized improvement")
    if review.selection_hash != selection.selection_hash or review.selected_candidate_hash != candidate.candidate_hash or review.decision != "APPROVE":
        raise ValueError("validated structural apply requires APPROVE review")
    underlying_review = review_structural_graph_revision(
        candidate.proposal,
        candidate.selection_replay,
        decision="APPROVE",
        rationale_ref=review.rationale_ref,
        reviewer_ref=review.reviewer_ref,
        reviewed_at=review.reviewed_at,
    )
    new_graph, underlying = apply_structural_graph_revision(
        current_graph=current_graph,
        proposal=candidate.proposal,
        replay=candidate.selection_replay,
        review=underlying_review,
        applier_ref=applier_ref,
        applied_at=applied_at,
    )
    fields = {
        "selection_hash": selection.selection_hash,
        "validation_hash": validation.validation_hash,
        "review_hash": review.review_hash,
        "candidate_hash": candidate.candidate_hash,
        "underlying_graph_revision_hash": underlying.revision_hash,
        "base_graph_hash": current_graph.graph_hash,
        "new_graph_hash": new_graph.graph_hash,
        "base_generation": current_graph.generation,
        "new_generation": new_graph.generation,
        "applier_ref": applier_ref,
        "applied_at": applied_at,
    }
    provisional = ValidatedDependencyGraphRevisionReceipt(**fields, revision_hash="0" * 64)
    receipt = ValidatedDependencyGraphRevisionReceipt(**fields, revision_hash=_digest(provisional.material()))
    receipt.validate()
    return new_graph, receipt
