# AUTOMATES -- NOTIFICATION DIGEST ARCHITECTURE SPECIFICATION
## Opus Spec for Sonnet Build
**Prepared by:** Claude Opus 4.6 -- June 10, 2026
**For:** Kevin Lundy / HomeBridge Group, LLC
**Build executor:** Sonnet (against this spec, one file at a time, no improvisation)
**Status:** Build after Twilio A2P campaign is approved. Code can be written now; SMS sending will fail with Error 30034 until campaign clears.
**Prerequisite:** Twilio A2P campaign "AutoMates Agent Notifications" must show Approved status.

---

## 0. WHY THIS EXISTS

The previous notification system fired an individual SendGrid email every time content was generated or an event occurred. Kevin described it as "spamming myself" at 2-3 notifications per day for similar content. SendGrid's free trial expired May 11, 2026. No notifications of any kind have been delivered for 30 days.

The replacement: one SMS per agent per morning summarizing overnight activity. Consolidated. Useful. Aligned with the Jordan morning briefing concept already in the product.

---

## 1. ARCHITECTURE

### 1.1 New background worker: notification_digest_worker

Runs once daily. Piggybacks on the existing APScheduler pattern used by content_scheduler_worker, r2_backup_worker, and signal_collector_worker in app.py.

**Schedule:** Runs at 07:00 Mountain Time (13:00 UTC) every day. This is configurable via env var DIGEST_HOUR_UTC (default 13).

**What it does on each run:**
1. Query all active users (plan != 'trial' OR role in UNLIMITED_ROLES) who have a verified phone number
2. For each user, collect overnight activity (last 24 hours)
3. Format a single SMS message per user
4. Send via Twilio
5. Log success/failure per user

### 1.2 Data collection per agent

For each user, the worker queries the following from the last 24 hours:

- **Posts ready for review:** COUNT of content_library rows where user_id matches, status = 'generated' (or whatever the pre-approval status is -- verify against database.py), created_at within last 24 hours, context = 'agent'
- **Posts approved:** COUNT of content_library rows where user_id matches, status = 'approved', updated_at within last 24 hours, context = 'agent'
- **Posts distributed:** COUNT of content_library rows where user_id matches, status = 'distributed' (or equivalent -- verify), updated_at within last 24 hours, context = 'agent'
- **Videos rendered:** COUNT of video_jobs rows where user_id matches, status = 'completed', updated_at within last 24 hours
- **Videos pending:** COUNT of video_jobs rows where user_id matches, status IN ('pending', 'processing', 'queued'), created_at within last 24 hours
- **CPR records created:** COUNT of compliance_records rows where user_id matches, created_at within last 24 hours, context = 'agent'

If ALL counts are zero for a user, do NOT send an SMS. No activity = no message. Do not send "nothing happened" messages.

### 1.3 Message format

Single SMS segment (160 characters max). If content exceeds 160 chars, it will be split into 2 segments by Twilio (acceptable, costs $0.0158 instead of $0.0079).

**Format:**

```
AutoMates morning summary:
{X} posts ready for review
{Y} approved, {Z} distributed
{V} videos complete
{C} new CPR records
Log in: app.homebridgegroup.co
```

Only include lines where the count is > 0. Examples:

If 3 posts ready, 1 video complete:
```
AutoMates morning summary:
3 posts ready for review
1 video complete
Log in: app.homebridgegroup.co
```

If 2 posts approved, 2 distributed, 5 CPR records:
```
AutoMates morning summary:
2 approved, 2 distributed
5 new CPR records
Log in: app.homebridgegroup.co
```

If only CPR records:
```
AutoMates morning summary:
3 new CPR records
Log in: app.homebridgegroup.co
```

### 1.4 SMS sending function

Add to social.py:

```python
def send_sms_notification(to_phone, message_body):
    """
    Sends an SMS via Twilio.
    Returns True on success, False on failure.
    Logs errors but does not raise.
    """
```

Uses existing Twilio credentials from env vars (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER). These should already exist from the approval notification code. Verify against social.py.

Error handling: catch all Twilio exceptions, log the error, return False. Never let one failed SMS stop the worker from processing remaining users.

### 1.5 User phone number source

The phone number comes from the users table or user_contact_methods table. Verify which table stores the agent's SMS-capable phone number. The registration consent checkbox (Session 65) captures consent to receive notifications via text message.

Only send to users who:
- Have a verified phone number on file
- Have an active plan (not expired, not trial unless they are super_admin/admin)
- Have not opted out of notifications (see 1.6)

### 1.6 Notification preferences

Add a single column to the users table:

```sql
ALTER TABLE users ADD COLUMN sms_notifications_enabled BOOLEAN DEFAULT TRUE;
```

Default TRUE for all existing and new users (consent is captured at registration via the checkbox added in Session 65). Users can turn this off in their Identity/Profile settings.

Add a simple toggle in the Identity panel (app.js / index.html): "Receive daily SMS summary" with an on/off toggle. Calls a new endpoint:

```
PUT /user/notification-preferences
Body: { "sms_notifications_enabled": true/false }
```

### 1.7 Worker registration in app.py

Add to the scheduler setup section (find where content_scheduler_worker and r2_backup_worker are registered):

```python
scheduler.add_job(
    notification_digest_worker,
    'cron',
    hour=int(os.getenv('DIGEST_HOUR_UTC', '13')),
    minute=0,
    id='notification_digest',
    replace_existing=True
)
```

### 1.8 Gating

The worker must be gated on Twilio A2P campaign approval. Add an env var:

```
SMS_NOTIFICATIONS_ENABLED=false
```

Set to false in Render until Twilio A2P campaign is approved. The worker checks this var on each run and exits immediately if false. When Kevin confirms A2P approval, set to true in Render env vars.

---

## 2. REMOVE PER-EVENT NOTIFICATION TRIGGERS

The current codebase has per-event notification calls (SendGrid emails) scattered through app.py. These fire on content generation, approval, video completion, etc.

**Do NOT delete these call sites.** Instead:

1. Find every place that calls a SendGrid/email notification function
2. Wrap each call in a check: `if False:` or comment out with `# DISABLED: replaced by daily digest`
3. This preserves the code for reference without executing it
4. Leave the SendGrid import and function definitions in place but unused

This is safer than deleting and ensures nothing breaks if a function is called from an unexpected path.

---

## 3. FILES TOUCHED

| File | Changes |
|------|---------|
| database.py | sms_notifications_enabled column migration, digest data collection query functions |
| social.py | send_sms_notification() function |
| app.py | notification_digest_worker function, scheduler registration, notification preferences endpoint, disable per-event email triggers |
| app.js | Notification toggle in Identity panel, API call for preferences |
| index.html (app) | Toggle UI element in Identity section |

Deploy order: database.py -> social.py -> app.py -> app.js -> index.html

---

## 4. COST

Twilio SMS: ~$0.0079 per segment.

- 1 agent, 1 message/day = ~$0.24/month
- 10 agents = ~$2.37/month
- 50 agents = ~$11.85/month
- 100 agents = ~$23.70/month

Well within budget at any scale.

---

## 5. WHAT THIS DOES NOT INCLUDE

- Per-event real-time notifications (explicitly removed)
- Email notifications (SendGrid is dead, stays dead)
- Push notifications (not built, future item)
- HB Marketing digest (super_admin only, Kevin can add later)
- Customizable digest timing per agent (all agents get 07:00 MT, future item)
- Weekly digest option (future item -- daily only for now)

---

## 6. VERIFICATION

After build and deploy:
1. Set SMS_NOTIFICATIONS_ENABLED=true in Render env vars (only after Twilio A2P approved)
2. Kevin generates content or approves a post
3. Next morning at 07:00 MT, Kevin receives a single SMS with the summary
4. Kevin verifies the counts match actual platform activity
5. Kevin tests the opt-out toggle -- turns off, verifies no SMS next morning, turns back on

---

*AutoMates Notification Digest Architecture Specification -- June 10, 2026*
*Prepared by Claude Opus 4.6 for Sonnet build execution.*
*Do not build SMS sending until Twilio A2P campaign is confirmed Approved.*
