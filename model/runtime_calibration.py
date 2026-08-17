from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import sqlite3
from typing import Mapping

from model.authority import AuthorityGrant, AuthorityProof, verify_authority_proof
from model.calibration import (
    CalibrationFamilySnapshot,
    CalibrationTargetReceipt,
    DependencyCalibrationSnapshot,
    DependencyPairSample,
    ForecastCalibrationReceipt,
    LikelihoodCalibrationReceipt,
    ResolvedOutcomeReceipt,
    calibrate_forecast,
    calibrate_likelihood,
    make_calibration_target,
    make_dependency_pair_sample,
    make_resolved_outcome,
    summarize_calibration_family,
    summarize_dependency_samples,
)
from model.enforcement import EnforcementContext
from model.runtime_multihypothesis import (
    _connect as multi_connect,
    _dependency,
    _distribution_for_candidate,
    _ensure_work_incomplete,
    _model,
    evidence_from_dict,
)
from model.runtime_protocol import authority_grant_from_dict, authority_proof_from_dict
from model.runtime_verification import verification_scope

CALIBRATION_PROTOCOL = "ATMAN-CALIBRATION/1.12"
CALIBRATION_OPERATIONS = {
    "register_calibration_target",
    "register_resolved_outcome",
    "record_calibration_observation",
    "record_dependency_pair",
    "get_calibration_state",
}

ROLE_CALIBRATION_TARGET_KEEPER = "CALIBRATION_TARGET_KEEPER"
ROLE_CALIBRATION_RESOLVER = "CALIBRATION_RESOLVER"
ROLE_CALIBRATION_RECORDER = "CALIBRATION_RECORDER"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def target_to_dict(value: CalibrationTargetReceipt) -> dict[str, object]:
    value.validate()
    data = asdict(value)
    data["probability_bps"] = [[key, probability] for key, probability in value.probability_bps]
    data["positive_likelihood_bps"] = [[key, probability] for key, probability in value.positive_likelihood_bps]
    data["conditioning_evidence_hashes"] = list(value.conditioning_evidence_hashes)
    data["parent_evidence_hashes"] = list(value.parent_evidence_hashes)
    return data


def target_from_dict(data: Mapping[str, object]) -> CalibrationTargetReceipt:
    result = CalibrationTargetReceipt(
        target_ref=str(data["target_ref"]),
        calibration_family_ref=str(data["calibration_family_ref"]),
        candidate_hash=str(data["candidate_hash"]),
        distribution_ref=str(data["distribution_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        distribution_hash=str(data["distribution_hash"]),
        probability_bps=tuple((str(item[0]), int(item[1])) for item in data["probability_bps"]),
        likelihood_model_hash=str(data["likelihood_model_hash"]),
        likelihood_model_ref=str(data["likelihood_model_ref"]),
        positive_likelihood_bps=tuple((str(item[0]), int(item[1])) for item in data["positive_likelihood_bps"]),
        conditioning_evidence_hashes=tuple(str(value) for value in data.get("conditioning_evidence_hashes", [])),
        dependency_hash=str(data["dependency_hash"]),
        dependency_group_ref=str(data["dependency_group_ref"]),
        dependency_mode=str(data["dependency_mode"]),
        source_event_hash=str(data["source_event_hash"]),
        derivation_hash=str(data["derivation_hash"]),
        parent_evidence_hashes=tuple(str(value) for value in data.get("parent_evidence_hashes", [])),
        committed_at=int(data["committed_at"]),
        target_hash=str(data["target_hash"]),
    )
    result.validate()
    return result


def resolution_to_dict(value: ResolvedOutcomeReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def resolution_from_dict(data: Mapping[str, object]) -> ResolvedOutcomeReceipt:
    result = ResolvedOutcomeReceipt(
        resolution_ref=str(data["resolution_ref"]),
        distribution_ref=str(data["distribution_ref"]),
        subject_identity_ref=str(data["subject_identity_ref"]),
        resolved_hypothesis_ref=str(data["resolved_hypothesis_ref"]),
        resolution_source_hash=str(data["resolution_source_hash"]),
        resolved_at=int(data["resolved_at"]),
        resolver_ref=str(data["resolver_ref"]),
        resolution_hash=str(data["resolution_hash"]),
    )
    result.validate()
    return result


def forecast_to_dict(value: ForecastCalibrationReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def forecast_from_dict(data: Mapping[str, object]) -> ForecastCalibrationReceipt:
    result = ForecastCalibrationReceipt(
        target_hash=str(data["target_hash"]),
        resolution_hash=str(data["resolution_hash"]),
        calibration_family_ref=str(data["calibration_family_ref"]),
        distribution_hash=str(data["distribution_hash"]),
        resolved_hypothesis_ref=str(data["resolved_hypothesis_ref"]),
        resolved_probability_bps=int(data["resolved_probability_bps"]),
        brier_score_ppm=int(data["brier_score_ppm"]),
        calibrated_at=int(data["calibrated_at"]),
        calibration_hash=str(data["calibration_hash"]),
    )
    result.validate()
    return result


def likelihood_to_dict(value: LikelihoodCalibrationReceipt) -> dict[str, object]:
    value.validate()
    return asdict(value)


def likelihood_from_dict(data: Mapping[str, object]) -> LikelihoodCalibrationReceipt:
    raw_brier = data.get("brier_score_ppm")
    result = LikelihoodCalibrationReceipt(
        target_hash=str(data["target_hash"]),
        evidence_hash=str(data["evidence_hash"]),
        resolution_hash=str(data["resolution_hash"]),
        calibration_family_ref=str(data["calibration_family_ref"]),
        likelihood_model_hash=str(data["likelihood_model_hash"]),
        likelihood_model_ref=str(data["likelihood_model_ref"]),
        resolved_hypothesis_ref=str(data["resolved_hypothesis_ref"]),
        predicted_positive_bps=int(data["predicted_positive_bps"]),
        observed_outcome=str(data["observed_outcome"]),
        scored=bool(data["scored"]),
        brier_score_ppm=None if raw_brier is None else int(raw_brier),
        dependency_mode=str(data["dependency_mode"]),
        calibrated_at=int(data["calibrated_at"]),
        calibration_hash=str(data["calibration_hash"]),
    )
    result.validate()
    return result


def pair_to_dict(value: DependencyPairSample) -> dict[str, object]:
    value.validate()
    return asdict(value)


def pair_from_dict(data: Mapping[str, object]) -> DependencyPairSample:
    result = DependencyPairSample(
        pair_key=str(data["pair_key"]),
        resolution_hash=str(data["resolution_hash"]),
        dependency_group_ref=str(data["dependency_group_ref"]),
        left_model_ref=str(data["left_model_ref"]),
        right_model_ref=str(data["right_model_ref"]),
        declared_mode=str(data["declared_mode"]),
        resolved_hypothesis_ref=str(data["resolved_hypothesis_ref"]),
        left_evidence_hash=str(data["left_evidence_hash"]),
        right_evidence_hash=str(data["right_evidence_hash"]),
        left_positive=bool(data["left_positive"]),
        right_positive=bool(data["right_positive"]),
        sampled_at=int(data["sampled_at"]),
        sample_hash=str(data["sample_hash"]),
    )
    result.validate()
    return result


def family_snapshot_to_dict(value: CalibrationFamilySnapshot) -> dict[str, object]:
    value.validate()
    return asdict(value)


def dependency_snapshot_to_dict(value: DependencyCalibrationSnapshot) -> dict[str, object]:
    value.validate()
    return asdict(value)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = multi_connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_target (
            candidate_hash TEXT PRIMARY KEY,
            target_ref TEXT NOT NULL UNIQUE,
            distribution_ref TEXT NOT NULL,
            family_ref TEXT NOT NULL,
            target_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_resolution (
            distribution_ref TEXT PRIMARY KEY,
            resolution_ref TEXT NOT NULL UNIQUE,
            resolution_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_forecast_history (
            calibration_hash TEXT PRIMARY KEY,
            target_hash TEXT NOT NULL UNIQUE,
            family_ref TEXT NOT NULL,
            receipt_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_likelihood_history (
            calibration_hash TEXT PRIMARY KEY,
            target_hash TEXT NOT NULL UNIQUE,
            evidence_hash TEXT NOT NULL UNIQUE,
            family_ref TEXT NOT NULL,
            model_ref TEXT NOT NULL,
            receipt_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_dependency_pair (
            sample_hash TEXT PRIMARY KEY,
            pair_key TEXT NOT NULL,
            resolution_hash TEXT NOT NULL,
            receipt_json TEXT NOT NULL,
            UNIQUE(pair_key, resolution_hash)
        )
        """
    )
    return conn


def _enforce(
    grant: AuthorityGrant,
    proof: AuthorityProof,
    *,
    action: object,
    required_role: str,
    required_scope: str,
    enforcement: EnforcementContext,
) -> None:
    enforcement.validate()
    valid, limitations = verify_authority_proof(
        grant,
        proof,
        action=action,
        trusted_issuer_keys=enforcement.trusted_issuer_keys,
        current_policy_generation=enforcement.policy_generation,
        now=enforcement.now,
    )
    failures = list(limitations)
    if proof.role != required_role:
        failures.append("required_role_mismatch")
    if proof.scope != required_scope:
        failures.append("required_scope_mismatch")
    if not valid or failures:
        raise PermissionError("calibration authority failed: " + ",".join(dict.fromkeys(failures)))


def _target(conn: sqlite3.Connection, candidate_hash: str) -> CalibrationTargetReceipt:
    row = conn.execute("SELECT target_json FROM calibration_target WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("calibration target is not registered")
    return target_from_dict(json.loads(row[0]))


def _resolution(conn: sqlite3.Connection, distribution_ref: str) -> ResolvedOutcomeReceipt:
    row = conn.execute("SELECT resolution_json FROM calibration_resolution WHERE distribution_ref=?", (distribution_ref,)).fetchone()
    if row is None:
        raise ValueError("resolved outcome is not registered")
    return resolution_from_dict(json.loads(row[0]))


def _evidence_for_candidate(conn: sqlite3.Connection, candidate_hash: str):
    row = conn.execute("SELECT receipt_json FROM multi_evidence_history WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if row is None:
        raise ValueError("calibration requires accepted evidence for candidate")
    return evidence_from_dict(json.loads(row[0]))


def action_register_calibration_target(value: CalibrationTargetReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "register_calibration_target",
        "candidate_hash": value.candidate_hash,
        "target_hash": value.target_hash,
        "distribution_hash": value.distribution_hash,
        "likelihood_model_hash": value.likelihood_model_hash,
        "dependency_hash": value.dependency_hash,
        "committed_at": value.committed_at,
    }


def action_register_resolved_outcome(value: ResolvedOutcomeReceipt) -> dict[str, object]:
    value.validate()
    return {
        "operation": "register_resolved_outcome",
        "distribution_ref": value.distribution_ref,
        "resolution_hash": value.resolution_hash,
        "resolved_hypothesis_ref": value.resolved_hypothesis_ref,
        "resolved_at": value.resolved_at,
    }


def action_record_calibration_observation(*, target_hash: str, resolution_hash: str, evidence_hash: str, calibrated_at: int) -> dict[str, object]:
    return {
        "operation": "record_calibration_observation",
        "target_hash": target_hash,
        "resolution_hash": resolution_hash,
        "evidence_hash": evidence_hash,
        "calibrated_at": calibrated_at,
    }


def action_record_dependency_pair(value: DependencyPairSample) -> dict[str, object]:
    value.validate()
    return {
        "operation": "record_dependency_pair",
        "pair_key": value.pair_key,
        "sample_hash": value.sample_hash,
        "resolution_hash": value.resolution_hash,
        "sampled_at": value.sampled_at,
    }


def _register_target(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> CalibrationTargetReceipt:
    candidate_hash = str(payload["candidate_hash"])
    candidate = _ensure_work_incomplete(conn, candidate_hash)
    if conn.execute("SELECT 1 FROM calibration_resolution r JOIN multi_candidate_binding b ON r.distribution_ref=b.distribution_ref WHERE b.candidate_hash=?", (candidate_hash,)).fetchone() is not None:
        raise ValueError("calibration target must be committed before resolution")
    distribution = _distribution_for_candidate(conn, candidate_hash)
    model = _model(conn, candidate_hash)
    dependency = _dependency(conn, candidate_hash)
    target = make_calibration_target(
        target_ref=str(payload["target_ref"]),
        calibration_family_ref=str(payload["calibration_family_ref"]),
        distribution=distribution,
        likelihood_model=model,
        dependency=dependency,
        committed_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_register_calibration_target(target),
        required_role=ROLE_CALIBRATION_TARGET_KEEPER,
        required_scope=verification_scope(candidate.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT target_json FROM calibration_target WHERE candidate_hash=?", (candidate_hash,)).fetchone()
    if existing is not None:
        current = target_from_dict(json.loads(existing[0]))
        if current == target:
            return current
        raise ValueError("calibration target is immutable once committed")
    conn.execute(
        "INSERT INTO calibration_target(candidate_hash,target_ref,distribution_ref,family_ref,target_json) VALUES(?,?,?,?,?)",
        (candidate_hash, target.target_ref, target.distribution_ref, target.calibration_family_ref, json.dumps(target_to_dict(target), sort_keys=True, separators=(",", ":"))),
    )
    return target


def _register_resolution(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> ResolvedOutcomeReceipt:
    candidate_hash = str(payload["candidate_hash"])
    target = _target(conn, candidate_hash)
    resolution = make_resolved_outcome(
        target,
        resolution_ref=str(payload["resolution_ref"]),
        resolved_hypothesis_ref=str(payload["resolved_hypothesis_ref"]),
        resolution_source_hash=str(payload["resolution_source_hash"]),
        resolved_at=enforcement.now,
        resolver_ref=grant.subject_ref,
    )
    _enforce(
        grant,
        proof,
        action=action_register_resolved_outcome(resolution),
        required_role=ROLE_CALIBRATION_RESOLVER,
        required_scope=verification_scope(target.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT resolution_json FROM calibration_resolution WHERE distribution_ref=?", (target.distribution_ref,)).fetchone()
    if existing is not None:
        current = resolution_from_dict(json.loads(existing[0]))
        if current == resolution:
            return current
        raise ValueError("resolved outcome is immutable once registered")
    conn.execute(
        "INSERT INTO calibration_resolution(distribution_ref,resolution_ref,resolution_json) VALUES(?,?,?)",
        (target.distribution_ref, resolution.resolution_ref, json.dumps(resolution_to_dict(resolution), sort_keys=True, separators=(",", ":"))),
    )
    return resolution


def _record_observation(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> tuple[ForecastCalibrationReceipt, LikelihoodCalibrationReceipt]:
    candidate_hash = str(payload["candidate_hash"])
    target = _target(conn, candidate_hash)
    resolution = _resolution(conn, target.distribution_ref)
    evidence = _evidence_for_candidate(conn, candidate_hash)
    forecast = calibrate_forecast(target, resolution, calibrated_at=enforcement.now)
    likelihood = calibrate_likelihood(target, evidence, resolution, calibrated_at=enforcement.now)
    action = action_record_calibration_observation(
        target_hash=target.target_hash,
        resolution_hash=resolution.resolution_hash,
        evidence_hash=evidence.evidence_hash,
        calibrated_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action,
        required_role=ROLE_CALIBRATION_RECORDER,
        required_scope=verification_scope(target.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT receipt_json FROM calibration_likelihood_history WHERE evidence_hash=?", (evidence.evidence_hash,)).fetchone()
    if existing is not None:
        current_likelihood = likelihood_from_dict(json.loads(existing[0]))
        forecast_row = conn.execute("SELECT receipt_json FROM calibration_forecast_history WHERE target_hash=?", (target.target_hash,)).fetchone()
        current_forecast = forecast_from_dict(json.loads(forecast_row[0]))
        if current_likelihood == likelihood and current_forecast == forecast:
            return current_forecast, current_likelihood
        raise ValueError("calibration observation already recorded with different material")
    conn.execute(
        "INSERT INTO calibration_forecast_history(calibration_hash,target_hash,family_ref,receipt_json) VALUES(?,?,?,?)",
        (forecast.calibration_hash, target.target_hash, target.calibration_family_ref, json.dumps(forecast_to_dict(forecast), sort_keys=True, separators=(",", ":"))),
    )
    conn.execute(
        "INSERT INTO calibration_likelihood_history(calibration_hash,target_hash,evidence_hash,family_ref,model_ref,receipt_json) VALUES(?,?,?,?,?,?)",
        (likelihood.calibration_hash, target.target_hash, evidence.evidence_hash, target.calibration_family_ref, target.likelihood_model_ref, json.dumps(likelihood_to_dict(likelihood), sort_keys=True, separators=(",", ":"))),
    )
    return forecast, likelihood


def _record_pair(conn: sqlite3.Connection, payload: Mapping[str, object], *, grant: AuthorityGrant, proof: AuthorityProof, enforcement: EnforcementContext) -> DependencyPairSample:
    left_target = _target(conn, str(payload["left_candidate_hash"]))
    right_target = _target(conn, str(payload["right_candidate_hash"]))
    resolution = _resolution(conn, left_target.distribution_ref)
    left_evidence = _evidence_for_candidate(conn, left_target.candidate_hash)
    right_evidence = _evidence_for_candidate(conn, right_target.candidate_hash)
    sample = make_dependency_pair_sample(
        left_target=left_target,
        left_evidence=left_evidence,
        right_target=right_target,
        right_evidence=right_evidence,
        resolution=resolution,
        sampled_at=enforcement.now,
    )
    _enforce(
        grant,
        proof,
        action=action_record_dependency_pair(sample),
        required_role=ROLE_CALIBRATION_RECORDER,
        required_scope=verification_scope(left_target.subject_identity_ref),
        enforcement=enforcement,
    )
    existing = conn.execute("SELECT receipt_json FROM calibration_dependency_pair WHERE pair_key=? AND resolution_hash=?", (sample.pair_key, sample.resolution_hash)).fetchone()
    if existing is not None:
        current = pair_from_dict(json.loads(existing[0]))
        if current == sample:
            return current
        raise ValueError("dependency pair already recorded for this resolved case")
    conn.execute(
        "INSERT INTO calibration_dependency_pair(sample_hash,pair_key,resolution_hash,receipt_json) VALUES(?,?,?,?)",
        (sample.sample_hash, sample.pair_key, sample.resolution_hash, json.dumps(pair_to_dict(sample), sort_keys=True, separators=(",", ":"))),
    )
    return sample


def _state(conn: sqlite3.Connection, *, family_min_samples: int, family_gap_threshold_bps: int, dependency_min_samples: int, dependency_threshold_bps: int, measured_at: int) -> dict[str, object]:
    forecast_rows = conn.execute("SELECT receipt_json FROM calibration_forecast_history ORDER BY calibration_hash").fetchall()
    likelihood_rows = conn.execute("SELECT receipt_json FROM calibration_likelihood_history ORDER BY calibration_hash").fetchall()
    pair_rows = conn.execute("SELECT receipt_json FROM calibration_dependency_pair ORDER BY sample_hash").fetchall()
    forecasts = tuple(forecast_from_dict(json.loads(row[0])) for row in forecast_rows)
    likelihoods = tuple(likelihood_from_dict(json.loads(row[0])) for row in likelihood_rows)
    pairs = tuple(pair_from_dict(json.loads(row[0])) for row in pair_rows)
    families = sorted({item.calibration_family_ref for item in forecasts} | {item.calibration_family_ref for item in likelihoods})
    family_snapshots = tuple(
        summarize_calibration_family(
            forecasts,
            likelihoods,
            calibration_family_ref=family,
            min_samples=family_min_samples,
            marginal_gap_threshold_bps=family_gap_threshold_bps,
            measured_at=measured_at,
        )
        for family in families
    )
    pair_keys = sorted({item.pair_key for item in pairs})
    dependency_snapshots = tuple(
        summarize_dependency_samples(
            tuple(item for item in pairs if item.pair_key == pair_key),
            min_samples=dependency_min_samples,
            dependency_threshold_bps=dependency_threshold_bps,
            measured_at=measured_at,
        )
        for pair_key in pair_keys
    )
    state_material = {
        "domain": "ATMAN-LATTICE/runtime-calibration-state/v1.12",
        "forecast_hashes": [item.calibration_hash for item in forecasts],
        "likelihood_hashes": [item.calibration_hash for item in likelihoods],
        "dependency_sample_hashes": [item.sample_hash for item in pairs],
        "family_min_samples": family_min_samples,
        "family_gap_threshold_bps": family_gap_threshold_bps,
        "dependency_min_samples": dependency_min_samples,
        "dependency_threshold_bps": dependency_threshold_bps,
    }
    return {
        "state_hash": _digest(state_material),
        "family_snapshots": family_snapshots,
        "dependency_snapshots": dependency_snapshots,
        "forecast_count": len(forecasts),
        "likelihood_count": len(likelihoods),
        "dependency_pair_count": len(pairs),
    }


def execute_calibration_request(request: Mapping[str, object], *, enforcement: EnforcementContext, db_path: str) -> dict[str, object]:
    if request.get("protocol") != CALIBRATION_PROTOCOL:
        raise ValueError("unsupported calibration protocol")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("request_id is required")
    operation = str(request.get("operation", ""))
    if operation not in CALIBRATION_OPERATIONS:
        raise ValueError("unsupported calibration operation")
    payload = _mapping(request.get("payload", {}), "payload")
    conn = _connect(db_path)
    try:
        if operation == "get_calibration_state":
            state = _state(
                conn,
                family_min_samples=int(payload.get("family_min_samples", 5)),
                family_gap_threshold_bps=int(payload.get("family_gap_threshold_bps", 1000)),
                dependency_min_samples=int(payload.get("dependency_min_samples", 8)),
                dependency_threshold_bps=int(payload.get("dependency_threshold_bps", 1000)),
                measured_at=enforcement.now,
            )
            return {
                "protocol": CALIBRATION_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "state_hash": state["state_hash"],
                "forecast_count": state["forecast_count"],
                "likelihood_count": state["likelihood_count"],
                "dependency_pair_count": state["dependency_pair_count"],
                "family_snapshots": [family_snapshot_to_dict(item) for item in state["family_snapshots"]],
                "dependency_snapshots": [dependency_snapshot_to_dict(item) for item in state["dependency_snapshots"]],
            }

        grant = authority_grant_from_dict(_mapping(request.get("grant"), "grant"))
        proof = authority_proof_from_dict(_mapping(request.get("proof"), "proof"))
        conn.execute("BEGIN IMMEDIATE")
        if operation == "register_calibration_target":
            target = _register_target(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": CALIBRATION_PROTOCOL, "request_id": request_id, "ok": True, "target": target_to_dict(target)}
        if operation == "register_resolved_outcome":
            resolution = _register_resolution(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {"protocol": CALIBRATION_PROTOCOL, "request_id": request_id, "ok": True, "resolution": resolution_to_dict(resolution)}
        if operation == "record_calibration_observation":
            forecast, likelihood = _record_observation(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
            conn.execute("COMMIT")
            return {
                "protocol": CALIBRATION_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "forecast_calibration": forecast_to_dict(forecast),
                "likelihood_calibration": likelihood_to_dict(likelihood),
            }
        sample = _record_pair(conn, payload, grant=grant, proof=proof, enforcement=enforcement)
        conn.execute("COMMIT")
        return {"protocol": CALIBRATION_PROTOCOL, "request_id": request_id, "ok": True, "dependency_pair": pair_to_dict(sample)}
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
