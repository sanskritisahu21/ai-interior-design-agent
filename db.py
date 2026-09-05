"""
db.py - Real-Time SQLite Session & Conversation Persistence
Manages chat_sessions and chat_messages tables in interior_company_catalog.db
for the conversational AI interior design consultant (Siya).
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interior_company_catalog.db")
if not os.path.exists(DB_PATH) and os.path.exists("interior_company_catalog.db"):
    DB_PATH = "interior_company_catalog.db"


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    target_path = db_path or DB_PATH
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_chat_tables(db_path: Optional[str] = None) -> None:
    """Initialize chat_sessions and chat_messages tables if they do not exist."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        session_id TEXT PRIMARY KEY,
        stage TEXT DEFAULT 'GREETING',
        room_type TEXT,
        length_cm REAL,
        width_cm REAL,
        height_cm REAL,
        budget_min REAL,
        budget_max REAL,
        budget_raw TEXT,
        style TEXT,
        must_haves TEXT,
        constraints TEXT,
        notes TEXT,
        current_plan_json TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        sender TEXT,
        message TEXT,
        metadata_json TEXT,
        timestamp TEXT,
        FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS session_scorecards (
        session_id TEXT PRIMARY KEY,
        scorecard_json TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


def get_or_create_session(session_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve existing session or create a new one."""
    init_chat_tables(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    now_iso = datetime.now().isoformat()

    if not row:
        cursor.execute("""
        INSERT INTO chat_sessions (
            session_id, stage, must_haves, created_at, updated_at
        ) VALUES (?, 'GREETING', '[]', ?, ?)
        """, (session_id, now_iso, now_iso))
        conn.commit()
        cursor.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()

    session_data = dict(row)
    conn.close()
    return session_data


def update_session(session_id: str, db_path: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Update fields of an active chat session."""
    init_chat_tables(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    kwargs["updated_at"] = datetime.now().isoformat()
    keys = list(kwargs.keys())
    set_clause = ", ".join([f"{k} = ?" for k in keys])
    values = [kwargs[k] for k in keys]
    values.append(session_id)

    cursor.execute(f"UPDATE chat_sessions SET {set_clause} WHERE session_id = ?", values)
    conn.commit()

    cursor.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}


def add_chat_message(
    session_id: str,
    sender: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None
) -> int:
    """Insert a user, assistant, or system message into chat_messages."""
    init_chat_tables(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    now_iso = datetime.now().isoformat()
    meta_str = json.dumps(metadata) if metadata else "{}"

    cursor.execute("""
    INSERT INTO chat_messages (session_id, sender, message, metadata_json, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (session_id, sender, message, meta_str, now_iso))

    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
    return msg_id


def get_chat_history(session_id: str, limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve full chronological conversation history for a session."""
    init_chat_tables(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, session_id, sender, message, metadata_json, timestamp
    FROM chat_messages
    WHERE session_id = ?
    ORDER BY id ASC
    LIMIT ?
    """, (session_id, limit))

    rows = cursor.fetchall()
    conn.close()

    history = []
    for r in rows:
        item = dict(r)
        try:
            item["metadata"] = json.loads(item["metadata_json"])
        except Exception:
            item["metadata"] = {}
        history.append(item)
    return history


def save_session_scorecard(session_id: str, scorecard: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Save an evaluated 14-column scorecard row for a completed chat session."""
    init_chat_tables(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    cursor.execute("""
    INSERT OR REPLACE INTO session_scorecards (session_id, scorecard_json, created_at)
    VALUES (?, ?, ?)
    """, (session_id, json.dumps(scorecard), now_iso))

    conn.commit()
    conn.close()


def get_all_session_scorecards(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all saved session scorecards in reverse chronological order."""
    init_chat_tables(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT scorecard_json FROM session_scorecards ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()

    scorecards = []
    for r in rows:
        try:
            scorecards.append(json.loads(r[0]))
        except Exception:
            pass
    return scorecards

