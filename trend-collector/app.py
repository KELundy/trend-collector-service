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


("/schedules/{niche}")
async def delete_schedule(niche: str, user = Depends(get_current_user)):
    schedule_delete(user["id"], niche)
    return {"deleted": True}


# ─────────────────────────────────────────────
# IDENTITY STRENGTH SCORE
# ─────────────────────────────────────────────

class ScoreRequest(BaseModel):
    setup: dict = {}

@app.post("/identity/score")
async def get_identity_score(req: ScoreRequest, user = Depends(get_current_user)):
    """
    Calculate the agent's identity strength score.
    Frontend passes current setup (from localStorage) so profile
    completeness is always current even before DB migration.
    """
    score = calculate_identity_score(user["id"], req.setup)
    return score
