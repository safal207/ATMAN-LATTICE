from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

from model.lattice import IdentityReceipt, issue_genesis_receipt

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(material: object) -> str:
    return sha256(_canonical_json(material)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True)
class RestoreReceipt:
    identity_ref: str
    source_branch_ref: str
    source_generation: int
    source_lineage_root_hash: str
    source_receipt_hash: str
    source_state_ref: str
    source_sequence: int
    target_branch_ref: str
    target_generation: int
    target_lineage_root_hash: str
    target_genesis_receipt_hash: str
    replayed_at: int
    restore_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/restore-receipt/v0.5",
            "identity_ref": self.identity_ref,
            "source_branch_ref": self.source_branch_ref,
            "source_generation": self.source_generation,
            "source_lineage_root_hash": self.source_lineage_root_hash,
            "source_receipt_hash": self.source_receipt_hash,
            "source_state_ref": self.source_state_ref,
            "source_sequence": self.source_sequence,
            "target_branch_ref": self.target_branch_ref,
            "target_generation": self.target_generation,
            "target_lineage_root_hash": self.target_lineage_root_hash,
            "target_genesis_receipt_hash": self.target_genesis_receipt_hash,
            "replayed_at": self.replayed_at,
        }

    def validate(self) -> None:
        if not self.identity_ref:
            raise ValueError("identity_ref is required")
        if not self.source_branch_ref or not self.target_branch_ref:
            raise ValueError("branch refs are required")
        if self.source_branch_ref == self.target_branch_ref:
            raise ValueError("restore must create a distinct branch")
        if self.source_generation < 0:
            raise ValueError("source_generation must be >= 0")
        if self.target_generation <= self.source_generation:
            raise ValueError("target_generation must advance")
        if self.source_sequence < 0:
            raise ValueError("source_sequence must be >= 0")
        if self.replayed_at < 0:
            raise ValueError("replayed_at must be >= 0")
        for name, value in (
            ("source_lineage_root_hash", self.source_lineage_root_hash),
            ("source_receipt_hash", self.source_receipt_hash),
            ("target_lineage_root_hash", self.target_lineage_root_hash),
            ("target_genesis_receipt_hash", self.target_genesis_receipt_hash),
            ("restore_hash", self.restore_hash),
        ):
            _require_digest(name, value)
        if self.restore_hash != _digest(self.material()):
            raise ValueError("restore_hash does not match receipt content")


def restore_checkpoint(
    source: IdentityReceipt,
    *,
    target_branch_ref: str,
    target_generation: int,
    replayed_at: int,
) -> tuple[IdentityReceipt, RestoreReceipt]:
    """Restore a historical checkpoint as a new branch/generation, never as silent continuation."""
    source.validate()
    if target_branch_ref == source.branch_ref:
        raise ValueError("restore must create a distinct branch")
    if target_generation <= source.generation:
        raise ValueError("target_generation must advance")
    if replayed_at < 0:
        raise ValueError("replayed_at must be >= 0")

    target = issue_genesis_receipt(
        identity_ref=source.identity_ref,
        state_ref=f"restore:{source.state_ref}",
        branch_ref=target_branch_ref,
        generation=target_generation,
        payload=source.receipt_hash,
        provenance_refs=(
            f"restore-source:{source.receipt_hash}",
            f"restore-root:{source.lineage_root_hash}",
        ),
    )

    material = {
        "domain": "ATMAN-LATTICE/restore-receipt/v0.5",
        "identity_ref": source.identity_ref,
        "source_branch_ref": source.branch_ref,
        "source_generation": source.generation,
        "source_lineage_root_hash": source.lineage_root_hash,
        "source_receipt_hash": source.receipt_hash,
        "source_state_ref": source.state_ref,
        "source_sequence": source.sequence,
        "target_branch_ref": target.branch_ref,
        "target_generation": target.generation,
        "target_lineage_root_hash": target.lineage_root_hash,
        "target_genesis_receipt_hash": target.receipt_hash,
        "replayed_at": replayed_at,
    }
    restore = RestoreReceipt(**material | {"restore_hash": _digest(material)})
    restore.validate()
    return target, restore


def verify_restore(
    source: IdentityReceipt,
    target: IdentityReceipt,
    restore: RestoreReceipt,
) -> tuple[bool, tuple[str, ...]]:
    limitations: list[str] = []
    try:
        source.validate()
        target.validate()
        restore.validate()
    except ValueError:
        return False, ("invalid_restore_artifact",)

    checks = (
        (restore.identity_ref == source.identity_ref == target.identity_ref, "identity_mismatch"),
        (restore.source_branch_ref == source.branch_ref, "source_branch_mismatch"),
        (restore.source_generation == source.generation, "source_generation_mismatch"),
        (restore.source_lineage_root_hash == source.lineage_root_hash, "source_root_mismatch"),
        (restore.source_receipt_hash == source.receipt_hash, "source_receipt_mismatch"),
        (restore.source_state_ref == source.state_ref, "source_state_mismatch"),
        (restore.source_sequence == source.sequence, "source_sequence_mismatch"),
        (restore.target_branch_ref == target.branch_ref, "target_branch_mismatch"),
        (restore.target_generation == target.generation, "target_generation_mismatch"),
        (restore.target_lineage_root_hash == target.lineage_root_hash, "target_root_mismatch"),
        (restore.target_genesis_receipt_hash == target.receipt_hash, "target_genesis_mismatch"),
        (target.branch_ref != source.branch_ref, "branch_not_forked"),
        (target.generation > source.generation, "generation_not_advanced"),
        (target.lineage_root_hash != source.lineage_root_hash, "root_not_forked"),
        (f"restore-source:{source.receipt_hash}" in target.provenance_refs, "missing_source_provenance"),
    )
    for ok, limitation in checks:
        if not ok:
            limitations.append(limitation)
    return not limitations, tuple(dict.fromkeys(limitations))
