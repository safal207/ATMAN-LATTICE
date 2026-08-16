from __future__ import annotations

import json
import os
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import model.enforcement as enforcement_module
from model.authority import issue_authority_grant, sign_authorized_action
from model.enforcement import ROLE_A1, ROLE_A4, action_observe_space, identity_scope
from model.lattice import issue_genesis_receipt, issue_successor_receipt
from model.runtime_protocol import identity_receipt_to_dict, make_runtime_request


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def runtime_fixture(*, roles=(ROLE_A1,), policy_generation=12):
    root_key = Ed25519PrivateKey.generate()
    observer_key = Ed25519PrivateKey.generate()
    genesis = issue_genesis_receipt(
        identity_ref="agent:runtime",
        state_ref="origin",
        branch_ref="main",
        generation=4,
        payload="origin",
    )
    left = issue_successor_receipt(genesis, state_ref="waking", payload="awake")
    right = issue_successor_receipt(left, state_ref="dream", payload="dream")
    grant = issue_authority_grant(
        grant_id="grant:runtime:a1",
        subject_ref="runtime-observer:a1",
        subject_key_id="runtime-observer-key",
        subject_public_key=observer_key.public_key(),
        roles=tuple(roles),
        scopes=(identity_scope(left.identity_ref),),
        policy_generation=policy_generation,
        valid_from=1_000,
        valid_until=2_000,
        issuer_ref="runtime-root",
        issuer_key_id="runtime-root-key",
        issuer_private_key=root_key,
    )
    return root_key, observer_key, left, right, grant


def invoke(request, *, root_key, policy_generation=12, now=1_250):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({
        "runtime-root-key": raw_public(root_key).hex(),
    })
    env["ATMAN_POLICY_GENERATION"] = str(policy_generation)
    env["ATMAN_RUNTIME_NOW"] = str(now)
    completed = subprocess.run(
        [sys.executable, "-m", "model.runtime_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def signed_request(*, role=ROLE_A1, roles=(ROLE_A1,), policy_generation=12):
    root_key, observer_key, left, right, grant = runtime_fixture(
        roles=roles,
        policy_generation=policy_generation,
    )
    action = action_observe_space(left, right)
    proof = sign_authorized_action(
        grant,
        private_key=observer_key,
        role=role,
        scope=identity_scope(left.identity_ref),
        action=action,
        signed_at=1_200,
    )
    request = make_runtime_request(
        request_id="request:1",
        operation="observe_space",
        payload={
            "left": identity_receipt_to_dict(left),
            "right": identity_receipt_to_dict(right),
        },
        grant=grant,
        proof=proof,
    )
    return root_key, request


def test_runtime_process_executes_valid_authorized_observer():
    root_key, request = signed_request()
    completed, response = invoke(request, root_key=root_key)
    assert completed.returncode == 0
    assert response["ok"] is True
    assert response["request_id"] == "request:1"
    assert response["receipt"]["observer_id"] == "A1"
    assert response["receipt"]["verdict"] == "PASS"


def test_runtime_rejects_granted_but_wrong_role_before_primitive():
    root_key, request = signed_request(role=ROLE_A4, roles=(ROLE_A1, ROLE_A4))
    completed, response = invoke(request, root_key=root_key)
    assert completed.returncode == 2
    assert response["ok"] is False
    assert response["error_type"] == "PermissionError"
    assert "required_role_mismatch" in response["error"]


def test_runtime_uses_server_policy_generation_not_client_claim():
    root_key, request = signed_request(policy_generation=12)
    request["policy_generation"] = 12
    completed, response = invoke(request, root_key=root_key, policy_generation=13)
    assert completed.returncode == 2
    assert response["ok"] is False
    assert "stale_authority_policy_generation" in response["error"]


def test_request_cannot_inject_trusted_root_configuration():
    real_root, request = signed_request()
    attacker_root = Ed25519PrivateKey.generate()
    request["trusted_issuer_keys"] = {
        "runtime-root-key": raw_public(real_root).hex(),
    }
    completed, response = invoke(request, root_key=attacker_root)
    assert completed.returncode == 2
    assert response["ok"] is False
    assert "invalid_grant_signature" in response["error"]


def test_client_monkeypatch_does_not_cross_process_boundary(monkeypatch):
    root_key, request = signed_request()

    def bomb(*args, **kwargs):
        raise AssertionError("client-side primitive must not execute")

    monkeypatch.setattr(enforcement_module, "governed_observe_space", bomb)
    completed, response = invoke(request, root_key=root_key)
    assert completed.returncode == 0
    assert response["ok"] is True
    assert response["receipt"]["observer_id"] == "A1"
