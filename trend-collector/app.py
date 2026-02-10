import threading
import time
from datetime import datetime
from typing import Dict, Any, List
import os  # NEW: needed to print the public URL

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, save_trends, get_latest_trends

from collectors.google_trends import fetch_google_trends
from collectors.youtube_trends import fetch_youtube_trends
from collectors.reddit_trends import fetch_reddit_trends
from collectors.bing_trends import fetch_bing_trends
from collectors.tiktok_trends import fetch_tiktok_trends

# 6 hours in seconds
COLLECTION_INTERVAL_SECONDS = 6 * 60 * 60

app = FastAPI(
    title="Trend Collector Service",
    description="Collects and exposes trending topics for Responsible Ones.",
    version="0.1.0",
)

# Allow your future dashboard / command center to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can tighten this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def collect_all_trends() -> Dict[str, List[str]]:
    """
    Calls all collectors, saves their results, and returns a summary.
    """
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
    """
    Background loop that runs every COLLECTION_INTERVAL_SECONDS.
    """
    while True:
        print(
            f"[Scheduler] Collecting trends at {datetime.utcnow().isoformat()}..."
        )
        summary = collect_all_trends()
        print(f"[Scheduler] Collection complete. Summary: {summary}")
        time.sleep(COLLECTION_INTERVAL_SECONDS)


@app.on_event("startup")
def on_startup():
    """
    Initialize the database and start the background scheduler thread.
    """
    print("[Startup] Initializing database...")
    init_db()
    print("[Startup] Database ready.")

    # ⭐ NEW: Force Replit to reveal the public URL
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
    """
    Manually trigger a collection run (e.g., from your Command Center).
    """
    summary = collect_all_trends()
    return {
        "status": "ok",
        "collected_at": datetime.utcnow().isoformat(),
        "summary": summary,
    }


@app.get("/trends")
def get_trends(limit: int = 50) -> Dict[str, Any]:
    """
    Get the latest stored trends (for your dashboard).
    """
    trends = get_latest_trends(limit=limit)
    return {
        "status": "ok",
        "count": len(trends),
        "trends": trends,
    }


# For local running: uvicorn app:app --reload
# In Replit, you'll configure the run command to use uvicorn.
