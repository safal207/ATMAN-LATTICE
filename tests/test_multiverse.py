from dataclasses import replace

import pytest

from model.lattice import issue_genesis_receipt
from model.merge import merge_branches
from model.multiverse import (
    CompositeRealityReceipt,
    _digest,
    assess_incursion,
    bind_composite_reality,
    commit_potential,
    propose_branch,
    verify_branch_commit,
    verify_composite_reality,
)
from model.replay import restore_checkpoint


def source_receipt():
    return issue_genesis_receipt(
        identity_ref="agent:multiverse",
        state_ref="origin",
        branch_ref="main",
        generation=1,
        payload="origin",
    )


def fork_pair():
    source = source_receipt()
    left, left_restore = restore_checkpoint(
        source,
        target_branch_ref="left",
        target_generation=2,
        replayed_at=100,
    )
    right, right_restore = restore_checkpoint(
        source,
        target_branch_ref="right",
        target_generation=3,
        replayed_at=110,
    )
    return source, left, left_restore, right, right_restore


def merged_fixture():
    source, left, left_restore, right, right_restore = fork_pair()
    target, merge = merge_branches(
        source,
        (left,),
        left_restore,
        (right,),
        right_restore,
        target_branch_ref="composite",
        target_generation=4,
        merged_payload="composite-state",
        conflicts=(),
        resolutions=(),
        merged_at=200,
    )
    incursion = assess_incursion(
        left,
        right,
        verdict="INCOMPATIBLE",
        resolution_mode="MERGE",
        reason_ref="reason:shared-resource-conflict",
        evidence_ref="evidence:collision-1",
        assessed_at=190,
    )
    composite = bind_composite_reality(
        left,
        right,
        target,
        incursion,
        merge,
        created_at=201,
    )
    return left, right, target, incursion, merge, composite


def test_potentiality_is_not_history_until_explicit_commit():
    source = source_receipt()
    potential = propose_branch(
        source,
        potential_id="plan:B",
        proposed_branch_ref="future-b",
        proposed_generation=2,
        payload="candidate-state",
        created_at=10,
        rationale_ref="plan:search-result",
    )

    assert potential.source_receipt_hash == source.receipt_hash
    assert potential.proposed_branch_ref == "future-b"
    assert source.branch_ref == "main"
    assert source.generation == 1

    target, commit = commit_potential(
        source,
        potential,
        payload="candidate-state",
        committed_at=20,
    )
    valid, limitations = verify_branch_commit(source, potential, target, commit)
    assert valid is True
    assert limitations == ()
    assert target.branch_ref == "future-b"
    assert target.lineage_root_hash != source.lineage_root_hash


def test_commit_rejects_payload_that_differs_from_considered_future():
    source = source_receipt()
    potential = propose_branch(
        source,
        potential_id="plan:A",
        proposed_branch_ref="future-a",
        proposed_generation=2,
        payload="safe-plan",
        created_at=10,
        rationale_ref="plan:safe",
    )
    with pytest.raises(ValueError, match="commit payload differs"):
        commit_potential(source, potential, payload="different-plan", committed_at=20)


def test_one_commit_cannot_be_relabelled_as_another_potential():
    source = source_receipt()
    a = propose_branch(
        source,
        potential_id="plan:A",
        proposed_branch_ref="future-a",
        proposed_generation=2,
        payload="same-payload",
        created_at=10,
        rationale_ref="plan:a",
    )
    b = propose_branch(
        source,
        potential_id="plan:B",
        proposed_branch_ref="future-b",
        proposed_generation=2,
        payload="same-payload",
        created_at=10,
        rationale_ref="plan:b",
    )
    target, commit = commit_potential(source, a, payload="same-payload", committed_at=20)
    valid, limitations = verify_branch_commit(source, b, target, commit)
    assert valid is False
    assert "potential_hash_mismatch" in limitations
    assert "target_branch_mismatch" in limitations


def test_two_valid_futures_can_be_explicitly_incompatible():
    _, left, _, right, _ = fork_pair()
    incursion = assess_incursion(
        left,
        right,
        verdict="INCOMPATIBLE",
        resolution_mode="ISOLATE",
        reason_ref="reason:exclusive-tool-state",
        evidence_ref="evidence:tool-lock",
        assessed_at=150,
    )
    assert incursion.verdict == "INCOMPATIBLE"
    assert incursion.resolution_mode == "ISOLATE"
    assert left.identity_ref == right.identity_ref
    assert left.lineage_root_hash != right.lineage_root_hash


def test_incompatible_worlds_cannot_silently_choose_no_resolution():
    _, left, _, right, _ = fork_pair()
    with pytest.raises(ValueError, match="explicit resolution mode"):
        assess_incursion(
            left,
            right,
            verdict="INCOMPATIBLE",
            resolution_mode="NONE",
            reason_ref="reason:collision",
            evidence_ref="evidence:collision",
            assessed_at=150,
        )


def test_coexisting_worlds_do_not_invent_a_resolution_event():
    _, left, _, right, _ = fork_pair()
    with pytest.raises(ValueError, match="NONE resolution mode"):
        assess_incursion(
            left,
            right,
            verdict="COEXIST",
            resolution_mode="MERGE",
            reason_ref="reason:no-conflict",
            evidence_ref="evidence:compatible",
            assessed_at=150,
        )


def test_composite_reality_preserves_both_parent_histories():
    left, right, target, incursion, merge, composite = merged_fixture()
    valid, limitations = verify_composite_reality(
        left,
        right,
        target,
        incursion,
        merge,
        composite,
    )
    assert valid is True
    assert limitations == ()
    assert composite.left_head_receipt_hash == left.receipt_hash
    assert composite.right_head_receipt_hash == right.receipt_hash
    assert composite.target_lineage_root_hash not in {
        left.lineage_root_hash,
        right.lineage_root_hash,
    }


def test_anti_doom_narrative_rewrite_is_detected_even_if_receipt_is_rehashed():
    left, right, target, incursion, merge, composite = merged_fixture()
    forged_fields = {
        **composite.material(),
        "left_head_receipt_hash": right.receipt_hash,
    }
    forged_fields.pop("domain")
    forged = CompositeRealityReceipt(
        **forged_fields,
        narrative_hash=_digest({"domain": "ATMAN-LATTICE/composite-reality/v1.3", **forged_fields}),
    )
    forged.validate()

    valid, limitations = verify_composite_reality(
        left,
        right,
        target,
        incursion,
        merge,
        forged,
    )
    assert valid is False
    assert "left_parent_erased_or_changed" in limitations
