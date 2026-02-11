import sqlite3
from datetime import datetime
import json

DB_NAME = "trends.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Existing trends table
    c.execute("""
        CREATE TABLE IF NOT EXISTS trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            topic TEXT NOT NULL,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # NEW: Content Queue table
    c.execute("""
        CREATE TABLE IF NOT EXISTS content_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            trend TEXT,
            niche TEXT,
            headline TEXT,
            post TEXT,
            call_to_action TEXT,
            script30 TEXT,
            thumbnail_idea TEXT,
            hashtags TEXT,  -- stored as JSON
            status TEXT DEFAULT 'draft'
        )
    """)

    conn.commit()
    conn.close()


# -----------------------------
# TREND STORAGE
# -----------------------------

def save_trends(source, topics):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    for topic in topics:
        c.execute(
            "INSERT INTO trends (source, topic) VALUES (?, ?)",
            (source, topic)
        )

    conn.commit()
    conn.close()


def get_latest_trends(limit=50):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT source, topic, collected_at
        FROM trends
        ORDER BY collected_at DESC
        LIMIT ?
    """, (limit,))

    rows = c.fetchall()
    conn.close()

    return [
        {"source": r[0], "topic": r[1], "collected_at": r[2]}
        for r in rows
    ]


# -----------------------------
# CONTENT QUEUE STORAGE
# -----------------------------

def add_content_to_queue(item: dict):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        INSERT INTO content_queue (
            created_at, trend, niche, headline, post,
            call_to_action, script30, thumbnail_idea,
            hashtags, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().isoformat(),
        item.get("trend"),
        item.get("niche"),
        item.get("headline"),
        item.get("post"),
        item.get("call_to_action"),
        item.get("script30"),
        item.get("thumbnail_idea"),
        json.dumps(item.get("hashtags", [])),
        item.get("status", "draft")
    ))

    conn.commit()
    conn.close()


def get_content_queue():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT id, created_at, trend, niche, headline,
               status, hashtags
        FROM content_queue
        ORDER BY created_at DESC
    """)

    rows = c.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "created_at": r[1],
            "trend": r[2],
            "niche": r[3],
            "headline": r[4],
            "status": r[5],
            "hashtags": json.loads(r[6]) if r[6] else []
        })

    return results


def update_content_status(item_id: int, new_status: str):
    """
    Update the status of a content_queue item.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        "UPDATE content_queue SET status = ? WHERE id = ?",
        (new_status, item_id)
    )

    conn.commit()
    conn.close()
