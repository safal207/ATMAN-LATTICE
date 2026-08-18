from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.remediation import (
    assess_remediation_proposal,
    make_remediation_proposal,
    select_remediation,
)
from model.runtime_remediation import (
    ROLE_REMEDIATION_ASSESSOR,
    ROLE_REMEDIATION_PROPOSER,
    ROLE_REMEDIATION_REVIEWER,
    ROLE_REMEDIATION_SELECTOR,
    action_assessment,
    action_proposal,
    action_review,
    action_selection,
)
from test_runtime_remediation import (
    grant_for,
    invoke,
    seed_persistent_drift,
    setup_remediation_policy,
    signed_request,
)
from model.remediation import review_remediation_selection


def test_new_assessed_proposal_stales_old_selection_but_allows_reselection(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    root, target, snapshot, latest, base_graph, current_graph = seed_persistent_drift(db_path)
    policy = setup_remediation_policy(db_path, root)

    def register(action, proposer, assessor, now):
        pkey = Ed25519PrivateKey.generate()
        pgrant = grant_for(root, pkey, subject=proposer, role=ROLE_REMEDIATION_PROPOSER)
        prop = make_remediation_proposal(
            proposal_ref=f"proposal:{action}:reselection", target=target, snapshot=snapshot, latest_evaluation=latest,
            current_graph=current_graph, rollback_graph=base_graph, policy=policy, action=action,
            reason_ref="reselection", proposer_ref=proposer, proposed_at=now,
        )
        req = signed_request(
            "register_remediation_proposal",
            {"proposal_ref": prop.proposal_ref, "snapshot_hash": snapshot.snapshot_hash, "action": action, "reason_ref": "reselection"},
            action_proposal(prop), key=pkey, grant=pgrant, role=ROLE_REMEDIATION_PROPOSER,
            request_id=f"proposal-{action}", now=now,
        )
        completed, response = invoke(req, root=root, db_path=db_path, now=now)
        assert completed.returncode == 0, response

        akey = Ed25519PrivateKey.generate()
        agrant = grant_for(root, akey, subject=assessor, role=ROLE_REMEDIATION_ASSESSOR)
        assessment = assess_remediation_proposal(proposal=prop, latest_evaluation=latest, policy=policy, assessor_ref=assessor, assessed_at=now + 1)
        req = signed_request(
            "assess_remediation_proposal", {"proposal_hash": prop.proposal_hash}, action_assessment(assessment),
            key=akey, grant=agrant, role=ROLE_REMEDIATION_ASSESSOR, request_id=f"assessment-{action}", now=now + 1,
        )
        completed, response = invoke(req, root=root, db_path=db_path, now=now + 1)
        assert completed.returncode == 0, response
        return prop, assessment

    hold, hold_assessment = register("HOLD", "proposer:hold:reselect", "assessor:hold:reselect", 2200)

    skey = Ed25519PrivateKey.generate()
    sgrant = grant_for(root, skey, subject="selector:reselect", role=ROLE_REMEDIATION_SELECTOR)
    first = select_remediation(
        selection_ref="selection:first", snapshot=snapshot, proposals=(hold,), assessments=(hold_assessment,),
        selected_proposal_hash=hold.proposal_hash, selector_ref="selector:reselect", selected_at=2220,
    )
    req = signed_request(
        "select_remediation",
        {"selection_ref": first.selection_ref, "snapshot_hash": snapshot.snapshot_hash, "selected_proposal_hash": hold.proposal_hash},
        action_selection(first), key=skey, grant=sgrant, role=ROLE_REMEDIATION_SELECTOR, request_id="selection-first", now=2220,
    )
    completed, response = invoke(req, root=root, db_path=db_path, now=2220)
    assert completed.returncode == 0, response

    collect, collect_assessment = register("COLLECT_MORE_DATA", "proposer:collect:reselect", "assessor:collect:reselect", 2230)

    reviewer_key = Ed25519PrivateKey.generate()
    reviewer_grant = grant_for(root, reviewer_key, subject="reviewer:reselect", role=ROLE_REMEDIATION_REVIEWER)
    old_review = review_remediation_selection(
        selection=first, decision="APPROVE", rationale_ref="now-stale", reviewer_ref="reviewer:reselect", reviewed_at=2240,
    )
    req = signed_request(
        "record_remediation_review",
        {"selection_hash": first.selection_hash, "decision": "APPROVE", "rationale_ref": "now-stale"},
        action_review(old_review), key=reviewer_key, grant=reviewer_grant, role=ROLE_REMEDIATION_REVIEWER,
        request_id="review-stale", now=2240,
    )
    completed, response = invoke(req, root=root, db_path=db_path, now=2240)
    assert completed.returncode == 2
    assert "candidate set changed" in response["error"]

    second = select_remediation(
        selection_ref="selection:second", snapshot=snapshot,
        proposals=(hold, collect), assessments=(hold_assessment, collect_assessment),
        selected_proposal_hash=collect.proposal_hash, selector_ref="selector:reselect", selected_at=2250,
    )
    req = signed_request(
        "select_remediation",
        {"selection_ref": second.selection_ref, "snapshot_hash": snapshot.snapshot_hash, "selected_proposal_hash": collect.proposal_hash},
        action_selection(second), key=skey, grant=sgrant, role=ROLE_REMEDIATION_SELECTOR, request_id="selection-second", now=2250,
    )
    completed, response = invoke(req, root=root, db_path=db_path, now=2250)
    assert completed.returncode == 0, response
    assert response["selection"]["selection_hash"] == second.selection_hash
    assert len(response["selection"]["proposal_hashes"]) == 2
