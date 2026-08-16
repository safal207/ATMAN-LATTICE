from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ED25519_PUBLIC_RE = re.compile(r"^[0-9a-f]{64}$")
_ED25519_SIGNATURE_RE = re.compile(r"^[0-9a-f]{128}$")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def _raw_public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


@dataclass(frozen=True)
class TrustRoot:
    key_id: str
    public_key: str

    def validate(self) -> None:
        if not self.key_id:
            raise ValueError("trust root key_id is required")
        if not _ED25519_PUBLIC_RE.fullmatch(self.public_key):
            raise ValueError("trust root public_key must be a raw Ed25519 public key encoded as lowercase hex")


@dataclass(frozen=True)
class TrustPolicy:
    generation: int
    threshold: int
    roots: tuple[TrustRoot, ...]
    previous_policy_hash: str | None
    activated_at: int
    policy_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/trust-policy/v1.2",
            "generation": self.generation,
            "threshold": self.threshold,
            "roots": [
                {"key_id": root.key_id, "public_key": root.public_key}
                for root in self.roots
            ],
            "previous_policy_hash": self.previous_policy_hash,
            "activated_at": self.activated_at,
        }

    def validate(self) -> None:
        if self.generation < 0:
            raise ValueError("trust policy generation must be >= 0")
        if self.activated_at < 0:
            raise ValueError("trust policy activated_at must be >= 0")
        if not self.roots:
            raise ValueError("trust policy requires at least one root")
        for root in self.roots:
            root.validate()
        key_ids = [root.key_id for root in self.roots]
        if key_ids != sorted(key_ids):
            raise ValueError("trust roots must be sorted by key_id")
        if len(set(key_ids)) != len(key_ids):
            raise ValueError("trust root key_ids must be unique")
        if self.threshold <= 0 or self.threshold > len(self.roots):
            raise ValueError("trust threshold must be between 1 and root count")
        if self.previous_policy_hash is not None:
            _require_digest("previous_policy_hash", self.previous_policy_hash)
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match trust policy content")

    def root_map(self) -> dict[str, bytes]:
        self.validate()
        return {root.key_id: bytes.fromhex(root.public_key) for root in self.roots}


def _canonical_roots(roots: Mapping[str, bytes]) -> tuple[TrustRoot, ...]:
    if not roots:
        raise ValueError("at least one trust root is required")
    items = tuple(
        TrustRoot(key_id=key_id, public_key=public_key.hex())
        for key_id, public_key in sorted(roots.items())
    )
    for item in items:
        item.validate()
    return items


def create_bootstrap_policy(
    roots: Mapping[str, bytes],
    *,
    generation: int,
    threshold: int,
    activated_at: int = 0,
) -> TrustPolicy:
    canonical_roots = _canonical_roots(roots)
    fields = {
        "generation": generation,
        "threshold": threshold,
        "roots": canonical_roots,
        "previous_policy_hash": None,
        "activated_at": activated_at,
    }
    policy = TrustPolicy(**fields, policy_hash=_digest({
        "domain": "ATMAN-LATTICE/trust-policy/v1.2",
        "generation": generation,
        "threshold": threshold,
        "roots": [{"key_id": root.key_id, "public_key": root.public_key} for root in canonical_roots],
        "previous_policy_hash": None,
        "activated_at": activated_at,
    }))
    policy.validate()
    return policy


def trust_transition_action(
    current: TrustPolicy,
    *,
    next_roots: Mapping[str, bytes],
    next_threshold: int,
    reason_ref: str,
    transitioned_at: int,
) -> dict[str, object]:
    current.validate()
    canonical_next = _canonical_roots(next_roots)
    if next_threshold <= 0 or next_threshold > len(canonical_next):
        raise ValueError("next trust threshold must be between 1 and next root count")
    if not reason_ref:
        raise ValueError("reason_ref is required")
    if transitioned_at < current.activated_at:
        raise ValueError("trust transition cannot predate current policy activation")
    return {
        "domain": "ATMAN-LATTICE/trust-transition-action/v1.2",
        "current_policy_hash": current.policy_hash,
        "current_generation": current.generation,
        "next_generation": current.generation + 1,
        "next_threshold": next_threshold,
        "next_roots": [
            {"key_id": root.key_id, "public_key": root.public_key}
            for root in canonical_next
        ],
        "reason_ref": reason_ref,
        "transitioned_at": transitioned_at,
    }


@dataclass(frozen=True)
class TrustApproval:
    signer_key_id: str
    current_policy_hash: str
    transition_digest: str
    signed_at: int
    signature: str
    approval_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/trust-approval/v1.2",
            "signer_key_id": self.signer_key_id,
            "current_policy_hash": self.current_policy_hash,
            "transition_digest": self.transition_digest,
            "signed_at": self.signed_at,
        }

    def validate(self) -> None:
        if not self.signer_key_id:
            raise ValueError("approval signer_key_id is required")
        _require_digest("current_policy_hash", self.current_policy_hash)
        _require_digest("transition_digest", self.transition_digest)
        if self.signed_at < 0:
            raise ValueError("approval signed_at must be >= 0")
        if not _ED25519_SIGNATURE_RE.fullmatch(self.signature):
            raise ValueError("approval signature must be a 64-byte Ed25519 signature encoded as lowercase hex")
        _require_digest("approval_hash", self.approval_hash)
        expected = _digest({
            "domain": "ATMAN-LATTICE/trust-approval-hash/v1.2",
            "material": self.material(),
            "signature": self.signature,
        })
        if self.approval_hash != expected:
            raise ValueError("approval_hash does not match approval content")


def sign_trust_transition(
    current: TrustPolicy,
    *,
    signer_key_id: str,
    signer_private_key: Ed25519PrivateKey,
    next_roots: Mapping[str, bytes],
    next_threshold: int,
    reason_ref: str,
    transitioned_at: int,
    signed_at: int,
) -> TrustApproval:
    current.validate()
    current_root = next((root for root in current.roots if root.key_id == signer_key_id), None)
    if current_root is None:
        raise ValueError("signer is not a current trust root")
    if _raw_public_hex(signer_private_key) != current_root.public_key:
        raise ValueError("signer private key does not match current trust root")
    if signed_at > transitioned_at:
        raise ValueError("trust approval cannot be signed after transition time")
    action = trust_transition_action(
        current,
        next_roots=next_roots,
        next_threshold=next_threshold,
        reason_ref=reason_ref,
        transitioned_at=transitioned_at,
    )
    fields = {
        "signer_key_id": signer_key_id,
        "current_policy_hash": current.policy_hash,
        "transition_digest": _digest(action),
        "signed_at": signed_at,
    }
    material = {"domain": "ATMAN-LATTICE/trust-approval/v1.2", **fields}
    signature = signer_private_key.sign(_canonical_json(material)).hex()
    approval = TrustApproval(
        **fields,
        signature=signature,
        approval_hash=_digest({
            "domain": "ATMAN-LATTICE/trust-approval-hash/v1.2",
            "material": material,
            "signature": signature,
        }),
    )
    approval.validate()
    return approval


@dataclass(frozen=True)
class TrustTransitionReceipt:
    from_policy_hash: str
    from_generation: int
    to_policy_hash: str
    to_generation: int
    required_threshold: int
    approval_key_ids: tuple[str, ...]
    approval_hashes: tuple[str, ...]
    reason_ref: str
    transitioned_at: int
    transition_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/trust-transition-receipt/v1.2",
            "from_policy_hash": self.from_policy_hash,
            "from_generation": self.from_generation,
            "to_policy_hash": self.to_policy_hash,
            "to_generation": self.to_generation,
            "required_threshold": self.required_threshold,
            "approval_key_ids": list(self.approval_key_ids),
            "approval_hashes": list(self.approval_hashes),
            "reason_ref": self.reason_ref,
            "transitioned_at": self.transitioned_at,
        }

    def validate(self) -> None:
        _require_digest("from_policy_hash", self.from_policy_hash)
        _require_digest("to_policy_hash", self.to_policy_hash)
        _require_digest("transition_hash", self.transition_hash)
        if self.to_generation != self.from_generation + 1:
            raise ValueError("trust transition must advance exactly one generation")
        if self.required_threshold <= 0:
            raise ValueError("required_threshold must be > 0")
        if len(self.approval_key_ids) < self.required_threshold:
            raise ValueError("transition receipt does not contain quorum")
        if self.approval_key_ids != tuple(sorted(self.approval_key_ids)):
            raise ValueError("approval_key_ids must be sorted")
        if len(set(self.approval_key_ids)) != len(self.approval_key_ids):
            raise ValueError("approval_key_ids must be unique")
        if len(self.approval_hashes) != len(self.approval_key_ids):
            raise ValueError("approval hashes must align with approval keys")
        for approval_hash in self.approval_hashes:
            _require_digest("approval_hash", approval_hash)
        if not self.reason_ref or self.transitioned_at < 0:
            raise ValueError("transition reason and time are required")
        if self.transition_hash != _digest(self.material()):
            raise ValueError("transition_hash does not match transition receipt")


def apply_trust_transition(
    current: TrustPolicy,
    *,
    next_roots: Mapping[str, bytes],
    next_threshold: int,
    reason_ref: str,
    transitioned_at: int,
    approvals: tuple[TrustApproval, ...],
) -> tuple[TrustPolicy, TrustTransitionReceipt]:
    current.validate()
    action = trust_transition_action(
        current,
        next_roots=next_roots,
        next_threshold=next_threshold,
        reason_ref=reason_ref,
        transitioned_at=transitioned_at,
    )
    transition_digest = _digest(action)
    current_roots = current.root_map()
    valid_approvals: dict[str, TrustApproval] = {}
    for approval in approvals:
        approval.validate()
        if approval.signer_key_id in valid_approvals:
            raise ValueError("duplicate trust approval signer")
        if approval.current_policy_hash != current.policy_hash:
            raise PermissionError("trust approval bound to stale policy")
        if approval.transition_digest != transition_digest:
            raise PermissionError("trust approval bound to different transition")
        if approval.signed_at > transitioned_at:
            raise PermissionError("trust approval signed after transition time")
        public_key = current_roots.get(approval.signer_key_id)
        if public_key is None:
            raise PermissionError("trust approval signer is not a current root")
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                bytes.fromhex(approval.signature),
                _canonical_json(approval.material()),
            )
        except (ValueError, InvalidSignature):
            raise PermissionError("invalid trust approval signature")
        valid_approvals[approval.signer_key_id] = approval

    if len(valid_approvals) < current.threshold:
        raise PermissionError("insufficient trust-root quorum")

    canonical_next = _canonical_roots(next_roots)
    next_fields = {
        "generation": current.generation + 1,
        "threshold": next_threshold,
        "roots": canonical_next,
        "previous_policy_hash": current.policy_hash,
        "activated_at": transitioned_at,
    }
    next_material = {
        "domain": "ATMAN-LATTICE/trust-policy/v1.2",
        "generation": next_fields["generation"],
        "threshold": next_threshold,
        "roots": [{"key_id": root.key_id, "public_key": root.public_key} for root in canonical_next],
        "previous_policy_hash": current.policy_hash,
        "activated_at": transitioned_at,
    }
    next_policy = TrustPolicy(**next_fields, policy_hash=_digest(next_material))
    next_policy.validate()

    ordered = tuple(valid_approvals[key_id] for key_id in sorted(valid_approvals))
    receipt_fields = {
        "from_policy_hash": current.policy_hash,
        "from_generation": current.generation,
        "to_policy_hash": next_policy.policy_hash,
        "to_generation": next_policy.generation,
        "required_threshold": current.threshold,
        "approval_key_ids": tuple(item.signer_key_id for item in ordered),
        "approval_hashes": tuple(item.approval_hash for item in ordered),
        "reason_ref": reason_ref,
        "transitioned_at": transitioned_at,
    }
    receipt = TrustTransitionReceipt(
        **receipt_fields,
        transition_hash=_digest({"domain": "ATMAN-LATTICE/trust-transition-receipt/v1.2", **{
            **receipt_fields,
            "approval_key_ids": list(receipt_fields["approval_key_ids"]),
            "approval_hashes": list(receipt_fields["approval_hashes"]),
        }}),
    )
    receipt.validate()
    return next_policy, receipt


def trust_policy_to_dict(policy: TrustPolicy) -> dict[str, object]:
    policy.validate()
    return {
        "generation": policy.generation,
        "threshold": policy.threshold,
        "roots": [{"key_id": root.key_id, "public_key": root.public_key} for root in policy.roots],
        "previous_policy_hash": policy.previous_policy_hash,
        "activated_at": policy.activated_at,
        "policy_hash": policy.policy_hash,
    }


def trust_policy_from_dict(data: Mapping[str, object]) -> TrustPolicy:
    raw_roots = data.get("roots")
    if not isinstance(raw_roots, list):
        raise ValueError("trust policy roots must be an array")
    roots = tuple(
        TrustRoot(key_id=str(item["key_id"]), public_key=str(item["public_key"]))
        for item in raw_roots
        if isinstance(item, dict)
    )
    if len(roots) != len(raw_roots):
        raise ValueError("each trust root must be an object")
    policy = TrustPolicy(
        generation=int(data["generation"]),
        threshold=int(data["threshold"]),
        roots=roots,
        previous_policy_hash=None if data.get("previous_policy_hash") is None else str(data["previous_policy_hash"]),
        activated_at=int(data["activated_at"]),
        policy_hash=str(data["policy_hash"]),
    )
    policy.validate()
    return policy


def trust_approval_to_dict(approval: TrustApproval) -> dict[str, object]:
    approval.validate()
    return {
        "signer_key_id": approval.signer_key_id,
        "current_policy_hash": approval.current_policy_hash,
        "transition_digest": approval.transition_digest,
        "signed_at": approval.signed_at,
        "signature": approval.signature,
        "approval_hash": approval.approval_hash,
    }


def trust_approval_from_dict(data: Mapping[str, object]) -> TrustApproval:
    approval = TrustApproval(
        signer_key_id=str(data["signer_key_id"]),
        current_policy_hash=str(data["current_policy_hash"]),
        transition_digest=str(data["transition_digest"]),
        signed_at=int(data["signed_at"]),
        signature=str(data["signature"]),
        approval_hash=str(data["approval_hash"]),
    )
    approval.validate()
    return approval


def trust_transition_receipt_to_dict(receipt: TrustTransitionReceipt) -> dict[str, object]:
    receipt.validate()
    return {
        "from_policy_hash": receipt.from_policy_hash,
        "from_generation": receipt.from_generation,
        "to_policy_hash": receipt.to_policy_hash,
        "to_generation": receipt.to_generation,
        "required_threshold": receipt.required_threshold,
        "approval_key_ids": list(receipt.approval_key_ids),
        "approval_hashes": list(receipt.approval_hashes),
        "reason_ref": receipt.reason_ref,
        "transitioned_at": receipt.transitioned_at,
        "transition_hash": receipt.transition_hash,
    }
