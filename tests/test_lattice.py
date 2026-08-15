from dataclasses import replace

from model.lattice import (
    cross_axis_bind,
    global_coherence,
    issue_genesis_receipt,
    issue_successor_receipt,
    observe_space,
    observe_time,
    verify_lineage_chain,
)


def lineage(
    *,
    identity="person:1",
    branch="main",
    generation=7,
    genesis_state="origin",
    genesis_payload="origin",
):
    root = issue_genesis_receipt(
        identity_ref=identity,
        state_ref=genesis_state,
        branch_ref=branch,
        generation=generation,
        payload=genesis_payload,
        provenance_refs=("evidence:origin",),
    )
    waking = issue_successor_receipt(root, state_ref="waking", payload="awake")
    dream = issue_successor_receipt(waking, state_ref="dream", payload="dream")
    past = issue_successor_receipt(dream, state_ref="past", payload="past")
    future = issue_successor_receipt(past, state_ref="future", payload="future")
    return root, waking, dream, past, future


def test_valid_hash_chain_and_observers_pass():
    chain = lineage()
    valid, limitations = verify_lineage_chain(chain)
    assert valid is True
    assert limitations == ()

    _, waking, dream, past, future = chain
    a1 = observe_space(waking, dream)
    a2 = observe_time(past, future)
    a3 = cross_axis_bind(a1, a2)
    a4 = global_coherence((a1, a2, a3))

    assert [a1.verdict, a2.verdict, a3.verdict, a4.verdict] == ["PASS"] * 4


def test_receipt_tamper_is_detected():
    root, waking, *_ = lineage()
    tampered = replace(waking, state_ref="waking-tampered")
    valid, limitations = verify_lineage_chain((root, tampered))
    assert valid is False
    assert "invalid_receipt:1" in limitations


def test_parent_splice_is_detected():
    alpha = lineage(branch="alpha")
    beta = lineage(branch="beta")
    spliced = replace(alpha[2], parent_receipt_hash=beta[1].receipt_hash)
    valid, limitations = verify_lineage_chain((alpha[0], alpha[1], spliced))
    assert valid is False
    assert "invalid_receipt:2" in limitations


def test_local_passes_fail_cross_axis_for_distinct_crypto_roots():
    alpha = lineage(genesis_payload="root-alpha")
    beta = lineage(genesis_payload="root-beta")

    a1 = observe_space(alpha[1], alpha[2])
    a2 = observe_time(beta[3], beta[4])

    assert a1.verdict == "PASS"
    assert a2.verdict == "PASS"
    assert a1.subject_identity_ref == a2.subject_identity_ref
    assert a1.branch_ref == a2.branch_ref
    assert a1.generation == a2.generation

    a3 = cross_axis_bind(a1, a2)
    a4 = global_coherence((a1, a2, a3))

    assert a3.verdict == "FAIL"
    assert "lineage_root_mismatch" in a3.limitations
    assert a4.verdict == "FAIL"
    assert "lineage_root_mismatch" in a4.limitations


def test_local_passes_can_fail_cross_axis_on_branch_collision():
    alpha = lineage(branch="alpha")
    beta = lineage(branch="beta")
    a1 = observe_space(alpha[1], alpha[2])
    a2 = observe_time(beta[3], beta[4])
    assert a1.verdict == "PASS"
    assert a2.verdict == "PASS"
    a3 = cross_axis_bind(a1, a2)
    assert a3.verdict == "FAIL"
    assert "branch_mismatch" in a3.limitations


def test_local_passes_can_fail_cross_axis_on_generation_collision():
    g7 = lineage(generation=7)
    g8 = lineage(generation=8)
    a1 = observe_space(g7[1], g7[2])
    a2 = observe_time(g8[3], g8[4])
    assert a1.verdict == "PASS"
    assert a2.verdict == "PASS"
    a3 = cross_axis_bind(a1, a2)
    assert a3.verdict == "FAIL"
    assert "generation_mismatch" in a3.limitations


def test_global_coherence_rejects_mixed_observer_sets():
    alpha = lineage(branch="alpha")
    beta = lineage(branch="beta")
    a1 = observe_space(alpha[1], alpha[2])
    a2 = observe_time(beta[3], beta[4])
    a3 = cross_axis_bind(a1, a2)
    a4 = global_coherence((a1, a2, a3))
    assert a4.verdict == "FAIL"
    assert "observer_set_contains_fail" in a4.limitations
    assert "branch_mismatch" in a4.limitations


def test_axis_observer_rejects_identity_mismatch():
    left = lineage(identity="person:1")
    right = lineage(identity="person:2")
    a1 = observe_space(left[1], right[2])
    assert a1.verdict == "FAIL"
    assert "identity_mismatch" in a1.limitations
