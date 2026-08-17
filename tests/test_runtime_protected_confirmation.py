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
    authorize_confirmation_exposure,
    evaluate_confirmation,
    make_confirmation_batch,
    make_confirmation_policy,
    review_confirmation,
)
from model.runtime_calibration import pair_to_dict
from model.runtime_dependency_graph import graph_to_dict
from model.runtime_protected_confirmation import (
    CONFIRM_PROTOCOL,
    ROLE_CONFIRMED_APPLIER,
    ROLE_CONFIRM_BATCH_KEEPER,
    ROLE_CONFIRM_EVALUATOR,
    ROLE_CONFIRM_EXPOSURE_KEEPER,
    ROLE_CONFIRM_POLICY_KEEPER,
    ROLE_CONFIRM_REVIEWER,
    _connect,
    action_apply,
    action_authorize_exposure,
    action_evaluate,
    action_register_policy,
    action_review,
    action_seal_batch,
)
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_search_budget import (
    evaluation_to_dict as search_evaluation_to_dict,
    policy_to_dict as search_policy_to_dict,
    reservation_to_dict,
    review_to_dict as search_review_to_dict,
    selection_to_dict as search_selection_to_dict,
)
from model.runtime_structural_validation import candidate_to_dict, policy_to_dict as structural_policy_to_dict, validation_to_dict
from model.runtime_verification import verification_scope
from model.search_budget import evaluate_reserved_candidate, make_search_budget_policy, reserve_heldout_search, review_search_budget_selection, select_search_budget_candidate
from model.structural_validation import make_structural_validation_candidate, make_structural_validation_policy, partition_dependency_samples

IDENTITY = "agent:confirm-runtime"
PAIR_KEY = sha256(b"pair:confirm-runtime").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def sample(index: int, *, left: bool, right: bool, prefix: str = "search") -> DependencyPairSample:
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
    return make_structural_validation_policy(policy_ref="policy:structure:confirm-runtime", subject_identity_ref=IDENTITY, evaluation_modulus=3, min_selection_samples=6, min_evaluation_samples=2, dependency_threshold_bps=1000, edge_penalty_ppm=1_000, registered_at=100)


def collect_partitioned(desired, count, start, policy):
    rows = []; index = start
    while len(rows) < count:
        left = len(rows) % 2 == 0; item = sample(index, left=left, right=left)
        selection, evaluation, _ = partition_dependency_samples((item,), policy)
        if (desired == "selection" and selection) or (desired == "evaluation" and evaluation): rows.append(item)
        index += 1
    return rows, index


def build_chain():
    sp = structural_policy(); g = make_dependency_graph("graph:confirm-runtime", subject_identity_ref=IDENTITY, generation=0, edges=(), evidence_state_hash=h("graph:confirm-runtime:0"))
    selection_rows, cursor = collect_partitioned("selection", 8, 0, sp); evaluation_rows, _ = collect_partitioned("evaluation", 4, cursor + 100, sp); history = tuple(selection_rows + evaluation_rows)
    candidate = make_structural_validation_candidate(candidate_ref="candidate:confirm-runtime", base_graph=g, samples=history, policy=sp, direction="LEFT_TO_RIGHT", reason_ref="search", proposer_ref="proposer", created_at=200)
    search_policy = make_search_budget_policy(policy_ref="policy:search:confirm-runtime", subject_identity_ref=IDENTITY, max_unique_evaluations=4, base_min_regularized_improvement_ppm=0, multiplicity_penalty_ppm=0, registered_at=210)
    reservation = reserve_heldout_search(candidate=candidate, policy=search_policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=220)
    _, underlying, search_eval = evaluate_reserved_candidate(candidate=candidate, reservation=reservation, base_graph=g, samples=history, structural_policy=sp, search_policy=search_policy, evaluator_ref="search-evaluator", evaluated_at=230)
    selection = select_search_budget_candidate(selection_ref="selection:confirm-runtime", current_candidates=(candidate,), current_evaluations=(search_eval,), all_family_reservations=(reservation,), search_policy=search_policy, selector_ref="selector", selected_at=240)
    search_review = review_search_budget_selection(selection=selection, selected_candidate=candidate, decision="APPROVE", rationale_ref="search-review", reviewer_ref="search-reviewer", reviewed_at=250)
    return sp, g, history, candidate, search_policy, reservation, underlying, search_eval, selection, search_review


def confirmation_rows(correlated=True, start=5000):
    return tuple(sample(start + i, left=(i % 2 == 0), right=((i % 2 == 0) if correlated else (i % 2 != 0)), prefix="confirm") for i in range(6))


def initialize_db(db_path):
    bootstrap = sqlite3.connect(db_path)
    bootstrap.execute("CREATE TABLE verification_work (work_hash TEXT PRIMARY KEY, work_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, target_gate_hash TEXT NOT NULL, work_json TEXT NOT NULL, status TEXT NOT NULL, completion_json TEXT)")
    bootstrap.commit(); bootstrap.close()
    sp, g, history, candidate, search_policy, reservation, underlying, search_eval, selection, search_review = build_chain()
    conn = _connect(str(db_path))
    conn.execute("INSERT INTO dependency_graph_current(subject_identity_ref,graph_json) VALUES(?,?)", (IDENTITY, json.dumps(graph_to_dict(g), sort_keys=True, separators=(",", ":"))))
    for item in history:
        conn.execute("INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)", (item.sample_hash, item.pair_key, item.resolution_hash, json.dumps(pair_to_dict(item), sort_keys=True, separators=(",", ":"))))
    conn.execute("INSERT INTO structural_validation_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)", (IDENTITY, sp.policy_ref, json.dumps(structural_policy_to_dict(sp), sort_keys=True, separators=(",", ":"))))
    conn.execute("INSERT INTO structural_validation_candidate(candidate_hash,candidate_ref,subject_identity_ref,pair_key,base_graph_hash,policy_hash,history_hash,candidate_json) VALUES(?,?,?,?,?,?,?,?)", (candidate.candidate_hash, candidate.candidate_ref, IDENTITY, PAIR_KEY, candidate.proposal.base_graph_hash, candidate.policy_hash, candidate.history_hash, json.dumps(candidate_to_dict(candidate), sort_keys=True, separators=(",", ":"))))
    conn.execute("INSERT INTO heldout_search_budget_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)", (IDENTITY, search_policy.policy_ref, json.dumps(search_policy_to_dict(search_policy), sort_keys=True, separators=(",", ":"))))
    conn.execute("INSERT INTO heldout_search_reservation(reservation_hash,candidate_hash,family_hash,context_hash,ordinal,reservation_json) VALUES(?,?,?,?,?,?)", (reservation.reservation_hash, candidate.candidate_hash, reservation.family_hash, reservation.context_hash, reservation.ordinal, json.dumps(reservation_to_dict(reservation), sort_keys=True, separators=(",", ":"))))
    conn.execute("INSERT INTO heldout_search_evaluation(evaluation_hash,candidate_hash,reservation_hash,underlying_validation_json,evaluation_json,cases_json) VALUES(?,?,?,?,?,?)", (search_eval.evaluation_hash, candidate.candidate_hash, reservation.reservation_hash, json.dumps(validation_to_dict(underlying), sort_keys=True, separators=(",", ":")), json.dumps(search_evaluation_to_dict(search_eval), sort_keys=True, separators=(",", ":")), "[]"))
    conn.execute("INSERT INTO heldout_search_selection(selection_hash,selection_ref,subject_identity_ref,pair_key,family_hash,selection_json) VALUES(?,?,?,?,?,?)", (selection.selection_hash, selection.selection_ref, IDENTITY, PAIR_KEY, selection.family_hash, json.dumps(search_selection_to_dict(selection), sort_keys=True, separators=(",", ":"))))
    conn.execute("INSERT INTO heldout_search_review(review_hash,selection_hash,review_json) VALUES(?,?,?)", (search_review.review_hash, selection.selection_hash, json.dumps(search_review_to_dict(search_review), sort_keys=True, separators=(",", ":"))))
    conn.commit(); conn.close()
    return sp, g, history, candidate, reservation, underlying, search_eval, selection, search_review


def grant_for(root, actor, *, subject, role):
    return issue_authority_grant(grant_id=f"grant:{subject}", subject_ref=subject, subject_key_id=f"key:{subject}", subject_public_key=actor.public_key(), roles=(role,), scopes=(verification_scope(IDENTITY),), policy_generation=17, valid_from=100, valid_until=2000, issuer_ref="root", issuer_key_id="root-key", issuer_private_key=root)


def invoke(request, *, root, db_path, now):
    env = os.environ.copy(); env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"root-key": raw_public(root).hex()}); env["ATMAN_POLICY_GENERATION"] = "17"; env["ATMAN_RUNTIME_NOW"] = str(now); env["ATMAN_RUNTIME_DB"] = str(db_path)
    completed = subprocess.run([sys.executable, "-m", "model.confirm_worker"], input=json.dumps(request), text=True, capture_output=True, env=env, check=False)
    return completed, json.loads(completed.stdout)


def request(protocol_op, payload, action, *, key, grant, role, request_id, now):
    proof = sign_authorized_action(grant, private_key=key, role=role, scope=verification_scope(IDENTITY), action=action, signed_at=now)
    return {"protocol": CONFIRM_PROTOCOL, "request_id": request_id, "operation": protocol_op, "payload": payload, "grant": authority_grant_to_dict(grant), "proof": authority_proof_to_dict(proof)}


def setup_to_evaluation(db_path, *, correlated=True):
    sp, g, history, candidate, reservation, underlying, search_eval, selection, sreview = initialize_db(db_path)
    root = Ed25519PrivateKey.generate()
    policy_key = Ed25519PrivateKey.generate(); policy_grant = grant_for(root, policy_key, subject="confirm-policy", role=ROLE_CONFIRM_POLICY_KEEPER)
    cp = make_confirmation_policy(policy_ref="policy:confirm-runtime", subject_identity_ref=IDENTITY, min_confirmation_samples=4, min_regularized_improvement_ppm=0, registered_at=300)
    req = request("register_confirmation_policy", {"policy_ref": cp.policy_ref, "subject_identity_ref": IDENTITY, "min_confirmation_samples": 4, "min_regularized_improvement_ppm": 0}, action_register_policy(cp), key=policy_key, grant=policy_grant, role=ROLE_CONFIRM_POLICY_KEEPER, request_id="policy", now=300)
    completed, response = invoke(req, root=root, db_path=db_path, now=300); assert completed.returncode == 0, response
    batch_key = Ed25519PrivateKey.generate(); batch_grant = grant_for(root, batch_key, subject="batch-keeper", role=ROLE_CONFIRM_BATCH_KEEPER); rows = confirmation_rows(correlated=correlated)
    batch = make_confirmation_batch(batch_ref="batch:runtime", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="external:sealed", samples=rows, batch_keeper_ref="batch-keeper", sealed_at=320)
    req = request("seal_confirmation_batch", {"batch_ref": batch.batch_ref, "subject_identity_ref": IDENTITY, "pair_key": PAIR_KEY, "source_ref": batch.source_ref, "samples": [pair_to_dict(item) for item in rows]}, action_seal_batch(batch), key=batch_key, grant=batch_grant, role=ROLE_CONFIRM_BATCH_KEEPER, request_id="batch", now=320)
    completed, response = invoke(req, root=root, db_path=db_path, now=320); assert completed.returncode == 0, response
    exposure_key = Ed25519PrivateKey.generate(); exposure_grant = grant_for(root, exposure_key, subject="exposure-keeper", role=ROLE_CONFIRM_EXPOSURE_KEEPER)
    exposure = authorize_confirmation_exposure(selection=selection, search_review=sreview, candidate=candidate, batch=batch, policy=cp, prior_exposures=(), exposure_keeper_ref="exposure-keeper", authorized_at=340)
    req = request("authorize_confirmation_exposure", {"selection_hash": selection.selection_hash, "batch_hash": batch.batch_hash}, action_authorize_exposure(exposure), key=exposure_key, grant=exposure_grant, role=ROLE_CONFIRM_EXPOSURE_KEEPER, request_id="exposure", now=340)
    completed, response = invoke(req, root=root, db_path=db_path, now=340); assert completed.returncode == 0, response
    eval_key = Ed25519PrivateKey.generate(); eval_grant = grant_for(root, eval_key, subject="confirmation-evaluator", role=ROLE_CONFIRM_EVALUATOR)
    _, ceval = evaluate_confirmation(selection=selection, candidate=candidate, batch=batch, exposure=exposure, confirmation_samples=rows, search_samples=history, current_graph=g, structural_policy=sp, confirmation_policy=cp, evaluator_ref="confirmation-evaluator", evaluated_at=360)
    req = request("evaluate_confirmation", {"exposure_hash": exposure.exposure_hash}, action_evaluate(ceval), key=eval_key, grant=eval_grant, role=ROLE_CONFIRM_EVALUATOR, request_id="evaluation", now=360)
    completed, response = invoke(req, root=root, db_path=db_path, now=360); assert completed.returncode == 0, response
    return root, sp, g, history, candidate, reservation, underlying, search_eval, selection, sreview, batch, exposure, ceval


def test_runtime_confirmation_survives_processes_and_applies_only_after_review(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    root, _, g, _, candidate, reservation, underlying, search_eval, selection, sreview, batch, exposure, ceval = setup_to_evaluation(db_path, correlated=True)
    assert ceval.status == "CONFIRMED"
    review_key = Ed25519PrivateKey.generate(); review_grant = grant_for(root, review_key, subject="confirmation-reviewer", role=ROLE_CONFIRM_REVIEWER)
    creview = review_confirmation(evaluation=ceval, decision="APPROVE", rationale_ref="final-independent-review", reviewer_ref="confirmation-reviewer", reviewed_at=380)
    req = request("record_confirmation_review", {"evaluation_hash": ceval.evaluation_hash, "decision": "APPROVE", "rationale_ref": "final-independent-review"}, action_review(creview), key=review_key, grant=review_grant, role=ROLE_CONFIRM_REVIEWER, request_id="review", now=380)
    completed, response = invoke(req, root=root, db_path=db_path, now=380); assert completed.returncode == 0, response
    apply_key = Ed25519PrivateKey.generate(); apply_grant = grant_for(root, apply_key, subject="confirmed-applier", role=ROLE_CONFIRMED_APPLIER)
    _, revision = apply_confirmed_selection(current_graph=g, candidate=candidate, reservation=reservation, underlying_validation=underlying, search_evaluation=search_eval, search_selection=selection, search_review=sreview, exposure=exposure, confirmation_evaluation=ceval, confirmation_review=creview, applier_ref="confirmed-applier", applied_at=400)
    req = request("apply_confirmed_structural_selection", {"evaluation_hash": ceval.evaluation_hash}, action_apply(revision), key=apply_key, grant=apply_grant, role=ROLE_CONFIRMED_APPLIER, request_id="apply", now=400)
    completed, response = invoke(req, root=root, db_path=db_path, now=400); assert completed.returncode == 0, response
    assert response["graph"]["generation"] == 1
    assert response["revision"]["revision_hash"] == revision.revision_hash


def test_runtime_sealing_rejects_search_history_as_fake_fresh_batch(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"; _, _, history, *_ = initialize_db(db_path); root = Ed25519PrivateKey.generate()
    policy_key = Ed25519PrivateKey.generate(); policy_grant = grant_for(root, policy_key, subject="confirm-policy", role=ROLE_CONFIRM_POLICY_KEEPER); cp = make_confirmation_policy(policy_ref="policy:confirm-runtime", subject_identity_ref=IDENTITY, registered_at=300)
    req = request("register_confirmation_policy", {"policy_ref": cp.policy_ref, "subject_identity_ref": IDENTITY}, action_register_policy(cp), key=policy_key, grant=policy_grant, role=ROLE_CONFIRM_POLICY_KEEPER, request_id="policy", now=300); completed, response = invoke(req, root=root, db_path=db_path, now=300); assert completed.returncode == 0, response
    batch_key = Ed25519PrivateKey.generate(); batch_grant = grant_for(root, batch_key, subject="batch-keeper", role=ROLE_CONFIRM_BATCH_KEEPER); batch = make_confirmation_batch(batch_ref="batch:fake", subject_identity_ref=IDENTITY, pair_key=PAIR_KEY, source_ref="fake", samples=(history[0],), batch_keeper_ref="batch-keeper", sealed_at=320)
    req = request("seal_confirmation_batch", {"batch_ref": batch.batch_ref, "subject_identity_ref": IDENTITY, "pair_key": PAIR_KEY, "source_ref": "fake", "samples": [pair_to_dict(history[0])]}, action_seal_batch(batch), key=batch_key, grant=batch_grant, role=ROLE_CONFIRM_BATCH_KEEPER, request_id="fake", now=320)
    completed, response = invoke(req, root=root, db_path=db_path, now=320)
    assert completed.returncode == 2 and "search sample hash" in response["error"]


def test_runtime_new_search_evidence_after_confirmation_makes_apply_stale(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    root, _, g, _, candidate, reservation, underlying, search_eval, selection, sreview, _, exposure, ceval = setup_to_evaluation(db_path, correlated=True)
    review_key = Ed25519PrivateKey.generate(); review_grant = grant_for(root, review_key, subject="confirmation-reviewer", role=ROLE_CONFIRM_REVIEWER); creview = review_confirmation(evaluation=ceval, decision="APPROVE", rationale_ref="review", reviewer_ref="confirmation-reviewer", reviewed_at=380)
    req = request("record_confirmation_review", {"evaluation_hash": ceval.evaluation_hash, "decision": "APPROVE", "rationale_ref": "review"}, action_review(creview), key=review_key, grant=review_grant, role=ROLE_CONFIRM_REVIEWER, request_id="review", now=380); completed, response = invoke(req, root=root, db_path=db_path, now=380); assert completed.returncode == 0, response
    extra = sample(9999, left=True, right=True, prefix="new-search")
    conn = _connect(str(db_path)); conn.execute("INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)", (extra.sample_hash, extra.pair_key, extra.resolution_hash, json.dumps(pair_to_dict(extra), sort_keys=True, separators=(",", ":")))); conn.commit(); conn.close()
    apply_key = Ed25519PrivateKey.generate(); apply_grant = grant_for(root, apply_key, subject="confirmed-applier", role=ROLE_CONFIRMED_APPLIER)
    _, revision = apply_confirmed_selection(current_graph=g, candidate=candidate, reservation=reservation, underlying_validation=underlying, search_evaluation=search_eval, search_selection=selection, search_review=sreview, exposure=exposure, confirmation_evaluation=ceval, confirmation_review=creview, applier_ref="confirmed-applier", applied_at=400)
    req = request("apply_confirmed_structural_selection", {"evaluation_hash": ceval.evaluation_hash}, action_apply(revision), key=apply_key, grant=apply_grant, role=ROLE_CONFIRMED_APPLIER, request_id="apply", now=400)
    completed, response = invoke(req, root=root, db_path=db_path, now=400)
    assert completed.returncode == 2
    assert "stale" in response["error"] or "current structural context" in response["error"] or "no reserved candidates" in response["error"]


def test_runtime_failed_confirmation_cannot_be_approved(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"; root, *_, ceval = setup_to_evaluation(db_path, correlated=False)
    assert ceval.status == "CONFIRMATION_REJECTED"
    review_key = Ed25519PrivateKey.generate(); review_grant = grant_for(root, review_key, subject="confirmation-reviewer", role=ROLE_CONFIRM_REVIEWER)
    try:
        review_confirmation(evaluation=ceval, decision="APPROVE", rationale_ref="bad", reviewer_ref="confirmation-reviewer", reviewed_at=380)
    except ValueError as exc:
        assert "requires CONFIRMED" in str(exc)
    else:
        raise AssertionError("failed confirmation unexpectedly approved")
