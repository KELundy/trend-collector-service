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
    "office_starter_monthly":  os.getenv("STRIPE_PRICE_OFFICE_STARTER_MONTHLY", ""),
    "office_starter_annual":   os.getenv("STRIPE_PRICE_OFFICE_STARTER_ANNUAL",  ""),
    "office_growth_monthly":   os.getenv("STRIPE_PRICE_OFFICE_GROWTH_MONTHLY",  ""),
    "office_growth_annual":    os.getenv("STRIPE_PRICE_OFFICE_GROWTH_ANNUAL",   ""),
    "office_team_monthly":     os.getenv("STRIPE_PRICE_OFFICE_TEAM_MONTHLY",    ""),
    "office_team_annual":      os.getenv("STRIPE_PRICE_OFFICE_TEAM_ANNUAL",     ""),
}

OFFICE_SEAT_LIMITS = {
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
    migrate_context_column, tag_existing_as_marketing,
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

# ── Safe fallbacks in case database.py is older version ──
try:
    from database import migrate_context_column, tag_existing_as_marketing
except ImportError:
    def migrate_context_column():
        print("[Startup] migrate_context_column not available in this database.py version")
    def tag_existing_as_marketing(user_id):
        print(f"[Startup] tag_existing_as_marketing not available — push updated database.py")

from auth import router as auth_router, get_current_user
from content_engine import router as content_engine_router, generate_content_core

from collectors.google_trends import fetch_google_trends
from collectors.youtube_trends import fetch_youtube_trends
from collectors.reddit_trends import fetch_reddit_trends
from collectors.bing_trends import fetch_bing_trends
from collectors.tiktok_trends import fetch_tiktok_trends

from anthropic import Anthropic
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

COLLECTION_INTERVAL_SECONDS = 6 * 60 * 60

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
    try:
        migrate_context_column()
        tag_existing_as_marketing(2)  # Option A: tags Kevin's existing posts as hb_marketing
    except Exception as _ctx_e:
        print(f"[Startup] Context migration skipped: {_ctx_e}")
    print("[Startup] Starting background trend collector...")
    t1 = threading.Thread(target=trend_collection_worker, daemon=True)
    t1.start()
    print("[Startup] Starting content scheduler...")
    t2 = threading.Thread(target=content_scheduler_worker, daemon=True)
    t2.start()
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
    niche: str
    frequency: str
    timeOfDay: str
    timezone: Optional[str] = "America/Denver"

class ScheduleDeleteRequest(BaseModel):
    niche: str


@app.get("/schedules")
async def get_schedules(current_user=Depends(get_current_user)):
    return {"schedules": schedules_get_all(current_user["id"])}


@app.post("/schedules")
async def upsert_schedule(body: ScheduleRequest, current_user=Depends(get_current_user)):
    schedule = schedule_upsert(user_id=current_user["id"], niche=body.niche, frequency=body.frequency, time_of_day=body.timeOfDay, timezone=body.timezone)
    return {"success": True, "schedule": schedule}


@app.delete("/schedules/{niche}")
async def delete_schedule(niche: str, current_user=Depends(get_current_user)):
    success = schedule_delete(current_user["id"], niche)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True}


class ScoreRequest(BaseModel):
    setup: dict = {}

@app.post("/identity/score")
async def get_identity_score(req: ScoreRequest, current_user=Depends(get_current_user)):
    score = calculate_identity_score(current_user["id"], req.setup)
    return score


def _compute_next_run(frequency: str, time_of_day: str) -> str:
    try:
        hour, minute = map(int, time_of_day.split(":"))
    except Exception:
        hour, minute = 8, 0
    now = datetime.utcnow()
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if frequency == "daily": delta = timedelta(days=1)
    elif frequency == "3x_week": delta = timedelta(days=2)
    else: delta = timedelta(days=7)
    if candidate <= now: candidate += delta
    return candidate.isoformat()


def content_scheduler_worker():
    print("[Scheduler] Worker started.")
    while True:
        try:
            due = schedules_get_due()
            if due: print(f"[Scheduler] {len(due)} schedule(s) due.")
            for sched in due:
                _run_scheduled_generation(sched)
        except Exception as e:
            print(f"[Scheduler] Error in worker: {e}")
        time.sleep(15 * 60)


def _run_scheduled_generation(sched: dict):
    user_id  = sched["user_id"]
    niche    = sched["niche"]
    sched_id = sched["id"]
    print(f"[Scheduler] Generating for user {user_id} / niche '{niche}'")
    try:
        from database import get_conn
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
        )
        library_save(user_id=user_id, niche=niche, content=result["content"], compliance=result["compliance"], source="scheduled")
        print(f"[Scheduler] ✓ Saved scheduled content for user {user_id} / '{niche}'")
    except Exception as e:
        print(f"[Scheduler] ✗ Generation failed for user {user_id} / '{niche}': {e}")
    finally:
        next_run = _compute_next_run(sched.get("frequency", "weekly"), sched.get("time_of_day", "08:00"))
        schedule_mark_ran(sched_id, next_run)


def classify_topic_to_niches(topic: str) -> list:
    prompt = f"""You are a real estate niche classifier. Given a trend topic, return a JSON list of real estate niches it belongs to. No explanation, only JSON.\nTrend topic: "{topic}" """
    try:
        response = anthropic_client.messages.create(model="claude-sonnet-4-20250514", max_tokens=200, messages=[{"role": "user", "content": prompt}])
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
        try:
            print("[Trend Collector] Collecting trends...")
            classified = collect_all_trends()
            for niche, niche_trends in classified.items():
                save_trends(niche_trends, niche)
            print("[Trend Collector] Done.")
        except Exception as e:
            print(f"[Trend Collector] Error: {e}")
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
    if user.get("role") not in ("admin","super_admin","staff"): raise HTTPException(403, "Admin only")
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
    if user.get("role") not in ("admin","super_admin","staff"): raise HTTPException(403, "Admin only")
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
    if user.get("role") not in ("admin","super_admin","staff"): raise HTTPException(403, "Admin only")
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
    if current_user.get("role") not in ("broker", "admin", "super_admin", "staff"):
        raise HTTPException(403, "Office managers only")
    body  = await request.json()
    name  = (body.get("name")  or "").strip()
    email = (body.get("email") or "").strip()
    if not name or not email: raise HTTPException(400, "Name and email required")
    conn = database.get_conn()
    c    = conn.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS office_invites (id INTEGER PRIMARY KEY AUTOINCREMENT, office_id INTEGER NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL, invited_at TEXT DEFAULT (datetime('now')), status TEXT DEFAULT 'pending')""")
        c.execute("INSERT INTO office_invites (office_id, name, email) VALUES (?,?,?)", (current_user["id"], name, email))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(500, f"Could not store invite: {e}")
    conn.close()
    return {"ok": True, "message": f"Invite queued for {name} ({email})"}


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
    if current_user.get("role") not in ("broker", "admin", "super_admin", "staff"):
        raise HTTPException(status_code=403, detail="Broker accounts only.")
    stats = get_broker_office_stats(current_user["id"])
    return {"agents": stats, "count": len(stats)}


@app.post("/broker/agent-compliance-report")
async def broker_agent_report(req: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ("broker", "admin", "super_admin", "staff"):
        raise HTTPException(status_code=403, detail="Broker accounts only.")
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
    c.execute("SELECT setup_data FROM user_setup WHERE user_id = ?", (user_id,))
    row   = c.fetchone()
    setup = {}
    if row:
        try:
            setup = _json.loads(row["setup_data"] or "{}")
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
    c.execute("SELECT setup_data FROM user_setup WHERE user_id = ?", (user_id,))
    row   = c.fetchone()
    setup = {}
    if row:
        try: setup = _json.loads(row["setup_data"] or "{}")
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
        c2.execute("SELECT setup_data FROM user_setup WHERE user_id = ?", (current_user["id"],))
        row2 = c2.fetchone()
        conn2.close()
        setup2 = {}
        if row2:
            try: setup2 = _json.loads(row2["setup_data"] or "{}")
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
        c2.execute("SELECT setup_data FROM user_setup WHERE user_id = ?", (current_user["id"],))
        row2 = c2.fetchone()
        c2conn.close()
        setup2 = {}
        if row2:
            try: setup2 = _json.loads(row2["setup_data"] or "{}")
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
# Roles: super_admin, staff_licensed, staff_marketing,
#        broker, agent, assistant
# ═══════════════════════════════════════════════════════════════

def _is_super_admin(user: dict) -> bool:
    return user.get("role") == "super_admin"

def _require_super_admin(user: dict):
    if not _is_super_admin(user):
        raise HTTPException(403, "Super admin access required.")

def _is_staff_or_above(user: dict) -> bool:
    return user.get("role") in ("super_admin", "staff_licensed", "staff_marketing")

def _can_use_hb_marketing(user: dict) -> bool:
    """Only super_admin, staff_licensed, and staff_marketing can use HB Marketing context."""
    return user.get("role") in ("super_admin", "staff_licensed", "staff_marketing")

def _can_have_agent_profile(user: dict) -> bool:
    """Only licensed roles can generate CIR-verified content as themselves."""
    return user.get("role") in ("super_admin", "staff_licensed", "agent")

def _can_approve_content(user: dict) -> bool:
    """Only licensed professionals can approve content and generate CIR records."""
    return user.get("role") in ("super_admin", "staff_licensed", "agent")


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

    valid_roles = ("super_admin", "staff_licensed", "staff_marketing",
                   "broker", "agent", "assistant")
    if new_role not in valid_roles:
        raise HTTPException(400, f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    if not target_id:
        raise HTTPException(400, "user_id required.")

    # is_licensed is true for roles that can generate CIR-verified content
    is_licensed = 1 if new_role in ("super_admin", "staff_licensed", "agent") else 0

    # staff_type for display
    staff_type = None
    if new_role == "staff_licensed":    staff_type = "licensed"
    elif new_role == "staff_marketing": staff_type = "marketing"

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




# ═══════════════════════════════════════════════════════════════
# ROLE SYSTEM
# Roles: super_admin > staff > broker > agent > assistant
#
# super_admin  — full control including billing and termination
# staff        — HB Marketing context only, no agent profile
# broker       — their office agents only
# agent        — their own content only
# assistant    — generate/draft for assigned agents only, no approve
# ═══════════════════════════════════════════════════════════════

def _is_super_admin(user: dict) -> bool:
    return user.get("role") == "super_admin"

def _is_admin_or_above(user: dict) -> bool:
    return user.get("role") in ("super_admin", "admin")

def _is_staff_or_above(user: dict) -> bool:
    return user.get("role") in ("super_admin", "admin", "staff")

def _require_super_admin(user: dict):
    if not _is_super_admin(user):
        raise HTTPException(403, "Super admin access required.")

def _require_staff_or_above(user: dict):
    if not _is_staff_or_above(user):
        raise HTTPException(403, "Staff access required.")


@app.get("/admin/users")
async def admin_list_users(current_user: dict = Depends(get_current_user)):
    """List all users — super_admin and staff can view."""
    _require_staff_or_above(current_user)
    from database import get_conn as _gc
    conn = _gc()
    c    = conn.cursor()
    c.execute("""
        SELECT id, email, agent_name, brokerage, role,
               is_active, created_at, plan, sub_status,
               trial_ends_at, is_licensed, staff_type, agent_slug
        FROM users
        ORDER BY created_at DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    # Remove sensitive fields for staff (non super_admin)
    if not _is_super_admin(current_user):
        for r in rows:
            r.pop("plan", None)
            r.pop("sub_status", None)
            r.pop("trial_ends_at", None)
    return {"users": rows, "total": len(rows)}


@app.post("/admin/users/{user_id}/role")
async def admin_set_role(user_id: int, request: Request,
                         current_user: dict = Depends(get_current_user)):
    """Change a user's role — super_admin only."""
    _require_super_admin(current_user)
    body = await request.json()
    new_role = str(body.get("role", "")).strip()
    valid_roles = ("super_admin", "admin", "staff", "broker", "agent", "assistant")
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
    valid_roles = ("super_admin","admin","staff","broker","agent","assistant")
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
    conn.close()
    return {
        "total_users":      total_users,
        "new_users_30d":    new_30,
        "total_brokers":    total_brokers,
        "total_agents":     total_agents,
        "total_content":    total_content,
        "content_this_week":content_week,
        "total_published":  total_published,
        "active_schedules": active_schedules,
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


@app.post("/waitlist")
async def submit_waitlist(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid request body.")

    name    = str(body.get("name",    "")).strip()[:120]
    email   = str(body.get("email",   "")).strip()[:200]
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
                name TEXT, email TEXT, role TEXT, company TEXT,
                message TEXT, submitted_at TEXT
            )
        """)
        from datetime import datetime
        c.execute(
            "INSERT INTO waitlist (name, email, role, company, message, submitted_at) VALUES (?,?,?,?,?,?)",
            (name, email, role, company, message, datetime.utcnow().isoformat())
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
            email_body = f"""New First Look Request\n\nName: {name}\nEmail: {email}\nRole: {role}\nCompany: {company}\nMessage: {message}\n\nSubmitted via homebridgegroup.co"""
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
