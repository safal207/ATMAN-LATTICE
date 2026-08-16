from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ED25519_PUBLIC_RE = re.compile(r"^[0-9a-f]{64}$")
_ED25519_SIGNATURE_RE = re.compile(r"^[0-9a-f]{128}$")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _public_key_hex(private_key: Ed25519PrivateKey) -> str:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def _load_public_key(public_key_hex: str) -> Ed25519PublicKey:
    if not _ED25519_PUBLIC_RE.fullmatch(public_key_hex):
        raise ValueError("public_key must be a raw 32-byte Ed25519 public key encoded as lowercase hex")
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))


def _require_digest(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def digest_action(action: object) -> str:
    return _digest({"domain": "ATMAN-LATTICE/action-digest/v0.8", "action": action})


@dataclass(frozen=True)
class AuthorityGrant:
    grant_id: str
    subject_ref: str
    key_id: str
    public_key: str
    roles: tuple[str, ...]
    scopes: tuple[str, ...]
    policy_generation: int
    valid_from: int
    valid_until: int
    issuer_ref: str
    issuer_key_id: str
    issuer_signature: str
    grant_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/authority-grant/v0.8",
            "grant_id": self.grant_id,
            "subject_ref": self.subject_ref,
            "key_id": self.key_id,
            "public_key": self.public_key,
            "roles": list(self.roles),
            "scopes": list(self.scopes),
            "policy_generation": self.policy_generation,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "issuer_ref": self.issuer_ref,
            "issuer_key_id": self.issuer_key_id,
        }

    def validate(self) -> None:
        if not self.grant_id or not self.subject_ref or not self.key_id:
            raise ValueError("grant_id, subject_ref, and key_id are required")
        _load_public_key(self.public_key)
        if not self.roles or any(not role for role in self.roles):
            raise ValueError("at least one non-empty role is required")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("roles must be unique")
        if not self.scopes or any(not scope for scope in self.scopes):
            raise ValueError("at least one non-empty scope is required")
        if len(set(self.scopes)) != len(self.scopes):
            raise ValueError("scopes must be unique")
        if self.policy_generation < 0:
            raise ValueError("policy_generation must be >= 0")
        if self.valid_from < 0 or self.valid_until <= self.valid_from:
            raise ValueError("invalid grant validity interval")
        if not self.issuer_ref or not self.issuer_key_id:
            raise ValueError("issuer identity is required")
        if not _ED25519_SIGNATURE_RE.fullmatch(self.issuer_signature):
            raise ValueError("issuer_signature must be a 64-byte Ed25519 signature encoded as lowercase hex")
        _require_digest("grant_hash", self.grant_hash)
        expected_hash = _digest(
            {
                "domain": "ATMAN-LATTICE/authority-grant-hash/v0.8",
                "material": self.material(),
                "issuer_signature": self.issuer_signature,
            }
        )
        if self.grant_hash != expected_hash:
            raise ValueError("grant_hash does not match grant content")


def issue_authority_grant(
    *,
    grant_id: str,
    subject_ref: str,
    subject_key_id: str,
    subject_public_key: Ed25519PublicKey,
    roles: tuple[str, ...],
    scopes: tuple[str, ...],
    policy_generation: int,
    valid_from: int,
    valid_until: int,
    issuer_ref: str,
    issuer_key_id: str,
    issuer_private_key: Ed25519PrivateKey,
) -> AuthorityGrant:
    public_key = subject_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    fields = {
        "grant_id": grant_id,
        "subject_ref": subject_ref,
        "key_id": subject_key_id,
        "public_key": public_key,
        "roles": roles,
        "scopes": scopes,
        "policy_generation": policy_generation,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "issuer_ref": issuer_ref,
        "issuer_key_id": issuer_key_id,
    }
    material = {
        "domain": "ATMAN-LATTICE/authority-grant/v0.8",
        **{**fields, "roles": list(roles), "scopes": list(scopes)},
    }
    signature = issuer_private_key.sign(_canonical_json(material)).hex()
    grant_hash = _digest(
        {
            "domain": "ATMAN-LATTICE/authority-grant-hash/v0.8",
            "material": material,
            "issuer_signature": signature,
        }
    )
    grant = AuthorityGrant(**fields, issuer_signature=signature, grant_hash=grant_hash)
    grant.validate()
    return grant


def verify_authority_grant(
    grant: AuthorityGrant,
    *,
    trusted_issuer_keys: Mapping[str, bytes],
    current_policy_generation: int,
    now: int,
) -> tuple[bool, tuple[str, ...]]:
    limitations: list[str] = []
    try:
        grant.validate()
    except ValueError:
        return False, ("invalid_authority_grant",)

    issuer_bytes = trusted_issuer_keys.get(grant.issuer_key_id)
    if issuer_bytes is None:
        limitations.append("untrusted_grant_issuer")
    else:
        try:
            Ed25519PublicKey.from_public_bytes(issuer_bytes).verify(
                bytes.fromhex(grant.issuer_signature),
                _canonical_json(grant.material()),
            )
        except (ValueError, InvalidSignature):
            limitations.append("invalid_grant_signature")

    if grant.policy_generation != current_policy_generation:
        limitations.append("stale_authority_policy_generation")
    if now < grant.valid_from:
        limitations.append("grant_not_yet_valid")
    if now > grant.valid_until:
        limitations.append("grant_expired")

    return not limitations, tuple(dict.fromkeys(limitations))


@dataclass(frozen=True)
class AuthorityProof:
    subject_ref: str
    key_id: str
    grant_hash: str
    role: str
    scope: str
    action_digest: str
    policy_generation: int
    signed_at: int
    signature: str
    proof_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/authority-proof/v0.8",
            "subject_ref": self.subject_ref,
            "key_id": self.key_id,
            "grant_hash": self.grant_hash,
            "role": self.role,
            "scope": self.scope,
            "action_digest": self.action_digest,
            "policy_generation": self.policy_generation,
            "signed_at": self.signed_at,
        }

    def validate(self) -> None:
        if not self.subject_ref or not self.key_id or not self.role or not self.scope:
            raise ValueError("subject, key, role, and scope are required")
        _require_digest("grant_hash", self.grant_hash)
        _require_digest("action_digest", self.action_digest)
        if self.policy_generation < 0 or self.signed_at < 0:
            raise ValueError("policy_generation and signed_at must be >= 0")
        if not _ED25519_SIGNATURE_RE.fullmatch(self.signature):
            raise ValueError("signature must be a 64-byte Ed25519 signature encoded as lowercase hex")
        _require_digest("proof_hash", self.proof_hash)
        expected_hash = _digest(
            {
                "domain": "ATMAN-LATTICE/authority-proof-hash/v0.8",
                "material": self.material(),
                "signature": self.signature,
            }
        )
        if self.proof_hash != expected_hash:
            raise ValueError("proof_hash does not match proof content")


def sign_authorized_action(
    grant: AuthorityGrant,
    *,
    private_key: Ed25519PrivateKey,
    role: str,
    scope: str,
    action: object,
    signed_at: int,
) -> AuthorityProof:
    grant.validate()
    if _public_key_hex(private_key) != grant.public_key:
        raise ValueError("private key does not match grant public key")
    fields = {
        "subject_ref": grant.subject_ref,
        "key_id": grant.key_id,
        "grant_hash": grant.grant_hash,
        "role": role,
        "scope": scope,
        "action_digest": digest_action(action),
        "policy_generation": grant.policy_generation,
        "signed_at": signed_at,
    }
    material = {"domain": "ATMAN-LATTICE/authority-proof/v0.8", **fields}
    signature = private_key.sign(_canonical_json(material)).hex()
    proof_hash = _digest(
        {
            "domain": "ATMAN-LATTICE/authority-proof-hash/v0.8",
            "material": material,
            "signature": signature,
        }
    )
    proof = AuthorityProof(**fields, signature=signature, proof_hash=proof_hash)
    proof.validate()
    return proof


def verify_authority_proof(
    grant: AuthorityGrant,
    proof: AuthorityProof,
    *,
    action: object,
    trusted_issuer_keys: Mapping[str, bytes],
    current_policy_generation: int,
    now: int,
) -> tuple[bool, tuple[str, ...]]:
    limitations: list[str] = []
    grant_valid, grant_limitations = verify_authority_grant(
        grant,
        trusted_issuer_keys=trusted_issuer_keys,
        current_policy_generation=current_policy_generation,
        now=now,
    )
    limitations.extend(grant_limitations)

    try:
        proof.validate()
    except ValueError:
        return False, tuple(dict.fromkeys((*limitations, "invalid_authority_proof")))

    checks = (
        (proof.subject_ref == grant.subject_ref, "authority_subject_mismatch"),
        (proof.key_id == grant.key_id, "authority_key_mismatch"),
        (proof.grant_hash == grant.grant_hash, "authority_grant_mismatch"),
        (proof.role in grant.roles, "role_not_authorized"),
        (proof.scope in grant.scopes, "scope_not_authorized"),
        (proof.policy_generation == grant.policy_generation, "proof_grant_generation_mismatch"),
        (proof.policy_generation == current_policy_generation, "proof_policy_generation_stale"),
        (grant.valid_from <= proof.signed_at <= grant.valid_until, "proof_signed_outside_grant_window"),
        (proof.action_digest == digest_action(action), "action_digest_mismatch"),
    )
    for ok, limitation in checks:
        if not ok:
            limitations.append(limitation)

    try:
        _load_public_key(grant.public_key).verify(
            bytes.fromhex(proof.signature),
            _canonical_json(proof.material()),
        )
    except (ValueError, InvalidSignature):
        limitations.append("invalid_authority_signature")

    return grant_valid and not limitations, tuple(dict.fromkeys(limitations))
