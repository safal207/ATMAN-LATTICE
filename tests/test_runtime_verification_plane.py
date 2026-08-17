from __future__ import annotations

import json
import os
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
from model.geometric_coherence import TorsionEvidence, a3_geometric_gate
from model.lattice import (
    cross_axis_bind,
    issue_genesis_receipt,
    issue_successor_receipt,
    observe_space,
    observe_time,
)
from model.runtime_protocol import authority_grant_to_dict, authority_proof_to_dict
from model.runtime_verification import (
    ROLE_VERIFICATION_EXECUTOR,
    ROLE_VERIFICATION_SUBMITTER,
    VERIFY_PROTOCOL,
    action_complete_verification,
    action_submit_verification,
    geometric_observer_to_dict,
    verification_scope,
)
from model.transition_geometry import (
    make_transition_endpoint,
    make_transition_operator,
    measure_transition_torsion,
)

NOW = 2_000


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def authority_fixture(identity_ref: str):
    root = Ed25519PrivateKey.generate()
    actor = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id=f"verify-grant:{identity_ref}",
        subject_ref="verification-actor",
        subject_key_id="verification-actor-key",
        subject_public_key=actor.public_key(),
        roles=(ROLE_VERIFICATION_SUBMITTER, ROLE_VERIFICATION_EXECUTOR),
        scopes=(verification_scope(identity_ref),),
        policy_generation=12,
        valid_from=1_000,
        valid_until=5_000,
        issuer_ref="runtime-root",
        issuer_key_id="runtime-root-key",
        issuer_private_key=root,
    )
    return root, actor, grant


def invoke(request, *, root, db_path, now=NOW, capacity=1, max_items=1):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"runtime-root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "12"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    env["ATMAN_VERIFICATION_CAPACITY_UNITS"] = str(capacity)
    env["ATMAN_VERIFICATION_MAX_ADMITTED_ITEMS"] = str(max_items)
    env["ATMAN_VERIFICATION_AGING_QUANTUM"] = "10"
    completed = subprocess.run(
        [sys.executable, "-m", "model.verification_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def hold_gate(identity_ref: str = "agent:runtime-verify"):
    genesis = issue_genesis_receipt(
        identity_ref=identity_ref,
        state_ref="origin",
        branch_ref="main",
        generation=1,
        payload="origin",
    )
    s1 = issue_successor_receipt(genesis, state_ref="s1", payload="one")
    s2 = issue_successor_receipt(s1, state_ref="s2", payload="two")
    s4 = issue_successor_receipt(s2, state_ref="s4", payload="four")
    s5 = issue_successor_receipt(s4, state_ref="s5", payload="five")
    a3 = cross_axis_bind(observe_space(s1, s2), observe_time(s4, s5))

    origin_receipt = issue_genesis_receipt(
        identity_ref=identity_ref,
        state_ref="geometry-origin",
        branch_ref="geometry-origin",
        generation=0,
        payload="origin",
    )
    left_receipt = issue_genesis_receipt(
        identity_ref=identity_ref,
        state_ref="ab",
        branch_ref="ab",
        generation=2,
        payload="left-result",
    )
    right_receipt = issue_genesis_receipt(
        identity_ref=identity_ref,
        state_ref="ba",
        branch_ref="ba",
        generation=2,
        payload="right-result",
    )
    origin = make_transition_endpoint(origin_receipt, context="ctx", authority="auth", effects="effects")
    left = make_transition_endpoint(left_receipt, context="ctx", authority="auth", effects="effects")
    right = make_transition_endpoint(right_receipt, context="ctx", authority="auth", effects="effects")
    op_a = make_transition_operator("A", {"op": "read"})
    op_b = make_transition_operator("B", {"op": "plan"})
    torsion = measure_transition_torsion(origin, op_a, op_b, left, right, measured_at=1_900)
    gate = a3_geometric_gate(a3, torsion=TorsionEvidence(torsion, origin, op_a, op_b, left, right))
    assert gate.decision == "HOLD"
    return gate


def submit_request(gate, actor, grant, *, work_ref: str, evidence: object, now: int, cost=1, priority=0, role=ROLE_VERIFICATION_SUBMITTER):
    _, action = action_submit_verification(
        gate,
        work_ref=work_ref,
        evidence=evidence,
        cost_units=cost,
        priority=priority,
        submitted_at=now,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=role,
        scope=verification_scope(gate.subject_identity_ref),
        action=action,
        signed_at=now,
    )
    return {
        "protocol": VERIFY_PROTOCOL,
        "request_id": f"submit:{work_ref}",
        "operation": "submit_verification_work",
        "payload": {
            "geometry_gate": geometric_observer_to_dict(gate),
            "work_ref": work_ref,
            "evidence": evidence,
            "cost_units": cost,
            "priority": priority,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def schedule_request(request_id="schedule:1", **extra):
    return {
        "protocol": VERIFY_PROTOCOL,
        "request_id": request_id,
        "operation": "schedule_verification",
        "payload": dict(extra),
    }


def evaluate_request(gate, request_id="evaluate:1"):
    return {
        "protocol": VERIFY_PROTOCOL,
        "request_id": request_id,
        "operation": "evaluate_geometric_verification",
        "payload": {"geometry_gate": geometric_observer_to_dict(gate)},
    }


def complete_request(gate, actor, grant, *, work_hash, generation, pressure_hash, decision, evidence, now, actor_ref="verifier:1"):
    _, action = action_complete_verification(
        work_hash=work_hash,
        subject_identity_ref=gate.subject_identity_ref,
        target_gate_hash=gate.gate_hash,
        schedule_generation=generation,
        pressure_hash=pressure_hash,
        decision=decision,
        evidence=evidence,
        actor_ref=actor_ref,
        completed_at=now,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_VERIFICATION_EXECUTOR,
        scope=verification_scope(gate.subject_identity_ref),
        action=action,
        signed_at=now,
    )
    return {
        "protocol": VERIFY_PROTOCOL,
        "request_id": f"complete:{work_hash[:8]}",
        "operation": "complete_verification_work",
        "payload": {
            "work_hash": work_hash,
            "decision": decision,
            "evidence": evidence,
            "actor_ref": actor_ref,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def test_runtime_hold_is_discharged_only_after_completed_pass_across_processes(tmp_path):
    gate = hold_gate()
    root, actor, grant = authority_fixture(gate.subject_identity_ref)
    db_path = tmp_path / "runtime.sqlite3"

    completed, submitted = invoke(
        submit_request(gate, actor, grant, work_ref="torsion-review", evidence={"check": "replay"}, now=NOW),
        root=root,
        db_path=db_path,
        now=NOW,
    )
    assert completed.returncode == 0, submitted
    work_hash = submitted["work"]["work_hash"]

    _, before = invoke(evaluate_request(gate), root=root, db_path=db_path, now=NOW + 1)
    assert before["decision"]["decision"] == "HOLD"
    assert "verification_pending" in before["decision"]["reasons"]

    _, scheduled = invoke(schedule_request(), root=root, db_path=db_path, now=NOW + 2)
    generation = scheduled["schedule_generation"]
    pressure_hash = scheduled["pressure"]["pressure_hash"]
    assert scheduled["pressure"]["admitted_work_hashes"] == [work_hash]

    completion_evidence = {"replayed": True, "compatible": True}
    completed, response = invoke(
        complete_request(
            gate,
            actor,
            grant,
            work_hash=work_hash,
            generation=generation,
            pressure_hash=pressure_hash,
            decision="PASS",
            evidence=completion_evidence,
            now=NOW + 3,
        ),
        root=root,
        db_path=db_path,
        now=NOW + 3,
    )
    assert completed.returncode == 0, response

    _, after = invoke(evaluate_request(gate, "evaluate:after"), root=root, db_path=db_path, now=NOW + 4)
    assert after["decision"]["decision"] == "PASS"
    assert "geometric_hold_discharged_by_completed_verification" in after["decision"]["reasons"]


def test_completed_fail_cannot_turn_geometric_hold_into_pass(tmp_path):
    gate = hold_gate()
    root, actor, grant = authority_fixture(gate.subject_identity_ref)
    db_path = tmp_path / "runtime.sqlite3"
    _, submitted = invoke(submit_request(gate, actor, grant, work_ref="review", evidence="e", now=NOW), root=root, db_path=db_path, now=NOW)
    work_hash = submitted["work"]["work_hash"]
    _, scheduled = invoke(schedule_request(), root=root, db_path=db_path, now=NOW + 1)
    _, completed = invoke(
        complete_request(
            gate,
            actor,
            grant,
            work_hash=work_hash,
            generation=scheduled["schedule_generation"],
            pressure_hash=scheduled["pressure"]["pressure_hash"],
            decision="FAIL",
            evidence={"counterexample": True},
            now=NOW + 2,
        ),
        root=root,
        db_path=db_path,
        now=NOW + 2,
    )
    assert completed["ok"] is True
    _, evaluated = invoke(evaluate_request(gate), root=root, db_path=db_path, now=NOW + 3)
    assert evaluated["decision"]["decision"] == "FAIL"
    assert "verification_result_failed" in evaluated["decision"]["reasons"]


def test_deferred_work_survives_restart_and_blocks_global_pass(tmp_path):
    gate = hold_gate()
    root, actor, grant = authority_fixture(gate.subject_identity_ref)
    db_path = tmp_path / "runtime.sqlite3"
    work_hashes = []
    for index in range(2):
        _, response = invoke(
            submit_request(gate, actor, grant, work_ref=f"review:{index}", evidence={"index": index}, now=NOW + index),
            root=root,
            db_path=db_path,
            now=NOW + index,
        )
        work_hashes.append(response["work"]["work_hash"])

    _, scheduled = invoke(schedule_request(), root=root, db_path=db_path, now=NOW + 5, capacity=1, max_items=1)
    assert len(scheduled["pressure"]["admitted_work_hashes"]) == 1
    assert len(scheduled["pressure"]["deferred_capacity_work_hashes"]) == 1
    admitted = scheduled["pressure"]["admitted_work_hashes"][0]

    _, response = invoke(
        complete_request(
            gate,
            actor,
            grant,
            work_hash=admitted,
            generation=scheduled["schedule_generation"],
            pressure_hash=scheduled["pressure"]["pressure_hash"],
            decision="PASS",
            evidence="ok",
            now=NOW + 6,
        ),
        root=root,
        db_path=db_path,
        now=NOW + 6,
        capacity=1,
        max_items=1,
    )
    assert response["ok"] is True

    # New process, same SQLite file: deferred debt must still be present.
    _, evaluated = invoke(evaluate_request(gate), root=root, db_path=db_path, now=NOW + 7, capacity=1, max_items=1)
    assert evaluated["decision"]["decision"] == "HOLD"
    assert len(evaluated["decision"]["deferred_work_hashes"]) == 1


def test_client_capacity_claim_does_not_override_server_policy(tmp_path):
    gate = hold_gate()
    root, actor, grant = authority_fixture(gate.subject_identity_ref)
    db_path = tmp_path / "runtime.sqlite3"
    for index in range(2):
        invoke(
            submit_request(gate, actor, grant, work_ref=f"capacity:{index}", evidence=index, now=NOW + index),
            root=root,
            db_path=db_path,
            now=NOW + index,
        )
    _, response = invoke(
        schedule_request(capacity_units=999, max_admitted_items=999),
        root=root,
        db_path=db_path,
        now=NOW + 5,
        capacity=1,
        max_items=1,
    )
    assert response["pressure"]["capacity_units"] == 1
    assert len(response["pressure"]["admitted_work_hashes"]) == 1


def test_deferred_work_cannot_be_marked_complete(tmp_path):
    gate = hold_gate()
    root, actor, grant = authority_fixture(gate.subject_identity_ref)
    db_path = tmp_path / "runtime.sqlite3"
    for index in range(2):
        invoke(submit_request(gate, actor, grant, work_ref=f"defer:{index}", evidence=index, now=NOW + index), root=root, db_path=db_path, now=NOW + index)
    _, scheduled = invoke(schedule_request(), root=root, db_path=db_path, now=NOW + 3, capacity=1, max_items=1)
    deferred = scheduled["pressure"]["deferred_capacity_work_hashes"][0]
    completed, response = invoke(
        complete_request(
            gate,
            actor,
            grant,
            work_hash=deferred,
            generation=scheduled["schedule_generation"],
            pressure_hash=scheduled["pressure"]["pressure_hash"],
            decision="PASS",
            evidence="fake-complete",
            now=NOW + 4,
        ),
        root=root,
        db_path=db_path,
        now=NOW + 4,
        capacity=1,
        max_items=1,
    )
    assert completed.returncode == 2
    assert response["error_type"] == "PermissionError"
    assert "not admitted" in response["error"]


def test_wrong_role_cannot_submit_verification_debt(tmp_path):
    gate = hold_gate()
    root, actor, grant = authority_fixture(gate.subject_identity_ref)
    db_path = tmp_path / "runtime.sqlite3"
    request = submit_request(
        gate,
        actor,
        grant,
        work_ref="unauthorized",
        evidence="e",
        now=NOW,
        role=ROLE_VERIFICATION_EXECUTOR,
    )
    completed, response = invoke(request, root=root, db_path=db_path, now=NOW)
    assert completed.returncode == 2
    assert response["error_type"] == "PermissionError"
    assert "required_role_mismatch" in response["error"]
