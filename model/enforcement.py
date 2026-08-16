from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.consumption import (
    AuthorizationEvent,
    AuthorizationLedger,
    digest_use_token,
    revoke_use_token,
)
from model.freshness import (
    ObserverAttestation,
    UseToken,
    digest_attestation,
    digest_context,
    digest_observer_receipt,
    issue_use_token,
)
from model.lattice import (
    IdentityReceipt,
    ObserverReceipt,
    cross_axis_bind,
    digest_payload,
    global_coherence,
    observe_space,
    observe_time,
)
from model.merge import (
    ConflictResolution,
    MergeConflict,
    MergeReceipt,
    digest_resolution_set,
    merge_branches,
)
from model.replay import RestoreReceipt

ROLE_A1 = "A1_OBSERVER"
ROLE_A2 = "A2_OBSERVER"
ROLE_A3 = "A3_BINDER"
ROLE_A4 = "A4_KEEPER"
ROLE_USE_TOKEN_ISSUER = "USE_TOKEN_ISSUER"
ROLE_USE_TOKEN_REVOKER = "USE_TOKEN_REVOKER"
ROLE_BRANCH_MERGER = "BRANCH_MERGER"


@dataclass(frozen=True)
class EnforcementContext:
    trusted_issuer_keys: Mapping[str, bytes]
    policy_generation: int
    now: int

    def validate(self) -> None:
        if self.policy_generation < 0:
            raise ValueError("policy_generation must be >= 0")
        if self.now < 0:
            raise ValueError("now must be >= 0")


def identity_scope(identity_ref: str) -> str:
    if not identity_ref:
        raise ValueError("identity_ref is required")
    return f"identity:{identity_ref}"


def authorization_scope(identity_ref: str) -> str:
    if not identity_ref:
        raise ValueError("identity_ref is required")
    return f"authorization:{identity_ref}"


def _require_authority(
    grant: AuthorityGrant,
    proof: AuthorityProof,
    *,
    action: object,
    required_role: str,
    required_scope: str,
    enforcement: EnforcementContext,
) -> None:
    enforcement.validate()
    valid, limitations = verify_authority_proof(
        grant,
        proof,
        action=action,
        trusted_issuer_keys=enforcement.trusted_issuer_keys,
        current_policy_generation=enforcement.policy_generation,
        now=enforcement.now,
    )
    failures = list(limitations)
    if proof.role != required_role:
        failures.append("required_role_mismatch")
    if proof.scope != required_scope:
        failures.append("required_scope_mismatch")
    if not valid or failures:
        raise PermissionError("authority enforcement failed: " + ",".join(dict.fromkeys(failures)))


def action_observe_space(s1: IdentityReceipt, s2: IdentityReceipt) -> dict[str, object]:
    s1.validate()
    s2.validate()
    return {
        "operation": "observe_space",
        "left_receipt_hash": s1.receipt_hash,
        "right_receipt_hash": s2.receipt_hash,
        "left_identity_ref": s1.identity_ref,
        "right_identity_ref": s2.identity_ref,
    }


def action_observe_time(s4: IdentityReceipt, s5: IdentityReceipt) -> dict[str, object]:
    s4.validate()
    s5.validate()
    return {
        "operation": "observe_time",
        "past_receipt_hash": s4.receipt_hash,
        "future_receipt_hash": s5.receipt_hash,
        "past_identity_ref": s4.identity_ref,
        "future_identity_ref": s5.identity_ref,
    }


def action_cross_axis(a1: ObserverReceipt, a2: ObserverReceipt) -> dict[str, object]:
    a1.validate()
    a2.validate()
    return {
        "operation": "cross_axis_bind",
        "a1_digest": digest_observer_receipt(a1),
        "a2_digest": digest_observer_receipt(a2),
        "subject_identity_ref": a1.subject_identity_ref,
    }


def action_global_coherence(observers: Iterable[ObserverReceipt]) -> tuple[tuple[ObserverReceipt, ...], dict[str, object]]:
    receipts = tuple(observers)
    if not receipts:
        raise ValueError("at least one observer receipt is required")
    for receipt in receipts:
        receipt.validate()
    return receipts, {
        "operation": "global_coherence",
        "observer_receipt_digests": [digest_observer_receipt(receipt) for receipt in receipts],
        "subject_identity_ref": receipts[0].subject_identity_ref,
    }


def action_issue_use_token(
    attestation: ObserverAttestation,
    receipt: ObserverReceipt,
    *,
    current_context: object,
    now: int,
    ttl_seconds: int,
    token_key_id: str,
) -> dict[str, object]:
    attestation.validate()
    receipt.validate()
    return {
        "operation": "issue_use_token",
        "observer_receipt_digest": digest_observer_receipt(receipt),
        "attestation_digest": digest_attestation(attestation),
        "context_digest": digest_context(current_context),
        "subject_identity_ref": receipt.subject_identity_ref,
        "issued_at": now,
        "ttl_seconds": ttl_seconds,
        "token_key_id": token_key_id,
    }


def action_revoke_use_token(
    ledger: AuthorizationLedger,
    token: UseToken,
    *,
    now: int,
    actor_ref: str,
    reason_ref: str,
    expected_ledger_generation: int,
) -> dict[str, object]:
    ledger.validate()
    token.validate()
    return {
        "operation": "revoke_use_token",
        "token_digest": digest_use_token(token),
        "subject_identity_ref": token.subject_identity_ref,
        "ledger_generation": ledger.generation,
        "expected_ledger_generation": expected_ledger_generation,
        "occurred_at": now,
        "actor_ref": actor_ref,
        "reason_ref": reason_ref,
    }


def action_merge_branches(
    ancestor: IdentityReceipt,
    left_chain: Iterable[IdentityReceipt],
    right_chain: Iterable[IdentityReceipt],
    *,
    target_branch_ref: str,
    target_generation: int,
    merged_payload: str | bytes,
    conflicts: Iterable[MergeConflict],
    resolutions: Iterable[ConflictResolution],
    merged_at: int,
) -> tuple[
    tuple[IdentityReceipt, ...],
    tuple[IdentityReceipt, ...],
    tuple[MergeConflict, ...],
    tuple[ConflictResolution, ...],
    dict[str, object],
]:
    ancestor.validate()
    left = tuple(left_chain)
    right = tuple(right_chain)
    conflict_items = tuple(conflicts)
    resolution_items = tuple(resolutions)
    if not left or not right:
        raise ValueError("merge parent chains must not be empty")
    for receipt in (*left, *right):
        receipt.validate()
    resolution_digest = digest_resolution_set(conflict_items, resolution_items)
    action = {
        "operation": "merge_branches",
        "identity_ref": ancestor.identity_ref,
        "ancestor_receipt_hash": ancestor.receipt_hash,
        "left_head_receipt_hash": left[-1].receipt_hash,
        "right_head_receipt_hash": right[-1].receipt_hash,
        "target_branch_ref": target_branch_ref,
        "target_generation": target_generation,
        "merged_payload_digest": digest_payload(merged_payload),
        "resolution_digest": resolution_digest,
        "merged_at": merged_at,
    }
    return left, right, conflict_items, resolution_items, action


def governed_observe_space(
    s1: IdentityReceipt,
    s2: IdentityReceipt,
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> ObserverReceipt:
    action = action_observe_space(s1, s2)
    _require_authority(
        grant,
        proof,
        action=action,
        required_role=ROLE_A1,
        required_scope=identity_scope(s1.identity_ref),
        enforcement=enforcement,
    )
    return observe_space(s1, s2)


def governed_observe_time(
    s4: IdentityReceipt,
    s5: IdentityReceipt,
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> ObserverReceipt:
    action = action_observe_time(s4, s5)
    _require_authority(
        grant,
        proof,
        action=action,
        required_role=ROLE_A2,
        required_scope=identity_scope(s4.identity_ref),
        enforcement=enforcement,
    )
    return observe_time(s4, s5)


def governed_cross_axis_bind(
    a1: ObserverReceipt,
    a2: ObserverReceipt,
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> ObserverReceipt:
    action = action_cross_axis(a1, a2)
    _require_authority(
        grant,
        proof,
        action=action,
        required_role=ROLE_A3,
        required_scope=identity_scope(a1.subject_identity_ref),
        enforcement=enforcement,
    )
    return cross_axis_bind(a1, a2)


def governed_global_coherence(
    observers: Iterable[ObserverReceipt],
    *,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> ObserverReceipt:
    receipts, action = action_global_coherence(observers)
    _require_authority(
        grant,
        proof,
        action=action,
        required_role=ROLE_A4,
        required_scope=identity_scope(receipts[0].subject_identity_ref),
        enforcement=enforcement,
    )
    return global_coherence(receipts)


def governed_issue_use_token(
    attestation: ObserverAttestation,
    receipt: ObserverReceipt,
    *,
    current_context: object,
    now: int,
    max_attestation_age_seconds: int,
    attestation_keys: Mapping[str, bytes],
    token_key_id: str,
    token_secret: bytes,
    ttl_seconds: int,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> UseToken:
    action = action_issue_use_token(
        attestation,
        receipt,
        current_context=current_context,
        now=now,
        ttl_seconds=ttl_seconds,
        token_key_id=token_key_id,
    )
    _require_authority(
        grant,
        proof,
        action=action,
        required_role=ROLE_USE_TOKEN_ISSUER,
        required_scope=authorization_scope(receipt.subject_identity_ref),
        enforcement=enforcement,
    )
    return issue_use_token(
        attestation,
        receipt,
        current_context=current_context,
        now=now,
        max_attestation_age_seconds=max_attestation_age_seconds,
        attestation_keys=attestation_keys,
        token_key_id=token_key_id,
        token_secret=token_secret,
        ttl_seconds=ttl_seconds,
    )


def governed_revoke_use_token(
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
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> tuple[AuthorizationLedger, AuthorizationEvent]:
    action = action_revoke_use_token(
        ledger,
        token,
        now=now,
        actor_ref=actor_ref,
        reason_ref=reason_ref,
        expected_ledger_generation=expected_ledger_generation,
    )
    _require_authority(
        grant,
        proof,
        action=action,
        required_role=ROLE_USE_TOKEN_REVOKER,
        required_scope=authorization_scope(token.subject_identity_ref),
        enforcement=enforcement,
    )
    return revoke_use_token(
        ledger,
        token,
        now=now,
        token_keys=token_keys,
        event_keys=event_keys,
        expected_ledger_generation=expected_ledger_generation,
        actor_ref=actor_ref,
        reason_ref=reason_ref,
        event_key_id=event_key_id,
        event_secret=event_secret,
    )


def governed_merge_branches(
    ancestor: IdentityReceipt,
    left_chain: Iterable[IdentityReceipt],
    left_restore: RestoreReceipt,
    right_chain: Iterable[IdentityReceipt],
    right_restore: RestoreReceipt,
    *,
    target_branch_ref: str,
    target_generation: int,
    merged_payload: str | bytes,
    conflicts: Iterable[MergeConflict] = (),
    resolutions: Iterable[ConflictResolution] = (),
    merged_at: int,
    grant: AuthorityGrant,
    proof: AuthorityProof,
    enforcement: EnforcementContext,
) -> tuple[IdentityReceipt, MergeReceipt]:
    left, right, conflict_items, resolution_items, action = action_merge_branches(
        ancestor,
        left_chain,
        right_chain,
        target_branch_ref=target_branch_ref,
        target_generation=target_generation,
        merged_payload=merged_payload,
        conflicts=conflicts,
        resolutions=resolutions,
        merged_at=merged_at,
    )
    _require_authority(
        grant,
        proof,
        action=action,
        required_role=ROLE_BRANCH_MERGER,
        required_scope=identity_scope(ancestor.identity_ref),
        enforcement=enforcement,
    )
    return merge_branches(
        ancestor,
        left,
        left_restore,
        right,
        right_restore,
        target_branch_ref=target_branch_ref,
        target_generation=target_generation,
        merged_payload=merged_payload,
        conflicts=conflict_items,
        resolutions=resolution_items,
        merged_at=merged_at,
    )
