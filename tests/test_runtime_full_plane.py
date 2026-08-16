from __future__ import annotations

import json
import os
import subprocess
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import issue_authority_grant, sign_authorized_action
from model.consumption import empty_authorization_ledger
from model.enforcement import (
    ROLE_BRANCH_MERGER,
    ROLE_USE_TOKEN_CONSUMER,
    ROLE_USE_TOKEN_ISSUER,
    ROLE_USE_TOKEN_REVOKER,
    action_consume_use_token,
    action_issue_use_token,
    action_merge_branches,
    action_revoke_use_token,
    authorization_scope,
    identity_scope,
)
from model.freshness import attest_observer, verify_use_token
from model.lattice import issue_genesis_receipt, issue_successor_receipt, observe_space
from model.replay import restore_checkpoint
from model.runtime_protocol import (
    identity_receipt_to_dict,
    make_runtime_request,
    observer_attestation_to_dict,
    observer_receipt_to_dict,
    restore_receipt_to_dict,
    use_token_from_dict,
    use_token_to_dict,
)
from model.runtime_store import read_authorization_ledger

NOW = 1_250
ATTESTATION_SECRET = b"runtime-attestation-secret"
TOKEN_SECRET = b"runtime-token-secret"
EVENT_SECRET = b"runtime-event-secret"


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def authority_fixture(identity_ref: str, roles: tuple[str, ...], scope: str):
    root = Ed25519PrivateKey.generate()
    actor = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id=f"grant:{identity_ref}",
        subject_ref="runtime-actor",
        subject_key_id="runtime-actor-key",
        subject_public_key=actor.public_key(),
        roles=roles,
        scopes=(scope,),
        policy_generation=12,
        valid_from=1_000,
        valid_until=2_000,
        issuer_ref="runtime-root",
        issuer_key_id="runtime-root-key",
        issuer_private_key=root,
    )
    return root, actor, grant


def invoke(request, *, root, db_path, now=NOW):
    env = os.environ.copy()
    env["ATMAN_TRUSTED_ISSUER_KEYS"] = json.dumps({"runtime-root-key": raw_public(root).hex()})
    env["ATMAN_POLICY_GENERATION"] = "12"
    env["ATMAN_RUNTIME_NOW"] = str(now)
    env["ATMAN_ATTESTATION_KEYS"] = json.dumps({"attest-key": ATTESTATION_SECRET.hex()})
    env["ATMAN_TOKEN_KEYS"] = json.dumps({"token-key": TOKEN_SECRET.hex()})
    env["ATMAN_EVENT_KEYS"] = json.dumps({"event-key": EVENT_SECRET.hex()})
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


def issuance_fixture():
    genesis = issue_genesis_receipt(
        identity_ref="agent:full-plane",
        state_ref="origin",
        branch_ref="main",
        generation=5,
        payload="origin",
    )
    left = issue_successor_receipt(genesis, state_ref="waking", payload="awake")
    right = issue_successor_receipt(left, state_ref="dream", payload="dream")
    receipt = observe_space(left, right)
    context = {"tool_policy": "v1", "workspace": "agent:full-plane"}
    attestation = attest_observer(
        receipt,
        context=context,
        verified_at=1_200,
        key_id="attest-key",
        secret=ATTESTATION_SECRET,
    )
    roles = (
        ROLE_USE_TOKEN_ISSUER,
        ROLE_USE_TOKEN_CONSUMER,
        ROLE_USE_TOKEN_REVOKER,
    )
    root, actor, grant = authority_fixture(
        receipt.subject_identity_ref,
        roles,
        authorization_scope(receipt.subject_identity_ref),
    )
    return root, actor, grant, receipt, attestation, context


def issue_token_via_runtime(tmp_path):
    root, actor, grant, receipt, attestation, context = issuance_fixture()
    action = action_issue_use_token(
        attestation,
        receipt,
        current_context=context,
        now=NOW,
        ttl_seconds=60,
        token_key_id="token-key",
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_USE_TOKEN_ISSUER,
        scope=authorization_scope(receipt.subject_identity_ref),
        action=action,
        signed_at=1_220,
    )
    request = make_runtime_request(
        request_id="issue:1",
        operation="issue_use_token",
        payload={
            "attestation": observer_attestation_to_dict(attestation),
            "receipt": observer_receipt_to_dict(receipt),
            "current_context": context,
            "max_attestation_age_seconds": 100,
            "token_key_id": "token-key",
            "ttl_seconds": 60,
            "token_secret": "client-must-not-control-this",
        },
        grant=grant,
        proof=proof,
    )
    db_path = tmp_path / "runtime.sqlite3"
    completed, response = invoke(request, root=root, db_path=db_path)
    assert completed.returncode == 0, response
    assert response["ok"] is True
    token = use_token_from_dict(response["token"])
    valid, limitations = verify_use_token(
        token,
        current_context=context,
        now=NOW,
        token_keys={"token-key": TOKEN_SECRET},
    )
    assert valid is True
    assert limitations == ()
    return root, actor, grant, token, context, db_path


def test_runtime_issues_capability_with_server_owned_token_key(tmp_path):
    _, _, _, token, _, _ = issue_token_via_runtime(tmp_path)
    valid, _ = verify_use_token(
        token,
        current_context={"tool_policy": "v1", "workspace": "agent:full-plane"},
        now=NOW,
        token_keys={"token-key": b"attacker-secret"},
    )
    assert valid is False


def test_runtime_consumption_is_atomic_across_processes(tmp_path):
    root, actor, grant, token, context, db_path = issue_token_via_runtime(tmp_path)
    empty = empty_authorization_ledger()
    action = action_consume_use_token(
        empty,
        token,
        current_context=context,
        now=NOW,
        actor_ref="tool:executor",
        reason_ref="reason:first-use",
        expected_ledger_generation=0,
    )
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_USE_TOKEN_CONSUMER,
        scope=authorization_scope(token.subject_identity_ref),
        action=action,
        signed_at=1_230,
    )
    request = make_runtime_request(
        request_id="consume:1",
        operation="consume_use_token",
        payload={
            "token": use_token_to_dict(token),
            "current_context": context,
            "expected_ledger_generation": 0,
            "actor_ref": "tool:executor",
            "reason_ref": "reason:first-use",
            "event_key_id": "event-key",
        },
        grant=grant,
        proof=proof,
    )

    first_completed, first = invoke(request, root=root, db_path=db_path)
    assert first_completed.returncode == 0, first
    assert first["event"]["event_type"] == "CONSUMED"
    assert first["ledger"]["generation"] == 1

    second_completed, second = invoke(request, root=root, db_path=db_path)
    assert second_completed.returncode == 2
    assert second["ok"] is False
    assert "action_digest_mismatch" in second["error"] or "token_already_consumed" in second["error"]

    stored = read_authorization_ledger(str(db_path), token.subject_identity_ref)
    assert stored.generation == 1
    assert len(stored.events) == 1
    assert stored.events[0].event_type == "CONSUMED"


def test_runtime_revocation_blocks_later_consumption(tmp_path):
    root, actor, grant, token, context, db_path = issue_token_via_runtime(tmp_path)
    empty = empty_authorization_ledger()
    revoke_action = action_revoke_use_token(
        empty,
        token,
        now=NOW,
        actor_ref="keeper:a4",
        reason_ref="reason:policy-change",
        expected_ledger_generation=0,
    )
    revoke_proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_USE_TOKEN_REVOKER,
        scope=authorization_scope(token.subject_identity_ref),
        action=revoke_action,
        signed_at=1_230,
    )
    revoke_request = make_runtime_request(
        request_id="revoke:1",
        operation="revoke_use_token",
        payload={
            "token": use_token_to_dict(token),
            "expected_ledger_generation": 0,
            "actor_ref": "keeper:a4",
            "reason_ref": "reason:policy-change",
            "event_key_id": "event-key",
        },
        grant=grant,
        proof=revoke_proof,
    )
    completed, revoked = invoke(revoke_request, root=root, db_path=db_path)
    assert completed.returncode == 0, revoked
    assert revoked["event"]["event_type"] == "REVOKED"

    stored = read_authorization_ledger(str(db_path), token.subject_identity_ref)
    consume_action = action_consume_use_token(
        stored,
        token,
        current_context=context,
        now=NOW,
        actor_ref="tool:executor",
        reason_ref="reason:late-use",
        expected_ledger_generation=1,
    )
    consume_proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_USE_TOKEN_CONSUMER,
        scope=authorization_scope(token.subject_identity_ref),
        action=consume_action,
        signed_at=1_235,
    )
    consume_request = make_runtime_request(
        request_id="consume:after-revoke",
        operation="consume_use_token",
        payload={
            "token": use_token_to_dict(token),
            "current_context": context,
            "expected_ledger_generation": 1,
            "actor_ref": "tool:executor",
            "reason_ref": "reason:late-use",
            "event_key_id": "event-key",
        },
        grant=grant,
        proof=consume_proof,
    )
    completed, rejected = invoke(consume_request, root=root, db_path=db_path)
    assert completed.returncode == 2
    assert "token_already_revoked" in rejected["error"]


def test_runtime_merges_two_proven_futures_inside_boundary(tmp_path):
    ancestor = issue_genesis_receipt(
        identity_ref="agent:merge-runtime",
        state_ref="ancestor",
        branch_ref="main",
        generation=1,
        payload="ancestor",
    )
    left, left_restore = restore_checkpoint(
        ancestor,
        target_branch_ref="left",
        target_generation=2,
        replayed_at=1_100,
    )
    right, right_restore = restore_checkpoint(
        ancestor,
        target_branch_ref="right",
        target_generation=3,
        replayed_at=1_110,
    )
    root, actor, grant = authority_fixture(
        ancestor.identity_ref,
        (ROLE_BRANCH_MERGER,),
        identity_scope(ancestor.identity_ref),
    )
    action_parts = action_merge_branches(
        ancestor,
        (left,),
        (right,),
        target_branch_ref="merged",
        target_generation=4,
        merged_payload="merged-state",
        conflicts=(),
        resolutions=(),
        merged_at=NOW,
    )
    action = action_parts[-1]
    proof = sign_authorized_action(
        grant,
        private_key=actor,
        role=ROLE_BRANCH_MERGER,
        scope=identity_scope(ancestor.identity_ref),
        action=action,
        signed_at=1_240,
    )
    request = make_runtime_request(
        request_id="merge:1",
        operation="merge_branches",
        payload={
            "ancestor": identity_receipt_to_dict(ancestor),
            "left_chain": [identity_receipt_to_dict(left)],
            "left_restore": restore_receipt_to_dict(left_restore),
            "right_chain": [identity_receipt_to_dict(right)],
            "right_restore": restore_receipt_to_dict(right_restore),
            "target_branch_ref": "merged",
            "target_generation": 4,
            "merged_payload": "merged-state",
            "conflicts": [],
            "resolutions": [],
        },
        grant=grant,
        proof=proof,
    )
    completed, response = invoke(request, root=root, db_path=tmp_path / "merge.sqlite3")
    assert completed.returncode == 0, response
    assert response["ok"] is True
    assert response["target"]["branch_ref"] == "merged"
    assert response["target"]["generation"] == 4
    assert response["merge"]["left_branch_ref"] == "left"
    assert response["merge"]["right_branch_ref"] == "right"
