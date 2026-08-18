import json
import os
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
from model.remediation import (
    assess_remediation_proposal,
    execute_remediation,
    make_remediation_policy,
    make_remediation_proposal,
    review_remediation_selection,
    select_remediation,
)
from model.replication import (
    assert_replication_freshness,
    evaluate_replication,
    make_replication_batch,
    review_replication,
    summarize_replication_series,
)
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_remediation import (
    REMEDIATION_PROTOCOL,
    ROLE_REMEDIATION_APPLIER,
    ROLE_REMEDIATION_ASSESSOR,
    ROLE_REMEDIATION_POLICY_KEEPER,
    ROLE_REMEDIATION_PROPOSER,
    ROLE_REMEDIATION_REVIEWER,
    ROLE_REMEDIATION_SELECTOR,
    _connect,
    action_apply,
    action_assessment,
    action_proposal,
    action_register_policy,
    action_review,
    action_selection,
)
from model.runtime_replication import batch_to_dict, evaluation_to_dict, review_to_dict, snapshot_to_dict
from model.runtime_verification import verification_scope

from test_runtime_replication import IDENTITY, PAIR_KEY, replication_rows, setup_target


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def grant_for(root, actor, *, subject, role):
    return issue_authority_grant(
        grant_id=f"grant:remediation:{subject}", subject_ref=subject, subject_key_id=f"key:{subject}", subject_public_key=actor.public_key(),
        roles=(role,), scopes=(verification_scope(IDENTITY),), policy_generation=18,
        valid_from=100, valid_until=6000, issuer_ref="root", issuer_key_id="root-key", issuer_private_key=root,
    )


def invoke(request, *, root, db_path, now):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "18"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    completed = subprocess.run([sys.executable, "-m", "model.remediation_worker"], input=json.dumps(request), text=True, capture_output=True, env=env, check=False)
    return completed, json.loads(completed.stdout)


def signed_request(operation, payload, action, *, key, grant, role, request_id, now):
    proof = sign_authorized_action(grant, private_key=key, role=role, scope=verification_scope(IDENTITY), action=action, signed_at=now)
    return {"protocol":REMEDIATION_PROTOCOL,"request_id":request_id,"operation":operation,"payload":payload,"grant":authority_grant_to_dict(grant),"proof":authority_proof_to_dict(proof)}


def seed_persistent_drift(db_path):
    root, replication_policy, target, sp, base_graph, confirmed_graph, history, candidate = setup_target(db_path)
    evaluations = []
    reviews = []
    batches = []
    previous = None
    for generation, (start, collected_from, collected_to, sealed_at, evaluated_at, reviewed_at) in enumerate(((1000,1000,1200,1300,1400,1450),(1500,1500,1700,1800,1900,1950))):
        rows = replication_rows(correlated=False, start=start, prefix=f"drift:{generation}")
        batch = make_replication_batch(
            batch_ref=f"batch:drift:{generation}", target=target, policy=replication_policy, mode="TEMPORAL_EXTERNAL",
            source_ref=f"source:drift-lab:{generation}", environment_ref=f"environment:drift:{generation}", samples=rows,
            collected_from=collected_from, collected_to=collected_to, generation=generation, previous_batch=previous,
            batch_keeper_ref=f"drift-batch:{generation}", sealed_at=sealed_at,
        )
        assert_replication_freshness(batch=batch, search_samples=history, confirmation_batches=(), prior_replication_batches=tuple(batches))
        _, evaluation = evaluate_replication(
            target=target, batch=batch, replication_samples=rows, search_samples=history, candidate=candidate,
            base_graph=base_graph, confirmed_graph=confirmed_graph, structural_policy=sp, replication_policy=replication_policy,
            evaluator_ref=f"drift-evaluator:{generation}", evaluated_at=evaluated_at,
        )
        assert evaluation.status == "DRIFT_SIGNAL"
        review = review_replication(evaluation=evaluation, decision="ACKNOWLEDGE", rationale_ref=f"drift-reviewed:{generation}", reviewer_ref=f"drift-reviewer:{generation}", reviewed_at=reviewed_at)
        batches.append(batch); evaluations.append(evaluation); reviews.append(review); previous=batch
        conn=_connect(str(db_path))
        conn.execute("INSERT INTO replication_batch(batch_hash,batch_ref,target_hash,generation,batch_json,samples_json) VALUES(?,?,?,?,?,?)",(batch.batch_hash,batch.batch_ref,target.target_hash,batch.generation,json.dumps(batch_to_dict(batch),sort_keys=True,separators=(",",":")),json.dumps([],sort_keys=True,separators=(",",":"))))
        conn.execute("INSERT INTO replication_evaluation(evaluation_hash,batch_hash,target_hash,evaluation_json,cases_json) VALUES(?,?,?,?,?)",(evaluation.evaluation_hash,batch.batch_hash,target.target_hash,json.dumps(evaluation_to_dict(evaluation),sort_keys=True,separators=(",",":")),"[]"))
        conn.execute("INSERT INTO replication_review(review_hash,evaluation_hash,target_hash,review_json) VALUES(?,?,?,?)",(review.review_hash,evaluation.evaluation_hash,target.target_hash,json.dumps(review_to_dict(review),sort_keys=True,separators=(",",":"))))
        conn.commit(); conn.close()
    snapshot=summarize_replication_series(evaluations=tuple(evaluations),reviews=tuple(reviews),policy=replication_policy,measured_at=2000)
    assert snapshot.signal == "PERSISTENT_DRIFT_SIGNAL"
    conn=_connect(str(db_path)); conn.execute("INSERT INTO replication_snapshot(snapshot_hash,target_hash,replication_count,snapshot_json) VALUES(?,?,?,?)",(snapshot.snapshot_hash,target.target_hash,snapshot.replication_count,json.dumps(snapshot_to_dict(snapshot),sort_keys=True,separators=(",",":")))); conn.commit(); conn.close()
    return root,target,snapshot,evaluations[-1],base_graph,confirmed_graph


def setup_remediation_policy(db_path, root):
    key=Ed25519PrivateKey.generate(); grant=grant_for(root,key,subject="rem-policy",role=ROLE_REMEDIATION_POLICY_KEEPER)
    policy=make_remediation_policy(policy_ref="policy:remediation:runtime",subject_identity_ref=IDENTITY,registered_at=2100)
    req=signed_request("register_remediation_policy",{"policy_ref":policy.policy_ref,"subject_identity_ref":IDENTITY,"allowed_actions":list(policy.allowed_actions),"rollback_requires_nonpositive_improvement":True},action_register_policy(policy),key=key,grant=grant,role=ROLE_REMEDIATION_POLICY_KEEPER,request_id="policy",now=2100)
    completed,response=invoke(req,root=root,db_path=db_path,now=2100); assert completed.returncode==0,response
    return policy


def test_runtime_persistent_drift_can_choose_and_apply_forward_safe_rollback(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"
    root,target,snapshot,latest,base_graph,current_graph=seed_persistent_drift(db_path)
    policy=setup_remediation_policy(db_path,root)

    proposals=[]; assessments=[]
    for index,action in enumerate(("HOLD","SAFE_ROLLBACK")):
        proposer=f"rem-proposer:{action}"; pkey=Ed25519PrivateKey.generate(); pgrant=grant_for(root,pkey,subject=proposer,role=ROLE_REMEDIATION_PROPOSER)
        prop=make_remediation_proposal(proposal_ref=f"proposal:{action}",target=target,snapshot=snapshot,latest_evaluation=latest,current_graph=current_graph,rollback_graph=base_graph,policy=policy,action=action,reason_ref="persistent-drift",proposer_ref=proposer,proposed_at=2200+index*20)
        req=signed_request("register_remediation_proposal",{"proposal_ref":prop.proposal_ref,"snapshot_hash":snapshot.snapshot_hash,"action":action,"reason_ref":"persistent-drift"},action_proposal(prop),key=pkey,grant=pgrant,role=ROLE_REMEDIATION_PROPOSER,request_id=f"proposal-{index}",now=2200+index*20)
        completed,response=invoke(req,root=root,db_path=db_path,now=2200+index*20); assert completed.returncode==0,response
        akey=Ed25519PrivateKey.generate(); assessor=f"rem-assessor:{action}"; agrant=grant_for(root,akey,subject=assessor,role=ROLE_REMEDIATION_ASSESSOR)
        assessment=assess_remediation_proposal(proposal=prop,latest_evaluation=latest,policy=policy,assessor_ref=assessor,assessed_at=2210+index*20)
        req=signed_request("assess_remediation_proposal",{"proposal_hash":prop.proposal_hash},action_assessment(assessment),key=akey,grant=agrant,role=ROLE_REMEDIATION_ASSESSOR,request_id=f"assessment-{index}",now=2210+index*20)
        completed,response=invoke(req,root=root,db_path=db_path,now=2210+index*20); assert completed.returncode==0,response
        proposals.append(prop); assessments.append(assessment)
    rollback=proposals[1]; rollback_assessment=assessments[1]
    assert rollback_assessment.status == "ROLLBACK_SUPPORTED"

    skey=Ed25519PrivateKey.generate(); sgrant=grant_for(root,skey,subject="rem-selector",role=ROLE_REMEDIATION_SELECTOR)
    selection=select_remediation(selection_ref="selection:remediation",snapshot=snapshot,proposals=tuple(proposals),assessments=tuple(assessments),selected_proposal_hash=rollback.proposal_hash,selector_ref="rem-selector",selected_at=2260)
    req=signed_request("select_remediation",{"selection_ref":selection.selection_ref,"snapshot_hash":snapshot.snapshot_hash,"selected_proposal_hash":rollback.proposal_hash},action_selection(selection),key=skey,grant=sgrant,role=ROLE_REMEDIATION_SELECTOR,request_id="selection",now=2260)
    completed,response=invoke(req,root=root,db_path=db_path,now=2260); assert completed.returncode==0,response

    rkey=Ed25519PrivateKey.generate(); rgrant=grant_for(root,rkey,subject="rem-reviewer",role=ROLE_REMEDIATION_REVIEWER)
    review=review_remediation_selection(selection=selection,decision="APPROVE",rationale_ref="rollback-supported-by-fresh-drift",reviewer_ref="rem-reviewer",reviewed_at=2270)
    req=signed_request("record_remediation_review",{"selection_hash":selection.selection_hash,"decision":"APPROVE","rationale_ref":"rollback-supported-by-fresh-drift"},action_review(review),key=rkey,grant=rgrant,role=ROLE_REMEDIATION_REVIEWER,request_id="review",now=2270)
    completed,response=invoke(req,root=root,db_path=db_path,now=2270); assert completed.returncode==0,response

    akey=Ed25519PrivateKey.generate(); agrant=grant_for(root,akey,subject="rem-applier",role=ROLE_REMEDIATION_APPLIER)
    new_graph,execution=execute_remediation(target=target,snapshot=snapshot,current_graph=current_graph,rollback_graph=base_graph,proposal=rollback,assessment=rollback_assessment,selection=selection,review=review,applier_ref="rem-applier",applied_at=2280)
    req=signed_request("apply_remediation",{"selection_hash":selection.selection_hash},action_apply(execution),key=akey,grant=agrant,role=ROLE_REMEDIATION_APPLIER,request_id="apply",now=2280)
    completed,response=invoke(req,root=root,db_path=db_path,now=2280); assert completed.returncode==0,response
    assert response["execution"]["execution_kind"] == "FORWARD_ROLLBACK"
    assert response["graph"]["generation"] == current_graph.generation + 1
    assert response["graph"]["edges"] == []
    assert response["execution"]["former_confirmed_graph_hash"] == current_graph.graph_hash
    assert response["execution"]["rollback_source_graph_hash"] == base_graph.graph_hash


def test_runtime_wrong_role_cannot_apply_remediation(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"
    root,target,snapshot,latest,base_graph,current_graph=seed_persistent_drift(db_path)
    policy=setup_remediation_policy(db_path,root)
    pkey=Ed25519PrivateKey.generate(); pgrant=grant_for(root,pkey,subject="rem-proposer",role=ROLE_REMEDIATION_PROPOSER)
    prop=make_remediation_proposal(proposal_ref="proposal:hold",target=target,snapshot=snapshot,latest_evaluation=latest,current_graph=current_graph,rollback_graph=base_graph,policy=policy,action="HOLD",reason_ref="hold",proposer_ref="rem-proposer",proposed_at=2200)
    req=signed_request("register_remediation_proposal",{"proposal_ref":prop.proposal_ref,"snapshot_hash":snapshot.snapshot_hash,"action":"HOLD","reason_ref":"hold"},action_proposal(prop),key=pkey,grant=pgrant,role=ROLE_REMEDIATION_PROPOSER,request_id="proposal",now=2200); completed,response=invoke(req,root=root,db_path=db_path,now=2200); assert completed.returncode==0,response
    akey=Ed25519PrivateKey.generate(); agrant=grant_for(root,akey,subject="rem-assessor",role=ROLE_REMEDIATION_ASSESSOR); assessment=assess_remediation_proposal(proposal=prop,latest_evaluation=latest,policy=policy,assessor_ref="rem-assessor",assessed_at=2210)
    req=signed_request("assess_remediation_proposal",{"proposal_hash":prop.proposal_hash},action_assessment(assessment),key=akey,grant=agrant,role=ROLE_REMEDIATION_ASSESSOR,request_id="assessment",now=2210); completed,response=invoke(req,root=root,db_path=db_path,now=2210); assert completed.returncode==0,response
    skey=Ed25519PrivateKey.generate(); sgrant=grant_for(root,skey,subject="rem-selector",role=ROLE_REMEDIATION_SELECTOR); selection=select_remediation(selection_ref="selection:hold",snapshot=snapshot,proposals=(prop,),assessments=(assessment,),selected_proposal_hash=prop.proposal_hash,selector_ref="rem-selector",selected_at=2220)
    req=signed_request("select_remediation",{"selection_ref":selection.selection_ref,"snapshot_hash":snapshot.snapshot_hash,"selected_proposal_hash":prop.proposal_hash},action_selection(selection),key=skey,grant=sgrant,role=ROLE_REMEDIATION_SELECTOR,request_id="selection",now=2220); completed,response=invoke(req,root=root,db_path=db_path,now=2220); assert completed.returncode==0,response
    rkey=Ed25519PrivateKey.generate(); rgrant=grant_for(root,rkey,subject="rem-reviewer",role=ROLE_REMEDIATION_REVIEWER); review=review_remediation_selection(selection=selection,decision="APPROVE",rationale_ref="hold",reviewer_ref="rem-reviewer",reviewed_at=2230)
    req=signed_request("record_remediation_review",{"selection_hash":selection.selection_hash,"decision":"APPROVE","rationale_ref":"hold"},action_review(review),key=rkey,grant=rgrant,role=ROLE_REMEDIATION_REVIEWER,request_id="review",now=2230); completed,response=invoke(req,root=root,db_path=db_path,now=2230); assert completed.returncode==0,response
    wrong=Ed25519PrivateKey.generate(); wrong_grant=grant_for(root,wrong,subject="wrong",role=ROLE_REMEDIATION_REVIEWER)
    _,execution=execute_remediation(target=target,snapshot=snapshot,current_graph=current_graph,rollback_graph=base_graph,proposal=prop,assessment=assessment,selection=selection,review=review,applier_ref="wrong",applied_at=2240)
    req=signed_request("apply_remediation",{"selection_hash":selection.selection_hash},action_apply(execution),key=wrong,grant=wrong_grant,role=ROLE_REMEDIATION_REVIEWER,request_id="wrong-apply",now=2240)
    completed,response=invoke(req,root=root,db_path=db_path,now=2240)
    assert completed.returncode == 2
    assert "required_role_mismatch" in response["error"]
