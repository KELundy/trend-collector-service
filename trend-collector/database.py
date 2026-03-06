import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

# ─────────────────────────────────────────────
# DB PATH — persistent Render disk
# ─────────────────────────────────────────────
DB_NAME = os.getenv("DB_PATH", "/data/homebridge.db")


def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────
# INIT — creates all tables on startup
# ─────────────────────────────────────────────
def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Users
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            brokerage TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Trends
    c.execute("""
        CREATE TABLE IF NOT EXISTS trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            topic TEXT NOT NULL,
            niche TEXT,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Content library — per-user, survives redeploys
    c.execute("""
        CREATE TABLE IF NOT EXISTS content_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            niche TEXT,
            status TEXT DEFAULT 'pending',
            content TEXT NOT NULL,
            compliance TEXT,
            copied_platforms TEXT DEFAULT '[]',
            saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
            approved_at TEXT,
            published_at TEXT,
            source TEXT DEFAULT 'manual',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Content schedules — per-user, per-niche automation settings
    c.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            niche TEXT NOT NULL,
            frequency TEXT NOT NULL DEFAULT 'weekly',
            time_of_day TEXT NOT NULL DEFAULT '08:00',
            timezone TEXT DEFAULT 'America/Denver',
            active INTEGER DEFAULT 1,
            last_run TEXT,
            next_run TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, niche),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# TRENDS
# ─────────────────────────────────────────────
def save_trends(trends: Dict[str, Any], niche: str):
    conn = get_conn()
    c = conn.cursor()
    for source, items in trends.items():
        if source == "timestamp":
            continue
        for item in items:
            topic = (
                item.get("topic") or item.get("title") or
                item.get("query") or json.dumps(item)
            ) if isinstance(item, dict) else str(item)
            c.execute(
                "INSERT INTO trends (source, topic, niche) VALUES (?, ?, ?)",
                (source, topic, niche)
            )
    conn.commit()
    conn.close()


def get_latest_trends(limit=200):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT source, topic, collected_at FROM trends
        ORDER BY collected_at DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    grouped = {
        "google": [], "youtube": [], "reddit": [],
        "bing": [], "tiktok": [],
        "timestamp": datetime.utcnow().isoformat()
    }
    for row in rows:
        src = row["source"]
        if src in grouped:
            grouped[src].append({"topic": row["topic"], "collected_at": row["collected_at"]})
    return grouped


def migrate_add_niche_column():
    """Legacy migration — safe to call even if column exists."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("PRAGMA table_info(trends)")
    columns = [col[1] for col in c.fetchall()]
    if "niche" not in columns:
        c.execute("ALTER TABLE trends ADD COLUMN niche TEXT")
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# CONTENT LIBRARY
# ─────────────────────────────────────────────
def library_save(user_id: int, niche: str, content: dict,
                 compliance: dict, source: str = "manual") -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO content_library
            (user_id, niche, status, content, compliance, source, saved_at)
        VALUES (?, ?, 'pending', ?, ?, ?, ?)
    """, (
        user_id, niche,
        json.dumps(content),
        json.dumps(compliance),
        source,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    item_id = c.lastrowid
    conn.close()
    return library_get_item(item_id)


def library_get_all(user_id: int) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM content_library
        WHERE user_id = ?
        ORDER BY saved_at DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return [_row_to_item(r) for r in rows]


def library_get_item(item_id: int) -> Optional[dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM content_library WHERE id = ?", (item_id,))
    row = c.fetchone()
    conn.close()
    return _row_to_item(row) if row else None


def library_update(item_id: int, user_id: int, updates: dict) -> Optional[dict]:
    """Update status, copiedPlatforms, content, approvedAt, publishedAt."""
    conn = get_conn()
    c = conn.cursor()

    allowed = {
        "status", "content", "compliance",
        "copied_platforms", "approved_at", "published_at"
    }
    fields, values = [], []

    for key, val in updates.items():
        if key not in allowed:
            continue
        fields.append(f"{key} = ?")
        values.append(json.dumps(val) if isinstance(val, (dict, list)) else val)

    if not fields:
        conn.close()
        return library_get_item(item_id)

    values += [item_id, user_id]
    c.execute(
        f"UPDATE content_library SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
        values
    )
    conn.commit()
    conn.close()
    return library_get_item(item_id)


def library_delete(item_id: int, user_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "DELETE FROM content_library WHERE id = ? AND user_id = ?",
        (item_id, user_id)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def _row_to_item(row) -> dict:
    return {
        "id":              row["id"],
        "userId":          row["user_id"],
        "niche":           row["niche"] or "",
        "status":          row["status"] or "pending",
        "content":         json.loads(row["content"]) if row["content"] else {},
        "compliance":      json.loads(row["compliance"]) if row["compliance"] else None,
        "copiedPlatforms": json.loads(row["copied_platforms"]) if row["copied_platforms"] else [],
        "savedAt":         row["saved_at"],
        "approvedAt":      row["approved_at"],
        "publishedAt":     row["published_at"],
        "source":          row["source"] or "manual",
    }


# ─────────────────────────────────────────────
# SCHEDULES
# ─────────────────────────────────────────────
def schedule_upsert(user_id: int, niche: str, frequency: str,
                    time_of_day: str, timezone: str = "America/Denver") -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO schedules (user_id, niche, frequency, time_of_day, timezone, active)
        VALUES (?, ?, ?, ?, ?, 1)
        ON CONFLICT(user_id, niche) DO UPDATE SET
            frequency   = excluded.frequency,
            time_of_day = excluded.time_of_day,
            timezone    = excluded.timezone,
            active      = 1
    """, (user_id, niche, frequency, time_of_day, timezone))
    conn.commit()
    conn.close()
    return schedule_get(user_id, niche)


def schedule_get(user_id: int, niche: str) -> Optional[dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM schedules WHERE user_id = ? AND niche = ?",
        (user_id, niche)
    )
    row = c.fetchone()
    conn.close()
    return _schedule_row(row) if row else None


def schedules_get_all(user_id: int) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM schedules WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [_schedule_row(r) for r in rows]


def schedules_get_due() -> list:
    """Return all active schedules whose next_run is due (or never run)."""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        SELECT s.*, u.id as uid, u.email, u.agent_name, u.brokerage
        FROM schedules s
        JOIN users u ON s.user_id = u.id
        WHERE s.active = 1
          AND (s.next_run IS NULL OR s.next_run <= ?)
    """, (now,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def schedule_mark_ran(schedule_id: int, next_run: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE schedules SET last_run = ?, next_run = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), next_run, schedule_id)
    )
    conn.commit()
    conn.close()


def schedule_delete(user_id: int, niche: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "DELETE FROM schedules WHERE user_id = ? AND niche = ?",
        (user_id, niche)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def _schedule_row(row) -> dict:
    return {
        "id":         row["id"],
        "userId":     row["user_id"],
        "niche":      row["niche"],
        "frequency":  row["frequency"],
        "timeOfDay":  row["time_of_day"],
        "timezone":   row["timezone"],
        "active":     bool(row["active"]),
        "lastRun":    row["last_run"],
        "nextRun":    row["next_run"],
    }


# ─────────────────────────────────────────────
# LEGACY — content_queue kept for compatibility
# ─────────────────────────────────────────────
def add_content_to_queue(item: dict):
    pass  # No-op — content_library replaces this

def get_content_queue():
    return []

def update_content_status(item_id: int, new_status: str):
    pass
