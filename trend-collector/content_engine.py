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
    "Seniors & Downsizing": [
        "Seniors are asking: is now the right time to sell?",
        "Empty nesters ready to rightsize — but don't know where to start",
        "Rising home values creating unexpected equity for long-term owners",
        "Family asking mom or dad to consider moving closer",
        "Health changes making the current home harder to manage",
        "Interest rates affecting downsizing math — is it still worth it?",
        "Senior living options expanding — more choices than ever",
    ],
    "Probate & Inherited Homes": [
        "Family inherited a home and doesn't know what to do with it",
        "Executor needs to sell quickly to settle an estate",
        "Inherited property needs significant repairs before listing",
        "Multiple heirs disagreeing on whether to sell or keep",
        "Out-of-state heirs trying to manage a local property remotely",
        "Probate timeline creating urgency to sell",
        "Tax implications of inherited property creating confusion",
    ],
    "Divorce & Separation": [
        "Couple needs to sell the family home as part of a settlement",
        "One spouse wants to buy out the other — is it financially viable?",
        "Sensitive timeline — court-ordered sale deadline approaching",
        "Emotional attachment to the home complicating the decision",
        "Children in the picture — school district decisions matter",
        "Credit impact of divorce affecting buying power",
    ],
    "Relocation": [
        "Corporate relocation with a tight move-in timeline",
        "Family relocating from out of state — buying sight unseen",
        "Military PCS orders creating urgent need to buy or sell",
        "Remote work opening up new markets for relocating buyers",
        "Cost of living comparison driving relocation decisions",
        "Neighborhood and school research for incoming families",
    ],
    "Luxury": [
        "High-net-worth buyers prioritizing privacy and off-market access",
        "Luxury market showing resilience despite rate environment",
        "Second home and investment property demand among affluent buyers",
        "Lifestyle-driven search — location, amenities, architecture",
        "Confidential listing opportunities for sellers valuing discretion",
        "International buyers entering the local luxury market",
    ],
    "First-Time Buyers": [
        "First-time buyers overwhelmed by the current market",
        "Down payment assistance programs many buyers don't know exist",
        "Rent vs. buy analysis shifting in buyer's favor",
        "Interest rate confusion — buyers waiting for the perfect moment",
        "Credit score questions holding buyers back unnecessarily",
        "New construction as an alternative to competitive resale market",
    ],
    "Investors": [
        "Cash flow opportunities emerging in current market",
        "BRRRR strategy buyers looking for the right property",
        "Short-term rental regulations changing investor calculus",
        "Rising rents making investment property more attractive",
        "1031 exchange opportunities for portfolio repositioning",
        "Off-market deals — how serious investors find them",
    ],
    "Veterans": [
        "VA loan benefits many veterans don't fully understand",
        "PCS orders creating time-sensitive buying and selling needs",
        "Zero down payment still possible in today's market",
        "VA appraisal process — what buyers need to know",
        "Transitioning from military to civilian housing market",
        "Surviving spouse VA loan eligibility often overlooked",
    ],
    "New Construction": [
        "Builder incentives creating real opportunity for buyers",
        "New construction vs. resale — the honest comparison",
        "Lot selection and upgrade decisions overwhelming buyers",
        "Builder contract review — what buyers miss",
        "Construction timeline delays affecting buyer plans",
        "Warranty walkthrough — what to look for at closing",
    ],
    "Move-Up Buyers": [
        "Growing family needs more space — timing the sell and buy",
        "Equity in current home creating move-up opportunity",
        "Bridge loan options for buyers who need to buy before selling",
        "School district driving the move-up decision",
        "Contingency offers in a competitive market",
        "Interest rate impact on move-up affordability",
    ],
    "Distressed / Pre-Foreclosure": [
        "Homeowner behind on payments — options before foreclosure",
        "Short sale as an alternative to foreclosure",
        "Cash offer timeline giving distressed sellers a way out",
        "Loan modification vs. selling — helping owners understand choices",
        "Foreclosure timeline creating urgency for action",
        "Rebuilding after hardship — what comes next",
    ],
    "Land & Rural": [
        "Buyers seeking land for homesteading or rural lifestyle",
        "Zoning and land use questions slowing rural transactions",
        "Agricultural exemption opportunities for rural buyers",
        "Septic and well due diligence — what buyers need to know",
        "Rural financing challenges and solutions",
        "Survey and boundary issues common in rural transactions",
    ],
    "Short-Term Rentals": [
        "STR regulations tightening in popular markets",
        "Revenue projection tools helping buyers evaluate STR potential",
        "Furnishing and setup costs affecting STR ROI",
        "Seasonal pricing strategy maximizing STR income",
        "HOA and condo restrictions on short-term rentals",
        "Transitioning a long-term rental to STR",
    ],
    "Green / Energy Efficient Homes": [
        "Solar panels — impact on home value and sale",
        "Energy audit results driving buyer decisions",
        "Green financing options many buyers don't know about",
        "Net-zero homes entering mainstream market",
        "Utility savings becoming a marketing differentiator",
        "EV charging infrastructure as a buyer priority",
    ],
}

DEFAULT_SITUATIONS = [
    "Market update — prices are shifting in your favor",
    "Low inventory creating urgency for serious buyers",
    "Interest rate changes affecting buyer decisions",
    "Spring market heating up — now is the time to act",
    "Local development changing neighborhood values",
    "AI and search engines changing how buyers find agents",
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
