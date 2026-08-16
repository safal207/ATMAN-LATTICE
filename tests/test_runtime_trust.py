from __future__ import annotations

import json
import os
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
from model.enforcement import ROLE_A1, action_observe_space, identity_scope
from model.lattice import issue_genesis_receipt, issue_successor_receipt
from model.runtime_governance import make_trust_policy_request, make_trust_rotation_request
from model.runtime_protocol import identity_receipt_to_dict, make_runtime_request
from model.trust_root import create_bootstrap_policy, sign_trust_transition

NOW = 1_250


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def invoke(request, *, bootstrap_roots, db_path, threshold=2, now=NOW):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({
        key_id: raw_public(key).hex() for key_id, key in bootstrap_roots.items()
    })
    env["ATMAN_POLICY_GENERATION"] = "12"
    env["ATMAN_TRUST_THRESHOLD"] = str(threshold)
    env["ATMAN_TRUST_BOOTSTRAP_ACTIVATED_AT"] = "100"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_RUNTIME_DB"] = str(db_path)
    completed = subprocess.run(
        [sys.executable, "-m", "model.runtime_worker"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def bootstrap_fixture():
    roots = {f"root-{i}": Ed25519PrivateKey.generate() for i in range(1, 4)}
    current = create_bootstrap_policy(
        {key_id: raw_public(key) for key_id, key in roots.items()},
        generation=12,
        threshold=2,
        activated_at=100,
    )
    next_keys = {f"next-{i}": Ed25519PrivateKey.generate() for i in range(1, 3)}
    next_roots = {key_id: raw_public(key) for key_id, key in next_keys.items()}
    return roots, current, next_keys, next_roots


def approvals(current, roots, next_roots):
    return tuple(
        sign_trust_transition(
            current,
            signer_key_id=key_id,
            signer_private_key=roots[key_id],
            next_roots=next_roots,
            next_threshold=2,
            reason_ref="reason:runtime-rotation",
            transitioned_at=NOW,
            signed_at=1_240,
        )
        for key_id in ("root-1", "root-2")
    )


def test_runtime_rejects_rotation_without_current_quorum(tmp_path):
    roots, current, _, next_roots = bootstrap_fixture()
    one = approvals(current, roots, next_roots)[:1]
    request = make_trust_rotation_request(
        request_id="trust:insufficient",
        next_roots=next_roots,
        next_threshold=2,
        reason_ref="reason:runtime-rotation",
        approvals=one,
    )
    completed, response = invoke(
        request,
        bootstrap_roots=roots,
        db_path=tmp_path / "trust.sqlite3",
    )
    assert completed.returncode == 2
    assert response["protocol"] == "ATMAN-TRUST/1.2"
    assert "insufficient trust-root quorum" in response["error"]


def test_runtime_rotation_persists_and_old_environment_cannot_roll_it_back(tmp_path):
    roots, current, next_keys, next_roots = bootstrap_fixture()
    db_path = tmp_path / "trust.sqlite3"
    rotate = make_trust_rotation_request(
        request_id="trust:rotate",
        next_roots=next_roots,
        next_threshold=2,
        reason_ref="reason:runtime-rotation",
        approvals=approvals(current, roots, next_roots),
    )
    completed, response = invoke(rotate, bootstrap_roots=roots, db_path=db_path)
    assert completed.returncode == 0, response
    assert response["policy"]["generation"] == 13
    assert response["policy"]["previous_policy_hash"] == current.policy_hash
    assert response["transition"]["required_threshold"] == 2

    query = make_trust_policy_request(request_id="trust:get")
    completed, after_restart = invoke(query, bootstrap_roots=roots, db_path=db_path)
    assert completed.returncode == 0, after_restart
    assert after_restart["policy"]["generation"] == 13
    assert {item["key_id"] for item in after_restart["policy"]["roots"]} == set(next_keys)


def _observer_request(*, root_key, root_key_id, policy_generation):
    actor = Ed25519PrivateKey.generate()
    genesis = issue_genesis_receipt(
        identity_ref="agent:trust-evolution",
        state_ref="origin",
        branch_ref="main",
        generation=1,
        payload="origin",
    )
    left = issue_successor_receipt(genesis, state_ref="waking", payload="awake")
    right = issue_successor_receipt(left, state_ref="dream", payload="dream")
    grant = issue_authority_grant(
        grant_id=f"grant:{root_key_id}",
        subject_ref="observer:a1",
        subject_key_id="observer-key",
        subject_public_key=actor.public_key(),
        roles=(ROLE_A1,),
        scopes=(identity_scope(left.identity_ref),),
        policy_generation=policy_generation,
        valid_from=1_000,
        valid_until=2_000,
        issuer_ref=f"issuer:{root_key_id}",
        issuer_key_id=root_key_id,
        issuer_private_key=root_key,
    )
    action = action_observe_space(left, right)
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_A1,
        scope=identity_scope(left.identity_ref),
        action=action,
        signed_at=1_245,
    )
    return make_runtime_request(
        request_id=f"observe:{root_key_id}",
        operation="observe_space",
        payload={
            "left": identity_receipt_to_dict(left),
            "right": identity_receipt_to_dict(right),
        },
        grant=grant,
        proof=proof,
    )


def test_rotated_policy_rejects_old_root_and_accepts_new_root(tmp_path):
    roots, current, next_keys, next_roots = bootstrap_fixture()
    db_path = tmp_path / "trust.sqlite3"
    rotate = make_trust_rotation_request(
        request_id="trust:rotate",
        next_roots=next_roots,
        next_threshold=2,
        reason_ref="reason:runtime-rotation",
        approvals=approvals(current, roots, next_roots),
    )
    completed, response = invoke(rotate, bootstrap_roots=roots, db_path=db_path)
    assert completed.returncode == 0, response

    old_request = _observer_request(
        root_key=roots["root-1"],
        root_key_id="root-1",
        policy_generation=13,
    )
    completed, rejected = invoke(old_request, bootstrap_roots=roots, db_path=db_path)
    assert completed.returncode == 2
    assert "untrusted_grant_issuer" in rejected["error"]

    new_request = _observer_request(
        root_key=next_keys["next-1"],
        root_key_id="next-1",
        policy_generation=13,
    )
    completed, accepted = invoke(new_request, bootstrap_roots=roots, db_path=db_path)
    assert completed.returncode == 0, accepted
    assert accepted["receipt"]["observer_id"] == "A1"
    assert accepted["receipt"]["verdict"] == "PASS"


def test_rotation_replay_cannot_advance_policy_twice(tmp_path):
    roots, current, _, next_roots = bootstrap_fixture()
    db_path = tmp_path / "trust.sqlite3"
    rotate = make_trust_rotation_request(
        request_id="trust:rotate",
        next_roots=next_roots,
        next_threshold=2,
        reason_ref="reason:runtime-rotation",
        approvals=approvals(current, roots, next_roots),
    )
    first_completed, first = invoke(rotate, bootstrap_roots=roots, db_path=db_path)
    assert first_completed.returncode == 0, first
    second_completed, second = invoke(rotate, bootstrap_roots=roots, db_path=db_path)
    assert second_completed.returncode == 2
    assert "stale policy" in second["error"] or "different transition" in second["error"]

    query = make_trust_policy_request(request_id="trust:get")
    completed, state = invoke(query, bootstrap_roots=roots, db_path=db_path)
    assert completed.returncode == 0
    assert state["policy"]["generation"] == 13
