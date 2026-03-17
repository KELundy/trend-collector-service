"""
HomeBridge — Social Platform OAuth + Posting
Handles: LinkedIn, Google Business, Facebook/Instagram (when approved)

Flow per platform:
  1. GET  /social/{platform}/connect      → redirects user to platform OAuth
  2. GET  /social/{platform}/callback     → receives code, exchanges for token, stores
  3. GET  /social/connections             → returns all connected platforms for this user
  4. POST /social/{platform}/disconnect   → revokes and removes token
  5. POST /social/post                    → posts approved content to connected platform(s)
"""

import os
import json
import httpx
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List

from auth import get_current_user
import database

router = APIRouter(prefix="/social", tags=["social"])

# ─────────────────────────────────────────────
# ENV VARS — names only, never hardcoded values
# ─────────────────────────────────────────────
LINKEDIN_CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID       = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET   = os.getenv("GOOGLE_CLIENT_SECRET", "")
META_APP_ID            = os.getenv("META_APP_ID", "")
META_APP_SECRET        = os.getenv("META_APP_SECRET", "")
FRONTEND_URL           = os.getenv("FRONTEND_URL", "https://app.homebridgegroup.co")
BACKEND_URL            = os.getenv("BACKEND_URL", "https://api.homebridgegroup.co")

# ─────────────────────────────────────────────
# PLATFORM CONFIG
# ─────────────────────────────────────────────
PLATFORMS = {
    "linkedin": {
        "auth_url":    "https://www.linkedin.com/oauth/v2/authorization",
        "token_url":   "https://www.linkedin.com/oauth/v2/accessToken",
        "scopes":      "openid profile w_member_social",
        "client_id":   LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
        "redirect_uri": f"{BACKEND_URL}/social/linkedin/callback",
        "enabled":     bool(LINKEDIN_CLIENT_ID),
    },
    "google": {
        "auth_url":    "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url":   "https://oauth2.googleapis.com/token",
        "scopes":      "openid email profile https://www.googleapis.com/auth/business.manage",
        "client_id":   GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": f"{BACKEND_URL}/social/google/callback",
        "enabled":     bool(GOOGLE_CLIENT_ID),
    },
    "facebook": {
        "auth_url":    "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url":   "https://graph.facebook.com/v19.0/oauth/access_token",
        "scopes":      "pages_manage_posts,pages_read_engagement,instagram_content_publish,instagram_basic",
        "client_id":   META_APP_ID,
        "client_secret": META_APP_SECRET,
        "redirect_uri": f"{BACKEND_URL}/social/facebook/callback",
        "enabled":     bool(META_APP_ID),
    },
}

# ─────────────────────────────────────────────
# OAUTH STATE — temporary store (in-memory, good enough for low volume)
# For scale: move to Redis or DB
# ─────────────────────────────────────────────
_oauth_states: dict = {}  # state_token → {user_id, platform, expires}

def _store_state(user_id: int, platform: str) -> str:
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = {
        "user_id":  user_id,
        "platform": platform,
        "expires":  datetime.utcnow() + timedelta(minutes=10),
    }
    return state

def _consume_state(state: str) -> dict:
    entry = _oauth_states.pop(state, None)
    if not entry:
        raise HTTPException(400, "Invalid or expired OAuth state. Please try connecting again.")
    if datetime.utcnow() > entry["expires"]:
        raise HTTPException(400, "OAuth session expired. Please try connecting again.")
    return entry

# ─────────────────────────────────────────────
# ROUTE 1: Initiate OAuth
# ─────────────────────────────────────────────
@router.get("/{platform}/connect")
async def connect_platform(platform: str, current_user=Depends(get_current_user)):
    cfg = PLATFORMS.get(platform)
    if not cfg:
        raise HTTPException(404, f"Platform '{platform}' not supported.")
    if not cfg["enabled"]:
        raise HTTPException(503, f"{platform.title()} integration is not yet configured. Check back soon.")

    state = _store_state(current_user["id"], platform)

    params = {
        "response_type": "code",
        "client_id":     cfg["client_id"],
        "redirect_uri":  cfg["redirect_uri"],
        "scope":         cfg["scopes"],
        "state":         state,
    }
    # LinkedIn requires explicit access_type
    if platform == "google":
        params["access_type"] = "offline"
        params["prompt"]      = "consent"

    url = cfg["auth_url"] + "?" + urlencode(params)
    return RedirectResponse(url)


# ─────────────────────────────────────────────
# ROUTE 2: OAuth Callback — exchange code for token, store
# ─────────────────────────────────────────────
@router.get("/{platform}/callback")
async def oauth_callback(platform: str, request: Request):
    params = dict(request.query_params)
    code   = params.get("code")
    state  = params.get("state")
    error  = params.get("error")

    if error:
        return RedirectResponse(f"{FRONTEND_URL}?social_error={platform}&reason={error}")

    if not code or not state:
        return RedirectResponse(f"{FRONTEND_URL}?social_error={platform}&reason=missing_params")

    try:
        session = _consume_state(state)
    except HTTPException:
        return RedirectResponse(f"{FRONTEND_URL}?social_error={platform}&reason=invalid_state")

    user_id  = session["user_id"]
    cfg      = PLATFORMS[platform]

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(cfg["token_url"], data={
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  cfg["redirect_uri"],
                "client_id":     cfg["client_id"],
                "client_secret": cfg["client_secret"],
            }, headers={"Accept": "application/json"})
            token_data = resp.json()
        except Exception as e:
            return RedirectResponse(f"{FRONTEND_URL}?social_error={platform}&reason=token_exchange_failed")

    access_token  = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token", "")
    expires_in    = token_data.get("expires_in", 3600)
    expires_at    = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

    if not access_token:
        return RedirectResponse(f"{FRONTEND_URL}?social_error={platform}&reason=no_access_token")

    # Fetch platform profile info (handle/name)
    platform_user_id = ""
    platform_handle  = ""

    async with httpx.AsyncClient() as client:
        try:
            if platform == "linkedin":
                me = await client.get("https://api.linkedin.com/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"})
                me_data = me.json()
                platform_user_id = me_data.get("sub", "")
                platform_handle  = me_data.get("name", "")

            elif platform == "google":
                me = await client.get("https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"})
                me_data = me.json()
                platform_user_id = me_data.get("sub", "")
                platform_handle  = me_data.get("email", "")

            elif platform == "facebook":
                me = await client.get("https://graph.facebook.com/me",
                    params={"fields": "id,name", "access_token": access_token})
                me_data = me.json()
                platform_user_id = me_data.get("id", "")
                platform_handle  = me_data.get("name", "")
        except Exception:
            pass  # Profile fetch failure is non-fatal

    # Store in DB
    database.save_platform_connection(
        user_id=user_id,
        platform=platform,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        platform_user_id=platform_user_id,
        platform_handle=platform_handle,
    )

    return RedirectResponse(f"{FRONTEND_URL}?social_connected={platform}&handle={platform_handle}")


# ─────────────────────────────────────────────
# ROUTE 3: Get all connections for current user
# ─────────────────────────────────────────────
@router.get("/connections")
async def get_connections(current_user=Depends(get_current_user)):
    connections = database.get_platform_connections(current_user["id"])
    # Never return tokens to frontend — return status only
    safe = []
    for c in connections:
        safe.append({
            "platform":       c["platform"],
            "handle":         c["platform_handle"],
            "connected_at":   c["connected_at"],
            "expires_at":     c["expires_at"],
            "is_expired":     _is_expired(c["expires_at"]),
        })
    return {"connections": safe}


# ─────────────────────────────────────────────
# ROUTE 4: Disconnect a platform
# ─────────────────────────────────────────────
@router.post("/{platform}/disconnect")
async def disconnect_platform(platform: str, current_user=Depends(get_current_user)):
    database.delete_platform_connection(current_user["id"], platform)
    return {"ok": True, "platform": platform}


# ─────────────────────────────────────────────
# ROUTE 5: Post content to a platform
# ─────────────────────────────────────────────
class PostRequest(BaseModel):
    library_item_id: int
    platform: str
    content_override: Optional[str] = None  # If user edited the copy in modal

@router.post("/post")
async def post_to_platform(body: PostRequest, current_user=Depends(get_current_user)):
    platform = body.platform.lower()

    # Get the connection
    conn_data = database.get_platform_connection(current_user["id"], platform)
    if not conn_data:
        raise HTTPException(400, f"No {platform} account connected. Connect it in Profile first.")
    if _is_expired(conn_data["expires_at"]):
        raise HTTPException(401, f"Your {platform} connection has expired. Please reconnect.")

    # Get the library item
    item = database.library_get_item(body.library_item_id, current_user["id"])
    if not item:
        raise HTTPException(404, "Content item not found.")
    if item["status"] not in ("approved", "published"):
        raise HTTPException(400, "Content must be approved before posting.")

    content = item.get("content", {})
    post_text = body.content_override or _format_post_text(content, platform)
    access_token = conn_data["access_token"]

    # Platform-specific posting
    try:
        if platform == "linkedin":
            result = await _post_linkedin(access_token, conn_data["platform_user_id"], post_text)
        elif platform == "google":
            result = await _post_google(access_token, post_text)
        elif platform == "facebook":
            result = await _post_facebook(access_token, conn_data["platform_user_id"], post_text)
        else:
            raise HTTPException(400, f"Posting to {platform} is not yet supported.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to post to {platform}: {str(e)}")

    # Mark as published in library
    database.library_update(body.library_item_id, current_user["id"], {
        "status":       "published",
        "published_at": datetime.utcnow().isoformat(),
    })

    # Log the post
    database.log_platform_post(
        user_id=current_user["id"],
        library_item_id=body.library_item_id,
        platform=platform,
        post_id=result.get("id", ""),
        post_url=result.get("url", ""),
    )

    return {
        "ok":      True,
        "platform": platform,
        "post_id":  result.get("id", ""),
        "post_url": result.get("url", ""),
    }


# ─────────────────────────────────────────────
# PLATFORM POSTING — LinkedIn
# ─────────────────────────────────────────────
async def _post_linkedin(access_token: str, person_urn: str, text: str) -> dict:
    if not person_urn.startswith("urn:"):
        person_urn = f"urn:li:person:{person_urn}"

    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            json=payload,
            headers={
                "Authorization":  f"Bearer {access_token}",
                "Content-Type":   "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            }
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"LinkedIn API error: {resp.text}")

    post_id = resp.headers.get("x-restli-id", "")
    return {
        "id":  post_id,
        "url": f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else "",
    }


# ─────────────────────────────────────────────
# PLATFORM POSTING — Google Business Profile
# ─────────────────────────────────────────────
async def _post_google(access_token: str, text: str) -> dict:
    # First get the account's locations
    async with httpx.AsyncClient() as client:
        accts = await client.get(
            "https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        acct_data = accts.json()

    accounts = acct_data.get("accounts", [])
    if not accounts:
        raise HTTPException(400, "No Google Business Profile account found. Make sure your account has a verified business location.")

    account_name = accounts[0]["name"]

    # Get locations
    async with httpx.AsyncClient() as client:
        locs = await client.get(
            f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations",
            params={"readMask": "name,title"},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        loc_data = locs.json()

    locations = loc_data.get("locations", [])
    if not locations:
        raise HTTPException(400, "No verified business location found on this Google Business Profile.")

    location_name = locations[0]["name"]

    # Post
    payload = {
        "languageCode": "en-US",
        "summary":      text[:1500],  # GBP limit
        "topicType":    "STANDARD",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://mybusiness.googleapis.com/v4/{location_name}/localPosts",
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type":  "application/json",
            }
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"Google Business API error: {resp.text}")

    result = resp.json()
    return {
        "id":  result.get("name", ""),
        "url": result.get("searchUrl", ""),
    }


# ─────────────────────────────────────────────
# PLATFORM POSTING — Facebook Page
# ─────────────────────────────────────────────
async def _post_facebook(access_token: str, user_id: str, text: str) -> dict:
    # Get managed pages
    async with httpx.AsyncClient() as client:
        pages = await client.get(
            f"https://graph.facebook.com/v19.0/{user_id}/accounts",
            params={"access_token": access_token}
        )
        page_data = pages.json()

    page_list = page_data.get("data", [])
    if not page_list:
        raise HTTPException(400, "No Facebook Pages found. You need a Facebook Page (not a personal profile) to post.")

    page       = page_list[0]
    page_id    = page["id"]
    page_token = page["access_token"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://graph.facebook.com/v19.0/{page_id}/feed",
            data={"message": text, "access_token": page_token}
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"Facebook API error: {resp.text}")

    result = resp.json()
    post_id = result.get("id", "")
    return {
        "id":  post_id,
        "url": f"https://www.facebook.com/{post_id.replace('_','/')}" if post_id else "",
    }


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _is_expired(expires_at: str) -> bool:
    if not expires_at:
        return False
    try:
        return datetime.utcnow() > datetime.fromisoformat(expires_at)
    except Exception:
        return False

def _format_post_text(content: dict, platform: str) -> str:
    """Build the post text from content fields, platform-appropriate."""
    post      = content.get("post", "")
    cta       = content.get("cta", "")
    hashtags  = content.get("hashtags", "")
    headline  = content.get("headline", "")

    if platform == "linkedin":
        parts = [p for p in [headline, post, cta, hashtags] if p]
        return "\n\n".join(parts)
    elif platform in ("facebook", "google"):
        parts = [p for p in [post, cta] if p]
        return "\n\n".join(parts)
    elif platform == "instagram":
        parts = [p for p in [post, cta, hashtags] if p]
        return "\n\n".join(parts)
    else:
        parts = [p for p in [post, cta] if p]
        return "\n\n".join(parts)
