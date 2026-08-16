from __future__ import annotations

import json
import os
import sys
from typing import Mapping

from model.enforcement import (
    EnforcementContext,
    governed_consume_use_token,
    governed_cross_axis_bind,
    governed_global_coherence,
    governed_issue_use_token,
    governed_merge_branches,
    governed_observe_space,
    governed_observe_time,
    governed_revoke_use_token,
)
from model.runtime_governance import TRUST_OPERATIONS, TRUST_PROTOCOL
from model.runtime_protocol import (
    PROTOCOL,
    SUPPORTED_OPERATIONS,
    authority_grant_from_dict,
    authority_proof_from_dict,
    authorization_event_to_dict,
    authorization_ledger_to_dict,
    conflict_resolution_from_dict,
    identity_receipt_from_dict,
    identity_receipt_to_dict,
    merge_conflict_from_dict,
    merge_receipt_to_dict,
    observer_attestation_from_dict,
    observer_receipt_from_dict,
    observer_receipt_to_dict,
    restore_receipt_from_dict,
    use_token_from_dict,
    use_token_to_dict,
)
from model.runtime_store import (
    mutate_authorization_ledger,
    mutate_trust_policy,
    read_or_bootstrap_trust_policy,
)
from model.trust_root import (
    apply_trust_transition,
    create_bootstrap_policy,
    trust_approval_from_dict,
    trust_policy_to_dict,
    trust_transition_receipt_to_dict,
)


def _hex_key_map_from_env(name: str) -> dict[str, bytes]:
    raw = os.environ.get(name, "{}")
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ValueError(f"{name} must be a JSON object")
    keys: dict[str, bytes] = {}
    for key_id, key_hex in decoded.items():
        if not isinstance(key_id, str) or not isinstance(key_hex, str):
            raise ValueError(f"{name} entries must be string:string")
        keys[key_id] = bytes.fromhex(key_hex)
    return keys


def _bootstrap_trust_config() -> tuple[dict[str, bytes], int, int, int]:
    roots = _hex_key_map_from_env("ATMAN_TRUSTED_ISSUER_KEYS")
    generation = int(os.environ["ATMAN_POLICY_GENERATION"])
    threshold = int(os.environ.get("ATMAN_TRUST_THRESHOLD", "1"))
    activated_at = int(os.environ.get("ATMAN_TRUST_BOOTSTRAP_ACTIVATED_AT", "0"))
    return roots, generation, threshold, activated_at


def _current_trust_policy():
    roots, generation, threshold, activated_at = _bootstrap_trust_config()
    db_path = os.environ.get("ATMAN_RUNTIME_DB")
    if db_path:
        return read_or_bootstrap_trust_policy(
            db_path,
            bootstrap_roots=roots,
            bootstrap_generation=generation,
            bootstrap_threshold=threshold,
            bootstrap_activated_at=activated_at,
        )
    return create_bootstrap_policy(
        roots,
        generation=generation,
        threshold=threshold,
        activated_at=activated_at,
    )


def _server_enforcement() -> EnforcementContext:
    policy = _current_trust_policy()
    return EnforcementContext(
        trusted_issuer_keys=policy.root_map(),
        policy_generation=policy.generation,
        now=int(os.environ["ATMAN_RUNTIME_NOW"]),
    )


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _array(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _required_server_secret(keys: Mapping[str, bytes], key_id: str, family: str) -> bytes:
    secret = keys.get(key_id)
    if secret is None:
        raise PermissionError(f"unknown server-owned {family} key")
    return secret


def _decode_next_roots(value: object) -> dict[str, bytes]:
    mapping = _mapping(value, "next_roots")
    roots: dict[str, bytes] = {}
    for key_id, public_hex in mapping.items():
        if not isinstance(key_id, str) or not isinstance(public_hex, str):
            raise ValueError("next_roots entries must be string:string")
        roots[key_id] = bytes.fromhex(public_hex)
    if not roots:
        raise ValueError("next_roots must not be empty")
    return roots


def _execute_trust_request(request: Mapping[str, object]) -> dict[str, object]:
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in TRUST_OPERATIONS:
        raise ValueError("unsupported trust governance operation")
    payload = _mapping(request.get("payload", {}), "payload")

    db_path = os.environ.get("ATMAN_RUNTIME_DB")
    if not db_path:
        raise ValueError("trust governance requires ATMAN_RUNTIME_DB")
    roots, generation, threshold, activated_at = _bootstrap_trust_config()

    if operation == "get_trust_policy":
        policy = read_or_bootstrap_trust_policy(
            db_path,
            bootstrap_roots=roots,
            bootstrap_generation=generation,
            bootstrap_threshold=threshold,
            bootstrap_activated_at=activated_at,
        )
        return {
            "protocol": TRUST_PROTOCOL,
            "request_id": request_id,
            "ok": True,
            "policy": trust_policy_to_dict(policy),
        }

    next_roots = _decode_next_roots(payload.get("next_roots"))
    next_threshold = int(payload["next_threshold"])
    reason_ref = str(payload["reason_ref"])
    approvals = tuple(
        trust_approval_from_dict(_mapping(item, "trust approval"))
        for item in _array(payload.get("approvals"), "approvals")
    )
    transitioned_at = int(os.environ["ATMAN_RUNTIME_NOW"])

    def mutation(current):
        return apply_trust_transition(
            current,
            next_roots=next_roots,
            next_threshold=next_threshold,
            reason_ref=reason_ref,
            transitioned_at=transitioned_at,
            approvals=approvals,
        )

    policy, receipt = mutate_trust_policy(
        db_path,
        bootstrap_roots=roots,
        bootstrap_generation=generation,
        bootstrap_threshold=threshold,
        bootstrap_activated_at=activated_at,
        mutation=mutation,
    )
    return {
        "protocol": TRUST_PROTOCOL,
        "request_id": request_id,
        "ok": True,
        "policy": trust_policy_to_dict(policy),
        "transition": trust_transition_receipt_to_dict(receipt),
    }


def execute_request(request: Mapping[str, object]) -> dict[str, object]:
    request_protocol = request.get("protocol")
    if request_protocol == TRUST_PROTOCOL:
        return _execute_trust_request(request)
    if request_protocol != PROTOCOL:
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
        result = {"receipt": observer_receipt_to_dict(receipt)}

    elif operation == "observe_time":
        receipt = governed_observe_time(
            identity_receipt_from_dict(_mapping(payload.get("past"), "past")),
            identity_receipt_from_dict(_mapping(payload.get("future"), "future")),
            grant=grant,
            proof=proof,
            enforcement=enforcement,
        )
        result = {"receipt": observer_receipt_to_dict(receipt)}

    elif operation == "cross_axis_bind":
        receipt = governed_cross_axis_bind(
            observer_receipt_from_dict(_mapping(payload.get("a1"), "a1")),
            observer_receipt_from_dict(_mapping(payload.get("a2"), "a2")),
            grant=grant,
            proof=proof,
            enforcement=enforcement,
        )
        result = {"receipt": observer_receipt_to_dict(receipt)}

    elif operation == "global_coherence":
        observers = tuple(
            observer_receipt_from_dict(_mapping(item, "observer"))
            for item in _array(payload.get("observers"), "observers")
        )
        receipt = governed_global_coherence(
            observers,
            grant=grant,
            proof=proof,
            enforcement=enforcement,
        )
        result = {"receipt": observer_receipt_to_dict(receipt)}

    elif operation == "issue_use_token":
        attestation_keys = _hex_key_map_from_env("ATMAN_ATTESTATION_KEYS")
        token_keys = _hex_key_map_from_env("ATMAN_TOKEN_KEYS")
        token_key_id = str(payload.get("token_key_id", ""))
        token = governed_issue_use_token(
            observer_attestation_from_dict(_mapping(payload.get("attestation"), "attestation")),
            observer_receipt_from_dict(_mapping(payload.get("receipt"), "receipt")),
            current_context=payload.get("current_context"),
            now=enforcement.now,
            max_attestation_age_seconds=int(payload["max_attestation_age_seconds"]),
            attestation_keys=attestation_keys,
            token_key_id=token_key_id,
            token_secret=_required_server_secret(token_keys, token_key_id, "token"),
            ttl_seconds=int(payload["ttl_seconds"]),
            grant=grant,
            proof=proof,
            enforcement=enforcement,
        )
        result = {"token": use_token_to_dict(token)}

    elif operation in {"consume_use_token", "revoke_use_token"}:
        token_keys = _hex_key_map_from_env("ATMAN_TOKEN_KEYS")
        event_keys = _hex_key_map_from_env("ATMAN_EVENT_KEYS")
        event_key_id = str(payload.get("event_key_id", ""))
        token = use_token_from_dict(_mapping(payload.get("token"), "token"))
        db_path = os.environ["ATMAN_RUNTIME_DB"]
        expected_generation = int(payload["expected_ledger_generation"])
        actor_ref = str(payload["actor_ref"])
        reason_ref = str(payload["reason_ref"])
        event_secret = _required_server_secret(event_keys, event_key_id, "event")

        def mutation(current):
            common = dict(
                now=enforcement.now,
                token_keys=token_keys,
                event_keys=event_keys,
                expected_ledger_generation=expected_generation,
                actor_ref=actor_ref,
                reason_ref=reason_ref,
                event_key_id=event_key_id,
                event_secret=event_secret,
                grant=grant,
                proof=proof,
                enforcement=enforcement,
            )
            if operation == "consume_use_token":
                return governed_consume_use_token(
                    current,
                    token,
                    current_context=payload.get("current_context"),
                    **common,
                )
            return governed_revoke_use_token(current, token, **common)

        updated, event = mutate_authorization_ledger(
            db_path,
            token.subject_identity_ref,
            mutation,
        )
        result = {
            "ledger": authorization_ledger_to_dict(updated),
            "event": authorization_event_to_dict(event),
        }

    else:  # merge_branches
        left_chain = tuple(
            identity_receipt_from_dict(_mapping(item, "left receipt"))
            for item in _array(payload.get("left_chain"), "left_chain")
        )
        right_chain = tuple(
            identity_receipt_from_dict(_mapping(item, "right receipt"))
            for item in _array(payload.get("right_chain"), "right_chain")
        )
        conflicts = tuple(
            merge_conflict_from_dict(_mapping(item, "merge conflict"))
            for item in _array(payload.get("conflicts", []), "conflicts")
        )
        resolutions = tuple(
            conflict_resolution_from_dict(_mapping(item, "conflict resolution"))
            for item in _array(payload.get("resolutions", []), "resolutions")
        )
        target, merge = governed_merge_branches(
            identity_receipt_from_dict(_mapping(payload.get("ancestor"), "ancestor")),
            left_chain,
            restore_receipt_from_dict(_mapping(payload.get("left_restore"), "left_restore")),
            right_chain,
            restore_receipt_from_dict(_mapping(payload.get("right_restore"), "right_restore")),
            target_branch_ref=str(payload["target_branch_ref"]),
            target_generation=int(payload["target_generation"]),
            merged_payload=str(payload["merged_payload"]),
            conflicts=conflicts,
            resolutions=resolutions,
            merged_at=enforcement.now,
            grant=grant,
            proof=proof,
            enforcement=enforcement,
        )
        result = {
            "target": identity_receipt_to_dict(target),
            "merge": merge_receipt_to_dict(merge),
        }

    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "ok": True,
        **result,
    }


def main() -> int:
    request_protocol = PROTOCOL
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("runtime request must be a JSON object")
        request_protocol = str(request.get("protocol", PROTOCOL))
        response = execute_request(request)
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        response = {
            "protocol": request_protocol,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
