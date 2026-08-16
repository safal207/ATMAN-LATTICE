from __future__ import annotations

from model.lattice import issue_genesis_receipt
from model.transition_geometry import (
    make_transition_endpoint,
    make_transition_operator,
    measure_loop_curvature,
    measure_transition_torsion,
    verify_loop_curvature,
    verify_transition_torsion,
)


def receipt(branch: str, payload: str, generation: int = 1):
    return issue_genesis_receipt(
        identity_ref="agent:geometry",
        state_ref=f"state:{branch}",
        branch_ref=branch,
        generation=generation,
        payload=payload,
    )


def endpoint(
    branch: str,
    payload: str,
    *,
    generation: int = 1,
    context="context:v1",
    authority="authority:v1",
    effects="effects:v1",
):
    return make_transition_endpoint(
        receipt(branch, payload, generation),
        context=context,
        authority=authority,
        effects=effects,
    )


def operators():
    return (
        make_transition_operator("A", {"op": "read", "version": 1}),
        make_transition_operator("B", {"op": "plan", "version": 1}),
    )


def test_torsion_closed_when_order_produces_exact_same_endpoint():
    origin = endpoint("origin", "origin", generation=0)
    result = endpoint("shared", "same", generation=2)
    a, b = operators()

    torsion = measure_transition_torsion(origin, a, b, result, result, measured_at=100)

    assert torsion.status == "CLOSED"
    assert torsion.semantic_delta_dimensions == ()
    assert torsion.history_delta_dimensions == ()


def test_torsion_can_be_semantically_closed_but_history_divergent():
    origin = endpoint("origin", "origin", generation=0)
    path_ab = endpoint("path:ab", "same-result", generation=2)
    path_ba = endpoint("path:ba", "same-result", generation=2)
    a, b = operators()

    torsion = measure_transition_torsion(origin, a, b, path_ab, path_ba, measured_at=101)

    assert torsion.status == "SEMANTICALLY_CLOSED_HISTORY_DIVERGENT"
    assert torsion.semantic_delta_dimensions == ()
    assert "lineage_root_hash" in torsion.history_delta_dimensions
    assert "branch_ref" in torsion.history_delta_dimensions
    assert "receipt_hash" in torsion.history_delta_dimensions


def test_torsion_detects_semantic_order_dependence():
    origin = endpoint("origin", "origin", generation=0)
    path_ab = endpoint("path:ab", "result-ab", generation=2)
    path_ba = endpoint("path:ba", "result-ba", generation=2)
    a, b = operators()

    torsion = measure_transition_torsion(origin, a, b, path_ab, path_ba, measured_at=102)

    assert torsion.status == "TORSION_DETECTED"
    assert "payload_digest" in torsion.semantic_delta_dimensions


def test_torsion_verifier_rejects_valid_receipt_for_different_path():
    origin = endpoint("origin", "origin", generation=0)
    actual_ab = endpoint("actual:ab", "actual-ab", generation=2)
    actual_ba = endpoint("actual:ba", "actual-ba", generation=2)
    other_ab = endpoint("other:ab", "other-ab", generation=2)
    a, b = operators()

    receipt_for_other_path = measure_transition_torsion(
        origin,
        a,
        b,
        other_ab,
        actual_ba,
        measured_at=103,
    )
    valid, limitations = verify_transition_torsion(
        receipt_for_other_path,
        origin,
        a,
        b,
        actual_ab,
        actual_ba,
    )

    assert valid is False
    assert "path_ab_binding_mismatch" in limitations


def test_flat_loop_when_returned_endpoint_is_exactly_origin():
    origin = endpoint("origin", "origin", generation=0)
    a, b = operators()

    curvature = measure_loop_curvature(origin, origin, (a, b), measured_at=200)

    assert curvature.status == "FLAT_LOOP"
    assert curvature.semantic_drift_dimensions == ()
    assert curvature.history_holonomy_dimensions == ()


def test_loop_can_return_semantically_while_history_advances():
    origin = endpoint("origin", "same-state", generation=0)
    returned = endpoint("loop:return", "same-state", generation=1)
    a, b = operators()

    curvature = measure_loop_curvature(origin, returned, (a, b), measured_at=201)

    assert curvature.status == "SEMANTICALLY_CLOSED_WITH_HOLONOMY"
    assert curvature.semantic_drift_dimensions == ()
    assert "lineage_root_hash" in curvature.history_holonomy_dimensions
    assert "branch_ref" in curvature.history_holonomy_dimensions


def test_curvature_detects_closed_loop_semantic_drift():
    origin = endpoint("origin", "state", generation=0, context={"policy": 1})
    returned = endpoint("loop:return", "state", generation=1, context={"policy": 2})
    a, b = operators()

    curvature = measure_loop_curvature(origin, returned, (a, b), measured_at=202)

    assert curvature.status == "CURVATURE_DETECTED"
    assert "context_digest" in curvature.semantic_drift_dimensions


def test_curvature_verifier_binds_exact_loop_operator_order():
    origin = endpoint("origin", "same-state", generation=0)
    returned = endpoint("loop:return", "same-state", generation=1)
    a, b = operators()
    c = make_transition_operator("C", {"op": "write", "version": 1})

    curvature = measure_loop_curvature(origin, returned, (a, b), measured_at=203)
    valid, limitations = verify_loop_curvature(curvature, origin, returned, (a, c))

    assert valid is False
    assert "loop_operator_binding_mismatch" in limitations
