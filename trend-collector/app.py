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

from collectors.google_trends import fetch_google_trends
from collectors.youtube_trends import fetch_youtube_trends
from collectors.reddit_trends import fetch_reddit_trends
from collectors.bing_trends import fetch_bing_trends
from collectors.tiktok_trends import fetch_tiktok_trends

# ---------------------------------------------------------
# TREND COLLECTION LOGIC (WITH CLASSIFICATION)
# ---------------------------------------------------------
def collect_all_trends() -> Dict[str, Any]:
    """
    Collect global trends, classify each topic into niches using Claude,
    and return a dictionary grouped by niche.
    """

    # 1. Collect raw global trends
    raw = {
        "google": fetch_google_trends(),
        "youtube": fetch_youtube_trends(),
        "reddit": fetch_reddit_trends(),
        "bing": fetch_bing_trends(),
        "tiktok": fetch_tiktok_trends(),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # 2. Build a niche-grouped structure
    classified = {}

    for source, items in raw.items():
        if source == "timestamp":
            continue

        for item in items:
            topic = (
                item.get("topic")
                or item.get("title")
                or item.get("query")
                or json.dumps(item)
            )

            # 3. Classify topic into niches
            niches = classify_topic_to_niches(topic)

            # 4. Store topic under each niche
            for niche in niches:
                if niche not in classified:
                    classified[niche] = {
                        "google": [],
                        "youtube": [],
                        "reddit": [],
                        "bing": [],
                        "tiktok": [],
                        "timestamp": raw["timestamp"]
                    }

                classified[niche][source].append({"topic": topic})

    return classified

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
    """
    Collect global trends, classify each topic into niches using Claude,
    and return a dictionary grouped by niche.
    """

    # 1. Collect raw global trends
    raw = {
        "google": fetch_google_trends(),
        "youtube": fetch_youtube_trends(),
        "reddit": fetch_reddit_trends(),
        "bing": fetch_bing_trends(),
        "tiktok": fetch_tiktok_trends(),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # 2. Build a niche-grouped structure
    classified = {}

    for source, items in raw.items():
        if source == "timestamp":
            continue

        for item in items:
            # Normalize topic into a string
            if isinstance(item, dict):
                topic = (
                    item.get("topic")
                    or item.get("title")
                    or item.get("query")
                    or json.dumps(item)
                )
            else:
                # Item is already a string
                topic = str(item)

            # 3. Classify topic into niches
            niches = classify_topic_to_niches(topic)

            # 4. Store topic under each niche
            for niche in niches:
                if niche not in classified:
                    classified[niche] = {
                        "google": [],
                        "youtube": [],
                        "reddit": [],
                        "bing": [],
                        "tiktok": [],
                        "timestamp": raw["timestamp"]
                    }

                classified[niche][source].append({"topic": topic})


    return classified


def trend_collection_worker():
    """Background worker that collects trends every X hours."""
    while True:
        try:
            print("[Trend Collector] Collecting trends...")
            classified = collect_all_trends()
            for niche, niche_trends in classified.items():
                save_trends(niche_trends, niche)
            print("[Trend Collector] Trends saved.")
        except Exception as e:
            print(f"[Trend Collector] Error: {e}")
        time.sleep(COLLECTION_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup_event():
    """Initialize DB and start background trend collector."""
    print("[Startup] Initializing database...")
    init_db()

    print("[Startup] Running DB migrations...")
    migrate_add_niche_column()

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
# TRENDS BY NICHE ENDPOINT
# ---------------------------------------------------------
@app.get("/trends/by-niche")
async def trends_by_niche(niche: str):
    """
    Return trends filtered by niche, grouped by source.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT source, topic, collected_at
        FROM trends
        WHERE niche = ?
        ORDER BY collected_at DESC
        LIMIT 200
    """, (niche,))

    rows = c.fetchall()
    conn.close()

    grouped = {
        "google": [],
        "youtube": [],
        "reddit": [],
        "bing": [],
        "tiktok": [],
        "timestamp": datetime.utcnow().isoformat()
    }

    for source, topic, collected_at in rows:
        if source in grouped:
            grouped[source].append({
                "topic": topic,
                "collected_at": collected_at
            })

    return grouped

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
