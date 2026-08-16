from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Literal

from model.lattice import IdentityReceipt, digest_payload, issue_genesis_receipt
from model.merge import MergeReceipt

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IncursionVerdict = Literal["COEXIST", "INCOMPATIBLE"]
ResolutionMode = Literal["NONE", "ISOLATE", "FORK", "RECONCILE", "MERGE", "REJECT", "COMPENSATE"]


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True)
class PotentialBranch:
    potential_id: str
    identity_ref: str
    source_receipt_hash: str
    source_lineage_root_hash: str
    source_branch_ref: str
    source_generation: int
    proposed_branch_ref: str
    proposed_generation: int
    payload_digest: str
    created_at: int
    rationale_ref: str
    potential_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/potential-branch/v1.3",
            "potential_id": self.potential_id,
            "identity_ref": self.identity_ref,
            "source_receipt_hash": self.source_receipt_hash,
            "source_lineage_root_hash": self.source_lineage_root_hash,
            "source_branch_ref": self.source_branch_ref,
            "source_generation": self.source_generation,
            "proposed_branch_ref": self.proposed_branch_ref,
            "proposed_generation": self.proposed_generation,
            "payload_digest": self.payload_digest,
            "created_at": self.created_at,
            "rationale_ref": self.rationale_ref,
        }

    def validate(self) -> None:
        if not self.potential_id or not self.identity_ref:
            raise ValueError("potential_id and identity_ref are required")
        if not self.source_branch_ref or not self.proposed_branch_ref:
            raise ValueError("branch refs are required")
        if self.proposed_branch_ref == self.source_branch_ref:
            raise ValueError("potential branch must differ from source branch")
        if self.source_generation < 0:
            raise ValueError("source_generation must be >= 0")
        if self.proposed_generation <= self.source_generation:
            raise ValueError("proposed_generation must advance")
        if self.created_at < 0:
            raise ValueError("created_at must be >= 0")
        if not self.rationale_ref:
            raise ValueError("rationale_ref is required")
        for name, value in (
            ("source_receipt_hash", self.source_receipt_hash),
            ("source_lineage_root_hash", self.source_lineage_root_hash),
            ("payload_digest", self.payload_digest),
            ("potential_hash", self.potential_hash),
        ):
            _require_digest(name, value)
        if self.potential_hash != _digest(self.material()):
            raise ValueError("potential_hash does not match potential content")


def propose_branch(
    source: IdentityReceipt,
    *,
    potential_id: str,
    proposed_branch_ref: str,
    proposed_generation: int,
    payload: str | bytes,
    created_at: int,
    rationale_ref: str,
) -> PotentialBranch:
    """Describe a possible future without inserting it into committed lineage."""
    source.validate()
    fields = {
        "potential_id": potential_id,
        "identity_ref": source.identity_ref,
        "source_receipt_hash": source.receipt_hash,
        "source_lineage_root_hash": source.lineage_root_hash,
        "source_branch_ref": source.branch_ref,
        "source_generation": source.generation,
        "proposed_branch_ref": proposed_branch_ref,
        "proposed_generation": proposed_generation,
        "payload_digest": digest_payload(payload),
        "created_at": created_at,
        "rationale_ref": rationale_ref,
    }
    material = {"domain": "ATMAN-LATTICE/potential-branch/v1.3", **fields}
    potential = PotentialBranch(**fields, potential_hash=_digest(material))
    potential.validate()
    return potential


@dataclass(frozen=True)
class BranchCommitReceipt:
    potential_hash: str
    identity_ref: str
    source_receipt_hash: str
    source_lineage_root_hash: str
    target_branch_ref: str
    target_generation: int
    target_lineage_root_hash: str
    target_genesis_receipt_hash: str
    payload_digest: str
    committed_at: int
    commit_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/branch-commit/v1.3",
            "potential_hash": self.potential_hash,
            "identity_ref": self.identity_ref,
            "source_receipt_hash": self.source_receipt_hash,
            "source_lineage_root_hash": self.source_lineage_root_hash,
            "target_branch_ref": self.target_branch_ref,
            "target_generation": self.target_generation,
            "target_lineage_root_hash": self.target_lineage_root_hash,
            "target_genesis_receipt_hash": self.target_genesis_receipt_hash,
            "payload_digest": self.payload_digest,
            "committed_at": self.committed_at,
        }

    def validate(self) -> None:
        if not self.identity_ref or not self.target_branch_ref:
            raise ValueError("identity_ref and target_branch_ref are required")
        if self.target_generation < 0 or self.committed_at < 0:
            raise ValueError("generation and time must be >= 0")
        for name, value in (
            ("potential_hash", self.potential_hash),
            ("source_receipt_hash", self.source_receipt_hash),
            ("source_lineage_root_hash", self.source_lineage_root_hash),
            ("target_lineage_root_hash", self.target_lineage_root_hash),
            ("target_genesis_receipt_hash", self.target_genesis_receipt_hash),
            ("payload_digest", self.payload_digest),
            ("commit_hash", self.commit_hash),
        ):
            _require_digest(name, value)
        if self.commit_hash != _digest(self.material()):
            raise ValueError("commit_hash does not match commit content")


def commit_potential(
    source: IdentityReceipt,
    potential: PotentialBranch,
    *,
    payload: str | bytes,
    committed_at: int,
) -> tuple[IdentityReceipt, BranchCommitReceipt]:
    """Turn one explicit potential into committed history as a new lineage."""
    source.validate()
    potential.validate()
    if potential.identity_ref != source.identity_ref:
        raise ValueError("potential identity does not match source")
    if potential.source_receipt_hash != source.receipt_hash:
        raise ValueError("potential source receipt does not match source")
    if potential.source_lineage_root_hash != source.lineage_root_hash:
        raise ValueError("potential source lineage does not match source")
    if potential.payload_digest != digest_payload(payload):
        raise ValueError("commit payload differs from proposed payload")
    if committed_at < potential.created_at:
        raise ValueError("commit cannot predate potential creation")

    target = issue_genesis_receipt(
        identity_ref=source.identity_ref,
        state_ref=f"commit:{potential.potential_id}",
        branch_ref=potential.proposed_branch_ref,
        generation=potential.proposed_generation,
        payload=payload,
        provenance_refs=(
            f"potential:{potential.potential_hash}",
            f"potential-source:{source.receipt_hash}",
            f"potential-source-root:{source.lineage_root_hash}",
        ),
    )
    fields = {
        "potential_hash": potential.potential_hash,
        "identity_ref": source.identity_ref,
        "source_receipt_hash": source.receipt_hash,
        "source_lineage_root_hash": source.lineage_root_hash,
        "target_branch_ref": target.branch_ref,
        "target_generation": target.generation,
        "target_lineage_root_hash": target.lineage_root_hash,
        "target_genesis_receipt_hash": target.receipt_hash,
        "payload_digest": potential.payload_digest,
        "committed_at": committed_at,
    }
    receipt = BranchCommitReceipt(
        **fields,
        commit_hash=_digest({"domain": "ATMAN-LATTICE/branch-commit/v1.3", **fields}),
    )
    receipt.validate()
    return target, receipt


def verify_branch_commit(
    source: IdentityReceipt,
    potential: PotentialBranch,
    target: IdentityReceipt,
    commit: BranchCommitReceipt,
) -> tuple[bool, tuple[str, ...]]:
    limitations: list[str] = []
    try:
        source.validate()
        potential.validate()
        target.validate()
        commit.validate()
    except ValueError:
        return False, ("invalid_branch_commit_artifact",)
    checks = (
        (potential.source_receipt_hash == source.receipt_hash, "potential_source_mismatch"),
        (commit.potential_hash == potential.potential_hash, "potential_hash_mismatch"),
        (commit.identity_ref == source.identity_ref == target.identity_ref, "identity_mismatch"),
        (commit.source_receipt_hash == source.receipt_hash, "source_receipt_mismatch"),
        (commit.source_lineage_root_hash == source.lineage_root_hash, "source_root_mismatch"),
        (commit.target_branch_ref == target.branch_ref == potential.proposed_branch_ref, "target_branch_mismatch"),
        (commit.target_generation == target.generation == potential.proposed_generation, "target_generation_mismatch"),
        (commit.target_lineage_root_hash == target.lineage_root_hash, "target_root_mismatch"),
        (commit.target_genesis_receipt_hash == target.receipt_hash, "target_receipt_mismatch"),
        (target.lineage_root_hash != source.lineage_root_hash, "lineage_not_forked"),
        (f"potential:{potential.potential_hash}" in target.provenance_refs, "missing_potential_provenance"),
    )
    for ok, limitation in checks:
        if not ok:
            limitations.append(limitation)
    return not limitations, tuple(dict.fromkeys(limitations))


@dataclass(frozen=True)
class IncursionReceipt:
    identity_ref: str
    left_branch_ref: str
    left_generation: int
    left_lineage_root_hash: str
    left_head_receipt_hash: str
    right_branch_ref: str
    right_generation: int
    right_lineage_root_hash: str
    right_head_receipt_hash: str
    verdict: IncursionVerdict
    resolution_mode: ResolutionMode
    reason_ref: str
    evidence_ref: str
    assessed_at: int
    incursion_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/incursion/v1.3",
            "identity_ref": self.identity_ref,
            "left_branch_ref": self.left_branch_ref,
            "left_generation": self.left_generation,
            "left_lineage_root_hash": self.left_lineage_root_hash,
            "left_head_receipt_hash": self.left_head_receipt_hash,
            "right_branch_ref": self.right_branch_ref,
            "right_generation": self.right_generation,
            "right_lineage_root_hash": self.right_lineage_root_hash,
            "right_head_receipt_hash": self.right_head_receipt_hash,
            "verdict": self.verdict,
            "resolution_mode": self.resolution_mode,
            "reason_ref": self.reason_ref,
            "evidence_ref": self.evidence_ref,
            "assessed_at": self.assessed_at,
        }

    def validate(self) -> None:
        if not self.identity_ref:
            raise ValueError("identity_ref is required")
        if self.left_branch_ref == self.right_branch_ref:
            raise ValueError("incursion requires distinct branches")
        if self.left_lineage_root_hash == self.right_lineage_root_hash:
            raise ValueError("incursion requires distinct lineage roots")
        if self.verdict not in {"COEXIST", "INCOMPATIBLE"}:
            raise ValueError("invalid incursion verdict")
        if self.resolution_mode not in {"NONE", "ISOLATE", "FORK", "RECONCILE", "MERGE", "REJECT", "COMPENSATE"}:
            raise ValueError("invalid resolution mode")
        if self.verdict == "COEXIST" and self.resolution_mode != "NONE":
            raise ValueError("coexisting branches require NONE resolution mode")
        if self.verdict == "INCOMPATIBLE" and self.resolution_mode == "NONE":
            raise ValueError("incompatible branches require explicit resolution mode")
        if not self.reason_ref or not self.evidence_ref:
            raise ValueError("reason_ref and evidence_ref are required")
        if self.assessed_at < 0:
            raise ValueError("assessed_at must be >= 0")
        for name, value in (
            ("left_lineage_root_hash", self.left_lineage_root_hash),
            ("left_head_receipt_hash", self.left_head_receipt_hash),
            ("right_lineage_root_hash", self.right_lineage_root_hash),
            ("right_head_receipt_hash", self.right_head_receipt_hash),
            ("incursion_hash", self.incursion_hash),
        ):
            _require_digest(name, value)
        if self.incursion_hash != _digest(self.material()):
            raise ValueError("incursion_hash does not match receipt content")


def assess_incursion(
    left: IdentityReceipt,
    right: IdentityReceipt,
    *,
    verdict: IncursionVerdict,
    resolution_mode: ResolutionMode,
    reason_ref: str,
    evidence_ref: str,
    assessed_at: int,
) -> IncursionReceipt:
    """Record whether two individually valid futures may coexist without composition."""
    left.validate()
    right.validate()
    if left.identity_ref != right.identity_ref:
        raise ValueError("incursion branches must refer to the same identity")
    fields = {
        "identity_ref": left.identity_ref,
        "left_branch_ref": left.branch_ref,
        "left_generation": left.generation,
        "left_lineage_root_hash": left.lineage_root_hash,
        "left_head_receipt_hash": left.receipt_hash,
        "right_branch_ref": right.branch_ref,
        "right_generation": right.generation,
        "right_lineage_root_hash": right.lineage_root_hash,
        "right_head_receipt_hash": right.receipt_hash,
        "verdict": verdict,
        "resolution_mode": resolution_mode,
        "reason_ref": reason_ref,
        "evidence_ref": evidence_ref,
        "assessed_at": assessed_at,
    }
    receipt = IncursionReceipt(
        **fields,
        incursion_hash=_digest({"domain": "ATMAN-LATTICE/incursion/v1.3", **fields}),
    )
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class CompositeRealityReceipt:
    identity_ref: str
    left_head_receipt_hash: str
    left_lineage_root_hash: str
    right_head_receipt_hash: str
    right_lineage_root_hash: str
    incursion_hash: str
    merge_hash: str
    target_genesis_receipt_hash: str
    target_lineage_root_hash: str
    created_at: int
    narrative_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/composite-reality/v1.3",
            "identity_ref": self.identity_ref,
            "left_head_receipt_hash": self.left_head_receipt_hash,
            "left_lineage_root_hash": self.left_lineage_root_hash,
            "right_head_receipt_hash": self.right_head_receipt_hash,
            "right_lineage_root_hash": self.right_lineage_root_hash,
            "incursion_hash": self.incursion_hash,
            "merge_hash": self.merge_hash,
            "target_genesis_receipt_hash": self.target_genesis_receipt_hash,
            "target_lineage_root_hash": self.target_lineage_root_hash,
            "created_at": self.created_at,
        }

    def validate(self) -> None:
        if not self.identity_ref:
            raise ValueError("identity_ref is required")
        if self.created_at < 0:
            raise ValueError("created_at must be >= 0")
        for name, value in (
            ("left_head_receipt_hash", self.left_head_receipt_hash),
            ("left_lineage_root_hash", self.left_lineage_root_hash),
            ("right_head_receipt_hash", self.right_head_receipt_hash),
            ("right_lineage_root_hash", self.right_lineage_root_hash),
            ("incursion_hash", self.incursion_hash),
            ("merge_hash", self.merge_hash),
            ("target_genesis_receipt_hash", self.target_genesis_receipt_hash),
            ("target_lineage_root_hash", self.target_lineage_root_hash),
            ("narrative_hash", self.narrative_hash),
        ):
            _require_digest(name, value)
        if self.narrative_hash != _digest(self.material()):
            raise ValueError("narrative_hash does not match receipt content")


def bind_composite_reality(
    left: IdentityReceipt,
    right: IdentityReceipt,
    target: IdentityReceipt,
    incursion: IncursionReceipt,
    merge: MergeReceipt,
    *,
    created_at: int,
) -> CompositeRealityReceipt:
    """Bind a merged reality to both parent histories so composition cannot erase ancestry."""
    left.validate()
    right.validate()
    target.validate()
    incursion.validate()
    merge.validate()
    if incursion.left_head_receipt_hash != left.receipt_hash or incursion.right_head_receipt_hash != right.receipt_hash:
        raise ValueError("incursion does not describe the exact merge parents")
    if merge.left_head_receipt_hash != left.receipt_hash or merge.right_head_receipt_hash != right.receipt_hash:
        raise ValueError("merge does not preserve the exact parent heads")
    if merge.target_genesis_receipt_hash != target.receipt_hash:
        raise ValueError("merge target does not match target receipt")
    if merge.target_lineage_root_hash != target.lineage_root_hash:
        raise ValueError("merge target root does not match target receipt")
    if merge.identity_ref != left.identity_ref or right.identity_ref != left.identity_ref or target.identity_ref != left.identity_ref:
        raise ValueError("composite identity mismatch")
    fields = {
        "identity_ref": left.identity_ref,
        "left_head_receipt_hash": left.receipt_hash,
        "left_lineage_root_hash": left.lineage_root_hash,
        "right_head_receipt_hash": right.receipt_hash,
        "right_lineage_root_hash": right.lineage_root_hash,
        "incursion_hash": incursion.incursion_hash,
        "merge_hash": merge.merge_hash,
        "target_genesis_receipt_hash": target.receipt_hash,
        "target_lineage_root_hash": target.lineage_root_hash,
        "created_at": created_at,
    }
    receipt = CompositeRealityReceipt(
        **fields,
        narrative_hash=_digest({"domain": "ATMAN-LATTICE/composite-reality/v1.3", **fields}),
    )
    receipt.validate()
    return receipt


def verify_composite_reality(
    left: IdentityReceipt,
    right: IdentityReceipt,
    target: IdentityReceipt,
    incursion: IncursionReceipt,
    merge: MergeReceipt,
    composite: CompositeRealityReceipt,
) -> tuple[bool, tuple[str, ...]]:
    limitations: list[str] = []
    try:
        left.validate()
        right.validate()
        target.validate()
        incursion.validate()
        merge.validate()
        composite.validate()
    except ValueError:
        return False, ("invalid_composite_artifact",)
    checks = (
        (composite.identity_ref == left.identity_ref == right.identity_ref == target.identity_ref, "identity_mismatch"),
        (composite.left_head_receipt_hash == left.receipt_hash == merge.left_head_receipt_hash, "left_parent_erased_or_changed"),
        (composite.right_head_receipt_hash == right.receipt_hash == merge.right_head_receipt_hash, "right_parent_erased_or_changed"),
        (composite.left_lineage_root_hash == left.lineage_root_hash, "left_root_mismatch"),
        (composite.right_lineage_root_hash == right.lineage_root_hash, "right_root_mismatch"),
        (composite.incursion_hash == incursion.incursion_hash, "incursion_mismatch"),
        (composite.merge_hash == merge.merge_hash, "merge_mismatch"),
        (composite.target_genesis_receipt_hash == target.receipt_hash == merge.target_genesis_receipt_hash, "target_receipt_mismatch"),
        (composite.target_lineage_root_hash == target.lineage_root_hash == merge.target_lineage_root_hash, "target_root_mismatch"),
        (target.lineage_root_hash not in {left.lineage_root_hash, right.lineage_root_hash}, "composite_reused_parent_root"),
    )
    for ok, limitation in checks:
        if not ok:
            limitations.append(limitation)
    return not limitations, tuple(dict.fromkeys(limitations))
