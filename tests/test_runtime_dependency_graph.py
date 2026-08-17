import json
import os
import sqlite3
import subprocess
import sys
from hashlib import sha256

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
from model.calibration import DependencyPairSample, _digest as calibration_digest, pair_to_dict, summarize_dependency_samples
from model.dependency_graph_revision import (
    apply_structural_graph_revision,
    make_dependency_graph,
    make_structural_graph_revision_proposal,
    replay_structural_graph_revision,
    review_structural_graph_revision,
)
from model.runtime_dependency_graph import (
    GRAPH_PROTOCOL,
    ROLE_GRAPH_BOOTSTRAP_KEEPER,
    ROLE_GRAPH_REPLAY_KEEPER,
    ROLE_GRAPH_REVISION_APPLIER,
    ROLE_GRAPH_REVISION_PROPOSER,
    ROLE_GRAPH_REVISION_REVIEWER,
    _connect,
    action_apply_graph_revision,
    action_record_graph_revision_replay,
    action_record_graph_revision_review,
    action_register_graph,
    action_register_graph_revision_proposal,
    graph_from_dict,
)
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_verification import verification_scope

IDENTITY = "agent:graph-runtime"
PAIR_KEY = sha256(b"pair:graph-runtime").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def sample(index: int, *, left: bool, right: bool) -> DependencyPairSample:
    fields = {
        "pair_key": PAIR_KEY,
        "resolution_hash": h(f"graph-resolution:{index}"),
        "dependency_group_ref": "group:graph-runtime",
        "left_model_ref": "signal:L",
        "right_model_ref": "signal:R",
        "declared_mode": "INDEPENDENT",
        "resolved_hypothesis_ref": "H:A",
        "left_evidence_hash": h(f"graph-left:{index}"),
        "right_evidence_hash": h(f"graph-right:{index}"),
        "left_positive": left,
        "right_positive": right,
        "sampled_at": 150 + index,
    }
    provisional = DependencyPairSample(**fields, sample_hash="0" * 64)
    result = DependencyPairSample(**fields, sample_hash=calibration_digest(provisional.material()))
    result.validate()
    return result


def pair_history():
    return tuple(sample(i, left=left, right=right) for i, (left, right) in enumerate([(True, True)] * 5 + [(False, False)] * 5))


def initialize_db(db_path):
    bootstrap = sqlite3.connect(db_path)
    bootstrap.execute(
        "CREATE TABLE verification_work (work_hash TEXT PRIMARY KEY, work_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, target_gate_hash TEXT NOT NULL, work_json TEXT NOT NULL, status TEXT NOT NULL, completion_json TEXT)"
    )
    bootstrap.commit()
    bootstrap.close()
    conn = _connect(str(db_path))
    history = pair_history()
    for item in history:
        conn.execute(
            "INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)",
            (item.sample_hash, item.pair_key, item.resolution_hash, json.dumps(pair_to_dict(item), sort_keys=True, separators=(",", ":"))),
        )
    conn.commit()
    conn.close()
    return history


def grant_for(root, actor, *, subject, roles):
    return issue_authority_grant(
        grant_id=f"grant:{subject}",
        subject_ref=subject,
        subject_key_id=f"key:{subject}",
        subject_public_key=actor.public_key(),
        roles=tuple(roles),
        scopes=(verification_scope(IDENTITY),),
        policy_generation=14,
        valid_from=100,
        valid_until=1000,
        issuer_ref="root",
        issuer_key_id="root-key",
        issuer_private_key=root,
    )


def invoke(request, *, root, db_path, now):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "14"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    completed = subprocess.run(
        [sys.executable, "-m", "model.graph_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def bootstrap_request(*, actor, grant, now=200):
    graph = make_dependency_graph(
        "graph:runtime",
        subject_identity_ref=IDENTITY,
        generation=0,
        edges=(),
        evidence_state_hash=h("graph-runtime:bootstrap"),
    )
    proof = sign_authorized_action(grant, private_key=actor, role=ROLE_GRAPH_BOOTSTRAP_KEEPER, scope=verification_scope(IDENTITY), action=action_register_graph(graph), signed_at=now)
    request = {
        "protocol": GRAPH_PROTOCOL,
        "request_id": "bootstrap",
        "operation": "register_dependency_graph",
        "payload": {"graph_ref": graph.graph_ref, "subject_identity_ref": IDENTITY, "edges": [], "evidence_state_hash": graph.evidence_state_hash},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return graph, request


def proposal_request(graph, history, *, actor, grant, direction="LEFT_TO_RIGHT", proposal_ref="proposal:runtime", now=300):
    snapshot = summarize_dependency_samples(history, min_samples=6, dependency_threshold_bps=1000, measured_at=now)
    proposal = make_structural_graph_revision_proposal(
        proposal_ref=proposal_ref,
        base_graph=graph,
        calibration_snapshot=snapshot,
        samples=history,
        direction=direction,
        reason_ref="dependency-challenge",
        proposer_ref=grant.subject_ref,
        proposed_at=now,
    )
    proof = sign_authorized_action(grant, private_key=actor, role=ROLE_GRAPH_REVISION_PROPOSER, scope=verification_scope(IDENTITY), action=action_register_graph_revision_proposal(proposal), signed_at=now)
    request = {
        "protocol": GRAPH_PROTOCOL,
        "request_id": proposal_ref,
        "operation": "register_graph_revision_proposal",
        "payload": {
            "proposal_ref": proposal_ref,
            "subject_identity_ref": IDENTITY,
            "pair_key": PAIR_KEY,
            "direction": direction,
            "reason_ref": "dependency-challenge",
            "min_samples": 6,
            "dependency_threshold_bps": 1000,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return proposal, request


def replay_request(graph, proposal, history, *, actor, grant, now=400):
    _, replay = replay_structural_graph_revision(proposal, graph, history, min_cases=6, replayed_at=now)
    proof = sign_authorized_action(grant, private_key=actor, role=ROLE_GRAPH_REPLAY_KEEPER, scope=verification_scope(IDENTITY), action=action_record_graph_revision_replay(replay), signed_at=now)
    request = {
        "protocol": GRAPH_PROTOCOL,
        "request_id": "replay:" + proposal.proposal_ref,
        "operation": "record_graph_revision_replay",
        "payload": {"proposal_hash": proposal.proposal_hash, "min_cases": 6},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return replay, request


def review_request(proposal, replay, *, actor, grant, now=500):
    review = review_structural_graph_revision(proposal, replay, decision="APPROVE", rationale_ref="independent-review", reviewer_ref=grant.subject_ref, reviewed_at=now)
    proof = sign_authorized_action(grant, private_key=actor, role=ROLE_GRAPH_REVISION_REVIEWER, scope=verification_scope(IDENTITY), action=action_record_graph_revision_review(review), signed_at=now)
    request = {
        "protocol": GRAPH_PROTOCOL,
        "request_id": "review:" + proposal.proposal_ref,
        "operation": "record_graph_revision_review",
        "payload": {"proposal_hash": proposal.proposal_hash, "decision": "APPROVE", "rationale_ref": "independent-review"},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return review, request


def apply_request(graph, proposal, replay, review, *, actor, grant, now=600):
    _, revision = apply_structural_graph_revision(current_graph=graph, proposal=proposal, replay=replay, review=review, applier_ref=grant.subject_ref, applied_at=now)
    proof = sign_authorized_action(grant, private_key=actor, role=ROLE_GRAPH_REVISION_APPLIER, scope=verification_scope(IDENTITY), action=action_apply_graph_revision(revision), signed_at=now)
    request = {
        "protocol": GRAPH_PROTOCOL,
        "request_id": "apply:" + proposal.proposal_ref,
        "operation": "apply_graph_revision",
        "payload": {"proposal_hash": proposal.proposal_hash},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return revision, request


def actors():
    root = Ed25519PrivateKey.generate()
    result = []
    for subject, role in (
        ("bootstrap", ROLE_GRAPH_BOOTSTRAP_KEEPER),
        ("proposer", ROLE_GRAPH_REVISION_PROPOSER),
        ("replay", ROLE_GRAPH_REPLAY_KEEPER),
        ("reviewer", ROLE_GRAPH_REVISION_REVIEWER),
        ("applier", ROLE_GRAPH_REVISION_APPLIER),
    ):
        key = Ed25519PrivateKey.generate()
        result.append((key, grant_for(root, key, subject=subject, roles=(role,))))
    return root, *result


def run_to_review(db_path, history):
    root, bootstrapper, proposer_actor, replay_actor, reviewer_actor, applier_actor = actors()
    key, grant = bootstrapper
    graph, request = bootstrap_request(actor=key, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=200)
    assert completed.returncode == 0, response
    key, grant = proposer_actor
    proposal, request = proposal_request(graph, history, actor=key, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=300)
    assert completed.returncode == 0, response
    key, grant = replay_actor
    replay, request = replay_request(graph, proposal, history, actor=key, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=400)
    assert completed.returncode == 0, response
    key, grant = reviewer_actor
    review, request = review_request(proposal, replay, actor=key, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=500)
    assert completed.returncode == 0, response
    return root, graph, proposal, replay, review, applier_actor


def test_runtime_structural_revision_preserves_old_and_new_graphs(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    history = initialize_db(db_path)
    root, graph, proposal, replay, review, applier_actor = run_to_review(db_path, history)
    key, grant = applier_actor
    revision, request = apply_request(graph, proposal, replay, review, actor=key, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=600)
    assert completed.returncode == 0, response
    assert response["revision"]["revision_hash"] == revision.revision_hash
    assert response["graph"]["generation"] == 1
    assert response["graph"]["edges"][0]["relation"] == "STATISTICAL_CONDITIONING"
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT base_graph_json,new_graph_json FROM dependency_graph_revision_history WHERE proposal_hash=?", (proposal.proposal_hash,)).fetchone()
    conn.close()
    old_graph = graph_from_dict(json.loads(row[0]))
    new_graph = graph_from_dict(json.loads(row[1]))
    assert old_graph.graph_hash == graph.graph_hash and old_graph.edges == ()
    assert new_graph.graph_hash == response["graph"]["graph_hash"] and len(new_graph.edges) == 1


def test_runtime_apply_rejects_stale_structural_replay_after_new_pair_sample(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    history = initialize_db(db_path)
    root, graph, proposal, replay, review, applier_actor = run_to_review(db_path, history)
    extra = sample(99, left=True, right=False)
    conn = _connect(str(db_path))
    conn.execute("INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)", (extra.sample_hash, extra.pair_key, extra.resolution_hash, json.dumps(pair_to_dict(extra), sort_keys=True, separators=(",", ":"))))
    conn.commit()
    conn.close()
    key, grant = applier_actor
    _, request = apply_request(graph, proposal, replay, review, actor=key, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=600)
    assert completed.returncode == 2
    assert "stale structural replay" in response["error"]


def test_runtime_reviewer_cannot_be_same_actor_as_proposer(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    history = initialize_db(db_path)
    root = Ed25519PrivateKey.generate()
    bootstrap_key = Ed25519PrivateKey.generate()
    bootstrap_grant = grant_for(root, bootstrap_key, subject="bootstrap", roles=(ROLE_GRAPH_BOOTSTRAP_KEEPER,))
    graph, request = bootstrap_request(actor=bootstrap_key, grant=bootstrap_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=200)
    assert completed.returncode == 0, response
    same_key = Ed25519PrivateKey.generate()
    same_grant = grant_for(root, same_key, subject="same", roles=(ROLE_GRAPH_REVISION_PROPOSER, ROLE_GRAPH_REVISION_REVIEWER))
    proposal, request = proposal_request(graph, history, actor=same_key, grant=same_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=300)
    assert completed.returncode == 0, response
    replay_key = Ed25519PrivateKey.generate()
    replay_grant = grant_for(root, replay_key, subject="replay", roles=(ROLE_GRAPH_REPLAY_KEEPER,))
    replay, request = replay_request(graph, proposal, history, actor=replay_key, grant=replay_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=400)
    assert completed.returncode == 0, response
    try:
        review_request(proposal, replay, actor=same_key, grant=same_grant)
    except ValueError as exc:
        assert "independent" in str(exc)
    else:
        raise AssertionError("structural proposer unexpectedly reviewed own proposal")


def test_runtime_competing_orientation_is_stale_after_first_graph_revision(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    history = initialize_db(db_path)
    root, bootstrapper, proposer_actor, replay_actor, reviewer_actor, applier_actor = actors()
    key, grant = bootstrapper
    graph, request = bootstrap_request(actor=key, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=200)
    assert completed.returncode == 0, response
    chains = []
    for direction, ref in (("LEFT_TO_RIGHT", "proposal:ltr"), ("RIGHT_TO_LEFT", "proposal:rtl")):
        key, grant = proposer_actor
        proposal, request = proposal_request(graph, history, actor=key, grant=grant, direction=direction, proposal_ref=ref, now=300)
        completed, response = invoke(request, root=root, db_path=db_path, now=300)
        assert completed.returncode == 0, response
        key, grant = replay_actor
        replay, request = replay_request(graph, proposal, history, actor=key, grant=grant, now=400)
        completed, response = invoke(request, root=root, db_path=db_path, now=400)
        assert completed.returncode == 0, response
        key, grant = reviewer_actor
        review, request = review_request(proposal, replay, actor=key, grant=grant, now=500)
        completed, response = invoke(request, root=root, db_path=db_path, now=500)
        assert completed.returncode == 0, response
        chains.append((proposal, replay, review))
    key, grant = applier_actor
    _, request = apply_request(graph, *chains[0], actor=key, grant=grant, now=600)
    completed, response = invoke(request, root=root, db_path=db_path, now=600)
    assert completed.returncode == 0, response
    _, request = apply_request(graph, *chains[1], actor=key, grant=grant, now=601)
    completed, response = invoke(request, root=root, db_path=db_path, now=601)
    assert completed.returncode == 2
    assert "base graph" in response["error"] or "stale" in response["error"]
