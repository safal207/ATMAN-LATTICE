from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from model.dependency_graph_revision import DependencyGraphState, make_dependency_graph
from model.replication import ReplicationEvaluationReceipt, ReplicationSeriesSnapshot, ReplicationTargetReceipt

RemediationAction = Literal[
    "HOLD",
    "COLLECT_MORE_DATA",
    "PARAMETER_REVISION",
    "STRUCTURAL_REVISION",
    "SAFE_ROLLBACK",
]
RemediationAssessmentStatus = Literal[
    "NON_MUTATING_SAFE",
    "DOWNSTREAM_GOVERNANCE_REQUIRED",
    "ROLLBACK_SUPPORTED",
    "ROLLBACK_UNSUPPORTED",
]
RemediationReviewDecision = Literal["APPROVE", "HOLD", "REJECT"]
RemediationExecutionKind = Literal[
    "NO_GRAPH_CHANGE",
    "DOWNSTREAM_GOVERNANCE_REQUIRED",
    "FORWARD_ROLLBACK",
]

ALL_REMEDIATION_ACTIONS: tuple[RemediationAction, ...] = (
    "COLLECT_MORE_DATA",
    "HOLD",
    "PARAMETER_REVISION",
    "SAFE_ROLLBACK",
    "STRUCTURAL_REVISION",
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _route_for(action: RemediationAction) -> str | None:
    if action == "PARAMETER_REVISION":
        return "ATMAN-REVISION/1.13"
    if action == "STRUCTURAL_REVISION":
        return "ATMAN-GRAPH/1.14"
    return None


@dataclass(frozen=True)
class RemediationPolicy:
    policy_ref: str
    subject_identity_ref: str
    allowed_actions: tuple[RemediationAction, ...]
    rollback_requires_nonpositive_improvement: bool
    registered_at: int
    policy_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/remediation-policy/v1.19",
            "policy_ref": self.policy_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "allowed_actions": list(self.allowed_actions),
            "rollback_requires_nonpositive_improvement": self.rollback_requires_nonpositive_improvement,
            "registered_at": self.registered_at,
        }

    def validate(self) -> None:
        if not self.policy_ref or not self.subject_identity_ref or self.registered_at < 0:
            raise ValueError("invalid remediation policy metadata")
        if tuple(sorted(set(self.allowed_actions))) != self.allowed_actions or not self.allowed_actions:
            raise ValueError("remediation allowed_actions must be unique and canonically sorted")
        if any(value not in ALL_REMEDIATION_ACTIONS for value in self.allowed_actions):
            raise ValueError("unsupported remediation action")
        if not self.rollback_requires_nonpositive_improvement:
            raise ValueError("v1.19 reference rollback policy requires non-positive current structural advantage")
        _require_digest("policy_hash", self.policy_hash)
        if self.policy_hash != _digest(self.material()):
            raise ValueError("policy_hash does not match remediation policy")


def make_remediation_policy(
    *,
    policy_ref: str,
    subject_identity_ref: str,
    allowed_actions: tuple[RemediationAction, ...] = ALL_REMEDIATION_ACTIONS,
    rollback_requires_nonpositive_improvement: bool = True,
    registered_at: int,
) -> RemediationPolicy:
    canonical = tuple(sorted(set(allowed_actions)))
    fields = {
        "policy_ref": policy_ref,
        "subject_identity_ref": subject_identity_ref,
        "allowed_actions": canonical,
        "rollback_requires_nonpositive_improvement": rollback_requires_nonpositive_improvement,
        "registered_at": registered_at,
    }
    provisional = RemediationPolicy(**fields, policy_hash="0" * 64)
    result = RemediationPolicy(**fields, policy_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class DriftRemediationProposal:
    proposal_ref: str
    subject_identity_ref: str
    target_hash: str
    snapshot_hash: str
    latest_evaluation_hash: str
    confirmed_revision_hash: str
    current_graph_hash: str
    current_generation: int
    rollback_graph_hash: str
    rollback_generation: int
    action: RemediationAction
    downstream_protocol: str | None
    drift_kind: str
    reason_ref: str
    proposer_ref: str
    proposed_at: int
    proposal_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/drift-remediation-proposal/v1.19",
            "proposal_ref": self.proposal_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "target_hash": self.target_hash,
            "snapshot_hash": self.snapshot_hash,
            "latest_evaluation_hash": self.latest_evaluation_hash,
            "confirmed_revision_hash": self.confirmed_revision_hash,
            "current_graph_hash": self.current_graph_hash,
            "current_generation": self.current_generation,
            "rollback_graph_hash": self.rollback_graph_hash,
            "rollback_generation": self.rollback_generation,
            "action": self.action,
            "downstream_protocol": self.downstream_protocol,
            "drift_kind": self.drift_kind,
            "reason_ref": self.reason_ref,
            "proposer_ref": self.proposer_ref,
            "proposed_at": self.proposed_at,
        }

    def validate(self) -> None:
        if not self.proposal_ref or not self.subject_identity_ref or not self.reason_ref or not self.proposer_ref:
            raise ValueError("remediation proposal refs are required")
        for name, value in (
            ("target_hash", self.target_hash),
            ("snapshot_hash", self.snapshot_hash),
            ("latest_evaluation_hash", self.latest_evaluation_hash),
            ("confirmed_revision_hash", self.confirmed_revision_hash),
            ("current_graph_hash", self.current_graph_hash),
            ("rollback_graph_hash", self.rollback_graph_hash),
            ("proposal_hash", self.proposal_hash),
        ):
            _require_digest(name, value)
        if self.action not in ALL_REMEDIATION_ACTIONS:
            raise ValueError("invalid remediation action")
        if self.downstream_protocol != _route_for(self.action):
            raise ValueError("remediation downstream protocol/action mismatch")
        if self.drift_kind not in {"STRUCTURAL", "PERFORMANCE", "BOTH"}:
            raise ValueError("remediation requires an observed drift kind")
        if self.current_generation < 1 or self.rollback_generation < 0 or self.current_generation != self.rollback_generation + 1:
            raise ValueError("safe remediation requires the exact pre-confirmation graph generation")
        if self.proposed_at < 0 or self.proposal_hash != _digest(self.material()):
            raise ValueError("invalid remediation proposal material")


def make_remediation_proposal(
    *,
    proposal_ref: str,
    target: ReplicationTargetReceipt,
    snapshot: ReplicationSeriesSnapshot,
    latest_evaluation: ReplicationEvaluationReceipt,
    current_graph: DependencyGraphState,
    rollback_graph: DependencyGraphState,
    policy: RemediationPolicy,
    action: RemediationAction,
    reason_ref: str,
    proposer_ref: str,
    proposed_at: int,
) -> DriftRemediationProposal:
    target.validate(); snapshot.validate(); latest_evaluation.validate(); current_graph.validate(); rollback_graph.validate(); policy.validate()
    if snapshot.signal != "PERSISTENT_DRIFT_SIGNAL":
        raise ValueError("remediation requires PERSISTENT_DRIFT_SIGNAL")
    if action not in policy.allowed_actions:
        raise ValueError("remediation action is not allowed by policy")
    if target.subject_identity_ref != policy.subject_identity_ref or snapshot.target_hash != target.target_hash:
        raise ValueError("remediation policy/target/snapshot mismatch")
    if latest_evaluation.target_hash != target.target_hash or latest_evaluation.evaluation_hash != snapshot.evaluation_hashes[-1]:
        raise ValueError("remediation requires exact latest replication evaluation")
    if latest_evaluation.status != "DRIFT_SIGNAL" or latest_evaluation.drift_kind == "NONE":
        raise ValueError("remediation requires current drift evidence")
    if current_graph.graph_hash != target.confirmed_graph_hash or current_graph.generation != target.confirmed_generation:
        raise ValueError("remediation target graph is no longer current")
    if rollback_graph.subject_identity_ref != current_graph.subject_identity_ref or rollback_graph.generation + 1 != current_graph.generation:
        raise ValueError("rollback graph must be the exact previous structural generation")
    if proposed_at < snapshot.measured_at:
        raise ValueError("remediation proposal cannot predate drift snapshot")
    fields = {
        "proposal_ref": proposal_ref,
        "subject_identity_ref": target.subject_identity_ref,
        "target_hash": target.target_hash,
        "snapshot_hash": snapshot.snapshot_hash,
        "latest_evaluation_hash": latest_evaluation.evaluation_hash,
        "confirmed_revision_hash": target.confirmed_revision_hash,
        "current_graph_hash": current_graph.graph_hash,
        "current_generation": current_graph.generation,
        "rollback_graph_hash": rollback_graph.graph_hash,
        "rollback_generation": rollback_graph.generation,
        "action": action,
        "downstream_protocol": _route_for(action),
        "drift_kind": latest_evaluation.drift_kind,
        "reason_ref": reason_ref,
        "proposer_ref": proposer_ref,
        "proposed_at": proposed_at,
    }
    provisional = DriftRemediationProposal(**fields, proposal_hash="0" * 64)
    result = DriftRemediationProposal(**fields, proposal_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class RemediationAssessmentReceipt:
    proposal_hash: str
    snapshot_hash: str
    latest_evaluation_hash: str
    action: RemediationAction
    latest_regularized_improvement_ppm: int
    latest_confirmed_mean_brier_ppm: int
    baseline_confirmed_mean_brier_ppm: int
    latest_drift_kind: str
    status: RemediationAssessmentStatus
    rollback_margin_ppm: int | None
    proposer_ref: str
    latest_evaluator_ref: str
    assessor_ref: str
    assessed_at: int
    assessment_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/remediation-assessment/v1.19",
            "proposal_hash": self.proposal_hash,
            "snapshot_hash": self.snapshot_hash,
            "latest_evaluation_hash": self.latest_evaluation_hash,
            "action": self.action,
            "latest_regularized_improvement_ppm": self.latest_regularized_improvement_ppm,
            "latest_confirmed_mean_brier_ppm": self.latest_confirmed_mean_brier_ppm,
            "baseline_confirmed_mean_brier_ppm": self.baseline_confirmed_mean_brier_ppm,
            "latest_drift_kind": self.latest_drift_kind,
            "status": self.status,
            "rollback_margin_ppm": self.rollback_margin_ppm,
            "proposer_ref": self.proposer_ref,
            "latest_evaluator_ref": self.latest_evaluator_ref,
            "assessor_ref": self.assessor_ref,
            "assessed_at": self.assessed_at,
        }

    def validate(self) -> None:
        for name, value in (("proposal_hash", self.proposal_hash), ("snapshot_hash", self.snapshot_hash), ("latest_evaluation_hash", self.latest_evaluation_hash), ("assessment_hash", self.assessment_hash)):
            _require_digest(name, value)
        if self.action not in ALL_REMEDIATION_ACTIONS:
            raise ValueError("invalid remediation assessment action")
        if self.status not in {"NON_MUTATING_SAFE", "DOWNSTREAM_GOVERNANCE_REQUIRED", "ROLLBACK_SUPPORTED", "ROLLBACK_UNSUPPORTED"}:
            raise ValueError("invalid remediation assessment status")
        if self.latest_confirmed_mean_brier_ppm < 0 or self.baseline_confirmed_mean_brier_ppm < 0:
            raise ValueError("invalid remediation Brier metrics")
        if self.latest_drift_kind not in {"STRUCTURAL", "PERFORMANCE", "BOTH"}:
            raise ValueError("invalid remediation drift kind")
        if not self.assessor_ref or self.assessor_ref in {self.proposer_ref, self.latest_evaluator_ref}:
            raise ValueError("remediation assessor must be independent from proposer and latest replication evaluator")
        if self.action == "SAFE_ROLLBACK":
            expected = "ROLLBACK_SUPPORTED" if self.latest_regularized_improvement_ppm <= 0 else "ROLLBACK_UNSUPPORTED"
            if self.status != expected:
                raise ValueError("rollback assessment status does not match observed replication advantage")
            if self.rollback_margin_ppm != max(0, -self.latest_regularized_improvement_ppm):
                raise ValueError("rollback margin does not match latest replication metrics")
        else:
            if self.rollback_margin_ppm is not None:
                raise ValueError("non-rollback assessment cannot carry rollback margin")
            expected = "DOWNSTREAM_GOVERNANCE_REQUIRED" if self.action in {"PARAMETER_REVISION", "STRUCTURAL_REVISION"} else "NON_MUTATING_SAFE"
            if self.status != expected:
                raise ValueError("remediation assessment/action mismatch")
        if self.assessed_at < 0 or self.assessment_hash != _digest(self.material()):
            raise ValueError("invalid remediation assessment material")


def assess_remediation_proposal(
    *,
    proposal: DriftRemediationProposal,
    latest_evaluation: ReplicationEvaluationReceipt,
    policy: RemediationPolicy,
    assessor_ref: str,
    assessed_at: int,
) -> RemediationAssessmentReceipt:
    proposal.validate(); latest_evaluation.validate(); policy.validate()
    if proposal.latest_evaluation_hash != latest_evaluation.evaluation_hash or proposal.snapshot_hash == "0" * 64:
        raise ValueError("remediation proposal/evaluation binding mismatch")
    if latest_evaluation.status != "DRIFT_SIGNAL" or latest_evaluation.regularized_improvement_ppm is None or latest_evaluation.confirmed_mean_brier_ppm is None:
        raise ValueError("remediation assessment requires complete drift metrics")
    if proposal.action == "SAFE_ROLLBACK":
        supported = latest_evaluation.regularized_improvement_ppm <= 0
        status: RemediationAssessmentStatus = "ROLLBACK_SUPPORTED" if supported else "ROLLBACK_UNSUPPORTED"
        margin = max(0, -latest_evaluation.regularized_improvement_ppm) if supported else 0
    elif proposal.action in {"PARAMETER_REVISION", "STRUCTURAL_REVISION"}:
        status = "DOWNSTREAM_GOVERNANCE_REQUIRED"; margin = None
    else:
        status = "NON_MUTATING_SAFE"; margin = None
    fields = {
        "proposal_hash": proposal.proposal_hash,
        "snapshot_hash": proposal.snapshot_hash,
        "latest_evaluation_hash": latest_evaluation.evaluation_hash,
        "action": proposal.action,
        "latest_regularized_improvement_ppm": int(latest_evaluation.regularized_improvement_ppm),
        "latest_confirmed_mean_brier_ppm": int(latest_evaluation.confirmed_mean_brier_ppm),
        "baseline_confirmed_mean_brier_ppm": latest_evaluation.baseline_confirmed_mean_brier_ppm,
        "latest_drift_kind": latest_evaluation.drift_kind,
        "status": status,
        "rollback_margin_ppm": margin,
        "proposer_ref": proposal.proposer_ref,
        "latest_evaluator_ref": latest_evaluation.evaluator_ref,
        "assessor_ref": assessor_ref,
        "assessed_at": assessed_at,
    }
    provisional = RemediationAssessmentReceipt(**fields, assessment_hash="0" * 64)
    result = RemediationAssessmentReceipt(**fields, assessment_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class RemediationSelectionReceipt:
    selection_ref: str
    snapshot_hash: str
    proposal_hashes: tuple[str, ...]
    assessment_hashes: tuple[str, ...]
    selected_proposal_hash: str
    selected_assessment_hash: str
    selected_action: RemediationAction
    selected_status: RemediationAssessmentStatus
    selected_proposer_ref: str
    selected_assessor_ref: str
    selector_ref: str
    selected_at: int
    selection_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/remediation-selection/v1.19",
            "selection_ref": self.selection_ref,
            "snapshot_hash": self.snapshot_hash,
            "proposal_hashes": list(self.proposal_hashes),
            "assessment_hashes": list(self.assessment_hashes),
            "selected_proposal_hash": self.selected_proposal_hash,
            "selected_assessment_hash": self.selected_assessment_hash,
            "selected_action": self.selected_action,
            "selected_status": self.selected_status,
            "selected_proposer_ref": self.selected_proposer_ref,
            "selected_assessor_ref": self.selected_assessor_ref,
            "selector_ref": self.selector_ref,
            "selected_at": self.selected_at,
        }

    def validate(self) -> None:
        if not self.selection_ref or not self.selector_ref:
            raise ValueError("remediation selection refs are required")
        _require_digest("snapshot_hash", self.snapshot_hash); _require_digest("selection_hash", self.selection_hash)
        for value in self.proposal_hashes + self.assessment_hashes:
            _require_digest("remediation_selection_component", value)
        _require_digest("selected_proposal_hash", self.selected_proposal_hash); _require_digest("selected_assessment_hash", self.selected_assessment_hash)
        if tuple(sorted(set(self.proposal_hashes))) != self.proposal_hashes or tuple(sorted(set(self.assessment_hashes))) != self.assessment_hashes:
            raise ValueError("remediation selection sets must be unique and sorted")
        if len(self.proposal_hashes) != len(self.assessment_hashes) or self.selected_proposal_hash not in self.proposal_hashes or self.selected_assessment_hash not in self.assessment_hashes:
            raise ValueError("remediation selection must bind complete proposal/assessment sets")
        if self.selected_status == "ROLLBACK_UNSUPPORTED":
            raise ValueError("unsupported rollback cannot be selected")
        if self.selector_ref in {self.selected_proposer_ref, self.selected_assessor_ref}:
            raise ValueError("remediation selector must be independent from selected proposer and assessor")
        if self.selected_at < 0 or self.selection_hash != _digest(self.material()):
            raise ValueError("invalid remediation selection material")


def select_remediation(
    *,
    selection_ref: str,
    snapshot: ReplicationSeriesSnapshot,
    proposals: tuple[DriftRemediationProposal, ...],
    assessments: tuple[RemediationAssessmentReceipt, ...],
    selected_proposal_hash: str,
    selector_ref: str,
    selected_at: int,
) -> RemediationSelectionReceipt:
    snapshot.validate()
    if snapshot.signal != "PERSISTENT_DRIFT_SIGNAL" or not proposals or len(proposals) != len(assessments):
        raise ValueError("remediation selection requires persistent drift and fully assessed proposals")
    for item in proposals: item.validate()
    for item in assessments: item.validate()
    proposal_by_hash = {item.proposal_hash: item for item in proposals}
    assessment_by_proposal = {item.proposal_hash: item for item in assessments}
    if len(proposal_by_hash) != len(proposals) or set(proposal_by_hash) != set(assessment_by_proposal):
        raise ValueError("every remediation proposal must have exactly one assessment")
    if any(item.snapshot_hash != snapshot.snapshot_hash for item in proposals) or any(item.snapshot_hash != snapshot.snapshot_hash for item in assessments):
        raise ValueError("remediation selection snapshot mismatch")
    if selected_proposal_hash not in proposal_by_hash:
        raise ValueError("selected remediation proposal is not in candidate set")
    selected = proposal_by_hash[selected_proposal_hash]
    assessment = assessment_by_proposal[selected_proposal_hash]
    if assessment.status == "ROLLBACK_UNSUPPORTED":
        raise ValueError("cannot select unsupported rollback")
    if selector_ref == assessment.latest_evaluator_ref:
        raise ValueError("remediation selector must be independent from latest replication evaluator")
    proposal_hashes = tuple(sorted(proposal_by_hash))
    assessment_hashes = tuple(sorted(item.assessment_hash for item in assessments))
    fields = {
        "selection_ref": selection_ref,
        "snapshot_hash": snapshot.snapshot_hash,
        "proposal_hashes": proposal_hashes,
        "assessment_hashes": assessment_hashes,
        "selected_proposal_hash": selected.proposal_hash,
        "selected_assessment_hash": assessment.assessment_hash,
        "selected_action": selected.action,
        "selected_status": assessment.status,
        "selected_proposer_ref": selected.proposer_ref,
        "selected_assessor_ref": assessment.assessor_ref,
        "selector_ref": selector_ref,
        "selected_at": selected_at,
    }
    provisional = RemediationSelectionReceipt(**fields, selection_hash="0" * 64)
    result = RemediationSelectionReceipt(**fields, selection_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class RemediationReviewReceipt:
    selection_hash: str
    snapshot_hash: str
    selected_proposal_hash: str
    selected_assessment_hash: str
    selected_action: RemediationAction
    decision: RemediationReviewDecision
    rationale_ref: str
    proposer_ref: str
    assessor_ref: str
    selector_ref: str
    reviewer_ref: str
    reviewed_at: int
    review_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/remediation-review/v1.19",
            "selection_hash": self.selection_hash,
            "snapshot_hash": self.snapshot_hash,
            "selected_proposal_hash": self.selected_proposal_hash,
            "selected_assessment_hash": self.selected_assessment_hash,
            "selected_action": self.selected_action,
            "decision": self.decision,
            "rationale_ref": self.rationale_ref,
            "proposer_ref": self.proposer_ref,
            "assessor_ref": self.assessor_ref,
            "selector_ref": self.selector_ref,
            "reviewer_ref": self.reviewer_ref,
            "reviewed_at": self.reviewed_at,
        }

    def validate(self) -> None:
        for name, value in (("selection_hash", self.selection_hash), ("snapshot_hash", self.snapshot_hash), ("selected_proposal_hash", self.selected_proposal_hash), ("selected_assessment_hash", self.selected_assessment_hash), ("review_hash", self.review_hash)):
            _require_digest(name, value)
        if self.decision not in {"APPROVE", "HOLD", "REJECT"} or not self.rationale_ref or not self.reviewer_ref:
            raise ValueError("invalid remediation review")
        if self.reviewer_ref in {self.proposer_ref, self.assessor_ref, self.selector_ref}:
            raise ValueError("remediation reviewer must be independent from proposer, assessor, and selector")
        if self.reviewed_at < 0 or self.review_hash != _digest(self.material()):
            raise ValueError("invalid remediation review material")


def review_remediation_selection(
    *,
    selection: RemediationSelectionReceipt,
    decision: RemediationReviewDecision,
    rationale_ref: str,
    reviewer_ref: str,
    reviewed_at: int,
) -> RemediationReviewReceipt:
    selection.validate()
    fields = {
        "selection_hash": selection.selection_hash,
        "snapshot_hash": selection.snapshot_hash,
        "selected_proposal_hash": selection.selected_proposal_hash,
        "selected_assessment_hash": selection.selected_assessment_hash,
        "selected_action": selection.selected_action,
        "decision": decision,
        "rationale_ref": rationale_ref,
        "proposer_ref": selection.selected_proposer_ref,
        "assessor_ref": selection.selected_assessor_ref,
        "selector_ref": selection.selector_ref,
        "reviewer_ref": reviewer_ref,
        "reviewed_at": reviewed_at,
    }
    provisional = RemediationReviewReceipt(**fields, review_hash="0" * 64)
    result = RemediationReviewReceipt(**fields, review_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class RemediationExecutionReceipt:
    selection_hash: str
    review_hash: str
    proposal_hash: str
    assessment_hash: str
    snapshot_hash: str
    target_hash: str
    confirmed_revision_hash: str
    action: RemediationAction
    execution_kind: RemediationExecutionKind
    downstream_protocol: str | None
    old_graph_hash: str
    old_generation: int
    new_graph_hash: str
    new_generation: int
    former_confirmed_graph_hash: str
    rollback_source_graph_hash: str
    applier_ref: str
    applied_at: int
    execution_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/remediation-execution/v1.19",
            "selection_hash": self.selection_hash,
            "review_hash": self.review_hash,
            "proposal_hash": self.proposal_hash,
            "assessment_hash": self.assessment_hash,
            "snapshot_hash": self.snapshot_hash,
            "target_hash": self.target_hash,
            "confirmed_revision_hash": self.confirmed_revision_hash,
            "action": self.action,
            "execution_kind": self.execution_kind,
            "downstream_protocol": self.downstream_protocol,
            "old_graph_hash": self.old_graph_hash,
            "old_generation": self.old_generation,
            "new_graph_hash": self.new_graph_hash,
            "new_generation": self.new_generation,
            "former_confirmed_graph_hash": self.former_confirmed_graph_hash,
            "rollback_source_graph_hash": self.rollback_source_graph_hash,
            "applier_ref": self.applier_ref,
            "applied_at": self.applied_at,
        }

    def validate(self) -> None:
        for name, value in (("selection_hash", self.selection_hash), ("review_hash", self.review_hash), ("proposal_hash", self.proposal_hash), ("assessment_hash", self.assessment_hash), ("snapshot_hash", self.snapshot_hash), ("target_hash", self.target_hash), ("confirmed_revision_hash", self.confirmed_revision_hash), ("old_graph_hash", self.old_graph_hash), ("new_graph_hash", self.new_graph_hash), ("former_confirmed_graph_hash", self.former_confirmed_graph_hash), ("rollback_source_graph_hash", self.rollback_source_graph_hash), ("execution_hash", self.execution_hash)):
            _require_digest(name, value)
        if self.execution_kind == "FORWARD_ROLLBACK":
            if self.action != "SAFE_ROLLBACK" or self.new_generation != self.old_generation + 1 or self.new_graph_hash == self.old_graph_hash:
                raise ValueError("invalid forward rollback execution")
        else:
            if self.new_generation != self.old_generation or self.new_graph_hash != self.old_graph_hash:
                raise ValueError("non-mutating remediation cannot change graph")
            expected = "DOWNSTREAM_GOVERNANCE_REQUIRED" if self.action in {"PARAMETER_REVISION", "STRUCTURAL_REVISION"} else "NO_GRAPH_CHANGE"
            if self.execution_kind != expected:
                raise ValueError("remediation execution kind/action mismatch")
        if self.downstream_protocol != _route_for(self.action):
            raise ValueError("remediation execution downstream protocol mismatch")
        if not self.applier_ref or self.applied_at < 0 or self.execution_hash != _digest(self.material()):
            raise ValueError("invalid remediation execution material")


def execute_remediation(
    *,
    target: ReplicationTargetReceipt,
    snapshot: ReplicationSeriesSnapshot,
    current_graph: DependencyGraphState,
    rollback_graph: DependencyGraphState,
    proposal: DriftRemediationProposal,
    assessment: RemediationAssessmentReceipt,
    selection: RemediationSelectionReceipt,
    review: RemediationReviewReceipt,
    applier_ref: str,
    applied_at: int,
) -> tuple[DependencyGraphState, RemediationExecutionReceipt]:
    target.validate(); snapshot.validate(); current_graph.validate(); rollback_graph.validate(); proposal.validate(); assessment.validate(); selection.validate(); review.validate()
    if snapshot.signal != "PERSISTENT_DRIFT_SIGNAL" or proposal.snapshot_hash != snapshot.snapshot_hash or selection.snapshot_hash != snapshot.snapshot_hash or review.snapshot_hash != snapshot.snapshot_hash:
        raise ValueError("remediation chain is stale against current persistent-drift snapshot")
    if proposal.target_hash != target.target_hash or proposal.current_graph_hash != current_graph.graph_hash or current_graph.graph_hash != target.confirmed_graph_hash:
        raise ValueError("remediation current graph/target binding mismatch")
    if proposal.rollback_graph_hash != rollback_graph.graph_hash or rollback_graph.generation + 1 != current_graph.generation:
        raise ValueError("remediation rollback graph binding mismatch")
    if selection.selected_proposal_hash != proposal.proposal_hash or selection.selected_assessment_hash != assessment.assessment_hash or assessment.proposal_hash != proposal.proposal_hash:
        raise ValueError("remediation selected proposal/assessment mismatch")
    if review.selection_hash != selection.selection_hash or review.decision != "APPROVE":
        raise ValueError("remediation apply requires independent APPROVE review")
    if applier_ref in {proposal.proposer_ref, assessment.assessor_ref, assessment.latest_evaluator_ref, selection.selector_ref, review.reviewer_ref}:
        raise ValueError("remediation applier must be independent from proposal, assessment, replication evaluation, selection, and review")
    if proposal.action == "SAFE_ROLLBACK" and assessment.status != "ROLLBACK_SUPPORTED":
        raise ValueError("safe rollback requires ROLLBACK_SUPPORTED assessment")
    if proposal.action == "SAFE_ROLLBACK":
        evidence_state_hash = _digest({
            "domain": "ATMAN-LATTICE/forward-rollback-evidence/v1.19",
            "target_hash": target.target_hash,
            "snapshot_hash": snapshot.snapshot_hash,
            "proposal_hash": proposal.proposal_hash,
            "assessment_hash": assessment.assessment_hash,
            "selection_hash": selection.selection_hash,
            "review_hash": review.review_hash,
            "former_confirmed_graph_hash": current_graph.graph_hash,
            "rollback_source_graph_hash": rollback_graph.graph_hash,
        })
        new_graph = make_dependency_graph(
            current_graph.graph_ref,
            subject_identity_ref=current_graph.subject_identity_ref,
            generation=current_graph.generation + 1,
            edges=rollback_graph.edges,
            evidence_state_hash=evidence_state_hash,
        )
        execution_kind: RemediationExecutionKind = "FORWARD_ROLLBACK"
    else:
        new_graph = current_graph
        execution_kind = "DOWNSTREAM_GOVERNANCE_REQUIRED" if proposal.action in {"PARAMETER_REVISION", "STRUCTURAL_REVISION"} else "NO_GRAPH_CHANGE"
    fields = {
        "selection_hash": selection.selection_hash,
        "review_hash": review.review_hash,
        "proposal_hash": proposal.proposal_hash,
        "assessment_hash": assessment.assessment_hash,
        "snapshot_hash": snapshot.snapshot_hash,
        "target_hash": target.target_hash,
        "confirmed_revision_hash": target.confirmed_revision_hash,
        "action": proposal.action,
        "execution_kind": execution_kind,
        "downstream_protocol": proposal.downstream_protocol,
        "old_graph_hash": current_graph.graph_hash,
        "old_generation": current_graph.generation,
        "new_graph_hash": new_graph.graph_hash,
        "new_generation": new_graph.generation,
        "former_confirmed_graph_hash": current_graph.graph_hash,
        "rollback_source_graph_hash": rollback_graph.graph_hash,
        "applier_ref": applier_ref,
        "applied_at": applied_at,
    }
    provisional = RemediationExecutionReceipt(**fields, execution_hash="0" * 64)
    receipt = RemediationExecutionReceipt(**fields, execution_hash=_digest(provisional.material()))
    receipt.validate()
    return new_graph, receipt
