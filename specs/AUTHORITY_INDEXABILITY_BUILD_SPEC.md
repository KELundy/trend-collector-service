# AUTOMATES -- AUTHORITY PAGE INDEXABILITY BUILD SPECIFICATION
## The Publishing Layer: Server-Side Rendering for AI and Search Visibility
**Prepared by:** Claude Opus 4.8 -- June 8, 2026
**For:** Kevin Lundy / HomeBridge Group, LLC
**Build executor:** Sonnet (against this spec, one file at a time, no improvisation)
**Status:** CRITICAL. This is the missing half of the core value proposition. Until this is built and verified, AutoMates authority pages are invisible to search engines and AI systems.

---

## 0. WHY THIS DOCUMENT EXISTS

The diagnosis is confirmed. A `site:kevin-lundy-denver.homebridgegroup.co` query returns 2 results despite 106 CPR records existing. View Source on the authority page shows empty container divs and JavaScript, not content. The records exist in the database and render correctly for human visitors, but the page is client-side rendered: the server sends an empty shell, and JavaScript fetches and draws the content after load. Search and AI crawlers do not reliably execute that JavaScript, so they see nothing.

**This is the single root cause of the visibility problem.** The product's promise -- making an agent citable by AI and search -- depends entirely on fixing it.

The fix: serve the authority pages and per-record pages as fully-rendered HTML from the Render backend, where the data already lives, with all content present in the page source at the moment the server responds. Then make those pages discoverable (sitemap, schema, robots) and submit them to the systems that index and cite (Google Search Console, Google Business Profile).

This document is the complete build plan. It is structured so that the Session 59 failure mode -- acting on hosting/routing assumptions before mapping reality -- cannot recur. Phase 1 changes nothing. It only maps. No file is touched and no DNS record is changed until the map is confirmed.

---

## 1. ARCHITECTURE DECISION (LOCKED)

Authority pages and per-record CPR pages move to server-side rendering on the Render backend (FastAPI, api/app on Render). Bluehost retains the marketing site only.

Rationale:
- The Render backend already holds every record in SQLite. It can assemble complete HTML before responding.
- Bluehost is a static Apache host. It cannot render dynamic content server-side. It is the cause of the current invisibility.
- This aligns with Kevin's standing intent (stated repeatedly since Session 59) to move everything except the marketing site off Bluehost.

What stays on Bluehost: the marketing site at the apex domain (homebridgegroup.co) only.
What moves to Render: agent authority pages (slug subdomains), per-record CPR pages, verify pages, sitemap, robots.

---

## 2. PHASE 1 -- DISCOVERY AND MAPPING (NO CHANGES)

Sonnet performs all of the following and reports findings to Kevin BEFORE writing or changing anything. This phase resolves every current unknown. No code is written, no route is changed, no DNS record is touched in Phase 1.

### 2.1 DNS reality map
In Cloudflare DNS for homebridgegroup.co, record the exact current state of:
- The apex record (homebridgegroup.co) -- type, target, proxy status
- The wildcard record (*.homebridgegroup.co) -- type, target, proxy status
- app.homebridgegroup.co
- api.homebridgegroup.co
- Any explicit agent-slug records

Produce a table: hostname, record type, target, proxied yes/no. This is the ground truth that the ADD documents have gotten wrong twice. Trust only what is live in Cloudflare.

### 2.2 What actually serves the authority subdomain
Determine, with certainty, what server responds to kevin-lundy-denver.homebridgegroup.co right now. Method: check which target the wildcard resolves to, and confirm whether agent.html is physically present and served from Bluehost or from Render.

### 2.3 Dormant file check
Locate the "outdated agent.html on Render" Kevin referenced. Determine whether any route or static mount on Render currently serves it. Confirm it is dormant (referenced by nothing) or identify what references it. This prevents a routing collision when the subdomain is pointed at Render.

### 2.4 Current per-record URL behavior
The CPR record ID (format CIR-YYYYMMDD-XXXXXX) renders on the authority page. Determine:
- Does each record currently have its own URL? If so, what is the pattern?
- Does that URL currently resolve to anything, and is it client-side or server-rendered?
- Where is verify.html in this flow, and what does it currently serve?

### 2.5 Data access path
Confirm the exact backend function and database query that returns an agent's records and profile (the data the current JavaScript fetches). The server-rendering build will call this same data layer directly. Identify the function name in app.py / database.py.

### 2.6 What else lives on the wildcard
Critical for the DNS cutover. Identify every hostname currently depending on the wildcard routing to its present target, so that moving the wildcard does not silently break compliance-check.html, app, api, or anything else. If app and api have their own explicit CNAME records (per ADD they do), they are safe. Confirm this.

**Phase 1 deliverable:** a short written map covering 2.1 through 2.6, delivered to Kevin for confirmation. Build does not proceed until Kevin confirms the map.

---

## 3. PHASE 2 -- SERVER-SIDE RENDERING BUILD (RENDER BACKEND)

Built in deploy order. One file at a time. Health check after each deploy at https://api.homebridgegroup.co/health. Whole files only, read completely before editing.

### 3.1 Authority page render endpoint
A backend route that, given an agent slug, returns a complete HTML document with all content baked into the source:
- Agent name, bio, niches, markets, designations
- All CPR records as real, visible HTML text (the post content, not a placeholder)
- The CPR explanation block (Certified Provenance Record language, per locked naming)
- Record count, publishing-since date, consistency indicator
- FAQ content fully rendered (not collapsed-and-JS-loaded; the answer text must be in source even if visually collapsed)
- All existing visual design preserved -- this is the same page, rendered server-side instead of client-side

The route reads directly from the data layer identified in Phase 1 (2.5). No client-side fetch for primary content.

Requirement: every piece of text a crawler should see must be present in the raw HTML response. Verify with View Source before considering the file done.

### 3.2 Per-record CPR page render endpoint
A backend route that, given a CPR record ID (CIR-YYYYMMDD-XXXXXX pattern, retained as internal ID), returns a complete standalone HTML page for that single record:
- The full post content
- The CPR provenance statement (who reviewed, when, license context, what was checked)
- Certified Provenance Record naming throughout
- Link back to the agent's authority page
- Its own schema markup (see 3.4)

Each record becomes an individually crawlable, individually citable URL. This multiplies the agent's indexable surface from 1 page to 100+ pages, each a discrete piece of evidence an AI system can cite.

### 3.3 Internal linking
- Authority page links to every per-record page
- Every per-record page links back to the authority page
- This gives crawlers a complete, followable path through all content from a single entry point

### 3.4 Server-side schema (JSON-LD)
Rendered into the HTML source server-side, not injected by JavaScript:
- Authority page: RealEstateAgent / Person schema with name, area served, knowsAbout (niches), and the set of records as associated items
- Per-record page: schema expressing the provenance record. Use CreativeWork or Article with author, datePublished, and a publisher/reviewer assertion that maps to the "licensed professional reviewed this" claim. Where possible, structure it to be legible to systems that understand content provenance (C2PA-aligned vocabulary in the future; standard schema.org now).
- All schema must validate against Google's Rich Results Test.

### 3.5 Naming compliance
All user-facing and crawler-facing text uses Certified Provenance Record / CPR. First mention per page: Certified Provenance Record (CPR). Internal record IDs retain the cir- prefix unchanged. No "CIR", "Compliance Intelligence Record", or "Certified Identity Record" in any rendered text.

---

## 4. PHASE 3 -- DISCOVERABILITY

### 4.1 sitemap.xml
A backend-generated sitemap, served from the agent domain, listing:
- Each agent authority page
- Every per-record CPR page
- Regenerated automatically as new records are created (generated from the database on request, not hand-maintained)

### 4.2 robots.txt
Served from the agent domain. Explicitly allows crawling of authority and record pages. Points to the sitemap. Confirm nothing in the current setup is accidentally disallowing crawlers.

### 4.3 Meta and canonical tags
Each page: title, meta description, canonical URL, Open Graph tags, all rendered server-side. Per-record pages get descriptive titles drawn from the post content, not generic boilerplate.

---

## 5. PHASE 4 -- DNS CUTOVER (THE SESSION 59 TRIPWIRE -- HANDLED DELIBERATELY)

Performed only after Phases 2 and 3 are built, deployed, and confirmed working when accessed directly via the Render URL. The pages must be proven complete in source BEFORE the domain points at them.

### 5.1 Pre-cutover verification
Access the new server-rendered authority page and a per-record page directly via their Render URLs (not the public domain). View Source on each. Confirm all content is present in the raw HTML. Do not proceed until this passes.

### 5.2 The routing change
Based on the Phase 1 DNS map, change the wildcard (or the specific agent-slug routing) in Cloudflare to point authority/record traffic to Render instead of Bluehost. Exact records to change will be specified from the Phase 1 map, not guessed here.

Guardrails:
- The apex (homebridgegroup.co, marketing site) must remain on Bluehost. Confirm the apex record is untouched.
- app and api explicit CNAMEs to Render must remain untouched.
- compliance-check.html: if it depends on the wildcard to Bluehost, it must be relocated or given an explicit record BEFORE the wildcard changes, so it does not break. This is identified in Phase 1 (2.6) and resolved before cutover.
- Cloudflare caches aggressively. Purge cache after the change.

### 5.3 Post-cutover verification
- Load the public authority page. Confirm it renders for humans (unchanged experience).
- View Source on the public URL. Confirm content is in the source.
- Confirm the marketing site at the apex still loads.
- Confirm app and api still function (health check).

---

## 6. PHASE 5 -- SUBMISSION AND THE PROOF (KEVIN, NO CODE, NO MONEY)

These steps are what convert "indexable" into "indexed and cited." Only Kevin can do them. Exact click-by-click guidance provided when reached.

### 6.1 Google Search Console
- Verify the homebridgegroup.co domain
- Submit sitemap.xml
- Request indexing on the authority page and several record pages

### 6.2 Google Business Profile
- Create/claim the profile. This is the single highest-leverage local visibility action and a major input to how AI systems answer "best agent in [city]" queries. Free.

### 6.3 Inbound links (foundation for citation)
- Link to the authority page from: the eXp agent profile, TheHomeBridgeGroup.com, any directory listings, any press. These are the trusted-source signals that move a page from merely indexed to actually cited.

### 6.4 THE VERIFICATION CHECKPOINT
Wait several days after submission, then re-run `site:kevin-lundy-denver.homebridgegroup.co`. The number must climb from 2 toward 100+. This is the proof. The build is not "done" on deploy. It is done when the index count climbs. If it does not climb within a reasonable window, we diagnose why before declaring victory or moving to launch.

---

## 7. WHAT THIS DOES AND DOES NOT PROMISE

Does: makes every CPR record a real, crawlable, citable page; gets the content into search indexes; builds the structural foundation AI systems require before they will cite an agent; gets AutoMates off Bluehost for everything but marketing.

Does NOT: instantly make an agent the top AI recommendation. Indexing is necessary but not sufficient. Citation also requires authority signals (links, reviews, Business Profile, time). The honest product claim, until proven otherwise by the verification checkpoint and real-world results, is that AutoMates builds the verifiable, structured, machine-readable foundation AI systems require -- not that it guarantees the top recommendation. Marketing copy must match this until results prove a stronger claim.

---

## 8. BUILD ORDER SUMMARY

1. Phase 1: Discovery map. No changes. Kevin confirms.
2. Phase 2: Server-side render endpoints (authority, per-record), internal linking, schema. Deploy and verify each via Render URL.
3. Phase 3: sitemap, robots, meta. Deploy and verify.
4. Phase 4: DNS cutover, only after source is proven complete. Guardrails enforced.
5. Phase 5: Search Console, Business Profile, links. Then the verification checkpoint.

Nothing is "done" until Section 6.4 shows the index count climbing.

---

*AutoMates Authority Page Indexability Build Specification -- June 8, 2026 -- Confidential -- HomeBridge Group, LLC*
*Prepared by Claude Opus 4.8. This is the missing publishing layer. It is the prerequisite to any honest launch.*
