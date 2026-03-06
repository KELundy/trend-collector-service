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


# ─────────────────────────────────────────────
# IDENTITY STRENGTH SCORE
# ─────────────────────────────────────────────

def calculate_identity_score(user_id: int, setup: dict) -> dict:
    """
    Calculate a 0-100 identity strength score across four pillars.
    setup dict comes from agent_setup table or is passed from frontend.

    Pillars:
      Foundation  (30 pts) — profile completeness
      Integrity   (25 pts) — compliance rate
      Presence    (30 pts) — publishing activity
      Consistency (15 pts) — regularity over time
    """
    from datetime import datetime, timedelta
    import json

    conn = get_conn()
    c    = conn.cursor()

    # ── Pull all library items for this user ──
    c.execute("""
        SELECT status, compliance, approved_at, published_at, saved_at, niche
        FROM content_library
        WHERE user_id = ?
        ORDER BY saved_at DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()

    total_items     = len(rows)
    approved_items  = [r for r in rows if r["status"] in ("approved", "published")]
    published_items = [r for r in rows if r["status"] == "published"]

    # ── PILLAR 1: Foundation (30 pts) ──
    foundation = 0
    foundation_breakdown = {}

    name_pts       = 5  if setup.get("agentName", "").strip()   else 0
    market_pts     = 5  if setup.get("market", "").strip()      else 0
    bio_pts        = 8  if len(setup.get("shortBio","").strip()) > 60  else (4 if len(setup.get("shortBio","").strip()) > 20 else 0)
    voice_pts      = 6  if len(setup.get("brandVoice","").strip()) > 30 else (3 if len(setup.get("brandVoice","").strip()) > 10 else 0)
    niches_raw     = setup.get("selectedNiches", [])
    niches         = niches_raw if isinstance(niches_raw, list) else []
    niche_pts      = 6  if len(niches) >= 2 else (3 if len(niches) == 1 else 0)

    foundation = name_pts + market_pts + bio_pts + voice_pts + niche_pts
    foundation_breakdown = {
        "name":   {"pts": name_pts,   "max": 5,  "label": "Name"},
        "market": {"pts": market_pts, "max": 5,  "label": "Market"},
        "bio":    {"pts": bio_pts,    "max": 8,  "label": "Bio"},
        "voice":  {"pts": voice_pts,  "max": 6,  "label": "Brand Voice"},
        "niches": {"pts": niche_pts,  "max": 6,  "label": "Niches"},
    }

    # ── PILLAR 2: Integrity (25 pts) ──
    integrity = 0
    integrity_breakdown = {}

    if total_items == 0:
        integrity = 0
        compliance_rate = None
        integrity_breakdown = {"label": "No content yet", "rate": None}
    else:
        compliant_count = 0
        for r in rows:
            try:
                comp = json.loads(r["compliance"]) if isinstance(r["compliance"], str) else r["compliance"]
                if isinstance(comp, dict):
                    verdict = comp.get("overall_verdict") or comp.get("status") or ""
                    if str(verdict).lower() in ("pass", "compliant", "ok", "green"):
                        compliant_count += 1
                    elif comp.get("passed") is True:
                        compliant_count += 1
            except Exception:
                pass

        compliance_rate = round((compliant_count / total_items) * 100) if total_items > 0 else 0

        if compliance_rate == 100:   integrity = 25
        elif compliance_rate >= 90:  integrity = 20
        elif compliance_rate >= 75:  integrity = 12
        elif compliance_rate >= 50:  integrity = 6
        else:                         integrity = 2

        integrity_breakdown = {
            "rate":     compliance_rate,
            "passing":  compliant_count,
            "total":    total_items,
        }

    # ── PILLAR 3: Presence (30 pts) ──
    presence = 0
    presence_breakdown = {}

    now = datetime.utcnow()
    last_7  = now - timedelta(days=7)
    last_30 = now - timedelta(days=30)

    def parse_date(s):
        if not s: return None
        try:    return datetime.fromisoformat(s.replace("Z",""))
        except: return None

    published_dates = [parse_date(r["published_at"] or r["approved_at"] or r["saved_at"]) for r in approved_items]
    published_dates = [d for d in published_dates if d]

    has_any        = len(approved_items) > 0
    in_last_7      = any(d >= last_7  for d in published_dates)
    in_last_30     = any(d >= last_30 for d in published_dates)
    total_approved = len(approved_items)

    any_pts      = 5  if has_any        else 0
    recent7_pts  = 12 if in_last_7      else 0
    recent30_pts = 8  if in_last_30 and not in_last_7 else 0
    volume_pts   = 5  if total_approved >= 5 else (3 if total_approved >= 2 else 0)

    presence = any_pts + recent7_pts + recent30_pts + volume_pts
    presence_breakdown = {
        "total_approved": total_approved,
        "published_last_7":  in_last_7,
        "published_last_30": in_last_30,
    }

    # ── PILLAR 4: Consistency (15 pts) ──
    consistency = 0
    consistency_breakdown = {}

    # Check for active schedule
    try:
        conn2 = get_conn()
        c2 = conn2.cursor()
        c2.execute("SELECT COUNT(*) as cnt FROM schedules WHERE user_id = ? AND active = 1", (user_id,))
        sched_row = c2.fetchone()
        conn2.close()
        has_schedule = (sched_row["cnt"] > 0) if sched_row else False
    except Exception:
        has_schedule = False

    # Check niche diversity
    niche_diversity = len(set(r["niche"] for r in approved_items if r["niche"])) if approved_items else 0

    # Check weekly regularity over last 4 weeks
    weeks_active = 0
    for i in range(4):
        week_start = now - timedelta(days=(i+1)*7)
        week_end   = now - timedelta(days=i*7)
        if any(week_start <= d < week_end for d in published_dates):
            weeks_active += 1

    schedule_pts   = 5 if has_schedule                  else 0
    diversity_pts  = 5 if niche_diversity >= 2          else (2 if niche_diversity == 1 else 0)
    regularity_pts = 5 if weeks_active >= 3             else (3 if weeks_active >= 2   else (1 if weeks_active == 1 else 0))

    consistency = schedule_pts + diversity_pts + regularity_pts
    consistency_breakdown = {
        "has_schedule":    has_schedule,
        "niche_diversity": niche_diversity,
        "weeks_active":    weeks_active,
    }

    # ── TOTAL ──
    total = foundation + integrity + presence + consistency
    total = min(total, 100)

    if total >= 90:   level = "Authoritative"
    elif total >= 75: level = "Recognized"
    elif total >= 50: level = "Building"
    elif total >= 25: level = "Establishing"
    else:             level = "Getting Started"

    # ── NEXT BEST ACTION ──
    next_action = _score_next_action(foundation, integrity, presence, consistency,
                                      foundation_breakdown, integrity_breakdown,
                                      presence_breakdown, consistency_breakdown)

    return {
        "total":       total,
        "level":       level,
        "pillars": {
            "foundation":  {"score": foundation,  "max": 30, "label": "Foundation",  "breakdown": foundation_breakdown},
            "integrity":   {"score": integrity,   "max": 25, "label": "Integrity",   "breakdown": integrity_breakdown},
            "presence":    {"score": presence,    "max": 30, "label": "Presence",    "breakdown": presence_breakdown},
            "consistency": {"score": consistency, "max": 15, "label": "Consistency", "breakdown": consistency_breakdown},
        },
        "next_action": next_action,
    }


def _score_next_action(f, i, p, c, fb, ib, pb, cb) -> str:
    """Return the single most impactful next action."""
    gaps = []
    if fb.get("bio", {}).get("pts", 0) < 8:
        gaps.append((8 - fb["bio"]["pts"], "Complete your bio — it's the largest single factor in your Foundation score."))
    if fb.get("niches", {}).get("pts", 0) < 6:
        gaps.append((6 - fb["niches"]["pts"], "Select at least two niches to establish your areas of expertise."))
    if fb.get("voice", {}).get("pts", 0) < 6:
        gaps.append((6 - fb["voice"]["pts"], "Define your brand voice — it shapes every piece of content you generate."))
    if pb.get("total_approved", 0) == 0:
        gaps.append((20, "Generate and approve your first piece of content to activate your Presence score."))
    if not pb.get("published_last_7"):
        gaps.append((12, "Approve and publish content this week to maintain an active Presence score."))
    if not cb.get("has_schedule"):
        gaps.append((5, "Set a content schedule so HomeBridge builds your presence automatically."))
    if cb.get("niche_diversity", 0) < 2 and pb.get("total_approved", 0) > 0:
        gaps.append((5, "Generate content across multiple niches to deepen your Consistency score."))

    if not gaps:
        return "Your identity is strong. Keep publishing consistently to maintain your score."

    gaps.sort(key=lambda x: -x[0])
    return gaps[0][1]
