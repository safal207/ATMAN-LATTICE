from dataclasses import replace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from model.authority import (
    _canonical_json,
    _digest,
    issue_authority_grant,
    sign_authorized_action,
    verify_authority_proof,
)


def raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def test_self_consistent_proof_signed_by_wrong_key_is_rejected():
    root = Ed25519PrivateKey.generate()
    authorized = Ed25519PrivateKey.generate()
    attacker = Ed25519PrivateKey.generate()
    grant = issue_authority_grant(
        grant_id="grant:a4",
        subject_ref="observer:a4",
        subject_key_id="observer-key-1",
        subject_public_key=authorized.public_key(),
        roles=("A4_KEEPER",),
        scopes=("identity:agent:1",),
        policy_generation=12,
        valid_from=1_000,
        valid_until=2_000,
        issuer_ref="authority:root",
        issuer_key_id="root-key-1",
        issuer_private_key=root,
    )
    action = {"operation": "global_coherence", "identity_ref": "agent:1"}
    proof = sign_authorized_action(
        grant,
        private_key=authorized,
        role="A4_KEEPER",
        scope="identity:agent:1",
        action=action,
        signed_at=1_200,
    )

    alien_signature = attacker.sign(_canonical_json(proof.material())).hex()
    alien_proof = replace(
        proof,
        signature=alien_signature,
        proof_hash=_digest(
            {
                "domain": "ATMAN-LATTICE/authority-proof-hash/v0.8",
                "material": proof.material(),
                "signature": alien_signature,
            }
        ),
    )

    valid, limitations = verify_authority_proof(
        grant,
        alien_proof,
        action=action,
        trusted_issuer_keys={"root-key-1": raw_public(root)},
        current_policy_generation=12,
        now=1_250,
    )

    assert valid is False
    assert "invalid_authority_signature" in limitations
