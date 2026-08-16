from __future__ import annotations

import json
import os
import sys
from typing import Mapping

from model.enforcement import (
    EnforcementContext,
    governed_cross_axis_bind,
    governed_global_coherence,
    governed_observe_space,
    governed_observe_time,
)
from model.runtime_protocol import (
    SUPPORTED_OPERATIONS,
    authority_grant_from_dict,
    authority_proof_from_dict,
    identity_receipt_from_dict,
    observer_receipt_from_dict,
    observer_receipt_to_dict,
)

PROTOCOL = "ATMAN-RUNTIME/1.0"


def _trusted_roots_from_env() -> dict[str, bytes]:
    raw = os.environ.get("ATMAN_TRUSTED_ISSUER_KEYS", "{}")
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ValueError("ATMAN_TRUSTED_ISSUER_KEYS must be a JSON object")
    roots: dict[str, bytes] = {}
    for key_id, public_key_hex in decoded.items():
        if not isinstance(key_id, str) or not isinstance(public_key_hex, str):
            raise ValueError("trusted root entries must be string:string")
        roots[key_id] = bytes.fromhex(public_key_hex)
    return roots


def _server_enforcement() -> EnforcementContext:
    policy_generation = int(os.environ["ATMAN_POLICY_GENERATION"])
    now = int(os.environ["ATMAN_RUNTIME_NOW"])
    return EnforcementContext(
        trusted_issuer_keys=_trusted_roots_from_env(),
        policy_generation=policy_generation,
        now=now,
    )


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def execute_request(request: Mapping[str, object]) -> dict[str, object]:
    if request.get("protocol") != PROTOCOL:
        raise ValueError("unsupported runtime protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in SUPPORTED_OPERATIONS:
        raise ValueError("unsupported runtime operation")

    payload = _mapping(request.get("payload"), "payload")
    grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
    proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
    enforcement = _server_enforcement()

    if operation == "observe_space":
        receipt = governed_observe_space(
            identity_receipt_from_dict(_mapping(payload.get("left"), "left")),
            identity_receipt_from_dict(_mapping(payload.get("right"), "right")),
            grant=grant,
            proof=proof,
            enforcement=enforcement,
        )
    elif operation == "observe_time":
        receipt = governed_observe_time(
            identity_receipt_from_dict(_mapping(payload.get("past"), "past")),
            identity_receipt_from_dict(_mapping(payload.get("future"), "future")),
            grant=grant,
            proof=proof,
            enforcement=enforcement,
        )
    elif operation == "cross_axis_bind":
        receipt = governed_cross_axis_bind(
            observer_receipt_from_dict(_mapping(payload.get("a1"), "a1")),
            observer_receipt_from_dict(_mapping(payload.get("a2"), "a2")),
            grant=grant,
            proof=proof,
            enforcement=enforcement,
        )
    else:
        raw_observers = payload.get("observers")
        if not isinstance(raw_observers, list):
            raise ValueError("observers must be an array")
        observers = tuple(
            observer_receipt_from_dict(_mapping(item, "observer"))
            for item in raw_observers
        )
        receipt = governed_global_coherence(
            observers,
            grant=grant,
            proof=proof,
            enforcement=enforcement,
        )

    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "ok": True,
        "receipt": observer_receipt_to_dict(receipt),
    }


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("runtime request must be a JSON object")
        response = execute_request(request)
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:  # boundary translates internal failure into a typed external rejection
        response = {
            "protocol": PROTOCOL,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
