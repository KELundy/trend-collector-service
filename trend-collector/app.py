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

# ─────────────────────────────────────────────
# LOCAL IMPORTS
# ─────────────────────────────────────────────
from database import (
    init_db, save_trends, get_latest_trends,
    migrate_add_niche_column,
    library_save, library_get_all, library_get_item,
    library_update, library_delete,
    schedule_upsert, schedules_get_all, schedule_get,
    schedule_delete, schedules_get_due, schedule_mark_ran,
    calculate_identity_score,
    generate_compliance_pdf,
    get_broker_office_stats,
    save_agent_setup, get_agent_setup,
    get_user_results,
    DB_NAME,
)
from auth import router as auth_router, get_current_user
from content_engine import router as content_engine_router, generate_content_core

from collectors.google_trends import fetch_google_trends
from collectors.youtube_trends import fetch_youtube_trends
from collectors.reddit_trends import fetch_reddit_trends
from collectors.bing_trends import fetch_bing_trends
from collectors.tiktok_trends import fetch_tiktok_trends

from anthropic import Anthropic
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

COLLECTION_INTERVAL_SECONDS = 6 * 60 * 60  # 6 hours


# ─────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────
app = FastAPI(
    title="HomeBridge Content Engine",
    description="Identity-aware, compliance-first content generation for real estate agents",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(content_engine_router)


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    print("[Startup] Initializing database...")
    init_db()
    migrate_add_niche_column()

    print("[Startup] Starting background trend collector...")
    t1 = threading.Thread(target=trend_collection_worker, daemon=True)
    t1.start()

    print("[Startup] Starting content scheduler...")
    t2 = threading.Thread(target=content_scheduler_worker, daemon=True)
    t2.start()

    print("[Startup] Ready.")


# ─────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "HomeBridge Content Engine",
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.get("/")
async def root():
    return {
        "service": "HomeBridge Content Engine",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────
# CONTENT LIBRARY ENDPOINTS
# ─────────────────────────────────────────────

class LibraryPatchRequest(BaseModel):
    status: Optional[str] = None
    content: Optional[dict] = None
    compliance: Optional[dict] = None
    copiedPlatforms: Optional[list] = None
    approvedAt: Optional[str] = None
    publishedAt: Optional[str] = None


@app.get("/library")
async def get_library(current_user=Depends(get_current_user)):
    """Return all library items for the logged-in agent."""
    items = library_get_all(current_user["id"])
    return {"items": items, "count": len(items)}


@app.post("/library")
async def save_to_library(payload: dict, current_user=Depends(get_current_user)):
    """Save a newly generated content item to the agent's library."""
    niche      = payload.get("niche", "")
    content    = payload.get("content", {})
    compliance = payload.get("compliance", {})
    source     = payload.get("source", "manual")

    if not content:
        raise HTTPException(status_code=400, detail="content is required")

    item = library_save(
        user_id=current_user["id"],
        niche=niche,
        content=content,
        compliance=compliance,
        source=source,
    )
    return {"success": True, "item": item}


@app.patch("/library/{item_id}")
async def update_library_item(
    item_id: int,
    body: LibraryPatchRequest,
    current_user=Depends(get_current_user)
):
    """Update status, copiedPlatforms, approvedAt, publishedAt on a library item."""
    updates = {}
    if body.status is not None:
        updates["status"] = body.status
    if body.content is not None:
        updates["content"] = body.content
    if body.compliance is not None:
        updates["compliance"] = body.compliance
    if body.copiedPlatforms is not None:
        updates["copied_platforms"] = body.copiedPlatforms
    if body.approvedAt is not None:
        updates["approved_at"] = body.approvedAt
    if body.publishedAt is not None:
        updates["published_at"] = body.publishedAt

    item = library_update(item_id, current_user["id"], updates)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True, "item": item}


@app.delete("/library/{item_id}")
async def delete_library_item(item_id: int, current_user=Depends(get_current_user)):
    """Delete a library item (must belong to the logged-in agent)."""
    success = library_delete(item_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True}


# ─────────────────────────────────────────────
# SCHEDULE ENDPOINTS
# ─────────────────────────────────────────────

class ScheduleRequest(BaseModel):
    niche: str
    frequency: str        # daily | 3x_week | weekly
    timeOfDay: str        # HH:MM  e.g. "08:00"
    timezone: Optional[str] = "America/Denver"

class ScheduleDeleteRequest(BaseModel):
    niche: str


@app.get("/schedules")
async def get_schedules(current_user=Depends(get_current_user)):
    """Return all active schedules for the logged-in agent."""
    return {"schedules": schedules_get_all(current_user["id"])}


@app.post("/schedules")
async def upsert_schedule(body: ScheduleRequest, current_user=Depends(get_current_user)):
    """Create or update a content schedule for a given niche."""
    schedule = schedule_upsert(
        user_id=current_user["id"],
        niche=body.niche,
        frequency=body.frequency,
        time_of_day=body.timeOfDay,
        timezone=body.timezone,
    )
    return {"success": True, "schedule": schedule}


@app.delete("/schedules/{niche}")
async def delete_schedule(niche: str, current_user=Depends(get_current_user)):
    """Remove a schedule for a given niche."""
    success = schedule_delete(current_user["id"], niche)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True}


# ─────────────────────────────────────────────
# IDENTITY STRENGTH SCORE
# ─────────────────────────────────────────────

class ScoreRequest(BaseModel):
    setup: dict = {}

@app.post("/identity/score")
async def get_identity_score(req: ScoreRequest, current_user = Depends(get_current_user)):
    """
    Calculate the agent's identity strength score.
    Frontend passes current setup (from localStorage) so profile
    completeness is always current even before full DB migration.
    """
    score = calculate_identity_score(current_user["id"], req.setup)
    return score


# ─────────────────────────────────────────────
# CONTENT SCHEDULER WORKER
# ─────────────────────────────────────────────
def _compute_next_run(frequency: str, time_of_day: str) -> str:
    """
    Compute next UTC run time based on frequency and preferred local time.
    Simplified: treats time_of_day as UTC for now.
    Timezone-aware scheduling added when Twilio/pytz is wired.
    """
    try:
        hour, minute = map(int, time_of_day.split(":"))
    except Exception:
        hour, minute = 8, 0

    now = datetime.utcnow()
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if frequency == "daily":
        delta = timedelta(days=1)
    elif frequency == "3x_week":
        delta = timedelta(days=2)  # every ~2.3 days, simplified
    else:  # weekly
        delta = timedelta(days=7)

    # If the candidate time today is already past, push to next cycle
    if candidate <= now:
        candidate += delta

    return candidate.isoformat()


def content_scheduler_worker():
    """
    Background thread — wakes every 15 minutes, checks for due schedules,
    generates content, saves to content_library.
    """
    print("[Scheduler] Worker started.")
    while True:
        try:
            due = schedules_get_due()
            if due:
                print(f"[Scheduler] {len(due)} schedule(s) due.")
            for sched in due:
                _run_scheduled_generation(sched)
        except Exception as e:
            print(f"[Scheduler] Error in worker: {e}")
        time.sleep(15 * 60)  # check every 15 minutes


def _run_scheduled_generation(sched: dict):
    """Generate content for one due schedule and save it to the library."""
    user_id    = sched["user_id"]
    niche      = sched["niche"]
    sched_id   = sched["id"]

    print(f"[Scheduler] Generating for user {user_id} / niche '{niche}'")

    try:
        # Build a minimal agent profile from DB user record
        from database import get_conn
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = c.fetchone()

        # Try to get agent setup from agent_setup table if it exists
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

        # Use a default situation for scheduled generation
        situation  = setup.get("defaultSituation") or "Market update and current conditions"
        persona    = setup.get("defaultPersona")    or "homeowners"
        brand_voice = setup.get("brandVoice")       or ""
        short_bio   = setup.get("shortBio")         or ""
        audience    = setup.get("audienceDescription") or ""

        # Call the core generation function from content_engine
        result = generate_content_core(
            agent_name  = user_row["agent_name"],
            brokerage   = user_row["brokerage"],
            market      = setup.get("market", ""),
            niche       = niche,
            situation   = situation,
            persona     = persona,
            tone        = setup.get("tone", "Professional"),
            length      = setup.get("length", "Standard"),
            trends      = setup.get("trends", []),
            brand_voice = brand_voice,
            short_bio   = short_bio,
            audience    = audience,
            words_avoid = setup.get("wordsAvoid", ""),
            words_prefer= setup.get("wordsPrefer", ""),
        )

        library_save(
            user_id    = user_id,
            niche      = niche,
            content    = result["content"],
            compliance = result["compliance"],
            source     = "scheduled",
        )
        print(f"[Scheduler] ✓ Saved scheduled content for user {user_id} / '{niche}'")

    except Exception as e:
        print(f"[Scheduler] ✗ Generation failed for user {user_id} / '{niche}': {e}")

    finally:
        # Always update next_run so we don't retry immediately on failure
        next_run = _compute_next_run(sched.get("frequency", "weekly"), sched.get("time_of_day", "08:00"))
        schedule_mark_ran(sched_id, next_run)


# ─────────────────────────────────────────────
# TREND COLLECTION WORKER (unchanged)
# ─────────────────────────────────────────────
def classify_topic_to_niches(topic: str) -> list:
    prompt = f"""You are a real estate niche classifier. Given a trend topic, return a JSON list
of real estate niches it belongs to. No explanation, only JSON.
Trend topic: "{topic}" """
    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)
    except Exception:
        return []


def collect_all_trends() -> Dict[str, Any]:
    raw = {
        "google":    fetch_google_trends(),
        "youtube":   fetch_youtube_trends(),
        "reddit":    fetch_reddit_trends(),
        "bing":      fetch_bing_trends(),
        "tiktok":    fetch_tiktok_trends(),
        "timestamp": datetime.utcnow().isoformat(),
    }
    classified = {}
    for source, items in raw.items():
        if source == "timestamp":
            continue
        for item in items:
            topic = (
                item.get("topic") or item.get("title") or
                item.get("query") or json.dumps(item)
            ) if isinstance(item, dict) else str(item)
            niches = classify_topic_to_niches(topic)
            for niche in niches:
                if niche not in classified:
                    classified[niche] = {
                        "google": [], "youtube": [], "reddit": [],
                        "bing": [], "tiktok": [],
                        "timestamp": raw["timestamp"]
                    }
                classified[niche][source].append({"topic": topic})
    return classified


def trend_collection_worker():
    while True:
        try:
            print("[Trend Collector] Collecting trends...")
            classified = collect_all_trends()
            for niche, niche_trends in classified.items():
                save_trends(niche_trends, niche)
            print("[Trend Collector] Done.")
        except Exception as e:
            print(f"[Trend Collector] Error: {e}")
        time.sleep(COLLECTION_INTERVAL_SECONDS)


# ─────────────────────────────────────────────
# TREND ENDPOINTS (preserved)
# ─────────────────────────────────────────────
@app.get("/trends/latest")
async def latest_trends():
    return get_latest_trends()


@app.get("/trends/by-niche")
async def trends_by_niche(niche: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT source, topic, collected_at FROM trends
        WHERE niche = ? ORDER BY collected_at DESC LIMIT 200
    """, (niche,))
    rows = c.fetchall()
    conn.close()
    grouped = {
        "google": [], "youtube": [], "reddit": [],
        "bing": [], "tiktok": [],
        "timestamp": datetime.utcnow().isoformat()
    }
    for source, topic, collected_at in rows:
        if source in grouped:
            grouped[source].append({"topic": topic, "collected_at": collected_at})
    if not any(grouped[s] for s in ["google","youtube","reddit","bing","tiktok"]):
        grouped["google"] = [{"topic": f"Rising interest in {niche} this week",
                               "collected_at": datetime.utcnow().isoformat()}]
    return grouped









# ─────────────────────────────────────────────
# AGENT SETUP — server-side storage
# ─────────────────────────────────────────────

class SetupSaveRequest(BaseModel):
    setup: dict

@app.post("/setup/save")
async def save_setup(body: SetupSaveRequest, current_user=Depends(get_current_user)):
    """Save agent identity/setup data to DB. Called every time agent saves Setup panel."""
    save_agent_setup(current_user["id"], body.setup)
    return {"success": True}

@app.get("/setup/get")
async def get_setup(current_user=Depends(get_current_user)):
    """Load agent identity/setup data from DB. Used to restore state on login."""
    setup = get_agent_setup(current_user["id"])
    return {"setup": setup, "has_setup": bool(setup)}


# ─────────────────────────────────────────────
# RESULTS PANEL
# ─────────────────────────────────────────────

@app.get("/results")
async def get_results(current_user=Depends(get_current_user)):
    """Return real content metrics for the Results panel."""
    results = get_user_results(current_user["id"])
    return results

# ─────────────────────────────────────────────
# COMPLIANCE REPORT — PDF DOWNLOAD
# ─────────────────────────────────────────────

class ComplianceReportRequest(BaseModel):
    setup: dict = {}
    date_from: str = ""   # ISO date string, optional filter
    date_to:   str = ""

@app.post("/compliance/report")
async def download_compliance_report(
    req: ComplianceReportRequest,
    current_user = Depends(get_current_user)
):
    """
    Generate and stream a compliance audit report PDF.
    Includes every approved/published item, compliance verdicts,
    approval timestamps, and agent identity summary.
    """
    try:
        pdf_bytes = generate_compliance_pdf(
            user_id    = current_user["id"],
            agent_name = current_user.get("agent_name", ""),
            brokerage  = current_user.get("brokerage", ""),
            email      = current_user.get("email", ""),
            setup      = req.setup,
            date_from  = req.date_from,
            date_to    = req.date_to,
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation requires reportlab: {str(e)}. Check requirements.txt."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {str(e)}"
        )

    filename = f"HomeBridge_Compliance_Report_{current_user.get('agent_name','Agent').replace(' ','_')}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────────────────────────────────────
# BROKER OFFICE STATS
# ─────────────────────────────────────────────


# ═════════════════════════════════════════════════════════════════════════════
# DEMO TOKEN ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

import secrets, json as _json
from datetime import datetime as _dt

@app.post("/demo/create-token")
async def create_demo_token(request: Request, user=Depends(require_admin)):
    body = await request.json()
    label = (body.get("label") or "").strip()
    if not label:
        raise HTTPException(400, "Label required")
    token = "tk_" + secrets.token_urlsafe(10)
    conn = database.get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO demo_tokens (token, label, created_by) VALUES (?,?,?)",
        (token, label, user["id"])
    )
    conn.commit()
    conn.close()
    return {"token": token, "label": label}

@app.get("/demo/tokens")
async def list_demo_tokens(user=Depends(require_admin)):
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
async def delete_demo_token(token_id: int, user=Depends(require_admin)):
    conn = database.get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM demo_tokens WHERE id=?", (token_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/demo/validate")
async def validate_demo_token(token: str, request: Request):
    """Public endpoint — validates demo token and logs the access."""
    if not token or not token.startswith("tk_"):
        raise HTTPException(403, "Invalid demo token")
    conn = database.get_conn()
    c = conn.cursor()
    c.execute("SELECT id, ip_log, open_count FROM demo_tokens WHERE token=?", (token,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(403, "Demo token not found or expired")
    # Log IP
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    try:
        ip_log = _json.loads(row["ip_log"] or "[]")
    except:
        ip_log = []
    if client_ip not in ip_log:
        ip_log.append(client_ip)
    c.execute(
        "UPDATE demo_tokens SET open_count=open_count+1, last_opened=?, ip_log=? WHERE id=?",
        (_dt.utcnow().isoformat(), _json.dumps(ip_log), row["id"])
    )
    conn.commit()
    conn.close()
    return {"valid": True, "message": "Demo access granted"}

@app.get("/broker/office-stats")
async def broker_office_stats(current_user = Depends(get_current_user)):
    """
    Return content stats for every agent under this broker.
    Broker-role only.
    """
    if current_user.get("role") not in ("broker", "admin"):
        raise HTTPException(status_code=403, detail="Broker accounts only.")
    stats = get_broker_office_stats(current_user["id"])
    return {"agents": stats, "count": len(stats)}


@app.post("/broker/agent-compliance-report")
async def broker_agent_report(
    req: dict,
    current_user = Depends(get_current_user)
):
    """
    Download compliance report for a specific agent — broker only.
    req: { agent_id: int }
    """
    if current_user.get("role") not in ("broker", "admin"):
        raise HTTPException(status_code=403, detail="Broker accounts only.")

    agent_id = req.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id required.")

    # Verify agent is under this broker
    from database import get_conn
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ? AND broker_id = ?", (agent_id, current_user["id"]))
    agent = c.fetchone()
    conn.close()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found in your office.")

    pdf_bytes = generate_compliance_pdf(
        user_id    = agent["id"],
        agent_name = agent["agent_name"],
        brokerage  = agent["brokerage"],
        email      = agent["email"],
        setup      = {},
    )

    filename = f"Compliance_{agent['agent_name'].replace(' ','_')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


