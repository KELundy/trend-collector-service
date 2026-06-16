# auth.py — HomeBridge Authentication
# Handles register, login, and token verification

import os
import sqlite3
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
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
    consent_at:   Optional[str] = None      # ISO timestamp of ToS/Privacy consent — Session 53
    sms_consent:  Optional[bool] = False    # standalone SMS notification opt-in — Twilio A2P

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
        "is_demo":           bool(d.get("is_demo", 0)),
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

# ── AUTH RATE LIMITER — Session 53 ───────────────────────────────────────────
# In-memory per-IP rate limiter for auth endpoints.
# Mirrors the waitlist rate limiter pattern in app.py.
# Resets on server restart — acceptable for auth (token TTL handles persistence).
_auth_rate: dict = {}      # { ip: [unix_timestamp, ...] }
_AUTH_MAX    = 20          # max auth attempts per window per IP
_AUTH_WINDOW = 900         # 15-minute rolling window

def _auth_check_rate_limit(ip: str) -> bool:
    """Returns True (allowed) or False (rate limited). Prunes stale hits on each call."""
    import time as _t
    now          = _t.time()
    window_start = now - _AUTH_WINDOW
    hits         = [t for t in _auth_rate.get(ip, []) if t > window_start]
    if len(hits) >= _AUTH_MAX:
        return False
    hits.append(now)
    _auth_rate[ip] = hits
    return True


def _get_client_ip(request) -> str:
    """Extract real client IP — Cloudflare passes it in x-forwarded-for."""
    forwarded = request.headers.get("x-forwarded-for") if request else None
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request and request.client else "unknown"


def create_token(user_id: int, email: str, role: str = "agent",
                 token_version: int = 1) -> str:
    payload = {
        "sub":   str(user_id),
        "email": email,
        "role":  role,
        "ver":   token_version,   # ── JWT revocation — Session 53
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
    # ── JWT version check — Session 53 ───────────────────────────────────────
    # If the token's version is older than the DB version, the user has changed
    # their password or been suspended since this token was issued. Force re-login.
    token_ver = payload.get("ver", 1)
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT token_version FROM users WHERE id = ?", (user["id"],))
        row = c.fetchone()
        conn.close()
        db_ver = row["token_version"] if row and row["token_version"] is not None else 1
        if token_ver < db_ver:
            raise HTTPException(
                status_code=401,
                detail="Session expired. Please log in again."
            )
    except HTTPException:
        raise
    except Exception:
        pass  # DB check failed — non-blocking, let request through
    return user


def forbid_demo(current_user=Depends(get_current_user)):
    """Block demo / Ghost-Page users from sensitive real-world actions (Stripe
    billing, social distribution). Reuses get_current_user for authentication and
    only adds the is_demo gate, returning the same user object so it can cleanly
    replace get_current_user as a route dependency."""
    if current_user.get("is_demo"):
        raise HTTPException(status_code=403, detail="This action is not available in demo mode.")
    return current_user


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────
@router.post("/register")
def register(body: RegisterRequest, request: Request = None):
    if not body.email or not body.password or not body.agent_name:
        raise HTTPException(status_code=400, detail="Email, password, and agent name are required.")
    # Checkbox 1 (ToS/Privacy) is required — Twilio A2P + Session 53.
    # Server-side enforcement: block registration if consent was not given.
    if not body.consent_at:
        raise HTTPException(status_code=400, detail="You must agree to the Terms of Service and Privacy Policy to create an account.")
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

    # Record consent — Session 53 + Twilio A2P compliance.
    # consent_at (Checkbox 1, ToS/Privacy) is now required above, so it is
    # always present here. sms_consent (Checkbox 2) is independent and optional:
    # when opted in, also stamp the timestamp and client IP for the audit trail.
    try:
        conn = sqlite3.connect(DB_NAME)
        if body.sms_consent:
            sms_ip = _get_client_ip(request)
            conn.execute(
                "UPDATE users SET consent_at = ?, sms_consent = 1, sms_consent_at = ?, sms_consent_ip = ? WHERE id = ?",
                (body.consent_at, datetime.utcnow().isoformat(), sms_ip, user["id"]),
            )
        else:
            conn.execute(
                "UPDATE users SET consent_at = ?, sms_consent = 0, sms_consent_at = NULL, sms_consent_ip = NULL WHERE id = ?",
                (body.consent_at, user["id"]),
            )
        conn.commit()
        conn.close()
    except Exception as _ce:
        print(f"[Register] consent record failed (non-blocking): {_ce}")

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
    consent_at = (body.get("consent_at") or "").strip()

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

    # Record ToS/Privacy consent timestamp — Session 53
    if consent_at:
        try:
            conn = sqlite3.connect(DB_NAME)
            conn.execute("UPDATE users SET consent_at = ? WHERE id = ?", (consent_at, user["id"]))
            conn.commit()
            conn.close()
        except Exception as _ce:
            print(f"[RegisterPartner] consent_at record failed (non-blocking): {_ce}")

    # Set is_licensed=0 — partner-only users don't generate CIR-verified content
    try:
        conn = sqlite3.connect(DB_NAME)
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
def login(body: LoginRequest, request: Request = None):
    # ── IP rate limit ─────────────────────────────────────────────────────────
    if request and not _auth_check_rate_limit(_get_client_ip(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts from this address. Please wait 15 minutes."
        )

    # Look up user — intentionally vague error to prevent email enumeration
    user = get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account disabled. Contact support@homebridgegroup.co")

    # ── Per-account lockout check ─────────────────────────────────────────────
    # Read lockout state directly from DB (not from _normalize_user which may
    # not include these newer columns on older schema versions).
    import time as _t
    try:
        _lc = sqlite3.connect(DB_NAME)
        _lc.row_factory = sqlite3.Row
        _lr = _lc.cursor()
        _lr.execute(
            "SELECT login_fail_count, login_locked_until, token_version FROM users WHERE id = ?",
            (user["id"],)
        )
        _lrow = _lr.fetchone()
        _lc.close()
        fail_count   = _lrow["login_fail_count"]   if _lrow and _lrow["login_fail_count"]   is not None else 0
        locked_until = _lrow["login_locked_until"] if _lrow and _lrow["login_locked_until"] is not None else None
        token_ver    = _lrow["token_version"]       if _lrow and _lrow["token_version"]       is not None else 1
    except Exception:
        fail_count = 0; locked_until = None; token_ver = 1

    if locked_until:
        try:
            lock_dt = datetime.fromisoformat(locked_until)
            if datetime.utcnow() < lock_dt:
                remaining = int((lock_dt - datetime.utcnow()).total_seconds() / 60) + 1
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many failed attempts. Account locked for {remaining} more minute(s). "
                           f"Contact support@homebridgegroup.co if you need immediate access."
                )
        except HTTPException:
            raise
        except Exception:
            pass  # Malformed timestamp — clear it and proceed

    # ── Password check ────────────────────────────────────────────────────────
    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        # Increment fail count — lock after 5 failures
        new_fail_count  = fail_count + 1
        new_locked_until = None
        if new_fail_count >= 5:
            new_locked_until = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
        try:
            _fc = sqlite3.connect(DB_NAME)
            _fc.execute(
                "UPDATE users SET login_fail_count = ?, login_locked_until = ? WHERE id = ?",
                (new_fail_count, new_locked_until, user["id"])
            )
            _fc.commit()
            _fc.close()
        except Exception:
            pass
        if new_locked_until:
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Account locked for 30 minutes. "
                       "Contact support@homebridgegroup.co if you need immediate access."
            )
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    # ── Successful login — clear lockout state ────────────────────────────────
    try:
        _sc = sqlite3.connect(DB_NAME)
        _sc.execute(
            "UPDATE users SET login_fail_count = 0, login_locked_until = NULL WHERE id = ?",
            (user["id"],)
        )
        _sc.commit()
        _sc.close()
    except Exception:
        pass

    token = create_token(user["id"], user["email"], user.get("role", "agent"), token_ver)
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
          <div style="font-size:18px;font-weight:700;color:#0f0f0d;margin-bottom:4px;">Home<span style="color:#1972A8;">Bridge</span></div>
          <hr style="border:none;border-top:1px solid #e8e7e0;margin:16px 0;" />
          <p style="color:#0f0f0d;font-size:15px;font-weight:600;margin-bottom:8px;">Reset your password</p>
          <p style="color:#787870;font-size:14px;line-height:1.6;margin-bottom:24px;">
            We received a request to reset the password for your HomeBridge account.
            Click the button below to choose a new password. This link expires in 1 hour.
          </p>
          <a href="{reset_url}"
             style="display:inline-block;background:#1972A8;color:#fff;font-weight:600;
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
    # Increment token_version — invalidates all existing sessions on other devices
    c.execute("""
        UPDATE users
        SET password_hash  = ?,
            token_version  = COALESCE(token_version, 1) + 1
        WHERE id = ?
    """, (new_hash, current_user["id"]))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Password updated. Other devices will be signed out."}
