from __future__ import annotations

from dataclasses import asdict
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof
from model.lattice import IdentityReceipt, ObserverReceipt

SUPPORTED_OPERATIONS = {
    "observe_space",
    "observe_time",
    "cross_axis_bind",
    "global_coherence",
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
        "protocol": "ATMAN-RUNTIME/1.0",
        "request_id": request_id,
        "operation": operation,
        "payload": dict(payload),
        "grant": authority_grant_to_dict(grant),
        "proof": authority_proof_to_dict(proof),
    }
