import json
import os
import sqlite3
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.active_verification import make_hypothesis_state, make_likelihood_model
from model.authority import issue_authority_grant, sign_authorized_action
from model.runtime_active_verification import (
    ACTIVE_PROTOCOL,
    GLOBAL_ACTIVE_SCOPE,
    ROLE_ACTIVE_MODEL_KEEPER,
    ROLE_ACTIVE_PLAN_KEEPER,
    action_finalize_active_plan,
    action_register_hypothesis,
    action_register_likelihood,
    make_active_policy_from_env,
)
from model.runtime_economy import candidate_to_dict, make_economy_policy_from_env
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_verification import verification_scope, work_to_dict
from model.verification_economy import make_economic_candidate
from model.verification_pressure import make_verification_work

NOW = 500
IDENTITY = "agent:active"


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def authority_fixture():
    root = Ed25519PrivateKey.generate()
    actor = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id="grant:active",
        subject_ref="active-actor",
        subject_key_id="active-key",
        subject_public_key=actor.public_key(),
        roles=(ROLE_ACTIVE_MODEL_KEEPER, ROLE_ACTIVE_PLAN_KEEPER),
        scopes=(verification_scope(IDENTITY), GLOBAL_ACTIVE_SCOPE),
        policy_generation=12,
        valid_from=100,
        valid_until=1000,
        issuer_ref="root",
        issuer_key_id="root-key",
        issuer_private_key=root,
    )
    return root, actor, grant


def invoke(request, *, root, db_path, now=NOW, extra_env=None):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "12"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    env["ATMAN_VERIFICATION_BUDGET_UNITS"] = "10"
    env["ATMAN_VERIFICATION_BUDGET_MAX_ITEMS"] = "10"
    env["ATMAN_VERIFICATION_BOOTSTRAP_COST"] = "5"
    env["ATMAN_VERIFICATION_MIN_COST_SAMPLES"] = "0"
    env["ATMAN_VERIFICATION_COST_UNCERTAINTY_PREMIUM"] = "0"
    env["ATMAN_ACTIVE_BUDGET_UNITS"] = "5"
    env["ATMAN_ACTIVE_MAX_SELECTED_ITEMS"] = "1"
    env["ATMAN_ACTIVE_MIN_INFORMATION_GAIN_MICROBITS"] = "1"
    env["ATMAN_ACTIVE_AGING_WEIGHT"] = "0"
    env["ATMAN_ACTIVE_RISK_WEIGHT"] = "0"
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        [sys.executable, "-m", "model.active_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def initialize_db(db_path):
    work = make_verification_work(
        "work:active",
        subject_identity_ref=IDENTITY,
        evidence={"kind": "geometry"},
        cost_units=1,
        priority=0,
        submitted_at=100,
    )
    candidate = make_economic_candidate(
        work_hash=work.work_hash,
        subject_identity_ref=IDENTITY,
        estimator_key="geometry",
        declared_cost_units=1,
        value_units=10,
        risk_units=5,
        priority=0,
        submitted_at=100,
    )
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE verification_work (
            work_hash TEXT PRIMARY KEY,
            work_ref TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            target_gate_hash TEXT NOT NULL,
            work_json TEXT NOT NULL,
            status TEXT NOT NULL,
            completion_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE verification_economy_candidate (
            work_hash TEXT PRIMARY KEY,
            candidate_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO verification_work(work_hash,work_ref,subject_identity_ref,target_gate_hash,work_json,status,completion_json) VALUES(?,?,?,?,?,?,NULL)",
        (work.work_hash, work.work_ref, IDENTITY, "a" * 64, json.dumps(work_to_dict(work)), "SUBMITTED"),
    )
    conn.execute(
        "INSERT INTO verification_economy_candidate(work_hash,candidate_json) VALUES(?,?)",
        (work.work_hash, json.dumps(candidate_to_dict(candidate))),
    )
    conn.commit()
    conn.close()
    return work, candidate


def hypothesis_request(candidate, *, actor, grant, probability=5000, generation=1, evidence_hash="e" * 64):
    hyp = make_hypothesis_state(
        "hypothesis:active",
        subject_identity_ref=IDENTITY,
        true_probability_bps=probability,
        evidence_state_hash=evidence_hash,
        generation=generation,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_ACTIVE_MODEL_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action_register_hypothesis(candidate.candidate_hash, hyp),
        signed_at=450,
    )
    return hyp, {
        "protocol": ACTIVE_PROTOCOL,
        "request_id": f"hyp:{generation}",
        "operation": "register_hypothesis_state",
        "payload": {
            "candidate_hash": candidate.candidate_hash,
            "hypothesis_ref": hyp.hypothesis_ref,
            "true_probability_bps": hyp.true_probability_bps,
            "evidence_state_hash": hyp.evidence_state_hash,
            "generation": hyp.generation,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def likelihood_request(candidate, hyp, *, actor, grant, sensitivity=9500, false_positive=500, generation=1):
    model = make_likelihood_model(
        candidate_hash=candidate.candidate_hash,
        hypothesis_hash=hyp.hypothesis_hash,
        positive_if_true_bps=sensitivity,
        positive_if_false_bps=false_positive,
        model_ref="model:active",
        model_generation=generation,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_ACTIVE_MODEL_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action_register_likelihood(model, IDENTITY),
        signed_at=450,
    )
    return model, {
        "protocol": ACTIVE_PROTOCOL,
        "request_id": f"model:{generation}",
        "operation": "register_likelihood_model",
        "payload": {
            "candidate_hash": candidate.candidate_hash,
            "positive_if_true_bps": model.positive_if_true_bps,
            "positive_if_false_bps": model.positive_if_false_bps,
            "model_ref": model.model_ref,
            "model_generation": model.model_generation,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def preview_request():
    return {
        "protocol": ACTIVE_PROTOCOL,
        "request_id": "preview",
        "operation": "preview_active_plan",
        "payload": {},
    }


def test_unmodeled_work_is_preserved_explicitly(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    _, candidate = initialize_db(db_path)
    root, _, _ = authority_fixture()
    completed, response = invoke(preview_request(), root=root, db_path=db_path)
    assert completed.returncode == 0, response
    assert response["plan"]["candidate_hashes"] == []
    assert response["unmodeled_candidate_hashes"] == [candidate.candidate_hash]


def test_registered_information_model_produces_selected_active_plan(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    _, candidate = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    hyp, request = hypothesis_request(candidate, actor=actor, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path)
    assert completed.returncode == 0, response
    _, request = likelihood_request(candidate, hyp, actor=actor, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path)
    assert completed.returncode == 0, response

    completed, response = invoke(preview_request(), root=root, db_path=db_path)
    assert completed.returncode == 0, response
    assert response["unmodeled_candidate_hashes"] == []
    assert response["plan"]["selected_candidate_hashes"] == [candidate.candidate_hash]
    assert response["insights"][0]["expected_information_gain_microbits"] > 0


def test_hypothesis_update_makes_old_likelihood_stale_until_remodeled(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    _, candidate = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    hyp1, request = hypothesis_request(candidate, actor=actor, grant=grant, generation=1)
    invoke(request, root=root, db_path=db_path)
    _, request = likelihood_request(candidate, hyp1, actor=actor, grant=grant, generation=1)
    invoke(request, root=root, db_path=db_path)
    _, before = invoke(preview_request(), root=root, db_path=db_path)
    assert before["unmodeled_candidate_hashes"] == []

    _, request = hypothesis_request(candidate, actor=actor, grant=grant, probability=7000, generation=2, evidence_hash="f" * 64)
    completed, response = invoke(request, root=root, db_path=db_path)
    assert completed.returncode == 0, response
    _, after = invoke(preview_request(), root=root, db_path=db_path)
    assert after["unmodeled_candidate_hashes"] == [candidate.candidate_hash]


def test_old_active_preview_cannot_finalize_after_information_state_changes(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    _, candidate = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    hyp1, request = hypothesis_request(candidate, actor=actor, grant=grant, generation=1)
    invoke(request, root=root, db_path=db_path)
    _, request = likelihood_request(candidate, hyp1, actor=actor, grant=grant, generation=1)
    invoke(request, root=root, db_path=db_path)
    _, preview = invoke(preview_request(), root=root, db_path=db_path)

    active_policy = make_active_policy_from_env()
    economy_policy = make_economy_policy_from_env()
    action = action_finalize_active_plan(
        state_hash=preview["state_hash"],
        runtime_plan_hash=preview["runtime_plan_hash"],
        active_policy_hash=active_policy.policy_hash,
        economy_policy_hash=economy_policy.policy_hash,
        generation=1,
        finalized_at=NOW,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_ACTIVE_PLAN_KEEPER,
        scope=GLOBAL_ACTIVE_SCOPE,
        action=action,
        signed_at=450,
    )
    finalize = {
        "protocol": ACTIVE_PROTOCOL,
        "request_id": "finalize:old",
        "operation": "finalize_active_plan",
        "payload": {
            "expected_state_hash": preview["state_hash"],
            "expected_runtime_plan_hash": preview["runtime_plan_hash"],
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }

    _, request = hypothesis_request(candidate, actor=actor, grant=grant, probability=6500, generation=2, evidence_hash="f" * 64)
    invoke(request, root=root, db_path=db_path)
    completed, response = invoke(finalize, root=root, db_path=db_path)
    assert completed.returncode == 2
    assert "stale active verification state" in response["error"]


def test_current_active_plan_finalizes_with_plan_keeper_authority(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    _, candidate = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    hyp, request = hypothesis_request(candidate, actor=actor, grant=grant)
    invoke(request, root=root, db_path=db_path)
    _, request = likelihood_request(candidate, hyp, actor=actor, grant=grant)
    invoke(request, root=root, db_path=db_path)
    _, preview = invoke(preview_request(), root=root, db_path=db_path)

    # Match the worker's environment-backed policies exactly.
    env = {
        "ATMAN_VERIFICATION_BUDGET_UNITS": "10",
        "ATMAN_VERIFICATION_BUDGET_MAX_ITEMS": "10",
        "ATMAN_VERIFICATION_BOOTSTRAP_COST": "5",
        "ATMAN_VERIFICATION_MIN_COST_SAMPLES": "0",
        "ATMAN_VERIFICATION_COST_UNCERTAINTY_PREMIUM": "0",
        "ATMAN_ACTIVE_BUDGET_UNITS": "5",
        "ATMAN_ACTIVE_MAX_SELECTED_ITEMS": "1",
        "ATMAN_ACTIVE_MIN_INFORMATION_GAIN_MICROBITS": "1",
        "ATMAN_ACTIVE_AGING_WEIGHT": "0",
        "ATMAN_ACTIVE_RISK_WEIGHT": "0",
    }
    old = os.environ.copy()
    os.environ.update(env)
    try:
        active_policy = make_active_policy_from_env()
        economy_policy = make_economy_policy_from_env()
    finally:
        os.environ.clear()
        os.environ.update(old)

    action = action_finalize_active_plan(
        state_hash=preview["state_hash"],
        runtime_plan_hash=preview["runtime_plan_hash"],
        active_policy_hash=active_policy.policy_hash,
        economy_policy_hash=economy_policy.policy_hash,
        generation=1,
        finalized_at=NOW,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_ACTIVE_PLAN_KEEPER,
        scope=GLOBAL_ACTIVE_SCOPE,
        action=action,
        signed_at=450,
    )
    request = {
        "protocol": ACTIVE_PROTOCOL,
        "request_id": "finalize:current",
        "operation": "finalize_active_plan",
        "payload": {
            "expected_state_hash": preview["state_hash"],
            "expected_runtime_plan_hash": preview["runtime_plan_hash"],
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    completed, response = invoke(request, root=root, db_path=db_path)
    assert completed.returncode == 0, response
    assert response["generation"] == 1
    assert response["plan"]["selected_candidate_hashes"] == [candidate.candidate_hash]
