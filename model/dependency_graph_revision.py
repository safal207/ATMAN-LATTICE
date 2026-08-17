from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from model.calibration import DependencyCalibrationSnapshot, DependencyPairSample, binary_brier_score_ppm

GraphDirection = Literal["LEFT_TO_RIGHT", "RIGHT_TO_LEFT"]
GraphChangeKind = Literal["ADD_CONDITIONAL_EDGE", "REMOVE_CONDITIONAL_EDGE"]
GraphReplayStatus = Literal["INSUFFICIENT_REPLAY", "STRUCTURE_IMPROVED", "NO_STRUCTURE_IMPROVEMENT"]
GraphReviewDecision = Literal["APPROVE", "HOLD", "REJECT"]


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _round_ratio(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be > 0")
    return (numerator + denominator // 2) // denominator


@dataclass(frozen=True)
class DependencyGraphEdge:
    parent_model_ref: str
    child_model_ref: str
    relation: str
    edge_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/dependency-graph-edge/v1.14",
            "parent_model_ref": self.parent_model_ref,
            "child_model_ref": self.child_model_ref,
            "relation": self.relation,
        }

    def validate(self) -> None:
        if not self.parent_model_ref or not self.child_model_ref or self.parent_model_ref == self.child_model_ref:
            raise ValueError("dependency graph edge requires distinct model refs")
        if self.relation != "STATISTICAL_CONDITIONING":
            raise ValueError("v1.14 graph edges represent STATISTICAL_CONDITIONING only")
        _require_digest("edge_hash", self.edge_hash)
        if self.edge_hash != _digest(self.material()):
            raise ValueError("edge_hash does not match dependency graph edge material")


def make_dependency_graph_edge(parent_model_ref: str, child_model_ref: str) -> DependencyGraphEdge:
    provisional = DependencyGraphEdge(parent_model_ref, child_model_ref, "STATISTICAL_CONDITIONING", "0" * 64)
    result = DependencyGraphEdge(parent_model_ref, child_model_ref, "STATISTICAL_CONDITIONING", _digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class DependencyGraphState:
    graph_ref: str
    subject_identity_ref: str
    generation: int
    edges: tuple[DependencyGraphEdge, ...]
    evidence_state_hash: str
    graph_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/dependency-graph-state/v1.14",
            "graph_ref": self.graph_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "generation": self.generation,
            "edges": [edge.edge_hash for edge in self.edges],
            "evidence_state_hash": self.evidence_state_hash,
        }

    def validate(self) -> None:
        if not self.graph_ref or not self.subject_identity_ref or self.generation < 0:
            raise ValueError("invalid dependency graph metadata")
        _require_digest("evidence_state_hash", self.evidence_state_hash)
        _require_digest("graph_hash", self.graph_hash)
        for edge in self.edges:
            edge.validate()
        keys = [(edge.parent_model_ref, edge.child_model_ref) for edge in self.edges]
        if keys != sorted(keys) or len(set(keys)) != len(keys):
            raise ValueError("dependency graph edges must be unique and canonically sorted")
        nodes = sorted({value for edge in self.edges for value in (edge.parent_model_ref, edge.child_model_ref)})
        indegree = {node: 0 for node in nodes}
        children = {node: [] for node in nodes}
        for edge in self.edges:
            indegree[edge.child_model_ref] += 1
            children[edge.parent_model_ref].append(edge.child_model_ref)
        queue = sorted(node for node, degree in indegree.items() if degree == 0)
        visited = 0
        while queue:
            node = queue.pop(0)
            visited += 1
            for child in sorted(children[node]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
                    queue.sort()
        if visited != len(nodes):
            raise ValueError("dependency graph must remain acyclic")
        if self.graph_hash != _digest(self.material()):
            raise ValueError("graph_hash does not match dependency graph material")


def make_dependency_graph(
    graph_ref: str,
    *,
    subject_identity_ref: str,
    generation: int,
    edges: tuple[DependencyGraphEdge, ...] = (),
    evidence_state_hash: str,
) -> DependencyGraphState:
    canonical = tuple(sorted(edges, key=lambda edge: (edge.parent_model_ref, edge.child_model_ref)))
    fields = {
        "graph_ref": graph_ref,
        "subject_identity_ref": subject_identity_ref,
        "generation": generation,
        "edges": canonical,
        "evidence_state_hash": evidence_state_hash,
    }
    provisional = DependencyGraphState(**fields, graph_hash="0" * 64)
    result = DependencyGraphState(**fields, graph_hash=_digest(provisional.material()))
    result.validate()
    return result


def _pair_refs(samples: tuple[DependencyPairSample, ...]) -> tuple[str, str, str]:
    if not samples:
        raise ValueError("structural revision requires dependency pair samples")
    for sample in samples:
        sample.validate()
    pair_key = samples[0].pair_key
    left_ref = samples[0].left_model_ref
    right_ref = samples[0].right_model_ref
    if any(sample.pair_key != pair_key or sample.left_model_ref != left_ref or sample.right_model_ref != right_ref for sample in samples):
        raise ValueError("structural revision samples must share one oriented pair")
    return pair_key, left_ref, right_ref


def _edge_present(graph: DependencyGraphState, parent: str, child: str) -> bool:
    return any(edge.parent_model_ref == parent and edge.child_model_ref == child for edge in graph.edges)


@dataclass(frozen=True)
class StructuralGraphRevisionProposal:
    proposal_ref: str
    subject_identity_ref: str
    pair_key: str
    calibration_snapshot_hash: str
    base_graph_hash: str
    base_generation: int
    proposed_generation: int
    direction: GraphDirection
    change_kind: GraphChangeKind
    parent_model_ref: str
    child_model_ref: str
    proposed_edges: tuple[DependencyGraphEdge, ...]
    reason_ref: str
    proposer_ref: str
    proposed_at: int
    proposal_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/structural-graph-revision-proposal/v1.14",
            "proposal_ref": self.proposal_ref,
            "subject_identity_ref": self.subject_identity_ref,
            "pair_key": self.pair_key,
            "calibration_snapshot_hash": self.calibration_snapshot_hash,
            "base_graph_hash": self.base_graph_hash,
            "base_generation": self.base_generation,
            "proposed_generation": self.proposed_generation,
            "direction": self.direction,
            "change_kind": self.change_kind,
            "parent_model_ref": self.parent_model_ref,
            "child_model_ref": self.child_model_ref,
            "proposed_edges": [edge.edge_hash for edge in self.proposed_edges],
            "reason_ref": self.reason_ref,
            "proposer_ref": self.proposer_ref,
            "proposed_at": self.proposed_at,
        }

    def validate(self) -> None:
        if not self.proposal_ref or not self.subject_identity_ref or not self.parent_model_ref or not self.child_model_ref or not self.reason_ref or not self.proposer_ref:
            raise ValueError("structural graph proposal refs are required")
        for name, value in (("pair_key", self.pair_key), ("calibration_snapshot_hash", self.calibration_snapshot_hash), ("base_graph_hash", self.base_graph_hash), ("proposal_hash", self.proposal_hash)):
            _require_digest(name, value)
        if self.direction not in {"LEFT_TO_RIGHT", "RIGHT_TO_LEFT"}:
            raise ValueError("invalid structural graph direction")
        if self.change_kind not in {"ADD_CONDITIONAL_EDGE", "REMOVE_CONDITIONAL_EDGE"}:
            raise ValueError("invalid structural graph change kind")
        if self.proposed_generation != self.base_generation + 1:
            raise ValueError("structural graph proposal must advance generation exactly once")
        if self.proposed_at < 0:
            raise ValueError("proposed_at must be >= 0")
        for edge in self.proposed_edges:
            edge.validate()
        keys = [(edge.parent_model_ref, edge.child_model_ref) for edge in self.proposed_edges]
        if keys != sorted(keys) or len(set(keys)) != len(keys):
            raise ValueError("proposed edges must be unique and sorted")
        if self.proposal_hash != _digest(self.material()):
            raise ValueError("proposal_hash does not match structural proposal material")


def make_structural_graph_revision_proposal(
    *,
    proposal_ref: str,
    base_graph: DependencyGraphState,
    calibration_snapshot: DependencyCalibrationSnapshot,
    samples: tuple[DependencyPairSample, ...],
    direction: GraphDirection,
    reason_ref: str,
    proposer_ref: str,
    proposed_at: int,
) -> StructuralGraphRevisionProposal:
    base_graph.validate()
    calibration_snapshot.validate()
    pair_key, left_ref, right_ref = _pair_refs(samples)
    if calibration_snapshot.pair_key != pair_key:
        raise ValueError("dependency calibration snapshot/pair mismatch")
    if direction == "LEFT_TO_RIGHT":
        parent, child = left_ref, right_ref
    elif direction == "RIGHT_TO_LEFT":
        parent, child = right_ref, left_ref
    else:
        raise ValueError("invalid structural graph direction")
    current_edges = list(base_graph.edges)
    if calibration_snapshot.assessment == "INDEPENDENCE_CHALLENGED":
        if _edge_present(base_graph, parent, child):
            raise ValueError("challenged independence edge is already present")
        change_kind: GraphChangeKind = "ADD_CONDITIONAL_EDGE"
        current_edges.append(make_dependency_graph_edge(parent, child))
    elif calibration_snapshot.assessment == "CONDITIONAL_DEPENDENCY_NOT_OBSERVED":
        if direction != "LEFT_TO_RIGHT":
            raise ValueError("conditional edge removal follows the declared left-to-right orientation")
        if not _edge_present(base_graph, parent, child):
            raise ValueError("conditional edge removal requires an existing edge")
        change_kind = "REMOVE_CONDITIONAL_EDGE"
        current_edges = [edge for edge in current_edges if not (edge.parent_model_ref == parent and edge.child_model_ref == child)]
    else:
        raise ValueError("structural revision requires a dependency calibration challenge")
    proposed_edges = tuple(sorted(current_edges, key=lambda edge: (edge.parent_model_ref, edge.child_model_ref)))
    # Validate the proposed graph before issuing a proposal; cycles are forbidden.
    make_dependency_graph(
        base_graph.graph_ref,
        subject_identity_ref=base_graph.subject_identity_ref,
        generation=base_graph.generation + 1,
        edges=proposed_edges,
        evidence_state_hash=base_graph.evidence_state_hash,
    )
    fields = {
        "proposal_ref": proposal_ref,
        "subject_identity_ref": base_graph.subject_identity_ref,
        "pair_key": pair_key,
        "calibration_snapshot_hash": calibration_snapshot.snapshot_hash,
        "base_graph_hash": base_graph.graph_hash,
        "base_generation": base_graph.generation,
        "proposed_generation": base_graph.generation + 1,
        "direction": direction,
        "change_kind": change_kind,
        "parent_model_ref": parent,
        "child_model_ref": child,
        "proposed_edges": proposed_edges,
        "reason_ref": reason_ref,
        "proposer_ref": proposer_ref,
        "proposed_at": proposed_at,
    }
    provisional = StructuralGraphRevisionProposal(**fields, proposal_hash="0" * 64)
    result = StructuralGraphRevisionProposal(**fields, proposal_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class StructuralReplayCase:
    sample_hash: str
    parent_positive: bool
    child_positive: bool
    base_predicted_positive_bps: int
    proposed_predicted_positive_bps: int
    base_brier_score_ppm: int
    proposed_brier_score_ppm: int
    case_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/structural-graph-replay-case/v1.14",
            "sample_hash": self.sample_hash,
            "parent_positive": self.parent_positive,
            "child_positive": self.child_positive,
            "base_predicted_positive_bps": self.base_predicted_positive_bps,
            "proposed_predicted_positive_bps": self.proposed_predicted_positive_bps,
            "base_brier_score_ppm": self.base_brier_score_ppm,
            "proposed_brier_score_ppm": self.proposed_brier_score_ppm,
        }

    def validate(self) -> None:
        _require_digest("sample_hash", self.sample_hash)
        _require_digest("case_hash", self.case_hash)
        for value in (self.base_predicted_positive_bps, self.proposed_predicted_positive_bps):
            if value < 0 or value > 10_000:
                raise ValueError("structural replay prediction must be 0..10000 basis points")
        for value in (self.base_brier_score_ppm, self.proposed_brier_score_ppm):
            if value < 0 or value > 1_000_000:
                raise ValueError("structural replay Brier score must be 0..1000000 ppm")
        if self.case_hash != _digest(self.material()):
            raise ValueError("case_hash does not match structural replay case")


def _prediction(others: tuple[tuple[bool, bool], ...], *, conditional: bool, parent_positive: bool) -> int | None:
    population = tuple(child for parent, child in others if (not conditional or parent == parent_positive))
    if not population:
        return None
    return _round_ratio(10_000 * sum(1 for value in population if value), len(population))


@dataclass(frozen=True)
class StructuralGraphReplayReceipt:
    proposal_hash: str
    sample_hashes: tuple[str, ...]
    case_hashes: tuple[str, ...]
    scored_case_count: int
    min_cases: int
    base_mean_brier_ppm: int | None
    proposed_mean_brier_ppm: int | None
    improvement_ppm: int | None
    status: GraphReplayStatus
    replayed_at: int
    replay_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/structural-graph-replay/v1.14",
            "proposal_hash": self.proposal_hash,
            "sample_hashes": list(self.sample_hashes),
            "case_hashes": list(self.case_hashes),
            "scored_case_count": self.scored_case_count,
            "min_cases": self.min_cases,
            "base_mean_brier_ppm": self.base_mean_brier_ppm,
            "proposed_mean_brier_ppm": self.proposed_mean_brier_ppm,
            "improvement_ppm": self.improvement_ppm,
            "status": self.status,
            "replayed_at": self.replayed_at,
        }

    def validate(self) -> None:
        _require_digest("proposal_hash", self.proposal_hash)
        _require_digest("replay_hash", self.replay_hash)
        for value in self.sample_hashes + self.case_hashes:
            _require_digest("replay_hash_component", value)
        if tuple(sorted(set(self.sample_hashes))) != self.sample_hashes or tuple(sorted(set(self.case_hashes))) != self.case_hashes:
            raise ValueError("structural replay hashes must be unique and sorted")
        if self.scored_case_count != len(self.case_hashes) or self.min_cases < 2 or self.replayed_at < 0:
            raise ValueError("invalid structural replay metadata")
        if self.status == "INSUFFICIENT_REPLAY":
            if self.scored_case_count >= self.min_cases:
                raise ValueError("insufficient replay status requires too few scored cases")
        else:
            if self.scored_case_count < self.min_cases or self.base_mean_brier_ppm is None or self.proposed_mean_brier_ppm is None or self.improvement_ppm is None:
                raise ValueError("complete structural replay requires scores")
            if self.improvement_ppm != self.base_mean_brier_ppm - self.proposed_mean_brier_ppm:
                raise ValueError("structural replay improvement mismatch")
            if self.status == "STRUCTURE_IMPROVED" and self.improvement_ppm <= 0:
                raise ValueError("STRUCTURE_IMPROVED requires positive improvement")
            if self.status == "NO_STRUCTURE_IMPROVEMENT" and self.improvement_ppm > 0:
                raise ValueError("NO_STRUCTURE_IMPROVEMENT cannot have positive improvement")
        if self.replay_hash != _digest(self.material()):
            raise ValueError("replay_hash does not match structural replay material")


def replay_structural_graph_revision(
    proposal: StructuralGraphRevisionProposal,
    base_graph: DependencyGraphState,
    samples: tuple[DependencyPairSample, ...],
    *,
    min_cases: int,
    replayed_at: int,
) -> tuple[tuple[StructuralReplayCase, ...], StructuralGraphReplayReceipt]:
    proposal.validate()
    base_graph.validate()
    if proposal.base_graph_hash != base_graph.graph_hash:
        raise ValueError("structural replay base graph mismatch")
    pair_key, left_ref, right_ref = _pair_refs(samples)
    if pair_key != proposal.pair_key:
        raise ValueError("structural replay pair mismatch")
    if min_cases < 2:
        raise ValueError("min_cases must be >= 2")
    if proposal.direction == "LEFT_TO_RIGHT":
        oriented = tuple((sample.left_positive, sample.right_positive, sample.sample_hash) for sample in samples)
        parent, child = left_ref, right_ref
    else:
        oriented = tuple((sample.right_positive, sample.left_positive, sample.sample_hash) for sample in samples)
        parent, child = right_ref, left_ref
    if parent != proposal.parent_model_ref or child != proposal.child_model_ref:
        raise ValueError("structural replay orientation mismatch")
    base_conditional = _edge_present(base_graph, parent, child)
    proposed_conditional = proposal.change_kind == "ADD_CONDITIONAL_EDGE" or (proposal.change_kind != "REMOVE_CONDITIONAL_EDGE" and base_conditional)
    cases: list[StructuralReplayCase] = []
    for index, (parent_positive, child_positive, sample_hash) in enumerate(oriented):
        others = tuple((p, c) for j, (p, c, _) in enumerate(oriented) if j != index)
        base_prediction = _prediction(others, conditional=base_conditional, parent_positive=parent_positive)
        proposed_prediction = _prediction(others, conditional=proposed_conditional, parent_positive=parent_positive)
        if base_prediction is None or proposed_prediction is None:
            continue
        fields = {
            "sample_hash": sample_hash,
            "parent_positive": parent_positive,
            "child_positive": child_positive,
            "base_predicted_positive_bps": base_prediction,
            "proposed_predicted_positive_bps": proposed_prediction,
            "base_brier_score_ppm": binary_brier_score_ppm(base_prediction, child_positive),
            "proposed_brier_score_ppm": binary_brier_score_ppm(proposed_prediction, child_positive),
        }
        provisional = StructuralReplayCase(**fields, case_hash="0" * 64)
        case = StructuralReplayCase(**fields, case_hash=_digest(provisional.material()))
        case.validate()
        cases.append(case)
    cases_tuple = tuple(sorted(cases, key=lambda item: item.case_hash))
    n = len(cases_tuple)
    if n < min_cases:
        base_mean = proposed_mean = improvement = None
        status: GraphReplayStatus = "INSUFFICIENT_REPLAY"
    else:
        base_mean = _round_ratio(sum(item.base_brier_score_ppm for item in cases_tuple), n)
        proposed_mean = _round_ratio(sum(item.proposed_brier_score_ppm for item in cases_tuple), n)
        improvement = base_mean - proposed_mean
        status = "STRUCTURE_IMPROVED" if improvement > 0 else "NO_STRUCTURE_IMPROVEMENT"
    fields = {
        "proposal_hash": proposal.proposal_hash,
        "sample_hashes": tuple(sorted(sample.sample_hash for sample in samples)),
        "case_hashes": tuple(item.case_hash for item in cases_tuple),
        "scored_case_count": n,
        "min_cases": min_cases,
        "base_mean_brier_ppm": base_mean,
        "proposed_mean_brier_ppm": proposed_mean,
        "improvement_ppm": improvement,
        "status": status,
        "replayed_at": replayed_at,
    }
    provisional = StructuralGraphReplayReceipt(**fields, replay_hash="0" * 64)
    receipt = StructuralGraphReplayReceipt(**fields, replay_hash=_digest(provisional.material()))
    receipt.validate()
    return cases_tuple, receipt


@dataclass(frozen=True)
class StructuralGraphReviewReceipt:
    proposal_hash: str
    replay_hash: str
    decision: GraphReviewDecision
    rationale_ref: str
    proposer_ref: str
    reviewer_ref: str
    reviewed_at: int
    review_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/structural-graph-review/v1.14",
            "proposal_hash": self.proposal_hash,
            "replay_hash": self.replay_hash,
            "decision": self.decision,
            "rationale_ref": self.rationale_ref,
            "proposer_ref": self.proposer_ref,
            "reviewer_ref": self.reviewer_ref,
            "reviewed_at": self.reviewed_at,
        }

    def validate(self) -> None:
        _require_digest("proposal_hash", self.proposal_hash)
        _require_digest("replay_hash", self.replay_hash)
        _require_digest("review_hash", self.review_hash)
        if self.decision not in {"APPROVE", "HOLD", "REJECT"} or not self.rationale_ref or not self.proposer_ref or not self.reviewer_ref:
            raise ValueError("invalid structural graph review")
        if self.proposer_ref == self.reviewer_ref:
            raise ValueError("structural graph reviewer must be independent from proposer")
        if self.reviewed_at < 0 or self.review_hash != _digest(self.material()):
            raise ValueError("invalid structural graph review material")


def review_structural_graph_revision(
    proposal: StructuralGraphRevisionProposal,
    replay: StructuralGraphReplayReceipt,
    *,
    decision: GraphReviewDecision,
    rationale_ref: str,
    reviewer_ref: str,
    reviewed_at: int,
) -> StructuralGraphReviewReceipt:
    proposal.validate()
    replay.validate()
    if replay.proposal_hash != proposal.proposal_hash:
        raise ValueError("structural review replay/proposal mismatch")
    if decision == "APPROVE" and replay.status != "STRUCTURE_IMPROVED":
        raise ValueError("structural graph approval requires improved replay")
    fields = {
        "proposal_hash": proposal.proposal_hash,
        "replay_hash": replay.replay_hash,
        "decision": decision,
        "rationale_ref": rationale_ref,
        "proposer_ref": proposal.proposer_ref,
        "reviewer_ref": reviewer_ref,
        "reviewed_at": reviewed_at,
    }
    provisional = StructuralGraphReviewReceipt(**fields, review_hash="0" * 64)
    result = StructuralGraphReviewReceipt(**fields, review_hash=_digest(provisional.material()))
    result.validate()
    return result


@dataclass(frozen=True)
class DependencyGraphRevisionReceipt:
    proposal_hash: str
    replay_hash: str
    review_hash: str
    base_graph_hash: str
    new_graph_hash: str
    base_generation: int
    new_generation: int
    applier_ref: str
    applied_at: int
    revision_hash: str

    def material(self) -> dict[str, object]:
        return {
            "domain": "ATMAN-LATTICE/dependency-graph-revision/v1.14",
            "proposal_hash": self.proposal_hash,
            "replay_hash": self.replay_hash,
            "review_hash": self.review_hash,
            "base_graph_hash": self.base_graph_hash,
            "new_graph_hash": self.new_graph_hash,
            "base_generation": self.base_generation,
            "new_generation": self.new_generation,
            "applier_ref": self.applier_ref,
            "applied_at": self.applied_at,
        }

    def validate(self) -> None:
        for name, value in (("proposal_hash", self.proposal_hash), ("replay_hash", self.replay_hash), ("review_hash", self.review_hash), ("base_graph_hash", self.base_graph_hash), ("new_graph_hash", self.new_graph_hash), ("revision_hash", self.revision_hash)):
            _require_digest(name, value)
        if self.new_generation != self.base_generation + 1 or not self.applier_ref or self.applied_at < 0:
            raise ValueError("invalid dependency graph revision metadata")
        if self.revision_hash != _digest(self.material()):
            raise ValueError("revision_hash does not match dependency graph revision material")


def apply_structural_graph_revision(
    *,
    current_graph: DependencyGraphState,
    proposal: StructuralGraphRevisionProposal,
    replay: StructuralGraphReplayReceipt,
    review: StructuralGraphReviewReceipt,
    applier_ref: str,
    applied_at: int,
) -> tuple[DependencyGraphState, DependencyGraphRevisionReceipt]:
    current_graph.validate()
    proposal.validate()
    replay.validate()
    review.validate()
    if current_graph.graph_hash != proposal.base_graph_hash or current_graph.generation != proposal.base_generation:
        raise ValueError("stale dependency graph base")
    if replay.proposal_hash != proposal.proposal_hash or review.proposal_hash != proposal.proposal_hash or review.replay_hash != replay.replay_hash:
        raise ValueError("dependency graph revision chain mismatch")
    if replay.status != "STRUCTURE_IMPROVED" or review.decision != "APPROVE":
        raise ValueError("dependency graph revision requires improved replay and APPROVE review")
    evidence_state_hash = _digest({
        "domain": "ATMAN-LATTICE/dependency-graph-revision-evidence/v1.14",
        "prior_evidence_state_hash": current_graph.evidence_state_hash,
        "proposal_hash": proposal.proposal_hash,
        "replay_hash": replay.replay_hash,
        "review_hash": review.review_hash,
    })
    new_graph = make_dependency_graph(
        current_graph.graph_ref,
        subject_identity_ref=current_graph.subject_identity_ref,
        generation=proposal.proposed_generation,
        edges=proposal.proposed_edges,
        evidence_state_hash=evidence_state_hash,
    )
    fields = {
        "proposal_hash": proposal.proposal_hash,
        "replay_hash": replay.replay_hash,
        "review_hash": review.review_hash,
        "base_graph_hash": current_graph.graph_hash,
        "new_graph_hash": new_graph.graph_hash,
        "base_generation": current_graph.generation,
        "new_generation": new_graph.generation,
        "applier_ref": applier_ref,
        "applied_at": applied_at,
    }
    provisional = DependencyGraphRevisionReceipt(**fields, revision_hash="0" * 64)
    receipt = DependencyGraphRevisionReceipt(**fields, revision_hash=_digest(provisional.material()))
    receipt.validate()
    return new_graph, receipt
