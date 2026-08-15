from dataclasses import replace

import pytest

from model.lattice import digest_payload, issue_genesis_receipt, issue_successor_receipt
from model.merge import (
    ConflictResolution,
    MergeConflict,
    merge_branches,
    verify_merge,
)
from model.replay import restore_checkpoint


def source_chain():
    root = issue_genesis_receipt(
        identity_ref="person:1",
        state_ref="origin",
        branch_ref="main",
        generation=7,
        payload="origin",
    )
    s1 = issue_successor_receipt(root, state_ref="s1", payload="s1")
    s2 = issue_successor_receipt(s1, state_ref="s2", payload="s2")
    return root, s1, s2


def fork_pair(ancestor):
    left_genesis, left_restore = restore_checkpoint(
        ancestor,
        target_branch_ref="future/left",
        target_generation=8,
        replayed_at=1000,
    )
    right_genesis, right_restore = restore_checkpoint(
        ancestor,
        target_branch_ref="future/right",
        target_generation=8,
        replayed_at=1001,
    )
    left_head = issue_successor_receipt(left_genesis, state_ref="left-head", payload="left-future")
    right_head = issue_successor_receipt(right_genesis, state_ref="right-head", payload="right-future")
    return (
        (left_genesis, left_head),
        left_restore,
        (right_genesis, right_head),
        right_restore,
    )


def conflict_bundle():
    conflict = MergeConflict(
        conflict_ref="policy:route",
        left_digest=digest_payload("route-left"),
        right_digest=digest_payload("route-right"),
    )
    resolution = ConflictResolution(
        conflict_ref=conflict.conflict_ref,
        left_digest=conflict.left_digest,
        right_digest=conflict.right_digest,
        strategy="SYNTHESIZED",
        result_digest=digest_payload("route-combined"),
        reason_ref="decision:merge-1",
    )
    return conflict, resolution


def test_merge_two_futures_creates_third_lineage():
    _, ancestor, _ = source_chain()
    left, left_restore, right, right_restore = fork_pair(ancestor)
    conflict, resolution = conflict_bundle()

    target, merge = merge_branches(
        ancestor,
        left,
        left_restore,
        right,
        right_restore,
        target_branch_ref="future/merged",
        target_generation=9,
        merged_payload="merged-state",
        conflicts=(conflict,),
        resolutions=(resolution,),
        merged_at=1100,
    )

    valid, limitations = verify_merge(
        ancestor,
        left,
        left_restore,
        right,
        right_restore,
        target,
        merge,
        conflicts=(conflict,),
        resolutions=(resolution,),
    )

    assert valid is True
    assert limitations == ()
    assert target.identity_ref == ancestor.identity_ref
    assert target.branch_ref not in {ancestor.branch_ref, left[-1].branch_ref, right[-1].branch_ref}
    assert target.generation > max(left[-1].generation, right[-1].generation)
    assert target.lineage_root_hash not in {left[-1].lineage_root_hash, right[-1].lineage_root_hash}


def test_merge_rejects_unresolved_conflict():
    _, ancestor, _ = source_chain()
    left, left_restore, right, right_restore = fork_pair(ancestor)
    conflict, _ = conflict_bundle()

    with pytest.raises(ValueError, match="resolution set does not exactly cover conflicts"):
        merge_branches(
            ancestor,
            left,
            left_restore,
            right,
            right_restore,
            target_branch_ref="future/merged",
            target_generation=9,
            merged_payload="merged-state",
            conflicts=(conflict,),
            resolutions=(),
            merged_at=1100,
        )


def test_merge_rejects_parents_from_different_restore_ancestors():
    _, s1, s2 = source_chain()
    left, left_restore, _, _ = fork_pair(s1)
    right_genesis, right_restore = restore_checkpoint(
        s2,
        target_branch_ref="future/right-other",
        target_generation=8,
        replayed_at=1002,
    )
    right_head = issue_successor_receipt(right_genesis, state_ref="right-head", payload="right")

    with pytest.raises(ValueError, match="invalid restore proof"):
        merge_branches(
            s1,
            left,
            left_restore,
            (right_genesis, right_head),
            right_restore,
            target_branch_ref="future/merged",
            target_generation=9,
            merged_payload="merged-state",
            merged_at=1100,
        )


def test_merge_rejects_same_parent_branch():
    _, ancestor, _ = source_chain()
    left, left_restore, _, _ = fork_pair(ancestor)

    with pytest.raises(ValueError, match="distinct branches"):
        merge_branches(
            ancestor,
            left,
            left_restore,
            left,
            left_restore,
            target_branch_ref="future/merged",
            target_generation=9,
            merged_payload="merged-state",
            merged_at=1100,
        )


def test_resolution_substitution_is_detected():
    _, ancestor, _ = source_chain()
    left, left_restore, right, right_restore = fork_pair(ancestor)
    conflict, resolution = conflict_bundle()
    target, merge = merge_branches(
        ancestor,
        left,
        left_restore,
        right,
        right_restore,
        target_branch_ref="future/merged",
        target_generation=9,
        merged_payload="merged-state",
        conflicts=(conflict,),
        resolutions=(resolution,),
        merged_at=1100,
    )

    substituted = replace(
        resolution,
        strategy="LEFT",
        result_digest=conflict.left_digest,
        reason_ref="decision:substituted",
    )
    valid, limitations = verify_merge(
        ancestor,
        left,
        left_restore,
        right,
        right_restore,
        target,
        merge,
        conflicts=(conflict,),
        resolutions=(substituted,),
    )

    assert valid is False
    assert "resolution_digest_mismatch" in limitations


def test_target_from_another_merge_cannot_be_substituted():
    _, ancestor, _ = source_chain()
    left, left_restore, right, right_restore = fork_pair(ancestor)
    conflict, resolution = conflict_bundle()

    target_a, merge_a = merge_branches(
        ancestor,
        left,
        left_restore,
        right,
        right_restore,
        target_branch_ref="future/merged-a",
        target_generation=9,
        merged_payload="merged-a",
        conflicts=(conflict,),
        resolutions=(resolution,),
        merged_at=1100,
    )
    target_b, _ = merge_branches(
        ancestor,
        left,
        left_restore,
        right,
        right_restore,
        target_branch_ref="future/merged-b",
        target_generation=9,
        merged_payload="merged-b",
        conflicts=(conflict,),
        resolutions=(resolution,),
        merged_at=1101,
    )

    valid, limitations = verify_merge(
        ancestor,
        left,
        left_restore,
        right,
        right_restore,
        target_b,
        merge_a,
        conflicts=(conflict,),
        resolutions=(resolution,),
    )

    assert target_a.receipt_hash != target_b.receipt_hash
    assert valid is False
    assert "target_branch_mismatch" in limitations or "target_genesis_mismatch" in limitations
