from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable, TypeVar

from model.consumption import AuthorizationEvent, AuthorizationLedger, empty_authorization_ledger
from model.runtime_protocol import authorization_ledger_from_dict, authorization_ledger_to_dict

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
