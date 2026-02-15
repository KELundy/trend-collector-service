import threading
import time
from datetime import datetime
from typing import Dict, Any, List
import os
import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from database import (
    init_db,
    save_trends,
    get_latest_trends,
    add_content_to_queue,
    get_content_queue,
    update_content_status,
)

from collectors.google_trends import fetch_google_trends
from collectors.youtube_trends import fetch_youtube_trends
from collectors.reddit_trends import fetch_reddit_trends
from collectors.bing_trends import fetch_bing_trends
from collectors.tiktok_trends import fetch_tiktok_trends


COLLECTION_INTERVAL_SECONDS = 6 * 60 * 60

app = FastAPI(
    title="Trend Collector Service",
    description="Collects and exposes trending topics for Responsible Ones.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# TREND COLLECTION
# ============================================================

def collect_all_trends() -> Dict[str, List[str]]:
    sources_and_functions = {
        "google_trends": fetch_google_trends,
        "youtube_trends": fetch_youtube_trends,
        "reddit_trends": fetch_reddit_trends,
        "bing_trends": fetch_bing_trends,
        "tiktok_trends": fetch_tiktok_trends,
    }

    summary: Dict[str, List[str]] = {}

    for source, func in sources_and_functions.items():
        try:
            topics = func()
            save_trends(source, topics)
            summary[source] = topics
        except Exception as e:
            summary[source] = [f"Error collecting trends: {e}"]

    return summary


def scheduler_loop():
    while True:
        print(f"[Scheduler] Collecting trends at {datetime.utcnow().isoformat()}...")
        summary = collect_all_trends()
        print(f"[Scheduler] Collection complete. Summary: {summary}")
        time.sleep(COLLECTION_INTERVAL_SECONDS)


@app.on_event("startup")
def on_startup():
    print("[Startup] Initializing database...")
    init_db()
    print("[Startup] Database ready.")

    print("PUBLIC URL:", os.environ.get("REPLIT_URL"))

    print("[Startup] Starting scheduler thread...")
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    print("[Startup] Scheduler thread started.")


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "message": "Trend Collector Service is running.",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================
# TRENDS
# ============================================================

@app.post("/collect")
def collect_now() -> Dict[str, Any]:
    summary = collect_all_trends()
    return {
        "status": "ok",
        "collected_at": datetime.utcnow().isoformat(),
        "summary": summary,
    }


@app.get("/trends")
def get_trends(limit: int = 50) -> Dict[str, Any]:
    trends = get_latest_trends(limit=limit)
    return {
        "status": "ok",
        "count": len(trends),
        "trends": trends,
    }


# ============================================================
# CLARITY ENGINE
# ============================================================

def analyze_situation(text: str) -> dict:
    t = text.lower()

    issue = None
    constraints = []
    choices = []
    confidence = 0.0

    if any(word in t for word in ["fall", "fell", "slipped"]):
        issue = "A fall has created a safety and care decision."
        constraints.append("Immediate safety concerns")
        confidence += 0.25

    if "memory" in t or "wandering" in t or "confused" in t:
        issue = "Cognitive decline is affecting daily safety."
        constraints.append("Cognitive impairment")
        confidence += 0.25

    if "can't stay home" in t or "not safe at home" in t:
        issue = issue or "The current home is no longer a safe environment."
        constraints.append("Home environment mismatch")
        confidence += 0.2

    if "no money" in t or "can't afford" in t or "broke" in t:
        constraints.append("Financial limitations")
        confidence += 0.2

    if "lawyer" in t or "attorney" in t:
        choices.append("Contact an elder law or estate attorney")
        confidence += 0.1

    if not issue:
        issue = "A situation requiring clarity and next-step planning."

    if not choices:
        choices.append("Identify the immediate concern and define the next safe step")

    summary = (
        f"{issue} "
        f"Constraints: {', '.join(constraints) if constraints else 'None identified'}. "
        f"Choices: {', '.join(choices)}."
    )

    return {
        "rawInput": text,
        "issue": issue,
        "constraints": constraints,
        "choices": choices,
        "summary": summary,
        "confidence": round(min(confidence, 1.0), 2),
    }


@app.post("/clarity")
async def clarity(request: Request):
    data = await request.json()
    text = data.get("text", "")

    result = analyze_situation(text)

    return {
        "status": "ok",
        "output": result
    }


# ============================================================
# CONTENT ENGINE
# ============================================================

@app.post("/generate-content")
async def generate_content(request: Request):
    body = await request.json()

    # Extract trend and niche exactly as sent by the frontend
    trend = body.get("trend")
    niche = body.get("niche")

    # Validate: trend must exist
    if not trend or not str(trend).strip():
        return {
            "status": "error",
            "message": "Trend is required but was not provided by the frontend."
        }

    # Validate: niche must exist
    if not niche or not str(niche).strip():
        return {
            "status": "error",
            "message": "Niche is required but was not provided by the frontend."
        }

    # --- REAL CLAUDE GENERATION LOGIC ---
    from anthropic import Anthropic
    import json
    import os

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""
You are an expert real estate content strategist writing for Kevin Lundy of HomeBridge Group in Denver.
You write with clarity, emotional intelligence, and the Obvious Adams principle.
Avoid the words “navigate” and “transitions.”
Use “plan” or “choices” instead of “pathways.”
Tone: supportive, calm, grounded, responsible, and never salesy.

Trend: {trend}
Niche: {niche}

Generate:
1. A compelling headline
2. A thumbnail idea
3. 5–7 hashtags relevant to Denver real estate and the niche
4. A short-form social post (100–150 words)
5. A call to action that feels earned, not pushy
6. A 30-second video script

Return ONLY valid JSON in this structure:

{{
  "headline": "...",
  "thumbnail": "...",
  "hashtags": ["...", "..."],
  "post": "...",
  "cta": "...",
  "script": "..."
}}
"""

    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text
    data = json.loads(text)

    return {
        "status": "ok",
        "trend": trend,
        "niche": niche,
        "headline": data["headline"],
        "post": data["post"],
        "call_to_action": data["cta"],
        "script30": data["script"],
        "thumbnailIdea": data["thumbnail"],
        "hashtags": data["hashtags"],
    }
# ============================================================
# CONTENT QUEUE
# ============================================================

@app.post("/queue/add")
async def queue_add(request: Request):
    item = await request.json()
    add_content_to_queue(item)
    return {"status": "ok", "message": "Content added to queue."}


@app.get("/queue/list")
def queue_list():
    items = get_content_queue()

    formatted = []
    for item in items:
        formatted.append({
            "id": item["id"],
            "created_at": item["created_at"],
            "headline": item["headline"],
            "post": item["post"],                     # ⭐ REQUIRED FOR PREVIEW
            "call_to_action": item["call_to_action"],
            "script30": item["script30"],
            "thumbnailIdea": item["thumbnailIdea"],
            "hashtags": item["hashtags"],
            "niche": item["niche"],
            "status": item["status"]
        })

    return {"status": "ok", "items": formatted}


@app.post("/queue/status")
async def queue_status(request: Request):
    """
    Update the status of a content_queue item.
    Expects JSON: { "id": <int>, "status": "ready" }
    """
    data = await request.json()
    item_id = data.get("id")
    new_status = data.get("status")

    if item_id is None or new_status is None:
        return {
            "status": "error",
            "message": "Both 'id' and 'status' are required."
        }

    try:
        item_id_int = int(item_id)
    except (TypeError, ValueError):
        return {
            "status": "error",
            "message": "Invalid 'id' value."
        }

    update_content_status(item_id_int, new_status)
    return {"status": "ok"}
    # ============================================================
# PUBLISH ENDPOINT
# ============================================================

@app.post("/queue/publish")
async def queue_publish(request: Request):
    """
    Publish a content_queue item.
    Returns a formatted block of content and updates status to 'published'.
    """
    data = await request.json()
    item_id = data.get("id")

    if item_id is None:
        return {"status": "error", "message": "'id' is required."}

    try:
        item_id_int = int(item_id)
    except (TypeError, ValueError):
        return {"status": "error", "message": "Invalid 'id' value."}

    # Fetch the item
    items = get_content_queue()
    item = next((i for i in items if i["id"] == item_id_int), None)

    if not item:
        return {"status": "error", "message": "Item not found."}

    # Update status to published
    update_content_status(item_id_int, "published")

    # Format content for publishing
    formatted = f"""
HEADLINE:
{item['headline']}

POST:
{item['post']}

CALL TO ACTION:
{item['call_to_action']}

30-SECOND SCRIPT:
{item['script30']}

THUMBNAIL IDEA:
{item['thumbnailIdea']}

HASHTAGS:
{', '.join(item['hashtags'])}
"""

    return {
        "status": "ok",
        "formatted": formatted.strip(),
        "item": item
    }
