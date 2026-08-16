from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Literal

from model.lattice import ObserverReceipt
from model.transition_geometry import (
    TransitionCurvatureReceipt,
    TransitionEndpoint,
    TransitionOperator,
    TransitionTorsionReceipt,
    verify_loop_curvature,
    verify_transition_torsion,
)

Decision = Literal["PASS", "HOLD", "FAIL"]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SEVERITY = {"PASS": 0, "HOLD": 1, "FAIL": 2}


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True)
class GeometricCoherencePolicy:
    policy_ref: str
    history_torsion_decision: Decision = "PASS"
    semantic_torsion_decision: Decision = "HOLD"
    holonomy_decision: Decision = "PASS"
    semantic_curvature_decision: Decision = "HOLD"
    policy_hash: str = ""

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/geometric-coherence-policy/v1.5",
            "policy_ref": self.policy_ref,
            "history_torsion_decision": self.history_torsion_decision,
            "semantic_torsion_decision": self.semantic_torsion_decision,
            "holonomy_decision": self.holonomy_decision,
            "semantic_curvature_decision": self.semantic_curvature_decision,
        }

    def validate(self) -> None:
        if not self.policy_ref:
            raise ValueError("policy_ref is required")
        for value in (
            self.history_torsion_decision,
            self.semantic_torsion_decision,
            self.holonomy_decision,
            self.semantic_curvature_decision,
        ):
            if value not in _SEVERITY:
                raise ValueError("invalid geometric policy decision")
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match policy material")


def make_geometric_policy(
    policy_ref: str = "atman:geometry:default:v1.5",
    *,
    history_torsion_decision: Decision = "PASS",
    semantic_torsion_decision: Decision = "HOLD",
    holonomy_decision: Decision = "PASS",
    semantic_curvature_decision: Decision = "HOLD",
) -> GeometricCoherencePolicy:
    provisional = GeometricCoherencePolicy(
        policy_ref=policy_ref,
        history_torsion_decision=history_torsion_decision,
        semantic_torsion_decision=semantic_torsion_decision,
        holonomy_decision=holonomy_decision,
        semantic_curvature_decision=semantic_curvature_decision,
        policy_hash="0" * 64,
    )
    policy = GeometricCoherencePolicy(
        policy_ref=policy_ref,
        history_torsion_decision=history_torsion_decision,
        semantic_torsion_decision=semantic_torsion_decision,
        holonomy_decision=holonomy_decision,
        semantic_curvature_decision=semantic_curvature_decision,
        policy_hash=_digest(provisional.material()),
    )
    policy.validate()
    return policy


@dataclass(frozen=True)
class TorsionEvidence:
    receipt: TransitionTorsionReceipt
    origin: TransitionEndpoint
    operator_a: TransitionOperator
    operator_b: TransitionOperator
    path_ab: TransitionEndpoint
    path_ba: TransitionEndpoint


@dataclass(frozen=True)
class CurvatureEvidence:
    receipt: TransitionCurvatureReceipt
    origin: TransitionEndpoint
    returned: TransitionEndpoint
    loop_operators: tuple[TransitionOperator, ...]


@dataclass(frozen=True)
class GeometricObserverReceipt:
    observer_id: str
    subject_identity_ref: str
    decision: Decision
    base_observer_id: str
    base_observer_verdict: str
    policy_hash: str
    torsion_hash: str | None
    torsion_status: str | None
    curvature_hash: str | None
    curvature_status: str | None
    evidence_refs: tuple[str, ...]
    reasons: tuple[str, ...]
    gate_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/geometric-observer-receipt/v1.5",
            "observer_id": self.observer_id,
            "subject_identity_ref": self.subject_identity_ref,
            "decision": self.decision,
            "base_observer_id": self.base_observer_id,
            "base_observer_verdict": self.base_observer_verdict,
            "policy_hash": self.policy_hash,
            "torsion_hash": self.torsion_hash,
            "torsion_status": self.torsion_status,
            "curvature_hash": self.curvature_hash,
            "curvature_status": self.curvature_status,
            "evidence_refs": list(self.evidence_refs),
            "reasons": list(self.reasons),
        }

    def validate(self) -> None:
        if self.observer_id not in {"A3-GEOMETRY", "A4-GEOMETRY"}:
            raise ValueError("invalid geometric observer_id")
        if not self.subject_identity_ref or not self.base_observer_id:
            raise ValueError("subject_identity_ref and base_observer_id are required")
        if self.decision not in _SEVERITY:
            raise ValueError("invalid geometric decision")
        if self.base_observer_verdict not in {"PASS", "FAIL"}:
            raise ValueError("invalid base observer verdict")
        _require_digest("policy_hash", self.policy_hash)
        if self.torsion_hash is not None:
            _require_digest("torsion_hash", self.torsion_hash)
        if self.curvature_hash is not None:
            _require_digest("curvature_hash", self.curvature_hash)
        _require_digest("gate_hash", self.gate_hash)
        if self.gate_hash != _digest(self.material()):
            raise ValueError("gate_hash does not match gate material")


def _combine(current: Decision, candidate: Decision) -> Decision:
    return candidate if _SEVERITY[candidate] > _SEVERITY[current] else current


def _torsion_decision(status: str, policy: GeometricCoherencePolicy) -> tuple[Decision, str | None]:
    if status == "CLOSED":
        return "PASS", None
    if status == "SEMANTICALLY_CLOSED_HISTORY_DIVERGENT":
        return policy.history_torsion_decision, "history_torsion_preserved"
    if status == "TORSION_DETECTED":
        return policy.semantic_torsion_decision, "semantic_torsion_detected"
    return "FAIL", "unknown_torsion_status"


def _curvature_decision(status: str, policy: GeometricCoherencePolicy) -> tuple[Decision, str | None]:
    if status == "FLAT_LOOP":
        return "PASS", None
    if status == "SEMANTICALLY_CLOSED_WITH_HOLONOMY":
        return policy.holonomy_decision, "history_holonomy_preserved"
    if status == "CURVATURE_DETECTED":
        return policy.semantic_curvature_decision, "semantic_curvature_detected"
    return "FAIL", "unknown_curvature_status"


def a3_geometric_gate(
    base_a3: ObserverReceipt,
    *,
    torsion: TorsionEvidence | None = None,
    curvature: CurvatureEvidence | None = None,
    policy: GeometricCoherencePolicy | None = None,
) -> GeometricObserverReceipt:
    base_a3.validate()
    if base_a3.observer_id != "A3":
        raise ValueError("base observer must be A3")
    policy = policy or make_geometric_policy()
    policy.validate()
    if torsion is None and curvature is None:
        raise ValueError("at least one geometric evidence item is required")

    decision: Decision = "PASS" if base_a3.verdict == "PASS" else "FAIL"
    reasons: list[str] = [] if base_a3.verdict == "PASS" else ["base_a3_failed"]
    evidence_refs = list(base_a3.evidence_refs)
    torsion_hash = torsion_status = curvature_hash = curvature_status = None

    if torsion is not None:
        valid, limitations = verify_transition_torsion(
            torsion.receipt,
            torsion.origin,
            torsion.operator_a,
            torsion.operator_b,
            torsion.path_ab,
            torsion.path_ba,
        )
        torsion_hash = torsion.receipt.torsion_hash
        torsion_status = torsion.receipt.status
        evidence_refs.append(f"torsion:{torsion_hash}")
        if not valid:
            decision = "FAIL"
            reasons.extend(f"torsion_evidence:{item}" for item in limitations)
        else:
            candidate, reason = _torsion_decision(torsion_status, policy)
            decision = _combine(decision, candidate)
            if reason is not None:
                reasons.append(reason)

    if curvature is not None:
        valid, limitations = verify_loop_curvature(
            curvature.receipt,
            curvature.origin,
            curvature.returned,
            curvature.loop_operators,
        )
        curvature_hash = curvature.receipt.curvature_hash
        curvature_status = curvature.receipt.status
        evidence_refs.append(f"curvature:{curvature_hash}")
        if not valid:
            decision = "FAIL"
            reasons.extend(f"curvature_evidence:{item}" for item in limitations)
        else:
            candidate, reason = _curvature_decision(curvature_status, policy)
            decision = _combine(decision, candidate)
            if reason is not None:
                reasons.append(reason)

    fields = {
        "observer_id": "A3-GEOMETRY",
        "subject_identity_ref": base_a3.subject_identity_ref,
        "decision": decision,
        "base_observer_id": base_a3.observer_id,
        "base_observer_verdict": base_a3.verdict,
        "policy_hash": policy.policy_hash,
        "torsion_hash": torsion_hash,
        "torsion_status": torsion_status,
        "curvature_hash": curvature_hash,
        "curvature_status": curvature_status,
        "evidence_refs": tuple(dict.fromkeys(evidence_refs)),
        "reasons": tuple(dict.fromkeys(reasons)),
    }
    provisional = GeometricObserverReceipt(**fields, gate_hash="0" * 64)
    receipt = GeometricObserverReceipt(**fields, gate_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt


def a4_geometric_coherence(
    base_a4: ObserverReceipt,
    geometric_receipts: tuple[GeometricObserverReceipt, ...],
    *,
    policy: GeometricCoherencePolicy | None = None,
) -> GeometricObserverReceipt:
    base_a4.validate()
    if base_a4.observer_id != "A4":
        raise ValueError("base observer must be A4")
    if not geometric_receipts:
        raise ValueError("at least one geometric observer receipt is required")
    policy = policy or make_geometric_policy()
    policy.validate()

    decision: Decision = "PASS" if base_a4.verdict == "PASS" else "FAIL"
    reasons: list[str] = [] if base_a4.verdict == "PASS" else ["base_a4_failed"]
    evidence_refs = list(base_a4.evidence_refs)

    for receipt in geometric_receipts:
        receipt.validate()
        if receipt.subject_identity_ref != base_a4.subject_identity_ref:
            decision = "FAIL"
            reasons.append("geometric_identity_mismatch")
        if receipt.policy_hash != policy.policy_hash:
            decision = "FAIL"
            reasons.append("geometric_policy_mismatch")
        decision = _combine(decision, receipt.decision)
        evidence_refs.append(f"geometry-gate:{receipt.gate_hash}")
        reasons.extend(receipt.reasons)

    fields = {
        "observer_id": "A4-GEOMETRY",
        "subject_identity_ref": base_a4.subject_identity_ref,
        "decision": decision,
        "base_observer_id": base_a4.observer_id,
        "base_observer_verdict": base_a4.verdict,
        "policy_hash": policy.policy_hash,
        "torsion_hash": None,
        "torsion_status": None,
        "curvature_hash": None,
        "curvature_status": None,
        "evidence_refs": tuple(dict.fromkeys(evidence_refs)),
        "reasons": tuple(dict.fromkeys(reasons)),
    }
    provisional = GeometricObserverReceipt(**fields, gate_hash="0" * 64)
    receipt = GeometricObserverReceipt(**fields, gate_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt
