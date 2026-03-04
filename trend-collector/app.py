import threading
import time
from datetime import datetime
from typing import Dict, Any, List
import os
import json
import sys
import sqlite3

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
from database import DB_NAME

from collectors.google_trends import fetch_google_trends
from collectors.youtube_trends import fetch_youtube_trends
from collectors.reddit_trends import fetch_reddit_trends
from collectors.bing_trends import fetch_bing_trends
from collectors.tiktok_trends import fetch_tiktok_trends

# ---------------------------------------------------------
# AUTH — NEW ADDITION (line 1 of 3)
# ---------------------------------------------------------
from auth import router as auth_router, init_users_table

# ---------------------------------------------------------
# CONTENT ENGINE ROUTER
# ---------------------------------------------------------
from content_engine import router as content_engine_router

# ---------------------------------------------------------
# CLAUDE CLASSIFICATION HELPER
# ---------------------------------------------------------
from anthropic import Anthropic

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def classify_topic_to_niches(topic: str) -> list[str]:
    prompt = f"""
    You are a real estate niche classifier. Given a trend topic, return a JSON list
    of real estate niches it belongs to. No explanation, only JSON.

    Trend topic: "{topic}"
    """
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    try:
        return json.loads(response.content[0].text)
    except Exception:
        return []

# ---------------------------------------------------------
# TREND COLLECTION LOGIC
# ---------------------------------------------------------
def collect_all_trends() -> Dict[str, Any]:
    raw = {
        "google": fetch_google_trends(),
        "youtube": fetch_youtube_trends(),
        "reddit": fetch_reddit_trends(),
        "bing": fetch_bing_trends(),
        "tiktok": fetch_tiktok_trends(),
        "timestamp": datetime.utcnow().isoformat(),
    }

    classified = {}

    for source, items in raw.items():
        if source == "timestamp":
            continue

        for item in items:
            if isinstance(item, dict):
                topic = (
                    item.get("topic")
                    or item.get("title")
                    or item.get("query")
                    or json.dumps(item)
                )
            else:
                topic = str(item)

            niches = classify_topic_to_niches(topic)

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
    """Background worker that collects trends every 6 hours."""
    while True:
        try:
            print("[Trend Collector] Collecting trends...")
            classified = collect_all_trends()
            for niche, niche_trends in classified.items():
                save_trends(niche_trends, niche)
            print("[Trend Collector] Trends saved.")
        except Exception as e:
            print(f"[Trend Collector] Error: {e}")
        time.sleep(6 * 60 * 60)


COLLECTION_INTERVAL_SECONDS = 6 * 60 * 60

app = FastAPI(
    title="Trend Collector + Content Engine Service",
    description="Unified backend for trend collection and content generation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    print("[Startup] Initializing database...")
    init_db()

    # AUTH — NEW ADDITION (line 2 of 3)
    print("[Startup] Initializing users table...")
    init_users_table()

    print("[Startup] Running DB migrations...")
    migrate_add_niche_column()

    print("[Startup] Starting background trend collector thread...")
    thread = threading.Thread(target=trend_collection_worker, daemon=True)
    thread.start()


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
# TREND ENDPOINTS
# ---------------------------------------------------------
@app.get("/trends/latest")
async def latest_trends():
    return get_latest_trends()


@app.get("/trends/by-niche")
async def trends_by_niche(niche: str):
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
        "google": [], "youtube": [], "reddit": [],
        "bing": [], "tiktok": [],
        "timestamp": datetime.utcnow().isoformat()
    }

    for source, topic, collected_at in rows:
        if source in grouped:
            grouped[source].append({"topic": topic, "collected_at": collected_at})

    all_topics = []
    for src in ["google", "youtube", "reddit", "bing", "tiktok"]:
        all_topics.extend([t["topic"] for t in grouped[src] if t.get("topic")])

    if not all_topics:
        grouped["google"] = [{
            "topic": f"Rising interest in {niche} this week",
            "collected_at": datetime.utcnow().isoformat()
        }]

    return grouped


# ---------------------------------------------------------
# CONTENT QUEUE ENDPOINTS
# ---------------------------------------------------------
@app.post("/queue/add")
async def queue_add(item: Dict[str, Any]):
    return add_content_to_queue(item)


@app.get("/queue/list")
async def queue_list():
    return get_content_queue()


@app.post("/queue/update-status")
async def queue_update_status(payload: Dict[str, Any]):
    item_id = payload.get("id")
    status = payload.get("status")
    return update_content_status(item_id, status)


# ---------------------------------------------------------
# PUBLISH ENDPOINT
# ---------------------------------------------------------
@app.post("/publish")
async def publish_item(payload: Dict[str, Any]):
    try:
        conn = sqlite3.connect("content.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO published (headline, thumbnailIdea, hashtags, post, cta, script, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.get("headline"),
            payload.get("thumbnailIdea"),
            payload.get("hashtags"),
            payload.get("post"),
            payload.get("cta"),
            payload.get("script"),
            payload.get("generated_at")
        ))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return {"success": True, "id": new_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------
# ROUTERS — AUTH + CONTENT ENGINE
# AUTH — NEW ADDITION (line 3 of 3)
# ---------------------------------------------------------
app.include_router(auth_router)
app.include_router(content_engine_router)


# ---------------------------------------------------------
# ROOT
# ---------------------------------------------------------
@app.get("/")
async def root():
    return {
        "service": "Trend Collector + Content Engine",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }
