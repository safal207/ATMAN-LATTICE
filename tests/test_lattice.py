from model.lattice import (
    IdentityReceipt,
    cross_axis_bind,
    global_coherence,
    observe_space,
    observe_time,
)


def receipt(state: str, *, identity: str = "person:1", branch: str = "main", generation: int = 7):
    return IdentityReceipt(
        identity_ref=identity,
        state_ref=state,
        branch_ref=branch,
        generation=generation,
        provenance_refs=(f"evidence:{state}",),
    )


def test_same_lineage_passes_all_layers():
    a1 = observe_space(receipt("waking"), receipt("dream"))
    a2 = observe_time(receipt("past"), receipt("future"))
    a3 = cross_axis_bind(a1, a2)
    a4 = global_coherence((a1, a2, a3))

    assert a1.verdict == "PASS"
    assert a2.verdict == "PASS"
    assert a3.verdict == "PASS"
    assert a4.verdict == "PASS"


def test_local_passes_can_fail_cross_axis_on_branch_collision():
    a1 = observe_space(receipt("waking", branch="alpha"), receipt("dream", branch="alpha"))
    a2 = observe_time(receipt("past", branch="beta"), receipt("future", branch="beta"))

    assert a1.verdict == "PASS"
    assert a2.verdict == "PASS"

    a3 = cross_axis_bind(a1, a2)
    assert a3.verdict == "FAIL"
    assert "branch_mismatch" in a3.limitations


def test_local_passes_can_fail_cross_axis_on_generation_collision():
    a1 = observe_space(receipt("waking", generation=7), receipt("dream", generation=7))
    a2 = observe_time(receipt("past", generation=8), receipt("future", generation=8))

    assert a1.verdict == "PASS"
    assert a2.verdict == "PASS"

    a3 = cross_axis_bind(a1, a2)
    assert a3.verdict == "FAIL"
    assert "generation_mismatch" in a3.limitations


def test_global_coherence_rejects_mixed_observer_sets():
    a1 = observe_space(receipt("waking", branch="alpha"), receipt("dream", branch="alpha"))
    a2 = observe_time(receipt("past", branch="beta"), receipt("future", branch="beta"))
    a3 = cross_axis_bind(a1, a2)
    a4 = global_coherence((a1, a2, a3))

    assert a4.verdict == "FAIL"
    assert "observer_set_contains_fail" in a4.limitations
    assert "branch_mismatch" in a4.limitations


def test_axis_observer_rejects_identity_mismatch():
    a1 = observe_space(receipt("waking", identity="person:1"), receipt("dream", identity="person:2"))
    assert a1.verdict == "FAIL"
    assert "lineage_mismatch" in a1.limitations
