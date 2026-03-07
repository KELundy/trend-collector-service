import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

router = APIRouter(prefix="/content", tags=["content-engine"])


# ─────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────
class IdentityModel(BaseModel):
    primaryCategories: List[str] = Field(default_factory=list)
    subNichesByCategory: Dict[str, List[str]] = Field(default_factory=dict)
    trendPreferences: List[str] = Field(default_factory=list)


class AgentProfileModel(BaseModel):
    agentName: Optional[str] = Field(None, description="Agent's full name")
    businessName: Optional[str] = Field(None, description="Business or team name")
    brokerage: Optional[str] = Field(None, description="Brokerage name")
    market: Optional[str] = Field(None, description="Market / city / region")
    brandVoice: Optional[str] = Field(None, description="Brand voice description")
    shortBio: Optional[str] = Field(None, description="Agent short bio")
    audienceDescription: Optional[str] = Field(None, description="Target audience description")
    wordsAvoid: Optional[str] = Field(None, description="Words or phrases to avoid")
    wordsPrefer: Optional[str] = Field(None, description="Words or phrases to prefer")
    mlsNames: Optional[List[str]] = Field(default_factory=list, description="MLS memberships for compliance")


class ComplianceBadge(BaseModel):
    fairHousing: str = Field(description="Fair Housing status: pass | warn | fail")
    brokerageDisclosure: str = Field(description="Disclosure status: pass | warn | fail")
    narStandards: str = Field(description="NAR standards status: pass | warn | fail")
    overallStatus: str = Field(description="Overall: compliant | review | attention")
    notes: List[str] = Field(default_factory=list, description="Specific compliance notes")


class ContentResponse(BaseModel):
    headline: str
    thumbnailIdea: str
    hashtags: str
    post: str
    cta: str
    script: str
    compliance: ComplianceBadge
    generated_at: datetime


class ContentRequest(BaseModel):
    identity: IdentityModel
    agentProfile: Optional[AgentProfileModel] = Field(
        None, description="Agent identity and brand profile"
    )
    situation: str = Field(..., description="The selected situation or trend context")
    persona: Optional[str] = None
    tone: Optional[str] = None
    length: Optional[str] = None
    selectedTrends: List[str] = Field(default_factory=list)
    timestamp: Optional[str] = None


# ─────────────────────────────────────────────
# ANTHROPIC CLIENT
# ─────────────────────────────────────────────
def _get_anthropic_client() -> Anthropic:
    if Anthropic is None:
        raise RuntimeError(
            "Anthropic Python client is not installed. "
            "Add `anthropic` to requirements.txt and redeploy."
        )
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
    return Anthropic(api_key=api_key)


# ─────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────
def _build_content_prompt(payload: ContentRequest) -> str:
    identity = payload.identity
    profile  = payload.agentProfile or AgentProfileModel()

    # ── Agent identity
    agent_name    = profile.agentName    or "the agent"
    business_name = profile.businessName or ""
    brokerage     = profile.brokerage    or ""
    market        = profile.market       or "their local market"
    brand_voice   = profile.brandVoice   or "professional and approachable"
    short_bio     = profile.shortBio     or ""
    audience      = profile.audienceDescription or ""
    words_avoid   = profile.wordsAvoid   or ""
    words_prefer  = profile.wordsPrefer  or ""

    # Build identity display string naturally
    agent_display = agent_name
    if business_name:
        agent_display += f" of {business_name}"
    if brokerage and brokerage.lower() not in business_name.lower():
        agent_display += f" with {brokerage}"

    # ── Niche context
    primary_categories = ", ".join(identity.primaryCategories) or "real estate"
    subniche_lines = []
    for cat, subs in identity.subNichesByCategory.items():
        if subs:
            subniche_lines.append(f"  - {cat}: {', '.join(subs)}")
    subniches_text = "\n".join(subniche_lines) or "  - General real estate services"

    trend_prefs      = ", ".join(identity.trendPreferences) or "current market conditions"
    selected_trends  = ", ".join(payload.selectedTrends)    or "current market activity"

    # ── Optional refinements
    persona_text = f"Target audience: {payload.persona}.\n" if payload.persona else ""
    tone_text    = f"Tone: {payload.tone}.\n" if payload.tone else f"Tone: {brand_voice}.\n"
    length_text  = f"Content length: {payload.length}.\n" if payload.length else "Content length: medium.\n"
    avoid_text   = f"Never use these words or phrases: {words_avoid}.\n" if words_avoid else ""
    prefer_text  = f"Naturally use these words or phrases where appropriate: {words_prefer}.\n" if words_prefer else ""
    bio_text     = f"Agent background: {short_bio}\n" if short_bio else ""
    audience_text = f"Audience context: {audience}\n" if audience else ""

    return f"""You are a senior marketing strategist and expert real estate copywriter.

You are creating content for {agent_display}, a real estate professional serving {market}.

AGENT IDENTITY
──────────────
Name: {agent_name}
{f"Business/Team: {business_name}" if business_name else ""}
{f"Brokerage: {brokerage}" if brokerage else ""}
Market: {market}
{bio_text}{audience_text}
Primary niches:
{primary_categories}

Sub-specializations:
{subniches_text}

CONTENT CONTEXT
───────────────
Current situation: {payload.situation}
Trend signals: {selected_trends}
Trend preferences: {trend_prefs}

STYLE GUIDANCE
──────────────
{tone_text}{length_text}{avoid_text}{prefer_text}
CRITICAL IDENTITY RULES — THESE ARE MANDATORY, NOT OPTIONAL
─────────────────────────────────────────────────────────────
1. AGENT NAME IN POST: The agent's name ({agent_name}) MUST appear in the
   social post (section 4) — naturally, as a first-person reference or sign-off.
   Example: "— {agent_name}" or "I'm {agent_name} and..." or "Reach out to {agent_name}".
   Also include in the CTA (section 5) and Script (section 6).

2. BROKERAGE IN POST: {f'The brokerage ({brokerage}) MUST appear in the social post (section 4) as a footer disclosure line. Format it like: "{agent_name} | {brokerage}" or "— {agent_name}, {brokerage}". This is a legal requirement, not optional.' if brokerage else 'Include agent name as a sign-off in the post.'}

3. MARKET SPECIFICITY: {f"Always say '{market}' specifically — never 'your local area', 'the local market', or generic geography. '{market}' must appear at least once in the post or script."}

4. Content must feel written FOR {agent_name} specifically, not a generic template.
5. Content must feel locally relevant to {market} and situationally timely.
6. Optimize for AI and search recommendation: clear, descriptive, niche-specific language.
7. Avoid clickbait. Avoid fluff. Use concrete, real-world phrasing.

COMPLIANCE RULES (BUILT IN — DO NOT SKIP)
──────────────────────────────────────────
All content must comply with:
- Fair Housing Act: No language suggesting preference or limitation based on race, color,
  national origin, religion, sex, familial status, or disability. Never use terms like
  "perfect for families," "great neighborhood," "ideal for young professionals" as these
  can imply discriminatory steering. Use property-focused language instead.
- NAR Code of Ethics Article 12: All advertising must be truthful and not misleading.
  No exaggerated claims. No promises of specific outcomes.
- Brokerage disclosure: {brokerage if brokerage else "agent's brokerage"} must be
  identifiable in the content. Agent's licensed name must appear.
- Do not make specific financial predictions or guarantee investment returns.

OUTPUT FORMAT — CRITICAL
────────────────────────
You MUST respond with ONLY a valid JSON object. No preamble, no explanation,
no markdown fences, no text before or after. Just the raw JSON object.

The JSON must have exactly these keys:

{{
  "headline": "A compelling, niche-specific headline — one sentence, no period",
  "thumbnailIdea": "A vivid 1-2 sentence description of a visual concept for this content",
  "hashtags": "#hashtag1 #hashtag2 #hashtag3 (8-12 tags, space-separated, mix of niche + location + broad)",
  "post": "A full platform-ready social post. MUST end with a footer line formatted exactly as: — {agent_name}{' | ' + brokerage if brokerage else ''}",
  "cta": "A specific action-oriented call to action that includes {agent_name} by name",
  "script": "A complete 45-75 second spoken script written as natural conversational dialogue. Must mention {agent_name} and {market} specifically. Full paragraphs, not a fragment."
}}

HARD RULES FOR JSON OUTPUT:
- Every value must be complete, fully written content — never a placeholder
- The post value MUST contain {agent_name}{' and ' + brokerage if brokerage else ''} — this is a legal disclosure requirement
- The script value must be a complete paragraph of dialogue, not a sentence fragment
- {market} must appear in the post or script — never use "your local market" or "the area"
- No line breaks inside JSON string values — use spaces between sentences
- Return ONLY the JSON. If you add any other text, the system will break.
"""


# ─────────────────────────────────────────────
# COMPLIANCE CHECKER
# ─────────────────────────────────────────────
# ── Fair Housing risk terms
FAIR_HOUSING_RISK_TERMS = [
    "perfect for families", "great for families", "ideal for families",
    "walking distance to churches", "good schools nearby", "safe neighborhood",
    "exclusive neighborhood", "desirable neighborhood", "up and coming",
    "gentrifying", "transitional neighborhood", "no children", "adults only",
    "perfect for couples", "ideal for young professionals", "bachelor pad",
    "master bedroom", "master bath",
    "integrated", "segregated", "ethnic", "hispanic", "asian neighborhood",
    "school district" , "crime", "quiet street",
]

# ── NAR Article 12 — unverifiable claims
NAR_RISK_TERMS = [
    "guaranteed", "i promise", "best in the city", "number one agent",
    "top agent in", "will sell your home", "promise you", "i guarantee",
    "100% success", "never fails", "best agent", "highest rated",
    "#1 agent", "number 1 agent",
]

# ── RESPA — referral fee and kickback language
RESPA_RISK_TERMS = [
    "referral fee", "kickback", "split the commission", "finder's fee",
    "paid for referral", "referral payment", "split my commission",
    "receive a fee", "compensation for referral", "refer and earn",
]

# ── Clear Cooperation / off-market language
CLEAR_COOPERATION_RISK_TERMS = [
    "pocket listing", "off-market exclusive", "coming soon exclusive",
    "pre-mls", "pre mls", "off mls", "not on the mls",
    "exclusive off-market", "private listing", "silent listing",
    "not listed publicly", "bypass the mls", "skip the mls",
]

# ── State commission — general property claim risk terms
STATE_COMMISSION_RISK_TERMS = [
    "as-is no inspection", "no inspection needed", "skip the inspection",
    "guaranteed to appreciate", "will increase in value", "guaranteed roi",
    "investment guaranteed", "never lose money", "risk free investment",
    "perfect investment", "zero risk",
]


def _run_compliance_check(
    content: str,
    agent_name: str,
    brokerage: str,
    mls_names: Optional[List[str]] = None,
) -> ComplianceBadge:
    """
    Full compliance check:
    - Fair Housing Act
    - Brokerage & licensee disclosure
    - NAR Code of Ethics Article 12
    - RESPA referral/kickback language
    - Clear Cooperation / off-market policy
    - State Real Estate Commission general rules
    - MLS-aware flagging
    """
    notes        = []
    fair_housing_status  = "pass"
    disclosure_status    = "pass"
    nar_status           = "pass"
    respa_status         = "pass"
    cooperation_status   = "pass"
    state_status         = "pass"

    content_lower = content.lower()
    mls_list = [m.strip() for m in (mls_names or []) if m and m.strip()]
    mls_display = ", ".join(mls_list) if mls_list else "your MLS"

    # ── Fair Housing
    triggered_fh = [t for t in FAIR_HOUSING_RISK_TERMS if t in content_lower]
    if triggered_fh:
        fair_housing_status = "warn"
        notes.append(
            f"Fair Housing: phrase(s) may imply steering — "
            f"'{triggered_fh[0]}'. Use property-focused language instead."
        )

    # ── Brokerage disclosure
    if brokerage:
        brokerage_words = [w.lower() for w in brokerage.split() if len(w) > 3]
        if not any(w in content_lower for w in brokerage_words):
            disclosure_status = "warn"
            notes.append(
                f"Brokerage disclosure: '{brokerage}' not detected. "
                f"Verify brokerage name appears before publishing."
            )

    # ── Agent name disclosure
    if agent_name:
        name_parts = [p.lower() for p in agent_name.split() if len(p) > 2]
        if not any(p in content_lower for p in name_parts):
            if disclosure_status == "pass":
                disclosure_status = "warn"
            notes.append(
                f"Licensee disclosure: '{agent_name}' not detected in content. "
                f"State law requires licensee name on all advertising."
            )

    # ── NAR Article 12
    triggered_nar = [t for t in NAR_RISK_TERMS if t in content_lower]
    if triggered_nar:
        nar_status = "warn"
        notes.append(
            f"NAR Article 12: '{triggered_nar[0]}' may constitute an unverifiable claim. "
            f"Remove or qualify the statement."
        )

    # ── RESPA
    triggered_respa = [t for t in RESPA_RISK_TERMS if t in content_lower]
    if triggered_respa:
        respa_status = "warn"
        notes.append(
            f"RESPA review suggested: '{triggered_respa[0]}' may reference a referral "
            f"fee or kickback arrangement. Verify compliance with RESPA Section 8 "
            f"before publishing."
        )

    # ── Clear Cooperation
    triggered_cc = [t for t in CLEAR_COOPERATION_RISK_TERMS if t in content_lower]
    if triggered_cc:
        cooperation_status = "warn"
        notes.append(
            f"MLS Cooperation: '{triggered_cc[0]}' may conflict with MLS cooperation "
            f"policies in {mls_display}. Verify this content complies with your MLS "
            f"advertising and listing rules before publishing."
        )

    # ── State Real Estate Commission
    triggered_state = [t for t in STATE_COMMISSION_RISK_TERMS if t in content_lower]
    if triggered_state:
        state_status = "warn"
        notes.append(
            f"State Commission review suggested: '{triggered_state[0]}' may conflict "
            f"with state real estate commission advertising standards. Verify compliance "
            f"with your state's rules before publishing."
        )
    else:
        # Always add a soft state reminder — rules vary too much to fully automate
        notes.append(
            f"State rules: Automated checks cover federal and NAR standards. "
            f"Verify content also meets your state real estate commission's "
            f"advertising requirements before publishing."
        )

    # ── MLS-specific reminder if MLS provided
    if mls_list:
        notes.append(
            f"MLS reminder: Content has not been checked against specific rules for "
            f"{mls_display}. Verify advertising rules including property description "
            f"standards and cooperation policies for your MLS before publishing."
        )

    # ── Overall status
    all_statuses = [
        fair_housing_status, disclosure_status, nar_status,
        respa_status, cooperation_status, state_status
    ]
    if "fail" in all_statuses:
        overall = "attention"
    elif "warn" in all_statuses:
        overall = "review"
    else:
        overall = "compliant"
        notes = ["Content passed all automated compliance checks. "
                 "Verify state commission and MLS-specific rules before publishing."]

    return ComplianceBadge(
        fairHousing=fair_housing_status,
        brokerageDisclosure=disclosure_status,
        narStandards=nar_status,
        overallStatus=overall,
        notes=notes,
    )


# ─────────────────────────────────────────────
# OUTPUT PARSER — JSON-based, no fragile splitting
# ─────────────────────────────────────────────
def _parse_claude_output(raw_text: str, compliance: ComplianceBadge) -> ContentResponse:
    """
    Parse Claude's JSON response into a ContentResponse.
    Falls back gracefully if JSON is malformed.
    """
    import re

    # Strip any accidental markdown fences Claude might add
    cleaned = raw_text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON object if surrounded by stray text
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    return ContentResponse(
        headline      = data.get("headline",      "Content generation error — please try again."),
        thumbnailIdea = data.get("thumbnailIdea", ""),
        hashtags      = data.get("hashtags",      ""),
        post          = data.get("post",          ""),
        cta           = data.get("cta",           ""),
        script        = data.get("script",        ""),
        compliance    = compliance,
        generated_at  = datetime.utcnow(),
    )


# ─────────────────────────────────────────────
# NICHE-AWARE SITUATIONS ENDPOINT
# ─────────────────────────────────────────────
NICHE_SITUATIONS = {

  # ── RESIDENTIAL ──────────────────────────────────────────────────────────────
  "Residential Buying & Selling": [
    "Buyer demand is outpacing available inventory in this market",
    "Interest rate changes shifting buyer affordability calculations",
    "Multiple offer situations becoming the norm again",
    "Sellers hesitating — waiting for the 'perfect' moment that may not come",
    "Spring market accelerating — serious buyers need to move now",
    "Fall slowdown creating hidden opportunity for prepared buyers",
    "AI and online tools changing how buyers find and evaluate homes",
    "Appraisal gap strategies buyers and sellers need to understand",
  ],
  "First-Time Homebuyers": [
    "First-time buyers overwhelmed by the current market",
    "Down payment assistance programs many buyers don't know exist",
    "Rent vs. buy analysis shifting in buyer's favor",
    "Interest rate confusion — buyers waiting for the perfect moment",
    "Credit score questions holding buyers back unnecessarily",
    "New construction as an alternative to competitive resale market",
    "Student loan debt and mortgage qualification — what's changed",
    "Co-buying with a friend or family member — how it works",
  ],
  "Luxury Real Estate": [
    "High-net-worth buyers prioritizing privacy and off-market access",
    "Luxury market showing resilience despite rate environment",
    "Second home and investment property demand among affluent buyers",
    "Lifestyle-driven search — location, amenities, architecture matter most",
    "Confidential listing opportunities for sellers valuing discretion",
    "International buyers entering the local luxury market",
    "Ultra-luxury supply constrained — qualified buyers waiting",
    "Wealth transfer creating new generation of luxury buyers",
  ],
  "Seniors & 55+ Communities": [
    "Seniors asking: is now the right time to sell?",
    "Empty nesters ready to rightsize — but don't know where to start",
    "Rising home values creating unexpected equity for long-term owners",
    "Family asking mom or dad to consider moving closer",
    "Health changes making the current home harder to manage",
    "Interest rates affecting downsizing math — is it still worth it?",
    "55+ communities expanding — more options than most people realize",
    "Aging-in-place modifications vs. moving — helping families decide",
  ],
  "New Construction": [
    "Builder incentives creating real opportunity for buyers right now",
    "New construction vs. resale — the honest comparison",
    "Lot selection and upgrade decisions overwhelming buyers",
    "Builder contract review — what buyers consistently miss",
    "Construction timeline delays affecting buyer plans",
    "Warranty walkthrough — what to inspect at closing",
    "Interest rate buydowns from builders making payments manageable",
    "New community amenities driving buyer interest in master-planned areas",
  ],
  "Move-Up Buyers": [
    "Growing family needs more space — timing the sell and buy",
    "Equity in current home creating a real move-up opportunity",
    "Bridge loan options for buyers who need to buy before selling",
    "School district driving the move-up decision",
    "Contingency offers in a competitive market",
    "Interest rate impact on move-up affordability",
    "Lifestyle change — working from home requiring dedicated office space",
    "Aging parents moving in — need for multi-generational floor plans",
  ],
  "Relocation": [
    "Corporate relocation with a tight move-in timeline",
    "Family relocating from out of state — buying sight unseen",
    "Military PCS orders creating urgent need to buy or sell",
    "Remote work opening up new markets for relocating buyers",
    "Cost of living comparison driving relocation decisions",
    "Neighborhood and school research for incoming families",
    "Temporary housing bridge while permanent home is secured",
    "Employer relocation packages — maximizing the benefit",
  ],
  "Veterans & Military": [
    "VA loan benefits many veterans don't fully understand",
    "PCS orders creating time-sensitive buying and selling needs",
    "Zero down payment still possible in today's market",
    "VA appraisal process — what buyers need to know",
    "Transitioning from military to civilian housing market",
    "Surviving spouse VA loan eligibility often overlooked",
    "Entitlement restoration for veterans who've used VA loans before",
    "Military community support networks for incoming families",
  ],
  "Condos & Townhomes": [
    "HOA financial health — what buyers should demand before closing",
    "Condo financing tightening — Fannie/Freddie rule changes",
    "Urban lifestyle appeal driving condo demand in walkable markets",
    "Special assessments — what buyers need to know before signing",
    "Lock-and-leave lifestyle resonating with remote workers and retirees",
    "Short-term rental restrictions changing condo investment math",
    "New condo supply entering the market — negotiating leverage for buyers",
    "Resale value analysis — which buildings hold value best",
  ],
  "Multi-Family (2–4 Units)": [
    "House-hacking strategy — live for free while building equity",
    "Rising rents making owner-occupied multi-family more attractive",
    "FHA financing for multi-family — low down payment with income offset",
    "Tenant-in-place sales — what buyers need to know",
    "Cash flow positive properties becoming harder to find — where to look",
    "Property management realities for first-time landlords",
    "Duplex to fourplex — scaling a portfolio from one property",
    "1031 exchange positioning for existing owners",
  ],
  "Short Sale & Foreclosure": [
    "Homeowner behind on payments — options before foreclosure",
    "Short sale as an alternative to foreclosure",
    "Cash offer timeline giving distressed sellers a way out",
    "Loan modification vs. selling — helping owners understand their choices",
    "Foreclosure timeline creating urgency for action",
    "Rebuilding credit and confidence after hardship",
    "REO properties — opportunities and risks for buyers",
    "Bank negotiation strategies that actually move deals forward",
  ],
  "Residential Leasing": [
    "Rental demand staying strong despite cooling for-sale market",
    "Tenant screening — protecting landlords in a changing legal landscape",
    "Rental pricing strategy — leaving money on the table is common",
    "Lease renewal vs. re-listing — which makes more financial sense",
    "New landlord mistakes that cost money and time",
    "Section 8 and housing assistance — understanding the opportunity",
    "Short-term vs. long-term rental strategy in this market",
    "Landlord-tenant law changes affecting lease terms",
  ],

  # ── COMMERCIAL ────────────────────────────────────────────────────────────────
  "Commercial Sales": [
    "Cap rate compression creating buyer-seller valuation gaps",
    "Sale-leaseback transactions gaining favor among business owners",
    "1031 exchange activity driving commercial acquisition demand",
    "Commercial lending tightening — what buyers need to secure financing",
    "Value-add opportunities in an otherwise constrained market",
    "Distressed commercial assets coming to market — buyer opportunity",
    "Net lease investments attracting passive income investors",
    "Commercial appraisal challenges slowing transaction timelines",
  ],
  "Commercial Leasing": [
    "Tenants gaining leverage as vacancy rates rise in some submarkets",
    "TI allowance negotiations becoming a major deal point",
    "Lease expiration planning — tenants waiting too long to start",
    "Landlords offering creative deal structures to attract quality tenants",
    "Sublease space flooding the market — hidden opportunity for tenants",
    "Letter of intent strategy — setting the right tone before lease negotiation",
    "Co-tenancy clauses and their impact on retail and office deals",
    "Build-to-suit options for tenants who can't find the right space",
  ],
  "Office Space": [
    "Hybrid work forcing companies to rethink their space requirements",
    "Sublease availability creating flight-to-quality opportunity for tenants",
    "Class A vs. B vs. C — the value case in today's market",
    "Amenity-rich buildings winning the talent attraction battle",
    "Lease restructuring — tenants renegotiating early for better terms",
    "Remote work permanence shrinking average office footprints",
    "Coworking integration into traditional office strategy",
    "Downtown vs. suburban office — the post-pandemic shift continues",
  ],
  "Retail & Mixed-Use": [
    "Experiential retail driving leasing demand in well-located centers",
    "E-commerce impact still reshaping which retail formats survive",
    "Food and beverage tenants filling spaces left by departing retailers",
    "Mixed-use development creating live-work-play demand",
    "Pop-up retail strategy — testing markets before committing to leases",
    "Anchor tenant vacancies rippling through neighborhood centers",
    "Last-mile logistics converting underperforming retail to distribution",
    "Street retail in urban corridors rebounding in select markets",
  ],
  "Industrial & Warehouse": [
    "E-commerce demand keeping industrial vacancy at historic lows",
    "Last-mile delivery facilities driving urban industrial demand",
    "Clear height and dock door specs becoming deal-breakers for tenants",
    "Industrial rent growth slowing — window opening for tenant negotiations",
    "Cold storage demand surging as food supply chains modernize",
    "Spec industrial development struggling to keep pace with demand",
    "Port-adjacent industrial commanding significant premium",
    "Flex industrial gaining favor among small manufacturers and distributors",
  ],
  "Medical & Dental": [
    "Healthcare consolidation driving MOB acquisition activity",
    "Medical office build-out costs — what tenants and landlords need to know",
    "ADA compliance requirements affecting older medical buildings",
    "Telehealth changing the square footage needs of healthcare providers",
    "Dental practice acquisition — real estate considerations often overlooked",
    "Healthcare district clustering strategy driving location decisions",
    "Imaging and radiology space requirements creating specialized demand",
    "Surgery center development — site selection and regulatory considerations",
  ],
  "Multi-Family (5+ Units)": [
    "Cap rate expansion creating acquisition opportunities for patient buyers",
    "Rent growth moderating in overbuilt markets — selective opportunities remain",
    "Value-add renovation strategy in a higher cost-of-capital environment",
    "Agency financing terms — Fannie and Freddie program updates",
    "Rent control legislation changing investment calculus in certain markets",
    "New supply wave creating temporary softness — long-term fundamentals intact",
    "Opportunity zone apartment development — tax incentive window open",
    "Class B to Class A repositioning — when it pencils and when it doesn't",
  ],
  "Hospitality": [
    "Leisure travel demand staying resilient despite economic headwinds",
    "Business travel recovery uneven — market-by-market analysis matters",
    "Conversion opportunities — office and retail to hotel",
    "RevPAR improvement strategies for independent operators",
    "Flag vs. independent positioning — the financial case for each",
    "Short-term rental competition reshaping hotel strategy in vacation markets",
    "Distressed hospitality assets — acquisition opportunity or value trap",
    "Extended stay demand growing as workforce housing shortage worsens",
  ],

  # ── LAND & SPECIALTY ──────────────────────────────────────────────────────────
  "Land & Development": [
    "Entitlement risk — why land deals fail after contract",
    "Zoning changes creating value where buyers aren't looking",
    "Infrastructure gaps limiting otherwise promising land parcels",
    "Builder demand for finished lots outpacing available supply",
    "Infill development opportunities in established neighborhoods",
    "Environmental due diligence — the step too many buyers skip",
    "Subdivision potential analysis — when the math works",
    "Agricultural land converting to residential — opportunity and process",
  ],
  "Ranch & Farm / Agricultural": [
    "Agricultural land values holding firm despite broader market shifts",
    "Water rights — the hidden value driver in Western markets",
    "Conservation easement opportunities for landowners with large acreage",
    "Farm transition planning — aging landowners with no succession plan",
    "Recreational and agricultural hybrid properties gaining buyer interest",
    "USDA financing options for farm and ranch acquisitions",
    "Carbon credit programs creating new revenue for agricultural landowners",
    "Drought and climate considerations in land valuation",
  ],
  "Recreational & Mountain": [
    "Vacation property demand staying elevated post-pandemic",
    "Short-term rental income offsetting carrying costs for recreational buyers",
    "Seasonal access considerations buyers from urban markets overlook",
    "Mountain community infrastructure — fire, utilities, road maintenance",
    "Hunting and fishing rights — value drivers rarely reflected in comps",
    "Off-grid capable properties attracting a growing buyer segment",
    "Climate migration driving demand for mountain and lake properties",
    "Second home financing — what's different from primary residence loans",
  ],
  "Vacant Land": [
    "Buildable lot scarcity in infill markets creating significant premium",
    "Soil and topography issues that derail deals after contract",
    "Utility access — the cost buyers consistently underestimate",
    "Rezoning opportunity — identifying parcels with upside potential",
    "Seller financing as a strategy to attract more land buyers",
    "Land banking strategy for patient investors",
    "Subdivision feasibility — when one parcel becomes multiple",
    "Environmental assessment requirements before development",
  ],

  # ── FUNCTIONAL SPECIALTIES ────────────────────────────────────────────────────
  "Property Management": [
    "Tenant screening standards tightening as eviction risks increase",
    "Maintenance cost inflation affecting owner net operating income",
    "Deferred maintenance creating liability for self-managing landlords",
    "Rent collection systems — technology making management more efficient",
    "Landlord-tenant law changes creating compliance risk",
    "Vacancy reduction strategy in a softening rental market",
    "Owner communication expectations rising — how to manage proactively",
    "Insurance requirements for rental properties getting more complex",
  ],
  "Investment Analysis": [
    "Rising interest rates reshinking return projections across asset classes",
    "Cap rate vs. cash-on-cash — which metric matters more right now",
    "Market cycle positioning — where we are and what it means for buyers",
    "Portfolio diversification across asset types and geographies",
    "Exit strategy planning before acquisition — working backward from the sale",
    "Tax-advantaged structure options investors often leave on the table",
    "Depreciation and cost segregation — accelerating tax benefits",
    "Syndication vs. direct ownership — the trade-offs investors need to understand",
  ],
  "Transaction Coordination": [
    "Contract-to-close timeline compression creating coordination pressure",
    "Title and escrow delays — the most common deal killers and how to prevent them",
    "Digital document management reducing errors and improving compliance",
    "Buyer and seller communication gaps causing last-minute surprises",
    "Vendor reliability — building a network that performs under pressure",
    "Compliance checklist gaps creating post-close liability",
    "Agent bandwidth — when transaction coordination creates competitive advantage",
    "Remote closings and digital notarization expanding access",
  ],
  "Appraisal & Valuation": [
    "Appraisal gap strategies in competitive offer situations",
    "Challenging a low appraisal — the process most agents don't use",
    "Pre-listing appraisal as a seller credibility tool",
    "Estate valuation — date of death appraisals and IRS requirements",
    "Refinance appraisal preparation — maximizing value evidence",
    "Market condition adjustments appraisers are making right now",
    "Automated valuation models vs. professional appraisal — knowing the difference",
    "Desktop and hybrid appraisal options changing the process",
  ],

  # ── LUXURY & UHNW ──────────────────────────────────────────────────────────────
  "Ultra-Luxury / UHNW": [
    "UHNW buyers prioritizing discretion over public listing exposure",
    "Family office real estate allocations increasing in uncertain markets",
    "Trophy property scarcity driving off-market transaction volume",
    "International capital flows into domestic ultra-luxury markets",
    "Estate and compound properties requiring specialized marketing",
    "Art, aviation, and real estate — the integrated UHNW asset conversation",
    "Privacy-first transaction structure for high-profile buyers and sellers",
    "Generational wealth transfer creating new ultra-luxury buyer cohort",
  ],
  "Second Homes & Vacation": [
    "Vacation property demand holding despite higher financing costs",
    "Short-term rental income changing the affordability calculus",
    "1031 exchange strategy for vacation property repositioning",
    "Destination market supply increasing — buyer leverage growing",
    "Second home financing rules — what's different from primary residence",
    "Property management options for absentee vacation home owners",
    "Climate and natural disaster risk in vacation market selection",
    "Fractional ownership emerging as alternative to full vacation property purchase",
  ],
  "Luxury New Construction": [
    "Custom home build timelines extending — managing buyer expectations",
    "Spec home inventory at luxury price points sitting longer",
    "Design-build partnership value for buyers who want true customization",
    "Luxury community amenities driving presale reservation activity",
    "Builder warranty and post-close service — the differentiator in luxury new construction",
    "Upgrade and finish selection ROI — what adds value and what doesn't",
    "Architectural style demand shifting — what luxury buyers want now",
    "Pre-construction pricing advantage narrowing as supply catches up",
  ],

  # ── LIFECYCLE & DEMOGRAPHIC ───────────────────────────────────────────────────
  "Divorce & Separation": [
    "Couple needs to sell the family home as part of a settlement",
    "One spouse wants to buy out the other — is it financially viable?",
    "Sensitive timeline — court-ordered sale deadline approaching",
    "Emotional attachment to the home complicating the decision",
    "Children in the picture — school district decisions matter",
    "Credit impact of divorce affecting buying power post-settlement",
    "QDRO and retirement asset division intersecting with real estate equity",
    "Coordinating with divorce attorneys — how agents can add value",
  ],
  "Probate & Inherited Homes": [
    "Family inherited a home and doesn't know what to do with it",
    "Executor needs to sell quickly to settle an estate",
    "Inherited property needs significant repairs before listing",
    "Multiple heirs disagreeing on whether to sell or keep",
    "Out-of-state heirs trying to manage a local property remotely",
    "Probate timeline creating urgency to sell",
    "Tax implications of inherited property creating confusion",
    "As-is sale vs. fix-up — helping heirs make the financial decision",
  ],
  "Empty Nesters & Downsizing": [
    "Kids are out — now what? The emotional and financial downsizing conversation",
    "Equity harvest — tapping decades of appreciation to fund retirement",
    "Maintenance burden of large home becoming the tipping point",
    "Active adult communities offering lifestyle that surprises skeptics",
    "Selling the family home — managing sentiment and market timing together",
    "Cost of living reduction as retirement income planning strategy",
    "Condos and townhomes as right-sizing solutions for empty nesters",
    "Geographic downsizing — moving to lower-cost market in retirement",
  ],
  "Young Professionals": [
    "First property as wealth-building foundation — starting the conversation early",
    "Urban condo vs. suburban starter home — the honest trade-off analysis",
    "Career mobility and real estate — when buying makes sense despite uncertainty",
    "Roommate strategy to qualify for a larger mortgage",
    "Student debt and homeownership — navigating the qualification math",
    "First condo as investment — house-hacking in an urban market",
    "Tech-forward home search tools young professionals actually use",
    "Building credit and savings simultaneously — the pre-purchase roadmap",
  ],
  "Families with Children": [
    "School district quality as the primary location driver",
    "Safe neighborhood data — how families research and what actually matters",
    "Room-to-grow strategy — buying ahead of the next life stage",
    "Proximity to family support networks influencing location decisions",
    "Backyard and outdoor space moving up the priority list post-pandemic",
    "Multi-generational floor plan demand increasing as parents age",
    "Community amenities — pools, parks, sports — driving neighborhood choice",
    "Future resale planning — buying in family-friendly locations for liquidity",
  ],

  # ── SITUATIONAL & DISTRESSED ──────────────────────────────────────────────────
  "Pre-Foreclosure & Hardship": [
    "Homeowner behind on payments — options that most people don't know exist",
    "Short sale as a dignity-preserving alternative to foreclosure",
    "Cash offer timeline giving distressed sellers a way out",
    "Loan modification vs. selling — helping owners understand their choices",
    "Foreclosure timeline — when delay becomes the enemy",
    "Rebuilding credit and confidence after financial hardship",
    "Job loss creating sudden housing urgency — rapid response options",
    "Medical expense burden forcing housing decisions",
  ],
  "Estate & Probate Sales": [
    "Family inherited a home and doesn't know what to do with it",
    "Executor timeline pressure — probate courts don't wait",
    "Out-of-state heirs managing a local property remotely",
    "As-is estate sale vs. preparing the property — the financial case",
    "Multiple heirs with conflicting priorities — neutral representation value",
    "Estate attorney coordination — how real estate professionals add value",
    "Hoarding or deferred maintenance — handling sensitive property conditions",
    "Estate liquidation coordination beyond the real estate transaction",
  ],
  "Care-Driven Transitions": [
    "Health event forcing a rapid housing transition for a senior",
    "Family caregivers coordinating a parent's move from a distance",
    "Memory care transition — selling the family home to fund care",
    "Aging-in-place modifications vs. the decision to move",
    "Power of attorney situation — navigating real estate decisions for a loved one",
    "Senior move management — the logistics most families underestimate",
    "Care facility proximity driving location decisions for the next home",
    "Family consensus breakdown — helping all parties reach alignment",
  ],
  "Emergency Relocation": [
    "Job loss requiring a fast sale to preserve financial stability",
    "Sudden employer relocation — selling and buying on compressed timeline",
    "Divorce forcing an immediate housing transition",
    "Natural disaster or fire displacing a family unexpectedly",
    "Cash offer options for sellers who can't afford to wait for retail buyers",
    "Temporary housing bridge while permanent situation is resolved",
    "Cross-country move with no local market knowledge — remote buying strategy",
    "iBuyer vs. traditional sale — the honest speed and net proceeds comparison",
  ],

  # ── INVESTMENT ─────────────────────────────────────────────────────────────────
  "Fix & Flip": [
    "ARV analysis — finding deals where the numbers actually work",
    "Contractor reliability — the biggest risk in every flip",
    "Hard money lending — rate and terms to understand before committing",
    "Permit vs. non-permit renovation decisions and their resale implications",
    "Neighborhood selection for flips — where buyers are actively competing",
    "Days on market creeping up — pricing strategy for flipped homes",
    "Material cost inflation squeezing flip margins — adaptation strategies",
    "Distressed property sourcing — finding deals before they hit MLS",
  ],
  "Long-Term Rentals (BRRRR)": [
    "BRRRR strategy execution — finding the right buy-rehab-rent sequence",
    "Cash flow positive markets getting harder to find — where to look",
    "Refinance timing in a higher rate environment — the BRRRR math still works here",
    "Tenant quality as the most important variable in long-term rental success",
    "Property management self-manage vs. hire — the real cost comparison",
    "Scaling from one to five properties — the systems that make it possible",
    "Off-market sourcing strategy for long-term rental acquisitions",
    "Market rent analysis — leaving money on the table is common",
  ],
  "Short-Term Rentals / Airbnb": [
    "STR regulation changes reshaping which markets pencil",
    "Revenue projection tools — separating realistic from optimistic forecasts",
    "Furnishing and setup investment — what guests actually care about",
    "Seasonal pricing strategy that maximizes annual revenue",
    "HOA and condo restrictions on short-term rentals — due diligence matters",
    "Platform fee and tax changes affecting STR net returns",
    "Competitor analysis — understanding your market before buying",
    "Transitioning a long-term rental to STR — the conversion playbook",
  ],
  "Mid-Term Rentals": [
    "Travel nurse housing demand creating reliable mid-term rental income",
    "Corporate housing demand in markets with large employer presence",
    "Furnished rental premium — the math vs. unfurnished long-term",
    "30-day minimum stay rules — navigating local STR restrictions",
    "Platform strategy for mid-term rental marketing",
    "Tenant profile for mid-term rentals — understanding your customer",
    "Lease structure for 30-90 day stays — what to include",
    "Mid-term rental as bridge strategy for properties between long-term tenants",
  ],
  "1031 Exchange": [
    "45-day identification deadline — the clock starts at closing",
    "Qualified intermediary selection — the most overlooked step in an exchange",
    "Like-kind property rules — broader than most investors realize",
    "Boot minimization strategy — keeping the exchange fully tax-deferred",
    "Delaware Statutory Trust as 1031 replacement property option",
    "Failed exchange consequences — and how to avoid them",
    "Multi-property identification rules — the three options investors can use",
    "Up-leg property selection — aligning replacement property with investment goals",
  ],
  "Opportunity Zones": [
    "Opportunity Zone investment window — understanding the remaining tax benefit timeline",
    "Qualified Opportunity Fund structure — direct investment vs. fund participation",
    "Community impact narrative — OZ investment as mission-aligned capital",
    "Development project due diligence in OZ — additional complexity to manage",
    "OZ compliance requirements — the 10-year hold and its implications",
    "Urban infill OZ opportunities often overlooked by institutional capital",
    "Rural Opportunity Zones — less competition, strong demographic tailwinds",
    "Pairing OZ investment with other tax strategies for maximum benefit",
  ],

  # ── TECHNOLOGY & INFRASTRUCTURE ───────────────────────────────────────────────
  "Data Centers": [
    "Power availability becoming the primary site selection constraint",
    "Mission-critical uptime requirements reshaping lease structure",
    "Cooling infrastructure cost and complexity driving build-to-suit demand",
    "Hyperscaler expansion creating significant land and building demand",
    "AI workload growth driving unprecedented data center development pipeline",
    "Special-use industrial zoning requirements for data center development",
    "Power purchase agreements and utility partnership as competitive differentiator",
    "Data center REIT market consolidation creating acquisition opportunity",
  ],
  "Colocation Facilities": [
    "Enterprise IT teams evaluating colo vs. cloud for cost optimization",
    "Colocation lease negotiation — power, cooling, and SLA terms that matter",
    "Cross-connect and interconnection as strategic competitive advantage",
    "Multi-tenant data center market consolidating around tier-certified operators",
    "AI and GPU compute demand reshaping colocation space requirements",
    "Colocation pricing pressure as hyperscalers build their own capacity",
    "Carrier-neutral facilities commanding premium in connectivity-sensitive markets",
    "Enterprise exit from owned data centers driving colocation demand surge",
  ],
  "Hyperscale Campuses": [
    "Hyperscaler land acquisition moving 200+ miles from traditional markets",
    "Power infrastructure investment as prerequisite for hyperscale site selection",
    "Water availability and sustainability requirements for cooling systems",
    "Fiber and network connectivity as non-negotiable hyperscale site criteria",
    "Tax incentive competition among states and municipalities for hyperscale investment",
    "Zoning and permitting complexity for large-scale data center campuses",
    "Build-to-suit lease structure for hyperscale — terms that differ from standard industrial",
    "AI infrastructure investment driving hyperscale development acceleration",
  ],
  "Edge Data Centers": [
    "Latency requirements driving edge deployment closer to population centers",
    "5G infrastructure rollout creating co-location demand for edge nodes",
    "Urban edge data center siting — zoning, power, and neighbor considerations",
    "Micro data center lease structures — smaller footprint, specialized terms",
    "Carrier-neutral edge facilities attracting multiple operator interest",
    "Last-mile connectivity demands pushing compute infrastructure to the edge",
    "Autonomous vehicle and IoT applications creating new edge demand drivers",
    "Edge vs. centralized — helping clients understand the hybrid infrastructure decision",
  ],
  "Powered Shells": [
    "Industrial shell conversion to data center — feasibility analysis framework",
    "Power delivery infrastructure investment required before tenant occupancy",
    "Zoning compliance for data center use in industrial-designated parcels",
    "Spec powered shell development — meeting the market before tenants arrive",
    "Investor underwriting for powered shell development — the risk/return case",
    "Build-to-suit powered shell — structuring the development agreement",
    "Existing industrial building assessment — can it support data center power loads",
    "Powered shell pre-leasing strategy to secure development financing",
  ],
  "Cloud Infrastructure Real Estate": [
    "Cloud region expansion creating concentrated real estate demand in select markets",
    "Long-term ground lease strategy for cloud campus development",
    "Power and sustainability commitments driving cloud provider site selection",
    "Market selection criteria for cloud region deployment",
    "Land aggregation strategy in advance of announced cloud expansion",
    "Infrastructure REIT relationships with major cloud providers",
    "Public cloud provider capex cycle — understanding the real estate timing",
    "Renewable energy access as a cloud infrastructure site selection driver",
  ],
  "Telecom & Fiber Infrastructure": [
    "Fiber network expansion creating easement and right-of-way opportunity",
    "Tower and antenna site leasing — lease terms evolving with 5G buildout",
    "Carrier hotel demand growing as networks densify",
    "Dark fiber asset evaluation — owned infrastructure vs. leased capacity",
    "Telecom facility sale-leaseback creating capital for network operators",
    "Municipal broadband investment creating new real estate partnerships",
    "Fiber-to-the-premises buildout driving last-mile infrastructure demand",
    "Telecom REIT consolidation reshaping the tower and fiber ownership landscape",
  ],
  "Network Facilities": [
    "Internet exchange point expansion creating colocation demand in tier-2 markets",
    "Carrier-neutral exchange strategy for operators seeking redundancy",
    "Network operations center space requirements and site criteria",
    "Peering strategy influencing facility location and lease decisions",
    "Redundant network path planning driving multi-site facility strategy",
    "Managed services growth increasing demand for purpose-built network facilities",
    "Edge peering demand growing as content delivery networks expand",
    "Network facility lease terms — what operators need that standard industrial doesn't provide",
  ],

    # ── LEGACY KEYS (backward compatibility) ──────────────────────────────────
    "Seniors & Downsizing": [
        "Seniors asking: is now the right time to sell?",
        "Empty nesters ready to rightsize — but don't know where to start",
        "Rising home values creating unexpected equity for long-term owners",
        "Family asking mom or dad to consider moving closer",
        "Health changes making the current home harder to manage",
        "Senior living options expanding — more choices than ever",
    ],
    "Probate & Inherited Homes": [
        "Family inherited a home and doesn't know what to do with it",
        "Executor needs to sell quickly to settle an estate",
        "Multiple heirs disagreeing on whether to sell or keep",
        "Out-of-state heirs trying to manage a local property remotely",
        "Tax implications of inherited property creating confusion",
    ],
    "Divorce & Separation": [
        "Couple needs to sell the family home as part of a settlement",
        "Sensitive timeline — court-ordered sale deadline approaching",
        "Credit impact of divorce affecting buying power",
    ],
    "Relocation": [
        "Corporate relocation with a tight move-in timeline",
        "Family relocating from out of state — buying sight unseen",
        "Military PCS orders creating urgent need to buy or sell",
    ],
    "Luxury": [
        "High-net-worth buyers prioritizing privacy and off-market access",
        "Luxury market showing resilience despite rate environment",
        "Confidential listing opportunities for sellers valuing discretion",
    ],
    "First-Time Buyers": [
        "First-time buyers overwhelmed by the current market",
        "Down payment assistance programs many buyers don't know exist",
        "Rent vs. buy analysis shifting in buyer's favor",
    ],
    "Investors": [
        "Cash flow opportunities emerging in current market",
        "BRRRR strategy buyers looking for the right property",
        "1031 exchange opportunities for portfolio repositioning",
    ],
    "Veterans": [
        "VA loan benefits many veterans don't fully understand",
        "PCS orders creating time-sensitive buying and selling needs",
        "Zero down payment still possible in today's market",
    ],
    "New Construction": [
        "Builder incentives creating real opportunity for buyers",
        "New construction vs. resale — the honest comparison",
        "Builder contract review — what buyers miss",
    ],
    "Move-Up Buyers": [
        "Growing family needs more space — timing the sell and buy",
        "Equity in current home creating move-up opportunity",
        "Bridge loan options for buyers who need to buy before selling",
    ],
    "Distressed / Pre-Foreclosure": [
        "Homeowner behind on payments — options before foreclosure",
        "Short sale as an alternative to foreclosure",
        "Cash offer timeline giving distressed sellers a way out",
    ],
    "Land & Rural": [
        "Buyers seeking land for homesteading or rural lifestyle",
        "Zoning and land use questions slowing rural transactions",
        "Rural financing challenges and solutions",
    ],
    "Short-Term Rentals": [
        "STR regulations tightening in popular markets",
        "Revenue projection tools helping buyers evaluate STR potential",
        "HOA and condo restrictions on short-term rentals",
    ],
    "Green / Energy Efficient Homes": [
        "Solar panels — impact on home value and sale",
        "Energy audit results driving buyer decisions",
        "Net-zero homes entering mainstream market",
    ],
}

DEFAULT_SITUATIONS = [
    "Market conditions creating new opportunity for prepared clients",
    "Technology and AI changing how professionals reach their audience",
    "Interest rate environment requiring updated client education",
    "Supply and demand dynamics shifting in this asset class",
    "Regulatory changes creating urgency for informed decision-making",
    "Capital markets activity creating transaction opportunity",
]




@router.get("/situations")
async def get_situations(niche: Optional[str] = None):
    """
    Return niche-aware situation options.
    If niche is provided, return situations specific to that niche.
    Falls back to default situations if niche not found.
    """
    if niche and niche in NICHE_SITUATIONS:
        situations = NICHE_SITUATIONS[niche]
    else:
        # Try partial match
        matched = next(
            (v for k, v in NICHE_SITUATIONS.items() if niche and niche.lower() in k.lower()),
            None
        )
        situations = matched if matched else DEFAULT_SITUATIONS

    return {"niche": niche, "situations": situations}


# ─────────────────────────────────────────────
# MAIN GENERATE ENDPOINT
# ─────────────────────────────────────────────
@router.post("/generate-content", response_model=ContentResponse)
async def generate_content(payload: ContentRequest) -> ContentResponse:
    """
    Main content generation endpoint.
    Builds identity-aware prompt, generates content via Claude,
    runs automatic compliance check, returns content + compliance badges.
    """
    try:
        client = _get_anthropic_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    prompt = _build_content_prompt(payload)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1800,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error calling Claude: {str(e)}")

    try:
        content_blocks = response.content or []
        text_chunks = [
            block.text
            for block in content_blocks
            if getattr(block, "type", "") == "text"
        ]
        raw_text = "\n\n".join(text_chunks).strip()
        if not raw_text:
            raise ValueError("Claude returned empty content.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing Claude response: {str(e)}")

    # ── Run automatic compliance check
    profile    = payload.agentProfile or AgentProfileModel()
    agent_name = profile.agentName or ""
    brokerage  = profile.brokerage  or ""
    mls_names  = profile.mlsNames   or []
    compliance = _run_compliance_check(raw_text, agent_name, brokerage, mls_names)

    try:
        return _parse_claude_output(raw_text, compliance)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error structuring content response: {str(e)}")


# ─────────────────────────────────────────────
# CORE GENERATION — callable by scheduler
# without going through HTTP layer
# ─────────────────────────────────────────────
def generate_content_core(
    agent_name:   str,
    brokerage:    str,
    market:       str       = "",
    niche:        str       = "",
    situation:    str       = "",
    persona:      str       = "homeowners",
    tone:         str       = "Professional",
    length:       str       = "Standard",
    trends:       list      = None,
    brand_voice:  str       = "",
    short_bio:    str       = "",
    audience:     str       = "",
    words_avoid:  str       = "",
    words_prefer: str       = "",
    mls_names:    list      = None,
) -> dict:
    """
    Generate content and run compliance check.
    Returns a dict with 'content' and 'compliance' keys.
    Used by the scheduler — no HTTP, no Depends(), no await.
    """
    from pydantic import BaseModel as _BM

    profile = AgentProfileModel(
        agentName          = agent_name,
        brokerage          = brokerage,
        market             = market,
        bio                = short_bio,
        brandVoice         = brand_voice,
        audienceDescription= audience,
        wordsAvoid         = words_avoid,
        wordsPrefer        = words_prefer,
        primaryNiches      = [niche] if niche else [],
        trends             = trends or [],
        persona            = persona,
        tone               = tone,
        length             = length,
        mlsNames           = mls_names or [],
    )

    payload = ContentRequest(
        niche        = niche,
        situation    = situation,
        agentProfile = profile,
    )

    client = _get_anthropic_client()
    prompt = _build_content_prompt(payload)

    response = client.messages.create(
        model      = "claude-sonnet-4-20250514",
        max_tokens = 1800,
        messages   = [{"role": "user", "content": prompt}],
    )

    text_chunks = [
        block.text for block in (response.content or [])
        if getattr(block, "type", "") == "text"
    ]
    raw_text = "\n\n".join(text_chunks).strip()
    if not raw_text:
        raise ValueError("Claude returned empty content")

    compliance = _run_compliance_check(raw_text, agent_name, brokerage, mls_names or [])
    content_response = _parse_claude_output(raw_text, compliance)

    return {
        "content":    content_response.dict(),
        "compliance": compliance.dict(),
    }
