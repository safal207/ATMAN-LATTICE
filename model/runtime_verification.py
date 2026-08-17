from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
import sqlite3
from typing import Mapping, Literal

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.enforcement import EnforcementContext
from model.geometric_coherence import GeometricObserverReceipt
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.verification_pressure import (
    VerificationCapacityPolicy,
    VerificationPressureReceipt,
    VerificationWorkItem,
    make_verification_capacity_policy,
    make_verification_work,
    schedule_verification,
)

VERIFY_PROTOCOL = "ATMAN-VERIFY/1.7"
VERIFY_OPERATIONS = {
    "submit_verification_work",
    "schedule_verification",
    "complete_verification_work",
    "get_verification_state",
    "evaluate_geometric_verification",
}

ROLE_VERIFICATION_SUBMITTER = "VERIFICATION_SUBMITTER"
ROLE_VERIFICATION_EXECUTOR = "VERIFICATION_EXECUTOR"
Decision = Literal["PASS", "HOLD", "FAIL"]
_SEVERITY = {"PASS": 0, "HOLD": 1, "FAIL": 2}


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def verification_scope(identity_ref: str) -> str:
    if not identity_ref:
        raise ValueError("identity_ref is required")
    return f"verification:{identity_ref}"


def geometric_observer_to_dict(receipt: GeometricObserverReceipt) -> dict[str, object]:
    receipt.validate()
    data = asdict(receipt)
    data["evidence_refs"] = list(receipt.evidence_refs)
    data["reasons"] = list(receipt.reasons)
    return data


def geometric_observer_from_dict(data: Mapping[str, object]) -> GeometricObserverReceipt:
    receipt = GeometricObserverReceipt(
        observer_id=str(data["observer_id"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        decision=str(data["decision"]),
        base_observer_id=str(data["base_observer_id"]),
        base_observer_verdict=str(data["base_observer_verdict"]),
        policy_hash=str(data["policy_hash"]),
        torsion_hash=None if data.get("torsion_hash") is None else str(data["torsion_hash"]),
        torsion_status=None if data.get("torsion_status") is None else str(data["torsion_status"]),
        curvature_hash=None if data.get("curvature_hash") is None else str(data["curvature_hash"]),
        curvature_status=None if data.get("curvature_status") is None else str(data["curvature_status"]),
        evidence_refs=tuple(str(item) for item in data.get("evidence_refs", ())),
        reasons=tuple(str(item) for item in data.get("reasons", ())),
        gate_hash=str(data["gate_hash"]),
    )
    receipt.validate()
    return receipt


def work_to_dict(item: VerificationWorkItem) -> dict[str, object]:
    item.validate()
    return asdict(item)


def work_from_dict(data: Mapping[str, object]) -> VerificationWorkItem:
    item = VerificationWorkItem(
        work_ref=str(data["work_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        evidence_digest=str(data["evidence_digest"]),
        cost_units=int(data["cost_units"]),
        priority=int(data["priority"]),
        submitted_at=int(data["submitted_at"]),
        work_hash=str(data["work_hash"]),
    )
    item.validate()
    return item


def pressure_to_dict(receipt: VerificationPressureReceipt) -> dict[str, object]:
    receipt.validate()
    data = asdict(receipt)
    for key in (
        "offered_work_hashes",
        "ranked_work_hashes",
        "admitted_work_hashes",
        "deferred_capacity_work_hashes",
        "deferred_oversized_work_hashes",
    ):
        data[key] = list(data[key])
    return data


def pressure_from_dict(data: Mapping[str, object]) -> VerificationPressureReceipt:
    receipt = VerificationPressureReceipt(
        policy_hash=str(data["policy_hash"]),
        measured_at=int(data["measured_at"]),
        offered_work_hashes=tuple(str(item) for item in data.get("offered_work_hashes", ())),
        ranked_work_hashes=tuple(str(item) for item in data.get("ranked_work_hashes", ())),
        admitted_work_hashes=tuple(str(item) for item in data.get("admitted_work_hashes", ())),
        deferred_capacity_work_hashes=tuple(str(item) for item in data.get("deferred_capacity_work_hashes", ())),
        deferred_oversized_work_hashes=tuple(str(item) for item in data.get("deferred_oversized_work_hashes", ())),
        capacity_units=int(data["capacity_units"]),
        used_units=int(data["used_units"]),
        pressure_status=str(data["pressure_status"]),
        pressure_hash=str(data["pressure_hash"]),
    )
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class VerificationCompletionReceipt:
    work_hash: str
    subject_identity_ref: str
    target_gate_hash: str
    schedule_generation: int
    pressure_hash: str
    decision: Decision
    evidence_digest: str
    completed_at: int
    actor_ref: str
    completion_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/runtime-verification-completion/v1.7",
            "work_hash": self.work_hash,
            "subject_identity_ref": self.subject_identity_ref,
            "target_gate_hash": self.target_gate_hash,
            "schedule_generation": self.schedule_generation,
            "pressure_hash": self.pressure_hash,
            "decision": self.decision,
            "evidence_digest": self.evidence_digest,
            "completed_at": self.completed_at,
            "actor_ref": self.actor_ref,
        }

    def validate(self) -> None:
        if self.decision not in _SEVERITY:
            raise ValueError("invalid completion decision")
        if self.schedule_generation <= 0 or self.completed_at < 0:
            raise ValueError("invalid completion time/generation")
        if not self.subject_identity_ref or not self.actor_ref:
            raise ValueError("subject_identity_ref and actor_ref are required")
        for value in (
            self.work_hash,
            self.target_gate_hash,
            self.pressure_hash,
            self.evidence_digest,
            self.completion_hash,
        ):
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError("completion digest must be lowercase SHA-256")
        if self.completion_hash != _digest(self.material()):
            raise ValueError("completion_hash does not match completion material")


def completion_to_dict(receipt: VerificationCompletionReceipt) -> dict[str, object]:
    receipt.validate()
    return asdict(receipt)


def completion_from_dict(data: Mapping[str, object]) -> VerificationCompletionReceipt:
    receipt = VerificationCompletionReceipt(
        work_hash=str(data["work_hash"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        target_gate_hash=str(data["target_gate_hash"]),
        schedule_generation=int(data["schedule_generation"]),
        pressure_hash=str(data["pressure_hash"]),
        decision=str(data["decision"]),
        evidence_digest=str(data["evidence_digest"]),
        completed_at=int(data["completed_at"]),
        actor_ref=str(data["actor_ref"]),
        completion_hash=str(data["completion_hash"]),
    )
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class RuntimeVerificationDecisionReceipt:
    subject_identity_ref: str
    target_gate_hash: str
    base_decision: Decision
    schedule_generation: int
    pressure_hash: str | None
    required_work_hashes: tuple[str, ...]
    completed_completion_hashes: tuple[str, ...]
    pending_work_hashes: tuple[str, ...]
    deferred_work_hashes: tuple[str, ...]
    decision: Decision
    reasons: tuple[str, ...]
    decided_at: int
    runtime_decision_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/runtime-verification-decision/v1.7",
            "subject_identity_ref": self.subject_identity_ref,
            "target_gate_hash": self.target_gate_hash,
            "base_decision": self.base_decision,
            "schedule_generation": self.schedule_generation,
            "pressure_hash": self.pressure_hash,
            "required_work_hashes": list(self.required_work_hashes),
            "completed_completion_hashes": list(self.completed_completion_hashes),
            "pending_work_hashes": list(self.pending_work_hashes),
            "deferred_work_hashes": list(self.deferred_work_hashes),
            "decision": self.decision,
            "reasons": list(self.reasons),
            "decided_at": self.decided_at,
        }

    def validate(self) -> None:
        if self.base_decision not in _SEVERITY or self.decision not in _SEVERITY:
            raise ValueError("invalid runtime verification decision")
        if self.schedule_generation < 0 or self.decided_at < 0:
            raise ValueError("invalid runtime decision generation/time")
        if not self.subject_identity_ref:
            raise ValueError("subject_identity_ref is required")
        for value in (self.target_gate_hash, self.runtime_decision_hash):
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError("runtime decision digest must be lowercase SHA-256")
        if self.pressure_hash is not None and (len(self.pressure_hash) != 64 or any(ch not in "0123456789abcdef" for ch in self.pressure_hash)):
            raise ValueError("pressure_hash must be lowercase SHA-256")
        required = set(self.required_work_hashes)
        pending = set(self.pending_work_hashes)
        deferred = set(self.deferred_work_hashes)
        if pending & deferred or not (pending | deferred).issubset(required):
            raise ValueError("invalid runtime work partition")
        if self.runtime_decision_hash != _digest(self.material()):
            raise ValueError("runtime_decision_hash does not match decision material")


def runtime_decision_to_dict(receipt: RuntimeVerificationDecisionReceipt) -> dict[str, object]:
    receipt.validate()
    data = asdict(receipt)
    for key in (
        "required_work_hashes",
        "completed_completion_hashes",
        "pending_work_hashes",
        "deferred_work_hashes",
        "reasons",
    ):
        data[key] = list(data[key])
    return data


def make_capacity_policy_from_env() -> VerificationCapacityPolicy:
    return make_verification_capacity_policy(
        os.environ.get("ATMAN_VERIFICATION_POLICY_REF", "atman:verification-runtime:v1.7"),
        capacity_units=int(os.environ.get("ATMAN_VERIFICATION_CAPACITY_UNITS", "10")),
        max_admitted_items=int(os.environ.get("ATMAN_VERIFICATION_MAX_ADMITTED_ITEMS", "10")),
        aging_quantum=int(os.environ.get("ATMAN_VERIFICATION_AGING_QUANTUM", "60")),
    )


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_work (
            work_hash TEXT PRIMARY KEY,
            work_ref TEXT NOT NULL UNIQUE,
            subject_identity_ref TEXT NOT NULL,
            target_gate_hash TEXT NOT NULL,
            work_json TEXT NOT NULL,
            status TEXT NOT NULL,
            completion_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_schedule (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            generation INTEGER NOT NULL,
            pressure_json TEXT NOT NULL
        )
        """
    )
    return conn


def _json_dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _array(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _enforce(
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
        raise PermissionError("verification authority failed: " + ",".join(dict.fromkeys(failures)))


def action_submit_verification(
    gate: GeometricObserverReceipt,
    *,
    work_ref: str,
    evidence: object,
    cost_units: int,
    priority: int,
    submitted_at: int,
) -> tuple[VerificationWorkItem, dict[str, object]]:
    gate.validate()
    item = make_verification_work(
        work_ref,
        subject_identity_ref=gate.subject_identity_ref,
        evidence={"target_gate_hash": gate.gate_hash, "evidence": evidence},
        cost_units=cost_units,
        priority=priority,
        submitted_at=submitted_at,
    )
    return item, {
        "operation": "submit_verification_work",
        "target_gate_hash": gate.gate_hash,
        "work_hash": item.work_hash,
        "subject_identity_ref": gate.subject_identity_ref,
        "cost_units": item.cost_units,
        "priority": item.priority,
        "submitted_at": submitted_at,
    }


def action_complete_verification(
    *,
    work_hash: str,
    subject_identity_ref: str,
    target_gate_hash: str,
    schedule_generation: int,
    pressure_hash: str,
    decision: Decision,
    evidence: object,
    actor_ref: str,
    completed_at: int,
) -> tuple[str, dict[str, object]]:
    evidence_digest = _digest({"domain": "ATMAN-LATTICE/runtime-verification-result/v1.7", "evidence": evidence})
    return evidence_digest, {
        "operation": "complete_verification_work",
        "work_hash": work_hash,
        "subject_identity_ref": subject_identity_ref,
        "target_gate_hash": target_gate_hash,
        "schedule_generation": schedule_generation,
        "pressure_hash": pressure_hash,
        "decision": decision,
        "evidence_digest": evidence_digest,
        "actor_ref": actor_ref,
        "completed_at": completed_at,
    }


def _submit_work(
    db_path: str,
    gate: GeometricObserverReceipt,
    item: VerificationWorkItem,
) -> str:
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        by_ref = conn.execute(
            "SELECT work_hash, target_gate_hash FROM verification_work WHERE work_ref = ?",
            (item.work_ref,),
        ).fetchone()
        if by_ref is not None:
            if by_ref[0] != item.work_hash or by_ref[1] != gate.gate_hash:
                raise ValueError("work_ref already bound to different verification work")
            conn.execute("COMMIT")
            return "EXISTING"
        conn.execute(
            "INSERT INTO verification_work(work_hash,work_ref,subject_identity_ref,target_gate_hash,work_json,status,completion_json) VALUES(?,?,?,?,?,?,NULL)",
            (
                item.work_hash,
                item.work_ref,
                item.subject_identity_ref,
                gate.gate_hash,
                _json_dump(work_to_dict(item)),
                "SUBMITTED",
            ),
        )
        conn.execute("COMMIT")
        return "SUBMITTED"
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _schedule(db_path: str, policy: VerificationCapacityPolicy, *, measured_at: int) -> tuple[int, VerificationPressureReceipt]:
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT work_json FROM verification_work WHERE status != 'COMPLETED' ORDER BY work_hash"
        ).fetchall()
        items = tuple(work_from_dict(json.loads(row[0])) for row in rows)
        pressure = schedule_verification(items, policy, measured_at=measured_at)
        current = conn.execute("SELECT generation FROM verification_schedule WHERE singleton = 1").fetchone()
        generation = 1 if current is None else int(current[0]) + 1
        admitted = set(pressure.admitted_work_hashes)
        deferred_capacity = set(pressure.deferred_capacity_work_hashes)
        deferred_oversized = set(pressure.deferred_oversized_work_hashes)
        for item in items:
            if item.work_hash in admitted:
                status = "ADMITTED"
            elif item.work_hash in deferred_capacity:
                status = "DEFERRED_CAPACITY"
            elif item.work_hash in deferred_oversized:
                status = "DEFERRED_OVERSIZED"
            else:
                raise RuntimeError("scheduler lost verification work")
            conn.execute("UPDATE verification_work SET status = ? WHERE work_hash = ?", (status, item.work_hash))
        conn.execute(
            "INSERT INTO verification_schedule(singleton,generation,pressure_json) VALUES(1,?,?) ON CONFLICT(singleton) DO UPDATE SET generation=excluded.generation, pressure_json=excluded.pressure_json",
            (generation, _json_dump(pressure_to_dict(pressure))),
        )
        conn.execute("COMMIT")
        return generation, pressure
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _read_schedule(conn: sqlite3.Connection) -> tuple[int, VerificationPressureReceipt | None]:
    row = conn.execute("SELECT generation, pressure_json FROM verification_schedule WHERE singleton = 1").fetchone()
    if row is None:
        return 0, None
    return int(row[0]), pressure_from_dict(json.loads(row[1]))


def _complete(
    db_path: str,
    *,
    work_hash: str,
    decision: Decision,
    evidence_digest: str,
    actor_ref: str,
    completed_at: int,
) -> VerificationCompletionReceipt:
    if decision not in _SEVERITY:
        raise ValueError("invalid completion decision")
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        generation, pressure = _read_schedule(conn)
        if pressure is None:
            raise ValueError("verification work has not been scheduled")
        row = conn.execute(
            "SELECT subject_identity_ref,target_gate_hash,status,completion_json FROM verification_work WHERE work_hash = ?",
            (work_hash,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown verification work")
        subject_identity_ref, target_gate_hash, status, completion_json = row
        if completion_json is not None or status == "COMPLETED":
            raise ValueError("verification work already completed")
        if status != "ADMITTED" or work_hash not in set(pressure.admitted_work_hashes):
            raise PermissionError("verification work is not admitted in current pressure window")
        fields = {
            "work_hash": work_hash,
            "subject_identity_ref": str(subject_identity_ref),
            "target_gate_hash": str(target_gate_hash),
            "schedule_generation": generation,
            "pressure_hash": pressure.pressure_hash,
            "decision": decision,
            "evidence_digest": evidence_digest,
            "completed_at": completed_at,
            "actor_ref": actor_ref,
        }
        provisional = VerificationCompletionReceipt(**fields, completion_hash="0" * 64)
        receipt = VerificationCompletionReceipt(**fields, completion_hash=_digest(provisional.material()))
        receipt.validate()
        conn.execute(
            "UPDATE verification_work SET status='COMPLETED', completion_json=? WHERE work_hash=?",
            (_json_dump(completion_to_dict(receipt)), work_hash),
        )
        conn.execute("COMMIT")
        return receipt
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _state(db_path: str) -> dict[str, object]:
    conn = _connect(db_path)
    try:
        generation, pressure = _read_schedule(conn)
        rows = conn.execute(
            "SELECT work_json,target_gate_hash,status,completion_json FROM verification_work ORDER BY work_ref"
        ).fetchall()
        work = []
        for work_json, gate_hash, status, completion_json in rows:
            work.append(
                {
                    "work": json.loads(work_json),
                    "target_gate_hash": gate_hash,
                    "status": status,
                    "completion": None if completion_json is None else json.loads(completion_json),
                }
            )
        return {
            "schedule_generation": generation,
            "pressure": None if pressure is None else pressure_to_dict(pressure),
            "work": work,
        }
    finally:
        conn.close()


def _evaluate(db_path: str, gate: GeometricObserverReceipt, *, decided_at: int) -> RuntimeVerificationDecisionReceipt:
    gate.validate()
    conn = _connect(db_path)
    try:
        generation, pressure = _read_schedule(conn)
        rows = conn.execute(
            "SELECT work_hash,status,completion_json FROM verification_work WHERE subject_identity_ref=? AND target_gate_hash=? ORDER BY work_hash",
            (gate.subject_identity_ref, gate.gate_hash),
        ).fetchall()
    finally:
        conn.close()

    required = tuple(str(row[0]) for row in rows)
    completions: list[VerificationCompletionReceipt] = []
    pending: list[str] = []
    deferred: list[str] = []
    reasons: list[str] = []
    for work_hash, status, completion_json in rows:
        if status == "COMPLETED":
            if completion_json is None:
                raise ValueError("completed verification work is missing completion receipt")
            completion = completion_from_dict(json.loads(completion_json))
            if completion.target_gate_hash != gate.gate_hash or completion.subject_identity_ref != gate.subject_identity_ref:
                raise ValueError("completion binding mismatch")
            completions.append(completion)
        elif status in {"DEFERRED_CAPACITY", "DEFERRED_OVERSIZED"}:
            deferred.append(str(work_hash))
        else:
            pending.append(str(work_hash))

    if gate.decision == "FAIL":
        decision: Decision = "FAIL"
        reasons.append("base_geometry_failed")
    elif any(item.decision == "FAIL" for item in completions):
        decision = "FAIL"
        reasons.append("verification_result_failed")
    elif pending or deferred:
        decision = "HOLD"
        if pending:
            reasons.append("verification_pending")
        if deferred:
            reasons.append("verification_deferred_capacity")
    elif completions:
        if any(item.decision == "HOLD" for item in completions):
            decision = "HOLD"
            reasons.append("verification_result_hold")
        else:
            # A complete set of PASS verification results may discharge a geometric HOLD.
            decision = "PASS"
            if gate.decision == "HOLD":
                reasons.append("geometric_hold_discharged_by_completed_verification")
    else:
        decision = gate.decision
        if gate.decision == "HOLD":
            reasons.append("geometric_hold_without_verification_work")

    fields = {
        "subject_identity_ref": gate.subject_identity_ref,
        "target_gate_hash": gate.gate_hash,
        "base_decision": gate.decision,
        "schedule_generation": generation,
        "pressure_hash": None if pressure is None else pressure.pressure_hash,
        "required_work_hashes": required,
        "completed_completion_hashes": tuple(item.completion_hash for item in completions),
        "pending_work_hashes": tuple(pending),
        "deferred_work_hashes": tuple(deferred),
        "decision": decision,
        "reasons": tuple(dict.fromkeys(reasons)),
        "decided_at": decided_at,
    }
    provisional = RuntimeVerificationDecisionReceipt(**fields, runtime_decision_hash="0" * 64)
    receipt = RuntimeVerificationDecisionReceipt(**fields, runtime_decision_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt


def execute_verification_request(
    request: Mapping[str, object],
    *,
    enforcement: EnforcementContext,
    db_path: str,
    policy: VerificationCapacityPolicy,
) -> dict[str, object]:
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in VERIFY_OPERATIONS:
        raise ValueError("unsupported verification operation")
    payload = _mapping(request.get("payload", {}), "payload")

    if operation == "submit_verification_work":
        gate = geometric_observer_from_dict(_mapping(payload.get("geometry_gate"), "geometry_gate"))
        item, action = action_submit_verification(
            gate,
            work_ref=str(payload["work_ref"]),
            evidence=payload.get("evidence"),
            cost_units=int(payload["cost_units"]),
            priority=int(payload.get("priority", 0)),
            submitted_at=enforcement.now,
        )
        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        _enforce(
            grant,
            proof,
            action=action,
            required_role=ROLE_VERIFICATION_SUBMITTER,
            required_scope=verification_scope(gate.subject_identity_ref),
            enforcement=enforcement,
        )
        disposition = _submit_work(db_path, gate, item)
        result = {"work": work_to_dict(item), "disposition": disposition}

    elif operation == "schedule_verification":
        generation, pressure = _schedule(db_path, policy, measured_at=enforcement.now)
        result = {
            "schedule_generation": generation,
            "pressure": pressure_to_dict(pressure),
        }

    elif operation == "complete_verification_work":
        state = _state(db_path)
        generation = int(state["schedule_generation"])
        pressure_data = state["pressure"]
        if pressure_data is None:
            raise ValueError("verification work has not been scheduled")
        pressure = pressure_from_dict(_mapping(pressure_data, "pressure"))
        work_hash = str(payload["work_hash"])
        matching = [entry for entry in _array(state["work"], "work") if _mapping(entry, "work entry")["work"]["work_hash"] == work_hash]
        if len(matching) != 1:
            raise ValueError("unknown verification work")
        entry = _mapping(matching[0], "work entry")
        work_data = _mapping(entry["work"], "work")
        subject_identity_ref = str(work_data["subject_identity_ref"])
        target_gate_hash = str(entry["target_gate_hash"])
        actor_ref = str(payload["actor_ref"])
        decision = str(payload["decision"])
        evidence_digest, action = action_complete_verification(
            work_hash=work_hash,
            subject_identity_ref=subject_identity_ref,
            target_gate_hash=target_gate_hash,
            schedule_generation=generation,
            pressure_hash=pressure.pressure_hash,
            decision=decision,
            evidence=payload.get("evidence"),
            actor_ref=actor_ref,
            completed_at=enforcement.now,
        )
        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        _enforce(
            grant,
            proof,
            action=action,
            required_role=ROLE_VERIFICATION_EXECUTOR,
            required_scope=verification_scope(subject_identity_ref),
            enforcement=enforcement,
        )
        completion = _complete(
            db_path,
            work_hash=work_hash,
            decision=decision,
            evidence_digest=evidence_digest,
            actor_ref=actor_ref,
            completed_at=enforcement.now,
        )
        result = {"completion": completion_to_dict(completion)}

    elif operation == "get_verification_state":
        result = _state(db_path)

    else:  # evaluate_geometric_verification
        gate = geometric_observer_from_dict(_mapping(payload.get("geometry_gate"), "geometry_gate"))
        result = {"decision": runtime_decision_to_dict(_evaluate(db_path, gate, decided_at=enforcement.now))}

    return {
        "protocol": VERIFY_PROTOCOL,
        "request_id": request_id,
        "ok": True,
        **result,
    }
