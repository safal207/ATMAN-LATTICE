from dataclasses import replace

import pytest

from model.consumption import (
    consume_use_token,
    digest_use_token,
    empty_authorization_ledger,
    revoke_use_token,
    verify_authorization_ledger,
)
from model.freshness import attest_observer, issue_use_token
from model.lattice import (
    cross_axis_bind,
    global_coherence,
    issue_genesis_receipt,
    issue_successor_receipt,
    observe_space,
    observe_time,
)

ATTEST_KEY = b"attestation-secret-v0.7"
TOKEN_KEY = b"use-token-secret-v0.7"
EVENT_KEY = b"authorization-event-secret-v0.7"
ATTEST_KEYS = {"observer-key-1": ATTEST_KEY}
TOKEN_KEYS = {"use-key-1": TOKEN_KEY}
EVENT_KEYS = {"event-key-1": EVENT_KEY}


def context(policy_generation=3):
    return {
        "policy_generation": policy_generation,
        "tool_scope": ["wallet.transfer"],
        "limit": 100,
    }


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


def token(*, issued_at=1_020, ttl_seconds=30):
    receipt = final_observer()
    ctx = context()
    attestation = attest_observer(
        receipt,
        context=ctx,
        verified_at=1_000,
        key_id="observer-key-1",
        secret=ATTEST_KEY,
    )
    use_token = issue_use_token(
        attestation,
        receipt,
        current_context=ctx,
        now=issued_at,
        max_attestation_age_seconds=60,
        attestation_keys=ATTEST_KEYS,
        token_key_id="use-key-1",
        token_secret=TOKEN_KEY,
        ttl_seconds=ttl_seconds,
    )
    return use_token, ctx


def consume(ledger, use_token, ctx, *, now=1_025, expected_generation=None):
    if expected_generation is None:
        expected_generation = ledger.generation
    return consume_use_token(
        ledger,
        use_token,
        current_context=ctx,
        now=now,
        token_keys=TOKEN_KEYS,
        event_keys=EVENT_KEYS,
        expected_ledger_generation=expected_generation,
        actor_ref="executor:wallet",
        reason_ref="action:transfer-1",
        event_key_id="event-key-1",
        event_secret=EVENT_KEY,
    )


def revoke(ledger, use_token, *, now=1_024, expected_generation=None):
    if expected_generation is None:
        expected_generation = ledger.generation
    return revoke_use_token(
        ledger,
        use_token,
        now=now,
        token_keys=TOKEN_KEYS,
        event_keys=EVENT_KEYS,
        expected_ledger_generation=expected_generation,
        actor_ref="policy:keeper",
        reason_ref="revocation:policy-change",
        event_key_id="event-key-1",
        event_secret=EVENT_KEY,
    )


def test_valid_use_token_can_be_consumed_once():
    use_token, ctx = token()
    ledger = empty_authorization_ledger()

    ledger, event = consume(ledger, use_token, ctx)

    assert event.event_type == "CONSUMED"
    assert event.token_digest == digest_use_token(use_token)
    assert ledger.generation == 1
    assert ledger.head_event_hash == event.event_hash
    valid, limitations = verify_authorization_ledger(ledger, event_keys=EVENT_KEYS)
    assert valid is True
    assert limitations == ()


def test_replay_of_consumed_token_is_rejected():
    use_token, ctx = token()
    ledger, _ = consume(empty_authorization_ledger(), use_token, ctx)

    with pytest.raises(ValueError, match="token_already_consumed"):
        consume(ledger, use_token, ctx, now=1_026)


def test_revoked_token_cannot_be_consumed():
    use_token, ctx = token()
    ledger, event = revoke(empty_authorization_ledger(), use_token)
    assert event.event_type == "REVOKED"

    with pytest.raises(ValueError, match="token_already_revoked"):
        consume(ledger, use_token, ctx, now=1_025)


def test_consumed_token_cannot_be_retroactively_revoked():
    use_token, ctx = token()
    ledger, _ = consume(empty_authorization_ledger(), use_token, ctx)

    with pytest.raises(ValueError, match="token_already_consumed"):
        revoke(ledger, use_token, now=1_026)


def test_stale_ledger_generation_is_rejected_before_second_token_append():
    first, ctx = token(issued_at=1_020)
    second, _ = token(issued_at=1_021)
    ledger, _ = consume(empty_authorization_ledger(), first, ctx, now=1_025)

    with pytest.raises(ValueError, match="stale_authorization_ledger"):
        consume(ledger, second, ctx, now=1_026, expected_generation=0)


def test_revocation_targets_exact_authentic_token_even_if_context_has_changed():
    use_token, _ = token()
    ledger, event = revoke(empty_authorization_ledger(), use_token)

    assert event.event_type == "REVOKED"
    assert event.context_digest == use_token.context_digest
    valid, limitations = verify_authorization_ledger(ledger, event_keys=EVENT_KEYS)
    assert valid is True
    assert limitations == ()


def test_authorization_event_tamper_is_detected():
    use_token, ctx = token()
    ledger, event = consume(empty_authorization_ledger(), use_token, ctx)
    tampered = replace(event, reason_ref="action:tampered")
    tampered_ledger = replace(
        ledger,
        events=(tampered,),
        head_event_hash=tampered.event_hash,
    )

    valid, limitations = verify_authorization_ledger(tampered_ledger, event_keys=EVENT_KEYS)
    assert valid is False
    assert "invalid_event:0" in limitations


def test_tampered_use_token_cannot_be_revoked_as_if_authentic():
    use_token, _ = token()
    tampered = replace(use_token, expires_at=use_token.expires_at + 60)

    with pytest.raises(ValueError, match="invalid_use_token_mac"):
        revoke(empty_authorization_ledger(), tampered)
