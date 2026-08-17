from hashlib import sha256

import pytest

from model.calibration import DependencyPairSample, _digest as calibration_digest
from model.dependency_graph_revision import make_dependency_graph
from model.search_budget import (
    apply_search_budgeted_selection,
    evaluate_reserved_candidate,
    make_search_budget_policy,
    reserve_heldout_search,
    review_search_budget_selection,
    search_family_hash,
    select_search_budget_candidate,
)
from model.structural_validation import (
    make_structural_validation_candidate,
    make_structural_validation_policy,
    partition_dependency_samples,
)


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def sample(index: int, *, left: bool, right: bool, pair_key: str) -> DependencyPairSample:
    fields = {
        "pair_key": pair_key,
        "resolution_hash": h(f"v1.16:resolution:{index}:{left}:{right}"),
        "dependency_group_ref": "group:v1.16",
        "left_model_ref": "signal:L",
        "right_model_ref": "signal:R",
        "declared_mode": "INDEPENDENT",
        "resolved_hypothesis_ref": "H:A",
        "left_evidence_hash": h(f"v1.16:left:{index}:{left}:{right}"),
        "right_evidence_hash": h(f"v1.16:right:{index}:{left}:{right}"),
        "left_positive": left,
        "right_positive": right,
        "sampled_at": 100 + index,
    }
    provisional = DependencyPairSample(**fields, sample_hash="0" * 64)
    result = DependencyPairSample(**fields, sample_hash=calibration_digest(provisional.material()))
    result.validate()
    return result


def structural_policy():
    return make_structural_validation_policy(
        policy_ref="policy:structure:v1.16",
        subject_identity_ref="agent:v1.16",
        evaluation_modulus=3,
        min_selection_samples=6,
        min_evaluation_samples=2,
        dependency_threshold_bps=1000,
        edge_penalty_ppm=1_000,
        registered_at=10,
    )


def search_policy(*, max_unique=4, penalty=10_000, base=0):
    return make_search_budget_policy(
        policy_ref="policy:search:v1.16",
        subject_identity_ref="agent:v1.16",
        max_unique_evaluations=max_unique,
        base_min_regularized_improvement_ppm=base,
        multiplicity_penalty_ppm=penalty,
        registered_at=20,
    )


def graph():
    return make_dependency_graph(
        "graph:v1.16",
        subject_identity_ref="agent:v1.16",
        generation=0,
        edges=(),
        evidence_state_hash=h("graph:v1.16:evidence"),
    )


def collect_partitioned(*, desired: str, count: int, start: int, pair_key: str, p):
    result = []
    index = start
    while len(result) < count and index < start + 10000:
        left, right = ((True, True), (False, False))[len(result) % 2]
        item = sample(index, left=left, right=right, pair_key=pair_key)
        selection, evaluation, _ = partition_dependency_samples((item,), p)
        if (desired == "selection" and selection) or (desired == "evaluation" and evaluation):
            result.append(item)
        index += 1
    assert len(result) == count
    return result, index


def history(p=None):
    p = p or structural_policy()
    pair_key = h("pair:v1.16")
    selection, next_index = collect_partitioned(desired="selection", count=8, start=0, pair_key=pair_key, p=p)
    evaluation, _ = collect_partitioned(desired="evaluation", count=4, start=next_index + 100, pair_key=pair_key, p=p)
    return tuple(selection + evaluation)


def candidate(samples, *, direction="LEFT_TO_RIGHT", ref=None, proposer="proposer"):
    return make_structural_validation_candidate(
        candidate_ref=ref or f"candidate:{direction}",
        base_graph=graph(),
        samples=samples,
        policy=structural_policy(),
        direction=direction,
        reason_ref="search-budget",
        proposer_ref=proposer,
        created_at=200,
    )


def test_repeated_same_candidate_reuses_reservation_without_spending_budget():
    samples = history()
    c = candidate(samples)
    policy = search_policy(max_unique=2)
    first = reserve_heldout_search(candidate=c, policy=policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    second = reserve_heldout_search(candidate=c, policy=policy, prior_reservations=(first,), budget_keeper_ref="budget", reserved_at=999)
    assert second == first
    assert second.ordinal == 1


def test_unique_heldout_looks_consume_budget_and_raise_threshold():
    samples = history()
    policy = search_policy(max_unique=3, penalty=25_000, base=5_000)
    c1 = candidate(samples, direction="LEFT_TO_RIGHT", ref="candidate:1", proposer="p1")
    c2 = candidate(samples, direction="RIGHT_TO_LEFT", ref="candidate:2", proposer="p2")
    r1 = reserve_heldout_search(candidate=c1, policy=policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    r2 = reserve_heldout_search(candidate=c2, policy=policy, prior_reservations=(r1,), budget_keeper_ref="budget", reserved_at=211)
    assert r1.ordinal == 1 and r1.effective_min_regularized_improvement_ppm == 5_000
    assert r2.ordinal == 2 and r2.effective_min_regularized_improvement_ppm == 30_000


def test_search_budget_does_not_reset_when_history_changes():
    p = structural_policy()
    samples = history(p)
    policy = search_policy(max_unique=3)
    c1 = candidate(samples, ref="candidate:old", proposer="p1")
    r1 = reserve_heldout_search(candidate=c1, policy=policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    extra, _ = collect_partitioned(desired="selection", count=1, start=5000, pair_key=samples[0].pair_key, p=p)
    newer = tuple(samples + tuple(extra))
    c2 = candidate(newer, ref="candidate:new", proposer="p2")
    assert c1.history_hash != c2.history_hash
    assert search_family_hash(c1, policy) == search_family_hash(c2, policy)
    r2 = reserve_heldout_search(candidate=c2, policy=policy, prior_reservations=(r1,), budget_keeper_ref="budget", reserved_at=220)
    assert r2.ordinal == 2


def test_budget_exhaustion_blocks_another_unique_heldout_exposure():
    samples = history()
    policy = search_policy(max_unique=1)
    c1 = candidate(samples, direction="LEFT_TO_RIGHT", ref="candidate:1", proposer="p1")
    c2 = candidate(samples, direction="RIGHT_TO_LEFT", ref="candidate:2", proposer="p2")
    r1 = reserve_heldout_search(candidate=c1, policy=policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    with pytest.raises(ValueError, match="budget exhausted"):
        reserve_heldout_search(candidate=c2, policy=policy, prior_reservations=(r1,), budget_keeper_ref="budget", reserved_at=211)


def test_multiplicity_penalty_can_reject_a_candidate_that_passes_plain_heldout():
    samples = history()
    policy = search_policy(max_unique=3, penalty=1_000_000)
    c1 = candidate(samples, direction="LEFT_TO_RIGHT", ref="candidate:1", proposer="p1")
    c2 = candidate(samples, direction="RIGHT_TO_LEFT", ref="candidate:2", proposer="p2")
    r1 = reserve_heldout_search(candidate=c1, policy=policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    r2 = reserve_heldout_search(candidate=c2, policy=policy, prior_reservations=(r1,), budget_keeper_ref="budget", reserved_at=211)
    _, u1, e1 = evaluate_reserved_candidate(candidate=c1, reservation=r1, base_graph=graph(), samples=samples, structural_policy=structural_policy(), search_policy=policy, evaluator_ref="eval1", evaluated_at=220)
    _, u2, e2 = evaluate_reserved_candidate(candidate=c2, reservation=r2, base_graph=graph(), samples=samples, structural_policy=structural_policy(), search_policy=policy, evaluator_ref="eval2", evaluated_at=221)
    assert u1.status == "HELDOUT_IMPROVED" and u2.status == "HELDOUT_IMPROVED"
    assert e1.status == "SEARCH_CORRECTED_IMPROVED"
    assert e2.status == "MULTIPLICITY_REJECTED"


def test_search_evaluator_is_independent_from_proposer_and_budget_keeper():
    samples = history()
    c = candidate(samples, proposer="proposer")
    policy = search_policy()
    reservation = reserve_heldout_search(candidate=c, policy=policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    for actor in ("proposer", "budget"):
        with pytest.raises(ValueError, match="independent"):
            evaluate_reserved_candidate(candidate=c, reservation=reservation, base_graph=graph(), samples=samples, structural_policy=structural_policy(), search_policy=policy, evaluator_ref=actor, evaluated_at=220)


def test_search_selection_uses_search_adjusted_margin_and_complete_current_set():
    samples = history()
    policy = search_policy(max_unique=3, penalty=1_000_000)
    c1 = candidate(samples, direction="LEFT_TO_RIGHT", ref="candidate:1", proposer="p1")
    c2 = candidate(samples, direction="RIGHT_TO_LEFT", ref="candidate:2", proposer="p2")
    r1 = reserve_heldout_search(candidate=c1, policy=policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    r2 = reserve_heldout_search(candidate=c2, policy=policy, prior_reservations=(r1,), budget_keeper_ref="budget", reserved_at=211)
    _, _, e1 = evaluate_reserved_candidate(candidate=c1, reservation=r1, base_graph=graph(), samples=samples, structural_policy=structural_policy(), search_policy=policy, evaluator_ref="eval1", evaluated_at=220)
    _, _, e2 = evaluate_reserved_candidate(candidate=c2, reservation=r2, base_graph=graph(), samples=samples, structural_policy=structural_policy(), search_policy=policy, evaluator_ref="eval2", evaluated_at=221)
    selection = select_search_budget_candidate(selection_ref="selection:1", current_candidates=(c1, c2), current_evaluations=(e1, e2), all_family_reservations=(r1, r2), search_policy=policy, selector_ref="selector", selected_at=230)
    assert selection.status == "SELECTED"
    assert selection.selected_candidate_hash == c1.candidate_hash
    assert selection.budget_used == 2 and selection.budget_remaining == 1


def test_search_review_requires_independence():
    samples = history()
    c = candidate(samples, proposer="proposer")
    policy = search_policy()
    r = reserve_heldout_search(candidate=c, policy=policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    _, _, e = evaluate_reserved_candidate(candidate=c, reservation=r, base_graph=graph(), samples=samples, structural_policy=structural_policy(), search_policy=policy, evaluator_ref="eval", evaluated_at=220)
    selection = select_search_budget_candidate(selection_ref="selection:review", current_candidates=(c,), current_evaluations=(e,), all_family_reservations=(r,), search_policy=policy, selector_ref="selector", selected_at=230)
    with pytest.raises(ValueError, match="independent"):
        review_search_budget_selection(selection=selection, selected_candidate=c, decision="APPROVE", rationale_ref="review", reviewer_ref="selector", reviewed_at=240)
    with pytest.raises(ValueError, match="independent"):
        review_search_budget_selection(selection=selection, selected_candidate=c, decision="APPROVE", rationale_ref="review", reviewer_ref="proposer", reviewed_at=240)


def test_search_budgeted_apply_preserves_full_underlying_validation_chain():
    samples = history()
    c = candidate(samples, proposer="proposer")
    policy = search_policy()
    r = reserve_heldout_search(candidate=c, policy=policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    _, underlying, evaluation = evaluate_reserved_candidate(candidate=c, reservation=r, base_graph=graph(), samples=samples, structural_policy=structural_policy(), search_policy=policy, evaluator_ref="eval", evaluated_at=220)
    selection = select_search_budget_candidate(selection_ref="selection:apply", current_candidates=(c,), current_evaluations=(evaluation,), all_family_reservations=(r,), search_policy=policy, selector_ref="selector", selected_at=230)
    review = review_search_budget_selection(selection=selection, selected_candidate=c, decision="APPROVE", rationale_ref="review", reviewer_ref="reviewer", reviewed_at=240)
    new_graph, receipt = apply_search_budgeted_selection(current_graph=graph(), candidate=c, reservation=r, underlying_validation=underlying, evaluation=evaluation, selection=selection, review=review, applier_ref="applier", applied_at=250)
    assert new_graph.generation == 1
    assert receipt.base_graph_hash == graph().graph_hash
    assert receipt.candidate_hash == c.candidate_hash
    assert receipt.underlying_validation_hash == underlying.validation_hash
