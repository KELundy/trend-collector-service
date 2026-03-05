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
CRITICAL IDENTITY RULES
───────────────────────
1. The agent's name ({agent_name}) must appear naturally in the content — in the post,
   CTA, or script — the way a skilled copywriter would reference it. Not robotically.
2. {f"The brokerage name ({brokerage}) must appear somewhere in the content — in the post footer, CTA, or script — as a natural disclosure, not a forced mention." if brokerage else ""}
3. {f"The market ({market}) must be referenced specifically — not generically. Say '{market}' not 'your local area'." }
4. Content must feel written FOR this specific agent, not as a generic template.
5. Content must feel locally and situationally relevant — specific to this niche and moment.
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

OUTPUT FORMAT
─────────────
Write exactly six sections separated by two blank lines.
NO labels. NO headings. NO brackets. NO numbers. NO explanations.
Write in this exact order:

1. A compelling, niche-specific headline (one sentence, no period)
2. A vivid thumbnail/image concept (one to two sentences describing the visual)
3. Hashtags (space-separated, 8-12 tags, mix of niche + location + broad)
4. A platform-ready social post (naturally includes agent name and brokerage disclosure)
5. A specific, action-oriented call to action (includes agent name or contact signal)
6. A 45-75 second spoken script written as natural, conversational dialogue

Each section must contain real, specific content — never placeholders or generic text.
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
# OUTPUT PARSER
# ─────────────────────────────────────────────
def _parse_claude_output(raw_text: str, compliance: ComplianceBadge) -> ContentResponse:
    parts = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    while len(parts) < 6:
        parts.append("")

    headline, thumbnail, hashtags, post, cta, script = parts[:6]

    return ContentResponse(
        headline=headline,
        thumbnailIdea=thumbnail,
        hashtags=hashtags,
        post=post,
        cta=cta,
        script=script,
        compliance=compliance,
        generated_at=datetime.utcnow(),
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

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>HomeBridge Content Engine</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Roboto+Condensed:wght@700&display=swap" rel="stylesheet" />
  <style>
    :root {
      --purple: rgb(88, 82, 149);
      --green: rgb(109, 190, 76);
      --aqua: rgb(76, 192, 176);
      --gray: rgb(200, 200, 200);
      --bg: #ffffff;
      --panel-bg: #ffffff;
      --border-subtle: #e3e5ec;
      --border-strong: #c8c8c8;
      --text-main: #1f2430;
      --text-muted: #6b7280;
      --accent: var(--aqua);
      --accent-soft: rgba(76, 192, 176, 0.08);
      --accent-strong: var(--purple);
      --shadow-soft: 0 10px 30px rgba(15, 23, 42, 0.08);
      --radius-lg: 14px;
      --radius-md: 10px;
      --radius-pill: 999px;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Roboto", system-ui, sans-serif; background: var(--bg); color: var(--text-main); }
    .app-shell { display: flex; min-height: 100vh; }

    /* ── SIDEBAR ── */
    .sidebar { width: 240px; background: var(--purple); color: #f9fafb; display: flex; flex-direction: column; padding: 20px 16px; position: sticky; top: 0; height: 100vh; overflow-y: auto; flex-shrink: 0; }
    .sidebar-header { margin-bottom: 24px; }
    .sidebar-title { font-family: "Roboto Condensed", sans-serif; font-size: 18px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
    .sidebar-subtitle { font-size: 11px; color: #e5e7eb; margin-top: 4px; }
    .nav-section-label { font-family: "Roboto Condensed", sans-serif; font-size: 10px; text-transform: uppercase; letter-spacing: 0.16em; color: #9ca3af; margin: 16px 0 6px; }
    .nav-list { list-style: none; padding: 0; margin: 0; }
    .nav-item { margin-bottom: 4px; }
    .nav-button { width: 100%; border: none; background: transparent; color: #f9fafb; text-align: left; padding: 9px 10px; border-radius: 8px; font-size: 13px; display: flex; align-items: center; gap: 8px; cursor: pointer; transition: background 0.15s, border-left 0.15s; font-family: "Roboto Condensed", sans-serif; letter-spacing: 0.04em; }
    .nav-button.active { background: rgba(255,255,255,0.10); color: #fff; border-left: 3px solid var(--aqua); padding-left: 7px; }
    .nav-button:hover:not(.active) { background: rgba(255,255,255,0.06); }
    .nav-divider { border: none; border-top: 1px solid rgba(255,255,255,0.12); margin: 10px 0; }
    .sidebar-footer { margin-top: auto; font-size: 10px; color: #9ca3af; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.12); }

    /* ── MAIN ── */
    .main { flex: 1; padding: 24px 28px; display: flex; justify-content: center; align-items: flex-start; min-width: 0; }
    .panel { width: 100%; max-width: 980px; background: var(--panel-bg); border-radius: 18px; box-shadow: var(--shadow-soft); padding: 22px 24px 28px; border: 1px solid var(--border-subtle); display: none; }
    .panel.active { display: block; }
    .panel-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; }
    .panel-title { font-family: "Roboto Condensed", sans-serif; font-size: 20px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
    .panel-subtitle { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
    .panel-tag { font-family: "Roboto Condensed", sans-serif; font-size: 11px; text-transform: uppercase; letter-spacing: 0.12em; color: var(--accent-strong); background: var(--accent-soft); padding: 4px 10px; border-radius: var(--radius-pill); white-space: nowrap; }
    .panel-body { display: flex; flex-direction: column; gap: 16px; }

    /* ── INLINE ERROR ── */
    .inline-error { background: #fef2f2; border: 1px solid #fca5a5; color: #dc2626; border-radius: 8px; padding: 10px 14px; font-size: 13px; display: none; }
    .inline-error.visible { display: block; }

    /* ── FIELD GROUPS ── */
    .field-group { border-radius: var(--radius-md); border: 1px solid var(--border-subtle); padding: 14px 14px 12px; background: #fff; }
    .field-label { font-family: "Roboto Condensed", sans-serif; font-size: 12px; font-weight: 700; margin-bottom: 5px; letter-spacing: 0.06em; text-transform: uppercase; }
    .field-hint { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; }
    input[type="text"], textarea { width: 100%; padding: 8px 9px; border-radius: 8px; border: 1px solid var(--border-strong); font-size: 13px; font-family: "Roboto", sans-serif; color: var(--text-main); background: #fff; }
    textarea { min-height: 68px; resize: vertical; }
    input:focus, textarea:focus, select:focus { outline: none; border-color: var(--aqua); box-shadow: 0 0 0 1px rgba(76,192,176,0.25); }
    .select-wrapper { position: relative; display: inline-block; width: 100%; }
    .select-wrapper select { appearance: none; width: 100%; padding: 10px 36px 10px 12px; border-radius: 8px; border: 1px solid var(--border-strong); background: #fff; font-size: 13px; cursor: pointer; font-family: "Roboto", sans-serif; color: var(--text-main); }
    .select-arrow { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); font-size: 14px; color: var(--text-muted); pointer-events: none; }

    /* ── CHIPS ── */
    .chip-row { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 8px; }
    .chip { display: inline-flex; align-items: center; padding: 5px 11px; font-size: 12px; border-radius: var(--radius-pill); background: #fff; border: 1px solid var(--border-strong); color: var(--text-main); cursor: pointer; transition: all 0.15s; user-select: none; }
    .chip:hover { background: rgba(76,192,176,0.06); border-color: var(--aqua); }
    .chip.selected { background: var(--accent-soft); border-color: var(--accent-strong); color: var(--accent-strong); font-weight: 600; }
    .chip-remove { font-size: 13px; cursor: pointer; color: var(--text-muted); margin-left: 5px; line-height: 1; }
    .empty-text { font-size: 12px; color: var(--text-muted); font-style: italic; margin-top: 4px; }

    /* ── BUTTONS ── */
    .btn-primary { background: var(--green); color: #fff; border: none; border-radius: var(--radius-pill); padding: 9px 20px; font-size: 13px; cursor: pointer; font-family: "Roboto Condensed", sans-serif; letter-spacing: 0.08em; text-transform: uppercase; transition: background 0.15s, box-shadow 0.15s, transform 0.1s; }
    .btn-primary:hover { background: rgb(95,170,62); box-shadow: 0 4px 10px rgba(109,190,76,0.3); }
    .btn-primary:active { transform: scale(0.97); }
    .btn-primary:disabled { background: #9ca3af; cursor: not-allowed; transform: none; box-shadow: none; }
    .btn-secondary { background: #fff; color: var(--accent-strong); border-radius: var(--radius-pill); padding: 8px 16px; font-size: 12px; border: 1px solid var(--border-strong); cursor: pointer; font-family: "Roboto Condensed", sans-serif; letter-spacing: 0.06em; text-transform: uppercase; transition: background 0.15s; }
    .btn-secondary:hover { background: #f3f4f6; }
    .button-row { display: flex; gap: 10px; margin-top: 8px; flex-wrap: wrap; }

    /* ── IDENTITY SUMMARY ── */
    .identity-summary { border-radius: var(--radius-md); border: 1px solid var(--border-subtle); background: #fff; padding: 14px; }
    .identity-summary-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .identity-summary-title { font-family: "Roboto Condensed", sans-serif; font-size: 12px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--text-muted); }
    .identity-summary-edit { font-size: 12px; color: var(--accent-strong); cursor: pointer; font-weight: 500; }
    .identity-summary-empty { font-size: 13px; color: var(--text-muted); font-style: italic; }
    #identity-summary-content .parent-category { font-weight: 600; font-size: 13px; margin: 10px 0 3px 0; padding-top: 8px; color: var(--text-main); border-top: 1px solid var(--border-subtle); }
    #identity-summary-content .parent-category:first-child { border-top: none; padding-top: 0; margin-top: 0; }
    #identity-summary-content .sub-item { margin-left: 16px; font-size: 12px; color: var(--text-muted); padding: 1px 0; }

    /* ── NICHE SELECTOR (Content Engine) ── */
    .niche-selector-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
    .niche-select-chip { display: inline-flex; align-items: center; padding: 7px 14px; font-size: 13px; border-radius: var(--radius-pill); background: #fff; border: 2px solid var(--border-strong); color: var(--text-main); cursor: pointer; transition: all 0.15s; font-weight: 500; }
    .niche-select-chip:hover { border-color: var(--aqua); background: rgba(76,192,176,0.05); }
    .niche-select-chip.active { background: var(--accent-soft); border-color: var(--accent-strong); color: var(--accent-strong); }

    /* ── CONTENT SETTINGS ROW ── */
    .content-settings-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 4px; }
    @media (max-width: 700px) { .content-settings-row { grid-template-columns: 1fr; } }

    /* ── CONTENT ENGINE LAYOUT ── */
    .content-engine-layout { display: flex; gap: 20px; align-items: flex-start; margin-top: 16px; }
    .generated-content-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; flex: 1; min-width: 0; }
    @media (max-width: 960px) { .content-engine-layout { flex-direction: column; } }
    @media (max-width: 700px) { .generated-content-grid { grid-template-columns: 1fr; } }

    /* ── CONTENT CARDS ── */
    .content-card { background: #fff; border: 1px solid var(--border-subtle); border-radius: 12px; padding: 14px 16px; box-shadow: 0 2px 6px rgba(15,23,42,0.05); display: flex; flex-direction: column; min-height: 110px; }
    .content-card-title { font-family: "Roboto Condensed", sans-serif; font-size: 13px; font-weight: 700; color: var(--text-main); margin-bottom: 6px; letter-spacing: 0.08em; text-transform: uppercase; }
    .content-card.edited .content-card-title::after { content: " ✎"; color: var(--aqua); font-size: 12px; }
    .content-card-actions { display: flex; gap: 6px; margin-bottom: 6px; }
    .card-copy-btn, .card-reset-btn { font-size: 10px; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border-subtle); background: #f8f8f8; cursor: pointer; font-family: "Roboto Condensed", sans-serif; letter-spacing: 0.06em; text-transform: uppercase; transition: background 0.15s; }
    .card-copy-btn:hover, .card-reset-btn:hover { background: #efefef; }
    .content-card-body { font-size: 13px; line-height: 1.5; color: var(--text-main); white-space: pre-wrap; flex: 1; border: 1px solid transparent; padding: 5px; border-radius: 6px; transition: border-color 0.15s, background 0.15s; min-height: 36px; }
    .content-card-body:focus { outline: none; border-color: var(--border-strong); background: #fafafa; }
    .content-card-body.empty { color: var(--text-muted); font-style: italic; }
    .content-card-body.loading { color: var(--aqua); font-style: italic; }

    /* ── STAGING PANEL ── */
    .staging-panel { width: 300px; flex-shrink: 0; background: #fff; border: 1px solid var(--gray); border-radius: 12px; padding: 18px; box-shadow: var(--shadow-soft); position: sticky; top: 20px; display: none; }
    .staging-panel.visible { display: block; }
    .staging-title { font-family: "Roboto Condensed", sans-serif; font-size: 16px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent-strong); margin-bottom: 4px; }
    .staging-subtitle { font-size: 12px; color: var(--text-muted); margin-bottom: 14px; line-height: 1.4; }
    .staging-panel-body { display: flex; flex-direction: column; gap: 12px; }
    .pill-row { display: flex; gap: 8px; margin-top: 4px; }
    .pill { border-radius: 999px; border: 1px solid var(--border-subtle); padding: 5px 12px; font-size: 12px; background: #f9fafb; cursor: pointer; font-family: "Roboto Condensed", sans-serif; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-main); transition: all 0.15s; }
    .pill.pill-selected { background: var(--accent-soft); border-color: var(--accent-strong); color: var(--accent-strong); }
    .staging-footer { margin-top: 16px; }
    .staging-footer .btn-primary { width: 100%; }
    .side-panel-header { position: relative; margin-bottom: 12px; }
    .side-panel-header h2 { margin: 0 0 3px; font-size: 16px; font-weight: 700; font-family: "Roboto Condensed", sans-serif; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent-strong); }
    .side-panel-subtitle { font-size: 12px; color: var(--text-muted); line-height: 1.4; }
    .side-panel-close { position: absolute; right: 0; top: 0; background: transparent; border: none; font-size: 18px; color: var(--text-muted); cursor: pointer; line-height: 1; }
    .side-panel-body { display: flex; flex-direction: column; gap: 12px; }
    .side-panel-body .field-group label { display: block; font-size: 12px; font-weight: 700; margin-bottom: 4px; font-family: "Roboto Condensed", sans-serif; letter-spacing: 0.06em; text-transform: uppercase; }
    .side-panel-body .field-group input,
    .side-panel-body .field-group textarea,
    .side-panel-body .field-group select { width: 100%; padding: 7px 9px; border-radius: 8px; border: 1px solid var(--border-strong); font-size: 12px; font-family: "Roboto", sans-serif; color: var(--text-main); background: #fff; margin-top: 3px; }
    .side-panel-footer { margin-top: 16px; }
    .side-panel-footer .btn-primary { width: 100%; }

    /* ── SETUP ── */
    .setup-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 800px) { .setup-grid { grid-template-columns: 1fr; } }
    .setup-section { border-radius: var(--radius-md); border: 1px solid var(--border-subtle); background: #fff; padding: 14px; box-shadow: 0 2px 6px rgba(15,23,42,0.04); }
    .setup-section-title { font-family: "Roboto Condensed", sans-serif; font-size: 12px; font-weight: 700; margin-bottom: 4px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent-strong); }
    .setup-section-hint { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; }
    .identity-section { grid-column: 1 / -1; }
    .identity-header { display: flex; justify-content: space-between; align-items: center; padding: 10px; cursor: pointer; background: #eef1f7; border-radius: 8px; margin-bottom: 10px; border: 1px solid var(--border-subtle); }
    .identity-title { font-family: "Roboto Condensed", sans-serif; font-size: 13px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent-strong); }
    .identity-arrow { width: 22px; height: 22px; border-radius: 999px; border: 1px solid var(--border-strong); display: flex; align-items: center; justify-content: center; font-size: 13px; color: var(--text-muted); background: #fff; }
    .identity-field { margin-bottom: 12px; }
    .identity-field label { display: block; font-family: "Roboto Condensed", sans-serif; font-weight: 700; margin-bottom: 3px; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; }

    /* ── WORKSPACE ── */
    .workspace-footer { margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap; }

    /* ── LIBRARY ── */
    .library-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin-top: 8px; }
    .library-card { background: #fff; border: 1px solid var(--border-subtle); border-radius: 12px; padding: 16px; box-shadow: 0 2px 6px rgba(15,23,42,0.05); display: flex; flex-direction: column; gap: 8px; }
    .library-card-date { font-size: 11px; color: var(--text-muted); font-family: "Roboto Condensed", sans-serif; text-transform: uppercase; letter-spacing: 0.06em; }
    .library-card-headline { font-size: 14px; font-weight: 600; color: var(--text-main); line-height: 1.3; }
    .library-card-niche { font-size: 11px; color: var(--accent-strong); background: var(--accent-soft); padding: 2px 8px; border-radius: 999px; display: inline-block; font-family: "Roboto Condensed", sans-serif; letter-spacing: 0.06em; text-transform: uppercase; }
    .library-card-actions { display: flex; gap: 8px; margin-top: 4px; }
    .library-empty { text-align: center; padding: 40px 20px; color: var(--text-muted); font-size: 14px; grid-column: 1/-1; }

    /* ── DISTRIBUTION (placeholder) ── */
    .distribution-placeholder { text-align: center; padding: 60px 20px; color: var(--text-muted); }
    .distribution-placeholder .big-icon { font-size: 48px; margin-bottom: 16px; }
    .distribution-placeholder h3 { font-family: "Roboto Condensed", sans-serif; font-size: 18px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent-strong); margin: 0 0 8px; }
    .distribution-placeholder p { font-size: 14px; max-width: 400px; margin: 0 auto; line-height: 1.6; }

    /* ── GENERATED CONTENT HEADER ── */
    .generated-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .copy-all-btn { border: 1px solid var(--border-strong); background: #fff; padding: 5px 12px; border-radius: 999px; cursor: pointer; font-size: 11px; font-family: "Roboto Condensed", sans-serif; letter-spacing: 0.06em; text-transform: uppercase; transition: background 0.15s; }
    .copy-all-btn:hover { background: #f3f4f6; }

    /* ── DISTRIBUTION MODAL ── */
    .distribution-modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.55); z-index:1000; align-items:flex-start; justify-content:center; padding:24px 16px; overflow-y:auto; }
    .distribution-modal.visible { display:flex; }
    .distribution-modal-inner { background:#fff; border-radius:18px; width:100%; max-width:720px; box-shadow:0 24px 60px rgba(0,0,0,0.2); overflow:hidden; margin:auto; }
    .dist-modal-header { display:flex; justify-content:space-between; align-items:center; padding:20px 24px 16px; border-bottom:1px solid var(--border-subtle); }
    .dist-modal-title { font-family:"Roboto Condensed",sans-serif; font-size:18px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:var(--accent-strong); }
    .dist-modal-subtitle { font-size:13px; color:var(--text-muted); margin-top:3px; }
    .dist-modal-close { background:transparent; border:none; font-size:20px; cursor:pointer; color:var(--text-muted); line-height:1; padding:4px; }
    .distribution-modal-body { padding:20px 24px; display:flex; flex-direction:column; gap:16px; }
    .dist-card { border:1px solid var(--border-subtle); border-radius:12px; padding:16px; display:flex; flex-direction:column; gap:10px; }
    .dist-card-header { display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:4px; }
    .dist-card-title { font-family:"Roboto Condensed",sans-serif; font-size:14px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; color:var(--text-main); }
    .dist-card-hint { font-size:11px; color:var(--text-muted); }
    .dist-card-body { font-size:13px; line-height:1.55; white-space:pre-wrap; border:1px solid transparent; padding:8px; border-radius:8px; min-height:60px; color:var(--text-main); transition:border-color 0.15s,background 0.15s; }
    .dist-card-body:focus { outline:none; border-color:var(--border-strong); background:#fafafa; }
    .dist-copy-btn { align-self:flex-start; }

    /* ── PROFILE PANEL ── */
    .profile-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    @media (max-width:700px) { .profile-grid { grid-template-columns:1fr; } }
    .profile-section { border-radius:var(--radius-md); border:1px solid var(--border-subtle); background:#fff; padding:18px; }
    .profile-section-title { font-family:"Roboto Condensed",sans-serif; font-size:13px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:var(--accent-strong); margin-bottom:4px; }
    .profile-section-hint { font-size:12px; color:var(--text-muted); margin-bottom:14px; }
    .profile-field { margin-bottom:12px; }
    .profile-field label { display:block; font-family:"Roboto Condensed",sans-serif; font-size:11px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; color:var(--text-muted); margin-bottom:4px; }
    .success-msg { background:#f0fdf4; border:1px solid #86efac; color:#16a34a; border-radius:8px; padding:10px 14px; font-size:13px; display:none; }
    .success-msg.visible { display:block; }

    /* ── SIDEBAR AVATAR ── */
    .sidebar-profile-divider { border-top:1px solid rgba(255,255,255,0.12); margin:12px 0 10px; }
    .sidebar-avatar-block { display:flex; align-items:center; gap:10px; padding:8px 6px; border-radius:10px; cursor:pointer; transition:background 0.15s; }
    .sidebar-avatar-block:hover { background:rgba(255,255,255,0.08); }
    .sidebar-avatar { width:36px; height:36px; border-radius:50%; background:var(--aqua); color:#fff; display:flex; align-items:center; justify-content:center; font-family:"Roboto Condensed",sans-serif; font-size:13px; font-weight:700; letter-spacing:0.04em; flex-shrink:0; }
    .sidebar-avatar-info { flex:1; min-width:0; }
    .sidebar-avatar-name { font-size:13px; font-weight:600; color:#fff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .sidebar-avatar-sub { font-size:11px; color:#9ca3af; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .sidebar-avatar-caret { font-size:13px; color:#9ca3af; flex-shrink:0; }

    @media (max-width:700px) {
      .profile-section[style*="grid-column"] > div[style*="grid-template-columns"] {
        grid-template-columns: 1fr 1fr !important;
      }
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }
  </style>
</head>
<body>
<div class="app-shell">

  <!-- ═══════════════════════════ SIDEBAR ═══════════════════════════ -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title">HomeBridge</div>
      <div class="sidebar-subtitle">Identity-aware content engine</div>
    </div>

    <div class="nav-section-label">Workspace</div>
    <ul class="nav-list">
      <li class="nav-item">
        <button class="nav-button" data-target="setup-panel">
          <span>⚙️</span><span>Setup</span>
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-button active" data-target="content-engine-panel">
          <span>🧠</span><span>Content Engine</span>
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-button" data-target="workspace-panel">
          <span>🛠️</span><span>Workspace</span>
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-button" data-target="library-panel">
          <span>📚</span><span>Library</span>
        </button>
      </li>

    </ul>

    <hr class="nav-divider" />
    <ul class="nav-list">
      <li class="nav-item">
        <button class="nav-button" data-target="distribution-panel">
          <span>🚀</span><span>Distribution</span>
        </button>
      </li>
    </ul>

    <!-- Avatar / Profile trigger -->
    <div class="sidebar-profile-divider"></div>
    <div class="sidebar-avatar-block" id="sidebar-avatar-block">
      <div class="sidebar-avatar" id="sidebar-avatar-initials">JR</div>
      <div class="sidebar-avatar-info">
        <div class="sidebar-avatar-name" id="sidebar-avatar-name">Agent Name</div>
        <div class="sidebar-avatar-sub" id="sidebar-avatar-brokerage">Brokerage</div>
      </div>
      <div class="sidebar-avatar-caret">⚙</div>
    </div>
    <div class="sidebar-footer">Built to create leverage, not more work.</div>
  </aside>

  <!-- ═══════════════════════════ MAIN ═══════════════════════════ -->
  <main class="main">

    <!-- ── CONTENT ENGINE PANEL ── -->
    <section id="content-engine-panel" class="panel active">
      <div class="panel-header">
        <div>
          <div class="panel-title">Content Engine</div>
          <div class="panel-subtitle">Generate niche-aware content based on your saved identity.</div>
        </div>
        <div class="panel-tag">Live workspace</div>
      </div>

      <div class="panel-body">

        <!-- Identity summary -->
        <div class="identity-summary">
          <div class="identity-summary-header">
            <div class="identity-summary-title">Your identity</div>
            <div class="identity-summary-edit" id="identity-edit-link">Adjust in Setup →</div>
          </div>
          <div id="identity-summary-content">
            <div class="identity-summary-empty">Identity not set yet. Go to Setup to define your niche and focus.</div>
          </div>
        </div>

        <!-- Primary niche selector (shows when multiple niches saved) -->
        <div class="field-group" id="niche-selector-group" style="display:none;">
          <div class="field-label">Generate for which niche?</div>
          <div class="field-hint">You have multiple niches set up. Choose one to focus this content on.</div>
          <div class="niche-selector-row" id="niche-selector-chips"></div>
        </div>

        <!-- Situation -->
        <div class="field-group">
          <div class="field-label">Situation</div>
          <div class="field-hint">Choose the type of moment you want content for.</div>
          <div class="select-wrapper">
            <select id="situation-select">
              <option value="">Select a situation…</option>
            </select>
            <span class="select-arrow">▾</span>
          </div>
        </div>

        <!-- Content settings -->
        <div class="field-group">
          <div class="field-label">Content settings</div>
          <div class="field-hint">Optional refinements — persona, tone, and length.</div>
          <div class="content-settings-row">
            <div class="select-wrapper">
              <select id="persona-select">
                <option value="">Persona (optional)</option>
                <option value="adult children managing a parent's home">Adult children managing a parent's home</option>
                <option value="seniors planning to downsize">Seniors planning to downsize</option>
                <option value="executors or heirs">Executors / heirs</option>
                <option value="distressed homeowners">Distressed homeowners</option>
                <option value="first-time buyers">First-time buyers</option>
                <option value="investors">Investors</option>
                <option value="relocating families">Relocating families</option>
                <option value="move-up buyers">Move-up buyers</option>
                <option value="veterans">Veterans</option>
              </select>
              <span class="select-arrow">▾</span>
            </div>
            <div class="select-wrapper">
              <select id="tone-select">
                <option value="">Tone (optional)</option>
                <option value="calm">Calm</option>
                <option value="bold">Bold</option>
                <option value="empathetic">Empathetic</option>
                <option value="analytical">Analytical</option>
                <option value="direct">Direct</option>
                <option value="warm">Warm</option>
                <option value="professional">Professional</option>
              </select>
              <span class="select-arrow">▾</span>
            </div>
            <div class="select-wrapper">
              <select id="length-select">
                <option value="">Length (optional)</option>
                <option value="short">Short</option>
                <option value="medium">Medium</option>
                <option value="long">Long</option>
              </select>
              <span class="select-arrow">▾</span>
            </div>
          </div>
        </div>

        <!-- Trend preferences -->
        <div class="field-group">
          <div class="field-label">Trend preferences</div>
          <div class="field-hint">Trends you saved in Setup — these inform your content.</div>
          <div id="content-engine-trends-display" class="empty-text">None saved yet.</div>
        </div>

        <!-- Error message (replaces alert) -->
        <div id="generate-error" class="inline-error"></div>

        <!-- Generate button -->
        <div class="button-row">
          <button id="generate-content-btn" class="btn-primary">Generate content</button>
        </div>

        <!-- Generating indicator — shown while API call is in flight -->
        <div id="generating-indicator" style="display:none;text-align:center;padding:24px 0;">
          <div style="font-family:'Roboto Condensed',sans-serif;font-size:14px;letter-spacing:0.08em;text-transform:uppercase;color:var(--accent-strong);animation:pulse 1.4s ease-in-out infinite;">
            ✦ Generating your content…
          </div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:6px;">Running compliance check — taking you to Library in a moment.</div>
        </div>

      </div>
    </section>

    <!-- ── SETUP PANEL ── -->
    <section id="setup-panel" class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">Setup</div>
          <div class="panel-subtitle">Define your identity so the Content Engine thinks like you do.</div>
        </div>
        <div class="panel-tag">Identity layer</div>
      </div>
      <div class="panel-body">
        <div class="setup-grid">

          <!-- Your Identity -->
          <div class="setup-section identity-section">
            <div class="identity-header" id="identity-toggle">
              <span class="identity-title">Your Identity</span>
              <span class="identity-arrow" id="identity-arrow">▾</span>
            </div>
            <div id="identity-content">
              <div class="identity-field"><label>Business Name</label><input type="text" id="business-name" /></div>
              <div class="identity-field"><label>Market / City / Region</label><input type="text" id="market" /></div>
              <div class="identity-field"><label>Words to Avoid</label><input type="text" id="words-avoid" /></div>
              <div class="identity-field"><label>Words to Prefer</label><input type="text" id="words-prefer" /></div>
              <div class="identity-field"><label>Brand Voice</label><textarea id="brand-voice"></textarea></div>
              <div class="identity-field"><label>Short Bio</label><textarea id="short-bio"></textarea></div>
              <div class="identity-field"><label>Audience Description</label><textarea id="audience-description"></textarea></div>
            </div>
          </div>

          <!-- Primary Niches -->
          <div class="setup-section">
            <div class="setup-section-title">Primary niches</div>
            <div class="setup-section-hint">Click to select one or more that define your focus.</div>
            <div id="primary-niche-chips" class="chip-row"></div>
          </div>

          <!-- Sub-Niches -->
          <div class="setup-section">
            <div class="setup-section-title">Sub-niches</div>
            <div class="setup-section-hint">Refine your focus. Sub-niches appear after selecting a primary niche.</div>
            <div id="subniche-chips" class="chip-row">
              <div class="empty-text" id="subniche-empty">Select a primary niche above to see options.</div>
            </div>
          </div>

          <!-- Trend Preferences -->
          <div class="setup-section">
            <div class="setup-section-title">Trend preferences</div>
            <div class="setup-section-hint">Add market or consumer trends you care about. Press Enter or click Add.</div>
            <input type="text" id="trend-input" placeholder="e.g., Rising interest rates, low inventory" />
            <div class="button-row">
              <button id="add-trend-btn" class="btn-secondary">+ Add trend</button>
            </div>
            <div id="trend-chips" class="chip-row">
              <div class="empty-text" id="trend-empty">No trends added yet.</div>
            </div>
          </div>

          <!-- Save -->
          <div class="setup-section">
            <div class="setup-section-title">Save your setup</div>
            <div class="setup-section-hint">Your identity is stored in your browser and used every time you generate content.</div>
            <div class="button-row">
              <button id="save-setup-btn" class="btn-primary">Save setup</button>
            </div>
            <div id="save-success" class="inline-error" style="background:#f0fdf4;border-color:#86efac;color:#16a34a;display:none;margin-top:10px;">
              ✓ Setup saved. Redirecting to Content Engine…
            </div>
          </div>

        </div>
      </div>
    </section>

    <!-- ── WORKSPACE PANEL ── -->
    <section id="workspace-panel" class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">Workspace</div>
          <div class="panel-subtitle">Review and edit your content. Changes save automatically back to Library.</div>
        </div>
        <div class="panel-tag">Editing</div>
      </div>
      <div id="workspace-empty" style="padding:40px 20px;text-align:center;color:var(--text-muted);font-size:14px;">
        No content here yet. Generate content and it will appear in Library — click Edit in Workspace to refine it here.
      </div>
      <div id="workspace-content" style="display:none;">
        <div class="generated-content-grid">
          <div class="content-card"><div class="content-card-title">Headline</div><div class="content-card-actions"><button class="card-copy-btn" data-target="ws-headline">Copy</button><button class="card-reset-btn" data-target="ws-headline">Reset</button></div><div id="ws-headline" class="content-card-body" contenteditable="true"></div></div>
          <div class="content-card"><div class="content-card-title">Thumbnail Idea</div><div class="content-card-actions"><button class="card-copy-btn" data-target="ws-thumbnail">Copy</button><button class="card-reset-btn" data-target="ws-thumbnail">Reset</button></div><div id="ws-thumbnail" class="content-card-body" contenteditable="true"></div></div>
          <div class="content-card"><div class="content-card-title">Hashtags</div><div class="content-card-actions"><button class="card-copy-btn" data-target="ws-hashtags">Copy</button><button class="card-reset-btn" data-target="ws-hashtags">Reset</button></div><div id="ws-hashtags" class="content-card-body" contenteditable="true"></div></div>
          <div class="content-card"><div class="content-card-title">Post</div><div class="content-card-actions"><button class="card-copy-btn" data-target="ws-post">Copy</button><button class="card-reset-btn" data-target="ws-post">Reset</button></div><div id="ws-post" class="content-card-body" contenteditable="true"></div></div>
          <div class="content-card"><div class="content-card-title">Call to Action</div><div class="content-card-actions"><button class="card-copy-btn" data-target="ws-cta">Copy</button><button class="card-reset-btn" data-target="ws-cta">Reset</button></div><div id="ws-cta" class="content-card-body" contenteditable="true"></div></div>
          <div class="content-card"><div class="content-card-title">Script</div><div class="content-card-actions"><button class="card-copy-btn" data-target="ws-script">Copy</button><button class="card-reset-btn" data-target="ws-script">Reset</button></div><div id="ws-script" class="content-card-body" contenteditable="true"></div></div>
        </div>
        <div class="workspace-footer">
          <button id="ws-copy-all" class="btn-secondary">Copy All</button>
          <button id="ws-save-btn" class="btn-primary">Save to Library</button>
          <button id="ws-distribute-btn" class="btn-secondary">🚀 Distribute</button>
          <button id="ws-back-btn" class="btn-secondary">← Back to Generate</button>
        </div>
      </div>
    </section>

    <!-- ── LIBRARY PANEL ── -->
    <section id="library-panel" class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">Library</div>
          <div class="panel-subtitle">All your saved content sets, ready to reload or review.</div>
        </div>
        <div class="panel-tag">Saved content</div>
      </div>
      <div id="library-grid" class="library-grid">
        <div class="library-empty">No saved content yet. Generate and save content to build your library.</div>
      </div>
    </section>


    <!-- ── PROFILE PANEL ── -->
    <section id="profile-panel" class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">My Profile</div>
          <div class="panel-subtitle">Update your account information at any time.</div>
        </div>
        <div class="panel-tag">Account</div>
      </div>

      <div id="profile-error" class="inline-error" style="margin-bottom:12px;"></div>
      <div id="profile-success" class="success-msg" style="margin-bottom:12px;"></div>

      <div class="profile-grid">

        <!-- Account Info -->
        <div class="profile-section">
          <div class="profile-section-title">Account info</div>
          <div class="profile-section-hint">Update your name, brokerage, email, or phone number.</div>
          <div class="profile-field"><label>Agent Name</label><input type="text" id="profile-name" placeholder="Your full name" /></div>
          <div class="profile-field"><label>Brokerage</label><input type="text" id="profile-brokerage" placeholder="Your brokerage or team name" /></div>
          <div class="profile-field"><label>Email</label><input type="email" id="profile-email" placeholder="your@email.com" /></div>
          <div class="profile-field"><label>Phone <span style="font-weight:400;text-transform:none;letter-spacing:0;">(optional)</span></label><input type="text" id="profile-phone" placeholder="e.g. 720-555-0100" /></div>
          <div class="profile-field" style="padding-top:10px;border-top:1px solid var(--border-subtle);margin-top:6px;">
            <label>MLS Membership(s) <span style="font-weight:400;text-transform:none;letter-spacing:0;">(for compliance checks)</span></label>
            <input type="text" id="profile-mls-1" placeholder="Primary MLS name e.g. REColorado" style="margin-bottom:6px;" />
            <input type="text" id="profile-mls-2" placeholder="Second MLS (optional)" style="margin-bottom:6px;" />
            <input type="text" id="profile-mls-3" placeholder="Third MLS (optional)" />
            <div style="font-size:11px;color:var(--text-muted);margin-top:5px;">Used to flag content that may conflict with your MLS advertising rules.</div>
          </div>
          <div class="profile-field" style="padding-top:4px;border-top:1px solid var(--border-subtle);margin-top:4px;">
            <div style="font-size:11px;color:var(--text-muted);">Your name and brokerage appear in generated content and your sidebar.</div>
          </div>
          <div class="button-row">
            <button id="save-profile-btn" class="btn-primary">Save changes</button>
          </div>
        </div>

        <!-- Change Password -->
        <div class="profile-section">
          <div class="profile-section-title">Change password</div>
          <div class="profile-section-hint">Must be at least 8 characters with uppercase, lowercase, and a number or symbol.</div>
          <div class="profile-field"><label>Current password</label><input type="password" id="profile-current-password" placeholder="Your current password" /></div>
          <div class="profile-field"><label>New password</label><input type="password" id="profile-new-password" placeholder="New password" /></div>
          <div class="profile-field"><label>Confirm new password</label><input type="password" id="profile-confirm-password" placeholder="Repeat new password" /></div>
          <div class="button-row">
            <button id="save-password-btn" class="btn-primary">Update password</button>
          </div>
        </div>

        <!-- Social Accounts — full width -->
        <div class="profile-section" style="grid-column:1/-1;">
          <div class="profile-section-title">Social & distribution accounts</div>
          <div class="profile-section-hint">Enter your handles or profile URLs. Used to personalize distributed content. All fields optional — add now or later.</div>
          <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;">
            <div class="profile-field"><label>LinkedIn URL</label><input type="text" id="social-linkedin" placeholder="linkedin.com/in/yourname" /></div>
            <div class="profile-field"><label>Instagram</label><input type="text" id="social-instagram" placeholder="@yourhandle" /></div>
            <div class="profile-field"><label>Facebook URL</label><input type="text" id="social-facebook" placeholder="facebook.com/yourpage" /></div>
            <div class="profile-field"><label>TikTok</label><input type="text" id="social-tiktok" placeholder="@yourhandle" /></div>
            <div class="profile-field"><label>YouTube URL</label><input type="text" id="social-youtube" placeholder="youtube.com/@yourchannel" /></div>
            <div class="profile-field"><label>X / Twitter</label><input type="text" id="social-twitter" placeholder="@yourhandle" /></div>
            <div class="profile-field"><label>Threads</label><input type="text" id="social-threads" placeholder="@yourhandle" /></div>
            <div class="profile-field"><label>Reddit</label><input type="text" id="social-reddit" placeholder="u/yourhandle" /></div>
            <div class="profile-field"><label>Google Business</label><input type="text" id="social-google" placeholder="Your business profile URL" /></div>
            <div class="profile-field"><label>Pinterest</label><input type="text" id="social-pinterest" placeholder="@yourhandle" /></div>
            <div class="profile-field"><label>Newsletter / Email</label><input type="text" id="social-email" placeholder="your@newsletter.com" /></div>
            <div class="profile-field"><label>Website</label><input type="text" id="social-website" placeholder="yoursite.com" /></div>
          </div>
          <div class="button-row" style="margin-top:12px;">
            <button id="save-socials-btn" class="btn-primary">Save accounts</button>
          </div>
        </div>

      </div>
    </section>

    <!-- ── DISTRIBUTION PANEL ── -->
    <section id="distribution-panel" class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">Distribution</div>
          <div class="panel-subtitle">Auto-publish your content to social platforms.</div>
        </div>
        <div class="panel-tag">Coming soon</div>
      </div>
      <div class="distribution-placeholder">
        <div class="big-icon">🚀</div>
        <h3>Auto-Publishing</h3>
        <p>Connect your social accounts and HomeBridge will publish your approved content automatically — LinkedIn, Instagram, Facebook, YouTube, TikTok, and more.</p>
      </div>
    </section>

  </main>
</div>

  <!-- ── DISTRIBUTION MODAL ── -->
  <div id="distribution-modal" class="distribution-modal">
    <div class="distribution-modal-inner">
      <div class="dist-modal-header">
        <div>
          <div class="dist-modal-title">🚀 Distribute</div>
          <div class="dist-modal-subtitle">Your content formatted for each platform. Edit freely, then copy and paste directly into the app.</div>
        </div>
        <button class="dist-modal-close" id="dist-modal-close">✕</button>
      </div>
      <div class="distribution-modal-body" id="distribution-modal-body"></div>
    </div>
  </div>

<script src="js/ui_main_v3.js"></script>
</body>
</html>

// ui_main_v3.js — HomeBridge Single Page App
// One clean file. No duplicates.

// ─────────────────────────────────────────────
// AUTH GUARD
// ─────────────────────────────────────────────
const BACKEND_URL = "https://trend-collector-service-clean.onrender.com";

const hb_token = localStorage.getItem("hb_token");
const hb_user  = JSON.parse(localStorage.getItem("hb_user") || "null");
if (!hb_token || !hb_user) {
  window.location.href = "login.html";
}

// ── SIDEBAR AVATAR ──
function getInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0,2).toUpperCase();
  return (parts[0][0] + parts[parts.length-1][0]).toUpperCase();
}

function updateSidebarAvatar() {
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!user) return;
  const initialsEl  = document.getElementById("sidebar-avatar-initials");
  const nameEl      = document.getElementById("sidebar-avatar-name");
  const brokerageEl = document.getElementById("sidebar-avatar-brokerage");
  if (initialsEl)  initialsEl.textContent  = getInitials(user.agent_name);
  if (nameEl)      nameEl.textContent      = user.agent_name || "";
  if (brokerageEl) brokerageEl.textContent = user.brokerage  || user.email || "";
}
updateSidebarAvatar();

// Avatar click → profile panel
document.getElementById("sidebar-avatar-block")?.addEventListener("click", () => navigateTo("profile-panel"));

// Sign out — add button to sidebar footer
const sidebarFooter = document.querySelector(".sidebar-footer");
if (sidebarFooter) {
  const signOutBtn = document.createElement("button");
  signOutBtn.textContent = "Sign Out";
  signOutBtn.style.cssText = "background:transparent;border:none;color:#6b7280;font-size:11px;cursor:pointer;font-family:'Roboto Condensed',sans-serif;letter-spacing:0.06em;text-transform:uppercase;padding:0;margin-top:6px;display:block;";
  signOutBtn.addEventListener("click", () => {
    localStorage.removeItem("hb_token");
    localStorage.removeItem("hb_user");
    window.location.href = "login.html";
  });
  sidebarFooter.appendChild(signOutBtn);
}

// Pre-fill setup from account if empty
const _savedSetup = JSON.parse(localStorage.getItem("hb_setup") || "{}");
if (!_savedSetup.agentName && hb_user?.agent_name) {
  _savedSetup.agentName = hb_user.agent_name;
  _savedSetup.brokerage = hb_user.brokerage || "";
  localStorage.setItem("hb_setup", JSON.stringify(_savedSetup));
}

// Authenticated fetch
async function authFetch(url, options = {}) {
  const token = localStorage.getItem("hb_token");
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
      ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    },
  });
}

// ─────────────────────────────────────────────
// NICHE DATA
// ─────────────────────────────────────────────
const NICHE_DATA = {
  "Seniors & Downsizing": ["Aging in place","Assisted living transitions","Estate planning coordination","Rightsizing consultations","Senior community tours","Home safety evaluations","Family decision support"],
  "Probate & Inherited Homes": ["Executor support","Trustee coordination","Clean-out & haul-away","Estate sale prep","As-is valuation","Heir communication","Vendor coordination"],
  "Divorce & Separation": ["Neutral market valuations","Coordinating with attorneys","Buyout vs. sell analysis","Privacy-sensitive showings","Timeline coordination","Post-divorce relocation"],
  "Relocation": ["Out-of-state buyer onboarding","Virtual tours","Temporary housing support","Neighborhood orientation","Cost-of-living analysis","Move logistics coordination"],
  "Luxury": ["High-net-worth client onboarding","Confidential showings","Luxury staging","Global buyer networks","Architectural home marketing","Lifestyle-driven search"],
  "First-Time Buyers": ["Down payment programs","Credit readiness","Rent vs. buy analysis","FHA/VA/Conventional guidance","Neighborhood fit analysis","Offer strategy coaching"],
  "Investors": ["Cash-flow analysis","BRRRR strategy","Fix-and-flip evaluation","Rental market analysis","Portfolio planning","Off-market sourcing"],
  "Veterans": ["VA loan navigation","PCS relocation","Military-friendly neighborhoods","Benefit maximization","Transition to civilian housing","VA appraisal prep"],
  "New Construction": ["Builder negotiations","Lot selection","Upgrade ROI guidance","Construction timeline tracking","Warranty walkthroughs","Builder contract review"],
  "Move-Up Buyers": ["Sell-to-buy timing","Bridge loan options","Contingency strategy","Family-friendly neighborhoods","School district analysis","Equity planning"],
  "Distressed / Pre-Foreclosure": ["Short sale navigation","Loan modification guidance","Cash-for-keys coordination","As-is valuation","Investor offer analysis","Hardship documentation"],
  "Land & Rural": ["Septic/well evaluation","Zoning & land use","Agricultural exemptions","Survey & boundary issues","Outbuilding assessments","Rural financing"],
  "Short-Term Rentals": ["STR regulations","Furnishing packages","Revenue projections","Seasonal pricing strategy","Guest experience design","Turnover vendor coordination"],
  "Green / Energy Efficient Homes": ["Solar valuation","Energy audits","Green financing","Net-zero homes","Eco-friendly upgrades","Utility savings analysis"],
};

const SITUATIONS = [
  "Market update — prices are rising",
  "Market update — prices are falling",
  "Low inventory — high competition",
  "Interest rate changes affecting buyers",
  "Spring market is heating up",
  "Fall/winter slowdown",
  "First-time buyer confusion in the market",
  "Investor opportunity window",
  "Local development or neighborhood change",
  "Post-divorce fresh start",
  "Inherited a home and don't know what to do",
  "Ready to downsize — not sure how",
  "Military relocation incoming",
  "Tax season — investment property questions",
];

// ─────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────
let selectedPrimaryNiches  = [];
let selectedSubNiches      = [];
let currentTrends          = [];
let activeNicheForGenerate = null;
let lastGeneratedContent   = {};
let stagingStatus          = "Draft";

// ─────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────
function getSaved() {
  return JSON.parse(localStorage.getItem("hb_setup") || "{}");
}
function showError(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.style.display = "block";
  el.classList.add("visible");
}
function hideError(id) {
  const el = document.getElementById(id);
  if (el) { el.style.display = "none"; el.classList.remove("visible"); }
}

// ─────────────────────────────────────────────
// NAVIGATION
// ─────────────────────────────────────────────
function navigateTo(target) {
  document.querySelectorAll(".nav-button").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  const panel = document.getElementById(target);
  if (panel) panel.classList.add("active");
  const btn = document.querySelector(`.nav-button[data-target="${target}"]`);
  if (btn) btn.classList.add("active");
  if (target === "content-engine-panel") { renderIdentitySummary(); renderTrendDisplay(); renderNicheSelector(); const saved = getSaved(); populateSituationDropdown(activeNicheForGenerate || (saved.primaryNiches||[])[0] || null); }
  if (target === "library-panel") renderLibrary();
  if (target === "profile-panel") renderProfilePanel();
}

document.querySelectorAll(".nav-button").forEach(btn => {
  btn.addEventListener("click", () => navigateTo(btn.getAttribute("data-target")));
});
document.getElementById("identity-edit-link")?.addEventListener("click", () => navigateTo("setup-panel"));

// ─────────────────────────────────────────────
// IDENTITY ACCORDION
// ─────────────────────────────────────────────
const identityToggle  = document.getElementById("identity-toggle");
const identityContent = document.getElementById("identity-content");
const identityArrow   = document.getElementById("identity-arrow");
if (identityToggle) {
  identityToggle.addEventListener("click", () => {
    const open = identityContent.style.display !== "none";
    identityContent.style.display = open ? "none" : "block";
    identityArrow.textContent = open ? "▸" : "▾";
  });
}

// ─────────────────────────────────────────────
// PRIMARY NICHE CHIPS
// ─────────────────────────────────────────────
function renderPrimaryNicheChips() {
  const container = document.getElementById("primary-niche-chips");
  if (!container) return;
  container.innerHTML = "";
  Object.keys(NICHE_DATA).forEach(niche => {
    const chip = document.createElement("div");
    chip.className = "chip" + (selectedPrimaryNiches.includes(niche) ? " selected" : "");
    chip.textContent = niche;
    chip.addEventListener("click", () => {
      if (selectedPrimaryNiches.includes(niche)) {
        selectedPrimaryNiches = selectedPrimaryNiches.filter(n => n !== niche);
        selectedSubNiches = selectedSubNiches.filter(s => !(NICHE_DATA[niche]||[]).includes(s));
      } else {
        selectedPrimaryNiches.push(niche);
      }
      renderPrimaryNicheChips();
      renderSubNicheChips();
    });
    container.appendChild(chip);
  });
}

// ─────────────────────────────────────────────
// SUB-NICHE CHIPS
// ─────────────────────────────────────────────
function renderSubNicheChips() {
  const container = document.getElementById("subniche-chips");
  if (!container) return;
  container.innerHTML = "";
  if (selectedPrimaryNiches.length === 0) {
    const e = document.createElement("div");
    e.className = "empty-text";
    e.textContent = "Select a primary niche above to see options.";
    container.appendChild(e);
    return;
  }
  selectedPrimaryNiches.forEach(niche => {
    const label = document.createElement("div");
    label.style.cssText = "width:100%;font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:var(--text-muted);margin-top:10px;margin-bottom:3px;font-weight:700;font-family:'Roboto Condensed',sans-serif;";
    label.textContent = niche;
    container.appendChild(label);
    (NICHE_DATA[niche]||[]).forEach(sub => {
      const chip = document.createElement("div");
      chip.className = "chip" + (selectedSubNiches.includes(sub) ? " selected" : "");
      chip.textContent = sub;
      chip.addEventListener("click", () => {
        selectedSubNiches = selectedSubNiches.includes(sub)
          ? selectedSubNiches.filter(s => s !== sub)
          : [...selectedSubNiches, sub];
        renderSubNicheChips();
      });
      container.appendChild(chip);
    });
  });
}

// ─────────────────────────────────────────────
// NICHE SELECTOR (Content Engine)
// ─────────────────────────────────────────────
function renderNicheSelector() {
  const saved    = getSaved();
  const primaries = saved.primaryNiches || [];
  const group    = document.getElementById("niche-selector-group");
  const chips    = document.getElementById("niche-selector-chips");
  if (!group || !chips) return;
  if (primaries.length <= 1) {
    group.style.display = "none";
    activeNicheForGenerate = primaries[0] || null;
    return;
  }
  group.style.display = "block";
  chips.innerHTML = "";
  if (!activeNicheForGenerate || !primaries.includes(activeNicheForGenerate)) {
    activeNicheForGenerate = primaries[0];
  }
  primaries.forEach(niche => {
    const chip = document.createElement("div");
    chip.className = "niche-select-chip" + (niche === activeNicheForGenerate ? " active" : "");
    chip.textContent = niche;
    chip.addEventListener("click", () => { activeNicheForGenerate = niche; renderNicheSelector(); populateSituationDropdown(niche); });
    chips.appendChild(chip);
  });
}

// ─────────────────────────────────────────────
// TREND CHIPS
// ─────────────────────────────────────────────
function addTrendChip(text) {
  if (!text || currentTrends.includes(text)) return;
  currentTrends.push(text);
  const container = document.getElementById("trend-chips");
  if (!container) return;
  const empty = document.getElementById("trend-empty");
  if (empty) empty.style.display = "none";
  const chip = document.createElement("div");
  chip.className = "chip";
  chip.textContent = text;
  const x = document.createElement("span");
  x.className = "chip-remove";
  x.textContent = "×";
  x.addEventListener("click", e => {
    e.stopPropagation();
    currentTrends = currentTrends.filter(t => t !== text);
    chip.remove();
    if (currentTrends.length === 0) {
      const mt = document.createElement("div");
      mt.className = "empty-text"; mt.id = "trend-empty";
      mt.textContent = "No trends added yet.";
      container.appendChild(mt);
    }
  });
  chip.appendChild(x);
  container.appendChild(chip);
}

document.getElementById("add-trend-btn")?.addEventListener("click", () => {
  const input = document.getElementById("trend-input");
  const v = input?.value.trim();
  if (v) { addTrendChip(v); input.value = ""; }
});
document.getElementById("trend-input")?.addEventListener("keydown", e => {
  if (e.key === "Enter") {
    e.preventDefault();
    const input = document.getElementById("trend-input");
    const v = input?.value.trim();
    if (v) { addTrendChip(v); input.value = ""; }
  }
});

// ─────────────────────────────────────────────
// SAVE SETUP
// ─────────────────────────────────────────────
document.getElementById("save-setup-btn")?.addEventListener("click", () => {
  const data = {
    agentName:           hb_user?.agent_name || getSaved().agentName || "",
    businessName:        document.getElementById("business-name")?.value.trim() || "",
    market:              document.getElementById("market")?.value.trim() || "",
    brokerage:           hb_user?.brokerage || getSaved().brokerage || "",
    wordsAvoid:          document.getElementById("words-avoid")?.value.trim() || "",
    wordsPrefer:         document.getElementById("words-prefer")?.value.trim() || "",
    brandVoice:          document.getElementById("brand-voice")?.value.trim() || "",
    shortBio:            document.getElementById("short-bio")?.value.trim() || "",
    audienceDescription: document.getElementById("audience-description")?.value.trim() || "",
    trends:              currentTrends,
    primaryNiches:       selectedPrimaryNiches,
    subNiches:           selectedSubNiches,
  };
  localStorage.setItem("hb_setup", JSON.stringify(data));
  const btn = document.getElementById("save-setup-btn");
  const success = document.getElementById("save-success");
  btn.textContent = "Saved ✓"; btn.style.background = "var(--aqua)";
  if (success) success.style.display = "block";
  setTimeout(() => {
    btn.textContent = "Save setup"; btn.style.background = "";
    if (success) success.style.display = "none";
    navigateTo("content-engine-panel");
  }, 1400);
});

// ─────────────────────────────────────────────
// LOAD SETUP
// ─────────────────────────────────────────────
function loadSetup() {
  const saved = getSaved();
  [["business-name","businessName"],["market","market"],
   ["words-avoid","wordsAvoid"],["words-prefer","wordsPrefer"],
   ["brand-voice","brandVoice"],["short-bio","shortBio"],["audience-description","audienceDescription"]
  ].forEach(([id,key]) => { const el = document.getElementById(id); if (el && saved[key]) el.value = saved[key]; });
  selectedPrimaryNiches = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
  selectedSubNiches     = Array.isArray(saved.subNiches)     ? saved.subNiches     : [];
  currentTrends         = [];
  renderPrimaryNicheChips();
  renderSubNicheChips();
  const trendChips = document.getElementById("trend-chips");
  if (trendChips) trendChips.innerHTML = "";
  (Array.isArray(saved.trends) ? saved.trends : []).forEach(t => addTrendChip(t));
}

// ─────────────────────────────────────────────
// SITUATION DROPDOWN — niche-aware, trend-driven
// ─────────────────────────────────────────────
async function populateSituationDropdown(niche) {
  const select = document.getElementById("situation-select");
  if (!select) return;

  select.innerHTML = '<option value="">Loading situations…</option>';
  select.disabled = true;

  try {
    const nicheParam = niche ? `?niche=${encodeURIComponent(niche)}` : "";
    const res = await authFetch(`${BACKEND_URL}/content/situations${nicheParam}`);
    const data = await res.json();
    const situations = data.situations || SITUATIONS;

    select.innerHTML = '<option value="">Select a situation…</option>';
    situations.forEach(s => {
      const o = document.createElement("option");
      o.value = s; o.textContent = s;
      select.appendChild(o);
    });
  } catch (err) {
    // Fallback to static list
    select.innerHTML = '<option value="">Select a situation…</option>';
    SITUATIONS.forEach(s => {
      const o = document.createElement("option");
      o.value = s; o.textContent = s;
      select.appendChild(o);
    });
  } finally {
    select.disabled = false;
  }
}

// ─────────────────────────────────────────────
// IDENTITY SUMMARY
// ─────────────────────────────────────────────
function renderIdentitySummary() {
  const container = document.getElementById("identity-summary-content");
  if (!container) return;
  const saved    = getSaved();
  const name     = saved.agentName || "";
  const business = saved.businessName || "";
  const market   = saved.market || "";
  const primaries = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
  const subs     = Array.isArray(saved.subNiches) ? saved.subNiches : [];
  if (!name && !business && primaries.length === 0) {
    container.innerHTML = '<div class="identity-summary-empty">Identity not set yet. Go to Setup to define your niche and focus.</div>';
    return;
  }
  let html = "";
  if (name || business || market) {
    html += `<div style="font-size:13px;margin-bottom:8px;">`;
    if (name) html += `<strong>${name}</strong>`;
    if (business) html += ` · ${business}`;
    if (market) html += ` · ${market}`;
    html += `</div>`;
  }
  primaries.forEach(p => {
    html += `<div class="parent-category">${p}</div>`;
    (NICHE_DATA[p]||[]).filter(s => subs.includes(s)).forEach(s => {
      html += `<div class="sub-item">↳ ${s}</div>`;
    });
  });
  container.innerHTML = html;
}

// ─────────────────────────────────────────────
// TREND DISPLAY
// ─────────────────────────────────────────────
function renderTrendDisplay() {
  const container = document.getElementById("content-engine-trends-display");
  if (!container) return;
  const trends = getSaved().trends || [];
  if (!trends.length) { container.innerHTML = '<span class="empty-text">None saved yet. Add trends in Setup.</span>'; return; }
  container.innerHTML = "";
  trends.forEach(t => {
    const chip = document.createElement("div");
    chip.className = "chip selected";
    chip.textContent = t;
    chip.style.cursor = "default";
    container.appendChild(chip);
  });
}

// ─────────────────────────────────────────────
// GENERATE CONTENT
// ─────────────────────────────────────────────
document.getElementById("generate-content-btn")?.addEventListener("click", async () => {
  hideError("generate-error");
  const saved     = getSaved();
  const primaries = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
  const situation = document.getElementById("situation-select")?.value || "";
  if (primaries.length === 0) {
    showError("generate-error", "⚠ Please complete Setup first — select at least one primary niche and click Save Setup.");
    return;
  }
  if (!situation) {
    showError("generate-error", "⚠ Please select a situation before generating.");
    return;
  }
  const focusNiche = activeNicheForGenerate || primaries[0];
  const subNichesByCategory = {};
  primaries.forEach(p => {
    const subs = (NICHE_DATA[p]||[]).filter(s => (saved.subNiches||[]).includes(s));
    if (subs.length) subNichesByCategory[p] = subs;
  });
  const payload = {
    identity: { primaryCategories:[focusNiche], subNichesByCategory, trendPreferences:saved.trends||[] },
    agentProfile: {
      agentName:           hb_user?.agent_name  || saved.agentName    || "",
      businessName:        saved.businessName   || "",
      brokerage:           hb_user?.brokerage   || saved.brokerage    || "",
      market:              saved.market         || "",
      brandVoice:          saved.brandVoice     || "",
      shortBio:            saved.shortBio       || "",
      audienceDescription: saved.audienceDescription || "",
      wordsAvoid:          saved.wordsAvoid     || "",
      wordsPrefer:         saved.wordsPrefer    || "",
      mlsNames:            JSON.parse(localStorage.getItem("hb_mls")||"[]"),
    },
    situation,
    persona:   document.getElementById("persona-select")?.value || null,
    tone:      document.getElementById("tone-select")?.value    || null,
    length:    document.getElementById("length-select")?.value  || null,
    selectedTrends: saved.trends || [],
    timestamp: new Date().toISOString(),
  };
  const btn = document.getElementById("generate-content-btn");
  const indicator = document.getElementById("generating-indicator");
  btn.disabled = true; btn.textContent = "Generating…";
  if (indicator) indicator.style.display = "block";
  try {
    const res = await authFetch(`${BACKEND_URL}/content/generate-content`, {
      method: "POST", body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    lastGeneratedContent = data;

    // Save to library as pending item with compliance badges
    const libraryItem = {
      id: Date.now(),
      savedAt: new Date().toISOString(),
      agentName: hb_user?.agent_name || saved.agentName || "",
      niche: focusNiche,
      status: "pending",
      compliance: data.compliance || null,
      content: {
        headline:      data.headline      || "",
        thumbnailIdea: data.thumbnailIdea || "",
        hashtags:      data.hashtags      || "",
        post:          data.post          || "",
        cta:           data.cta           || "",
        script:        data.script        || "",
      },
    };
    const library = JSON.parse(localStorage.getItem("hb_library") || "[]");
    library.unshift(libraryItem);
    localStorage.setItem("hb_library", JSON.stringify(library));

    // Auto-navigate to Library
    navigateTo("library-panel");

  } catch (err) {
    console.error("Generate error:", err);
    showError("generate-error", "⚠ Could not reach the backend. Wait 30 seconds and try again.");
  } finally {
    btn.disabled = false; btn.textContent = "Generate content";
    if (indicator) indicator.style.display = "none";
  }
});

document.addEventListener("click", e => {
});
document.addEventListener("input", e => {
  if (e.target.classList.contains("content-card-body")) {
    e.target.classList.remove("empty");
    e.target.closest(".content-card")?.classList.add("edited");
  }
});

// ─────────────────────────────────────────────
// COPY ALL (Workspace only)
// ─────────────────────────────────────────────
function copyAll(prefix) {
  const keys   = ["headline","thumbnail","hashtags","post","cta","script"];
  const labels = ["HEADLINE","THUMBNAIL IDEA","HASHTAGS","POST","CALL TO ACTION","SCRIPT"];
  const parts  = keys.map((k,i) => `--- ${labels[i]} ---\n${document.getElementById(`${prefix}-${k}`)?.textContent||""}`);
  navigator.clipboard.writeText(parts.join("\n\n"));
}
document.getElementById("ws-copy-all")?.addEventListener("click", () => {
  const btn = document.getElementById("ws-copy-all");
  copyAll("ws"); btn.textContent = "Copied!";
  setTimeout(() => (btn.textContent = "Copy All"), 1500);
});

// ─────────────────────────────────────────────
// WORKSPACE — TRACK ACTIVE LIBRARY ITEM + SAVE
// ─────────────────────────────────────────────
let activeLibraryItemId = null; // tracks which library item is open in workspace

function loadIntoWorkspace(item) {
  // Track which item we're editing
  activeLibraryItemId = item.id;

  // Populate all 6 cards
  const keys = ["headline","thumbnailIdea","hashtags","post","cta","script"];
  const ids  = ["ws-headline","ws-thumbnail","ws-hashtags","ws-post","ws-cta","ws-script"];
  keys.forEach((k, i) => {
    const el = document.getElementById(ids[i]);
    if (el) { el.textContent = item.content[k]||""; el.dataset.original = item.content[k]||""; }
  });

  // Update save button label to reflect editing mode
  const saveBtn = document.getElementById("ws-save-btn");
  if (saveBtn) saveBtn.textContent = "Save Changes";

  document.getElementById("workspace-empty").style.display   = "none";
  document.getElementById("workspace-content").style.display = "block";
}

function getWorkspaceContent() {
  return {
    headline:      document.getElementById("ws-headline")?.textContent  || "",
    thumbnailIdea: document.getElementById("ws-thumbnail")?.textContent || "",
    hashtags:      document.getElementById("ws-hashtags")?.textContent  || "",
    post:          document.getElementById("ws-post")?.textContent      || "",
    cta:           document.getElementById("ws-cta")?.textContent       || "",
    script:        document.getElementById("ws-script")?.textContent    || "",
  };
}

document.getElementById("ws-save-btn")?.addEventListener("click", () => {
  const btn     = document.getElementById("ws-save-btn");
  const content = getWorkspaceContent();
  const library = JSON.parse(localStorage.getItem("hb_library")||"[]");

  if (activeLibraryItemId) {
    // Update existing library item in place
    const item = library.find(x => String(x.id) === String(activeLibraryItemId));
    if (item) {
      item.content  = content;
      item.status   = item.status === "published" ? "published" : "approved";
      item.savedAt  = new Date().toISOString();
    }
  } else {
    // No active item — create new (fallback)
    const saved = getSaved();
    library.unshift({
      id: Date.now(), savedAt: new Date().toISOString(),
      agentName: hb_user?.agent_name || saved.agentName || "",
      niche: activeNicheForGenerate||(saved.primaryNiches||[])[0]||"",
      status: "approved",
      content,
    });
  }

  localStorage.setItem("hb_library", JSON.stringify(library));
  btn.textContent = "Saved ✓"; btn.style.background = "var(--aqua)";
  setTimeout(() => {
    btn.textContent = "Save Changes"; btn.style.background = "";
    navigateTo("library-panel");
  }, 1000);
});

document.getElementById("ws-back-btn")?.addEventListener("click", () => navigateTo("library-panel"));

// ─────────────────────────────────────────────
// LIBRARY
// ─────────────────────────────────────────────
// ── Compliance badge HTML builder
function getComplianceBadgeHTML(compliance) {
  if (!compliance) return "";
  const statusConfig = {
    compliant: { color:"#16a34a", bg:"#f0fdf4", border:"#86efac", icon:"✓", label:"Compliance Verified" },
    review:    { color:"#d97706", bg:"#fffbeb", border:"#fcd34d", icon:"⚠", label:"Review Suggested"   },
    attention: { color:"#dc2626", bg:"#fef2f2", border:"#fca5a5", icon:"✗", label:"Attention Required"  },
  };
  const cfg = statusConfig[compliance.overallStatus] || statusConfig.review;
  const badgeParts = [
    { key:"fairHousing",         label:"Fair Housing"   },
    { key:"brokerageDisclosure", label:"Disclosure"     },
    { key:"narStandards",        label:"NAR Standards"  },
  ].map(b => {
    const s = compliance[b.key];
    const c = s==="pass" ? "#16a34a" : s==="warn" ? "#d97706" : "#dc2626";
    const i = s==="pass" ? "✓" : s==="warn" ? "⚠" : "✗";
    return `<span style="font-size:10px;color:${c};font-weight:700;">${i} ${b.label}</span>`;
  }).join("&nbsp;&nbsp;");
  const noteHTML = (compliance.notes||[]).length && compliance.overallStatus !== "compliant"
    ? `<div style="margin-top:6px;display:flex;flex-direction:column;gap:3px;">
        ${(compliance.notes||[]).slice(0,3).map(n =>
          `<div style="font-size:11px;color:${cfg.color};line-height:1.4;">· ${n}</div>`
        ).join("")}
       </div>` : "";
  return `<div style="background:${cfg.bg};border:1px solid ${cfg.border};border-radius:8px;padding:8px 10px;margin-bottom:10px;">
    <div style="font-size:11px;font-weight:700;color:${cfg.color};font-family:'Roboto Condensed',sans-serif;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:5px;">${cfg.icon} ${cfg.label}</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;">${badgeParts}</div>${noteHTML}
  </div>`;
}

// ── Create a single library card element
function createLibraryCard(item) {
  const card = document.createElement("div");
  card.className = "library-card";
  const date = new Date(item.savedAt).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});
  const isPending   = !item.status || item.status === "pending";
  const isApproved  = item.status === "approved";
  const isPublished = item.status === "published";
  const statusLabel = isPublished ? "✓ Published" : isApproved ? "✓ Approved" : "Pending Review";
  const statusColor = (isApproved||isPublished) ? "#16a34a" : "#d97706";
  card.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
      <div class="library-card-date">${date}</div>
      <div style="font-size:11px;font-weight:700;color:${statusColor};font-family:'Roboto Condensed',sans-serif;">${statusLabel}</div>
    </div>
    ${item.niche ? `<div class="library-card-niche">${item.niche}</div>` : ""}
    <div class="library-card-headline">${item.content?.headline||"Untitled"}</div>
    <div style="font-size:12px;color:var(--text-muted);line-height:1.4;margin-bottom:10px;">${(item.content?.post||"").slice(0,120)}${(item.content?.post||"").length>120?"…":""}</div>
    ${getComplianceBadgeHTML(item.compliance)}
    <div class="library-card-actions">
      ${isPending ? `<button class="btn-primary" style="font-size:12px;padding:6px 14px;" data-lib-approve="${item.id}">Approve</button>` : ""}
      <button class="btn-secondary" data-lib-load="${item.id}">Edit in Workspace</button>
      <button class="btn-secondary" style="color:var(--accent-strong);border-color:var(--accent-strong);" data-dist-open="${item.id}">🚀 Distribute</button>
      <button class="btn-secondary" style="color:#dc2626;border-color:#fca5a5;" data-lib-delete="${item.id}">Delete</button>
    </div>
  `;
  return card;
}

// ── Render full library with approval queue sections
function renderLibrary() {
  const grid = document.getElementById("library-grid");
  if (!grid) return;
  const library = JSON.parse(localStorage.getItem("hb_library")||"[]");

  if (!library.length) {
    grid.innerHTML = '<div class="library-empty">No content yet. Generate content and it will appear here ready for review and approval.</div>';
    return;
  }

  const pending   = library.filter(x => !x.status || x.status === "pending");
  const approved  = library.filter(x => x.status === "approved");
  const published = library.filter(x => x.status === "published");

  grid.innerHTML = "";

  if (pending.length) {
    const hdr = document.createElement("div");
    hdr.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
      <div style="font-family:'Roboto Condensed',sans-serif;font-size:13px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:var(--accent-strong);">Pending Approval (${pending.length})</div>
      ${pending.length > 1 ? `<button class="btn-secondary" id="approve-all-btn" style="font-size:12px;">Approve All</button>` : ""}
    </div>`;
    grid.appendChild(hdr);
    document.getElementById("approve-all-btn")?.addEventListener("click", () => {
      const lib = JSON.parse(localStorage.getItem("hb_library")||"[]");
      lib.forEach(x => { if (!x.status || x.status === "pending") x.status = "approved"; });
      localStorage.setItem("hb_library", JSON.stringify(lib));
      renderLibrary();
    });
    pending.forEach(item => grid.appendChild(createLibraryCard(item)));
  }

  if (approved.length) {
    const hdr = document.createElement("div");
    hdr.innerHTML = `<div style="font-family:'Roboto Condensed',sans-serif;font-size:13px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:var(--text-muted);margin:20px 0 12px;">Approved (${approved.length})</div>`;
    grid.appendChild(hdr);
    approved.forEach(item => grid.appendChild(createLibraryCard(item)));
  }

  if (published.length) {
    const hdr = document.createElement("div");
    hdr.innerHTML = `<div style="font-family:'Roboto Condensed',sans-serif;font-size:13px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:var(--text-muted);margin:20px 0 12px;">Published (${published.length})</div>`;
    grid.appendChild(hdr);
    published.forEach(item => grid.appendChild(createLibraryCard(item)));
  }
}

document.addEventListener("click", e => {
  if (e.target.dataset.libLoad) {
    const library = JSON.parse(localStorage.getItem("hb_library")||"[]");
    const item = library.find(x => String(x.id) === String(e.target.dataset.libLoad));
    if (!item) return;
    loadIntoWorkspace(item);
    navigateTo("workspace-panel");
  }
  if (e.target.dataset.libApprove) {
    const library = JSON.parse(localStorage.getItem("hb_library")||"[]");
    const item = library.find(x => String(x.id) === String(e.target.dataset.libApprove));
    if (item) item.status = "approved";
    localStorage.setItem("hb_library", JSON.stringify(library));
    renderLibrary();
  }
  if (e.target.dataset.libDelete) {
    const library = JSON.parse(localStorage.getItem("hb_library")||"[]");
    localStorage.setItem("hb_library", JSON.stringify(library.filter(x => String(x.id) !== String(e.target.dataset.libDelete))));
    renderLibrary();
  }
});

// ─────────────────────────────────────────────
// DISTRIBUTION — Platform Registry
// To add a new platform: add one entry to PLATFORMS array below.
// ─────────────────────────────────────────────

const PLATFORMS = [
  {
    id: "linkedin",
    label: "LinkedIn",
    icon: "💼",
    hint: "Professional · Referral-friendly · Full length",
    status: "active",
    socialKey: "social-linkedin",
    format: (c, id) => {
      const tag = id.socials.linkedin ? `\n\n🔗 ${id.socials.linkedin}` : "";
      const tags = hashtagify(c.hashtags);
      return `${c.headline}\n\n${c.post}\n\n${c.cta}\n\n📍 ${id.name}${id.brokerage ? ` · ${id.brokerage}` : ""} · ${id.market}${tag}\n\n${tags}`;
    }
  },
  {
    id: "instagram",
    label: "Instagram",
    icon: "📸",
    hint: "Visual-first · Punchy caption · Hashtag block",
    status: "active",
    socialKey: "social-instagram",
    format: (c, id) => {
      const handle = id.socials.instagram ? `\n\nFollow: ${id.socials.instagram}` : "";
      const tags = hashtagify(c.hashtags);
      const market = id.market.toLowerCase().replace(/\s+/g, "");
      return `${c.headline} 🏡\n\n${c.post}\n\n${c.cta}${handle}\n\n.\n.\n.\n${tags} #realestate #realtor #${market}`;
    }
  },
  {
    id: "facebook",
    label: "Facebook",
    icon: "👥",
    hint: "Conversational · Community-focused · Longer form",
    status: "active",
    socialKey: "social-facebook",
    format: (c, id) => {
      const link = id.socials.facebook ? `\n\n👉 ${id.socials.facebook}` : "";
      return `${c.headline}\n\n${c.post}\n\n${c.cta}${link}\n\n— ${id.name}${id.brokerage ? `, ${id.brokerage}` : ""}\n📍 ${id.market}`;
    }
  },
  {
    id: "tiktok",
    label: "TikTok",
    icon: "🎵",
    hint: "Hook-first · Short · Trending tags",
    status: "active",
    socialKey: "social-tiktok",
    format: (c, id) => {
      const hook = c.script ? c.script.split(".")[0] + "." : c.headline;
      const market = id.market.toLowerCase().replace(/\s+/g, "");
      const tags = hashtagify(c.hashtags);
      const handle = id.socials.tiktok ? `\n\n${id.socials.tiktok}` : "";
      return `${hook}\n\n${c.post.slice(0, 180)}${c.post.length > 180 ? "…" : ""}\n\n${tags} #realestate #realtortok #${market}${handle}`;
    }
  },
  {
    id: "youtube",
    label: "YouTube",
    icon: "▶️",
    hint: "Title + Description + Tags · SEO-optimized",
    status: "active",
    socialKey: "social-youtube",
    format: (c, id) => {
      const rawTags = c.hashtags.split(/\s+/).filter(Boolean).map(h => h.replace("#","")).join(", ");
      const channel = id.socials.youtube ? `\nChannel: ${id.socials.youtube}` : "";
      return `TITLE:\n${c.headline}\n\nDESCRIPTION:\n${c.post}\n\n${c.cta}\n\n📍 ${id.name} serves ${id.market}${id.brokerage ? ` with ${id.brokerage}` : ""}.${channel}\n\nTAGS:\n${rawTags}, real estate, realtor, ${id.market}, ${id.niche}`;
    }
  },
  {
    id: "twitter",
    label: "X / Twitter",
    icon: "𝕏",
    hint: "280 chars max · Hook-first · High-volume hashtags",
    status: "active",
    socialKey: "social-twitter",
    format: (c, id) => {
      const handle = id.socials.twitter ? ` ${id.socials.twitter}` : "";
      const short = c.post.slice(0, 200);
      const market = id.market.toLowerCase().replace(/\s+/g, "");
      return `${c.headline}\n\n${short}${c.post.length > 200 ? "…" : ""}\n\n#realestate #${market} #realtor${handle}`;
    }
  },
  {
    id: "threads",
    label: "Threads",
    icon: "🧵",
    hint: "Conversational · Instagram-adjacent · Growing fast",
    status: "active",
    socialKey: "social-threads",
    format: (c, id) => {
      const handle = id.socials.threads ? `\n\n${id.socials.threads}` : "";
      return `${c.headline}\n\n${c.post}\n\n${c.cta}${handle}`;
    }
  },
  {
    id: "reddit",
    label: "Reddit",
    icon: "🤖",
    hint: "Community-first · No hard sell · Value-driven",
    status: "active",
    socialKey: "social-reddit",
    format: (c, id) => {
      const handle = id.socials.reddit ? `\n\n— ${id.socials.reddit}` : "";
      return `**${c.headline}**\n\n${c.post}\n\n${c.cta}\n\nHappy to answer questions — ${id.name}, ${id.market}.${handle}\n\n*Posted in r/RealEstate and local market subs*`;
    }
  },
  {
    id: "google",
    label: "Google Business",
    icon: "🔍",
    hint: "Boosts local search + AI recommendations · High ROI",
    status: "active",
    socialKey: "social-google",
    format: (c, id) => {
      const link = id.socials.google ? `\n\n🔗 ${id.socials.google}` : "";
      return `${c.headline}\n\n${c.post}\n\n${c.cta}\n\n📍 ${id.name} · ${id.market}${id.brokerage ? ` · ${id.brokerage}` : ""}${link}`;
    }
  },
  {
    id: "pinterest",
    label: "Pinterest",
    icon: "📌",
    hint: "Visual boards · Home search audience · Long shelf life",
    status: "active",
    socialKey: "social-pinterest",
    format: (c, id) => {
      const handle = id.socials.pinterest ? `\n\nFollow: ${id.socials.pinterest}` : "";
      const tags = hashtagify(c.hashtags);
      return `${c.headline}\n\n${c.post}\n\n${c.cta}${handle}\n\n${tags} #homebuying #realestate #${id.market.toLowerCase().replace(/\s+/g,"")}`;
    }
  },
  {
    id: "email",
    label: "Email Newsletter",
    icon: "✉️",
    hint: "Direct to inbox · No algorithm · Highest conversion",
    status: "active",
    socialKey: "social-email",
    format: (c, id) => {
      return `SUBJECT LINE:\n${c.headline}\n\n---\n\nHi [First Name],\n\n${c.post}\n\n${c.cta}\n\nBest,\n${id.name}${id.brokerage ? `\n${id.brokerage}` : ""}\n📍 ${id.market}${id.socials.email ? `\n${id.socials.email}` : ""}`;
    }
  },
];

function hashtagify(hashtags) {
  return (hashtags || "").split(/\s+/).filter(Boolean).map(h => h.startsWith("#") ? h : `#${h}`).join(" ");
}

function getSocials() {
  return JSON.parse(localStorage.getItem("hb_socials") || "{}");
}

function formatForPlatform(platform, content, identity) {
  const p = PLATFORMS.find(x => x.id === platform);
  if (!p) return content.post || "";
  return p.format(content, identity);
}

function openDistribution(content, nicheLabel) {
  const saved   = getSaved();
  const socials = getSocials();
  const identity = {
    name:      saved.agentName  || hb_user?.agent_name || "",
    brokerage: saved.brokerage  || hb_user?.brokerage  || "",
    market:    saved.market     || "",
    niche:     nicheLabel       || (saved.primaryNiches||[])[0] || "",
    socials: {
      linkedin:  socials.linkedin  || "",
      instagram: socials.instagram || "",
      facebook:  socials.facebook  || "",
      tiktok:    socials.tiktok    || "",
      youtube:   socials.youtube   || "",
      twitter:   socials.twitter   || "",
      threads:   socials.threads   || "",
      reddit:    socials.reddit    || "",
      google:    socials.google    || "",
      pinterest: socials.pinterest || "",
      email:     socials.email     || "",
      website:   socials.website   || "",
    },
  };

  const modal = document.getElementById("distribution-modal");
  const body  = document.getElementById("distribution-modal-body");
  if (!modal || !body) return;

  body.innerHTML = "";
  PLATFORMS.filter(p => p.status === "active").forEach(p => {
    const formatted = p.format(content, identity);
    const card = document.createElement("div");
    card.className = "dist-card";
    card.innerHTML = `
      <div class="dist-card-header">
        <div class="dist-card-title">${p.icon} ${p.label}</div>
        <div class="dist-card-hint">${p.hint}</div>
      </div>
      <div class="dist-card-body" id="dist-${p.id}" contenteditable="true">${formatted}</div>
      <button class="btn-secondary dist-copy-btn" data-platform="${p.id}" data-label="${p.label}">Copy for ${p.label}</button>
    `;
    body.appendChild(card);
  });

  body.querySelectorAll(".dist-copy-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const el = document.getElementById(`dist-${btn.dataset.platform}`);
      if (!el) return;
      navigator.clipboard.writeText(el.textContent || "").then(() => {
        const orig = btn.textContent;
        btn.textContent = "Copied! ✓";
        btn.style.cssText = "background:var(--aqua);color:#fff;border-color:var(--aqua);";
        setTimeout(() => { btn.textContent = orig; btn.style.cssText = ""; }, 2000);
      });
    });
  });

  modal.classList.add("visible");
  document.body.style.overflow = "hidden";
}

function closeDistribution() {
  document.getElementById("distribution-modal")?.classList.remove("visible");
  document.body.style.overflow = "";
}
document.getElementById("dist-modal-close")?.addEventListener("click", closeDistribution);
document.getElementById("distribution-modal")?.addEventListener("click", e => {
  if (e.target.id === "distribution-modal") closeDistribution();
});
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDistribution(); });

document.addEventListener("click", e => {
  if (e.target.dataset.distOpen) {
    const library = JSON.parse(localStorage.getItem("hb_library")||"[]");
    const item = library.find(x => String(x.id) === String(e.target.dataset.distOpen));
    if (item) openDistribution(item.content, item.niche);
  }
  if (e.target.id === "ws-distribute-btn") {
    openDistribution(
      getWorkspaceContent(),
      activeNicheForGenerate||(getSaved().primaryNiches||[])[0]||""
    );
  }
});

// ─────────────────────────────────────────────
// PROFILE PANEL
// ─────────────────────────────────────────────
function renderProfilePanel() {
  const user = JSON.parse(localStorage.getItem("hb_user")||"null");
  if (!user) return;
  const el = id => document.getElementById(id);
  if (el("profile-name"))      el("profile-name").value      = user.agent_name || "";
  if (el("profile-brokerage")) el("profile-brokerage").value = user.brokerage  || "";
  if (el("profile-email"))     el("profile-email").value     = user.email      || "";
  if (el("profile-phone"))     el("profile-phone").value     = user.phone      || "";
  // MLS fields from localStorage
  const mls = JSON.parse(localStorage.getItem("hb_mls")||"[]");
  if (el("profile-mls-1")) el("profile-mls-1").value = mls[0] || "";
  if (el("profile-mls-2")) el("profile-mls-2").value = mls[1] || "";
  if (el("profile-mls-3")) el("profile-mls-3").value = mls[2] || "";
  loadSocialAccounts();
}

// ── SOCIAL ACCOUNTS SAVE/LOAD ──
function loadSocialAccounts() {
  const socials = getSocials();
  const fields = ["linkedin","instagram","facebook","tiktok","youtube","twitter","threads","reddit","google","pinterest","email","website"];
  fields.forEach(k => {
    const el = document.getElementById(`social-${k}`);
    if (el && socials[k]) el.value = socials[k];
  });
}

document.getElementById("save-socials-btn")?.addEventListener("click", () => {
  const fields = ["linkedin","instagram","facebook","tiktok","youtube","twitter","threads","reddit","google","pinterest","email","website"];
  const socials = {};
  fields.forEach(k => {
    const el = document.getElementById(`social-${k}`);
    if (el) socials[k] = el.value.trim();
  });
  localStorage.setItem("hb_socials", JSON.stringify(socials));
  const btn = document.getElementById("save-socials-btn");
  btn.textContent = "Saved ✓";
  btn.style.background = "var(--aqua)";
  setTimeout(() => { btn.textContent = "Save accounts"; btn.style.background = ""; }, 1800);
});

document.getElementById("save-profile-btn")?.addEventListener("click", async () => {
  const btn = document.getElementById("save-profile-btn");
  hideError("profile-error");
  hideError("profile-success");

  const agent_name = document.getElementById("profile-name")?.value.trim()      || "";
  const brokerage  = document.getElementById("profile-brokerage")?.value.trim() || "";
  const email      = document.getElementById("profile-email")?.value.trim()     || "";
  const phone      = document.getElementById("profile-phone")?.value.trim()     || "";

  if (!agent_name || !email) {
    showError("profile-error", "Name and email are required.");
    return;
  }

  btn.disabled = true; btn.textContent = "Saving…";

  try {
    const res = await authFetch(`${BACKEND_URL}/auth/profile`, {
      method: "POST",
      body: JSON.stringify({ agent_name, brokerage, email, phone }),
    });
    const data = await res.json();
    if (!res.ok) { showError("profile-error", data.detail || "Update failed."); return; }

    // Update local storage
    const updated = { ...JSON.parse(localStorage.getItem("hb_user")||"{}"), ...data.user };
    localStorage.setItem("hb_user", JSON.stringify(updated));

    // Update avatar in sidebar
    updateSidebarAvatar();

    // Sync agent name + brokerage into hb_setup so content generation stays fresh
    const currentSetup = getSaved();
    currentSetup.agentName = data.user.agent_name;
    currentSetup.brokerage = data.user.brokerage || "";
    localStorage.setItem("hb_setup", JSON.stringify(currentSetup));

    // Save MLS fields
    const mls = [
      document.getElementById("profile-mls-1")?.value.trim() || "",
      document.getElementById("profile-mls-2")?.value.trim() || "",
      document.getElementById("profile-mls-3")?.value.trim() || "",
    ].filter(Boolean);
    localStorage.setItem("hb_mls", JSON.stringify(mls));

    showError("profile-success", "✓ Profile updated successfully.");

  } catch (err) {
    showError("profile-error", "Could not reach server. Please try again.");
  } finally {
    btn.disabled = false; btn.textContent = "Save changes";
  }
});

document.getElementById("save-password-btn")?.addEventListener("click", async () => {
  const btn = document.getElementById("save-password-btn");
  hideError("profile-error");

  const current  = document.getElementById("profile-current-password")?.value || "";
  const newPass  = document.getElementById("profile-new-password")?.value     || "";
  const confirm  = document.getElementById("profile-confirm-password")?.value || "";

  if (!current || !newPass || !confirm) { showError("profile-error","All password fields are required."); return; }
  if (newPass.length < 8)               { showError("profile-error","New password must be at least 8 characters."); return; }
  if (newPass !== confirm)              { showError("profile-error","New passwords do not match."); return; }

  btn.disabled = true; btn.textContent = "Updating…";

  try {
    const res = await authFetch(`${BACKEND_URL}/auth/change-password`, {
      method: "POST",
      body: JSON.stringify({ current_password: current, new_password: newPass }),
    });
    const data = await res.json();
    if (!res.ok) { showError("profile-error", data.detail||"Password update failed."); return; }
    showError("profile-success","✓ Password updated.");
    document.getElementById("profile-current-password").value = "";
    document.getElementById("profile-new-password").value     = "";
    document.getElementById("profile-confirm-password").value = "";
  } catch (err) {
    showError("profile-error","Could not reach server.");
  } finally {
    btn.disabled = false; btn.textContent = "Update password";
  }
});

// ─────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────
loadSetup();
renderIdentitySummary();
renderTrendDisplay();
renderNicheSelector();
// Situations loaded dynamically when Content Engine panel opens
const _initNiche = (() => {
  const saved = getSaved();
  return activeNicheForGenerate || (saved.primaryNiches||[])[0] || null;
})();
populateSituationDropdown(_initNiche);

console.log("HomeBridge UI v3 — clean build. Backend:", BACKEND_URL);
