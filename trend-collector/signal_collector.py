"""
signal_collector.py — HomeBridge Hyper-Local Signal Collector

Runs as a background thread alongside the content scheduler.
Every COLLECT_INTERVAL_HOURS it:
  1. Fetches all active agents with saved service areas
  2. For each agent, searches in three tiers:
     Tier 1 — Hyper-local: specific neighborhoods/service areas
     Tier 2 — Metro: broader city/market level
     Tier 3 — National niche: national trends for agent's primary niche
  3. Escalates automatically if a tier yields fewer than 2 strong signals
  4. Tags each signal with its tier so the frontend can label correctly
  5. Purges expired signals

These signals surface on the agent's Home dashboard and pre-load
into Local Intel generation.
"""

import os
import json
import time
import threading
from datetime import datetime

COLLECT_INTERVAL_HOURS  = int(os.getenv("SIGNAL_COLLECT_HOURS", "24"))  # Default 24hr — override via Render env var
HIGH_RELEVANCE_THRESHOLD = 0.6 # Minimum score to count as "strong"
MIN_STRONG_SIGNALS       = 2   # Escalate if fewer than this many strong signals found
MAX_SIGNAL_SEARCHES      = int(os.getenv("MAX_SIGNAL_SEARCHES", "3"))  # Max Tier 1 searches per agent per run — set in Render env vars
_collector_started       = False


def _get_anthropic_client():
    try:
        from anthropic import Anthropic
    except ImportError:
        return None
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return Anthropic(api_key=api_key)


def signal_collector_worker():
    """Background thread — collects signals for all active agents."""
    print("[Signals] Collector started.")
    while True:
        try:
            _collect_all_agent_signals()
        except Exception as e:
            print(f"[Signals] Worker error: {e}")
        time.sleep(COLLECT_INTERVAL_HOURS * 3600)


def _collect_all_agent_signals():
    """Fetch all active agents with service areas and collect signals for each."""
    from database import get_conn, signals_purge_expired

    try:
        signals_purge_expired()
    except Exception as e:
        print(f"[Signals] Purge error: {e}")

    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT u.id, u.agent_name, a.setup_json
        FROM users u
        JOIN agent_setup a ON a.user_id = u.id
        WHERE u.is_active = 1
          AND u.role IN ('agent', 'admin', 'super_admin')
    """)
    rows = c.fetchall()
    conn.close()

    for row in rows:
        try:
            setup         = json.loads(row["setup_json"] or "{}")
            service_areas = setup.get("serviceAreas", [])
            market        = setup.get("market", "")
            primary_niches= setup.get("primaryNiches", [])
            if not service_areas and not market:
                continue
            _collect_signals_for_agent(
                user_id       = row["id"],
                agent_name    = row["agent_name"] or "Agent",
                service_areas = service_areas,
                market        = market,
                primary_niches= primary_niches,
            )
        except Exception as e:
            print(f"[Signals] Error for user {row['id']}: {e}")


def _search_signals(client, prompt: str, user_id: int) -> list:
    """
    Execute a single Claude web search call and return parsed signals list.
    Returns [] on any failure — caller decides what to do.
    """
    try:
        response = client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 2500,
            tools      = [{"type": "web_search_20250305", "name": "web_search"}],
            messages   = [{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"[Signals] Claude call failed for user {user_id}: {e}")
        return []

    raw_text = ""
    for block in (response.content or []):
        if getattr(block, "type", "") == "text":
            raw_text += block.text

    if not raw_text.strip():
        print(f"[Signals] Empty response from Claude for user {user_id} — skipping tier.")
        return []

    try:
        clean = raw_text.strip()

        # Strip markdown code fences if present
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        # If the response doesn't look like a JSON array, Claude returned
        # conversational text (e.g. "I couldn't find anything specific").
        # Log it cleanly and return [] — do not attempt to parse.
        if not clean.startswith("["):
            print(f"[Signals] Non-JSON response from Claude for user {user_id} — escalating tier.")
            return []

        signals = json.loads(clean)
        if not isinstance(signals, list):
            print(f"[Signals] Unexpected JSON structure for user {user_id} — expected list, got {type(signals).__name__}.")
            return []
        return signals

    except Exception as e:
        print(f"[Signals] JSON parse error for user {user_id}: {e}")
        return []


def _validate_published_date(raw_date: str, user_id: int, headline: str) -> tuple:
    """
    Validate a published_date string from Claude.
    Returns (date_str_or_None, should_reject).
    should_reject=True means the signal is too old and must not be saved.
    """
    if not raw_date or not str(raw_date).strip():
        # No date provided — allow through with a warning, log it
        print(f"[Signals] No published_date for signal '{headline[:60]}' (user {user_id}) — saving without date.")
        return None, False

    try:
        from datetime import timedelta
        date_str = str(raw_date).strip()[:10]  # Take YYYY-MM-DD portion only
        parsed   = datetime.strptime(date_str, "%Y-%m-%d")
        age_days = (datetime.utcnow() - parsed).days
        if age_days > 45:
            print(f"[Signals] REJECTED stale signal ({age_days}d old): '{headline[:60]}' (user {user_id})")
            return None, True
        return date_str, False
    except Exception:
        # Unparseable date — allow through without date, don't reject
        print(f"[Signals] Unparseable published_date '{raw_date}' for '{headline[:60]}' (user {user_id}) — saving without date.")
        return None, False


def _save_signals(signals: list, user_id: int, tier: str, areas_str: str) -> int:
    """Save signals to DB, tagging with tier. Returns count saved.
    Rejects any signal with a published_date older than 45 days.
    Rejects duplicates (same source_url or near-identical headline within 30 days).
    Signals with no date are allowed through with a log warning.
    """
    from database import signals_save, signals_dedupe_check
    saved    = 0
    rejected = 0
    dupes    = 0
    for sig in signals[:5]:
        try:
            headline   = str(sig.get("headline", "")).strip()
            source_url = str(sig.get("source_url", "")).strip()
            if not headline or len(headline) < 10:
                continue

            # Validate recency — hard reject if published_date is present and >45 days old
            pub_date, should_reject = _validate_published_date(
                sig.get("published_date", ""), user_id, headline
            )
            if should_reject:
                rejected += 1
                continue

            # Deduplicate — skip if same URL or near-identical headline already saved recently
            if signals_dedupe_check(user_id, source_url, headline):
                dupes += 1
                print(f"[Signals] DUPE skipped: '{headline[:60]}' (user {user_id})")
                continue

            signals_save(
                user_id        = user_id,
                area           = str(sig.get("area", areas_str))[:200],
                headline       = headline[:500],
                summary        = str(sig.get("summary", ""))[:1000],
                source_url     = source_url[:500],
                signal_type    = f"{tier}:{sig.get('signal_type', 'general')}"[:50],
                relevance_score= float(sig.get("relevance_score", 0.5)),
                published_date = pub_date,
            )
            saved += 1
        except Exception as e:
            print(f"[Signals] Save error: {e}")
    if rejected:
        print(f"[Signals] {rejected} stale signal(s) rejected (>45 days) for user {user_id}.")
    if dupes:
        print(f"[Signals] {dupes} duplicate signal(s) skipped for user {user_id}.")
    return saved


def _strong_signal_count(signals: list) -> int:
    """Count signals above the high-relevance threshold."""
    return sum(1 for s in signals
               if float(s.get("relevance_score", 0)) >= HIGH_RELEVANCE_THRESHOLD)


def _collect_signals_for_agent(user_id: int, agent_name: str,
                                service_areas: list, market: str,
                                primary_niches: list = None,
                                force: bool = False):
    """
    Three-tier signal collection for a single agent.
    force=True bypasses the freshness check — used by manual trigger endpoint.
    """
    from database import get_conn

    # Skip if we already have fresh signals — unless forced
    if not force:
        conn = get_conn()
        c    = conn.cursor()
        c.execute("""
            SELECT COUNT(*) as n FROM local_signals
            WHERE user_id = ?
              AND collected_at > datetime('now', '-23 hours')
        """, (user_id,))
        recent_count = c.fetchone()["n"]
        conn.close()
        if recent_count >= 3:
            print(f"[Signals] User {user_id} has fresh signals — skipping.")
            return
    else:
        print(f"[Signals] Force collection triggered for user {user_id} — bypassing freshness check.")

    client = _get_anthropic_client()
    if not client:
        print("[Signals] No Anthropic client — skipping.")
        return

    areas_str  = ", ".join(service_areas[:5]) if service_areas else market
    market_str = market or "the local area"
    niche_str  = primary_niches[0] if primary_niches else "Residential Real Estate"
    today_str  = datetime.utcnow().strftime("%B %d, %Y")  # e.g. "April 30, 2026"
    cutoff_str = (datetime.utcnow() - __import__('datetime').timedelta(days=45)).strftime("%B %d, %Y")
    total_saved = 0

    # Signal search angles — rotated across individual area searches so
    # The Analyst doesn't keep finding the same dominant articles each run.
    # Each area gets one angle, cycling through the list.
    SEARCH_ANGLES = [
        ("new development projects, building permits, zoning approvals, groundbreakings",        "development|permit|zoning"),
        ("home sales data, inventory levels, days on market, price trends, market statistics",   "market"),
        ("new businesses opening, major employers moving in or out, job announcements",          "news|employer"),
        ("city council decisions, planning commission approvals, infrastructure or transit news", "infrastructure|zoning|policy"),
        ("neighborhood changes, school district news, community development, park improvements", "news|community"),
    ]

    # ── TIER 1: Hyper-local — one search per service area ───────────────────
    # Searching areas individually prevents one dominant area (e.g. DTC) from
    # consuming all 5 signal slots and burying quieter neighborhoods.
    # MAX_SIGNAL_SEARCHES caps total Tier 1 calls per agent per run — set via
    # Render env var MAX_SIGNAL_SEARCHES (default 3). Reduces API spend at scale.
    if service_areas:
        strong1 = 0
        areas_to_search = service_areas[:MAX_SIGNAL_SEARCHES]
        print(f"[Signals] Tier 1: searching {len(areas_to_search)} of {len(service_areas)} area(s) (MAX_SIGNAL_SEARCHES={MAX_SIGNAL_SEARCHES}) — user {user_id}")
        for idx, area in enumerate(areas_to_search):
            angle_desc, angle_types = SEARCH_ANGLES[idx % len(SEARCH_ANGLES)]
            tier1_prompt = f"""You are a hyper-local real estate market intelligence researcher.
Today's date is {today_str}. Only return news published on or after {cutoff_str}.

Search the web for very recent news specifically about: {area} in {market_str}.

Focus your search on: {angle_desc}

Your search MUST find stories published within the last 45 days (after {cutoff_str}).
Do not return articles from before {cutoff_str} under any circumstances.
If you cannot find anything published after {cutoff_str} specifically about {area},
return an empty array [] — do not fall back to older stories.

Return ONLY a valid JSON array of up to 2 signals. No explanation, no preamble.
[{{
  "area": "{area}",
  "headline": "one specific factual headline — must be from a real published article",
  "summary": "2-3 sentences: what happened and what it means for buyers/sellers in {area}",
  "source_url": "URL of the article — required if found",
  "published_date": "YYYY-MM-DD — the date the article was published",
  "signal_type": "{angle_types}",
  "relevance_score": 0.0 to 1.0
}}]

Return ONLY the JSON array. If nothing found after {cutoff_str}, return []."""

            area_signals = _search_signals(client, tier1_prompt, user_id)
            if area_signals:
                saved = _save_signals(area_signals, user_id, "local", area)
                total_saved += saved
                strong1 += _strong_signal_count(area_signals)
                print(f"[Signals] Tier 1 ({area}): {len(area_signals)} signals, {saved} saved — user {user_id}")
            else:
                print(f"[Signals] Tier 1 ({area}): no recent signals found — user {user_id}")

        if strong1 >= MIN_STRONG_SIGNALS:
            print(f"[Signals] ✓ User {user_id} — {total_saved} saved from Tier 1. Done.")
            return

        print(f"[Signals] Tier 1 thin ({strong1} strong) — escalating to Tier 2 (metro) for user {user_id}")
    else:
        print(f"[Signals] No service areas set for user {user_id} — starting at Tier 2 (market: {market_str})")

    # ── TIER 2: Metro-level ──────────────────────────────────────────────────
    # Runs two targeted searches — market data and development/policy —
    # so we get variety instead of one dominant story type.

    tier2_prompts = [
        f"""You are a metro-level real estate market intelligence researcher.
Today's date is {today_str}. Only return news published on or after {cutoff_str}.

Search the web for very recent {market_str} metro real estate MARKET DATA:
- New MLS reports, inventory statistics, median price changes
- Days on market trends, absorption rates, list-to-sale ratios
- REColorado, DMAR, or local MLS data releases from the last 45 days
- Mortgage rate impacts on the {market_str} market specifically

Only include data or reports published after {cutoff_str}.
If nothing found after {cutoff_str}, return [].

Return ONLY a valid JSON array of up to 3 signals. No explanation, no preamble.
[{{
  "area": "{market_str} metro",
  "headline": "one specific factual headline with actual numbers if available",
  "summary": "2-3 sentences on the data and what it means for buyers/sellers",
  "source_url": "URL if found",
  "published_date": "YYYY-MM-DD",
  "signal_type": "market",
  "relevance_score": 0.0 to 1.0
}}]

Return ONLY the JSON array.""",

        f"""You are a metro-level real estate development researcher.
Today's date is {today_str}. Only return news published on or after {cutoff_str}.

Search the web for very recent {market_str} metro development and policy news:
- Major projects approved, breaking ground, or completing in {market_str}
- City of Denver or surrounding city zoning or policy changes
- Large employer announcements, office expansions, relocations in {market_str}
- RTD, highway, or infrastructure projects affecting property values

Only include stories published after {cutoff_str}.
If nothing found after {cutoff_str}, return [].

Return ONLY a valid JSON array of up to 3 signals. No explanation, no preamble.
[{{
  "area": "{market_str} area",
  "headline": "one specific factual headline",
  "summary": "2-3 sentences on what happened and what it means for real estate",
  "source_url": "URL if found",
  "published_date": "YYYY-MM-DD",
  "signal_type": "development|infrastructure|policy|news",
  "relevance_score": 0.0 to 1.0
}}]

Return ONLY the JSON array.""",
    ]

    strong2 = 0
    for t2_prompt in tier2_prompts:
        t2_signals = _search_signals(client, t2_prompt, user_id)
        if t2_signals:
            saved = _save_signals(t2_signals, user_id, "metro", market_str)
            total_saved += saved
            strong2 += _strong_signal_count(t2_signals)
            print(f"[Signals] Tier 2 (metro): {len(t2_signals)} signals, {saved} saved — user {user_id}")

    if strong2 >= MIN_STRONG_SIGNALS:
        print(f"[Signals] ✓ User {user_id} — {total_saved} saved through Tier 2. Done.")
        return

    # ── TIER 3: National niche trends ────────────────────────────────────────
    print(f"[Signals] Tier 2 thin ({strong2} strong) — escalating to Tier 3 (national niche) for user {user_id}")

    tier3_prompt = f"""You are a national real estate trend researcher.
Today's date is {today_str}. Only return news published on or after {cutoff_str}.

Search for significant NATIONAL real estate news and trends relevant to: {niche_str}

Look for stories published after {cutoff_str} about:
- NAR, HUD, CFPB, or federal housing policy announcements
- Interest rate decisions and their impact on {niche_str}
- National inventory or affordability data releases
- Demographic or technology trends reshaping {niche_str}
- Industry reports from Zillow, Redfin, CoreLogic, ATTOM, or similar

These should be trends a {market_str} agent specializing in {niche_str}
could write a compelling local-angle post about.

Only include stories published after {cutoff_str}. If nothing found, return [].

Return ONLY a valid JSON array of up to 5 signals. No explanation, no preamble.
[{{
  "area": "National — {niche_str}",
  "headline": "one specific factual headline",
  "summary": "2-3 sentences: the trend and what it means for agents and clients in {market_str}",
  "source_url": "URL if found",
  "published_date": "YYYY-MM-DD",
  "signal_type": "policy|market|regulatory|technology|demographic|industry",
  "relevance_score": 0.0 to 1.0
}}]

Return ONLY the JSON array."""

    tier3_signals = _search_signals(client, tier3_prompt, user_id)
    if tier3_signals:
        saved = _save_signals(tier3_signals, user_id, "national", niche_str)
        total_saved += saved
        print(f"[Signals] Tier 3 (national): {len(tier3_signals)} signals, {saved} saved — user {user_id}")

    print(f"[Signals] ✓ User {user_id} ({agent_name}) — {total_saved} total signal(s) saved across all tiers.")


def start_signal_collector():
    """
    Start the signal collector background thread.
    Safe to call multiple times — only starts once.
    """
    global _collector_started
    if _collector_started:
        return
    _collector_started = True
    t = threading.Thread(target=signal_collector_worker, daemon=True)
    t.start()
    print("[Signals] Signal collector thread started.")
