"""
signal_collector.py — HomeBridge Hyper-Local Signal Collector

Runs as a background thread alongside the content scheduler.
Every COLLECT_INTERVAL_HOURS it:
  1. Fetches all active agents with saved service areas
  2. For each agent, calls Claude with web_search to find local signals
     (permits, planning approvals, neighborhood news, market shifts)
  3. Scores relevance and stores in local_signals table
  4. Purges expired signals

These signals surface on the agent's Home dashboard as "What's happening
in your market" and pre-load into Local Intel generation.
"""

import os
import json
import time
import threading
from datetime import datetime

COLLECT_INTERVAL_HOURS = 6  # Run every 6 hours
_collector_started     = False


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

    # Purge expired signals first
    try:
        signals_purge_expired()
    except Exception as e:
        print(f"[Signals] Purge error: {e}")

    conn = get_conn()
    c    = conn.cursor()
    # Get all active agents who have setup data (service areas)
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
            setup = json.loads(row["setup_json"] or "{}")
            service_areas = setup.get("serviceAreas", [])
            market        = setup.get("market", "")
            if not service_areas and not market:
                continue
            _collect_signals_for_agent(
                user_id      = row["id"],
                agent_name   = row["agent_name"] or "Agent",
                service_areas= service_areas,
                market       = market,
            )
        except Exception as e:
            print(f"[Signals] Error for user {row['id']}: {e}")


def _collect_signals_for_agent(user_id: int, agent_name: str,
                                service_areas: list, market: str):
    """
    Call Claude with web search to find hyper-local signals for this agent.
    Stores up to 5 signals per run. Skips if fresh signals exist from last 4 hours.
    """
    from database import get_conn, signals_save, signals_get_latest

    # Skip if we already have fresh signals collected in the last 4 hours
    conn = get_conn()
    c    = conn.cursor()
    four_hours_ago = datetime.utcnow().isoformat()[:13]  # Truncate to hour
    c.execute("""
        SELECT COUNT(*) as n FROM local_signals
        WHERE user_id = ?
          AND collected_at > datetime('now', '-4 hours')
    """, (user_id,))
    recent_count = c.fetchone()["n"]
    conn.close()
    if recent_count >= 3:
        print(f"[Signals] User {user_id} has fresh signals — skipping.")
        return

    client = _get_anthropic_client()
    if not client:
        print("[Signals] No Anthropic client — skipping signal collection.")
        return

    # Build search areas string
    areas_str = ", ".join(service_areas[:5]) if service_areas else market
    market_str = market or "the local area"

    search_prompt = f"""You are a hyper-local real estate market intelligence researcher.

Search the web for recent news, developments, and market signals specifically relevant to these neighborhoods/areas: {areas_str} in {market_str}.

Look for:
- New development projects, building permits, zoning approvals
- Neighborhood changes, new businesses opening or closing
- Local infrastructure projects, road work, transit changes
- Recent sales trends or inventory shifts specific to these areas
- City council or planning commission decisions affecting these neighborhoods
- Any news that would directly impact property values or buyer/seller decisions

For each signal you find, assess:
1. Is it specific to the named neighborhoods (not just the whole city)?
2. Is it recent (last 30 days preferred, last 90 days acceptable)?
3. Does it have a direct impact on real estate decisions?

Return ONLY a valid JSON array of up to 5 signals. Each signal:
{{
  "area": "specific neighborhood or zip code name",
  "headline": "one specific, factual headline about what's happening",
  "summary": "2-3 sentences: what's happening, when, and what it means for buyers/sellers",
  "source_url": "URL of the source article or permit record if found",
  "signal_type": "development|permit|market|infrastructure|zoning|news",
  "relevance_score": 0.0 to 1.0
}}

If you find fewer than 5 strong signals, return fewer. Quality over quantity.
Return ONLY the JSON array. No preamble."""

    try:
        response = client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 1500,
            tools      = [{"type": "web_search_20250305", "name": "web_search"}],
            messages   = [{"role": "user", "content": search_prompt}],
        )
    except Exception as e:
        print(f"[Signals] Claude call failed for user {user_id}: {e}")
        return

    # Extract JSON from response
    raw_text = ""
    for block in (response.content or []):
        if getattr(block, "type", "") == "text":
            raw_text += block.text

    if not raw_text.strip():
        print(f"[Signals] Empty response for user {user_id}")
        return

    try:
        # Strip markdown fences if present
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        signals = json.loads(clean.strip())
        if not isinstance(signals, list):
            raise ValueError("Expected JSON array")
    except Exception as e:
        print(f"[Signals] JSON parse error for user {user_id}: {e}")
        return

    saved = 0
    for sig in signals[:5]:
        try:
            signals_save(
                user_id        = user_id,
                area           = str(sig.get("area", areas_str))[:200],
                headline       = str(sig.get("headline", ""))[:500],
                summary        = str(sig.get("summary", ""))[:1000],
                source_url     = str(sig.get("source_url", ""))[:500],
                signal_type    = str(sig.get("signal_type", "general"))[:50],
                relevance_score= float(sig.get("relevance_score", 0.5)),
            )
            saved += 1
        except Exception as e:
            print(f"[Signals] Save error: {e}")

    print(f"[Signals] ✓ Saved {saved} signal(s) for user {user_id} ({agent_name}) — areas: {areas_str}")


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
