from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from model.calibration import CalibrationFamilySnapshot, LikelihoodCalibrationReceipt, binary_brier_score_ppm
from model.multihypothesis import HypothesisDistribution, MultiLikelihoodModel, make_multi_likelihood_model

ReplayStatus = Literal["INSUFFICIENT_SCORABLE_CASES", "IMPROVED", "NO_IMPROVEMENT"]
ReviewDecision = Literal["APPROVE", "HOLD", "REJECT"]


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


@dataclass(frozen=True)
class ModelRevisionProposal:
    proposal_ref: str
    candidate_hash: str
    subject_identity_ref: str
    calibration_family_ref: str
    calibration_snapshot_hash: str
    base_distribution_hash: str
    base_model_hash: str
    model_ref: str
    base_model_generation: int
    proposed_model_generation: int
    proposed_positive_likelihood_bps: tuple[tuple[str, int], ...]
    conditioning_evidence_hashes: tuple[str, ...]
    reason_ref: str
    proposer_ref: str
    proposed_at: int
    proposal_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/model-revision-proposal/v1.13",
            "proposal_ref": self.proposal_ref,
            "candidate_hash": self.candidate_hash,
            "subject_identity_ref": self.subject_identity_ref,
            "calibration_family_ref": self.calibration_family_ref,
            "calibration_snapshot_hash": self.calibration_snapshot_hash,
            "base_distribution_hash": self.base_distribution_hash,
            "base_model_hash": self.base_model_hash,
            "model_ref": self.model_ref,
            "base_model_generation": self.base_model_generation,
            "proposed_model_generation": self.proposed_model_generation,
            "proposed_positive_likelihood_bps": [[key, value] for key, value in self.proposed_positive_likelihood_bps],
            "conditioning_evidence_hashes": list(self.conditioning_evidence_hashes),
            "reason_ref": self.reason_ref,
            "proposer_ref": self.proposer_ref,
            "proposed_at": self.proposed_at,
        }

    def validate(self) -> None:
        if not self.proposal_ref or not self.subject_identity_ref or not self.calibration_family_ref or not self.model_ref or not self.reason_ref or not self.proposer_ref:
            raise ValueError("revision proposal refs are required")
        for name, value in (
            ("candidate_hash", self.candidate_hash),
            ("calibration_snapshot_hash", self.calibration_snapshot_hash),
            ("base_distribution_hash", self.base_distribution_hash),
            ("base_model_hash", self.base_model_hash),
            ("proposal_hash", self.proposal_hash),
        ):
            _require_digest(name, value)
        if self.proposed_model_generation != self.base_model_generation + 1:
            raise ValueError("proposed model generation must advance exactly once")
        refs = [key for key, _ in self.proposed_positive_likelihood_bps]
        if len(refs) < 2 or refs != sorted(refs) or len(set(refs)) != len(refs):
            raise ValueError("proposed likelihood hypotheses must be unique, sorted, and plural")
        if any(not key or value < 0 or value > 10_000 for key, value in self.proposed_positive_likelihood_bps):
            raise ValueError("proposed likelihoods must be 0..10000 basis points")
        for value in self.conditioning_evidence_hashes:
            _require_digest("conditioning_evidence_hash", value)
        if tuple(sorted(set(self.conditioning_evidence_hashes))) != self.conditioning_evidence_hashes:
            raise ValueError("conditioning evidence hashes must be unique and sorted")
        if self.proposed_at < 0:
            raise ValueError("proposed_at must be >= 0")
        if self.proposal_hash != _digest(self.material()):
            raise ValueError("proposal_hash does not match model revision proposal material")


def make_model_revision_proposal(
    *,
    proposal_ref: str,
    distribution: HypothesisDistribution,
    base_model: MultiLikelihoodModel,
    calibration_snapshot: CalibrationFamilySnapshot,
    proposed_positive_likelihood_bps: dict[str, int] | tuple[tuple[str, int], ...],
    reason_ref: str,
    proposer_ref: str,
    proposed_at: int,
) -> ModelRevisionProposal:
    distribution.validate()
    base_model.validate()
    calibration_snapshot.validate()
    if base_model.distribution_hash != distribution.distribution_hash:
        raise ValueError("revision proposal requires current distribution/model binding")
    if calibration_snapshot.status != "MISCALIBRATION_SIGNAL":
        raise ValueError("model revision proposal requires a miscalibration signal")
    entries = tuple(sorted(dict(proposed_positive_likelihood_bps).items()))
    if tuple(key for key, _ in entries) != tuple(key for key, _ in distribution.probability_bps):
        raise ValueError("proposed likelihoods must exactly cover distribution hypotheses")
    fields = {
        "proposal_ref": proposal_ref,
        "candidate_hash": base_model.candidate_hash,
        "subject_identity_ref": distribution.subject_identity_ref,
        "calibration_family_ref": calibration_snapshot.calibration_family_ref,
        "calibration_snapshot_hash": calibration_snapshot.snapshot_hash,
        "base_distribution_hash": distribution.distribution_hash,
        "base_model_hash": base_model.model_hash,
        "model_ref": base_model.model_ref,
        "base_model_generation": base_model.model_generation,
        "proposed_model_generation": base_model.model_generation + 1,
        "proposed_positive_likelihood_bps": entries,
        "conditioning_evidence_hashes": base_model.conditioning_evidence_hashes,
        "reason_ref": reason_ref,
        "proposer_ref": proposer_ref,
        "proposed_at": proposed_at,
    }
    provisional = ModelRevisionProposal(**fields, proposal_hash="0" * 64)
    result = ModelRevisionProposal(**fields, proposal_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class CounterfactualReplayCase:
    calibration_hash: str
    resolved_hypothesis_ref: str
    observed_outcome: str
    old_predicted_positive_bps: int
    proposed_predicted_positive_bps: int
    old_brier_score_ppm: int
    proposed_brier_score_ppm: int
    case_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/model-revision-replay-case/v1.13",
            "calibration_hash": self.calibration_hash,
            "resolved_hypothesis_ref": self.resolved_hypothesis_ref,
            "observed_outcome": self.observed_outcome,
            "old_predicted_positive_bps": self.old_predicted_positive_bps,
            "proposed_predicted_positive_bps": self.proposed_predicted_positive_bps,
            "old_brier_score_ppm": self.old_brier_score_ppm,
            "proposed_brier_score_ppm": self.proposed_brier_score_ppm,
        }

    def validate(self) -> None:
        _require_digest("calibration_hash", self.calibration_hash)
        _require_digest("case_hash", self.case_hash)
        if not self.resolved_hypothesis_ref or self.observed_outcome not in {"POSITIVE", "NEGATIVE"}:
            raise ValueError("replay case requires conclusive observed outcome")
        for value in (self.old_predicted_positive_bps, self.proposed_predicted_positive_bps):
            if value < 0 or value > 10_000:
                raise ValueError("replay probabilities must be 0..10000 basis points")
        for value in (self.old_brier_score_ppm, self.proposed_brier_score_ppm):
            if value < 0 or value > 1_000_000:
                raise ValueError("replay Brier scores must be 0..1000000 ppm")
        if self.case_hash != _digest(self.material()):
            raise ValueError("case_hash does not match replay case material")


def make_replay_case(proposal: ModelRevisionProposal, calibration: LikelihoodCalibrationReceipt) -> CounterfactualReplayCase:
    proposal.validate()
    calibration.validate()
    if not calibration.scored or calibration.observed_outcome == "INCONCLUSIVE" or calibration.brier_score_ppm is None:
        raise ValueError("counterfactual replay requires scored calibration")
    if calibration.calibration_family_ref != proposal.calibration_family_ref or calibration.likelihood_model_ref != proposal.model_ref:
        raise ValueError("replay calibration family/model mismatch")
    proposed = dict(proposal.proposed_positive_likelihood_bps)
    if calibration.resolved_hypothesis_ref not in proposed:
        raise ValueError("replay resolved hypothesis is outside proposed model")
    predicted = proposed[calibration.resolved_hypothesis_ref]
    fields = {
        "calibration_hash": calibration.calibration_hash,
        "resolved_hypothesis_ref": calibration.resolved_hypothesis_ref,
        "observed_outcome": calibration.observed_outcome,
        "old_predicted_positive_bps": calibration.predicted_positive_bps,
        "proposed_predicted_positive_bps": predicted,
        "old_brier_score_ppm": int(calibration.brier_score_ppm),
        "proposed_brier_score_ppm": binary_brier_score_ppm(predicted, calibration.observed_outcome == "POSITIVE"),
    }
    provisional = CounterfactualReplayCase(**fields, case_hash="0" * 64)
    result = CounterfactualReplayCase(**fields, case_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class CounterfactualReplayReceipt:
    proposal_hash: str
    case_hashes: tuple[str, ...]
    scored_case_count: int
    min_cases: int
    old_mean_brier_ppm: int | None
    proposed_mean_brier_ppm: int | None
    improvement_ppm: int | None
    status: ReplayStatus
    replayed_at: int
    replay_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/model-revision-counterfactual-replay/v1.13",
            "proposal_hash": self.proposal_hash,
            "case_hashes": list(self.case_hashes),
            "scored_case_count": self.scored_case_count,
            "min_cases": self.min_cases,
            "old_mean_brier_ppm": self.old_mean_brier_ppm,
            "proposed_mean_brier_ppm": self.proposed_mean_brier_ppm,
            "improvement_ppm": self.improvement_ppm,
            "status": self.status,
            "replayed_at": self.replayed_at,
        }

    def validate(self) -> None:
        _require_digest("proposal_hash", self.proposal_hash)
        _require_digest("replay_hash", self.replay_hash)
        for value in self.case_hashes:
            _require_digest("case_hash", value)
        if tuple(sorted(set(self.case_hashes))) != self.case_hashes:
            raise ValueError("replay case hashes must be unique and sorted")
        if self.scored_case_count != len(self.case_hashes) or self.min_cases < 1 or self.replayed_at < 0:
            raise ValueError("invalid replay count/policy metadata")
        if self.status == "INSUFFICIENT_SCORABLE_CASES":
            if self.scored_case_count >= self.min_cases:
                raise ValueError("insufficient replay status requires too few cases")
        else:
            if self.scored_case_count < self.min_cases or self.old_mean_brier_ppm is None or self.proposed_mean_brier_ppm is None or self.improvement_ppm is None:
                raise ValueError("complete replay status requires scores")
            expected = self.old_mean_brier_ppm - self.proposed_mean_brier_ppm
            if self.improvement_ppm != expected:
                raise ValueError("replay improvement does not match Brier means")
            if self.status == "IMPROVED" and self.improvement_ppm <= 0:
                raise ValueError("IMPROVED requires positive improvement")
            if self.status == "NO_IMPROVEMENT" and self.improvement_ppm > 0:
                raise ValueError("NO_IMPROVEMENT cannot have positive improvement")
        if self.replay_hash != _digest(self.material()):
            raise ValueError("replay_hash does not match counterfactual replay material")


def replay_revision(
    proposal: ModelRevisionProposal,
    calibrations: tuple[LikelihoodCalibrationReceipt, ...],
    *,
    min_cases: int,
    replayed_at: int,
) -> tuple[tuple[CounterfactualReplayCase, ...], CounterfactualReplayReceipt]:
    proposal.validate()
    if min_cases < 1:
        raise ValueError("min_cases must be >= 1")
    cases: list[CounterfactualReplayCase] = []
    for calibration in calibrations:
        calibration.validate()
        if not calibration.scored or calibration.observed_outcome == "INCONCLUSIVE":
            continue
        if calibration.calibration_family_ref != proposal.calibration_family_ref or calibration.likelihood_model_ref != proposal.model_ref:
            continue
        cases.append(make_replay_case(proposal, calibration))
    cases_tuple = tuple(sorted(cases, key=lambda item: item.case_hash))
    n = len(cases_tuple)
    if n < min_cases:
        old_mean = proposed_mean = improvement = None
        status: ReplayStatus = "INSUFFICIENT_SCORABLE_CASES"
    else:
        old_mean = _round_ratio(sum(item.old_brier_score_ppm for item in cases_tuple), n)
        proposed_mean = _round_ratio(sum(item.proposed_brier_score_ppm for item in cases_tuple), n)
        improvement = old_mean - proposed_mean
        status = "IMPROVED" if improvement > 0 else "NO_IMPROVEMENT"
    fields = {
        "proposal_hash": proposal.proposal_hash,
        "case_hashes": tuple(item.case_hash for item in cases_tuple),
        "scored_case_count": n,
        "min_cases": min_cases,
        "old_mean_brier_ppm": old_mean,
        "proposed_mean_brier_ppm": proposed_mean,
        "improvement_ppm": improvement,
        "status": status,
        "replayed_at": replayed_at,
    }
    provisional = CounterfactualReplayReceipt(**fields, replay_hash="0" * 64)
    receipt = CounterfactualReplayReceipt(**fields, replay_hash=_digest(provisional.material()))
    receipt.validate()
    return cases_tuple, receipt


@dataclass(frozen=True)
class ModelRevisionReviewReceipt:
    proposal_hash: str
    replay_hash: str
    decision: ReviewDecision
    rationale_ref: str
    proposer_ref: str
    reviewer_ref: str
    reviewed_at: int
    review_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/model-revision-review/v1.13",
            "proposal_hash": self.proposal_hash,
            "replay_hash": self.replay_hash,
            "decision": self.decision,
            "rationale_ref": self.rationale_ref,
            "proposer_ref": self.proposer_ref,
            "reviewer_ref": self.reviewer_ref,
            "reviewed_at": self.reviewed_at,
        }

    def validate(self) -> None:
        _require_digest("proposal_hash", self.proposal_hash)
        _require_digest("replay_hash", self.replay_hash)
        _require_digest("review_hash", self.review_hash)
        if self.decision not in {"APPROVE", "HOLD", "REJECT"} or not self.rationale_ref or not self.proposer_ref or not self.reviewer_ref:
            raise ValueError("invalid model revision review")
        if self.proposer_ref == self.reviewer_ref:
            raise ValueError("model revision review must be independent of proposer")
        if self.reviewed_at < 0:
            raise ValueError("reviewed_at must be >= 0")
        if self.review_hash != _digest(self.material()):
            raise ValueError("review_hash does not match review material")


def review_revision(
    proposal: ModelRevisionProposal,
    replay: CounterfactualReplayReceipt,
    *,
    decision: ReviewDecision,
    rationale_ref: str,
    reviewer_ref: str,
    reviewed_at: int,
) -> ModelRevisionReviewReceipt:
    proposal.validate()
    replay.validate()
    if replay.proposal_hash != proposal.proposal_hash:
        raise ValueError("review replay/proposal binding mismatch")
    if decision == "APPROVE" and replay.status != "IMPROVED":
        raise ValueError("APPROVE requires improved counterfactual replay")
    fields = {
        "proposal_hash": proposal.proposal_hash,
        "replay_hash": replay.replay_hash,
        "decision": decision,
        "rationale_ref": rationale_ref,
        "proposer_ref": proposal.proposer_ref,
        "reviewer_ref": reviewer_ref,
        "reviewed_at": reviewed_at,
    }
    provisional = ModelRevisionReviewReceipt(**fields, review_hash="0" * 64)
    result = ModelRevisionReviewReceipt(**fields, review_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class ModelRevisionReceipt:
    proposal_hash: str
    replay_hash: str
    review_hash: str
    calibration_snapshot_hash: str
    base_model_hash: str
    new_model_hash: str
    model_ref: str
    old_model_generation: int
    new_model_generation: int
    applied_at: int
    applier_ref: str
    revision_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/model-revision/v1.13",
            "proposal_hash": self.proposal_hash,
            "replay_hash": self.replay_hash,
            "review_hash": self.review_hash,
            "calibration_snapshot_hash": self.calibration_snapshot_hash,
            "base_model_hash": self.base_model_hash,
            "new_model_hash": self.new_model_hash,
            "model_ref": self.model_ref,
            "old_model_generation": self.old_model_generation,
            "new_model_generation": self.new_model_generation,
            "applied_at": self.applied_at,
            "applier_ref": self.applier_ref,
        }

    def validate(self) -> None:
        for name, value in (
            ("proposal_hash", self.proposal_hash),
            ("replay_hash", self.replay_hash),
            ("review_hash", self.review_hash),
            ("calibration_snapshot_hash", self.calibration_snapshot_hash),
            ("base_model_hash", self.base_model_hash),
            ("new_model_hash", self.new_model_hash),
            ("revision_hash", self.revision_hash),
        ):
            _require_digest(name, value)
        if not self.model_ref or not self.applier_ref or self.new_model_generation != self.old_model_generation + 1 or self.applied_at < 0:
            raise ValueError("invalid applied model revision metadata")
        if self.revision_hash != _digest(self.material()):
            raise ValueError("revision_hash does not match model revision material")


def apply_revision(
    *,
    distribution: HypothesisDistribution,
    current_model: MultiLikelihoodModel,
    proposal: ModelRevisionProposal,
    replay: CounterfactualReplayReceipt,
    review: ModelRevisionReviewReceipt,
    applied_at: int,
    applier_ref: str,
) -> tuple[MultiLikelihoodModel, ModelRevisionReceipt]:
    distribution.validate()
    current_model.validate()
    proposal.validate()
    replay.validate()
    review.validate()
    if current_model.model_hash != proposal.base_model_hash or current_model.model_generation != proposal.base_model_generation:
        raise ValueError("current model changed since revision proposal")
    if distribution.distribution_hash != proposal.base_distribution_hash or current_model.distribution_hash != distribution.distribution_hash:
        raise ValueError("current distribution changed since revision proposal")
    if replay.proposal_hash != proposal.proposal_hash or review.proposal_hash != proposal.proposal_hash or review.replay_hash != replay.replay_hash:
        raise ValueError("revision proposal/replay/review binding mismatch")
    if replay.status != "IMPROVED" or review.decision != "APPROVE":
        raise ValueError("model revision requires improved replay and APPROVE review")
    if applied_at < review.reviewed_at:
        raise ValueError("revision apply cannot precede review")
    new_model = make_multi_likelihood_model(
        candidate_hash=current_model.candidate_hash,
        distribution=distribution,
        positive_likelihood_bps=proposal.proposed_positive_likelihood_bps,
        conditioning_evidence_hashes=proposal.conditioning_evidence_hashes,
        model_ref=current_model.model_ref,
        model_generation=current_model.model_generation + 1,
    )
    fields = {
        "proposal_hash": proposal.proposal_hash,
        "replay_hash": replay.replay_hash,
        "review_hash": review.review_hash,
        "calibration_snapshot_hash": proposal.calibration_snapshot_hash,
        "base_model_hash": current_model.model_hash,
        "new_model_hash": new_model.model_hash,
        "model_ref": current_model.model_ref,
        "old_model_generation": current_model.model_generation,
        "new_model_generation": new_model.model_generation,
        "applied_at": applied_at,
        "applier_ref": applier_ref,
    }
    provisional = ModelRevisionReceipt(**fields, revision_hash="0" * 64)
    receipt = ModelRevisionReceipt(**fields, revision_hash=_digest(provisional.material()))
    receipt.validate()
    return new_model, receipt
