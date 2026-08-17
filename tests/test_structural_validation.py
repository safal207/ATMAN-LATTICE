from hashlib import sha256

import pytest

from model.calibration import DependencyPairSample, _digest as calibration_digest
from model.dependency_graph_revision import make_dependency_graph
from model.structural_validation import (
    apply_validated_structural_selection,
    make_structural_validation_candidate,
    make_structural_validation_policy,
    partition_dependency_samples,
    review_structural_selection,
    select_structural_candidate,
    validate_structural_candidate,
)


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def sample(index: int, *, left: bool, right: bool, pair_key: str) -> DependencyPairSample:
    fields = {
        "pair_key": pair_key,
        "resolution_hash": h(f"resolution:{index}:{left}:{right}"),
        "dependency_group_ref": "group:v1.15",
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


def policy(*, edge_penalty_ppm: int = 10_000, modulus: int = 3):
    return make_structural_validation_policy(
        policy_ref="policy:v1.15",
        subject_identity_ref="agent:v1.15",
        evaluation_modulus=modulus,
        min_selection_samples=6,
        min_evaluation_samples=2,
        dependency_threshold_bps=1000,
        edge_penalty_ppm=edge_penalty_ppm,
        registered_at=10,
    )


def graph():
    return make_dependency_graph(
        "graph:v1.15",
        subject_identity_ref="agent:v1.15",
        generation=0,
        edges=(),
        evidence_state_hash=h("graph:v1.15:evidence"),
    )


def collect_partitioned(*, desired: str, outcomes: list[tuple[bool, bool]], count: int, p, start: int, pair_key: str):
    result = []
    index = start
    attempts = 0
    while len(result) < count and attempts < 5000:
        left, right = outcomes[len(result) % len(outcomes)]
        item = sample(index, left=left, right=right, pair_key=pair_key)
        selection, evaluation, _ = partition_dependency_samples((item,), p)
        if (desired == "selection" and selection) or (desired == "evaluation" and evaluation):
            result.append(item)
        index += 1
        attempts += 1
    assert len(result) == count
    return result, index


def correlated_history(p, *, evaluation_outcomes=None, edge_pair=None):
    pair_key = edge_pair or h("pair:v1.15")
    selection, next_index = collect_partitioned(
        desired="selection",
        outcomes=[(True, True), (False, False)],
        count=8,
        p=p,
        start=0,
        pair_key=pair_key,
    )
    evaluation, _ = collect_partitioned(
        desired="evaluation",
        outcomes=evaluation_outcomes or [(True, True), (False, False)],
        count=4,
        p=p,
        start=next_index + 100,
        pair_key=pair_key,
    )
    return tuple(selection + evaluation)


def make_candidate_and_validation(*, p=None, direction="LEFT_TO_RIGHT", evaluation_outcomes=None, proposer="proposer", validator="validator"):
    p = p or policy()
    samples = correlated_history(p, evaluation_outcomes=evaluation_outcomes)
    candidate = make_structural_validation_candidate(
        candidate_ref=f"candidate:{direction}",
        base_graph=graph(),
        samples=samples,
        policy=p,
        direction=direction,
        reason_ref="heldout-selection",
        proposer_ref=proposer,
        created_at=200,
    )
    cases, validation = validate_structural_candidate(
        candidate=candidate,
        base_graph=graph(),
        samples=samples,
        policy=p,
        validator_ref=validator,
        validated_at=210,
    )
    return samples, candidate, cases, validation


def test_selection_and_evaluation_data_are_disjoint_and_exhaust_history():
    p = policy()
    samples = correlated_history(p)
    selection, evaluation, _ = partition_dependency_samples(samples, p)
    assert len(selection) >= p.min_selection_samples
    assert len(evaluation) >= p.min_evaluation_samples
    assert not ({item.sample_hash for item in selection} & {item.sample_hash for item in evaluation})
    assert {item.sample_hash for item in selection + evaluation} == {item.sample_hash for item in samples}


def test_candidate_selection_replay_uses_selection_partition_only():
    p = policy()
    samples = correlated_history(p)
    candidate = make_structural_validation_candidate(
        candidate_ref="candidate:selection-only",
        base_graph=graph(),
        samples=samples,
        policy=p,
        direction="LEFT_TO_RIGHT",
        reason_ref="challenge",
        proposer_ref="proposer",
        created_at=200,
    )
    assert candidate.selection_replay.sample_hashes == candidate.selection_sample_hashes
    assert set(candidate.selection_sample_hashes).isdisjoint(candidate.evaluation_sample_hashes)


def test_heldout_improvement_is_required_beyond_selection_replay():
    _, candidate, cases, validation = make_candidate_and_validation()
    assert candidate.selection_replay.status == "STRUCTURE_IMPROVED"
    assert len(cases) >= 2
    assert validation.status == "HELDOUT_IMPROVED"
    assert validation.raw_improvement_ppm > 0
    assert validation.regularized_improvement_ppm > 0


def test_selection_success_can_fail_on_heldout_data_as_overfit_signal():
    _, candidate, _, validation = make_candidate_and_validation(
        evaluation_outcomes=[(True, False), (False, True)],
    )
    assert candidate.selection_replay.status == "STRUCTURE_IMPROVED"
    assert validation.status == "OVERFIT_SIGNAL"
    assert validation.raw_improvement_ppm <= 0


def test_more_edges_are_not_more_knowledge_when_complexity_penalty_erases_gain():
    p = policy(edge_penalty_ppm=400_000)
    _, candidate, _, validation = make_candidate_and_validation(p=p)
    assert len(candidate.proposal.proposed_edges) == 1
    assert validation.raw_improvement_ppm > 0
    assert validation.regularized_improvement_ppm <= 0
    assert validation.status == "COMPLEXITY_REJECTED"


def test_heldout_validator_must_be_independent_from_proposer():
    p = policy()
    samples = correlated_history(p)
    candidate = make_structural_validation_candidate(
        candidate_ref="candidate:self-validate",
        base_graph=graph(),
        samples=samples,
        policy=p,
        direction="LEFT_TO_RIGHT",
        reason_ref="challenge",
        proposer_ref="same",
        created_at=200,
    )
    with pytest.raises(ValueError, match="independent"):
        validate_structural_candidate(
            candidate=candidate,
            base_graph=graph(),
            samples=samples,
            policy=p,
            validator_ref="same",
            validated_at=210,
        )


def test_selector_chooses_best_eligible_validation_not_just_more_edges():
    p = policy(edge_penalty_ppm=1_000)
    samples = correlated_history(p, evaluation_outcomes=[(True, True), (False, False), (True, False), (False, False)])
    candidates = []
    validations = []
    for direction, proposer, validator in (
        ("LEFT_TO_RIGHT", "proposer:ltr", "validator:ltr"),
        ("RIGHT_TO_LEFT", "proposer:rtl", "validator:rtl"),
    ):
        candidate = make_structural_validation_candidate(
            candidate_ref=f"candidate:{direction}",
            base_graph=graph(),
            samples=samples,
            policy=p,
            direction=direction,
            reason_ref="competing",
            proposer_ref=proposer,
            created_at=200,
        )
        _, validation = validate_structural_candidate(
            candidate=candidate,
            base_graph=graph(),
            samples=samples,
            policy=p,
            validator_ref=validator,
            validated_at=210,
        )
        candidates.append(candidate)
        validations.append(validation)
    selection = select_structural_candidate(
        selection_ref="selection:competing",
        candidates=tuple(candidates),
        validations=tuple(validations),
        selector_ref="selector",
        selected_at=220,
    )
    eligible = [item for item in validations if item.status == "HELDOUT_IMPROVED"]
    if eligible:
        best = sorted(eligible, key=lambda item: (-item.regularized_improvement_ppm, item.candidate_hash))[0]
        assert selection.status == "SELECTED"
        assert selection.selected_candidate_hash == best.candidate_hash
    else:
        assert selection.status == "NO_ELIGIBLE_CANDIDATE"


def test_validated_selection_apply_preserves_base_and_requires_independent_review():
    _, candidate, _, validation = make_candidate_and_validation(proposer="proposer", validator="validator")
    selection = select_structural_candidate(
        selection_ref="selection:apply",
        candidates=(candidate,),
        validations=(validation,),
        selector_ref="selector",
        selected_at=220,
    )
    review = review_structural_selection(
        selection=selection,
        selected_candidate=candidate,
        decision="APPROVE",
        rationale_ref="heldout-approved",
        reviewer_ref="reviewer",
        reviewed_at=230,
    )
    base = graph()
    new_graph, receipt = apply_validated_structural_selection(
        current_graph=base,
        candidate=candidate,
        validation=validation,
        selection=selection,
        review=review,
        applier_ref="applier",
        applied_at=240,
    )
    assert base.generation == 0 and base.edges == ()
    assert new_graph.generation == 1 and len(new_graph.edges) == 1
    assert receipt.base_graph_hash == base.graph_hash
    assert receipt.new_graph_hash == new_graph.graph_hash
