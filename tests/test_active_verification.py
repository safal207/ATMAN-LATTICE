from dataclasses import replace

import pytest

from model.active_verification import (
    entropy_microbits,
    expected_information_gain,
    make_active_verification_policy,
    make_hypothesis_state,
    make_likelihood_model,
    plan_active_verification,
)
from model.verification_economy import (
    build_cost_estimator,
    make_economic_candidate,
    make_verification_economy_policy,
    record_cost_observation,
)


def h(ch: str) -> str:
    return ch * 64


def candidate(ch: str, *, identity: str = "agent:1", estimator_key: str = "geometry", risk: int = 0, submitted_at: int = 100):
    return make_economic_candidate(
        work_hash=h(ch),
        subject_identity_ref=identity,
        estimator_key=estimator_key,
        declared_cost_units=1,
        value_units=1,
        risk_units=risk,
        priority=0,
        submitted_at=submitted_at,
    )


def hypothesis(ch: str, *, identity: str = "agent:1", probability: int = 5000, generation: int = 1):
    return make_hypothesis_state(
        f"hypothesis:{ch}",
        subject_identity_ref=identity,
        true_probability_bps=probability,
        evidence_state_hash=h("f"),
        generation=generation,
    )


def likelihood(item, hyp, *, sensitivity: int, false_positive: int, generation: int = 1):
    return make_likelihood_model(
        candidate_hash=item.candidate_hash,
        hypothesis_hash=hyp.hypothesis_hash,
        positive_if_true_bps=sensitivity,
        positive_if_false_bps=false_positive,
        model_ref=f"model:{item.work_hash[:4]}",
        model_generation=generation,
    )


def economy_policy(**overrides):
    values = dict(
        budget_units=20,
        max_funded_items=10,
        bootstrap_cost_units=10,
        min_samples_for_confidence=0,
        uncertainty_premium_units=0,
        value_weight=1,
        risk_weight=1,
        priority_weight=1,
        aging_quantum=60,
    )
    values.update(overrides)
    return make_verification_economy_policy(**values)


def active_policy(**overrides):
    values = dict(
        budget_units=20,
        max_selected_items=10,
        minimum_information_gain_microbits=1,
        aging_quantum=60,
        aging_weight=0,
        risk_weight=0,
    )
    values.update(overrides)
    return make_active_verification_policy(**values)


def estimator(key: str, cost: int):
    obs = record_cost_observation(
        work_hash=h("d"),
        completion_hash=h("e"),
        estimator_key=key,
        observed_cost_units=cost,
        measured_at=50,
        meter_ref="meter:test",
    )
    return build_cost_estimator(key, [obs])


def test_half_probability_has_one_bit_entropy():
    assert entropy_microbits(5000) == 1_000_000
    assert entropy_microbits(0) == 0
    assert entropy_microbits(10_000) == 0


def test_perfect_test_at_maximum_uncertainty_yields_one_bit_expected_gain():
    item = candidate("a")
    hyp = hypothesis("a", probability=5000)
    model = likelihood(item, hyp, sensitivity=10_000, false_positive=0)
    result = expected_information_gain(item, hyp, model, estimated_cost=10, computed_at=100)
    assert result.prior_entropy_microbits == 1_000_000
    assert result.expected_posterior_entropy_microbits == 0
    assert result.expected_information_gain_microbits == 1_000_000
    assert result.information_per_cost_scaled == 100_000_000_000


def test_uninformative_test_has_zero_expected_gain():
    item = candidate("a")
    hyp = hypothesis("a", probability=5000)
    model = likelihood(item, hyp, sensitivity=5000, false_positive=5000)
    result = expected_information_gain(item, hyp, model, estimated_cost=10, computed_at=100)
    assert result.expected_information_gain_microbits == 0


def test_information_model_must_bind_exact_candidate_and_hypothesis():
    left = candidate("a")
    right = candidate("b")
    hyp = hypothesis("a")
    model = likelihood(left, hyp, sensitivity=9000, false_positive=1000)
    with pytest.raises(ValueError, match="likelihood candidate mismatch"):
        expected_information_gain(right, hyp, model, estimated_cost=10, computed_at=100)


def test_candidate_and_hypothesis_identity_must_match():
    item = candidate("a", identity="agent:1")
    hyp = hypothesis("a", identity="agent:2")
    model = likelihood(item, hyp, sensitivity=9000, false_positive=1000)
    with pytest.raises(ValueError, match="identity mismatch"):
        expected_information_gain(item, hyp, model, estimated_cost=10, computed_at=100)


def test_active_plan_prefers_more_information_per_cost():
    high = candidate("a", estimator_key="high")
    low = candidate("b", estimator_key="low")
    high_h = hypothesis("a")
    low_h = hypothesis("b")
    hypotheses = {high.candidate_hash: high_h, low.candidate_hash: low_h}
    models = {
        high.candidate_hash: likelihood(high, high_h, sensitivity=9500, false_positive=500),
        low.candidate_hash: likelihood(low, low_h, sensitivity=6500, false_positive=3500),
    }
    estimators = {"high": estimator("high", 5), "low": estimator("low", 5)}
    plan, insights = plan_active_verification(
        [low, high], hypotheses, models, estimators, economy_policy(), active_policy(budget_units=5, max_selected_items=1), measured_at=200
    )
    assert plan.selected_candidate_hashes == (high.candidate_hash,)
    assert low.candidate_hash in plan.deferred_budget_candidate_hashes
    assert {item.candidate_hash for item in insights} == {high.candidate_hash, low.candidate_hash}


def test_high_information_but_expensive_can_lose_to_cheaper_test():
    expensive = candidate("a", estimator_key="expensive")
    cheap = candidate("b", estimator_key="cheap")
    expensive_h = hypothesis("a")
    cheap_h = hypothesis("b")
    hypotheses = {expensive.candidate_hash: expensive_h, cheap.candidate_hash: cheap_h}
    models = {
        expensive.candidate_hash: likelihood(expensive, expensive_h, sensitivity=10_000, false_positive=0),
        cheap.candidate_hash: likelihood(cheap, cheap_h, sensitivity=9000, false_positive=1000),
    }
    estimators = {"expensive": estimator("expensive", 20), "cheap": estimator("cheap", 4)}
    plan, _ = plan_active_verification(
        [expensive, cheap], hypotheses, models, estimators, economy_policy(), active_policy(budget_units=4, max_selected_items=1), measured_at=200
    )
    assert plan.selected_candidate_hashes == (cheap.candidate_hash,)
    assert expensive.candidate_hash in plan.deferred_oversized_candidate_hashes


def test_zero_information_is_deferred_not_marked_invalid():
    item = candidate("a")
    hyp = hypothesis("a")
    model = likelihood(item, hyp, sensitivity=5000, false_positive=5000)
    plan, _ = plan_active_verification(
        [item], {item.candidate_hash: hyp}, {item.candidate_hash: model}, {}, economy_policy(), active_policy(), measured_at=200
    )
    assert plan.selected_candidate_hashes == ()
    assert plan.deferred_low_information_candidate_hashes == (item.candidate_hash,)


def test_every_candidate_is_accounted_for_exactly_once():
    a = candidate("a", estimator_key="a")
    b = candidate("b", estimator_key="b")
    c = candidate("c", estimator_key="c")
    ah, bh, ch = hypothesis("a"), hypothesis("b"), hypothesis("c")
    hypotheses = {a.candidate_hash: ah, b.candidate_hash: bh, c.candidate_hash: ch}
    models = {
        a.candidate_hash: likelihood(a, ah, sensitivity=9500, false_positive=500),
        b.candidate_hash: likelihood(b, bh, sensitivity=9000, false_positive=1000),
        c.candidate_hash: likelihood(c, ch, sensitivity=5000, false_positive=5000),
    }
    estimators = {"a": estimator("a", 5), "b": estimator("b", 20), "c": estimator("c", 5)}
    plan, _ = plan_active_verification(
        [a, b, c], hypotheses, models, estimators, economy_policy(), active_policy(budget_units=5, max_selected_items=1), measured_at=200
    )
    dispositions = (
        set(plan.selected_candidate_hashes)
        | set(plan.deferred_budget_candidate_hashes)
        | set(plan.deferred_oversized_candidate_hashes)
        | set(plan.deferred_low_information_candidate_hashes)
    )
    assert dispositions == {a.candidate_hash, b.candidate_hash, c.candidate_hash}


def test_tampered_information_gain_receipt_is_rejected():
    item = candidate("a")
    hyp = hypothesis("a")
    model = likelihood(item, hyp, sensitivity=9000, false_positive=1000)
    result = expected_information_gain(item, hyp, model, estimated_cost=10, computed_at=100)
    forged = replace(result, expected_information_gain_microbits=result.expected_information_gain_microbits + 1)
    with pytest.raises(ValueError):
        forged.validate()
