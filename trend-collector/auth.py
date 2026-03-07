# auth.py — HomeBridge Authentication
# Handles register, login, and token verification

import os
import sqlite3
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()

DB_NAME = os.getenv("DB_PATH", "/data/homebridge.db")
JWT_SECRET = os.getenv("JWT_SECRET", "homebridge-secret-change-in-production")
JWT_EXPIRY_DAYS = 30


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str
    password: str
    agent_name: str
    brokerage:   Optional[str] = ""
    role:        Optional[str] = "agent"   # "agent" | "broker"
    office_code: Optional[str] = ""        # broker's invite code for agent signup

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    agent_name: str
    brokerage: str
    is_active: bool
    created_at: str


# ─────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────

def _normalize_user(d: dict) -> dict:
    """Ensure all expected fields exist regardless of schema version."""
    return {
        "id":           d.get("id"),
        "email":        d.get("email", ""),
        "password_hash":d.get("password_hash", ""),
        "agent_name":   d.get("agent_name", ""),
        "brokerage":    d.get("brokerage", ""),
        "phone":        d.get("phone", ""),
        "is_active":    bool(d.get("is_active", 1)),
        "created_at":   d.get("created_at", ""),
        "role":         d.get("role", "agent"),
        "broker_id":    d.get("broker_id", None),
    }

def make_office_code(user_id: int) -> str:
    """Generate a stable, short office invite code from broker user_id."""
    import hashlib
    raw = f"hb-office-{user_id}-secret"
    return hashlib.sha256(raw.encode()).hexdigest()[:8].upper()

def get_broker_by_code(office_code: str):
    """Find a broker by their office invite code."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE role = 'broker' AND is_active = 1")
    rows = c.fetchall()
    conn.close()
    for row in rows:
        d = dict(row)
        if make_office_code(d["id"]) == office_code.upper().strip():
            return _normalize_user(d)
    return None

def init_users_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            brokerage TEXT DEFAULT \'\',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Non-destructive migrations — safe to run on existing DB
    for col, defn in [
        ("role",      "TEXT DEFAULT \'agent\'"),
        ("broker_id", "INTEGER DEFAULT NULL"),
        ("phone",     "TEXT DEFAULT \'\' "),
    ]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
        except Exception:
            pass  # Column already exists
    conn.commit()
    conn.close()

def get_user_by_email(email: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    cols = [d[0] for d in c.description]
    conn.close()
    d = dict(zip(cols, row))
    return _normalize_user(d)

def get_user_by_id(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    cols = [d[0] for d in c.description]
    conn.close()
    d = dict(zip(cols, row))
    return _normalize_user(d)

def create_user(email: str, password: str, agent_name: str, brokerage: str,
               role: str = "agent", broker_id: int = None):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute(
            """INSERT INTO users (email, password_hash, agent_name, brokerage, role, broker_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (email.lower().strip(), hashed, agent_name.strip(), brokerage.strip(), role, broker_id)
        )
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        conn.close()
        return None


# ─────────────────────────────────────────────
# JWT HELPERS
# ─────────────────────────────────────────────
def create_token(user_id: int, email: str, role: str = "agent") -> str:
    payload = {
        "sub":   str(user_id),
        "email": email,
        "role":  role,
        "exp":   datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token. Please log in again.")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    user = get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account disabled. Contact support@homebridgegroup.co")
    return user


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────
@router.post("/register")
def register(body: RegisterRequest):
    if not body.email or not body.password or not body.agent_name:
        raise HTTPException(status_code=400, detail="Email, password, and agent name are required.")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    # Resolve broker_id from office_code if provided
    broker_id  = None
    brokerage  = body.brokerage or ""
    role       = body.role or "agent"

    if body.office_code and role == "agent":
        broker = get_broker_by_code(body.office_code)
        if not broker:
            raise HTTPException(status_code=400, detail="Invalid office code. Please check with your broker.")
        broker_id = broker["id"]
        if not brokerage:
            brokerage = broker["brokerage"] or broker["agent_name"]

    user = create_user(body.email, body.password, body.agent_name, brokerage, role, broker_id)
    if not user:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    token = create_token(user["id"], user["email"], user["role"])
    return {
        "token": token,
        "user": {
            "id":         user["id"],
            "email":      user["email"],
            "agent_name": user["agent_name"],
            "brokerage":  user["brokerage"],
            "role":       user["role"],
            "broker_id":  user["broker_id"],
        }
    }


@router.post("/login")
def login(body: LoginRequest):
    user = get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account disabled. Contact support@homebridgegroup.co")

    token = create_token(user["id"], user["email"], user.get("role", "agent"))
    return {
        "token": token,
        "user": {
            "id":         user["id"],
            "email":      user["email"],
            "agent_name": user["agent_name"],
            "brokerage":  user["brokerage"],
            "role":       user.get("role", "agent"),
            "broker_id":  user.get("broker_id", None),
        }
    }


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return {
        "id":         current_user["id"],
        "email":      current_user["email"],
        "agent_name": current_user["agent_name"],
        "brokerage":  current_user["brokerage"],
        "role":       current_user.get("role", "agent"),
        "broker_id":  current_user.get("broker_id", None),
    }


# ─────────────────────────────────────────────
# BROKER ENDPOINTS
# ─────────────────────────────────────────────

@router.get("/broker/office-code")
def get_office_code(current_user=Depends(get_current_user)):
    """Return the broker's unique invite code for agent signup."""
    if current_user.get("role") != "broker":
        raise HTTPException(status_code=403, detail="Broker accounts only.")
    code = make_office_code(current_user["id"])
    return {"office_code": code, "broker_id": current_user["id"]}


@router.get("/broker/agents")
def broker_get_agents(current_user=Depends(get_current_user)):
    """Return all agents linked to this broker."""
    if current_user.get("role") not in ("broker", "admin"):
        raise HTTPException(status_code=403, detail="Broker accounts only.")
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, email, agent_name, brokerage, is_active, created_at, role
        FROM users
        WHERE broker_id = ? AND role = 'agent'
        ORDER BY agent_name ASC
    """, (current_user["id"],))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id":         r["id"],
            "email":      r["email"],
            "agent_name": r["agent_name"],
            "brokerage":  r["brokerage"],
            "is_active":  bool(r["is_active"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ─────────────────────────────────────────────
# ADMIN — disable/enable a user
# ─────────────────────────────────────────────
@router.post("/admin/set-active")
def set_active(payload: dict, current_user=Depends(get_current_user)):
    # Only user id=1 (first registered = you) can do this
    if current_user["id"] != 1 and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    target_id = payload.get("user_id")
    active    = payload.get("is_active", True)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if active else 0, target_id))
    conn.commit()
    conn.close()
    return {"success": True, "user_id": target_id, "is_active": active}


@router.get("/admin/users")
def list_users(current_user=Depends(get_current_user)):
    if current_user["id"] != 1 and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.email, u.agent_name, u.brokerage,
               u.is_active, u.created_at,
               COALESCE(u.role, 'agent') as role,
               u.broker_id,
               COUNT(cl.id) as content_count
        FROM users u
        LEFT JOIN content_library cl ON cl.user_id = u.id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id":            r["id"],
            "email":         r["email"],
            "agent_name":    r["agent_name"],
            "brokerage":     r["brokerage"] or "",
            "is_active":     bool(r["is_active"]),
            "created_at":    r["created_at"],
            "role":          r["role"] or "agent",
            "broker_id":     r["broker_id"],
            "content_count": r["content_count"] or 0,
        }
        for r in rows
    ]


@router.post("/admin/set-role")
def set_role(payload: dict, current_user=Depends(get_current_user)):
    """Promote/demote a user's role. Admin only."""
    if current_user["id"] != 1 and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    target_id = payload.get("user_id")
    role      = payload.get("role", "agent")
    if role not in ("agent", "broker", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role.")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET role = ? WHERE id = ?", (role, target_id))
    conn.commit()
    conn.close()
    return {"success": True, "user_id": target_id, "role": role}


@router.get("/admin/stats")
def platform_stats(current_user=Depends(get_current_user)):
    """Platform-wide stats for the admin dashboard."""
    if current_user["id"] != 1 and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT COUNT(*) as cnt FROM users WHERE is_active = 1")
    total_users = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM users WHERE role = 'broker' AND is_active = 1")
    total_brokers = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM users WHERE role = 'agent' AND is_active = 1")
    total_agents = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM content_library")
    total_content = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM content_library WHERE status = 'published'")
    total_published = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM schedules WHERE active = 1")
    active_schedules = c.fetchone()["cnt"]

    c.execute("""
        SELECT COUNT(*) as cnt FROM content_library
        WHERE saved_at >= datetime('now', '-7 days')
    """)
    content_this_week = c.fetchone()["cnt"]

    # New users last 30 days
    c.execute("""
        SELECT COUNT(*) as cnt FROM users
        WHERE created_at >= datetime('now', '-30 days')
    """)
    new_users_30d = c.fetchone()["cnt"]

    conn.close()
    return {
        "total_users":       total_users,
        "total_brokers":     total_brokers,
        "total_agents":      total_agents,
        "total_content":     total_content,
        "total_published":   total_published,
        "active_schedules":  active_schedules,
        "content_this_week": content_this_week,
        "new_users_30d":     new_users_30d,
    }


# ─────────────────────────────────────────────
# PROFILE UPDATE
# ─────────────────────────────────────────────
class ProfileUpdateRequest(BaseModel):
    agent_name: str
    brokerage:  Optional[str] = ""
    email:      str
    phone:      Optional[str] = ""

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password:     str

@router.post("/profile")
def update_profile(body: ProfileUpdateRequest, current_user=Depends(get_current_user)):
    if not body.agent_name or not body.email:
        raise HTTPException(status_code=400, detail="Name and email are required.")

    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()

    # Add phone column if it doesn't exist yet
    try:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass  # Column already exists

    # Check email not taken by another user
    c.execute("SELECT id FROM users WHERE email = ? AND id != ?", (body.email.lower().strip(), current_user["id"]))
    if c.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="That email is already in use by another account.")

    c.execute("""
        UPDATE users SET agent_name=?, brokerage=?, email=?, phone=? WHERE id=?
    """, (body.agent_name.strip(), body.brokerage or "", body.email.lower().strip(), body.phone or "", current_user["id"]))
    conn.commit()
    conn.close()

    updated = get_user_by_id(current_user["id"])
    return {
        "success": True,
        "user": {
            "id":         updated["id"],
            "email":      updated["email"],
            "agent_name": updated["agent_name"],
            "brokerage":  updated["brokerage"],
            "phone":      updated.get("phone", ""),
        }
    }


@router.post("/change-password")
def change_password(body: PasswordChangeRequest, current_user=Depends(get_current_user)):
    if not bcrypt.checkpw(body.current_password.encode(), current_user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")

    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, current_user["id"]))
    conn.commit()
    conn.close()
    return {"success": True}
