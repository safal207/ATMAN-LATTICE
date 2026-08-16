from __future__ import annotations

from model.geometric_coherence import (
    CurvatureEvidence,
    TorsionEvidence,
    a3_geometric_gate,
    a4_geometric_coherence,
    make_geometric_policy,
)
from model.lattice import (
    cross_axis_bind,
    global_coherence,
    issue_genesis_receipt,
    issue_successor_receipt,
    observe_space,
    observe_time,
)
from model.transition_geometry import (
    make_transition_endpoint,
    make_transition_operator,
    measure_loop_curvature,
    measure_transition_torsion,
)


def base_observers(identity_ref: str = "agent:gate"):
    genesis = issue_genesis_receipt(
        identity_ref=identity_ref,
        state_ref="origin",
        branch_ref="main",
        generation=1,
        payload="origin",
    )
    s1 = issue_successor_receipt(genesis, state_ref="s1", payload="one")
    s2 = issue_successor_receipt(s1, state_ref="s2", payload="two")
    s4 = issue_successor_receipt(s2, state_ref="s4", payload="four")
    s5 = issue_successor_receipt(s4, state_ref="s5", payload="five")
    a1 = observe_space(s1, s2)
    a2 = observe_time(s4, s5)
    a3 = cross_axis_bind(a1, a2)
    a4 = global_coherence((a1, a2, a3))
    assert a3.verdict == "PASS"
    assert a4.verdict == "PASS"
    return a3, a4


def endpoint(branch: str, payload: str, *, identity_ref="agent:gate", generation=2, context="ctx"):
    receipt = issue_genesis_receipt(
        identity_ref=identity_ref,
        state_ref=f"state:{branch}",
        branch_ref=branch,
        generation=generation,
        payload=payload,
    )
    return make_transition_endpoint(
        receipt,
        context=context,
        authority="authority:v1",
        effects="effects:v1",
    )


def operators():
    return (
        make_transition_operator("A", {"op": "read"}),
        make_transition_operator("B", {"op": "plan"}),
    )


def torsion_evidence(path_ab, path_ba):
    origin = endpoint("origin", "origin", identity_ref=path_ab.identity_ref, generation=0)
    a, b = operators()
    receipt = measure_transition_torsion(origin, a, b, path_ab, path_ba, measured_at=100)
    return TorsionEvidence(receipt, origin, a, b, path_ab, path_ba)


def curvature_evidence(origin, returned):
    a, b = operators()
    receipt = measure_loop_curvature(origin, returned, (a, b), measured_at=200)
    return CurvatureEvidence(receipt, origin, returned, (a, b))


def test_a3_accepts_exactly_closed_transition_geometry():
    a3, _ = base_observers()
    result = endpoint("shared", "same")
    gate = a3_geometric_gate(a3, torsion=torsion_evidence(result, result))
    assert gate.decision == "PASS"
    assert gate.torsion_status == "CLOSED"
    assert gate.reasons == ()


def test_a3_preserves_history_only_torsion_without_calling_it_failure():
    a3, _ = base_observers()
    left = endpoint("ab", "same")
    right = endpoint("ba", "same")
    gate = a3_geometric_gate(a3, torsion=torsion_evidence(left, right))
    assert gate.decision == "PASS"
    assert gate.torsion_status == "SEMANTICALLY_CLOSED_HISTORY_DIVERGENT"
    assert "history_torsion_preserved" in gate.reasons


def test_a3_holds_semantic_torsion_by_default():
    a3, _ = base_observers()
    left = endpoint("ab", "left-result")
    right = endpoint("ba", "right-result")
    gate = a3_geometric_gate(a3, torsion=torsion_evidence(left, right))
    assert gate.decision == "HOLD"
    assert gate.torsion_status == "TORSION_DETECTED"
    assert "semantic_torsion_detected" in gate.reasons


def test_policy_can_escalate_semantic_torsion_to_fail():
    a3, _ = base_observers()
    left = endpoint("ab", "left-result")
    right = endpoint("ba", "right-result")
    policy = make_geometric_policy("strict", semantic_torsion_decision="FAIL")
    gate = a3_geometric_gate(a3, torsion=torsion_evidence(left, right), policy=policy)
    assert gate.decision == "FAIL"


def test_a3_rejects_self_consistent_torsion_receipt_for_another_path():
    a3, _ = base_observers()
    origin = endpoint("origin", "origin", generation=0)
    actual_ab = endpoint("actual-ab", "actual-ab")
    actual_ba = endpoint("actual-ba", "actual-ba")
    other_ab = endpoint("other-ab", "other-ab")
    a, b = operators()
    receipt = measure_transition_torsion(origin, a, b, other_ab, actual_ba, measured_at=101)
    forged_binding = TorsionEvidence(receipt, origin, a, b, actual_ab, actual_ba)
    gate = a3_geometric_gate(a3, torsion=forged_binding)
    assert gate.decision == "FAIL"
    assert "torsion_evidence:path_ab_binding_mismatch" in gate.reasons


def test_a3_rejects_geometry_from_another_identity():
    a3, _ = base_observers()
    other = endpoint("other", "same", identity_ref="agent:other")
    evidence = torsion_evidence(other, other)
    gate = a3_geometric_gate(a3, torsion=evidence)
    assert gate.decision == "FAIL"
    assert "torsion_identity_mismatch" in gate.reasons


def test_a3_accepts_semantic_loop_closure_with_preserved_holonomy():
    a3, _ = base_observers()
    origin = endpoint("origin-loop", "same", generation=0)
    returned = endpoint("return-loop", "same", generation=1)
    gate = a3_geometric_gate(a3, curvature=curvature_evidence(origin, returned))
    assert gate.decision == "PASS"
    assert gate.curvature_status == "SEMANTICALLY_CLOSED_WITH_HOLONOMY"
    assert "history_holonomy_preserved" in gate.reasons


def test_a3_holds_semantic_curvature_by_default():
    a3, _ = base_observers()
    origin = endpoint("origin-loop", "same", generation=0, context={"policy": 1})
    returned = endpoint("return-loop", "same", generation=1, context={"policy": 2})
    gate = a3_geometric_gate(a3, curvature=curvature_evidence(origin, returned))
    assert gate.decision == "HOLD"
    assert gate.curvature_status == "CURVATURE_DETECTED"


def test_a4_propagates_geometric_hold_instead_of_collapsing_to_fail():
    a3, a4 = base_observers()
    left = endpoint("ab", "left-result")
    right = endpoint("ba", "right-result")
    a3_gate = a3_geometric_gate(a3, torsion=torsion_evidence(left, right))
    a4_gate = a4_geometric_coherence(a4, (a3_gate,))
    assert a3_gate.decision == "HOLD"
    assert a4_gate.decision == "HOLD"
    assert "semantic_torsion_detected" in a4_gate.reasons


def test_a4_rejects_geometry_evaluated_under_another_policy():
    a3, a4 = base_observers()
    result = endpoint("shared", "same")
    strict = make_geometric_policy("strict", semantic_torsion_decision="FAIL")
    gate = a3_geometric_gate(a3, torsion=torsion_evidence(result, result), policy=strict)
    a4_gate = a4_geometric_coherence(a4, (gate,))
    assert a4_gate.decision == "FAIL"
    assert "geometric_policy_mismatch" in a4_gate.reasons


def test_a4_rejects_geometric_receipt_for_another_identity():
    other_a3, _ = base_observers("agent:other")
    _, a4 = base_observers()
    result = endpoint("shared", "same", identity_ref="agent:other")
    gate = a3_geometric_gate(other_a3, torsion=torsion_evidence(result, result))
    a4_gate = a4_geometric_coherence(a4, (gate,))
    assert a4_gate.decision == "FAIL"
    assert "geometric_identity_mismatch" in a4_gate.reasons
