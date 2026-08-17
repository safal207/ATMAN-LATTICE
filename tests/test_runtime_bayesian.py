import json
import os
import sqlite3
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.active_verification import entropy_microbits, make_hypothesis_state, make_likelihood_model
from model.authority import issue_authority_grant, sign_authorized_action
from model.bayesian_evidence import make_interpretation_rule
from model.runtime_active_verification import hypothesis_to_dict, likelihood_to_dict
from model.runtime_bayesian import (
    BAYES_PROTOCOL,
    ROLE_BAYES_RULE_KEEPER,
    ROLE_BAYES_UPDATE_KEEPER,
    action_apply_bayesian_update,
    action_register_interpretation_rule,
)
from model.runtime_economy import candidate_to_dict
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_verification import (
    VerificationCompletionReceipt,
    _digest as verification_digest,
    completion_to_dict,
    verification_scope,
    work_to_dict,
)
from model.verification_economy import make_economic_candidate
from model.verification_pressure import make_verification_work

IDENTITY = "agent:bayes-runtime"
RULE_NOW = 150
COMPLETED_AT = 200
APPLY_NOW = 250


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def authority_fixture():
    root = Ed25519PrivateKey.generate()
    actor = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id="grant:bayes",
        subject_ref="bayes-keeper",
        subject_key_id="bayes-key",
        subject_public_key=actor.public_key(),
        roles=(ROLE_BAYES_RULE_KEEPER, ROLE_BAYES_UPDATE_KEEPER),
        scopes=(verification_scope(IDENTITY),),
        policy_generation=12,
        valid_from=100,
        valid_until=1000,
        issuer_ref="root",
        issuer_key_id="root-key",
        issuer_private_key=root,
    )
    return root, actor, grant


def invoke(request, *, root, db_path, now):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "12"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    env["ATMAN_VERIFICATION_BUDGET_UNITS"] = "10"
    env["ATMAN_VERIFICATION_BUDGET_MAX_ITEMS"] = "10"
    env["ATMAN_VERIFICATION_BOOTSTRAP_COST"] = "1"
    env["ATMAN_VERIFICATION_MIN_COST_SAMPLES"] = "0"
    env["ATMAN_VERIFICATION_COST_UNCERTAINTY_PREMIUM"] = "0"
    env["ATMAN_ACTIVE_BUDGET_UNITS"] = "10"
    env["ATMAN_ACTIVE_MAX_SELECTED_ITEMS"] = "10"
    env["ATMAN_ACTIVE_MIN_INFORMATION_GAIN_MICROBITS"] = "1"
    env["ATMAN_ACTIVE_AGING_WEIGHT"] = "0"
    env["ATMAN_ACTIVE_RISK_WEIGHT"] = "0"
    completed = subprocess.run(
        [sys.executable, "-m", "model.bayes_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def initialize_db(db_path):
    work_a = make_verification_work(
        "work:bayes:a",
        subject_identity_ref=IDENTITY,
        evidence={"kind": "geometry-a"},
        cost_units=1,
        priority=0,
        submitted_at=100,
    )
    work_b = make_verification_work(
        "work:bayes:b",
        subject_identity_ref=IDENTITY,
        evidence={"kind": "geometry-b"},
        cost_units=1,
        priority=0,
        submitted_at=101,
    )
    candidate_a = make_economic_candidate(
        work_hash=work_a.work_hash,
        subject_identity_ref=IDENTITY,
        estimator_key="geometry",
        declared_cost_units=1,
        value_units=10,
        risk_units=5,
        priority=0,
        submitted_at=100,
    )
    candidate_b = make_economic_candidate(
        work_hash=work_b.work_hash,
        subject_identity_ref=IDENTITY,
        estimator_key="geometry",
        declared_cost_units=1,
        value_units=10,
        risk_units=5,
        priority=0,
        submitted_at=101,
    )
    prior = make_hypothesis_state(
        "hypothesis:shared",
        subject_identity_ref=IDENTITY,
        true_probability_bps=5000,
        evidence_state_hash="e" * 64,
        generation=1,
    )
    model_a = make_likelihood_model(
        candidate_hash=candidate_a.candidate_hash,
        hypothesis_hash=prior.hypothesis_hash,
        positive_if_true_bps=9000,
        positive_if_false_bps=1000,
        model_ref="model:a",
        model_generation=1,
    )
    model_b = make_likelihood_model(
        candidate_hash=candidate_b.candidate_hash,
        hypothesis_hash=prior.hypothesis_hash,
        positive_if_true_bps=8000,
        positive_if_false_bps=2000,
        model_ref="model:b",
        model_generation=1,
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
        """
        CREATE TABLE active_hypothesis (
            candidate_hash TEXT PRIMARY KEY,
            hypothesis_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE active_likelihood_model (
            candidate_hash TEXT PRIMARY KEY,
            model_json TEXT NOT NULL
        )
        """
    )
    for work, candidate, gate in ((work_a, candidate_a, "a" * 64), (work_b, candidate_b, "b" * 64)):
        conn.execute(
            "INSERT INTO verification_work(work_hash,work_ref,subject_identity_ref,target_gate_hash,work_json,status,completion_json) VALUES(?,?,?,?,?,?,NULL)",
            (work.work_hash, work.work_ref, IDENTITY, gate, json.dumps(work_to_dict(work)), "SUBMITTED"),
        )
        conn.execute(
            "INSERT INTO verification_economy_candidate(work_hash,candidate_json) VALUES(?,?)",
            (work.work_hash, json.dumps(candidate_to_dict(candidate))),
        )
        conn.execute(
            "INSERT INTO active_hypothesis(candidate_hash,hypothesis_json) VALUES(?,?)",
            (candidate.candidate_hash, json.dumps(hypothesis_to_dict(prior))),
        )
    conn.execute(
        "INSERT INTO active_likelihood_model(candidate_hash,model_json) VALUES(?,?)",
        (candidate_a.candidate_hash, json.dumps(likelihood_to_dict(model_a))),
    )
    conn.execute(
        "INSERT INTO active_likelihood_model(candidate_hash,model_json) VALUES(?,?)",
        (candidate_b.candidate_hash, json.dumps(likelihood_to_dict(model_b))),
    )
    conn.commit()
    conn.close()
    return work_a, work_b, candidate_a, candidate_b, prior, model_a, model_b


def register_rule_request(candidate, model, *, actor, grant, now=RULE_NOW):
    rule = make_interpretation_rule(
        candidate_hash=candidate.candidate_hash,
        likelihood_model_hash=model.model_hash,
        pass_outcome="POSITIVE",
        hold_outcome="INCONCLUSIVE",
        fail_outcome="NEGATIVE",
        rule_ref="rule:bayes",
        rule_generation=1,
        registered_at=now,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_BAYES_RULE_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action_register_interpretation_rule(rule, IDENTITY),
        signed_at=now,
    )
    return {
        "protocol": BAYES_PROTOCOL,
        "request_id": "rule",
        "operation": "register_interpretation_rule",
        "payload": {
            "candidate_hash": candidate.candidate_hash,
            "pass_outcome": "POSITIVE",
            "hold_outcome": "INCONCLUSIVE",
            "fail_outcome": "NEGATIVE",
            "rule_ref": "rule:bayes",
            "rule_generation": 1,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def complete_work(db_path, work, *, decision="PASS"):
    gate = "a" * 64 if work.work_ref.endswith(":a") else "b" * 64
    fields = {
        "work_hash": work.work_hash,
        "subject_identity_ref": IDENTITY,
        "target_gate_hash": gate,
        "schedule_generation": 1,
        "pressure_hash": "c" * 64,
        "decision": decision,
        "evidence_digest": "d" * 64,
        "completed_at": COMPLETED_AT,
        "actor_ref": "verification-executor",
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


def preview_request(candidate_hash, updater_ref="bayes-keeper"):
    return {
        "protocol": BAYES_PROTOCOL,
        "request_id": "preview",
        "operation": "preview_bayesian_update",
        "payload": {"candidate_hash": candidate_hash, "updater_ref": updater_ref},
    }


def apply_request(candidate_hash, preview, *, actor, grant):
    rebase_hashes = tuple(sorted(item["rebase_hash"] for item in preview["rebases"]))
    action = action_apply_bayesian_update(
        state_hash=preview["state_hash"],
        interpretation_hash=preview["interpretation"]["interpretation_hash"],
        update_hash=preview["update"]["update_hash"],
        posterior_hypothesis_hash=preview["posterior_hypothesis"]["hypothesis_hash"],
        rebase_hashes=rebase_hashes,
        applied_at=APPLY_NOW,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_BAYES_UPDATE_KEEPER,
        scope=verification_scope(IDENTITY),
        action=action,
        signed_at=APPLY_NOW,
    )
    return {
        "protocol": BAYES_PROTOCOL,
        "request_id": "apply",
        "operation": "apply_bayesian_update",
        "payload": {
            "candidate_hash": candidate_hash,
            "expected_state_hash": preview["state_hash"],
            "expected_interpretation_hash": preview["interpretation"]["interpretation_hash"],
            "expected_update_hash": preview["update"]["update_hash"],
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def test_completed_verification_updates_shared_prior_and_recalculates_next_active_plan(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    work_a, _, candidate_a, candidate_b, prior, model_a, model_b = initialize_db(db_path)
    root, actor, grant = authority_fixture()

    completed, response = invoke(register_rule_request(candidate_a, model_a, actor=actor, grant=grant), root=root, db_path=db_path, now=RULE_NOW)
    assert completed.returncode == 0, response
    complete_work(db_path, work_a, decision="PASS")

    completed, preview = invoke(preview_request(candidate_a.candidate_hash), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, preview
    assert preview["posterior_hypothesis"]["true_probability_bps"] == 9000
    assert len(preview["rebases"]) == 2

    completed, response = invoke(apply_request(candidate_a.candidate_hash, preview, actor=actor, grant=grant), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, response
    assert response["posterior_hypothesis"]["generation"] == prior.generation + 1
    assert response["next_unmodeled_candidate_hashes"] == []
    assert response["next_active_plan"]["candidate_hashes"] == [candidate_b.candidate_hash]
    assert response["next_active_insights"][0]["prior_entropy_microbits"] == entropy_microbits(9000)

    conn = sqlite3.connect(db_path)
    hyp_json = conn.execute("SELECT hypothesis_json FROM active_hypothesis WHERE candidate_hash=?", (candidate_b.candidate_hash,)).fetchone()[0]
    model_json = conn.execute("SELECT model_json FROM active_likelihood_model WHERE candidate_hash=?", (candidate_b.candidate_hash,)).fetchone()[0]
    conn.close()
    updated_hyp = json.loads(hyp_json)
    updated_model = json.loads(model_json)
    assert updated_hyp["hypothesis_hash"] == response["posterior_hypothesis"]["hypothesis_hash"]
    assert updated_model["hypothesis_hash"] == updated_hyp["hypothesis_hash"]
    assert updated_model["model_generation"] == model_b.model_generation + 1


def test_rule_cannot_be_registered_after_result_is_known(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    work_a, _, candidate_a, _, _, model_a, _ = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    complete_work(db_path, work_a, decision="PASS")
    completed, response = invoke(register_rule_request(candidate_a, model_a, actor=actor, grant=grant, now=APPLY_NOW), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 2
    assert "before verification completion" in response["error"]


def test_old_bayesian_preview_is_rejected_after_cohort_model_changes(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    work_a, _, candidate_a, candidate_b, prior, model_a, model_b = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    completed, response = invoke(register_rule_request(candidate_a, model_a, actor=actor, grant=grant), root=root, db_path=db_path, now=RULE_NOW)
    assert completed.returncode == 0, response
    complete_work(db_path, work_a, decision="PASS")
    completed, preview = invoke(preview_request(candidate_a.candidate_hash), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, preview

    changed = make_likelihood_model(
        candidate_hash=candidate_b.candidate_hash,
        hypothesis_hash=prior.hypothesis_hash,
        positive_if_true_bps=model_b.positive_if_true_bps,
        positive_if_false_bps=model_b.positive_if_false_bps,
        model_ref=model_b.model_ref,
        model_generation=model_b.model_generation + 1,
    )
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE active_likelihood_model SET model_json=? WHERE candidate_hash=?",
        (json.dumps(likelihood_to_dict(changed)), candidate_b.candidate_hash),
    )
    conn.commit()
    conn.close()

    completed, response = invoke(apply_request(candidate_a.candidate_hash, preview, actor=actor, grant=grant), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 2
    assert "stale Bayesian evidence state" in response["error"]


def test_same_completion_cannot_advance_knowledge_twice(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    work_a, _, candidate_a, _, _, model_a, _ = initialize_db(db_path)
    root, actor, grant = authority_fixture()
    completed, response = invoke(register_rule_request(candidate_a, model_a, actor=actor, grant=grant), root=root, db_path=db_path, now=RULE_NOW)
    assert completed.returncode == 0, response
    complete_work(db_path, work_a, decision="PASS")
    completed, preview = invoke(preview_request(candidate_a.candidate_hash), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, preview
    completed, response = invoke(apply_request(candidate_a.candidate_hash, preview, actor=actor, grant=grant), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 0, response

    completed, replay = invoke(apply_request(candidate_a.candidate_hash, preview, actor=actor, grant=grant), root=root, db_path=db_path, now=APPLY_NOW)
    assert completed.returncode == 2
    assert replay["ok"] is False
