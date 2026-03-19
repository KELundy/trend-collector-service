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
# MODELS
# ─────────────────────────────────────────────
class IdentityModel(BaseModel):
    primaryCategories: List[str] = Field(default_factory=list)
    subNichesByCategory: Dict[str, List[str]] = Field(default_factory=dict)
    trendPreferences: List[str] = Field(default_factory=list)


class AgentProfileModel(BaseModel):
    agentName: Optional[str] = Field(None)
    businessName: Optional[str] = Field(None)
    brokerage: Optional[str] = Field(None)
    market: Optional[str] = Field(None)
    brandVoice: Optional[str] = Field(None)
    shortBio: Optional[str] = Field(None)
    audienceDescription: Optional[str] = Field(None)
    wordsAvoid: Optional[str] = Field(None)
    wordsPrefer: Optional[str] = Field(None)
    mlsNames: Optional[List[str]] = Field(default_factory=list)
    serviceAreas: Optional[List[str]] = Field(default_factory=list)
    designations: Optional[List[str]] = Field(default_factory=list)
    languagePref: Optional[str] = Field("english")


class ComplianceBadge(BaseModel):
    fairHousing: str
    brokerageDisclosure: str
    narStandards: str
    overallStatus: str
    notes: List[str] = Field(default_factory=list)


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
    agentProfile: Optional[AgentProfileModel] = Field(None)
    situation: str
    persona: Optional[str] = None
    tone: Optional[str] = None
    length: Optional[str] = None
    selectedTrends: List[str] = Field(default_factory=list)
    timestamp: Optional[str] = None
    content_mode: Optional[str] = Field("agent")


def _get_anthropic_client():
    if Anthropic is None:
        raise RuntimeError("Anthropic Python client is not installed.")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
    return Anthropic(api_key=api_key)


def _build_content_prompt(payload):
    identity = payload.identity
    profile  = payload.agentProfile or AgentProfileModel()

    agent_name    = profile.agentName    or "the agent"
    business_name = profile.businessName or ""
    brokerage     = profile.brokerage    or ""
    base_market   = profile.market       or "their local market"
    service_areas = profile.serviceAreas or []
    market        = (f"{base_market} (serving: {', '.join(service_areas)})" if service_areas else base_market)
    brand_voice   = profile.brandVoice   or "conversational and genuine"
    short_bio     = profile.shortBio     or ""
    audience      = profile.audienceDescription or ""
    words_avoid   = profile.wordsAvoid   or ""
    words_prefer  = profile.wordsPrefer  or ""

    agent_display = agent_name
    if business_name:
        agent_display += f" of {business_name}"
    if brokerage and brokerage.lower() not in business_name.lower():
        agent_display += f" with {brokerage}"

    primary_categories = ", ".join(identity.primaryCategories) or "real estate"
    subniche_lines = []
    for cat, subs in identity.subNichesByCategory.items():
        if subs:
            subniche_lines.append("  - {}: {}".format(cat, ", ".join(subs)))
    subniches_text  = "\n".join(subniche_lines) or "  - General real estate services"
    trend_prefs     = ", ".join(identity.trendPreferences) or "current market conditions"
    selected_trends = ", ".join(payload.selectedTrends)    or "current market activity"

    tone_text    = f"Voice: {payload.tone}.\n"    if payload.tone   else f"Voice: {brand_voice}.\n"
    length_text  = f"Length: {payload.length}.\n" if payload.length else "Length: medium.\n"
    avoid_text   = f"Never use these words or phrases: {words_avoid}.\n" if words_avoid else ""
    prefer_text  = f"Naturally weave in these words or phrases: {words_prefer}.\n" if words_prefer else ""
    bio_text     = f"About {agent_name}: {short_bio}\n" if short_bio else ""
    audience_text = f"Who reads this: {audience}\n" if audience else ""
    desig_list    = profile.designations or []
    desig_context = f"Professional designations: {', '.join(desig_list)}." if desig_list else ""

    lang_pref = (profile.languagePref or "english").lower()
    if lang_pref == "spanish":
        lang_instruction = "LANGUAGE: Write ALL content entirely in Spanish."
    elif lang_pref == "bilingual":
        lang_instruction = "LANGUAGE: Write BILINGUAL content — English first, then Spanish translation."
    else:
        lang_instruction = ""

    brokerage_footer = f" | {brokerage}" if brokerage else ""
    brokerage_disclosure = (
        f'Brokerage disclosure required: end the post with "— {agent_name}{brokerage_footer}" as a quiet footer.'
        if brokerage else
        f'End with "— {agent_name}" as a natural sign-off.'
    )
    brokerage_compliance = brokerage if brokerage else "agent's brokerage"

    return f"""You are ghostwriting for {agent_display}, a real estate professional in {market}.

Your job is to write content that sounds exactly like a knowledgeable human being sharing what they know — not like a marketing campaign, not like an advertisement, and absolutely not like a sales pitch.

WHO {agent_name.upper()} IS
{"─" * 40}
{bio_text}{audience_text}Market: {market}
{desig_context}
{lang_instruction}
Specialization: {primary_categories}
Areas of depth: {subniches_text}

WHAT THIS CONTENT IS ABOUT
{"─" * 40}
Situation: {payload.situation}
Relevant signals: {selected_trends}
Context: {trend_prefs}

VOICE & STYLE
{"─" * 40}
{tone_text}{length_text}{avoid_text}{prefer_text}
THE MOST IMPORTANT THING
{"─" * 40}
This content must sound like a real person thinking out loud. The reader should feel like they're getting insight from someone who knows this world deeply — not like they're being sold to.

BANNED FOREVER:
- "Don't miss out" / "Act now" / "Limited time"
- "Call me today" as the opener or the whole point
- Exclamation points used to manufacture excitement
- Hype phrases: "game-changer", "incredible opportunity", "the market is on fire"
- Generic prompts to "like, share, and follow"

WHAT GREAT CONTENT SOUNDS LIKE:
- An observation the agent genuinely made: "Something I've been noticing in {market} lately..."
- A nuanced take only someone in the field would have: "Most people assume X, but what's actually happening is Y..."
- Honest acknowledgment of complexity: "There's no clean answer here, but the thing worth understanding is..."

THE CLOSING:
- Never a hard sell. Instead, plant a seed of curiosity.
- Good: "If you're thinking about this, it's worth a conversation — no agenda, just context."
- Bad: "Call {agent_name} TODAY to get started on your real estate journey!"

IDENTITY RULES
{"─" * 40}
1. {agent_name} must appear naturally in the post as a first-person voice or sign-off.
2. {brokerage_disclosure}
3. Always say "{market}" specifically — never "your local area."
4. The script must sound like someone actually talking — natural pauses, real sentences.

COMPLIANCE RULES
{"─" * 40}
- Fair Housing Act: No language implying preference by protected class. No steering. Focus on property facts.
- NAR Code of Ethics Article 12: Truthful only. No guaranteed outcomes. No "best agent" language.
- Brokerage disclosure: {brokerage_compliance} must be identifiable. Agent's licensed name must appear.
- No specific financial predictions. No guaranteed investment returns.

OUTPUT FORMAT — RETURN ONLY VALID JSON, NOTHING ELSE
{"─" * 40}
{{
  "headline": "A clear, specific, human headline. One sentence, no period.",
  "thumbnailIdea": "A grounded realistic visual concept specific to this niche and market. 1-2 sentences.",
  "hashtags": "#hashtag1 #hashtag2 (8-12 tags, space-separated)",
  "post": "A full social post in {agent_name}'s voice. NOT a sales pitch. Ends with: — {agent_name}{brokerage_footer}",
  "cta": "A low-pressure genuine next step — an invitation to a conversation, not a sales command.",
  "script": "A complete 45-75 second spoken script. Natural, conversational, specific to {market}. No announcer voice."
}}

HARD RULES:
- Every value must be complete — no placeholders
- post MUST contain {agent_name}{brokerage_footer if brokerage else ""} — legal disclosure requirement
- {market} must appear in the post or script
- No line breaks inside JSON string values — use spaces between sentences
- Return ONLY the JSON object."""


def _build_b2b_content_prompt(payload):
    identity = payload.identity
    profile  = payload.agentProfile or AgentProfileModel()

    company_name  = profile.agentName    or "HomeBridge Group"
    brand_voice   = profile.brandVoice   or "authoritative, forward-thinking, direct. No jargon. No hype."
    short_bio     = profile.shortBio     or "HomeBridge is the AI-powered content platform that keeps real estate professionals visible, compliant, and trusted."
    audience      = profile.audienceDescription or "Real estate brokers, office managers, and team leads."
    words_avoid   = profile.wordsAvoid   or "synergy, leverage, disrupt, hustle, game-changer"
    words_prefer  = profile.wordsPrefer  or "trusted, verified, authentic, compliant, visible"
    disclaimer    = profile.brokerage    or "HomeBridge Group · AI-powered content platform for real estate professionals · homebridgegroup.co"

    primary_categories = ", ".join(identity.primaryCategories) or "real estate technology"
    selected_trends    = ", ".join(payload.selectedTrends)     or "AI in real estate, content authenticity, agent visibility"

    tone_text   = f"Voice: {payload.tone}.\n"    if payload.tone   else f"Voice: {brand_voice}.\n"
    length_text = f"Length: {payload.length}.\n" if payload.length else "Length: medium — concise and substantive.\n"
    avoid_text  = f"Never use these words or phrases: {words_avoid}.\n" if words_avoid else ""
    prefer_text = f"Naturally weave in these words or phrases: {words_prefer}.\n" if words_prefer else ""
    persona_context = f"The person this post will resonate with most: {payload.persona}." if payload.persona else ""

    return f"""You are writing thought leadership content FOR {company_name}, a real estate technology company.

This is NOT ghostwriting for a real estate agent. This is B2B content marketing — {company_name} speaking directly to brokers and office managers about challenges they face with agent visibility, compliance, and brand consistency.

ABOUT {company_name.upper()}
{"─" * 40}
{short_bio}

WHO THIS REACHES
{"─" * 40}
Primary audience: {audience}
{persona_context}

WHAT THIS CONTENT IS ABOUT
{"─" * 40}
Situation: {payload.situation}
Topic area: {primary_categories}
Relevant signals: {selected_trends}

VOICE & STYLE
{"─" * 40}
{tone_text}{length_text}{avoid_text}{prefer_text}
THE MOST IMPORTANT THING
{"─" * 40}
This content must position {company_name} as the company that actually understands what brokers are dealing with — not the company trying to sell them something. The reader should feel understood before they feel pitched.

The best B2B thought leadership:
- Names a problem the reader recognizes immediately: "Every broker I talk to says the same thing: their agents know their market, but no one knows them."
- Shares a perspective that challenges conventional thinking: "The agents winning on social media aren't posting more — they're posting smarter."
- Demonstrates expertise without showing off: "Here's what we've learned from watching hundreds of agents build their online presence..."
- Creates a moment of recognition: "If your office's social presence depends entirely on which agents happen to be active that week, you have a consistency problem."

WHAT TO AVOID
{"─" * 40}
- Product feature lists ("HomeBridge does X, Y, Z")
- Self-promotional headlines ("Why HomeBridge is the best solution")
- Generic B2B language ("leverage synergies", "streamline workflows", "robust platform")
- Claiming to be the only solution or definitively the best

WHAT GREAT B2B CONTENT SOUNDS LIKE
{"─" * 40}
- Industry observation with a point of view: "The Compass-Anywhere merger just created the world's largest brokerage. The brokers who survive won't be the ones with the most agents — they'll be the ones with the most visible agents."
- A challenge reframed: "Compliance in real estate social media isn't a legal department problem. It's a marketing problem that legal departments are being asked to solve."
- A concrete truth: "An agent who posts three times a week — even with half the expertise — will be found before the agent who posts once a month. Visibility functions like credibility."

CLOSING PHILOSOPHY
{"─" * 40}
The CTA should invite a conversation — never a hard sell.
Good: "We built HomeBridge specifically for this problem. Happy to show you what it looks like for your office."
Bad: "Sign up for HomeBridge today and transform your brokerage's digital presence!"

Every post must end with: — {disclaimer}

OUTPUT FORMAT — RETURN ONLY VALID JSON, NOTHING ELSE
{"─" * 40}
{{
  "headline": "A sharp specific headline that a broker would immediately recognize as relevant. One sentence, no period. A point of view — not a product pitch.",
  "thumbnailIdea": "A visual concept conveying technology, trust, or real estate professionalism. Modern, clean, not generic stock. 1-2 sentences.",
  "hashtags": "#hashtag1 #hashtag2 (8-10 tags — mix of real estate tech, brokerage management, PropTech)",
  "post": "A full LinkedIn/social post written as {company_name}. Reads like a company with a genuine point of view. Ends with: — {disclaimer}",
  "cta": "A low-pressure invitation — a conversation offer, not a sales command.",
  "script": "A 45-75 second spoken script. Sounds like a real person from the company talking — no announcer voice, genuine and specific."
}}

HARD RULES:
- Every value must be complete — no placeholders
- post MUST contain "{disclaimer}" as the footer
- No line breaks inside JSON string values
- Do NOT mention specific pricing or make competitive comparisons by name
- Return ONLY the JSON object."""



# ─────────────────────────────────────────────
# COMPLIANCE RULE ENGINE
# ─────────────────────────────────────────────

COMPLIANCE_RULES = {
  "fair_housing": {
    "id": "fair_housing",
    "authority": "Fair Housing Act (42 U.S.C. § 3604)",
    "severity": "warn",
    "terms": [
      "perfect for families", "great for families", "ideal for families",
      "walking distance to churches", "good schools nearby", "safe neighborhood",
      "exclusive neighborhood", "desirable neighborhood", "up and coming",
      "gentrifying", "transitional neighborhood", "no children", "adults only",
      "perfect for couples", "ideal for young professionals", "bachelor pad",
      "master bedroom", "master bath", "integrated", "segregated",
      "hispanic neighborhood", "asian neighborhood", "school district", "quiet street",
    ],
    "message": "Fair Housing Act: phrase(s) may imply discriminatory steering. Use property-focused language only.",
  },
  "nar_article12": {
    "id": "nar_article12",
    "authority": "NAR Code of Ethics Article 12",
    "severity": "warn",
    "terms": [
      "guaranteed", "i promise", "best in the city", "number one agent",
      "top agent in", "will sell your home", "promise you", "i guarantee",
      "100% success", "never fails", "best agent", "highest rated",
      "#1 agent", "number 1 agent",
    ],
    "message": "NAR Article 12: unverifiable claim detected. Remove or qualify the statement.",
  },
  "respa_section8": {
    "id": "respa_section8",
    "authority": "RESPA Section 8 (12 U.S.C. § 2607)",
    "severity": "warn",
    "terms": [
      "referral fee", "kickback", "split the commission", "finder's fee",
      "paid for referral", "referral payment", "split my commission",
      "receive a fee", "compensation for referral", "refer and earn",
    ],
    "message": "RESPA Section 8: language may imply a referral fee or kickback arrangement.",
  },
  "clear_cooperation": {
    "id": "clear_cooperation",
    "authority": "NAR Clear Cooperation Policy",
    "severity": "warn",
    "terms": [
      "pocket listing", "off-market exclusive", "coming soon exclusive",
      "pre-mls", "pre mls", "off mls", "not on the mls",
      "exclusive off-market", "private listing", "silent listing",
    ],
    "message": "MLS Cooperation: language may conflict with Clear Cooperation Policy.",
  },
  "state_commission": {
    "id": "state_commission",
    "authority": "State Real Estate Commission (varies by state)",
    "severity": "warn",
    "terms": [
      "as-is no inspection", "no inspection needed", "skip the inspection",
      "guaranteed to appreciate", "will increase in value", "guaranteed roi",
      "investment guaranteed", "never lose money", "risk free investment",
      "perfect investment", "zero risk",
    ],
    "message": "State Commission: language may conflict with state advertising standards.",
  },
  "sec_investment_disclosure": {
    "id": "sec_investment_disclosure",
    "authority": "SEC Rule 10b-5 / Securities Act Section 17(b)",
    "severity": "fail",
    "terms": [
      "projected return", "expected return", "annual return of", "irr of",
      "cap rate guarantee", "guaranteed cap rate", "regulation d offering",
      "accredited investors only",
    ],
    "message": "SEC Rule 10b-5: securities-adjacent language detected. Legal review required.",
  },
  "sec_investment_risk": {
    "id": "sec_investment_risk",
    "authority": "SEC General Anti-Fraud / Rule 10b-5",
    "severity": "warn",
    "terms": [
      "safe investment", "guaranteed income", "passive income guaranteed",
      "risk-free", "no risk", "certain returns", "will cash flow",
      "guaranteed cash flow", "will appreciate",
    ],
    "message": "SEC: language implying guaranteed investment outcomes may be a securities violation.",
  },
  "finra_communications": {
    "id": "finra_communications",
    "authority": "FINRA Rule 2210",
    "severity": "warn",
    "terms": ["financial advisor recommends", "broker recommends", "strong buy", "must buy investment"],
    "message": "FINRA Rule 2210: content referencing financial recommendations may trigger broker-dealer standards.",
  },
  "fincen_aml": {
    "id": "fincen_aml",
    "authority": "FinCEN Geographic Targeting Orders / Bank Secrecy Act",
    "severity": "warn",
    "terms": [
      "cash only", "cash buyers preferred", "no financing required",
      "anonymous buyer", "no questions asked", "offshore buyer", "wire transfer only",
    ],
    "message": "FinCEN / BSA: language may attract AML scrutiny.",
  },
  "cercla_environmental": {
    "id": "cercla_environmental",
    "authority": "CERCLA (42 U.S.C. § 9601) / ASTM Phase I Standards",
    "severity": "fail",
    "terms": [
      "clean site", "no environmental issues", "environmentally clean",
      "no contamination", "no phase i needed",
    ],
    "message": "CERCLA: representing a property as environmentally clean without Phase I ESA is a material misrepresentation.",
  },
  "commercial_investment_disclaimer": {
    "id": "commercial_investment_disclaimer",
    "authority": "State Real Estate Commission / NAR Article 12",
    "severity": "warn",
    "terms": [
      "guaranteed noi", "noi will be", "income guaranteed",
      "lease guaranteed", "tenant guaranteed", "guaranteed occupancy", "will produce income",
    ],
    "message": "Commercial Investment: projecting guaranteed income may violate state advertising standards.",
  },
  "tier_certification_claims": {
    "id": "tier_certification_claims",
    "authority": "Uptime Institute Tier Certification Standards",
    "severity": "fail",
    "terms": [
      "tier iv certified", "tier 4 certified", "tier iii certified", "tier 3 certified",
      "uptime certified", "certified tier", "tier-certified",
    ],
    "message": "Uptime Institute: tier certification claims require active audited certification.",
  },
  "soc2_claims": {
    "id": "soc2_claims",
    "authority": "AICPA SOC 2 Standards / FTC Act Section 5",
    "severity": "warn",
    "terms": ["soc 2 compliant", "soc2 compliant", "soc 2 certified", "fully soc compliant"],
    "message": "SOC 2: use 'SOC 2 Type II audited' not 'SOC 2 compliant'.",
  },
  "ferc_power_claims": {
    "id": "ferc_power_claims",
    "authority": "FERC / Federal Power Act",
    "severity": "warn",
    "terms": ["guaranteed power", "power guaranteed", "100% uptime power", "unlimited power"],
    "message": "FERC: absolute power guarantees require qualification.",
  },
  "cfius_awareness": {
    "id": "cfius_awareness",
    "authority": "CFIUS (50 U.S.C. § 4565) / FIRRMA",
    "severity": "warn",
    "terms": [
      "foreign investor welcome", "international buyers welcome",
      "open to foreign capital", "no restrictions on foreign", "foreign ownership available",
    ],
    "message": "CFIUS / FIRRMA: data center assets are subject to foreign investment review.",
  },
  "critical_infrastructure_disclosure": {
    "id": "critical_infrastructure_disclosure",
    "authority": "DHS Critical Infrastructure Framework / FISMA",
    "severity": "warn",
    "terms": [
      "government tenant", "dod tenant", "federal government client",
      "classified facility", "scif", "clearance required", "cleared facility",
    ],
    "message": "Critical Infrastructure: references to government tenants require additional security review.",
  },
  "ppa_claims": {
    "id": "ppa_claims",
    "authority": "FERC / State PUC Regulations / FTC Green Guides (16 C.F.R. Part 260)",
    "severity": "warn",
    "terms": [
      "100% renewable", "fully renewable", "carbon neutral facility",
      "green powered", "net zero facility", "zero carbon data center",
    ],
    "message": "Renewable claims must be supported by verified PPAs or RECs. May violate FTC Green Guides.",
  },
  "nmls_disclosure": {
    "id": "nmls_disclosure",
    "authority": "SAFE Act / CFPB Regulation Z",
    "severity": "warn",
    "terms": ["loan officer", "mortgage advisor", "lender", "mortgage broker"],
    "message": "SAFE Act: Mortgage professional content must include NMLS license number.",
  },
  "regulation_z": {
    "id": "regulation_z",
    "authority": "CFPB Regulation Z (12 C.F.R. § 1026)",
    "severity": "fail",
    "terms": ["rates as low as", "payment of only", "only $", "payments starting at", "% interest rate"],
    "message": "Regulation Z: quoting rates or payments triggers full APR disclosure requirements.",
  },
  "ftc_endorsement": {
    "id": "ftc_endorsement",
    "authority": "FTC Endorsement Guides (16 C.F.R. Part 255)",
    "severity": "warn",
    "terms": [
      "results not typical", "typical results", "customers report",
      "studies show", "proven to", "clinically proven", "endorsed by",
    ],
    "message": "FTC Endorsement Guides: performance claims must be substantiated.",
  },
  "ftc_claims": {
    "id": "ftc_claims",
    "authority": "FTC Act Section 5",
    "severity": "warn",
    "terms": [
      "100% guarantee", "guaranteed results", "never fails", "always works",
      "the only platform", "the only tool", "no other platform",
    ],
    "message": "FTC Act Section 5: absolute claims must be substantiated.",
  },
  "can_spam": {
    "id": "can_spam",
    "authority": "CAN-SPAM Act (15 U.S.C. § 7701)",
    "severity": "warn",
    "terms": ["unsubscribe", "opt out", "remove me", "stop emails"],
    "message": "CAN-SPAM: email content must include opt-out mechanism and physical address.",
  },
}


COMPLIANCE_PROFILES = {
  "residential": ["fair_housing", "nar_article12", "respa_section8", "clear_cooperation", "state_commission"],
  "commercial":  ["nar_article12", "respa_section8", "state_commission", "sec_investment_disclosure", "sec_investment_risk", "finra_communications", "fincen_aml", "cercla_environmental", "commercial_investment_disclaimer"],
  "data_center": ["nar_article12", "state_commission", "sec_investment_disclosure", "sec_investment_risk", "finra_communications", "fincen_aml", "tier_certification_claims", "soc2_claims", "ferc_power_claims", "cfius_awareness", "critical_infrastructure_disclosure", "ppa_claims", "commercial_investment_disclaimer"],
  "investment":  ["nar_article12", "state_commission", "sec_investment_disclosure", "sec_investment_risk", "fincen_aml", "commercial_investment_disclaimer"],
  "mortgage":    ["nmls_disclosure", "regulation_z", "respa_section8", "fair_housing", "state_commission"],
  "b2b_saas":    ["ftc_endorsement", "ftc_claims", "can_spam", "nar_article12"],
}


NICHE_COMPLIANCE_PROFILE = {
  "Residential Buying & Selling": "residential",
  "First-Time Homebuyers": "residential",
  "Luxury Real Estate": "residential",
  "Seniors & 55+ Communities": "residential",
  "New Construction": "residential",
  "Move-Up Buyers": "residential",
  "Relocation": "residential",
  "Veterans & Military": "residential",
  "Condos & Townhomes": "residential",
  "Multi-Family (2-4 Units)": "residential",
  "Short Sale & Foreclosure": "residential",
  "Residential Leasing": "residential",
  "Commercial Sales": "commercial",
  "Commercial Leasing": "commercial",
  "Office Space": "commercial",
  "Retail & Mixed-Use": "commercial",
  "Industrial & Warehouse": "commercial",
  "Medical & Dental": "commercial",
  "Multi-Family (5+ Units)": "commercial",
  "Hospitality": "commercial",
  "Land & Development": "residential",
  "Ranch & Farm / Agricultural": "residential",
  "Recreational & Mountain": "residential",
  "Vacant Land": "residential",
  "Property Management": "residential",
  "Investment Analysis": "investment",
  "Transaction Coordination": "residential",
  "Appraisal & Valuation": "residential",
  "Ultra-Luxury / UHNW": "commercial",
  "Second Homes & Vacation": "residential",
  "Luxury New Construction": "residential",
  "Divorce & Separation": "residential",
  "Probate & Inherited Homes": "residential",
  "Empty Nesters & Downsizing": "residential",
  "Young Professionals": "residential",
  "Families with Children": "residential",
  "Pre-Foreclosure & Hardship": "residential",
  "Estate & Probate Sales": "residential",
  "Care-Driven Transitions": "residential",
  "Emergency Relocation": "residential",
  "Fix & Flip": "investment",
  "Long-Term Rentals (BRRRR)": "investment",
  "Short-Term Rentals / Airbnb": "investment",
  "Mid-Term Rentals": "investment",
  "1031 Exchange": "investment",
  "Opportunity Zones": "investment",
  "Data Centers": "data_center",
  "Colocation Facilities": "data_center",
  "Hyperscale Campuses": "data_center",
  "Edge Data Centers": "data_center",
  "Powered Shells": "data_center",
  "Cloud Infrastructure Real Estate": "data_center",
  "Telecom & Fiber Infrastructure": "data_center",
  "Network Facilities": "data_center",
  "Broker & Office Management": "b2b_saas",
  "Agent Productivity & Technology": "b2b_saas",
  "Real Estate Compliance": "b2b_saas",
  "PropTech & Innovation": "b2b_saas",
  "Mortgage & Lending": "mortgage",
  "Seniors & Downsizing": "residential",
  "Luxury": "residential",
  "First-Time Buyers": "residential",
  "Investors": "investment",
  "Veterans": "residential",
  "Distressed / Pre-Foreclosure": "residential",
  "Land & Rural": "residential",
  "Short-Term Rentals": "investment",
}


def _get_compliance_profile(niche):
    return NICHE_COMPLIANCE_PROFILE.get(niche, "residential")


def _get_rules_for_profile(profile_name):
    rule_ids = COMPLIANCE_PROFILES.get(profile_name, COMPLIANCE_PROFILES["residential"])
    return [COMPLIANCE_RULES[rid] for rid in rule_ids if rid in COMPLIANCE_RULES]


def _run_compliance_check(content, agent_name, brokerage, mls_names=None, niche="", custom_rule_ids=None, content_mode="agent"):
    content_lower = content.lower()
    notes         = []
    statuses      = {}

    if content_mode == "b2b":
        profile_name = "b2b_saas"
    else:
        profile_name = _get_compliance_profile(niche)

    rules = _get_rules_for_profile(profile_name)
    if custom_rule_ids:
        for rid in custom_rule_ids:
            if rid in COMPLIANCE_RULES:
                rules.append(COMPLIANCE_RULES[rid])

    for rule in rules:
        triggered = [t for t in rule["terms"] if t in content_lower]
        if triggered:
            statuses[rule["id"]] = rule["severity"]
            notes.append(f"[{rule.get('authority', '')}] {rule['message']} (triggered: '{triggered[0]}')")
        else:
            statuses[rule["id"]] = "pass"

    if brokerage and content_mode == "agent":
        brokerage_words = [w.lower() for w in brokerage.split() if len(w) > 3]
        if not any(w in content_lower for w in brokerage_words):
            statuses["brokerage_disclosure"] = "warn"
            notes.append(f"Brokerage disclosure: '{brokerage}' not detected. Verify brokerage name appears before publishing.")

    if agent_name and content_mode == "agent":
        name_parts = [p.lower() for p in agent_name.split() if len(p) > 2]
        if not any(p in content_lower for p in name_parts):
            statuses["agent_disclosure"] = "warn"
            notes.append(f"Licensee disclosure: '{agent_name}' not detected. State law requires licensee name on all advertising.")

    if content_mode == "b2b":
        company_name = agent_name or "HomeBridge"
        company_parts = [p.lower() for p in company_name.split() if len(p) > 3]
        if not any(p in content_lower for p in company_parts):
            statuses["company_disclosure"] = "warn"
            notes.append(f"Company disclosure: '{company_name}' not detected in content.")

    mls_list = [m.strip() for m in (mls_names or []) if m and m.strip()]
    if mls_list and content_mode == "agent":
        notes.append(f"MLS reminder: Verify advertising standards for {', '.join(mls_list)} before publishing.")

    if content_mode == "b2b":
        notes.append("FTC reminder: B2B marketing content should avoid unsubstantiated performance claims. Testimonials require FTC-compliant disclosure.")
    elif profile_name == "data_center":
        notes.append("Jurisdiction note: Data center transactions may involve additional federal and international regulatory review.")
    elif profile_name == "commercial":
        notes.append("Jurisdiction note: Commercial real estate advertising may be subject to state securities laws.")
    else:
        notes.append("State rules: Automated checks cover federal and NAR standards. Verify your state commission's advertising requirements.")

    def _worst(ids):
        vals = [statuses.get(i, "pass") for i in ids]
        if "fail" in vals: return "fail"
        if "warn" in vals: return "warn"
        return "pass"

    fair_housing_status = _worst(["fair_housing"])
    disclosure_status   = _worst(["brokerage_disclosure", "agent_disclosure", "company_disclosure"])
    nar_status          = _worst(["nar_article12"])
    all_vals            = list(statuses.values())

    if "fail" in all_vals:
        overall = "attention"
    elif "warn" in all_vals:
        overall = "review"
    else:
        overall = "compliant"
        if not notes or all(any(k in n.lower() for k in ["reminder", "jurisdiction", "state rules", "ftc reminder"]) for n in notes):
            notes = [f"Content passed all automated compliance checks for {profile_name} profile. Verify jurisdiction-specific rules before publishing."]

    return ComplianceBadge(
        fairHousing=fair_housing_status,
        brokerageDisclosure=disclosure_status,
        narStandards=nar_status,
        overallStatus=overall,
        notes=notes,
    )


def _parse_claude_output(raw_text, compliance):
    import re
    cleaned = raw_text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
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


NICHE_SITUATIONS = {
  "Residential Buying & Selling": [
    "Buyer demand is outpacing available inventory in this market",
    "Interest rate changes shifting buyer affordability calculations",
    "Multiple offer situations becoming the norm again",
    "Sellers hesitating — waiting for the perfect moment that may not come",
    "Spring market accelerating — serious buyers need to move now",
    "Fall/winter slowdown creating hidden opportunity for prepared buyers",
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
  "Multi-Family (2-4 Units)": [
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
    "Rising interest rates reshaping return projections across asset classes",
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
    "Compliance checklist gaps creating post-close liability",
    "Agent bandwidth — when transaction coordination creates competitive advantage",
    "Remote closings and digital notarization expanding access",
  ],
  "Appraisal & Valuation": [
    "Appraisal gap strategies in competitive offer situations",
    "Challenging a low appraisal — the process most agents don't use",
    "Pre-listing appraisal as a seller credibility tool",
    "Estate valuation — date of death appraisals and IRS requirements",
    "Market condition adjustments appraisers are making right now",
    "Automated valuation models vs. professional appraisal — knowing the difference",
    "Desktop and hybrid appraisal options changing the process",
  ],
  "Ultra-Luxury / UHNW": [
    "UHNW buyers prioritizing discretion over public listing exposure",
    "Family office real estate allocations increasing in uncertain markets",
    "Trophy property scarcity driving off-market transaction volume",
    "International capital flows into domestic ultra-luxury markets",
    "Estate and compound properties requiring specialized marketing",
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
  "Divorce & Separation": [
    "Couple needs to sell the family home as part of a settlement",
    "One spouse wants to buy out the other — is it financially viable?",
    "Sensitive timeline — court-ordered sale deadline approaching",
    "Emotional attachment to the home complicating the decision",
    "Children in the picture — school district decisions matter",
    "Credit impact of divorce affecting buying power post-settlement",
    "Coordinating with divorce attorneys — how agents can add value",
  ],
  "Probate & Inherited Homes": [
    "Family inherited a home and doesn't know what to do with it",
    "Executor needs to sell quickly to settle an estate",
    "Inherited property needs significant repairs before listing",
    "Multiple heirs disagreeing on whether to sell or keep",
    "Out-of-state heirs trying to manage a local property remotely",
    "Tax implications of inherited property creating confusion",
    "As-is sale vs. fix-up — helping heirs make the financial decision",
  ],
  "Empty Nesters & Downsizing": [
    "Kids are out — the emotional and financial downsizing conversation",
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
    "Student debt and homeownership — navigating the qualification math",
    "First condo as investment — house-hacking in an urban market",
    "Building credit and savings simultaneously — the pre-purchase roadmap",
  ],
  "Families with Children": [
    "School district quality as the primary location driver",
    "Room-to-grow strategy — buying ahead of the next life stage",
    "Proximity to family support networks influencing location decisions",
    "Backyard and outdoor space moving up the priority list post-pandemic",
    "Multi-generational floor plan demand increasing as parents age",
    "Community amenities — pools, parks, sports — driving neighborhood choice",
    "Future resale planning — buying in family-friendly locations for liquidity",
  ],
  "Pre-Foreclosure & Hardship": [
    "Homeowner behind on payments — options that most people don't know exist",
    "Short sale as a dignity-preserving alternative to foreclosure",
    "Cash offer timeline giving distressed sellers a way out",
    "Loan modification vs. selling — helping owners understand their choices",
    "Foreclosure timeline — when delay becomes the enemy",
    "Rebuilding credit and confidence after financial hardship",
    "Job loss creating sudden housing urgency — rapid response options",
  ],
  "Estate & Probate Sales": [
    "Family inherited a home and doesn't know what to do with it",
    "Executor timeline pressure — probate courts don't wait",
    "Out-of-state heirs managing a local property remotely",
    "As-is estate sale vs. preparing the property — the financial case",
    "Multiple heirs with conflicting priorities — neutral representation value",
    "Estate attorney coordination — how real estate professionals add value",
    "Hoarding or deferred maintenance — handling sensitive property conditions",
  ],
  "Care-Driven Transitions": [
    "Health event forcing a rapid housing transition for a senior",
    "Family caregivers coordinating a parent's move from a distance",
    "Memory care transition — selling the family home to fund care",
    "Aging-in-place modifications vs. the decision to move",
    "Power of attorney situation — navigating real estate decisions for a loved one",
    "Senior move management — the logistics most families underestimate",
    "Family consensus breakdown — helping all parties reach alignment",
  ],
  "Emergency Relocation": [
    "Job loss requiring a fast sale to preserve financial stability",
    "Sudden employer relocation — selling and buying on compressed timeline",
    "Divorce forcing an immediate housing transition",
    "Cash offer options for sellers who can't afford to wait for retail buyers",
    "Temporary housing bridge while permanent situation is resolved",
    "Cross-country move with no local market knowledge — remote buying strategy",
    "iBuyer vs. traditional sale — the honest speed and net proceeds comparison",
  ],
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
  ],
  "Short-Term Rentals / Airbnb": [
    "STR regulation changes reshaping which markets pencil",
    "Revenue projection tools — separating realistic from optimistic forecasts",
    "Furnishing and setup investment — what guests actually care about",
    "Seasonal pricing strategy that maximizes annual revenue",
    "HOA and condo restrictions on short-term rentals — due diligence matters",
    "Platform fee and tax changes affecting STR net returns",
    "Competitor analysis — understanding your market before buying",
  ],
  "Mid-Term Rentals": [
    "Travel nurse housing demand creating reliable mid-term rental income",
    "Corporate housing demand in markets with large employer presence",
    "Furnished rental premium — the math vs. unfurnished long-term",
    "30-day minimum stay rules — navigating local STR restrictions",
    "Platform strategy for mid-term rental marketing",
    "Tenant profile for mid-term rentals — understanding your customer",
  ],
  "1031 Exchange": [
    "45-day identification deadline — the clock starts at closing",
    "Qualified intermediary selection — the most overlooked step in an exchange",
    "Like-kind property rules — broader than most investors realize",
    "Boot minimization strategy — keeping the exchange fully tax-deferred",
    "Delaware Statutory Trust as 1031 replacement property option",
    "Failed exchange consequences — and how to avoid them",
    "Multi-property identification rules — the three options investors can use",
  ],
  "Opportunity Zones": [
    "Opportunity Zone investment window — understanding the remaining tax benefit timeline",
    "Qualified Opportunity Fund structure — direct investment vs. fund participation",
    "Community impact narrative — OZ investment as mission-aligned capital",
    "Development project due diligence in OZ — additional complexity to manage",
    "OZ compliance requirements — the 10-year hold and its implications",
    "Urban infill OZ opportunities often overlooked by institutional capital",
    "Rural Opportunity Zones — less competition, strong demographic tailwinds",
  ],
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
  ],
  "Hyperscale Campuses": [
    "Hyperscaler land acquisition moving 200+ miles from traditional markets",
    "Power infrastructure investment as prerequisite for hyperscale site selection",
    "Water availability and sustainability requirements for cooling systems",
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
    "Autonomous vehicle and IoT applications creating new edge demand drivers",
    "Edge vs. centralized — helping clients understand the hybrid infrastructure decision",
  ],
  "Powered Shells": [
    "Industrial shell conversion to data center — feasibility analysis framework",
    "Power delivery infrastructure investment required before tenant occupancy",
    "Zoning compliance for data center use in industrial-designated parcels",
    "Spec powered shell development — meeting the market before tenants arrive",
    "Existing industrial building assessment — can it support data center power loads",
    "Powered shell pre-leasing strategy to secure development financing",
  ],
  "Cloud Infrastructure Real Estate": [
    "Cloud region expansion creating concentrated real estate demand in select markets",
    "Long-term ground lease strategy for cloud campus development",
    "Power and sustainability commitments driving cloud provider site selection",
    "Land aggregation strategy in advance of announced cloud expansion",
    "Infrastructure REIT relationships with major cloud providers",
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
  ],
  "Network Facilities": [
    "Internet exchange point expansion creating colocation demand in tier-2 markets",
    "Carrier-neutral exchange strategy for operators seeking redundancy",
    "Network operations center space requirements and site criteria",
    "Redundant network path planning driving multi-site facility strategy",
    "Managed services growth increasing demand for purpose-built network facilities",
    "Edge peering demand growing as content delivery networks expand",
  ],
  "Broker & Office Management": [
    "Agents at my office aren't posting consistently — the visibility gap is real",
    "A compliance issue arose from an agent's social post",
    "We're losing listings to agents with stronger online presence",
    "New agents joining — how do I get them visible fast?",
    "The Compass-Anywhere merger just created the world's largest brokerage",
    "Our office brand is invisible — agents post as individuals only",
    "Broker wants to reduce compliance risk from agent social media",
    "Recruiting agents who expect modern marketing tools",
    "Building a team brand that survives agent turnover",
    "Office needs consistent content without hiring a marketing team",
  ],
  "Agent Productivity & Technology": [
    "AI content is flooding social — authenticity is now the differentiator",
    "Agents are using AI tools with zero compliance checks",
    "Google and LinkedIn are rewarding authentic verified content",
    "The agents winning online aren't posting more — they're posting smarter",
    "Consistency beats frequency — why most agent content strategies fail",
    "Time is the real barrier — agents know they should post but never do",
    "Voice and brand identity disappearing into generic AI content",
  ],
  "Real Estate Compliance": [
    "Fair Housing violations in social media are rising — and preventable",
    "NAR Article 12 violations from unverified claims in agent posts",
    "Compliance documentation — proving what was reviewed before it went live",
    "State commission advertising rules agents consistently overlook",
    "AI-generated content and the new standard for disclosure",
    "PaperTrail documentation as protection in an audit or complaint",
  ],
  "PropTech & Innovation": [
    "AGI is months away — what it means for real estate professionals",
    "The authenticity imperative — why verified human content is becoming premium",
    "Platform algorithm changes rewarding human-reviewed content",
    "EU AI Act and US FTC moving toward mandatory AI disclosure",
    "Instagram and TikTok already labeling AI content — LinkedIn is next",
    "Real estate technology consolidation — what survives and what doesn't",
  ],
  "Mortgage & Lending": [
    "Rate buydown strategies changing the math for buyers right now",
    "DSCR loans opening up investment property access for more borrowers",
    "Bridge loan demand rising as move-up buyers navigate timing",
    "Down payment assistance programs expanding — who qualifies in 2026",
    "Jumbo loan market tightening — what high-value buyers need to know",
    "FHA vs. conventional — the real comparison in today's market",
    "Non-QM lending creating options for self-employed borrowers",
    "Refinance wave planning — positioning clients for the next rate drop",
  ],
}

DEFAULT_SITUATIONS = [
    "Market conditions creating new opportunity for prepared clients",
    "Technology and AI changing how professionals reach their audience",
    "Interest rate environment requiring updated client education",
    "Supply and demand dynamics shifting in this asset class",
    "Regulatory changes creating urgency for informed decision-making",
]


@router.get("/situations")
async def get_situations(niche: Optional[str] = None):
    if niche and niche in NICHE_SITUATIONS:
        situations = NICHE_SITUATIONS[niche]
    else:
        matched = next(
            (v for k, v in NICHE_SITUATIONS.items() if niche and niche.lower() in k.lower()),
            None
        )
        situations = matched if matched else DEFAULT_SITUATIONS
    return {"niche": niche, "situations": situations}


@router.post("/generate-content", response_model=ContentResponse)
async def generate_content(payload: ContentRequest) -> ContentResponse:
    try:
        client = _get_anthropic_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    content_mode = (payload.content_mode or "agent").lower()
    if content_mode == "b2b":
        prompt = _build_b2b_content_prompt(payload)
    else:
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
        text_chunks    = [b.text for b in content_blocks if getattr(b, "type", "") == "text"]
        raw_text       = "\n\n".join(text_chunks).strip()
        if not raw_text:
            raise ValueError("Claude returned empty content.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing Claude response: {str(e)}")

    profile    = payload.agentProfile or AgentProfileModel()
    agent_name = profile.agentName or ""
    brokerage  = profile.brokerage  or ""
    mls_names  = profile.mlsNames   or []
    niche_for_check = ", ".join(payload.identity.primaryCategories) if payload.identity.primaryCategories else ""

    compliance = _run_compliance_check(
        raw_text, agent_name, brokerage, mls_names,
        niche=niche_for_check, content_mode=content_mode,
    )
    try:
        return _parse_claude_output(raw_text, compliance)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error structuring content response: {str(e)}")


def generate_content_core(
    agent_name="", brokerage="", market="", niche="",
    situation="", persona="homeowners", tone="Professional",
    length="Standard", trends=None, brand_voice="",
    short_bio="", audience="", words_avoid="", words_prefer="",
    mls_names=None, content_mode="agent",
):
    profile = AgentProfileModel(
        agentName=agent_name, brokerage=brokerage, market=market,
        brandVoice=brand_voice, shortBio=short_bio,
        audienceDescription=audience, wordsAvoid=words_avoid,
        wordsPrefer=words_prefer, mlsNames=mls_names or [],
    )
    payload = ContentRequest(
        identity     = IdentityModel(primaryCategories=[niche] if niche else []),
        situation    = situation,
        persona      = persona,
        tone         = tone,
        length       = length,
        agentProfile = profile,
        content_mode = content_mode,
    )
    client = _get_anthropic_client()
    mode   = (content_mode or "agent").lower()
    prompt = _build_b2b_content_prompt(payload) if mode == "b2b" else _build_content_prompt(payload)
    response = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
    )
    text_chunks = [b.text for b in (response.content or []) if getattr(b, "type", "") == "text"]
    raw_text    = "\n\n".join(text_chunks).strip()
    if not raw_text:
        raise ValueError("Claude returned empty content")
    compliance = _run_compliance_check(raw_text, agent_name, brokerage, mls_names or [], niche=niche, content_mode=mode)
    content_response = _parse_claude_output(raw_text, compliance)
    return {"content": content_response.dict(), "compliance": compliance.dict()}
