from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from model.calibration import DependencyPairSample, binary_brier_score_ppm
from model.dependency_graph_revision import DependencyGraphState
from model.protected_confirmation import (
    ConfirmedGraphRevisionReceipt,
    ConfirmationEvaluationReceipt,
    ConfirmationReviewReceipt,
    ProtectedConfirmationBatch,
)
from model.structural_validation import StructuralValidationCandidate, StructuralValidationPolicy

ReplicationMode = Literal["TEMPORAL", "EXTERNAL", "TEMPORAL_EXTERNAL"]
ReplicationStatus = Literal["INSUFFICIENT_REPLICATION", "REPLICATED", "DRIFT_SIGNAL"]
DriftKind = Literal["NONE", "STRUCTURAL", "PERFORMANCE", "BOTH"]
ReplicationReviewDecision = Literal["ACKNOWLEDGE", "HOLD", "DISPUTE"]
ReplicationSeriesSignal = Literal["STABLE_HISTORY", "DRIFT_OBSERVED", "PERSISTENT_DRIFT_SIGNAL"]


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


def _edge_present(graph: DependencyGraphState, parent: str, child: str) -> bool:
    return any(edge.parent_model_ref == parent and edge.child_model_ref == child for edge in graph.edges)


def _prediction(training: tuple[tuple[bool, bool], ...], *, conditional: bool, parent_positive: bool) -> int | None:
    population = tuple(child for parent, child in training if (not conditional or parent == parent_positive))
    if not population:
        return None
    return _round_ratio(10_000 * sum(1 for child in population if child), len(population))


@dataclass(frozen=True)
class ReplicationPolicy:
    policy_ref: str
    subject_identity_ref: str
    min_replication_samples: int
    min_temporal_gap: int
    min_regularized_improvement_ppm: int
    max_proposed_brier_degradation_ppm: int
    persistent_drift_epochs: int
    registered_at: int
    policy_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/replication-policy/v1.18",
            "policy_ref": self.policy_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "min_replication_samples": self.min_replication_samples,
            "min_temporal_gap": self.min_temporal_gap,
            "min_regularized_improvement_ppm": self.min_regularized_improvement_ppm,
            "max_proposed_brier_degradation_ppm": self.max_proposed_brier_degradation_ppm,
            "persistent_drift_epochs": self.persistent_drift_epochs,
            "registered_at": self.registered_at,
        }

    def validate(self) -> None:
        if not self.policy_ref or not self.subject_identity_ref:
            raise ValueError("replication policy refs are required")
        if self.min_replication_samples < 1 or self.min_temporal_gap < 0:
            raise ValueError("invalid replication sample/time policy")
        if self.min_regularized_improvement_ppm < 0 or self.max_proposed_brier_degradation_ppm < 0:
            raise ValueError("replication thresholds must be non-negative")
        if self.persistent_drift_epochs < 1 or self.registered_at < 0:
            raise ValueError("invalid persistent drift/time policy")
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match replication policy")


def make_replication_policy(
    *,
    policy_ref: str,
    subject_identity_ref: str,
    min_replication_samples: int = 4,
    min_temporal_gap: int = 1,
    min_regularized_improvement_ppm: int = 0,
    max_proposed_brier_degradation_ppm: int = 100_000,
    persistent_drift_epochs: int = 2,
    registered_at: int,
) -> ReplicationPolicy:
    fields = {
        "policy_ref": policy_ref,
        "subject_identity_ref": subject_identity_ref,
        "min_replication_samples": min_replication_samples,
        "min_temporal_gap": min_temporal_gap,
        "min_regularized_improvement_ppm": min_regularized_improvement_ppm,
        "max_proposed_brier_degradation_ppm": max_proposed_brier_degradation_ppm,
        "persistent_drift_epochs": persistent_drift_epochs,
        "registered_at": registered_at,
    }
    provisional = ReplicationPolicy(**fields, policy_hash="0" * 64)
    result = ReplicationPolicy(**fields, policy_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ReplicationTargetReceipt:
    target_ref: str
    subject_identity_ref: str
    pair_key: str
    confirmed_revision_hash: str
    candidate_hash: str
    confirmed_graph_hash: str
    confirmed_generation: int
    confirmation_evaluation_hash: str
    confirmation_review_hash: str
    confirmation_batch_hash: str
    confirmation_source_ref: str
    confirmation_evaluated_at: int
    baseline_proposed_mean_brier_ppm: int
    baseline_regularized_improvement_ppm: int
    candidate_proposer_ref: str
    confirmation_evaluator_ref: str
    confirmation_reviewer_ref: str
    registered_at: int
    target_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/replication-target/v1.18",
            "target_ref": self.target_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "pair_key": self.pair_key,
            "confirmed_revision_hash": self.confirmed_revision_hash,
            "candidate_hash": self.candidate_hash,
            "confirmed_graph_hash": self.confirmed_graph_hash,
            "confirmed_generation": self.confirmed_generation,
            "confirmation_evaluation_hash": self.confirmation_evaluation_hash,
            "confirmation_review_hash": self.confirmation_review_hash,
            "confirmation_batch_hash": self.confirmation_batch_hash,
            "confirmation_source_ref": self.confirmation_source_ref,
            "confirmation_evaluated_at": self.confirmation_evaluated_at,
            "baseline_proposed_mean_brier_ppm": self.baseline_proposed_mean_brier_ppm,
            "baseline_regularized_improvement_ppm": self.baseline_regularized_improvement_ppm,
            "candidate_proposer_ref": self.candidate_proposer_ref,
            "confirmation_evaluator_ref": self.confirmation_evaluator_ref,
            "confirmation_reviewer_ref": self.confirmation_reviewer_ref,
            "registered_at": self.registered_at,
        }

    def validate(self) -> None:
        if not self.target_ref or not self.subject_identity_ref or not self.confirmation_source_ref:
            raise ValueError("replication target refs are required")
        for name, value in (
            ("pair_key", self.pair_key),
            ("confirmed_revision_hash", self.confirmed_revision_hash),
            ("candidate_hash", self.candidate_hash),
            ("confirmed_graph_hash", self.confirmed_graph_hash),
            ("confirmation_evaluation_hash", self.confirmation_evaluation_hash),
            ("confirmation_review_hash", self.confirmation_review_hash),
            ("confirmation_batch_hash", self.confirmation_batch_hash),
            ("target_hash", self.target_hash),
        ):
            _require_digest(name, value)
        if self.confirmed_generation < 1 or self.confirmation_evaluated_at < 0 or self.registered_at < self.confirmation_evaluated_at:
            raise ValueError("invalid replication target time/generation")
        if self.baseline_proposed_mean_brier_ppm < 0 or self.baseline_proposed_mean_brier_ppm > 1_000_000:
            raise ValueError("invalid baseline proposed Brier score")
        if self.baseline_regularized_improvement_ppm <= 0:
            raise ValueError("replication target requires positive confirmed structural improvement")
        if not self.candidate_proposer_ref or not self.confirmation_evaluator_ref or not self.confirmation_reviewer_ref:
            raise ValueError("replication target actors are required")
        if self.target_hash != _digest(self.material()):
            raise ValueError("target_hash does not match replication target")


def make_replication_target(
    *,
    target_ref: str,
    confirmed_revision: ConfirmedGraphRevisionReceipt,
    confirmation_evaluation: ConfirmationEvaluationReceipt,
    confirmation_review: ConfirmationReviewReceipt,
    confirmation_batch: ProtectedConfirmationBatch,
    candidate: StructuralValidationCandidate,
    confirmed_graph: DependencyGraphState,
    registered_at: int,
) -> ReplicationTargetReceipt:
    confirmed_revision.validate(); confirmation_evaluation.validate(); confirmation_review.validate(); confirmation_batch.validate(); candidate.validate(); confirmed_graph.validate()
    if confirmation_evaluation.status != "CONFIRMED" or confirmation_review.decision != "APPROVE":
        raise ValueError("replication target requires approved CONFIRMED result")
    if confirmed_revision.confirmation_evaluation_hash != confirmation_evaluation.evaluation_hash or confirmed_revision.confirmation_review_hash != confirmation_review.review_hash:
        raise ValueError("replication target confirmation chain mismatch")
    if confirmed_revision.candidate_hash != candidate.candidate_hash or confirmation_evaluation.candidate_hash != candidate.candidate_hash:
        raise ValueError("replication target candidate mismatch")
    if confirmed_revision.new_graph_hash != confirmed_graph.graph_hash or confirmed_revision.new_generation != confirmed_graph.generation:
        raise ValueError("replication target confirmed graph mismatch")
    if confirmation_evaluation.batch_hash != confirmation_batch.batch_hash:
        raise ValueError("replication target confirmation batch mismatch")
    if candidate.subject_identity_ref != confirmed_graph.subject_identity_ref or confirmation_batch.subject_identity_ref != candidate.subject_identity_ref:
        raise ValueError("replication target subject mismatch")
    if confirmation_evaluation.proposed_mean_brier_ppm is None or confirmation_evaluation.regularized_improvement_ppm is None:
        raise ValueError("replication target requires complete confirmation metrics")
    fields = {
        "target_ref": target_ref,
        "subject_identity_ref": candidate.subject_identity_ref,
        "pair_key": candidate.pair_key,
        "confirmed_revision_hash": confirmed_revision.revision_hash,
        "candidate_hash": candidate.candidate_hash,
        "confirmed_graph_hash": confirmed_graph.graph_hash,
        "confirmed_generation": confirmed_graph.generation,
        "confirmation_evaluation_hash": confirmation_evaluation.evaluation_hash,
        "confirmation_review_hash": confirmation_review.review_hash,
        "confirmation_batch_hash": confirmation_batch.batch_hash,
        "confirmation_source_ref": confirmation_batch.source_ref,
        "confirmation_evaluated_at": confirmation_evaluation.evaluated_at,
        "baseline_proposed_mean_brier_ppm": int(confirmation_evaluation.proposed_mean_brier_ppm),
        "baseline_regularized_improvement_ppm": int(confirmation_evaluation.regularized_improvement_ppm),
        "candidate_proposer_ref": candidate.proposer_ref,
        "confirmation_evaluator_ref": confirmation_evaluation.evaluator_ref,
        "confirmation_reviewer_ref": confirmation_review.reviewer_ref,
        "registered_at": registered_at,
    }
    provisional = ReplicationTargetReceipt(**fields, target_hash="0" * 64)
    result = ReplicationTargetReceipt(**fields, target_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ReplicationBatch:
    batch_ref: str
    target_hash: str
    subject_identity_ref: str
    pair_key: str
    mode: ReplicationMode
    source_ref: str
    environment_ref: str
    collected_from: int
    collected_to: int
    generation: int
    previous_batch_hash: str | None
    sample_hashes: tuple[str, ...]
    resolution_hashes: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    sample_count: int
    batch_keeper_ref: str
    sealed_at: int
    batch_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/replication-batch/v1.18",
            "batch_ref": self.batch_ref,
            "target_hash": self.target_hash,
            "subject_identity_ref": self.subject_identity_ref,
            "pair_key": self.pair_key,
            "mode": self.mode,
            "source_ref": self.source_ref,
            "environment_ref": self.environment_ref,
            "collected_from": self.collected_from,
            "collected_to": self.collected_to,
            "generation": self.generation,
            "previous_batch_hash": self.previous_batch_hash,
            "sample_hashes": list(self.sample_hashes),
            "resolution_hashes": list(self.resolution_hashes),
            "evidence_hashes": list(self.evidence_hashes),
            "sample_count": self.sample_count,
            "batch_keeper_ref": self.batch_keeper_ref,
            "sealed_at": self.sealed_at,
        }

    def validate(self) -> None:
        if not self.batch_ref or not self.subject_identity_ref or not self.source_ref or not self.environment_ref or not self.batch_keeper_ref:
            raise ValueError("replication batch refs are required")
        for name, value in (("target_hash", self.target_hash), ("pair_key", self.pair_key), ("batch_hash", self.batch_hash)):
            _require_digest(name, value)
        if self.previous_batch_hash is not None:
            _require_digest("previous_batch_hash", self.previous_batch_hash)
        if self.mode not in {"TEMPORAL", "EXTERNAL", "TEMPORAL_EXTERNAL"}:
            raise ValueError("invalid replication mode")
        if self.collected_from < 0 or self.collected_to < self.collected_from or self.sealed_at < self.collected_to:
            raise ValueError("invalid replication collection/seal time")
        if self.generation < 0 or self.sample_count != len(self.sample_hashes) or self.sample_count < 1:
            raise ValueError("invalid replication generation/count")
        for name, values in (("sample_hash", self.sample_hashes), ("resolution_hash", self.resolution_hashes), ("evidence_hash", self.evidence_hashes)):
            for value in values:
                _require_digest(name, value)
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"replication {name} values must be unique and sorted")
        if len(self.resolution_hashes) != self.sample_count or len(self.evidence_hashes) != self.sample_count * 2:
            raise ValueError("replication provenance accounting mismatch")
        if self.batch_hash != _digest(self.material()):
            raise ValueError("batch_hash does not match replication batch")


def make_replication_batch(
    *,
    batch_ref: str,
    target: ReplicationTargetReceipt,
    policy: ReplicationPolicy,
    mode: ReplicationMode,
    source_ref: str,
    environment_ref: str,
    samples: tuple[DependencyPairSample, ...],
    collected_from: int,
    collected_to: int,
    generation: int,
    previous_batch: ReplicationBatch | None,
    batch_keeper_ref: str,
    sealed_at: int,
) -> ReplicationBatch:
    target.validate(); policy.validate()
    if target.subject_identity_ref != policy.subject_identity_ref:
        raise ValueError("replication policy/target subject mismatch")
    if not samples:
        raise ValueError("replication batch requires samples")
    for item in samples:
        item.validate()
        if item.pair_key != target.pair_key:
            raise ValueError("replication samples must share target pair key")
        if item.sampled_at < collected_from or item.sampled_at > collected_to:
            raise ValueError("replication sample time falls outside collection window")
    if collected_from < target.confirmation_evaluated_at:
        raise ValueError("replication data cannot predate baseline confirmation")
    if mode in {"TEMPORAL", "TEMPORAL_EXTERNAL"} and collected_from - target.confirmation_evaluated_at < policy.min_temporal_gap:
        raise ValueError("replication temporal gap is below policy minimum")
    if mode in {"EXTERNAL", "TEMPORAL_EXTERNAL"} and source_ref == target.confirmation_source_ref:
        raise ValueError("external replication requires a source distinct from confirmation source")
    if batch_keeper_ref in {target.candidate_proposer_ref, target.confirmation_evaluator_ref}:
        raise ValueError("replication batch keeper must be independent from model proposer and confirmation evaluator")
    if previous_batch is None:
        if generation != 0:
            raise ValueError("first replication batch must be generation 0")
        previous_hash = None
    else:
        previous_batch.validate()
        if previous_batch.target_hash != target.target_hash or previous_batch.subject_identity_ref != target.subject_identity_ref or previous_batch.pair_key != target.pair_key:
            raise ValueError("replication batch lineage mismatch")
        if generation != previous_batch.generation + 1:
            raise ValueError("replication generation must advance exactly once")
        if collected_from <= previous_batch.collected_to:
            raise ValueError("temporal replication windows must advance without overlap")
        previous_hash = previous_batch.batch_hash
    sample_hashes = tuple(sorted(item.sample_hash for item in samples))
    resolution_hashes = tuple(sorted(item.resolution_hash for item in samples))
    evidence_hashes = tuple(sorted(value for item in samples for value in (item.left_evidence_hash, item.right_evidence_hash)))
    fields = {
        "batch_ref": batch_ref,
        "target_hash": target.target_hash,
        "subject_identity_ref": target.subject_identity_ref,
        "pair_key": target.pair_key,
        "mode": mode,
        "source_ref": source_ref,
        "environment_ref": environment_ref,
        "collected_from": collected_from,
        "collected_to": collected_to,
        "generation": generation,
        "previous_batch_hash": previous_hash,
        "sample_hashes": sample_hashes,
        "resolution_hashes": resolution_hashes,
        "evidence_hashes": evidence_hashes,
        "sample_count": len(samples),
        "batch_keeper_ref": batch_keeper_ref,
        "sealed_at": sealed_at,
    }
    provisional = ReplicationBatch(**fields, batch_hash="0" * 64)
    result = ReplicationBatch(**fields, batch_hash=_digest(provisional.material()))
    result.validate()
    return result


def assert_replication_freshness(
    *,
    batch: ReplicationBatch,
    search_samples: tuple[DependencyPairSample, ...],
    confirmation_batches: tuple[ProtectedConfirmationBatch, ...],
    prior_replication_batches: tuple[ReplicationBatch, ...],
) -> None:
    batch.validate()
    sample_hashes = {item.sample_hash for item in search_samples}
    resolution_hashes = {item.resolution_hash for item in search_samples}
    evidence_hashes = {value for item in search_samples for value in (item.left_evidence_hash, item.right_evidence_hash)}
    for item in search_samples:
        item.validate()
        if item.pair_key != batch.pair_key:
            raise ValueError("search samples must share replication pair key")
    for item in confirmation_batches:
        item.validate()
        if item.subject_identity_ref != batch.subject_identity_ref or item.pair_key != batch.pair_key:
            raise ValueError("confirmation batches must share replication subject/pair")
        sample_hashes.update(item.sample_hashes)
        resolution_hashes.update(item.resolution_hashes)
        evidence_hashes.update(item.evidence_hashes)
    for item in prior_replication_batches:
        item.validate()
        if item.target_hash != batch.target_hash:
            raise ValueError("prior replication batches must share target")
        sample_hashes.update(item.sample_hashes)
        resolution_hashes.update(item.resolution_hashes)
        evidence_hashes.update(item.evidence_hashes)
    if sample_hashes & set(batch.sample_hashes):
        raise ValueError("replication reuses previously exposed sample hash")
    if resolution_hashes & set(batch.resolution_hashes):
        raise ValueError("replication reuses previously exposed resolution provenance")
    if evidence_hashes & set(batch.evidence_hashes):
        raise ValueError("replication reuses previously exposed evidence provenance")


@dataclass(frozen=True)
class ReplicationCase:
    sample_hash: str
    parent_positive: bool
    child_positive: bool
    base_predicted_positive_bps: int
    confirmed_predicted_positive_bps: int
    base_brier_score_ppm: int
    confirmed_brier_score_ppm: int
    case_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/replication-case/v1.18",
            "sample_hash": self.sample_hash,
            "parent_positive": self.parent_positive,
            "child_positive": self.child_positive,
            "base_predicted_positive_bps": self.base_predicted_positive_bps,
            "confirmed_predicted_positive_bps": self.confirmed_predicted_positive_bps,
            "base_brier_score_ppm": self.base_brier_score_ppm,
            "confirmed_brier_score_ppm": self.confirmed_brier_score_ppm,
        }

    def validate(self) -> None:
        _require_digest("sample_hash", self.sample_hash); _require_digest("case_hash", self.case_hash)
        for value in (self.base_predicted_positive_bps, self.confirmed_predicted_positive_bps):
            if value < 0 or value > 10_000:
                raise ValueError("replication prediction must be 0..10000 basis points")
        for value in (self.base_brier_score_ppm, self.confirmed_brier_score_ppm):
            if value < 0 or value > 1_000_000:
                raise ValueError("replication Brier score must be 0..1000000 ppm")
        if self.case_hash != _digest(self.material()):
            raise ValueError("case_hash does not match replication case")


@dataclass(frozen=True)
class ReplicationEvaluationReceipt:
    target_hash: str
    batch_hash: str
    batch_generation: int
    mode: ReplicationMode
    source_ref: str
    environment_ref: str
    policy_hash: str
    confirmed_revision_hash: str
    candidate_hash: str
    confirmed_graph_hash: str
    case_hashes: tuple[str, ...]
    evaluated_case_count: int
    min_replication_samples: int
    temporal_gap: int
    base_mean_brier_ppm: int | None
    confirmed_mean_brier_ppm: int | None
    base_regularized_brier_ppm: int | None
    confirmed_regularized_brier_ppm: int | None
    regularized_improvement_ppm: int | None
    baseline_confirmed_mean_brier_ppm: int
    proposed_brier_degradation_ppm: int | None
    allowed_brier_degradation_ppm: int
    required_min_regularized_improvement_ppm: int
    drift_kind: DriftKind
    status: ReplicationStatus
    batch_keeper_ref: str
    evaluator_ref: str
    evaluated_at: int
    evaluation_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/replication-evaluation/v1.18",
            "target_hash": self.target_hash,
            "batch_hash": self.batch_hash,
            "batch_generation": self.batch_generation,
            "mode": self.mode,
            "source_ref": self.source_ref,
            "environment_ref": self.environment_ref,
            "policy_hash": self.policy_hash,
            "confirmed_revision_hash": self.confirmed_revision_hash,
            "candidate_hash": self.candidate_hash,
            "confirmed_graph_hash": self.confirmed_graph_hash,
            "case_hashes": list(self.case_hashes),
            "evaluated_case_count": self.evaluated_case_count,
            "min_replication_samples": self.min_replication_samples,
            "temporal_gap": self.temporal_gap,
            "base_mean_brier_ppm": self.base_mean_brier_ppm,
            "confirmed_mean_brier_ppm": self.confirmed_mean_brier_ppm,
            "base_regularized_brier_ppm": self.base_regularized_brier_ppm,
            "confirmed_regularized_brier_ppm": self.confirmed_regularized_brier_ppm,
            "regularized_improvement_ppm": self.regularized_improvement_ppm,
            "baseline_confirmed_mean_brier_ppm": self.baseline_confirmed_mean_brier_ppm,
            "proposed_brier_degradation_ppm": self.proposed_brier_degradation_ppm,
            "allowed_brier_degradation_ppm": self.allowed_brier_degradation_ppm,
            "required_min_regularized_improvement_ppm": self.required_min_regularized_improvement_ppm,
            "drift_kind": self.drift_kind,
            "status": self.status,
            "batch_keeper_ref": self.batch_keeper_ref,
            "evaluator_ref": self.evaluator_ref,
            "evaluated_at": self.evaluated_at,
        }

    def validate(self) -> None:
        for name, value in (("target_hash", self.target_hash), ("batch_hash", self.batch_hash), ("policy_hash", self.policy_hash), ("confirmed_revision_hash", self.confirmed_revision_hash), ("candidate_hash", self.candidate_hash), ("confirmed_graph_hash", self.confirmed_graph_hash), ("evaluation_hash", self.evaluation_hash)):
            _require_digest(name, value)
        for value in self.case_hashes:
            _require_digest("case_hash", value)
        if self.batch_generation < 0 or self.evaluated_case_count != len(self.case_hashes) or self.min_replication_samples < 1 or self.temporal_gap < 0:
            raise ValueError("invalid replication counts/time")
        if self.allowed_brier_degradation_ppm < 0 or self.required_min_regularized_improvement_ppm < 0:
            raise ValueError("invalid replication thresholds")
        if not self.batch_keeper_ref or not self.evaluator_ref or self.evaluator_ref == self.batch_keeper_ref:
            raise ValueError("replication evaluator must be independent from batch keeper")
        metrics = (self.base_mean_brier_ppm, self.confirmed_mean_brier_ppm, self.base_regularized_brier_ppm, self.confirmed_regularized_brier_ppm, self.regularized_improvement_ppm, self.proposed_brier_degradation_ppm)
        if self.status == "INSUFFICIENT_REPLICATION":
            if self.evaluated_case_count >= self.min_replication_samples or any(value is not None for value in metrics) or self.drift_kind != "NONE":
                raise ValueError("insufficient replication must not issue aggregate drift metrics")
        else:
            if self.evaluated_case_count < self.min_replication_samples or any(value is None for value in metrics):
                raise ValueError("complete replication requires aggregate metrics")
            if self.regularized_improvement_ppm != self.base_regularized_brier_ppm - self.confirmed_regularized_brier_ppm:
                raise ValueError("replication regularized improvement mismatch")
            if self.proposed_brier_degradation_ppm != self.confirmed_mean_brier_ppm - self.baseline_confirmed_mean_brier_ppm:
                raise ValueError("replication baseline degradation mismatch")
            structural_drift = self.regularized_improvement_ppm <= self.required_min_regularized_improvement_ppm
            performance_drift = self.proposed_brier_degradation_ppm > self.allowed_brier_degradation_ppm
            expected_kind: DriftKind = "BOTH" if structural_drift and performance_drift else "STRUCTURAL" if structural_drift else "PERFORMANCE" if performance_drift else "NONE"
            if self.drift_kind != expected_kind:
                raise ValueError("replication drift kind mismatch")
            expected_status: ReplicationStatus = "DRIFT_SIGNAL" if expected_kind != "NONE" else "REPLICATED"
            if self.status != expected_status:
                raise ValueError("replication status/drift mismatch")
        if self.evaluated_at < 0 or self.evaluation_hash != _digest(self.material()):
            raise ValueError("invalid replication evaluation material")


def evaluate_replication(
    *,
    target: ReplicationTargetReceipt,
    batch: ReplicationBatch,
    replication_samples: tuple[DependencyPairSample, ...],
    search_samples: tuple[DependencyPairSample, ...],
    candidate: StructuralValidationCandidate,
    base_graph: DependencyGraphState,
    confirmed_graph: DependencyGraphState,
    structural_policy: StructuralValidationPolicy,
    replication_policy: ReplicationPolicy,
    evaluator_ref: str,
    evaluated_at: int,
) -> tuple[tuple[ReplicationCase, ...], ReplicationEvaluationReceipt]:
    target.validate(); batch.validate(); candidate.validate(); base_graph.validate(); confirmed_graph.validate(); structural_policy.validate(); replication_policy.validate()
    if batch.target_hash != target.target_hash or target.candidate_hash != candidate.candidate_hash:
        raise ValueError("replication target/batch/candidate chain mismatch")
    if target.confirmed_graph_hash != confirmed_graph.graph_hash or target.confirmed_revision_hash == "0" * 64:
        raise ValueError("replication confirmed graph binding mismatch")
    if candidate.proposal.base_graph_hash != base_graph.graph_hash or candidate.policy_hash != structural_policy.policy_hash:
        raise ValueError("replication base graph/policy binding mismatch")
    if target.subject_identity_ref != replication_policy.subject_identity_ref:
        raise ValueError("replication policy/target subject mismatch")
    if evaluator_ref in {batch.batch_keeper_ref, target.candidate_proposer_ref, target.confirmation_evaluator_ref}:
        raise ValueError("replication evaluator must be independent from batch keeper and prior evaluators")
    if tuple(sorted(item.sample_hash for item in replication_samples)) != batch.sample_hashes:
        raise ValueError("replication sample set does not match sealed batch")
    training_by_hash = {item.sample_hash: item for item in search_samples}
    if any(value not in training_by_hash for value in candidate.selection_sample_hashes):
        raise ValueError("replication requires original frozen candidate training samples")
    training_samples = tuple(training_by_hash[value] for value in candidate.selection_sample_hashes)
    for item in training_samples + replication_samples:
        item.validate()
        if item.pair_key != target.pair_key:
            raise ValueError("replication samples must share target pair key")
    if candidate.proposal.direction == "LEFT_TO_RIGHT":
        parent_ref, child_ref = training_samples[0].left_model_ref, training_samples[0].right_model_ref
        training = tuple((item.left_positive, item.right_positive) for item in training_samples)
        rows = tuple((item.left_positive, item.right_positive, item.sample_hash) for item in replication_samples)
    else:
        parent_ref, child_ref = training_samples[0].right_model_ref, training_samples[0].left_model_ref
        training = tuple((item.right_positive, item.left_positive) for item in training_samples)
        rows = tuple((item.right_positive, item.left_positive, item.sample_hash) for item in replication_samples)
    if parent_ref != candidate.proposal.parent_model_ref or child_ref != candidate.proposal.child_model_ref:
        raise ValueError("replication candidate orientation mismatch")
    base_conditional = _edge_present(base_graph, parent_ref, child_ref)
    confirmed_conditional = _edge_present(confirmed_graph, parent_ref, child_ref)
    if not confirmed_conditional:
        raise ValueError("replication target graph no longer contains confirmed structural edge")
    cases: list[ReplicationCase] = []
    for parent_positive, child_positive, sample_hash in rows:
        base_prediction = _prediction(training, conditional=base_conditional, parent_positive=parent_positive)
        confirmed_prediction = _prediction(training, conditional=confirmed_conditional, parent_positive=parent_positive)
        if base_prediction is None or confirmed_prediction is None:
            continue
        fields = {
            "sample_hash": sample_hash,
            "parent_positive": parent_positive,
            "child_positive": child_positive,
            "base_predicted_positive_bps": base_prediction,
            "confirmed_predicted_positive_bps": confirmed_prediction,
            "base_brier_score_ppm": binary_brier_score_ppm(base_prediction, child_positive),
            "confirmed_brier_score_ppm": binary_brier_score_ppm(confirmed_prediction, child_positive),
        }
        provisional = ReplicationCase(**fields, case_hash="0" * 64)
        case = ReplicationCase(**fields, case_hash=_digest(provisional.material()))
        case.validate(); cases.append(case)
    cases_tuple = tuple(sorted(cases, key=lambda item: item.case_hash))
    n = len(cases_tuple)
    temporal_gap = batch.collected_from - target.confirmation_evaluated_at
    if n < replication_policy.min_replication_samples:
        base_mean = confirmed_mean = base_reg = confirmed_reg = regularized = degradation = None
        drift_kind: DriftKind = "NONE"
        status: ReplicationStatus = "INSUFFICIENT_REPLICATION"
    else:
        base_mean = _round_ratio(sum(item.base_brier_score_ppm for item in cases_tuple), n)
        confirmed_mean = _round_ratio(sum(item.confirmed_brier_score_ppm for item in cases_tuple), n)
        base_reg = base_mean + structural_policy.edge_penalty_ppm * len(base_graph.edges)
        confirmed_reg = confirmed_mean + structural_policy.edge_penalty_ppm * len(confirmed_graph.edges)
        regularized = base_reg - confirmed_reg
        degradation = confirmed_mean - target.baseline_proposed_mean_brier_ppm
        structural_drift = regularized <= replication_policy.min_regularized_improvement_ppm
        performance_drift = degradation > replication_policy.max_proposed_brier_degradation_ppm
        drift_kind = "BOTH" if structural_drift and performance_drift else "STRUCTURAL" if structural_drift else "PERFORMANCE" if performance_drift else "NONE"
        status = "DRIFT_SIGNAL" if drift_kind != "NONE" else "REPLICATED"
    fields = {
        "target_hash": target.target_hash,
        "batch_hash": batch.batch_hash,
        "batch_generation": batch.generation,
        "mode": batch.mode,
        "source_ref": batch.source_ref,
        "environment_ref": batch.environment_ref,
        "policy_hash": replication_policy.policy_hash,
        "confirmed_revision_hash": target.confirmed_revision_hash,
        "candidate_hash": candidate.candidate_hash,
        "confirmed_graph_hash": confirmed_graph.graph_hash,
        "case_hashes": tuple(item.case_hash for item in cases_tuple),
        "evaluated_case_count": n,
        "min_replication_samples": replication_policy.min_replication_samples,
        "temporal_gap": temporal_gap,
        "base_mean_brier_ppm": base_mean,
        "confirmed_mean_brier_ppm": confirmed_mean,
        "base_regularized_brier_ppm": base_reg,
        "confirmed_regularized_brier_ppm": confirmed_reg,
        "regularized_improvement_ppm": regularized,
        "baseline_confirmed_mean_brier_ppm": target.baseline_proposed_mean_brier_ppm,
        "proposed_brier_degradation_ppm": degradation,
        "allowed_brier_degradation_ppm": replication_policy.max_proposed_brier_degradation_ppm,
        "required_min_regularized_improvement_ppm": replication_policy.min_regularized_improvement_ppm,
        "drift_kind": drift_kind,
        "status": status,
        "batch_keeper_ref": batch.batch_keeper_ref,
        "evaluator_ref": evaluator_ref,
        "evaluated_at": evaluated_at,
    }
    provisional = ReplicationEvaluationReceipt(**fields, evaluation_hash="0" * 64)
    receipt = ReplicationEvaluationReceipt(**fields, evaluation_hash=_digest(provisional.material()))
    receipt.validate()
    return cases_tuple, receipt


@dataclass(frozen=True)
class ReplicationReviewReceipt:
    evaluation_hash: str
    target_hash: str
    batch_hash: str
    status: ReplicationStatus
    drift_kind: DriftKind
    decision: ReplicationReviewDecision
    rationale_ref: str
    batch_keeper_ref: str
    evaluator_ref: str
    reviewer_ref: str
    reviewed_at: int
    review_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/replication-review/v1.18",
            "evaluation_hash": self.evaluation_hash,
            "target_hash": self.target_hash,
            "batch_hash": self.batch_hash,
            "status": self.status,
            "drift_kind": self.drift_kind,
            "decision": self.decision,
            "rationale_ref": self.rationale_ref,
            "batch_keeper_ref": self.batch_keeper_ref,
            "evaluator_ref": self.evaluator_ref,
            "reviewer_ref": self.reviewer_ref,
            "reviewed_at": self.reviewed_at,
        }

    def validate(self) -> None:
        for name, value in (("evaluation_hash", self.evaluation_hash), ("target_hash", self.target_hash), ("batch_hash", self.batch_hash), ("review_hash", self.review_hash)):
            _require_digest(name, value)
        if self.decision not in {"ACKNOWLEDGE", "HOLD", "DISPUTE"} or not self.rationale_ref or not self.reviewer_ref:
            raise ValueError("invalid replication review")
        if self.reviewer_ref in {self.batch_keeper_ref, self.evaluator_ref}:
            raise ValueError("replication reviewer must be independent from batch keeper and evaluator")
        if self.reviewed_at < 0 or self.review_hash != _digest(self.material()):
            raise ValueError("invalid replication review material")


def review_replication(*, evaluation: ReplicationEvaluationReceipt, decision: ReplicationReviewDecision, rationale_ref: str, reviewer_ref: str, reviewed_at: int) -> ReplicationReviewReceipt:
    evaluation.validate()
    fields = {
        "evaluation_hash": evaluation.evaluation_hash,
        "target_hash": evaluation.target_hash,
        "batch_hash": evaluation.batch_hash,
        "status": evaluation.status,
        "drift_kind": evaluation.drift_kind,
        "decision": decision,
        "rationale_ref": rationale_ref,
        "batch_keeper_ref": evaluation.batch_keeper_ref,
        "evaluator_ref": evaluation.evaluator_ref,
        "reviewer_ref": reviewer_ref,
        "reviewed_at": reviewed_at,
    }
    provisional = ReplicationReviewReceipt(**fields, review_hash="0" * 64)
    result = ReplicationReviewReceipt(**fields, review_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ReplicationSeriesSnapshot:
    target_hash: str
    policy_hash: str
    evaluation_hashes: tuple[str, ...]
    review_hashes: tuple[str, ...]
    latest_generation: int
    replication_count: int
    stable_count: int
    drift_count: int
    consecutive_drift_count: int
    persistent_drift_epochs: int
    latest_status: ReplicationStatus
    signal: ReplicationSeriesSignal
    measured_at: int
    snapshot_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/replication-series-snapshot/v1.18",
            "target_hash": self.target_hash,
            "policy_hash": self.policy_hash,
            "evaluation_hashes": list(self.evaluation_hashes),
            "review_hashes": list(self.review_hashes),
            "latest_generation": self.latest_generation,
            "replication_count": self.replication_count,
            "stable_count": self.stable_count,
            "drift_count": self.drift_count,
            "consecutive_drift_count": self.consecutive_drift_count,
            "persistent_drift_epochs": self.persistent_drift_epochs,
            "latest_status": self.latest_status,
            "signal": self.signal,
            "measured_at": self.measured_at,
        }

    def validate(self) -> None:
        _require_digest("target_hash", self.target_hash); _require_digest("policy_hash", self.policy_hash); _require_digest("snapshot_hash", self.snapshot_hash)
        for value in self.evaluation_hashes + self.review_hashes:
            _require_digest("replication_series_hash", value)
        if self.replication_count != len(self.evaluation_hashes) or self.replication_count != len(self.review_hashes) or self.replication_count < 1:
            raise ValueError("invalid replication series count")
        if self.latest_generation != self.replication_count - 1:
            raise ValueError("replication series generations must be contiguous from zero")
        if self.stable_count + self.drift_count > self.replication_count or self.consecutive_drift_count < 0 or self.persistent_drift_epochs < 1:
            raise ValueError("invalid replication series accounting")
        expected = "PERSISTENT_DRIFT_SIGNAL" if self.consecutive_drift_count >= self.persistent_drift_epochs else "DRIFT_OBSERVED" if self.drift_count > 0 else "STABLE_HISTORY"
        if self.signal != expected:
            raise ValueError("replication series signal mismatch")
        if self.measured_at < 0 or self.snapshot_hash != _digest(self.material()):
            raise ValueError("invalid replication series snapshot material")


def summarize_replication_series(*, evaluations: tuple[ReplicationEvaluationReceipt, ...], reviews: tuple[ReplicationReviewReceipt, ...], policy: ReplicationPolicy, measured_at: int) -> ReplicationSeriesSnapshot:
    if not evaluations or len(evaluations) != len(reviews):
        raise ValueError("replication series requires matched evaluations and reviews")
    policy.validate()
    for item in evaluations: item.validate()
    for item in reviews: item.validate()
    ordered = tuple(sorted(evaluations, key=lambda item: item.batch_generation))
    if tuple(item.batch_generation for item in ordered) != tuple(range(len(ordered))):
        raise ValueError("replication series generations must be contiguous")
    target_hash = ordered[0].target_hash
    if any(item.target_hash != target_hash or item.policy_hash != policy.policy_hash for item in ordered):
        raise ValueError("replication series target/policy mismatch")
    review_by_eval = {item.evaluation_hash: item for item in reviews}
    if set(review_by_eval) != {item.evaluation_hash for item in ordered}:
        raise ValueError("replication reviews must exactly cover evaluations")
    ordered_reviews = tuple(review_by_eval[item.evaluation_hash] for item in ordered)
    if any(item.decision != "ACKNOWLEDGE" for item in ordered_reviews):
        raise ValueError("replication series summarizes acknowledged observations only")
    drift_count = sum(1 for item in ordered if item.status == "DRIFT_SIGNAL")
    stable_count = sum(1 for item in ordered if item.status == "REPLICATED")
    consecutive = 0
    for item in reversed(ordered):
        if item.status == "DRIFT_SIGNAL": consecutive += 1
        else: break
    signal: ReplicationSeriesSignal = "PERSISTENT_DRIFT_SIGNAL" if consecutive >= policy.persistent_drift_epochs else "DRIFT_OBSERVED" if drift_count > 0 else "STABLE_HISTORY"
    fields = {
        "target_hash": target_hash,
        "policy_hash": policy.policy_hash,
        "evaluation_hashes": tuple(item.evaluation_hash for item in ordered),
        "review_hashes": tuple(item.review_hash for item in ordered_reviews),
        "latest_generation": ordered[-1].batch_generation,
        "replication_count": len(ordered),
        "stable_count": stable_count,
        "drift_count": drift_count,
        "consecutive_drift_count": consecutive,
        "persistent_drift_epochs": policy.persistent_drift_epochs,
        "latest_status": ordered[-1].status,
        "signal": signal,
        "measured_at": measured_at,
    }
    provisional = ReplicationSeriesSnapshot(**fields, snapshot_hash="0" * 64)
    result = ReplicationSeriesSnapshot(**fields, snapshot_hash=_digest(provisional.material()))
    result.validate()
    return result
