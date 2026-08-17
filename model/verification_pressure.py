from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Iterable, Literal

Decision = Literal["PASS", "HOLD", "FAIL"]
PressureStatus = Literal["NORMAL", "PRESSURED", "SATURATED"]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True)
class VerificationWorkItem:
    work_ref: str
    subject_identity_ref: str
    evidence_digest: str
    cost_units: int
    priority: int
    submitted_at: int
    work_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-work/v1.6",
            "work_ref": self.work_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "evidence_digest": self.evidence_digest,
            "cost_units": self.cost_units,
            "priority": self.priority,
            "submitted_at": self.submitted_at,
        }

    def validate(self) -> None:
        if not self.work_ref or not self.subject_identity_ref:
            raise ValueError("work_ref and subject_identity_ref are required")
        _require_digest("evidence_digest", self.evidence_digest)
        _require_digest("work_hash", self.work_hash)
        if self.cost_units <= 0:
            raise ValueError("cost_units must be > 0")
        if self.priority < 0:
            raise ValueError("priority must be >= 0")
        if self.submitted_at < 0:
            raise ValueError("submitted_at must be >= 0")
        if self.work_hash != _digest(self.material()):
            raise ValueError("work_hash does not match work material")


def make_verification_work(
    work_ref: str,
    *,
    subject_identity_ref: str,
    evidence: object,
    cost_units: int,
    priority: int = 0,
    submitted_at: int,
) -> VerificationWorkItem:
    evidence_digest = _digest(
        {
            "domain": "ATMAN-LATTICE/verification-evidence/v1.6",
            "evidence": evidence,
        }
    )
    provisional = VerificationWorkItem(
        work_ref=work_ref,
        subject_identity_ref=subject_identity_ref,
        evidence_digest=evidence_digest,
        cost_units=cost_units,
        priority=priority,
        submitted_at=submitted_at,
        work_hash="0" * 64,
    )
    item = VerificationWorkItem(
        work_ref=work_ref,
        subject_identity_ref=subject_identity_ref,
        evidence_digest=evidence_digest,
        cost_units=cost_units,
        priority=priority,
        submitted_at=submitted_at,
        work_hash=_digest(provisional.material()),
    )
    item.validate()
    return item


@dataclass(frozen=True)
class VerificationCapacityPolicy:
    policy_ref: str
    capacity_units: int
    max_admitted_items: int
    aging_quantum: int
    policy_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-capacity-policy/v1.6",
            "policy_ref": self.policy_ref,
            "capacity_units": self.capacity_units,
            "max_admitted_items": self.max_admitted_items,
            "aging_quantum": self.aging_quantum,
        }

    def validate(self) -> None:
        if not self.policy_ref:
            raise ValueError("policy_ref is required")
        if self.capacity_units < 0:
            raise ValueError("capacity_units must be >= 0")
        if self.max_admitted_items < 0:
            raise ValueError("max_admitted_items must be >= 0")
        if self.aging_quantum <= 0:
            raise ValueError("aging_quantum must be > 0")
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match policy material")


def make_verification_capacity_policy(
    policy_ref: str = "atman:verification-pressure:default:v1.6",
    *,
    capacity_units: int,
    max_admitted_items: int,
    aging_quantum: int = 60,
) -> VerificationCapacityPolicy:
    provisional = VerificationCapacityPolicy(
        policy_ref=policy_ref,
        capacity_units=capacity_units,
        max_admitted_items=max_admitted_items,
        aging_quantum=aging_quantum,
        policy_hash="0" * 64,
    )
    policy = VerificationCapacityPolicy(
        policy_ref=policy_ref,
        capacity_units=capacity_units,
        max_admitted_items=max_admitted_items,
        aging_quantum=aging_quantum,
        policy_hash=_digest(provisional.material()),
    )
    policy.validate()
    return policy


def _effective_priority(item: VerificationWorkItem, policy: VerificationCapacityPolicy, measured_at: int) -> int:
    waited = max(0, measured_at - item.submitted_at)
    return item.priority + waited // policy.aging_quantum


def _ranked(items: tuple[VerificationWorkItem, ...], policy: VerificationCapacityPolicy, measured_at: int) -> tuple[VerificationWorkItem, ...]:
    return tuple(
        sorted(
            items,
            key=lambda item: (
                -_effective_priority(item, policy, measured_at),
                item.submitted_at,
                item.work_hash,
            ),
        )
    )


@dataclass(frozen=True)
class VerificationPressureReceipt:
    policy_hash: str
    measured_at: int
    offered_work_hashes: tuple[str, ...]
    ranked_work_hashes: tuple[str, ...]
    admitted_work_hashes: tuple[str, ...]
    deferred_capacity_work_hashes: tuple[str, ...]
    deferred_oversized_work_hashes: tuple[str, ...]
    capacity_units: int
    used_units: int
    pressure_status: PressureStatus
    pressure_hash: str

    @property
    def deferred_work_hashes(self) -> tuple[str, ...]:
        return self.deferred_capacity_work_hashes + self.deferred_oversized_work_hashes

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-pressure/v1.6",
            "policy_hash": self.policy_hash,
            "measured_at": self.measured_at,
            "offered_work_hashes": list(self.offered_work_hashes),
            "ranked_work_hashes": list(self.ranked_work_hashes),
            "admitted_work_hashes": list(self.admitted_work_hashes),
            "deferred_capacity_work_hashes": list(self.deferred_capacity_work_hashes),
            "deferred_oversized_work_hashes": list(self.deferred_oversized_work_hashes),
            "capacity_units": self.capacity_units,
            "used_units": self.used_units,
            "pressure_status": self.pressure_status,
        }

    def validate(self) -> None:
        _require_digest("policy_hash", self.policy_hash)
        _require_digest("pressure_hash", self.pressure_hash)
        if self.measured_at < 0:
            raise ValueError("measured_at must be >= 0")
        if self.capacity_units < 0 or self.used_units < 0 or self.used_units > self.capacity_units:
            raise ValueError("invalid capacity accounting")
        if self.pressure_status not in {"NORMAL", "PRESSURED", "SATURATED"}:
            raise ValueError("invalid pressure_status")
        for collection in (
            self.offered_work_hashes,
            self.ranked_work_hashes,
            self.admitted_work_hashes,
            self.deferred_capacity_work_hashes,
            self.deferred_oversized_work_hashes,
        ):
            for value in collection:
                _require_digest("work_hash", value)
            if len(set(collection)) != len(collection):
                raise ValueError("duplicate work hash in pressure receipt")
        offered = set(self.offered_work_hashes)
        ranked = set(self.ranked_work_hashes)
        admitted = set(self.admitted_work_hashes)
        deferred_capacity = set(self.deferred_capacity_work_hashes)
        deferred_oversized = set(self.deferred_oversized_work_hashes)
        if ranked != offered:
            raise ValueError("ranked work must exactly cover offered work")
        if admitted & deferred_capacity or admitted & deferred_oversized or deferred_capacity & deferred_oversized:
            raise ValueError("work item cannot occupy multiple pressure dispositions")
        if admitted | deferred_capacity | deferred_oversized != offered:
            raise ValueError("pressure dispositions must exactly cover offered work")
        expected_status: PressureStatus
        if not deferred_capacity and not deferred_oversized:
            expected_status = "NORMAL"
        elif admitted:
            expected_status = "PRESSURED"
        else:
            expected_status = "SATURATED"
        if self.pressure_status != expected_status:
            raise ValueError("pressure_status does not match dispositions")
        if self.pressure_hash != _digest(self.material()):
            raise ValueError("pressure_hash does not match pressure material")


def _prepare_items(items: Iterable[VerificationWorkItem]) -> tuple[VerificationWorkItem, ...]:
    work = tuple(items)
    refs: set[str] = set()
    hashes: set[str] = set()
    for item in work:
        item.validate()
        if item.work_ref in refs:
            raise ValueError("duplicate work_ref")
        if item.work_hash in hashes:
            raise ValueError("duplicate work_hash")
        refs.add(item.work_ref)
        hashes.add(item.work_hash)
    return work


def schedule_verification(
    items: Iterable[VerificationWorkItem],
    policy: VerificationCapacityPolicy,
    *,
    measured_at: int,
) -> VerificationPressureReceipt:
    policy.validate()
    if measured_at < 0:
        raise ValueError("measured_at must be >= 0")
    work = _prepare_items(items)
    ranked = _ranked(work, policy, measured_at)

    admitted: list[str] = []
    deferred_capacity: list[str] = []
    deferred_oversized: list[str] = []
    used_units = 0

    for item in ranked:
        if item.cost_units > policy.capacity_units:
            deferred_oversized.append(item.work_hash)
            continue
        if len(admitted) >= policy.max_admitted_items:
            deferred_capacity.append(item.work_hash)
            continue
        if used_units + item.cost_units <= policy.capacity_units:
            admitted.append(item.work_hash)
            used_units += item.cost_units
        else:
            deferred_capacity.append(item.work_hash)

    if not deferred_capacity and not deferred_oversized:
        pressure_status: PressureStatus = "NORMAL"
    elif admitted:
        pressure_status = "PRESSURED"
    else:
        pressure_status = "SATURATED"

    fields = {
        "policy_hash": policy.policy_hash,
        "measured_at": measured_at,
        "offered_work_hashes": tuple(sorted(item.work_hash for item in work)),
        "ranked_work_hashes": tuple(item.work_hash for item in ranked),
        "admitted_work_hashes": tuple(admitted),
        "deferred_capacity_work_hashes": tuple(deferred_capacity),
        "deferred_oversized_work_hashes": tuple(deferred_oversized),
        "capacity_units": policy.capacity_units,
        "used_units": used_units,
        "pressure_status": pressure_status,
    }
    provisional = VerificationPressureReceipt(**fields, pressure_hash="0" * 64)
    receipt = VerificationPressureReceipt(**fields, pressure_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt


def verify_verification_pressure(
    receipt: VerificationPressureReceipt,
    items: Iterable[VerificationWorkItem],
    policy: VerificationCapacityPolicy,
) -> tuple[bool, tuple[str, ...]]:
    try:
        receipt.validate()
        expected = schedule_verification(items, policy, measured_at=receipt.measured_at)
    except ValueError:
        return False, ("invalid_pressure_evidence",)

    limitations: list[str] = []
    for field, limitation in (
        ("policy_hash", "pressure_policy_mismatch"),
        ("offered_work_hashes", "offered_work_mismatch"),
        ("ranked_work_hashes", "ranking_mismatch"),
        ("admitted_work_hashes", "admission_mismatch"),
        ("deferred_capacity_work_hashes", "capacity_deferral_mismatch"),
        ("deferred_oversized_work_hashes", "oversized_deferral_mismatch"),
        ("capacity_units", "capacity_units_mismatch"),
        ("used_units", "used_units_mismatch"),
        ("pressure_status", "pressure_status_mismatch"),
        ("pressure_hash", "pressure_hash_mismatch"),
    ):
        if getattr(receipt, field) != getattr(expected, field):
            limitations.append(limitation)
    return not limitations, tuple(limitations)


@dataclass(frozen=True)
class VerificationCoverageReceipt:
    pressure_hash: str
    base_decision: Decision
    completed_work_hashes: tuple[str, ...]
    pending_admitted_work_hashes: tuple[str, ...]
    deferred_work_hashes: tuple[str, ...]
    decision: Decision
    reasons: tuple[str, ...]
    coverage_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/verification-coverage/v1.6",
            "pressure_hash": self.pressure_hash,
            "base_decision": self.base_decision,
            "completed_work_hashes": list(self.completed_work_hashes),
            "pending_admitted_work_hashes": list(self.pending_admitted_work_hashes),
            "deferred_work_hashes": list(self.deferred_work_hashes),
            "decision": self.decision,
            "reasons": list(self.reasons),
        }

    def validate(self) -> None:
        _require_digest("pressure_hash", self.pressure_hash)
        _require_digest("coverage_hash", self.coverage_hash)
        if self.base_decision not in {"PASS", "HOLD", "FAIL"} or self.decision not in {"PASS", "HOLD", "FAIL"}:
            raise ValueError("invalid coverage decision")
        for collection in (
            self.completed_work_hashes,
            self.pending_admitted_work_hashes,
            self.deferred_work_hashes,
        ):
            for value in collection:
                _require_digest("work_hash", value)
            if len(set(collection)) != len(collection):
                raise ValueError("duplicate work hash in coverage receipt")
        if set(self.completed_work_hashes) & set(self.pending_admitted_work_hashes):
            raise ValueError("completed and pending admitted work must be disjoint")
        if self.coverage_hash != _digest(self.material()):
            raise ValueError("coverage_hash does not match coverage material")


def evaluate_verification_coverage(
    base_decision: Decision,
    pressure: VerificationPressureReceipt,
    items: Iterable[VerificationWorkItem],
    policy: VerificationCapacityPolicy,
    *,
    completed_work_hashes: Iterable[str],
) -> VerificationCoverageReceipt:
    if base_decision not in {"PASS", "HOLD", "FAIL"}:
        raise ValueError("invalid base_decision")
    work = _prepare_items(items)
    valid_pressure, limitations = verify_verification_pressure(pressure, work, policy)
    completed = tuple(sorted(set(completed_work_hashes)))
    reasons: list[str] = []
    decision: Decision = base_decision

    offered = set(pressure.offered_work_hashes)
    admitted = set(pressure.admitted_work_hashes)
    completed_set = set(completed)

    if not valid_pressure:
        decision = "FAIL"
        reasons.extend(f"pressure_evidence:{item}" for item in limitations)
    unknown_completion = completed_set - offered
    non_admitted_completion = completed_set - admitted
    if unknown_completion:
        decision = "FAIL"
        reasons.append("completion_not_offered")
    if non_admitted_completion:
        decision = "FAIL"
        reasons.append("completion_not_admitted")

    pending_admitted = tuple(sorted(admitted - completed_set))
    deferred = tuple(sorted(pressure.deferred_work_hashes))

    if decision != "FAIL" and (pending_admitted or deferred):
        decision = "HOLD"
        if pending_admitted:
            reasons.append("verification_pending")
        if deferred:
            reasons.append("verification_deferred_capacity")
    if base_decision == "FAIL":
        decision = "FAIL"
        reasons.append("base_decision_failed")
    elif base_decision == "HOLD" and decision == "PASS":
        decision = "HOLD"
        reasons.append("base_decision_hold")

    fields = {
        "pressure_hash": pressure.pressure_hash,
        "base_decision": base_decision,
        "completed_work_hashes": completed,
        "pending_admitted_work_hashes": pending_admitted,
        "deferred_work_hashes": deferred,
        "decision": decision,
        "reasons": tuple(dict.fromkeys(reasons)),
    }
    provisional = VerificationCoverageReceipt(**fields, coverage_hash="0" * 64)
    receipt = VerificationCoverageReceipt(**fields, coverage_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt
