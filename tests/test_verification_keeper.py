from __future__ import annotations

import json
import os
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
from model.geometric_coherence import GeometricObserverReceipt, _digest as geometry_digest
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
from model.verification_keeper import (
    FINALIZE_OPERATION,
    ROLE_VERIFICATION_KEEPER,
    action_finalize_verification,
)

NOW = 3_000


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def hold_gate(identity_ref="agent:keeper"):
    fields = {
        "observer_id": "A3-GEOMETRY",
        "subject_identity_ref": identity_ref,
        "decision": "HOLD",
        "base_observer_id": "A3",
        "base_observer_verdict": "PASS",
        "policy_hash": "1" * 64,
        "torsion_hash": "2" * 64,
        "torsion_status": "TORSION_DETECTED",
        "curvature_hash": None,
        "curvature_status": None,
        "evidence_refs": ("torsion:test",),
        "reasons": ("semantic_torsion_detected",),
    }
    provisional = GeometricObserverReceipt(**fields, gate_hash="0" * 64)
    gate = GeometricObserverReceipt(**fields, gate_hash=geometry_digest(provisional.material()))
    gate.validate()
    return gate


def authority_fixture(identity_ref: str, roles):
    root = Ed25519PrivateKey.generate()
    actor = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id=f"grant:{identity_ref}:{'-'.join(roles)}",
        subject_ref="verification-actor",
        subject_key_id="verification-actor-key",
        subject_public_key=actor.public_key(),
        roles=tuple(roles),
        scopes=(verification_scope(identity_ref),),
        policy_generation=12,
        valid_from=2_000,
        valid_until=5_000,
        issuer_ref="runtime-root",
        issuer_key_id="runtime-root-key",
        issuer_private_key=root,
    )
    return root, actor, grant


def invoke(request, *, root, db_path, now):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"runtime-root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "12"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    env["ATMAN_VERIFICATION_CAPACITY_UNITS"] = "4"
    env["ATMAN_VERIFICATION_MAX_ADMITTED_ITEMS"] = "4"
    completed = subprocess.run(
        [sys.executable, "-m", "model.verification_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def submit(gate, actor, grant, *, root, db_path, now):
    item, action = action_submit_verification(
        gate,
        work_ref="keeper-review",
        evidence={"replay": "required"},
        cost_units=1,
        priority=1,
        submitted_at=now,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_VERIFICATION_SUBMITTER,
        scope=verification_scope(gate.subject_identity_ref),
        action=action,
        signed_at=now,
    )
    request = {
        "protocol": VERIFY_PROTOCOL,
        "request_id": "submit",
        "operation": "submit_verification_work",
        "payload": {
            "geometry_gate": geometric_observer_to_dict(gate),
            "work_ref": "keeper-review",
            "evidence": {"replay": "required"},
            "cost_units": 1,
            "priority": 1,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    completed, response = invoke(request, root=root, db_path=db_path, now=now)
    assert completed.returncode == 0, response
    assert response["work"]["work_hash"] == item.work_hash
    return item.work_hash


def schedule(*, root, db_path, now):
    request = {
        "protocol": VERIFY_PROTOCOL,
        "request_id": "schedule",
        "operation": "schedule_verification",
        "payload": {},
    }
    completed, response = invoke(request, root=root, db_path=db_path, now=now)
    assert completed.returncode == 0, response
    return response


def preview(gate, *, root, db_path, now):
    request = {
        "protocol": VERIFY_PROTOCOL,
        "request_id": "preview",
        "operation": "evaluate_geometric_verification",
        "payload": {"geometry_gate": geometric_observer_to_dict(gate)},
    }
    completed, response = invoke(request, root=root, db_path=db_path, now=now)
    assert completed.returncode == 0, response
    return response


def complete(gate, actor, grant, *, root, db_path, work_hash, scheduled, now):
    evidence = {"verified": True}
    _, action = action_complete_verification(
        work_hash=work_hash,
        subject_identity_ref=gate.subject_identity_ref,
        target_gate_hash=gate.gate_hash,
        schedule_generation=scheduled["schedule_generation"],
        pressure_hash=scheduled["pressure"]["pressure_hash"],
        decision="PASS",
        evidence=evidence,
        actor_ref="verifier:keeper",
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
    request = {
        "protocol": VERIFY_PROTOCOL,
        "request_id": "complete",
        "operation": "complete_verification_work",
        "payload": {
            "work_hash": work_hash,
            "decision": "PASS",
            "evidence": evidence,
            "actor_ref": "verifier:keeper",
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
    completed, response = invoke(request, root=root, db_path=db_path, now=now)
    assert completed.returncode == 0, response


def finalize_request(gate, actor, grant, preview_response, scheduled, *, now, role=ROLE_VERIFICATION_KEEPER):
    state_hash = preview_response["decision_state_hash"]
    action = action_finalize_verification(
        subject_identity_ref=gate.subject_identity_ref,
        target_gate_hash=gate.gate_hash,
        decision_state_hash=state_hash,
        schedule_generation=scheduled["schedule_generation"],
        pressure_hash=scheduled["pressure"]["pressure_hash"],
        finalized_at=now,
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
        "request_id": "finalize",
        "operation": FINALIZE_OPERATION,
        "payload": {
            "geometry_gate": geometric_observer_to_dict(gate),
            "expected_decision_state_hash": state_hash,
        },
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }


def setup_completed_pass(tmp_path):
    gate = hold_gate()
    root = Ed25519PrivateKey.generate()
    actor = Ed25519PrivateKey.generate()
    roles = (ROLE_VERIFICATION_SUBMITTER, ROLE_VERIFICATION_EXECUTOR, ROLE_VERIFICATION_KEEPER)
    grant = issue_authority_grant(
        grant_id="grant:all",
        subject_ref="verification-actor",
        subject_key_id="verification-actor-key",
        subject_public_key=actor.public_key(),
        roles=roles,
        scopes=(verification_scope(gate.subject_identity_ref),),
        policy_generation=12,
        valid_from=2_000,
        valid_until=5_000,
        issuer_ref="runtime-root",
        issuer_key_id="runtime-root-key",
        issuer_private_key=root,
    )
    db_path = tmp_path / "runtime.sqlite3"
    work_hash = submit(gate, actor, grant, root=root, db_path=db_path, now=NOW)
    scheduled = schedule(root=root, db_path=db_path, now=NOW + 1)
    complete(gate, actor, grant, root=root, db_path=db_path, work_hash=work_hash, scheduled=scheduled, now=NOW + 2)
    return gate, root, actor, grant, db_path, scheduled


def test_keeper_can_finalize_stable_pass_preview_at_later_clock_time(tmp_path):
    gate, root, actor, grant, db_path, scheduled = setup_completed_pass(tmp_path)
    preview_response = preview(gate, root=root, db_path=db_path, now=NOW + 3)
    assert preview_response["decision"]["decision"] == "PASS"

    request = finalize_request(gate, actor, grant, preview_response, scheduled, now=NOW + 10)
    completed, response = invoke(request, root=root, db_path=db_path, now=NOW + 10)
    assert completed.returncode == 0, response
    assert response["finalization"]["decision"] == "PASS"
    assert response["finalization"]["decision_state_hash"] == preview_response["decision_state_hash"]


def test_finalization_rejects_stale_preview_after_verification_state_changes(tmp_path):
    gate = hold_gate()
    root = Ed25519PrivateKey.generate()
    actor = Ed25519PrivateKey.generate()
    roles = (ROLE_VERIFICATION_SUBMITTER, ROLE_VERIFICATION_EXECUTOR, ROLE_VERIFICATION_KEEPER)
    grant = issue_authority_grant(
        grant_id="grant:stale",
        subject_ref="verification-actor",
        subject_key_id="verification-actor-key",
        subject_public_key=actor.public_key(),
        roles=roles,
        scopes=(verification_scope(gate.subject_identity_ref),),
        policy_generation=12,
        valid_from=2_000,
        valid_until=5_000,
        issuer_ref="runtime-root",
        issuer_key_id="runtime-root-key",
        issuer_private_key=root,
    )
    db_path = tmp_path / "runtime.sqlite3"
    work_hash = submit(gate, actor, grant, root=root, db_path=db_path, now=NOW)
    scheduled = schedule(root=root, db_path=db_path, now=NOW + 1)
    stale_preview = preview(gate, root=root, db_path=db_path, now=NOW + 2)
    assert stale_preview["decision"]["decision"] == "HOLD"
    complete(gate, actor, grant, root=root, db_path=db_path, work_hash=work_hash, scheduled=scheduled, now=NOW + 3)

    request = finalize_request(gate, actor, grant, stale_preview, scheduled, now=NOW + 4)
    completed, response = invoke(request, root=root, db_path=db_path, now=NOW + 4)
    assert completed.returncode == 2
    assert response["error_type"] == "PermissionError"
    assert "stale verification decision" in response["error"]


def test_non_keeper_role_cannot_finalize_runtime_decision(tmp_path):
    gate, root, actor, grant, db_path, scheduled = setup_completed_pass(tmp_path)
    preview_response = preview(gate, root=root, db_path=db_path, now=NOW + 3)
    request = finalize_request(
        gate,
        actor,
        grant,
        preview_response,
        scheduled,
        now=NOW + 4,
        role=ROLE_VERIFICATION_EXECUTOR,
    )
    completed, response = invoke(request, root=root, db_path=db_path, now=NOW + 4)
    assert completed.returncode == 2
    assert response["error_type"] == "PermissionError"
    assert "required_role_mismatch" in response["error"]
