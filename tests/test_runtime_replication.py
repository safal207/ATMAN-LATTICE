import json
import os
import sqlite3
import subprocess
import sys
from hashlib import sha256

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
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
    evaluate_replication,
    make_replication_batch,
    make_replication_policy,
    make_replication_target,
    review_replication,
    summarize_replication_series,
)
from model.runtime_calibration import pair_to_dict
from model.runtime_dependency_graph import graph_to_dict
from model.runtime_protected_confirmation import (
    batch_to_dict as confirmation_batch_to_dict,
    evaluation_to_dict as confirmation_evaluation_to_dict,
    exposure_to_dict,
    review_to_dict as confirmation_review_to_dict,
    revision_to_dict as confirmed_revision_to_dict,
)
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_replication import (
    REPLICATION_PROTOCOL,
    ROLE_REPLICATION_BATCH_KEEPER,
    ROLE_REPLICATION_EVALUATOR,
    ROLE_REPLICATION_MONITOR_KEEPER,
    ROLE_REPLICATION_POLICY_KEEPER,
    ROLE_REPLICATION_REVIEWER,
    ROLE_REPLICATION_TARGET_KEEPER,
    _connect,
    action_evaluate,
    action_register_policy,
    action_register_target,
    action_review,
    action_seal_batch,
    action_snapshot,
)
from model.runtime_search_budget import (
    evaluation_to_dict as search_evaluation_to_dict,
    reservation_to_dict,
    review_to_dict as search_review_to_dict,
    selection_to_dict as search_selection_to_dict,
)
from model.runtime_structural_validation import candidate_to_dict, policy_to_dict as structural_policy_to_dict, validation_to_dict
from model.runtime_verification import verification_scope
from model.search_budget import (
    evaluate_reserved_candidate,
    make_search_budget_policy,
    reserve_heldout_search,
    review_search_budget_selection,
    select_search_budget_candidate,
)
from model.structural_validation import make_structural_validation_candidate, make_structural_validation_policy, partition_dependency_samples

IDENTITY = "agent:replication-runtime"
PAIR_KEY = sha256(b"pair:replication-runtime").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


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
    result.validate(); return result


def structural_policy():
    return make_structural_validation_policy(
        policy_ref="policy:structure:rep-runtime", subject_identity_ref=IDENTITY,
        evaluation_modulus=3, min_selection_samples=6, min_evaluation_samples=2,
        dependency_threshold_bps=1000, edge_penalty_ppm=1_000, registered_at=10,
    )


def collect_partitioned(desired, count, start, policy):
    rows = []; index = start
    while len(rows) < count:
        left = len(rows) % 2 == 0
        item = sample(index, left=left, right=left, prefix="search")
        selection, evaluation, _ = partition_dependency_samples((item,), policy)
        if (desired == "selection" and selection) or (desired == "evaluation" and evaluation): rows.append(item)
        index += 1
    return rows, index


def build_confirmed_chain():
    sp = structural_policy()
    base_graph = make_dependency_graph("graph:rep-runtime", subject_identity_ref=IDENTITY, generation=0, edges=(), evidence_state_hash=h("graph:rep-runtime:0"))
    selection_rows, cursor = collect_partitioned("selection", 8, 0, sp)
    evaluation_rows, _ = collect_partitioned("evaluation", 4, cursor + 100, sp)
    history = tuple(selection_rows + evaluation_rows)
    candidate = make_structural_validation_candidate(
        candidate_ref="candidate:rep-runtime", base_graph=base_graph, samples=history, policy=sp,
        direction="LEFT_TO_RIGHT", reason_ref="replication", proposer_ref="proposer", created_at=200,
    )
    search_policy = make_search_budget_policy(
        policy_ref="policy:search:rep-runtime", subject_identity_ref=IDENTITY, max_unique_evaluations=4,
        base_min_regularized_improvement_ppm=0, multiplicity_penalty_ppm=0, registered_at=20,
    )
    reservation = reserve_heldout_search(candidate=candidate, policy=search_policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=210)
    _, underlying, search_eval = evaluate_reserved_candidate(
        candidate=candidate, reservation=reservation, base_graph=base_graph, samples=history,
        structural_policy=sp, search_policy=search_policy, evaluator_ref="search-evaluator", evaluated_at=220,
    )
    selection = select_search_budget_candidate(
        selection_ref="selection:rep-runtime", current_candidates=(candidate,), current_evaluations=(search_eval,),
        all_family_reservations=(reservation,), search_policy=search_policy, selector_ref="selector", selected_at=230,
    )
    sreview = review_search_budget_selection(selection=selection, selected_candidate=candidate, decision="APPROVE", rationale_ref="search-review", reviewer_ref="search-reviewer", reviewed_at=240)
    cp = make_confirmation_policy(policy_ref="policy:confirm:rep-runtime", subject_identity_ref=IDENTITY, min_confirmation_samples=4, min_regularized_improvement_ppm=0, registered_at=30)
    confirmation_rows = tuple(sample(500 + i, left=(i % 2 == 0), right=(i % 2 == 0), prefix="confirm") for i in range(6))
    batch = make_confirmation_batch(batch_ref="batch:confirm:rep-runtime", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="source:confirm-a", samples=confirmation_rows, batch_keeper_ref="confirm-batch", sealed_at=260)
    assert_confirmation_freshness(batch=batch, search_samples=history, prior_batches=())
    exposure = authorize_confirmation_exposure(selection=selection, search_review=sreview, candidate=candidate, batch=batch, policy=cp, prior_exposures=(), exposure_keeper_ref="confirm-exposure", authorized_at=270)
    _, ceval = evaluate_confirmation(
        selection=selection, candidate=candidate, batch=batch, exposure=exposure, confirmation_samples=confirmation_rows,
        search_samples=history, current_graph=base_graph, structural_policy=sp, confirmation_policy=cp,
        evaluator_ref="confirm-evaluator", evaluated_at=700,
    )
    creview = review_confirmation(evaluation=ceval, decision="APPROVE", rationale_ref="confirm-review", reviewer_ref="confirm-reviewer", reviewed_at=710)
    confirmed_graph, revision = apply_confirmed_selection(
        current_graph=base_graph, candidate=candidate, reservation=reservation, underlying_validation=underlying,
        search_evaluation=search_eval, search_selection=selection, search_review=sreview, exposure=exposure,
        confirmation_evaluation=ceval, confirmation_review=creview, applier_ref="confirm-applier", applied_at=720,
    )
    return sp, base_graph, confirmed_graph, history, candidate, reservation, underlying, search_eval, selection, sreview, batch, confirmation_rows, exposure, ceval, creview, revision


def seed_db(db_path):
    bootstrap = sqlite3.connect(db_path)
    bootstrap.execute("CREATE TABLE verification_work (work_hash TEXT PRIMARY KEY, work_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, target_gate_hash TEXT NOT NULL, work_json TEXT NOT NULL, status TEXT NOT NULL, completion_json TEXT)")
    bootstrap.commit(); bootstrap.close()
    sp, base_graph, confirmed_graph, history, candidate, reservation, underlying, search_eval, selection, sreview, batch, confirmation_rows, exposure, ceval, creview, revision = build_confirmed_chain()
    conn = _connect(str(db_path))
    conn.execute("INSERT INTO dependency_graph_current(subject_identity_ref,graph_json) VALUES(?,?)", (IDENTITY, json.dumps(graph_to_dict(confirmed_graph), sort_keys=True, separators=(",", ":"))))
    for item in history:
        conn.execute("INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)", (item.sample_hash,item.pair_key,item.resolution_hash,json.dumps(pair_to_dict(item), sort_keys=True, separators=(",", ":"))))
    conn.execute("INSERT INTO structural_validation_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)", (IDENTITY,sp.policy_ref,json.dumps(structural_policy_to_dict(sp), sort_keys=True, separators=(",", ":"))))
    conn.execute("INSERT INTO structural_validation_candidate(candidate_hash,candidate_ref,subject_identity_ref,pair_key,base_graph_hash,policy_hash,history_hash,candidate_json) VALUES(?,?,?,?,?,?,?,?)", (candidate.candidate_hash,candidate.candidate_ref,IDENTITY,PAIR_KEY,candidate.proposal.base_graph_hash,candidate.policy_hash,candidate.history_hash,json.dumps(candidate_to_dict(candidate), sort_keys=True, separators=(",", ":"))))
    conn.execute("INSERT INTO protected_confirmation_batch(batch_hash,batch_ref,subject_identity_ref,pair_key,batch_json,samples_json) VALUES(?,?,?,?,?,?)", (batch.batch_hash,batch.batch_ref,IDENTITY,PAIR_KEY,json.dumps(confirmation_batch_to_dict(batch), sort_keys=True, separators=(",", ":")),json.dumps([pair_to_dict(item) for item in confirmation_rows], sort_keys=True, separators=(",", ":"))))
    conn.execute("""INSERT INTO protected_confirmation_revision_history(
        revision_hash,selection_hash,subject_identity_ref,base_graph_hash,new_graph_hash,base_graph_json,new_graph_json,batch_json,exposure_json,
        confirmation_evaluation_json,confirmation_review_json,search_selection_json,search_review_json,candidate_json,search_reservation_json,
        search_underlying_validation_json,search_evaluation_json,revision_json
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        revision.revision_hash,selection.selection_hash,IDENTITY,base_graph.graph_hash,confirmed_graph.graph_hash,
        json.dumps(graph_to_dict(base_graph), sort_keys=True, separators=(",", ":")), json.dumps(graph_to_dict(confirmed_graph), sort_keys=True, separators=(",", ":")),
        json.dumps(confirmation_batch_to_dict(batch), sort_keys=True, separators=(",", ":")), json.dumps(exposure_to_dict(exposure), sort_keys=True, separators=(",", ":")),
        json.dumps(confirmation_evaluation_to_dict(ceval), sort_keys=True, separators=(",", ":")), json.dumps(confirmation_review_to_dict(creview), sort_keys=True, separators=(",", ":")),
        json.dumps(search_selection_to_dict(selection), sort_keys=True, separators=(",", ":")), json.dumps(search_review_to_dict(sreview), sort_keys=True, separators=(",", ":")),
        json.dumps(candidate_to_dict(candidate), sort_keys=True, separators=(",", ":")), json.dumps(reservation_to_dict(reservation), sort_keys=True, separators=(",", ":")),
        json.dumps(validation_to_dict(underlying), sort_keys=True, separators=(",", ":")), json.dumps(search_evaluation_to_dict(search_eval), sort_keys=True, separators=(",", ":")),
        json.dumps(confirmed_revision_to_dict(revision), sort_keys=True, separators=(",", ":")),
    ))
    conn.commit(); conn.close()
    return sp, base_graph, confirmed_graph, history, candidate, batch, ceval, creview, revision


def grant_for(root, actor, *, subject, role):
    return issue_authority_grant(
        grant_id=f"grant:{subject}", subject_ref=subject, subject_key_id=f"key:{subject}", subject_public_key=actor.public_key(),
        roles=(role,), scopes=(verification_scope(IDENTITY),), policy_generation=18, valid_from=100, valid_until=5000,
        issuer_ref="root", issuer_key_id="root-key", issuer_private_key=root,
    )


def invoke(request, *, root, db_path, now):
    env = os.environ.copy(); env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"root-key": raw_public(root).hex()}); env["ATMAN_POLICY_GENERATION"] = "18"; env["ATMAN_RUNTIME_NOW"] = str(now); env["ATMAN_RUNTIME_DB"] = str(db_path)
    completed = subprocess.run([sys.executable, "-m", "model.replication_worker"], input=json.dumps(request), text=True, capture_output=True, env=env, check=False)
    return completed, json.loads(completed.stdout)


def request(operation, payload, action, *, key, grant, role, request_id):
    proof = sign_authorized_action(grant, private_key=key, role=role, scope=verification_scope(IDENTITY), action=action, signed_at=action.get("signed_at", 0) or 1)
    # Replace with server-aligned signature time after construction in caller.
    return {"protocol":REPLICATION_PROTOCOL,"request_id":request_id,"operation":operation,"payload":payload,"grant":authority_grant_to_dict(grant),"proof":authority_proof_to_dict(proof)}


def signed_request(operation, payload, action, *, key, grant, role, request_id, now):
    proof = sign_authorized_action(grant, private_key=key, role=role, scope=verification_scope(IDENTITY), action=action, signed_at=now)
    return {"protocol":REPLICATION_PROTOCOL,"request_id":request_id,"operation":operation,"payload":payload,"grant":authority_grant_to_dict(grant),"proof":authority_proof_to_dict(proof)}


def setup_target(db_path):
    sp, base_graph, confirmed_graph, history, candidate, confirmation_batch, ceval, creview, revision = seed_db(db_path)
    root = Ed25519PrivateKey.generate()
    pkey = Ed25519PrivateKey.generate(); pgrant = grant_for(root,pkey,subject="rep-policy",role=ROLE_REPLICATION_POLICY_KEEPER)
    policy = make_replication_policy(policy_ref="policy:replication:runtime", subject_identity_ref=IDENTITY, min_replication_samples=4, min_temporal_gap=100, min_regularized_improvement_ppm=0, max_proposed_brier_degradation_ppm=100_000, persistent_drift_epochs=2, registered_at=800)
    req = signed_request("register_replication_policy", {"policy_ref":policy.policy_ref,"subject_identity_ref":IDENTITY,"min_replication_samples":4,"min_temporal_gap":100,"min_regularized_improvement_ppm":0,"max_proposed_brier_degradation_ppm":100_000,"persistent_drift_epochs":2}, action_register_policy(policy), key=pkey, grant=pgrant, role=ROLE_REPLICATION_POLICY_KEEPER, request_id="policy", now=800)
    completed,response=invoke(req,root=root,db_path=db_path,now=800); assert completed.returncode==0,response
    tkey=Ed25519PrivateKey.generate(); tgrant=grant_for(root,tkey,subject="rep-target",role=ROLE_REPLICATION_TARGET_KEEPER)
    target=make_replication_target(target_ref="target:runtime",confirmed_revision=revision,confirmation_evaluation=ceval,confirmation_review=creview,confirmation_batch=confirmation_batch,candidate=candidate,confirmed_graph=confirmed_graph,registered_at=810)
    req=signed_request("register_replication_target",{"target_ref":target.target_ref,"confirmed_revision_hash":revision.revision_hash},action_register_target(target),key=tkey,grant=tgrant,role=ROLE_REPLICATION_TARGET_KEEPER,request_id="target",now=810)
    completed,response=invoke(req,root=root,db_path=db_path,now=810); assert completed.returncode==0,response
    return root,policy,target,sp,base_graph,confirmed_graph,history,candidate,confirmation_batch


def replication_rows(*, correlated=True, start=1000, prefix="replicate"):
    return tuple(sample(start+i,left=(i%2==0),right=((i%2==0) if correlated else (i%2!=0)),prefix=prefix) for i in range(6))


def setup_evaluation(db_path, *, correlated=True):
    root,policy,target,sp,base_graph,confirmed_graph,history,candidate,confirmation_batch=setup_target(db_path)
    rows=replication_rows(correlated=correlated)
    bkey=Ed25519PrivateKey.generate(); bgrant=grant_for(root,bkey,subject="rep-batch",role=ROLE_REPLICATION_BATCH_KEEPER)
    batch=make_replication_batch(batch_ref="batch:runtime:0",target=target,policy=policy,mode="TEMPORAL_EXTERNAL",source_ref="source:lab-b",environment_ref="env:lab-b",samples=rows,collected_from=1000,collected_to=1200,generation=0,previous_batch=None,batch_keeper_ref="rep-batch",sealed_at=820)
    req=signed_request("seal_replication_batch",{"target_hash":target.target_hash,"batch_ref":batch.batch_ref,"mode":batch.mode,"source_ref":batch.source_ref,"environment_ref":batch.environment_ref,"collected_from":1000,"collected_to":1200,"samples":[pair_to_dict(item) for item in rows]},action_seal_batch(batch),key=bkey,grant=bgrant,role=ROLE_REPLICATION_BATCH_KEEPER,request_id="batch",now=820)
    completed,response=invoke(req,root=root,db_path=db_path,now=820); assert completed.returncode==0,response
    ekey=Ed25519PrivateKey.generate(); egrant=grant_for(root,ekey,subject="rep-evaluator",role=ROLE_REPLICATION_EVALUATOR)
    _,evaluation=evaluate_replication(target=target,batch=batch,replication_samples=rows,search_samples=history,candidate=candidate,base_graph=base_graph,confirmed_graph=confirmed_graph,structural_policy=sp,replication_policy=policy,evaluator_ref="rep-evaluator",evaluated_at=830)
    req=signed_request("evaluate_replication",{"batch_hash":batch.batch_hash},action_evaluate(evaluation),key=ekey,grant=egrant,role=ROLE_REPLICATION_EVALUATOR,request_id="evaluation",now=830)
    completed,response=invoke(req,root=root,db_path=db_path,now=830); assert completed.returncode==0,response
    return root,policy,target,batch,evaluation


def test_runtime_replication_survives_processes_review_and_snapshot(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"
    root,policy,target,batch,evaluation=setup_evaluation(db_path,correlated=True)
    assert evaluation.status=="REPLICATED"
    rkey=Ed25519PrivateKey.generate(); rgrant=grant_for(root,rkey,subject="rep-reviewer",role=ROLE_REPLICATION_REVIEWER)
    review=review_replication(evaluation=evaluation,decision="ACKNOWLEDGE",rationale_ref="replication-reviewed",reviewer_ref="rep-reviewer",reviewed_at=840)
    req=signed_request("record_replication_review",{"evaluation_hash":evaluation.evaluation_hash,"decision":"ACKNOWLEDGE","rationale_ref":"replication-reviewed"},action_review(review),key=rkey,grant=rgrant,role=ROLE_REPLICATION_REVIEWER,request_id="review",now=840)
    completed,response=invoke(req,root=root,db_path=db_path,now=840); assert completed.returncode==0,response
    snapshot=summarize_replication_series(evaluations=(evaluation,),reviews=(review,),policy=policy,measured_at=850)
    mkey=Ed25519PrivateKey.generate(); mgrant=grant_for(root,mkey,subject="rep-monitor",role=ROLE_REPLICATION_MONITOR_KEEPER)
    req=signed_request("finalize_replication_snapshot",{"target_hash":target.target_hash},action_snapshot(snapshot),key=mkey,grant=mgrant,role=ROLE_REPLICATION_MONITOR_KEEPER,request_id="snapshot",now=850)
    completed,response=invoke(req,root=root,db_path=db_path,now=850); assert completed.returncode==0,response
    assert response["snapshot"]["signal"]=="STABLE_HISTORY"
    assert response["snapshot"]["replication_count"]==1


def test_runtime_external_replication_rejects_original_confirmation_source(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"
    root,policy,target,_,_,_,_,_,_=setup_target(db_path)
    rows=replication_rows()
    bkey=Ed25519PrivateKey.generate(); bgrant=grant_for(root,bkey,subject="rep-batch",role=ROLE_REPLICATION_BATCH_KEEPER)
    # Sign an otherwise expected action-shaped request; runtime must reject before accepting a batch.
    fake = make_replication_batch(batch_ref="fake",target=target,policy=policy,mode="TEMPORAL",source_ref=target.confirmation_source_ref,environment_ref="env",samples=rows,collected_from=1000,collected_to=1200,generation=0,previous_batch=None,batch_keeper_ref="rep-batch",sealed_at=820)
    req=signed_request("seal_replication_batch",{"target_hash":target.target_hash,"batch_ref":"bad-external","mode":"EXTERNAL","source_ref":target.confirmation_source_ref,"environment_ref":"env","collected_from":1000,"collected_to":1200,"samples":[pair_to_dict(item) for item in rows]},action_seal_batch(fake),key=bkey,grant=bgrant,role=ROLE_REPLICATION_BATCH_KEEPER,request_id="bad-source",now=820)
    completed,response=invoke(req,root=root,db_path=db_path,now=820)
    assert completed.returncode==2
    assert "source distinct" in response["error"]


def test_runtime_stale_target_rejects_evaluation_after_graph_change(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"
    root,policy,target,sp,base_graph,confirmed_graph,history,candidate,_=setup_target(db_path)
    rows=replication_rows()
    bkey=Ed25519PrivateKey.generate(); bgrant=grant_for(root,bkey,subject="rep-batch",role=ROLE_REPLICATION_BATCH_KEEPER)
    batch=make_replication_batch(batch_ref="batch:stale",target=target,policy=policy,mode="TEMPORAL_EXTERNAL",source_ref="source:lab-b",environment_ref="env",samples=rows,collected_from=1000,collected_to=1200,generation=0,previous_batch=None,batch_keeper_ref="rep-batch",sealed_at=820)
    req=signed_request("seal_replication_batch",{"target_hash":target.target_hash,"batch_ref":batch.batch_ref,"mode":batch.mode,"source_ref":batch.source_ref,"environment_ref":batch.environment_ref,"collected_from":1000,"collected_to":1200,"samples":[pair_to_dict(item) for item in rows]},action_seal_batch(batch),key=bkey,grant=bgrant,role=ROLE_REPLICATION_BATCH_KEEPER,request_id="batch",now=820)
    completed,response=invoke(req,root=root,db_path=db_path,now=820); assert completed.returncode==0,response
    replacement=make_dependency_graph("graph:replacement",subject_identity_ref=IDENTITY,generation=confirmed_graph.generation+1,edges=confirmed_graph.edges,evidence_state_hash=h("replacement"))
    conn=sqlite3.connect(db_path); conn.execute("UPDATE dependency_graph_current SET graph_json=? WHERE subject_identity_ref=?",(json.dumps(graph_to_dict(replacement),sort_keys=True,separators=(",",":")),IDENTITY)); conn.commit(); conn.close()
    ekey=Ed25519PrivateKey.generate(); egrant=grant_for(root,ekey,subject="rep-evaluator",role=ROLE_REPLICATION_EVALUATOR)
    _,evaluation=evaluate_replication(target=target,batch=batch,replication_samples=rows,search_samples=history,candidate=candidate,base_graph=base_graph,confirmed_graph=confirmed_graph,structural_policy=sp,replication_policy=policy,evaluator_ref="rep-evaluator",evaluated_at=830)
    req=signed_request("evaluate_replication",{"batch_hash":batch.batch_hash},action_evaluate(evaluation),key=ekey,grant=egrant,role=ROLE_REPLICATION_EVALUATOR,request_id="stale-eval",now=830)
    completed,response=invoke(req,root=root,db_path=db_path,now=830)
    assert completed.returncode==2
    assert "no longer represents current model" in response["error"]


def test_runtime_wrong_role_cannot_record_replication_review(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"
    root,_,_,_,evaluation=setup_evaluation(db_path,correlated=False)
    wrong_key=Ed25519PrivateKey.generate(); wrong_grant=grant_for(root,wrong_key,subject="wrong-review",role=ROLE_REPLICATION_EVALUATOR)
    review=review_replication(evaluation=evaluation,decision="ACKNOWLEDGE",rationale_ref="drift-seen",reviewer_ref="wrong-review",reviewed_at=840)
    req=signed_request("record_replication_review",{"evaluation_hash":evaluation.evaluation_hash,"decision":"ACKNOWLEDGE","rationale_ref":"drift-seen"},action_review(review),key=wrong_key,grant=wrong_grant,role=ROLE_REPLICATION_EVALUATOR,request_id="wrong-role",now=840)
    completed,response=invoke(req,root=root,db_path=db_path,now=840)
    assert completed.returncode==2
    assert "required_role_mismatch" in response["error"]
