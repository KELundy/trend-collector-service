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
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET or JWT_SECRET == "homebridge-secret-change-in-production":
    raise RuntimeError(
        "[auth] JWT_SECRET is not configured or is still the default placeholder. "
        "Set a strong random value in Render environment variables. "
        "Generate one with: python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )
JWT_EXPIRY_DAYS = 10   # Session 52: reduced from 30; revocation mechanism added

# ── SendGrid config (graceful no-op if not configured) ──
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM    = os.getenv("SENDGRID_FROM_EMAIL", "noreply@homebridgegroup.co")
FRONTEND_URL     = os.getenv("FRONTEND_URL", "https://app.homebridgegroup.co")
SENDGRID_ENABLED = bool(SENDGRID_API_KEY)

def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send email via SendGrid. Silent no-op if not configured."""
    if not SENDGRID_ENABLED:
        print(f"[EMAIL QUEUED — SendGrid not configured] To: {to_email} | Subject: {subject}")
        return False
    try:
        import httpx
        res = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": SENDGRID_FROM, "name": "HomeBridge"},
                "subject": subject,
                "content": [{"type": "text/html", "value": html_body}],
            },
            timeout=10,
        )
        return res.status_code in (200, 202)
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str
    password: str
    agent_name: str
    brokerage:    Optional[str] = ""
    role:         Optional[str] = "agent"   # "agent" | "broker"
    office_code:  Optional[str] = ""        # broker's invite code for agent signup
    referral_code: Optional[str] = ""       # partner referral code for attribution

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
        "id":                d.get("id"),
        "email":             d.get("email", ""),
        "password_hash":     d.get("password_hash", ""),
        "agent_name":        d.get("agent_name", ""),
        "brokerage":         d.get("brokerage", ""),
        "phone":             d.get("phone", ""),
        "notification_email":d.get("notification_email", None),
        "is_active":         bool(d.get("is_active", 1)),
        "created_at":        d.get("created_at", ""),
        "role":              d.get("role", "agent"),
        "broker_id":         d.get("broker_id", None),
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
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return _normalize_user(dict(row))

def get_user_by_id(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return _normalize_user(dict(row))

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
    import re
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", body.password):
        raise HTTPException(status_code=400, detail="Password must include at least one uppercase letter.")
    if not re.search(r"[a-z]", body.password):
        raise HTTPException(status_code=400, detail="Password must include at least one lowercase letter.")
    if not re.search(r"[0-9]", body.password):
        raise HTTPException(status_code=400, detail="Password must include at least one number.")

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

    # Start 14-day trial automatically
    try:
        from database import set_trial
        set_trial(user["id"], days=14)
    except Exception:
        pass

    # Auto-enroll every new agent as a partner (Option 3 — Session 52).
    # Every agent gets a referral code silently at registration.
    # No opt-in required. Bank connection (Stripe Connect) is prompted later,
    # only when they have earnings waiting. Non-blocking — enrollment failure
    # must never prevent account creation.
    try:
        from database import partner_enroll as _pe
        _pe(user["id"], tier="referral")
        print(f"[Register] Partner auto-enrolled for user {user['id']}")
    except Exception as _pe_err:
        print(f"[Register] Partner auto-enroll failed (non-blocking): {_pe_err}")

    # Record referral attribution if a partner code was provided — non-blocking
    if body.referral_code:
        try:
            from database import partner_get_by_code, referral_attribute
            ref_code = body.referral_code.upper().strip()
            referring = partner_get_by_code(ref_code)
            if referring:
                referral_attribute(
                    partner_id       = referring["id"],
                    referred_user_id = user["id"],
                    attribution_type = "code",
                    referral_code    = ref_code,
                )
        except Exception as _ae:
            # Attribution failure must never block registration
            print(f"[Register] Attribution failed (non-blocking): {_ae}")

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



@router.post("/register-partner")
def register_partner(body: dict):
    """
    Public partner registration endpoint — called by partner-signup.html.
    Creates a user account with role='referral', is_licensed=0, enrolls as
    a partner (Starter tier, auto-approved), and returns a JWT.

    This is for non-agent partners who want to refer agents but are not
    themselves agents. They will see only the Partner panel when they log in
    (renderViewSwitcher hides agent panels for is_licensed=0 users).

    Accepts: { name, email, password, referral_code? }
    Returns: { token, user, partner }
    """
    import re as _re

    name     = (body.get("name")     or "").strip()
    email    = (body.get("email")    or "").strip().lower()
    password = (body.get("password") or "").strip()
    ref_code = (body.get("referral_code") or "").strip().upper()

    # Validate required fields
    if not name:
        raise HTTPException(status_code=400, detail="Your name is required.")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if not _re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one uppercase letter.")
    if not _re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one lowercase letter.")
    if not _re.search(r"[0-9]", password):
        raise HTTPException(status_code=400, detail="Password must include at least one number.")

    # Create user account — role='referral', is_licensed=0
    # role='referral' is distinct from role='agent' so admin filters work correctly.
    # is_licensed=0 suppresses content engine access in renderViewSwitcher.
    user = create_user(
        email      = email,
        password   = password,
        agent_name = name,
        brokerage  = "",
        role       = "agent",   # base role; partner_tier drives partner UI visibility
        broker_id  = None,
    )
    if not user:
        raise HTTPException(
            status_code=409,
            detail="An account with that email already exists. Sign in instead."
        )

    # Set is_licensed=0 — partner-only users don't generate CIR-verified content
    try:
        conn = get_conn()
        conn.execute("UPDATE users SET is_licensed = 0 WHERE id = ?", (user["id"],))
        conn.commit()
        conn.close()
    except Exception as _e:
        print(f"[RegisterPartner] is_licensed update failed (non-blocking): {_e}")

    # Start 14-day trial (gives them access to the partner dashboard)
    try:
        from database import set_trial as _st
        _st(user["id"], days=14)
    except Exception:
        pass

    # Enroll as partner — Starter tier, auto-approved, code generated immediately
    try:
        from database import partner_enroll as _pe
        partner = _pe(user["id"], tier="referral")
    except Exception as _pe_err:
        print(f"[RegisterPartner] Partner enroll failed: {_pe_err}")
        raise HTTPException(status_code=500,
            detail="Account created but partner enrollment failed. Contact support@homebridgegroup.co.")

    # Record attribution if they arrived via someone else's referral code
    if ref_code:
        try:
            from database import partner_get_by_code as _pgbc, referral_attribute as _ra
            referring = _pgbc(ref_code)
            if referring:
                _ra(
                    partner_id       = referring["id"],
                    referred_user_id = user["id"],
                    attribution_type = "code",
                    referral_code    = ref_code,
                )
        except Exception as _ae:
            print(f"[RegisterPartner] Attribution failed (non-blocking): {_ae}")

    # Issue JWT
    token = create_token(user["id"], email, user["role"])

    return {
        "token":   token,
        "partner": partner,
        "user": {
            "id":           user["id"],
            "email":        email,
            "agent_name":   name,
            "role":         user["role"],
            "is_licensed":  0,
            "partner_tier": partner.get("tier") if partner else "referral",
            "partner_code": partner.get("referral_code") if partner else "",
        },
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
    # Determine if this is a new user (no setup data saved yet)
    from database import get_agent_setup
    existing_setup = get_agent_setup(user["id"])
    is_new = not bool(existing_setup)
    return {
        "token": token,
        "user": {
            "id":                user["id"],
            "email":             user["email"],
            "agent_name":        user["agent_name"],
            "brokerage":         user["brokerage"],
            "role":              user.get("role", "agent"),
            "broker_id":         user.get("broker_id", None),
            "phone":             user.get("phone", ""),
            "notification_email":user.get("notification_email", None),
            "is_new_user":       is_new,
        }
    }


@router.post("/forgot-password")
def forgot_password(body: dict):
    """Always returns 200 — never reveals whether email exists (security best practice)."""
    from database import create_reset_token
    email = (body.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "Email is required.")
    user = get_user_by_email(email)
    if user and user.get("is_active"):
        token     = create_reset_token(user["id"])
        reset_url = f"{FRONTEND_URL}/login.html?reset={token}"
        html_body = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;">
          <div style="font-size:18px;font-weight:700;color:#0f0f0d;margin-bottom:4px;">Home<span style="color:#1749c9;">Bridge</span></div>
          <hr style="border:none;border-top:1px solid #e8e7e0;margin:16px 0;" />
          <p style="color:#0f0f0d;font-size:15px;font-weight:600;margin-bottom:8px;">Reset your password</p>
          <p style="color:#787870;font-size:14px;line-height:1.6;margin-bottom:24px;">
            We received a request to reset the password for your HomeBridge account.
            Click the button below to choose a new password. This link expires in 1 hour.
          </p>
          <a href="{reset_url}"
             style="display:inline-block;background:#1749c9;color:#fff;font-weight:600;
                    font-size:14px;padding:12px 28px;border-radius:6px;text-decoration:none;">
            Reset My Password
          </a>
          <p style="color:#b0afa6;font-size:12px;margin-top:24px;line-height:1.5;">
            If you didn't request this, you can safely ignore this email.<br/>
            Your password won't change until you click the link above.
          </p>
          <hr style="border:none;border-top:1px solid #e8e7e0;margin:24px 0 16px;" />
          <p style="color:#b0afa6;font-size:11px;">HomeBridge &middot; Professional Identity Infrastructure</p>
        </div>
        """
        send_email(email, "Reset your HomeBridge password", html_body)
    return {"ok": True, "message": "If that email is registered, a reset link is on its way."}


@router.post("/reset-password")
def reset_password_endpoint(body: dict):
    """Validates reset token and updates password."""
    import re
    from database import validate_reset_token, consume_reset_token, update_password
    token        = (body.get("token") or "").strip()
    new_password = body.get("password") or ""
    if not token:
        raise HTTPException(400, "Reset token is required.")
    if len(new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", new_password):
        raise HTTPException(400, "Password must include at least one uppercase letter.")
    if not re.search(r"[a-z]", new_password):
        raise HTTPException(400, "Password must include at least one lowercase letter.")
    if not re.search(r"[0-9]", new_password):
        raise HTTPException(400, "Password must include at least one number.")
    row = validate_reset_token(token)
    if not row:
        raise HTTPException(400, "This reset link is invalid or has expired. Please request a new one.")
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    update_password(row["user_id"], hashed)
    consume_reset_token(token)
    return {"ok": True, "message": "Password updated. You can now sign in with your new password."}


@router.get("/validate-reset-token")
def validate_reset_token_endpoint(token: str):
    """Quick check — is reset token valid? Called when user lands on reset page."""
    from database import validate_reset_token
    row = validate_reset_token(token)
    if not row:
        raise HTTPException(400, "This reset link is invalid or has expired.")
    return {"ok": True, "email": row["email"], "name": row["agent_name"]}


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
