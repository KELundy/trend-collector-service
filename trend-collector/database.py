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
# PRIVATE HELPERS
# ─────────────────────────────────────────────

def _compliance_verdict(comp_raw) -> str:
    """
    Parse raw compliance JSON and return a normalized verdict string.
    Centralizes the compliance-parsing logic that was previously duplicated
    in 6 separate functions (get_user_results, generate_compliance_pdf,
    get_broker_office_stats, get_team_stats, get_broker_agent_content).

    Returns: 'pass' | 'warn' | 'fail' | 'pending'

    Actual overallStatus values from ComplianceBadge (content_engine.py):
      "reviewed"            → pass  (no issues detected)
      "review-recommended"  → warn  (one or more warn-level flags)
      "attention-required"  → fail  (one or more fail-level flags)
    Legacy / fallback values are also handled for backward compatibility.
    """
    try:
        comp = json.loads(comp_raw) if isinstance(comp_raw, str) else comp_raw
        if not isinstance(comp, dict):
            return "pending"
        v = str(comp.get("overallStatus") or comp.get("overall_verdict") or comp.get("status") or "").lower()
        if comp.get("passed") is True:
            v = "pass"
        # Current ComplianceBadge values (content_engine.py _build_final_badge)
        if v == "reviewed":
            return "pass"
        if v == "review-recommended":
            return "warn"
        if v == "attention-required":
            return "fail"
        # Legacy / fallback values
        if v in ("pass", "compliant", "ok", "green"):
            return "pass"
        if v in ("warn", "warning", "review"):
            return "warn"
        if v in ("attention", "fail", "error"):
            return "fail"
        return "pending"
    except Exception:
        return "pending"


def _calc_lightweight_identity(c, uid: int, compliance_rate, published_count: int) -> int:
    """
    Compute a lightweight identity score (0-100) for broker/team dashboards.
    Uses agent_setup JSON + published count + compliance rate.
    Centralizes logic previously duplicated in get_broker_office_stats
    and get_team_stats.
    Internal use only — never exposed to agents in UI.
    """
    score = 0
    try:
        c.execute("SELECT setup_json FROM agent_setup WHERE user_id=?", (uid,))
        sr = c.fetchone()
        if sr:
            setup = json.loads(sr["setup_json"] or "{}")
            if setup.get("shortBio", "").strip():   score += 15
            if setup.get("market", "").strip():      score += 10
            niches = setup.get("primaryNiches", [])
            score += 10 if len(niches) >= 2 else (5 if len(niches) == 1 else 0)
            if setup.get("brandVoice", "").strip():  score += 5
        score += 30 if published_count >= 5 else (20 if published_count >= 2 else (10 if published_count >= 1 else 0))
        if compliance_rate is not None:
            score += 30 if compliance_rate == 100 else (22 if compliance_rate >= 90 else (12 if compliance_rate >= 75 else 0))
        score = min(score, 100)
    except Exception:
        pass
    return score


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
        ("role",                   "TEXT DEFAULT 'agent'"),
        ("broker_id",              "INTEGER DEFAULT NULL"),
        ("phone",                  "TEXT DEFAULT ''"),
        ("plan",                   "TEXT DEFAULT 'trial'"),
        ("billing_cycle",          "TEXT DEFAULT 'monthly'"),
        ("sub_status",             "TEXT DEFAULT 'trial'"),
        ("trial_ends_at",          "TEXT DEFAULT NULL"),
        ("stripe_customer_id",     "TEXT DEFAULT NULL"),
        ("stripe_subscription_id", "TEXT DEFAULT NULL"),
        ("agent_slug",             "TEXT DEFAULT NULL"),
        ("is_licensed",            "INTEGER DEFAULT 1"),
        ("staff_type",             "TEXT DEFAULT NULL"),
        ("team_id",                "INTEGER DEFAULT NULL"),
        ("notification_email",     "TEXT DEFAULT NULL"),
        # Usage limits — added Session 5
        ("generation_count",       "INTEGER DEFAULT 0"),
        ("generation_reset_date",  "TEXT DEFAULT NULL"),
        ("monthly_limit",          "INTEGER DEFAULT 30"),
        # Approved post tracking — primary billing unit (Session 36)
        # approved_post_count: posts approved (CIR issued) this billing period
        # generation_backstop_count: raw generations this billing period (abuse guard)
        # billing_reset_day: day-of-month the agent's billing cycle resets (1-28)
        # addon_posts_limit: extra approved posts from purchased Add-on Packs this period
        # addon_backstop_limit: extra backstop credits from Add-on Packs this period
        # last_generation_hash: MD5 of last generation inputs — detects free regenerations
        ("approved_post_count",      "INTEGER DEFAULT 0"),
        ("generation_backstop_count","INTEGER DEFAULT 0"),
        ("billing_reset_day",        "INTEGER DEFAULT 1"),
        ("addon_posts_limit",        "INTEGER DEFAULT 0"),
        ("addon_backstop_limit",     "INTEGER DEFAULT 0"),
        ("last_generation_hash",     "TEXT DEFAULT NULL"),
        # Partner Program — added Session 12
        ("partner_tier",           "TEXT DEFAULT NULL"),
        ("partner_code",           "TEXT DEFAULT NULL"),
        # Organizational identity — added Session 18 (ADD v6 §2.6)
        # solo | member | lead | broker — professional configuration type
        # Does NOT replace the role field. Drives organizational feature activation only.
        ("org_config",             "TEXT DEFAULT NULL"),
        # HB Marketing profile — added Session 46
        # Stores HomeBridge company identity (voice, niches, market) separately from
        # agent_setup so switching to the marketing context never contaminates the
        # agent's personal profile. NULL until first save from marketing context.
        ("hb_marketing_setup_json","TEXT DEFAULT NULL"),
        # VIDEO IDENTITY — added Session 49
        # has_profile_photo: 1 = photo stored on persistent disk at
        #   /data/profile_photos/{user_id}.jpg — served via GET /profile/photo/{user_id}
        # profile_photo_updated_at: timestamp of last photo upload
        # heygen_avatar_id: HeyGen Instant Avatar ID — NULL until agent activates
        #   their Video Identity upgrade. When populated, used in place of photo avatar.
        # video_consent_at: timestamp when agent consented to likeness use for video.
        #   Required before any video render. Must be recorded before building
        #   the Instant Avatar upgrade flow (future session).
        # video_month_count: videos rendered (including regenerations) this calendar month.
        #   Resets on the 1st of each month. This is the primary video billing counter.
        # video_month_reset: ISO datetime of next monthly video counter reset.
        # addon_video_limit: extra video renders from purchased Video Top-up Packs.
        #   +10 per pack purchased. Stacks. Resets with video_month_count on billing reset.
        ("has_profile_photo",        "INTEGER DEFAULT 0"),
        ("profile_photo_updated_at", "TEXT DEFAULT NULL"),
        ("heygen_avatar_id",         "TEXT DEFAULT NULL"),
        ("video_consent_at",         "TEXT DEFAULT NULL"),
        ("video_month_count",        "INTEGER DEFAULT 0"),
        ("video_month_reset",        "TEXT DEFAULT NULL"),
        ("addon_video_limit",        "INTEGER DEFAULT 0"),
        # heygen_photo_avatar_id — added Session 50
        # Stores the talking_photo_id returned by HeyGen after one-time Photo Avatar
        # creation via POST /v3/avatars. Created on first render, reused on all
        # subsequent renders so we never re-upload or re-create the avatar.
        # NULL until agent's first video render completes the setup step.
        # Cleared when agent deletes their profile photo (consent withdrawal).
        ("heygen_photo_avatar_id",   "TEXT DEFAULT NULL"),
        # VOICE IDENTITY — added Session 51
        # lmnt_voice_id: voice clone ID returned by LMNT after agent submits
        #   a voice recording. Used at render time to synthesize the script into
        #   an audio file via LMNT, which is then passed to HeyGen as audio_url
        #   instead of a stock voice_id. NULL until agent completes voice setup.
        #   Cleared when agent deletes their voice (GDPR/CCPA requirement).
        #   Never exposed to agents in UI — LMNT is infrastructure, not a feature name.
        # voice_consent_at: timestamp when agent explicitly consented to voice
        #   cloning. Separate from video_consent_at — voice cloning requires its
        #   own distinct consent record. Required before voice setup can proceed.
        ("lmnt_voice_id",            "TEXT DEFAULT NULL"),
        ("voice_consent_at",         "TEXT DEFAULT NULL"),
        # TERMS CONSENT — added Session 53
        # consent_at: timestamp when agent or partner explicitly agreed to the
        #   Terms of Service and Privacy Policy at registration. Recorded
        #   server-side from the consent checkbox on login.html and
        #   partner-signup.html. NULL for accounts created before Session 53.
        #   Required field going forward — frontend blocks submission without it.
        ("consent_at",               "TEXT DEFAULT NULL"),
        # JWT REVOCATION — added Session 53
        # token_version: incremented on password change or admin suspend.
        #   Every JWT includes the version at issue time. get_current_user
        #   rejects tokens whose version is lower than the DB value, forcing
        #   re-login on all devices immediately rather than waiting for TTL.
        ("token_version",            "INTEGER DEFAULT 1"),
        # AUTH LOCKOUT — added Session 53
        # login_fail_count: consecutive failed login attempts since last reset.
        # login_locked_until: ISO timestamp — account locked until this time.
        #   Both reset to 0/NULL on successful login or admin unlock.
        #   Lockout threshold: 5 failures in 15 minutes — locked 30 minutes.
        ("login_fail_count",         "INTEGER DEFAULT 0"),
        ("login_locked_until",       "TEXT DEFAULT NULL"),
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
            day_of_week TEXT DEFAULT NULL,
            UNIQUE(user_id, niche),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # Non-destructive: add day_of_week to existing schedules table
    try:
        c.execute("ALTER TABLE schedules ADD COLUMN day_of_week TEXT DEFAULT NULL")
    except Exception:
        pass

    # Local signals — hyper-local market intelligence per agent
    c.execute("""
        CREATE TABLE IF NOT EXISTS local_signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            area            TEXT NOT NULL,
            headline        TEXT NOT NULL,
            summary         TEXT,
            source_url      TEXT,
            signal_type     TEXT DEFAULT 'general',
            relevance_score REAL DEFAULT 0.5,
            used            INTEGER DEFAULT 0,
            collected_at    TEXT DEFAULT (datetime('now')),
            expires_at      TEXT DEFAULT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # Non-destructive: Signal Exclusivity — track when a signal was consumed (Session 12)
    try:
        c.execute("ALTER TABLE local_signals ADD COLUMN used_at TEXT DEFAULT NULL")
    except Exception:
        pass  # Column already exists
    # Non-destructive: Signal recency — stores the article/story publish date (Session 20)
    # Used to reject stale signals (>90 days) at collection time and display date on signal card
    try:
        c.execute("ALTER TABLE local_signals ADD COLUMN published_date TEXT DEFAULT NULL")
    except Exception:
        pass  # Column already exists
    # Non-destructive: Signal source type — distinguishes RSS-sourced signals from Claude web search (Session 32)
    # Values: 'rss' | 'claude'  — defaults to 'claude' so all existing rows are correctly typed
    try:
        c.execute("ALTER TABLE local_signals ADD COLUMN source_type TEXT DEFAULT 'claude'")
    except Exception:
        pass  # Column already exists
    # Non-destructive: Signal audience context — separates agent-facing (consumer) from hb_marketing signals (Session 58)
    # Values: 'agent' | 'hb_marketing'  — defaults to 'agent' so all existing rows are correctly typed
    try:
        c.execute("ALTER TABLE local_signals ADD COLUMN context TEXT DEFAULT 'agent'")
    except Exception:
        pass  # Column already exists

    # Agent setup — stores identity/profile data server-side
    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_setup (
            user_id INTEGER PRIMARY KEY,
            setup_json TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Assistant Agent linking table
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

    # Platform connections — OAuth token storage
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
    # Non-destructive: add page_token to platform_connections (Plan B Facebook page picker)
    try:
        c.execute("ALTER TABLE platform_connections ADD COLUMN page_token TEXT DEFAULT ''")
    except Exception:
        pass  # Column already exists

    # Platform posts — PaperTrail audit of published content
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

    # Password reset tokens
    c.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            token      TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Waitlist
    c.execute("""
        CREATE TABLE IF NOT EXISTS waitlist (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT UNIQUE NOT NULL,
            name       TEXT DEFAULT '',
            source     TEXT DEFAULT '',
            notes      TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Contacts — marketing site form submissions (Session 24)
    # Saves every contact form submission for CRM-style querying.
    # type: agent | team | broker | partner | other
    # source: contact_form | partner_signup (future)
    c.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL DEFAULT '',
            email      TEXT    NOT NULL,
            type       TEXT    NOT NULL DEFAULT 'other',
            message    TEXT    DEFAULT '',
            source     TEXT    NOT NULL DEFAULT 'contact_form',
            ip_address TEXT    DEFAULT NULL,
            created_at TEXT    DEFAULT (datetime('now'))
        )
    """)

    # Office invites — broker-initiated agent invitations
    c.execute("""
        CREATE TABLE IF NOT EXISTS office_invites (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            broker_id   INTEGER NOT NULL,
            email       TEXT NOT NULL,
            phone       TEXT DEFAULT '',
            agent_name  TEXT DEFAULT '',
            status      TEXT DEFAULT 'pending',
            token       TEXT UNIQUE,
            invited_at  TEXT DEFAULT (datetime('now')),
            accepted_at TEXT DEFAULT NULL,
            FOREIGN KEY (broker_id) REFERENCES users(id)
        )
    """)

    # PARTNER PROGRAM — Session 12
    # Always "Partner Program" — never "affiliate program"
    # Earnings are "Partner Rewards" — never "commissions"

    # Partners — enrolled users and their tier/status
    c.execute("""
        CREATE TABLE IF NOT EXISTS partners (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL UNIQUE,
            tier           TEXT    NOT NULL DEFAULT 'referral',
            status         TEXT    NOT NULL DEFAULT 'pending',
            referral_code  TEXT    NOT NULL UNIQUE,
            enrolled_at    TEXT    DEFAULT (datetime('now')),
            approved_at    TEXT    DEFAULT NULL,
            approved_by    INTEGER DEFAULT NULL,
            total_referred INTEGER DEFAULT 0,
            total_earned   REAL    DEFAULT 0.0,
            FOREIGN KEY (user_id)     REFERENCES users(id),
            FOREIGN KEY (approved_by) REFERENCES users(id)
        )
    """)

    # Referral attributions — tracks which partner referred which subscriber
    # Last-touch wins. One attribution per referred_user lifetime.
    c.execute("""
        CREATE TABLE IF NOT EXISTS referral_attributions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id       INTEGER NOT NULL,
            referred_user_id INTEGER NOT NULL UNIQUE,
            attribution_type TEXT    NOT NULL DEFAULT 'link',
            referral_code    TEXT    DEFAULT NULL,
            attributed_at    TEXT    DEFAULT (datetime('now')),
            converted_at     TEXT    DEFAULT NULL,
            FOREIGN KEY (partner_id)       REFERENCES partners(id),
            FOREIGN KEY (referred_user_id) REFERENCES users(id)
        )
    """)

    # Partner payouts — monthly reward cycle
    # 30-day holdback (Referral/Broker), 15-day (Elite), $50 minimum (Referral/Broker)
    c.execute("""
        CREATE TABLE IF NOT EXISTS partner_payouts (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id         INTEGER NOT NULL,
            amount             REAL    NOT NULL,
            period_start       TEXT    NOT NULL,
            period_end         TEXT    NOT NULL,
            status             TEXT    NOT NULL DEFAULT 'pending',
            stripe_transfer_id TEXT    DEFAULT NULL,
            created_at         TEXT    DEFAULT (datetime('now')),
            paid_at            TEXT    DEFAULT NULL,
            FOREIGN KEY (partner_id) REFERENCES partners(id)
        )
    """)

    # ACCOUNT IDENTITY & ORGANIZATIONAL AFFILIATION — Session 18 (ADD v6 §2.5-2.6)

    # user_contact_methods — multiple verified contact methods per user.
    # Email is a contact address, not an identity key. user_id is the permanent anchor.
    # Any verified email or phone can be used for account recovery.
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_contact_methods (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            type        TEXT    NOT NULL,           -- email | phone
            value       TEXT    NOT NULL,           -- the address or number
            is_primary  INTEGER NOT NULL DEFAULT 0, -- 1 = receives notifications
            is_verified INTEGER NOT NULL DEFAULT 0, -- 1 = confirmed via verification flow
            added_at    TEXT    DEFAULT (datetime('now')),
            verified_at TEXT    DEFAULT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # organizations — teams, offices, and brokerages as first-class entities.
    # Created by explicit declaration during onboarding or claimed later in Settings.
    # Not inherited from signup order.
    c.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            type          TEXT    NOT NULL,           -- team | office | brokerage
            name          TEXT    NOT NULL,
            owner_user_id INTEGER NOT NULL,           -- declaring authority (FK users.id)
            billing_plan  TEXT    NOT NULL DEFAULT 'individual', -- individual | sponsored | organizational
            created_at    TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (owner_user_id) REFERENCES users(id)
        )
    """)

    # user_organizations — affiliation relationship records.
    # Joining creates a record. Leaving sets left_at. Content never transfers.
    # Visibility into an agent's content ends the moment left_at is set.
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_organizations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,           -- FK users.id
            organization_id INTEGER NOT NULL,           -- FK organizations.id
            role_within_org TEXT    NOT NULL DEFAULT 'member', -- member | lead | owner | broker
            joined_at       TEXT    DEFAULT (datetime('now')),
            left_at         TEXT    DEFAULT NULL,       -- NULL = currently affiliated
            billing_model   TEXT    NOT NULL DEFAULT 'individual', -- individual | sponsored | organizational
            invited_by      INTEGER DEFAULT NULL,       -- FK users.id (who invited them)
            FOREIGN KEY (user_id)         REFERENCES users(id),
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (invited_by)      REFERENCES users(id)
        )
    """)

    # MARKET REPORTS — Session 22
    # Stores extracted data from agent-uploaded market PDFs (MLS, RPR, Altos, etc.)
    # PDF bytes are NOT stored — agent retains the source file, we store only the
    # extracted stats JSON. This avoids MLS data licensing liability and disk bloat.
    # extracted_data stores structured JSON for content generation + future intelligence layer.
    # source_label is agent-supplied (e.g. "MLS", "RPR", "Altos Research").
    c.execute("""
        CREATE TABLE IF NOT EXISTS market_reports (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            filename       TEXT    NOT NULL,
            source_label   TEXT    DEFAULT 'MLS',
            report_month   TEXT    DEFAULT NULL,
            report_area    TEXT    DEFAULT NULL,
            extracted_data TEXT    DEFAULT NULL,
            uploaded_at    TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Non-destructive partner table migrations — Session 24 quarterly tier model
    # stripe_connect_id: partner's connected Stripe account for payouts
    # active_referral_count: snapshot count updated each quarter-end evaluation
    # tier_evaluated_at: timestamp of last quarterly tier recalculation
    # payout_frequency: always 'quarterly' per locked design decision Session 24
    # stripe_bank_connected: 1 = bank account connected and ready for payout
    # is_insider_partner: 1 = manually elevated by Admin/SuperAdmin to Insider Partner
    #   status. Earns 25% on direct referrals (no tier threshold) AND 5% override
    #   on referrals generated by partners they personally recruited. Never
    #   self-assigned — only set via admin panel. See partner_set_insider().
    for col, defn in [
        ("stripe_connect_id",     "TEXT DEFAULT NULL"),
        ("active_referral_count", "INTEGER DEFAULT 0"),
        ("tier_evaluated_at",     "TEXT DEFAULT NULL"),
        ("payout_frequency",      "TEXT DEFAULT 'quarterly'"),
        ("stripe_bank_connected", "INTEGER DEFAULT 0"),
        ("suspended_at",          "TEXT DEFAULT NULL"),
        ("suspended_by",          "INTEGER DEFAULT NULL"),
        ("suspension_reason",     "TEXT DEFAULT NULL"),
        ("is_insider_partner",    "INTEGER DEFAULT 0"),
    ]:
        try:
            c.execute(f"ALTER TABLE partners ADD COLUMN {col} {defn}")
        except Exception:
            pass  # Column already exists

    # Non-destructive referral_attributions migrations — Session 24
    # first_payment_at: when the referred user's first Stripe payment cleared
    # is_active: 1 = currently paying subscriber (updated by billing webhooks)
    # override_partner_id: partner_id of the Insider Partner who recruited the
    #   direct partner. NULL for all non-Insider-recruited partners.
    #   Set at partner enrollment if an Insider's referral code was used, OR
    #   set manually by Admin via admin panel (forward-only — never retroactive).
    #   When set, the payout calculator generates a second payout line: 5% of
    #   this subscriber's MRR goes to the Insider Partner at quarter-end.
    #   One subscriber can generate at most two payout lines. Total never > 30%.
    for col, defn in [
        ("first_payment_at",   "TEXT DEFAULT NULL"),
        ("is_active",          "INTEGER DEFAULT 0"),
        ("override_partner_id","INTEGER DEFAULT NULL"),
    ]:
        try:
            c.execute(f"ALTER TABLE referral_attributions ADD COLUMN {col} {defn}")
        except Exception:
            pass  # Column already exists

    # COMPLIANCE RECORDS — Session 34
    # Permanent audit trail written at the moment a post is approved and a
    # CIR ID is generated. Survives content_library deletions — once written
    # this record is never altered or removed by any platform action.
    # library_item_id is nullable so deleted posts do not orphan the record.
    # compliance_json stores the full ComplianceBadge for complete auditability.
    c.execute("""
        CREATE TABLE IF NOT EXISTS compliance_records (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            cir_id           TEXT    NOT NULL,
            library_item_id  INTEGER DEFAULT NULL,
            niche            TEXT    DEFAULT '',
            headline         TEXT    DEFAULT '',
            platform         TEXT    DEFAULT '',
            overall_status   TEXT    DEFAULT '',
            fair_housing     TEXT    DEFAULT '',
            disclosure       TEXT    DEFAULT '',
            nar_standards    TEXT    DEFAULT '',
            state_compliance TEXT    DEFAULT '',
            rules_version    TEXT    DEFAULT '',
            compliance_json  TEXT    DEFAULT NULL,
            approved_at      TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    try:
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_compliance_records_user "
            "ON compliance_records(user_id, approved_at DESC)"
        )
    except Exception:
        pass

    # VIDEO JOBS — Session 49
    # Tracks every avatar video render request submitted to the video API.
    # One row per render attempt — regenerations create new rows.
    # heygen_video_id: the video_id returned by the HeyGen API on submission.
    # library_item_id: the content_library item the script came from (nullable).
    # status: pending | processing | completed | failed
    # video_url: populated by webhook or poll when status = completed.
    #   HeyGen video URLs expire after 7 days — store promptly after completion.
    # photo_token: signed temporary token used for this render's photo URL.
    #   Stored for audit only — never reused.
    # script_preview: first 200 chars of script for display in admin/records.
    c.execute("""
        CREATE TABLE IF NOT EXISTS video_jobs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            heygen_video_id  TEXT    DEFAULT NULL,
            library_item_id  INTEGER DEFAULT NULL,
            status           TEXT    NOT NULL DEFAULT 'pending',
            video_url        TEXT    DEFAULT NULL,
            photo_token      TEXT    DEFAULT NULL,
            script_preview   TEXT    DEFAULT NULL,
            error_message    TEXT    DEFAULT NULL,
            created_at       TEXT    DEFAULT (datetime('now')),
            completed_at     TEXT    DEFAULT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    try:
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_video_jobs_user "
            "ON video_jobs(user_id, created_at DESC)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_video_jobs_heygen_id "
            "ON video_jobs(heygen_video_id)"
        )
    except Exception:
        pass

    # PHOTO TOKENS — Session 49
    # Short-lived signed tokens that make an agent's profile photo temporarily
    # accessible to the video render API during avatar generation.
    # token: random 32-char URL-safe string included in the photo URL.
    # expires_at: 30 minutes from creation — fetched within this window.
    # used: set to 1 after render job submitted (one-time use per render).
    c.execute("""
        CREATE TABLE IF NOT EXISTS photo_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            token      TEXT    NOT NULL UNIQUE,
            expires_at TEXT    NOT NULL,
            used       INTEGER DEFAULT 0,
            created_at TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    try:
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_photo_tokens_token "
            "ON photo_tokens(token)"
        )
    except Exception:
        pass

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
    - cir_id: CIR verification record ID
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
        ("image_regen_count",     "INTEGER DEFAULT 0"),
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
    Safe to call on every startup. Table is also created in init_db().
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


# ─────────────────────────────────────────────
# PLATFORM CONNECTIONS — OAuth token storage
# ─────────────────────────────────────────────
def save_platform_connection(user_id: int, platform: str, access_token: str,
                              refresh_token: str, expires_at: str,
                              platform_user_id: str, platform_handle: str,
                              page_token: str = ""):
    """Insert or replace a platform OAuth connection for a user."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO platform_connections
            (user_id, platform, access_token, refresh_token, expires_at,
             platform_user_id, platform_handle, page_token, connected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, platform) DO UPDATE SET
            access_token     = excluded.access_token,
            refresh_token    = excluded.refresh_token,
            expires_at       = excluded.expires_at,
            platform_user_id = excluded.platform_user_id,
            platform_handle  = excluded.platform_handle,
            page_token       = excluded.page_token,
            connected_at     = datetime('now')
    """, (user_id, platform, access_token, refresh_token, expires_at,
          platform_user_id, platform_handle, page_token))
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
               platform_user_id, platform_handle, page_token, connected_at
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
    # Niche-count enforcement
    # Check the agent's plan limit before saving. Raises ValueError on violation
    # so the caller (/setup/save route) can return a 400 with a clear message.
    # UNLIMITED_ROLES (super_admin, admin) bypass this check entirely.
    conn_check = get_conn()
    try:
        c_check = conn_check.cursor()
        c_check.execute("SELECT plan, role FROM users WHERE id = ?", (user_id,))
        row_check = c_check.fetchone()
        plan = (row_check["plan"] if row_check else None) or "trial"
        role = (row_check["role"] if row_check else None) or ""
    finally:
        conn_check.close()

    if role not in UNLIMITED_ROLES:
        limits      = _get_plan_limits(plan)
        niche_limit = limits.get("niches", 999)
        # Onboarding saves niches under "primaryNiches"; identity panel may use "niches"
        niches      = setup.get("primaryNiches", setup.get("niches", [])) or []
        if len(niches) > niche_limit:
            raise ValueError(
                f"Your {plan} plan allows up to {niche_limit} niche{'s' if niche_limit != 1 else ''}. "
                f"You submitted {len(niches)}. Please remove {len(niches) - niche_limit} before saving."
            )

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
        if _compliance_verdict(row["compliance"]) == "pass":
            passing += 1
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
# COMPLIANCE RECORDS — permanent audit trail
# ─────────────────────────────────────────────

def record_compliance_approval(
    user_id: int,
    cir_id: str,
    library_item_id: int,
    niche: str,
    content: dict,
    compliance: dict,
    approved_at: str,
) -> None:
    """
    Write a permanent compliance record at the moment a CIR is issued.
    Called from library_update() immediately after the CIR ID is generated.
    Never raises — a write failure here must never block the approval flow.
    The record is immutable once written: no update or delete path exists.
    """
    try:
        headline = ""
        if isinstance(content, dict):
            headline = (content.get("headline") or content.get("title") or "")[:300]

        comp = compliance if isinstance(compliance, dict) else {}
        overall  = comp.get("overallStatus") or comp.get("overall_verdict") or ""
        fh       = comp.get("fairHousing") or comp.get("fair_housing") or ""
        disc     = comp.get("brokerageDisclosure") or comp.get("disclosure") or ""
        nar      = comp.get("narStandards") or comp.get("nar_standards") or ""
        state_c  = comp.get("stateCompliance") or ""
        rules_v  = comp.get("rules_version") or ""

        conn = get_conn()
        c    = conn.cursor()
        c.execute("""
            INSERT INTO compliance_records
                (user_id, cir_id, library_item_id, niche, headline,
                 overall_status, fair_housing, disclosure, nar_standards,
                 state_compliance, rules_version, compliance_json, approved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, cir_id, library_item_id,
            niche or "", headline,
            overall, fh, disc, nar, state_c, rules_v,
            json.dumps(compliance),
            approved_at,
        ))
        conn.commit()
        conn.close()
        print(f"[CIR] Compliance record written — {cir_id} for user {user_id}")
    except Exception as e:
        print(f"[CIR] WARNING: compliance record write failed for {cir_id}: {e}")


def get_compliance_records(
    user_id: int,
    date_from: str = "",
    date_to: str = "",
    limit: int = 200,
) -> list:
    """
    Return permanent compliance records for an agent, newest first.
    Optionally filtered by approved_at date range (ISO strings).
    Used by agent history view and broker compliance tab.
    """
    conn = get_conn()
    c    = conn.cursor()

    query  = "SELECT * FROM compliance_records WHERE user_id = ?"
    params = [user_id]

    if date_from:
        query  += " AND approved_at >= ?"
        params.append(date_from)
    if date_to:
        query  += " AND approved_at <= ?"
        params.append(date_to)

    query += " ORDER BY approved_at DESC LIMIT ?"
    params.append(limit)

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    results = []
    for r in rows:
        comp = {}
        try:
            comp = json.loads(r["compliance_json"]) if r["compliance_json"] else {}
        except Exception:
            pass
        results.append({
            "id":               r["id"],
            "cir_id":           r["cir_id"],
            "library_item_id":  r["library_item_id"],
            "niche":            r["niche"] or "",
            "headline":         r["headline"] or "",
            "platform":         r["platform"] or "",
            "overall_status":   r["overall_status"] or "",
            "fair_housing":     r["fair_housing"] or "",
            "disclosure":       r["disclosure"] or "",
            "nar_standards":    r["nar_standards"] or "",
            "state_compliance": r["state_compliance"] or "",
            "rules_version":    r["rules_version"] or "",
            "approved_at":      r["approved_at"] or "",
            "compliance":       comp,
        })
    return results


def get_compliance_records_for_broker(
    broker_id: int,
    agent_id: int = None,
    date_from: str = "",
    date_to: str = "",
    limit: int = 500,
) -> list:
    """
    Return compliance records for all agents under a broker, or a single
    agent if agent_id is supplied. Verifies agent belongs to broker.
    Used by broker/team compliance dashboard.
    """
    conn = get_conn()
    c    = conn.cursor()

    # Build agent scope — all agents under this broker, or one specific agent
    if agent_id:
        c.execute(
            "SELECT id, agent_name FROM users WHERE id = ? AND broker_id = ? AND is_active = 1",
            (agent_id, broker_id)
        )
    else:
        c.execute(
            "SELECT id, agent_name FROM users WHERE broker_id = ? AND is_active = 1",
            (broker_id,)
        )
    agents = {row["id"]: row["agent_name"] for row in c.fetchall()}

    if not agents:
        conn.close()
        return []

    placeholders = ",".join("?" * len(agents))
    query  = f"SELECT * FROM compliance_records WHERE user_id IN ({placeholders})"
    params = list(agents.keys())

    if date_from:
        query  += " AND approved_at >= ?"
        params.append(date_from)
    if date_to:
        query  += " AND approved_at <= ?"
        params.append(date_to)

    query += " ORDER BY approved_at DESC LIMIT ?"
    params.append(limit)

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    results = []
    for r in rows:
        comp = {}
        try:
            comp = json.loads(r["compliance_json"]) if r["compliance_json"] else {}
        except Exception:
            pass
        results.append({
            "id":               r["id"],
            "agent_id":         r["user_id"],
            "agent_name":       agents.get(r["user_id"], "Unknown"),
            "cir_id":           r["cir_id"],
            "library_item_id":  r["library_item_id"],
            "niche":            r["niche"] or "",
            "headline":         r["headline"] or "",
            "overall_status":   r["overall_status"] or "",
            "fair_housing":     r["fair_housing"] or "",
            "disclosure":       r["disclosure"] or "",
            "nar_standards":    r["nar_standards"] or "",
            "state_compliance": r["state_compliance"] or "",
            "rules_version":    r["rules_version"] or "",
            "approved_at":      r["approved_at"] or "",
            "compliance":       comp,
        })
    return results


def backfill_compliance_records() -> int:
    """
    One-time backfill — copies approved/published posts that already have a
    CIR ID from content_library into compliance_records.
    Safe to call multiple times — skips any cir_id already present.
    Returns the number of records written.
    Called automatically at startup from app.py after init_db().
    """
    conn = get_conn()
    c    = conn.cursor()

    # Find all approved/published items with a cir_id not yet in compliance_records
    c.execute("""
        SELECT cl.id, cl.user_id, cl.cir_id, cl.niche, cl.content, cl.compliance,
               cl.approved_at, cl.saved_at
        FROM content_library cl
        WHERE cl.status IN ('approved', 'published')
          AND cl.cir_id IS NOT NULL
          AND cl.cir_id != ''
          AND cl.cir_id NOT IN (SELECT cir_id FROM compliance_records)
    """)
    rows = c.fetchall()

    written = 0
    for r in rows:
        try:
            content    = json.loads(r["content"])    if r["content"]    else {}
            compliance = json.loads(r["compliance"]) if r["compliance"] else {}

            headline = (content.get("headline") or content.get("title") or "")[:300]
            overall  = compliance.get("overallStatus") or compliance.get("overall_verdict") or ""
            fh       = compliance.get("fairHousing")   or compliance.get("fair_housing")    or ""
            disc     = compliance.get("brokerageDisclosure") or compliance.get("disclosure") or ""
            nar      = compliance.get("narStandards")  or compliance.get("nar_standards")   or ""
            state_c  = compliance.get("stateCompliance") or ""
            rules_v  = compliance.get("rules_version") or ""
            approved = r["approved_at"] or r["saved_at"] or datetime.utcnow().isoformat()

            c.execute("""
                INSERT INTO compliance_records
                    (user_id, cir_id, library_item_id, niche, headline,
                     overall_status, fair_housing, disclosure, nar_standards,
                     state_compliance, rules_version, compliance_json, approved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["user_id"], r["cir_id"], r["id"],
                r["niche"] or "", headline,
                overall, fh, disc, nar, state_c, rules_v,
                json.dumps(compliance),
                approved,
            ))
            written += 1
        except Exception as e:
            print(f"[Backfill] Skipping item {r['id']}: {e}")
            continue

    conn.commit()
    conn.close()
    if written:
        print(f"[Backfill] compliance_records: {written} historical record(s) written.")
    else:
        print("[Backfill] compliance_records: already up to date, nothing to write.")
    return written


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


def library_get_all(user_id: int, context: str = "agent", include_archived: bool = False) -> list:
    """
    Fetch all library items for a user filtered by context.
    context = 'agent'        — personal real estate content
    context = 'hb_marketing' — HomeBridge platform content
    include_archived = False — archived items excluded by default (only shown in Archived tab)
    """
    conn = get_conn()
    c = conn.cursor()
    archive_clause = "" if include_archived else "AND (status IS NULL OR status != 'archived')"
    c.execute(f"""
        SELECT * FROM content_library
        WHERE user_id = ? AND (context = ? OR (context IS NULL AND ? = 'agent'))
        {archive_clause}
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
    When status is set to 'approved', generates a CIR ID if one does not
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

    # CIR generation — write on first approval
    # Only create a CIR ID if this update sets status to 'approved'
    # and the item doesn't already have one.
    _new_cir_id      = None  # track whether we just generated one
    _item_for_record = None  # full item snapshot for compliance_records write
    if updates.get("status") == "approved":
        c.execute(
            "SELECT cir_id, niche, content, compliance FROM content_library WHERE id = ? AND user_id = ?",
            (item_id, user_id)
        )
        existing = c.fetchone()
        if existing and not existing["cir_id"]:
            import secrets as _sec
            cir_date     = datetime.utcnow().strftime("%Y%m%d")
            cir_rand     = _sec.token_hex(3).upper()  # 6 uppercase hex chars
            _new_cir_id  = f"CIR-{cir_date}-{cir_rand}"
            fields.append("cir_id = ?")
            values.append(_new_cir_id)
            print(f"[CIR] Generated {_new_cir_id} for library item {item_id} (user {user_id})")
            # Capture snapshot for compliance_records — use incoming content/compliance
            # if the update carries them, otherwise fall back to what's in the DB now.
            _snap_content    = updates.get("content")    or (json.loads(existing["content"])    if existing["content"]    else {})
            _snap_compliance = updates.get("compliance") or (json.loads(existing["compliance"]) if existing["compliance"] else {})
            _snap_niche      = existing["niche"] or ""
            _item_for_record = (_snap_niche, _snap_content, _snap_compliance)

    values += [item_id, user_id]
    c.execute(
        f"UPDATE content_library SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
        values
    )
    conn.commit()
    conn.close()

    # Write permanent compliance record — after DB commit, never blocks
    if _new_cir_id and _item_for_record:
        _niche, _content, _compliance = _item_for_record
        record_compliance_approval(
            user_id         = user_id,
            cir_id          = _new_cir_id,
            library_item_id = item_id,
            niche           = _niche,
            content         = _content,
            compliance      = _compliance,
            approved_at     = datetime.utcnow().isoformat(),
        )

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
    # Include cir_id, image_url, image_regen_count — columns exist in DB but were
    # never returned, so the frontend could never display them.
    cir_id            = None
    image_url         = None
    image_regen_count = 0
    try: cir_id            = row["cir_id"]
    except Exception: pass
    try: image_url         = row["image_url"]
    except Exception: pass
    try: image_regen_count = row["image_regen_count"] or 0
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
        "cir_id":              cir_id,
        "image_url":           image_url,
        "image_regen_count":   image_regen_count,
        "editedAt":            row["edited_at"]            if "edited_at"            in row.keys() else None,
        "complianceCheckedAt": row["compliance_checked_at"] if "compliance_checked_at" in row.keys() else None,
    }


# ─────────────────────────────────────────────
# SCHEDULES
# ─────────────────────────────────────────────
def schedule_upsert(user_id: int, niche: str, frequency: str,
                    time_of_day: str, timezone: str = "America/Denver",
                    day_of_week: str = None) -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO schedules (user_id, niche, frequency, time_of_day, timezone, active, next_run, day_of_week)
        VALUES (?, ?, ?, ?, ?, 1, NULL, ?)
        ON CONFLICT(user_id, niche) DO UPDATE SET
            frequency   = excluded.frequency,
            time_of_day = excluded.time_of_day,
            timezone    = excluded.timezone,
            active      = 1,
            next_run    = NULL,
            day_of_week = excluded.day_of_week
    """, (user_id, niche, frequency, time_of_day, timezone, day_of_week))
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


def schedule_deactivate(schedule_id: int) -> None:
    """
    Deactivate a schedule without deleting it.
    Called by the scheduler safety net (Part C) when a scheduled niche
    is no longer in the agent's current primaryNiches.
    Admin can inspect and manually delete if desired.
    """
    conn = get_conn()
    conn.execute(
        "UPDATE schedules SET active = 0 WHERE id = ?",
        (schedule_id,)
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


def schedules_delete_for_user(user_id: int) -> int:
    """
    Delete ALL schedules for a user. Used by the reset-niches admin endpoint (Part B).
    Returns the count of deleted rows.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM schedules WHERE user_id = ?", (user_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected


def _schedule_row(row) -> dict:
    dow = None
    try: dow = row["day_of_week"]
    except Exception: pass
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
        "dayOfWeek":  dow,
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
    # 12 bytes = 16-char URL-safe token = 96 bits entropy
    # Sufficient for a 7-day one-time token. Keeps SMS URLs under 160 chars (1 segment).
    token      = _sec.token_urlsafe(12)
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


def lookup_approval_token_record(token: str) -> Optional[dict]:
    """
    Fetch a token record regardless of expiry or used status.
    Used by the resend flow to recover item_id and user_id from an expired token.
    Returns None only if the token string doesn't exist at all (i.e. was forged).
    """
    migrate_approval_tokens()
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT at.id, at.user_id, at.library_item_id, at.action,
               at.expires_at, at.used,
               u.email, u.agent_name, u.phone,
               cl.niche, cl.content, cl.status
        FROM approval_tokens at
        JOIN users u ON u.id = at.user_id
        JOIN content_library cl ON cl.id = at.library_item_id
        WHERE at.token = ?
    """, (token,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# NEXT ACTION ENGINE
# Replaces calculate_identity_score() — Session 56
#
# Doctrine: Never grade agents. Never display numerical scores.
# This function returns one actionable recommendation, supporting
# data points, and a milestone progress indicator. Jordan uses this
# data for the daily briefing. Agents see what to do next and why
# it matters — never a score, never a grade.
# ─────────────────────────────────────────────

def get_agent_guidance(user_id: int) -> dict:
    """
    Return actionable guidance for an agent based on their current platform state.
    Called by the identity endpoint in app.py to power Jordan's briefing card
    and the Next Action panel in index.html.

    Returns:
        next_action  — one specific, actionable recommendation (string)
        data_points  — the metrics that informed the recommendation (dict)
        progress     — milestone indicator string (e.g. "12 of 25 CIR records
                       toward AI search visibility") — never a numerical score
        cir_count    — total CIR records issued (permanent compliance records)
    """
    from datetime import datetime as _dt, timedelta as _td

    conn = get_conn()
    c    = conn.cursor()

    # Load agent setup
    c.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
    setup_row = c.fetchone()
    setup = json.loads(setup_row["setup_json"]) if setup_row and setup_row["setup_json"] else {}

    # Load content state
    c.execute("""
        SELECT status, compliance, approved_at, published_at, saved_at, niche
        FROM content_library
        WHERE user_id = ?
        ORDER BY saved_at DESC
    """, (user_id,))
    rows = c.fetchall()

    # CIR count from permanent audit trail — authoritative count
    c.execute("SELECT COUNT(*) as cnt FROM compliance_records WHERE user_id = ?", (user_id,))
    cir_row   = c.fetchone()
    cir_count = cir_row["cnt"] if cir_row else 0

    # Active schedules
    c.execute("SELECT COUNT(*) as cnt FROM schedules WHERE user_id = ? AND active = 1", (user_id,))
    sched_row    = c.fetchone()
    has_schedule = bool(sched_row and sched_row["cnt"] > 0)

    conn.close()

    # Derive key data points
    now     = _dt.utcnow()
    last_7  = now - _td(days=7)
    last_30 = now - _td(days=30)

    def _parse_date(s):
        if not s: return None
        try:    return _dt.fromisoformat(s.replace("Z", ""))
        except: return None

    approved_items  = [r for r in rows if r["status"] in ("approved", "published")]
    total_approved  = len(approved_items)

    published_dates = [
        _parse_date(r["published_at"] or r["approved_at"] or r["saved_at"])
        for r in approved_items
    ]
    published_dates = [d for d in published_dates if d]

    published_last_7  = any(d >= last_7  for d in published_dates)
    published_last_30 = any(d >= last_30 for d in published_dates)

    niches_raw  = setup.get("primaryNiches", [])
    niches      = niches_raw if isinstance(niches_raw, list) else []
    has_bio     = len(setup.get("shortBio", "").strip()) > 20
    has_voice   = len(setup.get("brandVoice", "").strip()) > 10
    has_market  = bool(setup.get("market", "").strip())

    data_points = {
        "cir_count":           cir_count,
        "total_approved":      total_approved,
        "published_last_7":    published_last_7,
        "published_last_30":   published_last_30,
        "has_schedule":        has_schedule,
        "niche_count":         len(niches),
        "has_bio":             has_bio,
        "has_voice":           has_voice,
        "has_market":          has_market,
    }

    # Determine the single most impactful next action
    # Priority order: foundation gaps first, then content gaps, then cadence
    next_action = _determine_next_action(data_points)

    # Milestone progress indicator — never a score
    progress = _build_progress_indicator(cir_count, total_approved, has_schedule, len(niches))

    return {
        "next_action": next_action,
        "data_points": data_points,
        "progress":    progress,
        "cir_count":   cir_count,
    }


def _determine_next_action(dp: dict) -> str:
    """
    Return one specific, actionable recommendation based on data points.
    Priority: setup gaps first, then content gaps, then schedule, then cadence.
    Internal helper for get_agent_guidance().
    """
    if not dp["has_market"]:
        return "Add your primary market in your Identity settings — it anchors every piece of content to a real place."
    if dp["niche_count"] == 0:
        return "Select at least one niche in your Identity settings — your content needs a specialty to be useful to anyone."
    if not dp["has_bio"]:
        return "Write a short bio in your Identity settings — it tells the platform who you are and shapes your content voice."
    if not dp["has_voice"]:
        return "Define your brand voice in Identity settings — it ensures every post sounds like you, not a template."
    if dp["total_approved"] == 0:
        return "Generate and approve your first piece of content to start building your permanent record."
    if dp["niche_count"] == 1:
        return "Consider adding a second niche — it expands the topics available to you and strengthens your authority footprint."
    if not dp["published_last_7"]:
        if dp["total_approved"] > 0 and not dp["published_last_30"]:
            return "Your last approved content was more than 30 days ago. Generate and approve something this week to stay visible."
        return "Approve and publish something this week — consistent presence is how search and AI systems learn to cite you."
    if not dp["has_schedule"]:
        return "Set a content schedule so AutoMates builds your presence automatically — even one post per week compounds over time."
    if dp["cir_count"] < 10:
        return f"You have {dp['cir_count']} CIR records so far. Keep approving content — 10 records is the first visibility milestone."
    if dp["cir_count"] < 25:
        return f"You have {dp['cir_count']} CIR records. At 25, AI search platforms begin to have enough indexed content to cite you consistently."
    return "Your foundation is solid. Keep publishing consistently — your CIR record compounds with every approval."


def _build_progress_indicator(cir_count: int, approved_count: int,
                               has_schedule: bool, niche_count: int) -> str:
    """
    Return a milestone progress string. Never a numerical score.
    Internal helper for get_agent_guidance().
    """
    if cir_count == 0:
        return "Approve your first post to issue your first CIR record."
    if cir_count < 10:
        return f"{cir_count} of 10 CIR records toward your first visibility milestone."
    if cir_count < 25:
        return f"{cir_count} of 25 CIR records toward consistent AI search citation."
    if cir_count < 50:
        return f"{cir_count} CIR records issued. At 50, you have a substantial authority footprint."
    return f"{cir_count} CIR records on file. Your permanent record is well established."


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
    BLUE      = colors.HexColor("#1972A8")
    BLUE_DIM  = colors.HexColor("#EBF8FF")
    GREEN     = colors.HexColor("#1A7A4A")
    GREEN_DIM = colors.HexColor("#f0fdf4")
    AMBER     = colors.HexColor("#b45309")
    AMBER_DIM = colors.HexColor("#fffbeb")
    RED       = colors.HexColor("#b91c1c")
    RED_DIM   = colors.HexColor("#fef2f2")
    BG        = colors.HexColor("#FAF9F7")
    BORDER    = colors.HexColor("#E7E5E4")
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
        v = _compliance_verdict(r["compliance"])
        if v == "pass":   passing += 1
        elif v == "warn": review_count += 1
        else:             fail_count += 1

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
        return s[:n] + "..." if len(s) > n else s

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch)

    story = []

    # Header
    story += [
        Paragraph("AutoMates", styles["label"]),
        Paragraph("Pre-Publication Review Report", styles["h1"]),
        sp(4), rule(), sp(4),
    ]

    # Agent info block
    info_data = [
        ["Agent", agent_name or ""],
        ["Brokerage", brokerage or ""],
        ["Email", email or ""],
        ["Period", f"{date_from or 'All time'} to {date_to or 'Present'}"],
        ["Generated", generated_at],
    ]
    info_table = Table(info_data, colWidths=[1.2*inch, 5.3*inch])
    info_table.setStyle([
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 8),
        ("TEXTCOLOR", (0,0), (0,-1), INK_3),
        ("TEXTCOLOR", (1,0), (1,-1), INK_2),
        ("TOPPADDING",(0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
    ])
    story += [info_table, sp(8), rule(), sp(4)]

    # Summary stats
    story.append(Paragraph("Summary", styles["h2"]))
    summary_data = [
        ["Total Posts Reviewed", str(total)],
        ["Pre-Publication Review: Passed", str(passing)],
        ["Review Recommended", str(review_count)],
        ["Attention Required", str(fail_count)],
        ["Pre-Publication Review Rate", f"{compliance_rate}%"],
    ]
    summary_table = Table(summary_data, colWidths=[3*inch, 3.5*inch])
    summary_table.setStyle([
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), INK_2),
        ("TEXTCOLOR", (1,0), (1,-1), INK),
        ("TOPPADDING",(0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LINEBELOW", (0,-1),(-1,-1), 0.5, BORDER),
    ])
    story += [summary_table, sp(12), rule(), sp(4)]

    # Detail table
    story.append(Paragraph("Content Detail", styles["h2"]))

    if not rows:
        story.append(Paragraph("No reviewed content in this period.", styles["body"]))
    else:
        cw = {"date": 0.9*inch, "niche": 1.2*inch, "headline": 2.2*inch,
              "fh": 0.7*inch, "nar": 0.7*inch, "status": 0.8*inch}
        header = [
            Paragraph("Date", styles["label"]),
            Paragraph("Niche", styles["label"]),
            Paragraph("Headline", styles["label"]),
            Paragraph("Fair Housing", styles["label"]),
            Paragraph("NAR Standards", styles["label"]),
            Paragraph("Status", styles["label"]),
        ]
        tdata    = [header]
        row_meta = []
        data_row_idx = 1

        def _build_notes_text(comp_raw):
            try:
                comp  = json.loads(comp_raw) if isinstance(comp_raw, str) else (comp_raw or {})
                notes = []
                for check in comp.get("checks", []):
                    if check.get("level") in ("warn", "fail") and check.get("message"):
                        notes.append(check["message"])
                return " | ".join(notes) if notes else ""
            except Exception:
                return ""

        for r in rows:
            verdict = _compliance_verdict(r["compliance"])
            if verdict == "pass":
                status_style = styles["cell_pass"]
                status_label = "Reviewed"
                notes_bg     = GREEN_DIM
            elif verdict == "warn":
                status_style = styles["cell_warn"]
                status_label = "Review Recommended"
                notes_bg     = AMBER_DIM
            else:
                status_style = styles["cell_fail"]
                status_label = "Attention Required"
                notes_bg     = RED_DIM

            try:
                cd = json.loads(r["content"]) if r["content"] else {}
            except Exception:
                cd = {}
            try:
                comp = json.loads(r["compliance"]) if r["compliance"] else {}
            except Exception:
                comp = {}

            date_str = (r["approved_at"] or r["saved_at"] or "")[:10]
            headline = truncate(cd.get("headline") or cd.get("title") or "", 60)
            fh_val   = comp.get("fairHousing") or comp.get("fair_housing") or ""
            nar_val  = comp.get("narStandards") or comp.get("nar_standards") or ""

            data_row = [
                Paragraph(date_str, styles["cell"]),
                Paragraph(truncate(r["niche"] or "", 20), styles["cell"]),
                Paragraph(headline, styles["cell"]),
                Paragraph(str(fh_val)[:12], styles["cell"]),
                Paragraph(str(nar_val)[:12], styles["cell"]),
                Paragraph(status_label, status_style),
            ]
            bg = BLUE_DIM if data_row_idx % 2 == 0 else WHITE
            tdata.append(data_row)
            row_meta.append((data_row_idx, bg, False))
            data_row_idx += 1

            notes_text = _build_notes_text(r["compliance"])
            if notes_text:
                tdata.append([
                    Paragraph(notes_text, ParagraphStyle("notes_sub", fontName="Helvetica",
                        fontSize=6.5, textColor=INK_3, leading=9, leftIndent=4)),
                    "", "", "", "", ""
                ])
                row_meta.append((data_row_idx, notes_bg, True))
                data_row_idx += 1

        ct = Table(tdata, colWidths=list(cw.values()), repeatRows=1)
        ts = [
            ("BACKGROUND",(0,0),(-1,0),BLUE_DIM),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),7.5),
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
        Paragraph(f"This report was automatically generated by AutoMates on {generated_at}. "
                  "It reflects all content reviewed and approved by the agent named above. "
                  "All compliance verdicts are generated by AutoMates' automated compliance engine and do not constitute legal advice. "
                  "AutoMates checks compliance — it does not verify or guarantee compliance. "
                  "This document is intended for internal review and compliance record-keeping purposes.", styles["footer"])]

    doc.build(story)
    return buf.getvalue()


# ─────────────────────────────────────────────
# BROKER OFFICE STATS
# ─────────────────────────────────────────────
def get_broker_office_stats(broker_id: int) -> list:
    """
    Returns per-agent stats for every active agent linked to this broker.
    Used by the broker dashboard overview table.
    Fields returned match what renderBrokerOffice() expects in app.js.
    """
    import json
    from datetime import datetime, timedelta
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT id, email, agent_name, brokerage, created_at
        FROM users WHERE broker_id=? AND role='agent' AND is_active=1
        ORDER BY agent_name ASC
    """, (broker_id,))
    agents = c.fetchall()
    results = []
    now = datetime.utcnow()

    for agent in agents:
        uid = agent["id"]

        # Content counts + last activity
        c.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status='approved'  THEN 1 ELSE 0 END) as approved,
                   SUM(CASE WHEN status='published' THEN 1 ELSE 0 END) as published,
                   SUM(CASE WHEN status='pending'   THEN 1 ELSE 0 END) as pending,
                   MAX(COALESCE(approved_at, saved_at)) as last_activity
            FROM content_library WHERE user_id=?
        """, (uid,))
        stats = c.fetchone()

        # Compliance rate
        c.execute("SELECT compliance FROM content_library WHERE user_id=? AND status IN ('approved','published')", (uid,))
        passing = sum(1 for cr in c.fetchall() if _compliance_verdict(cr["compliance"]) == "pass")
        total_reviewed  = (stats["approved"] or 0) + (stats["published"] or 0)
        compliance_rate = round((passing / total_reviewed) * 100) if total_reviewed > 0 else None

        # Lightweight identity score (broker/team dashboards only — internal use)
        published_count = stats["published"] or 0
        identity_score  = _calc_lightweight_identity(c, uid, compliance_rate, published_count)

        # Active schedule
        c.execute("SELECT COUNT(*) as cnt FROM schedules WHERE user_id=? AND active=1", (uid,))
        sched = c.fetchone()
        has_schedule = (sched["cnt"] > 0) if sched else False

        # Activity status — derived from last_activity timestamp
        last_act = stats["last_activity"]
        if not last_act or stats["total"] == 0:
            activity_status = "new"
        else:
            try:
                last_dt = datetime.fromisoformat(str(last_act)[:19])
                days_ago = (now - last_dt).days
                if days_ago <= 7:    activity_status = "active"
                elif days_ago <= 30: activity_status = "active"
                else:                activity_status = "inactive"
            except Exception:
                activity_status = "active"

        results.append({
            # "name" alias — fixes frontend a.name reference in renderBrokerOffice
            "id":             uid,
            "name":           agent["agent_name"],
            "agent_name":     agent["agent_name"],
            "email":          agent["email"],
            "brokerage":      agent["brokerage"] or "",
            "joined":         agent["created_at"],
            "total_content":  stats["total"] or 0,
            "pending":        stats["pending"] or 0,
            "approved":       stats["approved"] or 0,
            "published":      stats["published"] or 0,
            "compliance_rate": compliance_rate,
            "score":          identity_score,
            "has_schedule":   has_schedule,
            "last_activity":  last_act,
            "status":         activity_status,
        })

    conn.close()
    return results


def get_team_stats(team_id: int) -> list:
    """
    Returns per-agent stats for every active agent linked to this team.
    Mirrors get_broker_office_stats but queries by team_id.
    Used by the team dashboard (same broker-panel UI).
    """
    import json
    from datetime import datetime, timedelta
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT id, email, agent_name, brokerage, created_at
        FROM users WHERE team_id=? AND role='agent' AND is_active=1
        ORDER BY agent_name ASC
    """, (team_id,))
    agents = c.fetchall()
    results = []
    now = datetime.utcnow()

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
        passing = sum(1 for cr in c.fetchall() if _compliance_verdict(cr["compliance"]) == "pass")
        total_reviewed  = (stats["approved"] or 0) + (stats["published"] or 0)
        compliance_rate = round((passing / total_reviewed) * 100) if total_reviewed > 0 else None

        # Lightweight identity score (broker/team dashboards only — internal use)
        published_count = stats["published"] or 0
        identity_score  = _calc_lightweight_identity(c, uid, compliance_rate, published_count)

        c.execute("SELECT COUNT(*) as cnt FROM schedules WHERE user_id=? AND active=1", (uid,))
        sched = c.fetchone()
        last_act = stats["last_activity"]
        if not last_act or stats["total"] == 0:
            activity_status = "new"
        else:
            try:
                days_ago = (now - datetime.fromisoformat(str(last_act)[:19])).days
                activity_status = "active" if days_ago <= 30 else "inactive"
            except Exception:
                activity_status = "active"

        results.append({
            "id": uid, "name": agent["agent_name"], "agent_name": agent["agent_name"],
            "email": agent["email"], "brokerage": agent["brokerage"] or "",
            "joined": agent["created_at"], "total_content": stats["total"] or 0,
            "pending": stats["pending"] or 0, "approved": stats["approved"] or 0,
            "published": stats["published"] or 0, "compliance_rate": compliance_rate,
            "score": identity_score, "has_schedule": (sched["cnt"]>0) if sched else False,
            "last_activity": last_act, "status": activity_status,
        })
    conn.close()
    return results


def get_broker_agent_content(broker_id: int, agent_id: int, limit: int = 20) -> list:
    """
    Returns recent content items for a specific agent, verified to belong to this broker.
    Used by the broker dashboard per-agent drill-down.
    """
    import json
    conn = get_conn()
    c    = conn.cursor()

    # Verify the agent belongs to this broker
    c.execute(
        "SELECT id, agent_name FROM users WHERE id=? AND broker_id=? AND is_active=1",
        (agent_id, broker_id)
    )
    if not c.fetchone():
        conn.close()
        return []

    c.execute("""
        SELECT id, niche, status, content, compliance,
               copied_platforms, saved_at, approved_at, published_at, cir_id
        FROM content_library
        WHERE user_id=?
        ORDER BY COALESCE(approved_at, saved_at) DESC
        LIMIT ?
    """, (agent_id, max(1, min(limit, 100))))

    rows = c.fetchall()
    conn.close()

    items = []
    for r in rows:
        try:
            cd = json.loads(r["content"]) if r["content"] else {}
        except Exception:
            cd = {}

        # Use _compliance_verdict for consistent parsing
        verdict = _compliance_verdict(r["compliance"])
        if verdict == "pass":   comp_label = "pass"
        elif verdict == "warn": comp_label = "review"
        elif verdict == "fail": comp_label = "attention"
        else:                   comp_label = "pending"

        try:
            plats = json.loads(r["copied_platforms"] or "[]")
        except Exception:
            plats = []

        items.append({
            "id":          r["id"],
            "niche":       r["niche"] or "",
            "status":      r["status"] or "pending",
            "headline":    cd.get("headline", ""),
            "post":        (cd.get("post", "")[:200] + "...") if len(cd.get("post","")) > 200 else cd.get("post",""),
            "compliance":  comp_label,
            "platforms":   plats,
            "cir_id":      r["cir_id"] or "",
            "saved_at":    r["saved_at"] or "",
            "approved_at": r["approved_at"] or "",
            "published_at":r["published_at"] or "",
        })

    return items


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

def cancel_subscription(user_id: int):
    conn = get_conn()
    conn.execute("UPDATE users SET sub_status='cancelled', stripe_subscription_id=NULL WHERE id=?", (user_id,))
    conn.commit(); conn.close()


# ─────────────────────────────────────────────
# PASSWORD RESET
# ─────────────────────────────────────────────
def init_reset_tokens_table():
    """
    Legacy compatibility wrapper. password_reset_tokens is now created in init_db().
    Safe to call — CREATE TABLE IF NOT EXISTS is idempotent.
    """
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


# ─────────────────────────────────────────────
# LOCAL SIGNALS
# ─────────────────────────────────────────────

def signals_dedupe_check(user_id: int, source_url: str, headline: str) -> bool:
    """
    Returns True if this signal is a duplicate and should be skipped.
    Duplicate = same source_url (non-empty) OR headline that starts with
    the same first 80 characters as an existing signal for this user
    collected in the last 30 days.
    Called by signal_collector.py before every signals_save() call.
    """
    conn = get_conn()
    c    = conn.cursor()

    # URL-based dedup — same source URL already saved for this user recently
    if source_url and source_url.strip():
        c.execute("""
            SELECT COUNT(*) as n FROM local_signals
            WHERE user_id = ?
              AND source_url = ?
              AND collected_at > datetime('now', '-30 days')
        """, (user_id, source_url.strip()))
        if c.fetchone()["n"] > 0:
            conn.close()
            return True

    # Headline-based dedup — first 80 chars match an existing signal
    headline_prefix = headline.strip()[:80]
    c.execute("""
        SELECT COUNT(*) as n FROM local_signals
        WHERE user_id = ?
          AND substr(headline, 1, 80) = ?
          AND collected_at > datetime('now', '-30 days')
    """, (user_id, headline_prefix))
    is_dupe = c.fetchone()["n"] > 0
    conn.close()
    return is_dupe


def signals_save(user_id: int, area: str, headline: str, summary: str,
                 source_url: str, signal_type: str = "general",
                 relevance_score: float = 0.5, published_date: str = None,
                 source_type: str = "claude", context: str = "agent"):
    """Save a hyper-local signal for an agent.
    published_date — ISO date string of when the story was published (e.g. '2026-04-15').
    source_type    — 'rss' for RSS-sourced signals, 'claude' for Claude web search signals.
    context        — 'agent' for consumer-facing signals, 'hb_marketing' for agent/broker-facing signals.
    Signals older than 45 days are rejected in signal_collector.py before this is called.
    """
    from datetime import timedelta
    conn = get_conn()
    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
    conn.execute("""
        INSERT INTO local_signals
            (user_id, area, headline, summary, source_url, signal_type, relevance_score, expires_at, published_date, source_type, context)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, area, headline, summary, source_url, signal_type, relevance_score, expires_at, published_date, source_type, context))
    conn.commit()
    conn.close()


def signals_get_latest(user_id: int, limit: int = 5, context: str = "agent") -> list:
    """Get the most recent unused high-relevance signals for an agent.

    context — 'agent' returns consumer-facing signals for content generation and
              the Home panel in agent context. 'hb_marketing' returns agent/broker-
              facing signals for the Home panel in HB Marketing context.
              Defaults to 'agent' so all existing callers are unaffected.

    Priority order — location specificity first, then recency, then relevance:
      1. Hyper-local  (signal_type LIKE 'local:%')    — agent's specific service areas
      2. Metro        (signal_type LIKE 'metro:%')    — city/market level
      3. Local RSS    (signal_type = 'rss:*', area != 'National') — market RSS feeds
      4. National RSS (signal_type = 'rss:*', area = 'National') — national RSS feeds
      5. National     (signal_type LIKE 'national:%') — national Claude web search

    Within each tier: newest collected_at first, then relevance_score as tiebreaker.
    This ensures a Denver service-area story always beats a national NAR story,
    regardless of when each was collected or their relevance scores.
    """
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        SELECT *,
            CASE
                WHEN signal_type LIKE 'local:%'                                    THEN 1
                WHEN signal_type LIKE 'metro:%'                                    THEN 2
                WHEN signal_type LIKE 'rss:%'   AND area != 'National'             THEN 3
                WHEN signal_type LIKE 'rss:%'   AND area  = 'National'             THEN 4
                WHEN signal_type LIKE 'national:%'                                 THEN 5
                ELSE 4
            END AS tier_rank
        FROM local_signals
        WHERE user_id = ?
          AND used = 0
          AND (expires_at IS NULL OR expires_at > ?)
          AND (context = ? OR (context IS NULL AND ? = 'agent'))
        ORDER BY tier_rank ASC, collected_at DESC, relevance_score DESC
        LIMIT ?
    """, (user_id, now, context, context, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def signals_mark_used(signal_id: int):
    """Mark a signal as used so it doesn't surface again. Records used_at timestamp."""
    conn = get_conn()
    conn.execute(
        "UPDATE local_signals SET used = 1, used_at = datetime('now') WHERE id = ?",
        (signal_id,)
    )
    conn.commit()
    conn.close()


def signals_purge_expired():
    """Remove expired signals — called by the signal collector on each run."""
    conn = get_conn()
    now = datetime.utcnow().isoformat()
    conn.execute("DELETE FROM local_signals WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# USAGE LIMITS
# ─────────────────────────────────────────────

# USAGE SYSTEM — two-counter model
#
# PRIMARY UNIT: approved_post_count
#   Incremented when an agent approves a post (CIR issued).
#   This is the billable unit — what agents pay for.
#   Resets on the agent's billing_reset_day each month.
#
# ABUSE GUARD: generation_backstop_count
#   Incremented on every raw generation API call.
#   Not shown prominently to agents — background guardrail only.
#   Soft message when hit: "Review what you have before generating more."
#   Ratio: 3x the approved post limit.
#
# TRIAL: 10 lifetime generations, never resets.
#
# UNLIMITED_ROLES: super_admin and admin bypass all checks entirely.

# ─────────────────────────────────────────────
# NICHE TAXONOMY v2.1 — Session 56 — SINGLE SOURCE OF TRUTH
# ─────────────────────────────────────────────
# Structure: Asset Class > Primary Niche > Sub-niches
# This constant is the canonical definition for the entire platform.
# app.js, onboarding.html, and content_engine.py all derive from this.
# Never define niche names anywhere else. Never use fuzzy matching.
# If a niche name changes here, update all consuming files in the same session.
#
# Asset Classes: Residential (12), Commercial (6), Investment (4),
#                Land (4), Industrial and Infrastructure (4), Special Purpose (5)
# Total: 35 primary niches
# ─────────────────────────────────────────────

NICHE_TAXONOMY = {

    # RESIDENTIAL (12 primary niches)
    "Residential": {

        "First-Time Buyers": [
            "FHA and low-down-payment buyers",
            "Down payment assistance program buyers",
            "Rent-to-own and lease-option buyers",
            "Millennial and Gen Z buyers",
            "Co-buying partners (friends, siblings, unmarried couples)",
        ],

        "Single Family": [
            "Move-up buyers and growing families",
            "School-district movers",
            "Suburban lifestyle buyers",
            "Empty nesters selling family homes",
            "Sellers preparing homes for market",
        ],

        "Luxury Residential": [
            "High-end buyers ($1M+)",
            "Ultra-luxury and UHNW clients",
            "Second-home and vacation-property buyers",
            "International buyers",
            "Off-market and private listings",
        ],

        "Condominiums": [
            "Urban lifestyle and walkable-neighborhood buyers",
            "Downsizers and retirees seeking low maintenance",
            "Vacation-home and resort-area condo buyers",
            "First-time condo buyers",
            "HOA-savvy buyers and investors",
        ],

        "Multifamily (2-4 Units)": [
            "House hackers and owner-occupants",
            "Duplex, triplex, and quadplex buyers",
            "Small investors and first rental-property buyers",
            "Mom-and-pop landlords",
            "Value-add and light-rehab investors",
        ],

        "Seniors and Downsizing": [
            "Empty nesters",
            "Age-in-place transitions",
            "55+ community buyers",
            "Assisted living and care transitions",
            "Multigenerational family moves",
            "Rightsizing (larger or smaller based on life stage)",
        ],

        "Probate and Estate Sales": [
            "Inherited property sellers",
            "Estate-sale families",
            "Trust-held property transactions",
            "Court-appointed sales",
            "Heirs managing out-of-state inherited homes",
        ],

        "Divorce and Life Transitions": [
            "Court-ordered property sales",
            "Separation and division of assets",
            "Major life-change relocations (job loss, health, family crisis)",
            "Pre-divorce property valuation",
            "Collaborative divorce real estate",
        ],

        "Relocation": [
            "Corporate relocation buyers and sellers",
            "Military PCS moves",
            "Job-transfer households",
            "Remote-worker relocations",
            "International relocation to the US",
        ],

        "Veterans and Military": [
            "VA loan buyers",
            "PCS timing and dual-transaction management",
            "Military family housing",
            "Veteran first-time buyers",
            "Surviving spouse VA eligibility",
        ],

        "New Construction": [
            "Builder-rep and spec-home sales",
            "Custom-home clients",
            "New community and master-planned buyers",
            "Builder incentive and rate-buydown navigation",
            "Lot selection and upgrade guidance",
        ],

        "Manufactured and Mobile Homes": [
            "Affordable-housing and budget-conscious buyers",
            "Land-lease community buyers",
            "Senior mobile-home park buyers",
            "Retirement-community manufactured homes",
            "Manufactured home on owned land",
        ],
    },

    # COMMERCIAL (6 primary niches)
    "Commercial": {

        "Retail": [
            "Small business owners and storefront tenants",
            "Franchise location buyers",
            "Shopping center and strip-center investors",
            "NNN lease investors",
            "Restaurant and food-service spaces",
        ],

        "Office": [
            "Professional service firms (law, accounting, consulting)",
            "Medical and dental office users",
            "Small office and coworking operators",
            "Corporate headquarters relocations",
            "Flex-office and hybrid-workspace buyers",
        ],

        "Hospitality": [
            "Hotel investors and boutique-hotel buyers",
            "Extended-stay operators",
            "Resort and leisure-market buyers",
            "Short-term lodging investors",
            "Owner-operated hospitality properties",
        ],

        "Multifamily (5+ Units)": [
            "Apartment building investors",
            "Workforce and affordable housing operators",
            "Value-add multifamily repositioning",
            "Syndication and joint-venture investors",
            "Student housing operators",
        ],

        "Mixed-Use and 1031 Exchange": [
            "1031 exchange buyers (tax-deferred swaps)",
            "Mixed-use property buyers (live-work, retail-residential)",
            "NNN and passive-income investors",
            "Portfolio diversification buyers",
            "Opportunity Zone investors",
        ],

        "Commercial Specialty": [
            "Business expansion and franchise growth",
            "Special-use commercial (car washes, gas stations, auto service)",
            "Owner-operator commercial buyers",
            "Tenant representation",
        ],
    },

    # INVESTMENT (4 primary niches) — NEW in v2.1
    "Investment": {

        "Fix and Flip": [
            "Rehab investors and ARV specialists",
            "Wholesale deal sourcing",
            "Contractor-network buyers",
            "First-time flip investors",
            "High-volume flip operators",
        ],

        "Long-Term Rentals": [
            "Buy-and-hold portfolio builders",
            "BRRRR strategy investors",
            "Turnkey rental buyers",
            "Section 8 and affordable rental operators",
            "Out-of-state rental investors",
        ],

        "Short-Term Rentals": [
            "Airbnb and VRBO operators",
            "Vacation rental investors",
            "Mid-term rental operators (30-90 day stays)",
            "Furnished rental investors",
            "STR regulation-savvy buyers",
        ],

        "Property Management": [
            "Landlord services and tenant placement",
            "Portfolio management and owner reporting",
            "Maintenance coordination and vendor management",
            "Rent collection and lease enforcement",
            "Property management company operators",
        ],
    },

    # LAND (4 primary niches)
    "Land": {

        "Raw Land": [
            "Rural lifestyle buyers and homesteaders",
            "Off-grid and self-sufficient buyers",
            "Recreational land buyers",
            "Acreage and ranchette buyers",
        ],

        "Development Land": [
            "Builders and subdivision developers",
            "Infill developers",
            "Entitlement buyers and land assemblers",
            "Spec and build-to-rent developers",
        ],

        "Agricultural Land": [
            "Farmers and ranchers",
            "Crop producers",
            "Legacy family-land buyers",
            "Conservation-minded buyers",
        ],

        "Land Specialty": [
            "Recreational and hunting land buyers",
            "Timberland investors",
            "Conservation easement buyers",
            "Transitional land and future-development investors",
            "Water-rights and mineral-rights properties",
        ],
    },

    # INDUSTRIAL AND INFRASTRUCTURE (4 primary niches)
    "Industrial and Infrastructure": {

        "Data Centers": [
            "Technology operators and cloud infrastructure users",
            "Hyperscale campus buyers",
            "Edge data center operators",
            "Colocation facility users",
            "Institutional data center investors",
        ],

        "Warehouse and Logistics": [
            "Distribution and fulfillment operators",
            "Last-mile delivery locations",
            "Cold storage and temperature-controlled facilities",
            "E-commerce logistics facilities",
            "Third-party logistics (3PL) operators",
        ],

        "Light Industrial Flex": [
            "Trades businesses and contractors",
            "Small manufacturers and assembly operations",
            "Service-and-storage users",
            "Maker spaces and creative industrial",
        ],

        "Industrial Specialty": [
            "Telecom and fiber infrastructure operators",
            "Powered shell buyers",
            "Network facility operators",
            "Specialized infrastructure investors",
        ],
    },

    # SPECIAL PURPOSE (5 primary niches)
    "Special Purpose": {

        "Healthcare": [
            "Assisted living and senior-care operators",
            "Skilled nursing facility buyers",
            "Medical campus and MOB investors",
            "Behavioral health facility buyers",
            "Urgent care and therapy-clinic users",
        ],

        "Institutional": [
            "Schools and charter-school operators",
            "Religious organizations and worship facilities",
            "Nonprofits and community organizations",
            "Government-use property buyers",
        ],

        "Storage": [
            "Self-storage investors",
            "Value-add storage operators",
            "Climate-controlled storage buyers",
            "Small-market storage operators",
        ],

        "Special Purpose Specialty": [
            "Daycare operators and childcare facility buyers",
            "Entertainment venues and event centers",
            "Sports and recreation facility operators",
            "Car wash and auto-service investors",
        ],

        "Distressed and Pre-Foreclosure": [
            "Short sale specialists",
            "Foreclosure and REO buyers",
            "Loss mitigation and lender negotiation",
            "Pre-foreclosure intervention and counseling",
            "Homeowner hardship transitions",
        ],
    },
}

# Compliance profile map — keyed to Asset Class
# Used by content_engine.py to select the right compliance check profile.
# Derived from NICHE_TAXONOMY asset class keys. Do not add keys here that
# are not asset class names in NICHE_TAXONOMY.
# Investment profile is new in v2.1 — includes SEC, FinCEN, and financial
# projection rules in addition to standard residential checks.
# Data Centers use the data_center profile; all other Industrial and
# Infrastructure niches use the commercial profile.
ASSET_CLASS_COMPLIANCE = {
    "Residential":                  "residential",
    "Commercial":                   "commercial",
    "Investment":                   "investment",
    "Land":                         "residential",
    "Industrial and Infrastructure": "commercial",   # Data Centers overridden per-niche in content_engine.py
    "Special Purpose":              "commercial",
}

# Helper: get all primary niche names across all asset classes
def get_all_primary_niches() -> list:
    """Returns a flat list of all primary niche names from NICHE_TAXONOMY."""
    result = []
    for asset_class, primaries in NICHE_TAXONOMY.items():
        result.extend(primaries.keys())
    return result

# Helper: get asset class for a given primary niche name
def get_asset_class_for_niche(primary_niche: str) -> str:
    """Returns the asset class name for a given primary niche. Empty string if not found."""
    for asset_class, primaries in NICHE_TAXONOMY.items():
        if primary_niche in primaries:
            return asset_class
    return ""

# Helper: get compliance profile for a primary niche
def get_compliance_profile_for_niche(primary_niche: str) -> str:
    """
    Returns the compliance profile string for a primary niche.
    Data Centers use the data_center profile regardless of asset class.
    All other niches derive their profile from their asset class.
    """
    if primary_niche == "Data Centers":
        return "data_center"
    asset_class = get_asset_class_for_niche(primary_niche)
    return ASSET_CLASS_COMPLIANCE.get(asset_class, "residential")


PLAN_LIMITS = {
    # plan_key: {"posts": N, "backstop": N*3, "niches": N, "videos": N}
    # posts    = approved post limit per billing period
    # backstop = raw generation ceiling per billing period (abuse guard)
    # niches   = max saved niches (enforced in save_agent_setup for trial only)
    #            Paid plans: unlimited. Token abuse is controlled by posts +
    #            backstop limits. Niche limits on paid plans created UX friction
    #            without meaningfully reducing abuse. — Session 54 decision.
    # videos   = avatar video renders per calendar month (includes regenerations).
    #            0 = video feature disabled for this plan.
    #            Resets on the 1st of each month (video_month_reset in users table).
    #            Top-up packs add to addon_video_limit (+10 per $19 pack).
    #
    # Video limit rationale — Session 49:
    #   Trial: 0   — video is a paid-plan benefit, not a trial feature
    #   Starter: 5 — enough to see value, not enough to abuse (~$7.50 cost/mo)
    #   Founding Member: 10 — early adopter bonus (~$15 cost/mo)
    #   Professional: 20 — primary use case for coaches/professionals (~$30 cost/mo)
    #   Coach: 20 — same as professional, B2B content focus (~$30 cost/mo)
    #   Power: 30 — highest tier, maximum value (~$45 cost/mo)
    #   Insider: 30 — matches Power, manually granted accounts
    "trial":           {"posts": 10,   "backstop": 30,   "niches": 2,   "videos": 0,  "lifetime": True},
    "founding_member": {"posts": 50,   "backstop": 150,  "niches": 999, "videos": 10, "lifetime": False},
    "starter":         {"posts": 50,   "backstop": 150,  "niches": 999, "videos": 5,  "lifetime": False},
    "professional":    {"posts": 60,   "backstop": 200,  "niches": 999, "videos": 20, "lifetime": False},
    "power":           {"posts": 100,  "backstop": 350,  "niches": 999, "videos": 30, "lifetime": False},
    # COACH — added Session 49
    # B2B plan for real estate coaches. $199/month. Stripe product created
    # Session 48. Nav/context built Session 50.
    "coach":           {"posts": 100,  "backstop": 350,  "niches": 999, "videos": 20, "lifetime": False},
    # INSIDER — DO NOT REMOVE
    # Granted manually by Kevin to influencer agents, beta evaluators, and
    # HomeBridge Group staff who need full platform access at no charge.
    # Never self-serve. Never in Stripe. Kevin sets plan="insider" directly
    # in the DB via the admin panel or SQL. Role stays "agent" — no admin
    # privileges. Billing panel is hidden for this plan. Never delete this key.
    "insider":         {"posts": 100,  "backstop": 350,  "niches": 999, "videos": 30, "lifetime": False},
    # Legacy keys — kept so existing DB rows never break
    "agent":           {"posts": 30,   "backstop": 90,   "niches": 999, "videos": 0,  "lifetime": False},
    "team":            {"posts": 75,   "backstop": 225,  "niches": 999, "videos": 0,  "lifetime": False},
    "office_starter":  {"posts": 150,  "backstop": 450,  "niches": 999, "videos": 0,  "lifetime": False},
    "office_growth":   {"posts": 400,  "backstop": 1200, "niches": 999, "videos": 0,  "lifetime": False},
    "enterprise":      {"posts": 9999, "backstop": 9999, "niches": 999, "videos": 999,"lifetime": False},
}

# Roles that are never limited — bypass all checks
UNLIMITED_ROLES = {"super_admin", "admin"}

# Hard rate limit — max generations per hour per account (bot protection)
HOURLY_RATE_LIMIT = 10


def _get_plan_limits(plan: str) -> dict:
    """Return the posts and backstop limits for a plan. Safe fallback to trial."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["trial"])


def _compute_next_billing_reset(reset_day: int) -> datetime:
    """
    Compute the next billing reset datetime from a day-of-month (1-28).
    If today is before reset_day this month, reset is this month.
    If today is on or after reset_day, reset is next month.
    Clamps to 28 to avoid Feb/short-month issues.
    """
    today = datetime.utcnow()
    day   = min(max(int(reset_day or 1), 1), 28)
    # Try this month first
    try:
        candidate = today.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        candidate = today.replace(day=28, hour=0, minute=0, second=0, microsecond=0)
    if candidate <= today:
        # Move to next month
        if today.month == 12:
            candidate = candidate.replace(year=today.year + 1, month=1)
        else:
            candidate = candidate.replace(month=today.month + 1)
    return candidate


def _check_and_reset_if_due(conn, user_id: int, row: dict, plan: str) -> dict:
    """
    Check whether the billing period has rolled over and reset counters if so.
    Returns the (possibly reset) row values as a plain dict.
    Trial accounts never reset — their counters are lifetime.
    Modifies the DB in place if reset is needed.
    Returns dict with keys: approved_post_count, generation_backstop_count,
    generation_reset_date, billing_reset_day, addon_posts_limit, addon_backstop_limit.
    """
    limits = _get_plan_limits(plan)
    if limits.get("lifetime"):
        # Trial — never reset
        return dict(row)

    reset_day  = row["billing_reset_day"] or 1
    reset_date = row["generation_reset_date"]
    today      = datetime.utcnow()

    needs_reset = False
    if not reset_date:
        needs_reset = True
    else:
        try:
            if today >= datetime.fromisoformat(reset_date):
                needs_reset = True
        except Exception:
            needs_reset = True

    if needs_reset:
        next_reset = _compute_next_billing_reset(reset_day)
        conn.execute("""
            UPDATE users
            SET approved_post_count       = 0,
                generation_backstop_count = 0,
                generation_reset_date     = ?,
                addon_posts_limit         = 0,
                addon_backstop_limit      = 0
            WHERE id = ?
        """, (next_reset.isoformat(), user_id))
        conn.commit()
        return {
            "approved_post_count":       0,
            "generation_backstop_count": 0,
            "generation_reset_date":     next_reset.isoformat(),
            "billing_reset_day":         reset_day,
            "addon_posts_limit":         0,
            "addon_backstop_limit":      0,
        }
    return dict(row)


def check_post_approval_allowed(user_id: int, role: str, plan: str) -> dict:
    """
    Check whether this user can approve one more post (consume a post credit).
    Called from PATCH /library/{item_id} when status changes to 'approved'.

    Returns:
        allowed        — bool
        posts_used     — approved posts this period
        posts_limit    — total approved post limit (base + addon)
        backstop_used  — generations this period
        backstop_limit — generation backstop (base + addon)
        resets_on      — human-readable reset date string
    """
    if role in UNLIMITED_ROLES:
        return {
            "allowed": True, "posts_used": 0, "posts_limit": 9999,
            "backstop_used": 0, "backstop_limit": 9999, "resets_on": None,
        }

    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT approved_post_count, generation_backstop_count,
               generation_reset_date, billing_reset_day,
               addon_posts_limit, addon_backstop_limit
        FROM users WHERE id = ?
    """, (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"allowed": False, "posts_used": 0, "posts_limit": 0,
                "backstop_used": 0, "backstop_limit": 0, "resets_on": None}

    row = _check_and_reset_if_due(conn, user_id, row, plan)
    conn.close()

    limits         = _get_plan_limits(plan)
    posts_limit    = limits["posts"]    + (row["addon_posts_limit"]    or 0)
    backstop_limit = limits["backstop"] + (row["addon_backstop_limit"] or 0)
    posts_used     = row["approved_post_count"]       or 0
    backstop_used  = row["generation_backstop_count"] or 0

    reset_day  = row["billing_reset_day"] or 1
    next_reset = _compute_next_billing_reset(reset_day)
    resets_on  = next_reset.strftime("%B %-d, %Y")

    return {
        "allowed":        posts_used < posts_limit,
        "posts_used":     posts_used,
        "posts_limit":    posts_limit,
        "backstop_used":  backstop_used,
        "backstop_limit": backstop_limit,
        "resets_on":      resets_on,
    }


def check_generation_backstop_allowed(user_id: int, role: str, plan: str) -> dict:
    """
    Check whether this user can perform another generation (backstop guard).
    Called before every Claude API call in content_engine.py.
    Does NOT check approved post count — that's check_post_approval_allowed().

    Returns:
        allowed        — bool (False = soft stop, show review message)
        backstop_used  — generations this period
        backstop_limit — ceiling for this period
        resets_on      — human-readable reset date
    """
    if role in UNLIMITED_ROLES:
        return {"allowed": True, "backstop_used": 0, "backstop_limit": 9999, "resets_on": None}

    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT approved_post_count, generation_backstop_count,
               generation_reset_date, billing_reset_day,
               addon_posts_limit, addon_backstop_limit
        FROM users WHERE id = ?
    """, (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"allowed": True, "backstop_used": 0, "backstop_limit": 9999, "resets_on": None}

    row = _check_and_reset_if_due(conn, user_id, row, plan)
    conn.close()

    limits         = _get_plan_limits(plan)
    backstop_limit = limits["backstop"] + (row["addon_backstop_limit"] or 0)
    backstop_used  = row["generation_backstop_count"] or 0

    # Trial: backstop is also lifetime
    if limits.get("lifetime"):
        posts_used  = row["approved_post_count"] or 0
        posts_limit = limits["posts"]
        allowed     = posts_used < posts_limit  # trial gates on approved posts, not backstop
        return {
            "allowed":        allowed,
            "backstop_used":  backstop_used,
            "backstop_limit": posts_limit,
            "resets_on":      None,
        }

    reset_day  = row["billing_reset_day"] or 1
    next_reset = _compute_next_billing_reset(reset_day)
    resets_on  = next_reset.strftime("%B %-d, %Y")

    return {
        "allowed":        backstop_used < backstop_limit,
        "backstop_used":  backstop_used,
        "backstop_limit": backstop_limit,
        "resets_on":      resets_on,
    }


def record_generation(user_id: int, role: str) -> None:
    """
    Increment generation_backstop_count for one raw generation call.
    Never called for demo-token or UNLIMITED_ROLES.
    Never blocks the request — fire and forget, called after generation succeeds.
    """
    if role in UNLIMITED_ROLES:
        return
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE users SET generation_backstop_count = COALESCE(generation_backstop_count, 0) + 1 WHERE id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Usage] record_generation failed for user {user_id}: {e}")


def record_post_approval(user_id: int, role: str) -> None:
    """
    Increment approved_post_count when a CIR is issued (status approved).
    This is the primary billing counter.
    Never called for UNLIMITED_ROLES.
    """
    if role in UNLIMITED_ROLES:
        return
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE users SET approved_post_count = COALESCE(approved_post_count, 0) + 1 WHERE id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Usage] record_post_approval failed for user {user_id}: {e}")


def apply_addon_pack(user_id: int) -> dict:
    """
    Apply one Add-on Pack purchase to a user's current billing period.
    Adds 30 approved posts and 90 backstop credits.
    Stackable — call once per pack purchased.
    Returns updated limits for confirmation.
    """
    conn = get_conn()
    conn.execute("""
        UPDATE users
        SET addon_posts_limit    = COALESCE(addon_posts_limit, 0)    + 30,
            addon_backstop_limit = COALESCE(addon_backstop_limit, 0) + 90
        WHERE id = ?
    """, (user_id,))
    conn.commit()
    c = conn.cursor()
    c.execute("SELECT addon_posts_limit, addon_backstop_limit FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return {
        "addon_posts_limit":    row["addon_posts_limit"]    if row else 0,
        "addon_backstop_limit": row["addon_backstop_limit"] if row else 0,
    }


def set_billing_reset_day(user_id: int, day: int) -> None:
    """
    Set the day-of-month on which this agent's billing period resets.
    Called by the Stripe webhook on subscription creation.
    Clamped to 1-28 to avoid month-end edge cases.
    """
    day = min(max(int(day), 1), 28)
    conn = get_conn()
    conn.execute("UPDATE users SET billing_reset_day = ? WHERE id = ?", (day, user_id))
    conn.commit()
    conn.close()


def activate_subscription(user_id: int, plan: str, billing_cycle: str,
                           stripe_customer_id: str, stripe_subscription_id: str,
                           billing_reset_day: int = 1):
    """
    Activate a subscription for a user.
    Sets plan, billing cycle, Stripe IDs, and billing reset day.
    Resets counters for the new billing period.
    """
    day = min(max(int(billing_reset_day or 1), 1), 28)
    next_reset = _compute_next_billing_reset(day)
    conn = get_conn()
    conn.execute("""
        UPDATE users
        SET plan                      = ?,
            billing_cycle             = ?,
            sub_status                = 'active',
            stripe_customer_id        = ?,
            stripe_subscription_id    = ?,
            billing_reset_day         = ?,
            generation_reset_date     = ?,
            approved_post_count       = 0,
            generation_backstop_count = 0,
            addon_posts_limit         = 0,
            addon_backstop_limit      = 0
        WHERE id = ?
    """, (plan, billing_cycle, stripe_customer_id, stripe_subscription_id,
          day, next_reset.isoformat(), user_id))
    conn.commit()
    conn.close()


# Keep usage_check and usage_increment as thin compatibility shims
# These are still imported by content_engine.py and app.py in places.
# They now delegate to the new two-counter system.
# Remove these once all call sites are updated.
def usage_check(user_id: int, role: str, plan: str) -> dict:
    """Compatibility shim — delegates to check_generation_backstop_allowed."""
    result = check_generation_backstop_allowed(user_id, role, plan)
    return {
        "allowed":   result["allowed"],
        "used":      result["backstop_used"],
        "limit":     result["backstop_limit"],
        "resets_on": result["resets_on"],
    }


def usage_increment(user_id: int):
    """Compatibility shim — use record_generation() for new call sites."""
    pass  # No-op — generation recording now happens via record_generation()


def _usage_reset(user_id: int, next_reset_iso: str):
    """Compatibility shim — reset now happens inside _check_and_reset_if_due."""
    pass


def usage_set_limit(user_id: int, limit: int):
    """Admin override — sets the base monthly_limit column (legacy). Use apply_addon_pack() for packs."""
    conn = get_conn()
    conn.execute("UPDATE users SET monthly_limit = ? WHERE id = ?", (limit, user_id))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# PARTNER PROGRAM
# ─────────────────────────────────────────────
# Always "Partner Program" — never "affiliate program"
# Earnings are "Partner Rewards" — never "commissions"
# Tiers: 'referral' (15% / 24mo), 'broker' (20% / lifetime), 'elite' (25% / lifetime)

def partner_enroll(user_id: int, tier: str = "referral") -> dict:
    """
    Enroll a user in the Partner Program. Generates a unique referral code.
    Auto-approves Referral tier; Broker tier requires admin approval.
    Returns the partner record.
    """
    import secrets
    conn = get_conn()
    c    = conn.cursor()

    # Generate a unique 8-char referral code
    for _ in range(10):
        code = secrets.token_hex(4).upper()  # e.g. "A3F2B1C8"
        c.execute("SELECT id FROM partners WHERE referral_code=?", (code,))
        if not c.fetchone():
            break

    status = "active" if tier == "referral" else "pending"
    approved_at = datetime.utcnow().isoformat() if tier == "referral" else None

    c.execute("""
        INSERT INTO partners (user_id, tier, status, referral_code, enrolled_at, approved_at)
        VALUES (?, ?, ?, ?, datetime('now'), ?)
        ON CONFLICT(user_id) DO UPDATE SET
            tier        = excluded.tier,
            status      = excluded.status,
            approved_at = excluded.approved_at
    """, (user_id, tier, status, code, approved_at))

    # Mirror referral_code onto users table for fast lookup
    conn.execute(
        "UPDATE users SET partner_tier=?, partner_code=? WHERE id=?",
        (tier, code, user_id)
    )
    conn.commit()

    c.execute("SELECT * FROM partners WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}


def partner_get(user_id: int) -> Optional[dict]:
    """Get a partner record by user_id."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT * FROM partners WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def partner_get_by_code(code: str) -> Optional[dict]:
    """Look up a partner by their referral code. Used at subscription time."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT p.*, u.email, u.agent_name
        FROM partners p
        JOIN users u ON u.id = p.user_id
        WHERE p.referral_code=? AND p.status='active'
    """, (code.upper(),))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def partner_approve(partner_id: int, approved_by: int) -> bool:
    """Approve a pending partner (Broker/Elite tier admin action)."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        "UPDATE partners SET status='active', approved_at=datetime('now'), approved_by=? WHERE id=? AND status='pending'",
        (approved_by, partner_id)
    )
    affected = c.rowcount
    if affected:
        c.execute("SELECT user_id, tier, referral_code FROM partners WHERE id=?", (partner_id,))
        row = c.fetchone()
        if row:
            conn.execute(
                "UPDATE users SET partner_tier=?, partner_code=? WHERE id=?",
                (row["tier"], row["referral_code"], row["user_id"])
            )
    conn.commit()
    conn.close()
    return affected > 0


def partner_list_all() -> list:
    """Return all partner records — admin use only."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT p.*, u.email, u.agent_name, u.brokerage
        FROM partners p
        JOIN users u ON u.id = p.user_id
        ORDER BY p.enrolled_at DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def referral_attribute(partner_id: int, referred_user_id: int,
                       attribution_type: str = "link",
                       referral_code: str = None) -> bool:
    """
    Record that a partner referred a new subscriber.
    Last-touch wins — UPSERT on referred_user_id (unique constraint).
    attribution_type: 'link' (20-day cookie) | 'code' (verbal, no expiry)

    Insider Partner override detection:
    If the partner making the referral (partner_id) has is_insider_partner = 1,
    this is a direct Insider referral — no override_partner_id is set because
    the Insider IS the direct partner earning 25%.

    If the partner making the referral was themselves recruited by an Insider
    (i.e., the partner's own referral_attributions row has an override_partner_id),
    that Insider's partner_id is propagated forward onto this new attribution row
    so the payout calculator can generate the 5% override line at quarter-end.
    """
    conn = get_conn()
    c    = conn.cursor()
    try:
        # Check if the referring partner is an Insider themselves
        c.execute(
            "SELECT is_insider_partner FROM partners WHERE id = ?",
            (partner_id,)
        )
        referring_partner_row = c.fetchone()
        referring_is_insider = (
            referring_partner_row and referring_partner_row["is_insider_partner"]
        ) if referring_partner_row else False

        # Check if the referring partner was themselves recruited by an Insider
        # (i.e., do they have an override_partner_id on their own attribution row?)
        override_id = None
        if not referring_is_insider:
            c.execute(
                """SELECT ra.override_partner_id
                   FROM referral_attributions ra
                   JOIN partners p ON p.id = ra.partner_id
                   WHERE p.id = ?
                   LIMIT 1""",
                (partner_id,)
            )
            override_row = c.fetchone()
            if override_row and override_row["override_partner_id"]:
                override_id = override_row["override_partner_id"]

        c.execute("""
            INSERT INTO referral_attributions
                (partner_id, referred_user_id, attribution_type, referral_code,
                 attributed_at, override_partner_id)
            VALUES (?, ?, ?, ?, datetime('now'), ?)
            ON CONFLICT(referred_user_id) DO UPDATE SET
                partner_id          = excluded.partner_id,
                attribution_type    = excluded.attribution_type,
                referral_code       = excluded.referral_code,
                attributed_at       = datetime('now'),
                override_partner_id = excluded.override_partner_id
        """, (partner_id, referred_user_id, attribution_type, referral_code, override_id))

        # Increment partner's total_referred
        conn.execute(
            "UPDATE partners SET total_referred = total_referred + 1 WHERE id=?",
            (partner_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[Partner] Attribution failed: {e}")
        return False
    finally:
        conn.close()


def referral_convert(referred_user_id: int) -> bool:
    """Mark a referral as converted (subscriber activated their account)."""
    conn = get_conn()
    conn.execute(
        "UPDATE referral_attributions SET converted_at=datetime('now') WHERE referred_user_id=? AND converted_at IS NULL",
        (referred_user_id,)
    )
    conn.commit()
    conn.close()
    return True


def referral_mark_paying(user_id: int) -> None:
    """
    Mark the referral attribution for a user as actively paying.
    Called by the Stripe billing webhook on checkout.session.completed (subscription mode).
    Sets is_active = 1 and records first_payment_at if not already set.
    The quarterly tier evaluator and payout calculator read is_active = 1 exclusively —
    without this being set, a partner's tier never advances and payouts are always $0.
    Non-blocking: logs on failure but never raises.
    """
    try:
        conn = get_conn()
        conn.execute(
            """UPDATE referral_attributions
               SET is_active      = 1,
                   first_payment_at = COALESCE(first_payment_at, datetime('now'))
               WHERE referred_user_id = ?""",
            (user_id,)
        )
        conn.commit()
        conn.close()
        print(f"[Partner] Referral marked paying for user {user_id}")
    except Exception as e:
        print(f"[Partner] referral_mark_paying failed for user {user_id}: {e}")


def referral_mark_lapsed(user_id: int) -> None:
    """
    Mark the referral attribution for a user as no longer paying.
    Called by the Stripe billing webhook on:
      - customer.subscription.deleted
      - customer.subscription.paused
      - invoice.payment_failed (after Stripe grace period)
    Sets is_active = 0 so the subscriber stops counting toward the partner's
    tier and is excluded from payout calculations at quarter-end.
    Non-blocking: logs on failure but never raises.
    """
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE referral_attributions SET is_active = 0 WHERE referred_user_id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()
        print(f"[Partner] Referral marked lapsed for user {user_id}")
    except Exception as e:
        print(f"[Partner] referral_mark_lapsed failed for user {user_id}: {e}")


def partner_set_insider(partner_id: int, is_insider: bool, set_by: int) -> bool:
    """
    Elevate or demote a partner's Insider Partner status.
    Admin/SuperAdmin only — never self-assigned.

    When is_insider=True:
      - Sets partners.is_insider_partner = 1
      - Partner earns 25% on their own direct referrals (no tier threshold)
      - Partner earns 5% override on referrals generated by partners they
        personally recruited (identified via referral_attributions.override_partner_id)

    When is_insider=False:
      - Sets partners.is_insider_partner = 0
      - Partner reverts to standard tier earnings
      - Existing override_partner_id relationships are preserved in DB for
        audit purposes but the payout calculator checks is_insider_partner
        at run time, so no further override payouts will be generated

    Returns True if a row was updated, False if partner_id not found.
    Caller (admin endpoint) is responsible for writing the audit log entry.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        "UPDATE partners SET is_insider_partner = ? WHERE id = ?",
        (1 if is_insider else 0, partner_id)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def partner_assign_override(partner_id: int, insider_partner_id: int,
                             assigned_by: int) -> bool:
    """
    Manually assign an Insider Partner as the override earner for all of a
    given partner's referral attribution rows.

    Called from the Admin Panel when an Insider claims they recruited a partner
    but the partner didn't enter the Insider's code at signup.

    FORWARD-ONLY: only updates referral_attributions rows where override_partner_id
    IS NULL. Does not touch rows that already have an override assigned (those were
    either set at enrollment or by a previous admin assignment). This prevents
    retroactive recalculation of already-processed payouts.

    partner_id         — the partners.id of the partner being assigned
    insider_partner_id — the partners.id of the Insider claiming override credit
    assigned_by        — users.id of the admin making the assignment (for audit)

    Returns True if any rows were updated, False if partner not found or all rows
    already have overrides assigned.

    Caller (admin endpoint) is responsible for writing the audit log entry,
    including a note explaining why the manual assignment was made.
    """
    conn = get_conn()
    c    = conn.cursor()

    # Verify the insider_partner_id actually has is_insider_partner = 1
    c.execute(
        "SELECT id, is_insider_partner FROM partners WHERE id = ?",
        (insider_partner_id,)
    )
    insider_row = c.fetchone()
    if not insider_row or not insider_row["is_insider_partner"]:
        conn.close()
        return False

    # Update only NULL override rows for this partner (forward-only)
    c.execute(
        """UPDATE referral_attributions
           SET override_partner_id = ?
           WHERE partner_id = ?
             AND override_partner_id IS NULL""",
        (insider_partner_id, partner_id)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def partner_remove_override(partner_id: int, removed_by: int) -> bool:
    """
    Remove the override assignment for a partner's referral attributions.
    Used if an Insider override was assigned in error.

    Only clears rows where override_partner_id is currently set.
    Caller is responsible for writing the audit log entry.
    Returns True if any rows were cleared.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        """UPDATE referral_attributions
           SET override_partner_id = NULL
           WHERE partner_id = ?
             AND override_partner_id IS NOT NULL""",
        (partner_id,)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def record_video_consent(user_id: int) -> None:
    """
    Record the timestamp when an agent explicitly consented to video likeness use.
    Consent is separate from voice_consent_at — video processing (face geometry
    via HeyGen) requires its own distinct consent record.
    Must be stored before any video render is permitted.
    Called by POST /video/consent endpoint.
    Idempotent: safe to call again — timestamp is not overwritten if already set.
    """
    conn = get_conn()
    conn.execute(
        "UPDATE users SET video_consent_at = datetime('now') WHERE id = ? AND video_consent_at IS NULL",
        (user_id,)
    )
    conn.commit()
    conn.close()


def partner_payout_create(partner_id: int, amount: float,
                           period_start: str, period_end: str) -> dict:
    """
    Create a pending payout record for a partner.
    Called by the monthly reward cycle job.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO partner_payouts (partner_id, amount, period_start, period_end, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (partner_id, amount, period_start, period_end))
    conn.commit()
    payout_id = c.lastrowid
    c.execute("SELECT * FROM partner_payouts WHERE id=?", (payout_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}


def partner_payout_list(partner_id: int) -> list:
    """Return all payout records for a partner, newest first."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT * FROM partner_payouts WHERE partner_id=?
        ORDER BY created_at DESC
    """, (partner_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def partner_payout_mark_paid(payout_id: int, stripe_transfer_id: str) -> bool:
    """Mark a payout as paid after Stripe Connect transfer completes."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        UPDATE partner_payouts
        SET status='paid', stripe_transfer_id=?, paid_at=datetime('now')
        WHERE id=? AND status IN ('pending','processing')
    """, (stripe_transfer_id, payout_id))
    # Update partner's total_earned
    c.execute("SELECT amount, partner_id FROM partner_payouts WHERE id=?", (payout_id,))
    row = c.fetchone()
    if row:
        conn.execute(
            "UPDATE partners SET total_earned = total_earned + ? WHERE id=?",
            (row["amount"], row["partner_id"])
        )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def partner_payout_list_all_pending() -> list:
    """Return all pending payouts — admin use for payout processing."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT pp.*, p.tier, p.referral_code, u.email, u.agent_name
        FROM partner_payouts pp
        JOIN partners p ON p.id = pp.partner_id
        JOIN users u ON u.id = p.user_id
        WHERE pp.status = 'pending'
        ORDER BY pp.created_at ASC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ─────────────────────────────────────────────
# MARKET REPORTS — Session 22
# Agent-uploaded PDFs (MLS, RPR, Altos, title co., etc.)
# user_id is enforced on every query — agent-only, never cross-user.
# ─────────────────────────────────────────────

def market_report_save(
    user_id: int,
    filename: str,
    source_label: str = "MLS",
    report_month: str = None,
    report_area: str = None,
    extracted_data: dict = None,
) -> dict:
    """
    Save a new market report record for an agent.
    PDF bytes are NOT stored — only the filename, metadata, and extracted stats.
    extracted_data: structured dict from Claude extraction — stored as JSON.
    Returns the saved record as a dict.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO market_reports
            (user_id, filename, source_label, report_month, report_area,
             extracted_data, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        user_id,
        filename,
        source_label or "MLS",
        report_month,
        report_area,
        json.dumps(extracted_data) if extracted_data else None,
    ))
    conn.commit()
    report_id = c.lastrowid
    conn.close()
    return market_report_get(report_id, user_id)


def market_report_get(report_id: int, user_id: int) -> Optional[dict]:
    """
    Fetch a single market report by id.
    user_id is always enforced — agents can only fetch their own reports.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT id, user_id, filename, source_label, report_month,
               report_area, extracted_data, uploaded_at
        FROM market_reports
        WHERE id = ? AND user_id = ?
    """, (report_id, user_id))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return _market_report_row(row)


def market_report_list(user_id: int) -> list:
    """
    Return all market reports for an agent, newest first.
    PDF bytes are never stored — only extracted stats and metadata.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT id, user_id, filename, source_label, report_month,
               report_area, extracted_data, uploaded_at
        FROM market_reports
        WHERE user_id = ?
        ORDER BY uploaded_at DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return [_market_report_row(r) for r in rows]


def market_report_update_extracted(report_id: int, user_id: int, extracted_data: dict) -> Optional[dict]:
    """
    Update the extracted_data JSON for a report after Claude processes it.
    Called after a successful extraction so the data is available for re-generation.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        UPDATE market_reports
        SET extracted_data = ?
        WHERE id = ? AND user_id = ?
    """, (json.dumps(extracted_data), report_id, user_id))
    conn.commit()
    conn.close()
    return market_report_get(report_id, user_id)


def market_report_delete(report_id: int, user_id: int) -> bool:
    """
    Delete a market report. user_id enforced — agents can only delete their own.
    Returns True if a row was deleted.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        "DELETE FROM market_reports WHERE id = ? AND user_id = ?",
        (report_id, user_id)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def _market_report_row(row) -> dict:
    """Serialize a market_reports DB row to a dict for API responses."""
    extracted = None
    try:
        raw = row["extracted_data"]
        if raw:
            extracted = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        pass
    return {
        "id":            row["id"],
        "userId":        row["user_id"],
        "filename":      row["filename"],
        "sourceLabel":   row["source_label"] or "MLS",
        "reportMonth":   row["report_month"],
        "reportArea":    row["report_area"],
        "extractedData": extracted,
        "uploadedAt":    row["uploaded_at"],
    }


# ─────────────────────────────────────────────
# CONTACTS — marketing site form submissions (Session 24)
# ─────────────────────────────────────────────

def contact_save(name: str, email: str, contact_type: str,
                 message: str, source: str = "contact_form",
                 ip_address: str = None) -> dict:
    """
    Save a contact form submission from homebridgegroup.co.
    Returns the saved record as a dict.
    type: agent | team | broker | partner | other
    source: contact_form | partner_signup
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO contacts (name, email, type, message, source, ip_address)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name.strip(), email.strip().lower(), contact_type, message.strip(),
          source, ip_address))
    conn.commit()
    contact_id = c.lastrowid
    c.execute("SELECT * FROM contacts WHERE id=?", (contact_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}


def contact_list_all(limit: int = 200, offset: int = 0) -> list:
    """
    Return all contact submissions, newest first. Admin use only.
    Supports pagination via limit/offset.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT * FROM contacts
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def contact_count_by_type() -> dict:
    """
    Return a count of contacts grouped by type. Admin dashboard use.
    Example: {'agent': 12, 'broker': 4, 'partner': 7, 'other': 2}
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT type, COUNT(*) as cnt
        FROM contacts
        GROUP BY type
    """)
    rows = c.fetchall()
    conn.close()
    return {row["type"]: row["cnt"] for row in rows}


# ─────────────────────────────────────────────
# SCHEDULE — day_of_week support (legacy alias)
# ─────────────────────────────────────────────

def schedule_row_with_days(row) -> dict:
    """
    Legacy alias for _schedule_row — kept for backward compatibility.
    _schedule_row already includes dayOfWeek; this is a pass-through.
    """
    return _schedule_row(row)


# ─────────────────────────────────────────────
# VIDEO IDENTITY — Session 49
# Profile photo storage, signed tokens, video job tracking,
# and monthly video limit enforcement.
# ─────────────────────────────────────────────

# Profile photo

def profile_photo_save(user_id: int, photo_bytes: bytes) -> bool:
    """
    Save a JPEG profile photo to persistent disk at
    /data/profile_photos/{user_id}.jpg and update the users table flag.
    Creates the directory if it does not exist.
    Returns True on success, False on failure.
    """
    import os
    photo_dir = os.getenv("PROFILE_PHOTO_DIR", "/data/profile_photos")
    try:
        os.makedirs(photo_dir, exist_ok=True)
        path = os.path.join(photo_dir, f"{user_id}.jpg")
        with open(path, "wb") as f:
            f.write(photo_bytes)
        conn = get_conn()
        conn.execute("""
            UPDATE users
            SET has_profile_photo       = 1,
                profile_photo_updated_at = datetime('now')
            WHERE id = ?
        """, (user_id,))
        conn.commit()
        conn.close()
        print(f"[Photo] Saved profile photo for user {user_id} ({len(photo_bytes)} bytes)")
        return True
    except Exception as e:
        print(f"[Photo] Save failed for user {user_id}: {e}")
        return False


def profile_photo_get_path(user_id: int) -> Optional[str]:
    """
    Return the disk path to a user's profile photo if it exists, else None.
    """
    import os
    photo_dir = os.getenv("PROFILE_PHOTO_DIR", "/data/profile_photos")
    path = os.path.join(photo_dir, f"{user_id}.jpg")
    return path if os.path.exists(path) else None


def profile_photo_exists(user_id: int) -> bool:
    """Return True if the user has a stored profile photo."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT has_profile_photo FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row and row["has_profile_photo"])


# Signed photo tokens

def photo_token_create(user_id: int) -> str:
    """
    Create a signed temporary token for serving a user's profile photo
    to the video render API. Token is valid for 30 minutes.
    Any previously unused tokens for this user are invalidated first.
    Returns the token string.
    """
    import secrets as _sec
    from datetime import timedelta
    token      = _sec.token_urlsafe(32)   # 43-char URL-safe token
    expires_at = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
    conn = get_conn()
    # Invalidate any existing unused tokens for this user
    conn.execute(
        "UPDATE photo_tokens SET used = 1 WHERE user_id = ? AND used = 0",
        (user_id,)
    )
    conn.execute(
        "INSERT INTO photo_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at)
    )
    conn.commit()
    conn.close()
    return token


def photo_token_validate(token: str) -> Optional[int]:
    """
    Validate a photo token. Returns user_id if valid and unexpired, else None.
    Does NOT consume (mark used) the token — that happens when render is submitted.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT user_id, expires_at FROM photo_tokens
        WHERE token = ? AND used = 0
    """, (token,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    try:
        if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
            return None
    except Exception:
        return None
    return row["user_id"]


def photo_token_consume(token: str) -> None:
    """Mark a photo token as used after the render job is submitted."""
    conn = get_conn()
    conn.execute("UPDATE photo_tokens SET used = 1 WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# Video limit enforcement

def _video_reset_if_due(conn, user_id: int, row: dict) -> dict:
    """
    Check whether the monthly video counter needs resetting.
    Resets on the 1st of each calendar month (UTC).
    Modifies DB in place if reset needed. Returns updated row dict.
    Called internally by check_video_allowed and record_video_render.
    """
    now        = datetime.utcnow()
    reset_date = row.get("video_month_reset")
    needs_reset = False

    if not reset_date:
        needs_reset = True
    else:
        try:
            if now >= datetime.fromisoformat(reset_date):
                needs_reset = True
        except Exception:
            needs_reset = True

    if needs_reset:
        # Next reset: 1st of next month at midnight UTC
        if now.month == 12:
            next_reset = now.replace(year=now.year + 1, month=1, day=1,
                                     hour=0, minute=0, second=0, microsecond=0)
        else:
            next_reset = now.replace(month=now.month + 1, day=1,
                                     hour=0, minute=0, second=0, microsecond=0)
        conn.execute("""
            UPDATE users
            SET video_month_count = 0,
                addon_video_limit = 0,
                video_month_reset = ?
            WHERE id = ?
        """, (next_reset.isoformat(), user_id))
        conn.commit()
        row = dict(row)
        row["video_month_count"] = 0
        row["addon_video_limit"] = 0
        row["video_month_reset"] = next_reset.isoformat()
    return row


def check_video_allowed(user_id: int, role: str, plan: str) -> dict:
    """
    Check whether an agent can render one more video this month.
    Called from POST /video/render before submitting to the video API.

    Returns:
        allowed       — bool
        videos_used   — renders this calendar month (including regenerations)
        videos_limit  — base plan limit + addon_video_limit
        resets_on     — human-readable reset date string
        plan_allows   — bool: False if this plan has 0 video limit (trial etc.)
    """
    if role in UNLIMITED_ROLES:
        return {
            "allowed": True, "videos_used": 0, "videos_limit": 999,
            "resets_on": None, "plan_allows": True,
        }

    limits       = _get_plan_limits(plan)
    base_videos  = limits.get("videos", 0)

    # Plans with 0 video limit: block entirely with a plan-upgrade message
    if base_videos == 0:
        return {
            "allowed": False, "videos_used": 0, "videos_limit": 0,
            "resets_on": None, "plan_allows": False,
        }

    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT video_month_count, video_month_reset, addon_video_limit
        FROM users WHERE id = ?
    """, (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"allowed": False, "videos_used": 0, "videos_limit": base_videos,
                "resets_on": None, "plan_allows": True}

    row = _video_reset_if_due(conn, user_id, row)
    conn.close()

    videos_used  = row["video_month_count"]  or 0
    addon        = row["addon_video_limit"]  or 0
    videos_limit = base_videos + addon

    # Compute next reset for display
    reset_str = row.get("video_month_reset")
    resets_on = None
    if reset_str:
        try:
            resets_on = datetime.fromisoformat(reset_str).strftime("%B 1, %Y")
        except Exception:
            pass

    return {
        "allowed":      videos_used < videos_limit,
        "videos_used":  videos_used,
        "videos_limit": videos_limit,
        "resets_on":    resets_on,
        "plan_allows":  True,
    }


def record_video_render(user_id: int, role: str) -> None:
    """
    Increment video_month_count by 1 for a render submission.
    Called after a video job is successfully submitted to the video API.
    Counts all renders including regenerations — pool is pool.
    Never called for UNLIMITED_ROLES or demo mode.
    """
    if role in UNLIMITED_ROLES:
        return
    try:
        conn = get_conn()
        c    = conn.cursor()
        c.execute("""
            SELECT video_month_count, video_month_reset, addon_video_limit
            FROM users WHERE id = ?
        """, (user_id,))
        row = c.fetchone()
        if row:
            _video_reset_if_due(conn, user_id, row)
        conn.execute("""
            UPDATE users
            SET video_month_count = COALESCE(video_month_count, 0) + 1
            WHERE id = ?
        """, (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Video] record_video_render failed for user {user_id}: {e}")


def apply_video_topup(user_id: int) -> dict:
    """
    Apply one Video Top-up Pack to a user's current month.
    Adds 10 video renders to addon_video_limit.
    Stackable — call once per pack purchased ($19/pack via Stripe).
    Returns updated video counts for confirmation.
    """
    conn = get_conn()
    conn.execute("""
        UPDATE users
        SET addon_video_limit = COALESCE(addon_video_limit, 0) + 10
        WHERE id = ?
    """, (user_id,))
    conn.commit()
    c = conn.cursor()
    c.execute("""
        SELECT video_month_count, addon_video_limit
        FROM users WHERE id = ?
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    return {
        "video_month_count": row["video_month_count"] if row else 0,
        "addon_video_limit": row["addon_video_limit"] if row else 0,
    }


# Video jobs

def video_job_create(user_id: int, library_item_id: Optional[int],
                     script_preview: str, photo_token: str) -> dict:
    """
    Create a new video job record in pending state.
    Called immediately before submitting the render request to the video API.
    Returns the created job as a dict.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO video_jobs
            (user_id, library_item_id, status, script_preview, photo_token, created_at)
        VALUES (?, ?, 'pending', ?, ?, datetime('now'))
    """, (user_id, library_item_id, script_preview[:200], photo_token))
    conn.commit()
    job_id = c.lastrowid
    conn.close()
    return video_job_get(job_id)


def video_job_set_heygen_id(job_id: int, heygen_video_id: str) -> None:
    """
    Record the video ID returned by the video API after successful submission.
    Called immediately after the API returns the video_id.
    """
    conn = get_conn()
    conn.execute(
        "UPDATE video_jobs SET heygen_video_id = ?, status = 'processing' WHERE id = ?",
        (heygen_video_id, job_id)
    )
    conn.commit()
    conn.close()


def video_job_complete(heygen_video_id: str, video_url: str) -> Optional[dict]:
    """
    Mark a video job as completed and store the render URL.
    Called by the webhook handler when the video API notifies completion.
    Returns the updated job dict, or None if job not found.
    """
    conn = get_conn()
    conn.execute("""
        UPDATE video_jobs
        SET status       = 'completed',
            video_url    = ?,
            completed_at = datetime('now')
        WHERE heygen_video_id = ?
    """, (video_url, heygen_video_id))
    conn.commit()
    c = conn.cursor()
    c.execute("SELECT id FROM video_jobs WHERE heygen_video_id = ?", (heygen_video_id,))
    row = c.fetchone()
    conn.close()
    return video_job_get(row["id"]) if row else None


def video_job_fail(heygen_video_id: str, error_message: str = "") -> None:
    """
    Mark a video job as failed. Called by webhook or poll on error status.
    """
    conn = get_conn()
    conn.execute("""
        UPDATE video_jobs
        SET status        = 'failed',
            error_message = ?,
            completed_at  = datetime('now')
        WHERE heygen_video_id = ?
    """, (error_message[:500], heygen_video_id))
    conn.commit()
    conn.close()


def video_job_get(job_id: int) -> Optional[dict]:
    """Fetch a single video job by internal ID."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT * FROM video_jobs WHERE id = ?", (job_id,))
    row = c.fetchone()
    conn.close()
    return _video_job_row(row) if row else None


def video_job_get_by_heygen_id(heygen_video_id: str) -> Optional[dict]:
    """Fetch a video job by its HeyGen video ID. Used in webhook handler."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT * FROM video_jobs WHERE heygen_video_id = ?", (heygen_video_id,))
    row = c.fetchone()
    conn.close()
    return _video_job_row(row) if row else None


def video_jobs_get_for_user(user_id: int, limit: int = 10) -> list:
    """
    Return recent video jobs for a user, newest first.
    Used by the agent's Records panel to show video history.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT * FROM video_jobs
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (user_id, min(limit, 50)))
    rows = c.fetchall()
    conn.close()
    return [_video_job_row(r) for r in rows]


def _video_job_row(row) -> dict:
    """Serialize a video_jobs DB row to a dict for API responses."""
    return {
        "id":             row["id"],
        "userId":         row["user_id"],
        "heygenVideoId":  row["heygen_video_id"],
        "libraryItemId":  row["library_item_id"],
        "status":         row["status"] or "pending",
        "videoUrl":       row["video_url"],
        "scriptPreview":  row["script_preview"] or "",
        "errorMessage":   row["error_message"] or "",
        "createdAt":      row["created_at"],
        "completedAt":    row["completed_at"],
    }


# HeyGen avatar ID management

def set_heygen_avatar_id(user_id: int, avatar_id: str) -> None:
    """
    Store an agent's HeyGen Instant Avatar ID.
    Set by admin panel when an agent's Video Identity upgrade is processed.
    When present, video renders use this ID instead of the photo avatar path.
    Never exposed to agents in UI — HeyGen is infrastructure, not a feature name.
    """
    conn = get_conn()
    conn.execute(
        "UPDATE users SET heygen_avatar_id = ? WHERE id = ?",
        (avatar_id.strip() if avatar_id else None, user_id)
    )
    conn.commit()
    conn.close()


def set_heygen_photo_avatar_id(user_id: int, avatar_id: str) -> None:
    """
    Store the HeyGen Photo Avatar ID (talking_photo_id) for an agent.
    Created once on the agent's first video render via POST /v3/avatars.
    Reused on all subsequent renders — never re-created unless cleared.
    Cleared when agent deletes their profile photo (consent withdrawal).
    Never exposed to agents in UI — HeyGen is infrastructure, not a feature name.
    """
    conn = get_conn()
    conn.execute(
        "UPDATE users SET heygen_photo_avatar_id = ? WHERE id = ?",
        (avatar_id.strip() if avatar_id else None, user_id)
    )
    conn.commit()
    conn.close()


def get_video_identity(user_id: int) -> dict:
    """
    Return the video identity state for an agent.
    Used by POST /video/render to determine render path:
      - heygen_photo_avatar_id: set use stored Photo Avatar (fast path, Session 50+)
      - has_photo: True create Photo Avatar first, then render
      - heygen_avatar_id: set use Instant Avatar (future upgrade path)
      - neither render not possible, agent needs to upload a photo
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT has_profile_photo, heygen_avatar_id, heygen_photo_avatar_id,
               video_consent_at, plan, role
        FROM users WHERE id = ?
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return {"has_photo": False, "heygen_avatar_id": None,
                "heygen_photo_avatar_id": None,
                "has_consent": False, "plan": "trial", "role": "agent"}
    return {
        "has_photo":               bool(row["has_profile_photo"]),
        "heygen_avatar_id":        row["heygen_avatar_id"],
        "heygen_photo_avatar_id":  row["heygen_photo_avatar_id"],
        "has_consent":             bool(row["video_consent_at"]),
        "plan":                    row["plan"] or "trial",
        "role":                    row["role"] or "agent",
    }


# Voice Identity — LMNT voice cloning — Session 51

def set_lmnt_voice_id(user_id: int, voice_id: str) -> None:
    """
    Store the LMNT voice clone ID for an agent.
    Set after the agent submits a voice recording and LMNT returns a voice_id.
    Used at render time: LMNT synthesizes script audio using this ID, and that
    audio is passed to HeyGen as audio_url instead of a stock voice_id.
    Never exposed to agents in UI — LMNT is infrastructure, not a feature name.
    Cleared by clear_lmnt_voice_id() when the agent deletes their voice.
    """
    conn = get_conn()
    conn.execute(
        "UPDATE users SET lmnt_voice_id = ? WHERE id = ?",
        (voice_id.strip() if voice_id else None, user_id)
    )
    conn.commit()
    conn.close()


def record_voice_consent(user_id: int) -> None:
    """
    Record the timestamp when an agent explicitly consented to voice cloning.
    Consent is separate from video_consent_at — voice cloning requires its own
    distinct record. Must be stored before voice setup can proceed.
    Called by POST /voice/consent endpoint.
    """
    conn = get_conn()
    conn.execute(
        "UPDATE users SET voice_consent_at = datetime('now') WHERE id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()


def clear_lmnt_voice_id(user_id: int) -> None:
    """
    Clear the agent's LMNT voice clone ID from the database.
    Called when agent deletes their voice (GDPR/CCPA requirement).
    The caller (DELETE /voice/setup endpoint in app.py) is also responsible
    for deleting the voice from LMNT's API before calling this function.
    Does NOT clear voice_consent_at — consent record is permanent once given.
    """
    conn = get_conn()
    conn.execute(
        "UPDATE users SET lmnt_voice_id = NULL WHERE id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()


def get_voice_identity(user_id: int) -> dict:
    """
    Return the voice identity state for an agent.
    Used by:
      - POST /video/render: to decide whether to use LMNT voice or stock voice
      - GET /voice/status: to drive the voice setup UI state in the Identity panel
      - POST /voice/setup: to check consent before allowing voice creation

    Returns dict with keys:
      lmnt_voice_id  — str or None. Set after successful voice clone creation.
      has_voice      — bool. True if lmnt_voice_id is set.
      has_consent    — bool. True if voice_consent_at is set.
      voice_consent_at — str or None. ISO timestamp of consent.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT lmnt_voice_id, voice_consent_at
        FROM users WHERE id = ?
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return {
            "lmnt_voice_id":    None,
            "has_voice":        False,
            "has_consent":      False,
            "voice_consent_at": None,
        }
    return {
        "lmnt_voice_id":    row["lmnt_voice_id"],
        "has_voice":        bool(row["lmnt_voice_id"]),
        "has_consent":      bool(row["voice_consent_at"]),
        "voice_consent_at": row["voice_consent_at"],
    }
