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
        ("role",           "TEXT DEFAULT 'agent'"),
        ("broker_id",      "INTEGER DEFAULT NULL"),
        ("phone",          "TEXT DEFAULT ''"),
        ("plan",           "TEXT DEFAULT 'trial'"),
        ("billing_cycle",  "TEXT DEFAULT 'monthly'"),
        ("sub_status",     "TEXT DEFAULT 'trial'"),
        ("trial_ends_at",  "TEXT DEFAULT NULL"),
        ("stripe_customer_id",     "TEXT DEFAULT NULL"),
        ("stripe_subscription_id", "TEXT DEFAULT NULL"),
        ("agent_slug",          "TEXT DEFAULT NULL"),
        ("is_licensed",         "INTEGER DEFAULT 1"),
        ("staff_type",          "TEXT DEFAULT NULL"),
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

    # Assistant → Agent linking table
    c.execute("""
        CREATE TABLE IF NOT EXISTS assistant_agents (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            assistant_id INTEGER NOT NULL,
            agent_id     INTEGER NOT NULL,
            granted_at   TEXT DEFAULT (datetime('now')),
            granted_by   INTEGER,
            UNIQUE(assistant_id, agent_id),
            FOREIGN KEY (assistant_id) REFERENCES users(id),
            FOREIGN KEY (agent_id)     REFERENCES users(id)
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

    # Audit log — records all privileged support/admin actions
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id   INTEGER NOT NULL,
            action     TEXT    NOT NULL,
            target_id  INTEGER,
            detail     TEXT,
            ip_address TEXT,
            created_at TEXT    DEFAULT (datetime('now'))
        )
    """)

    # Approval tokens — one-time tokenized links for broker/agent content approval (Item #1)
    c.execute("""
        CREATE TABLE IF NOT EXISTS approval_tokens (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            library_item_id INTEGER NOT NULL,
            token           TEXT    NOT NULL UNIQUE,
            action          TEXT    NOT NULL DEFAULT 'approve',
            expires_at      TEXT    NOT NULL,
            used            INTEGER DEFAULT 0,
            created_at      TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id)         REFERENCES users(id),
            FOREIGN KEY (library_item_id) REFERENCES content_library(id)
        )
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# MIGRATIONS
# ─────────────────────────────────────────────
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


def migrate_context_column():
    """
    Adds context column to content_library.
    context = 'agent' (personal real estate content)
              'hb_marketing' (HomeBridge platform content)
    Default is 'agent' for all existing records.
    """
    conn = get_conn()
    c    = conn.cursor()
    try:
        c.execute("ALTER TABLE content_library ADD COLUMN context TEXT DEFAULT 'agent'")
        conn.commit()
        print("[DB] context column added to content_library")
    except Exception:
        pass  # Already exists
    conn.close()


def migrate_content_library_columns():
    """
    Adds missing columns to content_library:
    - cir_id: CIR™ verification record ID
    - image_url: generated image URL
    - compliance_checked_at: timestamp of last compliance re-check
    - edited_at: timestamp of last workspace edit
    Safe to run multiple times — skips columns that already exist.
    """
    conn = get_conn()
    c    = conn.cursor()
    columns = [
        ("cir_id",                "TEXT"),
        ("image_url",             "TEXT"),
        ("compliance_checked_at", "TEXT"),
        ("edited_at",             "TEXT"),
    ]
    for col, coltype in columns:
        try:
            c.execute(f"ALTER TABLE content_library ADD COLUMN {col} {coltype}")
            conn.commit()
            print(f"[DB] Added column {col} to content_library")
        except Exception:
            pass  # Already exists
    conn.close()


def tag_existing_as_marketing(user_id: int):
    """
    One-time migration — tags all existing content for a user as hb_marketing.
    Used for Option A: treat all existing content as marketing context.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        "UPDATE content_library SET context = 'hb_marketing' WHERE user_id = ? AND (context IS NULL OR context = 'agent')",
        (user_id,)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    print(f"[DB] Tagged {affected} existing posts as hb_marketing for user {user_id}")
    return affected


def migrate_roles_to_new_system():
    """
    One-time migration: converts legacy staff_licensed and staff_marketing
    roles to the unified 'admin' role introduced in the new role architecture.
    staff_licensed  → admin (is_licensed=1, staff_type=NULL)
    staff_marketing → admin (is_licensed=0, staff_type=NULL)
    Safe to call on every startup — only updates rows that still have old roles.
    """
    conn = get_conn()
    c    = conn.cursor()
    try:
        c.execute("""
            UPDATE users
            SET role = 'admin', staff_type = NULL
            WHERE role IN ('staff_licensed', 'staff_marketing')
        """)
        affected = c.rowcount
        conn.commit()
        if affected:
            print(f"[DB] Role migration: {affected} user(s) moved to 'admin' role")
    except Exception as e:
        print(f"[DB] Role migration error: {e}")
    finally:
        conn.close()


def migrate_approval_tokens():
    """
    Non-destructive migration — creates approval_tokens table if it doesn't exist.
    Safe to call on every startup.
    """
    conn = get_conn()
    c    = conn.cursor()
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS approval_tokens (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                library_item_id INTEGER NOT NULL,
                token           TEXT    NOT NULL UNIQUE,
                action          TEXT    NOT NULL DEFAULT 'approve',
                expires_at      TEXT    NOT NULL,
                used            INTEGER DEFAULT 0,
                created_at      TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id)         REFERENCES users(id),
                FOREIGN KEY (library_item_id) REFERENCES content_library(id)
            )
        """)
        conn.commit()
        print("[DB] approval_tokens table ready.")
    except Exception as e:
        print(f"[DB] migrate_approval_tokens: {e}")
    finally:
        conn.close()


def log_audit_event(actor_id: int, action: str,
                    target_id: int = None, detail: str = None,
                    ip_address: str = None):
    """
    Write an entry to the audit_log table.
    Called automatically on all support and privileged admin actions.
    actor_id   — the user performing the action
    action     — short string e.g. 'support_view_account', 'support_reset_password'
    target_id  — the user being acted upon (if applicable)
    detail     — optional free-text detail
    ip_address — caller IP if available
    """
    try:
        conn = get_conn()
        conn.execute(
            """INSERT INTO audit_log (actor_id, action, target_id, detail, ip_address)
               VALUES (?, ?, ?, ?, ?)""",
            (actor_id, action, target_id, detail, ip_address)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Audit] Log failed: {e}")


    """Creates platform_connections and platform_posts tables if they don't exist."""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS platform_connections (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL,
            platform          TEXT NOT NULL,
            access_token      TEXT NOT NULL,
            refresh_token     TEXT DEFAULT '',
            expires_at        TEXT DEFAULT '',
            platform_user_id  TEXT DEFAULT '',
            platform_handle   TEXT DEFAULT '',
            connected_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, platform)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS platform_posts (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            library_item_id  INTEGER NOT NULL,
            platform         TEXT NOT NULL,
            post_id          TEXT DEFAULT '',
            post_url         TEXT DEFAULT '',
            posted_at        TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] platform_connections and platform_posts tables ready.")


# ─────────────────────────────────────────────
# PLATFORM CONNECTIONS — OAuth token storage
# ─────────────────────────────────────────────
def save_platform_connection(user_id: int, platform: str, access_token: str,
                              refresh_token: str, expires_at: str,
                              platform_user_id: str, platform_handle: str):
    """Insert or replace a platform OAuth connection for a user."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO platform_connections
            (user_id, platform, access_token, refresh_token, expires_at,
             platform_user_id, platform_handle, connected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, platform) DO UPDATE SET
            access_token     = excluded.access_token,
            refresh_token    = excluded.refresh_token,
            expires_at       = excluded.expires_at,
            platform_user_id = excluded.platform_user_id,
            platform_handle  = excluded.platform_handle,
            connected_at     = datetime('now')
    """, (user_id, platform, access_token, refresh_token, expires_at,
          platform_user_id, platform_handle))
    conn.commit()
    conn.close()


def get_platform_connections(user_id: int) -> list:
    """Get all platform connections for a user — no tokens returned."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT platform, platform_handle, platform_user_id,
               connected_at, expires_at
        FROM platform_connections
        WHERE user_id = ?
        ORDER BY connected_at DESC
    """, (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_platform_connection(user_id: int, platform: str) -> Optional[dict]:
    """Get a single connection including token — backend use only, never send to frontend."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT platform, access_token, refresh_token, expires_at,
               platform_user_id, platform_handle, connected_at
        FROM platform_connections
        WHERE user_id = ? AND platform = ?
    """, (user_id, platform))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_platform_connection(user_id: int, platform: str):
    """Remove a platform connection (disconnect)."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM platform_connections WHERE user_id=? AND platform=?",
              (user_id, platform))
    conn.commit()
    conn.close()


def log_platform_post(user_id: int, library_item_id: int, platform: str,
                       post_id: str, post_url: str):
    """Record a successful platform post in the audit trail (PaperTrail)."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO platform_posts (user_id, library_item_id, platform, post_id, post_url)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, library_item_id, platform, post_id, post_url))
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
                # FIX: check overallStatus (camelCase) — the actual field from ComplianceBadge
                v = str(comp.get("overallStatus") or comp.get("overall_verdict") or comp.get("status") or "").lower()
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


# ─────────────────────────────────────────────
# CONTENT LIBRARY
# ─────────────────────────────────────────────
def library_save(user_id: int, niche: str, content: dict,
                 compliance: dict, source: str = "manual",
                 context: str = "agent") -> dict:
    conn = get_conn()
    c = conn.cursor()
    if context not in ("agent", "hb_marketing"):
        context = "agent"
    c.execute("""
        INSERT INTO content_library
            (user_id, niche, status, content, compliance, source, saved_at, context)
        VALUES (?, ?, 'pending', ?, ?, ?, ?, ?)
    """, (
        user_id, niche,
        json.dumps(content),
        json.dumps(compliance),
        source,
        datetime.utcnow().isoformat(),
        context
    ))
    conn.commit()
    item_id = c.lastrowid
    conn.close()
    return library_get_item(item_id)


def library_get_all(user_id: int, context: str = "agent") -> list:
    """
    Fetch all library items for a user filtered by context.
    context = 'agent'        — personal real estate content
    context = 'hb_marketing' — HomeBridge platform content
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM content_library
        WHERE user_id = ? AND (context = ? OR (context IS NULL AND ? = 'agent'))
        ORDER BY saved_at DESC
    """, (user_id, context, context))
    rows = c.fetchall()
    conn.close()
    return [_row_to_item(r) for r in rows]


def library_get_item(item_id: int, user_id: int = None) -> Optional[dict]:
    conn = get_conn()
    c = conn.cursor()
    if user_id is not None:
        c.execute("SELECT * FROM content_library WHERE id = ? AND user_id = ?", (item_id, user_id))
    else:
        c.execute("SELECT * FROM content_library WHERE id = ?", (item_id,))
    row = c.fetchone()
    conn.close()
    return _row_to_item(row) if row else None


def library_update(item_id: int, user_id: int, updates: dict) -> Optional[dict]:
    """Update status, copiedPlatforms, content, approvedAt, publishedAt.
    When status is set to 'approved', generates a CIR™ ID if one does not
    already exist on this item.
    """
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

    # ── CIR™ generation — write on first approval ──
    # Only create a CIR ID if this update sets status to 'approved'
    # and the item doesn't already have one.
    if updates.get("status") == "approved":
        c.execute(
            "SELECT cir_id FROM content_library WHERE id = ? AND user_id = ?",
            (item_id, user_id)
        )
        existing = c.fetchone()
        if existing and not existing["cir_id"]:
            import secrets as _sec
            cir_date = datetime.utcnow().strftime("%Y%m%d")
            cir_rand = _sec.token_hex(3).upper()  # 6 uppercase hex chars
            cir_id   = f"CIR-{cir_date}-{cir_rand}"
            fields.append("cir_id = ?")
            values.append(cir_id)
            print(f"[CIR] Generated {cir_id} for library item {item_id} (user {user_id})")

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
    ctx = "agent"
    try: ctx = row["context"] or "agent"
    except Exception: pass
    # FIX: include cir_id and image_url — columns exist in DB but were
    # never returned, so the frontend could never display them.
    cir_id    = None
    image_url = None
    try: cir_id    = row["cir_id"]
    except Exception: pass
    try: image_url = row["image_url"]
    except Exception: pass
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
        "context":         ctx,
        "cir_id":          cir_id,
        "image_url":       image_url,
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
    c.execute("SELECT * FROM schedules WHERE user_id = ? AND niche = ?", (user_id, niche))
    row = c.fetchone()
    conn.close()
    return _schedule_row(row)


def schedules_get_all(user_id: int) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM schedules WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [_schedule_row(r) for r in rows]


def schedule_get(user_id: int, niche: str) -> Optional[dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM schedules WHERE user_id = ? AND niche = ?", (user_id, niche))
    row = c.fetchone()
    conn.close()
    return _schedule_row(row) if row else None


def schedules_get_due() -> list:
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        SELECT * FROM schedules
        WHERE active = 1
          AND (next_run IS NULL OR next_run <= ?)
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
# LEGACY — kept for compatibility
# ─────────────────────────────────────────────
def add_content_to_queue(item: dict):
    pass

def get_content_queue():
    return []

def update_content_status(item_id: int, new_status: str):
    pass


# ─────────────────────────────────────────────
# APPROVAL TOKENS — one-time tokenized content approval links (Item #1)
# ─────────────────────────────────────────────
def create_approval_token(user_id: int, library_item_id: int, action: str = "approve") -> str:
    """
    Create a one-time approval token for a library item.
    Token is valid for 7 days — agent may not check immediately.
    Returns the token string to embed in the approval link.
    """
    import secrets as _sec
    from datetime import datetime as _dt, timedelta as _td
    migrate_approval_tokens()
    token      = _sec.token_urlsafe(32)
    expires_at = (_dt.utcnow() + _td(days=7)).isoformat()
    conn = get_conn()
    # Invalidate any existing unused tokens for this item (one active token at a time)
    conn.execute(
        "UPDATE approval_tokens SET used=1 WHERE user_id=? AND library_item_id=? AND used=0",
        (user_id, library_item_id)
    )
    conn.execute(
        "INSERT INTO approval_tokens (user_id, library_item_id, token, action, expires_at) VALUES (?,?,?,?,?)",
        (user_id, library_item_id, token, action, expires_at)
    )
    conn.commit()
    conn.close()
    return token


def validate_approval_token(token: str) -> Optional[dict]:
    """
    Validate a token and return its record if valid and unexpired.
    Returns None if token is invalid, expired, or already used.
    """
    from datetime import datetime as _dt
    migrate_approval_tokens()
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT at.id, at.user_id, at.library_item_id, at.action, at.expires_at,
               u.email, u.agent_name,
               cl.content, cl.compliance, cl.status, cl.niche
        FROM approval_tokens at
        JOIN users u ON u.id = at.user_id
        JOIN content_library cl ON cl.id = at.library_item_id
        WHERE at.token = ? AND at.used = 0
    """, (token,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    try:
        if _dt.utcnow() > _dt.fromisoformat(row["expires_at"]):
            return None
    except Exception:
        return None
    return dict(row)


def consume_approval_token(token: str):
    """Mark a token as used so it cannot be replayed."""
    migrate_approval_tokens()
    conn = get_conn()
    conn.execute("UPDATE approval_tokens SET used=1 WHERE token=?", (token,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# IDENTITY STRENGTH SCORE
# ─────────────────────────────────────────────
def calculate_identity_score(user_id: int, setup: dict) -> dict:
    from datetime import datetime, timedelta
    import json

    conn = get_conn()
    c    = conn.cursor()
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

    # PILLAR 1: Foundation (30 pts)
    name_pts       = 5  if setup.get("agentName", "").strip()   else 0
    market_pts     = 5  if setup.get("market", "").strip()      else 0
    bio_pts        = 8  if len(setup.get("shortBio","").strip()) > 60  else (4 if len(setup.get("shortBio","").strip()) > 20 else 0)
    voice_pts      = 6  if len(setup.get("brandVoice","").strip()) > 30 else (3 if len(setup.get("brandVoice","").strip()) > 10 else 0)
    niches_raw     = setup.get("selectedNiches", [])
    niches         = niches_raw if isinstance(niches_raw, list) else []
    niche_pts      = 6  if len(niches) >= 2 else (3 if len(niches) == 1 else 0)
    desig_raw      = setup.get("designations", [])
    desig_list     = desig_raw if isinstance(desig_raw, list) else []
    desig_pts      = min(len(desig_list) * 2, 8)
    disclaimer     = setup.get("disclaimer", "") or ""
    disclaimer_pts = 4 if len(disclaimer.strip()) > 20 else 0
    areas_raw      = setup.get("serviceAreas", [])
    areas_list     = areas_raw if isinstance(areas_raw, list) else []
    areas_pts      = min(len(areas_list), 4)

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

    # PILLAR 2: Integrity (25 pts)
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
                    # FIX: check overallStatus (camelCase) — the actual field from ComplianceBadge
                    verdict = comp.get("overallStatus") or comp.get("overall_verdict") or comp.get("status") or ""
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
        integrity_breakdown = {"rate": compliance_rate, "passing": compliant_count, "total": total_items}

    # PILLAR 3: Presence (30 pts)
    now     = datetime.utcnow()
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

    any_pts      = 5  if has_any   else 0
    recent7_pts  = 12 if in_last_7 else 0
    recent30_pts = 8  if in_last_30 and not in_last_7 else 0
    volume_pts   = 5  if total_approved >= 5 else (3 if total_approved >= 2 else 0)

    presence = any_pts + recent7_pts + recent30_pts + volume_pts
    presence_breakdown = {
        "total_approved":    total_approved,
        "published_last_7":  in_last_7,
        "published_last_30": in_last_30,
    }

    # PILLAR 4: Consistency (15 pts)
    try:
        conn2 = get_conn()
        c2 = conn2.cursor()
        c2.execute("SELECT COUNT(*) as cnt FROM schedules WHERE user_id = ? AND active = 1", (user_id,))
        sched_row = c2.fetchone()
        conn2.close()
        has_schedule = (sched_row["cnt"] > 0) if sched_row else False
    except Exception:
        has_schedule = False

    niche_diversity = len(set(r["niche"] for r in approved_items if r["niche"])) if approved_items else 0
    weeks_active = 0
    for i in range(4):
        week_start = now - timedelta(days=(i+1)*7)
        week_end   = now - timedelta(days=i*7)
        if any(week_start <= d < week_end for d in published_dates):
            weeks_active += 1

    schedule_pts   = 5 if has_schedule       else 0
    diversity_pts  = 5 if niche_diversity >= 2 else (2 if niche_diversity == 1 else 0)
    regularity_pts = 5 if weeks_active >= 3  else (3 if weeks_active >= 2 else (1 if weeks_active == 1 else 0))

    consistency = schedule_pts + diversity_pts + regularity_pts
    consistency_breakdown = {
        "has_schedule":    has_schedule,
        "niche_diversity": niche_diversity,
        "weeks_active":    weeks_active,
    }

    total = min(foundation + integrity + presence + consistency, 100)

    if total >= 90:   level = "Authoritative"
    elif total >= 75: level = "Recognized"
    elif total >= 50: level = "Building"
    elif total >= 25: level = "Establishing"
    else:             level = "Getting Started"

    next_action = _score_next_action(
        foundation, integrity, presence, consistency,
        foundation_breakdown, integrity_breakdown,
        presence_breakdown, consistency_breakdown
    )

    return {
        "total": total, "level": level,
        "pillars": {
            "foundation":  {"score": foundation,  "max": 30, "label": "Foundation",  "breakdown": foundation_breakdown},
            "integrity":   {"score": integrity,   "max": 25, "label": "Integrity",   "breakdown": integrity_breakdown},
            "presence":    {"score": presence,    "max": 30, "label": "Presence",    "breakdown": presence_breakdown},
            "consistency": {"score": consistency, "max": 15, "label": "Consistency", "breakdown": consistency_breakdown},
        },
        "next_action": next_action,
    }


def _score_next_action(f, i, p, c, fb, ib, pb, cb) -> str:
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
# COMPLIANCE REPORT PDF
# ─────────────────────────────────────────────
def generate_compliance_pdf(
    user_id: int, agent_name: str, brokerage: str, email: str,
    setup: dict, date_from: str = "", date_to: str = "",
) -> bytes:
    import io, json
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.lib import colors

    INK       = colors.HexColor("#0f0f0d")
    INK_2     = colors.HexColor("#3d3d38")
    INK_3     = colors.HexColor("#787870")
    INK_4     = colors.HexColor("#b0afa6")
    BLUE      = colors.HexColor("#1749c9")
    BLUE_DIM  = colors.HexColor("#eef2fb")
    GREEN     = colors.HexColor("#15803d")
    GREEN_DIM = colors.HexColor("#f0fdf4")
    AMBER     = colors.HexColor("#b45309")
    AMBER_DIM = colors.HexColor("#fffbeb")
    RED       = colors.HexColor("#b91c1c")
    RED_DIM   = colors.HexColor("#fef2f2")
    BG        = colors.HexColor("#f5f4f0")
    BORDER    = colors.HexColor("#e8e7e0")
    WHITE     = colors.white

    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT * FROM content_library
        WHERE user_id = ? AND status IN ('approved','published')
        ORDER BY COALESCE(approved_at, saved_at) DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()

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

    total = len(rows)
    passing = review_count = fail_count = 0
    for r in rows:
        try:
            comp = json.loads(r["compliance"]) if isinstance(r["compliance"], str) else r["compliance"]
            v = ""
            if isinstance(comp, dict):
                # FIX: check overallStatus (camelCase) — the actual field from ComplianceBadge
                v = str(comp.get("overallStatus") or comp.get("overall_verdict") or comp.get("status") or "").lower()
                if comp.get("passed") is True: v = "pass"
            if v in ("pass","compliant","ok","green"): passing += 1
            elif v in ("warn","warning","review"):      review_count += 1
            else:                                        fail_count += 1
        except: fail_count += 1

    compliance_rate = round((passing / total) * 100) if total > 0 else 0
    generated_at    = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")

    def S(name, **kw): return ParagraphStyle(name, **kw)
    styles = {
        "label":      S("label",      fontName="Helvetica-Bold", fontSize=8,  textColor=INK_3,  leading=10, spaceAfter=4),
        "h1":         S("h1",         fontName="Helvetica-Bold", fontSize=16, textColor=INK,    leading=20, spaceAfter=4),
        "h2":         S("h2",         fontName="Helvetica-Bold", fontSize=11, textColor=INK,    leading=14, spaceBefore=14, spaceAfter=4),
        "body":       S("body",       fontName="Helvetica",      fontSize=9,  textColor=INK_2,  leading=13, spaceAfter=4),
        "body_small": S("body_small", fontName="Helvetica",      fontSize=8,  textColor=INK_3,  leading=11),
        "cell_bold":  S("cell_bold",  fontName="Helvetica-Bold", fontSize=8,  textColor=INK,    leading=11),
        "cell":       S("cell",       fontName="Helvetica",      fontSize=8,  textColor=INK_2,  leading=11),
        "cell_pass":  S("cell_pass",  fontName="Helvetica-Bold", fontSize=8,  textColor=GREEN,  leading=11),
        "cell_warn":  S("cell_warn",  fontName="Helvetica-Bold", fontSize=8,  textColor=AMBER,  leading=11),
        "cell_fail":  S("cell_fail",  fontName="Helvetica-Bold", fontSize=8,  textColor=RED,    leading=11),
        "footer":     S("footer",     fontName="Helvetica",      fontSize=7,  textColor=INK_4,  leading=10, alignment=TA_CENTER),
    }

    def sp(h=6): return Spacer(1, h)
    def rule(): return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8, spaceBefore=4)
    def truncate(s, n=80):
        s = str(s or "")
        return s[:n] + "…" if len(s) > n else s
    def fmt_date(s):
        if not s: return "—"
        try: return datetime.fromisoformat(s.replace("Z","")).strftime("%b %d, %Y")
        except: return s[:10]

    def compliance_label(comp_raw):
        try:
            comp = json.loads(comp_raw) if isinstance(comp_raw, str) else comp_raw
            if not isinstance(comp, dict): return ("—", "neutral")
            # FIX: check overallStatus (camelCase) — the actual field from ComplianceBadge
            v = str(comp.get("overallStatus") or comp.get("overall_verdict") or comp.get("status") or "").lower()
            if comp.get("passed") is True: v = "pass"
            if v in ("pass","compliant","ok","green"): return ("Verified", "pass")
            if v in ("warn","warning","review"):        return ("Review",   "warn")
            return ("Attention", "fail")
        except: return ("—", "neutral")

    def verdict_para(comp_raw):
        label_text, kind = compliance_label(comp_raw)
        st = {"pass": styles["cell_pass"], "warn": styles["cell_warn"], "fail": styles["cell_fail"]}.get(kind, styles["cell"])
        return Paragraph(label_text, st)

    buf = io.BytesIO()
    W   = letter[0] - 1.3*inch
    doc = SimpleDocTemplate(buf, pagesize=letter,
          leftMargin=0.65*inch, rightMargin=0.65*inch,
          topMargin=0.65*inch, bottomMargin=0.75*inch)
    story = []

    # Header
    hdr = Table([[
        Paragraph('<font name="Helvetica-Bold" size="18" color="#0f0f0d">Home</font><font name="Helvetica-Bold" size="18" color="#1749c9">Bridge</font>', styles["body"]),
        Paragraph('<font color="#787870">Compliance Audit Report</font>', styles["body_small"]),
    ]], colWidths=[W*0.5, W*0.5])
    hdr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(1,0),(1,0),"RIGHT"),("BOTTOMPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0)]))
    story += [hdr, rule(), sp(4)]

    # Agent info
    icw = W/4
    info = Table([[
        Table([[Paragraph("AGENT",styles["label"])],[Paragraph(agent_name or "—",styles["h1"])]],colWidths=[icw-8]),
        Table([[Paragraph("BROKERAGE",styles["label"])],[Paragraph(brokerage or "—",styles["body"])]],colWidths=[icw-8]),
        Table([[Paragraph("EMAIL",styles["label"])],[Paragraph(email or "—",styles["body"])]],colWidths=[icw-8]),
        Table([[Paragraph("GENERATED",styles["label"])],[Paragraph(generated_at,styles["body"])]],colWidths=[icw-8]),
    ]],colWidths=[icw]*4)
    info.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story += [info, sp(12), rule(), sp(4)]

    # Summary tiles
    def tile(lbl, val, col, sub):
        return Table([[Paragraph(lbl,styles["label"])],[Paragraph(str(val),ParagraphStyle("tv",fontName="Helvetica-Bold",fontSize=22,textColor=col,leading=26))],[Paragraph(sub,styles["body_small"])]],colWidths=[(W/4)-8])

    tiles = Table([[
        tile("TOTAL REVIEWED",  total,           BLUE,  "Items in this report"),
        tile("COMPLIANCE RATE", f"{compliance_rate}%", GREEN if compliance_rate>=90 else AMBER if compliance_rate>=75 else RED, "Passed compliance check"),
        tile("VERIFIED",        passing,          GREEN, "Fully compliant"),
        tile("NEEDS ATTENTION", review_count+fail_count, RED if (review_count+fail_count)>0 else INK_4, "Review or attention flagged"),
    ]],colWidths=[(W/4)]*4)
    tiles.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,0),BLUE_DIM),("BACKGROUND",(1,0),(1,0),GREEN_DIM if compliance_rate>=75 else AMBER_DIM),
        ("BACKGROUND",(2,0),(2,0),GREEN_DIM),("BACKGROUND",(3,0),(3,0),RED_DIM if (review_count+fail_count)>0 else BG),
        ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
        ("LINEAFTER",(0,0),(2,0),0.5,BORDER),("BOX",(0,0),(-1,-1),0.5,BORDER),
    ]))
    story += [tiles, sp(16), Paragraph("Content Audit Record", styles["h2"]), sp(4)]

    if total == 0:
        story.append(Paragraph("No approved or published content found for this report period.", styles["body"]))
    else:
        cw = {"date":1.0*inch,"title":2.4*inch,"niche":0.85*inch,"plat":0.9*inch,"verdict":0.75*inch,"approved":1.1*inch}
        tdata = [[Paragraph(h,styles["cell_bold"]) for h in ["DATE SAVED","CONTENT","NICHE","PLATFORMS","COMPLIANCE","APPROVED AT"]]]

        # row_meta tracks (row_index_in_tdata, bg_color, is_notes_subrow) for TableStyle
        row_meta = []
        data_row_idx = 1  # header is row 0

        def _build_notes_text(comp_raw):
            """
            Build the PaperTrail™ verification source string for Item #2.
            Prefers disclosureChecks (new format) then falls back to notes array.
            Format: ✓ pass | Authority  /  ⚠ warn | Authority | Message
            """
            try:
                comp = json.loads(comp_raw) if isinstance(comp_raw, str) else comp_raw
                if not isinstance(comp, dict):
                    return "No compliance data."
                # Prefer disclosureChecks (produced by the rebuilt compliance engine)
                checks = comp.get("disclosureChecks", [])
                if checks:
                    return "  ·  ".join(checks[:12])  # cap at 12 to avoid PDF overflow
                # Fallback: notes array (older records)
                notes = comp.get("notes", [])
                if notes:
                    return "  ·  ".join(str(n) for n in notes[:8])
                return "No detailed rule results available for this item."
            except Exception:
                return "Could not parse compliance data."

        for r in rows:
            try: cd = json.loads(r["content"]) if isinstance(r["content"],str) else r["content"]
            except: cd = {}
            title   = cd.get("headline") or cd.get("title") or cd.get("body","")
            display = truncate(title, 90) or "—"
            try:
                plats    = json.loads(r["copied_platforms"] or "[]")
                plat_str = ", ".join(plats) if plats else "Pending"
            except: plat_str = "Pending"
            _, kind = compliance_label(r["compliance"])
            main_bg  = {"pass":colors.HexColor("#f9fef9"),"warn":colors.HexColor("#fffdf5"),"fail":colors.HexColor("#fff9f9")}.get(kind,WHITE)
            notes_bg = {"pass":colors.HexColor("#f4fdf4"),"warn":colors.HexColor("#fdf9ee"),"fail":colors.HexColor("#fdf4f4")}.get(kind,colors.HexColor("#f8f8f6"))

            # Main content row
            tdata.append([
                Paragraph(fmt_date(r["saved_at"]),styles["cell"]),
                Paragraph(display,styles["cell"]),
                Paragraph(r["niche"] or "—",styles["cell"]),
                Paragraph(truncate(plat_str,40),styles["cell"]),
                verdict_para(r["compliance"]),
                Paragraph(fmt_date(r["approved_at"] or r["published_at"]),styles["cell"]),
            ])
            row_meta.append((data_row_idx, main_bg, False))
            data_row_idx += 1

            # Notes sub-row (Item #2 — PaperTrail™ verification sources)
            notes_text = _build_notes_text(r["compliance"])
            tdata.append([
                Paragraph(notes_text, ParagraphStyle("notes_sub", fontName="Helvetica",
                    fontSize=6.5, textColor=INK_3, leading=9, leftIndent=4)),
                "", "", "", "", ""
            ])
            row_meta.append((data_row_idx, notes_bg, True))
            data_row_idx += 1

        ct = Table(tdata, colWidths=list(cw.values()), repeatRows=1)
        ts = [
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f0eff8")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),7.5),
            ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
            ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("LINEBELOW",(0,0),(-1,0),0.75,BLUE),("BOX",(0,0),(-1,-1),0.5,BORDER),
        ]
        for idx, bg, is_notes in row_meta:
            ts.append(("BACKGROUND",(0,idx),(-1,idx),bg))
            if is_notes:
                ts.append(("SPAN",(0,idx),(5,idx)))
                ts.append(("TOPPADDING",(0,idx),(-1,idx),2))
                ts.append(("BOTTOMPADDING",(0,idx),(-1,idx),5))
                ts.append(("LEFTPADDING",(0,idx),(-1,idx),8))
            else:
                ts.append(("LINEBELOW",(0,idx),(-1,idx),0.3,BORDER))
        ct.setStyle(TableStyle(ts))
        story.append(ct)

    story += [sp(16), rule(), sp(4),
        Paragraph(f"This report was automatically generated by HomeBridge on {generated_at}. "
                  "It reflects all content reviewed and approved by the agent named above. "
                  "All compliance verdicts are generated by HomeBridge's automated compliance engine and do not constitute legal advice. "
                  "This document is intended for internal review and compliance record-keeping purposes.", styles["footer"])]

    doc.build(story)
    return buf.getvalue()


# ─────────────────────────────────────────────
# BROKER OFFICE STATS
# ─────────────────────────────────────────────
def get_broker_office_stats(broker_id: int) -> list:
    import json
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT id, email, agent_name, brokerage, created_at
        FROM users WHERE broker_id=? AND role='agent' AND is_active=1
        ORDER BY agent_name ASC
    """, (broker_id,))
    agents = c.fetchall()
    results = []
    for agent in agents:
        uid = agent["id"]
        c.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status='approved'  THEN 1 ELSE 0 END) as approved,
                   SUM(CASE WHEN status='published' THEN 1 ELSE 0 END) as published,
                   SUM(CASE WHEN status='pending'   THEN 1 ELSE 0 END) as pending,
                   MAX(COALESCE(approved_at, saved_at)) as last_activity
            FROM content_library WHERE user_id=?
        """, (uid,))
        stats = c.fetchone()
        c.execute("SELECT compliance FROM content_library WHERE user_id=? AND status IN ('approved','published')", (uid,))
        passing = 0
        for cr in c.fetchall():
            try:
                comp = json.loads(cr["compliance"]) if isinstance(cr["compliance"],str) else cr["compliance"]
                if isinstance(comp,dict):
                    # FIX: check overallStatus (camelCase) — the actual field from ComplianceBadge
                    v = str(comp.get("overallStatus") or comp.get("overall_verdict") or comp.get("status") or "").lower()
                    if comp.get("passed") is True: v = "pass"
                    if v in ("pass","compliant","ok","green"): passing += 1
            except: pass
        total_reviewed = (stats["approved"] or 0) + (stats["published"] or 0)
        compliance_rate = round((passing/total_reviewed)*100) if total_reviewed>0 else None
        c.execute("SELECT COUNT(*) as cnt FROM schedules WHERE user_id=? AND active=1", (uid,))
        sched = c.fetchone()
        results.append({
            "id": uid, "agent_name": agent["agent_name"], "email": agent["email"],
            "brokerage": agent["brokerage"], "joined": agent["created_at"],
            "total_content": stats["total"] or 0, "pending": stats["pending"] or 0,
            "approved": stats["approved"] or 0, "published": stats["published"] or 0,
            "compliance_rate": compliance_rate,
            "has_schedule": (sched["cnt"]>0) if sched else False,
            "last_activity": stats["last_activity"],
        })
    conn.close()
    return results


# ─────────────────────────────────────────────
# BILLING / SUBSCRIPTION
# ─────────────────────────────────────────────
def get_subscription_status(user_id: int) -> dict:
    from datetime import datetime
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT plan, billing_cycle, sub_status, trial_ends_at, stripe_customer_id, stripe_subscription_id FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row: return {"status": "unknown"}
    status     = row["sub_status"] or "trial"
    trial_ends = row["trial_ends_at"]
    plan       = row["plan"] or "trial"
    if status == "trial" and trial_ends:
        try:
            if datetime.utcnow() > datetime.fromisoformat(trial_ends):
                status = "expired"
                conn2 = get_conn()
                conn2.execute("UPDATE users SET sub_status=? WHERE id=?", ("expired", user_id))
                conn2.commit(); conn2.close()
        except Exception: pass
    days_left = None
    if status == "trial" and trial_ends:
        try:
            delta = datetime.fromisoformat(trial_ends) - datetime.utcnow()
            days_left = max(0, delta.days)
        except Exception: pass
    return {
        "status": status, "plan": plan,
        "billing_cycle": row["billing_cycle"] or "monthly",
        "trial_ends_at": trial_ends, "days_left": days_left,
        "stripe_customer_id": row["stripe_customer_id"],
        "stripe_subscription_id": row["stripe_subscription_id"],
    }

def set_trial(user_id: int, days: int = 14):
    from datetime import datetime, timedelta
    trial_ends = (datetime.utcnow() + timedelta(days=days)).isoformat()
    conn = get_conn()
    conn.execute("UPDATE users SET plan='trial', sub_status='trial', trial_ends_at=? WHERE id=?", (trial_ends, user_id))
    conn.commit(); conn.close()

def activate_subscription(user_id: int, plan: str, billing_cycle: str,
                           stripe_customer_id: str, stripe_subscription_id: str):
    conn = get_conn()
    conn.execute("UPDATE users SET plan=?, billing_cycle=?, sub_status='active', stripe_customer_id=?, stripe_subscription_id=? WHERE id=?",
                 (plan, billing_cycle, stripe_customer_id, stripe_subscription_id, user_id))
    conn.commit(); conn.close()

def cancel_subscription(user_id: int):
    conn = get_conn()
    conn.execute("UPDATE users SET sub_status='cancelled', stripe_subscription_id=NULL WHERE id=?", (user_id,))
    conn.commit(); conn.close()


# ─────────────────────────────────────────────
# PASSWORD RESET
# ─────────────────────────────────────────────
def init_reset_tokens_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit(); conn.close()

def create_reset_token(user_id: int) -> str:
    import secrets
    from datetime import datetime, timedelta
    init_reset_tokens_table()
    conn = get_conn()
    conn.execute("UPDATE password_reset_tokens SET used=1 WHERE user_id=? AND used=0", (user_id,))
    token      = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    conn.execute("INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?,?,?)", (user_id, token, expires_at))
    conn.commit(); conn.close()
    return token

def validate_reset_token(token: str) -> Optional[dict]:
    from datetime import datetime
    init_reset_tokens_table()
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT rt.user_id, rt.expires_at, u.email, u.agent_name
        FROM password_reset_tokens rt
        JOIN users u ON u.id = rt.user_id
        WHERE rt.token=? AND rt.used=0
    """, (token,))
    row = c.fetchone()
    conn.close()
    if not row: return None
    try:
        if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]): return None
    except Exception: return None
    return dict(row)

def consume_reset_token(token: str):
    init_reset_tokens_table()
    conn = get_conn()
    conn.execute("UPDATE password_reset_tokens SET used=1 WHERE token=?", (token,))
    conn.commit(); conn.close()

def update_password(user_id: int, new_password_hash: str):
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_password_hash, user_id))
    conn.commit(); conn.close()
