import pytest

from model.remediation import assess_remediation_proposal, make_remediation_policy, select_remediation
from test_remediation import IDENTITY, proposal


def test_reference_profile_rejects_relaxed_rollback_gate():
    with pytest.raises(ValueError, match="requires non-positive"):
        make_remediation_policy(
            policy_ref="policy:relaxed-not-allowed",
            subject_identity_ref=IDENTITY,
            rollback_requires_nonpositive_improvement=False,
            registered_at=390,
        )


def test_multi_proposal_selection_canonicalizes_assessment_hashes_independently():
    *_, latest, snap, p, hold = proposal("HOLD", proposer="proposer:hold")
    *_, _, _, _, rollback = proposal("SAFE_ROLLBACK", proposer="proposer:rollback")
    hold_assessment = assess_remediation_proposal(proposal=hold, latest_evaluation=latest, policy=p, assessor_ref="assessor:hold", assessed_at=420)
    rollback_assessment = assess_remediation_proposal(proposal=rollback, latest_evaluation=latest, policy=p, assessor_ref="assessor:rollback", assessed_at=421)
    selection = select_remediation(
        selection_ref="selection:canonical",
        snapshot=snap,
        proposals=(rollback, hold),
        assessments=(rollback_assessment, hold_assessment),
        selected_proposal_hash=rollback.proposal_hash,
        selector_ref="selector",
        selected_at=430,
    )
    assert selection.proposal_hashes == tuple(sorted((hold.proposal_hash, rollback.proposal_hash)))
    assert selection.assessment_hashes == tuple(sorted((hold_assessment.assessment_hash, rollback_assessment.assessment_hash)))


def test_latest_replication_evaluator_cannot_select_recovery_path():
    *_, latest, snap, p, hold = proposal("HOLD")
    assessment = assess_remediation_proposal(proposal=hold, latest_evaluation=latest, policy=p, assessor_ref="assessor", assessed_at=420)
    with pytest.raises(ValueError, match="latest replication evaluator"):
        select_remediation(
            selection_ref="selection:evaluator",
            snapshot=snap,
            proposals=(hold,),
            assessments=(assessment,),
            selected_proposal_hash=hold.proposal_hash,
            selector_ref=latest.evaluator_ref,
            selected_at=430,
        )
