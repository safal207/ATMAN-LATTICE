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
from model.runtime_dependency_graph import graph_from_dict, graph_to_dict
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_structural_validation import (
    STRUCTURE_PROTOCOL,
    ROLE_HELDOUT_VALIDATOR,
    ROLE_STRUCTURAL_CANDIDATE_PROPOSER,
    ROLE_STRUCTURAL_SELECTION_REVIEWER,
    ROLE_STRUCTURAL_SELECTOR,
    ROLE_VALIDATED_STRUCTURAL_APPLIER,
    ROLE_VALIDATION_POLICY_KEEPER,
    _connect,
    action_apply_validated_selection,
    action_finalize_selection,
    action_record_selection_review,
    action_record_validation,
    action_register_candidate,
    action_register_policy,
)
from model.runtime_verification import verification_scope
from model.structural_validation import (
    apply_validated_structural_selection,
    make_structural_validation_candidate,
    make_structural_validation_policy,
    partition_dependency_samples,
    review_structural_selection,
    select_structural_candidate,
    validate_structural_candidate,
)

IDENTITY = "agent:structure-runtime"
PAIR_KEY = sha256(b"pair:structure-runtime").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def sample(index: int, *, left: bool, right: bool) -> DependencyPairSample:
    fields = {
        "pair_key": PAIR_KEY,
        "resolution_hash": h(f"structure-resolution:{index}:{left}:{right}"),
        "dependency_group_ref": "group:structure-runtime",
        "left_model_ref": "signal:L",
        "right_model_ref": "signal:R",
        "declared_mode": "INDEPENDENT",
        "resolved_hypothesis_ref": "H:A",
        "left_evidence_hash": h(f"structure-left:{index}:{left}:{right}"),
        "right_evidence_hash": h(f"structure-right:{index}:{left}:{right}"),
        "left_positive": left,
        "right_positive": right,
        "sampled_at": 100 + index,
    }
    provisional = DependencyPairSample(**fields, sample_hash="0" * 64)
    result = DependencyPairSample(**fields, sample_hash=calibration_digest(provisional.material()))
    result.validate()
    return result


def split_policy(now=200, *, edge_penalty_ppm=10_000):
    return make_structural_validation_policy(
        policy_ref="policy:structure-runtime",
        subject_identity_ref=IDENTITY,
        evaluation_modulus=3,
        min_selection_samples=6,
        min_evaluation_samples=2,
        dependency_threshold_bps=1000,
        edge_penalty_ppm=edge_penalty_ppm,
        registered_at=now,
    )


def collect_partitioned(*, desired: str, count: int, start: int, p):
    result = []
    index = start
    while len(result) < count and index < start + 5000:
        left, right = ((True, True) if len(result) % 2 == 0 else (False, False))
        item = sample(index, left=left, right=right)
        selection, evaluation, _ = partition_dependency_samples((item,), p)
        if (desired == "selection" and selection) or (desired == "evaluation" and evaluation):
            result.append(item)
        index += 1
    assert len(result) == count
    return result, index


def pair_history():
    p = split_policy()
    selection, next_index = collect_partitioned(desired="selection", count=8, start=0, p=p)
    evaluation, _ = collect_partitioned(desired="evaluation", count=4, start=next_index + 100, p=p)
    return tuple(selection + evaluation)


def initial_graph():
    return make_dependency_graph(
        "graph:structure-runtime",
        subject_identity_ref=IDENTITY,
        generation=0,
        edges=(),
        evidence_state_hash=h("structure-runtime:graph:0"),
    )


def initialize_db(db_path):
    bootstrap = sqlite3.connect(db_path)
    bootstrap.execute(
        "CREATE TABLE verification_work (work_hash TEXT PRIMARY KEY, work_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, target_gate_hash TEXT NOT NULL, work_json TEXT NOT NULL, status TEXT NOT NULL, completion_json TEXT)"
    )
    bootstrap.commit()
    bootstrap.close()
    conn = _connect(str(db_path))
    graph = initial_graph()
    conn.execute(
        "INSERT INTO dependency_graph_current(subject_identity_ref,graph_json) VALUES(?,?)",
        (IDENTITY, json.dumps(graph_to_dict(graph), sort_keys=True, separators=(",", ":"))),
    )
    history = pair_history()
    for item in history:
        conn.execute(
            "INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)",
            (item.sample_hash, item.pair_key, item.resolution_hash, json.dumps(pair_to_dict(item), sort_keys=True, separators=(",", ":"))),
        )
    conn.commit()
    conn.close()
    return graph, history


def grant_for(root, actor, *, subject, roles):
    return issue_authority_grant(
        grant_id=f"grant:{subject}",
        subject_ref=subject,
        subject_key_id=f"key:{subject}",
        subject_public_key=actor.public_key(),
        roles=tuple(roles),
        scopes=(verification_scope(IDENTITY),),
        policy_generation=15,
        valid_from=100,
        valid_until=2000,
        issuer_ref="root",
        issuer_key_id="root-key",
        issuer_private_key=root,
    )


def invoke(request, *, root, db_path, now):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "15"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    completed = subprocess.run(
        [sys.executable, "-m", "model.structure_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def actor(root, subject, role):
    key = Ed25519PrivateKey.generate()
    return key, grant_for(root, key, subject=subject, roles=(role,))


def policy_request(p, *, key, grant, now=200):
    proof = sign_authorized_action(grant, private_key=key, role=ROLE_VALIDATION_POLICY_KEEPER, scope=verification_scope(IDENTITY), action=action_register_policy(p), signed_at=now)
    return {
        "protocol": STRUCTURE_PROTOCOL,
        "request_id": "policy",
        "operation": "register_structural_validation_policy",
        "payload": {
            "policy_ref": p.policy_ref,
            "subject_identity_ref": IDENTITY,
            "evaluation_modulus": p.evaluation_modulus,
            "min_selection_samples": p.min_selection_samples,
            "min_evaluation_samples": p.min_evaluation_samples,
            "dependency_threshold_bps": p.dependency_threshold_bps,
            "edge_penalty_ppm": p.edge_penalty_ppm,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def candidate_request(graph, history, p, *, direction, candidate_ref, key, grant, now=300):
    candidate = make_structural_validation_candidate(
        candidate_ref=candidate_ref,
        base_graph=graph,
        samples=history,
        policy=p,
        direction=direction,
        reason_ref="heldout-graph-selection",
        proposer_ref=grant.subject_ref,
        created_at=now,
    )
    proof = sign_authorized_action(grant, private_key=key, role=ROLE_STRUCTURAL_CANDIDATE_PROPOSER, scope=verification_scope(IDENTITY), action=action_register_candidate(candidate), signed_at=now)
    request = {
        "protocol": STRUCTURE_PROTOCOL,
        "request_id": candidate_ref,
        "operation": "register_structural_candidate",
        "payload": {
            "candidate_ref": candidate_ref,
            "subject_identity_ref": IDENTITY,
            "pair_key": PAIR_KEY,
            "direction": direction,
            "reason_ref": "heldout-graph-selection",
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return candidate, request


def validation_request(graph, history, p, candidate, *, key, grant, now=400):
    _, validation = validate_structural_candidate(
        candidate=candidate,
        base_graph=graph,
        samples=history,
        policy=p,
        validator_ref=grant.subject_ref,
        validated_at=now,
    )
    proof = sign_authorized_action(grant, private_key=key, role=ROLE_HELDOUT_VALIDATOR, scope=verification_scope(IDENTITY), action=action_record_validation(validation), signed_at=now)
    request = {
        "protocol": STRUCTURE_PROTOCOL,
        "request_id": "validate:" + candidate.candidate_ref,
        "operation": "record_heldout_validation",
        "payload": {"candidate_hash": candidate.candidate_hash},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return validation, request


def selection_request(candidates, validations, *, key, grant, now=500, selection_ref="selection:runtime"):
    selection = select_structural_candidate(
        selection_ref=selection_ref,
        candidates=tuple(candidates),
        validations=tuple(validations),
        selector_ref=grant.subject_ref,
        selected_at=now,
    )
    proof = sign_authorized_action(grant, private_key=key, role=ROLE_STRUCTURAL_SELECTOR, scope=verification_scope(IDENTITY), action=action_finalize_selection(selection), signed_at=now)
    request = {
        "protocol": STRUCTURE_PROTOCOL,
        "request_id": selection_ref,
        "operation": "finalize_structural_selection",
        "payload": {"selection_ref": selection_ref, "subject_identity_ref": IDENTITY, "pair_key": PAIR_KEY},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return selection, request


def review_request(selection, candidate, *, key, grant, now=600):
    review = review_structural_selection(
        selection=selection,
        selected_candidate=candidate,
        decision="APPROVE",
        rationale_ref="independent-heldout-review",
        reviewer_ref=grant.subject_ref,
        reviewed_at=now,
    )
    proof = sign_authorized_action(grant, private_key=key, role=ROLE_STRUCTURAL_SELECTION_REVIEWER, scope=verification_scope(IDENTITY), action=action_record_selection_review(review), signed_at=now)
    request = {
        "protocol": STRUCTURE_PROTOCOL,
        "request_id": "review",
        "operation": "record_structural_selection_review",
        "payload": {"selection_hash": selection.selection_hash, "decision": "APPROVE", "rationale_ref": "independent-heldout-review"},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return review, request


def apply_request(graph, candidate, validation, selection, review, *, key, grant, now=700):
    _, revision = apply_validated_structural_selection(
        current_graph=graph,
        candidate=candidate,
        validation=validation,
        selection=selection,
        review=review,
        applier_ref=grant.subject_ref,
        applied_at=now,
    )
    proof = sign_authorized_action(grant, private_key=key, role=ROLE_VALIDATED_STRUCTURAL_APPLIER, scope=verification_scope(IDENTITY), action=action_apply_validated_selection(revision), signed_at=now)
    request = {
        "protocol": STRUCTURE_PROTOCOL,
        "request_id": "apply",
        "operation": "apply_validated_structural_selection",
        "payload": {"selection_hash": selection.selection_hash},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return revision, request


def setup_to_selection(db_path, *, two_candidates=False):
    graph, history = initialize_db(db_path)
    root = Ed25519PrivateKey.generate()
    policy_key, policy_grant = actor(root, "policy", ROLE_VALIDATION_POLICY_KEEPER)
    p = split_policy(now=200)
    completed, response = invoke(policy_request(p, key=policy_key, grant=policy_grant), root=root, db_path=db_path, now=200)
    assert completed.returncode == 0, response

    candidates = []
    validations = []
    directions = ("LEFT_TO_RIGHT", "RIGHT_TO_LEFT") if two_candidates else ("LEFT_TO_RIGHT",)
    for offset, direction in enumerate(directions):
        proposer_key, proposer_grant = actor(root, f"proposer:{direction}", ROLE_STRUCTURAL_CANDIDATE_PROPOSER)
        candidate, request = candidate_request(graph, history, p, direction=direction, candidate_ref=f"candidate:{direction}", key=proposer_key, grant=proposer_grant, now=300 + offset)
        completed, response = invoke(request, root=root, db_path=db_path, now=300 + offset)
        assert completed.returncode == 0, response
        validator_key, validator_grant = actor(root, f"validator:{direction}", ROLE_HELDOUT_VALIDATOR)
        validation, request = validation_request(graph, history, p, candidate, key=validator_key, grant=validator_grant, now=400 + offset)
        completed, response = invoke(request, root=root, db_path=db_path, now=400 + offset)
        assert completed.returncode == 0, response
        candidates.append(candidate)
        validations.append(validation)

    selector_key, selector_grant = actor(root, "selector", ROLE_STRUCTURAL_SELECTOR)
    selection, request = selection_request(candidates, validations, key=selector_key, grant=selector_grant, now=500)
    completed, response = invoke(request, root=root, db_path=db_path, now=500)
    assert completed.returncode == 0, response
    assert selection.status == "SELECTED"
    selected = next(item for item in candidates if item.candidate_hash == selection.selected_candidate_hash)
    selected_validation = next(item for item in validations if item.candidate_hash == selected.candidate_hash)
    return root, graph, history, p, candidates, validations, selection, selected, selected_validation


def test_runtime_v115_full_path_preserves_old_and_new_graph_and_validation_history(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    root, graph, _, _, _, _, selection, selected, selected_validation = setup_to_selection(db_path, two_candidates=True)
    reviewer_key, reviewer_grant = actor(root, "reviewer", ROLE_STRUCTURAL_SELECTION_REVIEWER)
    review, request = review_request(selection, selected, key=reviewer_key, grant=reviewer_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=600)
    assert completed.returncode == 0, response
    applier_key, applier_grant = actor(root, "applier", ROLE_VALIDATED_STRUCTURAL_APPLIER)
    revision, request = apply_request(graph, selected, selected_validation, selection, review, key=applier_key, grant=applier_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=700)
    assert completed.returncode == 0, response
    assert response["revision"]["revision_hash"] == revision.revision_hash
    assert response["graph"]["generation"] == 1
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT base_graph_json,new_graph_json,candidate_json,validation_json,selection_json,review_json FROM structural_validation_history WHERE selection_hash=?", (selection.selection_hash,)).fetchone()
    conn.close()
    old_graph = graph_from_dict(json.loads(row[0]))
    new_graph = graph_from_dict(json.loads(row[1]))
    assert old_graph.graph_hash == graph.graph_hash and old_graph.edges == ()
    assert new_graph.graph_hash == response["graph"]["graph_hash"] and len(new_graph.edges) == 1
    assert json.loads(row[2])["candidate_hash"] == selected.candidate_hash
    assert json.loads(row[3])["validation_hash"] == selected_validation.validation_hash
    assert json.loads(row[4])["selection_hash"] == selection.selection_hash
    assert json.loads(row[5])["review_hash"] == review.review_hash


def test_runtime_apply_rejects_new_dependency_history_after_selection(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    root, graph, _, _, _, _, selection, selected, selected_validation = setup_to_selection(db_path)
    reviewer_key, reviewer_grant = actor(root, "reviewer", ROLE_STRUCTURAL_SELECTION_REVIEWER)
    review, request = review_request(selection, selected, key=reviewer_key, grant=reviewer_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=600)
    assert completed.returncode == 0, response
    extra = sample(9999, left=True, right=False)
    conn = _connect(str(db_path))
    conn.execute("INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)", (extra.sample_hash, extra.pair_key, extra.resolution_hash, json.dumps(pair_to_dict(extra), sort_keys=True, separators=(",", ":"))))
    conn.commit()
    conn.close()
    applier_key, applier_grant = actor(root, "applier", ROLE_VALIDATED_STRUCTURAL_APPLIER)
    _, request = apply_request(graph, selected, selected_validation, selection, review, key=applier_key, grant=applier_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=700)
    assert completed.returncode == 2
    assert "dependency history changed" in response["error"]


def test_runtime_new_validated_competing_candidate_makes_old_selection_stale(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    root, graph, history, p, candidates, validations, selection, selected, selected_validation = setup_to_selection(db_path, two_candidates=False)
    reviewer_key, reviewer_grant = actor(root, "reviewer", ROLE_STRUCTURAL_SELECTION_REVIEWER)
    review, request = review_request(selection, selected, key=reviewer_key, grant=reviewer_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=600)
    assert completed.returncode == 0, response

    proposer_key, proposer_grant = actor(root, "late-proposer", ROLE_STRUCTURAL_CANDIDATE_PROPOSER)
    late, request = candidate_request(graph, history, p, direction="RIGHT_TO_LEFT", candidate_ref="candidate:late", key=proposer_key, grant=proposer_grant, now=620)
    completed, response = invoke(request, root=root, db_path=db_path, now=620)
    assert completed.returncode == 0, response
    validator_key, validator_grant = actor(root, "late-validator", ROLE_HELDOUT_VALIDATOR)
    _, request = validation_request(graph, history, p, late, key=validator_key, grant=validator_grant, now=630)
    completed, response = invoke(request, root=root, db_path=db_path, now=630)
    assert completed.returncode == 0, response

    applier_key, applier_grant = actor(root, "applier", ROLE_VALIDATED_STRUCTURAL_APPLIER)
    _, request = apply_request(graph, selected, selected_validation, selection, review, key=applier_key, grant=applier_grant, now=700)
    completed, response = invoke(request, root=root, db_path=db_path, now=700)
    assert completed.returncode == 2
    assert "candidate set changed" in response["error"]


def test_runtime_validation_policy_cannot_be_silently_rewritten(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    initialize_db(db_path)
    root = Ed25519PrivateKey.generate()
    key, grant = actor(root, "policy", ROLE_VALIDATION_POLICY_KEEPER)
    first = split_policy(now=200, edge_penalty_ppm=10_000)
    completed, response = invoke(policy_request(first, key=key, grant=grant), root=root, db_path=db_path, now=200)
    assert completed.returncode == 0, response
    second = make_structural_validation_policy(
        policy_ref="policy:structure-runtime",
        subject_identity_ref=IDENTITY,
        evaluation_modulus=3,
        min_selection_samples=6,
        min_evaluation_samples=2,
        dependency_threshold_bps=1000,
        edge_penalty_ppm=999_999,
        registered_at=201,
    )
    request = policy_request(second, key=key, grant=grant, now=201)
    completed, response = invoke(request, root=root, db_path=db_path, now=201)
    assert completed.returncode == 2
    assert "immutable" in response["error"]
