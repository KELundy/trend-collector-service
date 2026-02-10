import sqlite3
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = "trend_collector.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            topic TEXT NOT NULL,
            collected_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_trends(source: str, topics: List[str]) -> None:
    if not topics:
        return

    conn = get_connection()
    cur = conn.cursor()
    collected_at = datetime.utcnow().isoformat()

    cur.executemany(
        """
        INSERT INTO trends (source, topic, collected_at)
        VALUES (?, ?, ?)
        """,
        [(source, topic, collected_at) for topic in topics],
    )

    conn.commit()
    conn.close()


def get_latest_trends(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT source, topic, collected_at
        FROM trends
        ORDER BY collected_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "source": row["source"],
            "topic": row["topic"],
            "collected_at": row["collected_at"],
        }
        for row in rows
    ]
