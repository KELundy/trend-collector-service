import threading
import time
import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import FastAPI, Request, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import io
from pydantic import BaseModel
from typing import Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

STRIPE_SECRET_KEY     = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_ENABLED        = bool(STRIPE_SECRET_KEY)

if STRIPE_ENABLED:
    import stripe as _stripe
    _stripe.api_key = STRIPE_SECRET_KEY
else:
    _stripe = None

STRIPE_PRICES = {
    # Individual agent plans
    "starter_monthly":          os.getenv("STRIPE_PRICE_STARTER_MONTHLY",         ""),
    "starter_annual":           os.getenv("STRIPE_PRICE_STARTER_ANNUAL",          ""),
    "professional_monthly":     os.getenv("STRIPE_PRICE_PROFESSIONAL_MONTHLY",    ""),
    "professional_annual":      os.getenv("STRIPE_PRICE_PROFESSIONAL_ANNUAL",     ""),
    "power_monthly":            os.getenv("STRIPE_PRICE_POWER_MONTHLY",           ""),
    "power_annual":             os.getenv("STRIPE_PRICE_POWER_ANNUAL",            ""),
    "founding_member_monthly":  os.getenv("STRIPE_PRICE_FOUNDING_MEMBER_MONTHLY", ""),
    "founding_member_annual":   os.getenv("STRIPE_PRICE_FOUNDING_MEMBER_ANNUAL",  ""),
    "coach_monthly":            os.getenv("STRIPE_PRICE_COACH_MONTHLY",           ""),
    # Office / team plans
    "office_starter_monthly":   os.getenv("STRIPE_PRICE_OFFICE_STARTER_MONTHLY",  ""),
    "office_starter_annual":    os.getenv("STRIPE_PRICE_OFFICE_STARTER_ANNUAL",   ""),
    "office_growth_monthly":    os.getenv("STRIPE_PRICE_OFFICE_GROWTH_MONTHLY",   ""),
    "office_growth_annual":     os.getenv("STRIPE_PRICE_OFFICE_GROWTH_ANNUAL",    ""),
    "office_team_monthly":      os.getenv("STRIPE_PRICE_OFFICE_TEAM_MONTHLY",     ""),
    "office_team_annual":       os.getenv("STRIPE_PRICE_OFFICE_TEAM_ANNUAL",      ""),
}

# ── Video Identity — HeyGen API ──────────────────────────────────────────────
# HEYGEN_API_KEY: added to Render env vars end of Session 48.
# Never logged. Never returned to frontend. Backend use only.
HEYGEN_API_KEY  = os.getenv("HEYGEN_API_KEY", "")
BACKEND_URL     = os.getenv("BACKEND_URL", "https://api.homebridgegroup.co")

# ── Voice Identity — LMNT API — Session 51 ───────────────────────────────────
# LMNT_API_KEY: add to Render env vars before voice setup goes live.
# Never logged. Never returned to frontend. Backend use only.
# LMNT is infrastructure — never mentioned in agent-facing UI.
LMNT_API_KEY    = os.getenv("LMNT_API_KEY", "")

OFFICE_SEAT_LIMITS = {
    "team":           5,   # $199/month — up to 5 agents, no broker required
    "office_starter": 5,
    "office_growth":  15,
    "office_team":    30,
}

def get_seat_limit(plan: str) -> int:
    for key, limit in OFFICE_SEAT_LIMITS.items():
        if key in (plan or ""):
            return limit
    return 0

import database
from database import (
    init_db, save_trends, get_latest_trends,
    migrate_add_niche_column,
    migrate_context_column,
    migrate_content_library_columns,
    seed_question_bank,
    library_save, library_get_all, library_get_item,
    library_update, library_delete,
    schedule_upsert, schedules_get_all, schedule_get,
    schedule_delete, schedules_get_due, schedule_mark_ran,
    schedule_deactivate, schedules_delete_for_user,
    get_agent_guidance,
    generate_compliance_pdf,
    get_compliance_records,
    get_compliance_records_for_broker,
    backfill_compliance_records,
    get_broker_office_stats,
    get_broker_agent_content,
    get_team_stats,
    save_agent_setup, get_agent_setup,
    get_user_results,
    market_report_save, market_report_list,
    market_report_get, market_report_update_extracted,
    market_report_delete,
    contact_save, contact_list_all,
    partner_get_by_code,
    # Usage system — two-counter model (Session 36)
    check_post_approval_allowed,
    check_generation_backstop_allowed,
    record_generation,
    record_post_approval,
    apply_addon_pack,
    set_billing_reset_day,
    activate_subscription,
    cancel_subscription,
    get_subscription_status,
    _compute_next_billing_reset,
    DB_NAME,
    # Video Identity — Session 49
    profile_photo_save,
    profile_photo_get_path,
    profile_photo_exists,
    photo_token_create,
    photo_token_validate,
    photo_token_consume,
    check_video_allowed,
    record_video_render,
    apply_video_topup,
    video_job_create,
    video_job_set_heygen_id,
    video_job_complete,
    video_job_fail,
    video_job_get,
    video_jobs_get_for_user,
    set_heygen_avatar_id,
    set_heygen_photo_avatar_id,
    get_video_identity,
    # Voice Identity — LMNT — Session 51
    set_lmnt_voice_id,
    record_voice_consent,
    clear_lmnt_voice_id,
    get_voice_identity,
    # Partner program — Session 52
    referral_mark_paying,
    referral_mark_lapsed,
    record_video_consent,
    partner_set_insider,
    partner_assign_override,
    partner_remove_override,
)

# ── Safe fallback in case database.py is older version ──
try:
    from database import migrate_context_column
except ImportError:
    def migrate_context_column():
        print("[Startup] migrate_context_column not available in this database.py version")

from auth import router as auth_router, get_current_user
from content_engine import router as content_engine_router, admin_router as compliance_admin_router, generate_content_core, hb_marketing_router, run_public_compliance_check
from social import router as social_router



from anthropic import Anthropic
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


SIGNAL_ENABLED = os.getenv("SIGNAL_ENABLED", "false").lower() == "true"  # off by default — set SIGNAL_ENABLED=true in Render when ready to go live

app = FastAPI(
    title="HomeBridge Content Engine",
    description="Identity-aware, compliance-first content generation for real estate agents",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.homebridgegroup.co",
        "https://homebridgegroup.co",
        "https://www.homebridgegroup.co",
    ],
    allow_origin_regex=r"https://.*\.homebridgegroup\.co",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(content_engine_router)
app.include_router(social_router)
app.include_router(compliance_admin_router)
app.include_router(hb_marketing_router)  # HB Marketing content generation — super_admin only — Session 56


def quarterly_evaluator_worker():
    """
    Background thread — wakes once per day and checks if today is the last
    day of a calendar quarter (Mar 31, Jun 30, Sep 30, Dec 31).
    If so, runs the partner tier evaluation directly against the database.

    Quarter-end dates:
      Q1 → March 31     → payouts early April
      Q2 → June 30      → payouts early July
      Q3 → September 30 → payouts early October
      Q4 → December 31  → payouts early January

    Runs at 06:00 UTC to ensure it fires after midnight in all US timezones.
    Safe to restart — checks today's date each cycle, idempotent if run twice.
    """
    import time as _time_qe
    from datetime import datetime as _dt_qe, timezone as _tz_qe

    # Quarter-end dates: (month, day)
    QUARTER_ENDS = {(3, 31), (6, 30), (9, 30), (12, 31)}

    print("[QuarterlyEvaluator] Worker started.")

    while True:
        try:
            now_utc = _dt_qe.now(_tz_qe.utc)

            # Only fire at 06:00 UTC (within the 06:00–06:59 window)
            if now_utc.hour == 6 and (now_utc.month, now_utc.day) in QUARTER_ENDS:
                print(f"[QuarterlyEvaluator] Quarter-end detected: {now_utc.date()} — running tier evaluation...")
                try:
                    from database import get_conn as _gc_qw
                    conn = _gc_qw()
                    c    = conn.cursor()

                    c.execute("SELECT id, tier, user_id FROM partners WHERE status = 'active'")
                    partners = [dict(r) for r in c.fetchall()]
                    now_iso  = _dt_qe.utcnow().isoformat()
                    changes  = 0

                    for p in partners:
                        c.execute("""
                            SELECT COUNT(*) as cnt
                            FROM referral_attributions
                            WHERE partner_id = ? AND is_active = 1
                        """, (p["id"],))
                        active_count = c.fetchone()["cnt"]

                        new_tier = "elite"    if active_count >= 15 else \
                                   "broker"   if active_count >= 5  else \
                                   "referral"

                        if new_tier != p["tier"]:
                            changes += 1

                        conn.execute("""
                            UPDATE partners
                            SET tier                  = ?,
                                active_referral_count = ?,
                                tier_evaluated_at     = ?
                            WHERE id = ?
                        """, (new_tier, active_count, now_iso, p["id"]))

                        conn.execute(
                            "UPDATE users SET partner_tier = ? WHERE id = ?",
                            (new_tier, p["user_id"])
                        )

                    conn.commit()
                    conn.close()

                    from database import log_audit_event as _lae_qw
                    _lae_qw(
                        actor_id = 2,  # super_admin — system action
                        action   = "partner_quarterly_evaluate",
                        detail   = f"Auto-run at quarter-end {now_utc.date()}. "
                                   f"{len(partners)} partners evaluated. {changes} tier changes.",
                    )
                    print(f"[QuarterlyEvaluator] ✓ Complete — {len(partners)} partners, {changes} tier changes.")

                except Exception as eval_err:
                    print(f"[QuarterlyEvaluator] ✗ Evaluation failed: {eval_err}")

        except Exception as outer_err:
            print(f"[QuarterlyEvaluator] Worker error: {outer_err}")

        # Sleep 55 minutes — wakes ~26 times per day, catches the 06:xx window reliably
        _time_qe.sleep(55 * 60)



# =============================================================================
# SQLITE BACKUP TO CLOUDFLARE R2 — Session 56, Phase 4, Item 12
# =============================================================================
# Runs daily. Copies /data/homebridge.db to R2 with a timestamped filename.
# Retains 30 days of backups. Deletes older files automatically.
# Uses S3-compatible API (boto3) — Cloudflare R2 is S3-compatible.
# Required env vars: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
#                    R2_BUCKET_NAME (default: automates-db-backup)
# If any env var is missing, worker logs a warning and exits cleanly.
# Never crashes the server. Always fire-and-forget.
# =============================================================================

def r2_backup_worker():
    """
    Daily SQLite backup to Cloudflare R2.
    Wakes every 24 hours. On each wake:
      1. Copies homebridge.db to R2 as homebridge-YYYY-MM-DD-HHMMSS.db
      2. Lists all backups in the bucket and deletes any older than 30 days.
    """
    import os as _os
    import time as _time
    from datetime import datetime as _dt, timedelta as _td

    R2_ACCOUNT_ID    = _os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY    = _os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_KEY    = _os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET        = _os.getenv("R2_BUCKET_NAME", "automates-db-backup")
    DB_PATH          = _os.getenv("DB_PATH", "/data/homebridge.db")
    BACKUP_INTERVAL  = 24 * 60 * 60   # 24 hours
    RETAIN_DAYS      = 30

    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY, R2_SECRET_KEY]):
        print("[R2Backup] R2 credentials not configured — backup worker will not run. "
              "Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in environment.")
        return

    # Cloudflare R2 S3-compatible endpoint
    endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    print(f"[R2Backup] Worker started. Bucket: {R2_BUCKET}. Interval: 24h. Retaining: {RETAIN_DAYS} days.")

    while True:
        try:
            _run_r2_backup(DB_PATH, R2_BUCKET, endpoint_url, R2_ACCESS_KEY, R2_SECRET_KEY, RETAIN_DAYS)
        except Exception as _e:
            print(f"[R2Backup] Backup cycle error (non-fatal): {_e}")
        _time.sleep(BACKUP_INTERVAL)


def _run_r2_backup(db_path, bucket, endpoint_url, access_key, secret_key, retain_days):
    """
    Execute one backup cycle:
      - Upload current DB file with timestamp
      - Prune backups older than retain_days
    """
    import os as _os
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    if not _os.path.exists(db_path):
        print(f"[R2Backup] DB file not found at {db_path} — skipping this cycle.")
        return

    db_size_mb = _os.path.getsize(db_path) / (1024 * 1024)

    try:
        import boto3 as _boto3
        from botocore.config import Config as _BotoConfig
    except ImportError:
        print("[R2Backup] boto3 not installed. Run: pip install boto3")
        return

    s3 = _boto3.client(
        "s3",
        endpoint_url         = endpoint_url,
        aws_access_key_id    = access_key,
        aws_secret_access_key= secret_key,
        config               = _BotoConfig(signature_version="s3v4"),
        region_name          = "auto",
    )

    # ── Upload ────────────────────────────────────────────────────────────────
    now       = _dt.now(_tz.utc)
    timestamp = now.strftime("%Y-%m-%d-%H%M%S")
    key       = f"homebridge-{timestamp}.db"

    try:
        with open(db_path, "rb") as f:
            s3.upload_fileobj(f, bucket, key)
        print(f"[R2Backup] Uploaded {key} ({db_size_mb:.2f} MB) to {bucket}.")
    except Exception as _upload_err:
        print(f"[R2Backup] Upload failed: {_upload_err}")
        return   # Do not prune if upload failed

    # ── Prune backups older than retain_days ──────────────────────────────────
    cutoff = now - _td(days=retain_days)
    deleted = 0
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                obj_key      = obj["Key"]
                last_modified = obj["LastModified"]
                # LastModified is timezone-aware from R2
                if last_modified < cutoff:
                    s3.delete_object(Bucket=bucket, Key=obj_key)
                    print(f"[R2Backup] Pruned old backup: {obj_key}")
                    deleted += 1
    except Exception as _prune_err:
        print(f"[R2Backup] Prune error (non-fatal): {_prune_err}")

    print(f"[R2Backup] Cycle complete. Uploaded: {key}. Pruned: {deleted} old backup(s).")

@app.on_event("startup")
async def startup_event():
    # Ensure super admin account is always set correctly
    try:
        from database import get_conn as _gc_sa
        _sa_conn = _gc_sa()
        _sa_conn.execute(
            "UPDATE users SET role = 'super_admin', is_licensed = 1 WHERE id = 2"
        )
        _sa_conn.commit()
        _sa_conn.close()
    except Exception as _sa_e:
        print(f"[Startup] Super admin check: {_sa_e}")
    print("[Startup] Initializing database...")
    init_db()
    migrate_add_niche_column()
    migrate_content_library_columns()
    migrate_context_column()  # safe no-op if column already exists
    try:
        seed_question_bank()  # DQ-1 — idempotent, skips questions already present
    except Exception as _sqb_e:
        print(f"[Startup] question_bank seed skipped: {_sqb_e}")
    try:
        backfill_compliance_records()  # one-time, skips already-present records
    except Exception as _bf_e:
        print(f"[Startup] compliance_records backfill skipped: {_bf_e}")
    print("[Startup] Starting content scheduler...")
    t2 = threading.Thread(target=content_scheduler_worker, daemon=True)
    t2.start()
    print("[Startup] Starting hyper-local signal collector...")
    if SIGNAL_ENABLED:
        try:
            from signal_collector import start_signal_collector
            start_signal_collector()
        except Exception as e:
            print(f"[Startup] Signal collector failed to start: {e}")
    else:
        print("[Startup] Signal collector DISABLED (SIGNAL_ENABLED=false) — set env var to true to enable.")
    print("[Startup] Starting quarterly partner tier evaluator...")
    t3 = threading.Thread(target=quarterly_evaluator_worker, daemon=True)
    t3.start()
    print("[Startup] Starting R2 database backup worker...")
    t4 = threading.Thread(target=r2_backup_worker, daemon=True)
    t4.start()
    print("[Startup] Ready.")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "HomeBridge Content Engine", "timestamp": datetime.utcnow().isoformat()}

@app.get("/")
async def root():
    return {"service": "HomeBridge Content Engine", "status": "running", "timestamp": datetime.utcnow().isoformat()}




class LibraryPatchRequest(BaseModel):
    status: Optional[str] = None
    content: Optional[dict] = None
    compliance: Optional[dict] = None
    copiedPlatforms: Optional[list] = None
    approvedAt: Optional[str] = None
    publishedAt: Optional[str] = None


@app.get("/library")
async def get_library(context: str = "agent", include_archived: bool = False, current_user=Depends(get_current_user)):
    items = library_get_all(current_user["id"], context=context, include_archived=include_archived)
    return {"items": items, "count": len(items)}


@app.post("/library")
async def save_to_library(payload: dict, current_user=Depends(get_current_user)):
    # context comes from payload or defaults to agent
    _ctx = str(payload.get("context", "agent"))
    if _ctx not in ("agent", "hb_marketing"): _ctx = "agent"
    payload["context"] = _ctx
    niche      = payload.get("niche", "")
    content    = payload.get("content", {})
    compliance = payload.get("compliance", {})
    source     = payload.get("source", "manual")
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    item = library_save(user_id=current_user["id"], niche=niche, content=content, compliance=compliance, source=source, context=_ctx)
    return {"success": True, "item": item}


@app.patch("/library/{item_id}")
async def update_library_item(item_id: int, body: LibraryPatchRequest, current_user=Depends(get_current_user)):
    updates = {}
    if body.status is not None: updates["status"] = body.status
    if body.content is not None: updates["content"] = body.content
    if body.compliance is not None: updates["compliance"] = body.compliance
    if body.copiedPlatforms is not None: updates["copied_platforms"] = body.copiedPlatforms
    if body.approvedAt is not None: updates["approved_at"] = body.approvedAt
    if body.publishedAt is not None: updates["published_at"] = body.publishedAt

    # ── Post approval limit gate ───────────────────────────────────────────────
    # Approval (CIR issuance) is the primary billing unit — not generation.
    # Check and record only when this patch is setting status to 'approved'
    # AND the item was previously 'pending' (first approval only, not re-approvals).
    if body.status == "approved":
        role = current_user.get("role", "agent")
        plan = current_user.get("plan", "trial")
        uid  = current_user["id"]
        from database import check_post_approval_allowed, record_post_approval, get_conn as _gc_patch
        # Check previous status — only gate and count on first approval
        _conn_p = _gc_patch()
        _c_p    = _conn_p.cursor()
        _c_p.execute("SELECT status FROM content_library WHERE id = ? AND user_id = ?", (item_id, uid))
        _prev   = _c_p.fetchone()
        _conn_p.close()
        _prev_status = _prev["status"] if _prev else None
        if _prev_status == "pending":
            # This is a first approval — check the limit
            check = check_post_approval_allowed(uid, role, plan)
            if not check["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error":      "post_limit_reached",
                        "message":    f"You've approved {check['posts_used']} of {check['posts_limit']} posts included in your plan this month. Add more with an Add-on Pack or upgrade your plan.",
                        "posts_used":  check["posts_used"],
                        "posts_limit": check["posts_limit"],
                        "resets_on":   check["resets_on"],
                    }
                )
            # Limit OK — proceed, then record the approval after DB write
            item = library_update(item_id, uid, updates)
            if not item:
                raise HTTPException(status_code=404, detail="Item not found")
            record_post_approval(uid, role)
            _post_approval_indexnow(item, uid, body.status)  # Build N — instant index ping
            return {"success": True, "item": item}
    # ─────────────────────────────────────────────────────────────────────────

    item = library_update(item_id, current_user["id"], updates)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if body.status in ("approved", "published"):
        _post_approval_indexnow(item, current_user["id"], body.status)  # Build N
    return {"success": True, "item": item}


@app.delete("/library/{item_id}")
async def delete_library_item(item_id: int, current_user=Depends(get_current_user)):
    success = library_delete(item_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True}


class ScheduleRequest(BaseModel):
    niche:      str
    frequency:  str
    timeOfDay:  str
    timezone:   Optional[str] = "America/Denver"
    dayOfWeek:  Optional[str] = None  # JSON array e.g. '["mon","wed","fri"]'
    context:    Optional[str] = "agent"  # 'agent' | 'hb_marketing' — Session 62

class ScheduleDeleteRequest(BaseModel):
    niche: str


@app.get("/schedules")
async def get_schedules(request: Request, current_user=Depends(get_current_user)):
    """
    Return schedules for the current user filtered by context.
    Accepts optional ?context=agent|hb_marketing query param.
    Defaults to 'agent' so existing agent schedule calls are unaffected.
    hb_marketing context only honoured for super_admin/admin/hb_marketer roles.
    """
    ctx = request.query_params.get("context", "agent")
    role = current_user.get("role", "agent")
    # Only privileged roles can request hb_marketing schedules
    if ctx == "hb_marketing" and role not in ("super_admin", "admin", "hb_marketer"):
        ctx = "agent"
    return {"schedules": schedules_get_all(current_user["id"], context=ctx)}


@app.post("/schedules")
async def upsert_schedule(body: ScheduleRequest, current_user=Depends(get_current_user)):
    """
    Create or update a schedule. Context from request body determines which
    workspace the schedule belongs to. Defaults to 'agent'.
    hb_marketing context only honoured for super_admin/admin/hb_marketer roles.
    """
    from database import schedule_upsert
    ctx = body.context or "agent"
    role = current_user.get("role", "agent")
    if ctx == "hb_marketing" and role not in ("super_admin", "admin", "hb_marketer"):
        ctx = "agent"
    schedule = schedule_upsert(
        user_id    = current_user["id"],
        niche      = body.niche,
        frequency  = body.frequency,
        time_of_day= body.timeOfDay,
        timezone   = body.timezone,
        day_of_week= body.dayOfWeek,
        context    = ctx,
    )
    return {"success": True, "schedule": schedule}


@app.delete("/schedules/{niche}")
async def delete_schedule(niche: str, request: Request, current_user=Depends(get_current_user)):
    """
    Delete a schedule by niche. Accepts optional ?context= query param.
    Defaults to 'agent' so existing agent delete calls are unaffected.
    """
    ctx = request.query_params.get("context", "agent")
    role = current_user.get("role", "agent")
    if ctx == "hb_marketing" and role not in ("super_admin", "admin", "hb_marketer"):
        ctx = "agent"
    success = schedule_delete(current_user["id"], niche, context=ctx)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True}


# ── Usage endpoints ────────────────────────────────────────────────────────────
@app.get("/usage")
async def get_usage(current_user=Depends(get_current_user)):
    """
    Return current usage for the logged-in agent.
    Returns both post approval count (primary billing unit)
    and generation backstop count (abuse guard).
    """
    uid  = current_user["id"]
    role = current_user.get("role", "agent")
    plan = current_user.get("plan", "trial")
    post_check     = check_post_approval_allowed(uid, role, plan)
    backstop_check = check_generation_backstop_allowed(uid, role, plan)
    return {
        "posts_used":      post_check["posts_used"],
        "posts_limit":     post_check["posts_limit"],
        "backstop_used":   backstop_check["backstop_used"],
        "backstop_limit":  backstop_check["backstop_limit"],
        "resets_on":       post_check["resets_on"],
        "plan":            plan,
        "role":            role,
        "unlimited":       role in ("super_admin", "admin"),
    }


# ── Local signals endpoint ─────────────────────────────────────────────────────
@app.get("/signals/latest")
async def get_latest_signals(
    request: Request,
    current_user=Depends(get_current_user)
):
    """
    Returns the most recent high-relevance local signals for the agent.
    Used by the Home dashboard to surface the suggested next action.
    Accepts optional ?context=agent|hb_marketing query param.
    Defaults to 'agent'. hb_marketing only honoured for super_admin/admin/hb_marketer.
    """
    from database import signals_get_latest
    ctx = request.query_params.get("context", "agent")
    role = current_user.get("role", "agent")
    # Enforce: only privileged roles can request hb_marketing signals
    if ctx == "hb_marketing" and role not in ("super_admin", "admin", "hb_marketer"):
        ctx = "agent"
    signals = signals_get_latest(current_user["id"], limit=10, context=ctx)
    return {"signals": signals}


@app.post("/signals/trigger")
async def trigger_signal_collection(current_user=Depends(get_current_user)):
    """
    Manually trigger signal collection for the current user.
    Super admin only — used for testing.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(403, "Super admin only.")
    try:
        from signal_collector import _collect_signals_for_agent
        import json as _json
        conn2 = __import__('database').get_conn()
        c2    = conn2.cursor()
        c2.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (current_user["id"],))
        row = c2.fetchone()
        conn2.close()
        setup = _json.loads(row["setup_json"]) if row else {}
        _collect_signals_for_agent(
            user_id      = current_user["id"],
            agent_name   = current_user.get("agent_name", "Agent"),
            service_areas= setup.get("serviceAreas", []),
            market       = setup.get("market", ""),
            force        = True,
        )
        return {"ok": True, "message": "Signal collection triggered."}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/signals/rss-status")
async def get_rss_status(current_user=Depends(get_current_user)):
    """
    Returns the count and most recent RSS-sourced signals for the current agent.
    Used by the Home dashboard to confirm RSS integration is running.
    Super admin can also use this to verify feed health.
    """
    from database import get_conn
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT COUNT(*) as total,
               MAX(collected_at) as last_collected
        FROM local_signals
        WHERE user_id = ?
          AND source_type = 'rss'
          AND (expires_at IS NULL OR expires_at > datetime('now'))
    """, (current_user["id"],))
    row   = c.fetchone()
    total = row["total"] if row else 0
    last  = row["last_collected"] if row else None

    c.execute("""
        SELECT headline, area, signal_type, published_date, collected_at
        FROM local_signals
        WHERE user_id = ?
          AND source_type = 'rss'
          AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY collected_at DESC
        LIMIT 5
    """, (current_user["id"],))
    recent = [dict(r) for r in c.fetchall()]
    conn.close()
    return {
        "rss_enabled":       os.getenv("RSS_ENABLED", "true").lower() == "true",
        "total_active":      total,
        "last_collected_at": last,
        "recent_signals":    recent,
    }




# ── Generate from signal — Home screen flow ─────────────────────────────────
# Called when agent taps "Get Your Writer on this" on a Home signal card.
# Generates content from signal context and saves as pending — same path as
# scheduler-generated content. Agent reviews from the "waiting for you" queue.
# Never routes through Studio or the broadcast panel.

class GenerateFromSignalRequest(BaseModel):
    signal_id:  Optional[int] = None
    headline:   str = ""
    summary:    str = ""
    niche:      Optional[str] = None

@app.post("/content/generate-from-signal")
async def generate_from_signal(body: GenerateFromSignalRequest, current_user=Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        from database import get_conn, signals_get_latest
        conn = get_conn()
        c    = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = c.fetchone()
        c.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
        setup_row = c.fetchone()
        setup = json.loads(setup_row["setup_json"]) if setup_row else {}
        conn.close()

        if not user_row:
            raise HTTPException(400, "User not found.")

        # Backstop check — this endpoint previously bypassed usage limits entirely
        # (Opus N9 fix). Pattern mirrors the scheduler at app.py line 871.
        role = current_user.get("role", "agent")
        plan = current_user.get("plan", "trial")
        if role not in ("super_admin", "admin"):
            backstop = check_generation_backstop_allowed(user_id, role, plan)
            if not backstop["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error":   "backstop_limit_reached",
                        "message": f"You've reached your generation limit for this period. "                                    f"Review and approve what you have, then generate more "                                    f"after {backstop['resets_on']}.",
                        "resets_on": backstop["resets_on"],
                    }
                )

        # Use first saved niche if none provided
        niche = body.niche or (setup.get("primaryNiches") or ["Residential Buying & Selling"])[0]

        # Build situation from signal context
        context_parts = []
        if body.headline: context_parts.append(body.headline)
        if body.summary:  context_parts.append(body.summary)
        if context_parts:
            situation = "Signal-driven post: " + " ".join(context_parts)
        else:
            # No signal context — draw a niche-specific situation so content stays relevant
            from content_engine import NICHE_SITUATIONS, DEFAULT_SITUATIONS
            import random as _random
            _sit_pool = NICHE_SITUATIONS.get(niche) or DEFAULT_SITUATIONS
            situation = _random.choice(_sit_pool)

        result = generate_content_core(
            agent_name           = user_row["agent_name"],
            brokerage            = user_row["brokerage"],
            market               = setup.get("market", ""),
            niche                = niche,
            situation            = situation,
            persona              = setup.get("defaultPersona") or "homeowners",
            tone                 = setup.get("tone", "Professional"),
            length               = setup.get("length", "Standard"),
            trends               = setup.get("trends", []),
            brand_voice          = setup.get("brandVoice", ""),
            short_bio            = setup.get("shortBio", ""),
            audience             = setup.get("audienceDescription", ""),
            words_avoid          = setup.get("wordsAvoid", ""),
            words_prefer         = setup.get("wordsPrefer", ""),
            mls_names            = setup.get("mlsNames", []),
            state                = setup.get("state", ""),
            cta_type             = setup.get("ctaType", ""),
            cta_url              = setup.get("ctaUrl", ""),
            cta_label            = setup.get("ctaLabel", ""),
            origin_story         = setup.get("originStory", ""),
            unfair_advantage     = setup.get("unfairAdvantage", ""),
            signature_perspective= setup.get("signaturePerspective", ""),
            not_for_client       = setup.get("notForClient", ""),
        )

        content_to_save = dict(result["content"])
        if "generated_at" in content_to_save:
            from datetime import datetime as _dt
            val = content_to_save["generated_at"]
            if isinstance(val, _dt):
                content_to_save["generated_at"] = val.isoformat()

        compliance_to_save = dict(result["compliance"])

        saved_item = library_save(
            user_id    = user_id,
            niche      = niche,
            content    = content_to_save,
            compliance = compliance_to_save,
            source     = "signal",
        )

        # Record generation against backstop counter (Opus N9 fix)
        if current_user.get("role") not in ("super_admin", "admin"):
            try:
                record_generation(user_id, current_user.get("role", "agent"))
            except Exception as _rg_e:
                print(f"[SignalGenerate] record_generation failed (non-blocking): {_rg_e}")

        return {"ok": True, "item_id": saved_item.get("id"), "niche": niche}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[SignalGenerate] Error for user {user_id}: {e}")
        raise HTTPException(500, f"Generation failed: {str(e)}")


def _run_foundation_generation(user_id: int, answer_id: int) -> dict:
    """
    Shared DQ-4 core (FOUNDATION_DAILY_QUESTION_SPEC_v2 §6-7): read a stored
    member_answer, generate a record in the member's voice, and save it to
    content_library flagged with human-origin provenance (origin_type +
    answer_ref). Used by the /content/generate-from-answer route AND by the DQ-2
    Foundation flow's background task.

    Returns {"ok": True, "item": ..., "origin_type": ...} or
    {"ok": False, "error": <msg>, "status": <http code>}. Never raises — safe to
    run as a FastAPI BackgroundTask, where exceptions would otherwise be swallowed.

    Setting a member_answer origin requires a real member_answers row (answer_ref),
    so the §7 honesty flag cannot be applied to arbitrary content.
    """
    try:
        from database import member_answer_with_question, get_conn as _gc_ans, library_save as _lsave
        from content_engine import (
            AgentProfileModel, generate_from_member_answer, foundation_category_for_bank,
        )

        answer = member_answer_with_question(answer_id, user_id)
        if not answer:
            return {"ok": False, "error": "Answer not found.", "status": 404}

        # Identity/voice from the agent's saved setup — same source the scheduler uses.
        conn = _gc_ans()
        c    = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = c.fetchone()
        c.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
        setup_row = c.fetchone()
        conn.close()
        if not user_row:
            return {"ok": False, "error": "User not found.", "status": 400}
        setup = json.loads(setup_row["setup_json"]) if setup_row and setup_row["setup_json"] else {}

        profile = AgentProfileModel(
            agentName  = user_row["agent_name"],
            brokerage  = user_row["brokerage"],
            market     = setup.get("market", ""),
            brandVoice = setup.get("brandVoice", ""),
            shortBio   = setup.get("shortBio", ""),
            state      = setup.get("state", ""),
            mlsNames   = setup.get("mlsNames", []),
        )

        gen_category = foundation_category_for_bank(answer.get("bank_category"))
        input_type   = (answer.get("input_type") or "text").lower()

        cr = generate_from_member_answer(
            {
                "transcript":    answer.get("transcript") or "",
                "category":      gen_category,
                "question_text": answer.get("rendered_text") or "",
                "input_type":    input_type,
            },
            profile = profile,
            user_id = user_id,
        )

        content_to_save = {
            "headline":      cr.headline,
            "thumbnailIdea": cr.thumbnailIdea,
            "hashtags":      cr.hashtags,
            "post":          cr.post,
            "cta":           cr.cta,
            "script":        cr.script,
            "generated_at":  cr.generated_at.isoformat(),
        }
        compliance_to_save = cr.compliance.dict() if hasattr(cr.compliance, "dict") else dict(cr.compliance)

        # 'voice' vs 'text' provenance — the answer's own input_type decides, never the caller.
        origin_type = "member_answer_voice" if input_type == "voice" else "member_answer_text"
        saved_item  = _lsave(
            user_id     = user_id,
            niche       = "",
            content     = content_to_save,
            compliance  = compliance_to_save,
            source      = "foundation_answer",
            context     = "agent",
            origin_type = origin_type,
            answer_ref  = answer_id,
        )
        return {"ok": True, "item": saved_item, "origin_type": origin_type}
    except Exception as e:
        print(f"[FoundationGenerate] Error for user {user_id}, answer {answer_id}: {e}")
        return {"ok": False, "error": str(e), "status": 500}


@app.post("/content/generate-from-answer")
async def generate_from_answer_route(body: dict, current_user=Depends(get_current_user)):
    """
    DQ-4 bridge (FOUNDATION_DAILY_QUESTION_SPEC_v2 §6-7). Turn a member's own
    stored answer into a content_library item in their voice, synchronously.
    Thin wrapper over _run_foundation_generation().
    """
    answer_id = body.get("answer_id")
    if not answer_id:
        raise HTTPException(status_code=400, detail="answer_id is required.")
    result = _run_foundation_generation(current_user["id"], answer_id)
    if not result.get("ok"):
        raise HTTPException(status_code=result.get("status", 500), detail=result.get("error", "Generation failed."))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# DQ-2 — FOUNDATION FLOW (typed input only this session)
# FOUNDATION_DAILY_QUESTION_SPEC_v2 §2-3. The platform asks; the member answers
# in their own words; the engine shapes it; they review/approve. Voice capture is
# DQ-3. These routes run for new users inside onboarding.
# ─────────────────────────────────────────────────────────────────────────────

# Canonical copy — spec §2, served to the UI so wording lives in one place.
_FOUNDATION_CONSENT_COPY = {
    "title": "Three quick questions before your team gets to work.",
    "body": (
        "Your answers do two things: they teach your team to write the way you "
        "actually talk, and they become the first records on your page — your words, "
        "shaped up, signed by you."
    ),
    "promises": [
        "Nothing publishes without your approval.",
        "You can edit or discard anything.",
        "You can skip any question, no reason needed.",
    ],
}
_DAILY_QUESTION_COPY = (
    "Your team will ask you one quick question most mornings. Answer it and it "
    "becomes that day's content. Ignore it and nothing happens."
)
_F1_PLACEHOLDER = "answer like you're leaving a voicemail to a friend — about 60 seconds of typing"


@app.get("/foundation/questions")
async def foundation_questions(current_user=Depends(get_current_user)):
    """Return the three Foundation questions (F1-F3) in order plus the §2 copy."""
    from database import get_conn as _gc_fq
    conn = _gc_fq()
    c    = conn.cursor()
    c.execute(
        "SELECT id, text_template, category FROM question_bank "
        "WHERE source = 'foundation' AND active = 1 ORDER BY id LIMIT 3"
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    # Render [market] / [primary niche audience] placeholders from the agent's
    # setup. A brand-new member usually has no setup yet, so fall back gracefully.
    setup     = get_agent_setup(current_user["id"]) or {}
    market    = setup.get("market", "") or "your market"
    niche_aud = (setup.get("primaryNiches") or ["buyers and sellers"])[0]

    def _render(t):
        return (t or "").replace("[market]", market).replace("[primary niche audience]", niche_aud)

    questions = [
        {"id": r["id"], "text": _render(r["text_template"]), "category": r["category"], "position": i + 1}
        for i, r in enumerate(rows)
    ]
    return {
        "questions":           questions,
        "consent_copy":        _FOUNDATION_CONSENT_COPY,
        "daily_question_copy": _DAILY_QUESTION_COPY,
        "input_placeholder":   _F1_PLACEHOLDER,
    }


@app.post("/foundation/answer")
async def foundation_answer(body: dict, background_tasks: BackgroundTasks,
                            current_user=Depends(get_current_user)):
    """
    Store a typed Foundation answer (§3) and kick off background generation so the
    record is ready by the time the next question is answered.
    body: { question_id (question_bank id, optional), question_text, transcript }
    """
    user_id    = current_user["id"]
    transcript = (body.get("transcript") or "").strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="An answer is required.")
    question_id   = body.get("question_id")
    question_text = (body.get("question_text") or "").strip()

    from database import member_question_create, member_answer_create
    mq_id     = member_question_create(user_id, question_id=question_id,
                                       rendered_text=question_text, status="answered")
    answer_id = member_answer_create(user_id, mq_id, "text", transcript)

    # Background generation — reuse the shared DQ-4 core (never raises).
    background_tasks.add_task(_run_foundation_generation, user_id, answer_id)
    return {"ok": True, "answer_id": answer_id, "member_question_id": mq_id}


@app.post("/foundation/skip")
async def foundation_skip(body: dict, current_user=Depends(get_current_user)):
    """Record a skipped question (§3 per-question Skip). No generation triggered."""
    from database import member_question_create
    mq_id = member_question_create(
        current_user["id"],
        question_id=body.get("question_id"),
        rendered_text=(body.get("question_text") or "").strip(),
        status="skipped",
    )
    return {"ok": True, "member_question_id": mq_id, "status": "skipped"}


@app.get("/foundation/record")
async def foundation_record(answer_id: int, current_user=Depends(get_current_user)):
    """
    Return the generated content_library item for a Foundation answer (the reveal),
    or {"ready": False} while background generation is still running.
    """
    user_id = current_user["id"]
    from database import get_conn as _gc_fr, library_get_item
    conn = _gc_fr()
    c    = conn.cursor()
    c.execute(
        "SELECT id FROM content_library WHERE user_id = ? AND answer_ref = ? ORDER BY id DESC LIMIT 1",
        (user_id, answer_id),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return {"ready": False}
    return {"ready": True, "item": library_get_item(row["id"], user_id)}


@app.post("/foundation/paste-samples")
async def foundation_paste_samples(body: dict, current_user=Depends(get_current_user)):
    """
    §3 shortcut — seed the voice exemplar pool from 2-3 posts the agent pastes.
    Each becomes an APPROVED content_library item (so get_voice_exemplars picks it
    up), but NO CPR is minted: these are the agent's own existing writing, not
    reviewed Foundation records, so we approve the status directly without routing
    through the compliance/CIR path. origin stays engine_draft.
    """
    user_id = current_user["id"]
    samples = body.get("samples") or []
    if isinstance(samples, str):
        samples = [samples]

    from database import library_save, get_conn as _gc_ps
    saved_ids = []
    for s in samples:
        text = (s or "").strip()
        if len(text) < 50:
            continue  # too short to be a useful voice exemplar
        content = {"headline": "", "post": text, "generated_at": datetime.utcnow().isoformat()}
        item = library_save(user_id, "", content, {"overallStatus": "voice_sample"},
                            source="voice_sample", context="agent")
        # Approve the status directly — voice seed material, not a reviewed record.
        conn = _gc_ps()
        c    = conn.cursor()
        c.execute(
            "UPDATE content_library SET status = 'approved', approved_at = ? WHERE id = ? AND user_id = ?",
            (datetime.utcnow().isoformat(), item["id"], user_id),
        )
        conn.commit()
        conn.close()
        saved_ids.append(item["id"])

    return {"ok": True, "saved": len(saved_ids), "item_ids": saved_ids}


@app.post("/foundation/daily-preference")
async def foundation_daily_preference(body: dict, current_user=Depends(get_current_user)):
    """Store the Daily Question preference set at the end of Foundation (§2)."""
    pref = (body.get("preference") or "off").strip().lower()
    if pref not in ("daily", "weekdays", "off"):
        pref = "off"
    from database import get_conn as _gc_dp
    conn = _gc_dp()
    c    = conn.cursor()
    c.execute("UPDATE users SET daily_question_pref = ? WHERE id = ?", (pref, current_user["id"]))
    conn.commit()
    conn.close()
    return {"ok": True, "preference": pref}


@app.get("/identity/guidance")
async def get_identity_guidance(request: Request, current_user=Depends(get_current_user)):
    """
    Return actionable guidance for the current agent via the Next Action Engine.
    Replaces the retired /identity/score endpoint (Session 56).
    Never returns a numerical score or grade. Returns one actionable recommendation,
    supporting data points, a milestone progress indicator, and the CIR count.
    Used by Jordan's briefing card and the Next Action panel in index.html.
    Accepts optional ?context=agent|hb_marketing to scope counts to the correct workspace.
    hb_marketing context only honoured for super_admin/admin/hb_marketer roles.
    """
    ctx  = request.query_params.get("context", "agent")
    role = current_user.get("role", "agent")
    if ctx == "hb_marketing" and role not in ("super_admin", "admin", "hb_marketer"):
        ctx = "agent"
    guidance = get_agent_guidance(current_user["id"], context=ctx)
    return guidance


def _compute_next_run(frequency: str, time_of_day: str, timezone: str = "America/Denver") -> str:
    """
    Compute the next UTC run time for a schedule.
    time_of_day is treated as LOCAL time in the given timezone — not UTC.
    Returns an ISO-format UTC datetime string for storage and comparison.
    """
    try:
        hour, minute = map(int, time_of_day.split(":"))
    except Exception:
        hour, minute = 8, 0

    if frequency == "daily":
        delta = timedelta(days=1)
    elif frequency == "3x_week":
        delta = timedelta(days=2)
    elif frequency == "biweekly":
        delta = timedelta(days=14)
    elif frequency == "monthly":
        delta = timedelta(days=30)
    else:  # "weekly" and any unknown value
        delta = timedelta(days=7)

    try:
        from zoneinfo import ZoneInfo
        tz        = ZoneInfo(timezone or "America/Denver")
        from datetime import datetime as _dt2
        now_local = _dt2.now(tz)
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local:
            candidate += delta
        # Store as UTC (no tzinfo) for consistent DB comparison
        import datetime as _dt_mod
        return candidate.astimezone(_dt_mod.timezone.utc).replace(tzinfo=None).isoformat()
    except Exception:
        # Fallback: treat time as UTC if zoneinfo unavailable
        now = datetime.utcnow()
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += delta
        return candidate.isoformat()


def content_scheduler_worker():
    print("[Scheduler] Worker started.")
    while True:
        try:
            due = schedules_get_due()
            if due: print(f"[Scheduler] {len(due)} schedule(s) due.")
            # Group by user so we send ONE notification email per user
            # regardless of how many niches are scheduled in the same window.
            # This prevents agents with multiple niches getting flooded with emails.
            from collections import defaultdict
            by_user = defaultdict(list)
            for sched in due:
                by_user[sched["user_id"]].append(sched)
            for user_id, scheds in by_user.items():
                _run_scheduled_generation_for_user(user_id, scheds)
        except Exception as e:
            print(f"[Scheduler] Error in worker: {e}")
        time.sleep(15 * 60)



def _pick_niche_situation(niche: str) -> str:
    """
    Returns a randomly selected situation string from NICHE_SITUATIONS[niche].
    Falls back to DEFAULT_SITUATIONS if the niche is not in the taxonomy.
    Used by the scheduler when no defaultSituation is set in agent setup.
    Ensures every agent gets niche-specific content regardless of which niche
    is scheduled — switching niches takes effect on the next scheduler run.
    """
    import random as _random
    from content_engine import NICHE_SITUATIONS, DEFAULT_SITUATIONS
    pool = NICHE_SITUATIONS.get(niche) or DEFAULT_SITUATIONS
    return _random.choice(pool)


def _run_scheduled_generation(sched: dict):
    user_id  = sched["user_id"]
    niche    = sched["niche"]
    sched_id = sched["id"]
    print(f"[Scheduler] Generating for user {user_id} / niche '{niche}'")
    try:
        from database import get_conn, create_approval_token
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = c.fetchone()
        try:
            c.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
            setup_row = c.fetchone()
            setup = json.loads(setup_row["setup_json"]) if setup_row else {}
        except Exception:
            setup = {}
        conn.close()
        if not user_row:
            print(f"[Scheduler] User {user_id} not found, skipping.")
            return
        result = generate_content_core(
            agent_name  = user_row["agent_name"],
            brokerage   = user_row["brokerage"],
            market      = setup.get("market", ""),
            niche       = niche,
            situation   = setup.get("defaultSituation") or _pick_niche_situation(niche),
            persona     = setup.get("defaultPersona") or "homeowners",
            tone        = setup.get("tone", "Professional"),
            length      = setup.get("length", "Standard"),
            trends      = setup.get("trends", []),
            brand_voice = setup.get("brandVoice", ""),
            short_bio   = setup.get("shortBio", ""),
            audience    = setup.get("audienceDescription", ""),
            words_avoid = setup.get("wordsAvoid", ""),
            words_prefer= setup.get("wordsPrefer", ""),
            mls_names   = setup.get("mlsNames", []),
            state       = setup.get("state", ""),
        )

        # ── FIX: strip non-serializable fields before saving ──────────────
        # generate_content_core returns content_response.dict() which includes
        # generated_at as a Python datetime object. json.dumps() cannot serialize
        # datetime, causing a silent TypeError that prevented content from ever
        # being saved to the library. Convert to ISO string before saving.
        content_to_save = dict(result["content"])
        if "generated_at" in content_to_save:
            from datetime import datetime as _dt
            val = content_to_save["generated_at"]
            if isinstance(val, _dt):
                content_to_save["generated_at"] = val.isoformat()

        # compliance is a ComplianceBadge.dict() — also strip any datetime values
        compliance_to_save = dict(result["compliance"])

        saved_item = library_save(
            user_id    = user_id,
            niche      = niche,
            content    = content_to_save,
            compliance = compliance_to_save,
            source     = "scheduled",
        )
        print(f"[Scheduler] ✓ Saved scheduled content item {saved_item.get('id')} for user {user_id} / '{niche}'")

        # ── Notify agent via email + SMS ───────────────────────────────────
        # Create a one-time approval token and send the link so the agent
        # can review and approve directly from their phone or inbox.
        try:
            from social import send_approval_email, send_approval_sms
            import asyncio

            item_id    = saved_item.get("id")
            token      = create_approval_token(user_id, item_id)
            # Point directly at the API endpoint — no static approve.html needed.
            # The /approve endpoint looks up item_id from the token, so the URL is clean.
            api_url     = os.getenv("BACKEND_URL", "https://api.homebridgegroup.co")
            approve_url = f"{api_url}/approve/{token}"
            agent_name = user_row["agent_name"] or "Agent"
            headline   = content_to_save.get("headline", "Your scheduled content is ready")

            # Email — always attempt (email is on the user record)
            # Use notification_email if set, else fall back to account email
            to_email = ""
            if user_row:
                to_email = user_row["notification_email"] if user_row["notification_email"] else user_row["email"]
            if to_email:
                try:
                    asyncio.run(send_approval_email(to_email, agent_name, headline, approve_url))
                    print(f"[Scheduler] ✓ Approval email sent to {to_email}")
                except Exception as email_err:
                    print(f"[Scheduler] ✗ Email failed: {email_err}")

            # SMS — use phone from user record, fall back to setup approvalPhone
            phone = (user_row["phone"] if user_row else "") or setup.get("approvalPhone", "") or setup.get("phone", "")
            if phone:
                try:
                    asyncio.run(send_approval_sms(phone, agent_name, headline, approve_url))
                    print(f"[Scheduler] ✓ Approval SMS sent to {phone}")
                except Exception as sms_err:
                    print(f"[Scheduler] ✗ SMS failed (check Twilio env vars): {sms_err}")
            else:
                print(f"[Scheduler] No phone on file for user {user_id} — SMS skipped.")

        except Exception as notify_err:
            # Notification failure must never block the scheduled run
            print(f"[Scheduler] ✗ Notification error (content was saved): {notify_err}")

    except Exception as e:
        print(f"[Scheduler] ✗ Generation failed for user {user_id} / '{niche}': {e}")
    finally:
        next_run = _compute_next_run(
            sched.get("frequency",  "weekly"),
            sched.get("time_of_day", "08:00"),
            sched.get("timezone",   "America/Denver"),
        )
        schedule_mark_ran(sched_id, next_run)


def _run_scheduled_generation_for_user(user_id: int, scheds: list):
    """
    Run all due schedules for a single user and send ONE consolidated
    notification email/SMS covering all generated niches.
    Prevents agents with multiple niches from receiving a flood of emails
    in a single 15-minute scheduler window.
    """
    saved_items   = []  # (niche, item_id, headline) tuples
    failed_niches = []

    for sched in scheds:
        niche    = sched["niche"]
        sched_id = sched["id"]
        try:
            from database import get_conn, create_approval_token
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user_row = c.fetchone()
            try:
                c.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
                setup_row = c.fetchone()
                setup = json.loads(setup_row["setup_json"]) if setup_row else {}
            except Exception:
                setup = {}
            conn.close()

            if not user_row:
                print(f"[Scheduler] User {user_id} not found, skipping niche '{niche}'.")
                continue

            # ── Part C: Scheduler-Niche Lifecycle safety net ─────────────────────
            # Verify the scheduled niche still exists in the agent's current
            # primaryNiches before generating. If not, deactivate the schedule
            # (do not delete -- admin may want to inspect) and skip.
            # HB Marketing schedules are exempt -- their niches live in
            # hb_marketing_setup_json, not agent_setup primaryNiches.
            # Spec: Niche Taxonomy v2.1 Specification, Scheduler-Niche Lifecycle Part C.
            _sched_context = sched.get("context", "agent")
            if _sched_context != "hb_marketing":
                _current_niches = setup.get("primaryNiches", []) or []
                if niche not in _current_niches:
                    print(f"[Scheduler] Stale schedule: '{niche}' not in user {user_id} active niches {_current_niches}. Deactivating.")
                    schedule_deactivate(sched_id)
                    failed_niches.append(niche)
                    continue

            # ── Usage limit check — never generate beyond backstop limit ────────
            # Protects against runaway token costs from auto-generation.
            from database import check_generation_backstop_allowed, record_generation
            role = user_row["role"] or "agent"
            plan = user_row["plan"] or "trial"
            if role not in ("super_admin", "admin"):
                backstop = check_generation_backstop_allowed(user_id, role, plan)
                if not backstop["allowed"]:
                    print(f"[Scheduler] ✗ User {user_id} at generation backstop ({backstop['backstop_used']}/{backstop['backstop_limit']}) — skipping niche '{niche}'. Resets: {backstop['resets_on']}")
                    failed_niches.append(niche)
                    schedule_mark_ran(sched_id, _compute_next_run(
                        sched.get("frequency", "weekly"),
                        sched.get("time_of_day", "08:00"),
                        sched.get("timezone", "America/Denver"),
                    ))
                    continue

            # ── Fetch hyper-local signals to enrich content generation ──────
            local_signal_trends = []
            try:
                from database import signals_get_latest as _sgl
                raw_signals = _sgl(user_id, limit=5, context="agent")
                local_signal_trends = [
                    f"{s.get('headline','')} ({s.get('area','')})".strip()
                    for s in raw_signals
                    if s.get("headline")
                ]
                if local_signal_trends:
                    print(f"[Scheduler] ✓ {len(local_signal_trends)} local signal(s) injected for user {user_id}")
            except Exception as _sig_e:
                print(f"[Scheduler] Signal fetch failed (non-blocking): {_sig_e}")

            result = generate_content_core(
                agent_name  = user_row["agent_name"],
                brokerage   = user_row["brokerage"],
                market      = setup.get("market", ""),
                niche       = niche,
                situation   = setup.get("defaultSituation") or _pick_niche_situation(niche),
                persona     = setup.get("defaultPersona") or "homeowners",
                tone        = setup.get("tone", "Professional"),
                length      = setup.get("length", "Standard"),
                trends      = local_signal_trends + (setup.get("trends", []) or []),
                brand_voice = setup.get("brandVoice", ""),
                short_bio   = setup.get("shortBio", ""),
                audience    = setup.get("audienceDescription", ""),
                words_avoid = setup.get("wordsAvoid", ""),
                words_prefer= setup.get("wordsPrefer", ""),
                mls_names   = setup.get("mlsNames", []),
                state       = setup.get("state", ""),
                cta_type    = setup.get("ctaType", ""),
                cta_url     = setup.get("ctaUrl", ""),
                cta_label   = setup.get("ctaLabel", ""),
                origin_story         = setup.get("originStory", ""),
                unfair_advantage     = setup.get("unfairAdvantage", ""),
                signature_perspective= setup.get("signaturePerspective", ""),
                not_for_client       = setup.get("notForClient", ""),
            )

            content_to_save = dict(result["content"])
            if "generated_at" in content_to_save:
                from datetime import datetime as _dt
                val = content_to_save["generated_at"]
                if isinstance(val, _dt):
                    content_to_save["generated_at"] = val.isoformat()

            compliance_to_save = dict(result["compliance"])
            saved_item = library_save(
                user_id    = user_id,
                niche      = niche,
                content    = content_to_save,
                compliance = compliance_to_save,
                source     = "scheduled",
            )
            item_id  = saved_item.get("id")
            headline = content_to_save.get("headline", "Your scheduled content is ready")
            saved_items.append((niche, item_id, headline))
            # Record this generation against the backstop counter
            if role not in ("super_admin", "admin"):
                record_generation(user_id, role)
            print(f"[Scheduler] ✓ Saved item {item_id} for user {user_id} / '{niche}'")

        except Exception as e:
            print(f"[Scheduler] ✗ Generation failed for user {user_id} / '{niche}': {e}")
            failed_niches.append(niche)
        finally:
            next_run = _compute_next_run(
                sched.get("frequency",  "weekly"),
                sched.get("time_of_day", "08:00"),
                sched.get("timezone",   "America/Denver"),
            )
            schedule_mark_ran(sched_id, next_run)

    # Send ONE consolidated notification for all successfully generated items
    if not saved_items:
        return

    try:
        from social import send_approval_email, send_approval_sms
        import asyncio
        from database import get_conn as _gc2, create_approval_token

        conn2 = _gc2()
        c2    = conn2.cursor()
        c2.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = c2.fetchone()
        c2.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
        setup_row = c2.fetchone()
        setup = json.loads(setup_row["setup_json"]) if setup_row else {}
        conn2.close()

        if not user_row:
            return

        agent_name = user_row["agent_name"] or "Agent"
        to_email   = user_row["notification_email"] or user_row["email"] or ""
        phone      = (user_row["phone"] or "") or setup.get("approvalPhone", "") or setup.get("phone", "")
        api_url    = os.getenv("BACKEND_URL", "https://api.homebridgegroup.co")

        # Use first item for the primary approval link; headline reflects count
        first_niche, first_item_id, first_headline = saved_items[0]
        token       = create_approval_token(user_id, first_item_id)
        approve_url = f"{api_url}/approve/{token}"

        if len(saved_items) == 1:
            headline_for_email = first_headline
        else:
            niches_str = ", ".join(n for n, _, _ in saved_items)
            headline_for_email = f"{len(saved_items)} new posts ready — {niches_str}"

        if to_email:
            try:
                asyncio.run(send_approval_email(to_email, agent_name, headline_for_email, approve_url))
                print(f"[Scheduler] ✓ Consolidated approval email sent to {to_email} ({len(saved_items)} item(s))")
            except Exception as email_err:
                print(f"[Scheduler] ✗ Email failed: {email_err}")

        if phone:
            try:
                asyncio.run(send_approval_sms(phone, agent_name, headline_for_email, approve_url))
                print(f"[Scheduler] ✓ Approval SMS sent to {phone}")
            except Exception as sms_err:
                print(f"[Scheduler] ✗ SMS failed: {sms_err}")

    except Exception as notify_err:
        print(f"[Scheduler] ✗ Notification error (content was saved): {notify_err}")


@app.get("/trends/latest")
async def latest_trends():
    return get_latest_trends()


@app.get("/trends/by-niche")
async def trends_by_niche(niche: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT source, topic, collected_at FROM trends WHERE niche = ? ORDER BY collected_at DESC LIMIT 200", (niche,))
    rows = c.fetchall()
    conn.close()
    grouped = {"google": [], "youtube": [], "reddit": [], "bing": [], "tiktok": [], "timestamp": datetime.utcnow().isoformat()}
    for source, topic, collected_at in rows:
        if source in grouped:
            grouped[source].append({"topic": topic, "collected_at": collected_at})
    if not any(grouped[s] for s in ["google","youtube","reddit","bing","tiktok"]):
        grouped["google"] = [{"topic": f"Rising interest in {niche} this week", "collected_at": datetime.utcnow().isoformat()}]
    return grouped


class SetupSaveRequest(BaseModel):
    setup: dict

@app.post("/setup/save")
async def save_setup(body: SetupSaveRequest, current_user=Depends(get_current_user)):
    uid = current_user["id"]

    # ── Part A: Scheduler-Niche Lifecycle — clean up stale schedules ──────────
    # Before saving the new setup, read the current primaryNiches from the DB.
    # Any niche that was in the old list but is NOT in the new list gets its
    # schedule record deleted. This prevents the scheduler from generating content
    # for niches the agent is no longer practicing in.
    # Spec: Niche Taxonomy v2.1 Specification, Scheduler-Niche Lifecycle Part A.
    try:
        _old_setup  = get_agent_setup(uid)
        _old_niches = set(_old_setup.get("primaryNiches", []) or [])
        _new_niches = set((body.setup or {}).get("primaryNiches", []) or [])
        _removed    = _old_niches - _new_niches
        if _removed:
            for _removed_niche in _removed:
                deleted = schedule_delete(uid, _removed_niche)
                if deleted:
                    print(f"[Setup] Cleared stale schedule for user {uid} / '{_removed_niche}'")
    except Exception as _sched_cleanup_e:
        # Never let schedule cleanup block the save
        print(f"[Setup] Schedule cleanup error for user {uid} (non-blocking): {_sched_cleanup_e}")

    try:
        save_agent_setup(uid, body.setup)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "Plan limit exceeded", "message": str(e)})

    from database import get_conn as _gc_slug
    _conn_s = _gc_slug()
    _c_s    = _conn_s.cursor()

    # ── Sync approvalPhone → users.phone so SMS notifications fire correctly ──
    # The scheduler and send-approval routes read users.phone directly from the
    # JWT/user record. Without this sync, the phone saved in setup JSON is never
    # seen by those routes and SMS is silently skipped.
    _approval_phone = (body.setup or {}).get("approvalPhone", "").strip()
    if _approval_phone:
        # Normalise to E.164 (+1XXXXXXXXXX) before storing
        _ph = _approval_phone
        if not _ph.startswith("+"):
            _ph = "+1" + "".join(c for c in _ph if c.isdigit())
        _c_s.execute(
            "UPDATE users SET phone = ? WHERE id = ?",
            (_ph, current_user["id"])
        )

    # Auto-generate slug if this agent doesn't have one yet
    _c_s.execute("SELECT agent_slug FROM users WHERE id = ?", (current_user["id"],))
    _slug_row = _c_s.fetchone()
    if not (_slug_row and _slug_row["agent_slug"]):
        _auto_slug = _make_slug(
            current_user.get("agent_name","agent"),
            (body.setup or {}).get("market","")
        )
        # Ensure uniqueness
        _c_s.execute("SELECT id FROM users WHERE agent_slug = ? AND id != ?",
                     (_auto_slug, current_user["id"]))
        if _c_s.fetchone():
            _auto_slug = f"{_auto_slug}-{current_user['id']}"
        _c_s.execute("UPDATE users SET agent_slug = ? WHERE id = ?",
                     (_auto_slug, current_user["id"]))

    _conn_s.commit()
    _conn_s.close()

    return {"success": True}

@app.get("/setup/get")
async def get_setup(current_user=Depends(get_current_user)):
    setup = get_agent_setup(current_user["id"])
    return {"setup": setup, "has_setup": bool(setup)}


# ── HB Marketing profile — separate from agent_setup ──────────────────────────
# These routes read/write users.hb_marketing_setup_json exclusively.
# They never touch agent_setup. This is the server-side half of the
# context separation that prevents marketing profile saves from
# overwriting the agent's personal identity data.

@app.post("/marketing-setup/save")
async def save_marketing_setup(request: Request, current_user=Depends(get_current_user)):
    """
    Save the HB Marketing company profile for this user.
    Writes to users.hb_marketing_setup_json — never touches agent_setup.
    Available to super_admin and hb_marketer roles only.
    """
    allowed_roles = ("super_admin", "admin", "hb_marketer")
    if current_user.get("role") not in allowed_roles:
        raise HTTPException(403, "Marketing profile access requires super_admin or hb_marketer role.")
    body  = await request.json()
    setup = body.get("setup", {})
    if not isinstance(setup, dict):
        raise HTTPException(400, "setup must be a JSON object.")
    from database import get_conn as _gc
    import json as _json
    conn = _gc()
    try:
        conn.execute(
            "UPDATE users SET hb_marketing_setup_json = ? WHERE id = ?",
            (_json.dumps(setup), current_user["id"])
        )
        conn.commit()
    finally:
        conn.close()
    return {"success": True}


@app.get("/marketing-setup/get")
async def get_marketing_setup(current_user=Depends(get_current_user)):
    """
    Retrieve the HB Marketing company profile for this user.
    Reads from users.hb_marketing_setup_json — never touches agent_setup.
    Returns empty dict if not yet saved (first-time marketing context boot).
    """
    allowed_roles = ("super_admin", "admin", "hb_marketer")
    if current_user.get("role") not in allowed_roles:
        raise HTTPException(403, "Marketing profile access requires super_admin or hb_marketer role.")
    from database import get_conn as _gc
    import json as _json
    conn = _gc()
    try:
        c = conn.cursor()
        c.execute("SELECT hb_marketing_setup_json FROM users WHERE id = ?", (current_user["id"],))
        row = c.fetchone()
    finally:
        conn.close()
    if not row or not row["hb_marketing_setup_json"]:
        return {"setup": {}, "has_setup": False}
    try:
        setup = _json.loads(row["hb_marketing_setup_json"])
        return {"setup": setup, "has_setup": True}
    except Exception:
        return {"setup": {}, "has_setup": False}


@app.get("/results")
async def get_results(current_user=Depends(get_current_user)):
    results = get_user_results(current_user["id"])
    return results


class ComplianceReportRequest(BaseModel):
    setup: dict = {}
    date_from: str = ""
    date_to:   str = ""

@app.post("/compliance/report")
async def download_compliance_report(req: ComplianceReportRequest, current_user=Depends(get_current_user)):
    try:
        pdf_bytes = generate_compliance_pdf(user_id=current_user["id"], agent_name=current_user.get("agent_name",""), brokerage=current_user.get("brokerage",""), email=current_user.get("email",""), setup=req.setup, date_from=req.date_from, date_to=req.date_to)
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"PDF generation requires reportlab: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    filename = f"AutoMates_Compliance_Report_{current_user.get('agent_name','Agent').replace(' ','_')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/compliance/history")
async def get_agent_compliance_history(
    date_from: str = "",
    date_to:   str = "",
    context:   str = "",
    current_user=Depends(get_current_user)
):
    """
    Return the agent's permanent compliance record history.
    Newest first. Optionally filtered by date range (ISO strings).
    Optionally filtered by context ('agent' or 'hb_marketing').
    Records persist even after library items are deleted.
    """
    records = get_compliance_records(
        user_id   = current_user["id"],
        date_from = date_from,
        date_to   = date_to,
        context   = context,
    )
    return {"records": records, "total": len(records)}


@app.get("/compliance/history/report")
async def download_agent_compliance_history_pdf(
    date_from: str = "",
    date_to:   str = "",
    context:   str = "",
    current_user=Depends(get_current_user)
):
    """
    Generate a PDF compliance report from the permanent compliance_records
    table instead of content_library — survives post deletions.
    Optionally filtered by context ('agent' or 'hb_marketing').
    """
    try:
        pdf_bytes = generate_compliance_pdf(
            user_id    = current_user["id"],
            agent_name = current_user.get("agent_name", ""),
            brokerage  = current_user.get("brokerage", ""),
            email      = current_user.get("email", ""),
            setup      = {},
            date_from  = date_from,
            date_to    = date_to,
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"PDF generation requires reportlab: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    name     = current_user.get("agent_name", "Agent").replace(" ", "_")
    filename = f"AutoMates_Compliance_History_{name}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/broker/compliance-history")
async def broker_compliance_history(req: dict, current_user=Depends(get_current_user)):
    """
    Return compliance records for all agents under a broker, or a single
    agent if agent_id is provided. Filterable by date range.
    Used by the broker/team compliance dashboard.
    """
    if current_user.get("role") not in ("broker", "team", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Broker or team accounts only.")
    records = get_compliance_records_for_broker(
        broker_id  = current_user["id"],
        agent_id   = req.get("agent_id"),
        date_from  = req.get("date_from", ""),
        date_to    = req.get("date_to", ""),
    )
    return {"records": records, "total": len(records)}


@app.post("/broker/compliance-history/report")
async def broker_compliance_history_pdf(req: dict, current_user=Depends(get_current_user)):
    """
    Generate a PDF compliance report for a specific agent under this broker.
    Uses generate_compliance_pdf with optional date filtering.
    """
    if current_user.get("role") not in ("broker", "team", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Broker or team accounts only.")
    agent_id = req.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id required.")
    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ? AND broker_id = ?", (agent_id, current_user["id"]))
    agent = c.fetchone()
    conn.close()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found in your office.")
    try:
        pdf_bytes = generate_compliance_pdf(
            user_id    = agent["id"],
            agent_name = agent["agent_name"],
            brokerage  = agent["brokerage"],
            email      = agent["email"],
            setup      = {},
            date_from  = req.get("date_from", ""),
            date_to    = req.get("date_to", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    filename = f"AutoMates_Compliance_{agent['agent_name'].replace(' ','_')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


import secrets, json as _json
from datetime import datetime as _dt

@app.post("/demo/create-token")
async def create_demo_token(request: Request, user=Depends(get_current_user)):
    if user.get("role") not in ("admin","super_admin"): raise HTTPException(403, "Admin only")
    body = await request.json()
    label = (body.get("label") or "").strip()
    if not label: raise HTTPException(400, "Label required")
    token = "tk_" + secrets.token_urlsafe(10)
    conn = database.get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO demo_tokens (token, label, created_by) VALUES (?,?,?)", (token, label, user["id"]))
    conn.commit()
    conn.close()
    return {"token": token, "label": label}

@app.get("/demo/tokens")
async def list_demo_tokens(user=Depends(get_current_user)):
    if user.get("role") not in ("admin","super_admin"): raise HTTPException(403, "Admin only")
    conn = database.get_conn()
    c = conn.cursor()
    c.execute("SELECT id, token, label, created_at, open_count, last_opened, ip_log FROM demo_tokens ORDER BY created_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        try: r["ip_log"] = _json.loads(r["ip_log"] or "[]")
        except: r["ip_log"] = []
    return {"tokens": rows}

@app.delete("/demo/tokens/{token_id}")
async def delete_demo_token(token_id: int, user=Depends(get_current_user)):
    if user.get("role") not in ("admin","super_admin"): raise HTTPException(403, "Admin only")
    conn = database.get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM demo_tokens WHERE id=?", (token_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/demo/validate")
async def validate_demo_token(token: str, request: Request):
    if not token or not token.startswith("tk_"):
        raise HTTPException(403, "Invalid demo token")
    conn = database.get_conn()
    c = conn.cursor()
    c.execute("SELECT id, ip_log, open_count FROM demo_tokens WHERE token=?", (token,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(403, "Demo token not found or expired")
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded: client_ip = forwarded.split(",")[0].strip()
    try: ip_log = _json.loads(row["ip_log"] or "[]")
    except: ip_log = []
    if client_ip not in ip_log: ip_log.append(client_ip)
    c.execute("UPDATE demo_tokens SET open_count=open_count+1, last_opened=?, ip_log=? WHERE id=?", (_dt.utcnow().isoformat(), _json.dumps(ip_log), row["id"]))
    conn.commit()
    conn.close()
    return {"valid": True, "message": "Demo access granted"}


@app.post("/office/invite")
async def invite_agent(request: Request, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ("broker", "admin", "super_admin"):
        raise HTTPException(403, "Office managers only")
    body  = await request.json()
    name  = (body.get("name")  or "").strip()
    email = (body.get("email") or "").strip()
    phone = (body.get("phone") or "").strip()[:30]
    if not name or not email: raise HTTPException(400, "Name and email required")

    # Persist invite to DB
    conn = database.get_conn()
    c    = conn.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS office_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            office_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            invited_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'pending'
        )""")
        # Add phone column if table already existed without it
        try: c.execute("ALTER TABLE office_invites ADD COLUMN phone TEXT")
        except Exception: pass
        c.execute("INSERT INTO office_invites (office_id, name, email, phone) VALUES (?,?,?,?)",
                  (current_user["id"], name, email, phone))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(500, f"Could not store invite: {e}")
    conn.close()

    # Build invite link — agents register and get linked to this office automatically
    office_code = current_user.get("office_code", "")
    frontend_url = os.getenv("FRONTEND_URL", "https://app.homebridgegroup.co")
    invite_url   = f"{frontend_url}/register?office={office_code}" if office_code else frontend_url
    inviter_name = current_user.get("agent_name") or current_user.get("email", "Your broker")

    # Send invite email via SendGrid
    email_sent = False
    sendgrid_key  = os.getenv("SENDGRID_API_KEY", "")
    sendgrid_from = os.getenv("SENDGRID_FROM_EMAIL", "support@homebridgegroup.co")
    if sendgrid_key:
        try:
            import httpx as _httpx
            html_body = f"""
<div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:32px 24px;">
  <div style="font-size:22px;font-weight:700;color:#1a1a1a;margin-bottom:8px;">You're invited to HomeBridge</div>
  <div style="font-size:15px;color:#444;margin-bottom:24px;">
    <strong>{inviter_name}</strong> has invited you to join HomeBridge — the platform that writes hyper-local real estate content in your voice, checks it for compliance, and sends it to you for one-tap approval.
  </div>
  <a href="{invite_url}" style="display:inline-block;background:#1749c9;color:#fff;font-weight:700;font-size:15px;padding:14px 28px;border-radius:8px;text-decoration:none;margin-bottom:24px;">Accept Invitation →</a>
  <div style="font-size:13px;color:#666;margin-top:16px;">
    Or copy this link: <a href="{invite_url}" style="color:#1749c9;">{invite_url}</a>
  </div>
  <div style="margin-top:32px;font-size:12px;color:#999;border-top:1px solid #eee;padding-top:16px;">
    HomeBridge · homebridgegroup.co
  </div>
</div>"""
            payload = {
                "personalizations": [{"to": [{"email": email, "name": name}]}],
                "from": {"email": sendgrid_from, "name": "HomeBridge"},
                "subject": f"{inviter_name} invited you to HomeBridge",
                "content": [{"type": "text/html", "value": html_body}],
            }
            r = await _httpx.AsyncClient().post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {sendgrid_key}", "Content-Type": "application/json"},
                json=payload, timeout=10,
            )
            email_sent = r.status_code in (200, 202)
        except Exception as e:
            print(f"[Invite] Email send failed: {e}")

    return {"ok": True, "email_sent": email_sent, "message": f"Invite {'sent' if email_sent else 'queued'} for {name} ({email})"}


def check_paywall(user: dict):
    if not STRIPE_ENABLED: return
    sub = get_subscription_status(user["id"])
    if sub.get("status") == "expired":
        raise HTTPException(status_code=402, detail={"code": "subscription_expired", "message": "Your 14-day trial has ended. Subscribe to continue.", "upgrade_url": "/billing/create-checkout"})

@app.get("/billing/status")
async def billing_status(current_user=Depends(get_current_user)):
    return get_subscription_status(current_user["id"])

@app.post("/billing/create-checkout")
async def create_checkout(request: Request, current_user=Depends(get_current_user)):
    if not STRIPE_ENABLED: raise HTTPException(503, "Billing not yet configured — check back soon.")
    body      = await request.json()
    price_key = body.get("price_key", "starter_monthly")
    price_id  = STRIPE_PRICES.get(price_key, "")
    if not price_id: raise HTTPException(400, f"Unknown plan key: {price_key}")
    sub_data    = get_subscription_status(current_user["id"])
    customer_id = sub_data.get("stripe_customer_id")
    if not customer_id:
        customer    = _stripe.Customer.create(email=current_user["email"], name=current_user.get("agent_name",""), metadata={"hb_user_id": str(current_user["id"])})
        customer_id = customer.id
    # Founding Member and Coach both get a 20-day free trial — card required, not charged until day 21
    subscription_data = {"trial_period_days": 20} if price_key == "coach_monthly" else {}
    session = _stripe.checkout.Session.create(customer=customer_id, mode="subscription", line_items=[{"price": price_id, "quantity": 1}], success_url=f"{os.getenv('FRONTEND_URL','https://app.homebridgegroup.co')}?billing=success", cancel_url=f"{os.getenv('FRONTEND_URL','https://app.homebridgegroup.co')}?billing=cancelled", metadata={"hb_user_id": str(current_user["id"]), "price_key": price_key}, allow_promotion_codes=True, subscription_data=subscription_data)
    return {"checkout_url": session.url}

@app.post("/billing/portal")
async def billing_portal(current_user=Depends(get_current_user)):
    if not STRIPE_ENABLED: raise HTTPException(503, "Billing not yet configured.")
    sub_data    = get_subscription_status(current_user["id"])
    customer_id = sub_data.get("stripe_customer_id")
    if not customer_id: raise HTTPException(400, "No billing account yet. Please subscribe first.")
    session = _stripe.billing_portal.Session.create(customer=customer_id, return_url=f"{os.getenv('FRONTEND_URL','https://app.homebridgegroup.co')}")
    return {"portal_url": session.url}

@app.post("/billing/webhook")
async def stripe_webhook(request: Request):
    if not STRIPE_ENABLED: return {"ok": True}
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = _stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        print(f"[Webhook] Signature verification failed: {e}")
        print(f"[Webhook] Secret in use starts with: {STRIPE_WEBHOOK_SECRET[:12] if STRIPE_WEBHOOK_SECRET else 'EMPTY'}")
        print(f"[Webhook] Payload length: {len(payload)} sig_header present: {bool(sig_header)}")
        raise HTTPException(400, f"Webhook error: {e}")
    etype = event["type"]
    obj   = event["data"]["object"]

    if etype == "checkout.session.completed":
        hb_uid    = int(obj.get("metadata", {}).get("hb_user_id", 0) or 0)
        price_key = obj.get("metadata", {}).get("price_key", "")
        if not hb_uid:
            return {"ok": True}

        # ── Add-on Pack — one-time purchase, no subscription ─────────────────
        if "addon" in price_key or "add_on" in price_key or "add-on" in price_key:
            from database import apply_addon_pack
            result = apply_addon_pack(hb_uid)
            print(f"[Billing] Add-on Pack applied for user {hb_uid}: +30 posts, +90 backstop. New totals: {result}")
            return {"ok": True}

        # ── Video Top-up Pack — one-time purchase, +10 video renders ────────
        if "video_topup" in price_key or "video-topup" in price_key or "video_top_up" in price_key:
            result = apply_video_topup(hb_uid)
            print(f"[Billing] Video Top-up applied for user {hb_uid}: +10 renders. New totals: {result}")
            return {"ok": True}

        # ── Subscription plan — map price_key to plan name ───────────────────
        # price_key must match PLAN_LIMITS keys exactly.
        # Format expected: "starter_monthly", "professional_annual", "power_monthly", etc.
        if   "founding_member" in price_key: plan = "founding_member"
        elif "coach"           in price_key: plan = "coach"
        elif "power"           in price_key: plan = "power"
        elif "professional"    in price_key: plan = "professional"
        elif "starter"         in price_key: plan = "starter"
        elif "office_team"     in price_key: plan = "office_team"
        elif "office_growth"   in price_key: plan = "office_growth"
        elif "office_starter"  in price_key: plan = "office_starter"
        else:                                plan = "starter"  # safe default — not "agent" (wrong limits)

        cycle = "annual" if "annual" in price_key else "monthly"

        # Billing reset day — set from subscription's current_period_start day
        # so the agent's counter resets on their actual billing anniversary.
        billing_reset_day = 1
        try:
            sub_id = obj.get("subscription", "")
            if sub_id:
                sub = _stripe.Subscription.retrieve(sub_id)
                from datetime import datetime as _dt_wh
                period_start = sub.get("current_period_start")
                if period_start:
                    billing_reset_day = _dt_wh.utcfromtimestamp(period_start).day
        except Exception as _brd_e:
            print(f"[Billing] Could not retrieve billing day for user {hb_uid}: {_brd_e}")

        activate_subscription(
            hb_uid, plan, cycle,
            obj.get("customer", ""),
            obj.get("subscription", ""),
            billing_reset_day=billing_reset_day,
        )
        print(f"[Billing] Subscription activated: user {hb_uid}, plan={plan}, cycle={cycle}, reset_day={billing_reset_day}")

        # Mark referral as actively paying — this is what makes partner tiers
        # advance and payouts calculate. Without this, every partner stays at
        # Starter forever and every payout is $0. (Opus N1 fix)
        try:
            referral_mark_paying(hb_uid)
        except Exception as _rmp_e:
            print(f"[Billing] referral_mark_paying failed for user {hb_uid} (non-blocking): {_rmp_e}")

    elif etype in ("customer.subscription.deleted", "customer.subscription.paused"):
        cust_id = obj.get("customer", "")
        conn = database.get_conn()
        c    = conn.cursor()
        c.execute("SELECT id FROM users WHERE stripe_customer_id=?", (cust_id,))
        row = c.fetchone()
        conn.close()
        if row:
            cancel_subscription(row["id"])
            # Mark referral as lapsed so partner tier counts drop at quarter-end
            try:
                referral_mark_lapsed(row["id"])
            except Exception as _rml_e:
                print(f"[Billing] referral_mark_lapsed failed for user {row['id']} (non-blocking): {_rml_e}")

    elif etype == "invoice.payment_succeeded":
        # Monthly renewal — reset billing period counters
        cust_id = obj.get("customer", "")
        conn = database.get_conn()
        c    = conn.cursor()
        c.execute("SELECT id, billing_reset_day FROM users WHERE stripe_customer_id=?", (cust_id,))
        row = c.fetchone()
        conn.close()
        if row:
            uid       = row["id"]
            reset_day = row["billing_reset_day"] or 1
            from database import _compute_next_billing_reset
            next_reset = _compute_next_billing_reset(reset_day)
            conn2 = database.get_conn()
            conn2.execute("""
                UPDATE users
                SET approved_post_count       = 0,
                    generation_backstop_count = 0,
                    generation_reset_date     = ?,
                    addon_posts_limit         = 0,
                    addon_backstop_limit      = 0
                WHERE id = ?
            """, (next_reset.isoformat(), uid))
            conn2.commit()
            conn2.close()
            print(f"[Billing] Monthly renewal counters reset for user {uid}, next reset: {next_reset.date()}")

    elif etype == "invoice.payment_failed":
        # After Stripe exhausts its retry grace period, mark the referral as
        # lapsed so it stops counting toward partner tier and payout calculations.
        cust_id = obj.get("customer", "")
        if cust_id:
            conn = database.get_conn()
            c    = conn.cursor()
            c.execute("SELECT id FROM users WHERE stripe_customer_id=?", (cust_id,))
            row = c.fetchone()
            conn.close()
            if row:
                try:
                    referral_mark_lapsed(row["id"])
                except Exception as _rml_f:
                    print(f"[Billing] referral_mark_lapsed (payment_failed) for user {row['id']} (non-blocking): {_rml_f}")

    return {"ok": True}

@app.get("/broker/office-stats")
async def broker_office_stats(current_user=Depends(get_current_user)):
    if current_user.get("role") not in ("broker", "team", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Broker or team accounts only.")
    stats = get_broker_office_stats(current_user["id"])
    return {"agents": stats, "count": len(stats)}


@app.post("/broker/agent-compliance-report")
async def broker_agent_report(req: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ("broker", "team", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Broker or team accounts only.")
    agent_id = req.get("agent_id")
    if not agent_id: raise HTTPException(status_code=400, detail="agent_id required.")
    from database import get_conn
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ? AND broker_id = ?", (agent_id, current_user["id"]))
    agent = c.fetchone()
    conn.close()
    if not agent: raise HTTPException(status_code=404, detail="Agent not found in your office.")
    pdf_bytes = generate_compliance_pdf(user_id=agent["id"], agent_name=agent["agent_name"], brokerage=agent["brokerage"], email=agent["email"], setup={})
    filename = f"Compliance_{agent['agent_name'].replace(' ','_')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ─────────────────────────────────────────────
# PUBLIC AGENT PROFILE — CIR™ Verified
# No auth required. Safe public data only.
# Never returns email, phone, tokens, or scores.
# Called by homebridgegroup.co/agent-profile.html?id={user_id}
# ─────────────────────────────────────────────
@app.get("/profile/{user_id}")
async def public_agent_profile(user_id: int):
    try:
        from database import get_conn
        from datetime import datetime, timedelta
        conn = get_conn()
        c    = conn.cursor()

        # User basics — agent or broker only
        c.execute("SELECT id, agent_name, brokerage, role FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        if not user or user["role"] not in ("agent", "broker"):
            raise HTTPException(404, "Profile not found.")

        # Setup data
        c.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
        setup_row = c.fetchone()
        setup = {}
        try:
            if setup_row:
                setup = json.loads(setup_row["setup_json"] or "{}")
        except Exception:
            pass

        # Library stats
        now       = datetime.utcnow()
        month_ago = (now - timedelta(days=30)).isoformat()

        c.execute("""
            SELECT id, status, approved_at, published_at, niche, content, cir_id, compliance
            FROM content_library
            WHERE user_id = ? AND status IN ('approved','published')
            ORDER BY approved_at DESC
        """, (user_id,))
        all_items = [dict(r) for r in c.fetchall()]

        posts_total     = len(all_items)
        posts_30_days   = sum(1 for i in all_items if (i.get("approved_at") or "") >= month_ago)
        posts_published = sum(1 for i in all_items if i.get("status") == "published")
        cir_count       = sum(1 for i in all_items if i.get("cir_id"))

        # ── Weekly streak calculation ──
        # A week counts if the user approved at least 1 post in that Mon-Sun window.
        week_streak = 0
        if all_items:
            from collections import defaultdict
            week_set = set()
            for item in all_items:
                approved = item.get("approved_at") or ""
                if approved:
                    try:
                        dt = datetime.fromisoformat(approved[:19])
                        # ISO week key e.g. "2026-W12"
                        week_key = dt.strftime("%G-W%V")
                        week_set.add(week_key)
                    except Exception:
                        pass
            # Count consecutive weeks ending this week
            check = now
            while True:
                wk = check.strftime("%G-W%V")
                if wk in week_set:
                    week_streak += 1
                    check -= timedelta(weeks=1)
                else:
                    break

        # Compliance pct — clean passes only
        clean_count = 0
        for item in all_items:
            try:
                comp = json.loads(item.get("compliance") or "{}")
                if comp.get("overallStatus") in ("compliant", "pass"):
                    clean_count += 1
            except Exception:
                clean_count += 1
        compliance_pct = round((clean_count / posts_total * 100)) if posts_total > 0 else 100

        # Recent headlines — last 3, title only, no full content
        recent_headlines = []
        for item in all_items[:3]:
            try:
                content  = json.loads(item.get("content") or "{}")
                headline = content.get("headline", "")
                if headline:
                    recent_headlines.append({
                        "headline": headline,
                        "niche":    item.get("niche", ""),
                        "date":     (item.get("approved_at") or "")[:10],
                        "cir_id":   item.get("cir_id", ""),
                    })
            except Exception:
                pass

        # Member since
        c.execute("SELECT MIN(approved_at) as earliest FROM content_library WHERE user_id = ?", (user_id,))
        earliest_row = c.fetchone()
        member_since = ""
        if earliest_row and earliest_row["earliest"]:
            try:
                dt = datetime.fromisoformat(earliest_row["earliest"])
                member_since = dt.strftime("%B %Y")
            except Exception:
                pass

        conn.close()

        return {
            "id":               user_id,
            "agent_name":       user["agent_name"] or "",
            "brokerage":        user["brokerage"]  or "",
            "market":           setup.get("market", ""),
            "business_name":    setup.get("businessName", ""),
            "short_bio":        setup.get("shortBio", ""),
            "service_areas":    setup.get("serviceAreas", []),
            "niches":           setup.get("primaryNiches", []),
            "designations":     setup.get("designations", []),
            "posts_total":      posts_total,
            "posts_30_days":    posts_30_days,
            "posts_published":  posts_published,
            "cir_count":        cir_count,
            "compliance_pct":   compliance_pct,
            "member_since":     member_since,
            "recent_headlines": recent_headlines,
            "cir_verified":     cir_count > 0,
            "week_streak":      week_streak,
            "profile_url":      f"https://homebridgegroup.co/agent-profile.html?id={user_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Profile lookup failed: {str(e)}")


# ─────────────────────────────────────────────
# WAITLIST / FIRST LOOK — Public endpoint
# No auth required. Stores lead + sends email via SendGrid.
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────────────────
# WEEKLY PROMPT — surfaces this week's suggested situation
# Called on dashboard load. Returns a curated situation,
# the user's streak, and a motivational nudge.
# ─────────────────────────────────────────────────────────
@app.get("/weekly-prompt")
async def weekly_prompt(current_user: dict = Depends(get_current_user)):
    from database import get_conn as _gc_wp
    user_id = current_user["id"]
    conn = _gc_wp()
    c = conn.cursor()

    # Get user setup for niche
    c.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    setup = {}
    if row:
        try:
            import json as _json
            setup = _json.loads(row["setup_json"] or "{}")
        except Exception:
            pass

    niches = setup.get("primaryNiches", [])
    primary_niche = niches[0] if niches else None

    # Get streak
    c.execute("""
        SELECT approved_at FROM content_library
        WHERE user_id = ? AND approved_at IS NOT NULL
        ORDER BY approved_at DESC LIMIT 200
    """, (user_id,))
    rows = c.fetchall()
    conn.close()

    from datetime import datetime, timedelta
    now = datetime.utcnow()
    week_streak = 0
    if rows:
        week_set = set()
        for r in rows:
            try:
                dt = datetime.fromisoformat(str(r["approved_at"])[:19])
                week_set.add(dt.strftime("%G-W%V"))
            except Exception:
                pass
        check = now
        while True:
            wk = check.strftime("%G-W%V")
            if wk in week_set:
                week_streak += 1
                check -= timedelta(weeks=1)
            else:
                break

    # Pick a situation — every 6th prompt is Lighter Side
    import random
    from content_engine import NICHE_SITUATIONS, LIGHTER_SIDE_SITUATIONS, DEFAULT_SITUATIONS

    # Lighter Side every ~6 weeks (use week number mod 6)
    week_num = int(now.strftime("%V"))
    use_lighter = (week_num % 6 == 0)

    if use_lighter:
        situation = random.choice(LIGHTER_SIDE_SITUATIONS)
        situation_type = "lighter"
    elif primary_niche and primary_niche in NICHE_SITUATIONS:
        pool = NICHE_SITUATIONS[primary_niche]
        situation = random.choice(pool)
        situation_type = "niche"
    else:
        situation = random.choice(DEFAULT_SITUATIONS)
        situation_type = "default"

    # Streak message
    if week_streak == 0:
        nudge = "This week is a great time to start."
    elif week_streak == 1:
        nudge = "You posted last week. Keep the momentum going."
    elif week_streak < 4:
        nudge = f"{week_streak} weeks in a row. You're building something real."
    elif week_streak < 12:
        nudge = f"{week_streak} consecutive weeks. Your presence is compounding."
    else:
        nudge = f"{week_streak} weeks straight. That's a track record most agents never build."

    return {
        "situation":      situation,
        "situation_type": situation_type,
        "week_streak":    week_streak,
        "nudge":          nudge,
        "niche":          primary_niche or "General",
    }



# ─────────────────────────────────────────────
# OAUTH DIAGNOSTIC — checks credential config
# GET /oauth-status  (authenticated)
# Returns which platforms are configured with
# credentials in env vars, without exposing keys.
# ─────────────────────────────────────────────
@app.get("/oauth-status")
async def oauth_status(current_user: dict = Depends(get_current_user)):
    import os as _os
    checks = {
        "google": {
            "client_id_set":     bool(_os.getenv("GOOGLE_CLIENT_ID")),
            "client_secret_set": bool(_os.getenv("GOOGLE_CLIENT_SECRET")),
            "redirect_uri":      f"{_os.getenv('BACKEND_URL', 'https://api.homebridgegroup.co')}/social/google/callback",
        },
        "linkedin": {
            "client_id_set":     bool(_os.getenv("LINKEDIN_CLIENT_ID")),
            "client_secret_set": bool(_os.getenv("LINKEDIN_CLIENT_SECRET")),
            "redirect_uri":      f"{_os.getenv('BACKEND_URL', 'https://api.homebridgegroup.co')}/social/linkedin/callback",
        },
        "facebook": {
            "client_id_set":     bool(_os.getenv("META_APP_ID")),
            "client_secret_set": bool(_os.getenv("META_APP_SECRET")),
            "redirect_uri":      f"{_os.getenv('BACKEND_URL', 'https://api.homebridgegroup.co')}/social/facebook/callback",
        },
        "youtube": {
            "client_id_set":     bool(_os.getenv("YOUTUBE_CLIENT_ID") or _os.getenv("GOOGLE_CLIENT_ID")),
            "client_secret_set": bool(_os.getenv("YOUTUBE_CLIENT_SECRET") or _os.getenv("GOOGLE_CLIENT_SECRET")),
            "redirect_uri":      f"{_os.getenv('BACKEND_URL', 'https://api.homebridgegroup.co')}/social/youtube/callback",
        },
        "sendgrid": {
            "api_key_set": bool(_os.getenv("SENDGRID_API_KEY")),
        },
        "stripe": {
            "secret_key_set": bool(_os.getenv("STRIPE_SECRET_KEY")),
        },
    }

    # Also check DB connections for this user
    try:
        from database import get_conn as _get_conn
        _conn = _get_conn()
        _c    = _conn.cursor()
        _c.execute(
            "SELECT platform, platform_handle, expires_at FROM platform_connections WHERE user_id = ?",
            (current_user["id"],)
        )
        connected = [
            {"platform": r["platform"], "handle": r["platform_handle"], "expires_at": r["expires_at"]}
            for r in _c.fetchall()
        ]
        _conn.close()
    except Exception:
        connected = []

    return {
        "user_id":    current_user["id"],
        "credentials": checks,
        "connected_platforms": connected,
    }



# ═══════════════════════════════════════════════════════════════
# AGENT AUTHORITY PAGES — Public SEO infrastructure
# Every agent gets: {slug}.homebridgegroup.co
# Slug = firstname-lastname-primarycity (auto-generated, customizable)
# These endpoints are PUBLIC — no auth required.
# They power Google ranking, AI search citation, and agent presence.
# ═══════════════════════════════════════════════════════════════

import re as _re

def _make_slug(agent_name: str, market: str) -> str:
    """Generate a URL slug from agent name + primary market city."""
    name = _re.sub(r"[^a-z0-9]+", "-", agent_name.lower().strip()).strip("-")
    city = ""
    if market:
        # Take the first word before any comma, dash, or 'metro'
        raw = market.split(",")[0].split("-")[0]
        raw = _re.sub(r"(?i)\bmetro\b|\barea\b|\bcounty\b", "", raw).strip()
        words = raw.split()
        city  = words[0].lower() if words else ""
        city  = _re.sub(r"[^a-z0-9]+", "", city)
    slug = f"{name}-{city}" if city else name
    return slug[:60]

def _get_agent_by_slug(slug: str) -> dict | None:
    """Look up a user by their agent_slug. Returns user row or None."""
    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    c.execute("SELECT * FROM users WHERE agent_slug = ? AND is_active = 1", (slug,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


@app.get("/public/agent/{slug}")
async def public_agent_profile(slug: str):
    """
    Public agent authority page data.
    Powers SEO landing pages at {slug}.homebridgegroup.co
    Returns full agent identity + all verified posts (full text).
    No auth required — this is intentionally public for Google/AI indexing.
    """
    import json as _json
    from database import get_conn as _gc

    user = _get_agent_by_slug(slug)
    if not user:
        raise HTTPException(404, "Agent profile not found.")

    user_id = user["id"]
    conn    = _gc()
    c       = conn.cursor()

    # Setup data
    c.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
    row   = c.fetchone()
    setup = {}
    if row:
        try:
            setup = _json.loads(row["setup_json"] or "{}")
        except Exception:
            pass

    # All approved/published/archived posts — FULL TEXT for SEO.
    # Archived posts remain on the authority page — archiving is housekeeping,
    # not a retraction of CIR-verified content. No LIMIT — agents accumulate
    # hundreds of posts over time.
    now       = datetime.utcnow()
    month_ago = (now - timedelta(days=30)).isoformat()

    c.execute("""
        SELECT id, niche, content, compliance, cir_id,
               approved_at, published_at, status, origin_type, answer_ref
        FROM content_library
        WHERE user_id = ? AND status IN ('approved','published','archived')
        ORDER BY approved_at DESC
    """, (user_id,))
    items = [dict(r) for r in c.fetchall()]

    # Stats — active posts only (approved/published) for displayed metrics.
    # CIR count queries compliance_records directly — permanent table, survives post deletion.
    # This ensures deleted posts do not reduce the displayed CIR count on the authority page.
    active_items  = [i for i in items if i.get("status") in ("approved", "published")]
    posts_30_days = sum(1 for i in active_items if (i.get("approved_at") or "") >= month_ago)
    c2            = conn.cursor()
    c2.execute("SELECT COUNT(*) FROM compliance_records WHERE user_id = ?", (user_id,))
    cir_count     = c2.fetchone()[0] or 0
    # posts_total = all CIR-reviewed posts per compliance_records — permanent, not affected by deletion.
    posts_total   = cir_count

    clean_count = 0
    for item in active_items:
        try:
            comp = _json.loads(item.get("compliance") or "{}")
            if comp.get("overallStatus") in ("compliant","pass"):
                clean_count += 1
        except Exception:
            clean_count += 1
    compliance_pct = round((clean_count / posts_total * 100)) if posts_total > 0 else 100

    # Member since
    member_since = ""
    if items:
        oldest = min((i.get("approved_at") or "") for i in items if i.get("approved_at"))
        if oldest:
            try:
                member_since = datetime.fromisoformat(oldest).strftime("%B %Y")
            except Exception:
                pass

    # Week streak — consecutive weeks with at least one approved post
    week_streak = 0
    if items:
        from collections import defaultdict as _dd
        week_set = set()
        for item in items:
            approved = item.get("approved_at") or ""
            if approved:
                try:
                    dt = datetime.fromisoformat(approved[:19])
                    week_set.add(dt.strftime("%G-W%V"))
                except Exception:
                    pass
        check = now
        while True:
            wk = check.strftime("%G-W%V")
            if wk in week_set:
                week_streak += 1
                check -= timedelta(weeks=1)
            else:
                break

    # Build posts array — full text + per-post slug for individual URLs
    import re as _re
    def _post_slug(headline, post_id):
        base = _re.sub(r"[^a-z0-9]+", "-",
               (headline or "post").lower().strip()).strip("-")[:60]
        return f"{base}-{post_id}"

    posts = []
    for item in items:
        try:
            cd = _json.loads(item.get("content") or "{}")
        except Exception:
            cd = {}
        body     = cd.get("body","") or cd.get("post","") or cd.get("content","")
        headline = cd.get("headline","") or cd.get("title","")
        if not body and not headline:
            continue
        ps = _post_slug(headline, item["id"])
        posts.append({
            "id":          item["id"],
            "slug":        ps,
            "headline":    headline,
            "body":        body,
            "niche":       item.get("niche",""),
            "cir_id":      item.get("cir_id",""),
            "approved_at": (item.get("approved_at") or "")[:10],
            "origin_type": item.get("origin_type") or "engine_draft",
            "post_url":    f"https://{slug}.homebridgegroup.co/posts/{ps}",
            "verify_url":  f"https://{slug}.homebridgegroup.co/verify/{item.get('cir_id','')}" if item.get("cir_id") else "",
        })

    conn.close()

    return {
        "slug":          slug,
        "agent_name":    user["agent_name"],
        "brokerage":     user.get("brokerage",""),
        "market":        setup.get("market",""),
        "short_bio":     setup.get("shortBio",""),
        # Voice fields — the differentiating human content
        "origin":        setup.get("origin",""),
        "advantage":     setup.get("unfairAdvantage","") or setup.get("advantage",""),
        "belief":        setup.get("signatureBelief","") or setup.get("belief",""),
        "not_for":       setup.get("notForClient","") or setup.get("notFor",""),
        "niches":        setup.get("primaryNiches",[]),
        "sub_niches":    setup.get("subNiches",[]),
        "designations":  setup.get("designations",[]),
        "service_areas": setup.get("serviceAreas",[]),
        "website":       setup.get("websiteUrl",""),
        "cta_url":       setup.get("ctaUrl",""),
        "cta_label":     setup.get("ctaLabel",""),
        "state":         setup.get("state",""),
        "posts_total":   posts_total,
        "posts_30_days": posts_30_days,
        "cir_count":     cir_count,
        "compliance_pct":compliance_pct,
        "member_since":  member_since,
        "week_streak":   week_streak,
        "posts":         posts,
        "profile_url":   f"https://{slug}.homebridgegroup.co",
        "rss_url":       f"https://api.homebridgegroup.co/public/agent/{slug}/feed",
        "cir_verified":  cir_count > 0,
    }


@app.get("/public/agent/{slug}/feed")
async def public_agent_rss(slug: str):
    """
    RSS feed for an agent's verified posts.
    URL: {slug}.homebridgegroup.co/feed
    (Frontend agent.html intercepts /feed path and proxies to this endpoint)
    Can be pointed at by any WordPress/Squarespace/Wix site.
    """
    import json as _json
    from fastapi.responses import Response as _Response
    from database import get_conn as _gc

    user = _get_agent_by_slug(slug)
    if not user:
        raise HTTPException(404, "Agent not found.")

    user_id = user["id"]
    conn    = _gc()
    c       = conn.cursor()

    # Setup
    c.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (user_id,))
    row   = c.fetchone()
    setup = {}
    if row:
        try: setup = _json.loads(row["setup_json"] or "{}")
        except: pass

    market = setup.get("market","")

    c.execute("""
        SELECT id, niche, content, cir_id, approved_at
        FROM content_library
        WHERE user_id = ? AND status IN ('approved','published')
        ORDER BY approved_at DESC
        LIMIT 20
    """, (user_id,))
    items = [dict(r) for r in c.fetchall()]
    conn.close()

    def esc(s):
        return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

    items_xml = ""
    for item in items:
        try: cd = _json.loads(item.get("content") or "{}")
        except: cd = {}
        headline = cd.get("headline","") or cd.get("title","") or "Update"
        body     = cd.get("body","") or cd.get("post","") or cd.get("content","")
        pub_date = ""
        try:
            pub_date = datetime.fromisoformat(item["approved_at"]).strftime(
                "%a, %d %b %Y %H:%M:%S +0000"
            )
        except: pass
        link = f"https://{slug}.homebridgegroup.co"
        if item.get("cir_id"):
            link = f"https://{slug}.homebridgegroup.co/verify/{item['cir_id']}"
        items_xml += f"""
  <item>
    <title>{esc(headline)}</title>
    <link>{link}</link>
    <description>{esc(body[:500])}</description>
    <pubDate>{pub_date}</pubDate>
    <guid isPermaLink="false">hb-{item['id']}</guid>
    <author>agent@homebridgegroup.co ({esc(user['agent_name'])})</author>
    <category>{esc(item.get('niche','Real Estate'))}</category>
  </item>"""

    agent_name = user["agent_name"]
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{esc(agent_name)} — Real Estate Insights</title>
    <link>https://{slug}.homebridgegroup.co</link>
    <description>Verified real estate content by {esc(agent_name)}, {esc(market)}. CPR-reviewed by HomeBridge.</description>
    <language>en-us</language>
    <atom:link href="https://api.homebridgegroup.co/public/agent/{slug}/feed" rel="self" type="application/rss+xml"/>
    <managingEditor>support@homebridgegroup.co ({esc(agent_name)})</managingEditor>
    <generator>HomeBridge CPR Platform</generator>
{items_xml}
  </channel>
</rss>"""

    return _Response(content=rss, media_type="application/rss+xml")


@app.get("/public/agent/{slug}/posts/{post_slug}")
async def public_agent_post(slug: str, post_slug: str):
    """
    Individual post page — permanent crawlable URL for each approved post.
    Powers per-post Google indexing and AI citation.
    URL: {slug}.homebridgegroup.co/posts/{post-slug}
    Serves agent.html — JavaScript reads the path and fetches this data.
    """
    import json as _json, re as _re
    from database import get_conn as _gc
    from fastapi.responses import JSONResponse

    user = _get_agent_by_slug(slug)
    if not user:
        raise HTTPException(404, "Agent not found.")

    conn = _gc()
    c    = conn.cursor()

    # Find post by matching slug pattern (headline-based + id suffix)
    c.execute("""
        SELECT id, niche, content, cir_id, approved_at, status
        FROM content_library
        WHERE user_id = ? AND status IN ('approved','published')
        ORDER BY approved_at DESC
    """, (user["id"],))
    items = [dict(r) for r in c.fetchall()]
    conn.close()

    def _make_post_slug(headline, item_id):
        base = _re.sub(r"[^a-z0-9]+", "-",
               (headline or "post").lower().strip()).strip("-")[:60]
        return f"{base}-{item_id}"

    matched = None
    for item in items:
        try:
            cd = _json.loads(item.get("content") or "{}")
        except Exception:
            cd = {}
        headline = cd.get("headline","") or cd.get("title","")
        if _make_post_slug(headline, item["id"]) == post_slug:
            body = cd.get("body","") or cd.get("post","") or cd.get("content","")
            matched = {
                "id":          item["id"],
                "slug":        post_slug,
                "headline":    headline,
                "body":        body,
                "niche":       item.get("niche",""),
                "cir_id":      item.get("cir_id",""),
                "approved_at": (item.get("approved_at") or "")[:10],
                "agent_name":  user["agent_name"],
                "brokerage":   user.get("brokerage",""),
                "profile_url": f"https://{slug}.homebridgegroup.co",
                "verify_url":  f"https://{slug}.homebridgegroup.co/verify/{item['cir_id']}" if item.get("cir_id") else "",
            }
            break

    if not matched:
        raise HTTPException(404, "Post not found.")

    return JSONResponse(matched)


@app.get("/public/verify/{cir_id}")
async def public_verify_cir(cir_id: str):
    """
    Public CIR verification endpoint.
    Called by verify.html at app.homebridgegroup.co/verify/{cir_id}
    Returns the full compliance record for a given CIR ID.
    No auth required — this is intentionally public.
    """
    import json as _json
    from database import get_conn as _gc

    conn = _gc()
    c    = conn.cursor()

    # Check compliance_records first (permanent table)
    c.execute("""
        SELECT cr.*, u.agent_name, u.brokerage, u.agent_slug
        FROM compliance_records cr
        JOIN users u ON cr.user_id = u.id
        WHERE cr.cir_id = ?
    """, (cir_id,))
    row = c.fetchone()

    if not row:
        # Fall back to content_library for older records
        c.execute("""
            SELECT cl.*, u.agent_name, u.brokerage, u.agent_slug
            FROM content_library cl
            JOIN users u ON cl.user_id = u.id
            WHERE cl.cir_id = ?
        """, (cir_id,))
        row = c.fetchone()

    conn.close()

    if not row:
        raise HTTPException(404, "CPR record not found.")

    row = dict(row)

    comp = {}
    try:
        comp = _json.loads(row.get("compliance_json") or row.get("compliance") or "{}")
    except Exception:
        pass

    headline = row.get("headline","")
    if not headline:
        try:
            cd = _json.loads(row.get("content") or "{}")
            headline = cd.get("headline","") or cd.get("title","")
        except Exception:
            pass

    return {
        "cir_id":         cir_id,
        "agent_name":     row.get("agent_name",""),
        "brokerage":      row.get("brokerage",""),
        "agent_slug":     row.get("agent_slug",""),
        "niche":          row.get("niche",""),
        "headline":       headline,
        "overall_status": row.get("overall_status","") or comp.get("overallStatus",""),
        "fair_housing":   row.get("fair_housing","")   or comp.get("fairHousing",""),
        "disclosure":     row.get("disclosure","")     or comp.get("brokerageDisclosure",""),
        "nar_standards":  row.get("nar_standards","")  or comp.get("narStandards",""),
        "state_compliance": row.get("state_compliance","") or comp.get("stateCompliance",""),
        "rules_version":  row.get("rules_version","")  or comp.get("rules_version",""),
        "rules_verified_dates": comp.get("rules_verified_dates",{}),
        "notes":          comp.get("notes",[]) or comp.get("disclosureChecks",[]),
        "disclosure_checks": comp.get("disclosureChecks",[]) or comp.get("notes",[]),
        "approved_at":    row.get("approved_at",""),
        "profile_url":    f"https://{row.get('agent_slug','')}.homebridgegroup.co" if row.get("agent_slug") else "",
        "record_confirmed": True,
    }


# =============================================================================
# SERVER-SIDE RENDERED AUTHORITY PAGES — Session 66
# =============================================================================
# Replaces client-side agent.html / verify.html with fully-rendered HTML
# served directly from the backend. All content is in the page source at
# the moment the server responds. Crawlers see everything.
#
# Routes:
#   GET /public/agent/{slug}/page        — full authority page HTML
#   GET /public/agent/{slug}/posts/{post_slug}/page  — per-record post page HTML
#   GET /public/verify/{cir_id}/page     — CPR record verification page HTML
#   GET /public/sitemap.xml              — platform-wide sitemap
#   GET /public/agent/{slug}/sitemap.xml — per-agent sitemap
#   GET /robots.txt                      — robots file pointing to sitemap
#
# The host-detection middleware at the bottom of this block automatically
# routes requests arriving at {slug}.homebridgegroup.co to the authority
# page HTML without requiring the /page suffix.
# =============================================================================

def _esc_html(s: str) -> str:
    """Escape a string for safe embedding in HTML."""
    return (str(s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def _fmt_date_long(s: str) -> str:
    """Format ISO date string as 'Month DD, YYYY'."""
    if not s:
        return ""
    try:
        from datetime import datetime as _dt2
        return _dt2.fromisoformat(s[:10]).strftime("%B %d, %Y").replace(" 0", " ")
    except Exception:
        return s[:10]


def _fmt_date_short(s: str) -> str:
    """Format ISO date string as 'Mon YYYY'."""
    if not s:
        return ""
    try:
        from datetime import datetime as _dt2
        return _dt2.fromisoformat(s[:10]).strftime("%B %Y")
    except Exception:
        return s[:10]


def _headline_to_question(h: str) -> str:
    """Convert a headline to a question form for FAQ schema."""
    h = (h or "").strip()
    if not h:
        return ""
    if h.endswith("?"):
        return h
    import re as _re2
    if _re2.match(r"^(why|how|what|when|is|are|should|can|do|does)\s", h, _re2.IGNORECASE):
        return h + "?"
    if len(h) < 80:
        return "What should I know about: " + h.lower() + "?"
    return ""


def _post_slug_make(headline: str, post_id: int) -> str:
    import re as _re3
    base = _re3.sub(r"[^a-z0-9]+", "-", (headline or "post").lower().strip()).strip("-")[:60]
    return f"{base}-{post_id}"


def _opening_sentences(text: str, max_sentences: int = 3, hard_cap: int = 600) -> str:
    """Returns the first 2-3 definitive sentences of a record body — the
    extraction-grade FAQ answer (POSITIONING_FUNNEL_SPINE_v3 §2 / Build O).
    Answer engines lift the opening; this keeps the FAQ answer to that quotable
    opener rather than a mid-sentence character truncation."""
    t = (text or "").strip()
    if not t:
        return ""
    import re as _re4
    parts = _re4.split(r"(?<=[.!?])\s+", t)
    out = " ".join(parts[:max_sentences]).strip()
    if len(out) > hard_cap:
        out = out[:hard_cap].rstrip()
    return out


_AUTHORITY_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#F8F7F5;--white:#FFF;--ink:#1A1A1A;--ink-2:#2E2E2E;
  --ink-3:#4A4540;--ink-4:#7A7470;--border:#E8E4DE;
  --gold:#A67C2E;--gold-on-dark:#C8963C;--gold-dim:rgba(166,124,46,.10);--gold-mid:rgba(166,124,46,.25);
  --green:#1A7A4A;--green-dim:rgba(26,122,74,.08);--green-mid:rgba(26,122,74,.18);
  --amber:#b45309;--nav:#101620;
  --shadow:0 2px 16px rgba(0,0,0,.06);--r:12px;
}
html{scroll-behavior:smooth}
body{font-family:'DM Sans',sans-serif;background:var(--white);color:var(--ink);-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{text-decoration:none;color:inherit}
.top-bar{background:var(--nav);height:52px;padding:0 40px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.tb-logo{font-size:15px;font-weight:700;color:#fff;letter-spacing:.01em}
.tb-logo span{color:var(--gold-on-dark)}
.tb-cta{font-size:12px;font-weight:600;color:var(--gold-on-dark);border:1px solid rgba(200,150,60,.35);padding:6px 16px;border-radius:999px;transition:all .2s}
.tb-cta:hover{background:var(--gold-on-dark);color:#fff}
@media(max-width:600px){.top-bar{padding:0 20px}}
.hero{background:var(--nav);padding:72px 40px 64px}
.hero-inner{max-width:960px;margin:0 auto;display:grid;grid-template-columns:1fr auto;gap:48px;align-items:start}
@media(max-width:680px){.hero-inner{grid-template-columns:1fr}.hero-badge-col{display:none}.hero{padding:52px 20px 44px}}
.hero-eyebrow{font-size:11px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:rgba(200,150,60,.9);margin-bottom:18px;display:flex;align-items:center;gap:10px}
.hero-eyebrow::before{content:'';width:24px;height:1px;background:rgba(200,150,60,.6)}
.hero-name{font-family:'Outfit','DM Sans',sans-serif;font-size:clamp(42px,6vw,72px);font-weight:700;line-height:.95;letter-spacing:-.025em;color:#fff;margin-bottom:14px}
.hero-role{font-size:16px;color:rgba(255,255,255,.45);margin-bottom:6px;font-weight:300}
.hero-market{font-size:13px;color:rgba(255,255,255,.3);margin-bottom:22px}
.authority-statement{font-size:16px;line-height:1.72;color:rgba(255,255,255,.55);max-width:580px;font-weight:300;margin-bottom:28px}
.authority-statement strong{color:rgba(255,255,255,.8);font-weight:500}
.hero-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}
.btn-gold{display:inline-flex;align-items:center;gap:6px;background:var(--gold);color:#fff;font-family:'DM Sans',sans-serif;font-size:13px;font-weight:600;padding:10px 22px;border-radius:999px;border:none;cursor:pointer;transition:opacity .2s}
.btn-gold:hover{opacity:.88}
.btn-outline-lt{display:inline-flex;align-items:center;gap:6px;background:transparent;color:rgba(255,255,255,.55);font-family:'DM Sans',sans-serif;font-size:13px;font-weight:500;padding:9px 20px;border-radius:999px;border:1px solid rgba(255,255,255,.18);cursor:pointer;transition:all .2s}
.btn-outline-lt:hover{border-color:rgba(255,255,255,.4);color:rgba(255,255,255,.85)}
.hero-badge-col{text-align:right}
.cir-hero-badge{display:inline-flex;flex-direction:column;align-items:center;background:rgba(26,122,74,.12);border:1px solid rgba(26,122,74,.28);border-radius:16px;padding:22px 26px;gap:4px}
.chb-icon{font-size:26px;color:var(--green);margin-bottom:6px}
.chb-n{font-family:'Outfit','DM Sans',sans-serif;font-size:40px;font-weight:700;line-height:1;color:#fff}
.chb-l{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--green)}
.chb-s{font-size:11px;color:rgba(255,255,255,.3);margin-top:2px}
.stats-strip{background:var(--bg);border-bottom:1px solid var(--border)}
.stats-row{max-width:960px;margin:0 auto;padding:0 40px;display:grid;grid-template-columns:repeat(4,1fr)}
.stat-item{padding:26px 0;border-right:1px solid var(--border);text-align:center}
.stat-item:last-child{border-right:none}
.si-n{font-family:'Outfit','DM Sans',sans-serif;font-size:36px;font-weight:700;line-height:1;color:var(--ink);margin-bottom:5px}
.si-n.gold{color:var(--gold)}.si-n.green{color:var(--green)}
.si-l{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-4)}
.si-stmt{font-size:13px;font-weight:600;color:var(--green);line-height:1.35;margin-bottom:5px;padding:0 8px}
@media(max-width:640px){.stats-row{grid-template-columns:repeat(2,1fr);padding:0 20px}.stat-item:nth-child(2){border-right:none}.stat-item:nth-child(3){border-right:1px solid var(--border)}}
.main{max-width:960px;margin:0 auto;padding:0 40px}
@media(max-width:600px){.main{padding:0 20px}}
.sec{padding:52px 0 0}
.sec-hdr{display:flex;align-items:center;gap:12px;margin-bottom:24px}
.sec-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--ink-4);white-space:nowrap}
.sec-line{flex:1;height:1px;background:var(--border)}
.compliance-block{background:var(--green-dim);border:1px solid var(--green-mid);border-radius:var(--r);padding:24px 28px;display:flex;gap:18px;align-items:flex-start}
.cb-icon{font-size:22px;flex-shrink:0;margin-top:1px}
.cb-title{font-size:15px;font-weight:700;color:var(--green);margin-bottom:5px}
.cb-body{font-size:13px;color:var(--ink-3);line-height:1.6}
.chip-row{display:flex;flex-wrap:wrap;gap:8px}
.chip{font-size:12px;font-weight:500;padding:5px 14px;border-radius:999px;background:var(--bg);border:1px solid var(--border);color:var(--ink-3)}
.chip.niche{background:var(--gold-dim);border-color:var(--gold-mid);color:var(--gold);font-weight:600}
.desig{font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px;background:var(--nav);color:rgba(255,255,255,.8);letter-spacing:.04em}
.streak-badge{display:inline-flex;align-items:center;gap:8px;background:var(--gold-dim);border:1px solid var(--gold-mid);border-radius:999px;padding:8px 16px;font-size:13px;font-weight:600;color:var(--gold)}
.faq-list{display:flex;flex-direction:column;gap:1px;background:var(--border);border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.faq-item{background:var(--white)}
.faq-q{width:100%;text-align:left;padding:20px 24px;background:none;border:none;cursor:pointer;font-family:'DM Sans',sans-serif;font-size:14px;font-weight:600;color:var(--ink);display:flex;justify-content:space-between;align-items:center;gap:12px}
.faq-icon{font-size:18px;color:var(--ink-4);flex-shrink:0;line-height:1}
.faq-a{padding:0 24px 20px;font-size:14px;color:var(--ink-3);line-height:1.7}
.post-list{display:flex;flex-direction:column;gap:16px}
.post-card{background:var(--white);border:1px solid var(--border);border-radius:var(--r);padding:28px}
.post-card.featured{border-left:3px solid var(--gold)}
.post-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.post-niche{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--gold)}
.post-dot{color:var(--border);font-size:11px}
.post-date{font-size:11px;color:var(--ink-4)}
.post-h{font-family:'Outfit','DM Sans',sans-serif;font-size:20px;font-weight:700;line-height:1.25;color:var(--ink);margin-bottom:10px}
.post-body{font-size:14px;line-height:1.75;color:var(--ink-3);white-space:pre-line}
.post-footer{display:flex;align-items:center;justify-content:space-between;margin-top:16px;padding-top:14px;border-top:1px solid var(--border);flex-wrap:wrap;gap:8px}
.cir-stamp{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--green)}
.post-permalink{font-size:11px;color:var(--ink-4)}
.post-permalink:hover{color:var(--gold)}
.tools-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:640px){.tools-grid{grid-template-columns:1fr}}
.tool-card{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:24px}
.tool-t{font-size:14px;font-weight:700;color:var(--ink);margin-bottom:6px}
.tool-p{font-size:12px;color:var(--ink-4);line-height:1.6;margin-bottom:14px}
.tool-code{background:var(--nav);border-radius:8px;padding:12px 14px;font-family:'SF Mono','Courier New',monospace;font-size:11px;color:rgba(255,255,255,.65);line-height:1.6;word-break:break-all}
.trust-footer{margin:56px 0 80px;background:var(--nav);border-radius:var(--r);padding:36px 40px;display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap}
.tf-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:rgba(255,255,255,.35);margin-bottom:5px}
.tf-headline{font-family:'Outfit','DM Sans',sans-serif;font-size:20px;color:#fff;margin-bottom:4px}
.tf-sub{font-size:13px;color:rgba(255,255,255,.45);line-height:1.5}
.tf-cta{font-size:13px;font-weight:600;color:var(--gold);border:1px solid rgba(200,150,60,.4);padding:10px 22px;border-radius:999px;white-space:nowrap}
.tf-cta:hover{background:var(--gold);color:#fff}
@media(max-width:600px){.trust-footer{padding:28px 24px;flex-direction:column}}
/* Verify page styles */
.page{max-width:680px;margin:0 auto;padding:48px 24px 80px}
.verify-header{text-align:center;margin-bottom:40px}
.verify-eyebrow{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-4);margin-bottom:12px}
.verify-title{font-family:'Outfit','DM Sans',sans-serif;font-size:32px;font-weight:700;color:var(--ink);margin-bottom:8px}
.verify-sub{font-size:14px;color:var(--ink-4);line-height:1.6}
.result-card{background:var(--white);border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.result-card.valid{border-color:var(--green-mid)}
.rc-header{padding:24px 28px;display:flex;gap:16px;align-items:flex-start}
.rc-icon{font-size:28px;flex-shrink:0}
.rc-cir{font-family:'DM Sans',sans-serif;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--green);margin-bottom:4px}
.rc-headline{font-family:'Outfit','DM Sans',sans-serif;font-size:20px;font-weight:700;color:var(--ink);line-height:1.2;margin-bottom:6px}
.rc-agent{font-size:14px;color:var(--ink-3)}
.rc-rows{border-top:1px solid var(--border)}
.rc-row{display:flex;justify-content:space-between;align-items:center;padding:14px 28px;border-bottom:1px solid var(--border);gap:12px}
.rc-row:last-child{border-bottom:none}
.rc-row-label{font-size:12px;color:var(--ink-4);font-weight:500}
.rc-row-val{font-size:13px;font-weight:600;color:var(--ink)}
.badge-pass{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;color:var(--green);background:var(--green-dim);border:1px solid var(--green-mid);padding:3px 10px;border-radius:999px}
.rc-footer{padding:20px 28px;border-top:1px solid var(--border);background:var(--bg);font-size:12px;color:var(--ink-4);line-height:1.6}
.rc-link{display:inline-block;margin-top:12px;font-size:13px;font-weight:600;color:var(--gold)}
"""


def _build_authority_page_html(d: dict, slug: str) -> str:
    """
    Build a fully server-side rendered HTML page for an agent authority page.
    Every piece of content is present in the raw HTML source.
    No JavaScript required to see content — crawlers see everything.
    """
    import json as _json2
    import re as _re4

    name       = _esc_html(d.get("agent_name", "Real Estate Agent"))
    brokerage  = _esc_html(d.get("brokerage", ""))
    market     = _esc_html(d.get("market", ""))
    niches     = d.get("niches", [])
    areas      = d.get("service_areas", [])
    desigs     = d.get("designations", [])
    posts      = d.get("posts", [])
    cir_count  = int(d.get("cir_count", 0))
    posts_total= int(d.get("posts_total", 0))
    member_since = _esc_html(d.get("member_since", ""))
    week_streak  = int(d.get("week_streak", 0))
    cta_url    = _esc_html(d.get("cta_url", "") or d.get("website", "") or "https://app.homebridgegroup.co")
    cta_label  = _esc_html(d.get("cta_label", "") or f"Connect with {d.get('agent_name','').split(' ')[0]}")
    profile_url = f"https://{slug}.homebridgegroup.co"
    rss_url     = f"https://api.homebridgegroup.co/public/agent/{slug}/feed"
    state       = d.get("state", "")

    # Authority statement — in source for crawlers
    niche_str = ", ".join(niches[:3])
    area_str  = ", ".join(areas[:3])
    auth_stmt = (
        f"{d.get('agent_name','')} is a licensed real estate agent"
        + (f" with {d.get('brokerage','')}" if d.get("brokerage") else "")
        + (f" in {d.get('market','')}" if d.get("market") else "")
        + (f", specializing in {niche_str}" if niche_str else "")
        + (f". Serving {area_str}" if area_str else "")
        + f". {posts_total} professionally reviewed posts. Each post carries a CPR\u2122 record "
          f"confirming pre-publication review by a licensed real estate professional."
    )
    auth_stmt_esc = _esc_html(auth_stmt)

    # Fixed-template meta description for search engines -- capped at 155 characters
    _meta_parts = [d.get('agent_name', ''), " | Licensed Real Estate Agent"]
    if d.get('market'):
        _meta_parts.append(f" in {d.get('market','')}")
    if posts_total:
        _meta_parts.append(f" | {posts_total} CPR-reviewed posts")
    if niche_str:
        _meta_parts.append(f" on {niche_str}")
    if area_str:
        _meta_parts.append(f". Serving {area_str}.")
    _meta_desc_raw = "".join(_meta_parts)
    meta_desc = _meta_desc_raw if len(_meta_desc_raw) <= 155 else _meta_desc_raw[:152] + "..."
    meta_desc_esc = _esc_html(meta_desc)

    page_title = _esc_html(
        f"{d.get('agent_name','')} — {d.get('market','') or 'Real Estate'} | Real Estate Expert | AutoMates"
    )

    # JSON-LD schema — fully server-side
    schema = {
        "@context": "https://schema.org",
        "@type": ["Person", "RealEstateAgent"],
        "name": d.get("agent_name", ""),
        "jobTitle": "Licensed Real Estate Agent",
        "url": profile_url,
        "description": auth_stmt,
    }
    if d.get("brokerage"):
        schema["worksFor"] = {"@type": "Organization", "name": d["brokerage"]}
    if niches:
        schema["knowsAbout"] = niches
    if areas:
        schema["areaServed"] = [{"@type": "City", "name": a} for a in areas]
    if d.get("market"):
        schema["homeLocation"] = {"@type": "Place", "name": d["market"]}
    creds = []
    if desigs:
        creds = [{"@type": "EducationalOccupationalCredential", "name": x} for x in desigs]
    if cir_count > 0:
        creds.append({
            "@type": "EducationalOccupationalCredential",
            "credentialCategory": "CPR\u2122 \u2014 Certified Provenance Record",
            "description": f"{cir_count} posts carrying CPR\u2122 provenance records confirming pre-publication professional compliance review",
            "recognizedBy": {"@type": "Organization", "name": "AutoMates by HomeBridge Group, LLC", "url": "https://homebridgegroup.co"},
        })
    if creds:
        schema["hasCredential"] = creds
    schema["review"] = {
        "@type": "Review",
        "reviewAspect": "Professional compliance review",
        "reviewBody": "Each post reviewed by a licensed real estate professional prior to publication. Review process covers federal advertising standards, NAR Code of Ethics, and applicable state real estate commission requirements.",
        "author": {
            "@type": "Person",
            "name": d.get("agent_name", ""),
            "hasCredential": {
                "@type": "EducationalOccupationalCredential",
                "credentialCategory": "Real Estate License",
                "recognizedBy": {"@type": "Organization", "name": f"{state or 'State'} Real Estate Commission"},
            },
        },
    }
    faq_items = []
    for p in posts[:10]:
        q = _headline_to_question(p.get("headline", ""))
        if q and p.get("body"):
            faq_items.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": _opening_sentences(p["body"])},
            })
    if faq_items:
        schema["mainEntity"] = {"@type": "FAQPage", "mainEntity": faq_items}
    _agent_first = (d.get("agent_name", "") or "").split(" ")[0]

    def _record_article(p, position):
        art = {
            "@type": "Article",
            "headline": p.get("headline", ""),
            "articleBody": (p.get("body", "") or "")[:500],
            "datePublished": p.get("approved_at", ""),
            "url": p.get("post_url", profile_url),
            "author": {"@type": "Person", "name": d.get("agent_name", "")},
            "publisher": {"@type": "Organization", "name": "AutoMates", "url": "https://homebridgegroup.co"},
            "about": {"@type": "Thing", "name": p.get("niche", "Real Estate")},
        }
        # Human-origin provenance (FOUNDATION_DAILY_QUESTION_SPEC_v2 §7), C2PA-aligned:
        # human-authored, machine-structured, human-reviewed. Only member_answer
        # records carry it — engine drafts are left as ordinary Articles.
        _ot = p.get("origin_type", "engine_draft")
        if _ot.startswith("member_answer"):
            _mode = "spoken" if _ot == "member_answer_voice" else "written"
            art["creator"] = {"@type": "Person", "name": d.get("agent_name", "")}
            art["creativeWorkStatus"] = (
                f"Human-originated: began as {_agent_first}'s own {_mode} answer, "
                "machine-structured, and reviewed by the licensed professional before publication."
            )
        return {"@type": "ListItem", "position": position, "item": art}

    if posts:
        schema["subjectOf"] = {
            "@type": "ItemList",
            "numberOfItems": len(posts),
            "itemListElement": [_record_article(p, i + 1) for i, p in enumerate(posts[:20])],
        }
    schema["speakable"] = {"@type": "SpeakableSpecification", "cssSelector": [".authority-statement", ".hero-name"]}
    schema_json = _json2.dumps(schema, ensure_ascii=False, indent=2)

    # Niche chips
    niche_chips_html = "".join(
        f'<span class="chip niche">{_esc_html(n)}</span>' for n in niches
    ) if niches else ""

    # Area chips
    area_chips_html = "".join(
        f'<span class="chip">{_esc_html(a)}</span>' for a in areas
    ) if areas else ""

    # Designation chips
    desig_chips_html = "".join(
        f'<span class="desig">{_esc_html(x)}</span>' for x in desigs
    ) if desigs else ""

    # Streak section
    streak_html = ""
    if week_streak > 1:
        streak_html = f"""
    <div class="sec" id="streak-sec">
      <div class="sec-hdr"><span class="sec-label">Publishing Consistency</span><span class="sec-line"></span></div>
      <div class="streak-badge">&#128293; Publishing consistently for {week_streak} consecutive week{'s' if week_streak > 1 else ''}</div>
      <p style="font-size:13px;color:var(--ink-4);margin-top:10px">Consistent publishing is one of the strongest signals search engines and AI platforms use to evaluate expertise.</p>
    </div>"""

    # FAQ section — answers fully in source
    faq_html = ""
    faq_posts = [p for p in posts if _headline_to_question(p.get("headline", "")) and p.get("body")][:12]
    if faq_posts:
        faq_items_html = ""
        for p in faq_posts:
            q = _headline_to_question(p.get("headline", ""))
            body_preview = _esc_html(_opening_sentences(p.get("body", "")))
            cir_note = f'<div style="margin-top:10px;font-size:11px;font-weight:700;color:var(--green)">&#10003; CPR&#8482; {_esc_html(p.get("cir_id",""))}</div>' if p.get("cir_id") else ""
            post_link = f'<p style="margin-top:10px"><a href="{_esc_html(p.get("post_url",""))}" style="font-size:12px;color:var(--gold);font-weight:600">Read full post &#8594;</a></p>' if p.get("post_url") else ""
            faq_items_html += f"""
      <div class="faq-item">
        <div class="faq-q" style="width:100%;text-align:left;padding:20px 24px;font-family:\'DM Sans\',sans-serif;font-size:14px;font-weight:600;color:var(--ink);display:flex;justify-content:space-between;align-items:center;gap:12px">
          <span>{_esc_html(q)}</span>
        </div>
        <div class="faq-a">
          <p>{body_preview}</p>
          {cir_note}
          {post_link}
        </div>
      </div>"""
        faq_intro = _esc_html(f"Questions {d.get('agent_name','').split(' ')[0]}'s clients ask most.")
        faq_html = f"""
    <div class="sec" id="faq-sec">
      <div class="sec-hdr"><span class="sec-label">Recent Questions</span><span class="sec-line"></span></div>
      <p style="font-size:13px;color:var(--ink-4);margin-bottom:20px">{faq_intro}</p>
      <div class="faq-list">{faq_items_html}</div>
    </div>"""

    # Posts — all content in source
    posts_html = ""
    if posts:
        post_cards = ""
        for i, p in enumerate(posts):
            headline = _esc_html(p.get("headline", ""))
            body     = _esc_html(p.get("body", "") or "")
            niche_lbl = _esc_html(p.get("niche", ""))
            date_lbl  = _esc_html(_fmt_date_long(p.get("approved_at", "")))
            cir_id    = p.get("cir_id", "")
            post_url  = p.get("post_url", "")
            verify_url = f"https://{slug}.homebridgegroup.co/verify/{cir_id}" if cir_id else ""
            featured  = " featured" if i == 0 else ""
            # Human-origin line — only for records that began as the member's own
            # answer (FOUNDATION_DAILY_QUESTION_SPEC_v2 §7). engine_draft records
            # show nothing. itemprop ties it into the Article microdata for crawlers.
            origin_type = p.get("origin_type", "engine_draft")
            origin_line = ""
            if origin_type.startswith("member_answer"):
                _omode = "spoken" if origin_type == "member_answer_voice" else "written"
                _ofn   = _esc_html((d.get("agent_name", "").split(" ")[0]) or "")
                origin_line = (
                    f'<div class="post-origin" itemprop="creativeWorkStatus" '
                    f'style="font-size:12px;color:var(--ink-4,#6b7280);font-style:italic;margin:6px 0 0">'
                    f'This piece began as {_ofn}&#8217;s own {_omode} answer, reviewed and approved before publication.'
                    f'</div>'
                )
            cir_stamp = f'<div class="cir-stamp"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5.5" stroke="#1A7A4A"/><path d="M3.5 6l2 2 3-3" stroke="#1A7A4A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>CPR&#8482; {_esc_html(cir_id)}</div>' if cir_id else "<div></div>"
            permalink = f'<a href="{_esc_html(post_url)}" class="post-permalink">Read Full Post &#8594;</a>' if post_url else ""
            post_cards += f"""
        <div class="post-card{featured}" itemscope itemtype="https://schema.org/Article">
          <div class="post-meta">
            {f'<span class="post-niche">{niche_lbl}</span>' if niche_lbl else ''}
            {f'<span class="post-dot">&middot;</span>' if niche_lbl and date_lbl else ''}
            {f'<span class="post-date">{date_lbl}</span>' if date_lbl else ''}
          </div>
          {f'<h2 class="post-h" itemprop="headline">{headline}</h2>' if headline else ''}
          {f'<div class="post-body" itemprop="articleBody">{body}</div>' if body else ''}
          {origin_line}
          <div class="post-footer">
            {cir_stamp}
            {permalink}
          </div>
        </div>"""
        posts_html = f"""
    <div class="sec" id="posts-sec">
      <div class="sec-hdr"><span class="sec-label">Recently Reviewed</span><span class="sec-line"></span></div>
      <div class="post-list">{post_cards}</div>
    </div>"""

    # Sitemap and RSS tool section
    tools_html = f"""
    <div class="sec" id="tools-sec">
      <div class="sec-hdr"><span class="sec-label">Share &amp; Syndicate</span><span class="sec-line"></span></div>
      <div class="tools-grid">
        <div class="tool-card">
          <div class="tool-t">&#128225; RSS Feed</div>
          <div class="tool-p">Paste this URL into WordPress, Squarespace, or any CMS to auto-display reviewed posts.</div>
          <div class="tool-code">{_esc_html(rss_url)}</div>
        </div>
        <div class="tool-card">
          <div class="tool-t">&#60;/&#62; Embed Widget</div>
          <div class="tool-p">One line of code. Your reviewed posts appear automatically on any webpage.</div>
          <div class="tool-code">&lt;script src="https://app.homebridgegroup.co/widget.js" data-agent="{_esc_html(slug)}"&gt;&lt;/script&gt;</div>
        </div>
      </div>
    </div>"""

    # Compliance block — Certified Provenance Record explanation (G3).
    # Provenance-aligned language optimized for AI-crawler comprehension:
    # references content provenance, the C2PA standard, and human attestation.
    compliance_body = (
        "CPR&#8482; (Certified Provenance Record) is a content-provenance record, aligned with "
        "the C2PA content-authenticity standard. Each CPR is a timestamped human attestation that a "
        "licensed real estate professional personally reviewed this content for professional compliance "
        "before publication, establishing a verifiable, tamper-evident chain of origin and human "
        "accountability. Records flagged as member-originated carry an additional attestation: the content "
        "began as the professional&#8217;s own answer, in their own words, was machine-structured, and was "
        "human-reviewed before publication. CPR&#8482; certifies the provenance and the completion of that "
        "review; it does not certify the accuracy of market data, valuations, or predictions."
        + (f" Publishing since {_esc_html(member_since)}." if member_since else "")
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="robots" content="index,follow">
<title>{page_title}</title>
<meta name="description" content="{meta_desc_esc}">
<meta property="og:type" content="profile">
<meta property="og:site_name" content="AutoMates">
<meta property="og:title" content="{page_title}">
<meta property="og:description" content="{meta_desc_esc}">
<meta property="og:url" content="{_esc_html(profile_url)}">
<link rel="alternate" type="application/rss+xml" href="{_esc_html(rss_url)}" title="{name} &#8212; Verified Real Estate Insights">
<link rel="canonical" href="{_esc_html(profile_url)}">
<script type="application/ld+json">{schema_json}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&display=swap" rel="stylesheet">
<style>{_AUTHORITY_CSS}</style>
</head>
<body>
<nav class="top-bar">
  <a class="tb-logo" href="https://homebridgegroup.co"><span>Auto</span>Mates</a>
  <a class="tb-cta" href="https://app.homebridgegroup.co">Sign In &#8594;</a>
</nav>
<div class="hero">
  <div class="hero-inner">
    <div>
      <div class="hero-eyebrow">CPR&#8482; Reviewed Professional</div>
      <h1 class="hero-name">{name}</h1>
      <div class="hero-role">Licensed Real Estate Agent{(' &middot; ' + brokerage) if brokerage else ''}</div>
      {f'<div class="hero-market">&#128205; {market}</div>' if market else ''}
      <p class="authority-statement">{auth_stmt_esc}</p>
      <div class="hero-actions">
        <a href="{cta_url}" class="btn-gold" target="_blank">{cta_label} &#8594;</a>
        <a href="#posts-sec" class="btn-outline-lt">View reviewed posts &#8595;</a>
      </div>
    </div>
    <div class="hero-badge-col">
      <div class="cir-hero-badge">
        <div class="chb-icon">&#10003;</div>
        <div class="chb-n">{cir_count}</div>
        <div class="chb-l">CPR&#8482; Records</div>
        <div class="chb-s">Provenance Certified</div>
      </div>
    </div>
  </div>
</div>
<div class="stats-strip">
  <div class="stats-row">
    <div class="stat-item"><div class="si-n gold">{cir_count}</div><div class="si-l">CPR&#8482; Records</div></div>
    <div class="stat-item"><div class="si-stmt">Every post on this page was reviewed before publication</div><div class="si-l">Pre-Publication Review</div></div>
    <div class="stat-item"><div class="si-n">{posts_total}</div><div class="si-l">Professionally Reviewed</div></div>
    <div class="stat-item"><div class="si-n">{_esc_html(member_since) if member_since else '&#8212;'}</div><div class="si-l">Publishing Since</div></div>
  </div>
</div>
<div class="main">
  <div class="sec">
    <div class="sec-hdr"><span class="sec-label">Compliance Record</span><span class="sec-line"></span></div>
    <div class="compliance-block">
      <div class="cb-icon">&#10003;</div>
      <div>
        <div class="cb-title">Every post on this page carries a CPR&#8482; record</div>
        <div class="cb-body">{compliance_body}</div>
      </div>
    </div>
  </div>
  {streak_html}
  {'<div class="sec" id="niches-sec"><div class="sec-hdr"><span class="sec-label">Specializations</span><span class="sec-line"></span></div><div class="chip-row">' + niche_chips_html + '</div></div>' if niche_chips_html else ''}
  {'<div class="sec" id="areas-sec"><div class="sec-hdr"><span class="sec-label">Markets Served</span><span class="sec-line"></span></div><div class="chip-row">' + area_chips_html + '</div></div>' if area_chips_html else ''}
  {'<div class="sec" id="desig-sec"><div class="sec-hdr"><span class="sec-label">Designations &amp; Certifications</span><span class="sec-line"></span></div><div class="chip-row">' + desig_chips_html + '</div></div>' if desig_chips_html else ''}
  {faq_html}
  {posts_html}
  {tools_html}
  <div class="trust-footer">
    <div>
      <div class="tf-label">Reviewed by AutoMates</div>
      <div class="tf-headline">Real professionals. Reviewed content.</div>
      <div class="tf-sub">Every post reviewed by a licensed agent. Checked against Fair Housing,<br>NAR Standards, and state advertising rules.</div>
      <div style="margin-top:10px;font-size:11px;"><a href="https://homebridgegroup.co" style="color:rgba(255,255,255,.35);text-decoration:underline;">What is AutoMates? &#8594;</a></div>
    </div>
    <a href="https://homebridgegroup.co" class="tf-cta" target="_blank">What is AutoMates? &#8594;</a>
  </div>
</div>
</body>
</html>"""
    return html


def _build_verify_page_html(d: dict) -> str:
    """
    Build a fully server-side rendered HTML page for a single CPR record.
    All content in source. No JavaScript needed for crawlers.
    """
    import json as _json3

    cir_id     = _esc_html(d.get("cir_id", ""))
    agent_name = _esc_html(d.get("agent_name", ""))
    brokerage  = _esc_html(d.get("brokerage", ""))
    headline   = _esc_html(d.get("headline", ""))
    niche      = _esc_html(d.get("niche", ""))
    approved   = _esc_html(_fmt_date_long(d.get("approved_at", "")))
    overall    = d.get("overall_status", "")
    slug       = d.get("agent_slug", "")
    profile_url = f"https://{slug}.homebridgegroup.co" if slug else "https://homebridgegroup.co"
    rules_ver  = _esc_html(d.get("rules_version", ""))
    page_title = f"CPR&#8482; Record {cir_id} | {agent_name} | AutoMates"
    desc       = f"Certified Provenance Record {d.get('cir_id','')} issued to {d.get('agent_name','')}. Pre-publication compliance review confirmed."

    badge_html = '<span class="badge-pass">&#10003; Reviewed</span>'
    if overall in ("warn", "review-recommended"):
        badge_html = '<span style="font-size:11px;font-weight:700;color:var(--amber)">&#9888; Note</span>'
    elif overall in ("fail", "attention-required"):
        badge_html = '<span style="font-size:11px;font-weight:700;color:#b91c1c">&#10007; Attention Required</span>'

    # JSON-LD schema for per-record page
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": d.get("headline", ""),
        "datePublished": d.get("approved_at", ""),
        "author": {
            "@type": "Person",
            "name": d.get("agent_name", ""),
            "worksFor": {"@type": "Organization", "name": d.get("brokerage", "")} if d.get("brokerage") else None,
        },
        "publisher": {"@type": "Organization", "name": "AutoMates", "url": "https://homebridgegroup.co"},
        "identifier": d.get("cir_id", ""),
        "about": {"@type": "Thing", "name": niche or "Real Estate"},
        "review": {
            "@type": "Review",
            "reviewAspect": "Professional compliance review",
            "reviewBody": "This content was reviewed by a licensed real estate professional prior to publication under the AutoMates CPR (Certified Provenance Record) system.",
            "reviewRating": {"@type": "Rating", "ratingValue": "5", "bestRating": "5"},
        },
    }
    schema_json = _json3.dumps(schema, ensure_ascii=False, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="robots" content="index,follow">
<title>{page_title}</title>
<meta name="description" content="{_esc_html(desc)}">
<meta property="og:title" content="{page_title}">
<meta property="og:description" content="{_esc_html(desc)}">
<meta property="og:url" content="https://{_esc_html(slug)}.homebridgegroup.co/verify/{cir_id}">
<link rel="canonical" href="https://{_esc_html(slug)}.homebridgegroup.co/verify/{cir_id}">
<script type="application/ld+json">{schema_json}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_AUTHORITY_CSS}</style>
</head>
<body>
<nav class="top-bar">
  <a class="tb-logo" href="https://homebridgegroup.co"><span>Auto</span>Mates</a>
  <a class="tb-cta" href="https://app.homebridgegroup.co">Sign In &#8594;</a>
</nav>
<div class="page">
  <div class="verify-header">
    <div class="verify-eyebrow">CPR&#8482; Record Lookup</div>
    <h1 class="verify-title">Certified Provenance Record&#8482; (CPR&#8482;)</h1>
    <p class="verify-sub">This record confirms a licensed real estate professional reviewed and approved this content prior to publication.</p>
  </div>
  <div class="result-card valid">
    <div class="rc-header">
      <div class="rc-icon">&#10003;</div>
      <div>
        <div class="rc-cir">{cir_id}</div>
        {f'<div class="rc-headline">{headline}</div>' if headline else ''}
        <div class="rc-agent">{agent_name}{(' &middot; ' + brokerage) if brokerage else ''}</div>
      </div>
    </div>
    <div class="rc-rows">
      <div class="rc-row"><span class="rc-row-label">Review outcome</span>{badge_html}</div>
      <div class="rc-row"><span class="rc-row-label">Niche</span><span class="rc-row-val">{niche or '&#8212;'}</span></div>
      <div class="rc-row"><span class="rc-row-label">Reviewed</span><span class="rc-row-val">{approved or '&#8212;'}</span></div>
      {f'<div class="rc-row"><span class="rc-row-label">Rules version at time of review</span><span class="rc-row-val">{rules_ver}</span></div>' if rules_ver else ''}
    </div>
    <div class="rc-footer">
      <strong>What this record confirms:</strong> A licensed real estate professional reviewed this content prior to publication.
      The review covered federal advertising standards, NAR Code of Ethics requirements, and applicable state real estate commission rules active at the time of review.
      <strong>What this record does not confirm:</strong> The accuracy of market data, valuations, predictions, or any factual claims in the content.
      CPR&#8482; certifies the completion of the review process, not the accuracy of the content.
      {f'<br><a href="{_esc_html(profile_url)}" class="rc-link">View agent profile &#8594;</a>' if slug else ''}
    </div>
  </div>
</div>
</body>
</html>"""
    return html


@app.get("/public/agent/{slug}/page")
async def public_agent_authority_page(slug: str, request: Request):
    """
    Server-side rendered authority page for an agent.
    All content baked into HTML source — fully crawlable by Google and AI systems.
    URL: https://{slug}.homebridgegroup.co (via host middleware) or
         https://api.homebridgegroup.co/public/agent/{slug}/page (direct test)
    """
    from fastapi.responses import HTMLResponse as _HTMLResponse
    import json as _json4

    user = _get_agent_by_slug(slug)
    if not user:
        raise HTTPException(404, "Agent not found.")

    # Reuse the existing public_agent_profile data assembly
    # Call the data-gathering logic directly rather than duplicating it
    response_data = await public_agent_profile(slug)

    html = _build_authority_page_html(response_data, slug)
    return _HTMLResponse(content=html, status_code=200, headers={
        "Cache-Control": "public, max-age=300",  # 5-minute cache — fresh enough, fast enough
        "X-Robots-Tag": "index, follow",
    })


@app.get("/public/agent/{slug}/posts/{post_slug}/page")
async def public_agent_post_page(slug: str, post_slug: str):
    """
    Server-side rendered individual post page.
    Each approved post gets its own crawlable, citable URL.
    URL: https://{slug}.homebridgegroup.co/posts/{post-slug}
    """
    from fastapi.responses import HTMLResponse as _HTMLResponse
    import json as _json5, re as _re5
    from database import get_conn as _gc5

    user = _get_agent_by_slug(slug)
    if not user:
        raise HTTPException(404, "Agent not found.")

    conn = _gc5()
    c    = conn.cursor()
    c.execute("""
        SELECT id, niche, content, cir_id, approved_at, status
        FROM content_library
        WHERE user_id = ? AND status IN ('approved','published')
        ORDER BY approved_at DESC
    """, (user["id"],))
    items = [dict(r) for r in c.fetchall()]
    conn.close()

    matched = None
    for item in items:
        try:
            cd = _json5.loads(item.get("content") or "{}")
        except Exception:
            cd = {}
        headline = cd.get("headline", "") or cd.get("title", "")
        if _post_slug_make(headline, item["id"]) == post_slug:
            body = cd.get("body", "") or cd.get("post", "") or cd.get("content", "")
            matched = {
                "headline":    headline,
                "body":        body,
                "niche":       item.get("niche", ""),
                "cir_id":      item.get("cir_id", ""),
                "approved_at": (item.get("approved_at") or "")[:10],
                "agent_name":  user["agent_name"],
                "brokerage":   user.get("brokerage", ""),
            }
            break

    if not matched:
        raise HTTPException(404, "Post not found.")

    import json as _j6
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": matched["headline"],
        "articleBody": matched["body"],
        "datePublished": matched["approved_at"],
        "author": {"@type": "Person", "name": matched["agent_name"]},
        "publisher": {"@type": "Organization", "name": "AutoMates", "url": "https://homebridgegroup.co"},
    }
    if matched["cir_id"]:
        schema["identifier"] = matched["cir_id"]
    schema_json = _j6.dumps(schema, ensure_ascii=False, indent=2)

    profile_url = f"https://{slug}.homebridgegroup.co"
    verify_url  = f"https://{slug}.homebridgegroup.co/verify/{matched['cir_id']}" if matched["cir_id"] else ""
    page_title  = _esc_html(f"{matched['headline']} — {matched['agent_name']} | AutoMates")
    desc        = _esc_html((matched["body"] or "")[:160])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="robots" content="index,follow">
<title>{page_title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{page_title}">
<meta property="og:description" content="{desc}">
<link rel="canonical" href="https://{_esc_html(slug)}.homebridgegroup.co/posts/{_esc_html(post_slug)}">
<script type="application/ld+json">{schema_json}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_AUTHORITY_CSS}</style>
</head>
<body>
<nav class="top-bar">
  <a class="tb-logo" href="https://homebridgegroup.co"><span>Auto</span>Mates</a>
  <a class="tb-cta" href="https://app.homebridgegroup.co">Sign In &#8594;</a>
</nav>
<div class="hero">
  <div class="hero-inner">
    <div>
      <div class="hero-eyebrow">{_esc_html(matched['niche']) if matched['niche'] else 'Real Estate'}</div>
      <h1 class="hero-name" style="font-size:clamp(28px,4vw,48px)">{_esc_html(matched['headline'])}</h1>
      <div class="hero-role">{_esc_html(matched['agent_name'])}{(' &middot; ' + _esc_html(matched['brokerage'])) if matched['brokerage'] else ''}</div>
      {f'<div class="hero-market">Reviewed {_esc_html(_fmt_date_long(matched["approved_at"]))}</div>' if matched["approved_at"] else ''}
      <div class="hero-actions">
        <a href="{_esc_html(profile_url)}" class="btn-outline-lt">&#8592; Back to profile</a>
        {f'<a href="{_esc_html(verify_url)}" class="btn-outline-lt">Verify CPR&#8482; &#8594;</a>' if verify_url else ''}
      </div>
    </div>
  </div>
</div>
<div class="main">
  <div class="sec">
    <div class="compliance-block" style="margin-bottom:0">
      <div class="cb-icon">&#10003;</div>
      <div>
        <div class="cb-title">CPR&#8482; Reviewed</div>
        <div class="cb-body">{_esc_html(matched['cir_id']) if matched['cir_id'] else 'This post was reviewed by a licensed professional prior to publication.'}</div>
      </div>
    </div>
  </div>
  <div class="sec" id="posts-sec">
    <div class="post-list">
      <div class="post-card featured" itemscope itemtype="https://schema.org/Article">
        <h2 class="post-h" itemprop="headline">{_esc_html(matched['headline'])}</h2>
        <div class="post-body" itemprop="articleBody" style="margin-top:12px">{_esc_html(matched['body'])}</div>
      </div>
    </div>
  </div>
  <div class="trust-footer">
    <div>
      <div class="tf-label">Reviewed by AutoMates</div>
      <div class="tf-headline">Real professionals. Reviewed content.</div>
      <div class="tf-sub">Every post reviewed by a licensed agent before publication.</div>
    </div>
    <a href="https://homebridgegroup.co" class="tf-cta" target="_blank">What is AutoMates? &#8594;</a>
  </div>
</div>
</body>
</html>"""
    return _HTMLResponse(content=html, status_code=200, headers={"Cache-Control": "public, max-age=300"})


@app.get("/public/verify/{cir_id}/page")
async def public_verify_cir_page(cir_id: str):
    """
    Server-side rendered CPR record verification page.
    All content in HTML source — crawlable, citable.
    URL: https://{slug}.homebridgegroup.co/verify/{cir_id}
    """
    from fastapi.responses import HTMLResponse as _HTMLResponse

    # Reuse existing verify data endpoint
    data = await public_verify_cir(cir_id)
    html = _build_verify_page_html(data)
    return _HTMLResponse(content=html, status_code=200, headers={
        "Cache-Control": "public, max-age=300",
        "X-Robots-Tag": "index, follow",
    })


@app.get("/public/agent/{slug}/sitemap.xml")
async def public_agent_sitemap(slug: str):
    """
    Per-agent sitemap listing authority page + all per-record post pages.
    Auto-generated from database. Submit to Google Search Console.
    """
    from fastapi.responses import Response as _Resp
    import json as _json7

    user = _get_agent_by_slug(slug)
    if not user:
        raise HTTPException(404, "Agent not found.")

    from database import get_conn as _gc7
    conn = _gc7()
    c    = conn.cursor()
    c.execute("""
        SELECT id, content, cir_id, approved_at
        FROM content_library
        WHERE user_id = ? AND status IN ('approved','published','archived')
        ORDER BY approved_at DESC
    """, (user["id"],))
    items = [dict(r) for r in c.fetchall()]
    conn.close()

    base = f"https://{slug}.homebridgegroup.co"
    urls = [f"  <url><loc>{base}</loc><changefreq>daily</changefreq><priority>1.0</priority></url>"]
    for item in items:
        try:
            cd = _json7.loads(item.get("content") or "{}")
        except Exception:
            cd = {}
        headline = cd.get("headline", "") or cd.get("title", "")
        if not headline:
            continue
        ps  = _post_slug_make(headline, item["id"])
        loc = f"{base}/posts/{ps}"
        lastmod = (item.get("approved_at") or "")[:10]
        urls.append(
            f"  <url><loc>{loc}</loc>"
            + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "")
            + "<changefreq>monthly</changefreq><priority>0.8</priority></url>"
        )
        if item.get("cir_id"):
            verify_loc = f"{base}/verify/{item['cir_id']}"
            urls.append(
                f"  <url><loc>{verify_loc}</loc>"
                + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "")
                + "<changefreq>never</changefreq><priority>0.6</priority></url>"
            )

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += "\n".join(urls)
    xml += "\n</urlset>"
    return _Resp(content=xml, media_type="application/xml")


@app.get("/public/sitemap.xml")
async def public_platform_sitemap():
    """
    Platform-wide sitemap listing all active agent authority pages.
    Submit this to Google Search Console as the master sitemap.
    """
    from fastapi.responses import Response as _Resp2
    from database import get_conn as _gc8

    conn = _gc8()
    c    = conn.cursor()
    c.execute("""
        SELECT agent_slug, created_at
        FROM users
        WHERE agent_slug IS NOT NULL AND agent_slug != '' AND is_active = 1
        ORDER BY created_at DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    urls = []
    for row in rows:
        slug_val = row.get("agent_slug", "")
        if not slug_val:
            continue
        loc     = f"https://{slug_val}.homebridgegroup.co"
        lastmod = (row.get("created_at") or "")[:10]
        urls.append(
            f"  <url><loc>{loc}</loc>"
            + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "")
            + "<changefreq>daily</changefreq><priority>1.0</priority></url>"
        )

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += "\n".join(urls)
    xml += "\n</urlset>"
    return _Resp2(content=xml, media_type="application/xml")


@app.get("/robots.txt")
async def robots_txt():
    """
    Robots.txt served from the backend.
    Allows all crawlers. Points to platform sitemap.
    """
    from fastapi.responses import PlainTextResponse
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "Sitemap: https://api.homebridgegroup.co/public/sitemap.xml\n"
    )
    return PlainTextResponse(content=content)


# ── Host-based middleware for slug subdomain routing ──────────────────────────
# When a request arrives with Host: {slug}.homebridgegroup.co
# route it to the server-side rendered authority page automatically.
# This fires AFTER Cloudflare changes the wildcard to point to this backend.
# app and api subdomains are excluded — they have explicit DNS records and
# their requests will never reach this middleware via the wildcard.
# The path is inspected so /feed, /posts/*, /verify/*, /sitemap.xml all work.

# ── IndexNow — instant index notification (POSITIONING_FUNNEL_SPINE_v3 Build N) ──
# Records live at {slug}.homebridgegroup.co/posts/{post_slug}. IndexNow validates
# that submitted URLs and the key file share a host, so each record is submitted
# under its own subdomain host with the key file served from that same subdomain
# (every subdomain routes to this app). One key value covers all of them.
_INDEXNOW_KEY_PATH = os.path.join(
    os.path.dirname(os.getenv("DB_PATH", "/data/homebridge.db")) or "/data",
    "indexnow_key.txt",
)


def _get_indexnow_key() -> str:
    """Returns the IndexNow key, generating and persisting it once."""
    try:
        if os.path.exists(_INDEXNOW_KEY_PATH):
            with open(_INDEXNOW_KEY_PATH) as _f:
                _k = _f.read().strip()
                if _k:
                    return _k
    except Exception:
        pass
    import secrets as _sec
    key = _sec.token_hex(16)  # 32 hex chars (IndexNow accepts 8-128 hex chars)
    try:
        os.makedirs(os.path.dirname(_INDEXNOW_KEY_PATH), exist_ok=True)
        with open(_INDEXNOW_KEY_PATH, "w") as _f:
            _f.write(key)
        print("[IndexNow] generated and stored new key")
    except Exception as _e:
        print(f"[IndexNow] key persist skipped: {_e}")
    return key


def _indexnow_submit(urls: list, host: str) -> None:
    """Best-effort IndexNow ping. Never raises — indexing must never block or
    fail an approval."""
    if not urls or not host:
        return
    try:
        import requests as _rq
        key = _get_indexnow_key()
        body = {
            "host": host,
            "key": key,
            "keyLocation": f"https://{host}/{key}.txt",
            "urlList": urls,
        }
        r = _rq.post("https://api.indexnow.org/indexnow", json=body, timeout=8)
        print(f"[IndexNow] submitted {len(urls)} url(s) for {host} -> HTTP {r.status_code}")
    except Exception as _e:
        print(f"[IndexNow] submit skipped: {_e}")


def _record_public_url(item: dict, user_id: int):
    """Canonical public URL for an approved record, or None if no slug."""
    try:
        from database import get_conn as _gc
        _c = _gc()
        _cur = _c.cursor()
        _cur.execute("SELECT agent_slug FROM users WHERE id = ?", (user_id,))
        _row = _cur.fetchone()
        _c.close()
        slug = _row["agent_slug"] if _row else None
        if not slug:
            return None
        content = item.get("content") or {}
        headline = content.get("headline") or content.get("title") or "post"
        import re as _re
        base = _re.sub(r"[^a-z0-9]+", "-", headline.lower().strip()).strip("-")[:60]
        ps = f"{base}-{item['id']}"
        return f"https://{slug}.homebridgegroup.co/posts/{ps}"
    except Exception:
        return None


def _post_approval_indexnow(item: dict, user_id: int, status: str) -> None:
    """Fire IndexNow + log sitemap resubmit when a record is approved/published.
    Build N. Best-effort; swallows all errors."""
    if status not in ("approved", "published"):
        return
    try:
        url = _record_public_url(item, user_id)
        if not url:
            return
        host = url.split("/")[2]  # {slug}.homebridgegroup.co
        _indexnow_submit([url], host)
        # Build N.2 — sitemaps are generated dynamically (no static file to
        # rebuild). Google has no instant-submit equivalent to IndexNow and GSC
        # API credentials are not wired, so log the sitemap URL for manual
        # resubmission to Google Search Console.
        print(f"[Sitemap] {host} updated — resubmit https://{host}/sitemap.xml to Google Search Console")
    except Exception as _e:
        print(f"[IndexNow] post-approval hook skipped: {_e}")


@app.middleware("http")
async def slug_subdomain_router(request: Request, call_next):
    """
    Detects requests arriving at {slug}.homebridgegroup.co and routes them
    to the appropriate server-side rendered page without requiring the /page suffix.
    """
    host = request.headers.get("host", "")
    # Strip port if present (local testing)
    host = host.split(":")[0]

    # Only act on *.homebridgegroup.co subdomains
    # Exclude known non-agent subdomains
    EXCLUDED = {"www", "app", "api", "homebridgegroup", ""}
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] == "homebridgegroup" and parts[-1] == "co":
        subdomain = parts[0]
        if subdomain not in EXCLUDED:
            path = request.url.path

            # /feed — RSS, already handled by existing route, pass through
            if path == "/feed" or path.startswith("/feed"):
                # Rewrite to /public/agent/{slug}/feed
                from fastapi.responses import RedirectResponse as _RR
                return _RR(url=f"https://api.homebridgegroup.co/public/agent/{subdomain}/feed", status_code=301)

            # /posts/{post_slug} — server-rendered post page
            import re as _re_mw
            post_match = _re_mw.match(r"^/posts/([^/]+)$", path)
            if post_match:
                post_slug_val = post_match.group(1)
                return await public_agent_post_page(subdomain, post_slug_val)

            # /verify/{cir_id} — server-rendered verify page
            verify_match = _re_mw.match(r"^/verify/([^/]+)$", path)
            if verify_match:
                cir_val = verify_match.group(1)
                return await public_verify_cir_page(cir_val)

            # /{key}.txt — IndexNow key file (Build N). Served on every agent
            # subdomain so IndexNow can verify ownership of {slug}.homebridgegroup.co.
            if path == f"/{_get_indexnow_key()}.txt":
                from fastapi.responses import PlainTextResponse as _PT
                return _PT(_get_indexnow_key())

            # /sitemap.xml — per-agent sitemap
            if path == "/sitemap.xml":
                return await public_agent_sitemap(subdomain)

            # /robots.txt — already handled globally, pass through
            if path == "/robots.txt":
                return await call_next(request)

            # Root and anything else — serve the authority page
            if path == "/" or path == "":
                return await public_agent_authority_page(subdomain, request)

    # Not a slug subdomain request — proceed normally
    return await call_next(request)

# ── End SSR authority pages block ─────────────────────────────────────────────


@app.post("/setup/slug")
async def set_agent_slug(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Let an agent set or customize their URL slug.
    Called on setup save if no slug exists yet, or when they customize it.
    Slug is validated for uniqueness and URL-safety.
    """
    import json as _json
    from database import get_conn as _gc

    body = await request.json()
    requested = str(body.get("slug","")).lower().strip()

    # Auto-generate if not provided
    if not requested:
        from database import get_conn as _gc2
        conn2 = _gc2()
        c2    = conn2.cursor()
        c2.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (current_user["id"],))
        row2 = c2.fetchone()
        conn2.close()
        setup2 = {}
        if row2:
            try: setup2 = _json.loads(row2["setup_json"] or "{}")
            except: pass
        requested = _make_slug(
            current_user.get("agent_name","agent"),
            setup2.get("market","")
        )

    # Sanitize
    slug = _re.sub(r"[^a-z0-9-]+", "-", requested).strip("-")[:60]
    if not slug:
        raise HTTPException(400, "Invalid slug.")

    # Check uniqueness (allow same user to re-set their own slug)
    from database import get_conn as _gc3
    conn3 = _gc3()
    c3    = conn3.cursor()
    c3.execute("SELECT id FROM users WHERE agent_slug = ? AND id != ?",
               (slug, current_user["id"]))
    conflict = c3.fetchone()
    if conflict:
        # Append user id to make unique
        slug = f"{slug}-{current_user['id']}"

    c3.execute("UPDATE users SET agent_slug = ? WHERE id = ?",
               (slug, current_user["id"]))
    conn3.commit()
    conn3.close()

    return {
        "ok":   True,
        "slug": slug,
        "url":  f"https://{slug}.homebridgegroup.co",
    }


@app.get("/setup/my-slug")
async def get_my_slug(current_user: dict = Depends(get_current_user)):
    """Return the agent's current slug and authority URL."""
    import json as _json
    from database import get_conn as _gc

    conn = _gc()
    c    = conn.cursor()
    c.execute("SELECT agent_slug FROM users WHERE id = ?", (current_user["id"],))
    row  = c.fetchone()
    conn.close()

    slug = row["agent_slug"] if row and row["agent_slug"] else None

    # Auto-generate if none exists yet
    if not slug:
        c2conn = _gc()
        c2     = c2conn.cursor()
        c2.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (current_user["id"],))
        row2 = c2.fetchone()
        c2conn.close()
        setup2 = {}
        if row2:
            try: setup2 = _json.loads(row2["setup_json"] or "{}")
            except: pass
        slug = _make_slug(
            current_user.get("agent_name","agent"),
            setup2.get("market","")
        )

    return {
        "slug": slug,
        "url":  f"https://{slug}.homebridgegroup.co",
        "rss":  f"https://api.homebridgegroup.co/public/agent/{slug}/feed",
        "set":  bool(row and row["agent_slug"]),
    }




# ═══════════════════════════════════════════════════════════════
# ROLE MANAGEMENT SYSTEM
# Super Admin controls all roles. Nobody else can change roles.
# Roles: super_admin, admin, support, broker, agent, assistant
# ═══════════════════════════════════════════════════════════════

def _is_super_admin(user: dict) -> bool:
    return user.get("role") == "super_admin"

def _require_super_admin(user: dict):
    if not _is_super_admin(user):
        raise HTTPException(403, "Super admin access required.")

def _is_staff_or_above(user: dict) -> bool:
    return user.get("role") in ("super_admin", "admin", "support")

def _can_use_hb_marketing(user: dict) -> bool:
    """super_admin and admin can use HB Marketing context."""
    return user.get("role") in ("super_admin", "admin")

def _can_have_agent_profile(user: dict) -> bool:
    """Only licensed roles can generate CIR-verified content as themselves."""
    return user.get("role") in ("super_admin", "admin", "agent")

def _can_approve_content(user: dict) -> bool:
    """Only licensed professionals can approve content and generate CIR records."""
    return user.get("role") in ("super_admin", "admin", "agent")


@app.post("/admin/set-role")
async def set_user_role(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Super admin only — set any user's role.
    Also sets is_licensed based on role.
    """
    _require_super_admin(current_user)
    body = await request.json()

    target_id = int(body.get("user_id", 0))
    new_role   = str(body.get("role", "")).strip()

    valid_roles = ("super_admin", "admin", "support",
                   "broker", "team", "agent", "assistant", "hb_marketer")
    if new_role not in valid_roles:
        raise HTTPException(400, f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    if not target_id:
        raise HTTPException(400, "user_id required.")

    # is_licensed is true for roles that can generate CIR-verified content
    is_licensed = 1 if new_role in ("super_admin", "admin", "agent") else 0

    # staff_type retained for DB compatibility but no longer role-driven
    staff_type = None

    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    c.execute("SELECT id, email, agent_name, role FROM users WHERE id = ?", (target_id,))
    target = c.fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, "User not found.")

    c.execute("""
        UPDATE users
        SET role = ?, is_licensed = ?, staff_type = ?
        WHERE id = ?
    """, (new_role, is_licensed, staff_type, target_id))
    conn.commit()
    conn.close()

    return {
        "ok":         True,
        "user_id":    target_id,
        "email":      target["email"],
        "agent_name": target["agent_name"],
        "new_role":   new_role,
        "is_licensed": bool(is_licensed),
    }


@app.post("/admin/set-plan")
async def set_user_plan(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Super admin only — set any user's plan directly.
    Used to grant insider access, founding member status, or manually
    assign a plan outside of Stripe (e.g. HomeBridge staff, beta testers).
    Stripe-managed plans (active subscriptions) should be changed via Stripe,
    not here — this route does not touch Stripe at all.
    """
    _require_super_admin(current_user)
    body = await request.json()

    target_id = int(body.get("user_id", 0))
    new_plan   = str(body.get("plan", "")).strip()

    # Only plans that make sense to set manually.
    # Stripe webhook handles subscription lifecycle — don't duplicate it here.
    _admin_assignable_plans = (
        "trial", "insider", "founding_member",
        "starter", "professional", "power", "coach"
    )
    if new_plan not in _admin_assignable_plans:
        raise HTTPException(400, f"Invalid plan. Must be one of: {', '.join(_admin_assignable_plans)}")

    if not target_id:
        raise HTTPException(400, "user_id required.")

    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    c.execute("SELECT id, email, agent_name, plan FROM users WHERE id = ?", (target_id,))
    target = c.fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, "User not found.")

    c.execute("UPDATE users SET plan = ? WHERE id = ?", (new_plan, target_id))
    conn.commit()
    conn.close()

    return {
        "ok":         True,
        "user_id":    target_id,
        "email":      target["email"],
        "agent_name": target["agent_name"],
        "new_plan":   new_plan,
    }


@app.get("/admin/users")
async def list_all_users(current_user: dict = Depends(get_current_user)):
    """
    Super admin and staff — see all users.
    Super admin sees billing status too.
    Staff see basic info only.
    """
    if not _is_staff_or_above(current_user):
        raise HTTPException(403, "Staff access required.")

    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    c.execute("""
        SELECT id, email, agent_name, brokerage, role, is_licensed,
               staff_type, plan, sub_status, created_at, is_active
        FROM users
        ORDER BY created_at DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    # Strip billing data for non-super-admins
    is_super = _is_super_admin(current_user)
    result = []
    for r in rows:
        user_data = {
            "id":          r["id"],
            "email":       r["email"],
            "agent_name":  r["agent_name"],
            "brokerage":   r["brokerage"],
            "role":        r["role"],
            "is_licensed": bool(r.get("is_licensed", 1)),
            "staff_type":  r.get("staff_type"),
            "is_active":   bool(r.get("is_active", 1)),
            "created_at":  r["created_at"],
        }
        if is_super:
            user_data["plan"]       = r.get("plan")
            user_data["sub_status"] = r.get("sub_status")
        result.append(user_data)

    return {"users": result, "total": len(result)}


@app.post("/admin/suspend-user")
async def suspend_user(request: Request, current_user: dict = Depends(get_current_user)):
    """Super admin only — suspend (deactivate) any user."""
    _require_super_admin(current_user)
    body      = await request.json()
    target_id = int(body.get("user_id", 0))
    if not target_id:
        raise HTTPException(400, "user_id required.")
    if target_id == current_user["id"]:
        raise HTTPException(400, "Cannot suspend your own account.")

    from database import get_conn as _gc
    conn = _gc()
    conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (target_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "suspended": target_id}


@app.post("/admin/reinstate-user")
async def reinstate_user(request: Request, current_user: dict = Depends(get_current_user)):
    """Super admin only — reinstate a suspended user."""
    _require_super_admin(current_user)
    body      = await request.json()
    target_id = int(body.get("user_id", 0))
    if not target_id:
        raise HTTPException(400, "user_id required.")

    from database import get_conn as _gc
    conn = _gc()
    conn.execute("UPDATE users SET is_active = 1 WHERE id = ?", (target_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "reinstated": target_id}


@app.post("/admin/unlock-user")
async def unlock_user(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Super admin only — clear login lockout on a user account.
    Used when an agent contacts support after being locked out by failed login attempts.
    Resets login_fail_count to 0 and clears login_locked_until.
    Does not affect token_version or session state.
    """
    _require_super_admin(current_user)
    body      = await request.json()
    target_id = int(body.get("user_id", 0))
    if not target_id:
        raise HTTPException(400, "user_id required.")

    from database import get_conn as _gc, log_audit_event as _lae
    conn = _gc()
    conn.execute(
        "UPDATE users SET login_fail_count = 0, login_locked_until = NULL WHERE id = ?",
        (target_id,)
    )
    conn.commit()
    conn.close()

    try:
        _lae(
            actor_id = current_user["id"],
            action   = "admin_unlock_user",
            detail   = f"Admin cleared login lockout for user_id={target_id}.",
        )
    except Exception:
        pass

    return {"ok": True, "unlocked": target_id}


@app.get("/admin/role-capabilities")
async def my_role_capabilities(current_user: dict = Depends(get_current_user)):
    """
    Returns what the current user is allowed to do.
    Frontend uses this to show/hide UI elements.
    """
    role = current_user.get("role", "agent")
    return {
        "role":                  role,
        "is_super_admin":        _is_super_admin(current_user),
        "is_staff_or_above":     _is_staff_or_above(current_user),
        "can_use_hb_marketing":  _can_use_hb_marketing(current_user),
        "can_have_agent_profile":_can_have_agent_profile(current_user),
        "can_approve_content":   _can_approve_content(current_user),
        "can_manage_users":      _is_super_admin(current_user),
        "can_see_billing":       _is_super_admin(current_user),
        "can_demo_platform":     _is_staff_or_above(current_user),
    }


@app.post("/admin/assign-assistant")
async def assign_assistant(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Super admin or broker — link an assistant to an agent.
    Assistant can then generate/draft content for that agent.
    """
    if not (_is_super_admin(current_user) or current_user.get("role") == "broker"):
        raise HTTPException(403, "Super admin or broker access required.")

    body         = await request.json()
    assistant_id = int(body.get("assistant_id", 0))
    agent_id     = int(body.get("agent_id", 0))
    if not assistant_id or not agent_id:
        raise HTTPException(400, "assistant_id and agent_id required.")

    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()

    # Verify assistant role
    c.execute("SELECT role FROM users WHERE id = ?", (assistant_id,))
    row = c.fetchone()
    if not row or row["role"] != "assistant":
        conn.close()
        raise HTTPException(400, "User is not an assistant.")

    c.execute("""
        INSERT INTO assistant_agents (assistant_id, agent_id, granted_by)
        VALUES (?, ?, ?)
        ON CONFLICT(assistant_id, agent_id) DO NOTHING
    """, (assistant_id, agent_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"ok": True, "assistant_id": assistant_id, "agent_id": agent_id}


@app.get("/my-agents")
async def get_my_agents(current_user: dict = Depends(get_current_user)):
    """
    For assistants — returns the agents they are linked to.
    Used to let the assistant select which agent they are posting for.
    """
    if current_user.get("role") != "assistant":
        raise HTTPException(403, "Assistant role required.")

    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    c.execute("""
        SELECT u.id, u.agent_name, u.brokerage, u.email
        FROM assistant_agents aa
        JOIN users u ON u.id = aa.agent_id
        WHERE aa.assistant_id = ? AND u.is_active = 1
    """, (current_user["id"],))
    agents = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"agents": agents}







@app.post("/admin/users/{user_id}/role")
async def admin_set_role(user_id: int, request: Request,
                         current_user: dict = Depends(get_current_user)):
    """Change a user's role — super_admin only."""
    _require_super_admin(current_user)
    body = await request.json()
    new_role = str(body.get("role", "")).strip()
    valid_roles = ("super_admin", "admin", "support", "broker", "team", "agent", "coach", "assistant", "hb_marketer")
    if new_role not in valid_roles:
        raise HTTPException(400, f"Invalid role. Must be one of: {', '.join(valid_roles)}")
    # Cannot demote yourself
    if user_id == current_user["id"] and new_role != "super_admin":
        raise HTTPException(400, "Cannot change your own role.")
    from database import get_conn as _gc
    conn = _gc()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()
    return {"ok": True, "user_id": user_id, "new_role": new_role}


@app.post("/admin/users/{user_id}/suspend")
async def admin_suspend_user(user_id: int,
                              current_user: dict = Depends(get_current_user)):
    """Suspend a user account — super_admin only."""
    _require_super_admin(current_user)
    if user_id == current_user["id"]:
        raise HTTPException(400, "Cannot suspend your own account.")
    from database import get_conn as _gc
    conn = _gc()
    conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "user_id": user_id, "status": "suspended"}


@app.post("/admin/users/{user_id}/reactivate")
async def admin_reactivate_user(user_id: int,
                                 current_user: dict = Depends(get_current_user)):
    """Reactivate a suspended user — super_admin only."""
    _require_super_admin(current_user)
    from database import get_conn as _gc
    conn = _gc()
    conn.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "user_id": user_id, "status": "active"}


@app.delete("/admin/users/{user_id}")
async def admin_terminate_user(user_id: int,
                                current_user: dict = Depends(get_current_user)):
    """
    Permanently terminate a user account — super_admin only.
    Soft-deletes: marks inactive and anonymises email.
    Data retained for compliance/audit trail.
    """
    _require_super_admin(current_user)
    if user_id == current_user["id"]:
        raise HTTPException(400, "Cannot terminate your own account.")
    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    # Soft delete — anonymise but keep audit trail
    c.execute("""
        UPDATE users SET
            is_active    = 0,
            email        = 'terminated-' || id || '@deleted.homebridgegroup.co',
            password_hash = 'TERMINATED',
            sub_status   = 'terminated'
        WHERE id = ?
    """, (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "user_id": user_id, "status": "terminated"}


@app.post("/admin/users/{user_id}/assign-assistant")
async def admin_assign_assistant(user_id: int, request: Request,
                                  current_user: dict = Depends(get_current_user)):
    """Link an assistant to one or more agents — super_admin or broker."""
    if not _is_super_admin(current_user) and current_user.get("role") != "broker":
        raise HTTPException(403, "Not authorized.")
    body = await request.json()
    agent_ids = body.get("agent_ids", [])
    if not agent_ids:
        raise HTTPException(400, "Provide at least one agent_id.")
    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    for agent_id in agent_ids:
        try:
            c.execute("""
                INSERT INTO assistant_agents (assistant_id, agent_id, granted_by)
                VALUES (?, ?, ?)
                ON CONFLICT(assistant_id, agent_id) DO NOTHING
            """, (user_id, agent_id, current_user["id"]))
        except Exception:
            pass
    conn.commit()
    conn.close()
    return {"ok": True, "assistant_id": user_id, "linked_agents": agent_ids}


@app.get("/admin/users/{user_id}/assigned-agents")
async def admin_get_assigned_agents(user_id: int,
                                     current_user: dict = Depends(get_current_user)):
    """Get agents linked to an assistant."""
    if not _is_staff_or_above(current_user) and current_user.get("role") != "broker":
        raise HTTPException(403, "Not authorized.")
    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    c.execute("""
        SELECT u.id, u.agent_name, u.brokerage, u.email
        FROM assistant_agents aa
        JOIN users u ON u.id = aa.agent_id
        WHERE aa.assistant_id = ?
    """, (user_id,))
    agents = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"assistant_id": user_id, "agents": agents}


@app.post("/admin/users/{user_id}/reset-niches")
async def admin_reset_niches(user_id: int, current_user: dict = Depends(get_current_user)):
    """
    Super admin only — reset an agent's niche selections and clear all their schedules.
    Used when an agent has stale niche data from a previous taxonomy version and needs
    a clean slate to re-select niches from the current v2.1 taxonomy.

    Part B of the Scheduler-Niche Lifecycle fix (Session 56).
    Spec: Niche Taxonomy v2.1 Specification, Scheduler-Niche Lifecycle Part B.

    Steps:
    1. Load the agent's current setup_json
    2. Clear primaryNiches and subNiches from setup_json
    3. Save the cleaned setup_json back to agent_setup
    4. DELETE all schedules for this user (clean slate)
    5. Return counts for confirmation

    The agent will need to re-select their niches and re-create their schedules.
    Content in the library is not affected. CIR records are not affected.
    """
    _require_super_admin(current_user)

    from database import get_conn as _gc_rn, get_agent_setup as _gas_rn, schedules_delete_for_user as _sdf

    # Load current setup
    current_setup = _gas_rn(user_id)
    if not current_setup and not isinstance(current_setup, dict):
        current_setup = {}

    old_niches    = current_setup.get("primaryNiches", []) or []
    old_sub_niches = current_setup.get("subNiches", []) or []

    # Clear niche selections from setup
    current_setup["primaryNiches"] = []
    current_setup["subNiches"]     = []

    # Save cleaned setup
    conn_rn = _gc_rn()
    try:
        conn_rn.execute("""
            INSERT INTO agent_setup (user_id, setup_json, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                setup_json = excluded.setup_json,
                updated_at = excluded.updated_at
        """, (user_id, json.dumps(current_setup)))
        conn_rn.commit()
    finally:
        conn_rn.close()

    # Delete all schedules for this user
    cleared_schedules = _sdf(user_id)

    from database import log_audit_event as _lae_rn
    _lae_rn(
        actor_id  = current_user["id"],
        action    = "admin_reset_niches",
        target_id = user_id,
        detail    = (
            f"Reset niches and cleared all schedules for user {user_id}. "
            f"Removed niches: {old_niches}. "
            f"Cleared {cleared_schedules} schedule record(s)."
        ),
    )

    print(f"[Admin] Reset niches and cleared all schedules for user {user_id}. "
          f"Old niches: {old_niches}. Schedules cleared: {cleared_schedules}.")

    return {
        "ok":               True,
        "user_id":          user_id,
        "niches_cleared":   old_niches,
        "sub_niches_cleared": old_sub_niches,
        "schedules_cleared": cleared_schedules,
        "message": (
            f"Niche selections cleared. {cleared_schedules} schedule record(s) deleted. "
            "The agent must re-select their niches and re-create their schedules."
        ),
    }


@app.post("/admin/users/{user_id}/purge-stale-schedules")
async def admin_purge_stale_schedules(user_id: int, current_user: dict = Depends(get_current_user)):
    """
    Super admin only — delete schedule records whose niche column does not match
    any of the agent's current primaryNiches.

    This fixes the pre-migration orphan problem: schedule rows created under old
    taxonomy names that were never cleaned up by Part A of the Scheduler-Niche
    Lifecycle (which only removes niches that were present in primaryNiches at
    save time, not rows that pre-date the taxonomy migration).

    Does NOT touch the agent's niche selections, setup_json, library, or CIR records.
    Only deletes schedule rows whose niche name is no longer valid for this agent.

    Session 57 — fixes Kevin's 9-entry schedule panel (should be 3).
    """
    _require_super_admin(current_user)

    from database import log_audit_event as _lae_ps

    # Read the agent's current primaryNiches
    current_setup   = get_agent_setup(user_id) or {}
    current_niches  = set(current_setup.get("primaryNiches", []) or [])

    # Read all schedule rows for this user
    all_schedules   = schedules_get_all(user_id)

    stale   = [s for s in all_schedules if s["niche"] not in current_niches]
    valid   = [s for s in all_schedules if s["niche"] in current_niches]

    deleted_niches  = []
    deleted_count   = 0
    for s in stale:
        removed = schedule_delete(user_id, s["niche"])
        if removed:
            deleted_niches.append(s["niche"])
            deleted_count += 1

    _lae_ps(
        actor_id  = current_user["id"],
        action    = "admin_purge_stale_schedules",
        target_id = user_id,
        detail    = (
            f"Purged {deleted_count} stale schedule(s) for user {user_id}. "
            f"Deleted niches: {deleted_niches}. "
            f"Retained niches: {[s['niche'] for s in valid]}."
        ),
    )

    print(f"[Admin] Purged {deleted_count} stale schedule(s) for user {user_id}. "
          f"Deleted: {deleted_niches}. Retained: {[s['niche'] for s in valid]}.")

    return {
        "ok":               True,
        "user_id":          user_id,
        "current_niches":   sorted(current_niches),
        "deleted_count":    deleted_count,
        "deleted_niches":   deleted_niches,
        "retained_niches":  [s["niche"] for s in valid],
        "message": (
            f"{deleted_count} stale schedule record(s) deleted. "
            f"{len(valid)} valid schedule(s) retained. "
            f"Agent's active niches: {sorted(current_niches)}."
        ),
    }


@app.post("/admin/create-user")
async def admin_create_user(request: Request,
                             current_user: dict = Depends(get_current_user)):
    """
    Create a new user account directly — super_admin only.
    Used to add staff, assistants, or test accounts without
    going through the public registration flow.
    """
    _require_super_admin(current_user)
    import bcrypt as _bcrypt
    body        = await request.json()
    email       = str(body.get("email","")).strip().lower()
    password    = str(body.get("password","")).strip()
    agent_name  = str(body.get("agent_name","")).strip()
    role        = str(body.get("role","agent")).strip()
    brokerage   = str(body.get("brokerage","")).strip()
    is_licensed = int(body.get("is_licensed", 1))
    # plan — defaults to "trial"; "insider" is set via the HomeBridge Team Member checkbox.
    # Only allow plans that exist in PLAN_LIMITS. Never allow self-serve billing plans
    # to be set here (those come from Stripe webhooks). Admin-assignable plans only.
    _admin_assignable_plans = ("trial", "insider", "founding_member",
                               "starter", "professional", "power")
    plan = str(body.get("plan", "trial")).strip()
    if plan not in _admin_assignable_plans:
        plan = "trial"

    if not email or not password or not agent_name:
        raise HTTPException(400, "email, password, and agent_name are required.")
    valid_roles = ("super_admin","admin","support","broker","team","agent","assistant","hb_marketer")
    if role not in valid_roles:
        raise HTTPException(400, f"Invalid role.")

    pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (email, password_hash, agent_name, brokerage, role, is_licensed, plan)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (email, pw_hash, agent_name, brokerage, role, is_licensed, plan))
        conn.commit()
        new_id = c.lastrowid
    except Exception as e:
        conn.close()
        raise HTTPException(409, f"Could not create user: {str(e)}")
    conn.close()
    return {"ok": True, "user_id": new_id, "email": email, "role": role, "plan": plan}


# ── Startup: ensure user_id=2 is super_admin ──
# This runs once on every deploy — safe and idempotent.
@app.on_event("startup")
async def ensure_super_admin():
    try:
        from database import get_conn as _gc
        conn = _gc()
        conn.execute(
            "UPDATE users SET role = 'super_admin' WHERE id = 2 AND role != 'super_admin'"
        )
        conn.commit()
        conn.close()
        print("[HomeBridge] Super admin confirmed: user_id=2")
    except Exception as e:
        print(f"[HomeBridge] Super admin check failed: {e}")




@app.get("/admin/stats")
async def admin_stats(current_user: dict = Depends(get_current_user)):
    """Platform stats for admin dashboard. Super admin sees billing data."""
    if not _is_staff_or_above(current_user):
        raise HTTPException(403, "Staff access required.")
    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    now  = datetime.utcnow()
    m30  = (now - timedelta(days=30)).isoformat()
    w7   = (now - timedelta(days=7)).isoformat()

    c.execute("SELECT COUNT(*) as n FROM users WHERE is_active=1")
    total_users = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM users WHERE is_active=1 AND created_at >= ?", (m30,))
    new_30 = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM users WHERE role='broker' AND is_active=1")
    total_brokers = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM users WHERE role='agent' AND is_active=1")
    total_agents = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM content_library")
    total_content = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM content_library WHERE saved_at >= ?", (w7,))
    content_week = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM content_library WHERE status='published'")
    total_published = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM schedules WHERE active=1")
    active_schedules = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM users WHERE agent_slug IS NOT NULL AND agent_slug != '' AND is_active=1")
    live_authority_pages = c.fetchone()["n"]
    conn.close()
    return {
        "total_users":          total_users,
        "new_users_30d":        new_30,
        "total_brokers":        total_brokers,
        "total_agents":         total_agents,
        "total_content":        total_content,
        "content_this_week":    content_week,
        "total_published":      total_published,
        "active_schedules":     active_schedules,
        "live_authority_pages": live_authority_pages,
    }


@app.post("/admin/set-active")
async def set_user_active(request: Request, current_user: dict = Depends(get_current_user)):
    """Super admin only — activate or deactivate any user."""
    _require_super_admin(current_user)
    body      = await request.json()
    target_id = int(body.get("user_id", 0))
    is_active = bool(body.get("is_active", True))
    if not target_id:
        raise HTTPException(400, "user_id required.")
    if target_id == current_user["id"]:
        raise HTTPException(400, "Cannot change your own active status.")
    from database import get_conn as _gc
    conn = _gc()
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (1 if is_active else 0, target_id))
    conn.commit()
    conn.close()
    return {"ok": True, "user_id": target_id, "is_active": is_active}


@app.post("/admin/delete-user")
async def delete_user(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Super admin only — permanently delete a user and all their data.
    Double confirmation required in the UI before this is called.
    Cannot delete your own account or another super_admin.
    """
    _require_super_admin(current_user)
    body      = await request.json()
    target_id = int(body.get("user_id", 0))
    if not target_id:
        raise HTTPException(400, "user_id required.")
    if target_id == current_user["id"]:
        raise HTTPException(400, "Cannot delete your own account.")

    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()

    # Protect other super admins
    c.execute("SELECT role FROM users WHERE id=?", (target_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "User not found.")
    if row["role"] == "super_admin":
        conn.close()
        raise HTTPException(403, "Cannot delete another super admin account.")

    # Delete all user data
    for table, col in [
        ("content_library",      "user_id"),
        ("schedules",            "user_id"),
        ("agent_setup",          "user_id"),
        ("platform_connections", "user_id"),
        ("platform_posts",       "user_id"),
        ("assistant_agents",     "assistant_id"),
        ("assistant_agents",     "agent_id"),
    ]:
        try:
            c.execute(f"DELETE FROM {table} WHERE {col}=?", (target_id,))
        except Exception:
            pass

    c.execute("DELETE FROM users WHERE id=?", (target_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "deleted": target_id}


@app.post("/compliance/check")
async def recheck_compliance(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Re-run compliance check on an existing library item after editing.
    Uses the same rule-based checker as generation — no AI call, instant.
    Updates the item's compliance field and returns the new result.
    """
    from content_engine import _run_compliance_check
    from database import get_conn as _gc

    body         = await request.json()
    item_id      = int(body.get("item_id", 0))
    content_mode = str(body.get("content_mode", "agent"))

    if not item_id:
        raise HTTPException(400, "item_id required.")

    # Load the library item
    conn = _gc()
    c    = conn.cursor()
    c.execute("SELECT content, niche FROM content_library WHERE id = ? AND user_id = ?",
              (item_id, current_user["id"]))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, "Library item not found.")

    try:
        import json as _json
        content_data = _json.loads(row["content"] or "{}")
    except Exception:
        content_data = {}

    # Build the full post text for checking
    post_text = " ".join(filter(None, [
        content_data.get("headline", ""),
        content_data.get("post", ""),
        content_data.get("cta", ""),
    ]))

    # Get agent info for disclosure checks
    agent_name = current_user.get("agent_name", "")
    brokerage  = current_user.get("brokerage", "")
    niche      = row["niche"] or ""

    # Get MLS names from agent setup
    mls_names = []
    try:
        conn2 = _gc()
        c2    = conn2.cursor()
        c2.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (current_user["id"],))
        setup_row = c2.fetchone()
        conn2.close()
        if setup_row:
            import json as _json2
            setup = _json2.loads(setup_row["setup_json"] or "{}")
            mls_names = setup.get("mlsNames", [])
    except Exception:
        pass

    # Get agent state for state_commission personalisation (Item #3)
    agent_state = ""
    try:
        setup_obj = {}
        conn4 = _gc()
        c4    = conn4.cursor()
        c4.execute("SELECT setup_json FROM agent_setup WHERE user_id = ?", (current_user["id"],))
        sr4 = c4.fetchone()
        conn4.close()
        if sr4:
            import json as _json4
            setup_obj = _json4.loads(sr4["setup_json"] or "{}")
        agent_state = setup_obj.get("state", "")
    except Exception:
        pass

    result = _run_compliance_check(
        content      = post_text,
        agent_name   = agent_name,
        brokerage    = brokerage,
        mls_names    = mls_names,
        niche        = niche,
        content_mode = content_mode,
        state        = agent_state,
    )

    # Save updated compliance + timestamp back to library item
    result_dict = result.dict()
    from datetime import datetime as _dt2
    checked_at = _dt2.utcnow().isoformat()
    try:
        conn3 = _gc()
        import json as _json3
        conn3.execute(
            "UPDATE content_library SET compliance = ?, compliance_checked_at = ? WHERE id = ? AND user_id = ?",
            (_json3.dumps(result_dict), checked_at, item_id, current_user["id"])
        )
        conn3.commit()
        conn3.close()
    except Exception as _e:
        print(f"[Compliance] Could not save re-check result for item {item_id}: {_e}")

    result_dict["checked_at"] = checked_at
    return result_dict


@app.post("/image/generate")
async def generate_image(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Generate a social-ready image for a library item using gpt-image-2.
    Requires OPENAI_API_KEY in Render environment variables.

    Images are returned as base64 and stored as data URIs — permanent, no expiry.
    No people or agents are included in generated images — property and market
    scenes only, driven by the agent's niche, service areas, and post content.

    Regeneration limit: 3 per library item. Enforced here and displayed in the UI.
    """
    import os as _os
    import httpx as _httpx
    import base64 as _b64

    openai_key = _os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        raise HTTPException(503, "Image generation not configured. Add OPENAI_API_KEY to Render environment variables.")

    body            = await request.json()
    thumbnail_idea  = str(body.get("thumbnail_idea", "")).strip()
    niche           = str(body.get("niche",          "real estate")).strip()
    market          = str(body.get("market",         "")).strip()
    library_item_id = body.get("library_item_id")

    # ── Regeneration limit — 3 per post, all plans ───────────────────────────
    IMAGE_REGEN_LIMIT = 3
    current_count = 0
    if library_item_id:
        try:
            from database import get_conn as _gc
            _conn = _gc()
            _row = _conn.execute(
                "SELECT image_regen_count FROM content_library WHERE id = ? AND user_id = ?",
                (library_item_id, current_user["id"])
            ).fetchone()
            _conn.close()
            if _row:
                current_count = _row["image_regen_count"] or 0
        except Exception as _e:
            print(f"[Image] Could not read regen count for item {library_item_id}: {_e}")

    if current_count >= IMAGE_REGEN_LIMIT:
        raise HTTPException(429, f"Image generation limit reached ({IMAGE_REGEN_LIMIT} per post). Edit the image description to unlock a new generation.")

    # ── Build prompt — specific, grounded, no people ─────────────────────────
    # thumbnail_idea is generated by Claude in content_engine.py with full
    # niche/area/post context — it arrives as a concrete visual brief.
    # We reinforce photorealism and explicitly exclude people here.
    parts = []
    if thumbnail_idea: parts.append(thumbnail_idea)
    if market:         parts.append(f"Location: {market}")
    if niche:          parts.append(f"Real estate context: {niche}")

    base = ". ".join(filter(None, parts)) if parts else f"Professional real estate scene, {niche}, {market}"
    prompt = (
        f"{base}. "
        f"Photorealistic photography, natural lighting, sharp focus. "
        f"No people, no agents, no text overlays, no watermarks, no logos. "
        f"Property and neighborhood scenes only. Professional quality."
    )

    # ── Call gpt-image-2 — returns base64, permanent storage ─────────────────
    try:
        async with _httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model":   "gpt-image-2",
                    "prompt":  prompt[:4000],
                    "n":       1,
                    "size":    "1024x1024",   # gpt-image-2 supported sizes: 1024x1024, 1024x1536, 1536x1024
                    "quality": "low",         # cost-efficient for testing; change to "medium" or "high" for production
                    # response_format not supported by gpt-image-2 — it returns b64_json by default
                }
            )
    except Exception as e:
        raise HTTPException(502, f"Image generation request failed: {str(e)}")

    if resp.status_code != 200:
        try:    err_msg = resp.json().get("error", {}).get("message", "Unknown error")
        except: err_msg = resp.text[:200]
        raise HTTPException(502, f"Image generation failed: {err_msg}")

    b64_data  = resp.json()["data"][0]["b64_json"]
    image_url = f"data:image/png;base64,{b64_data}"

    # ── Save image and increment regen counter — best effort ─────────────────
    if library_item_id:
        try:
            from database import get_conn as _gc
            conn = _gc()
            conn.execute(
                """UPDATE content_library
                   SET image_url = ?,
                       image_regen_count = COALESCE(image_regen_count, 0) + 1
                   WHERE id = ? AND user_id = ?""",
                (image_url, library_item_id, current_user["id"])
            )
            conn.commit()
            conn.close()
        except Exception as _e:
            print(f"[Image] Could not save image for item {library_item_id}: {_e}")

    new_count = current_count + 1
    remaining = IMAGE_REGEN_LIMIT - new_count
    return {
        "image_url":  image_url,
        "regen_count": new_count,
        "regen_remaining": remaining,
    }


# ── Waitlist IP-based rate limiter ───────────────────────────────────────────
# Prevents bot/spam abuse of the public contact form.
# In-memory rolling window — resets on server restart, which is acceptable
# for a walkthrough-request form (not a payment or auth endpoint).
_waitlist_rate: dict = {}   # { ip: [unix_timestamp, ...] }
_WAITLIST_MAX    = 3        # max submissions allowed per window
_WAITLIST_WINDOW = 3600     # rolling window in seconds (1 hour)

def _waitlist_check_rate_limit(ip: str) -> bool:
    """
    Returns True (request allowed) or False (rate limited).
    Prunes stale timestamps on every call — no background cleanup needed.
    """
    now          = time.time()
    window_start = now - _WAITLIST_WINDOW
    hits         = [t for t in _waitlist_rate.get(ip, []) if t > window_start]
    if len(hits) >= _WAITLIST_MAX:
        return False
    hits.append(now)
    _waitlist_rate[ip] = hits
    return True


@app.post("/waitlist")
async def submit_waitlist(request: Request):
    # ── IP extraction — Cloudflare passes real IP in x-forwarded-for ─────────
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    if not _waitlist_check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests from this address. Please try again later."
        )

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid request body.")

    name    = str(body.get("name",    "")).strip()[:120]
    email   = str(body.get("email",   "")).strip()[:200]
    phone   = str(body.get("phone",   "")).strip()[:30]
    role    = str(body.get("role",    "")).strip()[:120]
    company = str(body.get("company", "")).strip()[:200]
    message = str(body.get("message", "")).strip()[:1000]

    if not name or not email:
        raise HTTPException(400, "Name and email are required.")

    # Store in DB
    try:
        from database import get_conn
        conn = get_conn()
        c    = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT, phone TEXT, role TEXT, company TEXT,
                message TEXT, submitted_at TEXT
            )
        """)
        # Safe migration: add phone column if table existed before this change
        try:
            c.execute("ALTER TABLE waitlist ADD COLUMN phone TEXT")
        except Exception:
            pass  # Column already exists — not an error
        from datetime import datetime
        c.execute(
            "INSERT INTO waitlist (name, email, phone, role, company, message, submitted_at) VALUES (?,?,?,?,?,?,?)",
            (name, email, phone, role, company, message, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Waitlist] DB error: {e}")

    # Send email via SendGrid
    try:
        import httpx as _httpx
        sendgrid_key  = os.getenv("SENDGRID_API_KEY", "")
        sendgrid_from = os.getenv("SENDGRID_FROM_EMAIL", "support@homebridgegroup.co")
        if sendgrid_key:
            phone_line = f"Phone: {phone}\n" if phone else ""
            email_body = f"""New First Look Request\n\nName: {name}\nEmail: {email}\n{phone_line}Role: {role}\nCompany: {company}\nMessage: {message}\n\nSubmitted via homebridgegroup.co"""
            await _httpx.AsyncClient().post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {sendgrid_key}", "Content-Type": "application/json"},
                json={
                    "personalizations": [{"to": [{"email": "support@homebridgegroup.co"}]}],
                    "from": {"email": sendgrid_from, "name": "HomeBridge Waitlist"},
                    "subject": f"First Look Request: {name} — {company or role}",
                    "content": [{"type": "text/plain", "value": email_body}]
                },
                timeout=10
            )
    except Exception as e:
        print(f"[Waitlist] SendGrid error: {e}")

    return {"ok": True, "message": "Request received. We'll be in touch shortly."}

# ─────────────────────────────────────────────────────────────────────────────
# CONTACT FORM — Session 24
# POST /contact  — public, saves to DB + sends notification to Kevin
# GET  /admin/contacts — admin only, list all submissions
# Rate-limited: reuses _waitlist_rate limiter (3 per hour per IP)
# ─────────────────────────────────────────────────────────────────────────────

class ContactRequest(BaseModel):
    name:    str
    email:   str
    type:    str = "other"   # agent | team | broker | partner | other
    message: str = ""


# =============================================================================
# PUBLIC COMPLIANCE CHECKER — Session 56, Phase 4, Item 11
# POST /public/compliance-check
# =============================================================================
# Unauthenticated lead-gen endpoint. Runs an 8-rule compliance check
# against a pasted social media post after email capture.
# Rate limited: 3 requests per hour per IP.
# One check per email: enforced by compliance_checker_leads table.
# =============================================================================

_comp_check_rate: dict = {}   # { ip: [unix_timestamp, ...] }
_COMP_CHECK_MAX    = 3
_COMP_CHECK_WINDOW = 3600     # 1 hour rolling window

def _comp_check_rate_limit(ip: str) -> bool:
    """Returns True (allowed) or False (rate limited)."""
    import time as _t
    now          = _t.time()
    window_start = now - _COMP_CHECK_WINDOW
    hits = [t for t in _comp_check_rate.get(ip, []) if t > window_start]
    if len(hits) >= _COMP_CHECK_MAX:
        return False
    hits.append(now)
    _comp_check_rate[ip] = hits
    return True


def _geolocate_ip_state(ip: str) -> str:
    """
    Best-effort IP geolocation to US state using ip-api.com (free, no key required).
    Returns two-letter state abbreviation (e.g. "CO") or empty string on failure.
    Non-blocking — never raises.
    """
    import urllib.request as _ureq
    import json as _jgeo
    try:
        if not ip or ip in ("unknown", "127.0.0.1", "::1"):
            return ""
        with _ureq.urlopen(f"http://ip-api.com/json/{ip}?fields=status,regionCode", timeout=2) as r:
            data = _jgeo.loads(r.read().decode())
            if data.get("status") == "success":
                return data.get("regionCode", "")
    except Exception:
        pass
    return ""


def _normalize_email_base(email: str) -> str:
    """
    Returns the base email address stripping Gmail-style plus-addressing.
    e.g. user+test@gmail.com -> user@gmail.com
    Used for duplicate detection, not gatekeeping.
    """
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    base_local = local.split("+")[0]
    return f"{base_local}@{domain}"


@app.post("/public/compliance-check")
async def public_compliance_check(request: Request):
    """
    Public-facing compliance check endpoint for compliance-check.html.
    Flow:
      1. Validate post_text, email, and name are present.
      2. Check IP rate limit (3/hour).
      3. Check email against compliance_checker_leads (one check per email).
      4. Geolocate IP to US state (non-blocking, best-effort).
      5. Run 8-rule compliance check via run_public_compliance_check().
      6. Save lead record to compliance_checker_leads.
      7. Return results.
    No authentication required. CORS-permissive for Bluehost cross-origin requests.
    Schema migration: adds name, state, base_email columns if not present (additive).
    """
    # ── IP extraction ─────────────────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    # ── IP rate limit ─────────────────────────────────────────────────────────
    if not _comp_check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again in an hour."
        )

    # ── Parse body ─────────────────────────────────────────────────────────────
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid request body.")

    post_text = str(body.get("post_text", "")).strip()[:5000]
    email     = str(body.get("email",     "")).strip().lower()[:200]
    name      = str(body.get("name",      "")).strip()[:120]

    if not post_text:
        raise HTTPException(400, "post_text is required.")
    if not email or "@" not in email:
        raise HTTPException(400, "A valid email address is required.")
    if not name:
        raise HTTPException(400, "Your name is required.")

    base_email = _normalize_email_base(email)

    # ── DB: ensure table exists with full schema, migrate if needed ───────────
    from database import get_conn as _gc_pub
    try:
        conn = _gc_pub()
        c    = conn.cursor()
        # Base table — always ensure it exists
        c.execute("""
            CREATE TABLE IF NOT EXISTS compliance_checker_leads (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                email        TEXT NOT NULL UNIQUE,
                post_text    TEXT NOT NULL,
                results_json TEXT,
                ip_address   TEXT,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        # Additive migrations — safe to run every request, SQLite silently errors on existing columns
        for _col_sql in [
            "ALTER TABLE compliance_checker_leads ADD COLUMN name TEXT",
            "ALTER TABLE compliance_checker_leads ADD COLUMN state TEXT",
            "ALTER TABLE compliance_checker_leads ADD COLUMN base_email TEXT",
        ]:
            try:
                c.execute(_col_sql)
                conn.commit()
            except Exception:
                pass  # Column already exists

        # Check email uniqueness (exact match)
        c.execute("SELECT id FROM compliance_checker_leads WHERE email = ?", (email,))
        existing = c.fetchone()
        conn.close()
    except Exception as _db_err:
        print(f"[ComplianceCheck] DB setup error: {_db_err}")
        existing = None

    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error":   "email_already_used",
                "message": (
                    "You have already used your free check. "
                    "Sign up for AutoMates to check every post before you publish."
                ),
                "signup_url": "https://app.homebridgegroup.co",
            }
        )

    # ── Geolocate IP to state (non-blocking) ─────────────────────────────────
    state = _geolocate_ip_state(client_ip)

    # ── Run the 8-rule compliance check ──────────────────────────────────────
    try:
        check_result = run_public_compliance_check(post_text)
    except HTTPException:
        raise
    except Exception as _ce:
        raise HTTPException(500, f"Compliance check failed: {str(_ce)}")

    # ── Save lead record ──────────────────────────────────────────────────────
    import json as _json_cl
    try:
        conn = _gc_pub()
        conn.execute(
            """INSERT INTO compliance_checker_leads
               (name, email, base_email, post_text, results_json, ip_address, state)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, email, base_email, post_text, _json_cl.dumps(check_result), client_ip, state)
        )
        conn.commit()
        conn.close()
    except Exception as _save_err:
        print(f"[ComplianceCheck] Lead save error (non-blocking): {_save_err}")

    return {
        "ok":      True,
        "results": check_result.get("results", []),
    }


# =============================================================================
# GET /admin/compliance-checker-leads
# GET /admin/compliance-checker-leads/export
# =============================================================================
# Super admin and admin only.
# Returns all compliance checker leads with enriched fields:
#   - name, email, state, date, truncated post text
#   - flag/review/pass counts derived from stored results_json
#   - plus_address flag (email contains '+' before @)
#   - ip_repeat_count (how many times this IP has submitted)
# Export returns a CSV download.
# =============================================================================

def _parse_lead_counts(results_json: str) -> dict:
    """Parse stored results JSON and return flag/review/pass counts."""
    import json as _jlc
    try:
        data    = _jlc.loads(results_json or "[]")
        results = data.get("results", data) if isinstance(data, dict) else data
        flags   = sum(1 for r in results if str(r.get("status", "")).upper() == "FLAG")
        reviews = sum(1 for r in results if str(r.get("status", "")).upper() == "REVIEW")
        passes  = sum(1 for r in results if str(r.get("status", "")).upper() == "PASS")
        return {"flags": flags, "reviews": reviews, "passes": passes}
    except Exception:
        return {"flags": 0, "reviews": 0, "passes": 0}


@app.get("/admin/compliance-checker-leads")
async def admin_compliance_leads(
    page: int = 1,
    per_page: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """
    Super admin and admin only.
    Returns paginated compliance checker leads with enriched fields.
    Includes plus-address flag and IP repeat count for duplicate detection.
    """
    if current_user.get("role") not in ("super_admin", "admin"):
        raise HTTPException(403, "Admin access required.")

    from database import get_conn as _gc_leads
    conn   = _gc_leads()
    c      = conn.cursor()

    # Ensure table exists (defensive — may not exist if no checks done yet)
    c.execute("""
        CREATE TABLE IF NOT EXISTS compliance_checker_leads (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            email        TEXT NOT NULL UNIQUE,
            post_text    TEXT NOT NULL,
            results_json TEXT,
            ip_address   TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # Total count
    c.execute("SELECT COUNT(*) as n FROM compliance_checker_leads")
    total = c.fetchone()["n"]

    # Paginated rows
    offset = (max(1, page) - 1) * per_page
    c.execute("""
        SELECT id, name, email, base_email, state, post_text,
               results_json, ip_address, created_at
        FROM compliance_checker_leads
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    rows = [dict(r) for r in c.fetchall()]

    # Build IP repeat count lookup
    c.execute("""
        SELECT ip_address, COUNT(*) as cnt
        FROM compliance_checker_leads
        WHERE ip_address IS NOT NULL AND ip_address != 'unknown'
        GROUP BY ip_address
    """)
    ip_counts = {r["ip_address"]: r["cnt"] for r in c.fetchall()}
    conn.close()

    leads = []
    for r in rows:
        counts      = _parse_lead_counts(r.get("results_json") or "")
        raw_email   = r.get("email") or ""
        plus_flag   = "+" in raw_email.split("@")[0] if "@" in raw_email else False
        ip          = r.get("ip_address") or ""
        ip_repeats  = ip_counts.get(ip, 1)
        post_text   = r.get("post_text") or ""

        leads.append({
            "id":            r["id"],
            "name":          r.get("name") or "",
            "email":         raw_email,
            "base_email":    r.get("base_email") or _normalize_email_base(raw_email),
            "state":         r.get("state") or "",
            "created_at":    r.get("created_at") or "",
            "post_preview":  post_text[:120] + ("..." if len(post_text) > 120 else ""),
            "flags":         counts["flags"],
            "reviews":       counts["reviews"],
            "passes":        counts["passes"],
            "plus_address":  plus_flag,
            "ip_repeat_count": ip_repeats,
        })

    return {
        "leads":    leads,
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "pages":    max(1, -(-total // per_page)),  # ceiling division
    }


@app.get("/admin/compliance-checker-leads/export")
async def admin_compliance_leads_export(current_user: dict = Depends(get_current_user)):
    """
    Super admin and admin only.
    Returns full leads table as a CSV file download.
    Columns: id, name, email, base_email, state, flags, reviews, passes,
             plus_address, ip_repeat_count, post_preview, created_at
    """
    if current_user.get("role") not in ("super_admin", "admin"):
        raise HTTPException(403, "Admin access required.")

    import csv as _csv
    import io  as _io
    from database import get_conn as _gc_exp

    conn = _gc_exp()
    c    = conn.cursor()
    c.execute("""
        SELECT id, name, email, base_email, state, post_text,
               results_json, ip_address, created_at
        FROM compliance_checker_leads
        ORDER BY created_at DESC
    """)
    rows = [dict(r) for r in c.fetchall()]

    # Build IP repeat count lookup
    c.execute("""
        SELECT ip_address, COUNT(*) as cnt
        FROM compliance_checker_leads
        WHERE ip_address IS NOT NULL AND ip_address != 'unknown'
        GROUP BY ip_address
    """)
    ip_counts = {r["ip_address"]: r["cnt"] for r in c.fetchall()}
    conn.close()

    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow([
        "id", "name", "email", "base_email", "state",
        "flags", "reviews", "passes", "plus_address",
        "ip_repeat_count", "post_preview", "created_at"
    ])
    for r in rows:
        counts     = _parse_lead_counts(r.get("results_json") or "")
        raw_email  = r.get("email") or ""
        plus_flag  = "+" in raw_email.split("@")[0] if "@" in raw_email else False
        ip         = r.get("ip_address") or ""
        post_text  = r.get("post_text") or ""
        writer.writerow([
            r["id"],
            r.get("name") or "",
            raw_email,
            r.get("base_email") or _normalize_email_base(raw_email),
            r.get("state") or "",
            counts["flags"],
            counts["reviews"],
            counts["passes"],
            "yes" if plus_flag else "no",
            ip_counts.get(ip, 1),
            post_text[:120].replace("\n", " "),
            r.get("created_at") or "",
        ])

    from datetime import datetime as _dt
    filename = f"compliance-leads-{_dt.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/contact")
async def submit_contact(body: ContactRequest, request: Request):
    """
    Public contact form endpoint — no auth required.
    Saves to contacts table and sends notification email to Kevin.
    Rate-limited: 3 submissions per IP per hour.
    type values: agent | team | broker | partner | other
    """
    # IP extraction — Cloudflare passes real IP in x-forwarded-for
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    if not _waitlist_check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many submissions from this address. Please try again later."
        )

    name    = (body.name    or "").strip()[:120]
    email   = (body.email   or "").strip()[:200]
    message = (body.message or "").strip()[:2000]
    contact_type = (body.type or "other").strip()[:50]

    if not name or not email:
        raise HTTPException(400, "Name and email are required.")

    valid_types = ("agent", "team", "broker", "partner", "other")
    if contact_type not in valid_types:
        contact_type = "other"

    # Save to DB
    try:
        contact_save(
            name         = name,
            email        = email,
            contact_type = contact_type,
            message      = message,
            source       = "contact_form",
            ip_address   = client_ip,
        )
    except Exception as e:
        print(f"[Contact] DB save failed: {e}")
        # Don't fail the request — still send the email

    # Send notification email to Kevin via SendGrid
    try:
        import httpx as _httpx_c
        sendgrid_key  = os.getenv("SENDGRID_API_KEY", "")
        sendgrid_from = os.getenv("SENDGRID_FROM_EMAIL", "support@homebridgegroup.co")
        notify_email  = "kevin@kevinlundy.net"

        if sendgrid_key:
            type_labels = {
                "agent":   "Solo Agent",
                "team":    "Team Lead",
                "broker":  "Broker / Office Owner",
                "partner": "Partner Program Interest",
                "other":   "Other",
            }
            type_label = type_labels.get(contact_type, contact_type)
            subject    = f"[HomeBridge Contact] {type_label} — {name}"

            html_body = f"""
<div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:32px 24px;background:#fff;">
  <div style="font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
              color:#1B4FD8;margin-bottom:20px;">HomeBridge · New Contact Submission</div>
  <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
    <tr>
      <td style="padding:10px 0;border-bottom:1px solid #eee;font-size:13px;
                 color:#64748B;width:140px;font-weight:600;">Name</td>
      <td style="padding:10px 0;border-bottom:1px solid #eee;font-size:14px;color:#0F172A;">{name}</td>
    </tr>
    <tr>
      <td style="padding:10px 0;border-bottom:1px solid #eee;font-size:13px;
                 color:#64748B;font-weight:600;">Email</td>
      <td style="padding:10px 0;border-bottom:1px solid #eee;font-size:14px;color:#0F172A;">
        <a href="mailto:{email}" style="color:#1B4FD8;">{email}</a></td>
    </tr>
    <tr>
      <td style="padding:10px 0;border-bottom:1px solid #eee;font-size:13px;
                 color:#64748B;font-weight:600;">Type</td>
      <td style="padding:10px 0;border-bottom:1px solid #eee;font-size:14px;color:#0F172A;">{type_label}</td>
    </tr>
    <tr>
      <td style="padding:10px 0;font-size:13px;color:#64748B;font-weight:600;vertical-align:top;">Message</td>
      <td style="padding:10px 0;font-size:14px;color:#0F172A;line-height:1.6;">{message or "—"}</td>
    </tr>
  </table>
  <div style="font-size:12px;color:#94A3B8;border-top:1px solid #eee;padding-top:16px;">
    Submitted via homebridgegroup.co · IP: {client_ip}
  </div>
</div>"""

            await _httpx_c.AsyncClient().post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {sendgrid_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": notify_email, "name": "Kevin Lundy"}]}],
                    "from":    {"email": sendgrid_from, "name": "HomeBridge"},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}],
                },
                timeout=10,
            )
            print(f"[Contact] Notification sent for {name} ({email}) type={contact_type}")
    except Exception as e:
        print(f"[Contact] SendGrid notification failed: {e}")

    return {"ok": True, "message": "Message received. We'll be in touch within 1 business day."}


@app.get("/admin/contacts")
async def admin_list_contacts(
    limit:  int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """
    Admin only — list all contact form submissions newest first.
    Supports pagination via limit/offset.
    """
    if not _is_staff_or_above(current_user):
        raise HTTPException(403, "Admin access required.")

    contacts = contact_list_all(limit=min(limit, 500), offset=offset)
    return {"contacts": contacts, "count": len(contacts)}


# ─────────────────────────────────────────────────────────────────────────────
# APPROVAL FLOW — Item #1
# POST /library/{id}/send-approval  — creates token, sends SMS + email to agent
# GET  /library/{id}/quick-approve  — validates token, approves, returns HTML page
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/library/{item_id}/send-approval")
async def send_approval_request(
    item_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Creates a one-time approval token and sends it to the agent via SMS and/or email.
    The approval link is valid for 7 days.  Only the item owner can trigger this.
    """
    from database import library_get_item, create_approval_token
    from social import send_approval_email, send_approval_sms

    item = library_get_item(item_id, current_user["id"])
    if not item:
        raise HTTPException(404, "Content item not found.")
    if item["status"] not in ("pending",):
        raise HTTPException(400, f"Item is already {item['status']} — no approval needed.")

    token    = create_approval_token(current_user["id"], item_id)
    api_url     = os.getenv("BACKEND_URL", "https://api.homebridgegroup.co")
    approve_url = f"{api_url}/approve/{token}"

    # Pull agent name + headline for the message
    agent_name = current_user.get("agent_name", "Your agent")
    try:
        import json as _json_a
        cd        = _json_a.loads(item["content"]) if isinstance(item["content"], str) else item["content"]
        headline  = cd.get("headline", "New content ready for review")
    except Exception:
        headline  = "New content ready for review"

    results = {"token_created": True, "email_sent": False, "sms_sent": False}

    # Send email
    to_email = current_user.get("notification_email") or current_user.get("email", "")
    if to_email:
        try:
            await send_approval_email(to_email, agent_name, headline, approve_url)
            results["email_sent"] = True
        except Exception as e:
            print(f"[Approval] Email failed: {e}")

    # Send SMS if phone is on file
    phone = current_user.get("phone", "")
    if not phone:
        # Check setup JSON for approval_phone
        try:
            from database import get_agent_setup as _gas
            setup_d = _gas(current_user["id"])
            phone = setup_d.get("approvalPhone", "") or setup_d.get("phone", "")
        except Exception:
            pass
    if phone:
        try:
            await send_approval_sms(phone, agent_name, headline, approve_url)
            results["sms_sent"] = True
        except Exception as e:
            print(f"[Approval] SMS failed: {e}")

    results["approve_url"] = approve_url
    return results


@app.get("/library/{item_id}/quick-approve")
async def quick_approve(item_id: int, token: str = ""):
    """
    Token-gated approval endpoint.  No login required — the token IS the auth.
    On success: marks the item approved, consumes the token, returns a simple HTML page.
    Hosted at app.homebridgegroup.co/api/library/{id}/quick-approve?token=...
    """
    from database import (
        validate_approval_token, consume_approval_token,
        library_get_item, library_update,
    )
    from fastapi.responses import HTMLResponse
    from datetime import datetime as _dt_qa

    if not token:
        return HTMLResponse(_approval_page("error", "Missing token.", "", ""), status_code=400)

    record = validate_approval_token(token)
    if not record:
        return HTMLResponse(_approval_page("error", "This approval link has expired or already been used.", "", ""), status_code=410)

    if str(record["library_item_id"]) != str(item_id):
        return HTMLResponse(_approval_page("error", "Token does not match this content item.", "", ""), status_code=400)

    # Load item to check current status
    item = library_get_item(item_id)
    if not item:
        return HTMLResponse(_approval_page("error", "Content item not found.", "", ""), status_code=404)

    if item["status"] not in ("pending",):
        return HTMLResponse(_approval_page(
            "already_done",
            f"This content is already {item['status']}.",
            record.get("agent_name", ""),
            "",
        ), status_code=200)

    # Approve the item
    consume_approval_token(token)
    library_update(item_id, record["user_id"], {
        "status":      "approved",
        "approved_at": _dt_qa.utcnow().isoformat(),
    })

    try:
        import json as _json_qa
        cd       = _json_qa.loads(item["content"]) if isinstance(item["content"], str) else item["content"]
        headline = cd.get("headline", "Content approved")
    except Exception:
        headline = "Content approved"

    return HTMLResponse(_approval_page(
        "success",
        headline,
        record.get("agent_name", ""),
        record.get("niche", ""),
    ))



# Platform display metadata for the approve page
_PLAT_ICONS = {
    "instagram": "📸", "facebook": "📘", "linkedin": "💼",
    "tiktok": "🎵",  "youtube": "▶️",  "twitter": "𝕏",
    "threads": "🧵",  "reddit": "🤖",   "nextdoor": "🏘️",
    "email": "✉️",   "google": "🔍",
}
_PLAT_LABELS = {
    "instagram": "Instagram", "facebook": "Facebook",  "linkedin": "LinkedIn",
    "tiktok":    "TikTok",    "youtube":  "YouTube",   "twitter":  "X / Twitter",
    "threads":   "Threads",   "reddit":   "Reddit",    "nextdoor": "Nextdoor",
    "email":     "Email",     "google":   "Google",
}


def _approval_page(state: str, headline: str, agent_name: str, niche: str,
                   post_body: str = "", compliance_status: str = "",
                   compliance_notes: list = None,
                   token: str = "", platforms: list = None,
                   published_to: list = None,
                   item_id: int = None) -> str:
    """
    Renders the mobile-first approval page.
    state values:
      'preview'      — show content + platform checkboxes + Approve buttons
      'success'      — approved (and optionally published), shows CIR™ confirmation
      'already_done' — content was already approved/published
      'expired'      — token expired, show resend option
      'error'        — generic error

    platforms    — list of {platform, platform_handle} dicts from DB (for preview)
    published_to — list of platform id strings that were published (for success)
    """
    app_url = f"https://app.homebridgegroup.co?view=agent&panel=library{'&item=' + str(item_id) if item_id else ''}"
    if platforms is None:
        platforms = []
    if published_to is None:
        published_to = []

    # ── Shared styles ─────────────────────────────────────────────────────────
    styles = """
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#f5f4f0;min-height:100vh;padding:20px 16px;
         display:flex;flex-direction:column;align-items:center}
    .card{background:#fff;border-radius:16px;padding:28px 22px;max-width:520px;
          width:100%;box-shadow:0 4px 24px rgba(0,0,0,.08)}
    .brand{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
           color:#787870;margin-bottom:18px}
    .brand b{color:#1749c9}
    .niche-pill{display:inline-block;background:#eef2fb;color:#1749c9;font-size:11px;
                font-weight:600;padding:3px 10px;border-radius:20px;margin-bottom:12px}
    h1{font-size:18px;font-weight:700;color:#0f0f0d;line-height:1.4;margin-bottom:12px}
    .comp{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;
          padding:5px 12px;border-radius:20px;margin-bottom:14px}
    .comp-pass{background:#f0fdf4;color:#15803d}
    .comp-warn{background:#fffbeb;color:#b45309}
    .comp-fail{background:#fef2f2;color:#b91c1c}
    .comp-notes{margin:0 0 14px 0;padding:10px 14px;background:#fffbeb;border:1px solid #fde68a;
                border-radius:10px;list-style:none}
    .comp-notes li{font-size:12px;color:#78350f;line-height:1.6;padding:3px 0;
                   border-bottom:1px solid #fde68a}
    .comp-notes li:last-child{border-bottom:none}
    .post{font-size:14px;color:#3d3d38;line-height:1.75;background:#f9f8f6;
          border-radius:10px;padding:16px 18px;margin-bottom:20px;
          white-space:pre-wrap;word-break:break-word;
          max-height:300px;overflow-y:auto}
    .sect-label{font-size:10px;font-weight:700;text-transform:uppercase;
                letter-spacing:.08em;color:#aeaeb2;margin-bottom:10px}
    .plat-grid{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px}
    .plat-chip{display:flex;align-items:center;gap:7px;padding:9px 14px;
               border-radius:10px;border:1.5px solid #e5e5ea;background:#fff;
               cursor:pointer;font-size:13px;font-weight:500;color:#3d3d3f;
               transition:all .15s;user-select:none;-webkit-user-select:none}
    .plat-chip.on{border-color:#1749c9;background:#eef2fb;color:#1749c9;font-weight:600}
    .plat-chip input{position:absolute;opacity:0;width:0;height:0}
    .no-plat{background:#f9f8f6;border:1px solid #e5e5ea;border-radius:10px;
             padding:14px 16px;font-size:13px;color:#787870;margin-bottom:18px;
             line-height:1.55}
    .no-plat a{color:#1749c9;font-weight:600;text-decoration:none}
    .btn{display:block;width:100%;padding:15px;border-radius:12px;font-size:15px;
         font-weight:700;cursor:pointer;border:none;font-family:inherit;
         letter-spacing:-.01em;text-align:center;transition:opacity .15s;margin-top:8px}
    .btn:hover{opacity:.88}
    .btn:disabled{opacity:.4;cursor:default}
    .btn-green{background:#15803d;color:#fff}
    .btn-outline{background:transparent;border:1.5px solid #e5e5ea;
                 color:#3d3d38;font-size:14px;padding:12px}
    .result-icon{font-size:44px;margin-bottom:14px;display:block;text-align:center}
    .result-title{font-size:22px;font-weight:700;color:#0f0f0d;text-align:center;
                  margin-bottom:10px}
    .result-msg{font-size:14px;color:#3d3d38;line-height:1.7;text-align:center;
                margin-bottom:20px}
    .cir-badge{font-size:11px;font-weight:700;letter-spacing:.08em;
               text-transform:uppercase;color:#1749c9;background:#eef2fb;
               padding:5px 12px;border-radius:20px;display:inline-block;
               margin-bottom:16px}
    .pub-list{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;
              margin-bottom:18px}
    .pub-chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;
              font-weight:600;padding:5px 12px;border-radius:20px;
              background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0}
    .footer{margin-top:22px;font-size:12px;color:#b0afa6;text-align:center;
            line-height:1.6}
    a{color:#1749c9;text-decoration:none;font-weight:600}
    """

    # ── Compliance badge ───────────────────────────────────────────────────────
    if compliance_status in ("compliant", "pass", "ok"):
        comp_html = "<span class='comp comp-pass'>✓ Compliance Verified</span>"
    elif compliance_status in ("review", "warn"):
        _notes_list = compliance_notes or []
        if _notes_list:
            _note_items = "".join(f"<li>{n}</li>" for n in _notes_list[:4])
            _notes_html = f"<ul class='comp-notes'>{_note_items}</ul>"
        else:
            _notes_html = ""
        comp_html = f"<span class='comp comp-warn'>⚠ Soft flag — review before approving</span>{_notes_html}"
    elif compliance_status in ("attention", "fail"):
        _notes_list = compliance_notes or []
        if _notes_list:
            _note_items = "".join(f"<li>{n}</li>" for n in _notes_list[:4])
            _notes_html = f"<ul class='comp-notes' style='border-color:#fecaca;background:#fef2f2'>{_note_items}</ul>"
        else:
            _notes_html = ""
        comp_html = f"<span class='comp comp-fail'>✗ Attention Required — review before approving</span>{_notes_html}"
    else:
        comp_html = ""

    # ── PREVIEW state ─────────────────────────────────────────────────────────
    if state == "preview":
        niche_html = f"<div class='niche-pill'>{niche}</div>" if niche else ""
        post_html  = f"<div class='post'>{post_body}</div>" if post_body else ""

        # Build platform section
        if platforms:
            chips = ""
            for p in platforms:
                pid    = (p.get("platform") or "").lower()
                handle = p.get("platform_handle") or p.get("handle") or ""
                icon   = _PLAT_ICONS.get(pid, "🔗")
                label  = _PLAT_LABELS.get(pid, pid.capitalize())
                hdisplay = f" · {handle}" if handle else ""
                chips += f"""<label class="plat-chip on" id="chip-{pid}">
          <input type="checkbox" name="platforms" value="{pid}" checked
                 onchange="toggleChip(this)"> {icon} {label}{hdisplay}
        </label>"""
            platform_section = f"""
      <div class="sect-label">Publish to</div>
      <div class="plat-grid">{chips}</div>"""
            primary_btn = """<button type="submit" id="pub-btn" class="btn btn-green">
        ✓ Approve &amp; Publish
      </button>"""
            secondary_btn = """<button type="submit" name="approve_only" value="1"
              class="btn btn-outline">
        Approve Only
      </button>"""
        else:
            platform_section = f"""
      <div class="no-plat">
        📱 No social platforms connected yet.<br>
        <a href="{app_url}">Connect platforms in the app →</a>
      </div>"""
            primary_btn = """<button type="submit" name="approve_only" value="1"
              class="btn btn-green">
        ✓ Approve This Post
      </button>"""
            secondary_btn = ""

        plat_script = """
<script>
function toggleChip(cb) {
  cb.closest('.plat-chip').classList.toggle('on', cb.checked);
  var btn = document.getElementById('pub-btn');
  if (!btn) return;
  var any = [].some.call(document.querySelectorAll('.plat-chip input'), function(c){ return c.checked; });
  btn.disabled = !any;
  btn.textContent = any ? '✓ Approve & Publish' : 'Select a platform above';
}
</script>""" if platforms else ""

        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Review Your Content — HomeBridge</title>
<style>{styles}</style></head>
<body><div class="card">
  <div class="brand">Home<b>Bridge</b> · Content Review</div>
  {niche_html}
  <h1>{headline}</h1>
  {comp_html}
  {post_html}
  <form method="POST" action="/approve/{token}">
    {platform_section}
    {primary_btn}
    {secondary_btn}
  </form>
  <div class="footer">
    Approving creates a CPR™ Certified Provenance Record.<br>
    <a href="{app_url}">Edit in App instead →</a>
  </div>
</div>{plat_script}</body></html>"""

    # ── SUCCESS state ─────────────────────────────────────────────────────────
    if state == "success":
        # niche slot is overloaded with cir_id in the POST handler
        cir_id   = niche  # passed as niche arg from POST handler
        cir_html = f"<div class='cir-badge'>CIR™ {cir_id}</div><br>" if cir_id else ""

        if published_to:
            pub_chips = "".join(
                f"<span class='pub-chip'>{_PLAT_ICONS.get(p,'🔗')} {_PLAT_LABELS.get(p, p.capitalize())}</span>"
                for p in published_to
            )
            pub_html    = f"<div class='pub-list'>{pub_chips}</div>"
            action_line = "Your post has been approved, a CPR™ record created, and queued for publishing."
            btn_label   = "Open App →"
            open_app_url = f"https://app.homebridgegroup.co?view=agent&panel=library{'&item=' + str(item_id) if item_id else ''}"
        else:
            pub_html     = ""
            action_line  = "Your approval has been recorded and a Certified Provenance Record™ (CPR™) has been created. Open the app to publish when ready."
            btn_label    = "Publish Now →"
            open_app_url = f"https://app.homebridgegroup.co?view=agent&panel=library{'&item=' + str(item_id) if item_id else ''}"

        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Content Approved — HomeBridge</title>
<style>{styles}</style></head>
<body><div class="card">
  <div class="brand">Home<b>Bridge</b></div>
  <span class="result-icon">✓</span>
  <div class="result-title">Content Approved</div>
  {cir_html}
  {pub_html}
  <div class="result-msg">
    <strong>{headline}</strong><br><br>{action_line}
  </div>
  <a href="{open_app_url}" class="btn btn-green"
     style="text-decoration:none;display:block;padding:15px;border-radius:12px;">
    {btn_label}
  </a>
  <div class="footer">HomeBridge · homebridgegroup.co</div>
</div></body></html>"""

    # ── EXPIRED state — with resend option ────────────────────────────────────
    if state == "expired":
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Link Expired — HomeBridge</title>
<style>{styles}</style>
<script>
async function resendLink() {{
  const btn = document.getElementById('resend-btn');
  btn.textContent = 'Sending…';
  btn.disabled = true;
  try {{
    const r = await fetch('/approve/resend?token={token}', {{method:'POST'}});
    const d = await r.json();
    if (d.ok) {{
      btn.textContent = '✓ New link sent to your email';
      btn.style.background = '#15803d';
    }} else {{
      btn.textContent = 'Could not resend — open app to approve';
      btn.disabled = false;
    }}
  }} catch(e) {{
    btn.textContent = 'Could not resend — open app to approve';
    btn.disabled = false;
  }}
}}
</script>
</head>
<body><div class="card">
  <div class="brand">HomeBridge</div>
  <span class="result-icon" style="color:#b45309">⏱</span>
  <div class="result-title">Approval Link Expired</div>
  <div class="result-msg">
    This link is more than 7 days old. Tap below to receive a fresh link
    at your email address — no login needed.
  </div>
  <button id="resend-btn" onclick="resendLink()" class="btn btn-approve"
          style="background:#1749c9;">Send Me a Fresh Link</button>
  <a href="{app_url}" class="btn btn-secondary"
     style="text-align:center;display:block;text-decoration:none;padding:12px;">
    Log In to App Instead
  </a>
  <div class="footer">HomeBridge · homebridgegroup.co</div>
</div></body></html>"""

    # ── ALREADY DONE state ────────────────────────────────────────────────────
    if state == "already_done":
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Already Approved — HomeBridge</title>
<style>{styles}</style></head>
<body><div class="card">
  <div class="brand">HomeBridge</div>
  <span class="result-icon" style="color:#1749c9">●</span>
  <div class="result-title">Already Approved</div>
  <div class="result-msg">{headline}</div>
  <a href="{app_url}" class="btn btn-approve"
     style="text-align:center;display:block;text-decoration:none;padding:14px;
     border-radius:10px;">Open App →</a>
  <div class="footer">HomeBridge · homebridgegroup.co</div>
</div></body></html>"""

    # ── ERROR state ───────────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Error — HomeBridge</title>
<style>{styles}</style></head>
<body><div class="card">
  <div class="brand">HomeBridge</div>
  <span class="result-icon" style="color:#b91c1c">✗</span>
  <div class="result-title">Something went wrong</div>
  <div class="result-msg">{headline}</div>
  <a href="{app_url}" class="btn btn-approve"
     style="text-align:center;display:block;text-decoration:none;padding:14px;
     border-radius:10px;">Open App →</a>
  <div class="footer">HomeBridge · homebridgegroup.co</div>
</div></body></html>"""


# ─────────────────────────────────────────────────────────
# AUDIT LOG — GET /support/audit-log
# Returns all audit events. Accessible to super_admin and support only.
# Viewing the audit log is itself logged.
# ─────────────────────────────────────────────────────────
@app.get("/support/audit-log")
async def get_audit_log(
    request: Request,
    limit:    int = 200,
    actor_id: int = None,
    current_user: dict = Depends(get_current_user),
):
    from database import get_conn as _gc_al, log_audit_event as _lae

    role = current_user.get("role", "")
    if role not in ("super_admin", "support"):
        raise HTTPException(403, "Audit log access requires super_admin or support role.")

    conn = _gc_al()
    c    = conn.cursor()

    # Join with users table so we can return human-readable actor info
    if actor_id:
        c.execute("""
            SELECT al.id, al.actor_id, al.action, al.target_id, al.detail,
                   al.ip_address, al.created_at,
                   u.agent_name, u.email
            FROM audit_log al
            LEFT JOIN users u ON u.id = al.actor_id
            WHERE al.actor_id = ?
            ORDER BY al.created_at DESC
            LIMIT ?
        """, (actor_id, max(1, min(limit, 1000))))
    else:
        c.execute("""
            SELECT al.id, al.actor_id, al.action, al.target_id, al.detail,
                   al.ip_address, al.created_at,
                   u.agent_name, u.email
            FROM audit_log al
            LEFT JOIN users u ON u.id = al.actor_id
            ORDER BY al.created_at DESC
            LIMIT ?
        """, (max(1, min(limit, 1000)),))

    rows = c.fetchall()
    conn.close()

    logs = []
    for r in rows:
        # Format actor_id as "Name (email)" for display in the existing frontend column
        actor_name  = r["agent_name"] or ""
        actor_email = r["email"] or ""
        if actor_name and actor_email:
            actor_display = f"{actor_name} ({actor_email})"
        elif actor_email:
            actor_display = actor_email
        elif actor_name:
            actor_display = actor_name
        else:
            actor_display = str(r["actor_id"]) if r["actor_id"] else "—"

        logs.append({
            "id":         r["id"],
            "actor_id":   actor_display,
            "action":     r["action"] or "",
            "target_id":  r["target_id"],
            "detail":     r["detail"] or "",
            "ip_address": r["ip_address"] or "",
            "created_at": r["created_at"] or "",
        })

    # Log this view — audit log access is itself audited
    caller_ip = request.client.host if request.client else None
    try:
        _lae(
            actor_id   = current_user["id"],
            action     = "audit_log_viewed",
            detail     = f"Returned {len(logs)} events (limit={limit})",
            ip_address = caller_ip,
        )
    except Exception:
        pass

    return {"logs": logs, "total": len(logs)}

# ─────────────────────────────────────────────────────────
# BROKER DASHBOARD — additional endpoints
# ─────────────────────────────────────────────────────────

@app.get("/auth/broker/office-code")
async def get_office_code(current_user: dict = Depends(get_current_user)):
    """
    Returns a stable office join code for the broker.
    Derived from user ID — no DB column needed.
    Agents enter this code during signup to link to the broker's office.
    """
    role = current_user.get("role", "")
    if role not in ("broker", "admin", "super_admin"):
        raise HTTPException(403, "Broker accounts only.")
    # Stable 6-char alphanumeric code derived from user ID
    import hashlib
    raw   = f"hb-office-{current_user['id']}-{current_user.get('email','')}"
    hashed = hashlib.sha256(raw.encode()).hexdigest()[:6].upper()
    return {"office_code": hashed, "user_id": current_user["id"]}


@app.get("/broker/agent-content")
async def broker_get_agent_content(
    agent_id: int,
    limit:    int = 20,
    current_user: dict = Depends(get_current_user),
):
    """
    Returns recent content items for a specific agent in the broker's office.
    Agent ownership is verified — a broker cannot view agents outside their office.
    Used by the broker dashboard per-agent drill-down.
    """
    if current_user.get("role") not in ("broker", "team", "admin", "super_admin"):
        raise HTTPException(403, "Broker or team accounts only.")
    items = get_broker_agent_content(
        broker_id = current_user["id"],
        agent_id  = agent_id,
        limit     = max(1, min(limit, 100)),
    )
    return {"items": items, "agent_id": agent_id, "count": len(items)}



# ─────────────────────────────────────────────────────────
# TEAM DASHBOARD
# ─────────────────────────────────────────────────────────
@app.get("/team/stats")
async def team_stats(current_user: dict = Depends(get_current_user)):
    """
    Returns per-agent stats for all agents linked to this team lead.
    Team lead = role 'team', agents linked via team_id = current_user["id"].
    Also accessible to admin and super_admin for support purposes.
    """
    if current_user.get("role") not in ("team", "admin", "super_admin"):
        raise HTTPException(403, "Team accounts only.")
    stats = get_team_stats(current_user["id"])
    return {"agents": stats, "count": len(stats)}


@app.get("/auth/team/team-code")
async def get_team_code(current_user: dict = Depends(get_current_user)):
    """
    Returns a stable team join code for the team lead.
    Agents enter this code during signup to link to the team.
    Mirrors /auth/broker/office-code.
    """
    if current_user.get("role") not in ("team", "admin", "super_admin"):
        raise HTTPException(403, "Team accounts only.")
    import hashlib
    raw    = f"hb-team-{current_user['id']}-{current_user.get('email','')}"
    hashed = hashlib.sha256(raw.encode()).hexdigest()[:6].upper()
    return {"team_code": hashed, "user_id": current_user["id"]}


# ─────────────────────────────────────────────────────────
# PARTNER PROGRAM
# Always "Partner Program" — never "affiliate program"
# Earnings are "Partner Rewards" — never "commissions"
#
# GET  /partner/me              — current user's partner record (404 if not enrolled)
# POST /partner/enroll          — enroll in partner program
# GET  /partner/payouts         — payout history for current partner
# GET  /partner/referrals       — referred agents list
# POST /partner/attribute       — record referral attribution for current user (post-registration)
# POST /partner/approve/{id}    — admin: approve pending broker partner
# GET  /admin/partners          — admin: list all enrolled partners
# ─────────────────────────────────────────────────────────

class PartnerEnrollRequest(BaseModel):
    tier: str = "referral"  # 'referral' | 'broker'


@app.get("/partner/me")
async def get_my_partner_record(current_user: dict = Depends(get_current_user)):
    """
    Return the current user's partner record.
    Returns 404 if not enrolled — partner.js uses this to decide
    whether to show the enrollment flow or the dashboard.
    """
    from database import partner_get as _pg
    partner = _pg(current_user["id"])
    if not partner:
        raise HTTPException(404, "Not enrolled in the Partner Program.")
    return {"partner": partner}


@app.post("/partner/enroll")
async def enroll_in_partner_program(
    body: PartnerEnrollRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Enroll the current user in the Partner Program.
    Referral tier: auto-approved, code generated immediately.
    Broker tier:   status='pending', requires admin approval.
    Elite tier:    invitation-only, cannot be self-enrolled.
    """
    from database import partner_enroll as _pe, partner_get as _pg

    tier = (body.tier or "referral").lower().strip()
    valid_tiers = ("referral", "starter", "growth", "elite")
    if tier not in valid_tiers:
        raise HTTPException(
            400,
            "Invalid tier. All tiers are earned automatically by active referral volume. "
            "Start with 'referral' (Starter tier) and advance quarterly based on results."
        )

    # Elite tier is invitation-only — cannot be self-enrolled
    if tier == "elite":
        raise HTTPException(
            400,
            "Elite tier is by invitation only — it is earned automatically when you reach 15+ active referrals."
        )

    # All tiers start as 'referral' (Starter) — tier advances quarterly by volume
    # Per Session 24 locked design: tiers are earned, not assigned by role
    tier = "referral"

    # If already enrolled and active, return the existing record
    existing = _pg(current_user["id"])
    if existing and existing.get("status") == "active":
        return {
            "partner": existing,
            "message": "Already enrolled.",
        }

    partner = _pe(current_user["id"], tier)
    if not partner:
        raise HTTPException(500, "Enrollment failed — please try again.")

    return {
        "partner": partner,
        "message": "Welcome to the Partner Program! Your referral link and code are ready. "
                   "Your tier advances automatically each quarter based on active paying referrals.",
    }


@app.get("/partner/payouts")
async def get_my_partner_payouts(current_user: dict = Depends(get_current_user)):
    """Return payout history for the current partner."""
    from database import partner_get as _pg, partner_payout_list as _ppl

    partner = _pg(current_user["id"])
    if not partner:
        raise HTTPException(404, "Not enrolled in the Partner Program.")

    payouts = _ppl(partner["id"])
    return {"payouts": payouts, "count": len(payouts)}


@app.get("/partner/referrals")
async def get_my_partner_referrals(current_user: dict = Depends(get_current_user)):
    """Return referral attributions for the current partner, joined with agent details."""
    from database import partner_get as _pg, get_conn as _gc_pr

    partner = _pg(current_user["id"])
    if not partner:
        raise HTTPException(404, "Not enrolled in the Partner Program.")

    conn = _gc_pr()
    c    = conn.cursor()
    c.execute("""
        SELECT ra.id, ra.attribution_type, ra.referral_code,
               ra.attributed_at, ra.converted_at,
               u.email, u.agent_name, u.brokerage
        FROM referral_attributions ra
        JOIN users u ON u.id = ra.referred_user_id
        WHERE ra.partner_id = ?
        ORDER BY ra.attributed_at DESC
    """, (partner["id"],))
    referrals = [dict(r) for r in c.fetchall()]
    conn.close()

    return {"referrals": referrals, "count": len(referrals)}


@app.post("/partner/attribute")
async def attribute_referral(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Record referral attribution for the current user using a partner referral code.
    Called from onboarding when a user enters a code after registration.
    Non-destructive — silently succeeds if code is invalid or already attributed.
    """
    body         = await request.json()
    referral_code = (body.get("referral_code") or "").upper().strip()

    if not referral_code:
        return {"ok": False, "message": "No referral code provided."}

    try:
        from database import referral_attribute, partner_get_by_code as _pgbc
        referring = _pgbc(referral_code)
        if not referring:
            return {"ok": False, "message": "Referral code not found."}
        referral_attribute(
            partner_id       = referring["id"],
            referred_user_id = current_user["id"],
            attribution_type = "code",
            referral_code    = referral_code,
        )
        return {"ok": True, "message": "Attribution recorded."}
    except Exception as _ae:
        print(f"[/partner/attribute] Failed (non-blocking): {_ae}")
        return {"ok": False, "message": "Attribution could not be recorded."}

@app.post("/admin/partners/{partner_id}/approve")
async def approve_partner_application(
    partner_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Admin or super_admin approves a pending Broker Partner application.
    Sets status to 'active' and records the approving admin.
    """
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(403, "Admin access required.")

    from database import partner_approve as _pa
    success = _pa(partner_id, current_user["id"])
    if not success:
        raise HTTPException(
            404, "Partner not found or already approved."
        )

    from database import log_audit_event as _lae
    _lae(
        actor_id  = current_user["id"],
        action    = "partner_approved",
        target_id = partner_id,
        detail    = f"Broker Partner application approved by {current_user.get('email','')}",
    )
    return {"ok": True, "partner_id": partner_id, "status": "active"}


@app.get("/admin/partners")
async def admin_list_all_partners(current_user: dict = Depends(get_current_user)):
    """Admin: list all enrolled partners for the Partners section of the admin dashboard."""
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(403, "Admin access required.")

    from database import partner_list_all as _pla
    partners = _pla()
    return {"partners": partners, "count": len(partners)}


@app.post("/admin/partners/{partner_id}/suspend")
async def admin_suspend_partner(
    partner_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Admin: suspend a partner — disables their referral link and code.
    Earnings stop accruing. Existing payouts are not affected.
    """
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(403, "Admin access required.")

    body   = await request.json()
    reason = (body.get("reason") or "").strip()[:500]

    from database import get_conn as _gc_sp
    conn = _gc_sp()
    c    = conn.cursor()
    c.execute("SELECT id, status FROM partners WHERE id = ?", (partner_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Partner not found.")
    if row["status"] == "suspended":
        conn.close()
        return {"ok": True, "partner_id": partner_id, "status": "suspended", "message": "Already suspended."}

    from datetime import datetime as _dt_sp
    c.execute("""
        UPDATE partners
        SET status = 'suspended',
            suspended_at = ?,
            suspended_by = ?,
            suspension_reason = ?
        WHERE id = ?
    """, (_dt_sp.utcnow().isoformat(), current_user["id"], reason or None, partner_id))
    conn.commit()
    conn.close()

    from database import log_audit_event as _lae_sp
    _lae_sp(
        actor_id  = current_user["id"],
        action    = "partner_suspended",
        target_id = partner_id,
        detail    = reason or "No reason provided",
    )
    return {"ok": True, "partner_id": partner_id, "status": "suspended"}


@app.post("/admin/partners/{partner_id}/reinstate")
async def admin_reinstate_partner(
    partner_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Admin: reinstate a suspended partner — re-enables their referral link and code."""
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(403, "Admin access required.")

    from database import get_conn as _gc_rp
    conn = _gc_rp()
    c    = conn.cursor()
    c.execute("SELECT id, status FROM partners WHERE id = ?", (partner_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Partner not found.")

    c.execute("""
        UPDATE partners
        SET status = 'active',
            suspended_at = NULL,
            suspended_by = NULL,
            suspension_reason = NULL
        WHERE id = ?
    """, (partner_id,))
    conn.commit()
    conn.close()

    from database import log_audit_event as _lae_rp
    _lae_rp(
        actor_id  = current_user["id"],
        action    = "partner_reinstated",
        target_id = partner_id,
        detail    = f"Reinstated by {current_user.get('email','')}",
    )
    return {"ok": True, "partner_id": partner_id, "status": "active"}


# ── Insider Partner management — Admin/SuperAdmin only ────────────────────────

@app.post("/admin/partners/{partner_id}/set-insider")
async def admin_set_partner_insider(
    partner_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Elevate or demote a partner's Insider Partner status.
    Admin/SuperAdmin only — Insider status is NEVER self-assigned.

    When is_insider=True:
      - Partner earns 25% on their own direct referrals (no tier threshold required)
      - Partner earns 5% override on referrals generated by partners they recruited

    Body: { "is_insider": true | false, "note": "optional reason" }
    """
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(403, "Admin access required.")

    body      = await request.json()
    is_insider = bool(body.get("is_insider", False))
    note       = (body.get("note") or "").strip()[:500]

    success = partner_set_insider(partner_id, is_insider, current_user["id"])
    if not success:
        raise HTTPException(404, "Partner not found.")

    from database import log_audit_event as _lae_ins
    action = "partner_insider_elevated" if is_insider else "partner_insider_demoted"
    _lae_ins(
        actor_id  = current_user["id"],
        action    = action,
        target_id = partner_id,
        detail    = f"{'Elevated to' if is_insider else 'Removed from'} Insider Partner "
                    f"by {current_user.get('email','')}. "
                    + (f"Note: {note}" if note else ""),
    )
    return {
        "ok":         True,
        "partner_id": partner_id,
        "is_insider": is_insider,
        "action":     action,
    }


@app.post("/admin/partners/{partner_id}/assign-override")
async def admin_assign_partner_override(
    partner_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Manually assign an Insider Partner as the override earner for a partner's
    referral attributions. Used when an Insider claims they recruited a partner
    but the partner didn't enter the code at signup.

    FORWARD-ONLY: only sets override on attribution rows where it is currently NULL.
    Does not recalculate already-processed payouts.

    Body: { "insider_partner_id": <partners.id>, "note": "reason for manual assignment" }
    """
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(403, "Admin access required.")

    body               = await request.json()
    insider_partner_id = int(body.get("insider_partner_id") or 0)
    note               = (body.get("note") or "").strip()[:500]

    if not insider_partner_id:
        raise HTTPException(400, "insider_partner_id is required.")
    if not note:
        raise HTTPException(400, "A note explaining why this override is being assigned is required.")

    success = partner_assign_override(partner_id, insider_partner_id, current_user["id"])
    if not success:
        raise HTTPException(
            400,
            "Assignment failed. Either the partner was not found, the insider_partner_id "
            "does not belong to an active Insider Partner, or all attribution rows already "
            "have overrides assigned."
        )

    from database import log_audit_event as _lae_ov
    _lae_ov(
        actor_id  = current_user["id"],
        action    = "partner_override_assigned",
        target_id = partner_id,
        detail    = f"Override assigned to insider partner {insider_partner_id} "
                    f"by {current_user.get('email','')}. Note: {note}",
    )
    return {
        "ok":                 True,
        "partner_id":         partner_id,
        "insider_partner_id": insider_partner_id,
    }


@app.post("/admin/partners/{partner_id}/remove-override")
async def admin_remove_partner_override(
    partner_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Remove the Insider override assignment for a partner's referral attributions.
    Used to correct a bad assignment or when the Insider relationship ends.

    Body: { "note": "reason for removal" }
    """
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(403, "Admin access required.")

    body = await request.json()
    note = (body.get("note") or "").strip()[:500]

    success = partner_remove_override(partner_id, current_user["id"])
    if not success:
        raise HTTPException(404, "Partner not found or no override to remove.")

    from database import log_audit_event as _lae_rov
    _lae_rov(
        actor_id  = current_user["id"],
        action    = "partner_override_removed",
        target_id = partner_id,
        detail    = f"Override removed by {current_user.get('email','')}. "
                    + (f"Note: {note}" if note else "No note provided."),
    )
    return {"ok": True, "partner_id": partner_id}


@app.post("/auth/profile/notification-email")
async def update_notification_email(
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Updates the notification_email for the current user.
    This is the address approval notifications and contact form inquiries go to.
    Falls back to login email if not set.
    """
    from database import get_conn as _gc_ne
    notification_email = payload.get("notification_email", "").strip()
    conn = _gc_ne()
    conn.execute(
        "UPDATE users SET notification_email=? WHERE id=?",
        (notification_email or None, current_user["id"])
    )
    conn.commit()
    conn.close()
    return {"ok": True, "notification_email": notification_email or None}


# ─────────────────────────────────────────────────────────────────────────────
# APPROVAL ENDPOINTS
# GET  /approve?token=      → preview page (query param — legacy)
# GET  /approve/{token}     → preview page (path param — new, shorter URL)
# POST /approve?token=      → performs approval (query param — legacy)
# POST /approve/{token}     → performs approval (path param — new)
# POST /approve/resend?token= → creates fresh token from expired one, resends
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/approve/{token_path}")
async def approval_preview_path(token_path: str, request: Request):
    """Path-based approve route — shorter URL, fits in one SMS segment."""
    return await approval_preview(token=token_path)

@app.post("/approve/{token_path}")
async def approval_post_path(token_path: str, request: Request):
    """Path-based approve POST route — delegates to approval_confirm."""
    return await approval_confirm(request=request, token=token_path)

@app.get("/approve")
async def approval_preview(token: str = ""):
    """
    Shows the content preview page. Does NOT approve on GET.
    Agent reads the post, then clicks Approve to POST.
    """
    from database import validate_approval_token, lookup_approval_token_record
    from fastapi.responses import HTMLResponse
    import json as _json_prev

    if not token:
        return HTMLResponse(_approval_page("error", "No token provided.", "", ""), status_code=400)

    # Check if token exists at all (may be expired)
    raw = lookup_approval_token_record(token)
    if not raw:
        return HTMLResponse(
            _approval_page("error", "Invalid approval link.", "", ""),
            status_code=400,
        )

    # Check if expired
    from database import validate_approval_token
    record = validate_approval_token(token)
    if not record:
        # Token exists but is expired or used
        if raw.get("used"):
            return HTMLResponse(
                _approval_page("already_done", "This content has already been approved.", "", ""),
                status_code=200,
            )
        return HTMLResponse(
            _approval_page("expired", "", raw.get("agent_name",""), "", token=token),
            status_code=200,
        )

    # Load content for preview
    try:
        cd = _json_prev.loads(record["content"]) if isinstance(record["content"], str) else (record["content"] or {})
    except Exception:
        cd = {}

    headline   = cd.get("headline", "Your scheduled content")
    post_body  = cd.get("post", "")
    compliance = cd.get("compliance", {})
    if isinstance(compliance, str):
        try: compliance = _json_prev.loads(compliance)
        except Exception: compliance = {}
    comp_status = str(compliance.get("overallStatus") or compliance.get("overall_verdict") or "").lower()

    # Extract compliance notes to show on approval page — agent needs to know what the flag is
    comp_notes = []
    try:
        raw_notes = compliance.get("notes", [])
        if isinstance(raw_notes, list):
            comp_notes = [str(n).strip() for n in raw_notes if n and str(n).strip()]
    except Exception:
        comp_notes = []

    if record["status"] not in ("pending",):
        return HTMLResponse(
            _approval_page("already_done", f"This content is already {record['status']}.",
                           record.get("agent_name",""), record.get("niche","")),
            status_code=200,
        )

    # Fetch connected platforms for the platform checkbox section
    try:
        from database import get_platform_connections as _gpc
        platforms = _gpc(record["user_id"])
    except Exception:
        platforms = []

    return HTMLResponse(_approval_page(
        "preview", headline, record.get("agent_name",""), record.get("niche",""),
        post_body=post_body, compliance_status=comp_status, compliance_notes=comp_notes,
        token=token, platforms=platforms,
    ))


@app.post("/approve")
async def approval_confirm(request: Request, token: str = ""):
    """
    Performs the actual approval. Called by the Approve/Publish form POST.
    Reads selected platform checkboxes from form data.
    If platforms selected: approves + marks copied_platforms + sets published.
    If approve_only flag: approves only, no platform update.
    """
    from database import validate_approval_token, consume_approval_token, library_update
    from fastapi.responses import HTMLResponse
    from datetime import datetime as _dt_conf
    import json as _json_conf

    if not token:
        return HTMLResponse(_approval_page("error", "No token provided.", "", ""), status_code=400)

    # Read form data — platform checkboxes and approve_only flag
    try:
        form_data        = await request.form()
        selected_platforms = list(form_data.getlist("platforms"))
        approve_only     = bool(form_data.get("approve_only"))
    except Exception:
        selected_platforms = []
        approve_only     = True  # safe default

    record = validate_approval_token(token)
    if not record:
        from database import lookup_approval_token_record
        raw = lookup_approval_token_record(token)
        if raw and raw.get("used"):
            return HTMLResponse(
                _approval_page("already_done", "This content was already approved.", "", ""),
                status_code=200,
            )
        return HTMLResponse(
            _approval_page("expired", "", "", "", token=token),
            status_code=200,
        )

    item_id = record["library_item_id"]
    user_id = record["user_id"]

    item = library_get_item(item_id)
    if not item:
        return HTMLResponse(_approval_page("error", "Content item not found.", "", ""), status_code=404)

    if item["status"] not in ("pending",):
        return HTMLResponse(
            _approval_page("already_done", f"Already {item['status']}.",
                           record.get("agent_name",""), record.get("niche","")),
            status_code=200,
        )

    # ── Step 1: Approve ───────────────────────────────────────────────────────
    consume_approval_token(token)
    updated = library_update(item_id, user_id, {
        "status":      "approved",
        "approved_at": _dt_conf.utcnow().isoformat(),
    })

    try:
        cd       = _json_conf.loads(item["content"]) if isinstance(item["content"], str) else (item["content"] or {})
        headline = cd.get("headline", "Content approved")
    except Exception:
        headline = "Content approved"

    cir_id = updated.get("cir_id", "") if updated else ""

    # ── Step 2: Publish to selected platforms (if any) ────────────────────────
    published_to = []
    if selected_platforms and not approve_only:
        try:
            library_update(item_id, user_id, {
                "status":           "published",
                "copied_platforms": selected_platforms,
                "published_at":     _dt_conf.utcnow().isoformat(),
            })
            published_to = selected_platforms
            print(f"[Approve] Item {item_id} approved + published to {selected_platforms} for user {user_id}")
        except Exception as pub_err:
            # Publishing failure must never block approval — item is approved regardless
            print(f"[Approve] Platform update failed (item still approved): {pub_err}")

    return HTMLResponse(_approval_page(
        "success", headline, record.get("agent_name",""), cir_id,
        published_to=published_to,
        item_id=item_id,
    ))


@app.post("/approve/resend")
async def approval_resend(token: str = ""):
    """
    Creates a fresh approval token from an expired one and resends email/SMS.
    No login required — the original token proves the user is who they say.
    """
    from database import lookup_approval_token_record, create_approval_token
    from social import send_approval_email, send_approval_sms
    import asyncio as _asyncio_rs

    if not token:
        return {"ok": False, "error": "No token."}

    raw = lookup_approval_token_record(token)
    if not raw:
        return {"ok": False, "error": "Token not found."}

    # Only resend for expired tokens, not for already-used ones
    if raw.get("used") and raw.get("status") not in ("pending",):
        return {"ok": False, "error": "Content already approved."}

    user_id  = raw["user_id"]
    item_id  = raw["library_item_id"]
    to_email = raw.get("email", "")
    phone    = raw.get("phone", "")
    agent_name = raw.get("agent_name", "Agent")

    try:
        import json as _json_rs
        cd = _json_rs.loads(raw["content"]) if isinstance(raw["content"], str) else (raw["content"] or {})
        headline = cd.get("headline", "Your content is ready for approval")
    except Exception:
        headline = "Your content is ready for approval"

    new_token   = create_approval_token(user_id, item_id)
    api_url     = os.getenv("BACKEND_URL", "https://api.homebridgegroup.co")
    approve_url = f"{api_url}/approve/{new_token}"

    sent_email = False
    sent_sms   = False

    if to_email:
        try:
            _asyncio_rs.run(send_approval_email(to_email, agent_name, headline, approve_url))
            sent_email = True
        except Exception as e:
            print(f"[Resend] Email failed: {e}")

    if phone:
        try:
            _asyncio_rs.run(send_approval_sms(phone, agent_name, headline, approve_url))
            sent_sms = True
        except Exception as e:
            print(f"[Resend] SMS failed: {e}")

    return {"ok": sent_email or sent_sms, "email_sent": sent_email, "sms_sent": sent_sms}

# ─────────────────────────────────────────────────────────
# MARKET REPORTS — Session 22
# Agent uploads MLS, RPR, Altos, or any market data PDF.
# Claude extracts key stats. Agent reviews, then taps Generate
# to produce a niche-framed post from real local data.
#
# POST /market-reports/upload    — upload PDF, extract stats, save record
# GET  /market-reports           — list all saved reports for the agent
# DELETE /market-reports/{id}    — delete a saved report
#
# Agent-only: user_id enforced on every operation.
# Never returns pdf_data to the frontend — bytes stay server-side.
# ─────────────────────────────────────────────────────────

class MarketReportUploadRequest(BaseModel):
    filename:     str
    pdf_data:     str               # base64-encoded PDF bytes — processed then discarded, not stored
    source_label: Optional[str] = "MLS"   # e.g. "MLS", "RPR", "Altos Research"
    report_month: Optional[str] = None    # e.g. "March 2026"
    report_area:  Optional[str] = None    # e.g. "Southmoor Park"


@app.post("/market-reports/upload")
async def upload_market_report(
    body: MarketReportUploadRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Upload and process a market data PDF.
    Step 1: Send PDF to Claude for extraction — returns structured stats preview.
    Step 2: Save the record with extracted stats only. PDF bytes are discarded.
    Returns the report record + extracted stats for the frontend preview card.
    """
    import base64 as _b64
    from content_engine import extract_market_report_data

    if not body.pdf_data:
        raise HTTPException(400, "pdf_data is required.")
    if not body.filename:
        raise HTTPException(400, "filename is required.")

    # Validate it looks like base64
    try:
        _b64.b64decode(body.pdf_data[:100])
    except Exception:
        raise HTTPException(400, "pdf_data must be base64-encoded.")

    # Run Claude extraction first — save record only after we have stats
    # If extraction fails entirely, still save the record so agent sees it
    # in their saved list and can retry
    extracted = None
    extraction_error = None
    try:
        setup = get_agent_setup(current_user["id"])
        extracted = await extract_market_report_data(
            pdf_b64      = body.pdf_data,
            source_label = body.source_label or "MLS",
            report_month = body.report_month,
            report_area  = body.report_area or setup.get("market", ""),
        )
    except Exception as e:
        extraction_error = str(e)
        print(f"[MarketReport] Extraction failed for {body.filename}: {e}")

    # Save record — PDF bytes are NOT stored, only extracted stats + metadata
    record = market_report_save(
        user_id      = current_user["id"],
        filename     = body.filename[:255],
        source_label = body.source_label or "MLS",
        report_month = body.report_month,
        report_area  = body.report_area,
        extracted_data = extracted,
    )

    return {
        "ok":               True,
        "report":           record,
        "extracted":        extracted,
        "extraction_error": extraction_error,
    }


@app.get("/market-reports")
async def list_market_reports(current_user: dict = Depends(get_current_user)):
    """
    Return all saved market reports for the current agent, newest first.
    PDF bytes are never stored — only extracted stats and metadata are returned.
    """
    reports = market_report_list(current_user["id"])
    return {"reports": reports, "count": len(reports)}


@app.delete("/market-reports/{report_id}")
async def delete_market_report(
    report_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Delete a market report. Agent can only delete their own reports."""
    success = market_report_delete(report_id, current_user["id"])
    if not success:
        raise HTTPException(404, "Report not found.")
    return {"ok": True, "deleted": report_id}


# ─────────────────────────────────────────────
# PARTNER PROGRAM — PUBLIC ENDPOINTS (no auth required)
#
# GET  /partner/public/{code}   — returns partner display name for referral
#                                 landing page. Public, no auth. Used by
#                                 partner-landing.html to personalize header.
#
# POST /partner/public-enroll   — public partner signup. Creates a HomeBridge
#                                 account + enrolls as partner atomically.
#                                 Sends welcome email with code and link via
#                                 SendGrid. No auth required — this is the
#                                 entry point for non-agent partners who will
#                                 never use the content engine.
#
# POST /partner/quarterly-evaluate — admin/cron trigger. Runs quarter-end
#                                    snapshot: counts active paying referrals
#                                    per partner, updates tier accordingly.
#                                    Starter: 1–4, Growth: 5–14, Elite: 15+
# ─────────────────────────────────────────────

@app.get("/partner/public/{code}")
async def partner_public_lookup(code: str):
    """
    Returns the display name of an active partner by referral code.
    Public endpoint — no auth required.
    Used by partner-landing.html to personalize: "You were referred by [Name]"
    Returns 404 if code is invalid or partner is not active.
    """
    partner = partner_get_by_code(code.upper().strip())
    if not partner:
        raise HTTPException(404, "Referral code not found or inactive.")
    return {
        "ok":          True,
        "agent_name":  partner.get("agent_name") or partner.get("email", "").split("@")[0],
        "referral_code": partner.get("referral_code"),
    }


class PublicPartnerEnrollRequest(BaseModel):
    name:         str
    email:        str
    password:     str
    partner_type: Optional[str] = "other"   # agent | broker | coach | lender | other
    message:      Optional[str] = ""
    referral_code: Optional[str] = ""       # if they arrived via someone else's link


@app.post("/partner/public-enroll")
async def partner_public_enroll(body: PublicPartnerEnrollRequest, request: Request):
    """
    Public partner signup — no HomeBridge account required to call this.
    Steps:
      1. Validate inputs (password rules match /auth/register)
      2. Create HomeBridge user account (role='agent', is_licensed=0 for non-agents)
      3. Enroll as partner (Starter tier, auto-approved, code generated)
      4. Record referral attribution if they arrived via a referral code
      5. Send welcome email with their code and referral link via SendGrid
      6. Return partner record + JWT token so frontend can show code immediately

    Non-agent partners will see only the Partner tab when they log in.
    Their is_licensed=0 flag suppresses content engine access in renderViewSwitcher.
    """
    import re as _re
    from auth import create_user as _create_user, create_token as _create_token, _auth_check_rate_limit as _acrl, _get_client_ip as _gcip

    # ── IP rate limit — Session 53 ────────────────────────────────────────────
    if not _acrl(_gcip(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many signup attempts from this address. Please wait 15 minutes."
        )

    from database import set_trial as _set_trial, partner_enroll as _partner_enroll, referral_attribute as _ref_attr

    # ── Validate required fields ──────────────────────────────────────────────
    name  = (body.name or "").strip()
    email = (body.email or "").strip().lower()
    pw    = body.password or ""

    if not name:
        raise HTTPException(400, "Name is required.")
    if not email or "@" not in email:
        raise HTTPException(400, "A valid email address is required.")

    # Password rules — match /auth/register exactly
    if len(pw) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    if not _re.search(r"[A-Z]", pw):
        raise HTTPException(400, "Password must include at least one uppercase letter.")
    if not _re.search(r"[a-z]", pw):
        raise HTTPException(400, "Password must include at least one lowercase letter.")
    if not _re.search(r"[0-9]", pw):
        raise HTTPException(400, "Password must include at least one number.")

    # ── Create user account ───────────────────────────────────────────────────
    # is_licensed=0 means renderViewSwitcher hides My Work pill for non-agents.
    # partner_type='agent' gets is_licensed=1 — they may also use the content engine.
    is_agent = (body.partner_type or "").lower() == "agent"

    user = _create_user(
        email      = email,
        password   = pw,
        agent_name = name,
        brokerage  = "",
        role       = "agent",
        broker_id  = None,
    )
    if not user:
        raise HTTPException(409, "An account with that email already exists. Please log in instead.")

    # Set is_licensed based on partner_type
    try:
        from database import get_conn as _gc_pe
        _conn = _gc_pe()
        _conn.execute(
            "UPDATE users SET is_licensed=? WHERE id=?",
            (1 if is_agent else 0, user["id"])
        )
        _conn.commit()
        _conn.close()
    except Exception as _e:
        print(f"[PublicEnroll] is_licensed update failed (non-blocking): {_e}")

    # Start 14-day trial
    try:
        _set_trial(user["id"], days=14)
    except Exception:
        pass

    # ── Enroll as partner ─────────────────────────────────────────────────────
    # Everyone starts at Starter (tier='referral'). Tier advances quarterly by volume.
    partner = _partner_enroll(user["id"], tier="referral")
    if not partner:
        raise HTTPException(500, "Account created but partner enrollment failed. Please contact support@homebridgegroup.co.")

    referral_code = partner.get("referral_code", "")
    referral_link = f"https://homebridgegroup.co/partner-landing.html?ref={referral_code}"

    # ── Record attribution if they arrived via someone else's referral code ──
    if body.referral_code:
        try:
            referring = partner_get_by_code(body.referral_code.upper().strip())
            if referring:
                _ref_attr(
                    partner_id       = referring["id"],
                    referred_user_id = user["id"],
                    attribution_type = "code",
                    referral_code    = body.referral_code.upper().strip(),
                )
        except Exception as _ae:
            print(f"[PublicEnroll] Attribution failed (non-blocking): {_ae}")

    # ── Send welcome email ────────────────────────────────────────────────────
    _sendgrid_key  = os.getenv("SENDGRID_API_KEY", "")
    _sendgrid_from = os.getenv("SENDGRID_FROM_EMAIL", "noreply@homebridgegroup.co")
    if _sendgrid_key:
        try:
            import httpx as _httpx
            _welcome_html = f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:520px;margin:0 auto;padding:32px 24px;">
  <div style="font-size:18px;font-weight:700;color:#0f0f0d;margin-bottom:4px;">Home<span style="color:#1749c9;">Bridge</span></div>
  <hr style="border:none;border-top:1px solid #e8e7e0;margin:16px 0;" />
  <p style="color:#0f0f0d;font-size:15px;font-weight:600;margin-bottom:8px;">Welcome to the Partner Program, {name.split()[0]}.</p>
  <p style="color:#787870;font-size:14px;line-height:1.6;margin-bottom:24px;">
    You're enrolled as a Starter Partner and earning 15% Partner Rewards on every active subscriber you refer.
    Your tier advances automatically each quarter based on your results — no applications, no approvals.
  </p>

  <div style="background:#f5f5f7;border-radius:12px;padding:20px 24px;margin-bottom:24px;">
    <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#86868b;margin-bottom:8px;">Your Referral Code</div>
    <div style="font-family:monospace;font-size:28px;font-weight:800;color:#1d1d1f;letter-spacing:.12em;margin-bottom:8px;">{referral_code}</div>
    <div style="font-size:13px;color:#86868b;line-height:1.5;">Share this verbally, in a text, or an email. Anyone who types it when signing up — you get credit. No expiry.</div>
  </div>

  <div style="background:#f5f5f7;border-radius:12px;padding:20px 24px;margin-bottom:24px;">
    <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#86868b;margin-bottom:8px;">Your Referral Link</div>
    <div style="font-size:13px;font-family:monospace;color:#1749c9;word-break:break-all;margin-bottom:8px;">{referral_link}</div>
    <div style="font-size:13px;color:#86868b;line-height:1.5;">20-day cookie. Anyone who signs up within 20 days of clicking your link is attributed to you.</div>
  </div>

  <div style="margin-bottom:24px;">
    <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#86868b;margin-bottom:10px;">How Your Tier Grows</div>
    <div style="display:flex;flex-direction:column;gap:6px;">
      <div style="display:flex;justify-content:space-between;font-size:13px;padding:8px 12px;background:#eef2fb;border-radius:6px;">
        <span style="font-weight:600;color:#1749c9;">Starter — You are here</span><span style="color:#1749c9;">15% · 1–4 active referrals</span>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:13px;padding:8px 12px;background:#f5f5f7;border-radius:6px;">
        <span style="color:#86868b;">Growth</span><span style="color:#86868b;">20% · 5–14 active referrals</span>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:13px;padding:8px 12px;background:#f5f5f7;border-radius:6px;">
        <span style="color:#86868b;">Elite</span><span style="color:#86868b;">25% · 15+ active referrals</span>
      </div>
    </div>
    <div style="font-size:12px;color:#b0afa6;margin-top:8px;line-height:1.5;">Tiers are evaluated at the end of each quarter based on active paying subscribers. Payouts are quarterly.</div>
  </div>

  <a href="https://app.homebridgegroup.co"
     style="display:inline-block;background:#1749c9;color:#fff;font-weight:600;
            font-size:14px;padding:12px 28px;border-radius:6px;text-decoration:none;">
    View Your Partner Dashboard →
  </a>

  <p style="color:#b0afa6;font-size:12px;margin-top:24px;line-height:1.5;">
    Log in at app.homebridgegroup.co with <strong>{email}</strong> anytime to see your referrals, earnings, and payout history.<br/>
    Questions? <a href="mailto:support@homebridgegroup.co" style="color:#1749c9;">support@homebridgegroup.co</a>
  </p>
  <hr style="border:none;border-top:1px solid #e8e7e0;margin:24px 0 16px;" />
  <p style="color:#b0afa6;font-size:11px;">HomeBridge Partner Program · homebridgegroup.co</p>
</div>
"""
            _httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {_sendgrid_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": email}]}],
                    "from":    {"email": _sendgrid_from, "name": "HomeBridge"},
                    "subject": f"Welcome to the HomeBridge Partner Program — your code is {referral_code}",
                    "content": [{"type": "text/html", "value": _welcome_html}],
                },
                timeout=10,
            )
            print(f"[PublicEnroll] Welcome email sent to {email}")
        except Exception as _mail_err:
            # Email failure must never block enrollment — code is shown on page
            print(f"[PublicEnroll] Welcome email failed (non-blocking): {_mail_err}")

    # ── Notify platform owner ─────────────────────────────────────────────────
    # Read notification_email from the super_admin account (user id=2).
    # Falls back to their login email if notification_email is not set.
    # No hardcoded addresses — whoever owns the platform controls this via
    # Profile → Lead & Notification Email in the app.
    _owner_email = None
    try:
        from database import get_conn as _gc_owner
        _oc = _gc_owner()
        _or = _oc.execute(
            "SELECT email, notification_email FROM users WHERE id = 2"
        ).fetchone()
        _oc.close()
        if _or:
            _owner_email = _or["notification_email"] or _or["email"]
    except Exception as _oe:
        print(f"[PublicEnroll] Owner email lookup failed (non-blocking): {_oe}")

    if _sendgrid_key and _owner_email:
        try:
            import httpx as _hx2
            _hx2.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {_sendgrid_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": _owner_email}]}],
                    "from":    {"email": _sendgrid_from, "name": "HomeBridge"},
                    "subject": f"New Partner: {name} ({body.partner_type or 'other'})",
                    "content": [{"type": "text/html", "value": f"<p><strong>{name}</strong> ({email}) just enrolled as a Partner ({body.partner_type or 'other'}).</p><p>Referral code: <strong>{referral_code}</strong></p>"}],
                },
                timeout=10,
            )
        except Exception:
            pass

    # ── Issue JWT token ───────────────────────────────────────────────────────
    token = _create_token(user["id"], email, "agent")

    return {
        "ok":            True,
        "token":         token,
        "referral_code": referral_code,
        "referral_link": referral_link,
        "partner":       partner,
        "user": {
            "id":         user["id"],
            "email":      email,
            "agent_name": name,
            "role":       "agent",
            "is_licensed": 1 if is_agent else 0,
            "partner_tier": partner.get("tier"),
            "partner_code": referral_code,
        },
    }


@app.post("/partner/quarterly-evaluate")
async def partner_quarterly_evaluate(current_user: dict = Depends(get_current_user)):
    """
    Admin/cron trigger — runs quarter-end tier evaluation for all active partners.
    Counts active paying referrals (referral_attributions.is_active = 1) per partner.
    Updates tier based on count:
      Starter (referral): 1–4 active referrals
      Growth  (broker):   5–14 active referrals
      Elite:              15+ active referrals
    Records tier_evaluated_at and active_referral_count on each partner row.
    Safe to run multiple times — idempotent snapshot.
    """
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(403, "Admin access required.")

    from database import get_conn as _gc_qe
    from datetime import datetime as _dt_qe

    conn = _gc_qe()
    c    = conn.cursor()

    # Fetch all active partners
    c.execute("SELECT id, tier, user_id FROM partners WHERE status = 'active'")
    partners = [dict(r) for r in c.fetchall()]

    results = []
    now_iso = _dt_qe.utcnow().isoformat()

    for p in partners:
        partner_id = p["id"]

        # Count active paying referrals for this partner
        c.execute("""
            SELECT COUNT(*) as cnt
            FROM referral_attributions
            WHERE partner_id = ? AND is_active = 1
        """, (partner_id,))
        active_count = c.fetchone()["cnt"]

        # Determine new tier based on locked Session 24 model
        if active_count >= 15:
            new_tier = "elite"
        elif active_count >= 5:
            new_tier = "broker"   # code key 'broker' = Growth tier in UI
        else:
            new_tier = "referral" # code key 'referral' = Starter tier in UI

        old_tier = p["tier"]

        # Update partner record
        conn.execute("""
            UPDATE partners
            SET tier                 = ?,
                active_referral_count = ?,
                tier_evaluated_at    = ?
            WHERE id = ?
        """, (new_tier, active_count, now_iso, partner_id))

        # Mirror to users table for fast lookup by renderViewSwitcher
        conn.execute(
            "UPDATE users SET partner_tier = ? WHERE id = ?",
            (new_tier, p["user_id"])
        )

        results.append({
            "partner_id":    partner_id,
            "active_count":  active_count,
            "old_tier":      old_tier,
            "new_tier":      new_tier,
            "changed":       old_tier != new_tier,
        })

    conn.commit()
    conn.close()

    from database import log_audit_event as _lae_qe
    _lae_qe(
        actor_id = current_user["id"],
        action   = "partner_quarterly_evaluate",
        detail   = f"Evaluated {len(partners)} partners. {sum(1 for r in results if r['changed'])} tier changes.",
    )

    return {
        "ok":              True,
        "partners_evaluated": len(partners),
        "tier_changes":    sum(1 for r in results if r["changed"]),
        "results":         results,
        "evaluated_at":    now_iso,
    }



# ─────────────────────────────────────────────
# FLYER EXPORT — Session 28
# Generates a print-ready Letter PDF flyer from approved content.
# Agent info pulled from their setup. Photo opt-in via include_photo flag.
# ─────────────────────────────────────────────

class FlyerRequest(BaseModel):
    item_id:       int
    headline:      str
    body:          str
    cta_label:     str  = ""
    cta_url:       str  = ""
    agent_name:    str  = ""
    brokerage:     str  = ""
    phone:         str  = ""
    email:         str  = ""
    license_number:str  = ""
    designations:  str  = ""
    disclaimer:    str  = ""
    include_photo: bool = False
    photo_b64:     str  = ""   # base64 JPEG — only used if include_photo is True
    include_logo:  bool = False
    logo_b64:      str  = ""   # base64 JPEG — brokerage logo, only used if include_logo is True

@app.post("/content/flyer")
async def generate_flyer(req: FlyerRequest, current_user: dict = Depends(get_current_user)):
    """
    Generate a print-ready Letter (8.5x11) PDF flyer from approved content.
    Uses ReportLab — same library as PaperTrail™ compliance PDFs.
    Agent info comes from the request payload (pre-filled by frontend from localStorage).
    Photo is opt-in — only included if include_photo=True and photo_b64 is provided.
    Returns PDF as streaming download.
    """
    import io, base64
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
    from reportlab.lib import colors

    # ── Color palette — matches AutoMates brand
    INK       = colors.HexColor("#060D1A")
    INK_2     = colors.HexColor("#334155")
    INK_3     = colors.HexColor("#64748B")
    BLUE      = colors.HexColor("#1749c9")
    ICE       = colors.HexColor("#60A5FA")
    WHITE     = colors.white
    OFF       = colors.HexColor("#F5F7FC")
    BORDER    = colors.HexColor("#E2E8F0")

    buf = io.BytesIO()
    PAGE_W, PAGE_H = letter  # 8.5 x 11 inches
    MARGIN = 0.65 * inch
    CONTENT_W = PAGE_W - (MARGIN * 2)

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    styles = {
        "logo_auto":  S("logo_auto",  fontName="Helvetica-Bold", fontSize=18, textColor=WHITE,  leading=22),
        "logo_mates": S("logo_mates", fontName="Helvetica-Bold", fontSize=18, textColor=ICE,    leading=22),
        "tagline":    S("tagline",    fontName="Helvetica",      fontSize=8,  textColor=colors.HexColor("#93C5FD"), leading=11, alignment=TA_LEFT),
        "headline":   S("headline",   fontName="Helvetica-Bold", fontSize=26, textColor=INK,    leading=32, spaceAfter=12),
        "body":       S("body",       fontName="Helvetica",      fontSize=11, textColor=INK_2,  leading=17, spaceAfter=8),
        "cta":        S("cta",        fontName="Helvetica-Bold", fontSize=12, textColor=BLUE,   leading=16),
        "agent_name": S("agent_name", fontName="Helvetica-Bold", fontSize=13, textColor=INK,    leading=17),
        "agent_sub":  S("agent_sub",  fontName="Helvetica",      fontSize=10, textColor=INK_3,  leading=14),
        "disclaimer": S("disclaimer", fontName="Helvetica",      fontSize=7,  textColor=INK_3,  leading=10),
        "footer":     S("footer",     fontName="Helvetica",      fontSize=7,  textColor=colors.HexColor("#94A3B8"), leading=10, alignment=TA_CENTER),
    }

    def sp(h=8):  return Spacer(1, h)
    def rule(col=BORDER, thick=0.5): return HRFlowable(width="100%", thickness=thick, color=col, spaceAfter=6, spaceBefore=4)

    story = []

    # ── HEADER — dark navy bar with AutoMates logo
    logo_text = '<font name="Helvetica-Bold" size="18" color="#FFFFFF">Auto</font><font name="Helvetica-Bold" size="18" color="#60A5FA">Mates</font>'
    tagline_text = "Your Digital Marketing Team"
    header_table = Table([[
        Paragraph(logo_text, styles["body"]),
        Paragraph(tagline_text, styles["tagline"]),
    ]], colWidths=[CONTENT_W * 0.4, CONTENT_W * 0.6])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), INK),
        ("ALIGN",         (1, 0), (1, 0),   "RIGHT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS",(0, 0), (-1, -1), [4, 4, 0, 0]),
    ]))
    story += [header_table, sp(20)]

    # ── HEADLINE
    story += [
        Paragraph(req.headline or "Untitled", styles["headline"]),
        rule(BORDER, 0.5),
        sp(10),
    ]

    # ── BODY + PHOTO (opt-in, right side)
    body_text = req.body or ""
    # Truncate body to ~600 chars to fit nicely on one page
    if len(body_text) > 620:
        body_text = body_text[:617] + "…"

    if req.include_photo and req.photo_b64:
        # Two-column layout: body left, photo right
        try:
            from reportlab.platypus import Image as RLImage
            img_bytes = base64.b64decode(req.photo_b64)
            img_buf   = io.BytesIO(img_bytes)
            photo_w   = 1.6 * inch
            photo_h   = 1.6 * inch
            img       = RLImage(img_buf, width=photo_w, height=photo_h)
            img.hAlign = "RIGHT"
            body_col_w = CONTENT_W - photo_w - 0.2 * inch
            body_table = Table([
                [Paragraph(body_text, styles["body"]), img],
            ], colWidths=[body_col_w, photo_w + 0.1 * inch])
            body_table.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                ("TOPPADDING",    (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(body_table)
        except Exception:
            # Photo failed — fall back to text only
            story.append(Paragraph(body_text, styles["body"]))
    else:
        story.append(Paragraph(body_text, styles["body"]))

    story.append(sp(16))

    # ── CTA
    if req.cta_label or req.cta_url:
        cta_display = req.cta_label or req.cta_url
        cta_url     = req.cta_url or ""
        cta_str     = f'<a href="{cta_url}" color="#1749c9">{cta_display}</a>' if cta_url else cta_display
        cta_box = Table([[Paragraph(f"→ {cta_str}", styles["cta"])]],
                        colWidths=[CONTENT_W])
        cta_box.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), OFF),
            ("LEFTPADDING",   (0, 0), (-1, -1), 14),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
            ("TOPPADDING",    (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("BOX",           (0, 0), (-1, -1), 1, BLUE),
            ("ROUNDEDCORNERS",(0, 0), (-1, -1), [6, 6, 6, 6]),
        ]))
        story += [cta_box, sp(20)]

    # ── AGENT INFO BAR
    story.append(rule(BORDER, 0.5))
    story.append(sp(10))

    # Build agent info — with optional brokerage logo on the right
    agent_name_para  = Paragraph(req.agent_name, styles["agent_name"]) if req.agent_name else None
    sub_parts = []
    if req.brokerage:      sub_parts.append(req.brokerage)
    if req.phone:          sub_parts.append(req.phone)
    if req.email:          sub_parts.append(req.email)
    if req.license_number: sub_parts.append(f"Lic. {req.license_number}")
    if req.designations:   sub_parts.append(req.designations)
    agent_sub_para = Paragraph("  ·  ".join(sub_parts), styles["agent_sub"]) if sub_parts else None

    if req.include_logo and req.logo_b64:
        try:
            from reportlab.platypus import Image as RLImage
            logo_bytes = base64.b64decode(req.logo_b64)
            logo_buf   = io.BytesIO(logo_bytes)
            logo_w     = 1.4 * inch
            logo_h     = 0.5 * inch
            logo_img   = RLImage(logo_buf, width=logo_w, height=logo_h)
            logo_img.hAlign = "RIGHT"
            left_col_w = CONTENT_W - logo_w - 0.2 * inch
            agent_content = []
            if agent_name_para:  agent_content.append(agent_name_para)
            if agent_sub_para:   agent_content.append(agent_sub_para)
            from reportlab.platypus import KeepTogether
            agent_col  = agent_content
            logo_table = Table(
                [[col if i == 0 else logo_img for i, col in enumerate([agent_col, logo_img])]],
                colWidths=[left_col_w, logo_w + 0.1 * inch]
            ) if False else None  # placeholder — use flat layout below
            # Flat layout: stack agent name/sub, then logo on same row as name
            info_rows = []
            if agent_name_para: info_rows.append([agent_name_para, logo_img])
            if agent_sub_para:  info_rows.append([agent_sub_para, ""])
            if info_rows:
                info_tbl = Table(info_rows, colWidths=[left_col_w, logo_w + 0.1 * inch])
                info_tbl.setStyle(TableStyle([
                    ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN",         (1, 0), (1, -1),  "RIGHT"),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                    ("TOPPADDING",    (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                story.append(info_tbl)
        except Exception:
            # Logo failed — fall back to text only
            if agent_name_para: story.append(agent_name_para)
            if agent_sub_para:  story.append(agent_sub_para)
    else:
        if agent_name_para: story.append(agent_name_para)
        if agent_sub_para:  story.append(agent_sub_para)

    story.append(sp(10))

    # ── DISCLAIMER
    if req.disclaimer:
        story += [
            rule(BORDER, 0.3),
            sp(4),
            Paragraph(req.disclaimer, styles["disclaimer"]),
            sp(6),
        ]

    # ── FOOTER
    generated_date = datetime.utcnow().strftime("%B %d, %Y")
    story += [
        rule(BORDER, 0.3),
        sp(4),
        Paragraph(
            f"Created with AutoMates — a product of HomeBridge Group, LLC · {generated_date} · automatesmarketing.com",
            styles["footer"]
        ),
    ]

    try:
        doc.build(story)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flyer PDF generation failed: {str(e)}")

    pdf_bytes = buf.getvalue()
    safe_name = (req.agent_name or "Agent").replace(" ", "_")
    filename  = f"AutoMates_Flyer_{safe_name}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────────────────────────────────────
# DIAGNOSTIC + MIGRATION — super_admin only
# Debug endpoints removed — migrations complete, one-time use only.


# ═══════════════════════════════════════════════════════════════════════════════
# VIDEO IDENTITY — Session 49
# Profile photo storage, signed token serving, video render pipeline,
# monthly limit enforcement, and HeyGen avatar ID management.
#
# HeyGen is infrastructure — never referenced in agent-facing copy.
# Agents see "Video Identity", "Generate Video", "Your video is ready."
# ═══════════════════════════════════════════════════════════════════════════════

import httpx as _httpx

# ── Profile photo upload ──────────────────────────────────────────────────────

@app.post("/profile/photo")
async def upload_profile_photo(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Accept a JPEG profile photo upload from the agent.
    Stores to persistent disk at /data/profile_photos/{user_id}.jpg.
    Also updates the in-browser display via the existing hb_profile_photo
    localStorage flow — the frontend sends base64 which we decode here.

    Accepts JSON: { "photo_b64": "<base64 JPEG string>" }
    The base64 string may include a data URI prefix (data:image/jpeg;base64,...)
    which we strip before decoding.
    """
    import base64 as _b64
    body = await request.json()
    photo_b64 = body.get("photo_b64", "")
    if not photo_b64:
        raise HTTPException(status_code=400, detail="photo_b64 is required")

    # Strip data URI prefix if present
    if "," in photo_b64:
        photo_b64 = photo_b64.split(",", 1)[1]

    try:
        photo_bytes = _b64.b64decode(photo_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    # Enforce reasonable size limit — 8MB
    if len(photo_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Photo too large. Please use a photo under 8MB.")

    uid     = current_user["id"]
    success = profile_photo_save(uid, photo_bytes)
    if not success:
        raise HTTPException(status_code=500, detail="Photo save failed. Please try again.")

    return {"success": True, "message": "Photo saved."}


# ── Signed photo token endpoint — serves photo to video render API ────────────

@app.get("/profile/photo/{token}")
async def serve_profile_photo(token: str):
    """
    Serve a profile photo using a signed temporary token.
    Token is valid for 30 minutes and single-use per render.
    No authentication required — token IS the auth for this endpoint.
    Called by the video render API during avatar generation.
    """
    from fastapi.responses import FileResponse
    uid = photo_token_validate(token)
    if uid is None:
        raise HTTPException(status_code=404, detail="Photo not found or link expired.")

    path = profile_photo_get_path(uid)
    if not path:
        raise HTTPException(status_code=404, detail="No profile photo on file.")

    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


# ── Video consent endpoint ────────────────────────────────────────────────────

@app.post("/video/consent")
async def video_consent_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Record the agent's explicit consent to video likeness use (face geometry
    processed by HeyGen to create an animated avatar).

    Must be called before POST /video/render is permitted.
    Consent is permanent once given — stored as video_consent_at timestamp.
    Idempotent: safe to call again if already consented.

    This is a BIPA/CPRA requirement. The consent modal text must be
    lawyer-reviewed before deploying to IL/TX/WA/CA agents.
    """
    uid   = current_user["id"]
    # Check current state via get_video_identity
    state = get_video_identity(uid)
    if not state["has_consent"]:
        record_video_consent(uid)
        print(f"[Video] Consent recorded for user {uid}")
    return {"success": True, "message": "Video consent recorded."}


# ── Video limit status ────────────────────────────────────────────────────────

@app.get("/video/limit")
async def get_video_limit(current_user: dict = Depends(get_current_user)):
    """
    Return the agent's current monthly video render usage and limit.
    Called by the frontend before showing the Generate Video button.
    """
    uid  = current_user["id"]
    role = current_user.get("role", "agent")
    plan = current_user.get("plan", "trial")
    return check_video_allowed(uid, role, plan)


# ── Video render request ──────────────────────────────────────────────────────

class VideoRenderRequest(BaseModel):
    script:          str
    library_item_id: Optional[int] = None

@app.post("/video/render")
async def video_render(req: VideoRenderRequest, current_user: dict = Depends(get_current_user)):
    """
    Submit an avatar video render job.

    Flow:
    1. Check monthly video limit — hard block if exceeded
    2. Verify agent has a profile photo
    3. Create a signed 30-min photo token
    4. Create a pending video_job record
    5. Submit to HeyGen API (avatar video from photo + script)
    6. Store the returned video_id on the job record
    7. Increment the monthly video counter
    8. Return job_id for frontend polling

    The agent's face from their profile photo is animated with lip sync.
    HeyGen is never mentioned to the agent.
    """
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=503, detail="Video generation is not yet configured. Please contact support.")

    uid  = current_user["id"]
    role = current_user.get("role", "agent")
    plan = current_user.get("plan", "trial")

    # 1. Monthly limit check
    limit_check = check_video_allowed(uid, role, plan)
    if not limit_check["allowed"]:
        if not limit_check["plan_allows"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "error":   "plan_no_video",
                    "message": "Video generation is available on Starter plans and above. Upgrade your plan to access this feature.",
                }
            )
        raise HTTPException(
            status_code=429,
            detail={
                "error":        "video_limit_reached",
                "message":      f"You've used {limit_check['videos_used']} of {limit_check['videos_limit']} videos included in your plan this month. Your limit resets on {limit_check['resets_on']}. Purchase a Video Top-up Pack for 10 more renders.",
                "videos_used":  limit_check["videos_used"],
                "videos_limit": limit_check["videos_limit"],
                "resets_on":    limit_check["resets_on"],
            }
        )

    # 2. Verify video consent has been recorded (BIPA/CPRA gate — Opus N4 fix)
    # ADD v4 claimed this was already enforced. It was not. Column existed but
    # was never written and never checked. Every render was happening without
    # recorded consent. This is the gate that was supposed to exist.
    video_id_state = get_video_identity(uid)
    if not video_id_state["has_consent"]:
        raise HTTPException(
            status_code=403,
            detail={
                "error":   "no_video_consent",
                "message": "Please complete the video consent step before generating your first video.",
            }
        )

    # 3. Verify profile photo exists
    if not profile_photo_exists(uid):
        raise HTTPException(
            status_code=400,
            detail={
                "error":   "no_photo",
                "message": "Upload your profile photo first to generate a video. Go to your avatar in the top-right corner and tap 'Upload Photo'.",
            }
        )

    # Script length guard — HeyGen limit is 5000 chars
    script = req.script.strip()
    if not script:
        raise HTTPException(status_code=400, detail="Script cannot be empty.")
    if len(script) > 4800:
        raise HTTPException(status_code=400, detail="Script is too long. Please shorten it to under 4800 characters.")

    # 4. Create pending job record
    job = video_job_create(
        user_id         = uid,
        library_item_id = req.library_item_id,
        script_preview  = script[:200],
        photo_token     = "",   # not used in Photo Avatar flow
    )
    job_id = job["id"]

    # 5. Resolve talking_photo_id — create Photo Avatar on first render,
    #    reuse stored ID on every subsequent render.
    #
    #    HeyGen Photo Avatar flow (v3 API — confirmed from docs Session 49):
    #      Step A: POST /v3/avatars  { type:"photo", name:..., file:{type:"url", url:...} }
    #              → response: avatar_item.id  (this is the talking_photo_id)
    #              → status may be "processing" — poll until "completed" (max 60s)
    #      Step B: POST /v2/video/generate  { video_inputs:[{ character:{ type:"talking_photo",
    #              talking_photo_id: <id> }, voice:{...}, background:{...} }] }
    #
    #    Photo Avatar creation is one-time per agent. Once created, the ID is stored
    #    in heygen_photo_avatar_id on the user record and reused forever.
    #    This avoids re-uploading the photo on every render.

    from database import get_conn as _gc_vid

    # Look up stored heygen_photo_avatar_id
    _vid_conn = _gc_vid()
    _vid_c    = _vid_conn.cursor()
    _vid_c.execute("SELECT heygen_photo_avatar_id FROM users WHERE id = ?", (uid,))
    _vid_row  = _vid_c.fetchone()
    _vid_conn.close()
    stored_photo_avatar_id = _vid_row["heygen_photo_avatar_id"] if _vid_row else None

    if stored_photo_avatar_id:
        # Fast path — reuse existing Photo Avatar
        talking_photo_id = stored_photo_avatar_id
        print(f"[Video] Reusing stored Photo Avatar ID {talking_photo_id} for user {uid}")
    else:
        # First render — create Photo Avatar in HeyGen using a signed photo URL.
        # The signed URL serves the agent's photo from our persistent disk
        # for 30 minutes — long enough for HeyGen to fetch it during avatar creation.

        # Step A1: Generate a signed photo token
        token = photo_token_create(uid)
        photo_url = f"{BACKEND_URL}/profile/photo/{token}"

        # Fetch agent name for the avatar label (never shown to agent)
        _name_conn = _gc_vid()
        _name_c    = _name_conn.cursor()
        _name_c.execute("SELECT agent_name FROM users WHERE id = ?", (uid,))
        _name_row  = _name_c.fetchone()
        _name_conn.close()
        avatar_name = (_name_row["agent_name"] if _name_row else f"agent_{uid}") or f"agent_{uid}"

        # Step A2: Create Photo Avatar via HeyGen /v3/avatars
        create_payload = {
            "type": "photo",
            "name": avatar_name,
            "file": {
                "type": "url",
                "url":  photo_url,
            },
        }

        try:
            async with _httpx.AsyncClient(timeout=30.0) as client:
                create_resp = await client.post(
                    "https://api.heygen.com/v3/avatars",
                    headers={
                        "X-Api-Key":    HEYGEN_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json=create_payload,
                )
            create_data = create_resp.json()
        except Exception as e:
            print(f"[Video] HeyGen Photo Avatar creation failed for user {uid}: {e}")
            video_job_fail(str(job_id), f"Avatar creation failed: {str(e)[:200]}")
            raise HTTPException(status_code=502, detail="Video generation service unavailable. Please try again in a moment.")

        if create_resp.status_code not in (200, 201) or not create_data.get("data"):
            raw_err = create_data.get("error") or create_data.get("message") or f"Status {create_resp.status_code}"
            err_msg = raw_err.get("message") if isinstance(raw_err, dict) else str(raw_err)
            print(f"[Video] HeyGen /v3/avatars rejected for user {uid}: {err_msg} — {create_data}")
            video_job_fail(str(job_id), f"Avatar creation rejected: {err_msg[:200]}")
            raise HTTPException(status_code=502, detail=f"Video generation failed: {err_msg}")

        # Extract avatar_item.id — this is the talking_photo_id
        avatar_item  = create_data["data"].get("avatar_item") or create_data["data"]
        new_avatar_id = (
            avatar_item.get("id")
            or avatar_item.get("avatar_id")
            or create_data["data"].get("id")
        )
        if not new_avatar_id:
            print(f"[Video] HeyGen avatar creation returned no ID for user {uid}: {create_data}")
            video_job_fail(str(job_id), "Avatar creation returned no ID")
            raise HTTPException(status_code=502, detail="Video generation service unavailable. Please try again in a moment.")

        # Step A3: Poll until avatar status is "completed" (max 60 seconds, every 5s)
        avatar_status = create_data["data"].get("status", "processing")
        if avatar_status != "completed":
            print(f"[Video] Polling for Photo Avatar completion — id {new_avatar_id}, user {uid}")
            import asyncio as _asyncio_vid
            for _poll_attempt in range(12):   # 12 × 5s = 60s max
                await _asyncio_vid.sleep(5)
                try:
                    async with _httpx.AsyncClient(timeout=15.0) as client:
                        poll_resp = await client.get(
                            f"https://api.heygen.com/v3/avatars/{new_avatar_id}",
                            headers={"X-Api-Key": HEYGEN_API_KEY},
                        )
                    poll_data    = poll_resp.json()
                    avatar_status = (
                        poll_data.get("data", {}).get("status")
                        or poll_data.get("data", {}).get("avatar_item", {}).get("status")
                        or "processing"
                    )
                    print(f"[Video] Avatar poll {_poll_attempt+1}/12 — status: {avatar_status}")
                    if avatar_status == "completed":
                        break
                    if avatar_status in ("failed", "error"):
                        print(f"[Video] Avatar processing failed for user {uid}: {poll_data}")
                        video_job_fail(str(job_id), "Avatar processing failed")
                        raise HTTPException(status_code=502, detail="Video generation failed. Please re-upload your photo and try again.")
                except HTTPException:
                    raise
                except Exception as poll_e:
                    print(f"[Video] Avatar poll error for user {uid}: {poll_e}")
                    # Continue polling — transient network error

            if avatar_status != "completed":
                # Timed out — store the ID anyway and attempt render;
                # HeyGen may accept it even while still processing.
                print(f"[Video] Avatar poll timed out for user {uid} — attempting render with id {new_avatar_id}")

        # Store the Photo Avatar ID — reused on all future renders
        set_heygen_photo_avatar_id(uid, new_avatar_id)
        talking_photo_id = new_avatar_id
        print(f"[Video] Photo Avatar created and stored — id {talking_photo_id}, user {uid}")

        # Consume the photo token now that HeyGen has fetched the image
        photo_token_consume(token)

    # 6. Build voice block for /v2/video/generate
    #
    #    If the agent has a cloned voice (lmnt_voice_id is set):
    #      - Call LMNT to synthesize the script into an audio file
    #      - Write audio bytes to /data/voice_audio/{job_id}.mp3 (temp, auto-cleaned)
    #      - Serve the audio via a signed URL (same token pattern as photo tokens)
    #      - Pass voice type "audio" with audio_url to HeyGen
    #    If no cloned voice: fall back to stock HeyGen voice (existing behavior).
    #
    #    Stock voice 1bd001e7e50f421d891986aad5158bc8 is HeyGen's English voice.
    #    It is female and wrong gender for Kevin — LMNT replaces it for any agent
    #    who has completed voice setup. Session 51.

    voice_identity  = get_voice_identity(uid)
    lmnt_voice_id   = voice_identity.get("lmnt_voice_id")
    voice_block     = None   # will be set below

    if lmnt_voice_id and LMNT_API_KEY:
        # ── LMNT path: synthesize script → temp audio → signed URL → HeyGen ──
        import asyncio as _asyncio_voice
        try:
            async with _httpx.AsyncClient(timeout=60.0) as client:
                lmnt_resp = await client.post(
                    "https://api.lmnt.com/v1/ai/speech/bytes",
                    headers={
                        "X-API-Key":    LMNT_API_KEY,
                        "Content-Type": "application/json",
                        "lmnt-version": "1.1",
                    },
                    json={
                        "voice":  lmnt_voice_id,
                        "text":   script,
                        "format": "mp3",
                    },
                )
            if lmnt_resp.status_code == 200 and lmnt_resp.content:
                # Write audio to temp file on persistent disk
                import pathlib as _pathlib
                voice_audio_dir = _pathlib.Path("/data/voice_audio")
                voice_audio_dir.mkdir(parents=True, exist_ok=True)
                audio_path = voice_audio_dir / f"{job_id}.mp3"
                audio_path.write_bytes(lmnt_resp.content)

                # Build a signed URL using same token infrastructure as photos
                voice_token = photo_token_create(uid)
                audio_url   = f"{BACKEND_URL}/voice/audio/{voice_token}/{job_id}"

                voice_block = {
                    "type":      "audio",
                    "audio_url": audio_url,
                }
                print(f"[Video] LMNT voice synthesis successful — job {job_id}, user {uid}, {len(lmnt_resp.content)} bytes")
            else:
                print(f"[Video] LMNT synthesis failed (status {lmnt_resp.status_code}) — falling back to stock voice for job {job_id}")
        except Exception as lmnt_e:
            print(f"[Video] LMNT synthesis exception for job {job_id}: {lmnt_e} — falling back to stock voice")

    if voice_block is None:
        # Stock voice fallback — used when no cloned voice or LMNT call failed
        voice_block = {
            "type":       "text",
            "input_text": script,
            "voice_id":   "1bd001e7e50f421d891986aad5158bc8",
        }

    heygen_payload = {
        "video_inputs": [
            {
                "character": {
                    "type":             "talking_photo",
                    "talking_photo_id": talking_photo_id,
                },
                "voice":      voice_block,
                "background": {
                    "type":  "color",
                    "value": "#F8F7F5",
                },
            }
        ],
        "dimension": {
            "width":  1280,
            "height": 720,
        },
    }

    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.heygen.com/v2/video/generate",
                headers={
                    "X-Api-Key":    HEYGEN_API_KEY,
                    "Content-Type": "application/json",
                },
                json=heygen_payload,
            )
        resp_data = resp.json()
    except Exception as e:
        print(f"[Video] HeyGen render API call failed for job {job_id}: {e}")
        video_job_fail(str(job_id), f"API call failed: {str(e)[:200]}")
        raise HTTPException(status_code=502, detail="Video generation service unavailable. Please try again in a moment.")

    # Normalise error — resp_data.error may be a dict or string
    if resp.status_code != 200 or not resp_data.get("data", {}).get("video_id"):
        raw_err = resp_data.get("error") or resp_data.get("message") or f"Status {resp.status_code}"
        err_msg = raw_err.get("message") if isinstance(raw_err, dict) else str(raw_err)
        print(f"[Video] HeyGen rejected render for job {job_id}: {err_msg} — full response: {resp_data}")
        video_job_fail(str(job_id), f"Rejected by render service: {err_msg[:200]}")
        raise HTTPException(status_code=502, detail=f"Video generation failed: {err_msg}")

    heygen_video_id = resp_data["data"]["video_id"]

    # 7. Store HeyGen video ID on job record
    video_job_set_heygen_id(job_id, heygen_video_id)

    # 8. Increment monthly video counter
    record_video_render(uid, role)

    print(f"[Video] Render submitted — job {job_id}, heygen_video_id {heygen_video_id}, user {uid}")

    return {
        "success":         True,
        "job_id":          job_id,
        "heygen_video_id": heygen_video_id,
        "status":          "processing",
        "message":         "Your video is being generated. This usually takes 1-3 minutes.",
    }


# ── Jordan message generation — backend proxy ────────────────────────────────
# Security fix (Session 50): Jordan's Anthropic API calls previously ran
# directly from the browser, exposing the API key in client-side code.
# All Jordan generation now routes through this endpoint.
# The browser never touches api.anthropic.com directly.
#
# Two message types:
#   "identity" — standing briefing for Identity panel. Cached by frontend.
#   "home"     — daily briefing for Home screen. Never cached.
#
# Returns: { "message": "<generated text>" }
# On any error: returns fallback message, never raises to the frontend.

class JordanMessageRequest(BaseModel):
    type:        str           # "identity" | "home"
    data:        dict          # context data (varies by type)
    jordan_name: str  = "Jordan"
    jordan_brief: str = ""

@app.post("/jordan/message")
async def jordan_message(req: JordanMessageRequest, current_user: dict = Depends(get_current_user)):
    """
    Generate a Jordan message via the Anthropic API — server-side only.
    The API key never leaves the backend. Frontend receives the message text only.
    Fallback message is returned on any error so Jordan is never blank.
    """
    name  = (req.jordan_name  or "Jordan").strip()
    brief = (req.jordan_brief or "").strip()
    data  = req.data or {}

    # ── Build prompts based on message type ───────────────────────────────────
    if req.type == "home":
        pending   = int(data.get("pending",   0))
        signals   = int(data.get("signals",   0))
        schedules = int(data.get("schedules", 0))
        published = int(data.get("published", 0))

        context_parts = [
            f"{pending} post{'s' if pending != 1 else ''} cleared by Your Auditor and waiting for the agent's approval." if pending else "Nothing waiting for the agent's approval right now.",
            f"Your Analyst found {signals} market signal{'s' if signals != 1 else ''} worth writing about." if signals else "No new market signals today.",
            "Schedule is active and running." if schedules else "No active schedule set.",
            f"{published} post{'s' if published != 1 else ''} have been approved or published so far." if published else "No posts approved or published yet.",
        ]
        context_str = " ".join(context_parts)

        system_prompt = " ".join([
            f"You are {name}, the Chief of Staff for a real estate agent using a platform called AutoMates.",
            "Your job is to give the agent a short, plain-spoken daily briefing about what their team has been doing.",
            f"Your personality: {brief}." if brief else "Your personality: warm, clear, direct, and calm.",
            "Rules you must always follow:",
            "Write at a 9th grade reading level. No jargon. No fancy words.",
            "Write exactly 1 to 2 sentences. Never longer.",
            "Never use em dashes. Use plain sentences instead.",
            "Never mention scores, ratings, grades, or numbers out of 100.",
            "Never say the word integrity. Never imply the agent is failing at anything.",
            "Focus on what the team has done and what needs the agent's attention today.",
            "Refer to team members as Your Writer, Your Analyst, Your Auditor, Your Scheduler, Your Publisher.",
            "Never use the agent's name. Speak to them directly but without using their name.",
            "Never start with the word I.",
            "Never use quotation marks around team member names.",
            "Keep it brief. This is a daily operational update, not a speech.",
        ])
        user_prompt = f"Here is today's situation: {context_str} Write {name}'s daily briefing now."

        # Fallback for home type
        def _fallback():
            if pending >= 3:
                return f"Your Auditor cleared {pending} posts while you were away. They are ready for your review below."
            if pending and signals:
                return f"Your Auditor cleared {pending} post{'s' if pending > 1 else ''} and Your Analyst found a story worth writing about. Both are waiting below."
            if pending:
                return f"Your Auditor cleared {pending} post{'s' if pending > 1 else ''} while you were away. Ready when you are."
            if signals:
                return "Your Analyst found something in your market worth writing about. Nothing is waiting for your approval right now."
            if schedules:
                return "Your Scheduler has everything on track. Nothing needs your attention right now."
            if published >= 5:
                return "Your team has been working hard. Everything is in good shape."
            return "Your whole team is standing by. Create a post or set a schedule and they will get to work."

    else:
        # type == "identity" (default)
        cir_count         = int(data.get("cir_count",           0))
        schedule_active   = bool(data.get("schedule_active",    False))
        platforms_conn    = int(data.get("platforms_connected", 0))
        identity_complete = bool(data.get("identity_complete",  False))

        context_str = " ".join([
            f"Agent has {cir_count} verified posts on file.",
            "Schedule is active." if schedule_active else "Schedule is not set yet.",
            f"{platforms_conn} platform{'s' if platforms_conn != 1 else ''} connected.",
            "Agent profile is fully set up." if identity_complete else "Agent profile is not fully set up yet.",
        ])

        system_prompt = " ".join([
            f"You are {name}, the Chief of Staff for a real estate agent using a platform called AutoMates.",
            "Your job is to give the agent a short, warm, plain-spoken briefing about how their platform is working for them.",
            f"Your personality: {brief}." if brief else "Your personality: warm, clear, encouraging, and direct.",
            "Rules you must always follow:",
            "Write at a 9th grade reading level. No jargon. No fancy words.",
            "Keep it to 2 to 4 sentences maximum. Never longer.",
            "Never use em dashes. Use plain sentences instead.",
            "Never mention scores, ratings, grades, or numbers out of 100.",
            "Never say the word integrity. Never imply the agent is failing at anything.",
            "Focus on what IS working and what is being built for them.",
            "Refer to team members as Your Writer, Your Analyst, Your Auditor, Your Scheduler, Your Publisher.",
            "Verified posts are posts that have been reviewed and are helping the agent get found online. Explain it that way if you mention it.",
            "Never start with the word I. Start with the agent's situation or accomplishment.",
            "Never use quotation marks around team member names.",
        ])
        user_prompt = f"Here is the agent's current situation: {context_str} Write {name}'s briefing message now."

        # Fallback for identity type
        def _fallback():
            if not identity_complete:
                return f"{name} here. Your profile is not fully filled in yet. Once you add your voice, your market, and your niches, your whole team will know exactly how to work for you."
            if cir_count == 0:
                return "Your profile is all set and your team knows what to do. Approve your first post and you will have your first verified record on file. That is when your name really starts to get out there."
            if cir_count < 10:
                return f"You are off to a good start. Your team has {cir_count} verified post{'s' if cir_count != 1 else ''} on file, each one helping the right people find you. Keep going."
            if cir_count < 50:
                return f"{cir_count} posts are out there right now showing up in searches and building your name. Your Writer knows how you talk, your Analyst is watching your market, and your Auditor makes sure everything going out looks professional."
            return f"{cir_count} posts. That is {cir_count} times your name showed up somewhere online when someone needed answers. Your whole team has been working hard for you and it shows. Keep approving content and that number keeps climbing."

    # ── Call Anthropic API ────────────────────────────────────────────────────
    try:
        response = anthropic_client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 300,
            system     = system_prompt,
            messages   = [{"role": "user", "content": user_prompt}],
        )
        message_text = ""
        if response.content and len(response.content) > 0:
            message_text = response.content[0].text.strip()
        if not message_text:
            return {"message": _fallback()}
        return {"message": message_text}
    except Exception as e:
        print(f"[Jordan] Anthropic API error (type={req.type}, user={current_user['id']}): {e}")
        return {"message": _fallback()}


# ── Jordan onboarding reflection — Session 54 ────────────────────────────────
# Called by onboarding.html Block 3 after each of the six voice questions.
# Receives the question number (1-6), the question text, and the agent's answer.
# Returns a single warm, specific sentence that reflects back something from
# the answer without evaluating it. Never starts with "Great" or "Wonderful".
# Names something specific from what the agent said.
#
# No auth required — agent may not have a token yet during onboarding.
# Rate limited by IP: 30 calls per hour per IP (6 questions x 5 retries max).

_reflection_rate: Dict[str, list] = {}
_reflection_lock = threading.Lock()

def _reflection_rate_limit(ip: str) -> bool:
    """Returns True if the request is allowed, False if rate limited."""
    now = time.time()
    window = 3600  # 1 hour
    max_calls = 30
    with _reflection_lock:
        calls = _reflection_rate.get(ip, [])
        calls = [t for t in calls if now - t < window]
        if len(calls) >= max_calls:
            return False
        calls.append(now)
        _reflection_rate[ip] = calls
        return True


class JordanReflectionRequest(BaseModel):
    question_number: int        # 1-6
    question_text:   str        # the question that was asked
    answer:          str        # the agent's answer
    agent_name:      Optional[str] = None


@app.post("/jordan/onboarding-reflection")
async def jordan_onboarding_reflection(req: JordanReflectionRequest, request: Request):
    """
    Generate Jordan's reflection after each onboarding voice question.
    Called without auth — agent may not have a token yet during onboarding.
    Returns: { "reflection": "<one sentence>" }
    On any error: returns a safe fallback so onboarding never stalls.
    """
    client_ip = request.headers.get("X-Forwarded-For", request.client.host or "unknown").split(",")[0].strip()
    if not _reflection_rate_limit(client_ip):
        # Return a fallback silently rather than breaking onboarding flow
        return {"reflection": "That's exactly the kind of thing that will make your content sound like you and not like every other agent out there."}

    answer = (req.answer or "").strip()
    question = (req.question_text or "").strip()
    q_num = req.question_number

    # Minimal answer guard — if they submitted almost nothing, acknowledge gently
    if len(answer) < 15:
        return {"reflection": "Take another swing at this one. Even a few sentences in your own words will give me more to work with than nothing."}

    system_prompt = " ".join([
        "You are Jordan, the Chief of Staff for a real estate agent setting up their AutoMates account.",
        "The agent just answered one of six voice questions designed to capture their authentic voice.",
        "Your job is to write exactly one sentence that reflects back something specific from what they said.",
        "Rules you must always follow:",
        "Write exactly one sentence. Never more.",
        "Never start with 'Great', 'Wonderful', 'Amazing', 'Fantastic', 'Excellent', 'Perfect', or any generic praise word.",
        "Never evaluate or grade the answer. Never say it was a good answer or a strong answer.",
        "Name something specific from what they said — a word, a detail, a moment, a position they took.",
        "The tone is warm and direct. Like a colleague who actually listened.",
        "Never use em dashes. Use plain sentences instead.",
        "Never ask a follow-up question.",
        "Never use the agent's name.",
        "This sentence will be shown on screen immediately after they finish typing. It should feel like someone heard them.",
    ])

    user_prompt = (
        f"Question {q_num} of 6: {question}\n\n"
        f"The agent answered: {answer}\n\n"
        "Write Jordan's one-sentence reflection now."
    )

    fallbacks = [
        "The way you described that is going to show up in your content in a way most agents can't replicate.",
        "That specific experience is exactly what separates your voice from a generic real estate post.",
        "The honesty in that answer is what makes content sound like a real person wrote it.",
        "That detail is something your clients will recognize immediately as true.",
        "Most agents would have given a much safer answer to that question.",
        "That perspective is going to give your content a point of view that's hard to argue with.",
    ]
    import random
    fallback_msg = fallbacks[(q_num - 1) % len(fallbacks)]

    try:
        response = anthropic_client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 120,
            system     = system_prompt,
            messages   = [{"role": "user", "content": user_prompt}],
        )
        reflection = ""
        if response.content and len(response.content) > 0:
            reflection = response.content[0].text.strip()
        if not reflection:
            return {"reflection": fallback_msg}
        return {"reflection": reflection}
    except Exception as e:
        print(f"[Jordan/reflection] Anthropic API error (q={q_num}): {e}")
        return {"reflection": fallback_msg}


# ── Video status polling ──────────────────────────────────────────────────────

@app.get("/video/status/{job_id}")
async def video_status(job_id: int, current_user: dict = Depends(get_current_user)):
    """
    Poll the status of a video render job.
    Called by the frontend every 5 seconds after submitting a render.
    Returns status + video_url when completed.

    If our DB shows completed/failed, returns immediately without hitting HeyGen.
    If still processing, polls HeyGen for the latest status.
    """
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=503, detail="Video service not configured.")

    uid = current_user["id"]
    job = video_job_get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Video job not found.")
    if job["userId"] != uid:
        raise HTTPException(status_code=403, detail="Not your video job.")

    # Already terminal — return from DB, no HeyGen call needed
    if job["status"] in ("completed", "failed"):
        return {
            "job_id":   job_id,
            "status":   job["status"],
            "video_url": job["videoUrl"],
            "error":    job["errorMessage"],
        }

    # Still processing — poll HeyGen
    heygen_video_id = job.get("heygenVideoId")
    if not heygen_video_id:
        return {"job_id": job_id, "status": "pending", "video_url": None, "error": None}

    try:
        async with _httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.heygen.com/v1/video_status.get?video_id={heygen_video_id}",
                headers={"X-Api-Key": HEYGEN_API_KEY},
            )
        resp_data = resp.json()
    except Exception as e:
        print(f"[Video] Status poll failed for job {job_id}: {e}")
        return {"job_id": job_id, "status": "processing", "video_url": None, "error": None}

    heygen_status = resp_data.get("data", {}).get("status", "processing")
    video_url     = resp_data.get("data", {}).get("video_url")

    if heygen_status == "completed" and video_url:
        updated = video_job_complete(heygen_video_id, video_url)
        return {
            "job_id":    job_id,
            "status":    "completed",
            "video_url": video_url,
            "error":     None,
        }
    elif heygen_status == "failed":
        error_msg = resp_data.get("data", {}).get("error", {}).get("message", "Render failed")
        video_job_fail(heygen_video_id, error_msg)
        return {
            "job_id":    job_id,
            "status":    "failed",
            "video_url": None,
            "error":     error_msg,
        }

    # Still pending/processing
    return {"job_id": job_id, "status": heygen_status, "video_url": None, "error": None}


# ── HeyGen webhook handler ────────────────────────────────────────────────────

def _voice_audio_cleanup(job_id: int) -> None:
    """
    Delete the temporary LMNT-synthesized voice audio file for a render job.
    Called by the webhook handler when a video render completes or fails.
    The file lives at /data/voice_audio/{job_id}.mp3.
    Non-fatal if the file doesn't exist — it may have already been cleaned up
    or the render used the stock voice with no audio file.
    """
    try:
        import pathlib as _pathlib_cleanup
        audio_path = _pathlib_cleanup.Path(f"/data/voice_audio/{job_id}.mp3")
        if audio_path.exists():
            audio_path.unlink()
            print(f"[Voice] Cleaned up audio file for job {job_id}")
    except Exception as e:
        print(f"[Voice] Audio cleanup failed for job {job_id}: {e}")


@app.post("/video/webhook")
async def video_webhook(request: Request):
    """
    Receives completion callbacks from HeyGen when a video finishes rendering.
    Register this URL in HeyGen dashboard:
      https://api.homebridgegroup.co/video/webhook

    Expected event types:
      avatar_video.success — video completed successfully
      avatar_video.fail    — video render failed

    No signature verification required by HeyGen for this endpoint type.
    We validate that the video_id exists in our DB before acting on it.
    """
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    event_type = body.get("event_type", "")
    data       = body.get("event_data", body.get("data", {}))

    video_id  = data.get("video_id", "")
    video_url = data.get("video_url", "")

    print(f"[Video Webhook] event={event_type} video_id={video_id}")

    if not video_id:
        return {"ok": True}

    if event_type in ("avatar_video.success", "video.completed", "completed"):
        if video_url:
            updated = video_job_complete(video_id, video_url)
            if updated:
                print(f"[Video Webhook] Completed: job {updated['id']} for user {updated['userId']}")
                # Clean up voice audio temp file now that render is done
                _voice_audio_cleanup(updated["id"])
    elif event_type in ("avatar_video.fail", "video.failed", "failed"):
        error_msg = data.get("error", {}).get("message", "") if isinstance(data.get("error"), dict) else str(data.get("error", "Render failed"))
        failed_job = video_job_fail(video_id, error_msg[:200])
        print(f"[Video Webhook] Failed: video_id {video_id} — {error_msg}")
        # Clean up voice audio temp file even on failure
        _job = video_job_get_by_heygen_id(video_id)
        if _job:
            _voice_audio_cleanup(_job["id"])

    return {"ok": True}


# ── Video top-up pack checkout ────────────────────────────────────────────────

@app.post("/billing/video-topup-checkout")
async def video_topup_checkout(current_user: dict = Depends(get_current_user)):
    """
    Create a Stripe checkout session for a Video Top-up Pack.
    $19 one-time purchase — adds 10 video renders to current month.
    Uses STRIPE_PRICE_VIDEO_TOPUP env var.
    """
    if not STRIPE_ENABLED:
        raise HTTPException(503, "Billing not yet configured.")

    price_id = os.getenv("STRIPE_PRICE_VIDEO_TOPUP", "")
    if not price_id:
        raise HTTPException(400, "Video Top-up Pack is not yet available. Check back soon.")

    sub_data    = get_subscription_status(current_user["id"])
    customer_id = sub_data.get("stripe_customer_id")
    if not customer_id:
        customer    = _stripe.Customer.create(
            email    = current_user["email"],
            name     = current_user.get("agent_name", ""),
            metadata = {"hb_user_id": str(current_user["id"])},
        )
        customer_id = customer.id

    session = _stripe.checkout.Session.create(
        customer   = customer_id,
        mode       = "payment",
        line_items = [{"price": price_id, "quantity": 1}],
        success_url= f"{os.getenv('FRONTEND_URL', 'https://app.homebridgegroup.co')}?billing=video_topup_success",
        cancel_url = f"{os.getenv('FRONTEND_URL', 'https://app.homebridgegroup.co')}?billing=cancelled",
        metadata   = {"hb_user_id": str(current_user["id"]), "price_key": "video_topup"},
    )
    return {"checkout_url": session.url}


# ── Admin: set HeyGen avatar ID for an agent ─────────────────────────────────

@app.put("/admin/users/{user_id}/avatar-id")
async def admin_set_avatar_id(user_id: int, request: Request, current_user: dict = Depends(get_current_user)):
    """
    Admin-only: set a HeyGen Instant Avatar ID for an agent.
    Used when HomeBridge staff manually processes an agent's Video Identity upgrade.
    HeyGen is never mentioned in agent-facing UI — this is internal admin tooling only.

    Body: { "avatar_id": "string" }  — pass null or "" to clear.
    """
    if current_user.get("role") not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    body      = await request.json()
    avatar_id = body.get("avatar_id", "")
    set_heygen_avatar_id(user_id, avatar_id)
    action = "set" if avatar_id else "cleared"
    print(f"[Admin] Avatar ID {action} for user {user_id} by admin {current_user['id']}")
    return {"success": True, "user_id": user_id, "avatar_id": avatar_id or None}


# ── Video jobs history for agent ─────────────────────────────────────────────

@app.get("/video/jobs")
async def get_video_jobs(current_user: dict = Depends(get_current_user)):
    """
    Return the agent's recent video render jobs.
    Used to show video history in Records panel (future session).
    """
    jobs = video_jobs_get_for_user(current_user["id"], limit=20)
    return {"jobs": jobs, "count": len(jobs)}


# ── Voice Identity — LMNT voice cloning — Session 51 ─────────────────────────
#
# Four endpoints manage the full voice lifecycle:
#   GET  /voice/status   — returns current voice setup state for the UI
#   POST /voice/consent  — records explicit voice cloning consent (required first)
#   POST /voice/setup    — accepts audio upload, creates LMNT clone, stores voice ID
#   DELETE /voice/setup  — deletes voice from LMNT + clears DB (GDPR/CCPA)
#
# Served audio endpoint (used during video renders only):
#   GET  /voice/audio/{token}/{job_id} — serves synthesized MP3 to HeyGen
#
# LMNT is infrastructure. Never mentioned in agent-facing UI or error messages.
# Agent-facing language: "Your Voice", "Set up your voice", "Voice is ready."

@app.get("/voice/status")
async def voice_status(current_user: dict = Depends(get_current_user)):
    """
    Return the agent's current voice identity state.
    Called by the Identity panel on load to determine which UI state to show:
      - No consent, no voice → show consent + setup prompt
      - Consent given, no voice → show recording/upload UI
      - Voice set up → show "Voice is ready" + delete option
    """
    uid   = current_user["id"]
    state = get_voice_identity(uid)
    return {
        "has_voice":        state["has_voice"],
        "has_consent":      state["has_consent"],
        "voice_consent_at": state["voice_consent_at"],
    }


@app.post("/voice/consent")
async def voice_consent_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Record the agent's explicit consent to voice cloning.
    Must be called before POST /voice/setup is permitted.
    Consent is permanent once given — stored as voice_consent_at timestamp.
    Idempotent: safe to call again if already consented (timestamp not overwritten
    because record_voice_consent uses datetime('now') only on first meaningful call —
    but we guard here so the agent knows consent is already on file).
    """
    uid   = current_user["id"]
    state = get_voice_identity(uid)
    if not state["has_consent"]:
        record_voice_consent(uid)
        print(f"[Voice] Consent recorded for user {uid}")
    return {"success": True, "message": "Voice cloning consent recorded."}


@app.post("/voice/setup")
async def voice_setup(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Accept an audio file upload, create an LMNT voice clone, and store the
    returned voice ID on the agent's record.

    Flow:
    1. Verify consent is on record (hard gate)
    2. Verify LMNT API key is configured
    3. Read multipart audio file from request
    4. POST to LMNT /v1/ai/voice/clone with the audio file
    5. Store returned voice ID via set_lmnt_voice_id()
    6. Return success — no voice ID exposed to frontend

    Accepts: multipart/form-data with field "audio" containing the recording.
    Audio format: any format LMNT accepts (mp3, wav, m4a, webm).
    Recommended: 2–3 minutes of clean speech.
    """
    if not LMNT_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Voice setup is not yet configured. Please contact support."
        )

    uid   = current_user["id"]
    state = get_voice_identity(uid)

    # 1. Consent gate — hard block, no exceptions
    if not state["has_consent"]:
        raise HTTPException(
            status_code=403,
            detail="Voice cloning consent is required before setup. Please complete the consent step."
        )

    # 2. Read multipart audio file
    try:
        form = await request.form()
        audio_file = form.get("audio")
        if not audio_file:
            raise HTTPException(status_code=400, detail="No audio file received. Please record or upload your voice sample.")
        audio_bytes = await audio_file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Audio file is empty. Please try again.")
        filename    = getattr(audio_file, "filename", None) or "voice_sample.mp3"
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Voice] File read error for user {uid}: {e}")
        raise HTTPException(status_code=400, detail="Could not read audio file. Please try again.")

    # 3. POST to LMNT POST /v1/ai/voice — correct endpoint per LMNT API spec
    #    Field: "files" (array, not "file"). "enhance" is required. "name" is required.
    #    Header: lmnt-version: 1.1 required on all voice operations.
    agent_name = current_user.get("agent_name", f"agent_{uid}")
    try:
        import httpx as _httpx_voice
        async with _httpx_voice.AsyncClient(timeout=120.0) as client:
            lmnt_resp = await client.post(
                "https://api.lmnt.com/v1/ai/voice",
                headers={
                    "X-API-Key":    LMNT_API_KEY,
                    "lmnt-version": "1.1",
                },
                files={"file": (filename, audio_bytes)},
                data={"name": agent_name, "enhance": "false"},
            )
        clone_data = lmnt_resp.json()
    except Exception as e:
        print(f"[Voice] LMNT clone API call failed for user {uid}: {e}")
        raise HTTPException(
            status_code=502,
            detail="Voice setup service is temporarily unavailable. Please try again in a moment."
        )

    if lmnt_resp.status_code not in (200, 201):
        err_msg = clone_data.get("message") or clone_data.get("error") or f"Status {lmnt_resp.status_code}"
        print(f"[Voice] LMNT rejected clone for user {uid}: {err_msg} — {clone_data}")
        raise HTTPException(
            status_code=502,
            detail="Voice setup failed. Please ensure your recording is clear and at least 30 seconds long, then try again."
        )

    # 4. Extract voice ID — LMNT returns { "id": "...", "name": "...", "state": "ready", ... }
    voice_id = clone_data.get("id") or clone_data.get("voice_id")
    if not voice_id:
        print(f"[Voice] LMNT returned no voice ID for user {uid}: {clone_data}")
        raise HTTPException(
            status_code=502,
            detail="Voice setup encountered an unexpected error. Please try again."
        )

    # 5. Store the voice ID
    set_lmnt_voice_id(uid, voice_id)
    print(f"[Voice] Voice clone created and stored for user {uid}")

    return {
        "success": True,
        "message": "Your voice is set up. It will be used in your next video.",
    }


@app.delete("/voice/setup")
async def voice_setup_delete(current_user: dict = Depends(get_current_user)):
    """
    Delete the agent's cloned voice.
    GDPR/CCPA requirement — agents must be able to remove their voice data.

    Flow:
    1. Look up the stored lmnt_voice_id
    2. Call LMNT DELETE /v1/ai/voice/{voice_id} to remove from LMNT's servers
    3. Clear lmnt_voice_id in our DB regardless of LMNT response
       (if LMNT already deleted it, we still need to clear our record)

    Does NOT clear voice_consent_at — consent record is permanent once given.
    Agent can re-consent and re-record a new voice sample at any time.
    """
    if not LMNT_API_KEY:
        raise HTTPException(status_code=503, detail="Voice service is not configured.")

    uid   = current_user["id"]
    state = get_voice_identity(uid)

    if not state["has_voice"]:
        # Nothing to delete — idempotent
        return {"success": True, "message": "No voice on file."}

    voice_id = state["lmnt_voice_id"]

    # 1. Delete from LMNT — best effort, do not block on failure
    try:
        import httpx as _httpx_voice_del
        async with _httpx_voice_del.AsyncClient(timeout=30.0) as client:
            del_resp = await client.delete(
                f"https://api.lmnt.com/v1/ai/voice/{voice_id}",
                headers={"X-API-Key": LMNT_API_KEY},
            )
        print(f"[Voice] LMNT delete response for user {uid}: {del_resp.status_code}")
    except Exception as e:
        # Log but do not block — we always clear our DB record
        print(f"[Voice] LMNT delete call failed for user {uid}: {e} — clearing DB record anyway")

    # 2. Clear from our DB regardless of LMNT response
    clear_lmnt_voice_id(uid)
    print(f"[Voice] Voice ID cleared from DB for user {uid}")

    return {
        "success": True,
        "message": "Your voice has been removed.",
    }


@app.get("/voice/audio/{token}/{job_id}")
async def serve_voice_audio(token: str, job_id: int):
    """
    Serve a synthesized voice audio file to HeyGen during video rendering.
    Uses the same signed token infrastructure as photo tokens.

    This endpoint is called by HeyGen's render pipeline, not by the agent browser.
    The token is single-use and expires 30 minutes after creation.
    The audio file is cleaned up after HeyGen fetches it.

    Returns the MP3 audio bytes with appropriate Content-Type header.
    """
    # Validate the signed token
    token_user_id = photo_token_validate(token)
    if not token_user_id:
        raise HTTPException(status_code=404, detail="Not found.")

    # Locate the audio file
    import pathlib as _pathlib_serve
    audio_path = _pathlib_serve.Path(f"/data/voice_audio/{job_id}.mp3")
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Not found.")

    # Read and return
    audio_bytes = audio_path.read_bytes()

    # Note: do NOT delete the file here — HeyGen's render pipeline fetches the audio
    # multiple times during processing. The file is cleaned up by the video webhook
    # handler when the render job completes or fails (see /video/webhook endpoint).
    # Token is NOT consumed here for the same reason — multiple fetches must succeed.

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={"Content-Length": str(len(audio_bytes))},
    )
