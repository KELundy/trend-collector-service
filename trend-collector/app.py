import threading
import time
from datetime import datetime
from typing import Dict, Any, List
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, save_trends, get_latest_trends

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


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "message": "Trend Collector Service is running.",
        "timestamp": datetime.utcnow().isoformat(),
    }


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


# -----------------------------
# REAL CLARITY ENGINE BACKEND
# -----------------------------

def analyze_situation(text: str) -> dict:
    t = text.lower()

    issue = None
    constraints = []
    choices = []
    confidence = 0.0

    # Issue detection
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
