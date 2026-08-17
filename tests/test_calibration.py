from hashlib import sha256

import pytest

from model.calibration import (
    binary_brier_score_ppm,
    calibrate_forecast,
    calibrate_likelihood,
    categorical_brier_score_ppm,
    make_calibration_target,
    make_dependency_pair_sample,
    make_resolved_outcome,
    summarize_calibration_family,
    summarize_dependency_samples,
)
from model.multihypothesis import (
    interpret_multi_completion,
    make_evidence_dependency,
    make_hypothesis_distribution,
    make_multi_evidence_rule,
    make_multi_likelihood_model,
)


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def base_case(*, case_ref="case:1", candidate_seed="candidate:1", model_ref="model:root", mode="INDEPENDENT", parent_hashes=(), probabilities=None, likelihoods=None, decision="PASS", committed_at=10, completed_at=20):
    probabilities = probabilities or {"H:A": 4000, "H:B": 3500, "H:C": 2500}
    likelihoods = likelihoods or {"H:A": 9000, "H:B": 4000, "H:C": 1000}
    distribution = make_hypothesis_distribution(
        case_ref,
        subject_identity_ref="agent:calibration",
        probability_bps=probabilities,
        evidence_state_hash=h(f"evidence:{case_ref}"),
        generation=1,
    )
    candidate_hash = h(candidate_seed)
    model = make_multi_likelihood_model(
        candidate_hash=candidate_hash,
        distribution=distribution,
        positive_likelihood_bps=likelihoods,
        conditioning_evidence_hashes=tuple(parent_hashes),
        model_ref=model_ref,
        model_generation=1,
    )
    dependency = make_evidence_dependency(
        candidate_hash=candidate_hash,
        source_event_hash=h(f"source:{candidate_seed}"),
        derivation_hash=h(f"derivation:{candidate_seed}"),
        dependency_group_ref="group:root-cause",
        mode=mode,
        parent_evidence_hashes=tuple(parent_hashes),
        declaration_ref=f"dependency:{candidate_seed}",
        declaration_generation=1,
        declared_at=committed_at,
    )
    rule = make_multi_evidence_rule(
        candidate_hash=candidate_hash,
        likelihood_model_hash=model.model_hash,
        pass_outcome="POSITIVE",
        hold_outcome="INCONCLUSIVE",
        fail_outcome="NEGATIVE",
        rule_ref=f"rule:{candidate_seed}",
        rule_generation=1,
        registered_at=committed_at,
    )
    target = make_calibration_target(
        target_ref=f"target:{candidate_seed}",
        calibration_family_ref="family:root-cause-v1",
        distribution=distribution,
        likelihood_model=model,
        dependency=dependency,
        committed_at=committed_at,
    )
    evidence = interpret_multi_completion(
        candidate_hash=candidate_hash,
        work_hash=h(f"work:{candidate_seed}"),
        completion_hash=h(f"completion:{candidate_seed}"),
        completion_decision=decision,
        distribution=distribution,
        likelihood_model=model,
        dependency=dependency,
        rule=rule,
        completion_completed_at=completed_at,
        interpreted_at=completed_at + 1,
    )
    resolution = make_resolved_outcome(
        target,
        resolution_ref=f"resolution:{case_ref}",
        resolved_hypothesis_ref="H:A",
        resolution_source_hash=h(f"resolution-source:{case_ref}"),
        resolved_at=completed_at + 10,
        resolver_ref="resolver:gold",
    )
    return distribution, model, dependency, target, evidence, resolution


def test_calibration_target_freezes_distribution_likelihood_and_dependency():
    distribution, model, dependency, target, _, _ = base_case()
    assert target.distribution_hash == distribution.distribution_hash
    assert target.likelihood_model_hash == model.model_hash
    assert target.dependency_hash == dependency.dependency_hash
    assert target.probability_bps == distribution.probability_bps
    assert target.positive_likelihood_bps == model.positive_likelihood_bps


def test_resolution_cannot_precede_target_or_resolve_unknown_hypothesis():
    _, _, _, target, _, _ = base_case()
    with pytest.raises(ValueError, match="outside calibration target"):
        make_resolved_outcome(target, resolution_ref="r", resolved_hypothesis_ref="H:Z", resolution_source_hash=h("r"), resolved_at=30, resolver_ref="resolver")
    with pytest.raises(ValueError, match="cannot precede"):
        make_resolved_outcome(target, resolution_ref="r", resolved_hypothesis_ref="H:A", resolution_source_hash=h("r"), resolved_at=9, resolver_ref="resolver")


def test_categorical_brier_rewards_accurate_forecast_and_penalizes_wrong_certainty():
    assert categorical_brier_score_ppm((('H:A', 10000), ('H:B', 0)), "H:A") == 0
    assert categorical_brier_score_ppm((('H:A', 0), ('H:B', 10000)), "H:A") == 2_000_000
    assert categorical_brier_score_ppm((('H:A', 5000), ('H:B', 5000)), "H:A") == 500_000


def test_forecast_calibration_binds_frozen_target_to_resolution():
    _, _, _, target, _, resolution = base_case()
    receipt = calibrate_forecast(target, resolution, calibrated_at=40)
    assert receipt.resolved_probability_bps == 4000
    assert receipt.brier_score_ppm == categorical_brier_score_ppm(target.probability_bps, "H:A")


def test_likelihood_calibration_scores_actual_observation_against_resolved_hypothesis():
    _, _, _, target, evidence, resolution = base_case(decision="PASS")
    receipt = calibrate_likelihood(target, evidence, resolution, calibrated_at=40)
    assert receipt.predicted_positive_bps == 9000
    assert receipt.observed_outcome == "POSITIVE"
    assert receipt.brier_score_ppm == binary_brier_score_ppm(9000, True) == 10_000


def test_inconclusive_likelihood_is_preserved_but_not_scored():
    _, _, _, target, evidence, resolution = base_case(decision="HOLD")
    receipt = calibrate_likelihood(target, evidence, resolution, calibrated_at=40)
    assert receipt.scored is False
    assert receipt.brier_score_ppm is None
    assert receipt.observed_outcome == "INCONCLUSIVE"


def test_likelihood_calibration_rejects_posthoc_model_substitution():
    distribution, _, dependency, target, evidence, resolution = base_case()
    changed_model = make_multi_likelihood_model(
        candidate_hash=target.candidate_hash,
        distribution=distribution,
        positive_likelihood_bps={"H:A": 1000, "H:B": 8000, "H:C": 1000},
        model_ref="model:root",
        model_generation=2,
    )
    changed_target = make_calibration_target(
        target_ref="target:changed",
        calibration_family_ref="family:root-cause-v1",
        distribution=distribution,
        likelihood_model=changed_model,
        dependency=dependency,
        committed_at=10,
    )
    with pytest.raises(ValueError, match="frozen-assumption"):
        calibrate_likelihood(changed_target, evidence, resolution, calibrated_at=40)


def pair_case(index: int, left_positive: bool, right_positive: bool, *, right_mode="INDEPENDENT"):
    case_ref = f"case:pair:{index}"
    left = base_case(
        case_ref=case_ref,
        candidate_seed=f"left:{index}",
        model_ref="signal:left",
        decision="PASS" if left_positive else "FAIL",
        committed_at=10,
        completed_at=20,
    )
    left_target, left_evidence, resolution = left[3], left[4], left[5]
    parents = (left_evidence.evidence_hash,) if right_mode == "CONDITIONAL" else ()
    right = base_case(
        case_ref=case_ref,
        candidate_seed=f"right:{index}",
        model_ref="signal:right",
        mode=right_mode,
        parent_hashes=parents,
        decision="PASS" if right_positive else "FAIL",
        committed_at=22,
        completed_at=24,
    )
    right_target, right_evidence = right[3], right[4]
    return make_dependency_pair_sample(
        left_target=left_target,
        left_evidence=left_evidence,
        right_target=right_target,
        right_evidence=right_evidence,
        resolution=resolution,
        sampled_at=40,
    )


def test_dependency_learning_challenges_independence_when_joint_rate_is_far_from_product():
    samples = tuple(pair_case(i, left, right) for i, (left, right) in enumerate([
        (True, True), (True, True), (True, True), (True, True), (True, True),
        (False, False), (False, False), (False, False), (False, False), (False, False),
    ]))
    snapshot = summarize_dependency_samples(samples, min_samples=8, dependency_threshold_bps=1000, measured_at=50)
    assert snapshot.independence_gap_bps == 2500
    assert snapshot.assessment == "INDEPENDENCE_CHALLENGED"


def test_balanced_joint_samples_produce_no_dependency_signal_not_proof_of_independence():
    samples = tuple(pair_case(i, left, right) for i, (left, right) in enumerate([
        (True, True), (True, False), (False, True), (False, False),
        (True, True), (True, False), (False, True), (False, False),
    ]))
    snapshot = summarize_dependency_samples(samples, min_samples=8, dependency_threshold_bps=500, measured_at=50)
    assert snapshot.independence_gap_bps == 0
    assert snapshot.assessment == "NO_DEPENDENCY_SIGNAL"


def test_conditional_dependency_preserves_parent_bound_relation_in_samples():
    samples = tuple(pair_case(i, left, right, right_mode="CONDITIONAL") for i, (left, right) in enumerate([
        (True, True), (True, True), (True, True), (True, True),
        (False, False), (False, False), (False, False), (False, False),
    ]))
    snapshot = summarize_dependency_samples(samples, min_samples=8, dependency_threshold_bps=1000, measured_at=50)
    assert snapshot.assessment == "CONDITIONAL_DEPENDENCY_SUPPORTED"


def test_family_snapshot_detects_marginal_likelihood_miscalibration():
    forecasts = []
    likelihoods = []
    for index, decision in enumerate(("PASS", "FAIL", "PASS", "FAIL")):
        _, _, _, target, evidence, resolution = base_case(case_ref=f"family:{index}", candidate_seed=f"family-candidate:{index}", decision=decision)
        forecasts.append(calibrate_forecast(target, resolution, calibrated_at=40))
        likelihoods.append(calibrate_likelihood(target, evidence, resolution, calibrated_at=40))
    snapshot = summarize_calibration_family(
        tuple(forecasts),
        tuple(likelihoods),
        calibration_family_ref="family:root-cause-v1",
        min_samples=4,
        marginal_gap_threshold_bps=1000,
        measured_at=50,
    )
    assert snapshot.likelihood_scored_count == 4
    assert snapshot.mean_predicted_positive_bps == 9000
    assert snapshot.observed_positive_rate_bps == 5000
    assert snapshot.marginal_calibration_gap_bps == -4000
    assert snapshot.status == "MISCALIBRATION_SIGNAL"
