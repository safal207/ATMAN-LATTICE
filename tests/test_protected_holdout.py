from dataclasses import replace
from hashlib import sha256

import pytest

from model.calibration import DependencyPairSample, _digest as calibration_digest
from model.dependency_graph_revision import make_dependency_graph
from model.protected_holdout import (
    apply_final_confirmed_selection,
    confirm_on_protected_holdout,
    make_protected_final_holdout_policy,
    make_protected_final_holdout_seal,
)
from model.search_budget import (
    evaluate_reserved_candidate,
    make_search_budget_policy,
    reserve_heldout_search,
    review_search_budget_selection,
    select_search_budget_candidate,
)
from model.structural_validation import (
    make_structural_validation_candidate,
    make_structural_validation_policy,
    partition_dependency_samples,
)

IDENTITY = "agent:v1.17"
PAIR_KEY = sha256(b"pair:v1.17").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def sample(index: int, *, left: bool, right: bool) -> DependencyPairSample:
    fields = {
        "pair_key": PAIR_KEY,
        "resolution_hash": h(f"resolution:{index}:{left}:{right}"),
        "dependency_group_ref": "group:v1.17",
        "left_model_ref": "signal:L",
        "right_model_ref": "signal:R",
        "declared_mode": "INDEPENDENT",
        "resolved_hypothesis_ref": "H:A",
        "left_evidence_hash": h(f"left:{index}:{left}:{right}"),
        "right_evidence_hash": h(f"right:{index}:{left}:{right}"),
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
        registered_at=50,
    )


def graph():
    return make_dependency_graph(
        "graph:v1.17",
        subject_identity_ref=IDENTITY,
        generation=0,
        edges=(),
        evidence_state_hash=h("graph:v1.17:evidence"),
    )


def collect_partitioned(*, desired: str, count: int, start: int, p):
    result = []
    index = start
    while len(result) < count and index < start + 5000:
        left, right = (True, True) if len(result) % 2 == 0 else (False, False)
        item = sample(index, left=left, right=right)
        selection, evaluation, _ = partition_dependency_samples((item,), p)
        if (desired == "selection" and selection) or (desired == "evaluation" and evaluation):
            result.append(item)
        index += 1
    assert len(result) == count
    return result, index


def exposed_history():
    p = structural_policy()
    selection, next_index = collect_partitioned(desired="selection", count=8, start=0, p=p)
    evaluation, _ = collect_partitioned(desired="evaluation", count=4, start=next_index + 100, p=p)
    return tuple(selection + evaluation)


def final_samples(*, correlated=True, start=10000):
    outcomes = [(True, True), (False, False)] if correlated else [(True, False), (False, True)]
    return tuple(sample(start + i, left=outcomes[i % 2][0], right=outcomes[i % 2][1]) for i in range(4))


def search_chain():
    exposed = exposed_history()
    sp = structural_policy()
    candidate = make_structural_validation_candidate(
        candidate_ref="candidate:v1.17",
        base_graph=graph(),
        samples=exposed,
        policy=sp,
        direction="LEFT_TO_RIGHT",
        reason_ref="protected-final-confirmation",
        proposer_ref="proposer",
        created_at=200,
    )
    search_policy = make_search_budget_policy(
        policy_ref="policy:search:v1.17",
        subject_identity_ref=IDENTITY,
        max_unique_evaluations=4,
        base_min_regularized_improvement_ppm=0,
        multiplicity_penalty_ppm=0,
        registered_at=60,
    )
    reservation = reserve_heldout_search(
        candidate=candidate,
        policy=search_policy,
        prior_reservations=(),
        budget_keeper_ref="budget",
        reserved_at=205,
    )
    _, underlying, evaluation = evaluate_reserved_candidate(
        candidate=candidate,
        reservation=reservation,
        base_graph=graph(),
        samples=exposed,
        structural_policy=sp,
        search_policy=search_policy,
        evaluator_ref="search-evaluator",
        evaluated_at=210,
    )
    assert evaluation.status == "SEARCH_CORRECTED_IMPROVED"
    selection = select_search_budget_candidate(
        selection_ref="selection:v1.17",
        current_candidates=(candidate,),
        current_evaluations=(evaluation,),
        all_family_reservations=(reservation,),
        search_policy=search_policy,
        selector_ref="selector",
        selected_at=230,
    )
    review = review_search_budget_selection(
        selection=selection,
        selected_candidate=candidate,
        decision="APPROVE",
        rationale_ref="independent-search-review",
        reviewer_ref="search-reviewer",
        reviewed_at=235,
    )
    return exposed, sp, candidate, reservation, underlying, evaluation, selection, review


def final_policy():
    return make_protected_final_holdout_policy(
        policy_ref="policy:final:v1.17",
        subject_identity_ref=IDENTITY,
        min_final_samples=4,
        min_final_regularized_improvement_ppm=0,
        registered_at=70,
    )


def seal(samples, *, generation=0, previous=None, sealed_at=150, keeper="final-pool-keeper"):
    return make_protected_final_holdout_seal(
        pool_ref=f"pool:v1.17:{generation}",
        subject_identity_ref=IDENTITY,
        samples=samples,
        policy=final_policy(),
        generation=generation,
        previous_pool=previous,
        keeper_ref=keeper,
        sealed_at=sealed_at,
    )


def confirm(*, protected=None, confirmer="final-confirmer", pool=None):
    exposed, sp, candidate, reservation, underlying, evaluation, selection, review = search_chain()
    protected = protected or final_samples()
    pool = pool or seal(protected)
    cases, lineage, confirmation = confirm_on_protected_holdout(
        candidate=candidate,
        reservation=reservation,
        search_evaluation=evaluation,
        selection=selection,
        review=review,
        base_graph=graph(),
        exposed_samples=exposed,
        protected_samples=protected,
        structural_policy=sp,
        final_policy=final_policy(),
        pool=pool,
        confirmer_ref=confirmer,
        confirmed_at=240,
    )
    return (exposed, sp, candidate, reservation, underlying, evaluation, selection, review, protected, pool, cases, lineage, confirmation)


def test_protected_seal_exposes_commitment_not_sample_hash_list():
    pool = seal(final_samples())
    assert pool.sample_count == 4
    assert len(pool.sample_commitment) == 64
    assert not hasattr(pool, "sample_hashes")


def test_final_confirmation_rejects_reusing_discovery_or_validation_sample_as_new_split():
    exposed, sp, candidate, reservation, _, evaluation, selection, review = search_chain()
    protected = (exposed[0],) + final_samples()[:3]
    pool = seal(protected)
    with pytest.raises(ValueError, match="new split is not fresh evidence"):
        confirm_on_protected_holdout(
            candidate=candidate, reservation=reservation, search_evaluation=evaluation, selection=selection, review=review,
            base_graph=graph(), exposed_samples=exposed, protected_samples=protected, structural_policy=sp,
            final_policy=final_policy(), pool=pool, confirmer_ref="final-confirmer", confirmed_at=240,
        )


def test_final_pool_must_be_sealed_before_search_selection():
    protected = final_samples()
    late_pool = seal(protected, sealed_at=231)
    with pytest.raises(ValueError, match="sealed before model selection"):
        confirm(protected=protected, pool=late_pool)


def test_correlated_protected_holdout_confirms_selected_structure_and_records_lineage():
    result = confirm()
    candidate, pool, cases, lineage, confirmation = result[2], result[9], result[10], result[11], result[12]
    assert len(cases) == 4
    assert confirmation.status == "FINAL_CONFIRMED"
    assert confirmation.regularized_improvement_ppm > 0
    assert lineage.candidate_hash == candidate.candidate_hash
    assert lineage.final_pool_hash == pool.pool_hash
    assert set(lineage.discovery_sample_hashes).isdisjoint(lineage.final_case_hashes)
    assert set(lineage.validation_sample_hashes).isdisjoint(lineage.final_case_hashes)


def test_adverse_protected_holdout_rejects_structure_without_rewriting_search_result():
    result = confirm(protected=final_samples(correlated=False))
    evaluation, confirmation = result[5], result[12]
    assert evaluation.status == "SEARCH_CORRECTED_IMPROVED"
    assert confirmation.status == "FINAL_REJECTED"
    assert confirmation.regularized_improvement_ppm <= 0


def test_final_confirmer_is_independent_from_pool_keeper_and_search_actors():
    protected = final_samples()
    with pytest.raises(ValueError, match="independent"):
        confirm(protected=protected, confirmer="final-pool-keeper")
    with pytest.raises(ValueError, match="independent"):
        confirm(protected=protected, confirmer="selector")


def test_rotation_advances_generation_and_preserves_previous_pool_hash():
    first_samples = final_samples(start=11000)
    first = seal(first_samples, generation=0)
    second_samples = final_samples(start=12000)
    second = seal(second_samples, generation=1, previous=first, sealed_at=151)
    assert second.generation == 1
    assert second.previous_pool_hash == first.pool_hash
    assert second.sample_commitment != first.sample_commitment


def test_final_confirmation_receipt_detects_tampering():
    confirmation = confirm()[12]
    with pytest.raises(ValueError):
        replace(confirmation, regularized_improvement_ppm=confirmation.regularized_improvement_ppm + 1).validate()


def test_final_confirmed_apply_requires_final_confirmation_and_preserves_underlying_chain():
    result = confirm()
    _, _, candidate, reservation, underlying, evaluation, selection, review, _, _, _, lineage, confirmation = result
    new_graph, revision = apply_final_confirmed_selection(
        current_graph=graph(),
        candidate=candidate,
        reservation=reservation,
        underlying_validation=underlying,
        search_evaluation=evaluation,
        selection=selection,
        review=review,
        confirmation=confirmation,
        applier_ref="final-applier",
        applied_at=250,
    )
    assert new_graph.generation == 1
    assert revision.confirmation_hash == confirmation.confirmation_hash
    assert revision.lineage_hash == lineage.lineage_hash
    assert revision.base_graph_hash == graph().graph_hash


def test_rejected_final_confirmation_cannot_apply():
    result = confirm(protected=final_samples(correlated=False))
    _, _, candidate, reservation, underlying, evaluation, selection, review, _, _, _, _, confirmation = result
    with pytest.raises(ValueError, match="FINAL_CONFIRMED"):
        apply_final_confirmed_selection(
            current_graph=graph(), candidate=candidate, reservation=reservation, underlying_validation=underlying,
            search_evaluation=evaluation, selection=selection, review=review, confirmation=confirmation,
            applier_ref="final-applier", applied_at=250,
        )