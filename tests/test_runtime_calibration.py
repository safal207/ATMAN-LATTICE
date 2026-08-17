import json
import os
import sqlite3
import subprocess
import sys
from hashlib import sha256

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
from model.calibration import make_calibration_target, make_resolved_outcome
from model.multihypothesis import (
    interpret_multi_completion,
    make_evidence_dependency,
    make_hypothesis_distribution,
    make_multi_evidence_rule,
    make_multi_likelihood_model,
)
from model.runtime_calibration import (
    CALIBRATION_PROTOCOL,
    ROLE_CALIBRATION_RECORDER,
    ROLE_CALIBRATION_RESOLVER,
    ROLE_CALIBRATION_TARGET_KEEPER,
    _connect as calibration_connect,
    action_record_calibration_observation,
    action_register_calibration_target,
    action_register_resolved_outcome,
    target_from_dict,
)
from model.runtime_economy import candidate_to_dict
from model.runtime_multihypothesis import (
    dependency_to_dict,
    distribution_to_dict,
    evidence_to_dict,
    model_to_dict,
    rule_to_dict,
)
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

IDENTITY = "agent:calibration-runtime"
TARGET_AT = 150
COMPLETED_AT = 200
RESOLVED_AT = 250
CALIBRATED_AT = 300


def h(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def authority_fixture():
    root = Ed25519PrivateKey.generate()
    actor = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id="grant:calibration",
        subject_ref="calibration-keeper",
        subject_key_id="calibration-key",
        subject_public_key=actor.public_key(),
        roles=(ROLE_CALIBRATION_TARGET_KEEPER, ROLE_CALIBRATION_RESOLVER, ROLE_CALIBRATION_RECORDER),
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
    completed = subprocess.run(
        [sys.executable, "-m", "model.calibration_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def initialize_case(db_path):
    work = make_verification_work(
        "work:calibration:a",
        subject_identity_ref=IDENTITY,
        evidence={"kind": "root-cause-check"},
        cost_units=1,
        priority=0,
        submitted_at=100,
    )
    candidate = make_economic_candidate(
        work_hash=work.work_hash,
        subject_identity_ref=IDENTITY,
        estimator_key="calibration",
        declared_cost_units=1,
        value_units=10,
        risk_units=5,
        priority=0,
        submitted_at=100,
    )
    distribution = make_hypothesis_distribution(
        "dist:calibration-case",
        subject_identity_ref=IDENTITY,
        probability_bps={"H:A": 4000, "H:B": 3500, "H:C": 2500},
        evidence_state_hash=h("evidence:initial"),
        generation=1,
    )
    model = make_multi_likelihood_model(
        candidate_hash=candidate.candidate_hash,
        distribution=distribution,
        positive_likelihood_bps={"H:A": 9000, "H:B": 2000, "H:C": 1000},
        model_ref="model:calibration-root",
        model_generation=1,
    )
    dependency = make_evidence_dependency(
        candidate_hash=candidate.candidate_hash,
        source_event_hash=h("source:calibration-a"),
        derivation_hash=h("derivation:calibration-a"),
        dependency_group_ref="group:calibration-root",
        mode="INDEPENDENT",
        declaration_ref="dependency:calibration-a",
        declaration_generation=1,
        declared_at=120,
    )
    rule = make_multi_evidence_rule(
        candidate_hash=candidate.candidate_hash,
        likelihood_model_hash=model.model_hash,
        pass_outcome="POSITIVE",
        hold_outcome="INCONCLUSIVE",
        fail_outcome="NEGATIVE",
        rule_ref="rule:calibration-a",
        rule_generation=1,
        registered_at=130,
    )

    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE verification_work (work_hash TEXT PRIMARY KEY, work_ref TEXT NOT NULL UNIQUE, subject_identity_ref TEXT NOT NULL, target_gate_hash TEXT NOT NULL, work_json TEXT NOT NULL, status TEXT NOT NULL, completion_json TEXT)"
    )
    conn.execute("CREATE TABLE verification_economy_candidate (work_hash TEXT PRIMARY KEY, candidate_json TEXT NOT NULL)")
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

    conn = calibration_connect(str(db_path))
    conn.execute(
        "INSERT INTO multi_hypothesis_distribution(distribution_ref,distribution_json) VALUES(?,?)",
        (distribution.distribution_ref, json.dumps(distribution_to_dict(distribution))),
    )
    conn.execute(
        "INSERT INTO multi_candidate_binding(candidate_hash,distribution_ref) VALUES(?,?)",
        (candidate.candidate_hash, distribution.distribution_ref),
    )
    conn.execute(
        "INSERT INTO multi_likelihood_model(candidate_hash,model_json) VALUES(?,?)",
        (candidate.candidate_hash, json.dumps(model_to_dict(model))),
    )
    conn.execute(
        "INSERT INTO multi_evidence_dependency(candidate_hash,dependency_json) VALUES(?,?)",
        (candidate.candidate_hash, json.dumps(dependency_to_dict(dependency))),
    )
    conn.execute(
        "INSERT INTO multi_evidence_rule(candidate_hash,rule_json) VALUES(?,?)",
        (candidate.candidate_hash, json.dumps(rule_to_dict(rule))),
    )
    conn.commit()
    conn.close()
    return work, candidate, distribution, model, dependency, rule


def target_request(candidate, distribution, model, dependency, *, actor, grant, role=ROLE_CALIBRATION_TARGET_KEEPER):
    target = make_calibration_target(
        target_ref="target:calibration-a",
        calibration_family_ref="family:calibration-v1",
        distribution=distribution,
        likelihood_model=model,
        dependency=dependency,
        committed_at=TARGET_AT,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=role,
        scope=verification_scope(IDENTITY),
        action=action_register_calibration_target(target),
        signed_at=TARGET_AT,
    )
    request = {
        "protocol": CALIBRATION_PROTOCOL,
        "request_id": "target",
        "operation": "register_calibration_target",
        "payload": {
            "candidate_hash": candidate.candidate_hash,
            "target_ref": target.target_ref,
            "calibration_family_ref": target.calibration_family_ref,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return target, request


def complete_and_accept_evidence(db_path, work, candidate, distribution, model, dependency, rule, *, decision="PASS"):
    fields = {
        "work_hash": work.work_hash,
        "subject_identity_ref": IDENTITY,
        "target_gate_hash": "a" * 64,
        "schedule_generation": 1,
        "pressure_hash": "d" * 64,
        "decision": decision,
        "evidence_digest": "e" * 64,
        "completed_at": COMPLETED_AT,
        "actor_ref": "verification-executor",
    }
    provisional = VerificationCompletionReceipt(**fields, completion_hash="0" * 64)
    completion = VerificationCompletionReceipt(**fields, completion_hash=verification_digest(provisional.material()))
    completion.validate()
    evidence = interpret_multi_completion(
        candidate_hash=candidate.candidate_hash,
        work_hash=work.work_hash,
        completion_hash=completion.completion_hash,
        completion_decision=decision,
        distribution=distribution,
        likelihood_model=model,
        dependency=dependency,
        rule=rule,
        completion_completed_at=COMPLETED_AT,
        interpreted_at=COMPLETED_AT + 1,
    )
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE verification_work SET status='COMPLETED',completion_json=? WHERE work_hash=?",
        (json.dumps(completion_to_dict(completion)), work.work_hash),
    )
    conn.execute(
        "INSERT INTO multi_evidence_history(evidence_hash,candidate_hash,completion_hash,source_event_hash,dependency_group_ref,receipt_json) VALUES(?,?,?,?,?,?)",
        (evidence.evidence_hash, candidate.candidate_hash, completion.completion_hash, evidence.source_event_hash, evidence.dependency_group_ref, json.dumps(evidence_to_dict(evidence))),
    )
    conn.commit()
    conn.close()
    return completion, evidence


def resolution_request(target, *, actor, grant, resolved_hypothesis_ref="H:A"):
    resolution = make_resolved_outcome(
        target,
        resolution_ref="resolution:calibration-case",
        resolved_hypothesis_ref=resolved_hypothesis_ref,
        resolution_source_hash=h("gold:calibration-case"),
        resolved_at=RESOLVED_AT,
        resolver_ref=grant.subject_ref,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_CALIBRATION_RESOLVER,
        scope=verification_scope(IDENTITY),
        action=action_register_resolved_outcome(resolution),
        signed_at=RESOLVED_AT,
    )
    request = {
        "protocol": CALIBRATION_PROTOCOL,
        "request_id": "resolution",
        "operation": "register_resolved_outcome",
        "payload": {
            "candidate_hash": target.candidate_hash,
            "resolution_ref": resolution.resolution_ref,
            "resolved_hypothesis_ref": resolved_hypothesis_ref,
            "resolution_source_hash": resolution.resolution_source_hash,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    return resolution, request


def observation_request(target, resolution, evidence, *, actor, grant):
    action = action_record_calibration_observation(
        target_hash=target.target_hash,
        resolution_hash=resolution.resolution_hash,
        evidence_hash=evidence.evidence_hash,
        calibrated_at=CALIBRATED_AT,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_CALIBRATION_RECORDER,
        scope=verification_scope(IDENTITY),
        action=action,
        signed_at=CALIBRATED_AT,
    )
    return {
        "protocol": CALIBRATION_PROTOCOL,
        "request_id": "observation",
        "operation": "record_calibration_observation",
        "payload": {"candidate_hash": target.candidate_hash},
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def test_runtime_freezes_target_then_scores_resolved_evidence_and_exposes_state(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    work, candidate, distribution, model, dependency, rule = initialize_case(db_path)
    root, actor, grant = authority_fixture()

    expected_target, request = target_request(candidate, distribution, model, dependency, actor=actor, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=TARGET_AT)
    assert completed.returncode == 0, response
    target = target_from_dict(response["target"])
    assert target == expected_target

    _, evidence = complete_and_accept_evidence(db_path, work, candidate, distribution, model, dependency, rule, decision="PASS")
    resolution, request = resolution_request(target, actor=actor, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=RESOLVED_AT)
    assert completed.returncode == 0, response

    completed, response = invoke(observation_request(target, resolution, evidence, actor=actor, grant=grant), root=root, db_path=db_path, now=CALIBRATED_AT)
    assert completed.returncode == 0, response
    assert response["forecast_calibration"]["resolved_probability_bps"] == 4000
    assert response["likelihood_calibration"]["predicted_positive_bps"] == 9000
    assert response["likelihood_calibration"]["observed_outcome"] == "POSITIVE"
    assert response["likelihood_calibration"]["brier_score_ppm"] == 10000

    state_request = {
        "protocol": CALIBRATION_PROTOCOL,
        "request_id": "state",
        "operation": "get_calibration_state",
        "payload": {"family_min_samples": 1, "family_gap_threshold_bps": 1500},
    }
    completed, state = invoke(state_request, root=root, db_path=db_path, now=CALIBRATED_AT + 1)
    assert completed.returncode == 0, state
    assert state["forecast_count"] == 1
    assert state["likelihood_count"] == 1
    assert state["family_snapshots"][0]["calibration_family_ref"] == "family:calibration-v1"
    assert state["family_snapshots"][0]["status"] == "NO_MARGINAL_MISCALIBRATION_SIGNAL"


def test_calibration_target_cannot_be_created_after_result_is_known(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    work, candidate, distribution, model, dependency, rule = initialize_case(db_path)
    root, actor, grant = authority_fixture()
    complete_and_accept_evidence(db_path, work, candidate, distribution, model, dependency, rule)
    _, request = target_request(candidate, distribution, model, dependency, actor=actor, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=TARGET_AT)
    assert completed.returncode == 2
    assert "before verification completion" in response["error"]


def test_calibration_authority_roles_are_not_interchangeable(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    _, candidate, distribution, model, dependency, _ = initialize_case(db_path)
    root, actor, grant = authority_fixture()
    _, request = target_request(candidate, distribution, model, dependency, actor=actor, grant=grant, role=ROLE_CALIBRATION_RESOLVER)
    completed, response = invoke(request, root=root, db_path=db_path, now=TARGET_AT)
    assert completed.returncode == 2
    assert "required_role_mismatch" in response["error"]


def test_resolution_is_immutable_once_registered(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    _, candidate, distribution, model, dependency, _ = initialize_case(db_path)
    root, actor, grant = authority_fixture()
    target, request = target_request(candidate, distribution, model, dependency, actor=actor, grant=grant)
    completed, response = invoke(request, root=root, db_path=db_path, now=TARGET_AT)
    assert completed.returncode == 0, response
    target = target_from_dict(response["target"])

    _, request = resolution_request(target, actor=actor, grant=grant, resolved_hypothesis_ref="H:A")
    completed, response = invoke(request, root=root, db_path=db_path, now=RESOLVED_AT)
    assert completed.returncode == 0, response

    _, request = resolution_request(target, actor=actor, grant=grant, resolved_hypothesis_ref="H:B")
    completed, response = invoke(request, root=root, db_path=db_path, now=RESOLVED_AT)
    assert completed.returncode == 2
    assert "immutable" in response["error"]
