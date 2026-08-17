from hashlib import sha256

import pytest

from model.calibration import DependencyPairSample, _digest as calibration_digest
from model.dependency_graph_revision import make_dependency_graph
from model.protected_confirmation import (
    apply_confirmed_selection,
    assert_confirmation_freshness,
    authorize_confirmation_exposure,
    evaluate_confirmation,
    make_confirmation_batch,
    make_confirmation_policy,
    review_confirmation,
)
from model.search_budget import (
    evaluate_reserved_candidate,
    make_search_budget_policy,
    reserve_heldout_search,
    review_search_budget_selection,
    select_search_budget_candidate,
)
from model.structural_validation import make_structural_validation_candidate, make_structural_validation_policy, partition_dependency_samples

IDENTITY = "agent:v1.17"
PAIR_KEY = sha256(b"pair:v1.17").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def sample(index: int, *, left: bool, right: bool, prefix: str = "search", resolution_hash: str | None = None, left_evidence_hash: str | None = None) -> DependencyPairSample:
    fields = {
        "pair_key": PAIR_KEY,
        "resolution_hash": resolution_hash or h(f"{prefix}:resolution:{index}"),
        "dependency_group_ref": f"group:{prefix}",
        "left_model_ref": "signal:L",
        "right_model_ref": "signal:R",
        "declared_mode": "INDEPENDENT",
        "resolved_hypothesis_ref": "H:A",
        "left_evidence_hash": left_evidence_hash or h(f"{prefix}:left:{index}"),
        "right_evidence_hash": h(f"{prefix}:right:{index}"),
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
        policy_ref="policy:structure:v1.17",
        subject_identity_ref=IDENTITY,
        evaluation_modulus=3,
        min_selection_samples=6,
        min_evaluation_samples=2,
        dependency_threshold_bps=1000,
        edge_penalty_ppm=1_000,
        registered_at=10,
    )


def graph():
    return make_dependency_graph(
        "graph:v1.17",
        subject_identity_ref=IDENTITY,
        generation=0,
        edges=(),
        evidence_state_hash=h("graph:v1.17:0"),
    )


def collect_partitioned(*, desired: str, count: int, start: int, policy):
    rows = []
    index = start
    while len(rows) < count and index < start + 10000:
        outcome = (True, True) if len(rows) % 2 == 0 else (False, False)
        item = sample(index, left=outcome[0], right=outcome[1])
        selection, evaluation, _ = partition_dependency_samples((item,), policy)
        if (desired == "selection" and selection) or (desired == "evaluation" and evaluation):
            rows.append(item)
        index += 1
    assert len(rows) == count
    return rows, index


def search_history():
    policy = structural_policy()
    selection, cursor = collect_partitioned(desired="selection", count=8, start=0, policy=policy)
    evaluation, _ = collect_partitioned(desired="evaluation", count=4, start=cursor + 100, policy=policy)
    return tuple(selection + evaluation)


def confirmation_samples(*, correlated: bool = True, count: int = 6, start: int = 5000):
    rows = []
    for i in range(count):
        left = i % 2 == 0
        right = left if correlated else (not left)
        rows.append(sample(start + i, left=left, right=right, prefix="confirm"))
    return tuple(rows)


def build_search_chain():
    sp = structural_policy()
    g = graph()
    history = search_history()
    candidate = make_structural_validation_candidate(
        candidate_ref="candidate:v1.17",
        base_graph=g,
        samples=history,
        policy=sp,
        direction="LEFT_TO_RIGHT",
        reason_ref="search",
        proposer_ref="proposer",
        created_at=200,
    )
    search_policy = make_search_budget_policy(
        policy_ref="policy:search:v1.17",
        subject_identity_ref=IDENTITY,
        max_unique_evaluations=4,
        base_min_regularized_improvement_ppm=0,
        multiplicity_penalty_ppm=0,
        registered_at=210,
    )
    reservation = reserve_heldout_search(
        candidate=candidate,
        policy=search_policy,
        prior_reservations=(),
        budget_keeper_ref="budget",
        reserved_at=220,
    )
    _, underlying, evaluation = evaluate_reserved_candidate(
        candidate=candidate,
        reservation=reservation,
        base_graph=g,
        samples=history,
        structural_policy=sp,
        search_policy=search_policy,
        evaluator_ref="search-evaluator",
        evaluated_at=230,
    )
    assert evaluation.status == "SEARCH_CORRECTED_IMPROVED"
    selection = select_search_budget_candidate(
        selection_ref="selection:v1.17",
        current_candidates=(candidate,),
        current_evaluations=(evaluation,),
        all_family_reservations=(reservation,),
        search_policy=search_policy,
        selector_ref="selector",
        selected_at=240,
    )
    review = review_search_budget_selection(
        selection=selection,
        selected_candidate=candidate,
        decision="APPROVE",
        rationale_ref="search-review",
        reviewer_ref="search-reviewer",
        reviewed_at=250,
    )
    return sp, g, history, candidate, reservation, underlying, evaluation, selection, review


def confirmation_policy():
    return make_confirmation_policy(
        policy_ref="policy:confirm:v1.17",
        subject_identity_ref=IDENTITY,
        min_confirmation_samples=4,
        min_regularized_improvement_ppm=0,
        registered_at=260,
    )


def test_repartitioned_old_data_is_not_fresh_confirmation():
    _, _, history, *_ = build_search_chain()
    batch = make_confirmation_batch(
        batch_ref="batch:old",
        subject_identity_ref=IDENTITY,
        pair_key=PAIR_KEY,
        source_ref="source:old",
        samples=(history[0],),
        batch_keeper_ref="batch-keeper",
        sealed_at=270,
    )
    with pytest.raises(ValueError, match="search sample hash"):
        assert_confirmation_freshness(batch=batch, search_samples=history, prior_batches=())


def test_new_sample_hash_with_old_resolution_is_not_fresh():
    _, _, history, *_ = build_search_chain()
    alias = sample(9000, left=True, right=True, prefix="alias", resolution_hash=history[0].resolution_hash)
    assert alias.sample_hash != history[0].sample_hash
    batch = make_confirmation_batch(batch_ref="batch:alias", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="source:alias", samples=(alias,), batch_keeper_ref="batch-keeper", sealed_at=270)
    with pytest.raises(ValueError, match="resolution provenance"):
        assert_confirmation_freshness(batch=batch, search_samples=history, prior_batches=())


def test_new_derivation_with_old_evidence_is_not_fresh():
    _, _, history, *_ = build_search_chain()
    alias = sample(9001, left=True, right=True, prefix="alias-evidence", left_evidence_hash=history[0].left_evidence_hash)
    batch = make_confirmation_batch(batch_ref="batch:evidence-alias", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="source:alias", samples=(alias,), batch_keeper_ref="batch-keeper", sealed_at=270)
    with pytest.raises(ValueError, match="evidence provenance"):
        assert_confirmation_freshness(batch=batch, search_samples=history, prior_batches=())


def test_confirmation_rotation_requires_new_provenance_not_new_batch_name():
    _, _, history, *_ = build_search_chain()
    rows = confirmation_samples(count=4)
    first = make_confirmation_batch(batch_ref="batch:first", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="source:first", samples=rows, batch_keeper_ref="batch-keeper", sealed_at=270)
    renamed = make_confirmation_batch(batch_ref="batch:renamed", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="source:renamed", samples=rows, batch_keeper_ref="batch-keeper-2", sealed_at=280)
    assert_confirmation_freshness(batch=first, search_samples=history, prior_batches=())
    with pytest.raises(ValueError, match="genuinely fresh provenance"):
        assert_confirmation_freshness(batch=renamed, search_samples=history, prior_batches=(first,))


def test_one_selection_gets_only_one_confirmation_exposure():
    _, _, history, candidate, _, _, _, selection, search_review = build_search_chain()
    cp = confirmation_policy()
    rows = confirmation_samples()
    batch1 = make_confirmation_batch(batch_ref="batch:1", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="source:1", samples=rows, batch_keeper_ref="batch-keeper", sealed_at=270)
    assert_confirmation_freshness(batch=batch1, search_samples=history, prior_batches=())
    exposure = authorize_confirmation_exposure(selection=selection, search_review=search_review, candidate=candidate, batch=batch1, policy=cp, prior_exposures=(), exposure_keeper_ref="exposure-keeper", authorized_at=280)
    rows2 = confirmation_samples(start=6000)
    batch2 = make_confirmation_batch(batch_ref="batch:2", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="source:2", samples=rows2, batch_keeper_ref="batch-keeper-2", sealed_at=290)
    with pytest.raises(ValueError, match="already consumed"):
        authorize_confirmation_exposure(selection=selection, search_review=search_review, candidate=candidate, batch=batch2, policy=cp, prior_exposures=(exposure,), exposure_keeper_ref="exposure-keeper-2", authorized_at=300)


def test_fresh_confirmation_can_confirm_selected_structure():
    sp, g, history, candidate, _, _, _, selection, search_review = build_search_chain()
    cp = confirmation_policy()
    rows = confirmation_samples(correlated=True)
    batch = make_confirmation_batch(batch_ref="batch:confirm", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="external:confirm", samples=rows, batch_keeper_ref="batch-keeper", sealed_at=270)
    assert_confirmation_freshness(batch=batch, search_samples=history, prior_batches=())
    exposure = authorize_confirmation_exposure(selection=selection, search_review=search_review, candidate=candidate, batch=batch, policy=cp, prior_exposures=(), exposure_keeper_ref="exposure-keeper", authorized_at=280)
    cases, evaluation = evaluate_confirmation(selection=selection, candidate=candidate, batch=batch, exposure=exposure, confirmation_samples=rows, search_samples=history, current_graph=g, structural_policy=sp, confirmation_policy=cp, evaluator_ref="confirmation-evaluator", evaluated_at=290)
    assert len(cases) == len(rows)
    assert evaluation.status == "CONFIRMED"
    assert evaluation.regularized_improvement_ppm > 0


def test_fresh_confirmation_can_reject_search_winner_without_retrying_truth():
    sp, g, history, candidate, _, _, _, selection, search_review = build_search_chain()
    cp = confirmation_policy()
    rows = confirmation_samples(correlated=False)
    batch = make_confirmation_batch(batch_ref="batch:reject", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="external:reject", samples=rows, batch_keeper_ref="batch-keeper", sealed_at=270)
    exposure = authorize_confirmation_exposure(selection=selection, search_review=search_review, candidate=candidate, batch=batch, policy=cp, prior_exposures=(), exposure_keeper_ref="exposure-keeper", authorized_at=280)
    _, evaluation = evaluate_confirmation(selection=selection, candidate=candidate, batch=batch, exposure=exposure, confirmation_samples=rows, search_samples=history, current_graph=g, structural_policy=sp, confirmation_policy=cp, evaluator_ref="confirmation-evaluator", evaluated_at=290)
    assert evaluation.status == "CONFIRMATION_REJECTED"
    with pytest.raises(ValueError, match="requires CONFIRMED"):
        review_confirmation(evaluation=evaluation, decision="APPROVE", rationale_ref="nope", reviewer_ref="confirmation-reviewer", reviewed_at=300)


def test_confirmed_apply_advances_graph_only_after_independent_review():
    sp, g, history, candidate, reservation, underlying, search_evaluation, selection, search_review = build_search_chain()
    cp = confirmation_policy()
    rows = confirmation_samples(correlated=True)
    batch = make_confirmation_batch(batch_ref="batch:apply", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="external:apply", samples=rows, batch_keeper_ref="batch-keeper", sealed_at=270)
    exposure = authorize_confirmation_exposure(selection=selection, search_review=search_review, candidate=candidate, batch=batch, policy=cp, prior_exposures=(), exposure_keeper_ref="exposure-keeper", authorized_at=280)
    _, evaluation = evaluate_confirmation(selection=selection, candidate=candidate, batch=batch, exposure=exposure, confirmation_samples=rows, search_samples=history, current_graph=g, structural_policy=sp, confirmation_policy=cp, evaluator_ref="confirmation-evaluator", evaluated_at=290)
    review = review_confirmation(evaluation=evaluation, decision="APPROVE", rationale_ref="independent-confirmation", reviewer_ref="confirmation-reviewer", reviewed_at=300)
    new_graph, receipt = apply_confirmed_selection(current_graph=g, candidate=candidate, reservation=reservation, underlying_validation=underlying, search_evaluation=search_evaluation, search_selection=selection, search_review=search_review, exposure=exposure, confirmation_evaluation=evaluation, confirmation_review=review, applier_ref="confirmed-applier", applied_at=310)
    assert new_graph.generation == g.generation + 1
    assert len(new_graph.edges) == 1
    assert receipt.base_graph_hash == g.graph_hash
    assert receipt.new_graph_hash == new_graph.graph_hash
