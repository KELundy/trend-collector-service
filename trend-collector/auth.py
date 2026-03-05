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

DB_NAME = "/data/homebridge.db"
JWT_SECRET = os.getenv("JWT_SECRET", "homebridge-secret-change-in-production")
JWT_EXPIRY_DAYS = 30


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str
    password: str
    agent_name: str
    brokerage: Optional[str] = ""

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
def init_users_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            brokerage TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
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
    return {
        "id": row[0], "email": row[1], "password_hash": row[2],
        "agent_name": row[3], "brokerage": row[4],
        "is_active": bool(row[5]), "created_at": row[6]
    }

def get_user_by_id(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "email": row[1], "password_hash": row[2],
        "agent_name": row[3], "brokerage": row[4],
        "is_active": bool(row[5]), "created_at": row[6]
    }

def create_user(email: str, password: str, agent_name: str, brokerage: str):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (email, password_hash, agent_name, brokerage) VALUES (?, ?, ?, ?)",
            (email.lower().strip(), hashed, agent_name.strip(), brokerage.strip())
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
def create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS)
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
        raise HTTPException(status_code=403, detail="Account disabled. Contact support.")
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

    user = create_user(body.email, body.password, body.agent_name, body.brokerage or "")
    if not user:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    token = create_token(user["id"], user["email"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "agent_name": user["agent_name"],
            "brokerage": user["brokerage"],
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
        raise HTTPException(status_code=403, detail="Account disabled. Contact support.")

    token = create_token(user["id"], user["email"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "agent_name": user["agent_name"],
            "brokerage": user["brokerage"],
        }
    }


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "agent_name": current_user["agent_name"],
        "brokerage": current_user["brokerage"],
    }


# ─────────────────────────────────────────────
# ADMIN — disable/enable a user
# ─────────────────────────────────────────────
@router.post("/admin/set-active")
def set_active(payload: dict, current_user=Depends(get_current_user)):
    # Only user id=1 (first registered = you) can do this
    if current_user["id"] != 1:
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
    if current_user["id"] != 1:
        raise HTTPException(status_code=403, detail="Admin only.")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, email, agent_name, brokerage, is_active, created_at FROM users ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "email": r[1], "agent_name": r[2], "brokerage": r[3], "is_active": bool(r[4]), "created_at": r[5]} for r in rows]


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
