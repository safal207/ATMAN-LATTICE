import json
import os
import sqlite3
import subprocess
import sys
from hashlib import sha256

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
from model.calibration import LikelihoodCalibrationReceipt, _digest as calibration_digest, summarize_calibration_family
from model.model_revision import apply_revision, make_model_revision_proposal, replay_revision, review_revision
from model.multihypothesis import make_hypothesis_distribution, make_multi_likelihood_model
from model.runtime_calibration import likelihood_to_dict
from model.runtime_multihypothesis import distribution_to_dict, model_from_dict, model_to_dict
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_revision import (
    REVISION_PROTOCOL,
    ROLE_REVISION_APPLIER,
    ROLE_REVISION_PROPOSER,
    ROLE_REVISION_REPLAY_KEEPER,
    ROLE_REVISION_REVIEWER,
    _connect,
    action_apply_model_revision,
    action_record_revision_replay,
    action_record_revision_review,
    action_register_revision_proposal,
)
from model.runtime_verification import verification_scope

IDENTITY = "agent:revision-runtime"
FAMILY = "family:revision-runtime"
MODEL_REF = "model:revision-runtime"
CANDIDATE_HASH = sha256(b"candidate:revision-runtime").hexdigest()


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def grant_for(root, actor, *, subject, roles):
    return issue_authority_grant(
        grant_id=f"grant:{subject}",
        subject_ref=subject,
        subject_key_id=f"key:{subject}",
        subject_public_key=actor.public_key(),
        roles=tuple(roles),
        scopes=(verification_scope(IDENTITY),),
        policy_generation=12,
        valid_from=100,
        valid_until=1000,
        issuer_ref="root",
        issuer_key_id="root-key",
        issuer_private_key=root,
    )


def invoke(request, *, root, db_path, now):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "12"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    completed = subprocess.run(
        [sys.executable, "-m", "model.revision_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def calibration(index: int, *, outcome: str):
    predicted = 9000
    observed_positive = outcome == "POSITIVE"
    old_brier = (predicted - (10000 if observed_positive else 0)) ** 2 // 100
    fields = {
        "target_hash": h(f"runtime-target:{index}"),
        "evidence_hash": h(f"runtime-evidence:{index}"),
        "resolution_hash": h(f"runtime-resolution:{index}"),
        "calibration_family_ref": FAMILY,
        "likelihood_model_hash": h(f"runtime-historical-model:{index}"),
        "likelihood_model_ref": MODEL_REF,
        "resolved_hypothesis_ref": "H:A",
        "predicted_positive_bps": predicted,
        "observed_outcome": outcome,
        "scored": True,
        "brier_score_ppm": old_brier,
        "dependency_mode": "INDEPENDENT",
        "calibrated_at": 200 + index,
    }
    provisional = LikelihoodCalibrationReceipt(**fields, calibration_hash="0" * 64)
    result = LikelihoodCalibrationReceipt(**fields, calibration_hash=calibration_digest(provisional.material()))
    result.validate()
    return result


def initialize_db(db_path):
    dist = make_hypothesis_distribution(
        "dist:revision-runtime",
        subject_identity_ref=IDENTITY,
        probability_bps={"H:A": 5000, "H:B": 5000},
        evidence_state_hash=h("runtime:initial-evidence"),
        generation=2,
    )
    model = make_multi_likelihood_model(
        candidate_hash=CANDIDATE_HASH,
        distribution=dist,
        positive_likelihood_bps={"H:A": 9000, "H:B": 1000},
        model_ref=MODEL_REF,
        model_generation=5,
    )
    history = tuple(calibration(i, outcome="POSITIVE" if i % 2 == 0 else "NEGATIVE") for i in range(6))
    bootstrap = sqlite3.connect(db_path)
    bootstrap.execute(
        "CREATE TABLE verification_work (work_hash TEXT PRIMARY KEY, work_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, target_gate_hash TEXT NOT NULL, work_json TEXT NOT NULL, status TEXT NOT NULL, completion_json TEXT)"
    )
    bootstrap.commit()
    bootstrap.close()
    conn = _connect(str(db_path))
    conn.execute(
        "INSERT INTO multi_hypothesis_distribution(distribution_ref,distribution_json) VALUES(?,?)",
        (dist.distribution_ref, json.dumps(distribution_to_dict(dist), sort_keys=True, separators=(",", ":"))),
    )
    conn.execute("INSERT INTO multi_candidate_binding(candidate_hash,distribution_ref) VALUES(?,?)", (CANDIDATE_HASH, dist.distribution_ref))
    conn.execute(
        "INSERT INTO multi_likelihood_model(candidate_hash,model_json) VALUES(?,?)",
        (CANDIDATE_HASH, json.dumps(model_to_dict(model), sort_keys=True, separators=(",", ":"))),
    )
    for item in history:
        conn.execute(
            "INSERT INTO calibration_likelihood_history(calibration_hash,target_hash,evidence_hash,family_ref,model_ref,receipt_json) VALUES(?,?,?,?,?,?)",
            (item.calibration_hash, item.target_hash, item.evidence_hash, FAMILY, MODEL_REF, json.dumps(likelihood_to_dict(item), sort_keys=True, separators=(",", ":"))),
        )
    conn.commit()
    conn.close()
    return dist, model, history


def proposal_request(dist, model, history, *, actor, grant, now=300):
    snapshot = summarize_calibration_family((), history, calibration_family_ref=FAMILY, min_samples=5, marginal_gap_threshold_bps=1000, measured_at=now)
    proposal = make_model_revision_proposal(
        proposal_ref="proposal:runtime",
        distribution=dist,
        base_model=model,
        calibration_snapshot=snapshot,
        proposed_positive_likelihood_bps={"H:A": 5000, "H:B": 5000},
        reason_ref="reason:runtime-miscalibration",
        proposer_ref=grant.subject_ref,
        proposed_at=now,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_REVISION_PROPOSER,
        scope=verification_scope(IDENTITY),
        action=action_register_revision_proposal(proposal),
        signed_at=now,
    )
    request = {
        "protocol": REVISION_PROTOCOL,
        "request_id": "proposal",
        "operation": "register_revision_proposal",
        "payload": {
            "proposal_ref": proposal.proposal_ref,
            "candidate_hash": CANDIDATE_HASH,
            "calibration_family_ref": FAMILY,
            "min_samples": 5,
            "marginal_gap_threshold_bps": 1000,
            "proposed_positive_likelihood_bps": dict(proposal.proposed_positive_likelihood_bps),
            "reason_ref": proposal.reason_ref,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return proposal, request


def replay_request(proposal, history, *, actor, grant, now=400):
    _, replay = replay_revision(proposal, history, min_cases=5, replayed_at=now)
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_REVISION_REPLAY_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action_record_revision_replay(replay),
        signed_at=now,
    )
    request = {
        "protocol": REVISION_PROTOCOL,
        "request_id": "replay",
        "operation": "record_counterfactual_replay",
        "payload": {"proposal_hash": proposal.proposal_hash, "min_cases": 5},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return replay, request


def review_request(proposal, replay, *, actor, grant, now=500, decision="APPROVE"):
    review = review_revision(
        proposal,
        replay,
        decision=decision,
        rationale_ref="review:independent",
        reviewer_ref=grant.subject_ref,
        reviewed_at=now,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_REVISION_REVIEWER,
        scope=verification_scope(IDENTITY),
        action=action_record_revision_review(review),
        signed_at=now,
    )
    request = {
        "protocol": REVISION_PROTOCOL,
        "request_id": "review",
        "operation": "record_revision_review",
        "payload": {"proposal_hash": proposal.proposal_hash, "decision": decision, "rationale_ref": review.rationale_ref},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return review, request


def apply_request(dist, model, proposal, replay, review, *, actor, grant, now=600):
    _, revision = apply_revision(
        distribution=dist,
        current_model=model,
        proposal=proposal,
        replay=replay,
        review=review,
        applied_at=now,
        applier_ref=grant.subject_ref,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_REVISION_APPLIER,
        scope=verification_scope(IDENTITY),
        action=action_apply_model_revision(revision),
        signed_at=now,
    )
    request = {
        "protocol": REVISION_PROTOCOL,
        "request_id": "apply",
        "operation": "apply_model_revision",
        "payload": {"proposal_hash": proposal.proposal_hash},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return revision, request


def actors():
    root = Ed25519PrivateKey.generate()
    proposer_key = Ed25519PrivateKey.generate()
    replay_key = Ed25519PrivateKey.generate()
    reviewer_key = Ed25519PrivateKey.generate()
    applier_key = Ed25519PrivateKey.generate()
    return (
        root,
        (proposer_key, grant_for(root, proposer_key, subject="proposer", roles=(ROLE_REVISION_PROPOSER,))),
        (replay_key, grant_for(root, replay_key, subject="replay-keeper", roles=(ROLE_REVISION_REPLAY_KEEPER,))),
        (reviewer_key, grant_for(root, reviewer_key, subject="reviewer", roles=(ROLE_REVISION_REVIEWER,))),
        (applier_key, grant_for(root, applier_key, subject="applier", roles=(ROLE_REVISION_APPLIER,))),
    )


def run_to_review(db_path, root, dist, model, history, proposer, replay_keeper, reviewer):
    proposer_key, proposer_grant = proposer
    replay_key, replay_grant = replay_keeper
    reviewer_key, reviewer_grant = reviewer
    proposal, request = proposal_request(dist, model, history, actor=proposer_key, grant=proposer_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=300)
    assert completed.returncode == 0, response
    replay, request = replay_request(proposal, history, actor=replay_key, grant=replay_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=400)
    assert completed.returncode == 0, response
    review, request = review_request(proposal, replay, actor=reviewer_key, grant=reviewer_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=500)
    assert completed.returncode == 0, response
    return proposal, replay, review


def test_runtime_revision_full_path_preserves_old_and_new_models(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    dist, model, history = initialize_db(db_path)
    root, proposer, replay_keeper, reviewer, applier = actors()
    proposal, replay, review = run_to_review(db_path, root, dist, model, history, proposer, replay_keeper, reviewer)
    applier_key, applier_grant = applier
    revision, request = apply_request(dist, model, proposal, replay, review, actor=applier_key, grant=applier_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=600)
    assert completed.returncode == 0, response
    assert response["revision"]["revision_hash"] == revision.revision_hash
    conn = sqlite3.connect(db_path)
    current = model_from_dict(json.loads(conn.execute("SELECT model_json FROM multi_likelihood_model WHERE candidate_hash=?", (CANDIDATE_HASH,)).fetchone()[0]))
    row = conn.execute("SELECT base_model_json,new_model_json FROM model_revision_history WHERE proposal_hash=?", (proposal.proposal_hash,)).fetchone()
    conn.close()
    preserved_old = model_from_dict(json.loads(row[0]))
    preserved_new = model_from_dict(json.loads(row[1]))
    assert preserved_old.model_hash == model.model_hash
    assert preserved_new.model_hash == current.model_hash
    assert current.model_generation == model.model_generation + 1


def test_runtime_reviewer_must_be_independent_from_proposer(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    dist, model, history = initialize_db(db_path)
    root = Ed25519PrivateKey.generate()
    key = Ed25519PrivateKey.generate()
    grant = grant_for(root, key, subject="same-person", roles=(ROLE_REVISION_PROPOSER, ROLE_REVISION_REVIEWER))
    replay_key = Ed25519PrivateKey.generate()
    replay_grant = grant_for(root, replay_key, subject="replay-keeper", roles=(ROLE_REVISION_REPLAY_KEEPER,))
    proposal, request = proposal_request(dist, model, history, actor=key, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=300)
    assert completed.returncode == 0, response
    replay, request = replay_request(proposal, history, actor=replay_key, grant=replay_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=400)
    assert completed.returncode == 0, response
    try:
        review_request(proposal, replay, actor=key, grant=grant)
    except ValueError as exc:
        assert "independent" in str(exc)
    else:
        raise AssertionError("proposer unexpectedly reviewed own revision")


def test_runtime_apply_rejects_stale_replay_after_new_calibration(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    dist, model, history = initialize_db(db_path)
    root, proposer, replay_keeper, reviewer, applier = actors()
    proposal, replay, review = run_to_review(db_path, root, dist, model, history, proposer, replay_keeper, reviewer)
    extra = calibration(99, outcome="NEGATIVE")
    conn = _connect(str(db_path))
    conn.execute(
        "INSERT INTO calibration_likelihood_history(calibration_hash,target_hash,evidence_hash,family_ref,model_ref,receipt_json) VALUES(?,?,?,?,?,?)",
        (extra.calibration_hash, extra.target_hash, extra.evidence_hash, FAMILY, MODEL_REF, json.dumps(likelihood_to_dict(extra), sort_keys=True, separators=(",", ":"))),
    )
    conn.commit()
    conn.close()
    applier_key, applier_grant = applier
    _, request = apply_request(dist, model, proposal, replay, review, actor=applier_key, grant=applier_grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=600)
    assert completed.returncode == 2
    assert "stale counterfactual replay" in response["error"]


def test_runtime_revision_state_separates_proposal_replay_review_and_apply(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    dist, model, history = initialize_db(db_path)
    root, proposer, replay_keeper, reviewer, applier = actors()
    proposal, replay, review = run_to_review(db_path, root, dist, model, history, proposer, replay_keeper, reviewer)
    request = {"protocol": REVISION_PROTOCOL, "request_id": "state", "operation": "get_revision_state", "payload": {}}
    completed, response = invoke(request, root=root, db_path=db_path, now=550)
    assert completed.returncode == 0, response
    assert response["proposal_hashes"] == [proposal.proposal_hash]
    assert response["replay_hashes"] == [replay.replay_hash]
    assert response["review_hashes"] == [review.review_hash]
    assert response["revision_hashes"] == []
