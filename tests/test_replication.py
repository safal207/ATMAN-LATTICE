from dataclasses import replace
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
from model.replication import (
    assert_replication_freshness,
    evaluate_replication,
    make_replication_batch,
    make_replication_policy,
    make_replication_target,
    review_replication,
    summarize_replication_series,
)
from model.search_budget import (
    evaluate_reserved_candidate,
    make_search_budget_policy,
    reserve_heldout_search,
    review_search_budget_selection,
    select_search_budget_candidate,
)
from model.structural_validation import make_structural_validation_candidate, make_structural_validation_policy, partition_dependency_samples

IDENTITY = "agent:v1.18"
PAIR_KEY = sha256(b"pair:v1.18").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def sample(index: int, *, left: bool, right: bool, prefix: str) -> DependencyPairSample:
    fields = {
        "pair_key": PAIR_KEY,
        "resolution_hash": h(f"{prefix}:resolution:{index}"),
        "dependency_group_ref": f"group:{prefix}",
        "left_model_ref": "signal:L",
        "right_model_ref": "signal:R",
        "declared_mode": "INDEPENDENT",
        "resolved_hypothesis_ref": "H:A",
        "left_evidence_hash": h(f"{prefix}:left:{index}"),
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
        policy_ref="policy:structure:v1.18",
        subject_identity_ref=IDENTITY,
        evaluation_modulus=3,
        min_selection_samples=6,
        min_evaluation_samples=2,
        dependency_threshold_bps=1000,
        edge_penalty_ppm=1_000,
        registered_at=10,
    )


def graph():
    return make_dependency_graph("graph:v1.18", subject_identity_ref=IDENTITY, generation=0, edges=(), evidence_state_hash=h("graph:v1.18:0"))


def collect_partitioned(desired: str, count: int, start: int, policy):
    rows = []
    index = start
    while len(rows) < count:
        left = len(rows) % 2 == 0
        item = sample(index, left=left, right=left, prefix="search")
        selection, evaluation, _ = partition_dependency_samples((item,), policy)
        if (desired == "selection" and selection) or (desired == "evaluation" and evaluation):
            rows.append(item)
        index += 1
    return rows, index


def search_chain():
    sp = structural_policy(); g = graph()
    selection_rows, cursor = collect_partitioned("selection", 8, 0, sp)
    evaluation_rows, _ = collect_partitioned("evaluation", 4, cursor + 100, sp)
    history = tuple(selection_rows + evaluation_rows)
    candidate = make_structural_validation_candidate(
        candidate_ref="candidate:v1.18", base_graph=g, samples=history, policy=sp,
        direction="LEFT_TO_RIGHT", reason_ref="replication-baseline", proposer_ref="proposer", created_at=200,
    )
    search_policy = make_search_budget_policy(
        policy_ref="policy:search:v1.18", subject_identity_ref=IDENTITY,
        max_unique_evaluations=4, base_min_regularized_improvement_ppm=0,
        multiplicity_penalty_ppm=0, registered_at=20,
    )
    reservation = reserve_heldout_search(candidate=candidate, policy=search_policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    _, underlying, search_eval = evaluate_reserved_candidate(
        candidate=candidate, reservation=reservation, base_graph=g, samples=history,
        structural_policy=sp, search_policy=search_policy, evaluator_ref="search-evaluator", evaluated_at=220,
    )
    assert search_eval.status == "SEARCH_CORRECTED_IMPROVED"
    selection = select_search_budget_candidate(
        selection_ref="selection:v1.18", current_candidates=(candidate,), current_evaluations=(search_eval,),
        all_family_reservations=(reservation,), search_policy=search_policy, selector_ref="selector", selected_at=230,
    )
    sreview = review_search_budget_selection(
        selection=selection, selected_candidate=candidate, decision="APPROVE",
        rationale_ref="search-review", reviewer_ref="search-reviewer", reviewed_at=240,
    )
    return sp, g, history, candidate, reservation, underlying, search_eval, selection, sreview


def confirmation_chain():
    sp, g, history, candidate, reservation, underlying, search_eval, selection, sreview = search_chain()
    cp = make_confirmation_policy(
        policy_ref="policy:confirm:v1.18", subject_identity_ref=IDENTITY,
        min_confirmation_samples=4, min_regularized_improvement_ppm=0, registered_at=30,
    )
    rows = tuple(sample(500 + i, left=(i % 2 == 0), right=(i % 2 == 0), prefix="confirm") for i in range(6))
    batch = make_confirmation_batch(
        batch_ref="batch:confirm:v1.18", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY,
        source_ref="source:confirm-a", samples=rows, batch_keeper_ref="confirm-batch", sealed_at=260,
    )
    assert_confirmation_freshness(batch=batch, search_samples=history, prior_batches=())
    exposure = authorize_confirmation_exposure(
        selection=selection, search_review=sreview, candidate=candidate, batch=batch, policy=cp,
        prior_exposures=(), exposure_keeper_ref="confirm-exposure", authorized_at=270,
    )
    _, ceval = evaluate_confirmation(
        selection=selection, candidate=candidate, batch=batch, exposure=exposure,
        confirmation_samples=rows, search_samples=history, current_graph=g,
        structural_policy=sp, confirmation_policy=cp, evaluator_ref="confirm-evaluator", evaluated_at=700,
    )
    assert ceval.status == "CONFIRMED"
    creview = review_confirmation(
        evaluation=ceval, decision="APPROVE", rationale_ref="confirm-review",
        reviewer_ref="confirm-reviewer", reviewed_at=710,
    )
    confirmed_graph, revision = apply_confirmed_selection(
        current_graph=g, candidate=candidate, reservation=reservation, underlying_validation=underlying,
        search_evaluation=search_eval, search_selection=selection, search_review=sreview,
        exposure=exposure, confirmation_evaluation=ceval, confirmation_review=creview,
        applier_ref="confirm-applier", applied_at=720,
    )
    target = make_replication_target(
        target_ref="target:v1.18", confirmed_revision=revision, confirmation_evaluation=ceval,
        confirmation_review=creview, confirmation_batch=batch, candidate=candidate,
        confirmed_graph=confirmed_graph, registered_at=730,
    )
    return sp, g, history, candidate, batch, confirmed_graph, revision, ceval, creview, target


def replication_policy(**overrides):
    values = dict(
        policy_ref="policy:replication:v1.18", subject_identity_ref=IDENTITY,
        min_replication_samples=4, min_temporal_gap=100,
        min_regularized_improvement_ppm=0, max_proposed_brier_degradation_ppm=100_000,
        persistent_drift_epochs=2, registered_at=740,
    )
    values.update(overrides)
    return make_replication_policy(**values)


def replication_rows(*, start=1000, correlated=True, prefix="replicate"):
    return tuple(sample(start + i, left=(i % 2 == 0), right=((i % 2 == 0) if correlated else (i % 2 != 0)), prefix=prefix) for i in range(6))


def make_batch(*, rows=None, mode="TEMPORAL_EXTERNAL", source="source:lab-b", generation=0, previous=None, start=1000):
    *_, target = confirmation_chain()
    rows = rows or replication_rows(start=start)
    return make_replication_batch(
        batch_ref=f"batch:replicate:{generation}:{source}", target=target, policy=replication_policy(),
        mode=mode, source_ref=source, environment_ref="environment:lab-b", samples=rows,
        collected_from=1000 + generation * 1000, collected_to=1200 + generation * 1000,
        generation=generation, previous_batch=previous, batch_keeper_ref=f"replication-batch-{generation}",
        sealed_at=1300 + generation * 1000,
    )


def evaluate(rows=None, *, correlated=True, generation=0, previous=None, source="source:lab-b"):
    sp, base_graph, history, candidate, confirmation_batch, confirmed_graph, _, _, _, target = confirmation_chain()
    rows = rows or replication_rows(start=1000 + generation * 1000, correlated=correlated, prefix=f"replicate:{generation}")
    batch = make_replication_batch(
        batch_ref=f"batch:replicate:{generation}", target=target, policy=replication_policy(),
        mode="TEMPORAL_EXTERNAL", source_ref=source, environment_ref=f"environment:{generation}", samples=rows,
        collected_from=1000 + generation * 1000, collected_to=1200 + generation * 1000,
        generation=generation, previous_batch=previous, batch_keeper_ref=f"batch-keeper:{generation}",
        sealed_at=1300 + generation * 1000,
    )
    assert_replication_freshness(batch=batch, search_samples=history, confirmation_batches=(confirmation_batch,), prior_replication_batches=(() if previous is None else (previous,)))
    cases, receipt = evaluate_replication(
        target=target, batch=batch, replication_samples=rows, search_samples=history,
        candidate=candidate, base_graph=base_graph, confirmed_graph=confirmed_graph,
        structural_policy=sp, replication_policy=replication_policy(), evaluator_ref=f"replication-evaluator:{generation}",
        evaluated_at=1400 + generation * 1000,
    )
    return batch, cases, receipt


def test_replication_target_binds_exact_confirmed_revision_and_baseline():
    *_, revision, ceval, _, target = confirmation_chain()
    assert target.confirmed_revision_hash == revision.revision_hash
    assert target.confirmation_evaluation_hash == ceval.evaluation_hash
    assert target.baseline_proposed_mean_brier_ppm == ceval.proposed_mean_brier_ppm


def test_external_replication_requires_distinct_source():
    *_, target = confirmation_chain()
    rows = replication_rows()
    with pytest.raises(ValueError, match="source distinct"):
        make_replication_batch(
            batch_ref="bad", target=target, policy=replication_policy(), mode="EXTERNAL",
            source_ref=target.confirmation_source_ref, environment_ref="env", samples=rows,
            collected_from=1000, collected_to=1200, generation=0, previous_batch=None,
            batch_keeper_ref="external-keeper", sealed_at=1300,
        )


def test_temporal_replication_requires_minimum_gap():
    *_, target = confirmation_chain()
    rows = tuple(sample(605 + i, left=True, right=True, prefix="too-soon") for i in range(4))
    with pytest.raises(ValueError, match="temporal gap"):
        make_replication_batch(
            batch_ref="too-soon", target=target, policy=replication_policy(min_temporal_gap=100), mode="TEMPORAL",
            source_ref=target.confirmation_source_ref, environment_ref="same-env", samples=rows,
            collected_from=705, collected_to=720, generation=0, previous_batch=None,
            batch_keeper_ref="temporal-keeper", sealed_at=730,
        )


def test_replication_freshness_rejects_confirmation_resolution_alias():
    *_, history, _, confirmation_batch, _, _, _, _, target = confirmation_chain()
    original = next(iter(confirmation_batch.resolution_hashes))
    rows = list(replication_rows())
    first = rows[0]
    fields = dict(first.__dict__)
    fields["resolution_hash"] = original
    fields["sample_hash"] = "0" * 64
    provisional = DependencyPairSample(**fields)
    fields["sample_hash"] = calibration_digest(provisional.material())
    rows[0] = DependencyPairSample(**fields)
    batch = make_replication_batch(
        batch_ref="alias", target=target, policy=replication_policy(), mode="TEMPORAL_EXTERNAL",
        source_ref="source:lab-b", environment_ref="environment:b", samples=tuple(rows),
        collected_from=1000, collected_to=1200, generation=0, previous_batch=None,
        batch_keeper_ref="replication-batch", sealed_at=1300,
    )
    with pytest.raises(ValueError, match="resolution provenance"):
        assert_replication_freshness(batch=batch, search_samples=history, confirmation_batches=(confirmation_batch,), prior_replication_batches=())


def test_fresh_external_temporal_replication_stays_replicated():
    _, cases, receipt = evaluate(correlated=True)
    assert len(cases) == 6
    assert receipt.status == "REPLICATED"
    assert receipt.drift_kind == "NONE"
    assert receipt.regularized_improvement_ppm > 0


def test_adverse_future_environment_emits_drift_without_mutation():
    _, _, receipt = evaluate(correlated=False)
    assert receipt.status == "DRIFT_SIGNAL"
    assert receipt.drift_kind in {"STRUCTURAL", "PERFORMANCE", "BOTH"}


def test_replication_uses_frozen_training_not_replication_refit():
    _, cases, receipt = evaluate(correlated=False)
    assert receipt.status == "DRIFT_SIGNAL"
    # The confirmed predictor remains the original conditional model; adverse replication data is score-only.
    assert any(case.confirmed_brier_score_ppm > 0 for case in cases)


def test_replication_batch_lineage_advances_and_windows_do_not_overlap():
    first, _, _ = evaluate(generation=0)
    second_rows = replication_rows(start=2000, prefix="replicate:1")
    *_, target = confirmation_chain()
    second = make_replication_batch(
        batch_ref="batch:replicate:1", target=target, policy=replication_policy(), mode="TEMPORAL_EXTERNAL",
        source_ref="source:lab-c", environment_ref="environment:c", samples=second_rows,
        collected_from=2000, collected_to=2200, generation=1, previous_batch=first,
        batch_keeper_ref="batch-keeper:1", sealed_at=2300,
    )
    assert second.generation == 1
    assert second.previous_batch_hash == first.batch_hash


def test_replication_reviewer_must_be_independent():
    batch, _, receipt = evaluate()
    with pytest.raises(ValueError, match="independent"):
        review_replication(evaluation=receipt, decision="ACKNOWLEDGE", rationale_ref="bad", reviewer_ref=batch.batch_keeper_ref, reviewed_at=1500)


def test_two_acknowledged_drift_epochs_raise_persistent_drift_signal():
    first, _, e0 = evaluate(correlated=False, generation=0)
    r0 = review_replication(evaluation=e0, decision="ACKNOWLEDGE", rationale_ref="drift-0", reviewer_ref="reviewer:0", reviewed_at=1500)
    rows1 = replication_rows(start=2000, correlated=False, prefix="replicate:1")
    sp, base_graph, history, candidate, confirmation_batch, confirmed_graph, _, _, _, target = confirmation_chain()
    second = make_replication_batch(
        batch_ref="batch:replicate:1", target=target, policy=replication_policy(), mode="TEMPORAL_EXTERNAL",
        source_ref="source:lab-c", environment_ref="environment:c", samples=rows1,
        collected_from=2000, collected_to=2200, generation=1, previous_batch=first,
        batch_keeper_ref="batch-keeper:1", sealed_at=2300,
    )
    assert_replication_freshness(batch=second, search_samples=history, confirmation_batches=(confirmation_batch,), prior_replication_batches=(first,))
    _, e1 = evaluate_replication(
        target=target, batch=second, replication_samples=rows1, search_samples=history, candidate=candidate,
        base_graph=base_graph, confirmed_graph=confirmed_graph, structural_policy=sp,
        replication_policy=replication_policy(), evaluator_ref="replication-evaluator:1", evaluated_at=2400,
    )
    r1 = review_replication(evaluation=e1, decision="ACKNOWLEDGE", rationale_ref="drift-1", reviewer_ref="reviewer:1", reviewed_at=2500)
    snapshot = summarize_replication_series(evaluations=(e0, e1), reviews=(r0, r1), policy=replication_policy(), measured_at=2600)
    assert snapshot.consecutive_drift_count == 2
    assert snapshot.signal == "PERSISTENT_DRIFT_SIGNAL"


def test_replication_evaluation_detects_tampering():
    _, _, receipt = evaluate()
    with pytest.raises(ValueError):
        replace(receipt, confirmed_mean_brier_ppm=receipt.confirmed_mean_brier_ppm + 1).validate()
