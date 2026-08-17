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
from model.runtime_calibration import pair_to_dict
from model.runtime_dependency_graph import graph_to_dict
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_search_budget import (
    SEARCH_PROTOCOL,
    ROLE_SEARCH_APPLIER,
    ROLE_SEARCH_BUDGET_KEEPER,
    ROLE_SEARCH_EVALUATOR,
    ROLE_SEARCH_POLICY_KEEPER,
    ROLE_SEARCH_REVIEWER,
    ROLE_SEARCH_SELECTOR,
    _connect,
    action_apply,
    action_evaluate,
    action_finalize_selection,
    action_register_policy,
    action_reserve,
    action_review,
)
from model.runtime_structural_validation import candidate_to_dict, heldout_case_to_dict, policy_to_dict as structural_policy_to_dict, validation_to_dict
from model.runtime_verification import verification_scope
from model.search_budget import (
    apply_search_budgeted_selection,
    evaluate_reserved_candidate,
    make_search_budget_policy,
    reserve_heldout_search,
    review_search_budget_selection,
    select_search_budget_candidate,
)
from model.structural_validation import make_structural_validation_candidate, make_structural_validation_policy, partition_dependency_samples, validate_structural_candidate

IDENTITY = "agent:search-runtime"
PAIR_KEY = sha256(b"pair:search-runtime").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def sample(index: int, *, left: bool, right: bool) -> DependencyPairSample:
    fields = {
        "pair_key": PAIR_KEY,
        "resolution_hash": h(f"search-resolution:{index}:{left}:{right}"),
        "dependency_group_ref": "group:search-runtime",
        "left_model_ref": "signal:L",
        "right_model_ref": "signal:R",
        "declared_mode": "INDEPENDENT",
        "resolved_hypothesis_ref": "H:A",
        "left_evidence_hash": h(f"search-left:{index}:{left}:{right}"),
        "right_evidence_hash": h(f"search-right:{index}:{left}:{right}"),
        "left_positive": left,
        "right_positive": right,
        "sampled_at": 100 + index,
    }
    provisional = DependencyPairSample(**fields, sample_hash="0" * 64)
    result = DependencyPairSample(**fields, sample_hash=calibration_digest(provisional.material()))
    result.validate()
    return result


def structure_policy(now=100):
    return make_structural_validation_policy(
        policy_ref="policy:structure:search-runtime",
        subject_identity_ref=IDENTITY,
        evaluation_modulus=3,
        min_selection_samples=6,
        min_evaluation_samples=2,
        dependency_threshold_bps=1000,
        edge_penalty_ppm=1_000,
        registered_at=now,
    )


def collect_partitioned(*, desired: str, count: int, start: int, p):
    result = []
    index = start
    while len(result) < count and index < start + 10000:
        left, right = ((True, True), (False, False))[len(result) % 2]
        item = sample(index, left=left, right=right)
        selection, evaluation, _ = partition_dependency_samples((item,), p)
        if (desired == "selection" and selection) or (desired == "evaluation" and evaluation):
            result.append(item)
        index += 1
    assert len(result) == count
    return result, index


def pair_history():
    p = structure_policy()
    selection, next_index = collect_partitioned(desired="selection", count=8, start=0, p=p)
    evaluation, _ = collect_partitioned(desired="evaluation", count=4, start=next_index + 100, p=p)
    return tuple(selection + evaluation)


def initial_graph():
    return make_dependency_graph("graph:search-runtime", subject_identity_ref=IDENTITY, generation=0, edges=(), evidence_state_hash=h("graph:search-runtime:0"))


def initialize_db(db_path):
    bootstrap = sqlite3.connect(db_path)
    bootstrap.execute("CREATE TABLE verification_work (work_hash TEXT PRIMARY KEY, work_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, target_gate_hash TEXT NOT NULL, work_json TEXT NOT NULL, status TEXT NOT NULL, completion_json TEXT)")
    bootstrap.commit()
    bootstrap.close()
    conn = _connect(str(db_path))
    graph = initial_graph()
    conn.execute("INSERT INTO dependency_graph_current(subject_identity_ref,graph_json) VALUES(?,?)", (IDENTITY, json.dumps(graph_to_dict(graph), sort_keys=True, separators=(",", ":"))))
    p = structure_policy()
    conn.execute("INSERT INTO structural_validation_policy(subject_identity_ref,policy_ref,policy_json) VALUES(?,?,?)", (IDENTITY, p.policy_ref, json.dumps(structural_policy_to_dict(p), sort_keys=True, separators=(",", ":"))))
    history = pair_history()
    for item in history:
        conn.execute("INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)", (item.sample_hash, item.pair_key, item.resolution_hash, json.dumps(pair_to_dict(item), sort_keys=True, separators=(",", ":"))))
    candidates = []
    for direction, ref, proposer in (("LEFT_TO_RIGHT", "candidate:ltr", "proposer:ltr"), ("RIGHT_TO_LEFT", "candidate:rtl", "proposer:rtl")):
        candidate = make_structural_validation_candidate(candidate_ref=ref, base_graph=graph, samples=history, policy=p, direction=direction, reason_ref="search-budget", proposer_ref=proposer, created_at=200)
        conn.execute("INSERT INTO structural_validation_candidate(candidate_hash,candidate_ref,subject_identity_ref,pair_key,base_graph_hash,policy_hash,history_hash,candidate_json) VALUES(?,?,?,?,?,?,?,?)", (candidate.candidate_hash, candidate.candidate_ref, IDENTITY, PAIR_KEY, graph.graph_hash, candidate.policy_hash, candidate.history_hash, json.dumps(candidate_to_dict(candidate), sort_keys=True, separators=(",", ":"))))
        candidates.append(candidate)
    conn.commit()
    conn.close()
    return graph, p, history, tuple(candidates)


def grant_for(root, actor, *, subject, role):
    return issue_authority_grant(grant_id=f"grant:{subject}", subject_ref=subject, subject_key_id=f"key:{subject}", subject_public_key=actor.public_key(), roles=(role,), scopes=(verification_scope(IDENTITY),), policy_generation=16, valid_from=100, valid_until=3000, issuer_ref="root", issuer_key_id="root-key", issuer_private_key=root)


def actor(root, subject, role):
    key = Ed25519PrivateKey.generate()
    return key, grant_for(root, key, subject=subject, role=role)


def invoke(request, *, root, db_path, now):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "16"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    completed = subprocess.run([sys.executable, "-m", "model.search_worker"], input=json.dumps(request), text=True, capture_output=True, env=env, check=False)
    return completed, json.loads(completed.stdout)


def wrap(operation, payload, *, key, grant, role, action, request_id, now):
    proof = sign_authorized_action(grant, private_key=key, role=role, scope=verification_scope(IDENTITY), action=action, signed_at=now)
    return {"protocol": SEARCH_PROTOCOL, "request_id": request_id, "operation": operation, "payload": payload, "grant": authority_grant_to_dict(grant), "proof": authority_proof_to_dict(proof)}


def register_policy(db_path, root, *, max_unique=3, penalty=1_000, now=250):
    key, grant = actor(root, "search-policy", ROLE_SEARCH_POLICY_KEEPER)
    policy = make_search_budget_policy(policy_ref="policy:search-runtime", subject_identity_ref=IDENTITY, max_unique_evaluations=max_unique, base_min_regularized_improvement_ppm=0, multiplicity_penalty_ppm=penalty, registered_at=now)
    request = wrap("register_search_budget_policy", {"policy_ref": policy.policy_ref, "subject_identity_ref": IDENTITY, "max_unique_evaluations": max_unique, "base_min_regularized_improvement_ppm": 0, "multiplicity_penalty_ppm": penalty}, key=key, grant=grant, role=ROLE_SEARCH_POLICY_KEEPER, action=action_register_policy(policy), request_id="search-policy", now=now)
    completed, response = invoke(request, root=root, db_path=db_path, now=now)
    assert completed.returncode == 0, response
    return policy


def reserve(db_path, root, candidate, policy, prior, *, subject="budget", now=300):
    key, grant = actor(root, subject, ROLE_SEARCH_BUDGET_KEEPER)
    expected = reserve_heldout_search(candidate=candidate, policy=policy, prior_reservations=prior, budget_keeper_ref=subject, reserved_at=now)
    request = wrap("reserve_heldout_evaluation", {"candidate_hash": candidate.candidate_hash}, key=key, grant=grant, role=ROLE_SEARCH_BUDGET_KEEPER, action=action_reserve(expected), request_id=f"reserve:{candidate.candidate_ref}", now=now)
    completed, response = invoke(request, root=root, db_path=db_path, now=now)
    return expected, completed, response, (key, grant)


def evaluate(db_path, root, graph, p, history, candidate, reservation, policy, *, subject, now):
    key, grant = actor(root, subject, ROLE_SEARCH_EVALUATOR)
    _, underlying, expected = evaluate_reserved_candidate(candidate=candidate, reservation=reservation, base_graph=graph, samples=history, structural_policy=p, search_policy=policy, evaluator_ref=subject, evaluated_at=now)
    request = wrap("evaluate_reserved_candidate", {"candidate_hash": candidate.candidate_hash}, key=key, grant=grant, role=ROLE_SEARCH_EVALUATOR, action=action_evaluate(expected), request_id=f"evaluate:{candidate.candidate_ref}", now=now)
    completed, response = invoke(request, root=root, db_path=db_path, now=now)
    return underlying, expected, completed, response


def test_runtime_full_search_budgeted_flow_applies_only_after_reserved_exposure(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    graph, p, history, candidates = initialize_db(db_path)
    root = Ed25519PrivateKey.generate()
    policy = register_policy(db_path, root)
    reservation, completed, response, _ = reserve(db_path, root, candidates[0], policy, (), now=300)
    assert completed.returncode == 0, response
    underlying, evaluation, completed, response = evaluate(db_path, root, graph, p, history, candidates[0], reservation, policy, subject="evaluator", now=400)
    assert completed.returncode == 0, response
    assert response["evaluation"]["status"] == "SEARCH_CORRECTED_IMPROVED"
    selector_key, selector_grant = actor(root, "selector", ROLE_SEARCH_SELECTOR)
    selection = select_search_budget_candidate(selection_ref="selection:runtime", current_candidates=(candidates[0],), current_evaluations=(evaluation,), all_family_reservations=(reservation,), search_policy=policy, selector_ref="selector", selected_at=500)
    request = wrap("finalize_search_budget_selection", {"selection_ref": selection.selection_ref, "subject_identity_ref": IDENTITY, "pair_key": PAIR_KEY}, key=selector_key, grant=selector_grant, role=ROLE_SEARCH_SELECTOR, action=action_finalize_selection(selection), request_id="selection", now=500)
    completed, response = invoke(request, root=root, db_path=db_path, now=500)
    assert completed.returncode == 0, response
    reviewer_key, reviewer_grant = actor(root, "reviewer", ROLE_SEARCH_REVIEWER)
    review = review_search_budget_selection(selection=selection, selected_candidate=candidates[0], decision="APPROVE", rationale_ref="independent-review", reviewer_ref="reviewer", reviewed_at=600)
    request = wrap("record_search_budget_selection_review", {"selection_hash": selection.selection_hash, "decision": "APPROVE", "rationale_ref": "independent-review"}, key=reviewer_key, grant=reviewer_grant, role=ROLE_SEARCH_REVIEWER, action=action_review(review), request_id="review", now=600)
    completed, response = invoke(request, root=root, db_path=db_path, now=600)
    assert completed.returncode == 0, response
    applier_key, applier_grant = actor(root, "applier", ROLE_SEARCH_APPLIER)
    _, revision = apply_search_budgeted_selection(current_graph=graph, candidate=candidates[0], reservation=reservation, underlying_validation=underlying, evaluation=evaluation, selection=selection, review=review, applier_ref="applier", applied_at=700)
    request = wrap("apply_search_budgeted_selection", {"selection_hash": selection.selection_hash}, key=applier_key, grant=applier_grant, role=ROLE_SEARCH_APPLIER, action=action_apply(revision), request_id="apply", now=700)
    completed, response = invoke(request, root=root, db_path=db_path, now=700)
    assert completed.returncode == 0, response
    assert response["graph"]["generation"] == 1
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT reservation_json,underlying_validation_json,evaluation_json,selection_json,review_json FROM heldout_search_revision_history WHERE selection_hash=?", (selection.selection_hash,)).fetchone()
    conn.close()
    assert all(row)


def test_runtime_repeated_reservation_is_idempotent_and_budget_exhaustion_persists(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    _, _, _, candidates = initialize_db(db_path)
    root = Ed25519PrivateKey.generate()
    policy = register_policy(db_path, root, max_unique=1)
    first, completed, response, keeper = reserve(db_path, root, candidates[0], policy, (), subject="budget", now=300)
    assert completed.returncode == 0, response
    key, grant = keeper
    request = wrap("reserve_heldout_evaluation", {"candidate_hash": candidates[0].candidate_hash}, key=key, grant=grant, role=ROLE_SEARCH_BUDGET_KEEPER, action=action_reserve(first), request_id="repeat", now=301)
    completed, response = invoke(request, root=root, db_path=db_path, now=301)
    assert completed.returncode == 0, response
    assert response["reservation"]["reservation_hash"] == first.reservation_hash
    other_key, other_grant = actor(root, "budget", ROLE_SEARCH_BUDGET_KEEPER)
    proof = sign_authorized_action(other_grant, private_key=other_key, role=ROLE_SEARCH_BUDGET_KEEPER, scope=verification_scope(IDENTITY), action=action_reserve(first), signed_at=302)
    request = {"protocol": SEARCH_PROTOCOL, "request_id": "exhausted", "operation": "reserve_heldout_evaluation", "payload": {"candidate_hash": candidates[1].candidate_hash}, "grant": authority_grant_to_dict(other_grant), "proof": authority_proof_to_dict(proof)}
    completed, response = invoke(request, root=root, db_path=db_path, now=302)
    assert completed.returncode == 2
    assert "budget exhausted" in response["error"]


def test_runtime_rejects_candidate_already_exposed_outside_search_budget(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    graph, p, history, candidates = initialize_db(db_path)
    root = Ed25519PrivateKey.generate()
    policy = register_policy(db_path, root)
    cases, validation = validate_structural_candidate(candidate=candidates[0], base_graph=graph, samples=history, policy=p, validator_ref="legacy-validator", validated_at=275)
    conn = _connect(str(db_path))
    conn.execute("INSERT INTO structural_validation_receipt(validation_hash,candidate_hash,receipt_json,cases_json) VALUES(?,?,?,?)", (validation.validation_hash, candidates[0].candidate_hash, json.dumps(validation_to_dict(validation), sort_keys=True, separators=(",", ":")), json.dumps([heldout_case_to_dict(item) for item in cases], sort_keys=True, separators=(",", ":"))))
    conn.commit()
    conn.close()
    key, grant = actor(root, "budget", ROLE_SEARCH_BUDGET_KEEPER)
    fake = reserve_heldout_search(candidate=candidates[0], policy=policy, prior_reservations=(), budget_keeper_ref="budget", reserved_at=300)
    request = wrap("reserve_heldout_evaluation", {"candidate_hash": candidates[0].candidate_hash}, key=key, grant=grant, role=ROLE_SEARCH_BUDGET_KEEPER, action=action_reserve(fake), request_id="preexposed", now=300)
    completed, response = invoke(request, root=root, db_path=db_path, now=300)
    assert completed.returncode == 2
    assert "already exposed" in response["error"]


def test_runtime_new_search_exposure_after_selection_makes_old_selection_stale(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    graph, p, history, candidates = initialize_db(db_path)
    root = Ed25519PrivateKey.generate()
    policy = register_policy(db_path, root, max_unique=3, penalty=1_000)
    r1, completed, response, _ = reserve(db_path, root, candidates[0], policy, (), subject="budget1", now=300)
    assert completed.returncode == 0, response
    u1, e1, completed, response = evaluate(db_path, root, graph, p, history, candidates[0], r1, policy, subject="eval1", now=400)
    assert completed.returncode == 0, response
    selector_key, selector_grant = actor(root, "selector", ROLE_SEARCH_SELECTOR)
    selection = select_search_budget_candidate(selection_ref="selection:stale", current_candidates=(candidates[0],), current_evaluations=(e1,), all_family_reservations=(r1,), search_policy=policy, selector_ref="selector", selected_at=500)
    request = wrap("finalize_search_budget_selection", {"selection_ref": selection.selection_ref, "subject_identity_ref": IDENTITY, "pair_key": PAIR_KEY}, key=selector_key, grant=selector_grant, role=ROLE_SEARCH_SELECTOR, action=action_finalize_selection(selection), request_id="selection", now=500)
    completed, response = invoke(request, root=root, db_path=db_path, now=500)
    assert completed.returncode == 0, response
    reviewer_key, reviewer_grant = actor(root, "reviewer", ROLE_SEARCH_REVIEWER)
    review = review_search_budget_selection(selection=selection, selected_candidate=candidates[0], decision="APPROVE", rationale_ref="review", reviewer_ref="reviewer", reviewed_at=550)
    request = wrap("record_search_budget_selection_review", {"selection_hash": selection.selection_hash, "decision": "APPROVE", "rationale_ref": "review"}, key=reviewer_key, grant=reviewer_grant, role=ROLE_SEARCH_REVIEWER, action=action_review(review), request_id="review", now=550)
    completed, response = invoke(request, root=root, db_path=db_path, now=550)
    assert completed.returncode == 0, response
    r2, completed, response, _ = reserve(db_path, root, candidates[1], policy, (r1,), subject="budget2", now=600)
    assert completed.returncode == 0, response
    _, e2, completed, response = evaluate(db_path, root, graph, p, history, candidates[1], r2, policy, subject="eval2", now=650)
    assert completed.returncode == 0, response
    applier_key, applier_grant = actor(root, "applier", ROLE_SEARCH_APPLIER)
    _, old_revision = apply_search_budgeted_selection(current_graph=graph, candidate=candidates[0], reservation=r1, underlying_validation=u1, evaluation=e1, selection=selection, review=review, applier_ref="applier", applied_at=700)
    request = wrap("apply_search_budgeted_selection", {"selection_hash": selection.selection_hash}, key=applier_key, grant=applier_grant, role=ROLE_SEARCH_APPLIER, action=action_apply(old_revision), request_id="apply-stale", now=700)
    completed, response = invoke(request, root=root, db_path=db_path, now=700)
    assert completed.returncode == 2
    assert "stale search-budget selection" in response["error"]
