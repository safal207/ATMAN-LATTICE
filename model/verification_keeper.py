from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_verification import (
    VERIFY_PROTOCOL,
    RuntimeVerificationDecisionReceipt,
    _evaluate,
    _mapping,
    _state,
    geometric_observer_from_dict,
    runtime_decision_to_dict,
    verification_scope,
)

ROLE_VERIFICATION_KEEPER = "VERIFICATION_KEEPER"
FINALIZE_OPERATION = "finalize_geometric_verification"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def decision_state_hash(decision: RuntimeVerificationDecisionReceipt | Mapping[str, object]) -> str:
    if isinstance(decision, RuntimeVerificationDecisionReceipt):
        decision.validate()
        data = runtime_decision_to_dict(decision)
    else:
        data = dict(decision)
    data.pop("decided_at", None)
    data.pop("runtime_decision_hash", None)
    return _digest(
        {
            "domain": "ATMAN-LATTICE/runtime-verification-state/v1.7",
            "decision_state": data,
        }
    )


def action_finalize_verification(
    *,
    subject_identity_ref: str,
    target_gate_hash: str,
    decision_state_hash: str,
    schedule_generation: int,
    pressure_hash: str | None,
    finalized_at: int,
) -> dict[str, object]:
    return {
        "operation": FINALIZE_OPERATION,
        "subject_identity_ref": subject_identity_ref,
        "target_gate_hash": target_gate_hash,
        "decision_state_hash": decision_state_hash,
        "schedule_generation": schedule_generation,
        "pressure_hash": pressure_hash,
        "finalized_at": finalized_at,
    }


def _enforce(
    grant: AuthorityGrant,
    proof: AuthorityProof,
    *,
    action: object,
    required_scope: str,
    enforcement: EnforcementContext,
) -> None:
    valid, limitations = verify_authority_proof(
        grant,
        proof,
        action=action,
        trusted_issuer_keys=enforcement.trusted_issuer_keys,
        current_policy_generation=enforcement.policy_generation,
        now=enforcement.now,
    )
    failures = list(limitations)
    if proof.role != ROLE_VERIFICATION_KEEPER:
        failures.append("required_role_mismatch")
    if proof.scope != required_scope:
        failures.append("required_scope_mismatch")
    if not valid or failures:
        raise PermissionError("verification keeper authority failed: " + ",".join(dict.fromkeys(failures)))


@dataclass(frozen=True)
class VerificationFinalizationReceipt:
    subject_identity_ref: str
    target_gate_hash: str
    decision_state_hash: str
    runtime_decision_hash: str
    decision: str
    schedule_generation: int
    pressure_hash: str | None
    authority_proof_hash: str
    finalized_at: int
    finalization_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-finalization/v1.7",
            "subject_identity_ref": self.subject_identity_ref,
            "target_gate_hash": self.target_gate_hash,
            "decision_state_hash": self.decision_state_hash,
            "runtime_decision_hash": self.runtime_decision_hash,
            "decision": self.decision,
            "schedule_generation": self.schedule_generation,
            "pressure_hash": self.pressure_hash,
            "authority_proof_hash": self.authority_proof_hash,
            "finalized_at": self.finalized_at,
        }

    def validate(self) -> None:
        if self.decision not in {"PASS", "HOLD", "FAIL"}:
            raise ValueError("invalid finalization decision")
        if not self.subject_identity_ref or self.schedule_generation < 0 or self.finalized_at < 0:
            raise ValueError("invalid finalization fields")
        for value in (
            self.target_gate_hash,
            self.decision_state_hash,
            self.runtime_decision_hash,
            self.authority_proof_hash,
            self.finalization_hash,
        ):
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError("finalization digest must be lowercase SHA-256")
        if self.pressure_hash is not None and (len(self.pressure_hash) != 64 or any(ch not in "0123456789abcdef" for ch in self.pressure_hash)):
            raise ValueError("pressure_hash must be lowercase SHA-256")
        if self.finalization_hash != _digest(self.material()):
            raise ValueError("finalization_hash does not match finalization material")


def finalization_to_dict(receipt: VerificationFinalizationReceipt) -> dict[str, object]:
    receipt.validate()
    return asdict(receipt)


def execute_finalization_request(
    request: Mapping[str, object],
    *,
    enforcement: EnforcementContext,
    db_path: str,
) -> dict[str, object]:
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    payload = _mapping(request.get("payload", {}), "payload")
    gate = geometric_observer_from_dict(_mapping(payload.get("geometry_gate"), "geometry_gate"))
    expected_state_hash = str(payload.get("expected_decision_state_hash", ""))
    if not expected_state_hash:
        raise ValueError("expected_decision_state_hash is required")

    state = _state(db_path)
    current = _evaluate(db_path, gate, decided_at=enforcement.now)
    current_state_hash = decision_state_hash(current)
    if current_state_hash != expected_state_hash:
        raise PermissionError("stale verification decision: current runtime state no longer matches preview")

    pressure = state.get("pressure")
    pressure_hash = None if pressure is None else str(_mapping(pressure, "pressure")["pressure_hash"])
    action = action_finalize_verification(
        subject_identity_ref=gate.subject_identity_ref,
        target_gate_hash=gate.gate_hash,
        decision_state_hash=current_state_hash,
        schedule_generation=int(state["schedule_generation"]),
        pressure_hash=pressure_hash,
        finalized_at=enforcement.now,
    )
    grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
    proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
    _enforce(
        grant,
        proof,
        action=action,
        required_scope=verification_scope(gate.subject_identity_ref),
        enforcement=enforcement,
    )

    fields = {
        "subject_identity_ref": gate.subject_identity_ref,
        "target_gate_hash": gate.gate_hash,
        "decision_state_hash": current_state_hash,
        "runtime_decision_hash": current.runtime_decision_hash,
        "decision": current.decision,
        "schedule_generation": int(state["schedule_generation"]),
        "pressure_hash": pressure_hash,
        "authority_proof_hash": proof.proof_hash,
        "finalized_at": enforcement.now,
    }
    provisional = VerificationFinalizationReceipt(**fields, finalization_hash="0" * 64)
    receipt = VerificationFinalizationReceipt(**fields, finalization_hash=_digest(provisional.material()))
    receipt.validate()
    return {
        "protocol": VERIFY_PROTOCOL,
        "request_id": request_id,
        "ok": True,
        "decision_state_hash": current_state_hash,
        "decision": runtime_decision_to_dict(current),
        "finalization": finalization_to_dict(receipt),
    }
