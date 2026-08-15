from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import re
from typing import Literal, Mapping

from model.freshness import (
    UseToken,
    _canonical_json,
    _mac,
    _use_token_material,
    digest_context,
    verify_use_token,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EventType = Literal["CONSUMED", "REVOKED"]


def _digest(material: object) -> str:
    return sha256(_canonical_json(material)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def digest_use_token(token: UseToken) -> str:
    """Stable digest over the exact authenticated v0.4 UseToken."""
    token.validate()
    material = {
        "domain": "ATMAN-LATTICE/use-token-digest/v0.7",
        "token_material": _use_token_material(
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
        "mac": token.mac,
    }
    return _digest(material)


def verify_use_token_authenticity(
    token: UseToken,
    *,
    token_keys: Mapping[str, bytes],
) -> tuple[bool, tuple[str, ...]]:
    """Verify token structure and MAC without requiring current context or freshness."""
    try:
        token.validate()
    except ValueError:
        return False, ("invalid_use_token",)

    secret = token_keys.get(token.key_id)
    if secret is None:
        return False, ("unknown_token_key",)

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
        return False, ("invalid_use_token_mac",)
    return True, ()


@dataclass(frozen=True)
class AuthorizationEvent:
    ledger_generation: int
    event_type: EventType
    token_digest: str
    subject_identity_ref: str
    branch_ref: str
    subject_generation: int
    lineage_root_hash: str
    context_digest: str
    occurred_at: int
    actor_ref: str
    reason_ref: str
    previous_event_hash: str | None
    key_id: str
    mac: str
    event_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/authorization-event/v0.7",
            "ledger_generation": self.ledger_generation,
            "event_type": self.event_type,
            "token_digest": self.token_digest,
            "subject_identity_ref": self.subject_identity_ref,
            "branch_ref": self.branch_ref,
            "subject_generation": self.subject_generation,
            "lineage_root_hash": self.lineage_root_hash,
            "context_digest": self.context_digest,
            "occurred_at": self.occurred_at,
            "actor_ref": self.actor_ref,
            "reason_ref": self.reason_ref,
            "previous_event_hash": self.previous_event_hash,
            "key_id": self.key_id,
        }

    def validate(self) -> None:
        if self.ledger_generation <= 0:
            raise ValueError("ledger_generation must be > 0")
        if self.event_type not in {"CONSUMED", "REVOKED"}:
            raise ValueError("invalid event_type")
        _require_digest("token_digest", self.token_digest)
        if not self.subject_identity_ref:
            raise ValueError("subject_identity_ref is required")
        if not self.branch_ref:
            raise ValueError("branch_ref is required")
        if self.subject_generation < 0:
            raise ValueError("subject_generation must be >= 0")
        _require_digest("lineage_root_hash", self.lineage_root_hash)
        _require_digest("context_digest", self.context_digest)
        if self.occurred_at < 0:
            raise ValueError("occurred_at must be >= 0")
        if not self.actor_ref:
            raise ValueError("actor_ref is required")
        if not self.reason_ref:
            raise ValueError("reason_ref is required")
        if self.ledger_generation == 1:
            if self.previous_event_hash is not None:
                raise ValueError("first ledger event must not have a previous hash")
        else:
            if self.previous_event_hash is None:
                raise ValueError("non-first ledger event requires previous_event_hash")
            _require_digest("previous_event_hash", self.previous_event_hash)
        if not self.key_id:
            raise ValueError("key_id is required")
        _require_digest("mac", self.mac)
        _require_digest("event_hash", self.event_hash)
        expected_event_hash = _digest(
            {
                "domain": "ATMAN-LATTICE/authorization-event-hash/v0.7",
                "material": self.material(),
                "mac": self.mac,
            }
        )
        if self.event_hash != expected_event_hash:
            raise ValueError("event_hash does not match event content")


@dataclass(frozen=True)
class AuthorizationLedger:
    generation: int
    head_event_hash: str | None
    events: tuple[AuthorizationEvent, ...]

    def validate(self) -> None:
        if self.generation < 0:
            raise ValueError("generation must be >= 0")
        if self.generation == 0:
            if self.events:
                raise ValueError("empty generation must have no events")
            if self.head_event_hash is not None:
                raise ValueError("empty ledger must not have a head")
        else:
            if not self.events:
                raise ValueError("non-empty generation requires events")
            if self.head_event_hash is None:
                raise ValueError("non-empty ledger requires a head")
            _require_digest("head_event_hash", self.head_event_hash)


def empty_authorization_ledger() -> AuthorizationLedger:
    return AuthorizationLedger(generation=0, head_event_hash=None, events=())


def verify_authorization_ledger(
    ledger: AuthorizationLedger,
    *,
    event_keys: Mapping[str, bytes],
) -> tuple[bool, tuple[str, ...]]:
    try:
        ledger.validate()
    except ValueError:
        return False, ("invalid_authorization_ledger",)

    limitations: list[str] = []
    if ledger.generation != len(ledger.events):
        limitations.append("ledger_generation_mismatch")

    previous_hash: str | None = None
    seen_tokens: set[str] = set()
    for index, event in enumerate(ledger.events, start=1):
        try:
            event.validate()
        except ValueError:
            limitations.append(f"invalid_event:{index - 1}")
            continue

        if event.ledger_generation != index:
            limitations.append("event_generation_gap")
        if event.previous_event_hash != previous_hash:
            limitations.append("event_parent_hash_mismatch")

        secret = event_keys.get(event.key_id)
        if secret is None:
            limitations.append("unknown_event_key")
        else:
            expected_mac = _mac(secret, event.material())
            if not hmac.compare_digest(event.mac, expected_mac):
                limitations.append("invalid_event_mac")

        if event.token_digest in seen_tokens:
            limitations.append("duplicate_terminal_token_event")
        seen_tokens.add(event.token_digest)
        previous_hash = event.event_hash

    if ledger.events and ledger.head_event_hash != ledger.events[-1].event_hash:
        limitations.append("ledger_head_mismatch")

    return not limitations, tuple(dict.fromkeys(limitations))


def _terminal_event_for_token(
    ledger: AuthorizationLedger,
    token_digest: str,
) -> AuthorizationEvent | None:
    return next((event for event in ledger.events if event.token_digest == token_digest), None)


def _append_terminal_event(
    ledger: AuthorizationLedger,
    token: UseToken,
    *,
    event_type: EventType,
    occurred_at: int,
    actor_ref: str,
    reason_ref: str,
    expected_ledger_generation: int,
    event_key_id: str,
    event_secret: bytes,
) -> tuple[AuthorizationLedger, AuthorizationEvent]:
    if expected_ledger_generation != ledger.generation:
        raise ValueError("stale_authorization_ledger")
    if occurred_at < 0:
        raise ValueError("occurred_at must be >= 0")
    if not actor_ref:
        raise ValueError("actor_ref is required")
    if not reason_ref:
        raise ValueError("reason_ref is required")
    if not event_key_id:
        raise ValueError("event_key_id is required")

    token_digest = digest_use_token(token)
    terminal = _terminal_event_for_token(ledger, token_digest)
    if terminal is not None:
        if terminal.event_type == "CONSUMED":
            raise ValueError("token_already_consumed")
        raise ValueError("token_already_revoked")

    generation = ledger.generation + 1
    previous_event_hash = ledger.head_event_hash
    fields = {
        "ledger_generation": generation,
        "event_type": event_type,
        "token_digest": token_digest,
        "subject_identity_ref": token.subject_identity_ref,
        "branch_ref": token.branch_ref,
        "subject_generation": token.generation,
        "lineage_root_hash": token.lineage_root_hash,
        "context_digest": token.context_digest,
        "occurred_at": occurred_at,
        "actor_ref": actor_ref,
        "reason_ref": reason_ref,
        "previous_event_hash": previous_event_hash,
        "key_id": event_key_id,
    }
    mac = _mac(event_secret, {"domain": "ATMAN-LATTICE/authorization-event/v0.7", **fields})
    event = AuthorizationEvent(
        **fields,
        mac=mac,
        event_hash=_digest(
            {
                "domain": "ATMAN-LATTICE/authorization-event-hash/v0.7",
                "material": {"domain": "ATMAN-LATTICE/authorization-event/v0.7", **fields},
                "mac": mac,
            }
        ),
    )
    event.validate()
    updated = AuthorizationLedger(
        generation=generation,
        head_event_hash=event.event_hash,
        events=(*ledger.events, event),
    )
    updated.validate()
    return updated, event


def consume_use_token(
    ledger: AuthorizationLedger,
    token: UseToken,
    *,
    current_context: object,
    now: int,
    token_keys: Mapping[str, bytes],
    event_keys: Mapping[str, bytes],
    expected_ledger_generation: int,
    actor_ref: str,
    reason_ref: str,
    event_key_id: str,
    event_secret: bytes,
) -> tuple[AuthorizationLedger, AuthorizationEvent]:
    """Atomically-modelled one-time consumption against the current authorization ledger."""
    ledger_valid, ledger_limitations = verify_authorization_ledger(ledger, event_keys=event_keys)
    if not ledger_valid:
        raise ValueError("authorization ledger invalid: " + ",".join(ledger_limitations))

    token_valid, token_limitations = verify_use_token(
        token,
        current_context=current_context,
        now=now,
        token_keys=token_keys,
    )
    if not token_valid:
        raise ValueError("use token not currently valid: " + ",".join(token_limitations))

    if token.context_digest != digest_context(current_context):
        raise ValueError("context_mismatch")

    return _append_terminal_event(
        ledger,
        token,
        event_type="CONSUMED",
        occurred_at=now,
        actor_ref=actor_ref,
        reason_ref=reason_ref,
        expected_ledger_generation=expected_ledger_generation,
        event_key_id=event_key_id,
        event_secret=event_secret,
    )


def revoke_use_token(
    ledger: AuthorizationLedger,
    token: UseToken,
    *,
    now: int,
    token_keys: Mapping[str, bytes],
    event_keys: Mapping[str, bytes],
    expected_ledger_generation: int,
    actor_ref: str,
    reason_ref: str,
    event_key_id: str,
    event_secret: bytes,
) -> tuple[AuthorizationLedger, AuthorizationEvent]:
    """Revoke the exact authenticated token independent of its current execution context."""
    ledger_valid, ledger_limitations = verify_authorization_ledger(ledger, event_keys=event_keys)
    if not ledger_valid:
        raise ValueError("authorization ledger invalid: " + ",".join(ledger_limitations))

    authentic, limitations = verify_use_token_authenticity(token, token_keys=token_keys)
    if not authentic:
        raise ValueError("use token not authentic: " + ",".join(limitations))

    return _append_terminal_event(
        ledger,
        token,
        event_type="REVOKED",
        occurred_at=now,
        actor_ref=actor_ref,
        reason_ref=reason_ref,
        expected_ledger_generation=expected_ledger_generation,
        event_key_id=event_key_id,
        event_secret=event_secret,
    )
