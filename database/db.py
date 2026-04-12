#!/usr/bin/env python
# =============================================================================
#   HRI_lab_Pepper — Dialog Database
# =============================================================================
"""
Simple SQLite-based database to record dialog turns, events, and custom data.
No SQL knowledge required — use the Python methods directly.

Quick start
-----------
    from HRI_lab_Pepper.database import DialogDB

    db = DialogDB()                     # creates database.db next to your script

    # --- Logging a conversation ---
    db.log("robot", "Hello! How can I help you?")
    db.log("user",  "I need some water.", intent="ask_water")

    history = db.get_history(n=20)
    # [{"id": 1, "role": "robot", "text": "Hello...", "ts": "2026-...", ...}, ...]

    # --- Sessions (group turns by interaction) ---
    sid = db.new_session("customer_001")
    db.log("robot", "Welcome!", session_id=sid)
    db.log("user",  "Hi",       session_id=sid)
    turns = db.get_session(sid)

    # --- Key-value store (save anything) ---
    db.save("last_name", "Alice")
    db.save("score", 42)
    name = db.load("last_name")         # "Alice"

    # --- Export ---
    db.export_csv("my_log.csv")
    db.export_json("my_log.json")

    # --- Context manager (auto-closes) ---
    with DialogDB("session.db") as db:
        db.log("robot", "Hello")
"""

import csv
import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Optional


class DialogDB:
    """
    Lightweight SQLite wrapper for recording robot-human interactions.

    Parameters
    ----------
    path : str
        Path to the ``.db`` file.  Created automatically if it does not exist.
        Defaults to ``database/database.db`` in the current working directory.

    Examples
    --------
    >>> db = DialogDB()
    >>> db.log("robot", "Hello!")
    >>> db.log("user", "Hi there", intent="greet")
    >>> print(db.get_history(n=5))
    """

    # ─── schema ───────────────────────────────────────────────────────────────
    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS sessions (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        label      TEXT,
        started_at TEXT NOT NULL,
        ended_at   TEXT
    );

    CREATE TABLE IF NOT EXISTS dialog (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
        ts         TEXT NOT NULL,
        role       TEXT NOT NULL,      -- 'robot' | 'user' | 'system' | anything
        text       TEXT NOT NULL,
        intent     TEXT,               -- optional NLU intent label
        confidence REAL,               -- optional NLU confidence [0-1]
        metadata   TEXT               -- JSON blob for extra fields
    );

    CREATE TABLE IF NOT EXISTS store (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,      -- JSON-encoded value
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS events (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        ts         TEXT NOT NULL,
        event_type TEXT NOT NULL,
        data       TEXT               -- JSON blob
    );
    """

    def __init__(self, path: str = "database/database.db") -> None:
        self._path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(self._SCHEMA)
            self._conn.commit()
        print(f"[DB] Database ready → {os.path.abspath(path)}")

    # ─── context manager ──────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()

    # ─── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(sep=" ", timespec="seconds")

    @staticmethod
    def _rows_to_dicts(rows) -> list:
        return [dict(r) for r in rows]

    # ─── dialog logging ───────────────────────────────────────────────────────

    def log(
        self,
        role: str,
        text: str,
        *,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        session_id: Optional[int] = None,
        **extra,
    ) -> int:
        """
        Record one dialog turn.

        Parameters
        ----------
        role : str
            Who spoke: ``"robot"``, ``"user"``, or any label you choose.
        text : str
            What was said or heard.
        intent : str, optional
            Detected intent label (e.g. ``"ask_price"``).
        confidence : float, optional
            Confidence score [0.0 – 1.0].
        session_id : int, optional
            Link this turn to a session returned by :meth:`new_session`.
        **extra
            Any extra fields are stored in the metadata JSON column.

        Returns
        -------
        int
            Row ID of the inserted turn.
        """
        meta = json.dumps(extra) if extra else None
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO dialog (session_id, ts, role, text, intent, confidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, self._now(), role, text, intent, confidence, meta),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_history(
        self,
        n: int = 50,
        *,
        role: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> list:
        """
        Retrieve recent dialog turns, newest last.

        Parameters
        ----------
        n : int
            Maximum number of turns to return (default 50).
        role : str, optional
            Filter by role (e.g. ``"user"``).
        session_id : int, optional
            Filter to a specific session.

        Returns
        -------
        list of dict
            Each dict has: ``id``, ``ts``, ``role``, ``text``, ``intent``,
            ``confidence``, ``session_id``, ``metadata``.
        """
        filters = []
        params: list = []
        if role:
            filters.append("role = ?"); params.append(role)
        if session_id is not None:
            filters.append("session_id = ?"); params.append(session_id)

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.append(n)
        sql = f"SELECT * FROM (SELECT * FROM dialog {where} ORDER BY id DESC LIMIT ?) ORDER BY id"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return self._rows_to_dicts(rows)

    def clear_history(self, *, session_id: Optional[int] = None) -> int:
        """
        Delete dialog turns.

        Parameters
        ----------
        session_id : int, optional
            If given, delete only turns from that session; otherwise delete all.

        Returns
        -------
        int
            Number of rows deleted.
        """
        if session_id is not None:
            sql, params = "DELETE FROM dialog WHERE session_id = ?", (session_id,)
        else:
            sql, params = "DELETE FROM dialog", ()
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.rowcount

    # ─── sessions ─────────────────────────────────────────────────────────────

    def new_session(self, label: Optional[str] = None) -> int:
        """
        Start a new interaction session.

        Parameters
        ----------
        label : str, optional
            A human-readable name for this session (e.g. visitor ID, scenario name).

        Returns
        -------
        int
            Session ID to pass to :meth:`log`.

        Example
        -------
        >>> sid = db.new_session("visitor_42")
        >>> db.log("robot", "Hello!", session_id=sid)
        """
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO sessions (label, started_at) VALUES (?, ?)",
                (label, self._now()),
            )
            self._conn.commit()
            session_id = cur.lastrowid
        print(f"[DB] New session #{session_id}" + (f" ({label})" if label else ""))
        return session_id

    def end_session(self, session_id: int) -> None:
        """Mark a session as ended (records the end timestamp)."""
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (self._now(), session_id),
            )
            self._conn.commit()

    def get_session(self, session_id: int) -> list:
        """
        Return all dialog turns for a specific session.

        Parameters
        ----------
        session_id : int
            ID returned by :meth:`new_session`.

        Returns
        -------
        list of dict
        """
        return self.get_history(n=10000, session_id=session_id)

    def list_sessions(self) -> list:
        """Return all sessions (most recent first)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY id DESC"
            ).fetchall()
        return self._rows_to_dicts(rows)

    # ─── key-value store ──────────────────────────────────────────────────────

    def save(self, key: str, value: Any) -> None:
        """
        Save any Python value under a named key.

        Parameters
        ----------
        key : str
            Unique identifier (will be overwritten if it already exists).
        value : any
            Any JSON-serialisable value: string, number, list, dict, bool, None.

        Example
        -------
        >>> db.save("last_user", "Alice")
        >>> db.save("scores", [10, 20, 30])
        """
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO store (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, json.dumps(value), self._now()),
            )
            self._conn.commit()

    def load(self, key: str, default: Any = None) -> Any:
        """
        Load a saved value.

        Parameters
        ----------
        key : str
            Key used in :meth:`save`.
        default : any
            Value to return if the key does not exist.

        Returns
        -------
        any
            The stored Python value.

        Example
        -------
        >>> name = db.load("last_user", default="unknown")
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM store WHERE key = ?", (key,)
            ).fetchone()
        return json.loads(row["value"]) if row else default

    def delete(self, key: str) -> bool:
        """Delete a stored key. Returns True if the key existed."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM store WHERE key = ?", (key,))
            self._conn.commit()
            return cur.rowcount > 0

    def all_keys(self) -> list:
        """Return a list of all saved keys."""
        with self._lock:
            rows = self._conn.execute("SELECT key FROM store").fetchall()
        return [r["key"] for r in rows]

    # ─── event log ────────────────────────────────────────────────────────────

    def log_event(self, event_type: str, data: Any = None) -> int:
        """
        Record a generic event (sensor trigger, error, state change, etc.).

        Parameters
        ----------
        event_type : str
            A short label like ``"touch"``, ``"error"``, ``"human_detected"``.
        data : any, optional
            JSON-serialisable payload.

        Returns
        -------
        int
            Row ID.

        Example
        -------
        >>> db.log_event("touch", {"zone": "head_front"})
        >>> db.log_event("human_detected", {"count": 2, "confidence": 0.95})
        """
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events (ts, event_type, data) VALUES (?, ?, ?)",
                (self._now(), event_type, json.dumps(data) if data is not None else None),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_events(
        self,
        event_type: Optional[str] = None,
        *,
        limit: int = 100,
    ) -> list:
        """
        Retrieve recorded events.

        Parameters
        ----------
        event_type : str, optional
            Filter by type. Returns all types if omitted.
        limit : int
            Maximum number of rows (default 100).

        Returns
        -------
        list of dict
        """
        if event_type:
            sql  = "SELECT * FROM events WHERE event_type = ? ORDER BY id DESC LIMIT ?"
            args = (event_type, limit)
        else:
            sql  = "SELECT * FROM events ORDER BY id DESC LIMIT ?"
            args = (limit,)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d["data"]:
                try:
                    d["data"] = json.loads(d["data"])
                except json.JSONDecodeError:
                    pass
            result.append(d)
        return list(reversed(result))

    # ─── export ───────────────────────────────────────────────────────────────

    def export_csv(self, path: str, *, session_id: Optional[int] = None) -> None:
        """
        Export dialog history to a CSV file.

        Parameters
        ----------
        path : str
            Destination file path (e.g. ``"log.csv"``).
        session_id : int, optional
            Limit export to one session.

        Example
        -------
        >>> db.export_csv("session_log.csv")
        """
        rows = self.get_history(n=100_000, session_id=session_id)
        if not rows:
            print("[DB] Nothing to export.")
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"[DB] Exported {len(rows)} turns → {path}")

    def export_json(self, path: str, *, session_id: Optional[int] = None) -> None:
        """
        Export dialog history to a JSON file.

        Parameters
        ----------
        path : str
            Destination file path (e.g. ``"log.json"``).
        session_id : int, optional
            Limit export to one session.

        Example
        -------
        >>> db.export_json("session_log.json")
        """
        rows = self.get_history(n=100_000, session_id=session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"[DB] Exported {len(rows)} turns → {path}")

    # ─── stats ────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """
        Return basic database statistics.

        Returns
        -------
        dict
            ``{"dialog_turns": int, "sessions": int, "events": int, "keys": int}``
        """
        with self._lock:
            def _count(table):
                return self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            return {
                "dialog_turns": _count("dialog"),
                "sessions":     _count("sessions"),
                "events":       _count("events"),
                "keys":         _count("store"),
            }

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"DialogDB({self._path!r}  turns={s['dialog_turns']}  "
            f"sessions={s['sessions']}  events={s['events']}  keys={s['keys']})"
        )
