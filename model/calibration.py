from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from model.multihypothesis import (
    DependencyMode,
    EvidenceDependencyDeclaration,
    HypothesisDistribution,
    MultiEvidenceReceipt,
    MultiLikelihoodModel,
)

CalibrationStatus = Literal[
    "INSUFFICIENT_SAMPLES",
    "NO_MARGINAL_MISCALIBRATION_SIGNAL",
    "MISCALIBRATION_SIGNAL",
]
DependencyAssessment = Literal[
    "INSUFFICIENT_SAMPLES",
    "INDEPENDENCE_CHALLENGED",
    "NO_DEPENDENCY_SIGNAL",
    "CONDITIONAL_DEPENDENCY_SUPPORTED",
    "CONDITIONAL_DEPENDENCY_NOT_OBSERVED",
]


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
    if numerator >= 0:
        return (numerator + denominator // 2) // denominator
    return -((-numerator + denominator // 2) // denominator)


def _validate_probability_vector(values: tuple[tuple[str, int], ...]) -> None:
    refs = [key for key, _ in values]
    if len(refs) < 2 or refs != sorted(refs) or len(set(refs)) != len(refs):
        raise ValueError("probability vector must contain unique sorted hypotheses")
    if any(not key or value < 0 or value > 10_000 for key, value in values):
        raise ValueError("probabilities must be 0..10000 basis points")
    if sum(value for _, value in values) != 10_000:
        raise ValueError("probabilities must sum to 10000 basis points")


def categorical_brier_score_ppm(probability_bps: tuple[tuple[str, int], ...], resolved_hypothesis_ref: str) -> int:
    _validate_probability_vector(probability_bps)
    if resolved_hypothesis_ref not in {key for key, _ in probability_bps}:
        raise ValueError("resolved hypothesis is outside probability vector")
    numerator = 0
    for hypothesis_ref, probability in probability_bps:
        target = 10_000 if hypothesis_ref == resolved_hypothesis_ref else 0
        numerator += (probability - target) ** 2
    return _round_ratio(numerator * 1_000_000, 100_000_000)


def binary_brier_score_ppm(predicted_positive_bps: int, observed_positive: bool) -> int:
    if predicted_positive_bps < 0 or predicted_positive_bps > 10_000:
        raise ValueError("predicted positive probability must be 0..10000 basis points")
    target = 10_000 if observed_positive else 0
    return _round_ratio((predicted_positive_bps - target) ** 2 * 1_000_000, 100_000_000)


@dataclass(frozen=True)
class CalibrationTargetReceipt:
    target_ref: str
    calibration_family_ref: str
    candidate_hash: str
    distribution_ref: str
    subject_identity_ref: str
    distribution_hash: str
    probability_bps: tuple[tuple[str, int], ...]
    likelihood_model_hash: str
    likelihood_model_ref: str
    positive_likelihood_bps: tuple[tuple[str, int], ...]
    conditioning_evidence_hashes: tuple[str, ...]
    dependency_hash: str
    dependency_group_ref: str
    dependency_mode: DependencyMode
    source_event_hash: str
    derivation_hash: str
    parent_evidence_hashes: tuple[str, ...]
    committed_at: int
    target_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/calibration-target/v1.12",
            "target_ref": self.target_ref,
            "calibration_family_ref": self.calibration_family_ref,
            "candidate_hash": self.candidate_hash,
            "distribution_ref": self.distribution_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "distribution_hash": self.distribution_hash,
            "probability_bps": [[key, value] for key, value in self.probability_bps],
            "likelihood_model_hash": self.likelihood_model_hash,
            "likelihood_model_ref": self.likelihood_model_ref,
            "positive_likelihood_bps": [[key, value] for key, value in self.positive_likelihood_bps],
            "conditioning_evidence_hashes": list(self.conditioning_evidence_hashes),
            "dependency_hash": self.dependency_hash,
            "dependency_group_ref": self.dependency_group_ref,
            "dependency_mode": self.dependency_mode,
            "source_event_hash": self.source_event_hash,
            "derivation_hash": self.derivation_hash,
            "parent_evidence_hashes": list(self.parent_evidence_hashes),
            "committed_at": self.committed_at,
        }

    def validate(self) -> None:
        if not self.target_ref or not self.calibration_family_ref or not self.distribution_ref or not self.subject_identity_ref or not self.likelihood_model_ref or not self.dependency_group_ref:
            raise ValueError("calibration target refs are required")
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("distribution_hash", self.distribution_hash),
            ("likelihood_model_hash", self.likelihood_model_hash),
            ("dependency_hash", self.dependency_hash),
            ("source_event_hash", self.source_event_hash),
            ("derivation_hash", self.derivation_hash),
            ("target_hash", self.target_hash),
        ):
            _require_digest(name, value)
        _validate_probability_vector(self.probability_bps)
        if tuple(key for key, _ in self.positive_likelihood_bps) != tuple(key for key, _ in self.probability_bps):
            raise ValueError("target likelihoods must exactly cover target hypotheses")
        if any(value < 0 or value > 10_000 for _, value in self.positive_likelihood_bps):
            raise ValueError("target likelihoods must be 0..10000 basis points")
        for value in self.conditioning_evidence_hashes + self.parent_evidence_hashes:
            _require_digest("evidence_hash", value)
        if tuple(sorted(set(self.conditioning_evidence_hashes))) != self.conditioning_evidence_hashes:
            raise ValueError("conditioning evidence hashes must be unique and sorted")
        if tuple(sorted(set(self.parent_evidence_hashes))) != self.parent_evidence_hashes:
            raise ValueError("parent evidence hashes must be unique and sorted")
        if self.dependency_mode not in {"INDEPENDENT", "CONDITIONAL", "DUPLICATE"}:
            raise ValueError("invalid calibration dependency mode")
        if self.dependency_mode == "INDEPENDENT" and (self.conditioning_evidence_hashes or self.parent_evidence_hashes):
            raise ValueError("independent target cannot have conditioning parents")
        if self.dependency_mode == "CONDITIONAL" and self.conditioning_evidence_hashes != self.parent_evidence_hashes:
            raise ValueError("conditional target must preserve exact dependency conditioning")
        if self.dependency_mode == "DUPLICATE" and len(self.parent_evidence_hashes) != 1:
            raise ValueError("duplicate target requires exactly one parent")
        if self.committed_at < 0:
            raise ValueError("committed_at must be >= 0")
        if self.target_hash != _digest(self.material()):
            raise ValueError("target_hash does not match calibration target material")


def make_calibration_target(
    *,
    target_ref: str,
    calibration_family_ref: str,
    distribution: HypothesisDistribution,
    likelihood_model: MultiLikelihoodModel,
    dependency: EvidenceDependencyDeclaration,
    committed_at: int,
) -> CalibrationTargetReceipt:
    distribution.validate()
    likelihood_model.validate()
    dependency.validate()
    if likelihood_model.candidate_hash != dependency.candidate_hash:
        raise ValueError("calibration target candidate binding mismatch")
    if likelihood_model.distribution_hash != distribution.distribution_hash:
        raise ValueError("calibration target distribution/model mismatch")
    if dependency.mode == "INDEPENDENT" and likelihood_model.conditioning_evidence_hashes:
        raise ValueError("independent calibration target requires unconditional likelihood")
    if dependency.mode == "CONDITIONAL" and likelihood_model.conditioning_evidence_hashes != dependency.parent_evidence_hashes:
        raise ValueError("conditional calibration target requires exact parent-bound likelihood")
    fields = {
        "target_ref": target_ref,
        "calibration_family_ref": calibration_family_ref,
        "candidate_hash": likelihood_model.candidate_hash,
        "distribution_ref": distribution.distribution_ref,
        "subject_identity_ref": distribution.subject_identity_ref,
        "distribution_hash": distribution.distribution_hash,
        "probability_bps": distribution.probability_bps,
        "likelihood_model_hash": likelihood_model.model_hash,
        "likelihood_model_ref": likelihood_model.model_ref,
        "positive_likelihood_bps": likelihood_model.positive_likelihood_bps,
        "conditioning_evidence_hashes": likelihood_model.conditioning_evidence_hashes,
        "dependency_hash": dependency.dependency_hash,
        "dependency_group_ref": dependency.dependency_group_ref,
        "dependency_mode": dependency.mode,
        "source_event_hash": dependency.source_event_hash,
        "derivation_hash": dependency.derivation_hash,
        "parent_evidence_hashes": dependency.parent_evidence_hashes,
        "committed_at": committed_at,
    }
    provisional = CalibrationTargetReceipt(**fields, target_hash="0" * 64)
    result = CalibrationTargetReceipt(**fields, target_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ResolvedOutcomeReceipt:
    resolution_ref: str
    distribution_ref: str
    subject_identity_ref: str
    resolved_hypothesis_ref: str
    resolution_source_hash: str
    resolved_at: int
    resolver_ref: str
    resolution_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/resolved-outcome/v1.12",
            "resolution_ref": self.resolution_ref,
            "distribution_ref": self.distribution_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "resolved_hypothesis_ref": self.resolved_hypothesis_ref,
            "resolution_source_hash": self.resolution_source_hash,
            "resolved_at": self.resolved_at,
            "resolver_ref": self.resolver_ref,
        }

    def validate(self) -> None:
        if not self.resolution_ref or not self.distribution_ref or not self.subject_identity_ref or not self.resolved_hypothesis_ref or not self.resolver_ref:
            raise ValueError("resolution refs are required")
        _require_digest("resolution_source_hash", self.resolution_source_hash)
        _require_digest("resolution_hash", self.resolution_hash)
        if self.resolved_at < 0:
            raise ValueError("resolved_at must be >= 0")
        if self.resolution_hash != _digest(self.material()):
            raise ValueError("resolution_hash does not match resolution material")


def make_resolved_outcome(
    target: CalibrationTargetReceipt,
    *,
    resolution_ref: str,
    resolved_hypothesis_ref: str,
    resolution_source_hash: str,
    resolved_at: int,
    resolver_ref: str,
) -> ResolvedOutcomeReceipt:
    target.validate()
    if resolved_hypothesis_ref not in {key for key, _ in target.probability_bps}:
        raise ValueError("resolved hypothesis is outside calibration target")
    if resolved_at < target.committed_at:
        raise ValueError("resolution cannot precede calibration target commitment")
    fields = {
        "resolution_ref": resolution_ref,
        "distribution_ref": target.distribution_ref,
        "subject_identity_ref": target.subject_identity_ref,
        "resolved_hypothesis_ref": resolved_hypothesis_ref,
        "resolution_source_hash": resolution_source_hash,
        "resolved_at": resolved_at,
        "resolver_ref": resolver_ref,
    }
    provisional = ResolvedOutcomeReceipt(**fields, resolution_hash="0" * 64)
    result = ResolvedOutcomeReceipt(**fields, resolution_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ForecastCalibrationReceipt:
    target_hash: str
    resolution_hash: str
    calibration_family_ref: str
    distribution_hash: str
    resolved_hypothesis_ref: str
    resolved_probability_bps: int
    brier_score_ppm: int
    calibrated_at: int
    calibration_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/forecast-calibration/v1.12",
            "target_hash": self.target_hash,
            "resolution_hash": self.resolution_hash,
            "calibration_family_ref": self.calibration_family_ref,
            "distribution_hash": self.distribution_hash,
            "resolved_hypothesis_ref": self.resolved_hypothesis_ref,
            "resolved_probability_bps": self.resolved_probability_bps,
            "brier_score_ppm": self.brier_score_ppm,
            "calibrated_at": self.calibrated_at,
        }

    def validate(self) -> None:
        for name, value in (("target_hash", self.target_hash), ("resolution_hash", self.resolution_hash), ("distribution_hash", self.distribution_hash), ("calibration_hash", self.calibration_hash)):
            _require_digest(name, value)
        if not self.calibration_family_ref or not self.resolved_hypothesis_ref:
            raise ValueError("forecast calibration refs are required")
        if self.resolved_probability_bps < 0 or self.resolved_probability_bps > 10_000:
            raise ValueError("resolved probability must be 0..10000 basis points")
        if self.brier_score_ppm < 0 or self.brier_score_ppm > 2_000_000 or self.calibrated_at < 0:
            raise ValueError("invalid forecast calibration metrics")
        if self.calibration_hash != _digest(self.material()):
            raise ValueError("calibration_hash does not match forecast calibration material")


def calibrate_forecast(target: CalibrationTargetReceipt, resolution: ResolvedOutcomeReceipt, *, calibrated_at: int) -> ForecastCalibrationReceipt:
    target.validate()
    resolution.validate()
    if resolution.distribution_ref != target.distribution_ref or resolution.subject_identity_ref != target.subject_identity_ref:
        raise ValueError("forecast calibration resolution binding mismatch")
    if calibrated_at < resolution.resolved_at:
        raise ValueError("calibration cannot precede resolution")
    probabilities = dict(target.probability_bps)
    if resolution.resolved_hypothesis_ref not in probabilities:
        raise ValueError("resolved hypothesis is outside target distribution")
    fields = {
        "target_hash": target.target_hash,
        "resolution_hash": resolution.resolution_hash,
        "calibration_family_ref": target.calibration_family_ref,
        "distribution_hash": target.distribution_hash,
        "resolved_hypothesis_ref": resolution.resolved_hypothesis_ref,
        "resolved_probability_bps": probabilities[resolution.resolved_hypothesis_ref],
        "brier_score_ppm": categorical_brier_score_ppm(target.probability_bps, resolution.resolved_hypothesis_ref),
        "calibrated_at": calibrated_at,
    }
    provisional = ForecastCalibrationReceipt(**fields, calibration_hash="0" * 64)
    result = ForecastCalibrationReceipt(**fields, calibration_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class LikelihoodCalibrationReceipt:
    target_hash: str
    evidence_hash: str
    resolution_hash: str
    calibration_family_ref: str
    likelihood_model_hash: str
    likelihood_model_ref: str
    resolved_hypothesis_ref: str
    predicted_positive_bps: int
    observed_outcome: str
    scored: bool
    brier_score_ppm: int | None
    dependency_mode: DependencyMode
    calibrated_at: int
    calibration_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/likelihood-calibration/v1.12",
            "target_hash": self.target_hash,
            "evidence_hash": self.evidence_hash,
            "resolution_hash": self.resolution_hash,
            "calibration_family_ref": self.calibration_family_ref,
            "likelihood_model_hash": self.likelihood_model_hash,
            "likelihood_model_ref": self.likelihood_model_ref,
            "resolved_hypothesis_ref": self.resolved_hypothesis_ref,
            "predicted_positive_bps": self.predicted_positive_bps,
            "observed_outcome": self.observed_outcome,
            "scored": self.scored,
            "brier_score_ppm": self.brier_score_ppm,
            "dependency_mode": self.dependency_mode,
            "calibrated_at": self.calibrated_at,
        }

    def validate(self) -> None:
        for name, value in (("target_hash", self.target_hash), ("evidence_hash", self.evidence_hash), ("resolution_hash", self.resolution_hash), ("likelihood_model_hash", self.likelihood_model_hash), ("calibration_hash", self.calibration_hash)):
            _require_digest(name, value)
        if not self.calibration_family_ref or not self.likelihood_model_ref or not self.resolved_hypothesis_ref:
            raise ValueError("likelihood calibration refs are required")
        if self.predicted_positive_bps < 0 or self.predicted_positive_bps > 10_000:
            raise ValueError("predicted positive must be 0..10000 basis points")
        if self.observed_outcome not in {"POSITIVE", "NEGATIVE", "INCONCLUSIVE"}:
            raise ValueError("invalid observed outcome")
        if self.dependency_mode not in {"INDEPENDENT", "CONDITIONAL", "DUPLICATE"}:
            raise ValueError("invalid dependency mode")
        if self.scored:
            if self.observed_outcome == "INCONCLUSIVE" or self.brier_score_ppm is None or not (0 <= self.brier_score_ppm <= 1_000_000):
                raise ValueError("scored likelihood calibration requires conclusive Brier score")
        elif self.observed_outcome != "INCONCLUSIVE" or self.brier_score_ppm is not None:
            raise ValueError("only inconclusive likelihood calibration may be unscored")
        if self.calibrated_at < 0 or self.calibration_hash != _digest(self.material()):
            raise ValueError("invalid likelihood calibration material")


def calibrate_likelihood(
    target: CalibrationTargetReceipt,
    evidence: MultiEvidenceReceipt,
    resolution: ResolvedOutcomeReceipt,
    *,
    calibrated_at: int,
) -> LikelihoodCalibrationReceipt:
    target.validate()
    evidence.validate()
    resolution.validate()
    if evidence.candidate_hash != target.candidate_hash or evidence.prior_distribution_hash != target.distribution_hash:
        raise ValueError("likelihood calibration evidence target mismatch")
    if evidence.likelihood_model_hash != target.likelihood_model_hash or evidence.dependency_hash != target.dependency_hash:
        raise ValueError("likelihood calibration frozen-assumption mismatch")
    if evidence.source_event_hash != target.source_event_hash or evidence.derivation_hash != target.derivation_hash:
        raise ValueError("likelihood calibration provenance mismatch")
    if resolution.distribution_ref != target.distribution_ref or resolution.subject_identity_ref != target.subject_identity_ref:
        raise ValueError("likelihood calibration resolution binding mismatch")
    if evidence.interpreted_at > resolution.resolved_at:
        raise ValueError("calibration evidence must precede resolution")
    if calibrated_at < resolution.resolved_at:
        raise ValueError("calibration cannot precede resolution")
    likelihoods = dict(target.positive_likelihood_bps)
    if resolution.resolved_hypothesis_ref not in likelihoods:
        raise ValueError("resolved hypothesis is outside likelihood target")
    predicted = likelihoods[resolution.resolved_hypothesis_ref]
    scored = evidence.outcome != "INCONCLUSIVE"
    brier = None if not scored else binary_brier_score_ppm(predicted, evidence.outcome == "POSITIVE")
    fields = {
        "target_hash": target.target_hash,
        "evidence_hash": evidence.evidence_hash,
        "resolution_hash": resolution.resolution_hash,
        "calibration_family_ref": target.calibration_family_ref,
        "likelihood_model_hash": target.likelihood_model_hash,
        "likelihood_model_ref": target.likelihood_model_ref,
        "resolved_hypothesis_ref": resolution.resolved_hypothesis_ref,
        "predicted_positive_bps": predicted,
        "observed_outcome": evidence.outcome,
        "scored": scored,
        "brier_score_ppm": brier,
        "dependency_mode": target.dependency_mode,
        "calibrated_at": calibrated_at,
    }
    provisional = LikelihoodCalibrationReceipt(**fields, calibration_hash="0" * 64)
    result = LikelihoodCalibrationReceipt(**fields, calibration_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class DependencyPairSample:
    pair_key: str
    resolution_hash: str
    dependency_group_ref: str
    left_model_ref: str
    right_model_ref: str
    declared_mode: DependencyMode
    resolved_hypothesis_ref: str
    left_evidence_hash: str
    right_evidence_hash: str
    left_positive: bool
    right_positive: bool
    sampled_at: int
    sample_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/dependency-pair-sample/v1.12",
            "pair_key": self.pair_key,
            "resolution_hash": self.resolution_hash,
            "dependency_group_ref": self.dependency_group_ref,
            "left_model_ref": self.left_model_ref,
            "right_model_ref": self.right_model_ref,
            "declared_mode": self.declared_mode,
            "resolved_hypothesis_ref": self.resolved_hypothesis_ref,
            "left_evidence_hash": self.left_evidence_hash,
            "right_evidence_hash": self.right_evidence_hash,
            "left_positive": self.left_positive,
            "right_positive": self.right_positive,
            "sampled_at": self.sampled_at,
        }

    def validate(self) -> None:
        for name, value in (("pair_key", self.pair_key), ("resolution_hash", self.resolution_hash), ("left_evidence_hash", self.left_evidence_hash), ("right_evidence_hash", self.right_evidence_hash), ("sample_hash", self.sample_hash)):
            _require_digest(name, value)
        if not self.dependency_group_ref or not self.left_model_ref or not self.right_model_ref or not self.resolved_hypothesis_ref:
            raise ValueError("dependency sample refs are required")
        if self.declared_mode not in {"INDEPENDENT", "CONDITIONAL"}:
            raise ValueError("dependency pair samples support independent or conditional evidence")
        if self.sampled_at < 0 or self.sample_hash != _digest(self.material()):
            raise ValueError("invalid dependency pair sample")


def make_dependency_pair_sample(
    *,
    left_target: CalibrationTargetReceipt,
    left_evidence: MultiEvidenceReceipt,
    right_target: CalibrationTargetReceipt,
    right_evidence: MultiEvidenceReceipt,
    resolution: ResolvedOutcomeReceipt,
    sampled_at: int,
) -> DependencyPairSample:
    left_target.validate()
    right_target.validate()
    left_evidence.validate()
    right_evidence.validate()
    resolution.validate()
    if left_target.distribution_ref != right_target.distribution_ref or resolution.distribution_ref != left_target.distribution_ref:
        raise ValueError("dependency pair must belong to the same resolved case")
    if left_evidence.evidence_hash == right_evidence.evidence_hash:
        raise ValueError("dependency pair requires two distinct evidence receipts")
    if left_evidence.outcome == "INCONCLUSIVE" or right_evidence.outcome == "INCONCLUSIVE":
        raise ValueError("dependency learning requires conclusive evidence outcomes")
    if left_evidence.candidate_hash != left_target.candidate_hash or right_evidence.candidate_hash != right_target.candidate_hash:
        raise ValueError("dependency pair evidence target mismatch")
    if right_target.dependency_mode == "DUPLICATE":
        raise ValueError("duplicate evidence is structural, not a statistical dependency sample")
    if right_target.dependency_mode == "CONDITIONAL" and left_evidence.evidence_hash not in right_target.parent_evidence_hashes:
        raise ValueError("conditional pair must include declared parent evidence")
    if right_target.dependency_mode == "INDEPENDENT" and right_target.parent_evidence_hashes:
        raise ValueError("independent pair cannot declare parents")
    pair_key = _digest({
        "domain": "ATMAN-LATTICE/dependency-pair-key/v1.12",
        "dependency_group_ref": right_target.dependency_group_ref,
        "left_model_ref": left_target.likelihood_model_ref,
        "right_model_ref": right_target.likelihood_model_ref,
        "declared_mode": right_target.dependency_mode,
        "resolved_hypothesis_ref": resolution.resolved_hypothesis_ref,
    })
    fields = {
        "pair_key": pair_key,
        "resolution_hash": resolution.resolution_hash,
        "dependency_group_ref": right_target.dependency_group_ref,
        "left_model_ref": left_target.likelihood_model_ref,
        "right_model_ref": right_target.likelihood_model_ref,
        "declared_mode": right_target.dependency_mode,
        "resolved_hypothesis_ref": resolution.resolved_hypothesis_ref,
        "left_evidence_hash": left_evidence.evidence_hash,
        "right_evidence_hash": right_evidence.evidence_hash,
        "left_positive": left_evidence.outcome == "POSITIVE",
        "right_positive": right_evidence.outcome == "POSITIVE",
        "sampled_at": sampled_at,
    }
    provisional = DependencyPairSample(**fields, sample_hash="0" * 64)
    result = DependencyPairSample(**fields, sample_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class DependencyCalibrationSnapshot:
    pair_key: str
    declared_mode: DependencyMode
    sample_count: int
    left_positive_count: int
    right_positive_count: int
    both_positive_count: int
    independence_gap_bps: int
    min_samples: int
    dependency_threshold_bps: int
    assessment: DependencyAssessment
    measured_at: int
    snapshot_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/dependency-calibration-snapshot/v1.12",
            "pair_key": self.pair_key,
            "declared_mode": self.declared_mode,
            "sample_count": self.sample_count,
            "left_positive_count": self.left_positive_count,
            "right_positive_count": self.right_positive_count,
            "both_positive_count": self.both_positive_count,
            "independence_gap_bps": self.independence_gap_bps,
            "min_samples": self.min_samples,
            "dependency_threshold_bps": self.dependency_threshold_bps,
            "assessment": self.assessment,
            "measured_at": self.measured_at,
        }

    def validate(self) -> None:
        _require_digest("pair_key", self.pair_key)
        _require_digest("snapshot_hash", self.snapshot_hash)
        if self.declared_mode not in {"INDEPENDENT", "CONDITIONAL"}:
            raise ValueError("invalid dependency snapshot mode")
        if min(self.sample_count, self.left_positive_count, self.right_positive_count, self.both_positive_count, self.min_samples, self.dependency_threshold_bps, self.measured_at) < 0:
            raise ValueError("dependency snapshot counts must be non-negative")
        if self.left_positive_count > self.sample_count or self.right_positive_count > self.sample_count or self.both_positive_count > min(self.left_positive_count, self.right_positive_count):
            raise ValueError("invalid dependency snapshot counts")
        allowed = {"INSUFFICIENT_SAMPLES", "INDEPENDENCE_CHALLENGED", "NO_DEPENDENCY_SIGNAL", "CONDITIONAL_DEPENDENCY_SUPPORTED", "CONDITIONAL_DEPENDENCY_NOT_OBSERVED"}
        if self.assessment not in allowed:
            raise ValueError("invalid dependency assessment")
        if self.snapshot_hash != _digest(self.material()):
            raise ValueError("snapshot_hash does not match dependency calibration material")


def summarize_dependency_samples(
    samples: tuple[DependencyPairSample, ...],
    *,
    min_samples: int,
    dependency_threshold_bps: int,
    measured_at: int,
) -> DependencyCalibrationSnapshot:
    if not samples:
        raise ValueError("dependency calibration requires samples")
    for sample in samples:
        sample.validate()
    pair_key = samples[0].pair_key
    mode = samples[0].declared_mode
    if any(sample.pair_key != pair_key or sample.declared_mode != mode for sample in samples):
        raise ValueError("dependency calibration samples must share one pair key and mode")
    if min_samples < 1 or dependency_threshold_bps < 0 or dependency_threshold_bps > 10_000:
        raise ValueError("invalid dependency calibration policy")
    n = len(samples)
    left = sum(1 for sample in samples if sample.left_positive)
    right = sum(1 for sample in samples if sample.right_positive)
    both = sum(1 for sample in samples if sample.left_positive and sample.right_positive)
    gap = _round_ratio(10_000 * (both * n - left * right), n * n)
    if n < min_samples:
        assessment: DependencyAssessment = "INSUFFICIENT_SAMPLES"
    elif mode == "INDEPENDENT":
        assessment = "INDEPENDENCE_CHALLENGED" if abs(gap) >= dependency_threshold_bps else "NO_DEPENDENCY_SIGNAL"
    else:
        assessment = "CONDITIONAL_DEPENDENCY_SUPPORTED" if abs(gap) >= dependency_threshold_bps else "CONDITIONAL_DEPENDENCY_NOT_OBSERVED"
    fields = {
        "pair_key": pair_key,
        "declared_mode": mode,
        "sample_count": n,
        "left_positive_count": left,
        "right_positive_count": right,
        "both_positive_count": both,
        "independence_gap_bps": gap,
        "min_samples": min_samples,
        "dependency_threshold_bps": dependency_threshold_bps,
        "assessment": assessment,
        "measured_at": measured_at,
    }
    provisional = DependencyCalibrationSnapshot(**fields, snapshot_hash="0" * 64)
    result = DependencyCalibrationSnapshot(**fields, snapshot_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class CalibrationFamilySnapshot:
    calibration_family_ref: str
    forecast_count: int
    mean_forecast_brier_ppm: int | None
    likelihood_scored_count: int
    mean_likelihood_brier_ppm: int | None
    mean_predicted_positive_bps: int | None
    observed_positive_rate_bps: int | None
    marginal_calibration_gap_bps: int | None
    min_samples: int
    marginal_gap_threshold_bps: int
    status: CalibrationStatus
    measured_at: int
    snapshot_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/calibration-family-snapshot/v1.12",
            "calibration_family_ref": self.calibration_family_ref,
            "forecast_count": self.forecast_count,
            "mean_forecast_brier_ppm": self.mean_forecast_brier_ppm,
            "likelihood_scored_count": self.likelihood_scored_count,
            "mean_likelihood_brier_ppm": self.mean_likelihood_brier_ppm,
            "mean_predicted_positive_bps": self.mean_predicted_positive_bps,
            "observed_positive_rate_bps": self.observed_positive_rate_bps,
            "marginal_calibration_gap_bps": self.marginal_calibration_gap_bps,
            "min_samples": self.min_samples,
            "marginal_gap_threshold_bps": self.marginal_gap_threshold_bps,
            "status": self.status,
            "measured_at": self.measured_at,
        }

    def validate(self) -> None:
        if not self.calibration_family_ref or self.forecast_count < 0 or self.likelihood_scored_count < 0 or self.min_samples < 1 or self.marginal_gap_threshold_bps < 0:
            raise ValueError("invalid calibration family snapshot metadata")
        for value in (self.mean_forecast_brier_ppm, self.mean_likelihood_brier_ppm, self.mean_predicted_positive_bps, self.observed_positive_rate_bps):
            if value is not None and value < 0:
                raise ValueError("calibration snapshot metrics must be non-negative")
        if self.status not in {"INSUFFICIENT_SAMPLES", "NO_MARGINAL_MISCALIBRATION_SIGNAL", "MISCALIBRATION_SIGNAL"}:
            raise ValueError("invalid calibration family status")
        _require_digest("snapshot_hash", self.snapshot_hash)
        if self.snapshot_hash != _digest(self.material()):
            raise ValueError("snapshot_hash does not match calibration family material")


def summarize_calibration_family(
    forecast_receipts: tuple[ForecastCalibrationReceipt, ...],
    likelihood_receipts: tuple[LikelihoodCalibrationReceipt, ...],
    *,
    calibration_family_ref: str,
    min_samples: int,
    marginal_gap_threshold_bps: int,
    measured_at: int,
) -> CalibrationFamilySnapshot:
    if min_samples < 1 or marginal_gap_threshold_bps < 0 or marginal_gap_threshold_bps > 10_000:
        raise ValueError("invalid calibration summary policy")
    forecasts = tuple(item for item in forecast_receipts if item.calibration_family_ref == calibration_family_ref)
    likelihoods = tuple(item for item in likelihood_receipts if item.calibration_family_ref == calibration_family_ref and item.scored)
    for item in forecasts:
        item.validate()
    for item in likelihoods:
        item.validate()
    mean_forecast = None if not forecasts else _round_ratio(sum(item.brier_score_ppm for item in forecasts), len(forecasts))
    if likelihoods:
        mean_likelihood = _round_ratio(sum(int(item.brier_score_ppm) for item in likelihoods), len(likelihoods))
        mean_predicted = _round_ratio(sum(item.predicted_positive_bps for item in likelihoods), len(likelihoods))
        observed_rate = _round_ratio(10_000 * sum(1 for item in likelihoods if item.observed_outcome == "POSITIVE"), len(likelihoods))
        gap = observed_rate - mean_predicted
    else:
        mean_likelihood = None
        mean_predicted = None
        observed_rate = None
        gap = None
    if len(likelihoods) < min_samples:
        status: CalibrationStatus = "INSUFFICIENT_SAMPLES"
    else:
        status = "MISCALIBRATION_SIGNAL" if abs(int(gap)) >= marginal_gap_threshold_bps else "NO_MARGINAL_MISCALIBRATION_SIGNAL"
    fields = {
        "calibration_family_ref": calibration_family_ref,
        "forecast_count": len(forecasts),
        "mean_forecast_brier_ppm": mean_forecast,
        "likelihood_scored_count": len(likelihoods),
        "mean_likelihood_brier_ppm": mean_likelihood,
        "mean_predicted_positive_bps": mean_predicted,
        "observed_positive_rate_bps": observed_rate,
        "marginal_calibration_gap_bps": gap,
        "min_samples": min_samples,
        "marginal_gap_threshold_bps": marginal_gap_threshold_bps,
        "status": status,
        "measured_at": measured_at,
    }
    provisional = CalibrationFamilySnapshot(**fields, snapshot_hash="0" * 64)
    result = CalibrationFamilySnapshot(**fields, snapshot_hash=_digest(provisional.material()))
    result.validate()
    return result
