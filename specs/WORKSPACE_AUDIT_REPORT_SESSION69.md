# AUTOMATES -- WORKSPACE BOUNDARY AUDIT REPORT
## Full Platform UX and Information Architecture Audit
**Conducted by:** Kevin Lundy (founder) + Claude Sonnet 4.6 (Session 69)
**Date:** June 11, 2026
**Prepared for:** Claude Opus -- Strategic IA Redesign Session
**Status:** Audit complete. No fixes applied. All findings documented for Opus review before any code is written.

---

## WHY THIS AUDIT WAS CONDUCTED

AutoMates is targeting a June 17, 2026 launch with its first cohort of Founding Members. In preparing for launch, several workspace boundary bugs were discovered across multiple sessions -- compliance history bleeding between workspaces, HB Marketing content context errors, schedule save failures in the HB Marketing workspace, and admin dashboard issues described by Kevin as "crap." These bugs, taken individually, appeared to be isolated code issues. Taken together, they pointed to a deeper problem: the platform's information architecture was never comprehensively designed. It was built feature by feature, session by session, and the result is a set of workspaces where things are placed where they landed during development -- not where an agent, broker, partner, or admin would naturally look for them.

The audit was also prompted by a strategic inflection point. AutoMates is repositioning from "a content tool for real estate agents" to "the provenance registry for licensed professionals." That repositioning has implications for every workspace. A registry has different UX expectations than a SaaS tool. Members of a registry expect clarity, permanence, and a sense of belonging to something. The current platform does not consistently deliver that.

The decision was made to conduct a full workspace-by-workspace audit BEFORE writing any more fixes, so that individual bug fixes do not entrench a broken architecture further. This document is the output of that audit. Opus must produce an Information Architecture specification before Sonnet touches the workspace structure.

---

## CRITICAL PRE-LAUNCH ITEM NOT COVERED IN AUDIT: DEMO MODE

The Demo mode was not audited in this session because it is a separately tracked priority item. However, it must be called out explicitly here because it is a significant pre-launch blocker.

**Current state:** The demo currently shows only the onboarding flow. It does not show the full platform pipeline -- voice capture, content generation, compliance check, CPR issuance, authority page, verify page, or Jordan briefing. A prospect who clicks a demo link sees onboarding and nothing else.

**Why this matters for launch:** The Founding Member acquisition strategy (per GROWTH_ENGINE_BRIEF_FABLE5.md) depends on the Mirror Engine -- generating a Ghost Page preview for prospects and showing them what their authority page would look like. This requires a demo that shows the full platform, not just onboarding. Additionally, the current demo is not consistent with the current platform design. The platform has undergone significant design updates (split gold color system, Outfit + DM Sans fonts, new login page, SSR authority pages) that are not reflected in the demo experience.

**What is needed:** A full demo mode overhaul. Opus specification required before Sonnet builds. This must be completed before or immediately after launch -- it is the primary sales tool for post-Founding-Member acquisition.

---

## AUDIT FINDINGS BY WORKSPACE

---

### WORKSPACE 1: PLATFORM (ADMIN)

**Navigation sub-bar:** Dashboard, Users, Create User, Demo Links, Audit Log, Compliance, Leads

#### Dashboard
- 4 stat cards show: Total Users, Offices/Agents, Total Content, Published/Scheduled -- all vanity metrics with no actionable value
- No system health indicators (API status, Render uptime, Twilio A2P status, SendGrid status, Cloudflare status)
- No KPI tracking (indexed pages in Google, CPR records issued this week, agent approval rate, active vs inactive agents)
- No trend lines -- numbers without context are meaningless for decision-making
- No alert surface -- if something breaks, the dashboard does not tell Kevin
- Large dead space below the 4 cards -- page ends after the stat row
- Jordan/George button appears but is not useful or appropriate in admin context
- A dashboard must enable data-driven decisions, spot trends, track performance, and monitor activity at a glance. This one does none of those things.

#### Users Tab
- User list shows name, brokerage, role, plan, join date, status, and action buttons -- adequate starting point
- Missing: phone number per user
- Missing: last active date -- Kevin cannot identify inactive agents to reach out to
- Missing: edit capability on core fields (email, brokerage, phone) -- must open a separate flow
- Missing: password reset trigger per user
- Missing: plan usage per user (video count vs limit, post count vs limit) -- Kevin cannot troubleshoot "I'm at my limit" complaints
- Missing: bulk import and bulk export
- Missing: sort by signup date, inactivity period, or role type
- Missing: visibility into where agent is in onboarding flow

#### Create User Tab
- Functional and adequate
- Missing: optional phone number field

#### Demo Links Tab
- Can generate and copy demo links -- functional
- Missing: ability to email the link directly to a prospect from this screen (requires opening external email client)
- Demo overhaul is a separate priority -- see Critical Pre-Launch Item above

#### Audit Log Tab
- Displays timestamped admin actions -- technically correct
- No drill-down -- nothing is clickable
- Technical action names (audit_log_viewed, admin_reset_niches) mean nothing to Kevin without plain language descriptions
- No filter by date range, action type, or user
- No export
- As currently built, this log is for compliance defense, not operational understanding. Kevin gets no value from reading it.

#### Compliance Tab
- 12-layer framework displayed -- conceptually correct and strategically important
- Only 5 of 12 layers have Active or In Progress status
- 7 layers incomplete: ADA Accessibility, State Deceptive Trade Practices, Copyright/IP Law, Platform Ad Rules, FinCEN (monitoring only), AI-Generated Content Compliance (in progress), Civil Rights Act (in progress)
- Incomplete compliance layers visible to super_admin today -- will be visible to agents if access controls are not correct
- This is a credibility problem. If AutoMates' positioning is "the provenance registry for licensed professionals" and its own compliance framework is visibly incomplete, that undermines the core value proposition
- All 12 layers must be completed. This is a strategic imperative, not a nice-to-have.
- Verified dates and next-review dates present for active layers -- this is good and should be preserved

#### Leads Tab
- Populated by public compliance checker form submissions -- not CRM leads in any traditional sense
- Label "Leads" is misleading -- these are compliance checker users, not sales prospects
- "3F or 5P" result labels are unexplained -- means nothing without a legend (presumably 3 Failures, 5 Passes)
- "Post Preview" column shows content someone submitted for checking -- not obviously useful without context
- No HubSpot connection
- No pipeline view, no lead status, no follow-up tracking
- Jordan/George button appears -- not useful in admin context

#### Profile Dropdown (top right, admin context)
- Dropdown shows: Getting Started, Kevin Lundy / email, Upload Photo, Identity, My Profile, Billing, Sign Out
- "Getting Started" navigates to Agent home content while still in Platform workspace -- wrong context, should be removed from admin dropdown
- "Identity," "My Profile," and "Billing" are agent-context items -- should not appear in Platform Admin dropdown
- Platform Admin dropdown should contain only: Kevin Lundy / email, Upload Photo (acceptable), Sign Out
- "Ask George" button appears at bottom right of Platform workspace -- agent branding in admin context, should not appear

---

### WORKSPACE 2: AGENT (MY WORK)

**Navigation sub-bar:** Home, Studio, Records, Identity, Profile

#### Profile Dropdown (agent context)
- "Getting Started" link navigates to onboarding "you're all set" screen -- useless for an active agent, should be removed
- "Identity" and "Profile" appear as separate items in the dropdown AND as separate nav items -- the distinction between them is not clear to agents
- Dropdown should contain: name/email, Upload Photo, Sign Out

#### Home
- Morning Brief (George/Jordan) is well-executed -- fresh daily, actionable, sets the tone
- Team's Work section (Your Analyst, Your Writer) is functional and useful
- Market signals surfaced correctly
- "Profile" appears in the top nav bar -- this is a one-and-done item that belongs only in the dropdown, not in primary navigation
- "Ask George" button is present but not fully useful yet -- hiding it until it provides genuine value is preferable to showing a half-built feature
- The team introduction panel (shown when George is opened) is underselling -- text too small relative to available space, the team concept is the product's biggest differentiator and it is not communicated with appropriate weight

#### Studio
- Kevin's favorite page -- well-designed and functional
- 7 content mode choices may be too many for some agents -- worth flagging for Opus but not a blocker
- Quick Post mode does not clearly communicate that content can be personal or non-business -- this is a missed opportunity given the voice authenticity work planned

#### Records
- Functional but designed incrementally -- never comprehensively designed as a professional repository
- Action buttons (Approve, Resend to My Phone, Publish, Archive, Delete) are cramped -- added over time without layout rethinking
- The platform is repositioning around the word "Registry." This page IS the actual registry -- the permanent record of every CPR-verified piece of content. It does not feel like a registry. It feels like a task list.
- No elegance. No sense of permanence. The most important page in the product deserves a comprehensive redesign.
- Headline text truncated in list view -- agents cannot read what the post says without clicking in

#### Identity
- Page subtitle: "Your voice, your market, your niches. The foundation every post is built on." -- accurate but the page contains far more than that
- Authority page URL appears ONLY on this page -- agents may never find it. Should appear on Home, Records, and Identity.
- Jordan guidance block appears here -- wrong place. Jordan belongs on Home, not in a settings-like page
- Platform connection count, schedule status, posts on record stats appear here -- wrong place, belongs on Home or a dedicated Activity page
- Niches section is clean and functional -- no issues
- Content Schedule is buried inside Identity -- it is the most operationally critical setting on the platform and it is hidden inside a page called "Identity." It deserves its own nav item or significantly more prominent placement.
- "Your Voice" section label is ambiguous -- it appears next to the LMNT voice recording status, but agents don't know if "Your Voice" means their written voice style or their recorded audio. These are two completely different things and they need two different labels.

#### Profile
- Catastrophically long -- contains: Account Info, Zone of Greatness, Recruiting pitch, Short Bio, Brand Voice, Words to Avoid/Prefer, Designations, Languages, Platform Connections, Disclaimers, Billing, Jordan name customization
- These are unrelated items grouped by the fact that they had nowhere else to go
- "Words to Avoid/Prefer" belongs in Identity (voice configuration), not Profile (account settings)
- Platform Connections buried at the bottom of an endless page -- one of the most important settings on the platform, impossible to find
- Billing buried at the bottom -- agents who have billing questions will not find it here
- Jordan name customization at the bottom -- low-priority item getting equal visual weight with everything else
- The Profile page, as currently structured, will scare away agents. It communicates "this platform is complicated." The irony is that all this information IS needed -- it just cannot live on one page in this format.
- "Identity" and "Profile" as concepts are not distinct enough for agents to know which one they need. This confusion shows up in the dropdown, the nav, and the pages themselves.

---

### WORKSPACE 3: HB MARKETING

**Navigation sub-bar:** Identity, Studio, Edit, Records, Activity, Profile

#### Navigation Inconsistency
- Agent nav order: Home, Studio, Records, Identity, Profile
- HB Marketing nav order: Identity, Studio, Edit, Records, Activity, Profile
- Completely different structure for the same platform -- disorienting when switching workspaces
- No "Home" equivalent in HB Marketing -- no morning briefing, no team work surface, no daily orientation
- HB Marketing has "Activity" that Agent does not have -- and Activity is genuinely useful, which makes its absence in Agent worse

#### Identity
- Same Jordan-in-wrong-place issue as Agent
- "Primary Niches" label makes no sense in a B2B marketing context
- In Profile, the equivalent section is called "Who We Serve" -- that label is dramatically clearer and should be used everywhere, including Agent workspace
- Primary Niches in Identity shows "Compliance and Ethics" and "Agent Visibility and Growth" -- these are content categories, not audience segments
- The relationship between "Who We Serve" in Profile and "Primary Niches" in Identity is completely opaque -- Kevin himself could not explain the connection
- No sub-niches -- further reduces clarity
- Content Schedule buried in Identity -- same problem as Agent

#### Studio
- Same as Agent Studio
- No market context -- HB Marketing has no geographic anchor, making content feel generic
- Otherwise functional

#### Edit Tab
- Opens "Workspace" panel that says "No content here yet. Generate content and it will appear in Records -- click Edit in Workspace to refine it here."
- This feature was never completed or was abandoned
- It is a dead nav item -- confusing and embarrassing for a paying customer to encounter
- Should be removed from nav until the feature is actually built and useful
- Editing should happen inside Records directly, not in a separate tab

#### Records
- Identical layout and same issues as Agent Records
- Same cramped buttons, same incremental design
- Compliance Report button present but labeled "(NAR, state licensing)" -- this is agent-specific compliance framing in a B2B marketing workspace

#### Activity
- Genuinely good page -- the best informational page in the HB Marketing workspace
- Shows: Published count, Platforms Reached, Compliance Rate, Pending Review, Generated Total, This Month count, Active Schedules, Content by Niche breakdown with progress bars
- This page should exist in the Agent workspace -- agents want to see this data about their own content
- Missing: WHERE each piece of content was published (which platform)
- Missing: CPR record count -- the most important metric on the entire platform is absent from this page
- Content by Niche list shows agent niches (Senior Housing, Probate, Seller Representation) mixed with B2B niches (Independent Brokerages) -- confirms context bleed in activity reporting. Agent content is appearing in HB Marketing activity data.

#### Profile
- "My Profile" header appears at top of page
- "Name your Chief of Staff" section appears below it
- "My Profile" section header appears AGAIN below the Chief of Staff section -- two "My Profile" labels on one page
- No Zone of Greatness -- appropriate for a company profile, but the page doesn't explain what it is vs the agent profile
- Change Password appears at bottom -- same account-level function duplicated in both workspace profiles for no reason
- Page feels like a stripped-down copy of Agent Profile rather than a purpose-built company marketing profile
- No press release tool, no announcement format, no B2B-specific content types
- Assumes same social publishing channels as Agent -- LinkedIn and Facebook make sense for B2B, but the strategy is different

#### HB Marketing Meta-Finding
This workspace was built to serve AutoMates' own business marketing needs but has drifted into being a pale imitation of the Agent workspace. It lacks a clear identity of its own. If AutoMates is positioning as a registry that licensed professionals join, then HB Marketing is where the registry is managed and grown -- and it needs tools that reflect that purpose: agent acquisition pipeline, onboarding tracking, published content performance by platform, press/announcement formats, and a live view of the registry itself. None of those exist.

---

### WORKSPACE 4: MY OFFICE

**Navigation sub-bar:** Overview, Agents, Compliance, Identity

#### Navigation (Broken)
- Sub-nav tabs do not work when clicked -- page stays on Overview regardless
- Only the Identity sub-nav tab navigates correctly
- Clicking Agents in sub-nav does nothing; clicking Agents in the in-page tab works -- two navigation systems in conflict
- Clicking Compliance in sub-nav stays on Agents tab; clicking Compliance in-page tab works -- same conflict
- Broken navigation in a workspace intended for brokers is unacceptable at launch

#### Overview
- Office code displayed and copyable -- useful
- 4 stat cards all show 0 (no agents enrolled) -- understandable but no empty state guidance
- "Invite an Agent" form present -- correct concept, not yet tested with real data
- No publishing activity, no CPR records, no compliance history

#### Agents Tab
- Completely empty -- blank white screen with no agents enrolled
- No empty state messaging or guidance -- just nothing

#### Compliance Tab (in-page)
- Shows Compliance Record with filter buttons (All, Flags, Fails, Clean) -- correct concept
- Date range search and Download PDF present -- actually useful when populated
- Currently stuck on "Loading..." -- may be a data or rendering bug
- "You have oversight responsibility -- not editorial control" is a good legal distinction, well placed

#### Identity Tab
- Only tab that navigates correctly from sub-nav
- Assumed same issues as Agent Identity -- not reviewed in detail

---

### WORKSPACE 5: MY TEAM

- Identical structure to My Office with "Members" replacing "Agents"
- Same broken navigation
- Same empty state
- No distinguishing features from My Office whatsoever
- Zero functional or design difference between the two workspaces
- The original intent was: brokers are compliance/recruitment driven, team leads are production/recruitment driven. That distinction was never built into the actual screens.
- **Recommendation:** Consolidate My Office and My Team into one workspace unless Opus can identify a specific feature that genuinely requires the separation. Two identical broken placeholders are worse than one complete workspace.

---

### WORKSPACE 6: PARTNER

**Navigation sub-bar:** Overview, Referrals, Earnings, Payouts

#### Overall Assessment
- Best designed workspace on the platform
- Built in fewer than 3 sessions -- demonstrates what focused, purpose-driven design produces
- Clearly defined purpose from the first screen
- Instant information -- partner knows where they stand immediately
- Guided action -- 3-step getting started process is clear and motivating
- Cockpit/control center feel -- this is the design standard every other workspace should be measured against

#### Overview
- Referral code + link prominently displayed with copy buttons -- correct
- 4 stat cards: Partner Rewards, Referred count, Your Code, Tier -- all immediately useful
- 3-step Getting Started guide is clear and motivating
- Tier progression (Starter 15% / Growth 20% / Elite 25%) explained transparently
- Payout mechanics explained at bottom -- builds trust

#### Referrals
- Currently mirrors Overview -- correct behavior since no referrals exist yet
- Will populate with referred agent list as partners are added -- appropriate empty state
- Missing: ability to email referral code/link directly from the page without opening an external email client

#### Earnings
- Correct structure -- same top stats, more specific earnings breakdown below
- Will populate from Stripe as revenue is generated

#### Payouts
- Shows "No payouts yet" with clear explanation of payout schedule -- correct
- Will show payout history and next scheduled date when Stripe Connect is live

#### Issues
- No ability to email referral link directly from the workspace -- requires external email client
- Ask Jordan/George panel appears in Partner workspace and shows the agent content team (Analyst, Writer, Auditor, Scheduler, Publisher) -- completely wrong context. Partners are not necessarily licensed agents and may never generate content. The Jordan/George panel in Partner context should either be hidden entirely or show partner-specific guidance only (referral tips, not content team introductions).

---

## CROSS-WORKSPACE FINDINGS (PATTERNS ACROSS ALL WORKSPACES)

**1. Jordan/George placement is broken everywhere**
Jordan appears in Identity panels, in the Platform admin workspace, in the Partner workspace showing agent content team members. Jordan belongs on Home screens where it provides daily guidance. Jordan does not belong in settings-like pages, admin panels, or partner dashboards.

**2. Activity data exists in only one workspace**
HB Marketing has an Activity page showing published count, compliance rate, content by niche, platform reach. This data should exist in every workspace. Agents want to see it. Brokers want to see it for their agents. Kevin wants to see it at the platform level. Currently it exists only in HB Marketing.

**3. Authority page URL is buried**
The agent's authority page URL -- the most important public-facing output of the entire platform -- appears only in the Identity panel. It should appear on Home, on Records, and in Identity.

**4. "Profile" vs "Identity" confusion is universal**
Every workspace has both a Profile and an Identity section. The distinction is not clear to users. Agents don't know which one to go to for which settings. The naming must be resolved and the content reorganized so the distinction is obvious.

**5. Schedule is buried in Identity everywhere**
Content Schedule is the most operationally critical setting on the platform -- it is what makes AutoMates run automatically. It is buried inside a page called "Identity" in both Agent and HB Marketing workspaces. It deserves prominent, dedicated placement.

**6. Navigation is inconsistent between workspaces**
Agent: Home, Studio, Records, Identity, Profile
HB Marketing: Identity, Studio, Edit, Records, Activity, Profile
My Office: Overview, Agents, Compliance, Identity
Partner: Overview, Referrals, Earnings, Payouts

Four different nav structures for the same platform. A user switching workspaces has to relearn navigation every time.

**7. The Partner workspace cockpit design is the standard**
The Partner workspace was built with a clear purpose and a defined user. Every other workspace should be rebuilt to match that standard: immediate orientation, clear metrics, guided next action, no dead space.

**8. "Who We Serve" is better than "Primary Niches" everywhere**
In HB Marketing Profile, audience segments are labeled "Who We Serve." In HB Marketing Identity and Agent Identity, the same concept is labeled "Primary Niches." "Who We Serve" is clearer, more human, and more consistent with the platform's voice. It should be used everywhere.

**9. The Edit tab in HB Marketing is a dead nav item**
The Edit / Workspace tab exists in HB Marketing nav, opens a blank page, and provides no functionality. It should be removed until the feature is built.

**10. My Office and My Team are identical and both broken**
Two workspaces built for different audiences (brokers vs team leads) with zero functional distinction and broken navigation in both. Consolidation is the right call unless a specific differentiating feature is identified.

---

## WHAT THIS AUDIT IS ASKING OPUS TO PRODUCE

This audit should not result in individual bug fixes. It should result in a comprehensive Information Architecture specification that answers the following questions before Sonnet writes a single line of code:

1. **What is the correct nav structure for each workspace?** And can a common nav pattern be established so users don't relearn navigation every time they switch?

2. **What goes in Identity vs Profile?** These need to be clearly distinguished or collapsed into one thing. The current overlap is causing confusion at every level.

3. **Where does Schedule live?** It is too important to be buried. Does it get its own nav item? Its own panel on Home?

4. **Where does Activity live?** It should be universal. Does it become a tab in every workspace, or a dedicated section on Home?

5. **Where does Jordan live?** It belongs on Home and only on Home. What does Jordan show in workspaces that don't have a Home (HB Marketing, Partner)?

6. **Should My Office and My Team be consolidated?** If yes, what is the single workspace and what does it contain? If no, what is the genuine functional distinction?

7. **What does the Platform Admin dashboard actually need to show?** System health, KPIs, trend data, alerts. What are the specific metrics and how are they sourced?

8. **What does HB Marketing need to become?** If AutoMates is a registry, HB Marketing is where the registry is managed. What tools does a registry manager need that don't exist today?

9. **What is the Records/Registry page supposed to feel like?** It is the most important page in the product and it currently looks like a task list. What does a professional registry feel like?

10. **What happens to the Demo before launch?** The demo must show the full platform pipeline, not just onboarding, and it must match the current design system. This is a pre-launch blocker for post-Founding-Member acquisition.

---

## PRIORITY CLASSIFICATION

**Must be resolved before June 17 launch:**
- HB Marketing schedule save bug (diagnosed in Session 69 -- Part C niche validation running on wrong setup table)
- Demo mode showing only onboarding -- not consistent with current design or full platform experience

**Must be resolved in first 2 weeks post-launch:**
- Platform Admin dashboard redesign
- Profile dropdown cleanup (remove wrong-context items)
- Jordan placement (remove from wrong contexts)
- Authority page URL visibility (add to Home and Records)
- Edit tab removal from HB Marketing nav
- Activity page added to Agent workspace
- Records page redesign (registry feel, not task list feel)
- My Office / My Team consolidation decision and execution

**Requires Opus IA spec before Sonnet touches:**
- Identity vs Profile restructure
- Schedule placement and prominence
- Full nav consistency across workspaces
- HB Marketing workspace purpose and toolset redesign
- Platform Admin dashboard KPI definition
- Demo mode overhaul

---

*AutoMates Workspace Boundary Audit Report -- Session 69 -- June 11, 2026*
*Conducted by Kevin Lundy + Claude Sonnet 4.6*
*Prepared for Opus strategic IA session*
*No code was written as a result of this audit. All findings are documented for Opus review first.*
