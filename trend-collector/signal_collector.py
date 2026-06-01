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
import urllib.request
from datetime import datetime

COLLECT_INTERVAL_HOURS   = int(os.getenv("SIGNAL_COLLECT_HOURS", "24"))  # Default 24hr — override via Render env var
HIGH_RELEVANCE_THRESHOLD = 0.6  # Minimum score to count as "strong"
MIN_STRONG_SIGNALS       = 2    # Escalate if fewer than this many strong signals found
MAX_SIGNAL_SEARCHES      = int(os.getenv("MAX_SIGNAL_SEARCHES", "3"))    # Max Tier 1 searches per agent per run
RSS_ENABLED              = os.getenv("RSS_ENABLED", "true").lower() == "true"
_collector_started       = False


# ── TIER 0 RSS FEED REGISTRY ─────────────────────────────────────────────────
#
# Three layers:
#   AGENT_NATIONAL_RSS_FEEDS        — always-on for every agent. Consumer-facing
#                                     publications: housing market trackers,
#                                     mortgage/affordability sources, consumer
#                                     real estate portals, federal agencies.
#                                     context='agent'. Surfaces on agent Home panel.
#
#   HB_MARKETING_NATIONAL_RSS_FEEDS — super_admin, admin, hb_marketer roles only.
#                                     Agent and broker publications: industry news,
#                                     association media, CRE publications,
#                                     brokerage/business-development media.
#                                     context='hb_marketing'. Surfaces on HB Marketing panel.
#
#   DUAL_NATIONAL_RSS_FEEDS         — saved to BOTH contexts. Policy, rates, and
#                                     data relevant to both audiences.
#
#   MARKET_RSS_FEEDS                — keyed on agent's market string (case-insensitive
#                                     partial match). Always agent context. Covers
#                                     37 US metros with local business journals,
#                                     indie news, and development-focused sources.
#
# Each feed entry: (label, url, default_signal_type)
# Feeds that 404 or time out are logged and skipped — never break collection.
# Feed list verified by Claude Opus 4.6, Session 58, June 2026.
# Fair Housing note: school ratings and crime/safety feeds excluded by design.
# ─────────────────────────────────────────────────────────────────────────────

# Consumer-facing: housing market data, consumer portals, mortgage/affordability.
AGENT_NATIONAL_RSS_FEEDS = [
    ("Redfin Blog",              "https://www.redfin.com/blog/feed",                                    "market|news"),
    ("BiggerPockets Blog",       "https://www.biggerpockets.com/blog/feed",                             "market|news"),
    ("Norada Real Estate",       "https://www.noradarealestate.com/blog/feed/",                         "market|data"),
    ("The Mortgage Reports",     "https://themortgagereports.com/feed",                                 "market|rates"),
    ("Realty Times",             "https://realtytimes.com/archives?format=feed",                        "market|news"),
    ("Point2 Homes News",        "https://www.point2homes.com/news/feed",                               "market|news"),
    ("WSJ Real Estate",          "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",                       "market|news"),
    ("Bloomberg Real Estate",    "https://feeds.bloomberg.com/markets/news.rss",                        "market|news"),
]

# Agent and broker facing: industry news, association media, CRE publications.
HB_MARKETING_NATIONAL_RSS_FEEDS = [
    ("Inman News",               "https://feeds.feedburner.com/inmannews",                              "market|industry"),
    ("HousingWire",              "https://www.housingwire.com/feed/",                                   "market|industry"),
    ("RISMedia Housecall",       "https://blog.rismedia.com/feed",                                      "market|industry"),
    ("The Close",                "https://theclose.com/feed/",                                          "market|industry"),
    ("NAHB Eye on Housing",      "https://eyeonhousing.org/feed/",                                      "market|data"),
    ("ConnectCRE",               "https://www.connectcre.com/feed/",                                    "market|commercial"),
    ("Commercial Observer",      "https://commercialobserver.com/feed/",                                "market|commercial"),
    ("Propmodo",                 "https://www.propmodo.com/feed/",                                      "market|commercial"),
    ("DS News",                  "https://dsnews.com/feed",                                             "market|industry"),
    ("Working RE",               "https://www.workingre.com/feed/",                                     "market|industry"),
    ("Appraisal Buzz",           "https://www.appraisalbuzz.com/feed/",                                 "market|industry"),
    ("REjournals",               "https://rejournals.com/feed/",                                        "market|commercial"),
    ("Multi-Housing News",       "https://www.multihousingnews.com/feed/",                              "market|commercial"),
]

# Dual-context: policy, rates, and broad market data relevant to both audiences.
DUAL_NATIONAL_RSS_FEEDS = [
    ("Calculated Risk",          "https://www.calculatedriskblog.com/feeds/posts/default?alt=rss",      "market|data"),
    ("GlobeSt",                  "https://www.globest.com/feed/",                                       "market|commercial"),
    ("The Real Deal NY",         "https://therealdeal.com/new-york/feed/",                              "market|development"),
    ("NY YIMBY",                 "https://newyorkyimby.com/feed",                                       "market|development"),
    ("Chicago YIMBY",            "https://chicagoyimby.com/feed",                                       "market|development"),
]

# Market lookup table — keyed on lowercase partial-match strings.
# An agent's market field is lowercased and checked with `in` against each key.
# Multiple keys can match the same market string — all matching feeds are used.
# Format: { "match_string": [(label, url, signal_type), ...] }
# Source strategy per market:
#   1. Business Journal (bizjournals.com) — employers, development, construction, zoning
#   2. Local indie/nonprofit news — deeper zoning, transit, infrastructure, policy
#   3. Development-focused sites — groundbreakings, permits, neighborhood change
# Fair Housing: school ratings and crime/safety feeds excluded by design.
MARKET_RSS_FEEDS = {

    # ── COLORADO ──────────────────────────────────────────────────────────────
    "denver": [
        ("Denver Business Journal",  "https://feeds.bizjournals.com/bizj_denver",                       "market|development"),
        ("Colorado Sun",             "https://coloradosun.com/feed/",                                   "market|policy"),
        ("Denverite",                "https://denverite.com/feed/",                                     "market|development"),
        ("BusinessDen",              "https://businessden.com/feed/",                                   "market|development"),
        ("Mile High CRE",            "https://milehighcre.com/feed/",                                   "market|commercial"),
    ],

    # ── TEXAS ─────────────────────────────────────────────────────────────────
    "austin": [
        ("Austin Business Journal",  "https://feeds.bizjournals.com/bizj_austin",                       "market|development"),
        ("Austin Monitor",           "https://www.austinmonitor.com/feed/",                             "market|policy"),
        ("KUT Austin",               "https://www.kut.org/feed",                                        "market|policy"),
        ("CultureMap Austin",        "https://austin.culturemap.com/feeds/rss/",                        "market|development"),
    ],

    "dallas": [
        ("Dallas Business Journal",  "https://feeds.bizjournals.com/bizj_dallas",                       "market|development"),
        ("D Magazine",               "https://www.dmagazine.com/feed/",                                 "market|development"),
        ("CultureMap Dallas",        "https://dallas.culturemap.com/feeds/rss/",                        "market|development"),
    ],

    "houston": [
        ("Houston Business Journal", "https://feeds.bizjournals.com/bizj_houston",                      "market|development"),
        ("CultureMap Houston",       "https://houston.culturemap.com/feeds/rss/",                       "market|development"),
        ("Houston Public Media",     "https://www.houstonpublicmedia.org/feed/",                        "market|policy"),
    ],

    "san antonio": [
        ("San Antonio Business Journal", "https://feeds.bizjournals.com/bizj_sanantonio",               "market|development"),
        ("San Antonio Report",       "https://sanantonioreport.org/feed/",                              "market|policy"),
    ],

    # ── WEST ──────────────────────────────────────────────────────────────────
    "phoenix": [
        ("Phoenix Business Journal", "https://feeds.bizjournals.com/bizj_phoenix",                      "market|development"),
        ("AZ Big Media",             "https://azbigmedia.com/feed/",                                    "market|development"),
        ("Phoenix New Times",        "https://www.phoenixnewtimes.com/news/rss",                        "market|development"),
    ],

    "las vegas": [
        ("Nevada Independent",       "https://thenevadaindependent.com/feed",                           "market|policy"),
        ("Las Vegas Review-Journal", "https://www.reviewjournal.com/feed/",                             "market|development"),
        ("KLAS Las Vegas",           "https://www.8newsnow.com/feed/",                                  "market|development"),
    ],

    "seattle": [
        ("Puget Sound Business Journal", "https://feeds.bizjournals.com/bizj_pugetsound",               "market|development"),
        ("Seattle Times RE",         "https://www.seattletimes.com/business/real-estate/feed/",         "market|news"),
        ("The Urbanist",             "https://www.theurbanist.org/feed/",                               "market|development"),
        ("Crosscut",                 "https://crosscut.com/feeds/rss.xml",                              "market|policy"),
    ],

    "portland": [
        ("Portland Business Journal", "https://feeds.bizjournals.com/bizj_portland",                    "market|development"),
        ("OregonLive Business",      "https://www.oregonlive.com/business/rss",                         "market|development"),
        ("Willamette Week",          "https://www.wweek.com/feed/",                                     "market|development"),
    ],

    "salt lake": [
        ("Deseret News",             "https://www.deseret.com/feeds/rss",                               "market|development"),
        ("Building Salt Lake",       "https://buildingsaltlake.com/feed/",                              "market|development"),
        ("Salt Lake Tribune",        "https://www.sltrib.com/feed/",                                    "market|policy"),
    ],

    "boise": [
        ("Boise Dev",                "https://boisedev.com/feed/",                                      "market|development"),
        ("Idaho Business Review",    "https://idahobusinessreview.com/feed/",                           "market|development"),
    ],

    "albuquerque": [
        ("Albuquerque Business First", "https://feeds.bizjournals.com/bizj_albuquerque",                "market|development"),
        ("Albuquerque Journal",      "https://www.abqjournal.com/feed",                                 "market|development"),
    ],

    # ── SOUTHEAST ─────────────────────────────────────────────────────────────
    "atlanta": [
        ("Atlanta Business Chronicle", "https://feeds.bizjournals.com/bizj_atlanta",                    "market|development"),
        ("SaportaReport",            "https://saportareport.com/feed/",                                 "market|development"),
        ("What Now Atlanta",         "https://whatnowatlanta.com/feed/",                                 "market|development"),
        ("Rough Draft Atlanta",      "https://roughdraftatlanta.com/feed/",                             "market|development"),
    ],

    "charlotte": [
        ("Charlotte Business Journal", "https://feeds.bizjournals.com/bizj_charlotte",                  "market|development"),
        ("WFAE Charlotte",           "https://www.wfae.org/feed",                                       "market|policy"),
        ("Axios Charlotte",          "https://www.axios.com/local/charlotte/feed",                      "market|development"),
    ],

    "nashville": [
        ("Nashville Business Journal", "https://feeds.bizjournals.com/bizj_nashville",                  "market|development"),
        ("Nashville Scene",          "https://www.nashvillescene.com/news/rss",                         "market|development"),
        ("Axios Nashville",          "https://www.axios.com/local/nashville/feed",                      "market|development"),
    ],

    "tampa": [
        ("Tampa Bay Business Journal", "https://feeds.bizjournals.com/bizj_tampabay",                   "market|development"),
        ("Axios Tampa Bay",          "https://www.axios.com/local/tampa-bay/feed",                      "market|development"),
        ("St Pete Catalyst",         "https://stpetecatalyst.com/feed/",                                "market|development"),
    ],

    "orlando": [
        ("Orlando Business Journal", "https://feeds.bizjournals.com/bizj_orlando",                      "market|development"),
        ("GrowthSpotter",            "https://www.growthspotter.com/feed",                               "market|development"),
        ("Bungalower",               "https://bungalower.com/feed/",                                    "market|development"),
    ],

    "miami": [
        ("South Florida Business Journal", "https://feeds.bizjournals.com/bizj_southflorida",           "market|development"),
        ("The Real Deal Miami",      "https://therealdeal.com/miami/feed/",                             "market|development"),
        ("Next Miami",               "https://www.thenextmiami.com/feed/",                              "market|development"),
    ],

    "jacksonville": [
        ("Jacksonville Business Journal", "https://feeds.bizjournals.com/bizj_jacksonville",            "market|development"),
        ("Jax Daily Record",         "https://www.jaxdailyrecord.com/feed",                             "market|development"),
    ],

    # ── MID-ATLANTIC / NORTHEAST ──────────────────────────────────────────────
    "raleigh": [
        ("Triangle Business Journal", "https://feeds.bizjournals.com/bizj_triangle",                    "market|development"),
        ("Axios Raleigh",            "https://www.axios.com/local/raleigh/feed",                        "market|development"),
    ],

    "richmond": [
        ("Richmond BizSense",        "https://richmondbizsense.com/feed/",                              "market|development"),
    ],

    "washington": [
        ("Washington Business Journal", "https://feeds.bizjournals.com/bizj_washington",                "market|development"),
        ("Greater Greater Washington", "https://ggwash.org/feed",                                       "market|policy"),
        ("DCist",                    "https://dcist.com/feed/",                                         "market|development"),
        ("ARLnow",                   "https://www.arlnow.com/feed/",                                    "market|development"),
    ],

    "baltimore": [
        ("Baltimore Business Journal", "https://feeds.bizjournals.com/bizj_baltimore",                  "market|development"),
        ("Baltimore Brew",           "https://www.baltimorebrew.com/feed/",                             "market|policy"),
        ("Baltimore Fishbowl",       "https://baltimorefishbowl.com/feed/",                             "market|development"),
    ],

    "philadelphia": [
        ("Philadelphia Business Journal", "https://feeds.bizjournals.com/bizj_philadelphia",            "market|development"),
        ("Billy Penn",               "https://billypenn.com/feed/",                                     "market|development"),
        ("PhillyVoice",              "https://www.phillyvoice.com/feed/",                               "market|development"),
    ],

    "boston": [
        ("Boston Business Journal",  "https://feeds.bizjournals.com/bizj_boston",                       "market|development"),
    ],

    "new york": [
        ("The Real Deal NY",         "https://therealdeal.com/new-york/feed/",                          "market|development"),
        ("Commercial Observer",      "https://commercialobserver.com/feed/",                             "market|commercial"),
        ("Gothamist",                "https://gothamist.com/feed",                                      "market|development"),
        ("NY YIMBY",                 "https://newyorkyimby.com/feed",                                   "market|development"),
        ("6sqft",                    "https://www.6sqft.com/feed/",                                     "market|development"),
    ],

    # ── MIDWEST ───────────────────────────────────────────────────────────────
    "chicago": [
        ("Crain's Chicago Business", "https://www.chicagobusiness.com/rss",                             "market|development"),
        ("Chicago YIMBY",            "https://chicagoyimby.com/feed",                                   "market|development"),
        ("Block Club Chicago",       "https://blockclubchicago.org/feed/",                              "market|development"),
    ],

    "minneapolis": [
        ("Minneapolis/St Paul Business Journal", "https://feeds.bizjournals.com/bizj_twincities",       "market|development"),
        ("MinnPost",                 "https://www.minnpost.com/feed/",                                  "market|policy"),
        ("Finance and Commerce",     "https://finance-commerce.com/feed/",                              "market|development"),
    ],

    "kansas city": [
        ("Kansas City Business Journal", "https://feeds.bizjournals.com/bizj_kansascity",               "market|development"),
        ("KCUR",                     "https://www.kcur.org/feed",                                       "market|policy"),
        ("Flatland KC",              "https://flatlandkc.org/feed/",                                    "market|development"),
    ],

    "st louis": [
        ("St Louis Business Journal", "https://feeds.bizjournals.com/bizj_stlouis",                     "market|development"),
        ("NextSTL",                  "https://nextstl.com/feed/",                                       "market|development"),
    ],

    "detroit": [
        ("Crain's Detroit Business", "https://www.crainsdetroit.com/rss",                               "market|development"),
        ("Deadline Detroit",         "https://www.deadlinedetroit.com/rss",                             "market|development"),
    ],

    "columbus": [
        ("Columbus Business First",  "https://feeds.bizjournals.com/bizj_columbus",                     "market|development"),
        ("Columbus Underground",     "https://www.columbusunderground.com/feed",                        "market|development"),
    ],

    "cleveland": [
        ("Crain's Cleveland Business", "https://www.crainscleveland.com/rss",                           "market|development"),
        ("Fresh Water Cleveland",    "https://www.freshwatercleveland.com/feed",                        "market|development"),
    ],

    "cincinnati": [
        ("Cincinnati Business Courier", "https://feeds.bizjournals.com/bizj_cincinnati",                "market|development"),
    ],

    "pittsburgh": [
        ("Pittsburgh Business Times", "https://feeds.bizjournals.com/bizj_pittsburgh",                  "market|development"),
        ("NEXTpittsburgh",           "https://nextpittsburgh.com/feed/",                                "market|development"),
        ("PublicSource",             "https://www.publicsource.org/feed/",                              "market|policy"),
    ],

    # ── SOUTH ─────────────────────────────────────────────────────────────────
    "new orleans": [
        ("New Orleans CityBusiness", "https://neworleanscitybusiness.com/feed/",                        "market|development"),
        ("The Lens NOLA",            "https://thelensnola.org/feed/",                                   "market|policy"),
        ("Axios New Orleans",        "https://www.axios.com/local/new-orleans/feed",                    "market|development"),
    ],

    "memphis": [
        ("Memphis Business Journal", "https://feeds.bizjournals.com/bizj_memphis",                      "market|development"),
        ("Daily Memphian",           "https://dailymemphian.com/feed",                                  "market|development"),
    ],

    "louisville": [
        ("Louisville Business First", "https://feeds.bizjournals.com/bizj_louisville",                  "market|development"),
        ("Insider Louisville",       "https://insiderlouisville.com/feed/",                             "market|development"),
    ],

}



def _get_market_rss_feeds(market: str) -> list:
    """
    Return market-specific RSS feeds for an agent's market string.
    Matches case-insensitively — 'Denver', 'denver', 'DENVER' all match.
    Multiple keys can match (e.g. 'Denver Metro' matches 'denver').
    Returns a deduplicated list of (label, url, signal_type) tuples.
    Falls back to [] for unknown markets — caller adds national feeds.
    """
    if not market:
        return []
    market_lower = market.lower()
    matched = []
    seen_urls = set()
    for key, feeds in MARKET_RSS_FEEDS.items():
        if key in market_lower or market_lower in key:
            for feed in feeds:
                if feed[1] not in seen_urls:
                    matched.append(feed)
                    seen_urls.add(feed[1])
    return matched


def _fetch_rss_signals(market: str, cutoff_dt: datetime, context: str = "agent") -> list:
    """
    Tier 0 — Fetch RSS feeds via rss2json.com API and return signals in the
    same dict shape as Claude signals.

    context='agent'        — pulls AGENT_NATIONAL_RSS_FEEDS + DUAL_NATIONAL_RSS_FEEDS
                             + market-matched MARKET_RSS_FEEDS (consumer-facing).
    context='hb_marketing' — pulls HB_MARKETING_NATIONAL_RSS_FEEDS + DUAL_NATIONAL_RSS_FEEDS
                             only (no market feeds; HB Marketing is national-audience content).

    Uses rss2json.com as a proxy — bypasses publisher-side SSL/403 blocks
    that direct urllib fetches hit on Render. Requires RSS2JSON_API_KEY env var.

    Only returns items published after cutoff_dt (14-day hard limit).
    Never raises — individual feed failures are logged and skipped.
    Returns a list of signal dicts tagged with source_type='rss' and signal_context=context.
    """
    if not RSS_ENABLED:
        return []

    import re as _re
    import urllib.parse

    api_key = os.getenv("RSS2JSON_API_KEY", "")
    if not api_key:
        print("[Signals/RSS] RSS2JSON_API_KEY not set — skipping Tier 0.")
        return []

    # Build the feed list based on context
    if context == "hb_marketing":
        national_list = HB_MARKETING_NATIONAL_RSS_FEEDS + DUAL_NATIONAL_RSS_FEEDS
        market_feeds  = []
    else:
        national_list = AGENT_NATIONAL_RSS_FEEDS + DUAL_NATIONAL_RSS_FEEDS
        market_feeds  = _get_market_rss_feeds(market)

    all_feeds = [(label, url, sig_type, "National") for label, url, sig_type in national_list]
    all_feeds += [(label, url, sig_type, market or "Local") for label, url, sig_type in market_feeds]

    if market_feeds:
        print(f"[Signals/RSS] context={context} market='{market}': {len(national_list)} national + {len(market_feeds)} local feeds.")
    else:
        print(f"[Signals/RSS] context={context} market='{market}': {len(national_list)} national feeds, no local.")

    results = []
    for label, url, sig_type, default_area in all_feeds:
        try:
            # Call rss2json API — returns JSON regardless of source feed format
            api_url = (
                f"https://api.rss2json.com/v1/api.json"
                f"?api_key={api_key}"
                f"&rss_url={urllib.parse.quote(url, safe='')}"
                f"&count=10"
            )
            req = urllib.request.Request(api_url, headers={"User-Agent": "AutoMates/1.0 (signal-collector)"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read())

            # rss2json returns status "ok" on success, "error" on bad feed
            if data.get("status") != "ok":
                msg = data.get("message", "unknown error")
                print(f"[Signals/RSS] Feed skipped — {label}: rss2json status={data.get('status')} — {msg}")
                continue

            items = data.get("items", [])
            feed_count = 0

            for item in items:
                try:
                    # rss2json normalises field names across RSS and Atom
                    headline = (item.get("title") or "").strip()
                    if not headline or len(headline) < 10:
                        continue

                    source_url = (item.get("link") or "").strip()

                    # description is already HTML-stripped by rss2json in most cases;
                    # run a light strip pass to catch any residual tags
                    raw_desc = item.get("description") or item.get("content") or ""
                    summary  = " ".join(_re.sub(r"<[^>]+>", " ", raw_desc).split())[:500]

                    # pubDate from rss2json is normalised to "YYYY-MM-DD HH:MM:SS".
                    # Two edge cases to handle:
                    #   "0000-00-00 00:00:00" — sentinel meaning no date; treat as None
                    #   ""                    — empty; treat as None
                    # Note: do NOT slice pub_raw by len(fmt) — the format string is
                    # shorter than the actual date string and truncates it.
                    pub_raw = (item.get("pubDate") or "").strip()
                    pub_dt  = None
                    if pub_raw and not pub_raw.startswith("0000"):
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                            try:
                                pub_dt = datetime.strptime(pub_raw, fmt)
                                break
                            except Exception:
                                continue

                    if pub_dt is None:
                        pub_date_str = None  # No parseable date — allow through
                    else:
                        if pub_dt < cutoff_dt:
                            continue  # Hard reject — older than 14 days
                        pub_date_str = pub_dt.strftime("%Y-%m-%d")

                    results.append({
                        "area":            default_area,
                        "headline":        headline,
                        "summary":         summary or f"From {label}.",
                        "source_url":      source_url,
                        "published_date":  pub_date_str,
                        "signal_type":     sig_type,
                        "relevance_score": 0.75,  # Curated sources are high-relevance by default
                    })
                    feed_count += 1

                except Exception as item_err:
                    print(f"[Signals/RSS] Item parse error in {label}: {item_err}")
                    continue

            if feed_count:
                print(f"[Signals/RSS] {label}: {feed_count} item(s) within 14 days.")

        except Exception as feed_err:
            print(f"[Signals/RSS] Feed skipped — {label}: {feed_err}")
            continue

    return results


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
        if age_days > 14:
            print(f"[Signals] REJECTED stale signal ({age_days}d old): '{headline[:60]}' (user {user_id})")
            return None, True
        return date_str, False
    except Exception:
        # Unparseable date — allow through without date, don't reject
        print(f"[Signals] Unparseable published_date '{raw_date}' for '{headline[:60]}' (user {user_id}) — saving without date.")
        return None, False


def _save_signals(signals: list, user_id: int, tier: str, areas_str: str,
                  source_type: str = "claude") -> int:
    """Save signals to DB, tagging with tier and source_type. Returns count saved.
    source_type: 'rss' for Tier 0 RSS signals, 'claude' for Tier 1-3 Claude web search.
    Rejects any signal with a published_date older than 14 days.
    Rejects duplicates (same source_url or near-identical headline within 30 days).
    Signals with no date are allowed through with a log warning.
    """
    from database import signals_save, signals_dedupe_check
    saved    = 0
    rejected = 0
    dupes    = 0
    # RSS allows more items per call since feeds are pre-filtered; Claude capped at 5
    cap = 20 if source_type == "rss" else 5
    for sig in signals[:cap]:
        try:
            headline   = str(sig.get("headline", "")).strip()
            source_url = str(sig.get("source_url", "")).strip()
            if not headline or len(headline) < 10:
                continue

            # Validate recency — hard reject if published_date is present and >14 days old
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
                source_type    = source_type,
            )
            saved += 1
        except Exception as e:
            print(f"[Signals] Save error: {e}")
    if rejected:
        print(f"[Signals] {rejected} stale signal(s) rejected (>14 days) for user {user_id}.")
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

    areas_str  = ", ".join(service_areas[:5]) if service_areas else market
    market_str = market or "the local area"
    niche_str  = primary_niches[0] if primary_niches else "Residential Real Estate"
    today_str  = datetime.utcnow().strftime("%B %d, %Y")  # e.g. "April 30, 2026"
    cutoff_str = (datetime.utcnow() - __import__('datetime').timedelta(days=14)).strftime("%B %d, %Y")
    total_saved = 0

    # ── TIER 0: RSS feeds — real-time, no API cost ───────────────────────────
    # Parsed before any Claude web search fires.
    # National feeds run for every agent. Market feeds are matched automatically
    # from the agent's market string — zero agent configuration required.
    # If RSS yields enough strong signals, Claude searches are skipped entirely.
    from datetime import timedelta
    cutoff_dt   = datetime.utcnow() - timedelta(days=14)
    rss_signals = _fetch_rss_signals(market, cutoff_dt)
    strong0     = 0
    if rss_signals:
        saved_rss   = _save_signals(rss_signals, user_id, "rss", market_str, source_type="rss")
        total_saved += saved_rss
        strong0     = sum(1 for s in rss_signals
                         if float(s.get("relevance_score", 0)) >= HIGH_RELEVANCE_THRESHOLD)
        print(f"[Signals] Tier 0 (RSS): {len(rss_signals)} found, {saved_rss} saved, {strong0} strong — user {user_id}")
    else:
        print(f"[Signals] Tier 0 (RSS): no signals returned — user {user_id}")

    if strong0 >= MIN_STRONG_SIGNALS:
        print(f"[Signals] ✓ User {user_id} — {total_saved} saved from Tier 0 (RSS). Skipping Claude searches.")
        return

    # RSS was thin or disabled — proceed to Claude web search tiers
    client = _get_anthropic_client()
    if not client:
        print("[Signals] No Anthropic client — skipping Claude tiers.")
        return

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

Your search MUST find stories published within the last 14 days (after {cutoff_str}).
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
- REColorado, DMAR, or local MLS data releases from the last 14 days
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
