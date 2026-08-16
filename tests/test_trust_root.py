from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.trust_root import (
    apply_trust_transition,
    create_bootstrap_policy,
    sign_trust_transition,
)


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def fixture():
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


def approval(current, roots, signer_key_id, next_roots):
    return sign_trust_transition(
        current,
        signer_key_id=signer_key_id,
        signer_private_key=roots[signer_key_id],
        next_roots=next_roots,
        next_threshold=2,
        reason_ref="reason:scheduled-rotation",
        transitioned_at=1_250,
        signed_at=1_240,
    )


def test_single_root_cannot_rotate_two_of_three_policy():
    roots, current, _, next_roots = fixture()
    one = approval(current, roots, "root-1", next_roots)
    with pytest.raises(PermissionError, match="insufficient trust-root quorum"):
        apply_trust_transition(
            current,
            next_roots=next_roots,
            next_threshold=2,
            reason_ref="reason:scheduled-rotation",
            transitioned_at=1_250,
            approvals=(one,),
        )


def test_quorum_rotates_to_new_generation_and_links_policy_hash():
    roots, current, _, next_roots = fixture()
    approvals = (
        approval(current, roots, "root-1", next_roots),
        approval(current, roots, "root-2", next_roots),
    )
    updated, receipt = apply_trust_transition(
        current,
        next_roots=next_roots,
        next_threshold=2,
        reason_ref="reason:scheduled-rotation",
        transitioned_at=1_250,
        approvals=approvals,
    )
    assert updated.generation == 13
    assert updated.previous_policy_hash == current.policy_hash
    assert updated.policy_hash == receipt.to_policy_hash
    assert receipt.from_policy_hash == current.policy_hash
    assert receipt.required_threshold == 2
    assert receipt.approval_key_ids == ("root-1", "root-2")


def test_duplicate_signer_does_not_count_twice():
    roots, current, _, next_roots = fixture()
    one = approval(current, roots, "root-1", next_roots)
    with pytest.raises(ValueError, match="duplicate trust approval signer"):
        apply_trust_transition(
            current,
            next_roots=next_roots,
            next_threshold=2,
            reason_ref="reason:scheduled-rotation",
            transitioned_at=1_250,
            approvals=(one, one),
        )


def test_old_approvals_cannot_authorize_next_generation_transition():
    roots, current, _, next_roots = fixture()
    approvals = (
        approval(current, roots, "root-1", next_roots),
        approval(current, roots, "root-2", next_roots),
    )
    updated, _ = apply_trust_transition(
        current,
        next_roots=next_roots,
        next_threshold=2,
        reason_ref="reason:scheduled-rotation",
        transitioned_at=1_250,
        approvals=approvals,
    )
    newer_key = Ed25519PrivateKey.generate()
    with pytest.raises(PermissionError, match="stale policy"):
        apply_trust_transition(
            updated,
            next_roots={"future-root": raw_public(newer_key)},
            next_threshold=1,
            reason_ref="reason:second-rotation",
            transitioned_at=1_300,
            approvals=approvals,
        )
