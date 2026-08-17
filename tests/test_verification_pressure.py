from __future__ import annotations

import pytest

from model.verification_pressure import (
    evaluate_verification_coverage,
    make_verification_capacity_policy,
    make_verification_work,
    schedule_verification,
    verify_verification_pressure,
)


def work(
    ref: str,
    *,
    cost: int = 1,
    priority: int = 0,
    submitted_at: int = 0,
    subject: str = "agent:pressure",
):
    return make_verification_work(
        ref,
        subject_identity_ref=subject,
        evidence={"ref": ref, "claim": f"check:{ref}"},
        cost_units=cost,
        priority=priority,
        submitted_at=submitted_at,
    )


def policy(*, capacity=4, max_items=4, aging=10):
    return make_verification_capacity_policy(
        capacity_units=capacity,
        max_admitted_items=max_items,
        aging_quantum=aging,
    )


def test_all_work_is_admitted_when_capacity_covers_demand():
    items = (work("a"), work("b"), work("c"))
    receipt = schedule_verification(items, policy(capacity=3, max_items=3), measured_at=10)

    assert receipt.pressure_status == "NORMAL"
    assert set(receipt.admitted_work_hashes) == {item.work_hash for item in items}
    assert receipt.deferred_work_hashes == ()
    assert receipt.used_units == 3


def test_capacity_pressure_defers_without_marking_work_invalid():
    items = (work("a", cost=2), work("b", cost=2), work("c", cost=2))
    receipt = schedule_verification(items, policy(capacity=4, max_items=3), measured_at=10)

    assert receipt.pressure_status == "PRESSURED"
    assert len(receipt.admitted_work_hashes) == 2
    assert len(receipt.deferred_capacity_work_hashes) == 1
    assert receipt.deferred_oversized_work_hashes == ()


def test_pressure_receipt_accounts_for_every_offered_item_exactly_once():
    items = (
        work("normal", cost=1),
        work("capacity", cost=2),
        work("oversized", cost=10),
    )
    receipt = schedule_verification(items, policy(capacity=2, max_items=2), measured_at=10)

    accounted = (
        set(receipt.admitted_work_hashes)
        | set(receipt.deferred_capacity_work_hashes)
        | set(receipt.deferred_oversized_work_hashes)
    )
    assert accounted == {item.work_hash for item in items}
    assert len(receipt.admitted_work_hashes) + len(receipt.deferred_work_hashes) == len(items)


def test_oversized_work_remains_explicit_instead_of_disappearing():
    giant = work("giant", cost=5)
    receipt = schedule_verification((giant,), policy(capacity=3, max_items=1), measured_at=10)

    assert receipt.pressure_status == "SATURATED"
    assert receipt.admitted_work_hashes == ()
    assert receipt.deferred_oversized_work_hashes == (giant.work_hash,)


def test_scheduling_is_deterministic_independent_of_input_iteration_order():
    items = (
        work("a", priority=1, submitted_at=5),
        work("b", priority=3, submitted_at=5),
        work("c", priority=2, submitted_at=5),
    )
    p = policy(capacity=2, max_items=2)

    left = schedule_verification(items, p, measured_at=10)
    right = schedule_verification(tuple(reversed(items)), p, measured_at=10)

    assert left.ranked_work_hashes == right.ranked_work_hashes
    assert left.admitted_work_hashes == right.admitted_work_hashes
    assert left.pressure_hash == right.pressure_hash


def test_aging_can_promote_old_work_above_fresh_higher_base_priority():
    old = work("old", priority=0, submitted_at=0)
    fresh = work("fresh", priority=5, submitted_at=100)
    p = policy(capacity=1, max_items=1, aging=10)

    receipt = schedule_verification((fresh, old), p, measured_at=100)

    assert receipt.ranked_work_hashes[0] == old.work_hash
    assert receipt.admitted_work_hashes == (old.work_hash,)
    assert fresh.work_hash in receipt.deferred_capacity_work_hashes


def test_pressure_verifier_rejects_receipt_for_another_offered_set():
    a = work("a")
    b = work("b")
    c = work("c")
    p = policy(capacity=2, max_items=2)
    receipt = schedule_verification((a, b), p, measured_at=10)

    valid, limitations = verify_verification_pressure(receipt, (a, c), p)

    assert valid is False
    assert "offered_work_mismatch" in limitations


def test_duplicate_work_ref_is_rejected_instead_of_double_counted():
    one = work("same")
    two = make_verification_work(
        "same",
        subject_identity_ref="agent:pressure",
        evidence={"different": True},
        cost_units=1,
        submitted_at=1,
    )

    with pytest.raises(ValueError, match="duplicate work_ref"):
        schedule_verification((one, two), policy(), measured_at=10)


def test_coverage_holds_while_admitted_verification_is_still_pending():
    items = (work("a"), work("b"))
    p = policy(capacity=2, max_items=2)
    pressure = schedule_verification(items, p, measured_at=10)

    coverage = evaluate_verification_coverage(
        "PASS",
        pressure,
        items,
        p,
        completed_work_hashes=(items[0].work_hash,),
    )

    assert coverage.decision == "HOLD"
    assert "verification_pending" in coverage.reasons
    assert coverage.pending_admitted_work_hashes == (items[1].work_hash,)


def test_coverage_holds_when_capacity_forced_required_work_to_defer():
    items = (work("a"), work("b"))
    p = policy(capacity=1, max_items=1)
    pressure = schedule_verification(items, p, measured_at=10)

    coverage = evaluate_verification_coverage(
        "PASS",
        pressure,
        items,
        p,
        completed_work_hashes=pressure.admitted_work_hashes,
    )

    assert coverage.decision == "HOLD"
    assert "verification_deferred_capacity" in coverage.reasons
    assert coverage.deferred_work_hashes


def test_coverage_passes_only_when_every_required_item_was_admitted_and_completed():
    items = (work("a"), work("b"))
    p = policy(capacity=2, max_items=2)
    pressure = schedule_verification(items, p, measured_at=10)

    coverage = evaluate_verification_coverage(
        "PASS",
        pressure,
        items,
        p,
        completed_work_hashes=pressure.admitted_work_hashes,
    )

    assert coverage.decision == "PASS"
    assert coverage.pending_admitted_work_hashes == ()
    assert coverage.deferred_work_hashes == ()


def test_claiming_completion_for_deferred_work_is_a_fail_not_a_pass():
    items = (work("a"), work("b"))
    p = policy(capacity=1, max_items=1)
    pressure = schedule_verification(items, p, measured_at=10)
    deferred = pressure.deferred_work_hashes[0]

    coverage = evaluate_verification_coverage(
        "PASS",
        pressure,
        items,
        p,
        completed_work_hashes=(*pressure.admitted_work_hashes, deferred),
    )

    assert coverage.decision == "FAIL"
    assert "completion_not_admitted" in coverage.reasons


def test_base_failure_cannot_be_overridden_by_complete_verification_coverage():
    items = (work("a"),)
    p = policy(capacity=1, max_items=1)
    pressure = schedule_verification(items, p, measured_at=10)

    coverage = evaluate_verification_coverage(
        "FAIL",
        pressure,
        items,
        p,
        completed_work_hashes=pressure.admitted_work_hashes,
    )

    assert coverage.decision == "FAIL"
    assert "base_decision_failed" in coverage.reasons
