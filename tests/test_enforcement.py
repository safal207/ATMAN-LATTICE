import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import model.enforcement as enforcement_module
from model.authority import issue_authority_grant, sign_authorized_action
from model.consumption import empty_authorization_ledger
from model.enforcement import (
    EnforcementContext,
    ROLE_A1,
    ROLE_A2,
    ROLE_A3,
    ROLE_A4,
    ROLE_BRANCH_MERGER,
    ROLE_USE_TOKEN_ISSUER,
    ROLE_USE_TOKEN_REVOKER,
    action_cross_axis,
    action_global_coherence,
    action_issue_use_token,
    action_merge_branches,
    action_observe_space,
    action_observe_time,
    action_revoke_use_token,
    authorization_scope,
    governed_cross_axis_bind,
    governed_global_coherence,
    governed_issue_use_token,
    governed_merge_branches,
    governed_observe_space,
    governed_observe_time,
    governed_revoke_use_token,
    identity_scope,
)
from model.freshness import attest_observer, issue_use_token
from model.lattice import (
    cross_axis_bind,
    digest_payload,
    global_coherence,
    issue_genesis_receipt,
    issue_successor_receipt,
    observe_space,
    observe_time,
)
from model.merge import ConflictResolution, MergeConflict
from model.replay import restore_checkpoint

ATTEST_KEY = b"v0.9-attestation"
TOKEN_KEY = b"v0.9-token"
EVENT_KEY = b"v0.9-event"
ATTEST_KEYS = {"attest-1": ATTEST_KEY}
TOKEN_KEYS = {"token-1": TOKEN_KEY}
EVENT_KEYS = {"event-1": EVENT_KEY}
POLICY_GENERATION = 20


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def authority_for(action, *, role, scope, roles=None, scopes=None, policy_generation=POLICY_GENERATION):
    root = Ed25519PrivateKey.generate()
    subject = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id=f"grant:{role}:{scope}",
        subject_ref="component:governed",
        subject_key_id="component-key-1",
        subject_public_key=subject.public_key(),
        roles=tuple(roles or (role,)),
        scopes=tuple(scopes or (scope,)),
        policy_generation=policy_generation,
        valid_from=1_000,
        valid_until=2_000,
        issuer_ref="authority:root",
        issuer_key_id="root-key-1",
        issuer_private_key=root,
    )
    proof = sign_authorized_action(
        grant,
        private_key=subject,
        role=role,
        scope=scope,
        action=action,
        signed_at=1_200,
    )
    enforcement = EnforcementContext(
        trusted_issuer_keys={"root-key-1": raw_public(root)},
        policy_generation=POLICY_GENERATION,
        now=1_250,
    )
    return grant, proof, enforcement


def identity_chain():
    root = issue_genesis_receipt(
        identity_ref="agent:1",
        state_ref="origin",
        branch_ref="main",
        generation=11,
        payload="origin",
    )
    waking = issue_successor_receipt(root, state_ref="waking", payload="awake")
    dream = issue_successor_receipt(waking, state_ref="dream", payload="dream")
    past = issue_successor_receipt(dream, state_ref="past", payload="past")
    future = issue_successor_receipt(past, state_ref="future", payload="future")
    return root, waking, dream, past, future


def final_observer():
    _, waking, dream, past, future = identity_chain()
    a1 = observe_space(waking, dream)
    a2 = observe_time(past, future)
    a3 = cross_axis_bind(a1, a2)
    return a1, a2, a3, global_coherence((a1, a2, a3))


def signed_attestation():
    _, _, _, a4 = final_observer()
    ctx = {"policy_generation": 3, "tool_scope": ["wallet.transfer"], "limit": 100}
    attestation = attest_observer(
        a4,
        context=ctx,
        verified_at=1_200,
        key_id="attest-1",
        secret=ATTEST_KEY,
    )
    return a4, attestation, ctx


def test_a1_and_a2_require_exact_authority_before_execution():
    _, waking, dream, past, future = identity_chain()

    action = action_observe_space(waking, dream)
    grant, proof, ctx = authority_for(action, role=ROLE_A1, scope=identity_scope("agent:1"))
    a1 = governed_observe_space(waking, dream, grant=grant, proof=proof, enforcement=ctx)
    assert a1.verdict == "PASS"

    action = action_observe_time(past, future)
    grant, proof, ctx = authority_for(action, role=ROLE_A2, scope=identity_scope("agent:1"))
    a2 = governed_observe_time(past, future, grant=grant, proof=proof, enforcement=ctx)
    assert a2.verdict == "PASS"


def test_wrong_but_granted_role_is_stopped_before_observer_runs(monkeypatch):
    _, waking, dream, _, _ = identity_chain()
    action = action_observe_space(waking, dream)
    grant, proof, ctx = authority_for(
        action,
        role=ROLE_A4,
        scope=identity_scope("agent:1"),
        roles=(ROLE_A1, ROLE_A4),
    )

    called = False

    def bomb(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("observer primitive must not execute")

    monkeypatch.setattr(enforcement_module, "observe_space", bomb)
    with pytest.raises(PermissionError, match="required_role_mismatch"):
        governed_observe_space(waking, dream, grant=grant, proof=proof, enforcement=ctx)
    assert called is False


def test_wrong_but_granted_scope_is_rejected_by_operation_gate():
    _, waking, dream, _, _ = identity_chain()
    action = action_observe_space(waking, dream)
    grant, proof, ctx = authority_for(
        action,
        role=ROLE_A1,
        scope=identity_scope("agent:other"),
        scopes=(identity_scope("agent:1"), identity_scope("agent:other")),
    )
    with pytest.raises(PermissionError, match="required_scope_mismatch"):
        governed_observe_space(waking, dream, grant=grant, proof=proof, enforcement=ctx)


def test_a3_and_a4_are_separately_authorized_roles():
    a1, a2, _, _ = final_observer()

    action = action_cross_axis(a1, a2)
    grant, proof, ctx = authority_for(action, role=ROLE_A3, scope=identity_scope("agent:1"))
    a3 = governed_cross_axis_bind(a1, a2, grant=grant, proof=proof, enforcement=ctx)
    assert a3.verdict == "PASS"

    receipts, action = action_global_coherence((a1, a2, a3))
    assert len(receipts) == 3
    grant, proof, ctx = authority_for(action, role=ROLE_A4, scope=identity_scope("agent:1"))
    a4 = governed_global_coherence((a1, a2, a3), grant=grant, proof=proof, enforcement=ctx)
    assert a4.verdict == "PASS"


def test_stale_policy_generation_blocks_execution_even_with_valid_signature():
    _, waking, dream, _, _ = identity_chain()
    action = action_observe_space(waking, dream)
    grant, proof, ctx = authority_for(
        action,
        role=ROLE_A1,
        scope=identity_scope("agent:1"),
        policy_generation=19,
    )
    with pytest.raises(PermissionError, match="stale_authority_policy_generation"):
        governed_observe_space(waking, dream, grant=grant, proof=proof, enforcement=ctx)


def test_use_token_issuance_is_gated_by_exact_issuer_role():
    receipt, attestation, current_context = signed_attestation()
    action = action_issue_use_token(
        attestation,
        receipt,
        current_context=current_context,
        now=1_250,
        ttl_seconds=30,
        token_key_id="token-1",
    )
    grant, proof, ctx = authority_for(
        action,
        role=ROLE_USE_TOKEN_ISSUER,
        scope=authorization_scope("agent:1"),
    )
    token = governed_issue_use_token(
        attestation,
        receipt,
        current_context=current_context,
        now=1_250,
        max_attestation_age_seconds=100,
        attestation_keys=ATTEST_KEYS,
        token_key_id="token-1",
        token_secret=TOKEN_KEY,
        ttl_seconds=30,
        grant=grant,
        proof=proof,
        enforcement=ctx,
    )
    assert token.subject_identity_ref == "agent:1"


def test_revocation_is_gated_by_exact_revoker_role_and_action():
    receipt, attestation, current_context = signed_attestation()
    token = issue_use_token(
        attestation,
        receipt,
        current_context=current_context,
        now=1_250,
        max_attestation_age_seconds=100,
        attestation_keys=ATTEST_KEYS,
        token_key_id="token-1",
        token_secret=TOKEN_KEY,
        ttl_seconds=30,
    )
    ledger = empty_authorization_ledger()
    action = action_revoke_use_token(
        ledger,
        token,
        now=1_260,
        actor_ref="keeper:a4",
        reason_ref="policy:withdraw",
        expected_ledger_generation=0,
    )
    grant, proof, ctx = authority_for(
        action,
        role=ROLE_USE_TOKEN_REVOKER,
        scope=authorization_scope("agent:1"),
    )
    updated, event = governed_revoke_use_token(
        ledger,
        token,
        now=1_260,
        token_keys=TOKEN_KEYS,
        event_keys=EVENT_KEYS,
        expected_ledger_generation=0,
        actor_ref="keeper:a4",
        reason_ref="policy:withdraw",
        event_key_id="event-1",
        event_secret=EVENT_KEY,
        grant=grant,
        proof=proof,
        enforcement=ctx,
    )
    assert updated.generation == 1
    assert event.event_type == "REVOKED"


def merge_fixture():
    _, ancestor, _ = (
        issue_genesis_receipt(
            identity_ref="agent:1",
            state_ref="origin",
            branch_ref="main",
            generation=7,
            payload="origin",
        ),
        None,
        None,
    )
    root = issue_genesis_receipt(
        identity_ref="agent:1",
        state_ref="merge-origin",
        branch_ref="merge-main",
        generation=7,
        payload="merge-origin",
    )
    ancestor = issue_successor_receipt(root, state_ref="checkpoint", payload="checkpoint")
    left_genesis, left_restore = restore_checkpoint(
        ancestor,
        target_branch_ref="future/left",
        target_generation=8,
        replayed_at=1_000,
    )
    right_genesis, right_restore = restore_checkpoint(
        ancestor,
        target_branch_ref="future/right",
        target_generation=8,
        replayed_at=1_001,
    )
    left_head = issue_successor_receipt(left_genesis, state_ref="left-head", payload="left")
    right_head = issue_successor_receipt(right_genesis, state_ref="right-head", payload="right")
    conflict = MergeConflict(
        conflict_ref="policy:route",
        left_digest=digest_payload("left-route"),
        right_digest=digest_payload("right-route"),
    )
    resolution = ConflictResolution(
        conflict_ref=conflict.conflict_ref,
        left_digest=conflict.left_digest,
        right_digest=conflict.right_digest,
        strategy="SYNTHESIZED",
        result_digest=digest_payload("combined-route"),
        reason_ref="decision:merge",
    )
    return ancestor, (left_genesis, left_head), left_restore, (right_genesis, right_head), right_restore, conflict, resolution


def test_merge_is_an_authorized_operation_not_just_a_valid_reconciliation():
    ancestor, left, left_restore, right, right_restore, conflict, resolution = merge_fixture()
    _, _, _, _, action = action_merge_branches(
        ancestor,
        left,
        right,
        target_branch_ref="future/merged",
        target_generation=9,
        merged_payload="merged-state",
        conflicts=(conflict,),
        resolutions=(resolution,),
        merged_at=1_300,
    )
    grant, proof, ctx = authority_for(
        action,
        role=ROLE_BRANCH_MERGER,
        scope=identity_scope("agent:1"),
    )
    target, merge = governed_merge_branches(
        ancestor,
        left,
        left_restore,
        right,
        right_restore,
        target_branch_ref="future/merged",
        target_generation=9,
        merged_payload="merged-state",
        conflicts=(conflict,),
        resolutions=(resolution,),
        merged_at=1_300,
        grant=grant,
        proof=proof,
        enforcement=ctx,
    )
    assert target.branch_ref == "future/merged"
    assert merge.target_genesis_receipt_hash == target.receipt_hash
