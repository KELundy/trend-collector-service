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
# Two layers:
#   NATIONAL_RSS_FEEDS  — always-on for every agent, regardless of market.
#                         Industry publications, federal agencies, national
#                         real estate data sources.
#   MARKET_RSS_FEEDS    — keyed on the agent's market string (case-insensitive,
#                         partial match). Activated automatically when an agent's
#                         market field matches. No agent configuration required.
#                         Coverage: all 21 compliance states + top US metros.
#                         Fallback: agents in unlisted markets get national feeds only.
#
# Each feed entry: (label, url, default_signal_type)
# Feeds that 404 or time out are logged and skipped — never break collection.
# ─────────────────────────────────────────────────────────────────────────────

NATIONAL_RSS_FEEDS = [
    # ── Industry publications ────────────────────────────────────────────────
    ("Inman News",               "https://www.inman.com/feed/",                                          "market|news"),
    ("The Close",                "https://theclose.com/feed/",                                           "market|news"),
    ("RealTrends",               "https://www.realtrends.com/feed/",                                     "market|industry"),
    ("HousingWire",              "https://www.housingwire.com/feed/",                                    "market|policy"),
    ("Mortgage News Daily",      "https://www.mortgagenewsdaily.com/rss/headlines.aspx",                 "market|rates"),
    # ── Federal agencies ─────────────────────────────────────────────────────
    ("NAR News",                 "https://www.nar.realtor/rss/news",                                     "policy|market"),
    ("HUD News Releases",        "https://www.hud.gov/rss/News_Releases.xml",                            "policy|regulatory"),
    ("CFPB Newsroom",            "https://www.consumerfinance.gov/about-us/newsroom/feed/",              "regulatory|policy"),
    # ── National data providers ───────────────────────────────────────────────
    ("Redfin News",              "https://www.redfin.com/news/feed/",                                    "market|data"),
    ("Zillow Research",          "https://www.zillow.com/research/feed/",                                "market|data"),
    ("CoreLogic Insights",       "https://www.corelogic.com/intelligence/feed/",                        "market|data"),
    # ── National business / finance ──────────────────────────────────────────
    ("WSJ Real Estate",          "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",                       "market|news"),
    ("Bloomberg Real Estate",    "https://feeds.bloomberg.com/markets/news.rss",                        "market|news"),
]

# Market lookup table — keyed on lowercase partial-match strings.
# An agent's market field is lowercased and checked with `in` against each key.
# Multiple keys can match the same market string — all matching feeds are used.
# Format: { "match_string": [(label, url, signal_type), ...] }

MARKET_RSS_FEEDS = {

    # ── COLORADO (CO) ─────────────────────────────────────────────────────────
    "denver": [
        ("Denver Post Real Estate",      "https://feeds.denverpost.com/dp/real-estate",                   "market|news"),
        ("Denver Business Journal RE",   "https://www.bizjournals.com/denver/real_estate/rss/",           "market|development"),
        ("REColorado Blog",              "https://www.recolorado.com/blog/feed",                          "market|data"),
        ("Denver7 News",                 "https://www.thedenverchannel.com/rss/news.rss",                 "news|development"),
    ],
    "colorado springs": [
        ("Colorado Springs Gazette RE",  "https://gazette.com/search/?f=rss&t=article&c=business",       "market|news"),
        ("Colorado Springs Business Journal", "https://www.cobizmag.com/feed/",                          "market|development"),
    ],
    "boulder": [
        ("Boulder Daily Camera RE",      "https://www.dailycamera.com/feed/",                            "market|news"),
    ],
    "fort collins": [
        ("Coloradoan",                   "https://www.coloradoan.com/rss/news/",                         "market|news"),
    ],

    # ── WYOMING (WY) ─────────────────────────────────────────────────────────
    "cheyenne": [
        ("Wyoming Tribune Eagle",        "https://www.wyomingnews.com/rss.xml",                          "market|news"),
    ],
    "casper": [
        ("Casper Star-Tribune",          "https://trib.com/feed/",                                       "market|news"),
    ],

    # ── MONTANA (MT) ─────────────────────────────────────────────────────────
    "billings": [
        ("Billings Gazette",             "https://billingsgazette.com/feed/",                            "market|news"),
    ],
    "missoula": [
        ("Missoulian",                   "https://missoulian.com/feed/",                                 "market|news"),
    ],
    "bozeman": [
        ("Bozeman Daily Chronicle",      "https://www.bozemandailychronicle.com/feed/",                  "market|news"),
    ],

    # ── IDAHO (ID) ────────────────────────────────────────────────────────────
    "boise": [
        ("Idaho Statesman",              "https://www.idahostatesman.com/news/business/real-estate/rss", "market|news"),
        ("Boise Dev",                    "https://boisedev.com/feed/",                                   "development|news"),
    ],

    # ── UTAH (UT) ─────────────────────────────────────────────────────────────
    "salt lake": [
        ("Salt Lake Tribune RE",         "https://www.sltrib.com/feed/",                                 "market|news"),
        ("Deseret News Business",        "https://www.deseret.com/arc/outboundfeeds/rss/",               "market|development"),
        ("Utah Business",                "https://utahbusiness.com/feed/",                               "market|development"),
    ],
    "provo": [
        ("Daily Herald Utah",            "https://www.heraldextra.com/search/?f=rss&t=article",          "market|news"),
    ],

    # ── NEW MEXICO (NM) ───────────────────────────────────────────────────────
    "albuquerque": [
        ("Albuquerque Journal Business", "https://www.abqjournal.com/category/business/feed/",           "market|news"),
        ("Albuquerque Business First",   "https://www.bizjournals.com/albuquerque/real_estate/rss/",     "market|development"),
    ],
    "santa fe": [
        ("Santa Fe New Mexican",         "https://www.santafenewmexican.com/search/?f=rss&t=article",    "market|news"),
    ],

    # ── TEXAS (TX) ───────────────────────────────────────────────────────────
    "dallas": [
        ("Dallas Morning News RE",       "https://www.dallasnews.com/business/real-estate/rss/",         "market|news"),
        ("Dallas Business Journal RE",   "https://www.bizjournals.com/dallas/real_estate/rss/",          "market|development"),
        ("Dallas Innovates",             "https://dallasinnovates.com/feed/",                            "development|news"),
    ],
    "houston": [
        ("Houston Chronicle RE",         "https://www.houstonchronicle.com/business/real-estate/rss/",  "market|news"),
        ("Houston Business Journal RE",  "https://www.bizjournals.com/houston/real_estate/rss/",        "market|development"),
        ("HAR Market Updates",           "https://www.har.com/rss/news",                                "market|data"),
    ],
    "austin": [
        ("Austin American-Statesman RE", "https://www.statesman.com/business/real-estate/rss/",         "market|news"),
        ("Austin Business Journal RE",   "https://www.bizjournals.com/austin/real_estate/rss/",         "market|development"),
        ("ABoR Market Data",             "https://www.abor.com/news/feed/",                             "market|data"),
    ],
    "san antonio": [
        ("San Antonio Express-News RE",  "https://www.mysanantonio.com/business/real-estate/rss/",      "market|news"),
        ("San Antonio Business Journal", "https://www.bizjournals.com/sanantonio/real_estate/rss/",     "market|development"),
    ],

    # ── ARIZONA (AZ) ─────────────────────────────────────────────────────────
    "phoenix": [
        ("Arizona Republic RE",          "https://www.azcentral.com/business/real-estate/rss/",         "market|news"),
        ("Phoenix Business Journal RE",  "https://www.bizjournals.com/phoenix/real_estate/rss/",        "market|development"),
        ("AZBigMedia RE",                "https://azbigmedia.com/real-estate/feed/",                    "market|development"),
    ],
    "tucson": [
        ("Arizona Daily Star RE",        "https://tucson.com/business/real-estate/rss/",                "market|news"),
        ("Tucson Business Journal",      "https://www.bizjournals.com/phoenix/real_estate/rss/",        "market|development"),
    ],
    "scottsdale": [
        ("AZBigMedia RE",                "https://azbigmedia.com/real-estate/feed/",                    "market|development"),
        ("Arizona Republic RE",          "https://www.azcentral.com/business/real-estate/rss/",         "market|news"),
    ],

    # ── NEVADA (NV) ──────────────────────────────────────────────────────────
    "las vegas": [
        ("Las Vegas Review-Journal RE",  "https://www.reviewjournal.com/business/real-estate/rss/",     "market|news"),
        ("Las Vegas Business Press",     "https://lvbusinesspress.com/feed/",                           "market|development"),
        ("Vegas Inc",                    "https://vegasinc.lasvegassun.com/feed/",                      "market|development"),
    ],
    "reno": [
        ("Reno Gazette-Journal",         "https://www.rgj.com/rss/news/",                               "market|news"),
        ("Northern Nevada Business",     "https://www.nnbw.com/feed/",                                  "market|development"),
    ],

    # ── OREGON (OR) ──────────────────────────────────────────────────────────
    "portland": [
        ("Oregonian Business",           "https://www.oregonlive.com/business/rss/",                    "market|news"),
        ("Portland Business Journal RE", "https://www.bizjournals.com/portland/real_estate/rss/",       "market|development"),
        ("Oregon Business",              "https://oregonbusiness.com/feed/",                            "market|development"),
    ],
    "eugene": [
        ("Register-Guard",               "https://www.registerguard.com/search/?f=rss&t=article",       "market|news"),
    ],
    "bend": [
        ("Bend Bulletin",                "https://www.bendbulletin.com/feed/",                          "market|news"),
        ("Central Oregon Association",   "https://www.coar.com/feed/",                                  "market|data"),
    ],

    # ── WASHINGTON (WA) ──────────────────────────────────────────────────────
    "seattle": [
        ("Seattle Times RE",             "https://www.seattletimes.com/business/real-estate/rss/",      "market|news"),
        ("Puget Sound Business Journal", "https://www.bizjournals.com/seattle/real_estate/rss/",        "market|development"),
        ("NWMLS Market Data",            "https://www.nwmls.com/news/feed/",                            "market|data"),
    ],
    "spokane": [
        ("Spokesman-Review Business",    "https://www.spokesman.com/rss/business/",                     "market|news"),
        ("Spokane Business Journal",     "https://www.spokanejournal.com/feed/",                        "market|development"),
    ],
    "tacoma": [
        ("News Tribune Business",        "https://www.thenewstribune.com/news/business/rss/",           "market|news"),
    ],

    # ── CALIFORNIA (CA) ──────────────────────────────────────────────────────
    "los angeles": [
        ("LA Times RE",                  "https://www.latimes.com/business/real-estate/rss2.0.xml",     "market|news"),
        ("LA Business Journal RE",       "https://labusinessjournal.com/real-estate/rss/",              "market|development"),
        ("Bisnow LA",                    "https://www.bisnow.com/los-angeles/rss",                      "market|development"),
    ],
    "san francisco": [
        ("SF Chronicle RE",              "https://www.sfchronicle.com/business/real-estate/rss/",       "market|news"),
        ("SF Business Times RE",         "https://www.bizjournals.com/sanfrancisco/real_estate/rss/",   "market|development"),
        ("The Real Deal SF",             "https://therealdeal.com/tag/san-francisco/feed/",             "market|development"),
    ],
    "san diego": [
        ("San Diego Union-Tribune RE",   "https://www.sandiegouniontribune.com/business/real-estate/rss/", "market|news"),
        ("San Diego Business Journal",   "https://www.bizjournals.com/sandiego/real_estate/rss/",       "market|development"),
    ],
    "sacramento": [
        ("Sacramento Bee Business",      "https://www.sacbee.com/news/business/real-estate/rss/",       "market|news"),
        ("Sacramento Business Journal",  "https://www.bizjournals.com/sacramento/real_estate/rss/",     "market|development"),
    ],
    "san jose": [
        ("Mercury News RE",              "https://www.mercurynews.com/real-estate/rss/",                "market|news"),
        ("Silicon Valley Business Journal", "https://www.bizjournals.com/sanjose/real_estate/rss/",    "market|development"),
    ],

    # ── ALASKA (AK) ──────────────────────────────────────────────────────────
    "anchorage": [
        ("Anchorage Daily News",         "https://www.adn.com/real-estate/rss/",                        "market|news"),
        ("Alaska Business",              "https://www.akbizmag.com/feed/",                              "market|development"),
    ],

    # ── HAWAII (HI) ──────────────────────────────────────────────────────────
    "honolulu": [
        ("Honolulu Star-Advertiser RE",  "https://www.staradvertiser.com/real-estate/rss/",             "market|news"),
        ("Pacific Business News RE",     "https://www.bizjournals.com/pacific/real_estate/rss/",        "market|development"),
    ],
    "maui": [
        ("Maui News",                    "https://www.mauinews.com/feed/",                              "market|news"),
    ],

    # ── FLORIDA (FL) ─────────────────────────────────────────────────────────
    "miami": [
        ("Miami Herald RE",              "https://www.miamiherald.com/news/business/real-estate/rss/",  "market|news"),
        ("South Florida Business Journal","https://www.bizjournals.com/southflorida/real_estate/rss/",  "market|development"),
        ("The Real Deal Miami",          "https://therealdeal.com/tag/miami/feed/",                     "market|development"),
    ],
    "orlando": [
        ("Orlando Sentinel RE",          "https://www.orlandosentinel.com/business/real-estate/rss/",  "market|news"),
        ("Orlando Business Journal RE",  "https://www.bizjournals.com/orlando/real_estate/rss/",       "market|development"),
    ],
    "tampa": [
        ("Tampa Bay Times RE",           "https://www.tampabay.com/business/real-estate/rss/",         "market|news"),
        ("Tampa Bay Business Journal",   "https://www.bizjournals.com/tampabay/real_estate/rss/",      "market|development"),
    ],
    "jacksonville": [
        ("Florida Times-Union Business", "https://www.jacksonville.com/business/rss/",                 "market|news"),
        ("Jacksonville Business Journal","https://www.bizjournals.com/jacksonville/real_estate/rss/",  "market|development"),
    ],

    # ── GEORGIA (GA) ─────────────────────────────────────────────────────────
    "atlanta": [
        ("Atlanta Journal-Constitution RE","https://www.ajc.com/business/real-estate/rss/",            "market|news"),
        ("Atlanta Business Chronicle RE", "https://www.bizjournals.com/atlanta/real_estate/rss/",      "market|development"),
        ("Bisnow Atlanta",               "https://www.bisnow.com/atlanta/rss",                         "market|development"),
    ],
    "savannah": [
        ("Savannah Morning News",        "https://www.savannahnow.com/search/?f=rss&t=article",        "market|news"),
    ],

    # ── NORTH CAROLINA (NC) ──────────────────────────────────────────────────
    "charlotte": [
        ("Charlotte Observer RE",        "https://www.charlotteobserver.com/news/business/real-estate/rss/", "market|news"),
        ("Charlotte Business Journal RE","https://www.bizjournals.com/charlotte/real_estate/rss/",     "market|development"),
    ],
    "raleigh": [
        ("News & Observer Business",     "https://www.newsobserver.com/business/real-estate/rss/",     "market|news"),
        ("Triangle Business Journal RE", "https://www.bizjournals.com/triangle/real_estate/rss/",      "market|development"),
    ],
    "durham": [
        ("News & Observer Business",     "https://www.newsobserver.com/business/real-estate/rss/",     "market|news"),
        ("Triangle Business Journal RE", "https://www.bizjournals.com/triangle/real_estate/rss/",      "market|development"),
    ],

    # ── SOUTH CAROLINA (SC) ──────────────────────────────────────────────────
    "charleston": [
        ("Post and Courier Business",    "https://www.postandcourier.com/business/rss/",               "market|news"),
        ("Charleston Business Journal",  "https://www.charlestonbusiness.com/feed/",                   "market|development"),
    ],
    "columbia": [
        ("The State Business",           "https://www.thestate.com/news/business/rss/",                "market|news"),
    ],
    "greenville": [
        ("Greenville News Business",     "https://www.greenvilleonline.com/business/rss/",             "market|news"),
        ("Upstate Business Journal",     "https://upstatebusinessjournal.com/feed/",                   "market|development"),
    ],

    # ── TENNESSEE (TN) ───────────────────────────────────────────────────────
    "nashville": [
        ("Tennessean Business",          "https://www.tennessean.com/business/real-estate/rss/",       "market|news"),
        ("Nashville Business Journal RE","https://www.bizjournals.com/nashville/real_estate/rss/",     "market|development"),
        ("Nashville Post",               "https://www.nashvillepost.com/feed/",                        "market|development"),
    ],
    "memphis": [
        ("Memphis Commercial Appeal Business","https://www.commercialappeal.com/business/rss/",        "market|news"),
        ("Memphis Business Journal RE",  "https://www.bizjournals.com/memphis/real_estate/rss/",       "market|development"),
    ],
    "knoxville": [
        ("Knoxville News Sentinel Business","https://www.knoxnews.com/business/rss/",                  "market|news"),
    ],

    # ── VIRGINIA (VA) ────────────────────────────────────────────────────────
    "richmond": [
        ("Richmond Times-Dispatch RE",   "https://richmond.com/business/real-estate/rss/",             "market|news"),
        ("Richmond BizSense",            "https://richmondbizsense.com/feed/",                         "market|development"),
    ],
    "norfolk": [
        ("Virginian-Pilot Business",     "https://www.pilotonline.com/business/rss/",                  "market|news"),
        ("Inside Business Hampton Roads","https://insidebiz.com/feed/",                                "market|development"),
    ],
    "northern virginia": [
        ("Washington Business Journal RE","https://www.bizjournals.com/washington/real_estate/rss/",   "market|development"),
        ("Washington Post RE",           "https://feeds.washingtonpost.com/rss/realestate",            "market|news"),
    ],
    "arlington": [
        ("Washington Business Journal RE","https://www.bizjournals.com/washington/real_estate/rss/",   "market|development"),
        ("ARLnow",                       "https://www.arlnow.com/feed/",                               "market|news"),
    ],

    # ── MARYLAND (MD) ────────────────────────────────────────────────────────
    "baltimore": [
        ("Baltimore Sun Business",       "https://www.baltimoresun.com/business/real-estate/rss/",     "market|news"),
        ("Baltimore Business Journal RE","https://www.bizjournals.com/baltimore/real_estate/rss/",     "market|development"),
        ("Bisnow Baltimore",             "https://www.bisnow.com/washington-dc/rss",                   "market|development"),
    ],
    "bethesda": [
        ("Washington Post RE",           "https://feeds.washingtonpost.com/rss/realestate",            "market|news"),
        ("Washington Business Journal RE","https://www.bizjournals.com/washington/real_estate/rss/",   "market|development"),
    ],
    "annapolis": [
        ("Capital Gazette Business",     "https://www.capitalgazette.com/business/rss/",               "market|news"),
    ],

    # ── ADDITIONAL TOP METROS (non-compliance states, high transaction volume) ──

    # New York
    "new york": [
        ("NY Times RE",                  "https://feeds.nytimes.com/nyt/rss/RealEstate",               "market|news"),
        ("The Real Deal NY",             "https://therealdeal.com/new-york/feed/",                     "market|development"),
        ("Crain's NY Real Estate",       "https://www.crainsnewyork.com/real-estate/rss/",             "market|development"),
    ],
    # Chicago
    "chicago": [
        ("Chicago Tribune RE",           "https://www.chicagotribune.com/real-estate/rss/",            "market|news"),
        ("Crain's Chicago RE",           "https://www.chicagobusiness.com/real-estate/rss/",           "market|development"),
        ("Bisnow Chicago",               "https://www.bisnow.com/chicago/rss",                         "market|development"),
    ],
    # Boston
    "boston": [
        ("Boston Globe RE",              "https://www.bostonglobe.com/business/real-estate/rss/",      "market|news"),
        ("Boston Business Journal RE",   "https://www.bizjournals.com/boston/real_estate/rss/",        "market|development"),
        ("Banker & Tradesman",           "https://www.bankertradesman.com/feed/",                      "market|data"),
    ],
    # Minneapolis
    "minneapolis": [
        ("Star Tribune Business",        "https://www.startribune.com/business/rss/",                  "market|news"),
        ("Minneapolis Business Journal", "https://www.bizjournals.com/twincities/real_estate/rss/",    "market|development"),
    ],
    # Detroit
    "detroit": [
        ("Detroit Free Press Business",  "https://www.freep.com/business/rss/",                        "market|news"),
        ("Crain's Detroit Business RE",  "https://www.crainsdetroit.com/real-estate/rss/",             "market|development"),
    ],
    # Pittsburgh
    "pittsburgh": [
        ("Pittsburgh Post-Gazette Business","https://www.post-gazette.com/business/rss/",              "market|news"),
        ("Pittsburgh Business Times RE", "https://www.bizjournals.com/pittsburgh/real_estate/rss/",    "market|development"),
    ],
    # Philadelphia
    "philadelphia": [
        ("Philadelphia Inquirer RE",     "https://www.inquirer.com/real-estate/rss/",                  "market|news"),
        ("Philadelphia Business Journal","https://www.bizjournals.com/philadelphia/real_estate/rss/",  "market|development"),
    ],
    # Kansas City
    "kansas city": [
        ("KC Star Business",             "https://www.kansascity.com/news/business/real-estate/rss/",  "market|news"),
        ("Kansas City Business Journal", "https://www.bizjournals.com/kansascity/real_estate/rss/",    "market|development"),
    ],
    # St. Louis
    "st. louis": [
        ("St. Louis Post-Dispatch Business","https://www.stltoday.com/business/real-estate/rss/",      "market|news"),
        ("St. Louis Business Journal RE","https://www.bizjournals.com/stlouis/real_estate/rss/",       "market|development"),
    ],
    # Indianapolis
    "indianapolis": [
        ("Indianapolis Star Business",   "https://www.indystar.com/business/real-estate/rss/",         "market|news"),
        ("Indianapolis Business Journal","https://www.ibj.com/articles/rss/feed",                      "market|development"),
    ],
    # Columbus
    "columbus": [
        ("Columbus Dispatch Business",   "https://www.dispatch.com/business/rss/",                     "market|news"),
        ("Columbus Business First RE",   "https://www.bizjournals.com/columbus/real_estate/rss/",      "market|development"),
    ],
    # Cleveland
    "cleveland": [
        ("Plain Dealer Business",        "https://www.cleveland.com/business/rss/",                    "market|news"),
        ("Crain's Cleveland Business RE","https://www.crainscleveland.com/real-estate/rss/",           "market|development"),
    ],
    # Cincinnati
    "cincinnati": [
        ("Cincinnati Enquirer Business", "https://www.cincinnati.com/business/real-estate/rss/",       "market|news"),
        ("Cincinnati Business Courier",  "https://www.bizjournals.com/cincinnati/real_estate/rss/",    "market|development"),
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


def _fetch_rss_signals(market: str, cutoff_dt: datetime) -> list:
    """
    Tier 0 — Fetch RSS feeds via rss2json.com API and return signals in the
    same dict shape as Claude signals. Always includes all national feeds.
    Market-specific feeds are added based on the agent's market string.

    Uses rss2json.com as a proxy — bypasses publisher-side SSL/403 blocks
    that direct urllib fetches hit on Render. Requires RSS2JSON_API_KEY env var.

    Only returns items published after cutoff_dt (45-day hard limit).
    Never raises — individual feed failures are logged and skipped.
    Returns a list of signal dicts tagged with source_type='rss'.
    """
    if not RSS_ENABLED:
        return []

    import re as _re
    import urllib.parse

    api_key = os.getenv("RSS2JSON_API_KEY", "")
    if not api_key:
        print("[Signals/RSS] RSS2JSON_API_KEY not set — skipping Tier 0.")
        return []

    # Build the feed list: national always-on + market-matched feeds
    market_feeds = _get_market_rss_feeds(market)
    all_feeds = [(label, url, sig_type, "National") for label, url, sig_type in NATIONAL_RSS_FEEDS]
    all_feeds += [(label, url, sig_type, market or "Local") for label, url, sig_type in market_feeds]

    if market_feeds:
        print(f"[Signals/RSS] Market '{market}': {len(NATIONAL_RSS_FEEDS)} national + {len(market_feeds)} local feeds.")
    else:
        print(f"[Signals/RSS] Market '{market}': no local feeds matched — national feeds only.")

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

                    # pubDate from rss2json is normalised to "YYYY-MM-DD HH:MM:SS"
                    # rss2json returns "0000-00-00 00:00:00" as a sentinel when the
                    # feed has no date — treat that as no date rather than a real
                    # timestamp (which would fail the 45-day cutoff and drop the item).
                    pub_raw = (item.get("pubDate") or "").strip()
                    pub_dt  = None
                    if not pub_raw.startswith("0000"):
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                            try:
                                pub_dt = datetime.strptime(pub_raw[:len(fmt)], fmt)
                                break
                            except Exception:
                                continue

                    if pub_dt is None:
                        pub_date_str = None  # No parseable date — allow through
                    else:
                        if pub_dt < cutoff_dt:
                            continue  # Hard reject — older than 45 days
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
                print(f"[Signals/RSS] {label}: {feed_count} item(s) within 45 days.")

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
        if age_days > 45:
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
    Rejects any signal with a published_date older than 45 days.
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
                source_type    = source_type,
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

    areas_str  = ", ".join(service_areas[:5]) if service_areas else market
    market_str = market or "the local area"
    niche_str  = primary_niches[0] if primary_niches else "Residential Real Estate"
    today_str  = datetime.utcnow().strftime("%B %d, %Y")  # e.g. "April 30, 2026"
    cutoff_str = (datetime.utcnow() - __import__('datetime').timedelta(days=45)).strftime("%B %d, %Y")
    total_saved = 0

    # ── TIER 0: RSS feeds — real-time, no API cost ───────────────────────────
    # Parsed before any Claude web search fires.
    # National feeds run for every agent. Market feeds are matched automatically
    # from the agent's market string — zero agent configuration required.
    # If RSS yields enough strong signals, Claude searches are skipped entirely.
    from datetime import timedelta
    cutoff_dt   = datetime.utcnow() - timedelta(days=45)
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
