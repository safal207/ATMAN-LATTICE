from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal

Verdict = Literal["PASS", "FAIL"]


@dataclass(frozen=True)
class IdentityReceipt:
    identity_ref: str
    state_ref: str
    generation: int
    branch_ref: str
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


@dataclass(frozen=True)
class ObserverReceipt:
    observer_id: str
    subject_identity_ref: str
    branch_ref: str
    generation: int
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
        if self.verdict not in {"PASS", "FAIL"}:
            raise ValueError("verdict must be PASS or FAIL")
        if not self.input_state_refs:
            raise ValueError("input_state_refs must not be empty")


def _same_lineage(left: IdentityReceipt, right: IdentityReceipt) -> bool:
    return (
        left.identity_ref == right.identity_ref
        and left.branch_ref == right.branch_ref
        and left.generation == right.generation
    )


def observe_axis(observer_id: str, left: IdentityReceipt, right: IdentityReceipt) -> ObserverReceipt:
    left.validate()
    right.validate()
    same = _same_lineage(left, right)
    limitations: tuple[str, ...] = () if same else ("lineage_mismatch",)
    return ObserverReceipt(
        observer_id=observer_id,
        subject_identity_ref=left.identity_ref,
        branch_ref=left.branch_ref,
        generation=left.generation,
        verdict="PASS" if same else "FAIL",
        input_state_refs=(left.state_ref, right.state_ref),
        evidence_refs=tuple(dict.fromkeys((*left.provenance_refs, *right.provenance_refs))),
        limitations=limitations,
    )


def observe_space(s1: IdentityReceipt, s2: IdentityReceipt) -> ObserverReceipt:
    """A1: validate identity continuity across spatial/representational projections."""
    return observe_axis("A1", s1, s2)


def observe_time(s4: IdentityReceipt, s5: IdentityReceipt) -> ObserverReceipt:
    """A2: validate identity continuity across temporal projections."""
    return observe_axis("A2", s4, s5)


def cross_axis_bind(a1: ObserverReceipt, a2: ObserverReceipt) -> ObserverReceipt:
    """A3: bind independently valid space/time proofs to the same lineage."""
    a1.validate()
    a2.validate()
    same_subject = a1.subject_identity_ref == a2.subject_identity_ref
    same_branch = a1.branch_ref == a2.branch_ref
    same_generation = a1.generation == a2.generation
    local_pass = a1.verdict == "PASS" and a2.verdict == "PASS"
    consistent = local_pass and same_subject and same_branch and same_generation

    limitations = []
    if not local_pass:
        limitations.append("local_observer_failed")
    if not same_subject:
        limitations.append("identity_mismatch")
    if not same_branch:
        limitations.append("branch_mismatch")
    if not same_generation:
        limitations.append("generation_mismatch")

    return ObserverReceipt(
        observer_id="A3",
        subject_identity_ref=a1.subject_identity_ref,
        branch_ref=a1.branch_ref,
        generation=a1.generation,
        verdict="PASS" if consistent else "FAIL",
        input_state_refs=(a1.observer_id, a2.observer_id),
        evidence_refs=tuple(dict.fromkeys((*a1.evidence_refs, *a2.evidence_refs))),
        limitations=tuple(limitations),
    )


def global_coherence(observers: Iterable[ObserverReceipt]) -> ObserverReceipt:
    """A4: accept only one mutually coherent observer set."""
    receipts = tuple(observers)
    if not receipts:
        raise ValueError("at least one observer receipt is required")
    for receipt in receipts:
        receipt.validate()

    subject = receipts[0].subject_identity_ref
    branch = receipts[0].branch_ref
    generation = receipts[0].generation

    all_pass = all(r.verdict == "PASS" for r in receipts)
    same_subject = all(r.subject_identity_ref == subject for r in receipts)
    same_branch = all(r.branch_ref == branch for r in receipts)
    same_generation = all(r.generation == generation for r in receipts)
    coherent = all_pass and same_subject and same_branch and same_generation

    limitations = []
    if not all_pass:
        limitations.append("observer_set_contains_fail")
    if not same_subject:
        limitations.append("identity_mismatch")
    if not same_branch:
        limitations.append("branch_mismatch")
    if not same_generation:
        limitations.append("generation_mismatch")

    return ObserverReceipt(
        observer_id="A4",
        subject_identity_ref=subject,
        branch_ref=branch,
        generation=generation,
        verdict="PASS" if coherent else "FAIL",
        input_state_refs=tuple(r.observer_id for r in receipts),
        evidence_refs=tuple(dict.fromkeys(ref for r in receipts for ref in r.evidence_refs)),
        limitations=tuple(limitations),
    )
