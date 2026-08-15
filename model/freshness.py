from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import re
from typing import Mapping

from model.lattice import ObserverReceipt

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _require_digest(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def digest_context(context: object) -> str:
    """Commit to the execution-relevant context with canonical JSON."""
    return sha256(_canonical_json(context)).hexdigest()


def digest_observer_receipt(receipt: ObserverReceipt) -> str:
    """Hash the historical observer verdict without changing the v0.3 receipt."""
    receipt.validate()
    material = {
        "domain": "ATMAN-LATTICE/observer-receipt-digest/v0.4",
        "observer_id": receipt.observer_id,
        "subject_identity_ref": receipt.subject_identity_ref,
        "branch_ref": receipt.branch_ref,
        "generation": receipt.generation,
        "lineage_root_hash": receipt.lineage_root_hash,
        "verdict": receipt.verdict,
        "input_state_refs": list(receipt.input_state_refs),
        "evidence_refs": list(receipt.evidence_refs),
        "limitations": list(receipt.limitations),
    }
    return sha256(_canonical_json(material)).hexdigest()


def _mac(secret: bytes, material: object) -> str:
    if not secret:
        raise ValueError("secret must not be empty")
    return hmac.new(secret, _canonical_json(material), sha256).hexdigest()


@dataclass(frozen=True)
class ObserverAttestation:
    observer_id: str
    observer_receipt_digest: str
    subject_identity_ref: str
    branch_ref: str
    generation: int
    lineage_root_hash: str
    verdict: str
    context_digest: str
    verified_at: int
    key_id: str
    mac: str

    def validate(self) -> None:
        if not self.observer_id:
            raise ValueError("observer_id is required")
        _require_digest("observer_receipt_digest", self.observer_receipt_digest)
        if not self.subject_identity_ref:
            raise ValueError("subject_identity_ref is required")
        if not self.branch_ref:
            raise ValueError("branch_ref is required")
        if self.generation < 0:
            raise ValueError("generation must be >= 0")
        _require_digest("lineage_root_hash", self.lineage_root_hash)
        if self.verdict not in {"PASS", "FAIL"}:
            raise ValueError("verdict must be PASS or FAIL")
        _require_digest("context_digest", self.context_digest)
        if self.verified_at < 0:
            raise ValueError("verified_at must be >= 0")
        if not self.key_id:
            raise ValueError("key_id is required")
        _require_digest("mac", self.mac)


def _attestation_material(
    *,
    observer_id: str,
    observer_receipt_digest: str,
    subject_identity_ref: str,
    branch_ref: str,
    generation: int,
    lineage_root_hash: str,
    verdict: str,
    context_digest: str,
    verified_at: int,
    key_id: str,
) -> dict[str, object]:
    return {
        "domain": "ATMAN-LATTICE/observer-attestation/v0.4",
        "observer_id": observer_id,
        "observer_receipt_digest": observer_receipt_digest,
        "subject_identity_ref": subject_identity_ref,
        "branch_ref": branch_ref,
        "generation": generation,
        "lineage_root_hash": lineage_root_hash,
        "verdict": verdict,
        "context_digest": context_digest,
        "verified_at": verified_at,
        "key_id": key_id,
    }


def attest_observer(
    receipt: ObserverReceipt,
    *,
    context: object,
    verified_at: int,
    key_id: str,
    secret: bytes,
) -> ObserverAttestation:
    receipt.validate()
    if verified_at < 0:
        raise ValueError("verified_at must be >= 0")
    if not key_id:
        raise ValueError("key_id is required")

    receipt_digest = digest_observer_receipt(receipt)
    context_digest = digest_context(context)
    material = _attestation_material(
        observer_id=receipt.observer_id,
        observer_receipt_digest=receipt_digest,
        subject_identity_ref=receipt.subject_identity_ref,
        branch_ref=receipt.branch_ref,
        generation=receipt.generation,
        lineage_root_hash=receipt.lineage_root_hash,
        verdict=receipt.verdict,
        context_digest=context_digest,
        verified_at=verified_at,
        key_id=key_id,
    )
    attestation = ObserverAttestation(
        observer_id=receipt.observer_id,
        observer_receipt_digest=receipt_digest,
        subject_identity_ref=receipt.subject_identity_ref,
        branch_ref=receipt.branch_ref,
        generation=receipt.generation,
        lineage_root_hash=receipt.lineage_root_hash,
        verdict=receipt.verdict,
        context_digest=context_digest,
        verified_at=verified_at,
        key_id=key_id,
        mac=_mac(secret, material),
    )
    attestation.validate()
    return attestation


def verify_attestation(
    attestation: ObserverAttestation,
    receipt: ObserverReceipt,
    *,
    current_context: object,
    now: int,
    max_age_seconds: int,
    keys: Mapping[str, bytes],
) -> tuple[bool, tuple[str, ...]]:
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be >= 0")
    if now < 0:
        raise ValueError("now must be >= 0")

    limitations: list[str] = []
    try:
        attestation.validate()
    except ValueError:
        return False, ("invalid_attestation",)
    try:
        receipt.validate()
    except ValueError:
        return False, ("invalid_observer_receipt",)

    receipt_digest = digest_observer_receipt(receipt)
    if attestation.observer_receipt_digest != receipt_digest:
        limitations.append("observer_receipt_digest_mismatch")
    if attestation.observer_id != receipt.observer_id:
        limitations.append("observer_id_mismatch")
    if attestation.subject_identity_ref != receipt.subject_identity_ref:
        limitations.append("identity_mismatch")
    if attestation.branch_ref != receipt.branch_ref:
        limitations.append("branch_mismatch")
    if attestation.generation != receipt.generation:
        limitations.append("generation_mismatch")
    if attestation.lineage_root_hash != receipt.lineage_root_hash:
        limitations.append("lineage_root_mismatch")
    if attestation.verdict != receipt.verdict:
        limitations.append("verdict_mismatch")

    if attestation.context_digest != digest_context(current_context):
        limitations.append("context_mismatch")
    if attestation.verified_at > now:
        limitations.append("verified_at_in_future")
    elif now - attestation.verified_at > max_age_seconds:
        limitations.append("stale_attestation")

    secret = keys.get(attestation.key_id)
    if secret is None:
        limitations.append("unknown_attestation_key")
    else:
        expected_mac = _mac(
            secret,
            _attestation_material(
                observer_id=attestation.observer_id,
                observer_receipt_digest=attestation.observer_receipt_digest,
                subject_identity_ref=attestation.subject_identity_ref,
                branch_ref=attestation.branch_ref,
                generation=attestation.generation,
                lineage_root_hash=attestation.lineage_root_hash,
                verdict=attestation.verdict,
                context_digest=attestation.context_digest,
                verified_at=attestation.verified_at,
                key_id=attestation.key_id,
            ),
        )
        if not hmac.compare_digest(attestation.mac, expected_mac):
            limitations.append("invalid_attestation_mac")

    return not limitations, tuple(dict.fromkeys(limitations))


def digest_attestation(attestation: ObserverAttestation) -> str:
    attestation.validate()
    material = {
        **_attestation_material(
            observer_id=attestation.observer_id,
            observer_receipt_digest=attestation.observer_receipt_digest,
            subject_identity_ref=attestation.subject_identity_ref,
            branch_ref=attestation.branch_ref,
            generation=attestation.generation,
            lineage_root_hash=attestation.lineage_root_hash,
            verdict=attestation.verdict,
            context_digest=attestation.context_digest,
            verified_at=attestation.verified_at,
            key_id=attestation.key_id,
        ),
        "mac": attestation.mac,
    }
    return sha256(_canonical_json(material)).hexdigest()


@dataclass(frozen=True)
class UseToken:
    subject_identity_ref: str
    branch_ref: str
    generation: int
    lineage_root_hash: str
    observer_receipt_digest: str
    attestation_digest: str
    context_digest: str
    issued_at: int
    expires_at: int
    key_id: str
    mac: str

    def validate(self) -> None:
        if not self.subject_identity_ref:
            raise ValueError("subject_identity_ref is required")
        if not self.branch_ref:
            raise ValueError("branch_ref is required")
        if self.generation < 0:
            raise ValueError("generation must be >= 0")
        _require_digest("lineage_root_hash", self.lineage_root_hash)
        _require_digest("observer_receipt_digest", self.observer_receipt_digest)
        _require_digest("attestation_digest", self.attestation_digest)
        _require_digest("context_digest", self.context_digest)
        if self.issued_at < 0:
            raise ValueError("issued_at must be >= 0")
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be greater than issued_at")
        if not self.key_id:
            raise ValueError("key_id is required")
        _require_digest("mac", self.mac)


def _use_token_material(
    *,
    subject_identity_ref: str,
    branch_ref: str,
    generation: int,
    lineage_root_hash: str,
    observer_receipt_digest: str,
    attestation_digest: str,
    context_digest: str,
    issued_at: int,
    expires_at: int,
    key_id: str,
) -> dict[str, object]:
    return {
        "domain": "ATMAN-LATTICE/use-token/v0.4",
        "subject_identity_ref": subject_identity_ref,
        "branch_ref": branch_ref,
        "generation": generation,
        "lineage_root_hash": lineage_root_hash,
        "observer_receipt_digest": observer_receipt_digest,
        "attestation_digest": attestation_digest,
        "context_digest": context_digest,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "key_id": key_id,
    }


def issue_use_token(
    attestation: ObserverAttestation,
    receipt: ObserverReceipt,
    *,
    current_context: object,
    now: int,
    max_attestation_age_seconds: int,
    attestation_keys: Mapping[str, bytes],
    token_key_id: str,
    token_secret: bytes,
    ttl_seconds: int = 30,
) -> UseToken:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be > 0")

    valid, limitations = verify_attestation(
        attestation,
        receipt,
        current_context=current_context,
        now=now,
        max_age_seconds=max_attestation_age_seconds,
        keys=attestation_keys,
    )
    if not valid:
        raise ValueError("attestation not usable: " + ",".join(limitations))
    if receipt.verdict != "PASS":
        raise ValueError("observer verdict must be PASS before use")
    if not token_key_id:
        raise ValueError("token_key_id is required")

    expires_at = now + ttl_seconds
    attestation_hash = digest_attestation(attestation)
    material = _use_token_material(
        subject_identity_ref=receipt.subject_identity_ref,
        branch_ref=receipt.branch_ref,
        generation=receipt.generation,
        lineage_root_hash=receipt.lineage_root_hash,
        observer_receipt_digest=attestation.observer_receipt_digest,
        attestation_digest=attestation_hash,
        context_digest=attestation.context_digest,
        issued_at=now,
        expires_at=expires_at,
        key_id=token_key_id,
    )
    token = UseToken(
        subject_identity_ref=receipt.subject_identity_ref,
        branch_ref=receipt.branch_ref,
        generation=receipt.generation,
        lineage_root_hash=receipt.lineage_root_hash,
        observer_receipt_digest=attestation.observer_receipt_digest,
        attestation_digest=attestation_hash,
        context_digest=attestation.context_digest,
        issued_at=now,
        expires_at=expires_at,
        key_id=token_key_id,
        mac=_mac(token_secret, material),
    )
    token.validate()
    return token


def verify_use_token(
    token: UseToken,
    *,
    current_context: object,
    now: int,
    token_keys: Mapping[str, bytes],
    expected_observer_receipt_digest: str | None = None,
) -> tuple[bool, tuple[str, ...]]:
    if now < 0:
        raise ValueError("now must be >= 0")

    try:
        token.validate()
    except ValueError:
        return False, ("invalid_use_token",)

    limitations: list[str] = []
    if token.context_digest != digest_context(current_context):
        limitations.append("context_mismatch")
    if now < token.issued_at:
        limitations.append("token_not_yet_valid")
    if now > token.expires_at:
        limitations.append("token_expired")
    if (
        expected_observer_receipt_digest is not None
        and token.observer_receipt_digest != expected_observer_receipt_digest
    ):
        limitations.append("observer_receipt_digest_mismatch")

    secret = token_keys.get(token.key_id)
    if secret is None:
        limitations.append("unknown_token_key")
    else:
        expected_mac = _mac(
            secret,
            _use_token_material(
                subject_identity_ref=token.subject_identity_ref,
                branch_ref=token.branch_ref,
                generation=token.generation,
                lineage_root_hash=token.lineage_root_hash,
                observer_receipt_digest=token.observer_receipt_digest,
                attestation_digest=token.attestation_digest,
                context_digest=token.context_digest,
                issued_at=token.issued_at,
                expires_at=token.expires_at,
                key_id=token.key_id,
            ),
        )
        if not hmac.compare_digest(token.mac, expected_mac):
            limitations.append("invalid_use_token_mac")

    return not limitations, tuple(dict.fromkeys(limitations))
