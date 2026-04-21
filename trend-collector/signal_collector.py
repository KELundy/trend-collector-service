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
            max_tokens = 1500,
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


def _save_signals(signals: list, user_id: int, tier: str, areas_str: str) -> int:
    """Save signals to DB, tagging with tier. Returns count saved."""
    from database import signals_save
    saved = 0
    for sig in signals[:5]:
        try:
            headline = str(sig.get("headline", "")).strip()
            if not headline or len(headline) < 10:
                continue
            signals_save(
                user_id        = user_id,
                area           = str(sig.get("area", areas_str))[:200],
                headline       = headline[:500],
                summary        = str(sig.get("summary", ""))[:1000],
                source_url     = str(sig.get("source_url", ""))[:500],
                signal_type    = f"{tier}:{sig.get('signal_type', 'general')}"[:50],
                relevance_score= float(sig.get("relevance_score", 0.5)),
            )
            saved += 1
        except Exception as e:
            print(f"[Signals] Save error: {e}")
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

    areas_str   = ", ".join(service_areas[:5]) if service_areas else market
    market_str  = market or "the local area"
    niche_str   = primary_niches[0] if primary_niches else "Residential Real Estate"
    total_saved = 0

    # ── TIER 1: Hyper-local ──────────────────────────────────────────────────
    # Only run Tier 1 when the agent has specific service areas saved.
    # Without named neighborhoods the hyper-local prompt returns thin results
    # and wastes a Claude call — metro (Tier 2) is the right starting scope.
    if service_areas:
        tier1_prompt = f"""You are a hyper-local real estate market intelligence researcher.

Search the web for recent news and developments in these neighborhoods: {areas_str} in {market_str}.

Look for:
- New development projects, building permits, zoning approvals
- Neighborhood changes, new businesses opening or closing
- Local infrastructure or transit changes
- Recent sales trends or inventory shifts in these areas
- City council or planning commission decisions affecting these neighborhoods

Prioritize signals specific to the named neighborhoods. If a specific neighborhood
has no recent news, include the nearest relevant signal within the surrounding
{market_str} area — clearly noting the actual area in the "area" field.
Recency matters: last 30 days ideal, last 90 days acceptable.

Return ONLY a valid JSON array of up to 5 signals. No explanation, no preamble.
If you truly cannot find anything relevant within 90 days, return an empty array [].
[{{
  "area": "neighborhood or area name",
  "headline": "one specific factual headline",
  "summary": "2-3 sentences on what happened and what it means for buyers/sellers",
  "source_url": "URL if found",
  "signal_type": "development|permit|market|infrastructure|zoning|news",
  "relevance_score": 0.0 to 1.0
}}]

Return ONLY the JSON array."""

        tier1_signals = _search_signals(client, tier1_prompt, user_id)
        strong1       = _strong_signal_count(tier1_signals)
        if tier1_signals:
            total_saved += _save_signals(tier1_signals, user_id, "local", areas_str)
            print(f"[Signals] Tier 1 (local): {len(tier1_signals)} signals, {strong1} strong — user {user_id}")

        if strong1 >= MIN_STRONG_SIGNALS:
            print(f"[Signals] ✓ User {user_id} — {total_saved} saved from Tier 1. Done.")
            return

        print(f"[Signals] Tier 1 thin ({strong1} strong) — escalating to Tier 2 (metro) for user {user_id}")
    else:
        # No service areas configured — fall back to market city at Tier 2 scope
        print(f"[Signals] No service areas set for user {user_id} — starting at Tier 2 (market: {market_str})")

    # ── TIER 2: Metro-level ──────────────────────────────────────────────────

    tier2_prompt = f"""You are a metro-level real estate market intelligence researcher.

The hyper-local search for specific neighborhoods came up thin.
Now search for significant real estate and development news across the broader {market_str} metro area.

Look for:
- Major development projects anywhere in {market_str}
- City-wide zoning or policy changes affecting real estate
- Metro-area market shifts: inventory, pricing, days on market trends
- Large employers moving in or out of {market_str}
- Infrastructure projects (transit, highways, airports) affecting property values

Include signals from any part of {market_str} — not just specific neighborhoods.
Recency: last 60 days preferred.

Return ONLY a valid JSON array of up to 5 signals. No explanation, no preamble.
If you truly cannot find anything relevant, return an empty array [].
[{{
  "area": "{market_str} metro",
  "headline": "one specific factual headline",
  "summary": "2-3 sentences on what happened and what it means for real estate",
  "source_url": "URL if found",
  "signal_type": "development|permit|market|infrastructure|zoning|news|policy",
  "relevance_score": 0.0 to 1.0
}}]

Return ONLY the JSON array."""

    tier2_signals = _search_signals(client, tier2_prompt, user_id)
    strong2       = _strong_signal_count(tier2_signals)
    if tier2_signals:
        total_saved += _save_signals(tier2_signals, user_id, "metro", market_str)
        print(f"[Signals] Tier 2 (metro): {len(tier2_signals)} signals, {strong2} strong — user {user_id}")

    if strong2 >= MIN_STRONG_SIGNALS:
        print(f"[Signals] ✓ User {user_id} — {total_saved} saved through Tier 2. Done.")
        return

    # ── TIER 3: National niche trends ────────────────────────────────────────
    print(f"[Signals] Tier 2 thin ({strong2} strong) — escalating to Tier 3 (national niche) for user {user_id}")

    tier3_prompt = f"""You are a national real estate trend researcher.

The local and metro searches came up thin for {market_str}.
Search for significant NATIONAL real estate trends specifically relevant to: {niche_str}

Look for:
- National policy, regulatory, or legislative changes affecting {niche_str}
- Major national market shifts in this niche (interest rates, inventory, demand)
- Industry reports or data releases relevant to {niche_str} professionals
- NAR, HUD, CFPB, or other regulatory body announcements
- Technology or demographic trends reshaping {niche_str}

These should be trends that a real estate professional in {market_str} specializing
in {niche_str} could write a local-angle post about.

Return ONLY a valid JSON array of up to 5 signals. No explanation, no preamble.
If you truly cannot find anything relevant, return an empty array [].
[{{
  "area": "National — {niche_str}",
  "headline": "one specific factual headline about the national trend",
  "summary": "2-3 sentences on what the trend is and what it means for agents and clients",
  "source_url": "URL if found",
  "signal_type": "policy|market|regulatory|technology|demographic|industry",
  "relevance_score": 0.0 to 1.0
}}]

Return ONLY the JSON array."""

    tier3_signals = _search_signals(client, tier3_prompt, user_id)
    if tier3_signals:
        total_saved += _save_signals(tier3_signals, user_id, "national", niche_str)
        print(f"[Signals] Tier 3 (national): {len(tier3_signals)} signals — user {user_id}")

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
