import threading
import time
from datetime import datetime
from typing import Dict, Any, List
import os
import json
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Ensure local imports resolve correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Local modules
from database import (
    init_db,
    save_trends,
    get_latest_trends,
    add_content_to_queue,
    get_content_queue,
    update_content_status,
)
from database import migrate_add_niche_column
migrate_add_niche_column()

from collectors.google_trends import fetch_google_trends
from collectors.youtube_trends import fetch_youtube_trends
from collectors.reddit_trends import fetch_reddit_trends
from collectors.bing_trends import fetch_bing_trends
from collectors.tiktok_trends import fetch_tiktok_trends

# NEW: Content Engine router
from content_engine import router as content_engine_router


COLLECTION_INTERVAL_SECONDS = 6 * 60 * 60  # 6 hours

app = FastAPI(
    title="Trend Collector + Content Engine Service",
    description="Unified backend for trend collection and content generation",
    version="1.0.0",
)

# CORS — allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "message": "Trend Collector + Content Engine Service is running.",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------
# TREND COLLECTION LOGIC
# ---------------------------------------------------------
def collect_all_trends() -> Dict[str, Any]:
    """Collect trends from all sources and return a combined dictionary."""
    return {
        "google": fetch_google_trends(),
        "youtube": fetch_youtube_trends(),
        "reddit": fetch_reddit_trends(),
        "bing": fetch_bing_trends(),
        "tiktok": fetch_tiktok_trends(),
        "timestamp": datetime.utcnow().isoformat(),
    }


def trend_collection_worker():
    """Background worker that collects trends every X hours."""
    while True:
        try:
            print("[Trend Collector] Collecting trends...")
            trends = collect_all_trends()
            save_trends(trends)
            print("[Trend Collector] Trends saved.")
        except Exception as e:
            print(f"[Trend Collector] Error: {e}")
        time.sleep(COLLECTION_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup_event():
    """Initialize DB and start background trend collector."""
    print("[Startup] Initializing database...")
    init_db()

    print("[Startup] Starting background trend collector thread...")
    thread = threading.Thread(target=trend_collection_worker, daemon=True)
    thread.start()


# ---------------------------------------------------------
# TREND ENDPOINTS
# ---------------------------------------------------------
@app.get("/trends/latest")
async def latest_trends():
    """Return the most recently collected trends."""
    return get_latest_trends()


# ---------------------------------------------------------
# CONTENT QUEUE ENDPOINTS
# ---------------------------------------------------------
@app.post("/queue/add")
async def queue_add(item: Dict[str, Any]):
    """Add generated content to the queue."""
    return add_content_to_queue(item)


@app.get("/queue/list")
async def queue_list():
    """Return all queued content."""
    return get_content_queue()


@app.post("/queue/update-status")
async def queue_update_status(payload: Dict[str, Any]):
    """Update the status of a queued content item."""
    item_id = payload.get("id")
    status = payload.get("status")
    return update_content_status(item_id, status)


# ---------------------------------------------------------
# NEW: CONTENT ENGINE ROUTES
# ---------------------------------------------------------
app.include_router(content_engine_router)


# ---------------------------------------------------------
# ROOT ENDPOINT
# ---------------------------------------------------------
@app.get("/")
async def root():
    return {
        "service": "Trend Collector + Content Engine",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }
