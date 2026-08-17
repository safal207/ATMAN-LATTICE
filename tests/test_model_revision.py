from hashlib import sha256

import pytest

from model.calibration import CalibrationFamilySnapshot, LikelihoodCalibrationReceipt, _digest as calibration_digest
from model.model_revision import (
    apply_revision,
    make_model_revision_proposal,
    replay_revision,
    review_revision,
)
from model.multihypothesis import make_hypothesis_distribution, make_multi_likelihood_model


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def distribution():
    return make_hypothesis_distribution(
        "dist:revision",
        subject_identity_ref="agent:revision",
        probability_bps={"H:A": 5000, "H:B": 5000},
        evidence_state_hash=h("revision:evidence"),
        generation=3,
    )


def base_model(dist):
    return make_multi_likelihood_model(
        candidate_hash=h("candidate:revision"),
        distribution=dist,
        positive_likelihood_bps={"H:A": 9000, "H:B": 1000},
        model_ref="model:revision",
        model_generation=7,
    )


def snapshot(*, status="MISCALIBRATION_SIGNAL"):
    fields = {
        "calibration_family_ref": "family:revision",
        "forecast_count": 6,
        "mean_forecast_brier_ppm": 400000,
        "likelihood_scored_count": 6,
        "mean_likelihood_brier_ppm": 410000,
        "mean_predicted_positive_bps": 9000,
        "observed_positive_rate_bps": 5000,
        "marginal_calibration_gap_bps": -4000,
        "min_samples": 5,
        "marginal_gap_threshold_bps": 1000,
        "status": status,
        "measured_at": 100,
    }
    provisional = CalibrationFamilySnapshot(**fields, snapshot_hash="0" * 64)
    result = CalibrationFamilySnapshot(**fields, snapshot_hash=calibration_digest(provisional.material()))
    result.validate()
    return result


def calibration(index: int, *, outcome: str, resolved="H:A"):
    predicted = 9000 if resolved == "H:A" else 1000
    observed_positive = outcome == "POSITIVE"
    old_brier = (predicted - (10000 if observed_positive else 0)) ** 2 // 100
    fields = {
        "target_hash": h(f"target:{index}"),
        "evidence_hash": h(f"evidence:{index}"),
        "resolution_hash": h(f"resolution:{index}"),
        "calibration_family_ref": "family:revision",
        "likelihood_model_hash": h(f"historical-model:{index}"),
        "likelihood_model_ref": "model:revision",
        "resolved_hypothesis_ref": resolved,
        "predicted_positive_bps": predicted,
        "observed_outcome": outcome,
        "scored": True,
        "brier_score_ppm": old_brier,
        "dependency_mode": "INDEPENDENT",
        "calibrated_at": 200 + index,
    }
    provisional = LikelihoodCalibrationReceipt(**fields, calibration_hash="0" * 64)
    result = LikelihoodCalibrationReceipt(**fields, calibration_hash=calibration_digest(provisional.material()))
    result.validate()
    return result


def proposal(*, proposed=None, signal=None):
    dist = distribution()
    model = base_model(dist)
    value = make_model_revision_proposal(
        proposal_ref="proposal:revision",
        distribution=dist,
        base_model=model,
        calibration_snapshot=signal or snapshot(),
        proposed_positive_likelihood_bps=proposed or {"H:A": 5000, "H:B": 5000},
        reason_ref="reason:historical-miscalibration",
        proposer_ref="proposer:one",
        proposed_at=300,
    )
    return dist, model, value


def test_revision_proposal_requires_actual_miscalibration_signal():
    with pytest.raises(ValueError, match="miscalibration signal"):
        proposal(signal=snapshot(status="NO_MARGINAL_MISCALIBRATION_SIGNAL"))


def test_revision_proposal_advances_exactly_one_model_generation():
    _, model, value = proposal()
    assert value.base_model_generation == model.model_generation
    assert value.proposed_model_generation == model.model_generation + 1
    assert value.base_model_hash == model.model_hash


def test_counterfactual_replay_can_show_improvement_on_same_history():
    _, _, value = proposal()
    history = tuple(calibration(i, outcome="POSITIVE" if i % 2 == 0 else "NEGATIVE") for i in range(6))
    cases, replay = replay_revision(value, history, min_cases=5, replayed_at=400)
    assert len(cases) == 6
    assert replay.status == "IMPROVED"
    assert replay.proposed_mean_brier_ppm < replay.old_mean_brier_ppm
    assert replay.improvement_ppm > 0


def test_counterfactual_replay_preserves_exact_case_set():
    _, _, value = proposal()
    history = tuple(calibration(i, outcome="POSITIVE" if i % 2 == 0 else "NEGATIVE") for i in range(5))
    cases, replay = replay_revision(value, history, min_cases=5, replayed_at=400)
    assert replay.case_hashes == tuple(sorted(item.case_hash for item in cases))


def test_insufficient_replay_cannot_be_approved():
    _, _, value = proposal()
    _, replay = replay_revision(value, (calibration(1, outcome="NEGATIVE"),), min_cases=5, replayed_at=400)
    assert replay.status == "INSUFFICIENT_SCORABLE_CASES"
    with pytest.raises(ValueError, match="requires improved"):
        review_revision(value, replay, decision="APPROVE", rationale_ref="r", reviewer_ref="reviewer:two", reviewed_at=500)


def test_no_improvement_cannot_be_approved():
    _, _, value = proposal(proposed={"H:A": 10000, "H:B": 0})
    history = tuple(calibration(i, outcome="NEGATIVE") for i in range(5))
    _, replay = replay_revision(value, history, min_cases=5, replayed_at=400)
    assert replay.status == "NO_IMPROVEMENT"
    with pytest.raises(ValueError, match="requires improved"):
        review_revision(value, replay, decision="APPROVE", rationale_ref="r", reviewer_ref="reviewer:two", reviewed_at=500)


def test_proposer_cannot_review_own_revision():
    _, _, value = proposal()
    history = tuple(calibration(i, outcome="POSITIVE" if i % 2 == 0 else "NEGATIVE") for i in range(6))
    _, replay = replay_revision(value, history, min_cases=5, replayed_at=400)
    with pytest.raises(ValueError, match="independent"):
        review_revision(value, replay, decision="APPROVE", rationale_ref="r", reviewer_ref=value.proposer_ref, reviewed_at=500)


def test_approved_improved_revision_creates_new_model_without_erasing_old_model():
    dist, model, value = proposal()
    history = tuple(calibration(i, outcome="POSITIVE" if i % 2 == 0 else "NEGATIVE") for i in range(6))
    _, replay = replay_revision(value, history, min_cases=5, replayed_at=400)
    review = review_revision(value, replay, decision="APPROVE", rationale_ref="review:better-calibration", reviewer_ref="reviewer:two", reviewed_at=500)
    new_model, receipt = apply_revision(
        distribution=dist,
        current_model=model,
        proposal=value,
        replay=replay,
        review=review,
        applied_at=600,
        applier_ref="applier:three",
    )
    assert model.model_hash == value.base_model_hash
    assert new_model.model_hash != model.model_hash
    assert new_model.model_generation == model.model_generation + 1
    assert receipt.base_model_hash == model.model_hash
    assert receipt.new_model_hash == new_model.model_hash


def test_stale_base_model_blocks_revision_even_after_approval():
    dist, model, value = proposal()
    history = tuple(calibration(i, outcome="POSITIVE" if i % 2 == 0 else "NEGATIVE") for i in range(6))
    _, replay = replay_revision(value, history, min_cases=5, replayed_at=400)
    review = review_revision(value, replay, decision="APPROVE", rationale_ref="review:better", reviewer_ref="reviewer:two", reviewed_at=500)
    stale_current = make_multi_likelihood_model(
        candidate_hash=model.candidate_hash,
        distribution=dist,
        positive_likelihood_bps={"H:A": 8000, "H:B": 2000},
        model_ref=model.model_ref,
        model_generation=model.model_generation + 1,
    )
    with pytest.raises(ValueError, match="changed since revision proposal"):
        apply_revision(
            distribution=dist,
            current_model=stale_current,
            proposal=value,
            replay=replay,
            review=review,
            applied_at=600,
            applier_ref="applier:three",
        )
