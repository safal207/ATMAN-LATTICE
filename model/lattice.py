from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from typing import Iterable, Literal

Verdict = Literal["PASS", "FAIL"]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest_payload(payload: str | bytes) -> str:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    return sha256(raw).hexdigest()


def _root_commitment(
    *,
    identity_ref: str,
    branch_ref: str,
    generation: int,
    genesis_state_ref: str,
    genesis_payload_digest: str,
) -> str:
    material = {
        "domain": "ATMAN-LATTICE/root/v0.3",
        "identity_ref": identity_ref,
        "branch_ref": branch_ref,
        "generation": generation,
        "genesis_state_ref": genesis_state_ref,
        "genesis_payload_digest": genesis_payload_digest,
    }
    return sha256(_canonical_json(material)).hexdigest()


def _receipt_hash(
    *,
    identity_ref: str,
    state_ref: str,
    generation: int,
    branch_ref: str,
    sequence: int,
    payload_digest: str,
    parent_receipt_hash: str | None,
    lineage_root_hash: str,
    provenance_refs: tuple[str, ...],
) -> str:
    material = {
        "domain": "ATMAN-LATTICE/identity-receipt/v0.3",
        "identity_ref": identity_ref,
        "state_ref": state_ref,
        "generation": generation,
        "branch_ref": branch_ref,
        "sequence": sequence,
        "payload_digest": payload_digest,
        "parent_receipt_hash": parent_receipt_hash,
        "lineage_root_hash": lineage_root_hash,
        "provenance_refs": list(provenance_refs),
    }
    return sha256(_canonical_json(material)).hexdigest()


def _require_sha256(name: str, value: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True)
class IdentityReceipt:
    identity_ref: str
    state_ref: str
    generation: int
    branch_ref: str
    sequence: int
    payload_digest: str
    parent_receipt_hash: str | None
    lineage_root_hash: str
    receipt_hash: str
    provenance_refs: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.identity_ref:
            raise ValueError("identity_ref is required")
        if not self.state_ref:
            raise ValueError("state_ref is required")
        if self.generation < 0:
            raise ValueError("generation must be >= 0")
        if not self.branch_ref:
            raise ValueError("branch_ref is required")
        if self.sequence < 0:
            raise ValueError("sequence must be >= 0")
        _require_sha256("payload_digest", self.payload_digest)
        _require_sha256("lineage_root_hash", self.lineage_root_hash)
        _require_sha256("receipt_hash", self.receipt_hash)

        if self.sequence == 0:
            if self.parent_receipt_hash is not None:
                raise ValueError("genesis receipt must not have a parent")
            expected_root = _root_commitment(
                identity_ref=self.identity_ref,
                branch_ref=self.branch_ref,
                generation=self.generation,
                genesis_state_ref=self.state_ref,
                genesis_payload_digest=self.payload_digest,
            )
            if self.lineage_root_hash != expected_root:
                raise ValueError("genesis lineage_root_hash is invalid")
        else:
            if self.parent_receipt_hash is None:
                raise ValueError("non-genesis receipt requires parent_receipt_hash")
            _require_sha256("parent_receipt_hash", self.parent_receipt_hash)

        expected_hash = _receipt_hash(
            identity_ref=self.identity_ref,
            state_ref=self.state_ref,
            generation=self.generation,
            branch_ref=self.branch_ref,
            sequence=self.sequence,
            payload_digest=self.payload_digest,
            parent_receipt_hash=self.parent_receipt_hash,
            lineage_root_hash=self.lineage_root_hash,
            provenance_refs=self.provenance_refs,
        )
        if self.receipt_hash != expected_hash:
            raise ValueError("receipt_hash does not match receipt content")


def issue_genesis_receipt(
    *,
    identity_ref: str,
    state_ref: str,
    branch_ref: str,
    generation: int,
    payload: str | bytes,
    provenance_refs: Iterable[str] = (),
) -> IdentityReceipt:
    refs = tuple(dict.fromkeys(provenance_refs))
    payload_hash = digest_payload(payload)
    root_hash = _root_commitment(
        identity_ref=identity_ref,
        branch_ref=branch_ref,
        generation=generation,
        genesis_state_ref=state_ref,
        genesis_payload_digest=payload_hash,
    )
    receipt_hash = _receipt_hash(
        identity_ref=identity_ref,
        state_ref=state_ref,
        generation=generation,
        branch_ref=branch_ref,
        sequence=0,
        payload_digest=payload_hash,
        parent_receipt_hash=None,
        lineage_root_hash=root_hash,
        provenance_refs=refs,
    )
    receipt = IdentityReceipt(
        identity_ref=identity_ref,
        state_ref=state_ref,
        generation=generation,
        branch_ref=branch_ref,
        sequence=0,
        payload_digest=payload_hash,
        parent_receipt_hash=None,
        lineage_root_hash=root_hash,
        receipt_hash=receipt_hash,
        provenance_refs=refs,
    )
    receipt.validate()
    return receipt


def issue_successor_receipt(
    parent: IdentityReceipt,
    *,
    state_ref: str,
    payload: str | bytes,
    provenance_refs: Iterable[str] = (),
) -> IdentityReceipt:
    parent.validate()
    refs = tuple(dict.fromkeys(provenance_refs))
    payload_hash = digest_payload(payload)
    sequence = parent.sequence + 1
    receipt_hash = _receipt_hash(
        identity_ref=parent.identity_ref,
        state_ref=state_ref,
        generation=parent.generation,
        branch_ref=parent.branch_ref,
        sequence=sequence,
        payload_digest=payload_hash,
        parent_receipt_hash=parent.receipt_hash,
        lineage_root_hash=parent.lineage_root_hash,
        provenance_refs=refs,
    )
    receipt = IdentityReceipt(
        identity_ref=parent.identity_ref,
        state_ref=state_ref,
        generation=parent.generation,
        branch_ref=parent.branch_ref,
        sequence=sequence,
        payload_digest=payload_hash,
        parent_receipt_hash=parent.receipt_hash,
        lineage_root_hash=parent.lineage_root_hash,
        receipt_hash=receipt_hash,
        provenance_refs=refs,
    )
    receipt.validate()
    return receipt


def verify_lineage_chain(receipts: Iterable[IdentityReceipt]) -> tuple[bool, tuple[str, ...]]:
    chain = tuple(receipts)
    if not chain:
        return False, ("empty_chain",)

    limitations: list[str] = []
    for index, receipt in enumerate(chain):
        try:
            receipt.validate()
        except ValueError:
            limitations.append(f"invalid_receipt:{index}")

    if limitations:
        return False, tuple(limitations)

    first = chain[0]
    if first.sequence != 0:
        limitations.append("chain_does_not_start_at_genesis")

    for previous, current in zip(chain, chain[1:]):
        if current.sequence != previous.sequence + 1:
            limitations.append("sequence_gap")
        if current.parent_receipt_hash != previous.receipt_hash:
            limitations.append("parent_hash_mismatch")
        if current.lineage_root_hash != previous.lineage_root_hash:
            limitations.append("lineage_root_mismatch")
        if current.identity_ref != previous.identity_ref:
            limitations.append("identity_mismatch")
        if current.branch_ref != previous.branch_ref:
            limitations.append("branch_mismatch")
        if current.generation != previous.generation:
            limitations.append("generation_mismatch")

    return not limitations, tuple(dict.fromkeys(limitations))


@dataclass(frozen=True)
class ObserverReceipt:
    observer_id: str
    subject_identity_ref: str
    branch_ref: str
    generation: int
    lineage_root_hash: str
    verdict: Verdict
    input_state_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.observer_id:
            raise ValueError("observer_id is required")
        if not self.subject_identity_ref:
            raise ValueError("subject_identity_ref is required")
        if not self.branch_ref:
            raise ValueError("branch_ref is required")
        if self.generation < 0:
            raise ValueError("generation must be >= 0")
        _require_sha256("lineage_root_hash", self.lineage_root_hash)
        if self.verdict not in {"PASS", "FAIL"}:
            raise ValueError("verdict must be PASS or FAIL")
        if not self.input_state_refs:
            raise ValueError("input_state_refs must not be empty")


def _same_lineage(left: IdentityReceipt, right: IdentityReceipt) -> bool:
    return (
        left.identity_ref == right.identity_ref
        and left.branch_ref == right.branch_ref
        and left.generation == right.generation
        and left.lineage_root_hash == right.lineage_root_hash
    )


def observe_axis(observer_id: str, left: IdentityReceipt, right: IdentityReceipt) -> ObserverReceipt:
    left.validate()
    right.validate()
    same = _same_lineage(left, right)

    limitations: list[str] = []
    if left.identity_ref != right.identity_ref:
        limitations.append("identity_mismatch")
    if left.branch_ref != right.branch_ref:
        limitations.append("branch_mismatch")
    if left.generation != right.generation:
        limitations.append("generation_mismatch")
    if left.lineage_root_hash != right.lineage_root_hash:
        limitations.append("lineage_root_mismatch")

    return ObserverReceipt(
        observer_id=observer_id,
        subject_identity_ref=left.identity_ref,
        branch_ref=left.branch_ref,
        generation=left.generation,
        lineage_root_hash=left.lineage_root_hash,
        verdict="PASS" if same else "FAIL",
        input_state_refs=(left.state_ref, right.state_ref),
        evidence_refs=tuple(
            dict.fromkeys(
                (
                    f"receipt:{left.receipt_hash}",
                    f"receipt:{right.receipt_hash}",
                    *left.provenance_refs,
                    *right.provenance_refs,
                )
            )
        ),
        limitations=tuple(limitations),
    )


def observe_space(s1: IdentityReceipt, s2: IdentityReceipt) -> ObserverReceipt:
    """A1: validate identity continuity across spatial/representational projections."""
    return observe_axis("A1", s1, s2)


def observe_time(s4: IdentityReceipt, s5: IdentityReceipt) -> ObserverReceipt:
    """A2: validate identity continuity across temporal projections."""
    return observe_axis("A2", s4, s5)


def cross_axis_bind(a1: ObserverReceipt, a2: ObserverReceipt) -> ObserverReceipt:
    """A3: bind independently valid space/time proofs to the same cryptographic lineage."""
    a1.validate()
    a2.validate()
    same_subject = a1.subject_identity_ref == a2.subject_identity_ref
    same_branch = a1.branch_ref == a2.branch_ref
    same_generation = a1.generation == a2.generation
    same_root = a1.lineage_root_hash == a2.lineage_root_hash
    local_pass = a1.verdict == "PASS" and a2.verdict == "PASS"
    consistent = local_pass and same_subject and same_branch and same_generation and same_root

    limitations = []
    if not local_pass:
        limitations.append("local_observer_failed")
    if not same_subject:
        limitations.append("identity_mismatch")
    if not same_branch:
        limitations.append("branch_mismatch")
    if not same_generation:
        limitations.append("generation_mismatch")
    if not same_root:
        limitations.append("lineage_root_mismatch")

    return ObserverReceipt(
        observer_id="A3",
        subject_identity_ref=a1.subject_identity_ref,
        branch_ref=a1.branch_ref,
        generation=a1.generation,
        lineage_root_hash=a1.lineage_root_hash,
        verdict="PASS" if consistent else "FAIL",
        input_state_refs=(a1.observer_id, a2.observer_id),
        evidence_refs=tuple(dict.fromkeys((*a1.evidence_refs, *a2.evidence_refs))),
        limitations=tuple(limitations),
    )


def global_coherence(observers: Iterable[ObserverReceipt]) -> ObserverReceipt:
    """A4: accept only one mutually coherent cryptographic observer set."""
    receipts = tuple(observers)
    if not receipts:
        raise ValueError("at least one observer receipt is required")
    for receipt in receipts:
        receipt.validate()

    subject = receipts[0].subject_identity_ref
    branch = receipts[0].branch_ref
    generation = receipts[0].generation
    lineage_root_hash = receipts[0].lineage_root_hash

    all_pass = all(r.verdict == "PASS" for r in receipts)
    same_subject = all(r.subject_identity_ref == subject for r in receipts)
    same_branch = all(r.branch_ref == branch for r in receipts)
    same_generation = all(r.generation == generation for r in receipts)
    same_root = all(r.lineage_root_hash == lineage_root_hash for r in receipts)
    coherent = all_pass and same_subject and same_branch and same_generation and same_root

    limitations = []
    if not all_pass:
        limitations.append("observer_set_contains_fail")
    if not same_subject:
        limitations.append("identity_mismatch")
    if not same_branch:
        limitations.append("branch_mismatch")
    if not same_generation:
        limitations.append("generation_mismatch")
    if not same_root:
        limitations.append("lineage_root_mismatch")

    return ObserverReceipt(
        observer_id="A4",
        subject_identity_ref=subject,
        branch_ref=branch,
        generation=generation,
        lineage_root_hash=lineage_root_hash,
        verdict="PASS" if coherent else "FAIL",
        input_state_refs=tuple(r.observer_id for r in receipts),
        evidence_refs=tuple(dict.fromkeys(ref for r in receipts for ref in r.evidence_refs)),
        limitations=tuple(limitations),
    )
