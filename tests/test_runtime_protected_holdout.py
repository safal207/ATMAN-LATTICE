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
from model.protected_holdout import (
    apply_final_confirmed_selection,
    confirm_on_protected_holdout,
    make_protected_final_holdout_policy,
    make_protected_final_holdout_seal,
)
from model.runtime_calibration import pair_to_dict
from model.runtime_dependency_graph import graph_to_dict
from model.runtime_protected_holdout import (
    FINAL_PROTOCOL,
    ROLE_FINAL_APPLIER,
    ROLE_FINAL_CONFIRMER,
    ROLE_FINAL_POLICY_KEEPER,
    ROLE_FINAL_POOL_KEEPER,
    _connect,
    action_apply,
    action_confirm_request,
    action_register_policy,
    action_seal_pool,
)
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_search_budget import (
    evaluation_to_dict,
    policy_to_dict as search_policy_to_dict,
    reservation_to_dict,
    review_to_dict,
    selection_to_dict,
)
from model.runtime_structural_validation import (
    candidate_to_dict,
    heldout_case_to_dict,
    policy_to_dict as structural_policy_to_dict,
    validation_to_dict,
)
from model.runtime_verification import verification_scope
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

IDENTITY = "agent:final-runtime"
PAIR_KEY = sha256(b"pair:final-runtime").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def sample(index: int, *, left: bool, right: bool) -> DependencyPairSample:
    fields = {
        "pair_key": PAIR_KEY,
        "resolution_hash": h(f"final-resolution:{index}:{left}:{right}"),
        "dependency_group_ref": "group:final-runtime",
        "left_model_ref": "signal:L",
        "right_model_ref": "signal:R",
        "declared_mode": "INDEPENDENT",
        "resolved_hypothesis_ref": "H:A",
        "left_evidence_hash": h(f"final-left:{index}:{left}:{right}"),
        "right_evidence_hash": h(f"final-right:{index}:{left}:{right}"),
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
        policy_ref="policy:structure:final-runtime", subject_identity_ref=IDENTITY,
        evaluation_modulus=3, min_selection_samples=6, min_evaluation_samples=2,
        dependency_threshold_bps=1000, edge_penalty_ppm=1_000, registered_at=50,
    )


def initial_graph():
    return make_dependency_graph("graph:final-runtime", subject_identity_ref=IDENTITY, generation=0, edges=(), evidence_state_hash=h("graph:final-runtime:0"))


def collect_partitioned(*, desired: str, count: int, start: int, p):
    result=[]; index=start
    while len(result)<count and index<start+5000:
        left,right=(True,True) if len(result)%2==0 else (False,False)
        item=sample(index,left=left,right=right)
        selection,evaluation,_=partition_dependency_samples((item,),p)
        if (desired=="selection" and selection) or (desired=="evaluation" and evaluation): result.append(item)
        index+=1
    assert len(result)==count
    return result,index


def exposed_history():
    p=structural_policy()
    selection,next_index=collect_partitioned(desired="selection",count=8,start=0,p=p)
    evaluation,_=collect_partitioned(desired="evaluation",count=4,start=next_index+100,p=p)
    return tuple(selection+evaluation)


def protected_samples(start=10000, *, correlated=True):
    outcomes=[(True,True),(False,False)] if correlated else [(True,False),(False,True)]
    return tuple(sample(start+i,left=outcomes[i%2][0],right=outcomes[i%2][1]) for i in range(4))


def build_search_chain():
    graph=initial_graph(); exposed=exposed_history(); sp=structural_policy()
    candidate=make_structural_validation_candidate(
        candidate_ref="candidate:final-runtime", base_graph=graph, samples=exposed, policy=sp,
        direction="LEFT_TO_RIGHT", reason_ref="final-confirmation", proposer_ref="proposer", created_at=200,
    )
    search_policy=make_search_budget_policy(
        policy_ref="policy:search:final-runtime", subject_identity_ref=IDENTITY,
        max_unique_evaluations=4, base_min_regularized_improvement_ppm=0,
        multiplicity_penalty_ppm=0, registered_at=60,
    )
    reservation=reserve_heldout_search(candidate=candidate,policy=search_policy,prior_reservations=(),budget_keeper_ref="budget",reserved_at=205)
    cases,underlying,evaluation=evaluate_reserved_candidate(
        candidate=candidate,reservation=reservation,base_graph=graph,samples=exposed,
        structural_policy=sp,search_policy=search_policy,evaluator_ref="search-evaluator",evaluated_at=210,
    )
    assert evaluation.status=="SEARCH_CORRECTED_IMPROVED"
    selection=select_search_budget_candidate(
        selection_ref="selection:final-runtime",current_candidates=(candidate,),current_evaluations=(evaluation,),
        all_family_reservations=(reservation,),search_policy=search_policy,selector_ref="selector",selected_at=230,
    )
    review=review_search_budget_selection(
        selection=selection,selected_candidate=candidate,decision="APPROVE",rationale_ref="review",
        reviewer_ref="search-reviewer",reviewed_at=235,
    )
    return graph,exposed,sp,candidate,search_policy,reservation,cases,underlying,evaluation,selection,review


def seed_db(db_path):
    bootstrap=sqlite3.connect(db_path)
    bootstrap.execute("CREATE TABLE verification_work (work_hash TEXT PRIMARY KEY, work_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, target_gate_hash TEXT NOT NULL, work_json TEXT NOT NULL, status TEXT NOT NULL, completion_json TEXT)")
    bootstrap.commit(); bootstrap.close()
    graph,exposed,sp,candidate,search_policy,reservation,cases,underlying,evaluation,selection,review=build_search_chain()
    conn=_connect(str(db_path))
    conn.execute("INSERT INTO dependency_graph_current(subject_identity_ref,graph_json) VALUES(?,?)",(IDENTITY,json.dumps(graph_to_dict(graph),sort_keys=True,separators=(",",":"))))
    for item in exposed:
        conn.execute("INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)",(item.sample_hash,item.pair_key,item.resolution_hash,json.dumps(pair_to_dict(item),sort_keys=True,separators=(",",":"))))
    conn.execute("INSERT INTO structural_validation_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)",(IDENTITY,sp.policy_ref,json.dumps(structural_policy_to_dict(sp),sort_keys=True,separators=(",",":"))))
    conn.execute("INSERT INTO structural_validation_candidate(candidate_hash,candidate_ref,subject_identity_ref,pair_key,base_graph_hash,policy_hash,history_hash,candidate_json) VALUES(?,?,?,?,?,?,?,?)",(candidate.candidate_hash,candidate.candidate_ref,IDENTITY,candidate.pair_key,candidate.proposal.base_graph_hash,candidate.policy_hash,candidate.history_hash,json.dumps(candidate_to_dict(candidate),sort_keys=True,separators=(",",":"))))
    conn.execute("INSERT INTO heldout_search_budget_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)",(IDENTITY,search_policy.policy_ref,json.dumps(search_policy_to_dict(search_policy),sort_keys=True,separators=(",",":"))))
    conn.execute("INSERT INTO heldout_search_reservation(reservation_hash,candidate_hash,family_hash,context_hash,ordinal,reservation_json) VALUES(?,?,?,?,?,?)",(reservation.reservation_hash,candidate.candidate_hash,reservation.family_hash,reservation.context_hash,reservation.ordinal,json.dumps(reservation_to_dict(reservation),sort_keys=True,separators=(",",":"))))
    conn.execute("INSERT INTO heldout_search_evaluation(evaluation_hash,candidate_hash,reservation_hash,underlying_validation_json,evaluation_json,cases_json) VALUES(?,?,?,?,?,?)",(evaluation.evaluation_hash,candidate.candidate_hash,reservation.reservation_hash,json.dumps(validation_to_dict(underlying),sort_keys=True,separators=(",",":")),json.dumps(evaluation_to_dict(evaluation),sort_keys=True,separators=(",",":")),json.dumps([heldout_case_to_dict(item) for item in cases],sort_keys=True,separators=(",",":"))))
    conn.execute("INSERT INTO heldout_search_selection(selection_hash,selection_ref,subject_identity_ref,pair_key,family_hash,selection_json) VALUES(?,?,?,?,?,?)",(selection.selection_hash,selection.selection_ref,IDENTITY,PAIR_KEY,selection.family_hash,json.dumps(selection_to_dict(selection),sort_keys=True,separators=(",",":"))))
    conn.execute("INSERT INTO heldout_search_review(review_hash,selection_hash,review_json) VALUES(?,?,?)",(review.review_hash,selection.selection_hash,json.dumps(review_to_dict(review),sort_keys=True,separators=(",",":"))))
    conn.commit(); conn.close()
    return graph,exposed,sp,candidate,search_policy,reservation,underlying,evaluation,selection,review


def grant_for(root,actor,*,subject,role):
    return issue_authority_grant(
        grant_id=f"grant:{subject}",subject_ref=subject,subject_key_id=f"key:{subject}",subject_public_key=actor.public_key(),
        roles=(role,),scopes=(verification_scope(IDENTITY),),policy_generation=17,valid_from=100,valid_until=2000,
        issuer_ref="root",issuer_key_id="root-key",issuer_private_key=root,
    )


def invoke(request,*,root,db_path,now):
    env=os.environ.copy(); env["ATMAN_TRUSTED_ISSUER_KEYS"]=json.dumps({"root-key":raw_public(root).hex()}); env["ATMAN_POLICY_GENERATION"]="17"; env["ATMAN_RUNTIME_NOW"]=str(now); env["ATMAN_RUNTIME_DB"]=str(db_path)
    completed=subprocess.run([sys.executable,"-m","model.final_worker"],input=json.dumps(request),text=True,capture_output=True,env=env,check=False)
    return completed,json.loads(completed.stdout)


def actor(root,subject,role):
    key=Ed25519PrivateKey.generate(); return key,grant_for(root,key,subject=subject,role=role)


def final_policy(now=120):
    return make_protected_final_holdout_policy(policy_ref="policy:final:runtime",subject_identity_ref=IDENTITY,min_final_samples=4,min_final_regularized_improvement_ppm=0,registered_at=now)


def policy_request(p,*,key,grant,now=120):
    proof=sign_authorized_action(grant,private_key=key,role=ROLE_FINAL_POLICY_KEEPER,scope=verification_scope(IDENTITY),action=action_register_policy(p),signed_at=now)
    return {"protocol":FINAL_PROTOCOL,"request_id":"final-policy","operation":"register_final_holdout_policy","payload":{"policy_ref":p.policy_ref,"subject_identity_ref":IDENTITY,"min_final_samples":p.min_final_samples,"min_final_regularized_improvement_ppm":p.min_final_regularized_improvement_ppm},"grant":authority_grant_to_dict(grant),"proof":authority_proof_to_dict(proof)}


def seal_request(samples,*,key,grant,now=150,pool_ref="pool:final:0",previous=None,generation=0):
    seal=make_protected_final_holdout_seal(pool_ref=pool_ref,subject_identity_ref=IDENTITY,samples=samples,policy=final_policy(),generation=generation,previous_pool=previous,keeper_ref=grant.subject_ref,sealed_at=now)
    proof=sign_authorized_action(grant,private_key=key,role=ROLE_FINAL_POOL_KEEPER,scope=verification_scope(IDENTITY),action=action_seal_pool(seal),signed_at=now)
    request={"protocol":FINAL_PROTOCOL,"request_id":pool_ref,"operation":"seal_final_holdout_pool","payload":{"pool_ref":pool_ref,"subject_identity_ref":IDENTITY,"samples":[pair_to_dict(item) for item in samples]},"grant":authority_grant_to_dict(grant),"proof":authority_proof_to_dict(proof)}
    return seal,request


def confirm_request(selection_hash,pool_hash,*,key,grant,now=240):
    action=action_confirm_request(selection_hash,pool_hash)
    proof=sign_authorized_action(grant,private_key=key,role=ROLE_FINAL_CONFIRMER,scope=verification_scope(IDENTITY),action=action,signed_at=now)
    return {"protocol":FINAL_PROTOCOL,"request_id":"confirm","operation":"confirm_selected_structure","payload":{"selection_hash":selection_hash,"pool_hash":pool_hash},"grant":authority_grant_to_dict(grant),"proof":authority_proof_to_dict(proof)}


def setup_final_runtime(db_path):
    graph,exposed,sp,candidate,search_policy,reservation,underlying,evaluation,selection,review=seed_db(db_path)
    root=Ed25519PrivateKey.generate()
    policy_actor=actor(root,"final-policy",ROLE_FINAL_POLICY_KEEPER); pool_actor=actor(root,"final-pool",ROLE_FINAL_POOL_KEEPER); confirmer_actor=actor(root,"final-confirmer",ROLE_FINAL_CONFIRMER); applier_actor=actor(root,"final-applier",ROLE_FINAL_APPLIER)
    p=final_policy(); key,grant=policy_actor; completed,response=invoke(policy_request(p,key=key,grant=grant),root=root,db_path=db_path,now=120); assert completed.returncode==0,response
    protected=protected_samples(); key,grant=pool_actor; seal,request=seal_request(protected,key=key,grant=grant); completed,response=invoke(request,root=root,db_path=db_path,now=150); assert completed.returncode==0,response
    return root,(graph,exposed,sp,candidate,search_policy,reservation,underlying,evaluation,selection,review),protected,seal,confirmer_actor,applier_actor,pool_actor


def test_runtime_state_exposes_seal_but_not_protected_samples(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"; root,chain,protected,seal,_,_,_=setup_final_runtime(db_path)
    request={"protocol":FINAL_PROTOCOL,"request_id":"state","operation":"get_final_holdout_state","payload":{}}
    completed,response=invoke(request,root=root,db_path=db_path,now=160)
    assert completed.returncode==0,response
    encoded=json.dumps(response,sort_keys=True)
    assert seal.sample_commitment in encoded
    assert protected[0].sample_hash not in encoded
    assert "samples_json" not in encoded


def test_runtime_final_confirmation_consumes_pool_once_and_is_idempotent_for_same_confirmer(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"; root,chain,protected,seal,confirmer_actor,_,_=setup_final_runtime(db_path)
    selection=chain[8]; key,grant=confirmer_actor; request=confirm_request(selection.selection_hash,seal.pool_hash,key=key,grant=grant)
    completed,response=invoke(request,root=root,db_path=db_path,now=240); assert completed.returncode==0,response; assert response["confirmation"]["status"]=="FINAL_CONFIRMED"
    completed2,response2=invoke(request,root=root,db_path=db_path,now=240); assert completed2.returncode==0,response2; assert response2["confirmation"]["confirmation_hash"]==response["confirmation"]["confirmation_hash"]
    other_key,other_grant=actor(root,"other-confirmer",ROLE_FINAL_CONFIRMER); other_request=confirm_request(selection.selection_hash,seal.pool_hash,key=other_key,grant=other_grant)
    completed3,response3=invoke(other_request,root=root,db_path=db_path,now=241); assert completed3.returncode==2; assert "consumed" in response3["error"]


def test_runtime_rotation_requires_consumed_previous_pool_and_genuinely_new_samples(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"; root,chain,protected,seal,confirmer_actor,_,pool_actor=setup_final_runtime(db_path)
    key,grant=pool_actor; next_samples=protected_samples(start=11000); _,request=seal_request(next_samples,key=key,grant=grant,now=160,pool_ref="pool:final:1",previous=seal,generation=1)
    completed,response=invoke(request,root=root,db_path=db_path,now=160); assert completed.returncode==2; assert "previous pool" in response["error"]
    selection=chain[8]; ckey,cgrant=confirmer_actor; completed,response=invoke(confirm_request(selection.selection_hash,seal.pool_hash,key=ckey,grant=cgrant),root=root,db_path=db_path,now=240); assert completed.returncode==0,response
    key,grant=pool_actor; next_seal,request=seal_request(next_samples,key=key,grant=grant,now=250,pool_ref="pool:final:1",previous=seal,generation=1); completed,response=invoke(request,root=root,db_path=db_path,now=250); assert completed.returncode==0,response; assert response["pool"]["previous_pool_hash"]==seal.pool_hash
    reused=(protected[0],)+protected_samples(start=12000)[:3]
    # generation 2 can only be attempted after generation 1 consumption; registry must still reject old sample when that point is reached.
    conn=_connect(str(db_path)); conn.execute("UPDATE protected_final_holdout_pool SET consumed_by_selection_hash='synthetic-consumed' WHERE pool_hash=?",(next_seal.pool_hash,)); conn.commit(); conn.close()
    _,bad_request=seal_request(reused,key=key,grant=grant,now=260,pool_ref="pool:final:2",previous=next_seal,generation=2)
    completed,response=invoke(bad_request,root=root,db_path=db_path,now=260); assert completed.returncode==2; assert "genuinely new" in response["error"]


def test_runtime_apply_rejects_if_final_samples_leak_into_search_history(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"; root,chain,protected,seal,confirmer_actor,applier_actor,_=setup_final_runtime(db_path)
    graph,exposed,sp,candidate,search_policy,reservation,underlying,evaluation,selection,review=chain
    ckey,cgrant=confirmer_actor; completed,response=invoke(confirm_request(selection.selection_hash,seal.pool_hash,key=ckey,grant=cgrant),root=root,db_path=db_path,now=240); assert completed.returncode==0,response
    _,_,confirmation=confirm_on_protected_holdout(candidate=candidate,reservation=reservation,search_evaluation=evaluation,selection=selection,review=review,base_graph=graph,exposed_samples=exposed,protected_samples=protected,structural_policy=sp,final_policy=final_policy(),pool=seal,confirmer_ref=cgrant.subject_ref,confirmed_at=240)
    _,expected_revision=apply_final_confirmed_selection(current_graph=graph,candidate=candidate,reservation=reservation,underlying_validation=underlying,search_evaluation=evaluation,selection=selection,review=review,confirmation=confirmation,applier_ref=applier_actor[1].subject_ref,applied_at=250)
    conn=_connect(str(db_path)); leaked=protected[0]; conn.execute("INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)",(leaked.sample_hash,leaked.pair_key,leaked.resolution_hash,json.dumps(pair_to_dict(leaked),sort_keys=True,separators=(",",":")))); conn.commit(); conn.close()
    key,grant=applier_actor; proof=sign_authorized_action(grant,private_key=key,role=ROLE_FINAL_APPLIER,scope=verification_scope(IDENTITY),action=action_apply(expected_revision),signed_at=250)
    request={"protocol":FINAL_PROTOCOL,"request_id":"apply","operation":"apply_final_confirmed_selection","payload":{"selection_hash":selection.selection_hash},"grant":authority_grant_to_dict(grant),"proof":authority_proof_to_dict(proof)}
    completed,response=invoke(request,root=root,db_path=db_path,now=250); assert completed.returncode==2; assert "leaked" in response["error"] or "stale" in response["error"]


def test_runtime_final_confirmed_apply_updates_graph_and_preserves_history(tmp_path):
    db_path=tmp_path/"runtime.sqlite3"; root,chain,protected,seal,confirmer_actor,applier_actor,_=setup_final_runtime(db_path)
    graph,exposed,sp,candidate,search_policy,reservation,underlying,evaluation,selection,review=chain
    ckey,cgrant=confirmer_actor; completed,response=invoke(confirm_request(selection.selection_hash,seal.pool_hash,key=ckey,grant=cgrant),root=root,db_path=db_path,now=240); assert completed.returncode==0,response
    _,_,confirmation=confirm_on_protected_holdout(candidate=candidate,reservation=reservation,search_evaluation=evaluation,selection=selection,review=review,base_graph=graph,exposed_samples=exposed,protected_samples=protected,structural_policy=sp,final_policy=final_policy(),pool=seal,confirmer_ref=cgrant.subject_ref,confirmed_at=240)
    key,grant=applier_actor; _,expected_revision=apply_final_confirmed_selection(current_graph=graph,candidate=candidate,reservation=reservation,underlying_validation=underlying,search_evaluation=evaluation,selection=selection,review=review,confirmation=confirmation,applier_ref=grant.subject_ref,applied_at=250)
    proof=sign_authorized_action(grant,private_key=key,role=ROLE_FINAL_APPLIER,scope=verification_scope(IDENTITY),action=action_apply(expected_revision),signed_at=250)
    request={"protocol":FINAL_PROTOCOL,"request_id":"apply","operation":"apply_final_confirmed_selection","payload":{"selection_hash":selection.selection_hash},"grant":authority_grant_to_dict(grant),"proof":authority_proof_to_dict(proof)}
    completed,response=invoke(request,root=root,db_path=db_path,now=250); assert completed.returncode==0,response; assert response["graph"]["generation"]==1
    conn=sqlite3.connect(db_path); row=conn.execute("SELECT base_graph_hash,new_graph_hash,confirmation_hash FROM final_confirmed_revision_history WHERE selection_hash=?",(selection.selection_hash,)).fetchone(); conn.close()
    assert row[0]==graph.graph_hash and row[1]==response["graph"]["graph_hash"] and row[2]==response["revision"]["confirmation_hash"]
