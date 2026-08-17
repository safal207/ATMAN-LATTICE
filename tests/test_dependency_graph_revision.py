from hashlib import sha256

import pytest

from model.calibration import DependencyPairSample, _digest as calibration_digest, summarize_dependency_samples
from model.dependency_graph_revision import (
    DependencyGraphEdge,
    apply_structural_graph_revision,
    make_dependency_graph,
    make_dependency_graph_edge,
    make_structural_graph_revision_proposal,
    replay_structural_graph_revision,
    review_structural_graph_revision,
)


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def sample(index: int, *, left: bool, right: bool, mode: str = "INDEPENDENT", left_ref: str = "signal:L", right_ref: str = "signal:R", pair_key: str | None = None) -> DependencyPairSample:
    key = pair_key or h(f"pair:{left_ref}:{right_ref}:{mode}")
    fields = {
        "pair_key": key,
        "resolution_hash": h(f"resolution:{index}"),
        "dependency_group_ref": "group:test",
        "left_model_ref": left_ref,
        "right_model_ref": right_ref,
        "declared_mode": mode,
        "resolved_hypothesis_ref": "H:A",
        "left_evidence_hash": h(f"left:{index}"),
        "right_evidence_hash": h(f"right:{index}"),
        "left_positive": left,
        "right_positive": right,
        "sampled_at": 100 + index,
    }
    provisional = DependencyPairSample(**fields, sample_hash="0" * 64)
    result = DependencyPairSample(**fields, sample_hash=calibration_digest(provisional.material()))
    result.validate()
    return result


def challenged_samples() -> tuple[DependencyPairSample, ...]:
    values = [(True, True)] * 5 + [(False, False)] * 5
    return tuple(sample(i, left=left, right=right) for i, (left, right) in enumerate(values))


def independent_samples() -> tuple[DependencyPairSample, ...]:
    values = [(False, False), (False, True), (True, False), (True, True)] * 3
    return tuple(sample(i, left=left, right=right) for i, (left, right) in enumerate(values))


def empty_graph() -> object:
    return make_dependency_graph(
        "graph:test",
        subject_identity_ref="agent:test",
        generation=0,
        edges=(),
        evidence_state_hash=h("graph:evidence:0"),
    )


def challenge_snapshot(samples):
    return summarize_dependency_samples(samples, min_samples=6, dependency_threshold_bps=1000, measured_at=200)


def test_correlation_challenge_can_produce_competing_oriented_proposals_without_causality_claim():
    samples = challenged_samples()
    snapshot = challenge_snapshot(samples)
    assert snapshot.assessment == "INDEPENDENCE_CHALLENGED"
    graph = empty_graph()
    left_to_right = make_structural_graph_revision_proposal(
        proposal_ref="proposal:ltr",
        base_graph=graph,
        calibration_snapshot=snapshot,
        samples=samples,
        direction="LEFT_TO_RIGHT",
        reason_ref="correlation-challenge",
        proposer_ref="proposer",
        proposed_at=220,
    )
    right_to_left = make_structural_graph_revision_proposal(
        proposal_ref="proposal:rtl",
        base_graph=graph,
        calibration_snapshot=snapshot,
        samples=samples,
        direction="RIGHT_TO_LEFT",
        reason_ref="correlation-challenge",
        proposer_ref="proposer",
        proposed_at=220,
    )
    assert left_to_right.parent_model_ref == "signal:L"
    assert left_to_right.child_model_ref == "signal:R"
    assert right_to_left.parent_model_ref == "signal:R"
    assert right_to_left.child_model_ref == "signal:L"
    assert {edge.relation for edge in left_to_right.proposed_edges + right_to_left.proposed_edges} == {"STATISTICAL_CONDITIONING"}


def test_graph_edges_cannot_claim_causality_by_relation_label():
    edge = DependencyGraphEdge("signal:L", "signal:R", "CAUSES", h("fake-edge"))
    with pytest.raises(ValueError, match="STATISTICAL_CONDITIONING"):
        edge.validate()


def test_dependency_graph_rejects_cycles():
    base = make_dependency_graph(
        "graph:cycle",
        subject_identity_ref="agent:test",
        generation=0,
        edges=(make_dependency_graph_edge("A", "B"), make_dependency_graph_edge("B", "C")),
        evidence_state_hash=h("cycle:0"),
    )
    pair_key = h("pair:C:A")
    samples = tuple(sample(i, left=left, right=right, left_ref="C", right_ref="A", pair_key=pair_key) for i, (left, right) in enumerate([(True, True)] * 4 + [(False, False)] * 4))
    snapshot = summarize_dependency_samples(samples, min_samples=6, dependency_threshold_bps=1000, measured_at=200)
    with pytest.raises(ValueError, match="acyclic"):
        make_structural_graph_revision_proposal(
            proposal_ref="proposal:cycle",
            base_graph=base,
            calibration_snapshot=snapshot,
            samples=samples,
            direction="LEFT_TO_RIGHT",
            reason_ref="challenge",
            proposer_ref="proposer",
            proposed_at=220,
        )


def test_leave_one_out_replay_rewards_real_predictive_structure():
    samples = challenged_samples()
    graph = empty_graph()
    proposal = make_structural_graph_revision_proposal(
        proposal_ref="proposal:replay",
        base_graph=graph,
        calibration_snapshot=challenge_snapshot(samples),
        samples=samples,
        direction="LEFT_TO_RIGHT",
        reason_ref="challenge",
        proposer_ref="proposer",
        proposed_at=220,
    )
    cases, replay = replay_structural_graph_revision(proposal, graph, samples, min_cases=6, replayed_at=230)
    assert len(cases) == 10
    assert replay.status == "STRUCTURE_IMPROVED"
    assert replay.improvement_ppm is not None and replay.improvement_ppm > 0
    assert replay.proposed_mean_brier_ppm < replay.base_mean_brier_ppm


def test_unhelpful_structure_cannot_be_approved():
    samples = independent_samples()
    # Build an explicit challenge snapshot to exercise replay/review policy; replay still decides on history.
    snapshot = challenge_snapshot(challenged_samples())
    graph = empty_graph()
    proposal = make_structural_graph_revision_proposal(
        proposal_ref="proposal:no-improvement",
        base_graph=graph,
        calibration_snapshot=snapshot,
        samples=tuple(sample(i, left=s.left_positive, right=s.right_positive, pair_key=snapshot.pair_key) for i, s in enumerate(samples)),
        direction="LEFT_TO_RIGHT",
        reason_ref="challenge",
        proposer_ref="proposer",
        proposed_at=220,
    )
    _, replay = replay_structural_graph_revision(proposal, graph, tuple(sample(i, left=s.left_positive, right=s.right_positive, pair_key=snapshot.pair_key) for i, s in enumerate(samples)), min_cases=6, replayed_at=230)
    assert replay.status == "NO_STRUCTURE_IMPROVEMENT"
    with pytest.raises(ValueError, match="improved replay"):
        review_structural_graph_revision(
            proposal,
            replay,
            decision="APPROVE",
            rationale_ref="review",
            reviewer_ref="reviewer",
            reviewed_at=240,
        )


def test_reviewer_must_be_independent_from_structural_proposer():
    samples = challenged_samples()
    graph = empty_graph()
    proposal = make_structural_graph_revision_proposal(
        proposal_ref="proposal:self-review",
        base_graph=graph,
        calibration_snapshot=challenge_snapshot(samples),
        samples=samples,
        direction="LEFT_TO_RIGHT",
        reason_ref="challenge",
        proposer_ref="same-actor",
        proposed_at=220,
    )
    _, replay = replay_structural_graph_revision(proposal, graph, samples, min_cases=6, replayed_at=230)
    with pytest.raises(ValueError, match="independent"):
        review_structural_graph_revision(
            proposal,
            replay,
            decision="APPROVE",
            rationale_ref="review",
            reviewer_ref="same-actor",
            reviewed_at=240,
        )


def test_apply_advances_graph_generation_without_erasing_base_graph():
    samples = challenged_samples()
    graph = empty_graph()
    proposal = make_structural_graph_revision_proposal(
        proposal_ref="proposal:apply",
        base_graph=graph,
        calibration_snapshot=challenge_snapshot(samples),
        samples=samples,
        direction="LEFT_TO_RIGHT",
        reason_ref="challenge",
        proposer_ref="proposer",
        proposed_at=220,
    )
    _, replay = replay_structural_graph_revision(proposal, graph, samples, min_cases=6, replayed_at=230)
    review = review_structural_graph_revision(
        proposal,
        replay,
        decision="APPROVE",
        rationale_ref="independent-review",
        reviewer_ref="reviewer",
        reviewed_at=240,
    )
    new_graph, receipt = apply_structural_graph_revision(
        current_graph=graph,
        proposal=proposal,
        replay=replay,
        review=review,
        applier_ref="applier",
        applied_at=250,
    )
    assert graph.generation == 0 and graph.edges == ()
    assert new_graph.generation == 1 and len(new_graph.edges) == 1
    assert receipt.base_graph_hash == graph.graph_hash
    assert receipt.new_graph_hash == new_graph.graph_hash


def test_two_competing_proposals_from_same_base_cannot_both_apply_sequentially():
    samples = challenged_samples()
    graph = empty_graph()
    proposals = [
        make_structural_graph_revision_proposal(
            proposal_ref=f"proposal:{direction}",
            base_graph=graph,
            calibration_snapshot=challenge_snapshot(samples),
            samples=samples,
            direction=direction,
            reason_ref="challenge",
            proposer_ref="proposer",
            proposed_at=220,
        )
        for direction in ("LEFT_TO_RIGHT", "RIGHT_TO_LEFT")
    ]
    chains = []
    for proposal in proposals:
        _, replay = replay_structural_graph_revision(proposal, graph, samples, min_cases=6, replayed_at=230)
        review = review_structural_graph_revision(proposal, replay, decision="APPROVE", rationale_ref="review", reviewer_ref="reviewer", reviewed_at=240)
        chains.append((proposal, replay, review))
    first_graph, _ = apply_structural_graph_revision(current_graph=graph, proposal=chains[0][0], replay=chains[0][1], review=chains[0][2], applier_ref="applier", applied_at=250)
    with pytest.raises(ValueError, match="stale dependency graph base"):
        apply_structural_graph_revision(current_graph=first_graph, proposal=chains[1][0], replay=chains[1][1], review=chains[1][2], applier_ref="applier", applied_at=251)
