from dataclasses import replace

import pytest

from model.verification_economy import (
    allocate_verification_budget,
    build_cost_estimator,
    estimated_cost_units,
    make_economic_candidate,
    make_verification_economy_policy,
    record_cost_observation,
)


def h(ch: str) -> str:
    return ch * 64


def candidate(ch: str, *, estimator_key: str, declared: int, value: int, risk: int, priority: int = 0, submitted_at: int = 100):
    return make_economic_candidate(
        work_hash=h(ch),
        subject_identity_ref=f"agent:{ch}",
        estimator_key=estimator_key,
        declared_cost_units=declared,
        value_units=value,
        risk_units=risk,
        priority=priority,
        submitted_at=submitted_at,
    )


def observation(ch: str, *, estimator_key: str, cost: int, measured_at: int = 200):
    return record_cost_observation(
        work_hash=h(ch),
        completion_hash=h(chr(ord(ch) + 1)),
        estimator_key=estimator_key,
        observed_cost_units=cost,
        measured_at=measured_at,
        meter_ref="meter:runtime",
    )


def policy(**overrides):
    values = dict(
        budget_units=20,
        max_funded_items=10,
        bootstrap_cost_units=10,
        min_samples_for_confidence=2,
        uncertainty_premium_units=2,
        value_weight=1,
        risk_weight=2,
        priority_weight=1,
        aging_quantum=10,
    )
    values.update(overrides)
    return make_verification_economy_policy(**values)


def test_declared_cost_is_not_accounting_cost_without_history():
    cheap_claim = candidate("a", estimator_key="geometry", declared=1, value=5, risk=5)
    expensive_claim = candidate("c", estimator_key="geometry", declared=1000, value=5, risk=5)
    p = policy()
    assert estimated_cost_units(cheap_claim, None, p) == 12
    assert estimated_cost_units(expensive_claim, None, p) == 12


def test_observed_cost_replaces_bootstrap_estimate():
    item = candidate("a", estimator_key="geometry", declared=1, value=5, risk=5)
    estimator = build_cost_estimator(
        "geometry",
        [
            observation("b", estimator_key="geometry", cost=4),
            observation("d", estimator_key="geometry", cost=6),
        ],
    )
    assert estimator.mean_cost_units == 5
    assert estimated_cost_units(item, estimator, policy()) == 5


def test_uncertainty_premium_applies_until_minimum_sample_count():
    item = candidate("a", estimator_key="geometry", declared=1, value=5, risk=5)
    estimator = build_cost_estimator("geometry", [observation("b", estimator_key="geometry", cost=6)])
    assert estimated_cost_units(item, estimator, policy()) == 8


def test_observed_cost_can_change_budget_allocation_order():
    geometry = candidate("a", estimator_key="geometry", declared=1, value=12, risk=3)
    policy_check = candidate("c", estimator_key="policy", declared=999, value=8, risk=2)
    estimators = {
        "geometry": build_cost_estimator(
            "geometry",
            [observation("e", estimator_key="geometry", cost=18), observation("b", estimator_key="geometry", cost=18)],
        ),
        "policy": build_cost_estimator(
            "policy",
            [observation("c", estimator_key="policy", cost=3), observation("d", estimator_key="policy", cost=3)],
        ),
    }
    allocation = allocate_verification_budget([geometry, policy_check], estimators, policy(budget_units=10), measured_at=200)
    assert allocation.funded_candidate_hashes == (policy_check.candidate_hash,)
    assert geometry.candidate_hash in allocation.deferred_oversized_candidate_hashes


def test_every_candidate_is_accounted_for_exactly_once():
    a = candidate("a", estimator_key="a", declared=1, value=10, risk=1)
    b = candidate("c", estimator_key="b", declared=1, value=8, risk=1)
    c = candidate("e", estimator_key="c", declared=1, value=1, risk=1)
    allocation = allocate_verification_budget([a, b, c], {}, policy(budget_units=12, max_funded_items=1), measured_at=200)
    dispositions = (
        set(allocation.funded_candidate_hashes)
        | set(allocation.deferred_budget_candidate_hashes)
        | set(allocation.deferred_oversized_candidate_hashes)
    )
    assert dispositions == {a.candidate_hash, b.candidate_hash, c.candidate_hash}
    assert len(allocation.funded_candidate_hashes) == 1


def test_aging_can_raise_old_work_above_new_work():
    old = candidate("a", estimator_key="same", declared=1, value=1, risk=0, submitted_at=0)
    fresh = candidate("c", estimator_key="same", declared=1, value=5, risk=0, submitted_at=190)
    allocation = allocate_verification_budget([fresh, old], {}, policy(budget_units=12, max_funded_items=1, aging_quantum=10), measured_at=200)
    assert allocation.funded_candidate_hashes == (old.candidate_hash,)


def test_duplicate_cost_observation_for_same_work_is_rejected():
    first = observation("a", estimator_key="geometry", cost=4)
    second = record_cost_observation(
        work_hash=first.work_hash,
        completion_hash=h("f"),
        estimator_key="geometry",
        observed_cost_units=8,
        measured_at=201,
        meter_ref="meter:other",
    )
    with pytest.raises(ValueError, match="multiple cost observations"):
        build_cost_estimator("geometry", [first, second])


def test_tampered_observation_is_rejected_even_if_cost_is_plausible():
    receipt = observation("a", estimator_key="geometry", cost=4)
    tampered = replace(receipt, observed_cost_units=5)
    with pytest.raises(ValueError, match="observation_hash"):
        tampered.validate()


def test_allocation_receipt_detects_silent_reclassification():
    a = candidate("a", estimator_key="a", declared=1, value=10, risk=1)
    b = candidate("c", estimator_key="b", declared=1, value=1, risk=1)
    allocation = allocate_verification_budget([a, b], {}, policy(budget_units=12, max_funded_items=1), measured_at=200)
    forged = replace(
        allocation,
        funded_candidate_hashes=(a.candidate_hash, b.candidate_hash),
        deferred_budget_candidate_hashes=(),
    )
    with pytest.raises(ValueError):
        forged.validate()
