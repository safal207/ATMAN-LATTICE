from __future__ import annotations

from dataclasses import asdict
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof
from model.consumption import AuthorizationEvent, AuthorizationLedger
from model.freshness import ObserverAttestation, UseToken
from model.lattice import IdentityReceipt, ObserverReceipt
from model.merge import ConflictResolution, MergeConflict, MergeReceipt
from model.replay import RestoreReceipt

PROTOCOL = "ATMAN-RUNTIME/1.1"

SUPPORTED_OPERATIONS = {
    "observe_space",
    "observe_time",
    "cross_axis_bind",
    "global_coherence",
    "issue_use_token",
    "consume_use_token",
    "revoke_use_token",
    "merge_branches",
}


def identity_receipt_to_dict(receipt: IdentityReceipt) -> dict[str, object]:
    receipt.validate()
    data = asdict(receipt)
    data["provenance_refs"] = list(receipt.provenance_refs)
    return data


def identity_receipt_from_dict(data: Mapping[str, object]) -> IdentityReceipt:
    receipt = IdentityReceipt(
        identity_ref=str(data["identity_ref"]),
        state_ref=str(data["state_ref"]),
        generation=int(data["generation"]),
        branch_ref=str(data["branch_ref"]),
        sequence=int(data["sequence"]),
        payload_digest=str(data["payload_digest"]),
        parent_receipt_hash=None if data.get("parent_receipt_hash") is None else str(data["parent_receipt_hash"]),
        lineage_root_hash=str(data["lineage_root_hash"]),
        receipt_hash=str(data["receipt_hash"]),
        provenance_refs=tuple(str(item) for item in data.get("provenance_refs", ())),
    )
    receipt.validate()
    return receipt


def observer_receipt_to_dict(receipt: ObserverReceipt) -> dict[str, object]:
    receipt.validate()
    data = asdict(receipt)
    data["input_state_refs"] = list(receipt.input_state_refs)
    data["evidence_refs"] = list(receipt.evidence_refs)
    data["limitations"] = list(receipt.limitations)
    return data


def observer_receipt_from_dict(data: Mapping[str, object]) -> ObserverReceipt:
    receipt = ObserverReceipt(
        observer_id=str(data["observer_id"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        branch_ref=str(data["branch_ref"]),
        generation=int(data["generation"]),
        lineage_root_hash=str(data["lineage_root_hash"]),
        verdict=str(data["verdict"]),
        input_state_refs=tuple(str(item) for item in data.get("input_state_refs", ())),
        evidence_refs=tuple(str(item) for item in data.get("evidence_refs", ())),
        limitations=tuple(str(item) for item in data.get("limitations", ())),
    )
    receipt.validate()
    return receipt


def observer_attestation_to_dict(attestation: ObserverAttestation) -> dict[str, object]:
    attestation.validate()
    return asdict(attestation)


def observer_attestation_from_dict(data: Mapping[str, object]) -> ObserverAttestation:
    attestation = ObserverAttestation(
        observer_id=str(data["observer_id"]),
        observer_receipt_digest=str(data["observer_receipt_digest"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        branch_ref=str(data["branch_ref"]),
        generation=int(data["generation"]),
        lineage_root_hash=str(data["lineage_root_hash"]),
        verdict=str(data["verdict"]),
        context_digest=str(data["context_digest"]),
        verified_at=int(data["verified_at"]),
        key_id=str(data["key_id"]),
        mac=str(data["mac"]),
    )
    attestation.validate()
    return attestation


def use_token_to_dict(token: UseToken) -> dict[str, object]:
    token.validate()
    return asdict(token)


def use_token_from_dict(data: Mapping[str, object]) -> UseToken:
    token = UseToken(
        subject_identity_ref=str(data["subject_identity_ref"]),
        branch_ref=str(data["branch_ref"]),
        generation=int(data["generation"]),
        lineage_root_hash=str(data["lineage_root_hash"]),
        observer_receipt_digest=str(data["observer_receipt_digest"]),
        attestation_digest=str(data["attestation_digest"]),
        context_digest=str(data["context_digest"]),
        issued_at=int(data["issued_at"]),
        expires_at=int(data["expires_at"]),
        key_id=str(data["key_id"]),
        mac=str(data["mac"]),
    )
    token.validate()
    return token


def authorization_event_to_dict(event: AuthorizationEvent) -> dict[str, object]:
    event.validate()
    return asdict(event)


def authorization_event_from_dict(data: Mapping[str, object]) -> AuthorizationEvent:
    event = AuthorizationEvent(
        ledger_generation=int(data["ledger_generation"]),
        event_type=str(data["event_type"]),
        token_digest=str(data["token_digest"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        branch_ref=str(data["branch_ref"]),
        subject_generation=int(data["subject_generation"]),
        lineage_root_hash=str(data["lineage_root_hash"]),
        context_digest=str(data["context_digest"]),
        occurred_at=int(data["occurred_at"]),
        actor_ref=str(data["actor_ref"]),
        reason_ref=str(data["reason_ref"]),
        previous_event_hash=None if data.get("previous_event_hash") is None else str(data["previous_event_hash"]),
        key_id=str(data["key_id"]),
        mac=str(data["mac"]),
        event_hash=str(data["event_hash"]),
    )
    event.validate()
    return event


def authorization_ledger_to_dict(ledger: AuthorizationLedger) -> dict[str, object]:
    ledger.validate()
    return {
        "generation": ledger.generation,
        "head_event_hash": ledger.head_event_hash,
        "events": [authorization_event_to_dict(event) for event in ledger.events],
    }


def authorization_ledger_from_dict(data: Mapping[str, object]) -> AuthorizationLedger:
    raw_events = data.get("events", ())
    if not isinstance(raw_events, (list, tuple)):
        raise ValueError("authorization ledger events must be an array")
    ledger = AuthorizationLedger(
        generation=int(data["generation"]),
        head_event_hash=None if data.get("head_event_hash") is None else str(data["head_event_hash"]),
        events=tuple(authorization_event_from_dict(_mapping(item, "authorization event")) for item in raw_events),
    )
    ledger.validate()
    return ledger


def restore_receipt_to_dict(receipt: RestoreReceipt) -> dict[str, object]:
    receipt.validate()
    return asdict(receipt)


def restore_receipt_from_dict(data: Mapping[str, object]) -> RestoreReceipt:
    receipt = RestoreReceipt(
        identity_ref=str(data["identity_ref"]),
        source_branch_ref=str(data["source_branch_ref"]),
        source_generation=int(data["source_generation"]),
        source_lineage_root_hash=str(data["source_lineage_root_hash"]),
        source_receipt_hash=str(data["source_receipt_hash"]),
        source_state_ref=str(data["source_state_ref"]),
        source_sequence=int(data["source_sequence"]),
        target_branch_ref=str(data["target_branch_ref"]),
        target_generation=int(data["target_generation"]),
        target_lineage_root_hash=str(data["target_lineage_root_hash"]),
        target_genesis_receipt_hash=str(data["target_genesis_receipt_hash"]),
        replayed_at=int(data["replayed_at"]),
        restore_hash=str(data["restore_hash"]),
    )
    receipt.validate()
    return receipt


def merge_conflict_to_dict(conflict: MergeConflict) -> dict[str, object]:
    conflict.validate()
    return asdict(conflict)


def merge_conflict_from_dict(data: Mapping[str, object]) -> MergeConflict:
    conflict = MergeConflict(
        conflict_ref=str(data["conflict_ref"]),
        left_digest=str(data["left_digest"]),
        right_digest=str(data["right_digest"]),
    )
    conflict.validate()
    return conflict


def conflict_resolution_to_dict(resolution: ConflictResolution) -> dict[str, object]:
    resolution.validate()
    return asdict(resolution)


def conflict_resolution_from_dict(data: Mapping[str, object]) -> ConflictResolution:
    resolution = ConflictResolution(
        conflict_ref=str(data["conflict_ref"]),
        left_digest=str(data["left_digest"]),
        right_digest=str(data["right_digest"]),
        strategy=str(data["strategy"]),
        result_digest=str(data["result_digest"]),
        reason_ref=str(data["reason_ref"]),
    )
    resolution.validate()
    return resolution


def merge_receipt_to_dict(receipt: MergeReceipt) -> dict[str, object]:
    receipt.validate()
    return asdict(receipt)


def authority_grant_to_dict(grant: AuthorityGrant) -> dict[str, object]:
    grant.validate()
    data = asdict(grant)
    data["roles"] = list(grant.roles)
    data["scopes"] = list(grant.scopes)
    return data


def authority_grant_from_dict(data: Mapping[str, object]) -> AuthorityGrant:
    grant = AuthorityGrant(
        grant_id=str(data["grant_id"]),
        subject_ref=str(data["subject_ref"]),
        key_id=str(data["key_id"]),
        public_key=str(data["public_key"]),
        roles=tuple(str(item) for item in data.get("roles", ())),
        scopes=tuple(str(item) for item in data.get("scopes", ())),
        policy_generation=int(data["policy_generation"]),
        valid_from=int(data["valid_from"]),
        valid_until=int(data["valid_until"]),
        issuer_ref=str(data["issuer_ref"]),
        issuer_key_id=str(data["issuer_key_id"]),
        issuer_signature=str(data["issuer_signature"]),
        grant_hash=str(data["grant_hash"]),
    )
    grant.validate()
    return grant


def authority_proof_to_dict(proof: AuthorityProof) -> dict[str, object]:
    proof.validate()
    return asdict(proof)


def authority_proof_from_dict(data: Mapping[str, object]) -> AuthorityProof:
    proof = AuthorityProof(
        subject_ref=str(data["subject_ref"]),
        key_id=str(data["key_id"]),
        grant_hash=str(data["grant_hash"]),
        role=str(data["role"]),
        scope=str(data["scope"]),
        action_digest=str(data["action_digest"]),
        policy_generation=int(data["policy_generation"]),
        signed_at=int(data["signed_at"]),
        signature=str(data["signature"]),
        proof_hash=str(data["proof_hash"]),
    )
    proof.validate()
    return proof


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def make_runtime_request(
    *,
    request_id: str,
    operation: str,
    payload: Mapping[str, object],
    grant: AuthorityGrant,
    proof: AuthorityProof,
) -> dict[str, object]:
    if not request_id:
        raise ValueError("request_id is required")
    if operation not in SUPPORTED_OPERATIONS:
        raise ValueError("unsupported runtime operation")
    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "operation": operation,
        "payload": dict(payload),
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
