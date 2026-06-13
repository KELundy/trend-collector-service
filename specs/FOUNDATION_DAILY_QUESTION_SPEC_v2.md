# FOUNDATION & DAILY QUESTION SYSTEM -- BUILD SPEC v2
## One Mechanic, Three Jobs: Onboarding, Retention, Permanent Content Mode
**Prepared by:** Claude Fable 5 -- June 12, 2026
**For:** Kevin Lundy / HomeBridge Group, LLC
**Supersedes:** FOUNDATION_SEQUENCE_BUILD_SPEC v1 (unpin).
**Companions:** VOICE_AUTHENTICITY_BUILD_SPEC.md (this system is Phase 1's cold-start solution and permanent exemplar feed), POSITIONING_FUNNEL_SPINE_v3.md (this precedes and then runs alongside Ignition Mode), COMPLETE_PLATFORM_BUILD_SPEC.md (Opus to integrate session sequencing there).
**Written at build grade:** Opus should be able to sequence Sonnet sessions directly from Sections 9-11 without re-derivation. Kevin approves before any code.

---

## 1. SYSTEM OVERVIEW

One mechanic: **the platform asks a question; the member answers in their own words (spoken or typed); the engine shapes the answer into content in their voice; they review, edit, approve or discard; approved content publishes and mints a record flagged as human-originated.**

That mechanic runs in two modes:

- **Mode A -- Foundation Sequence (signup, ~5 minutes):** three questions, answered at onboarding. Produces Record #1 live, seeds the voice exemplar pool, and gives the page an honest opening body of work.
- **Mode B -- Daily Question (permanent):** one optional question per day, delivered inside the morning briefing. Sixty seconds of talking becomes that day's content. Three question sources: the remaining Foundation bank (days 1-7), evergreen banks, and signal-driven questions generated from the trend collector.

Three jobs it performs simultaneously:
1. **Onboarding proof** -- the member watches their own words return as signed work inside the first ten minutes.
2. **Retention hook for days 1-21** -- a daily 60-second exchange that visibly produces a new record by afternoon. Question in, record out, every day.
3. **The lowest-friction creation mode in the product** -- Studio is deliberate, the engine is automated, the Question is conversational. For the 1-5 transaction member, this becomes the default way content gets made.

Market position (verified June 12, 2026): guided-question and voice-note content tools exist (Cleve and journaling-to-post apps end at a draft). No product pushes a proactive, signal-aware daily question and ends at a compliance-checked, published, signed, indexed provenance record. The back half of this loop is unduplicable without the CPR/authority-page stack.

---

## 2. CONSENT AND FRAMING

Shown before the first Foundation question, in plain language:

> **Three quick questions before your team gets to work.**
> Your answers do two things: they teach your team to write the way you actually talk, and they become the first records on your page -- your words, shaped up, signed by you.
> Three promises: **nothing publishes without your approval**, you can edit or discard anything, and you can skip any question, no reason needed.

Daily Question consent is established once, at the end of Foundation: *"Your team will ask you one quick question most mornings. Answer it and it becomes that day's content. Ignore it and nothing happens."* Member-configurable in Settings: daily / weekdays only / off.

Standing rules (both modes): per-question Skip, always visible. No questions touching family, health, finances, politics, or religion -- excluded by construction (no question in any bank can be answered more naturally with sensitive content than safe content). Raw answers are stored as voice source material and provenance evidence; discarding a generated record discards the record, while the answer may still inform voice (disclosed in the consent line).

---

## 3. MODE A -- FOUNDATION SEQUENCE (SIGNUP)

**The three questions** (highest-yield trio from v1's research-grounded set; rationale preserved in v1 Section 2, summarized here):

| # | Question | Mechanism | Record produced |
|---|---|---|---|
| F1 | "What do you wish every [primary niche audience] knew before they ever called anyone?" | Client-protective stance = warmth + competence at once | Definitive-answer record, question-form heading (extraction-grade) |
| F2 | "What was the moment you knew this was the work for you?" | Narrative + warmth; "the moment" defeats the canned origin story | *Why I do this work* (story record) |
| F3 | "What's a question clients ask where you think they deserve a more honest answer than they usually get? Give them the honest answer." | Two-sided honesty -- the strongest single credibility device | *The honest answer* (stance record) |

**Input:** voice memo preferred ("answer like you're leaving a voicemail to a friend -- about 60 seconds"), typed fallback always available. Optional shortcut on the same screen: "Or paste 2-3 posts you've written that sound like you" -- members with existing voice data can seed the exemplar pool directly and skip to F1 only.

**Flow:** F1 answered → generation starts in background → F2 answered → F1's record is ready → **the reveal**: member reviews, edits inline, approves → Record #1 is live on their page. F3 answered; its record and F2's queue for review immediately after. Total member time: ~5 minutes. The page exists with 1-3 records before onboarding's remaining artifacts (calendar reveal, Day Zero screenshot, announcement post, badge) per POSITIONING_FUNNEL_SPINE_v3 Stage 4.

**Remaining v1 questions (Q4 deal-that-almost-died, Q5 early mistake, Q6 off-the-clock, Q7 ordinary place, Q9 what-it's-like, Q10 market outlook, plus Q2 newcomers-ask)** are not asked at signup. They become the Daily Question content for days 1-7 -- which makes the Foundation publication drip happen naturally instead of by scheduler artifice.

---

## 4. MODE B -- DAILY QUESTION (PERMANENT)

**Delivery:** one card in the morning briefing (Jordan's voice): question text, [🎤 Answer] [⌨️ Type] [Skip]. Mirrored in the notification digest once Twilio A2P clears (NOTIFICATION_DIGEST_SPEC: the question becomes a digest line item, never a separate per-event blast). Maximum one per day. Unanswered questions expire silently at day's end -- no streaks, no guilt mechanics, ever. The feature must feel like a colleague's question, not a chore app.

**Question sources, in priority order:**

1. **Foundation bank** (days 1-7): the seven remaining v1 questions, one per day, ordered Q2, Q4, Q7, Q5, Q9, Q6, Q10 (competence early, pratfall after competence is established per v1's research note, personal texture mid, forward-looking close).
2. **Signal-driven** (the killer variant; takes priority whenever available after day 7): the trend collector already harvests market signals. A signal tagged to the member's market/niche generates a question from a template set, e.g.:
   - Rate move → "Rates [moved X] this morning -- what's your honest take for [niche audience] who've been waiting?"
   - Inventory shift → "[Market] inventory just [shifted] -- what are you actually seeing on the ground?"
   - Local news item → "Everyone's talking about [signal] -- what does it mean for someone trying to [niche action] right now?"
   The member's 60-second answer becomes same-day, hyperlocal, timely, personally voiced commentary -- the single strongest content class for the extraction layer (Spine v3 §2), and unduplicable by generic tools because generic tools don't watch their market.
3. **Evergreen banks** (fallback rotation, tagged by category): client education ("What's the most expensive mistake you've watched someone make?"), process transparency ("Walk me through what actually happens in the 48 hours after an offer's accepted"), opinion ("What's a piece of common advice in your field you think is wrong?"), local texture, story prompts. Initial bank: 60 questions (Opus/Kevin to approve the bank as a content artifact; engine never invents questions outside approved banks except via signal templates).

**Repeat protection:** asked questions logged per member; evergreen questions don't repeat within 120 days; signal questions are inherently unique.

---

## 5. VOICE-MEMO PIPELINE

- **Capture:** browser MediaRecorder API (webm/opus), max 3 minutes, works on mobile web. Tap, talk, stop, send.
- **Transcription:** server-side speech-to-text (Whisper-class API). Store raw audio (provenance evidence + future voice features) and transcript. Cost note: pennies per answer; immaterial at current scale.
- **Fallback:** typed input always offered; transcription failure degrades to "we couldn't catch that -- type it or try again."
- **Privacy:** audio and transcripts are internal source material, never published; stated in consent. Member can delete any answer's audio in Settings.

---

## 6. GENERATION RULES (UNCHANGED FROM v1 -- THE ANTI-POLISH / ANTI-IDIOT CALIBRATION)

1. Preserve their phrasing -- distinctive words, rhythms, expressions survive verbatim where possible; the engine structures and trims, it does not rewrite.
2. Fix mechanics, keep one rough human edge per record; fully sanded output fails QA.
3. Never invent facts, numbers, credentials, or events beyond the answer. No superlative insertion ("top," "leading," "expert" banned).
4. Never dramatize; the member's modest version is the published version.
5. Auto-strip client-identifying details on story answers.
6. Full 12-layer compliance pass on everything; stance/pratfall records carry human-readable Auditor notes.
7. Output: 150-400 words, question-form or stance heading, 2-3 sentence definitive open (Spine v3 Build O architecture), then the texture. Voice exemplar block (Voice Phase 1) injected in all generation; **every approved question-record registers back into the exemplar pool** -- the voice system feeds itself permanently, which is the standing answer to voice drift ("voice is a moment, not a profile").

---

## 7. HUMAN-ORIGIN PROVENANCE FLAG

New record metadata: `origin_type` -- values `member_answer_voice`, `member_answer_text`, `engine_draft` (default for existing flows), `studio_authored`.

- **Display (record + authority page):** records originating from answers carry a quiet origin line: *"This piece began as [FirstName]'s own [spoken/written] answer, reviewed and approved before publication."* Truthful, verifiable against stored source, and a provenance class no competitor can mint: human-originated AND human-reviewed AND machine-structured.
- **Schema:** extend record structured data with the origin attribution (alongside existing reviewedBy/datePublished fields), language to be finalized in the G3 CPR-explanation pass so it reads cleanly to crawlers.
- **Honesty constraint:** the flag is set only by the answer pipeline. No backfill, no manual setting, no exceptions -- this flag's entire value is that it cannot be faked, including by us.

---

## 8. DATA MODEL (ADDITIVE; NO EXISTING TABLE ALTERED EXCEPT ONE COLUMN)

- `question_bank` -- id, text_template, category, source (foundation/evergreen/signal_template), niche_tags, active
- `member_questions` -- id, user_id, question_id (nullable for signal-generated), rendered_text, signal_ref (nullable), delivered_at, status (delivered/answered/skipped/expired)
- `member_answers` -- id, member_question_id, user_id, input_type (voice/text), transcript, audio_ref (nullable), created_at
- `compliance_records` -- **add column** `origin_type` (default `engine_draft`), `answer_ref` (nullable FK to member_answers)
Follow the standing large-file editing pattern and syntax-validation rule for all app.py work.

---

## 9. BUILD SESSIONS FOR SONNET (OPUS TO SEQUENCE INTO COMPLETE_PLATFORM_BUILD_SPEC)

| Session | Scope | Touches | Est. |
|---|---|---|---|
| DQ-1 | Data model (Section 8) + question bank seed (Foundation 10 + evergreen 60 as fixture) | database.py, migration, fixtures | 1 session |
| DQ-2 | Foundation flow UI: consent screen, F1-F3 capture (typed first), background generation, live reveal/edit/approve | onboarding templates, app.py routes | 1 session |
| DQ-3 | Voice-memo pipeline: MediaRecorder capture component, upload, transcription endpoint, fallback handling | app.py, JS, one new service call | 1 session |
| DQ-4 | Generation prompts per Section 6 (per-category templates), origin_type threading through approval → publish → CPR, origin display line + schema extension | content_engine.py, record/authority templates | 1 session |
| DQ-5 | Daily Question engine: delivery into briefing, scheduler, repeat protection, expiry, Settings toggle; Foundation bank days 1-7 ordering | app.py, briefing template, scheduler | 1 session |
| DQ-6 | Signal-driven questions: template set, trend-collector hook, rendering + priority logic | trend collector service, app.py | 1 session |
| DQ-7 | Digest integration (question as digest line item) -- gated on Twilio A2P | per NOTIFICATION_DIGEST_SPEC | Half session |

**Hard dependency: Voice Phase 1 ships before DQ-4.** Foundation records are its seed data; everything downstream generates through it.

---

## 10. SEQUENCING AGAINST THE JUNE 17 LAUNCH (SCOPE CONTROL -- READ THIS PART TWICE)

This system is worth building. It is not worth slipping the launch for, and most of it shouldn't try to make June 17:

- **Pre-launch (only if it fits without touching launch blockers):** Voice Phase 1 (already mandatory), DQ-1, DQ-2 with *typed input only*. That alone delivers the Foundation moment for Cohort 1's personal onboardings -- and on a Zoom onboarding, Kevin can run the questions conversationally and paste answers if the UI isn't ready, meaning **Cohort 1 gets the experience even with zero new code.** That is the fallback and it is fully acceptable.
- **Week 1-2 post-launch:** DQ-3 (voice memos), DQ-4, DQ-5 (daily mode live). Cohort 1 becomes the test group; their feedback shapes the bank.
- **Month 1:** DQ-6 (signal-driven), DQ-7 (digest, when Twilio clears).

Nothing here moves launch. The launch blockers remain the launch blockers.

---

## 11. DOCUMENT IMPACT (AMEND, DON'T REWRITE -- FOR NOW)

ADD v8 and Roadmap v7 already lag the Session 66 SSR changes. Do not attempt full rewrites of either before launch -- that's days of documentation work during launch week. Instead:

1. **Now:** one addendum file, `ARCHITECTURE_AND_ROADMAP_ADDENDUM_JUNE2026.md`, capturing: SSR architecture (Session 66), Growth Engine builds A-F, Spine v3 builds M-Q, this spec's DQ-1-7, Voice Phase 1 resequencing, and the funnel stages. Pin it beside the v8/v7 docs as the delta of record.
2. **Post-launch, first quiet week:** Opus consolidates into ADD v9 and Roadmap v8 in one sitting, then the addendum retires.

This honors the standing rule -- strategic decisions documented immediately -- without burning launch-week sessions on document archaeology.

---

*Foundation & Daily Question System -- Build Spec v2 -- June 12, 2026 -- Confidential -- HomeBridge Group, LLC*
*Prepared by Claude Fable 5. Awaiting Kevin's approval. The question is the interface; the voice is the product; the record is the proof.*
