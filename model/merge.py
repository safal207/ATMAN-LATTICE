from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Iterable, Literal

from model.lattice import (
    IdentityReceipt,
    digest_payload,
    issue_genesis_receipt,
    verify_lineage_chain,
)
from model.replay import RestoreReceipt, verify_restore

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ResolutionStrategy = Literal["LEFT", "RIGHT", "SYNTHESIZED"]


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(material: object) -> str:
    return sha256(_canonical_json(material)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True)
class MergeConflict:
    conflict_ref: str
    left_digest: str
    right_digest: str

    def validate(self) -> None:
        if not self.conflict_ref:
            raise ValueError("conflict_ref is required")
        _require_digest("left_digest", self.left_digest)
        _require_digest("right_digest", self.right_digest)
        if self.left_digest == self.right_digest:
            raise ValueError("equal values are not a merge conflict")


@dataclass(frozen=True)
class ConflictResolution:
    conflict_ref: str
    left_digest: str
    right_digest: str
    strategy: ResolutionStrategy
    result_digest: str
    reason_ref: str

    def validate(self) -> None:
        if not self.conflict_ref:
            raise ValueError("conflict_ref is required")
        _require_digest("left_digest", self.left_digest)
        _require_digest("right_digest", self.right_digest)
        _require_digest("result_digest", self.result_digest)
        if self.strategy not in {"LEFT", "RIGHT", "SYNTHESIZED"}:
            raise ValueError("invalid merge resolution strategy")
        if not self.reason_ref:
            raise ValueError("reason_ref is required")
        if self.strategy == "LEFT" and self.result_digest != self.left_digest:
            raise ValueError("LEFT resolution must select left_digest")
        if self.strategy == "RIGHT" and self.result_digest != self.right_digest:
            raise ValueError("RIGHT resolution must select right_digest")


def digest_resolution_set(
    conflicts: Iterable[MergeConflict],
    resolutions: Iterable[ConflictResolution],
) -> str:
    conflict_items = tuple(conflicts)
    resolution_items = tuple(resolutions)

    conflict_map: dict[str, MergeConflict] = {}
    for conflict in conflict_items:
        conflict.validate()
        if conflict.conflict_ref in conflict_map:
            raise ValueError("duplicate conflict_ref")
        conflict_map[conflict.conflict_ref] = conflict

    resolution_map: dict[str, ConflictResolution] = {}
    for resolution in resolution_items:
        resolution.validate()
        if resolution.conflict_ref in resolution_map:
            raise ValueError("duplicate resolution conflict_ref")
        resolution_map[resolution.conflict_ref] = resolution

    if set(conflict_map) != set(resolution_map):
        missing = sorted(set(conflict_map) - set(resolution_map))
        extra = sorted(set(resolution_map) - set(conflict_map))
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise ValueError("resolution set does not exactly cover conflicts: " + ";".join(details))

    canonical_resolutions: list[dict[str, object]] = []
    for conflict_ref in sorted(conflict_map):
        conflict = conflict_map[conflict_ref]
        resolution = resolution_map[conflict_ref]
        if resolution.left_digest != conflict.left_digest:
            raise ValueError(f"left digest mismatch for {conflict_ref}")
        if resolution.right_digest != conflict.right_digest:
            raise ValueError(f"right digest mismatch for {conflict_ref}")
        canonical_resolutions.append(
            {
                "conflict_ref": conflict_ref,
                "left_digest": conflict.left_digest,
                "right_digest": conflict.right_digest,
                "strategy": resolution.strategy,
                "result_digest": resolution.result_digest,
                "reason_ref": resolution.reason_ref,
            }
        )

    return _digest(
        {
            "domain": "ATMAN-LATTICE/merge-resolutions/v0.6",
            "resolutions": canonical_resolutions,
        }
    )


@dataclass(frozen=True)
class MergeReceipt:
    identity_ref: str
    ancestor_receipt_hash: str
    ancestor_lineage_root_hash: str
    left_branch_ref: str
    left_generation: int
    left_lineage_root_hash: str
    left_head_receipt_hash: str
    right_branch_ref: str
    right_generation: int
    right_lineage_root_hash: str
    right_head_receipt_hash: str
    target_branch_ref: str
    target_generation: int
    target_lineage_root_hash: str
    target_genesis_receipt_hash: str
    resolution_digest: str
    merged_payload_digest: str
    conflict_count: int
    merged_at: int
    merge_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/merge-receipt/v0.6",
            "identity_ref": self.identity_ref,
            "ancestor_receipt_hash": self.ancestor_receipt_hash,
            "ancestor_lineage_root_hash": self.ancestor_lineage_root_hash,
            "left_branch_ref": self.left_branch_ref,
            "left_generation": self.left_generation,
            "left_lineage_root_hash": self.left_lineage_root_hash,
            "left_head_receipt_hash": self.left_head_receipt_hash,
            "right_branch_ref": self.right_branch_ref,
            "right_generation": self.right_generation,
            "right_lineage_root_hash": self.right_lineage_root_hash,
            "right_head_receipt_hash": self.right_head_receipt_hash,
            "target_branch_ref": self.target_branch_ref,
            "target_generation": self.target_generation,
            "target_lineage_root_hash": self.target_lineage_root_hash,
            "target_genesis_receipt_hash": self.target_genesis_receipt_hash,
            "resolution_digest": self.resolution_digest,
            "merged_payload_digest": self.merged_payload_digest,
            "conflict_count": self.conflict_count,
            "merged_at": self.merged_at,
        }

    def validate(self) -> None:
        if not self.identity_ref:
            raise ValueError("identity_ref is required")
        if not self.left_branch_ref or not self.right_branch_ref or not self.target_branch_ref:
            raise ValueError("branch refs are required")
        if self.left_branch_ref == self.right_branch_ref:
            raise ValueError("merge parents must be distinct branches")
        if self.target_branch_ref in {self.left_branch_ref, self.right_branch_ref}:
            raise ValueError("merge target must be a new branch")
        if self.left_generation < 0 or self.right_generation < 0:
            raise ValueError("parent generations must be >= 0")
        if self.target_generation <= max(self.left_generation, self.right_generation):
            raise ValueError("target_generation must advance beyond both parents")
        if self.conflict_count < 0:
            raise ValueError("conflict_count must be >= 0")
        if self.merged_at < 0:
            raise ValueError("merged_at must be >= 0")
        for name, value in (
            ("ancestor_receipt_hash", self.ancestor_receipt_hash),
            ("ancestor_lineage_root_hash", self.ancestor_lineage_root_hash),
            ("left_lineage_root_hash", self.left_lineage_root_hash),
            ("left_head_receipt_hash", self.left_head_receipt_hash),
            ("right_lineage_root_hash", self.right_lineage_root_hash),
            ("right_head_receipt_hash", self.right_head_receipt_hash),
            ("target_lineage_root_hash", self.target_lineage_root_hash),
            ("target_genesis_receipt_hash", self.target_genesis_receipt_hash),
            ("resolution_digest", self.resolution_digest),
            ("merged_payload_digest", self.merged_payload_digest),
            ("merge_hash", self.merge_hash),
        ):
            _require_digest(name, value)
        if self.left_lineage_root_hash == self.right_lineage_root_hash:
            raise ValueError("merge parents must have distinct lineage roots")
        if self.target_lineage_root_hash in {
            self.left_lineage_root_hash,
            self.right_lineage_root_hash,
        }:
            raise ValueError("merge target must create a distinct lineage root")
        if self.merge_hash != _digest(self.material()):
            raise ValueError("merge_hash does not match receipt content")


def _validated_branch(
    chain: Iterable[IdentityReceipt],
) -> tuple[IdentityReceipt, ...]:
    items = tuple(chain)
    valid, limitations = verify_lineage_chain(items)
    if not valid:
        raise ValueError("invalid branch chain: " + ",".join(limitations))
    return items


def _verify_branch_origin(
    ancestor: IdentityReceipt,
    chain: tuple[IdentityReceipt, ...],
    restore: RestoreReceipt,
) -> None:
    valid, limitations = verify_restore(ancestor, chain[0], restore)
    if not valid:
        raise ValueError("invalid restore proof: " + ",".join(limitations))


def _merge_seed(
    *,
    ancestor: IdentityReceipt,
    left_head: IdentityReceipt,
    right_head: IdentityReceipt,
    resolution_digest: str,
    merged_payload_digest: str,
) -> dict[str, object]:
    return {
        "domain": "ATMAN-LATTICE/merge-genesis/v0.6",
        "identity_ref": ancestor.identity_ref,
        "ancestor_receipt_hash": ancestor.receipt_hash,
        "ancestor_lineage_root_hash": ancestor.lineage_root_hash,
        "left_head_receipt_hash": left_head.receipt_hash,
        "left_lineage_root_hash": left_head.lineage_root_hash,
        "right_head_receipt_hash": right_head.receipt_hash,
        "right_lineage_root_hash": right_head.lineage_root_hash,
        "resolution_digest": resolution_digest,
        "merged_payload_digest": merged_payload_digest,
    }


def merge_branches(
    ancestor: IdentityReceipt,
    left_chain: Iterable[IdentityReceipt],
    left_restore: RestoreReceipt,
    right_chain: Iterable[IdentityReceipt],
    right_restore: RestoreReceipt,
    *,
    target_branch_ref: str,
    target_generation: int,
    merged_payload: str | bytes,
    conflicts: Iterable[MergeConflict] = (),
    resolutions: Iterable[ConflictResolution] = (),
    merged_at: int,
) -> tuple[IdentityReceipt, MergeReceipt]:
    """Merge two explicitly forked futures into a third lineage with complete provenance."""
    ancestor.validate()
    left = _validated_branch(left_chain)
    right = _validated_branch(right_chain)
    _verify_branch_origin(ancestor, left, left_restore)
    _verify_branch_origin(ancestor, right, right_restore)

    left_head = left[-1]
    right_head = right[-1]
    if left_head.identity_ref != ancestor.identity_ref or right_head.identity_ref != ancestor.identity_ref:
        raise ValueError("merge parents must preserve ancestor identity")
    if left_head.branch_ref == right_head.branch_ref:
        raise ValueError("merge parents must be distinct branches")
    if left_head.lineage_root_hash == right_head.lineage_root_hash:
        raise ValueError("merge parents must have distinct lineage roots")
    if target_branch_ref in {
        ancestor.branch_ref,
        left_head.branch_ref,
        right_head.branch_ref,
    }:
        raise ValueError("merge target must be distinct from ancestor and both parents")
    if target_generation <= max(left_head.generation, right_head.generation):
        raise ValueError("target_generation must advance beyond both parents")
    if merged_at < 0:
        raise ValueError("merged_at must be >= 0")

    conflict_items = tuple(conflicts)
    resolution_items = tuple(resolutions)
    resolution_digest = digest_resolution_set(conflict_items, resolution_items)
    merged_payload_digest = digest_payload(merged_payload)
    seed = _merge_seed(
        ancestor=ancestor,
        left_head=left_head,
        right_head=right_head,
        resolution_digest=resolution_digest,
        merged_payload_digest=merged_payload_digest,
    )

    target = issue_genesis_receipt(
        identity_ref=ancestor.identity_ref,
        state_ref=f"merge:{left_head.branch_ref}+{right_head.branch_ref}",
        branch_ref=target_branch_ref,
        generation=target_generation,
        payload=_canonical_json(seed),
        provenance_refs=(
            f"merge-ancestor:{ancestor.receipt_hash}",
            f"merge-left:{left_head.receipt_hash}",
            f"merge-right:{right_head.receipt_hash}",
            f"merge-resolutions:{resolution_digest}",
        ),
    )

    fields = {
        "identity_ref": ancestor.identity_ref,
        "ancestor_receipt_hash": ancestor.receipt_hash,
        "ancestor_lineage_root_hash": ancestor.lineage_root_hash,
        "left_branch_ref": left_head.branch_ref,
        "left_generation": left_head.generation,
        "left_lineage_root_hash": left_head.lineage_root_hash,
        "left_head_receipt_hash": left_head.receipt_hash,
        "right_branch_ref": right_head.branch_ref,
        "right_generation": right_head.generation,
        "right_lineage_root_hash": right_head.lineage_root_hash,
        "right_head_receipt_hash": right_head.receipt_hash,
        "target_branch_ref": target.branch_ref,
        "target_generation": target.generation,
        "target_lineage_root_hash": target.lineage_root_hash,
        "target_genesis_receipt_hash": target.receipt_hash,
        "resolution_digest": resolution_digest,
        "merged_payload_digest": merged_payload_digest,
        "conflict_count": len(conflict_items),
        "merged_at": merged_at,
    }
    hash_material = {"domain": "ATMAN-LATTICE/merge-receipt/v0.6", **fields}
    receipt = MergeReceipt(**fields, merge_hash=_digest(hash_material))
    receipt.validate()
    return target, receipt


def verify_merge(
    ancestor: IdentityReceipt,
    left_chain: Iterable[IdentityReceipt],
    left_restore: RestoreReceipt,
    right_chain: Iterable[IdentityReceipt],
    right_restore: RestoreReceipt,
    target: IdentityReceipt,
    merge: MergeReceipt,
    *,
    conflicts: Iterable[MergeConflict] = (),
    resolutions: Iterable[ConflictResolution] = (),
) -> tuple[bool, tuple[str, ...]]:
    limitations: list[str] = []
    conflict_items = tuple(conflicts)
    resolution_items = tuple(resolutions)
    try:
        ancestor.validate()
        left = _validated_branch(left_chain)
        right = _validated_branch(right_chain)
        _verify_branch_origin(ancestor, left, left_restore)
        _verify_branch_origin(ancestor, right, right_restore)
        target.validate()
        merge.validate()
        expected_resolution_digest = digest_resolution_set(conflict_items, resolution_items)
    except ValueError:
        return False, ("invalid_merge_artifact",)

    left_head = left[-1]
    right_head = right[-1]
    checks = (
        (merge.identity_ref == ancestor.identity_ref == left_head.identity_ref == right_head.identity_ref == target.identity_ref, "identity_mismatch"),
        (merge.ancestor_receipt_hash == ancestor.receipt_hash, "ancestor_receipt_mismatch"),
        (merge.ancestor_lineage_root_hash == ancestor.lineage_root_hash, "ancestor_root_mismatch"),
        (merge.left_branch_ref == left_head.branch_ref, "left_branch_mismatch"),
        (merge.left_generation == left_head.generation, "left_generation_mismatch"),
        (merge.left_lineage_root_hash == left_head.lineage_root_hash, "left_root_mismatch"),
        (merge.left_head_receipt_hash == left_head.receipt_hash, "left_head_mismatch"),
        (merge.right_branch_ref == right_head.branch_ref, "right_branch_mismatch"),
        (merge.right_generation == right_head.generation, "right_generation_mismatch"),
        (merge.right_lineage_root_hash == right_head.lineage_root_hash, "right_root_mismatch"),
        (merge.right_head_receipt_hash == right_head.receipt_hash, "right_head_mismatch"),
        (merge.target_branch_ref == target.branch_ref, "target_branch_mismatch"),
        (merge.target_generation == target.generation, "target_generation_mismatch"),
        (merge.target_lineage_root_hash == target.lineage_root_hash, "target_root_mismatch"),
        (merge.target_genesis_receipt_hash == target.receipt_hash, "target_genesis_mismatch"),
        (merge.resolution_digest == expected_resolution_digest, "resolution_digest_mismatch"),
        (merge.conflict_count == len(conflict_items), "conflict_count_mismatch"),
        (target.branch_ref not in {ancestor.branch_ref, left_head.branch_ref, right_head.branch_ref}, "target_branch_not_new"),
        (target.generation > max(left_head.generation, right_head.generation), "target_generation_not_advanced"),
        (target.lineage_root_hash not in {left_head.lineage_root_hash, right_head.lineage_root_hash}, "target_root_not_new"),
        (f"merge-ancestor:{ancestor.receipt_hash}" in target.provenance_refs, "missing_ancestor_provenance"),
        (f"merge-left:{left_head.receipt_hash}" in target.provenance_refs, "missing_left_provenance"),
        (f"merge-right:{right_head.receipt_hash}" in target.provenance_refs, "missing_right_provenance"),
        (f"merge-resolutions:{merge.resolution_digest}" in target.provenance_refs, "missing_resolution_provenance"),
    )
    for ok, limitation in checks:
        if not ok:
            limitations.append(limitation)

    expected_seed = _merge_seed(
        ancestor=ancestor,
        left_head=left_head,
        right_head=right_head,
        resolution_digest=merge.resolution_digest,
        merged_payload_digest=merge.merged_payload_digest,
    )
    if target.payload_digest != digest_payload(_canonical_json(expected_seed)):
        limitations.append("target_payload_commitment_mismatch")

    return not limitations, tuple(dict.fromkeys(limitations))
