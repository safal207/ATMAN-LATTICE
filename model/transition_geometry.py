from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Literal

from model.lattice import IdentityReceipt

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

TorsionStatus = Literal[
    "CLOSED",
    "SEMANTICALLY_CLOSED_HISTORY_DIVERGENT",
    "TORSION_DETECTED",
]
CurvatureStatus = Literal[
    "FLAT_LOOP",
    "SEMANTICALLY_CLOSED_WITH_HOLONOMY",
    "CURVATURE_DETECTED",
]

_SEMANTIC_FIELDS = (
    "identity_ref",
    "payload_digest",
    "context_digest",
    "authority_digest",
    "effect_digest",
)
_HISTORY_FIELDS = (
    "lineage_root_hash",
    "branch_ref",
    "generation",
    "receipt_hash",
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _component_digest(kind: str, value: object) -> str:
    return _digest(
        {
            "domain": f"ATMAN-LATTICE/transition-geometry/{kind}/v1.4",
            "value": value,
        }
    )


def _require_digest(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def _delta_dimensions(left: "TransitionEndpoint", right: "TransitionEndpoint", fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(field for field in fields if getattr(left, field) != getattr(right, field))


@dataclass(frozen=True)
class TransitionOperator:
    operator_ref: str
    action_digest: str
    operator_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/transition-operator/v1.4",
            "operator_ref": self.operator_ref,
            "action_digest": self.action_digest,
        }

    def validate(self) -> None:
        if not self.operator_ref:
            raise ValueError("operator_ref is required")
        _require_digest("action_digest", self.action_digest)
        _require_digest("operator_hash", self.operator_hash)
        if self.operator_hash != _digest(self.material()):
            raise ValueError("operator_hash does not match operator material")


def make_transition_operator(operator_ref: str, action: object) -> TransitionOperator:
    if not operator_ref:
        raise ValueError("operator_ref is required")
    action_digest = _component_digest("action", action)
    provisional = TransitionOperator(
        operator_ref=operator_ref,
        action_digest=action_digest,
        operator_hash="0" * 64,
    )
    operator = TransitionOperator(
        operator_ref=operator_ref,
        action_digest=action_digest,
        operator_hash=_digest(provisional.material()),
    )
    operator.validate()
    return operator


@dataclass(frozen=True)
class TransitionEndpoint:
    identity_ref: str
    receipt_hash: str
    lineage_root_hash: str
    branch_ref: str
    generation: int
    payload_digest: str
    context_digest: str
    authority_digest: str
    effect_digest: str
    endpoint_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/transition-endpoint/v1.4",
            "identity_ref": self.identity_ref,
            "receipt_hash": self.receipt_hash,
            "lineage_root_hash": self.lineage_root_hash,
            "branch_ref": self.branch_ref,
            "generation": self.generation,
            "payload_digest": self.payload_digest,
            "context_digest": self.context_digest,
            "authority_digest": self.authority_digest,
            "effect_digest": self.effect_digest,
        }

    def validate(self) -> None:
        if not self.identity_ref or not self.branch_ref:
            raise ValueError("identity_ref and branch_ref are required")
        if self.generation < 0:
            raise ValueError("generation must be >= 0")
        for name, value in (
            ("receipt_hash", self.receipt_hash),
            ("lineage_root_hash", self.lineage_root_hash),
            ("payload_digest", self.payload_digest),
            ("context_digest", self.context_digest),
            ("authority_digest", self.authority_digest),
            ("effect_digest", self.effect_digest),
            ("endpoint_hash", self.endpoint_hash),
        ):
            _require_digest(name, value)
        if self.endpoint_hash != _digest(self.material()):
            raise ValueError("endpoint_hash does not match endpoint material")


def make_transition_endpoint(
    receipt: IdentityReceipt,
    *,
    context: object,
    authority: object,
    effects: object,
) -> TransitionEndpoint:
    receipt.validate()
    fields = {
        "identity_ref": receipt.identity_ref,
        "receipt_hash": receipt.receipt_hash,
        "lineage_root_hash": receipt.lineage_root_hash,
        "branch_ref": receipt.branch_ref,
        "generation": receipt.generation,
        "payload_digest": receipt.payload_digest,
        "context_digest": _component_digest("context", context),
        "authority_digest": _component_digest("authority", authority),
        "effect_digest": _component_digest("effects", effects),
    }
    provisional = TransitionEndpoint(**fields, endpoint_hash="0" * 64)
    endpoint = TransitionEndpoint(**fields, endpoint_hash=_digest(provisional.material()))
    endpoint.validate()
    return endpoint


@dataclass(frozen=True)
class TransitionTorsionReceipt:
    origin_endpoint_hash: str
    operator_a_hash: str
    operator_b_hash: str
    path_ab_endpoint_hash: str
    path_ba_endpoint_hash: str
    semantic_delta_dimensions: tuple[str, ...]
    history_delta_dimensions: tuple[str, ...]
    status: TorsionStatus
    measured_at: int
    torsion_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/transition-torsion/v1.4",
            "origin_endpoint_hash": self.origin_endpoint_hash,
            "operator_a_hash": self.operator_a_hash,
            "operator_b_hash": self.operator_b_hash,
            "path_ab_endpoint_hash": self.path_ab_endpoint_hash,
            "path_ba_endpoint_hash": self.path_ba_endpoint_hash,
            "semantic_delta_dimensions": list(self.semantic_delta_dimensions),
            "history_delta_dimensions": list(self.history_delta_dimensions),
            "status": self.status,
            "measured_at": self.measured_at,
        }

    def validate(self) -> None:
        for name, value in (
            ("origin_endpoint_hash", self.origin_endpoint_hash),
            ("operator_a_hash", self.operator_a_hash),
            ("operator_b_hash", self.operator_b_hash),
            ("path_ab_endpoint_hash", self.path_ab_endpoint_hash),
            ("path_ba_endpoint_hash", self.path_ba_endpoint_hash),
            ("torsion_hash", self.torsion_hash),
        ):
            _require_digest(name, value)
        if self.measured_at < 0:
            raise ValueError("measured_at must be >= 0")
        if any(field not in _SEMANTIC_FIELDS for field in self.semantic_delta_dimensions):
            raise ValueError("unknown semantic delta dimension")
        if any(field not in _HISTORY_FIELDS for field in self.history_delta_dimensions):
            raise ValueError("unknown history delta dimension")
        expected_status = _torsion_status(
            self.semantic_delta_dimensions,
            self.history_delta_dimensions,
        )
        if self.status != expected_status:
            raise ValueError("torsion status does not match delta dimensions")
        if self.torsion_hash != _digest(self.material()):
            raise ValueError("torsion_hash does not match torsion material")


def _torsion_status(semantic: tuple[str, ...], history: tuple[str, ...]) -> TorsionStatus:
    if semantic:
        return "TORSION_DETECTED"
    if history:
        return "SEMANTICALLY_CLOSED_HISTORY_DIVERGENT"
    return "CLOSED"


def measure_transition_torsion(
    origin: TransitionEndpoint,
    operator_a: TransitionOperator,
    operator_b: TransitionOperator,
    path_ab: TransitionEndpoint,
    path_ba: TransitionEndpoint,
    *,
    measured_at: int,
) -> TransitionTorsionReceipt:
    origin.validate()
    operator_a.validate()
    operator_b.validate()
    path_ab.validate()
    path_ba.validate()
    semantic = _delta_dimensions(path_ab, path_ba, _SEMANTIC_FIELDS)
    history = _delta_dimensions(path_ab, path_ba, _HISTORY_FIELDS)
    fields = {
        "origin_endpoint_hash": origin.endpoint_hash,
        "operator_a_hash": operator_a.operator_hash,
        "operator_b_hash": operator_b.operator_hash,
        "path_ab_endpoint_hash": path_ab.endpoint_hash,
        "path_ba_endpoint_hash": path_ba.endpoint_hash,
        "semantic_delta_dimensions": semantic,
        "history_delta_dimensions": history,
        "status": _torsion_status(semantic, history),
        "measured_at": measured_at,
    }
    provisional = TransitionTorsionReceipt(**fields, torsion_hash="0" * 64)
    receipt = TransitionTorsionReceipt(**fields, torsion_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt


def verify_transition_torsion(
    receipt: TransitionTorsionReceipt,
    origin: TransitionEndpoint,
    operator_a: TransitionOperator,
    operator_b: TransitionOperator,
    path_ab: TransitionEndpoint,
    path_ba: TransitionEndpoint,
) -> tuple[bool, tuple[str, ...]]:
    try:
        receipt.validate()
        expected = measure_transition_torsion(
            origin,
            operator_a,
            operator_b,
            path_ab,
            path_ba,
            measured_at=receipt.measured_at,
        )
    except ValueError:
        return False, ("invalid_torsion_evidence",)

    limitations: list[str] = []
    for field, limitation in (
        ("origin_endpoint_hash", "origin_binding_mismatch"),
        ("operator_a_hash", "operator_a_binding_mismatch"),
        ("operator_b_hash", "operator_b_binding_mismatch"),
        ("path_ab_endpoint_hash", "path_ab_binding_mismatch"),
        ("path_ba_endpoint_hash", "path_ba_binding_mismatch"),
        ("semantic_delta_dimensions", "semantic_delta_mismatch"),
        ("history_delta_dimensions", "history_delta_mismatch"),
        ("status", "torsion_status_mismatch"),
        ("torsion_hash", "torsion_hash_mismatch"),
    ):
        if getattr(receipt, field) != getattr(expected, field):
            limitations.append(limitation)
    return not limitations, tuple(limitations)


@dataclass(frozen=True)
class TransitionCurvatureReceipt:
    origin_endpoint_hash: str
    returned_endpoint_hash: str
    loop_operator_hashes: tuple[str, ...]
    semantic_drift_dimensions: tuple[str, ...]
    history_holonomy_dimensions: tuple[str, ...]
    status: CurvatureStatus
    measured_at: int
    curvature_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/transition-curvature/v1.4",
            "origin_endpoint_hash": self.origin_endpoint_hash,
            "returned_endpoint_hash": self.returned_endpoint_hash,
            "loop_operator_hashes": list(self.loop_operator_hashes),
            "semantic_drift_dimensions": list(self.semantic_drift_dimensions),
            "history_holonomy_dimensions": list(self.history_holonomy_dimensions),
            "status": self.status,
            "measured_at": self.measured_at,
        }

    def validate(self) -> None:
        _require_digest("origin_endpoint_hash", self.origin_endpoint_hash)
        _require_digest("returned_endpoint_hash", self.returned_endpoint_hash)
        _require_digest("curvature_hash", self.curvature_hash)
        if len(self.loop_operator_hashes) < 2:
            raise ValueError("closed-loop measurement requires at least two operators")
        for value in self.loop_operator_hashes:
            _require_digest("loop_operator_hash", value)
        if any(field not in _SEMANTIC_FIELDS for field in self.semantic_drift_dimensions):
            raise ValueError("unknown semantic drift dimension")
        if any(field not in _HISTORY_FIELDS for field in self.history_holonomy_dimensions):
            raise ValueError("unknown history holonomy dimension")
        if self.measured_at < 0:
            raise ValueError("measured_at must be >= 0")
        expected_status = _curvature_status(
            self.semantic_drift_dimensions,
            self.history_holonomy_dimensions,
        )
        if self.status != expected_status:
            raise ValueError("curvature status does not match drift dimensions")
        if self.curvature_hash != _digest(self.material()):
            raise ValueError("curvature_hash does not match curvature material")


def _curvature_status(semantic: tuple[str, ...], history: tuple[str, ...]) -> CurvatureStatus:
    if semantic:
        return "CURVATURE_DETECTED"
    if history:
        return "SEMANTICALLY_CLOSED_WITH_HOLONOMY"
    return "FLAT_LOOP"


def measure_loop_curvature(
    origin: TransitionEndpoint,
    returned: TransitionEndpoint,
    loop_operators: tuple[TransitionOperator, ...],
    *,
    measured_at: int,
) -> TransitionCurvatureReceipt:
    origin.validate()
    returned.validate()
    if len(loop_operators) < 2:
        raise ValueError("closed-loop measurement requires at least two operators")
    for operator in loop_operators:
        operator.validate()
    semantic = _delta_dimensions(origin, returned, _SEMANTIC_FIELDS)
    history = _delta_dimensions(origin, returned, _HISTORY_FIELDS)
    fields = {
        "origin_endpoint_hash": origin.endpoint_hash,
        "returned_endpoint_hash": returned.endpoint_hash,
        "loop_operator_hashes": tuple(operator.operator_hash for operator in loop_operators),
        "semantic_drift_dimensions": semantic,
        "history_holonomy_dimensions": history,
        "status": _curvature_status(semantic, history),
        "measured_at": measured_at,
    }
    provisional = TransitionCurvatureReceipt(**fields, curvature_hash="0" * 64)
    receipt = TransitionCurvatureReceipt(**fields, curvature_hash=_digest(provisional.material()))
    receipt.validate()
    return receipt


def verify_loop_curvature(
    receipt: TransitionCurvatureReceipt,
    origin: TransitionEndpoint,
    returned: TransitionEndpoint,
    loop_operators: tuple[TransitionOperator, ...],
) -> tuple[bool, tuple[str, ...]]:
    try:
        receipt.validate()
        expected = measure_loop_curvature(
            origin,
            returned,
            loop_operators,
            measured_at=receipt.measured_at,
        )
    except ValueError:
        return False, ("invalid_curvature_evidence",)

    limitations: list[str] = []
    for field, limitation in (
        ("origin_endpoint_hash", "origin_binding_mismatch"),
        ("returned_endpoint_hash", "returned_binding_mismatch"),
        ("loop_operator_hashes", "loop_operator_binding_mismatch"),
        ("semantic_drift_dimensions", "semantic_drift_mismatch"),
        ("history_holonomy_dimensions", "history_holonomy_mismatch"),
        ("status", "curvature_status_mismatch"),
        ("curvature_hash", "curvature_hash_mismatch"),
    ):
        if getattr(receipt, field) != getattr(expected, field):
            limitations.append(limitation)
    return not limitations, tuple(limitations)
