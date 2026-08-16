from dataclasses import replace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import (
    digest_action,
    issue_authority_grant,
    sign_authorized_action,
    verify_authority_grant,
    verify_authority_proof,
)


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def fixture():
    root = Ed25519PrivateKey.generate()
    observer = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id="grant:observer:a4",
        subject_ref="observer:a4",
        subject_key_id="observer-key-1",
        subject_public_key=observer.public_key(),
        roles=("A4_KEEPER", "USE_TOKEN_REVOKER"),
        scopes=("identity:agent:1", "authorization:agent:1"),
        policy_generation=12,
        valid_from=1_000,
        valid_until=2_000,
        issuer_ref="authority:root",
        issuer_key_id="root-key-1",
        issuer_private_key=root,
    )
    trusted = {"root-key-1": raw_public(root)}
    return root, observer, grant, trusted


def test_valid_ed25519_authority_proof_passes():
    _, observer, grant, trusted = fixture()
    action = {"operation": "global_coherence", "identity_ref": "agent:1"}
    proof = sign_authorized_action(
        grant,
        private_key=observer,
        role="A4_KEEPER",
        scope="identity:agent:1",
        action=action,
        signed_at=1_200,
    )

    valid, limitations = verify_authority_proof(
        grant,
        proof,
        action=action,
        trusted_issuer_keys=trusted,
        current_policy_generation=12,
        now=1_250,
    )
    assert valid is True
    assert limitations == ()


def test_cryptographically_valid_but_unauthorized_role_is_rejected():
    _, observer, grant, trusted = fixture()
    action = {"operation": "issue_use_token", "identity_ref": "agent:1"}
    proof = sign_authorized_action(
        grant,
        private_key=observer,
        role="USE_TOKEN_ISSUER",
        scope="authorization:agent:1",
        action=action,
        signed_at=1_200,
    )

    valid, limitations = verify_authority_proof(
        grant,
        proof,
        action=action,
        trusted_issuer_keys=trusted,
        current_policy_generation=12,
        now=1_250,
    )
    assert valid is False
    assert "role_not_authorized" in limitations


def test_cryptographically_valid_but_wrong_scope_is_rejected():
    _, observer, grant, trusted = fixture()
    action = {"operation": "revoke_use_token", "identity_ref": "agent:2"}
    proof = sign_authorized_action(
        grant,
        private_key=observer,
        role="USE_TOKEN_REVOKER",
        scope="authorization:agent:2",
        action=action,
        signed_at=1_200,
    )

    valid, limitations = verify_authority_proof(
        grant,
        proof,
        action=action,
        trusted_issuer_keys=trusted,
        current_policy_generation=12,
        now=1_250,
    )
    assert valid is False
    assert "scope_not_authorized" in limitations


def test_stale_policy_generation_revokes_old_grant_without_breaking_signature():
    _, observer, grant, trusted = fixture()
    action = {"operation": "global_coherence", "identity_ref": "agent:1"}
    proof = sign_authorized_action(
        grant,
        private_key=observer,
        role="A4_KEEPER",
        scope="identity:agent:1",
        action=action,
        signed_at=1_200,
    )

    valid, limitations = verify_authority_proof(
        grant,
        proof,
        action=action,
        trusted_issuer_keys=trusted,
        current_policy_generation=13,
        now=1_250,
    )
    assert valid is False
    assert "stale_authority_policy_generation" in limitations
    assert "proof_policy_generation_stale" in limitations


def test_action_substitution_is_detected():
    _, observer, grant, trusted = fixture()
    original = {"operation": "revoke_use_token", "token_digest": "a" * 64}
    substituted = {"operation": "revoke_use_token", "token_digest": "b" * 64}
    proof = sign_authorized_action(
        grant,
        private_key=observer,
        role="USE_TOKEN_REVOKER",
        scope="authorization:agent:1",
        action=original,
        signed_at=1_200,
    )

    valid, limitations = verify_authority_proof(
        grant,
        proof,
        action=substituted,
        trusted_issuer_keys=trusted,
        current_policy_generation=12,
        now=1_250,
    )
    assert valid is False
    assert "action_digest_mismatch" in limitations


def test_tampered_proof_signature_is_detected():
    _, observer, grant, trusted = fixture()
    action = {"operation": "global_coherence", "identity_ref": "agent:1"}
    proof = sign_authorized_action(
        grant,
        private_key=observer,
        role="A4_KEEPER",
        scope="identity:agent:1",
        action=action,
        signed_at=1_200,
    )
    mutated_signature = ("00" if proof.signature[:2] != "00" else "01") + proof.signature[2:]
    tampered = replace(proof, signature=mutated_signature)
    tampered = replace(
        tampered,
        proof_hash=digest_action({
            "material": tampered.material(),
            "signature": tampered.signature,
        }),
    )

    valid, limitations = verify_authority_proof(
        grant,
        tampered,
        action=action,
        trusted_issuer_keys=trusted,
        current_policy_generation=12,
        now=1_250,
    )
    assert valid is False
    assert "invalid_authority_proof" in limitations or "invalid_authority_signature" in limitations


def test_untrusted_root_cannot_authorize_grant():
    _, _, grant, _ = fixture()
    valid, limitations = verify_authority_grant(
        grant,
        trusted_issuer_keys={},
        current_policy_generation=12,
        now=1_250,
    )
    assert valid is False
    assert "untrusted_grant_issuer" in limitations


def test_grant_expiry_is_enforced_at_use_time():
    _, observer, grant, trusted = fixture()
    action = {"operation": "global_coherence", "identity_ref": "agent:1"}
    proof = sign_authorized_action(
        grant,
        private_key=observer,
        role="A4_KEEPER",
        scope="identity:agent:1",
        action=action,
        signed_at=1_900,
    )

    valid, limitations = verify_authority_proof(
        grant,
        proof,
        action=action,
        trusted_issuer_keys=trusted,
        current_policy_generation=12,
        now=2_001,
    )
    assert valid is False
    assert "grant_expired" in limitations
