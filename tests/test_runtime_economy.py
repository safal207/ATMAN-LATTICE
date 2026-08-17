from dataclasses import asdict
import json
import os
import sqlite3
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
from model.runtime_economy import (
    ECONOMY_PROTOCOL,
    GLOBAL_ECONOMY_SCOPE,
    ROLE_BUDGET_KEEPER,
    ROLE_COST_METER,
    ROLE_ECONOMY_SUBMITTER,
    action_finalize_allocation,
    action_record_cost,
    action_submit_candidate,
    make_economy_policy_from_env,
)
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_verification import (
    VerificationCompletionReceipt,
    _digest as verification_digest,
    completion_to_dict,
    verification_scope,
    work_to_dict,
)
from model.verification_economy import make_economic_candidate, record_cost_observation
from model.verification_pressure import make_verification_work

NOW = 500


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def authority_fixture(identity_ref: str):
    root = Ed25519PrivateKey.generate()
    actor = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id="grant:economy",
        subject_ref="economy-actor",
        subject_key_id="economy-key",
        subject_public_key=actor.public_key(),
        roles=(ROLE_ECONOMY_SUBMITTER, ROLE_COST_METER, ROLE_BUDGET_KEEPER),
        scopes=(verification_scope(identity_ref), GLOBAL_ECONOMY_SCOPE),
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
    env["ATMAN_VERIFICATION_BUDGET_UNITS"] = "12"
    env["ATMAN_VERIFICATION_BUDGET_MAX_ITEMS"] = "1"
    env["ATMAN_VERIFICATION_BOOTSTRAP_COST"] = "10"
    env["ATMAN_VERIFICATION_MIN_COST_SAMPLES"] = "1"
    env["ATMAN_VERIFICATION_COST_UNCERTAINTY_PREMIUM"] = "0"
    env["ATMAN_VERIFICATION_ECONOMY_AGING_QUANTUM"] = "60"
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        [sys.executable, "-m", "model.economy_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def initialize_verification_db(db_path, *, work_ref="work:1", identity_ref="agent:economy", cost=1, submitted_at=100):
    work = make_verification_work(
        work_ref,
        subject_identity_ref=identity_ref,
        evidence={"kind": "geometry"},
        cost_units=cost,
        priority=0,
        submitted_at=submitted_at,
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
        "INSERT INTO verification_work(work_hash,work_ref,subject_identity_ref,target_gate_hash,work_json,status,completion_json) VALUES(?,?,?,?,?,?,NULL)",
        (work.work_hash, work.work_ref, identity_ref, "a" * 64, json.dumps(work_to_dict(work)), "SUBMITTED"),
    )
    conn.commit()
    conn.close()
    return work


def add_work(db_path, *, work_ref, identity_ref="agent:economy", cost=999, submitted_at=101):
    work = make_verification_work(
        work_ref,
        subject_identity_ref=identity_ref,
        evidence={"kind": work_ref},
        cost_units=cost,
        priority=0,
        submitted_at=submitted_at,
    )
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO verification_work(work_hash,work_ref,subject_identity_ref,target_gate_hash,work_json,status,completion_json) VALUES(?,?,?,?,?,?,NULL)",
        (work.work_hash, work.work_ref, identity_ref, "b" * 64, json.dumps(work_to_dict(work)), "SUBMITTED"),
    )
    conn.commit()
    conn.close()
    return work


def candidate_for(work, *, estimator_key, value, risk):
    return make_economic_candidate(
        work_hash=work.work_hash,
        subject_identity_ref=work.subject_identity_ref,
        estimator_key=estimator_key,
        declared_cost_units=work.cost_units,
        value_units=value,
        risk_units=risk,
        priority=work.priority,
        submitted_at=work.submitted_at,
    )


def submit_candidate_request(candidate, *, actor, grant):
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_ECONOMY_SUBMITTER,
        scope=verification_scope(candidate.subject_identity_ref),
        action=action_submit_candidate(candidate),
        signed_at=450,
    )
    return {
        "protocol": ECONOMY_PROTOCOL,
        "request_id": f"submit:{candidate.work_hash[:8]}",
        "operation": "submit_economic_candidate",
        "payload": {
            "work_hash": candidate.work_hash,
            "estimator_key": candidate.estimator_key,
            "value_units": candidate.value_units,
            "risk_units": candidate.risk_units,
            "priority": candidate.priority,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def mark_completed(db_path, work, *, completion_hash_seed="c"):
    fields = {
        "work_hash": work.work_hash,
        "subject_identity_ref": work.subject_identity_ref,
        "target_gate_hash": "a" * 64,
        "schedule_generation": 1,
        "pressure_hash": "b" * 64,
        "decision": "PASS",
        "evidence_digest": "d" * 64,
        "completed_at": 480,
        "actor_ref": "executor",
    }
    provisional = VerificationCompletionReceipt(**fields, completion_hash="0" * 64)
    receipt = VerificationCompletionReceipt(**fields, completion_hash=verification_digest(provisional.material()))
    receipt.validate()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE verification_work SET status='COMPLETED', completion_json=? WHERE work_hash=?",
        (json.dumps(completion_to_dict(receipt)), work.work_hash),
    )
    conn.commit()
    conn.close()
    return receipt


def test_runtime_economy_persists_candidate_and_ignores_declared_cost_for_bootstrap(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    work = initialize_verification_db(db_path, cost=1)
    root, actor, grant = authority_fixture(work.subject_identity_ref)
    candidate = candidate_for(work, estimator_key="geometry", value=10, risk=5)
    completed, response = invoke(submit_candidate_request(candidate, actor=actor, grant=grant), root=root, db_path=db_path)
    assert completed.returncode == 0, response

    preview_request = {
        "protocol": ECONOMY_PROTOCOL,
        "request_id": "preview:1",
        "operation": "preview_budget_allocation",
        "payload": {},
    }
    _, preview = invoke(preview_request, root=root, db_path=db_path)
    costs = dict(preview["allocation"]["estimated_costs"])
    assert costs[candidate.candidate_hash] == 10
    assert candidate.declared_cost_units == 1


def test_cost_meter_requires_completed_work_and_observation_changes_future_estimate(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    work = initialize_verification_db(db_path, cost=1)
    root, actor, grant = authority_fixture(work.subject_identity_ref)
    candidate = candidate_for(work, estimator_key="geometry", value=10, risk=5)
    invoke(submit_candidate_request(candidate, actor=actor, grant=grant), root=root, db_path=db_path)

    fake_observation = record_cost_observation(
        work_hash=work.work_hash,
        completion_hash="c" * 64,
        estimator_key="geometry",
        observed_cost_units=4,
        measured_at=NOW,
        meter_ref=grant.subject_ref,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_COST_METER,
        scope=GLOBAL_ECONOMY_SCOPE,
        action=action_record_cost(fake_observation),
        signed_at=450,
    )
    request = {
        "protocol": ECONOMY_PROTOCOL,
        "request_id": "meter:before",
        "operation": "record_cost_observation",
        "payload": {"work_hash": work.work_hash, "observed_cost_units": 4},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    completed, response = invoke(request, root=root, db_path=db_path)
    assert completed.returncode == 2
    assert "completed verification work" in response["error"]

    completion = mark_completed(db_path, work)
    observation = record_cost_observation(
        work_hash=work.work_hash,
        completion_hash=completion.completion_hash,
        estimator_key="geometry",
        observed_cost_units=4,
        measured_at=NOW,
        meter_ref=grant.subject_ref,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_COST_METER,
        scope=GLOBAL_ECONOMY_SCOPE,
        action=action_record_cost(observation),
        signed_at=450,
    )
    request["request_id"] = "meter:after"
    request["proof"] = authority_proof_to_dict(proof)
    completed, response = invoke(request, root=root, db_path=db_path)
    assert completed.returncode == 0, response
    assert response["observation"]["observed_cost_units"] == 4

    second = add_work(db_path, work_ref="work:2", cost=999)
    second_candidate = candidate_for(second, estimator_key="geometry", value=10, risk=5)
    invoke(submit_candidate_request(second_candidate, actor=actor, grant=grant), root=root, db_path=db_path)
    _, preview = invoke({
        "protocol": ECONOMY_PROTOCOL,
        "request_id": "preview:after",
        "operation": "preview_budget_allocation",
        "payload": {},
    }, root=root, db_path=db_path)
    costs = dict(preview["allocation"]["estimated_costs"])
    assert costs[second_candidate.candidate_hash] == 4
    assert second_candidate.declared_cost_units == 999


def test_budget_finalization_is_keeper_authorized_and_generation_bound(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    work = initialize_verification_db(db_path, cost=1)
    root, actor, grant = authority_fixture(work.subject_identity_ref)
    candidate = candidate_for(work, estimator_key="geometry", value=10, risk=5)
    invoke(submit_candidate_request(candidate, actor=actor, grant=grant), root=root, db_path=db_path)
    _, preview = invoke({
        "protocol": ECONOMY_PROTOCOL,
        "request_id": "preview",
        "operation": "preview_budget_allocation",
        "payload": {},
    }, root=root, db_path=db_path)

    old_env = os.environ.copy()
    try:
        os.environ["ATMAN_VERIFICATION_BUDGET_UNITS"] = "12"
        os.environ["ATMAN_VERIFICATION_BUDGET_MAX_ITEMS"] = "1"
        os.environ["ATMAN_VERIFICATION_BOOTSTRAP_COST"] = "10"
        os.environ["ATMAN_VERIFICATION_MIN_COST_SAMPLES"] = "1"
        os.environ["ATMAN_VERIFICATION_COST_UNCERTAINTY_PREMIUM"] = "0"
        policy = make_economy_policy_from_env()
    finally:
        os.environ.clear()
        os.environ.update(old_env)

    action = action_finalize_allocation(
        state_hash=preview["state_hash"],
        allocation_hash=preview["allocation"]["allocation_hash"],
        policy_hash=policy.policy_hash,
        generation=1,
        finalized_at=NOW,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_BUDGET_KEEPER,
        scope=GLOBAL_ECONOMY_SCOPE,
        action=action,
        signed_at=450,
    )
    request = {
        "protocol": ECONOMY_PROTOCOL,
        "request_id": "finalize",
        "operation": "finalize_budget_allocation",
        "payload": {"expected_state_hash": preview["state_hash"]},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    completed, response = invoke(request, root=root, db_path=db_path)
    assert completed.returncode == 0, response
    assert response["generation"] == 1


def test_stale_budget_preview_cannot_be_finalized_after_candidate_set_changes(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    work = initialize_verification_db(db_path, cost=1)
    root, actor, grant = authority_fixture(work.subject_identity_ref)
    first = candidate_for(work, estimator_key="geometry", value=10, risk=5)
    invoke(submit_candidate_request(first, actor=actor, grant=grant), root=root, db_path=db_path)
    _, preview = invoke({
        "protocol": ECONOMY_PROTOCOL,
        "request_id": "preview:stale",
        "operation": "preview_budget_allocation",
        "payload": {},
    }, root=root, db_path=db_path)

    second_work = add_work(db_path, work_ref="work:2", cost=1)
    second = candidate_for(second_work, estimator_key="geometry", value=20, risk=5)
    invoke(submit_candidate_request(second, actor=actor, grant=grant), root=root, db_path=db_path)

    old_env = os.environ.copy()
    try:
        os.environ["ATMAN_VERIFICATION_BUDGET_UNITS"] = "12"
        os.environ["ATMAN_VERIFICATION_BUDGET_MAX_ITEMS"] = "1"
        os.environ["ATMAN_VERIFICATION_BOOTSTRAP_COST"] = "10"
        os.environ["ATMAN_VERIFICATION_MIN_COST_SAMPLES"] = "1"
        os.environ["ATMAN_VERIFICATION_COST_UNCERTAINTY_PREMIUM"] = "0"
        policy = make_economy_policy_from_env()
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    action = action_finalize_allocation(
        state_hash=preview["state_hash"],
        allocation_hash=preview["allocation"]["allocation_hash"],
        policy_hash=policy.policy_hash,
        generation=1,
        finalized_at=NOW,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_BUDGET_KEEPER,
        scope=GLOBAL_ECONOMY_SCOPE,
        action=action,
        signed_at=450,
    )
    completed, response = invoke({
        "protocol": ECONOMY_PROTOCOL,
        "request_id": "finalize:stale",
        "operation": "finalize_budget_allocation",
        "payload": {"expected_state_hash": preview["state_hash"]},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }, root=root, db_path=db_path)
    assert completed.returncode == 2
    assert "stale verification economy state" in response["error"]
