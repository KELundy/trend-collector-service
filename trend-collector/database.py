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
            role TEXT DEFAULT 'agent',
            broker_id INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Non-destructive migrations for existing deployments
    for col, defn in [
        ("role",      "TEXT DEFAULT 'agent'"),
        ("broker_id", "INTEGER DEFAULT NULL"),
        ("phone",     "TEXT DEFAULT ''"),
    ]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
        except Exception:
            pass  # Column already exists

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

    # Agent setup — stores identity/profile data server-side
    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_setup (
            user_id INTEGER PRIMARY KEY,
            setup_json TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS demo_tokens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            token       TEXT    NOT NULL UNIQUE,
            label       TEXT    NOT NULL,
            created_by  INTEGER NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now')),
            open_count  INTEGER DEFAULT 0,
            last_opened TEXT,
            ip_log      TEXT    DEFAULT '[]'
        )
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# AGENT SETUP (server-side identity storage)
# ─────────────────────────────────────────────
def save_agent_setup(user_id: int, setup: dict):
    """Save or update agent setup/identity data server-side."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO agent_setup (user_id, setup_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            setup_json = excluded.setup_json,
            updated_at = excluded.updated_at
    """, (user_id, json.dumps(setup), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def get_agent_setup(user_id: int) -> dict:
    """Get agent setup/identity data from DB."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return {}
    try:
        return json.loads(row["setup_json"])
    except Exception:
        return {}


def get_user_results(user_id: int) -> dict:
    """Return real metrics for the Results panel."""
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) as cnt FROM content_library WHERE user_id = ?", (user_id,))
    total_generated = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM content_library WHERE user_id = ? AND status = 'published'", (user_id,))
    total_published = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM content_library WHERE user_id = ? AND status = 'pending'", (user_id,))
    total_pending = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM content_library WHERE user_id = ? AND status IN ('approved','published')", (user_id,))
    total_approved = c.fetchone()["cnt"]

    c.execute("SELECT copied_platforms FROM content_library WHERE user_id = ? AND copied_platforms IS NOT NULL", (user_id,))
    all_platforms = set()
    for row in c.fetchall():
        try:
            plats = json.loads(row["copied_platforms"]) if isinstance(row["copied_platforms"], str) else row["copied_platforms"]
            if isinstance(plats, list):
                all_platforms.update(plats)
        except Exception:
            pass

    c.execute("SELECT compliance FROM content_library WHERE user_id = ? AND status IN ('approved','published')", (user_id,))
    passing = 0
    comp_rows = c.fetchall()
    for row in comp_rows:
        try:
            comp = json.loads(row["compliance"]) if isinstance(row["compliance"], str) else row["compliance"]
            if isinstance(comp, dict):
                v = str(comp.get("overall_verdict") or comp.get("status") or "").lower()
                if comp.get("passed") is True: v = "pass"
                if v in ("pass","compliant","ok","green"): passing += 1
        except Exception:
            pass
    compliance_rate = round((passing / total_approved) * 100) if total_approved > 0 else None

    c.execute("SELECT COUNT(*) as cnt FROM schedules WHERE user_id = ? AND active = 1", (user_id,))
    active_schedules = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM content_library WHERE user_id = ? AND saved_at >= datetime('now', '-7 days')", (user_id,))
    this_week = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM content_library WHERE user_id = ? AND saved_at >= datetime('now', '-30 days')", (user_id,))
    this_month = c.fetchone()["cnt"]

    c.execute("""
        SELECT niche, COUNT(*) as total,
               SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published
        FROM content_library WHERE user_id = ?
        GROUP BY niche ORDER BY total DESC
    """, (user_id,))
    niche_breakdown = [
        {"niche": r["niche"], "total": r["total"], "published": r["published"]}
        for r in c.fetchall() if r["niche"]
    ]

    c.execute("SELECT saved_at FROM content_library WHERE user_id = ? ORDER BY saved_at DESC LIMIT 1", (user_id,))
    last_row = c.fetchone()
    last_activity = last_row["saved_at"] if last_row else None

    conn.close()
    return {
        "total_generated":  total_generated,
        "total_published":  total_published,
        "total_pending":    total_pending,
        "total_approved":   total_approved,
        "platforms_reached": len(all_platforms),
        "platform_list":    sorted(list(all_platforms)),
        "compliance_rate":  compliance_rate,
        "active_schedules": active_schedules,
        "this_week":        this_week,
        "this_month":       this_month,
        "niche_breakdown":  niche_breakdown,
        "last_activity":    last_activity,
    }


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

    # Designations — up to 8 pts (2 per designation, max 4 designations)
    desig_raw  = setup.get("designations", [])
    desig_list = desig_raw if isinstance(desig_raw, list) else []
    desig_pts  = min(len(desig_list) * 2, 8)

    # Disclaimer filled — 4 pts (required for full compliance credibility)
    disclaimer     = setup.get("disclaimer", "") or ""
    disclaimer_pts = 4 if len(disclaimer.strip()) > 20 else 0

    # Service areas — up to 4 pts (1 per area, max 4)
    areas_raw  = setup.get("serviceAreas", [])
    areas_list = areas_raw if isinstance(areas_raw, list) else []
    areas_pts  = min(len(areas_list), 4)

    foundation = name_pts + market_pts + bio_pts + voice_pts + niche_pts + desig_pts + disclaimer_pts + areas_pts
    foundation_breakdown = {
        "name":        {"pts": name_pts,       "max": 5,  "label": "Name"},
        "market":      {"pts": market_pts,      "max": 5,  "label": "Primary Market"},
        "bio":         {"pts": bio_pts,         "max": 8,  "label": "Bio"},
        "voice":       {"pts": voice_pts,       "max": 6,  "label": "Brand Voice"},
        "niches":      {"pts": niche_pts,       "max": 6,  "label": "Niches"},
        "designations":{"pts": desig_pts,       "max": 8,  "label": "Professional Designations"},
        "disclaimer":  {"pts": disclaimer_pts,  "max": 4,  "label": "Broker Disclaimer"},
        "areas":       {"pts": areas_pts,       "max": 4,  "label": "Service Areas"},
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


# ─────────────────────────────────────────────
# COMPLIANCE REPORT PDF GENERATOR
# ─────────────────────────────────────────────

def generate_compliance_pdf(
    user_id: int,
    agent_name: str,
    brokerage: str,
    email: str,
    setup: dict,
    date_from: str = "",
    date_to:   str = "",
) -> bytes:
    """
    Generate a compliance audit report PDF.
    Returns raw PDF bytes ready to stream.
    """
    import io
    import json
    from datetime import datetime

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether,
    )
    from reportlab.lib import colors

    # ── DESIGN TOKENS ──
    INK        = colors.HexColor("#0f0f0d")
    INK_2      = colors.HexColor("#3d3d38")
    INK_3      = colors.HexColor("#787870")
    INK_4      = colors.HexColor("#b0afa6")
    BLUE       = colors.HexColor("#1749c9")
    BLUE_DIM   = colors.HexColor("#eef2fb")
    GREEN      = colors.HexColor("#15803d")
    GREEN_DIM  = colors.HexColor("#f0fdf4")
    AMBER      = colors.HexColor("#b45309")
    AMBER_DIM  = colors.HexColor("#fffbeb")
    RED        = colors.HexColor("#b91c1c")
    RED_DIM    = colors.HexColor("#fef2f2")
    BG         = colors.HexColor("#f5f4f0")
    WHITE      = colors.white
    BORDER     = colors.HexColor("#e8e7e0")

    # ── FETCH LIBRARY ITEMS ──
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT * FROM content_library
        WHERE user_id = ?
        AND status IN ('approved', 'published')
        ORDER BY COALESCE(approved_at, saved_at) DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()

    # Optional date filter
    def parse_dt(s):
        if not s: return None
        try: return datetime.fromisoformat(s.replace("Z",""))
        except: return None

    dt_from = parse_dt(date_from)
    dt_to   = parse_dt(date_to)

    if dt_from or dt_to:
        filtered = []
        for r in rows:
            d = parse_dt(r["approved_at"] or r["saved_at"])
            if d:
                if dt_from and d < dt_from: continue
                if dt_to   and d > dt_to:   continue
            filtered.append(r)
        rows = filtered

    # ── COMPLIANCE STATS ──
    total        = len(rows)
    passing      = 0
    review_count = 0
    fail_count   = 0

    for r in rows:
        try:
            comp = json.loads(r["compliance"]) if isinstance(r["compliance"], str) else r["compliance"]
            v = ""
            if isinstance(comp, dict):
                v = str(comp.get("overall_verdict") or comp.get("status") or "").lower()
                if comp.get("passed") is True: v = "pass"
            if v in ("pass","compliant","ok","green"): passing += 1
            elif v in ("warn","warning","review"):      review_count += 1
            else:                                        fail_count += 1
        except:
            fail_count += 1

    compliance_rate = round((passing / total) * 100) if total > 0 else 0
    generated_at    = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")
    report_date     = datetime.utcnow().strftime("%Y-%m-%d")

    # ── STYLES ──
    def style(name, **kw):
        return ParagraphStyle(name, **kw)

    S = {
        "logo":        style("logo",        fontName="Helvetica-Bold", fontSize=18, textColor=INK,   leading=22),
        "logo_blue":   style("logo_blue",   fontName="Helvetica-Bold", fontSize=18, textColor=BLUE,  leading=22),
        "label":       style("label",       fontName="Helvetica-Bold", fontSize=8,  textColor=INK_3, leading=10, spaceAfter=4),
        "h1":          style("h1",          fontName="Helvetica-Bold", fontSize=16, textColor=INK,   leading=20, spaceAfter=4),
        "h2":          style("h2",          fontName="Helvetica-Bold", fontSize=11, textColor=INK,   leading=14, spaceBefore=14, spaceAfter=4),
        "body":        style("body",        fontName="Helvetica",      fontSize=9,  textColor=INK_2, leading=13, spaceAfter=4),
        "body_small":  style("body_small",  fontName="Helvetica",      fontSize=8,  textColor=INK_3, leading=11),
        "cell_bold":   style("cell_bold",   fontName="Helvetica-Bold", fontSize=8,  textColor=INK,   leading=11),
        "cell":        style("cell",        fontName="Helvetica",      fontSize=8,  textColor=INK_2, leading=11),
        "cell_pass":   style("cell_pass",   fontName="Helvetica-Bold", fontSize=8,  textColor=GREEN, leading=11),
        "cell_warn":   style("cell_warn",   fontName="Helvetica-Bold", fontSize=8,  textColor=AMBER, leading=11),
        "cell_fail":   style("cell_fail",   fontName="Helvetica-Bold", fontSize=8,  textColor=RED,   leading=11),
        "cell_blue":   style("cell_blue",   fontName="Helvetica-Bold", fontSize=8,  textColor=BLUE,  leading=11),
        "footer":      style("footer",      fontName="Helvetica",      fontSize=7,  textColor=INK_4, leading=10, alignment=TA_CENTER),
    }

    # ── HELPERS ──
    def rule(color=BORDER, thickness=0.5):
        return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=8, spaceBefore=4)

    def sp(h=6):
        return Spacer(1, h)

    def compliance_label(comp_raw):
        try:
            comp = json.loads(comp_raw) if isinstance(comp_raw, str) else comp_raw
            if not isinstance(comp, dict): return ("—", "neutral")
            v = str(comp.get("overall_verdict") or comp.get("status") or "").lower()
            if comp.get("passed") is True: v = "pass"
            if v in ("pass","compliant","ok","green"): return ("Verified", "pass")
            if v in ("warn","warning","review"):        return ("Review",   "warn")
            return ("Attention", "fail")
        except:
            return ("—", "neutral")

    def verdict_para(comp_raw):
        label_text, kind = compliance_label(comp_raw)
        st = {"pass": S["cell_pass"], "warn": S["cell_warn"], "fail": S["cell_fail"]}.get(kind, S["cell"])
        return Paragraph(label_text, st)

    def fmt_date(s):
        if not s: return "—"
        try:
            dt = datetime.fromisoformat(s.replace("Z",""))
            return dt.strftime("%b %d, %Y %I:%M %p")
        except: return s[:16] if s else "—"

    def truncate(s, n=80):
        if not s: return ""
        s = str(s)
        return s[:n] + "…" if len(s) > n else s

    # ── BUILD DOCUMENT ──
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.65*inch,  bottomMargin=0.75*inch,
    )
    W = letter[0] - 1.3*inch  # content width

    story = []

    # ── HEADER ──
    header_data = [[
        Paragraph('<font name="Helvetica-Bold" size="18" color="#0f0f0d">Home</font>'
                  '<font name="Helvetica-Bold" size="18" color="#1749c9">Bridge</font>', S["body"]),
        Paragraph(f'<font color="#787870">Compliance Audit Report</font>', S["body_small"]),
    ]]
    header_table = Table(header_data, colWidths=[W*0.5, W*0.5])
    header_table.setStyle(TableStyle([
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",       (1,0), (1,0),   "RIGHT"),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
        ("TOPPADDING",  (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(rule(BORDER, 1))

    # ── AGENT INFO ROW ──
    story.append(sp(4))
    info_data = [[
        [Paragraph("AGENT", S["label"]),  Paragraph(agent_name or "—", S["h1"])],
        [Paragraph("BROKERAGE", S["label"]), Paragraph(brokerage or "—", S["body"])],
        [Paragraph("EMAIL", S["label"]),  Paragraph(email or "—", S["body"])],
        [Paragraph("GENERATED", S["label"]), Paragraph(generated_at, S["body"])],
    ]]
    info_col_w = W / 4
    info_table = Table([[
        Table([[Paragraph("AGENT", S["label"])], [Paragraph(agent_name or "—", S["h1"])]], colWidths=[info_col_w-8]),
        Table([[Paragraph("BROKERAGE", S["label"])], [Paragraph(brokerage or "—", S["body"])]], colWidths=[info_col_w-8]),
        Table([[Paragraph("EMAIL", S["label"])], [Paragraph(email or "—", S["body"])]], colWidths=[info_col_w-8]),
        Table([[Paragraph("REPORT DATE", S["label"])], [Paragraph(generated_at, S["body"])]], colWidths=[info_col_w-8]),
    ]], colWidths=[info_col_w]*4)
    info_table.setStyle(TableStyle([
        ("VALIGN",  (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING",   (0,0), (-1,-1), 0),
        ("BOTTOMPADDING",(0,0), (-1,-1), 0),
    ]))
    story.append(info_table)
    story.append(sp(12))
    story.append(rule())

    # ── SUMMARY TILES ──
    story.append(sp(4))
    def summary_tile(top_label, value, value_color, sub_label):
        return Table([
            [Paragraph(top_label, S["label"])],
            [Paragraph(str(value), ParagraphStyle("tv", fontName="Helvetica-Bold", fontSize=22, textColor=value_color, leading=26))],
            [Paragraph(sub_label, S["body_small"])],
        ], colWidths=[(W/4)-8])

    tiles = Table([[
        summary_tile("TOTAL REVIEWED",    total,            BLUE,  "Items in this report"),
        summary_tile("COMPLIANCE RATE",   f"{compliance_rate}%", GREEN if compliance_rate >= 90 else AMBER if compliance_rate >= 75 else RED, "Passed compliance check"),
        summary_tile("VERIFIED",          passing,          GREEN, "Items fully compliant"),
        summary_tile("NEEDS ATTENTION",   review_count + fail_count, RED if (review_count+fail_count)>0 else INK_4, "Review or attention flagged"),
    ]], colWidths=[(W/4)]*4)
    tiles.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (0,0), BLUE_DIM),
        ("BACKGROUND",   (1,0), (1,0), GREEN_DIM if compliance_rate >= 75 else AMBER_DIM),
        ("BACKGROUND",   (2,0), (2,0), GREEN_DIM),
        ("BACKGROUND",   (3,0), (3,0), RED_DIM if (review_count+fail_count)>0 else BG),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [None]),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING",   (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0), (-1,-1), 10),
        ("LINEAFTER",    (0,0), (2,0),   0.5, BORDER),
        ("BOX",          (0,0), (-1,-1), 0.5, BORDER),
    ]))
    story.append(tiles)
    story.append(sp(16))

    # ── CONTENT TABLE ──
    story.append(Paragraph("Content Audit Record", S["h2"]))
    story.append(sp(4))

    if total == 0:
        story.append(Paragraph(
            "No approved or published content found for this report period.",
            S["body"]
        ))
    else:
        # Column widths
        cw = {
            "date":      1.0*inch,
            "title":     2.4*inch,
            "niche":     0.85*inch,
            "platforms": 0.9*inch,
            "verdict":   0.75*inch,
            "approved":  1.1*inch,
        }

        col_headers = [
            Paragraph("DATE SAVED",    S["cell_bold"]),
            Paragraph("CONTENT",       S["cell_bold"]),
            Paragraph("NICHE",         S["cell_bold"]),
            Paragraph("PLATFORMS",     S["cell_bold"]),
            Paragraph("COMPLIANCE",    S["cell_bold"]),
            Paragraph("APPROVED AT",   S["cell_bold"]),
        ]

        table_data = [col_headers]
        row_colors = []

        for i, r in enumerate(rows):
            try:
                content_dict = json.loads(r["content"]) if isinstance(r["content"], str) else r["content"]
            except: content_dict = {}

            title = (
                content_dict.get("headline") or
                content_dict.get("title") or
                content_dict.get("hook") or
                content_dict.get("subject") or
                ""
            )
            body_text = (
                content_dict.get("body") or
                content_dict.get("caption") or
                content_dict.get("content") or
                ""
            )
            display = truncate(title or body_text, 90) or "—"

            platforms_raw = r["copied_platforms"] or "[]"
            try:
                platforms = json.loads(platforms_raw) if isinstance(platforms_raw, str) else platforms_raw
                plat_str  = ", ".join(platforms) if platforms else "Pending"
            except: plat_str = "Pending"

            _, comp_kind = compliance_label(r["compliance"])
            row_bg = {
                "pass":    colors.HexColor("#f9fef9"),
                "warn":    colors.HexColor("#fffdf5"),
                "fail":    colors.HexColor("#fff9f9"),
                "neutral": WHITE,
            }.get(comp_kind, WHITE)
            row_colors.append(row_bg)

            table_data.append([
                Paragraph(fmt_date(r["saved_at"])[:12], S["cell"]),
                Paragraph(display, S["cell"]),
                Paragraph(r["niche"] or "—", S["cell"]),
                Paragraph(truncate(plat_str, 40), S["cell"]),
                verdict_para(r["compliance"]),
                Paragraph(fmt_date(r["approved_at"] or r["published_at"]), S["cell"]),
            ])

        content_table = Table(
            table_data,
            colWidths=list(cw.values()),
            repeatRows=1,
        )

        ts = [
            # Header row
            ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#f0eff8")),
            ("TEXTCOLOR",     (0,0), (-1,0),  INK),
            ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,0),  7.5),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE]),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
            ("RIGHTPADDING",  (0,0), (-1,-1), 5),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LINEBELOW",     (0,0), (-1,0),  0.75, BLUE),
            ("LINEBELOW",     (0,1), (-1,-1), 0.3,  BORDER),
            ("BOX",           (0,0), (-1,-1), 0.5,  BORDER),
        ]
        # Per-row background colors
        for idx, bg in enumerate(row_colors):
            ts.append(("BACKGROUND", (0, idx+1), (-1, idx+1), bg))

        content_table.setStyle(TableStyle(ts))
        story.append(content_table)

    story.append(sp(16))
    story.append(rule())

    # ── FOOTER ATTESTATION ──
    story.append(sp(4))
    story.append(Paragraph(
        f"This report was automatically generated by HomeBridge on {generated_at}. "
        f"It reflects all content reviewed and approved by the agent named above. "
        f"All compliance verdicts are generated by HomeBridge's automated compliance engine and do not constitute legal advice. "
        f"This document is intended for internal review and compliance record-keeping purposes.",
        S["footer"]
    ))

    # ── BUILD ──
    doc.build(story)
    return buf.getvalue()


# ─────────────────────────────────────────────
# BROKER OFFICE FUNCTIONS
# ─────────────────────────────────────────────

def get_broker_office_stats(broker_id: int) -> list:
    """
    For each agent under broker_id, return their content stats
    and identity score inputs so the broker dashboard can render
    without hitting the score endpoint per-agent.
    """
    import json

    conn = get_conn()
    c    = conn.cursor()

    # Get all agents under this broker
    c.execute("""
        SELECT id, email, agent_name, brokerage, created_at
        FROM users
        WHERE broker_id = ? AND role = 'agent' AND is_active = 1
        ORDER BY agent_name ASC
    """, (broker_id,))
    agents = c.fetchall()

    results = []
    for agent in agents:
        uid = agent["id"]

        # Content stats
        c.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'approved'  THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
                SUM(CASE WHEN status = 'pending'   THEN 1 ELSE 0 END) as pending,
                MAX(COALESCE(approved_at, saved_at)) as last_activity
            FROM content_library
            WHERE user_id = ?
        """, (uid,))
        stats = c.fetchone()

        # Compliance rate
        c.execute("""
            SELECT compliance FROM content_library
            WHERE user_id = ? AND status IN ('approved','published')
        """, (uid,))
        comp_rows = c.fetchall()

        passing = 0
        for cr in comp_rows:
            try:
                comp = json.loads(cr["compliance"]) if isinstance(cr["compliance"], str) else cr["compliance"]
                if isinstance(comp, dict):
                    v = str(comp.get("overall_verdict") or comp.get("status") or "").lower()
                    if comp.get("passed") is True: v = "pass"
                    if v in ("pass","compliant","ok","green"): passing += 1
            except: pass

        total_reviewed = (stats["approved"] or 0) + (stats["published"] or 0)
        compliance_rate = round((passing / total_reviewed) * 100) if total_reviewed > 0 else None

        # Active schedule?
        c.execute("SELECT COUNT(*) as cnt FROM schedules WHERE user_id = ? AND active = 1", (uid,))
        sched = c.fetchone()
        has_schedule = (sched["cnt"] > 0) if sched else False

        results.append({
            "id":              uid,
            "agent_name":      agent["agent_name"],
            "email":           agent["email"],
            "brokerage":       agent["brokerage"],
            "joined":          agent["created_at"],
            "total_content":   stats["total"] or 0,
            "pending":         stats["pending"] or 0,
            "approved":        stats["approved"] or 0,
            "published":       stats["published"] or 0,
            "compliance_rate": compliance_rate,
            "has_schedule":    has_schedule,
            "last_activity":   stats["last_activity"],
        })

    conn.close()
    return results
