# AUTOMATES -- VOICE AUTHENTICITY BUILD SPECIFICATION
## Generation Layer: From Description to Demonstration to Drift
**Prepared by:** Claude Opus 4.7 -- June 9, 2026
**For:** Kevin Lundy / HomeBridge Group, LLC
**Build executor:** Sonnet (against this spec, one file at a time, no improvisation)
**Status:** POST-LAUNCH. Do not touch any of this before Tuesday June 10. All five phases are sequenced for the weeks after launch.

---

## 0. WHY THIS DOCUMENT EXISTS

Generated content reads as "fine but not me." Kevin's diagnosis is correct and the root cause is now confirmed by code review.

The current system treats voice as a *profile* -- a static blob captured at onboarding and applied uniformly to every generation. Real human writing voice is not a profile. It is a moving target. The same person sounds different writing about a grieving family than about June inventory numbers, different on a Tuesday than on a Friday, different the morning after good news than after bad. Any static capture, no matter how carefully designed, will feel flat to the agent on the days when they are not the person the snapshot captured.

There is a second failure compounding the first. `content_engine.py` line 168 injects the Brand Voice text field as `f"Voice: {brand_voice}.\n"` -- meaning the agent's *prose description of their voice* is being inserted into the prompt as a style instruction. The model treats "I speak in clear, every day language" the same way it treats any abstract style direction. It produces something generic that nominally matches the description. The Zone of Greatness fields at lines 290-304 have the same problem -- they are framed as biographical context ("Why X does this:", "Their unfair advantage:") rather than as writing samples. The model sees descriptions of the agent's voice, never the voice itself.

Meanwhile, the system is sitting on its single best source of voice signal: 102+ approved posts in `content_library` for Kevin alone, and growing for every active agent. None of this is being used in generation. The system is ignoring the writing the agent actually approved in favor of the agent's prose description of how they think they write.

This spec fixes both failures and adds the moment-and-drift signal that no onboarding capture can provide.

**Honest scope:** This document does not promise that generated content will read perfectly as the agent on the first draft. The honest claim is: the gap from "AI draft" to "sounds like me" should close from rewriting to polishing. Two-minute edits instead of five-minute rebuilds. The Certified Provenance Record gets its meaning precisely because a licensed professional shapes the content -- if the AI got it perfect, the human review would be a rubber stamp. The product position remains: AutoMates produces the draft, the agent makes it theirs, the CPR records that they did.

---

## 1. ARCHITECTURE DECISION (LOCKED)

Voice is captured and applied as four concurrent signals, none of which has to be perfect on its own:

1. **Base voice** -- a short audio recording the agent makes once, in response to a concrete prompt of their choosing. Transcribed. Replaces the role currently played by the Brand Voice text field.
2. **Live voice** -- a rolling sample of the agent's last several approved posts. Updates automatically. Captures drift over time at zero cost to the agent.
3. **Moment** -- an optional daily ambient signal. One short question from Jordan. One short answer from the agent. Captures the day-to-day flux that no static capture can.
4. **Steering** -- per-generation modulation buttons (Warmer / Sharper / Quieter / Standard) that let the agent shape the output without writing prose to describe what they want.

All four are injected into `content_engine.py` generation prompts as *few-shot exemplars and contextual modifiers*, never as style descriptions. The single most important change in this spec is that line: descriptions become demonstrations.

Existing fields (Brand Voice text, Zone of Greatness, Words to Avoid / Words to Prefer) are retained but repositioned. Words to Avoid / Words to Prefer remain as guardrails -- they work. Zone of Greatness fields remain as identity context, framed in prompts as "who this person is," not as "voice." The Brand Voice text field is downgraded to optional supplementary description and the audio sample becomes the primary voice source.

No grading. No scores. No "voice strength meter." Voice gets stronger over time and the agent feels it in the output, not in a number.

---

## 2. PHASE 1 -- FEW-SHOT EXEMPLARS FROM RECENT POSTS (NO AGENT WORK, NO SCHEMA CHANGE)

This is the highest-leverage / lowest-risk change in the spec and should ship first. Every change here is in code already deployed. No agent action required. Any agent with at least one approved post gets immediate lift.

### 2.1 New helper in `content_engine.py`
A single function that returns the agent's recent approved posts as raw text strings, suitable for injection as few-shot examples:

```
def _get_voice_exemplars(user_id, context, limit=3, min_chars=200):
    """
    Returns up to `limit` recent approved posts for the user, filtered by context
    ('agent' or 'hb_marketing'), each at least min_chars long. Most-recent first.
    Returns [] if none qualify -- caller must handle the empty case.
    """
```

Implementation calls into `database.py` against `content_library` where `user_id` matches, `context` matches, `status` indicates approval (use whatever the existing approval status field is -- verify against database.py), and `content.post` length passes the minimum. Order by approval timestamp descending. Limit by `limit`.

Minimum character threshold prevents one-line approvals from polluting the exemplar set. Three exemplars is the target; fewer is acceptable; more does not help and consumes context window.

### 2.2 New prompt section in `_build_content_prompt`
After the existing `voice_profile_block`, before the AUDIENCE FILTER section, insert a new `voice_exemplar_block`:

```
exemplars = _get_voice_exemplars(user_id, content_mode_or_context, limit=3)
if exemplars:
    voice_exemplar_block = (
        f"\nHOW {agent_name.upper()} ACTUALLY WRITES -- READ THESE CAREFULLY\n"
        + "─" * 40 + "\n"
        + "Below are recent posts this agent approved and published. "
        + "Match the rhythm, sentence length, vocabulary register, and how warmth is expressed. "
        + "Borrow voice, not phrasing. Do not lift sentences. Do not blend registers from across samples -- "
        + "pick the closest match to the situation you are writing about and stay inside it.\n\n"
        + "\n\n---\n\n".join(f'Sample {i+1}:\n"{post}"' for i, post in enumerate(exemplars))
        + "\n"
    )
else:
    voice_exemplar_block = ""
```

User ID is not currently passed into `_build_content_prompt`. It needs to be threaded through from the calling route in `app.py`. This is the only call-site change required.

### 2.3 Reposition the existing voice descriptions
Brand Voice text and Zone of Greatness blocks remain in the prompt, but their framing changes. The new framing makes them context, not voice:

- Brand Voice field (line 168): change the prompt label from "Voice:" to "How the agent describes their own voice (use as supplementary context, not as the primary voice source):"
- Zone of Greatness block (lines 290-304): change the instruction at line 301 from "Let these shape the texture and point of view of the content" to "These are biographical context about who this agent is. The actual voice comes from the samples above. Use these to ensure the content reflects this person's worldview, not to dictate sentence rhythm or vocabulary."

When `voice_exemplar_block` is non-empty, these descriptive blocks are de-emphasized. When it is empty (new agents with no approved posts yet), they remain the primary signal as today.

### 2.4 Apply the same pattern to all three prompt builders
The same `voice_exemplar_block` logic must be added to:
- `_build_content_prompt` (agent generation)
- `_build_b2b_content_prompt` (HB Marketing generation -- pulls exemplars with `context='hb_marketing'`)
- `_build_freeform_content_prompt` (freeform mode)
- `_build_video_script_prompt` (video script generation)

All four builders currently follow the same structural pattern. The helper is shared.

### 2.5 Deploy and verify
Files touched: `content_engine.py`, `app.py` (call sites).
Deploy order: `content_engine.py` → `app.py`.
Health check: https://api.homebridgegroup.co/health
Verification: Kevin generates three posts in his agent workspace and three in HB Marketing. Compare against pre-Phase-1 generations (which still exist in his library). The new posts should feel measurably closer to his voice. If they do not, the exemplar query or the prompt restructure is wrong and needs diagnosis before Phase 2.

---

## 3. PHASE 2 -- AUDIO VOICE CAPTURE WITH PROMPTED BANK

Replaces the Brand Voice text field as the primary base-voice source. Agent action required: one two-minute recording. Optional re-record any time.

### 3.1 Prompt bank
Ten prompts, agent picks one. Mix of opinion, hypothetical, memory, and small observation. None of them are work-bounded. Speech under non-work prompts surfaces the same voice the agent uses for work, with the professional performance reflex disengaged. That is the point.

Initial bank (Sonnet copies these verbatim into a constant in `app.js`):

1. Who's winning the Super Bowl this year and why?
2. If someone handed you a million dollars and told you that you had to spend it all in one week, what would you do?
3. Best meal you've had in the last year -- where, what, and why does it stick with you?
4. What's something most people seem to agree on that you think is actually wrong?
5. Tell me about a teacher, coach, or mentor who actually changed something for you.
6. You can have dinner with anyone, living or dead -- who, where, what do you order?
7. What's a small thing that always makes you laugh?
8. Best movie you've seen in the last year and why everyone should watch it?
9. If you could go back and give your twenty-five-year-old self one piece of advice, what would it be?
10. What's a place you've been that you think about more than you expected to?

Bank may be extended in the future. No prompt should be work-bounded. No prompt should be heavy enough to risk a dark answer (see Section 3.6 on safety).

### 3.2 Schema additions
`agent_setup` table gets four new columns (non-destructive ALTER TABLE migration):

- `voice_sample_transcript` (TEXT, nullable)
- `voice_sample_prompt_text` (TEXT, nullable) -- the prompt the agent answered, stored verbatim for context
- `voice_sample_captured_at` (TIMESTAMP, nullable)
- `voice_sample_audio_url` (TEXT, nullable) -- optional, for replay in UI; nullable because audio may be discarded after transcription

No new table is needed. Voice sample history (multiple samples over time) is deferred to a future iteration; for now, the most recent sample overwrites. Add a `voice_sample_history` JSON column if Kevin wants history preserved -- recommend deferring.

### 3.3 Backend routes
- `POST /voice/sample/upload` -- accepts audio blob, transcribes via existing LMNT infrastructure (or whichever transcription service is already wired -- verify against social.py and video pipeline), returns transcript for confirmation. Does not save yet.
- `POST /voice/sample/save` -- accepts confirmed transcript + prompt_text. Writes to `agent_setup`. Returns success.
- `GET /voice/sample/current` -- returns the agent's current sample for display in Identity panel.
- `DELETE /voice/sample` -- clears the sample. Optional but recommended; agents should be able to remove a recording they regret.

### 3.4 Identity panel UI changes
Add a new section "Voice Sample" between Zone of Greatness and How to Reach You. Components:

- Header: "Voice Sample" with subhead "A two-minute recording. The system uses this to learn how you actually sound -- not how you describe your sound."
- Prompt picker: pill buttons showing all ten prompts. Agent clicks one.
- Record button: prominent. Click to start, click to stop. Visual timer counts up to 2:00 then auto-stops.
- Playback: after recording, agent can play back, re-record, or proceed to transcribe.
- Transcript display: editable. Agent can fix transcription errors before saving.
- Save button: writes transcript + prompt to backend.
- Status line below: "Last captured: [date]" or "No sample captured yet."

The existing Brand Voice text field stays in the Identity panel but gets a new subhead: "Description of your voice (optional -- the voice sample above is what the system actually uses to write)." This signals the demotion without removing the field, preserving any existing data.

### 3.5 Prompt injection
In `content_engine.py`, the `voice_exemplar_block` from Phase 1 becomes the *secondary* sample source, with the audio transcript as the *primary*:

```
audio_sample = profile.voice_sample_transcript or ""
recent_posts = _get_voice_exemplars(user_id, context, limit=3)

samples = []
if audio_sample:
    samples.append(("Spoken sample -- this is the agent's natural unscripted voice", audio_sample))
for i, post in enumerate(recent_posts):
    samples.append((f"Recent approved post {i+1}", post))

if samples:
    voice_exemplar_block = (
        f"\nHOW {agent_name.upper()} ACTUALLY SOUNDS\n"
        + "─" * 40 + "\n"
        + "The samples below are real -- the spoken sample is unscripted; the posts are recent published work. "
        + "Match the rhythm, register, and vocabulary. Borrow voice, not phrasing. "
        + "Stay inside one register per piece; do not blend.\n\n"
        + "\n\n---\n\n".join(f'{label}:\n"{text}"' for label, text in samples)
        + "\n"
    )
```

Order matters: audio first (it is the freshest, most natural sample), then posts in recency order.

### 3.6 Safety
- Maximum recording length capped at 2:00. Hard stop.
- Transcript is shown before save -- the agent sees what was captured.
- Delete option always present.
- Audio URL storage is optional. Recommend NOT storing audio long-term -- transcribe, save transcript, discard audio. This sidesteps biometric storage questions for non-LMNT use (LMNT voice clones are a separate consent flow).
- No transcript content is exposed in any public-facing surface.

### 3.7 Deploy and verify
Files touched: `database.py` (schema migration), `app.py` (routes), `app.js` + `index.html` (Identity panel UI), `content_engine.py` (injection).
Deploy order: `database.py` → `app.py` → `content_engine.py` → `app.js` → `index.html`.
Verification: Kevin records a sample, confirms transcript, generates a post. The post should reflect the spoken voice register more than the descriptive Brand Voice field did.

---

## 4. PHASE 3 -- DAILY AMBIENT SIGNAL

The piece that captures flux. Optional. Dismissible. Off by default for new agents until they have been around at least seven days.

### 4.1 What it is
A Jordan card on the Home screen that surfaces one short question per day. Agent answers in a single sentence, fifteen seconds. Or scrolls past. If they scroll past three days in a row, the system pauses for fourteen days before asking again.

The day's answer is injected as moment-context into every generation that day. Posts generated the next morning use the previous day's most recent answer (or no answer, if none given).

### 4.2 Question bank
Rotating, never repeats within fourteen days. Mix of light and reflective. Same principles as the audio prompts -- never work-bounded, never heavy enough to risk a dark answer.

Initial bank (Sonnet copies verbatim):

1. What's been on your mind this morning?
2. Anything in the news this week coloring how you feel?
3. Who's someone you want to reach today?
4. What's something good that happened yesterday?
5. What's been making you laugh lately?
6. Is there a song stuck in your head?
7. What did you have for breakfast?
8. What's the weather feel like today?
9. What's something you're looking forward to this week?
10. Tell me about something small you noticed yesterday.
11. What's one thing you'd skip if you could today?
12. Who's someone you've been thinking about?

Bank may be extended. Same safety rule applies -- if a question lands too heavy in field testing, replace it.

### 4.3 Settings
A single setting in Identity: "How often should Jordan check in?" with three options:

- Daily (default for agents who explicitly turn it on)
- Weekly (default after first seven days, if the agent hasn't engaged with daily)
- Never

The setting is stored on the user record, not in agent_setup. Field name: `mood_check_frequency`. Values: `daily`, `weekly`, `never`. Default at registration: `weekly`.

### 4.4 Schema
New table `daily_mood_entries`:

- `id` (PRIMARY KEY)
- `user_id` (INTEGER, FK)
- `prompt_text` (TEXT) -- the question asked
- `response_text` (TEXT, nullable) -- the answer; nullable so we can record dismissals
- `dismissed` (BOOLEAN, DEFAULT FALSE)
- `entry_date` (DATE) -- one entry per user per day
- `created_at` (TIMESTAMP, DEFAULT NOW)

UNIQUE constraint on (user_id, entry_date). Inserting a second entry for the same user-day either replaces or no-ops -- Sonnet picks one and documents which in code.

### 4.5 Backend routes
- `GET /mood/today` -- returns today's prompt for this agent (or null if frequency setting suppresses today), and any existing answer for today.
- `POST /mood/submit` -- accepts response_text. Writes to daily_mood_entries.
- `POST /mood/dismiss` -- writes a row with dismissed=true.
- `GET /mood/recent?days=N` -- returns recent entries for the agent (used by `content_engine.py` and optionally by Jordan to show history).

### 4.6 Prompt injection
A new helper in `content_engine.py`:

```
def _get_ambient_context(user_id):
    """
    Returns the most recent mood entry for this user from the last 36 hours.
    Returns None if no entry exists or the most recent was dismissed.
    Output is a string suitable for direct injection.
    """
```

Inject into the prompt as a small new block, between voice samples and the audience filter:

```
ambient = _get_ambient_context(user_id)
if ambient:
    ambient_block = (
        f"\nTODAY'S CONTEXT FOR {agent_name.upper()}\n"
        + "─" * 40 + "\n"
        + f"Earlier today, when asked '{ambient['prompt']}', the agent said: '{ambient['response']}'\n"
        + "This is the mood and context the agent is in right now. "
        + "It does not need to be referenced explicitly in the content. "
        + "Let it shape tone -- warmer, sharper, lighter, more reflective -- as appropriate to the situation. "
        + "Never quote it. Never name it. Just write from that place.\n"
    )
else:
    ambient_block = ""
```

The 36-hour window covers normal evening-to-morning rhythm without using stale signal.

### 4.7 Jordan card UI
On the Home screen, a small card with:
- Header: "Quick check-in" (no "mood" label -- too clinical)
- The question text
- Single-line input field
- Two buttons: "Send" and "Skip today"
- Below: "You can change how often I ask in Identity > Voice settings."

Visual style matches existing Jordan momentum cards. Dismisses on submit or skip. Re-appears next scheduled day per frequency setting.

### 4.8 Deploy and verify
Files touched: `database.py`, `app.py`, `content_engine.py`, `app.js`, `index.html`.
Deploy order: `database.py` → `app.py` → `content_engine.py` → `app.js` → `index.html`.
Verification: Kevin answers the ambient question with something light ("watched my grandson learn to ride a bike yesterday"), then generates a post about probate. The post should carry warmth that wasn't in pre-ambient generations.

---

## 5. PHASE 4 -- GENERATION-TIME MODULATION

The smallest change with the broadest leverage for hard days. Lets the agent shape output without writing prose to describe what they want.

### 5.1 What it is
Four buttons that appear in Studio before the Generate action: **Standard / Warmer / Sharper / Quieter**. Default is Standard (matches current behavior exactly). The other three modulate the prompt.

- Warmer: more personal, more compassionate, slower rhythm, more invitation, less declarative.
- Sharper: more direct, denser, more position-taking, less hedging, more peer-level.
- Quieter: less performative, more reflective, shorter sentences, more space for the reader to fill in.

These are not registers in a fixed taxonomy. They are modifiers. The model interprets them in context with the rest of the prompt.

### 5.2 Schema
A single new field on `ContentRequest` in `content_engine.py`:

```
modulation: Optional[str] = Field("standard")  # "standard" | "warmer" | "sharper" | "quieter"
```

No database change needed. Modulation is per-generation, not persisted.

### 5.3 Prompt injection
At the top of the VOICE & STYLE section in each prompt builder, insert:

```
modulation = (payload.modulation or "standard").lower()
mod_lines = {
    "standard": "",
    "warmer":   "MODULATION: Lean warmer. More personal, more invitation, slower rhythm. Compassion over efficiency. Imagine writing to one person who is going through something.\n",
    "sharper":  "MODULATION: Lean sharper. More direct, more position-taking, denser. Cut hedge phrases. Write as a peer to peers, not as a teacher to students.\n",
    "quieter":  "MODULATION: Lean quieter. Less performance, shorter sentences, more space. Trust the reader to fill in. State less; imply more.\n",
}
modulation_block = mod_lines.get(modulation, "")
```

Insert `modulation_block` right after the existing `tone_text + length_text + EM_DASH_RULE + avoid_text + prefer_text` line.

### 5.4 UI changes
Four small buttons in the Studio generate panel, above the Generate action. Selected button is visually distinct (gold background per design system). Default selection is Standard. Selection is not sticky between generations -- each generation defaults to Standard unless the agent picks otherwise.

### 5.5 Deploy and verify
Files touched: `content_engine.py`, `app.py` (pass-through), `app.js`, `index.html`.
Deploy order: `content_engine.py` → `app.py` → `app.js` → `index.html`.
Verification: Kevin generates the same post twice -- once Standard, once Warmer. The Warmer version should feel measurably softer.

---

## 6. PHASE 5 -- EDIT-PATTERN LEARNING (POST-LAUNCH, AFTER DATA)

This phase requires real data to be valuable. Do not build until at least three months after launch, or until Kevin alone has thirty-plus posts where the original draft and the final approved version meaningfully differ.

### 6.1 What it is
Every approval is also an implicit correction. When the agent edits a draft before approving, the (draft → final) pair contains signal about what the model got wrong. A periodic analysis pass extracts patterns -- "this agent consistently shortens sentences over eighteen words," "this agent replaces 'help' with 'serve,'" "this agent removes intensifiers" -- and stores them as an edit-pattern addendum on the agent's voice profile.

The addendum gets injected alongside the voice samples in future generations.

### 6.2 Why this is last
Three reasons:
- Without enough edits, the patterns are noise.
- Some edits are time-pressured rubber-stamps and shouldn't count. Filter rules need real edit data to tune.
- The technical complexity is higher than any of Phases 1-4 and the lift is uncertain. Phases 1-4 might be enough.

### 6.3 What to build (sketch, not full spec)
- Schema: store both `draft_post` and `final_post` on `content_library` rows (currently only the final is preserved -- verify against database.py).
- Worker: monthly job that runs a one-shot Claude analysis per agent, extracting up to five edit patterns from their recent (draft, final) pairs.
- Storage: `voice_edit_patterns` JSON field on agent_setup, refreshed monthly.
- Injection: append to voice_exemplar_block as "Patterns this agent applies when editing: ..."

Full spec to be written when Phase 5 is actually being built. Do not start before then.

### 6.4 What to flag now
The only Phase 5 prerequisite is **preserving the draft**. Currently `content_library` stores only the final approved version. Phase 1's verification will not be possible to deepen later without this. Recommend: as part of Phase 1, add a `draft_content` JSON column to `content_library` with the originally-generated content, populated at generation time. The agent's edit then implicitly equals (draft_content vs. content). Zero cost to add now; large cost to backfill later. This is the only thing from Phase 5 that should ship earlier than Phase 5.

---

## 7. WHAT THIS DOES AND DOES NOT PROMISE

**Does:** Closes the gap from "AI draft" to "sounds like the agent" from rewriting to polishing. Makes the system get measurably better at each agent's voice over time, without that agent doing any additional work. Adds optional engagement for agents who want stronger voice faster. Preserves the differentiator: AutoMates produces the draft, the agent shapes it, the CPR records that a licensed professional reviewed and approved.

**Does not:** Produce content that reads perfectly as the agent on the first draft. Eliminate the need for review. Replace good writing instincts. The CPR's value depends on real human review, and real human review depends on there being something for the human to do. A draft that needs polishing is the feature.

**The honest product claim:** AutoMates generates a draft that gets closer to the agent's voice the longer the agent uses it. The agent's edits are what make it theirs. The CPR is the permanent record that they reviewed and approved. That is what is being sold.

---

## 8. BUILD ORDER SUMMARY

| Phase | What | Agent work? | Schema change? | Risk |
|-------|------|-------------|----------------|------|
| 1 | Few-shot exemplars from approved posts | None | None (add draft_content column as prerequisite for Phase 5) | Low |
| 2 | Audio voice capture + prompt bank | 2 min once | Add 4 columns to agent_setup | Low |
| 3 | Daily ambient signal | 15 sec/day optional | New table daily_mood_entries + user setting | Low |
| 4 | Generation-time modulation buttons | None | None | Low |
| 5 | Edit-pattern learning | None | Edit pattern JSON + worker | Medium, defer |

Recommended sequence: 1 → 4 → 2 → 3 → 5. Phase 4 jumps ahead of 2 because it is the smallest possible build and ships meaningful steering immediately. Phases 2 and 3 require more UI work and can follow.

Hard rule: nothing in this spec ships before Tuesday June 10. All five phases are post-launch.

---

## 9. ADDITIONS REQUIRED TO MASTER RE-ENTRY PROMPT

Three small edits to the existing post-Session-65 Master Re-Entry Prompt. Do not rewrite the whole document.

**Add to "POST-LAUNCH QUEUE" section, near the top (high priority but post-launch):**

> 2.5. Voice authenticity work (see VOICE_AUTHENTICITY_BUILD_SPEC.md) -- five phases, sequenced 1→4→2→3→5. Phase 1 is highest priority (few-shot exemplars from content_library, no agent work). All phases post-launch.

**Add to "FILES TO PROVIDE AT SESSION START" section:**

> For voice authenticity work (see VOICE_AUTHENTICITY_BUILD_SPEC.md):
> - content_engine.py (Render)
> - database.py (Render)
> - app.py (Render)
> - app.js (Render)
> - index.html (app, Render)

**Add to the doctrine block under "PRODUCT LANGUAGE -- LOCKED" or "BRAND AND DESIGN -- LOCKED":**

> Voice is captured as demonstration, not description. The agent's audio sample, recent approved posts, and daily ambient answers are voice signal. The Brand Voice text field is supplementary description only. The system never grades voice strength.

That is the full delta to the Master Re-Entry Prompt. The rest stands.

---

*AutoMates Voice Authenticity Build Specification -- June 9, 2026 -- Confidential -- HomeBridge Group, LLC*
*Prepared by Claude Opus 4.7. This is the generation-layer companion to the publishing-layer work in AUTHORITY_INDEXABILITY_BUILD_SPEC.md. All five phases are post-launch.*
