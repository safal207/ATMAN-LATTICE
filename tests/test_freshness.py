from dataclasses import replace

from model.freshness import (
    attest_observer,
    digest_observer_receipt,
    issue_use_token,
    verify_attestation,
    verify_use_token,
)
from model.lattice import (
    cross_axis_bind,
    global_coherence,
    issue_genesis_receipt,
    issue_successor_receipt,
    observe_space,
    observe_time,
)

ATTEST_KEY = b"attestation-secret-v0.4"
TOKEN_KEY = b"use-token-secret-v0.4"
ATTEST_KEYS = {"observer-key-1": ATTEST_KEY}
TOKEN_KEYS = {"use-key-1": TOKEN_KEY}


def final_observer():
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
    a1 = observe_space(waking, dream)
    a2 = observe_time(past, future)
    a3 = cross_axis_bind(a1, a2)
    return global_coherence((a1, a2, a3))


def context(policy_generation=3):
    return {
        "policy_generation": policy_generation,
        "tool_scope": ["wallet.transfer"],
        "limit": 100,
    }


def signed_attestation(*, verified_at=1_000, ctx=None):
    receipt = final_observer()
    ctx = context() if ctx is None else ctx
    attestation = attest_observer(
        receipt,
        context=ctx,
        verified_at=verified_at,
        key_id="observer-key-1",
        secret=ATTEST_KEY,
    )
    return receipt, attestation, ctx


def test_valid_signed_attestation_passes():
    receipt, attestation, ctx = signed_attestation()
    valid, limitations = verify_attestation(
        attestation,
        receipt,
        current_context=ctx,
        now=1_020,
        max_age_seconds=60,
        keys=ATTEST_KEYS,
    )
    assert valid is True
    assert limitations == ()


def test_attestation_rejects_observer_receipt_tamper():
    receipt, attestation, ctx = signed_attestation()
    tampered = replace(receipt, generation=receipt.generation + 1)
    valid, limitations = verify_attestation(
        attestation,
        tampered,
        current_context=ctx,
        now=1_020,
        max_age_seconds=60,
        keys=ATTEST_KEYS,
    )
    assert valid is False
    assert "observer_receipt_digest_mismatch" in limitations
    assert "generation_mismatch" in limitations


def test_stale_attestation_cannot_authorize_use():
    receipt, attestation, ctx = signed_attestation(verified_at=1_000)
    valid, limitations = verify_attestation(
        attestation,
        receipt,
        current_context=ctx,
        now=1_061,
        max_age_seconds=60,
        keys=ATTEST_KEYS,
    )
    assert valid is False
    assert "stale_attestation" in limitations


def test_context_change_after_verification_invalidates_attestation():
    receipt, attestation, _ = signed_attestation(ctx=context(policy_generation=3))
    valid, limitations = verify_attestation(
        attestation,
        receipt,
        current_context=context(policy_generation=4),
        now=1_020,
        max_age_seconds=60,
        keys=ATTEST_KEYS,
    )
    assert valid is False
    assert "context_mismatch" in limitations


def test_use_token_is_bound_to_exact_context_and_observer_receipt():
    receipt, attestation, ctx = signed_attestation()
    token = issue_use_token(
        attestation,
        receipt,
        current_context=ctx,
        now=1_020,
        max_attestation_age_seconds=60,
        attestation_keys=ATTEST_KEYS,
        token_key_id="use-key-1",
        token_secret=TOKEN_KEY,
        ttl_seconds=15,
    )

    valid, limitations = verify_use_token(
        token,
        current_context=ctx,
        now=1_025,
        token_keys=TOKEN_KEYS,
        expected_observer_receipt_digest=digest_observer_receipt(receipt),
    )
    assert valid is True
    assert limitations == ()

    valid, limitations = verify_use_token(
        token,
        current_context=context(policy_generation=4),
        now=1_025,
        token_keys=TOKEN_KEYS,
        expected_observer_receipt_digest=digest_observer_receipt(receipt),
    )
    assert valid is False
    assert "context_mismatch" in limitations


def test_expired_use_token_is_rejected():
    receipt, attestation, ctx = signed_attestation()
    token = issue_use_token(
        attestation,
        receipt,
        current_context=ctx,
        now=1_020,
        max_attestation_age_seconds=60,
        attestation_keys=ATTEST_KEYS,
        token_key_id="use-key-1",
        token_secret=TOKEN_KEY,
        ttl_seconds=15,
    )
    valid, limitations = verify_use_token(
        token,
        current_context=ctx,
        now=1_036,
        token_keys=TOKEN_KEYS,
    )
    assert valid is False
    assert "token_expired" in limitations


def test_use_token_tamper_is_detected():
    receipt, attestation, ctx = signed_attestation()
    token = issue_use_token(
        attestation,
        receipt,
        current_context=ctx,
        now=1_020,
        max_attestation_age_seconds=60,
        attestation_keys=ATTEST_KEYS,
        token_key_id="use-key-1",
        token_secret=TOKEN_KEY,
        ttl_seconds=15,
    )
    tampered = replace(token, expires_at=token.expires_at + 60)
    valid, limitations = verify_use_token(
        tampered,
        current_context=ctx,
        now=1_025,
        token_keys=TOKEN_KEYS,
    )
    assert valid is False
    assert "invalid_use_token_mac" in limitations
