from __future__ import annotations

from typing import Mapping

from model.trust_root import TrustApproval, trust_approval_to_dict

TRUST_PROTOCOL = "ATMAN-TRUST/1.2"
TRUST_OPERATIONS = {"get_trust_policy", "rotate_trust_roots"}


def make_trust_policy_request(*, request_id: str) -> dict[str, object]:
    if not request_id:
        raise ValueError("request_id is required")
    return {
        "protocol": TRUST_PROTOCOL,
        "request_id": request_id,
        "operation": "get_trust_policy",
        "payload": {},
    }


def make_trust_rotation_request(
    *,
    request_id: str,
    next_roots: Mapping[str, bytes],
    next_threshold: int,
    reason_ref: str,
    approvals: tuple[TrustApproval, ...],
) -> dict[str, object]:
    if not request_id:
        raise ValueError("request_id is required")
    if not next_roots:
        raise ValueError("next_roots are required")
    if not reason_ref:
        raise ValueError("reason_ref is required")
    return {
        "protocol": TRUST_PROTOCOL,
        "request_id": request_id,
        "operation": "rotate_trust_roots",
        "payload": {
            "next_roots": {key_id: public_key.hex() for key_id, public_key in sorted(next_roots.items())},
            "next_threshold": next_threshold,
            "reason_ref": reason_ref,
            "approvals": [trust_approval_to_dict(approval) for approval in approvals],
        },
    }
