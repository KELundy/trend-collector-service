# AUTOMATES — ARCHITECTURE AND ROADMAP ADDENDUM (JUNE 2026)
## Delta of Record Since ADD v8 / Roadmap v7
**Prepared by:** Claude Opus 4.6 — June 12, 2026
**For:** Kevin Lundy / HomeBridge Group, LLC
**Status:** Active. Pin beside ADD v8 and Roadmap v7. This is the authoritative record of everything that changed after June 5, 2026. Full ADD v9 and Roadmap v8 consolidation happens post-launch, first quiet week.
**Supersedes nothing.** Amends ADD v8 (June 5) and Roadmap v7 (June 5).

---

## 1. SSR ARCHITECTURE (SESSION 66, JUNE 8-9)

ADD v8 Section 2 (Infrastructure Map) is stale. The following changes are live in production.

**What changed:**
- Authority pages and per-record CPR pages now render server-side on the Render backend (FastAPI, trend-collector-service-clean). Full HTML with all content present in page source at response time. Crawlers see complete content without JavaScript execution.
- Wildcard custom domain `*.homebridgegroup.co` added to Render with TLS certificate issued. Agent subdomains (e.g., kevin-lundy-denver.homebridgegroup.co) route directly to Render.
- Cloudflare Worker `homebridge-agent-pages` that previously intercepted subdomain requests has been removed. **Standing rule: never re-add the `*.homebridgegroup.co/*` Worker route.**
- Bluehost retains marketing site only (homebridgegroup.co root domain).

**What it fixed:**
- Root cause of AI/search invisibility: client-side rendered authority pages returned empty HTML shells to crawlers. `site:kevin-lundy-denver.homebridgegroup.co` returned 2 results despite 106+ records.
- Post-fix: subdomain sitemap submitted to Google Search Console (184 pages discovered, Status: Success) and Bing Webmaster Tools (Status: Processing).

**Infrastructure Map correction (replaces ADD v8 Section 2 routing):**
```
homebridgegroup.co          → Bluehost (marketing site)      [A record]
app.homebridgegroup.co      → Render frontend                [CNAME]
api.homebridgegroup.co      → Render backend                 [CNAME]
*.homebridgegroup.co        → Render backend (SSR authority)  [CNAME wildcard]
```

---

## 2. CLOUDFLARE MANAGED ROBOTS.TXT DISCOVERY (SESSION 67, JUNE 10)

**Critical finding:** Cloudflare's "Managed robots.txt" toggle (Security > Signals) had been ON since at least April 2026. This setting automatically injected Disallow rules for every major AI crawler (ClaudeBot, GPTBot, Google-Extended, Applebot-Extended, Amazonbot, meta-externalagent) into robots.txt across all subdomains.

**Impact:** Complete AI invisibility since platform inception. The SSR fix (Session 66) made content visible in page source, but robots.txt told every AI crawler not to read it.

**Resolution:** Toggle turned OFF. **Standing rule: NEVER re-enable the Cloudflare "Managed robots.txt" toggle.** If visibility issues recur, this toggle is the first diagnostic check. Note: the Managed robots.txt toggle is distinct from individual AI Crawl Control toggles — these are separate Cloudflare settings.

---

## 3. POSITIONING & FUNNEL ARCHITECTURE (SPINE v3, JUNE 12)

New strategic framework superseding POSITIONING_FIRST_VALUE_BRIEF v1 and v2. Full spec: POSITIONING_FUNNEL_SPINE_v3.md.

**Three-engine model:**
1. **Manufacture** — compress the credibility timeline for new agents via published body of work
2. **Amplify** — win the search checkpoint between introduction and callback for all agents
3. **Capture** — claim the extraction layer (AI Overviews, answer engines) where everyone starts at zero

**Funnel stages:** Stage 0 (wound: Google yourself) → Stage 1 (free value: compliance checker + AI visibility check) → Stage 2 (proof: demo + Ghost Page) → Stage 3 (decision: $129/mo Founding Member) → Stage 4 (first 30 minutes: Foundation questions + onboarding artifacts) → Stage 5 (Ignition: 2x cadence, 25-30 real records in 14 days) → Stage 6 (recognition ladder: read → found → indexed → extracted → listed)

**New builds (Spine v3):**

| Build | What | Gate |
|---|---|---|
| M | Ignition Mode: 14-day 2x cadence, batch review UX, default-on at onboarding | Launch |
| N | IndexNow API ping + sitemap auto-resubmit on publish | Launch |
| O | Extraction architecture: question-form headings, definitive-answer opens, auto FAQ block | Launch |
| P | Checker result page conversion rebuild (Record #1 framing + demo link) | Launch |
| Q | Self-serve AI visibility check (lite) | Month 2 |

---

## 4. FOUNDATION & DAILY QUESTION SYSTEM (DQ SPEC v2, JUNE 12)

New system. Full spec: FOUNDATION_DAILY_QUESTION_SPEC_v2.md.

**Mechanic:** Platform asks a question → member answers (typed or spoken) → engine shapes answer into content in their voice → member reviews/edits/approves/discards → approved content publishes with human-originated provenance flag.

**Two modes:**
- **Mode A (Foundation Sequence):** Three questions at onboarding (~5 minutes). Produces Record #1 live, seeds voice exemplar pool.
- **Mode B (Daily Question):** One optional question per day in morning briefing. Three sources: Foundation bank (days 1-7), signal-driven (post day 7), evergreen (fallback rotation).

**Data model additions:**
- `question_bank` table (id, text_template, category, source, niche_tags, active)
- `member_questions` table (id, user_id, question_id, rendered_text, signal_ref, delivered_at, status)
- `member_answers` table (id, member_question_id, user_id, input_type, transcript, audio_ref, created_at)
- `origin_type` column on `compliance_records` (values: member_answer_voice, member_answer_text, engine_draft, studio_authored)
- `answer_ref` column on `compliance_records` (FK to member_answers)
- `draft_content` column on `content_library` (Voice Phase 5 prerequisite)

**Build sessions:**

| Session | Gate | Dependency |
|---|---|---|
| DQ-1: Data model + question bank seed (70 questions) | Launch | None |
| DQ-2: Foundation flow UI (typed input only) | Launch | DQ-1 |
| DQ-3: Voice-memo pipeline (MediaRecorder, transcription) | Should-have | DQ-2 |
| DQ-4: Generation prompts + origin_type threading | Launch | DQ-1 + Voice Phase 1 |
| DQ-5: Daily Question engine (delivery, scheduler, repeat protection) | Post-launch (week 1-2) | DQ-4 |
| DQ-6: Signal-driven questions (trend-collector hook) | Post-launch (month 1) | DQ-5 |
| DQ-7: Digest integration | Post-launch (after Twilio A2P) | DQ-5 + digest |

---

## 5. GROWTH ENGINE ARCHITECTURE (FABLE 5, JUNE 10)

Full spec: GROWTH_ENGINE_BRIEF_FABLE5.md.

**Three loops:**
1. **Proof Loop (Glass Box):** Kevin's indexing journey documented publicly on a live scoreboard. Constraint becomes the campaign.
2. **Mirror Engine:** Per-prospect AI Visibility Snapshot + Ghost Page (tokenized, watermarked, 7-day expiry preview of their authority page).
3. **Registry Loop:** Public registry page + embeddable On Record badge. Tools get churned; registries get joined.

**Builds:**

| Build | What | Gate |
|---|---|---|
| A | Glass Box scoreboard (SSR route, live CPR count, manual index count, EU AI Act countdown) | Should-have |
| B | Ghost Page generator (admin tool, tokenized preview, SAMPLE watermark, noindex, 7-day expiry) | Launch (in Demo Mode session) |
| C | AI Visibility Snapshot template (HTML, three query results, presence/absence) | Post-launch |
| D | On Record badge (embeddable snippet, links to verify page) | Should-have |
| E | Registry page + programmatic market/niche pages | Should-have |
| F | Monthly visibility re-check worker + notification | Month 2 |

---

## 6. VOICE AUTHENTICITY RESEQUENCING

VOICE_AUTHENTICITY_BUILD_SPEC.md (June 9) originally placed all five phases post-launch. Resequenced:

- **Phase 1 (few-shot exemplars from approved posts):** Moved to launch-gated. Hard dependency for DQ-4. Ships in CC-1.
- **Phase 4 (modulation buttons):** Backend ships with Phase 1 in CC-1. UI ships in CC-7. Launch-gated.
- **Phases 2, 3, 5:** Remain post-launch (weeks 2-4 and month 3+).

Rationale: Foundation records are Phase 1's seed data. DQ-4 generates content from member answers using the voice exemplar pipeline. Without Phase 1, Foundation answers produce generic output — defeating the purpose of the entire system.

---

## 7. PIPELINE CHANGE (JUNE 12)

**Retired:** Sonnet chat sessions for code execution. Session numbering (70-78) from COMPLETE_PLATFORM_BUILD_SPEC replaced by CC-series (CC-1 through CC-8).

**New pipeline:**
- **Fable 5:** Strategy, positioning, specs
- **Opus:** Sequencing, session prompts, architectural decisions, document maintenance
- **Claude Code:** All code execution under CLAUDE.md rules (both repos cloned locally, plan-before-edit, syntax-validate, never push)
- **Kevin:** Approves plans, reviews output, pushes and deploys

Both repos contain CLAUDE.md with standing rules: work only inside `trend-collector/` (backend) and `public2/` (frontend), never delete files, never push or deploy, syntax-validate every Python edit, plan-and-list-affected-files before any multi-file change, stop on conflicts.

---

## 8. REVISED LAUNCH WINDOW

**Original target:** June 10, 2026 (missed — critical Cloudflare/SSR discoveries)
**Second target:** June 17, 2026 (missed — scope expansion from DQ + Spine v3 specs, pipeline change)
**Current window:** June 23-27, 2026 (condition-based)

**Conditions:**
- Clean run (no rework): June 23
- One stumble: June 25
- Two stumbles or session split: June 26-27

**Build days:** June 13-14 (weekend, Kevin working), June 16-20 (weekdays). June 21-22 OFF.

**External dependencies (neither blocks launch):**
- Google indexing: Glass Box strategy reframes "not yet indexed" as the launch narrative
- Twilio A2P: Notification digest is should-have, not launch-gated. Cohort 1 gets personal texts from Kevin.

---

## 9. SECURITY FINDINGS (CLAUDE CODE READ-ONLY AUDIT, JUNE 12)

Two new findings from Claude Code's initial repository audit. Slotted into H-series for post-launch hardening. Neither blocks launch for a controlled Founding Member cohort.

### H5. Broker Office Invite Codes — Deterministic Hash, No Stored Secret
**Location:** auth.py:106
**Finding:** Broker office invite codes are generated as a deterministic hash of the user ID. There is no stored secret, no expiry, and no usage limit. Anyone who knows or guesses the hash algorithm and a user ID can generate valid invite codes.
**Risk:** Low for launch (broker offices not actively marketed). Medium at scale.
**Remediation (post-launch):** Replace with cryptographically random invite codes stored in the database with expiry timestamps and single-use enforcement. Add rate limiting on invite code redemption.
**Priority:** Post-launch hardening, before broker office feature is marketed.

### H6. No MFA on Admin/Super_Admin Accounts
**Finding:** Admin and super_admin accounts authenticate with username/password only. No multi-factor authentication option exists.
**Risk:** Low for launch (Kevin is the only admin, uses strong credentials). High before adding additional admins or at commercial scale.
**Remediation (post-launch):** Add TOTP-based MFA (Google Authenticator / Authy compatible) for admin and super_admin roles. Enforce MFA on all admin accounts before any second admin is created.
**Priority:** Post-launch hardening, before second admin account is created.

### Flagged — Do Not Touch
**Location:** database.py:339
**Finding:** `assistant_agents` table appears defined but unused. No references found in app.py, content_engine.py, or any route handler.
**Action:** Flag only. Do not delete, do not modify. May be a planned feature or legacy artifact. Investigate post-launch during ADD v9 consolidation.

---

## 10. DOCUMENTS STATUS

| Document | Version | Last Updated | Status |
|---|---|---|---|
| Architectural Design Document | v8 | June 5, 2026 | Stale — does not reflect SSR, Cloudflare discovery, DQ system, Spine v3, or pipeline change. This addendum is the delta. |
| Product Roadmap | v7 | June 5, 2026 | Stale — same gaps. This addendum is the delta. |
| Opus Strategic Brief | v2 | June 5, 2026 | Partially stale — launch target, notification status, pipeline model outdated. |
| Security Report | v3 | June 5, 2026 | Amended by Section 9 of this addendum (H5, H6). |
| Complete Platform Build Spec | v1 | June 11, 2026 | Superseded in sequencing by CC-series session prompts (this addendum Section 7 + CLAUDE_CODE_SESSION_PROMPTS.md). Scope definitions remain valid. |
| Voice Authenticity Build Spec | v1 | June 9, 2026 | Phase 1 resequenced to launch-gated (Section 6 of this addendum). Spec content unchanged. |
| Foundation Daily Question Spec | v2 | June 12, 2026 | Current. Launch gates per Section 4 of this addendum. |
| Positioning Funnel Spine | v3 | June 12, 2026 | Current. |
| Growth Engine Brief | v1 | June 10, 2026 | Current. |
| Notification Digest Spec | v1 | June 10, 2026 | Current. Gated on Twilio A2P. |
| Multi-Vertical Expansion Brief | v1 | June 10, 2026 | Current. Post-launch, post-10-agents. |
| Workspace Audit Report | Session 69 | June 11, 2026 | Current. Findings addressed in CC-5 (IA restructure). |

**Post-launch consolidation plan:** First quiet week after launch, Opus consolidates this addendum + all current specs into ADD v9 and Roadmap v8. This addendum then retires.

---

*AutoMates Architecture and Roadmap Addendum — June 12, 2026 — Confidential — HomeBridge Group, LLC*
*Prepared by Claude Opus 4.6. Pin beside ADD v8 and Roadmap v7. This is the delta of record.*
