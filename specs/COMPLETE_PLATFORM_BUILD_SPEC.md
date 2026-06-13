# AUTOMATES -- COMPLETE PLATFORM BUILD SPECIFICATION
## Everything. Done Right. Done Once.
**Prepared by:** Claude Opus 4.6 -- June 11, 2026
**For:** Kevin Lundy / HomeBridge Group, LLC
**Build executor:** Sonnet (against this spec and referenced pinned specs, one file at a time, no improvisation)
**Status:** COMPREHENSIVE. This document covers every buildable open item from every pinned document. Nothing is deferred to "post-launch." The launch date is when this spec is complete AND Google/Twilio have given thumbs up.
**Estimated sessions:** 9 focused Sonnet sessions across 9-10 days (Kevin working weekends)

---

## 0. WHAT THIS DOCUMENT COVERS

Every open build item from:
- WORKSPACE_AUDIT_REPORT_SESSION69.md (all 10 questions answered, all findings addressed)
- VOICE_AUTHENTICITY_BUILD_SPEC.md (Phases 1-4)
- NOTIFICATION_DIGEST_SPEC.md (full build)
- GROWTH_ENGINE_BRIEF_FABLE5.md (Builds A-E + verify footer)
- SECURITY_AND_LEGAL_VULNERABILITY_REPORT_v3.md (all code-fixable items)
- PRODUCT_ROADMAP_v7.md (all remaining launch and launch-week items)
- OPUS_STRATEGIC_BRIEF_v2.md (all open Opus-level decisions resolved)

Items NOT in this document (genuinely cannot be built yet or require non-code action):
- Voice Authenticity Phase 5 (edit-pattern learning -- needs 3 months of edit data to be meaningful)
- Attorney review items (voice consent language, video consent language, ToS/Privacy content review)
- Google Business Profile creation (Kevin action, not code)
- Google Workspace secondary domain setup (Kevin action)
- OAuth reconnection (Kevin action, Facebook July 4, LinkedIn July 13)
- Twilio A2P approval (waiting)
- Google indexing (waiting)
- PostgreSQL migration (required at agent 40-50, not now)

Everything else ships before launch.

---

## PART A: INFORMATION ARCHITECTURE

---

## A1. NAVIGATION ARCHITECTURE

### Design principle

Every workspace follows the same rhythm. First tab is the cockpit (orientation, metrics, next action). Last tab is Settings. Middle tabs are purpose-specific. An agent switching workspaces recognizes the pattern instantly.

### Agent workspace

```
Home | Studio | Records | Schedule | Settings
```

- **Home** -- cockpit: Jordan briefing, activity summary, authority page URL (prominent), team introductions (properly sized), market signals, next action guidance
- **Studio** -- content generation (unchanged -- Kevin's favorite page, it works)
- **Records** -- the agent's provenance registry (redesigned, see Section A5)
- **Schedule** -- promoted from buried-in-Identity to top-level nav
- **Settings** -- merged Identity + Profile (see Section A3)

### HB Marketing workspace

```
Home | Studio | Records | Schedule | Settings
```

Identical nav. Eliminates current inconsistency.

- **Home** -- NEW page. Marketing briefing, activity summary (moved from current Activity tab), content performance by niche. Currently HB Marketing has no landing page.
- **Studio** -- unchanged
- **Records** -- same redesign as Agent, B2B compliance labels
- **Schedule** -- promoted
- **Settings** -- merged Identity + Profile

**Removed:** Edit tab (dead), Activity tab (folded into Home), separate Identity and Profile tabs.

### Platform Admin workspace

```
Dashboard | Agents | Compliance | Tools
```

- **Dashboard** -- real KPIs and system health (see Section A6)
- **Agents** -- user management. Create User becomes a button at the top of the list, not a separate nav item.
- **Compliance** -- 12-layer framework view (unchanged)
- **Tools** -- contains Demo Links, Audit Log, Checker Leads (renamed from "Leads"), Reset Demo button

**Removed:** Create User tab, Leads tab, Audit Log tab (all consolidated into Agents or Tools).

### My Organization workspace (consolidated from My Office + My Team)

```
Overview | Members | Compliance | Settings
```

- **Overview** -- org stats, invite form, empty state guidance
- **Members** -- agent list with status
- **Compliance** -- cross-org view, "oversight not editorial control" disclaimer
- **Settings** -- org name, contact info, notification preferences

**Navigation fix:** Remove conflicting in-page tab navigation. Sub-nav is the only navigation mechanism. Each sub-nav click renders the correct panel directly.

**My Team removed from workspace switcher.** My Office renamed to My Organization.

### Partner workspace

```
Overview | Referrals | Earnings | Payouts
```

Unchanged. Benchmark.

---

## A2. PROFILE DROPDOWN

**Agent / HB Marketing:**
```
[Name]
[email]
---
Upload Photo
Settings
Billing
Sign Out
```

Remove: Getting Started, Identity, My Profile. Keep Billing as direct shortcut.

**Platform Admin:**
```
[Name]
[email]
---
Upload Photo
Sign Out
```

No Settings or Billing -- admin operates the registry, not their personal profile.

**Partner / My Organization:**
```
[Name]
[email]
---
Upload Photo
Sign Out
```

---

## A3. IDENTITY + PROFILE --> SETTINGS

The words "Identity" and "Profile" are retired from navigation. Replaced by a single **Settings** page with collapsible sections. Each section is a card with a header. Click header to expand/collapse.

### Agent Settings sections (in display order)

**1. Voice and Style** (default expanded -- most frequently edited)
- Brand Voice text field (label: "How you describe your voice -- supplementary to your voice sample")
- Voice sample status (Phase 2 adds the recording interface here)
- LMNT voice clone status
- Tone preference
- Words to Avoid
- Words to Prefer
- Content length preference
- Modulation default (Phase 4 adds this -- Standard/Warmer/Sharper/Quieter)

**2. About You**
- Short Bio
- Zone of Greatness (why you do this, unfair advantage, proudest moment)
- Designations and Certifications
- Languages
- Recruiting pitch

**3. Your Specialties** (renamed from "Primary Niches")
- Niches picker (existing, functional)
- Market / geographic area

**4. Connections** (PROMOTED -- was buried at bottom of Profile)
- Platform connections: LinkedIn, Facebook, YouTube, X/Twitter, Google Business
- Each shows: status, expiry date, reconnect button
- Expiry warnings per existing system

**5. Account**
- Name, email, phone
- Upload photo
- Change password
- Chief of Staff name customization
- Notification preferences (SMS digest toggle)
- Daily check-in frequency (Phase 3 adds this -- Daily/Weekly/Never)

**6. Billing**
- Current plan display
- Usage this month (posts used/limit, videos used/limit)
- Manage subscription (Stripe portal)

**7. Disclaimers** (collapsed by default)
- Brokerage disclaimers
- State-specific requirements

### HB Marketing Settings sections

**1. Voice and Style** -- same structure, B2B context
**2. Who We Serve** -- replaces "Primary Niches"; B2B content categories
**3. Connections** -- same
**4. Account** -- same minus designations
**5. Chief of Staff** -- Jordan name customization

No Billing (Kevin's workspace). No Disclaimers (B2B). No About You (company, not personal).

---

## A4. SCHEDULE PROMOTION

Schedule gets its own nav item. The page shows:
- Active schedules listed by niche: next generation time, frequency, on/off toggle
- "Add Schedule" button
- Clear indication of which niches have active schedules
- Existing schedule management UI moves here from Identity

---

## A5. RECORDS PAGE REDESIGN -- THE PROVENANCE REGISTRY

### Header

```
YOUR PROVENANCE REGISTRY
[authority page URL -- prominent, clickable, copy button]
[CPR count: "106 records on file"]
```

Authority page URL is the first thing an agent sees. CPR count is a point of pride.

### Filter row

```
All (106) | Pending Review (5) | Approved (89) | Distributed (12) | Archived (0)
```

Counts update live. Each filter shows only that status.

### Record cards

Each record is a card (not a cramped list row):
- **Post headline or first 2-3 lines** -- NOT truncated
- **Date** -- generation/approval date
- **CPR ID** -- small, below date
- **Status badge:**
  - Gold outline (#A67C2E) = Pending Review (action needed)
  - Compliance green (#1A7A4A) = Approved (permanent)
  - Compliance green + platform icons = Distributed
  - Gray = Archived
- **Niche tag** -- small pill

### Expanded card (click to expand)

Full post content, compliance check summary, context-appropriate actions:
- Pending Review: Approve, Edit, Archive, Delete
- Approved: Distribute, Archive
- Distributed: view only (permanent)
- Archived: Restore, Delete

Actions are full-width, not cramped. Each has clear label and icon.

### Visual language

Approved/distributed records feel **permanent** -- locked in, credential-like. Subtle lock icon or "On Record" indicator. Pending records feel **active** -- gold draws the eye. Default view is dominated by approved records (the archive), not pending items (the inbox). When all pending items are handled, the page feels like a wall of accomplishments.

---

## A6. PLATFORM ADMIN DASHBOARD

### Row 1: Registry health (4 stat cards)

| Card | Source |
|------|--------|
| Active agents | users WHERE plan != 'trial' AND last login within 30 days |
| CPR records | COUNT compliance_records |
| Pages indexed | Manual input field (Kevin updates from GSC) |
| Monthly revenue | Manual input or Stripe |

### Row 2: Alerts (conditional, only shows when relevant)

- OAuth expiry: any connection expiring within 14 days (agent name, platform)
- System: last R2 backup timestamp, Twilio status, API health
- Limits: any agent at 80%+ monthly post or video limit

### Row 3: 7-day activity

- Generations, approvals, distributions (counts or simple bar)
- New signups this week
- Checker submissions this week

### Row 4: Agent quick view

Condensed list: name, plan, CPR count, last active, status. Click to jump to Agents tab.

### Backend

New endpoint: `GET /admin/dashboard-stats`. Queries existing tables. "Pages indexed" and "Revenue" stored in a simple key-value admin_settings table or manual-entry fields.

---

## A7. MY OFFICE + MY TEAM CONSOLIDATION

**Decision: consolidate into My Organization.**

1. Remove My Team from workspace switcher
2. Rename My Office to My Organization
3. Fix sub-nav (remove conflicting in-page tabs)
4. Nav: Overview | Members | Compliance | Settings
5. Role-based distinction (broker vs team lead) handled by conditional content if needed later, not separate workspaces

---

## A8. JORDAN PLACEMENT AND CONTEXTUAL HELP

### Placement rule

Jordan appears on Home pages only. Remove from:
- Settings pages (both workspaces)
- Platform Admin (all pages)
- Partner workspace (all pages)

### What Jordan shows per workspace

| Workspace | Jordan content |
|-----------|---------------|
| Agent Home | Morning briefing, team introductions (properly sized), momentum messages, next action |
| HB Marketing Home | Marketing briefing, content performance |
| Platform Admin | Not present |
| My Organization | Not present |
| Partner | Not present |

### Ask George -- contextual help panel

Do NOT hide. Fix.

The Ask George button opens a context-aware help panel. The panel knows what page the agent is on and shows relevant guidance:

| Page | Help content |
|------|-------------|
| Home | "This is your daily briefing. Your team works overnight to prepare content." Overview of what each team member does. |
| Studio | "Choose a content mode. Generate creates a draft. In My Business captures your expertise. Market Pulse uses local signals. Quick Post lets you write freely." Brief description of each mode. |
| Records | "This is your provenance registry. Every approved post becomes a permanent CPR record. Pending posts need your review -- tap to expand and approve." How filtering works. |
| Schedule | "Your autopilot. Each active schedule generates content automatically. Toggle schedules on/off. Add schedules for new specialties." |
| Settings > Voice | "Your voice profile shapes every piece of content. Words to Avoid and Words to Prefer are guardrails. Your voice sample (when captured) teaches the system your actual rhythm." |
| Settings > Connections | "Connect your social platforms here. Posts can be distributed directly to any connected platform. Watch expiry dates -- reconnect before they expire." |
| Settings > Billing | "Your current plan and usage. Manage your subscription through the Stripe portal." |

Implementation: a `HELP_CONTENT` constant in app.js mapping page identifiers to pre-written help text. George panel reads current page state and displays the matching content. No API call needed. Static content, context-aware display.

The team introduction panel (Analyst, Writer, Auditor, Scheduler, Publisher) moves from Ask George to the Home page itself, displayed with proper visual weight. Text large enough to read. Each team member card communicates value. This is the product's differentiator -- treat it like one.

---

## A9. HOME PAGE ENHANCEMENTS

### Agent Home additions

**Authority page URL** -- top of page, prominent, copy button. An agent should never wonder where their page is.

**Activity summary strip** -- 4 compact stat cards:
- Records on file (total CPR count)
- Posts this month
- Platforms reached
- Pending review (gold badge if > 0)

**Team introductions** -- properly sized, each card large enough to convey value. Not tucked inside a panel. Visible on the Home page itself.

### HB Marketing Home (NEW)

- Marketing briefing (Jordan-style)
- Activity summary (same 4-card layout, B2B data)
- Content by niche breakdown (from current Activity page -- must NOT show agent niches, fix context bleed)
- Quick actions: "Generate in Studio" and "Review pending records"

---

## A10. LABEL AND COPY FIXES

- "Primary Niches" --> "Your Specialties" (Agent) / "Who We Serve" (HB Marketing)
- "Your Voice" section split into "Written Voice" and "Audio Voice" (clear labels for two different things)
- HB Marketing Records compliance label "(NAR, state licensing)" --> "(Content compliance)"
- HB Marketing Profile duplicate "My Profile" header --> single header
- Change Password appears once (in Account section of Settings), not duplicated across workspaces

---

## PART B: DEMO MODE

---

## B1. PURPOSE

The sponsor shares a demo link with Wolfpack agents. They browse independently and understand the product before Kevin contacts them. Self-guided. Self-explanatory. Visually identical to production.

## B2. PERSONA

**Brooke Callahan**, licensed real estate agent, Austin TX. Specialties: First-Time Homebuyers, Relocation. Locked. Never Denver. Never Kevin's name.

## B3. ACCESS

Tokenized URL via existing demo_tokens infrastructure. Pattern: `app.homebridgegroup.co/demo?token=XXXXX`. Admin generates tokens from Platform Admin > Tools > Demo Links. Tokens expire after 7 days.

## B4. DEMO ENVIRONMENT

Real user record for Brooke Callahan with `is_demo = true` (new boolean column on users table).

**Seeded data:**

User: Brooke Callahan, eXp Realty, Austin TX, First-Time Homebuyers + Relocation, founding_member plan, is_demo=true. Bio: "I help first-time buyers and relocating families find their place in Austin. Every piece of content I publish goes on record." Brand voice: "Clear, warm, direct. I talk to people like a neighbor who happens to know real estate."

Content library (15 records):
- 5 pending review (First-Time Homebuyer and Relocation mix)
- 8 approved with CPR records
- 2 distributed (LinkedIn, Facebook)
- Realistic Austin-market content (Sonnet writes these as static strings during build)

Schedules: First-Time Homebuyers 3x/week, Relocation 2x/week

Connections: LinkedIn connected (simulated), Facebook connected (simulated), YouTube not connected

Jordan briefing: static pre-written content. "Good morning, Brooke. You have 5 posts ready for review and 13 records on file."

## B5. DEMO RESTRICTIONS

When is_demo is true:

1. **No real API calls.** Studio Generate returns pre-written content from a bank of 5 demo posts (rotated). UI animates normally.
2. **No real social posting.** Distribution shows success simulation with checkmark. Record status updates locally.
3. **No real Stripe.** Billing shows "Founding Member -- $129/month." Manage Subscription replaced with CTA: "Ready to start? [Create Your Account]" linking to registration.
4. **No real voice cloning.** Voice section shows simulated "captured" status.
5. **No workspace switching.** Demo shows Agent workspace only. Switcher hidden.
6. **No admin access.**
7. **Scheduler worker skips** is_demo users.

## B6. DEMO UI ELEMENTS

**Persistent bottom CTA bar** (fixed, does not scroll):
```
See what Brooke sees every day. Ready to build your own provenance registry?  [Create Your Account]
```

Links to real registration page (new login.html design).

**Demo badge** -- subtle top nav indicator: "Demo Mode". Non-intrusive but unambiguous.

## B7. DEMO AUTHORITY PAGE

Brooke's authority page rendered by the same SSR engine. Slug: `brooke-callahan-austin`. Seeded compliance_records produce a real, viewable authority page with CPR records, schema, FAQ, provenance explanation. This is the single most powerful element in the demo.

## B8. DEMO DATA SEEDING

New endpoint: `POST /admin/demo/seed`

Creates/resets Brooke Callahan, clears existing demo content, seeds 15 content library entries + compliance records + schedules. "Reset Demo" button in Admin > Tools.

## B9. GHOST PAGE CONNECTION (SAME BUILD, DYNAMIC DATA)

The demo architecture makes Ghost Pages (Growth Engine Build B) trivial:
- Admin enters prospect name + market + niche
- System creates temporary is_demo user with that info
- Seeds sample content for that niche/market
- Generates tokenized 7-day link with SAMPLE watermark and noindex header
- Prospect sees "their" platform and authority page
- Token expiry purges data

Built in the same session as the demo, using the same infrastructure. Not a separate build.

---

## PART C: VOICE AUTHENTICITY

---

The complete specification exists in VOICE_AUTHENTICITY_BUILD_SPEC.md (pinned). Sonnet executes directly from that document. Summary of what ships:

## C1. PHASE 1 -- FEW-SHOT EXEMPLARS (no agent work, no schema change)

Per VOICE_AUTHENTICITY_BUILD_SPEC.md Section 2.

- `_get_voice_exemplars()` helper in content_engine.py
- `voice_exemplar_block` injection in all 4 prompt builders
- Brand Voice field reframed as supplementary context
- Zone of Greatness reframed as biographical context
- user_id threaded through from app.py call sites
- `draft_content` column added to content_library (Phase 5 prerequisite -- stores original generation for future edit-pattern analysis)

## C2. PHASE 4 -- MODULATION BUTTONS (no agent work, no schema change)

Per VOICE_AUTHENTICITY_BUILD_SPEC.md Section 5.

- 4 buttons in Studio: Standard / Warmer / Sharper / Quieter
- `modulation` field on ContentRequest
- `modulation_block` injection in prompt builders
- Not sticky between generations (defaults to Standard each time)
- UI: selected button gets gold background per design system

## C3. PHASE 2 -- AUDIO VOICE CAPTURE

Per VOICE_AUTHENTICITY_BUILD_SPEC.md Section 3.

- 10-prompt bank (copied verbatim from spec Section 3.1)
- 4 new columns on agent_setup (voice_sample_transcript, voice_sample_prompt_text, voice_sample_captured_at, voice_sample_audio_url)
- Backend routes: upload, save, current, delete
- Identity panel (now Settings > Voice and Style) gets recording interface: prompt picker, record button, timer, playback, transcript editing, save
- Brand Voice text field gets demotion subhead
- Prompt injection: audio sample becomes primary voice source, recent posts secondary
- Audio discarded after transcription (sidesteps biometric storage)
- 2-minute max recording, transcript shown before save, delete always available

## C4. PHASE 3 -- DAILY AMBIENT SIGNAL

Per VOICE_AUTHENTICITY_BUILD_SPEC.md Section 4.

- 12-question rotating bank (copied verbatim from spec Section 4.2)
- New table: daily_mood_entries
- mood_check_frequency setting on user record (daily/weekly/never, default weekly)
- Backend routes: today, submit, dismiss, recent
- `_get_ambient_context()` helper in content_engine.py
- ambient_block injection in prompts (36-hour window)
- Jordan card on Home: "Quick check-in" with single-line input, Send, Skip Today
- Pauses for 14 days if dismissed 3 consecutive days
- Settings toggle: "How often should Jordan check in?"

---

## PART D: NOTIFICATION DIGEST

---

The complete specification exists in NOTIFICATION_DIGEST_SPEC.md (pinned). Sonnet executes directly from that document. Summary:

- notification_digest_worker (runs 07:00 MT daily)
- Collects overnight activity per agent: posts ready, approved, distributed, videos, CPR records
- Single SMS per agent per morning (skip if zero activity)
- send_sms_notification() in social.py
- sms_notifications_enabled column on users (default true)
- Toggle in Settings > Account
- SMS_NOTIFICATIONS_ENABLED env var gate (false until A2P approved)
- Disable per-event SendGrid triggers (comment out, do not delete)
- Deploy order: database.py --> social.py --> app.py --> app.js --> index.html

---

## PART E: GROWTH ENGINE BUILDS

---

Per GROWTH_ENGINE_BRIEF_FABLE5.md Section 8.

## E1. BUILD A -- GLASS BOX SCOREBOARD

SSR page on Render backend at a public URL (e.g., `homebridgegroup.co/scoreboard` or `api.homebridgegroup.co/scoreboard`).

Shows:
- CPR records count (live from DB)
- Pages indexed (manual field, Kevin updates daily from GSC)
- Days until EU AI Act Article 50 (countdown to August 2, 2026)
- Timestamped daily log entries (like a lab notebook)
- One-line explanation: "This is the AutoMates indexing experiment. Watch the line climb."

Implementation: new SSR route in app.py. Reads compliance_records count from DB. Reads indexed_count from admin_settings table. Renders simple HTML page with the data. No JavaScript required -- fully server-rendered for crawlers.

Daily log entries stored in a new `scoreboard_entries` table: date, cpr_count, indexed_count, note (optional). Kevin adds entries via admin endpoint or the scoreboard page itself.

## E2. RECURSIVE VERIFY FOOTER

Every post published through AutoMates appends one line:

```
Reviewed and on record: [verify URL]
```

Implementation: in content_engine.py or social.py (wherever the post text is finalized before distribution), append the footer with the post's CPR verify URL. The verify URL pattern already exists.

One-line change. Highest leverage per effort in this entire document.

## E3. BUILD D -- ON RECORD BADGE

Embeddable HTML snippet an agent places on their existing website. Links to their verify page.

```html
<a href="https://[slug].homebridgegroup.co/verify" target="_blank" rel="noopener">
  <img src="https://api.homebridgegroup.co/badge/on-record.svg" alt="On Record -- Certified Provenance Registry" width="180" />
</a>
```

Implementation:
- Create on-record.svg badge (split gold, "On Record" text, CPR shield icon) -- static asset on Render
- Badge endpoint in app.py serves the SVG
- Agent sees their badge embed code in Settings > Connections or on the Records page
- Copy button for the embed code

The badge is the agent's pride artifact, an inbound link to the platform, and the thing their colleagues ask about.

## E4. BUILD B -- GHOST PAGE GENERATOR

Uses demo infrastructure from Part B. Admin tool:

1. Admin enters: prospect name, market, niche(s)
2. System creates temporary is_demo user with SAMPLE watermark flag
3. Seeds 8-10 sample posts for that niche/market (generated at seed time or drawn from a template bank per niche)
4. Generates tokenized private URL (7-day expiry, noindex header)
5. Prospect sees: a pre-populated platform view AND a real SSR authority page with their name
6. Token expiry purges all data

Admin UI: form in Platform Admin > Tools with name, market, niche fields and "Generate Ghost Page" button. Returns the private URL.

Hard rules (from Growth Engine Brief risk register):
- SAMPLE watermark on every screen
- noindex on all pages
- Private tokenized URL only
- Built from prospect's public professional info only
- Never published
- Deleted on request or token expiry

## E5. BUILD E -- REGISTRY PAGE

Public, crawlable page listing every CPR-verified agent by market and niche.

URL: `homebridgegroup.co/registry` or `api.homebridgegroup.co/registry`

Shows:
- List of all agents with at least one approved CPR record
- Each entry: agent name, market, specialties, CPR record count, link to authority page
- Filter by market and niche
- Auto-generated market/niche sub-pages: "Probate and estate agents on record in Denver"

Implementation: SSR route in app.py. Queries users + compliance_records. Renders HTML with schema markup. Each agent entry links to their authority subdomain. Sub-pages generated from the unique market/niche combinations that exist in the data.

This is thin with 1-3 agents. With 30 it becomes a search asset no competitor can replicate.

## E6. BUILD C -- AI VISIBILITY SNAPSHOT TEMPLATE

HTML template for the snapshot Kevin sends prospects. Contains:
- Prospect name and market
- 3 AI query results (manual for now -- Kevin runs the queries and pastes results)
- Presence/absence verdict per query
- AutoMates explanation and CTA
- Kevin's branding

Implementation: HTML template in app.py that accepts form data (name, market, query results) and renders a shareable page or downloadable PDF. Admin tool in Platform Admin > Tools.

Automating the AI queries ($20-40/month in API calls) is a month-2 item. The template ships now with manual input.

---

## PART F: MARKETING SITE COMPLETE CLEANUP

---

All changes are on Bluehost (homebridgegroup.co files). These are copy and configuration changes.

## F1. CPR NAMING MIGRATION

Verify and complete the CIR --> CPR rename across ALL user-facing surfaces:

- Marketing site (homebridgegroup.co/index.html): all explanation blocks, process steps, meta tags
- Authority page template: explanation text, schema markup
- Verify page: verification explanation
- App UI (index.html app, app.js): all user-facing references
- Backend user-facing strings in content_engine.py, app.py
- Generation prompts in content_engine.py

First mention format: Certified Provenance Record (CPR). Database column names (cir_*) unchanged.

Sonnet must grep all files for "CIR", "Compliance Intelligence Record", "Certified Identity Record" and replace every user-facing instance.

## F2. "SIGNAL" REPLACEMENT

Replace in 5 locations on marketing site:
- Section header: "Signal" --> "Market Intelligence" or "Market Update"
- Process steps: "signal" --> "market development" or "news"
- Comparison column: "signal" --> "market data"
- CPR section: "signal" --> "market update"
- Any other instance

## F3. META DESCRIPTION

Current: uses "verified presence"
Fix: use "reviewed" per locked doctrine. "Verified" implies guarantee.

## F4. "CPR RECORD" REDUNDANCY

"CPR record" = "Certified Provenance Record record." Fix to just "CPR" or "provenance record."

## F5. HUBSPOT FORM EMBED

Replace mailto: contact form with HubSpot embedded form. Kevin creates the form in HubSpot. Sonnet embeds the form code in the marketing site index.html on Bluehost.

## F6. PRIVACY POLICY SMS DISCLOSURE

Add to privacy.html on Bluehost:
- Statement of non-sharing for mobile numbers
- Message frequency disclosure (up to 1 message per day)
- "Message and data rates may apply"

Per Twilio A2P requirements.

## F7. EM DASH ON IDENTITY/SETTINGS PAGE

Remove the em dash in "Your voice, your market, your niches -- the foundation..." Replace with a comma or period.

---

## PART G: CONTENT ENGINE FIXES

---

## G1. EM DASH PROHIBITION IN GENERATION PROMPTS

Add explicit instruction to all prompt builders in content_engine.py:

```
"NEVER use em dashes (--) in generated content. Use periods, commas, semicolons, or line breaks instead."
```

Add to: _build_content_prompt, _build_b2b_content_prompt, _build_freeform_content_prompt, _build_video_script_prompt.

## G2. DRAFT CONTENT PRESERVATION

Add `draft_content` JSON column to content_library table. Populated at generation time with the originally-generated content. The agent's edit is implicitly (draft_content vs content). Zero cost to add now; enables Voice Authenticity Phase 5 later.

## G3. AUTHORITY PAGE CPR EXPLANATION

Update the CPR explanation text on the authority page to use "Certified Provenance Record" with provenance-aligned language optimized for AI crawler comprehension. Reference C2PA, content provenance, human attestation.

---

## PART H: SECURITY HARDENING

---

## H1. /voice/audio OWNERSHIP VERIFICATION (N7)

Currently anyone with a valid job_id can access voice audio files. Add ownership check: verify requesting user owns the job before serving audio.

## H2. HEYGEN WEBHOOK SIGNATURE VERIFICATION (N8)

Verify HeyGen webhook payloads using signature header. Reject unsigned or invalid webhooks.

## H3. SIGNAL GENERATION USAGE LIMIT (N9)

/content/generate-from-signal currently bypasses plan usage limits. Add the same limit check used in other generation endpoints.

## H4. VIDEO CONSENT GATE ENFORCEMENT

The video_consent column exists. The gate is never checked. Add check: before any video render, verify video_consent is true. If not, show consent modal before proceeding. This is the code enforcement -- the legal language review is an attorney item.

## H5. ANTHROPIC API KEY ROTATION

Kevin action: generate new key in Anthropic console, update STRIPE_... wait, ANTHROPIC_API_KEY env var in Render, delete old key. Not a Sonnet task, but must be done before launch.

---

## PART I: REMAINING ITEMS

---

## I1. HB MARKETING SCHEDULE BUG FIX

Root cause (diagnosed Session 69): Part C niche lifecycle validation in the scheduler worker reads primaryNiches from agent_setup, but HB Marketing schedules use B2B niches stored in marketing setup. Fix: if context is hb_marketing, validate against marketing setup niches instead of agent_setup primaryNiches.

One-line conditional in app.py.

## I2. ADMIN AGENTS TAB ENHANCEMENTS

- Add phone number column
- Add last active date column
- Add inline edit for email, brokerage, phone
- Add password reset trigger button per user
- Add plan usage display (posts used/limit, videos used/limit)
- Add sort by signup date, last active, role
- Add onboarding status indicator

## I3. ADMIN AUDIT LOG ENHANCEMENTS

- Plain language action descriptions (not technical names)
- Filter by date range, action type, user
- Drill-down on individual entries
- Export to CSV

## I4. ADMIN CHECKER LEADS

- Rename tab from "Leads" to "Checker Leads" (now in Tools)
- Add legend for result codes (3F = 3 Failures, 5P = 5 Passes)
- Add HubSpot sync when HubSpot integration is configured

---

## PART J: PRICING STRUCTURE

---

## J1. SINGLE TIER: FOUNDING MEMBER ONLY

At launch, the platform has ONE pricing tier. Period.

- **Founding Member: $129/month OR $1,290/year (2 months free)**
- Locked for life. Window closes December 18, 2026.

No trial. No Professional. No Power. No Coaching. No free tier. None of it. Those tiers go on hold until the market's willingness to subscribe is understood. Launching with multiple tiers before having a single paying customer is guessing. Launch with one price, learn, then expand.

### Code changes
1. Kevin: deactivate ALL non-Founding-Member Price IDs in Stripe (trial, Professional, Power, Coaching)
2. Kevin: create annual Founding Member Price ID in Stripe ($1,290/year)
3. Update checkout flow in app.js: show ONLY Founding Member with monthly/annual toggle. No tier comparison. No "choose your plan." One price, two billing options.
4. Remove all tier comparison UI, feature gating by tier, and plan-selection screens
5. Remove all trial references from: onboarding, Settings > Billing, marketing site, login page, app UI
6. Update plan_limits logic in app.py: one plan, one set of limits (Founding Member limits)
7. Update any admin tools that reference other tiers
8. Stripe webhook handler: only needs to handle one plan

### Copy
"Founding Member -- $129/month or $1,290/year. Locked for life."
No "starting at." No "plans and pricing." No tier names. One price.

---

## PART K: NAME AND TEAM EMPHASIS

---

## K1. THE "MATES" ARE THE TEAM

"AutoMates" is not automation software. It is a team of specialists who work inside a professional registry. Without this framing, the name is a liability.

The five Mates:
- **Analyst** -- researches the agent's market, tracks signals, surfaces opportunities
- **Writer** -- drafts content in the agent's voice using their approved style
- **Auditor** -- runs every post through the 12-layer compliance framework
- **Scheduler** -- manages timing and cadence across platforms
- **Publisher** -- distributes approved content and manages platform connections

### Where the team must be visible

1. **Login/registration page:** below the positioning statement, the 5 team roles listed with one-line descriptions. The agent sees WHO they're hiring before they sign up.
2. **Agent Home:** team introductions with proper visual weight -- large cards, clear role names and descriptions, not cramped text. This is the product's differentiator.
3. **Demo:** Brooke's Home shows the full team. Visitors see the team immediately.
4. **Marketing site:** the process section must name the team members by role, not describe abstract "steps."
5. **Onboarding completion:** "Meet your team" screen before landing on Home.
6. **Studio:** subtle role indicators showing which team member is active at each stage (Analyst surfaced the signal, Writer is drafting, Auditor is checking).

### The two-pillar positioning

Every public surface reinforces both pillars:
1. **Your team of Mates** -- the people who do the work
2. **The provenance registry** -- the system that makes the work permanent and findable

Neither pillar alone is sufficient. "A team that creates content" is generic. "A registry of records" is abstract. Together: "A team of specialists who create, review, and permanently register your professional content" -- that is the product.

---

## BUILD SEQUENCE

---

### Session 70 (Day 1): Core IA Restructure

**Files:** app.js, index.html (app), app.py (HB Marketing bug fix)

Everything in Part A: nav restructure (all workspaces), Settings merge, Schedule promotion, dropdown cleanup, Jordan placement, Ask George contextual help, Home page enhancements, HB Marketing Home (new), Activity integration, label changes, authority page URL visibility, My Organization consolidation, HB Marketing schedule bug fix.

ALSO Part J: remove ALL non-Founding-Member tier UI (trial, Professional, Power, Coaching). Show Founding Member only with monthly/annual toggle. Remove tier comparison screens, plan selection, feature gating by tier. One plan, one set of limits.

ALSO Part K: team emphasis on Home (large team member cards), login page (team roles below positioning statement), Studio (role indicators). Onboarding "Meet your team" screen.

This is the biggest session. It is overwhelmingly frontend restructuring of existing elements.

### Session 71 (Day 2): Records Redesign + Admin Overhaul

**Files:** app.js, index.html, app.py, database.py

Records --> Provenance Registry redesign (Part A5). Platform Admin Dashboard (A6). Admin Agents tab enhancements (I2). Admin nav consolidation (Tools absorbs Demo Links, Audit Log, Checker Leads). Audit Log enhancements (I3). Checker Leads legend (I4). Dashboard stats endpoint and queries.

### Session 72 (Day 3): Demo Mode

**Files:** database.py, app.py, app.js, index.html

Everything in Part B: is_demo column, demo data seeding, 15 static posts, demo restrictions, simulated generation, distribution simulation, CTA bar, demo badge, scheduler skip, demo authority page (Brooke Callahan slug), Reset Demo button. Ghost Page generator (E4) built in same session using same infrastructure.

### Session 73 (Day 4): Voice Authenticity -- Backend

**Files:** content_engine.py, app.py, database.py

Voice Phase 1: _get_voice_exemplars helper, voice_exemplar_block injection in all 4 prompt builders, Brand Voice reframing, Zone of Greatness reframing, user_id threading. Voice Phase 4: modulation field, modulation_block injection. Draft content column (G2). Em dash prohibition in prompts (G1). Em dash removal from Settings page text (F7). Authority page CPR explanation update (G3). Recursive verify footer (E2).

### Session 74 (Day 5): Voice Authenticity -- Frontend + Audio

**Files:** app.js, index.html, database.py, app.py

Voice Phase 2: 4 schema columns, upload/save/current/delete routes, Settings > Voice recording interface (prompt picker, record, playback, transcript edit, save), Brand Voice demotion subhead, audio-first prompt injection. Voice Phase 4 UI: modulation buttons in Studio. Phase 3: daily_mood_entries table, mood routes, _get_ambient_context helper, ambient_block injection, Jordan check-in card on Home, frequency setting in Settings.

### Session 75 (Day 6): Notification Digest + Security

**Files:** database.py, social.py, app.py, app.js, index.html

Everything in Part D (per NOTIFICATION_DIGEST_SPEC.md): sms_notifications_enabled column, send_sms_notification(), digest worker, scheduler registration, disable SendGrid triggers, notification toggle in Settings. Security: N7 voice audio ownership (H1), N8 HeyGen webhook signature (H2), N9 signal generation limit (H3), video consent gate enforcement (H4).

### Session 76 (Day 7): Growth Engine

**Files:** app.py, database.py

Glass Box scoreboard (E1): SSR route, scoreboard_entries table, admin update interface. On Record badge (E3): SVG asset, badge endpoint, embed code display. Registry page (E5): SSR route, agent listing, market/niche sub-pages, schema. AI Visibility Snapshot template (E6): admin form, HTML template.

### Session 77 (Day 8): Marketing Site + CPR Migration

**Files:** Bluehost files (marketing index.html, privacy.html), app.py, content_engine.py, app.js

CPR naming migration (F1): grep and replace all CIR references across all files. "Signal" replacement (F2). Meta description fix (F3). CPR record redundancy (F4). HubSpot form embed (F5). Privacy policy SMS disclosure (F6).

### Session 78 (Day 9): Full Verification + Polish

Complete walkthrough of every workspace, every page, every feature:
- Demo link: full Brooke Callahan experience, end to end
- Agent workspace: every nav item, every Settings section, every Records function
- HB Marketing: Home exists, schedules save, no context bleed
- Admin: dashboard KPIs, Agents tab enhanced, Tools consolidated
- My Organization: nav works
- Generate content: voice exemplars active, modulation buttons work, em dashes prohibited
- Authority page: CPR naming correct, schema valid
- Scoreboard: renders, data correct
- Registry page: renders, agents listed
- Badge: SVG serves, embed code works
- Marketing site: all copy correct, HubSpot form works, privacy policy updated

Fix anything that fails. This session exists because something always fails.

---

## KEVIN ACTIONS (PARALLEL, NOT DEPENDENT ON SESSIONS)

- [ ] Google Business Profile: create/claim (free, high leverage)
- [ ] Google Workspace: add homebridgegroup.co as secondary domain, verify via Cloudflare TXT
- [ ] OAuth calendar reminders: Facebook reconnect by July 4, LinkedIn by July 13
- [ ] HubSpot: create account, build 3-email sequence (per Growth Engine Brief Section 4)
- [ ] Anthropic API key: generate new key, update Render env var, delete old key
- [ ] Twilio A2P: monitor campaign status daily
- [ ] Google Search Console: monitor index count daily, update scoreboard
- [ ] Bing Webmaster: monitor index count
- [ ] Wolfpack post: write when index count shows first uptick (per Growth Engine Brief Section 6)

---

## LAUNCH CRITERIA

Launch happens when ALL of the following are true:
1. All 9 sessions complete and verified
2. Google index count shows meaningful uptick (target 50+, minimum 20+)
3. Twilio A2P campaign approved
4. Kevin has completed a full personal walkthrough and is satisfied
5. Demo link tested with at least one external person (Tammy or sponsor)

**Estimated timeline:** 9 sessions across 9-10 days. If starting Thursday June 12 and Kevin works weekends: complete by Saturday June 21 or Monday June 23. Launch the next business day after all criteria are met.

---

## DOCUMENTS TO UPDATE AFTER THIS SESSION

1. OPUS_STRATEGIC_BRIEF -- IA decisions, launch criteria, full build scope
2. ARCHITECTURAL_DESIGN_DOCUMENT -- nav structures, Settings page, My Organization, demo mode, dashboard
3. PRODUCT_ROADMAP -- revised launch blockers, complete build sequence
4. Master Re-Entry Prompt -- this spec as the primary build document for Sessions 70-78

---

*AutoMates Complete Platform Build Specification -- June 11, 2026 -- Confidential -- HomeBridge Group, LLC*
*Prepared by Claude Opus 4.6. This covers everything from every pinned document. Nothing deferred. Sonnet executes from this and the referenced pinned specs. No improvisation.*
