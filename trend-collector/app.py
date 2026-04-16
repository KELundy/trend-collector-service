import threading
import time
import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import FastAPI, Request, Depends, HTTPException
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
    "agent_monthly":           os.getenv("STRIPE_PRICE_AGENT_MONTHLY",          ""),
    "agent_annual":            os.getenv("STRIPE_PRICE_AGENT_ANNUAL",           ""),
    "team_monthly":            os.getenv("STRIPE_PRICE_TEAM_MONTHLY",           ""),
    "team_annual":             os.getenv("STRIPE_PRICE_TEAM_ANNUAL",            ""),
    "office_starter_monthly":  os.getenv("STRIPE_PRICE_OFFICE_STARTER_MONTHLY", ""),
    "office_starter_annual":   os.getenv("STRIPE_PRICE_OFFICE_STARTER_ANNUAL",  ""),
    "office_growth_monthly":   os.getenv("STRIPE_PRICE_OFFICE_GROWTH_MONTHLY",  ""),
    "office_growth_annual":    os.getenv("STRIPE_PRICE_OFFICE_GROWTH_ANNUAL",   ""),
    "office_team_monthly":     os.getenv("STRIPE_PRICE_OFFICE_TEAM_MONTHLY",    ""),
    "office_team_annual":      os.getenv("STRIPE_PRICE_OFFICE_TEAM_ANNUAL",     ""),
}

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
    library_save, library_get_all, library_get_item,
    library_update, library_delete,
    schedule_upsert, schedules_get_all, schedule_get,
    schedule_delete, schedules_get_due, schedule_mark_ran,
    calculate_identity_score,
    generate_compliance_pdf,
    get_broker_office_stats,
    get_broker_agent_content,
    get_team_stats,
    save_agent_setup, get_agent_setup,
    get_user_results,
    DB_NAME,
)

# ── Safe fallback in case database.py is older version ──
try:
    from database import migrate_context_column
except ImportError:
    def migrate_context_column():
        print("[Startup] migrate_context_column not available in this database.py version")

from auth import router as auth_router, get_current_user
from content_engine import router as content_engine_router, generate_content_core
from social import router as social_router

from collectors.google_trends import fetch_google_trends
from collectors.youtube_trends import fetch_youtube_trends
from collectors.reddit_trends import fetch_reddit_trends
from collectors.bing_trends import fetch_bing_trends
from collectors.tiktok_trends import fetch_tiktok_trends

from anthropic import Anthropic
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

COLLECTION_INTERVAL_SECONDS = int(os.getenv("TREND_INTERVAL_SECONDS", str(24 * 60 * 60)))
TREND_ENABLED  = os.getenv("TREND_ENABLED",  "true").lower() == "true"
SIGNAL_ENABLED = os.getenv("SIGNAL_ENABLED", "true").lower() == "true"

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
    print("[Startup] Starting background trend collector...")
    t1 = threading.Thread(target=trend_collection_worker, daemon=True)
    t1.start()
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
async def get_library(context: str = "agent", current_user=Depends(get_current_user)):
    items = library_get_all(current_user["id"], context=context)
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
    item = library_save(user_id=current_user["id"], niche=niche, content=content, compliance=compliance, source=source)
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
    item = library_update(item_id, current_user["id"], updates)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
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

class ScheduleDeleteRequest(BaseModel):
    niche: str


@app.get("/schedules")
async def get_schedules(current_user=Depends(get_current_user)):
    return {"schedules": schedules_get_all(current_user["id"])}


@app.post("/schedules")
async def upsert_schedule(body: ScheduleRequest, current_user=Depends(get_current_user)):
    from database import schedule_upsert
    schedule = schedule_upsert(
        user_id    = current_user["id"],
        niche      = body.niche,
        frequency  = body.frequency,
        time_of_day= body.timeOfDay,
        timezone   = body.timezone,
        day_of_week= body.dayOfWeek,
    )
    return {"success": True, "schedule": schedule}


@app.delete("/schedules/{niche}")
async def delete_schedule(niche: str, current_user=Depends(get_current_user)):
    success = schedule_delete(current_user["id"], niche)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True}


# ── Usage limit check ──────────────────────────────────────────────────────────
def check_generation_limit(user: dict) -> None:
    """
    Raises HTTP 429 if agent has exceeded their monthly generation limit.
    super_admin and admin are always allowed.
    Called before every generation endpoint.
    """
    from database import usage_check, usage_increment
    role = user.get("role", "agent")
    plan = user.get("plan", "trial")
    uid  = user.get("id")
    check = usage_check(uid, role, plan)
    if not check["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={
                "error":      "generation_limit_reached",
                "message":    f"You've used all {check['limit']} posts included in your plan this month.",
                "used":       check["used"],
                "limit":      check["limit"],
                "resets_on":  check["resets_on"],
                "upgrade_msg":"Contact us to add more generations or upgrade your plan.",
            }
        )
    # Increment counter on the way through — only for non-unlimited roles
    if role not in ("super_admin", "admin"):
        usage_increment(uid)


@app.get("/usage")
async def get_usage(current_user=Depends(get_current_user)):
    """Return current generation usage for the logged-in agent."""
    from database import usage_check
    check = usage_check(current_user["id"], current_user.get("role","agent"), current_user.get("plan","trial"))
    return check


# ── Local signals endpoint ─────────────────────────────────────────────────────
@app.get("/signals/latest")
async def get_latest_signals(current_user=Depends(get_current_user)):
    """
    Returns the most recent high-relevance local signals for the agent.
    Used by the Home dashboard to surface the suggested next action.
    """
    from database import signals_get_latest
    signals = signals_get_latest(current_user["id"], limit=5)
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
        )
        return {"ok": True, "message": "Signal collection triggered."}
    except Exception as e:
        raise HTTPException(500, detail=str(e))




class ScoreRequest(BaseModel):
    setup: dict = {}

@app.post("/identity/score")
async def get_identity_score(req: ScoreRequest, current_user=Depends(get_current_user)):
    score = calculate_identity_score(current_user["id"], req.setup)
    return score


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
            situation   = setup.get("defaultSituation") or "Market update and current conditions",
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
            approve_url = f"{api_url}/approve?token={token}"
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

            # ── Fetch hyper-local signals to enrich content generation ──────
            local_signal_trends = []
            try:
                from database import signals_get_latest as _sgl
                raw_signals = _sgl(user_id, limit=5)
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
                situation   = setup.get("defaultSituation") or "Market update and current conditions",
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
        approve_url = f"{api_url}/approve?token={token}"

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


def classify_topic_to_niches(topic: str) -> list:
    """Classify a trend topic into real estate niches using Claude.
    Uses Haiku — background classification task, not user-facing content generation."""
    prompt = f"""You are a real estate niche classifier. Given a trend topic, return a JSON list of real estate niches it belongs to. No explanation, only JSON.\nTrend topic: "{topic}" """
    try:
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)
    except Exception:
        return []


def collect_all_trends() -> Dict[str, Any]:
    raw = {"google": fetch_google_trends(), "youtube": fetch_youtube_trends(), "reddit": fetch_reddit_trends(), "bing": fetch_bing_trends(), "tiktok": fetch_tiktok_trends(), "timestamp": datetime.utcnow().isoformat()}
    classified = {}
    for source, items in raw.items():
        if source == "timestamp": continue
        for item in items:
            topic = (item.get("topic") or item.get("title") or item.get("query") or json.dumps(item)) if isinstance(item, dict) else str(item)
            niches = classify_topic_to_niches(topic)
            for niche in niches:
                if niche not in classified:
                    classified[niche] = {"google": [], "youtube": [], "reddit": [], "bing": [], "tiktok": [], "timestamp": raw["timestamp"]}
                classified[niche][source].append({"topic": topic})
    return classified


def trend_collection_worker():
    while True:
        if TREND_ENABLED:
            try:
                print("[Trend Collector] Collecting trends...")
                classified = collect_all_trends()
                for niche, niche_trends in classified.items():
                    save_trends(niche_trends, niche)
                print("[Trend Collector] Done.")
            except Exception as e:
                print(f"[Trend Collector] Error: {e}")
        else:
            print("[Trend Collector] DISABLED (TREND_ENABLED=false) — skipping this cycle.")
        time.sleep(COLLECTION_INTERVAL_SECONDS)


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
    save_agent_setup(current_user["id"], body.setup)

    # Auto-generate slug if this agent doesn't have one yet
    from database import get_conn as _gc_slug
    _conn_s = _gc_slug()
    _c_s    = _conn_s.cursor()
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
    filename = f"HomeBridge_Compliance_Report_{current_user.get('agent_name','Agent').replace(' ','_')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


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
    price_key = body.get("price_key", "agent_monthly")
    price_id  = STRIPE_PRICES.get(price_key, "")
    if not price_id: raise HTTPException(400, f"Unknown plan key: {price_key}")
    sub_data    = get_subscription_status(current_user["id"])
    customer_id = sub_data.get("stripe_customer_id")
    if not customer_id:
        customer    = _stripe.Customer.create(email=current_user["email"], name=current_user.get("agent_name",""), metadata={"hb_user_id": str(current_user["id"])})
        customer_id = customer.id
    session = _stripe.checkout.Session.create(customer=customer_id, mode="subscription", line_items=[{"price": price_id, "quantity": 1}], success_url=f"{os.getenv('FRONTEND_URL','https://app.homebridgegroup.co')}?billing=success", cancel_url=f"{os.getenv('FRONTEND_URL','https://app.homebridgegroup.co')}?billing=cancelled", metadata={"hb_user_id": str(current_user["id"]), "price_key": price_key}, allow_promotion_codes=True)
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
    try: event = _stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e: raise HTTPException(400, f"Webhook error: {e}")
    etype = event["type"]
    obj   = event["data"]["object"]
    if etype == "checkout.session.completed":
        hb_uid    = int(obj.get("metadata", {}).get("hb_user_id", 0) or 0)
        price_key = obj.get("metadata", {}).get("price_key", "agent_monthly")
        if   "office_team"    in price_key: plan = "office_team"
        elif "office_growth"  in price_key: plan = "office_growth"
        elif "office_starter" in price_key: plan = "office_starter"
        elif "office"         in price_key: plan = "office_starter"
        else:                               plan = "agent"
        cycle = "annual" if "annual" in price_key else "monthly"
        if hb_uid: activate_subscription(hb_uid, plan, cycle, obj.get("customer",""), obj.get("subscription",""))
    elif etype in ("customer.subscription.deleted", "customer.subscription.paused"):
        cust_id = obj.get("customer","")
        conn = database.get_conn()
        c    = conn.cursor()
        c.execute("SELECT id FROM users WHERE stripe_customer_id=?", (cust_id,))
        row = c.fetchone()
        conn.close()
        if row: cancel_subscription(row["id"])
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

    # All approved/published posts — FULL TEXT for SEO
    now       = datetime.utcnow()
    month_ago = (now - timedelta(days=30)).isoformat()

    c.execute("""
        SELECT id, niche, content, compliance, cir_id,
               approved_at, published_at, status
        FROM content_library
        WHERE user_id = ? AND status IN ('approved','published')
        ORDER BY approved_at DESC
        LIMIT 50
    """, (user_id,))
    items = [dict(r) for r in c.fetchall()]

    # Stats
    posts_total   = len(items)
    posts_30_days = sum(1 for i in items if (i.get("approved_at") or "") >= month_ago)
    cir_count     = sum(1 for i in items if i.get("cir_id"))

    clean_count = 0
    for item in items:
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

    # Build posts array with full text
    posts = []
    for item in items:
        try:
            cd = _json.loads(item.get("content") or "{}")
        except Exception:
            cd = {}
        body      = cd.get("body","") or cd.get("post","") or cd.get("content","")
        headline  = cd.get("headline","") or cd.get("title","")
        if not body and not headline:
            continue
        posts.append({
            "id":          item["id"],
            "headline":    headline,
            "body":        body,
            "niche":       item.get("niche",""),
            "cir_id":      item.get("cir_id",""),
            "approved_at": (item.get("approved_at") or "")[:10],
            "verify_url":  f"https://homebridgegroup.co/verify.html?cir={item.get('cir_id','')}" if item.get("cir_id") else "",
        })

    conn.close()

    return {
        "slug":          slug,
        "agent_name":    user["agent_name"],
        "brokerage":     user.get("brokerage",""),
        "market":        setup.get("market",""),
        "short_bio":     setup.get("shortBio",""),
        "niches":        setup.get("primaryNiches",[]),
        "designations":  setup.get("designations",[]),
        "service_areas": setup.get("serviceAreas",[]),
        "website":       setup.get("websiteUrl",""),
        "posts_total":   posts_total,
        "posts_30_days": posts_30_days,
        "cir_count":     cir_count,
        "compliance_pct":compliance_pct,
        "member_since":  member_since,
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
            link = f"https://homebridgegroup.co/verify.html?cir={item['cir_id']}"
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
    <description>Verified real estate content by {esc(agent_name)}, {esc(market)}. CIR-certified by HomeBridge.</description>
    <language>en-us</language>
    <atom:link href="https://api.homebridgegroup.co/public/agent/{slug}/feed" rel="self" type="application/rss+xml"/>
    <managingEditor>support@homebridgegroup.co ({esc(agent_name)})</managingEditor>
    <generator>HomeBridge CIR Platform</generator>
{items_xml}
  </channel>
</rss>"""

    return _Response(content=rss, media_type="application/rss+xml")


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
                   "broker", "team", "agent", "assistant")
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
    valid_roles = ("super_admin", "admin", "support", "broker", "team", "agent", "assistant")
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

    if not email or not password or not agent_name:
        raise HTTPException(400, "email, password, and agent_name are required.")
    valid_roles = ("super_admin","admin","support","broker","team","agent","assistant")
    if role not in valid_roles:
        raise HTTPException(400, f"Invalid role.")

    pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (email, password_hash, agent_name, brokerage, role, is_licensed)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email, pw_hash, agent_name, brokerage, role, is_licensed))
        conn.commit()
        new_id = c.lastrowid
    except Exception as e:
        conn.close()
        raise HTTPException(409, f"Could not create user: {str(e)}")
    conn.close()
    return {"ok": True, "user_id": new_id, "email": email, "role": role}


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
    Generate a social-ready image for a library item using DALL-E 3.
    Requires OPENAI_API_KEY in Render environment variables.
    """
    import os as _os
    import httpx as _httpx

    openai_key = _os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        raise HTTPException(503, "Image generation not configured. Add OPENAI_API_KEY to Render environment variables.")

    body             = await request.json()
    headline         = str(body.get("headline",       "")).strip()
    thumbnail_idea   = str(body.get("thumbnail_idea", "")).strip()
    niche            = str(body.get("niche",          "real estate")).strip()
    market           = str(body.get("market",         "")).strip()
    library_item_id  = body.get("library_item_id")

    # Build a clean, professional real estate image prompt
    parts = []
    if thumbnail_idea:  parts.append(thumbnail_idea)
    if market:          parts.append(f"Location: {market}")
    if niche:           parts.append(f"Real estate context: {niche}")
    base = ". ".join(parts) if parts else f"Professional real estate photography, {niche}"
    prompt = (
        f"{base}. Professional real estate photography, warm natural lighting, "
        f"high quality, photorealistic. No text, no watermarks, no people."
    )

    try:
        async with _httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model":   "dall-e-3",
                    "prompt":  prompt[:4000],
                    "n":       1,
                    "size":    "1792x1024",
                    "quality": "standard",
                }
            )
    except Exception as e:
        raise HTTPException(502, f"Image generation request failed: {str(e)}")

    if resp.status_code != 200:
        try:    err_msg = resp.json().get("error", {}).get("message", "Unknown error")
        except: err_msg = resp.text[:200]
        raise HTTPException(502, f"Image generation failed: {err_msg}")

    image_url = resp.json()["data"][0]["url"]

    # Save image_url back to the library item — best effort, don't fail if column missing
    if library_item_id:
        try:
            from database import get_conn as _gc
            conn = _gc()
            conn.execute(
                "UPDATE content_library SET image_url = ? WHERE id = ? AND user_id = ?",
                (image_url, library_item_id, current_user["id"])
            )
            conn.commit()
            conn.close()
        except Exception as _e:
            print(f"[Image] Could not save image_url to library item {library_item_id}: {_e}")

    return {"image_url": image_url}


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
    approve_url = f"{api_url}/approve?token={token}"

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
                   published_to: list = None) -> str:
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
    app_url = "https://app.homebridgegroup.co?view=agent"
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
  <form method="POST" action="/approve?token={token}">
    {platform_section}
    {primary_btn}
    {secondary_btn}
  </form>
  <div class="footer">
    Approving creates a CIR™ Certified Identity Record.<br>
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
            action_line = "Your post has been approved, a CIR™ record created, and queued for publishing."
            btn_label   = "Open App →"
            open_app_url = "https://app.homebridgegroup.co?view=agent"
        else:
            pub_html     = ""
            action_line  = "Your approval has been recorded and a CIR™ Certified Identity Record has been created. Open the app to publish when ready."
            btn_label    = "Open App to Publish →"
            open_app_url = "https://app.homebridgegroup.co?view=agent&panel=library"

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
    valid_tiers = ("referral", "broker")
    if tier not in valid_tiers:
        raise HTTPException(
            400,
            "Elite tier is invitation-only. Referral and Broker tiers are available."
            if tier == "elite"
            else f"Invalid tier. Choose 'referral' or 'broker'."
        )

    # Broker tier only available to licensed roles
    if tier == "broker" and current_user.get("role") not in (
        "agent", "broker", "admin", "super_admin"
    ):
        raise HTTPException(
            403, "Broker Partner tier requires a licensed real estate role."
        )

    # If already enrolled and active, just return the existing record
    existing = _pg(current_user["id"])
    if existing and existing.get("status") == "active":
        return {
            "partner": existing,
            "message": "Already enrolled.",
        }

    partner = _pe(current_user["id"], tier)
    if not partner:
        raise HTTPException(500, "Enrollment failed — please try again.")

    msg = (
        "Welcome to the Partner Program! Your referral code is ready."
        if tier == "referral"
        else "Application submitted — we'll review within 1–2 business days."
    )
    return {"partner": partner, "message": msg}


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


@app.post("/partner/approve/{partner_id}")
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
# GET  /approve?token=   → preview page (shows content, Approve button)
# POST /approve?token=   → performs approval, returns success page
# POST /approve/resend?token= → creates fresh token from expired one, resends
# ─────────────────────────────────────────────────────────────────────────────

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
    approve_url = f"{api_url}/approve?token={new_token}"

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

# ─────────────────────────────────────────────
# DIAGNOSTIC + MIGRATION — super_admin only
# Debug endpoints removed — migrations complete, one-time use only.
