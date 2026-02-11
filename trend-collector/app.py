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
    trend = body.get("trend") or "Adult child in Denver dealing with an inherited home after a parent’s health crisis."
    niche = body.get("niche") or "probate real estate"

    headline = "What To Do With an Inherited Home in Denver (Without Breaking Your Family)"

    post = (
        "If you’ve just inherited a home in Denver after a parent’s health crisis or passing, "
        "you’re not alone—and you’re not supposed to have all the answers.\n\n"
        "The real tension usually isn’t about the house. It’s about grief, guilt, and siblings who "
        "see the situation differently. Before you rush into a quick sale or let the home sit vacant, "
        "you need a clear, step-by-step plan that protects the estate, honors your parent, and keeps "
        "the family intact.\n\n"
        "At The HomeBridge Group, we specialize in guiding The Responsible One—the person who quietly "
        "takes on everything—through inherited property decisions in Denver. From timelines and repairs "
        "to legal coordination and selling strategies, we help you turn a stressful inheritance into a "
        "thoughtful transition."
    )

    cta = (
        "If you’re staring at an inherited home and a stack of unanswered questions, start with a "
        "20-minute call. No pressure, no sales pitch—just clarity on your options in Denver’s real market."
    )

    script30 = (
        "If you’ve just inherited a home in Denver after a parent’s health crisis or passing, you’re "
        "probably carrying more than anyone can see.\n\n"
        "The house, the paperwork, the siblings, the decisions—none of it is simple. At The HomeBridge "
        "Group, we work with the person who ends up responsible for all of it. In about 20 minutes, we "
        "can walk you through your real options for the property, the timeline, and the family.\n\n"
        "If that’s you, and you’re tired of feeling like you have to figure it out alone, reach out. "
        "You don’t have to carry this by yourself."
    )

    thumbnailIdea = (
        "A calm, well-lit Denver home exterior at dusk with subtle overlay text: "
        "'Inherited Home? Start Here.' No people—just stability and guidance."
    )

    hashtags = [
        "#DenverRealEstate",
        "#InheritedHome",
        "#ProbateRealEstate",
        "#SeniorTransition",
        "#TheResponsibleOne",
        "#HomeBridgeGroup",
    ]

    return {
        "status": "ok",
        "trend": trend,
        "niche": niche,
        "headline": headline,
        "post": post,
        "call_to_action": cta,
        "script30": script30,
        "thumbnailIdea": thumbnailIdea,
        "hashtags": hashtags,
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
