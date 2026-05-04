"""
HomeBridge — Social Platform OAuth + Posting
Handles: LinkedIn, Google Business, Facebook/Instagram, YouTube

Flow per platform:
  1. GET  /social/{platform}/connect      → returns {"auth_url": "..."} for frontend to redirect
  2. GET  /social/{platform}/callback     → receives code, exchanges for token, stores, redirects to frontend
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
YOUTUBE_CLIENT_ID      = os.getenv("YOUTUBE_CLIENT_ID", os.getenv("GOOGLE_CLIENT_ID", ""))
YOUTUBE_CLIENT_SECRET  = os.getenv("YOUTUBE_CLIENT_SECRET", os.getenv("GOOGLE_CLIENT_SECRET", ""))
FRONTEND_URL           = os.getenv("FRONTEND_URL", "https://app.homebridgegroup.co")
BACKEND_URL            = os.getenv("BACKEND_URL", "https://api.homebridgegroup.co")

# ─────────────────────────────────────────────
# PLATFORM CONFIG
# ─────────────────────────────────────────────
PLATFORMS = {
    "linkedin": {
        "auth_url":      "https://www.linkedin.com/oauth/v2/authorization",
        "token_url":     "https://www.linkedin.com/oauth/v2/accessToken",
        "scopes":        "openid profile email w_member_social",
        "client_id":     LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
        "redirect_uri":  f"{BACKEND_URL}/social/linkedin/callback",
        "enabled":       bool(LINKEDIN_CLIENT_ID),
    },
    "google": {
        "auth_url":      "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url":     "https://oauth2.googleapis.com/token",
        "scopes":        "openid email profile https://www.googleapis.com/auth/business.manage",
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri":  f"{BACKEND_URL}/social/google/callback",
        "enabled":       bool(GOOGLE_CLIENT_ID),
    },
    "facebook": {
        "auth_url":      "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url":     "https://graph.facebook.com/v19.0/oauth/access_token",
        "scopes":        "pages_manage_posts,pages_read_engagement,instagram_content_publish,instagram_basic",
        "client_id":     META_APP_ID,
        "client_secret": META_APP_SECRET,
        "redirect_uri":  f"{BACKEND_URL}/social/facebook/callback",
        "enabled":       bool(META_APP_ID),
    },
    "youtube": {
        "auth_url":      "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url":     "https://oauth2.googleapis.com/token",
        "scopes":        "https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtube.upload",
        "client_id":     YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "redirect_uri":  f"{BACKEND_URL}/social/youtube/callback",
        "enabled":       bool(YOUTUBE_CLIENT_ID),
    },
}

# ─────────────────────────────────────────────
# OAUTH STATE — temporary in-memory store
# ─────────────────────────────────────────────
_oauth_states: dict = {}

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
    if platform in ("google", "youtube"):
        params["access_type"] = "offline"
        params["prompt"]      = "consent"

    auth_url = cfg["auth_url"] + "?" + urlencode(params)
    return {"auth_url": auth_url}


# ─────────────────────────────────────────────
# ROUTE 2: OAuth Callback
# ─────────────────────────────────────────────
@router.get("/{platform}/callback")
async def oauth_callback(platform: str, request: Request):
    params = dict(request.query_params)
    code   = params.get("code")
    state  = params.get("state")
    error  = params.get("error")

    if error:
        return RedirectResponse(f"{FRONTEND_URL}?oauth_error={error}")
    if not code or not state:
        return RedirectResponse(f"{FRONTEND_URL}?oauth_error=missing_params")

    try:
        session = _consume_state(state)
    except HTTPException:
        return RedirectResponse(f"{FRONTEND_URL}?oauth_error=invalid_state")

    user_id = session["user_id"]
    cfg     = PLATFORMS[platform]

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
        except Exception:
            return RedirectResponse(f"{FRONTEND_URL}?oauth_error=token_exchange_failed")

    access_token  = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token", "")
    expires_in    = token_data.get("expires_in", 3600)
    expires_at    = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

    if not access_token:
        return RedirectResponse(f"{FRONTEND_URL}?oauth_error=no_access_token")

    platform_user_id = ""
    platform_handle  = ""

    async with httpx.AsyncClient() as client:
        try:
            if platform == "linkedin":
                me               = await client.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"})
                me_data          = me.json()
                platform_user_id = me_data.get("sub", "")
                platform_handle  = me_data.get("name", "")

            elif platform == "google":
                me               = await client.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {access_token}"})
                me_data          = me.json()
                platform_user_id = me_data.get("sub", "")
                platform_handle  = me_data.get("email", "")

            elif platform == "facebook":
                me               = await client.get("https://graph.facebook.com/me", params={"fields": "id,name", "access_token": access_token})
                me_data          = me.json()
                platform_user_id = me_data.get("id", "")
                platform_handle  = me_data.get("name", "")

            elif platform == "youtube":
                me               = await client.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"}, headers={"Authorization": f"Bearer {access_token}"})
                me_data          = me.json()
                items            = me_data.get("items", [])
                if items:
                    platform_user_id = items[0].get("id", "")
                    platform_handle  = items[0].get("snippet", {}).get("title", "")

        except Exception:
            pass

    database.save_platform_connection(
        user_id=user_id,
        platform=platform,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        platform_user_id=platform_user_id,
        platform_handle=platform_handle,
    )

    return RedirectResponse(f"{FRONTEND_URL}?connected={platform}&handle={platform_handle}")


# ─────────────────────────────────────────────
# ROUTE 3: Get all connections
# ─────────────────────────────────────────────
@router.get("/connections")
async def get_connections(current_user=Depends(get_current_user)):
    connections = database.get_platform_connections(current_user["id"])
    safe = []
    for c in connections:
        safe.append({
            "platform":     c["platform"],
            "handle":       c.get("platform_handle", ""),
            "connected_at": c.get("connected_at", ""),
            "expires_at":   c.get("expires_at", ""),
            "is_expired":   _is_expired(c.get("expires_at", "")),
        })
    return {"connections": safe}


# ─────────────────────────────────────────────
# ROUTE 4: Disconnect
# ─────────────────────────────────────────────
@router.post("/{platform}/disconnect")
async def disconnect_platform(platform: str, current_user=Depends(get_current_user)):
    database.delete_platform_connection(current_user["id"], platform)
    return {"ok": True, "platform": platform}


# ─────────────────────────────────────────────
# ROUTE 5: Post content
# ─────────────────────────────────────────────
class PostRequest(BaseModel):
    library_item_id: Optional[int] = None
    platform: str
    content: Optional[str] = None
    content_override: Optional[str] = None
    image_url: Optional[str] = None        # Generated image to attach
    org_urn: Optional[str] = None          # LinkedIn org URN for company page posting

@router.post("/post")
async def post_to_platform(body: PostRequest, current_user=Depends(get_current_user)):
    platform = body.platform.lower()

    conn_data = database.get_platform_connection(current_user["id"], platform)
    if not conn_data:
        raise HTTPException(400, f"No {platform} account connected. Connect it in Profile first.")
    if _is_expired(conn_data.get("expires_at", "")):
        raise HTTPException(401, f"Your {platform} connection has expired. Please reconnect in Profile.")

    access_token = conn_data["access_token"]
    post_text    = body.content or body.content_override

    item = None
    if not post_text and body.library_item_id:
        item = database.library_get_item(body.library_item_id, current_user["id"])
        if not item:
            raise HTTPException(404, "Content item not found.")
        if item["status"] not in ("approved", "published"):
            raise HTTPException(400, "Content must be approved before posting.")
        post_text = _format_post_text(item.get("content", {}), platform)

    if not post_text:
        raise HTTPException(400, "No content provided to post.")

    # Use image_url from request body; fall back to what's saved on the library item
    if body.image_url:
        image_url = body.image_url
    elif body.library_item_id:
        if item is None:
            item = database.library_get_item(body.library_item_id, current_user["id"])
        image_url = (item or {}).get("image_url") or None
    else:
        image_url = None

    try:
        if platform == "linkedin":
            result = await _post_linkedin(access_token, conn_data.get("platform_user_id", ""), post_text, image_url, body.org_urn)
        elif platform == "google":
            result = await _post_google(access_token, post_text)
        elif platform == "facebook":
            result = await _post_facebook(access_token, conn_data.get("platform_user_id", ""), post_text, image_url)
        elif platform == "youtube":
            result = await _post_youtube(access_token, conn_data.get("platform_user_id", ""), post_text, image_url)
        else:
            raise HTTPException(400, f"Direct posting to {platform} is not yet supported.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to post to {platform}: {str(e)}")

    # Mark as published for all outcomes — including script_ready
    # (the script was "sent" — it's done from HomeBridge's perspective)
    if body.library_item_id:
        database.library_update(body.library_item_id, current_user["id"], {
            "status":       "published",
            "published_at": datetime.utcnow().isoformat(),
        })
        database.log_platform_post(
            user_id=current_user["id"],
            library_item_id=body.library_item_id,
            platform=platform,
            post_id=result.get("id", ""),
            post_url=result.get("url", ""),
        )

    return {
        "ok":       True,
        "platform": platform,
        "post_id":  result.get("id", ""),
        "post_url": result.get("url", ""),
        "message":  result.get("message", ""),
        "action":   result.get("action", "posted"),
    }


# ─────────────────────────────────────────────
# PLATFORM POSTING — LinkedIn
# ─────────────────────────────────────────────
async def _post_linkedin(access_token: str, person_urn: str, text: str, image_url: str = None, org_urn: str = None) -> dict:
    # Determine author — use org URN for company page posting, person URN for personal
    if org_urn:
        author = org_urn if org_urn.startswith("urn:") else f"urn:li:organization:{org_urn}"
    else:
        if not person_urn:
            raise HTTPException(400, "LinkedIn user ID not found. Please reconnect your LinkedIn account.")
        author = person_urn if person_urn.startswith("urn:") else f"urn:li:person:{person_urn}"

    media_asset = None
    if image_url:
        try:
            import base64 as _base64
            # Handle base64 data URI — decode to raw bytes
            if image_url.startswith("data:"):
                _header, b64data = image_url.split(",", 1)
                image_bytes = _base64.b64decode(b64data)
            else:
                image_bytes = None

            async with httpx.AsyncClient(timeout=30) as client:
                reg = await client.post(
                    "https://api.linkedin.com/v2/assets?action=registerUpload",
                    json={"registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                        "owner": author,
                        "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}]
                    }},
                    headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"}
                )
                if reg.status_code in (200, 201):
                    reg_data    = reg.json()
                    upload_url  = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                    media_asset = reg_data["value"]["asset"]
                    put_resp    = None
                    if image_bytes is not None:
                        put_resp = await client.put(upload_url, content=image_bytes, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "image/png"})
                    else:
                        img_resp = await client.get(image_url)
                        if img_resp.status_code == 200:
                            put_resp = await client.put(upload_url, content=img_resp.content, headers={"Authorization": f"Bearer {access_token}"})
                        else:
                            print(f"[LinkedIn] Image fetch failed {img_resp.status_code} — posting text-only.")
                            media_asset = None
                    if put_resp and put_resp.status_code not in (200, 201):
                        print(f"[LinkedIn] Image PUT failed {put_resp.status_code}: {put_resp.text[:200]}")
                        media_asset = None
        except Exception as e:
            print(f"[LinkedIn] Image upload exception: {e}")
            media_asset = None

    if media_asset:
        payload = {
            "author": author, "lifecycleState": "PUBLISHED",
            "specificContent": {"com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text}, "shareMediaCategory": "IMAGE",
                "media": [{"status": "READY", "description": {"text": text[:200]}, "media": media_asset, "title": {"text": text.split("\n")[0][:100]}}]
            }},
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
    else:
        payload = {
            "author": author, "lifecycleState": "PUBLISHED",
            "specificContent": {"com.linkedin.ugc.ShareContent": {"shareCommentary": {"text": text}, "shareMediaCategory": "NONE"}},
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.linkedin.com/v2/ugcPosts", json=payload,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"}
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"LinkedIn API error {resp.status_code}: {resp.text}")

    post_id = resp.headers.get("x-restli-id", "")
    return {"id": post_id, "url": f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else "", "action": "posted"}


# ─────────────────────────────────────────────
# PLATFORM POSTING — Google Business Profile
# ─────────────────────────────────────────────
async def _post_google(access_token: str, text: str) -> dict:
    async with httpx.AsyncClient() as client:
        accts = await client.get("https://mybusinessaccountmanagement.googleapis.com/v1/accounts", headers={"Authorization": f"Bearer {access_token}"})
        acct_data = accts.json()

    accounts = acct_data.get("accounts", [])
    if not accounts:
        raise HTTPException(400, "No Google Business Profile account found.")

    account_name = accounts[0]["name"]

    async with httpx.AsyncClient() as client:
        locs     = await client.get(f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations", params={"readMask": "name,title"}, headers={"Authorization": f"Bearer {access_token}"})
        loc_data = locs.json()

    locations = loc_data.get("locations", [])
    if not locations:
        raise HTTPException(400, "No verified business location found on this Google Business Profile.")

    location_name = locations[0]["name"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://mybusiness.googleapis.com/v4/{location_name}/localPosts",
            json={"languageCode": "en-US", "summary": text[:1500], "topicType": "STANDARD"},
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"Google Business API error {resp.status_code}: {resp.text}")

    result = resp.json()
    return {"id": result.get("name", ""), "url": result.get("searchUrl", ""), "action": "posted"}


# ─────────────────────────────────────────────
# PLATFORM POSTING — Facebook Page
# ─────────────────────────────────────────────
async def _post_facebook(access_token: str, user_id: str, text: str, image_url: str = None) -> dict:
    async with httpx.AsyncClient() as client:
        pages     = await client.get(f"https://graph.facebook.com/v19.0/{user_id}/accounts", params={"access_token": access_token})
        page_data = pages.json()

    page_list = page_data.get("data", [])
    if not page_list:
        raise HTTPException(400, "No Facebook Pages found. You need a Facebook Page to post.")

    page       = page_list[0]
    page_id    = page["id"]
    page_token = page["access_token"]

    post_data   = {"message": text, "access_token": page_token}
    fb_endpoint = f"https://graph.facebook.com/v19.0/{page_id}/feed"

    async with httpx.AsyncClient() as client:
        if image_url:
            import base64 as _base64
            # Handle base64 data URI — send raw bytes to Facebook /photos endpoint
            if image_url.startswith("data:"):
                _header, b64data = image_url.split(",", 1)
                image_bytes = _base64.b64decode(b64data)
                fb_endpoint = f"https://graph.facebook.com/v19.0/{page_id}/photos"
                resp = await client.post(
                    fb_endpoint,
                    data={"caption": text, "access_token": page_token},
                    files={"source": ("image.png", image_bytes, "image/png")},
                )
            else:
                fb_endpoint = f"https://graph.facebook.com/v19.0/{page_id}/photos"
                post_data["url"]     = image_url
                post_data["caption"] = text
                resp = await client.post(fb_endpoint, data=post_data)
        else:
            resp = await client.post(fb_endpoint, data=post_data)

    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"Facebook API error {resp.status_code}: {resp.text}")

    result  = resp.json()
    post_id = result.get("id", "")
    return {"id": post_id, "url": f"https://www.facebook.com/{post_id.replace('_', '/')}" if post_id else "", "action": "posted"}


# ─────────────────────────────────────────────
# PLATFORM POSTING — YouTube
#
# YouTube is a VIDEO platform. The API does not support text-only posts.
# Two paths:
#   1. Community Posts — works if channel has Brand Account + 500 subscribers
#   2. Script Ready — returns guidance to film and upload manually via YouTube Studio
#
# The script HomeBridge generates IS the content. The agent films it.
# HomeBridge marks the item as published either way — the script was prepared.
# ─────────────────────────────────────────────
async def _post_youtube(access_token: str, channel_id: str, text: str, image_url: str = None) -> dict:

    # Attempt Community Post (works for qualifying channels)
    community_payload = {
        "snippet": {
            "type": "textPost",
            "textOriginalContent": text[:2000],
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://www.googleapis.com/youtube/v3/communityPosts",
                params={"part": "snippet"},
                json=community_payload,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            )

        if resp.status_code in (200, 201):
            result  = resp.json()
            post_id = result.get("id", "")
            channel = channel_id or ""
            return {
                "id":      post_id,
                "url":     f"https://www.youtube.com/channel/{channel}/community" if channel else "https://www.youtube.com",
                "action":  "posted",
                "message": "Posted to your YouTube Community tab.",
            }

    except Exception:
        pass

    # Community posts not available — return script_ready
    # Frontend detects action="script_ready" and shows Film This workflow
    return {
        "id":      "",
        "url":     "https://studio.youtube.com",
        "action":  "script_ready",
        "message": (
            "Your YouTube script is ready to film. YouTube requires video content — "
            "open YouTube Studio, create a Short, and use your script. "
            "Your script is saved in My Content."
        ),
    }


# ─────────────────────────────────────────────
# APPROVAL NOTIFICATIONS — Item #1
# SendGrid email + Twilio SMS for content approval flow
# ─────────────────────────────────────────────

async def send_approval_email(to_email: str, agent_name: str, headline: str, approve_url: str):
    """Send approval request email via SendGrid. Raises on failure."""
    sendgrid_key  = os.getenv("SENDGRID_API_KEY", "")
    sendgrid_from = os.getenv("SENDGRID_FROM_EMAIL", "noreply@homebridgegroup.co")
    if not sendgrid_key:
        raise RuntimeError("SENDGRID_API_KEY not configured.")

    subject   = "Content ready for your approval — HomeBridge"
    body_text = (
        "Hi " + agent_name + ",\n\n"
        "Your HomeBridge content is ready for review:\n\n"
        "\"" + headline + "\"\n\n"
        "Tap the link below to approve or review in the app:\n"
        + approve_url + "\n\n"
        "This link expires in 7 days and can only be used once.\n\n"
        "— HomeBridge\nhttps://app.homebridgegroup.co"
    )
    body_html = (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;'
        'max-width:520px;margin:0 auto;padding:32px 24px;background:#f5f4f0;">'
        '<div style="background:#fff;border-radius:12px;padding:32px;'
        'box-shadow:0 2px 12px rgba(0,0,0,.06);">'
        '<p style="font-size:12px;font-weight:700;letter-spacing:.1em;'
        'text-transform:uppercase;color:#787870;margin-bottom:20px;">HomeBridge</p>'
        '<h2 style="font-size:20px;color:#0f0f0d;margin-bottom:12px;">'
        'Content ready for your approval</h2>'
        '<p style="font-size:14px;color:#3d3d38;line-height:1.7;">Hi ' + agent_name + ',<br><br>'
        'Your HomeBridge content is ready for review:</p>'
        '<blockquote style="margin:16px 0;padding:14px 18px;background:#f5f4f0;'
        'border-left:3px solid #1749c9;border-radius:4px;font-size:14px;'
        'color:#0f0f0d;font-weight:600;">' + headline + '</blockquote>'
        '<a href="' + approve_url + '" style="display:inline-block;background:#1749c9;'
        'color:#fff;font-size:14px;font-weight:700;padding:12px 28px;border-radius:999px;'
        'text-decoration:none;margin:8px 0 20px;">Review &amp; Approve</a>'
        '<p style="font-size:12px;color:#b0afa6;line-height:1.6;">'
        'This link expires in 7 days and can only be used once.<br>'
        'If you did not request this, you can ignore this email.</p>'
        '</div></div>'
    )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {sendgrid_key}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": sendgrid_from, "name": "HomeBridge"},
                "subject": subject,
                "content": [
                    {"type": "text/plain", "value": body_text},
                    {"type": "text/html",  "value": body_html},
                ],
            },
        )
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"SendGrid error {resp.status_code}: {resp.text}")


async def send_approval_sms(to_phone: str, agent_name: str, headline: str, approve_url: str):
    """Send approval request SMS via Twilio. Raises on failure."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_FROM_NUMBER", "")
    if not (account_sid and auth_token and from_number):
        raise RuntimeError(
            "Twilio env vars not configured "
            "(TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER)."
        )

    phone = to_phone.strip()
    if not phone.startswith("+"):
        phone = "+1" + "".join(c for c in phone if c.isdigit())

    short_headline = headline[:60] + ("..." if len(headline) > 60 else "")
    message = (
        "HomeBridge: \"" + short_headline + "\" "
        "is ready for your approval. Tap to review: " + approve_url
    )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
            auth=(account_sid, auth_token),
            data={"From": from_number, "To": phone, "Body": message},
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Twilio error {resp.status_code}: {resp.text}")


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
    """Build platform-appropriate post text from content fields."""
    post     = content.get("post", "")
    cta      = content.get("cta", "")
    hashtags = content.get("hashtags", "")
    headline = content.get("headline", "")
    script   = content.get("script", "")

    if platform == "linkedin":
        parts = [p for p in [headline, post, cta, hashtags] if p]
    elif platform in ("facebook", "google"):
        parts = [p for p in [post, cta] if p]
    elif platform == "instagram":
        parts = [p for p in [post, cta, hashtags] if p]
    elif platform == "youtube":
        # Use script if available (generated for YouTube), else post body
        base  = script or post
        parts = [p for p in [headline, base, cta] if p]
    else:
        parts = [p for p in [post, cta] if p]

    return "\n\n".join(parts)
