from dataclasses import replace
from hashlib import sha256

import pytest

from model.dependency_graph_revision import make_dependency_graph, make_dependency_graph_edge
from model.remediation import (
    ALL_REMEDIATION_ACTIONS,
    assess_remediation_proposal,
    execute_remediation,
    make_remediation_policy,
    make_remediation_proposal,
    review_remediation_selection,
    select_remediation,
)
from model.replication import ReplicationEvaluationReceipt, ReplicationSeriesSnapshot, ReplicationTargetReceipt, _digest as replication_digest

IDENTITY = "agent:v1.19"
PAIR = sha256(b"pair:v1.19").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def graphs():
    base = make_dependency_graph("graph:v1.19", subject_identity_ref=IDENTITY, generation=0, edges=(), evidence_state_hash=h("base-evidence"))
    edge = make_dependency_graph_edge("signal:L", "signal:R")
    current = make_dependency_graph("graph:v1.19", subject_identity_ref=IDENTITY, generation=1, edges=(edge,), evidence_state_hash=h("confirmed-evidence"))
    return base, current


def target(current):
    fields = {
        "target_ref": "target:v1.19",
        "subject_identity_ref": IDENTITY,
        "pair_key": PAIR,
        "confirmed_revision_hash": h("confirmed-revision"),
        "candidate_hash": h("candidate"),
        "confirmed_graph_hash": current.graph_hash,
        "confirmed_generation": current.generation,
        "confirmation_evaluation_hash": h("confirmation-evaluation"),
        "confirmation_review_hash": h("confirmation-review"),
        "confirmation_batch_hash": h("confirmation-batch"),
        "confirmation_source_ref": "source:confirmation",
        "confirmation_evaluated_at": 100,
        "baseline_proposed_mean_brier_ppm": 100_000,
        "baseline_regularized_improvement_ppm": 200_000,
        "candidate_proposer_ref": "candidate-proposer",
        "confirmation_evaluator_ref": "confirmation-evaluator",
        "confirmation_reviewer_ref": "confirmation-reviewer",
        "registered_at": 110,
    }
    provisional = ReplicationTargetReceipt(**fields, target_hash="0" * 64)
    result = ReplicationTargetReceipt(**fields, target_hash=replication_digest(provisional.material()))
    result.validate(); return result


def drift_evaluation(t, *, improvement=-100_000, drift_kind="BOTH", generation=1):
    confirmed_mean = 500_000 if drift_kind in {"PERFORMANCE", "BOTH"} else 150_000
    degradation = confirmed_mean - t.baseline_proposed_mean_brier_ppm
    base_reg = 400_000 if improvement <= 0 else 610_000
    confirmed_reg = base_reg - improvement
    base_mean = base_reg
    case_hashes = tuple(h(f"case:{generation}:{i}") for i in range(4))
    fields = {
        "target_hash": t.target_hash,
        "batch_hash": h(f"batch:{generation}"),
        "batch_generation": generation,
        "mode": "TEMPORAL_EXTERNAL",
        "source_ref": "source:external",
        "environment_ref": "environment:future",
        "policy_hash": h("replication-policy"),
        "confirmed_revision_hash": t.confirmed_revision_hash,
        "candidate_hash": t.candidate_hash,
        "confirmed_graph_hash": t.confirmed_graph_hash,
        "case_hashes": case_hashes,
        "evaluated_case_count": 4,
        "min_replication_samples": 4,
        "temporal_gap": 100,
        "base_mean_brier_ppm": base_mean,
        "confirmed_mean_brier_ppm": confirmed_mean,
        "base_regularized_brier_ppm": base_reg,
        "confirmed_regularized_brier_ppm": confirmed_reg,
        "regularized_improvement_ppm": improvement,
        "baseline_confirmed_mean_brier_ppm": t.baseline_proposed_mean_brier_ppm,
        "proposed_brier_degradation_ppm": degradation,
        "allowed_brier_degradation_ppm": 100_000,
        "required_min_regularized_improvement_ppm": 0,
        "drift_kind": drift_kind,
        "status": "DRIFT_SIGNAL",
        "batch_keeper_ref": "replication-batch-keeper",
        "evaluator_ref": "replication-evaluator",
        "evaluated_at": 300 + generation,
    }
    provisional = ReplicationEvaluationReceipt(**fields, evaluation_hash="0" * 64)
    result = ReplicationEvaluationReceipt(**fields, evaluation_hash=replication_digest(provisional.material()))
    result.validate(); return result


def snapshot(t, latest):
    eval0 = h("older-evaluation")
    review0 = h("older-review")
    review1 = h("latest-review")
    fields = {
        "target_hash": t.target_hash,
        "policy_hash": latest.policy_hash,
        "evaluation_hashes": (eval0, latest.evaluation_hash),
        "review_hashes": (review0, review1),
        "latest_generation": 1,
        "replication_count": 2,
        "stable_count": 0,
        "drift_count": 2,
        "consecutive_drift_count": 2,
        "persistent_drift_epochs": 2,
        "latest_status": "DRIFT_SIGNAL",
        "signal": "PERSISTENT_DRIFT_SIGNAL",
        "measured_at": 400,
    }
    provisional = ReplicationSeriesSnapshot(**fields, snapshot_hash="0" * 64)
    result = ReplicationSeriesSnapshot(**fields, snapshot_hash=replication_digest(provisional.material()))
    result.validate(); return result


def policy():
    return make_remediation_policy(policy_ref="policy:remediation:v1.19", subject_identity_ref=IDENTITY, registered_at=390)


def proposal(action="SAFE_ROLLBACK", *, improvement=-100_000, drift_kind="BOTH", proposer="proposer"):
    base, current = graphs(); t = target(current); latest = drift_evaluation(t, improvement=improvement, drift_kind=drift_kind); snap = snapshot(t, latest); p = policy()
    prop = make_remediation_proposal(proposal_ref=f"proposal:{action}:{proposer}", target=t, snapshot=snap, latest_evaluation=latest, current_graph=current, rollback_graph=base, policy=p, action=action, reason_ref="persistent-drift", proposer_ref=proposer, proposed_at=410)
    return base, current, t, latest, snap, p, prop


def test_persistent_drift_is_required_for_remediation():
    base, current, t, latest, snap, p, _ = proposal("HOLD")
    stale = replace(snap, persistent_drift_epochs=3, signal="DRIFT_OBSERVED")
    stale = replace(stale, snapshot_hash=replication_digest(stale.material()))
    stale.validate()
    with pytest.raises(ValueError, match="PERSISTENT_DRIFT_SIGNAL"):
        make_remediation_proposal(proposal_ref="proposal:nope", target=t, snapshot=stale, latest_evaluation=latest, current_graph=current, rollback_graph=base, policy=p, action="HOLD", reason_ref="too-early", proposer_ref="proposer", proposed_at=410)


def test_all_five_competing_remediation_paths_can_be_explicit_proposals():
    hashes = set()
    for action in ALL_REMEDIATION_ACTIONS:
        *_, prop = proposal(action)
        hashes.add(prop.proposal_hash)
        assert prop.action == action
    assert len(hashes) == 5


def test_safe_rollback_requires_replication_evidence_that_base_is_not_worse():
    *_, latest, snap, p, prop = proposal("SAFE_ROLLBACK", improvement=-100_000, drift_kind="BOTH")
    assessment = assess_remediation_proposal(proposal=prop, latest_evaluation=latest, policy=p, assessor_ref="assessor", assessed_at=420)
    assert assessment.status == "ROLLBACK_SUPPORTED"
    assert assessment.rollback_margin_ppm == 100_000


def test_performance_drift_alone_does_not_justify_rollback_when_structure_still_wins():
    *_, latest, snap, p, prop = proposal("SAFE_ROLLBACK", improvement=20_000, drift_kind="PERFORMANCE")
    assessment = assess_remediation_proposal(proposal=prop, latest_evaluation=latest, policy=p, assessor_ref="assessor", assessed_at=420)
    assert assessment.status == "ROLLBACK_UNSUPPORTED"
    with pytest.raises(ValueError, match="unsupported rollback"):
        select_remediation(selection_ref="selection:nope", snapshot=snap, proposals=(prop,), assessments=(assessment,), selected_proposal_hash=prop.proposal_hash, selector_ref="selector", selected_at=430)


def test_parameter_and_structural_paths_route_back_through_existing_governance():
    for action, expected in (("PARAMETER_REVISION", "ATMAN-REVISION/1.13"), ("STRUCTURAL_REVISION", "ATMAN-GRAPH/1.14")):
        *_, latest, snap, p, prop = proposal(action, proposer=f"proposer:{action}")
        assessment = assess_remediation_proposal(proposal=prop, latest_evaluation=latest, policy=p, assessor_ref=f"assessor:{action}", assessed_at=420)
        assert assessment.status == "DOWNSTREAM_GOVERNANCE_REQUIRED"
        assert prop.downstream_protocol == expected


def test_reviewer_must_be_independent_from_selection_chain():
    *_, latest, snap, p, prop = proposal("HOLD")
    assessment = assess_remediation_proposal(proposal=prop, latest_evaluation=latest, policy=p, assessor_ref="assessor", assessed_at=420)
    selection = select_remediation(selection_ref="selection:hold", snapshot=snap, proposals=(prop,), assessments=(assessment,), selected_proposal_hash=prop.proposal_hash, selector_ref="selector", selected_at=430)
    with pytest.raises(ValueError, match="reviewer must be independent"):
        review_remediation_selection(selection=selection, decision="APPROVE", rationale_ref="bad", reviewer_ref="selector", reviewed_at=440)


def test_safe_rollback_is_a_forward_generation_not_history_rewrite():
    base, current, t, latest, snap, p, prop = proposal("SAFE_ROLLBACK")
    assessment = assess_remediation_proposal(proposal=prop, latest_evaluation=latest, policy=p, assessor_ref="assessor", assessed_at=420)
    selection = select_remediation(selection_ref="selection:rollback", snapshot=snap, proposals=(prop,), assessments=(assessment,), selected_proposal_hash=prop.proposal_hash, selector_ref="selector", selected_at=430)
    review = review_remediation_selection(selection=selection, decision="APPROVE", rationale_ref="rollback-supported", reviewer_ref="reviewer", reviewed_at=440)
    new_graph, receipt = execute_remediation(target=t, snapshot=snap, current_graph=current, rollback_graph=base, proposal=prop, assessment=assessment, selection=selection, review=review, applier_ref="applier", applied_at=450)
    assert new_graph.generation == 2
    assert new_graph.edges == base.edges
    assert new_graph.graph_hash != base.graph_hash
    assert new_graph.graph_hash != current.graph_hash
    assert receipt.former_confirmed_graph_hash == current.graph_hash
    assert receipt.rollback_source_graph_hash == base.graph_hash
    assert receipt.execution_kind == "FORWARD_ROLLBACK"


def test_hold_is_explicit_but_does_not_mutate_graph():
    base, current, t, latest, snap, p, prop = proposal("HOLD")
    assessment = assess_remediation_proposal(proposal=prop, latest_evaluation=latest, policy=p, assessor_ref="assessor", assessed_at=420)
    selection = select_remediation(selection_ref="selection:hold", snapshot=snap, proposals=(prop,), assessments=(assessment,), selected_proposal_hash=prop.proposal_hash, selector_ref="selector", selected_at=430)
    review = review_remediation_selection(selection=selection, decision="APPROVE", rationale_ref="hold-and-observe", reviewer_ref="reviewer", reviewed_at=440)
    new_graph, receipt = execute_remediation(target=t, snapshot=snap, current_graph=current, rollback_graph=base, proposal=prop, assessment=assessment, selection=selection, review=review, applier_ref="applier", applied_at=450)
    assert new_graph == current
    assert receipt.execution_kind == "NO_GRAPH_CHANGE"


def test_parameter_revision_selection_does_not_bypass_revision_governance():
    base, current, t, latest, snap, p, prop = proposal("PARAMETER_REVISION")
    assessment = assess_remediation_proposal(proposal=prop, latest_evaluation=latest, policy=p, assessor_ref="assessor", assessed_at=420)
    selection = select_remediation(selection_ref="selection:param", snapshot=snap, proposals=(prop,), assessments=(assessment,), selected_proposal_hash=prop.proposal_hash, selector_ref="selector", selected_at=430)
    review = review_remediation_selection(selection=selection, decision="APPROVE", rationale_ref="route-to-v1.13", reviewer_ref="reviewer", reviewed_at=440)
    new_graph, receipt = execute_remediation(target=t, snapshot=snap, current_graph=current, rollback_graph=base, proposal=prop, assessment=assessment, selection=selection, review=review, applier_ref="applier", applied_at=450)
    assert new_graph == current
    assert receipt.execution_kind == "DOWNSTREAM_GOVERNANCE_REQUIRED"
    assert receipt.downstream_protocol == "ATMAN-REVISION/1.13"


def test_old_snapshot_cannot_authorize_current_remediation_apply():
    base, current, t, latest, snap, p, prop = proposal("HOLD")
    assessment = assess_remediation_proposal(proposal=prop, latest_evaluation=latest, policy=p, assessor_ref="assessor", assessed_at=420)
    selection = select_remediation(selection_ref="selection:stale", snapshot=snap, proposals=(prop,), assessments=(assessment,), selected_proposal_hash=prop.proposal_hash, selector_ref="selector", selected_at=430)
    review = review_remediation_selection(selection=selection, decision="APPROVE", rationale_ref="old", reviewer_ref="reviewer", reviewed_at=440)
    newer = replace(snap, measured_at=500)
    newer = replace(newer, snapshot_hash=replication_digest(newer.material()))
    with pytest.raises(ValueError, match="stale"):
        execute_remediation(target=t, snapshot=newer, current_graph=current, rollback_graph=base, proposal=prop, assessment=assessment, selection=selection, review=review, applier_ref="applier", applied_at=510)
