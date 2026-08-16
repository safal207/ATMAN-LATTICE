from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable, Mapping, TypeVar

from model.consumption import AuthorizationEvent, AuthorizationLedger, empty_authorization_ledger
from model.runtime_protocol import authorization_ledger_from_dict, authorization_ledger_to_dict
from model.trust_root import (
    TrustPolicy,
    TrustTransitionReceipt,
    create_bootstrap_policy,
    trust_policy_from_dict,
    trust_policy_to_dict,
    trust_transition_receipt_to_dict,
)

T = TypeVar("T")


def _connect(db_path: str) -> sqlite3.Connection:
    if not db_path:
        raise ValueError("runtime database path is required")
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10.0, isolation_level=None)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS authorization_ledgers (
            identity_ref TEXT PRIMARY KEY,
            generation INTEGER NOT NULL,
            ledger_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS trust_policy_state (
            singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
            generation INTEGER NOT NULL,
            policy_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS trust_transition_receipts (
            transition_hash TEXT PRIMARY KEY,
            from_generation INTEGER NOT NULL,
            to_generation INTEGER NOT NULL,
            receipt_json TEXT NOT NULL
        )
        """
    )
    return connection


def _load_locked(connection: sqlite3.Connection, identity_ref: str) -> AuthorizationLedger:
    row = connection.execute(
        "SELECT ledger_json FROM authorization_ledgers WHERE identity_ref = ?",
        (identity_ref,),
    ).fetchone()
    if row is None:
        return empty_authorization_ledger()
    decoded = json.loads(str(row[0]))
    if not isinstance(decoded, dict):
        raise ValueError("stored authorization ledger must decode to an object")
    return authorization_ledger_from_dict(decoded)


def read_authorization_ledger(db_path: str, identity_ref: str) -> AuthorizationLedger:
    if not identity_ref:
        raise ValueError("identity_ref is required")
    connection = _connect(db_path)
    try:
        return _load_locked(connection, identity_ref)
    finally:
        connection.close()


def mutate_authorization_ledger(
    db_path: str,
    identity_ref: str,
    mutation: Callable[[AuthorizationLedger], tuple[AuthorizationLedger, AuthorizationEvent]],
) -> tuple[AuthorizationLedger, AuthorizationEvent]:
    """Serialize a ledger mutation with a database write lock.

    BEGIN IMMEDIATE ensures two processes cannot both validate and append against the
    same previous generation. The mutation itself still enforces the caller's exact
    expected generation and token terminal-state rules.
    """
    if not identity_ref:
        raise ValueError("identity_ref is required")
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _load_locked(connection, identity_ref)
        updated, event = mutation(current)
        updated.validate()
        event.validate()
        encoded = json.dumps(
            authorization_ledger_to_dict(updated),
            sort_keys=True,
            separators=(",", ":"),
        )
        connection.execute(
            """
            INSERT INTO authorization_ledgers(identity_ref, generation, ledger_json)
            VALUES (?, ?, ?)
            ON CONFLICT(identity_ref) DO UPDATE SET
                generation = excluded.generation,
                ledger_json = excluded.ledger_json
            """,
            (identity_ref, updated.generation, encoded),
        )
        connection.execute("COMMIT")
        return updated, event
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        raise
    finally:
        connection.close()


def _load_trust_policy_locked(connection: sqlite3.Connection) -> TrustPolicy | None:
    row = connection.execute(
        "SELECT policy_json FROM trust_policy_state WHERE singleton_id = 1"
    ).fetchone()
    if row is None:
        return None
    decoded = json.loads(str(row[0]))
    if not isinstance(decoded, dict):
        raise ValueError("stored trust policy must decode to an object")
    return trust_policy_from_dict(decoded)


def _bootstrap_trust_policy_locked(
    connection: sqlite3.Connection,
    *,
    bootstrap_roots: Mapping[str, bytes],
    bootstrap_generation: int,
    bootstrap_threshold: int,
    bootstrap_activated_at: int,
) -> TrustPolicy:
    current = _load_trust_policy_locked(connection)
    if current is not None:
        return current
    policy = create_bootstrap_policy(
        bootstrap_roots,
        generation=bootstrap_generation,
        threshold=bootstrap_threshold,
        activated_at=bootstrap_activated_at,
    )
    encoded = json.dumps(trust_policy_to_dict(policy), sort_keys=True, separators=(",", ":"))
    connection.execute(
        "INSERT INTO trust_policy_state(singleton_id, generation, policy_json) VALUES (1, ?, ?)",
        (policy.generation, encoded),
    )
    return policy


def read_or_bootstrap_trust_policy(
    db_path: str,
    *,
    bootstrap_roots: Mapping[str, bytes],
    bootstrap_generation: int,
    bootstrap_threshold: int,
    bootstrap_activated_at: int = 0,
) -> TrustPolicy:
    """Return server trust state, persisting bootstrap roots only on first initialization.

    Once initialized, environment/bootstrap roots are no longer authoritative for this
    database. This prevents a process restart from silently rolling a rotated policy back.
    """
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        policy = _bootstrap_trust_policy_locked(
            connection,
            bootstrap_roots=bootstrap_roots,
            bootstrap_generation=bootstrap_generation,
            bootstrap_threshold=bootstrap_threshold,
            bootstrap_activated_at=bootstrap_activated_at,
        )
        connection.execute("COMMIT")
        return policy
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        raise
    finally:
        connection.close()


def mutate_trust_policy(
    db_path: str,
    *,
    bootstrap_roots: Mapping[str, bytes],
    bootstrap_generation: int,
    bootstrap_threshold: int,
    bootstrap_activated_at: int,
    mutation: Callable[[TrustPolicy], tuple[TrustPolicy, TrustTransitionReceipt]],
) -> tuple[TrustPolicy, TrustTransitionReceipt]:
    """Atomically advance the singleton trust policy and append its transition receipt."""
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _bootstrap_trust_policy_locked(
            connection,
            bootstrap_roots=bootstrap_roots,
            bootstrap_generation=bootstrap_generation,
            bootstrap_threshold=bootstrap_threshold,
            bootstrap_activated_at=bootstrap_activated_at,
        )
        updated, receipt = mutation(current)
        updated.validate()
        receipt.validate()
        if updated.previous_policy_hash != current.policy_hash:
            raise ValueError("new trust policy must link to exact current policy")
        if receipt.from_policy_hash != current.policy_hash or receipt.to_policy_hash != updated.policy_hash:
            raise ValueError("trust transition receipt does not bind current and updated policies")

        encoded_policy = json.dumps(
            trust_policy_to_dict(updated),
            sort_keys=True,
            separators=(",", ":"),
        )
        connection.execute(
            "UPDATE trust_policy_state SET generation = ?, policy_json = ? WHERE singleton_id = 1",
            (updated.generation, encoded_policy),
        )
        encoded_receipt = json.dumps(
            trust_transition_receipt_to_dict(receipt),
            sort_keys=True,
            separators=(",", ":"),
        )
        connection.execute(
            """
            INSERT INTO trust_transition_receipts(
                transition_hash, from_generation, to_generation, receipt_json
            ) VALUES (?, ?, ?, ?)
            """,
            (
                receipt.transition_hash,
                receipt.from_generation,
                receipt.to_generation,
                encoded_receipt,
            ),
        )
        connection.execute("COMMIT")
        return updated, receipt
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        raise
    finally:
        connection.close()
