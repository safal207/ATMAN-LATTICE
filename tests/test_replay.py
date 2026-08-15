from dataclasses import replace

import pytest

from model.lattice import issue_genesis_receipt, issue_successor_receipt
from model.replay import restore_checkpoint, verify_restore


def chain():
    root = issue_genesis_receipt(
        identity_ref="person:1",
        state_ref="origin",
        branch_ref="main",
        generation=7,
        payload="origin",
    )
    s1 = issue_successor_receipt(root, state_ref="s1", payload="one")
    s2 = issue_successor_receipt(s1, state_ref="s2", payload="two")
    s3 = issue_successor_receipt(s2, state_ref="s3", payload="three")
    return root, s1, s2, s3


def test_restore_creates_new_branch_generation_and_root():
    _, _, checkpoint, current_head = chain()
    target, restore = restore_checkpoint(
        checkpoint,
        target_branch_ref="restore/s2",
        target_generation=8,
        replayed_at=1000,
    )
    valid, limitations = verify_restore(checkpoint, target, restore)

    assert valid is True
    assert limitations == ()
    assert target.identity_ref == checkpoint.identity_ref
    assert target.branch_ref != checkpoint.branch_ref
    assert target.generation > checkpoint.generation
    assert target.lineage_root_hash != checkpoint.lineage_root_hash
    assert target.lineage_root_hash != current_head.lineage_root_hash


def test_restore_cannot_silently_reuse_source_branch():
    _, _, checkpoint, _ = chain()
    with pytest.raises(ValueError, match="distinct branch"):
        restore_checkpoint(
            checkpoint,
            target_branch_ref="main",
            target_generation=8,
            replayed_at=1000,
        )


def test_restore_cannot_reuse_old_generation():
    _, _, checkpoint, _ = chain()
    with pytest.raises(ValueError, match="generation must advance"):
        restore_checkpoint(
            checkpoint,
            target_branch_ref="restore/s2",
            target_generation=7,
            replayed_at=1000,
        )


def test_restore_receipt_tamper_is_detected():
    _, _, checkpoint, _ = chain()
    target, restore = restore_checkpoint(
        checkpoint,
        target_branch_ref="restore/s2",
        target_generation=8,
        replayed_at=1000,
    )
    tampered = replace(restore, source_state_ref="other")
    valid, limitations = verify_restore(checkpoint, target, tampered)
    assert valid is False
    assert "invalid_restore_artifact" in limitations


def test_target_from_another_restore_cannot_be_substituted():
    _, s1, s2, _ = chain()
    target_a, restore_a = restore_checkpoint(
        s1,
        target_branch_ref="restore/s1",
        target_generation=8,
        replayed_at=1000,
    )
    target_b, _ = restore_checkpoint(
        s2,
        target_branch_ref="restore/s2",
        target_generation=8,
        replayed_at=1000,
    )

    valid, limitations = verify_restore(s1, target_b, restore_a)
    assert valid is False
    assert "target_branch_mismatch" in limitations or "target_root_mismatch" in limitations
    assert target_a.receipt_hash != target_b.receipt_hash
