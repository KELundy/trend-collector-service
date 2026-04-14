import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Request
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
    state: Optional[str] = Field(None)
    # CTA / Booking fields — agent configures once, appear in every post
    ctaType:    Optional[str]  = Field(None)   # legacy single — kept for backward compat
    ctaUrl:     Optional[str]  = Field(None)
    ctaLabel:   Optional[str]  = Field(None)
    ctaMethods: Optional[List[Dict[str, str]]] = Field(default_factory=list)  # [{type, url, label}, ...]
    # MLS data — agent pastes from their MLS report for hyper-local stats
    mlsData:  Optional[str] = Field(None)
    # Voice Profile fields — Zone of Greatness / authentic differentiation
    originStory:       Optional[str] = Field(None)
    unfairAdvantage:   Optional[str] = Field(None)
    signaturePerspective: Optional[str] = Field(None)
    notForClient:      Optional[str] = Field(None)
    notificationEmail: Optional[str] = Field(None)


class ComplianceBadge(BaseModel):
    fairHousing: str
    brokerageDisclosure: str
    narStandards: str
    overallStatus: str
    notes: List[str] = Field(default_factory=list)
    # ── NEW FIELDS (Item #3) ──────────────────
    stateCompliance: str = Field(default="pass")
    mlsCompliance: str = Field(default="pass")
    disclosureChecks: List[str] = Field(default_factory=list)


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

    # ── CTA / booking block — multi-method support ──────────────────────────
    methods = profile.ctaMethods or []
    # Filter to methods that have a URL
    active_methods = [m for m in methods if isinstance(m, dict) and m.get("url","").strip()]
    # Fallback to legacy single fields if no ctaMethods
    if not active_methods and (profile.ctaUrl or "").strip():
        active_methods = [{"type": profile.ctaType or "calendar",
                           "url":  profile.ctaUrl  or "",
                           "label": profile.ctaLabel or ""}]

    if active_methods:
        type_phrases = {
            "calendar": "calendar booking link",
            "text":     "direct text number",
            "phone":    "phone number",
            "email":    "email address",
            "website":  "website URL",
            "authority":"authority page URL",
        }
        method_lines = []
        for m in active_methods:
            t   = m.get("type","calendar")
            url = m.get("url","").strip()
            lbl = m.get("label","").strip()
            phrase = type_phrases.get(t, "contact link")
            if lbl:
                method_lines.append(f'  • {lbl}: {url}  [{phrase}]')
            else:
                method_lines.append(f'  • {url}  [{phrase}]')
        combined = "\n".join(method_lines)
        cta_instruction = (
            f"CTA REQUIREMENT: The cta field MUST include ALL of the following contact methods verbatim — "
            f"weave them naturally into a single, human-sounding call to action.\n"
            f"Contact methods:\n{combined}\n"
            f"Do not invent labels. Use the provided labels exactly. "
            f"If multiple methods are listed, present them as natural options: "
            f"'Book a call, send a text, or visit my site — whatever works best for you.'"
        )
    else:
        cta_instruction = (
            "CTA REQUIREMENT: Write a low-pressure genuine invitation to a conversation. "
            "Plant curiosity, not urgency. No 'call me today' commands."
        )

    # ── MLS data block ────────────────────────────────────────────────────────
    mls_data  = profile.mlsData or ""
    mls_block = ""
    if mls_data.strip():
        mls_block = (
            "\nLOCAL MARKET DATA (from agent's MLS report — use specific numbers in content)\n"
            + "─" * 40 + "\n"
            + mls_data.strip() + "\n"
            "INSTRUCTION: Reference at least one specific metric from this data in the post or script. "
            "Real numbers make content shareable. "
            '"Days on market dropped from 18 to 11" beats "homes are selling faster."\n'
        )

    # ── Voice Profile / Zone of Greatness block ───────────────────────────────
    origin      = profile.originStory          or ""
    advantage   = profile.unfairAdvantage      or ""
    perspective = profile.signaturePerspective or ""
    not_for     = profile.notForClient         or ""

    voice_profile_block = ""
    if any([origin, advantage, perspective, not_for]):
        parts = []
        if origin:      parts.append(f"Why {agent_name} does this: {origin}")
        if advantage:   parts.append(f"Their unfair advantage: {advantage}")
        if perspective: parts.append(f"Their signature belief: {perspective}")
        if not_for:     parts.append(f"Who they are NOT for: {not_for}")
        voice_profile_block = (
            f"\nZONE OF GREATNESS — {agent_name.upper()}'S AUTHENTIC VOICE\n"
            + "─" * 40 + "\n"
            + "\n".join(parts) + "\n\n"
            "INSTRUCTION: Let these shape the texture and point of view of the content. "
            "This agent is not trying to sound like every other agent. They have a specific perspective. "
            "The content should feel like it could only come from this person.\n"
        )

    market_first_word = market.split()[0].replace(",", "")

    return (
        f"You are ghostwriting for {agent_display}, a real estate professional in {market}.\n\n"
        "Your job is to write content that sounds exactly like a knowledgeable human being sharing "
        "what they know — not like a marketing campaign, not like an advertisement, and absolutely "
        "not like a sales pitch.\n\n"
        f"WHO {agent_name.upper()} IS\n"
        + "─" * 40 + "\n"
        + bio_text + audience_text
        + f"Market: {market}\n"
        + (desig_context + "\n" if desig_context else "")
        + (lang_instruction + "\n" if lang_instruction else "")
        + f"Specialization: {primary_categories}\n"
        + f"Areas of depth: {subniches_text}\n"
        + voice_profile_block
        + f"\nWHAT THIS CONTENT IS ABOUT\n"
        + "─" * 40 + "\n"
        + f"Situation: {payload.situation}\n"
        + f"Relevant signals: {selected_trends}\n"
        + f"Context: {trend_prefs}\n"
        + mls_block
        + f"\nVOICE & STYLE\n"
        + "─" * 40 + "\n"
        + tone_text + length_text + avoid_text + prefer_text
        + "\nTHE MOST IMPORTANT THING\n"
        + "─" * 40 + "\n"
        "This content must sound like a real person thinking out loud. The reader should feel like "
        "they're getting insight from someone who knows this world deeply — not like they're being sold to.\n\n"
        "AUTHENTICITY REQUIREMENTS — NON-NEGOTIABLE:\n"
        "1. Take a REAL POSITION. 'It depends' is not a position. Pick a side and defend it.\n"
        "2. Include ONE QUOTABLE LINE — a single sentence that stands alone as a screenshot-worthy insight. "
        "This is the sentence that gets shared. Make it specific, surprising, or counter-intuitive.\n"
        f"3. End the POST with a GENUINE LOCAL QUESTION that only a {market} expert would ask, "
        f"and that only people actually interested in {market} real estate would answer. "
        f'Examples: "Are you one of the buyers I\'ve talked to this week who\'s still waiting?" '
        f'/ "Has your block felt different this spring?" '
        "NOT: 'What do you think?' or 'Have any questions?'\n"
        "4. SOCIAL MEDIA IS A CONVERSATION, NOT A BILLBOARD. The post should invite a specific reply, "
        "not broadcast at an audience. Write to one person, not a crowd.\n\n"
        "SHAREABILITY RUBRIC — every post must pass all four:\n"
        "- Would someone share this because it makes THEM look smart? (not because it promotes the agent)\n"
        "- Does it contain a specific, surprising insight that most people don't know?\n"
        "- Could the headline stand alone as something worth forwarding?\n"
        "- Is there zero hedge language? (remove 'it depends,' 'every situation is different,' 'consult a professional')\n\n"
        "BANNED FOREVER:\n"
        "- 'Don't miss out' / 'Act now' / 'Limited time'\n"
        "- 'Call me today' as the opener or the whole point\n"
        "- Exclamation points used to manufacture excitement\n"
        "- Hype phrases: 'game-changer', 'incredible opportunity', 'the market is on fire'\n"
        "- Generic prompts to 'like, share, and follow'\n"
        "- Hedge language: 'it depends,' 'every market is different,' 'results may vary'\n\n"
        "LIGHTER SIDE SPECIAL INSTRUCTION:\n"
        "If the situation starts with 'Lighter Side:', write with warmth and genuine humor. "
        "The tone should feel like a funny, self-aware professional — not a stand-up comedian. "
        "Think: the kind of post a trusted colleague sends that makes you smile and share it. "
        "Keep it short. One sharp observation or a tight list. End with something that invites "
        "a reply or a smile — never a hard sell. The humor should be relatable, never mean.\n\n"
        "WHAT GREAT CONTENT SOUNDS LIKE:\n"
        f"- An observation the agent genuinely made: 'Something I've been noticing in {market} lately...'\n"
        "- A nuanced take only someone in the field would have: 'Most people assume X, but what's actually happening is Y...'\n"
        f"- A real position: 'Here's my honest take on whether you should buy right now in {market}...'\n"
        "- Honest acknowledgment of complexity: 'There's no clean answer here, but the thing worth understanding is...'\n\n"
        "VIDEO SCRIPT — NEWS FORMAT:\n"
        "Structure the script as follows:\n"
        f"1. HOOK (5 sec): One sharp local observation — something happening in {market} RIGHT NOW. "
        f"Sounds like: 'Something shifted in {market} this week that most people haven't noticed yet.'\n"
        f"2. CONTEXT (15 sec): The real situation, explained in plain language. Specific to {market}.\n"
        f"3. IMPLICATION (25 sec): What this means for buyers/sellers/investors in {market} specifically. "
        "Reference real local details — neighborhoods, developments, micro-markets.\n"
        "4. CTA (10 sec): Natural, conversational close. Not a sales pitch.\n"
        "Include on a separate line: [B-ROLL: description of a specific local visual to film]\n"
        f"Include on a separate line: [GREEN SCREEN: description of ideal background — e.g., 'aerial view of {market} downtown']\n"
        "Teleprompter pace: write for 130-150 words per minute. Mark natural pause points with ' / '.\n\n"
        f"THE CTA FIELD:\n{cta_instruction}\n\n"
        f"IDENTITY RULES\n"
        + "─" * 40 + "\n"
        + f"1. {agent_name} must appear naturally in the post as a first-person voice or sign-off.\n"
        + f"2. {brokerage_disclosure}\n"
        + f"3. Always say \"{market}\" specifically — never \"your local area.\"\n"
        + "4. The script must sound like someone actually talking — natural pauses, real sentences.\n\n"
        + "COMPLIANCE RULES\n"
        + "─" * 40 + "\n"
        "- Fair Housing Act: No language implying preference by protected class. No steering. Focus on property facts.\n"
        "- NAR Code of Ethics Article 12: Truthful only. No guaranteed outcomes. No 'best agent' language.\n"
        f"- Brokerage disclosure: {brokerage_compliance} must be identifiable. Agent's licensed name must appear.\n"
        "- No specific financial predictions. No guaranteed investment returns.\n\n"
        "OUTPUT FORMAT — RETURN ONLY VALID JSON, NOTHING ELSE\n"
        + "─" * 40 + "\n"
        "{\n"
        '  "headline": "A clear, specific, human headline with a real point of view. One sentence, no period. Something worth sharing.",\n'
        f'  "thumbnailIdea": "A grounded realistic visual concept specific to this niche and {market}. 1-2 sentences.",\n'
        f'  "hashtags": "#hashtag1 #hashtag2 (8-12 tags, space-separated, include {market_first_word}-specific tags)",\n'
        f'  "post": "A full social post in {agent_name}\'s voice. Takes a real position. Ends with a genuine local question. Ends with: — {agent_name}{brokerage_footer}",\n'
        '  "cta": "The CTA as specified — include booking/contact URL if provided.",\n'
        '  "script": "News-format teleprompter script with [B-ROLL] and [GREEN SCREEN] direction notes."\n'
        "}\n\n"
        "HARD RULES:\n"
        "- Every value must be complete — no placeholders\n"
        f'- post MUST contain {agent_name}{brokerage_footer if brokerage else ""} — legal disclosure requirement\n'
        "- post MUST end with a genuine local question (not generic)\n"
        f"- {market} must appear in the post or script\n"
        "- cta MUST include the booking URL if one was provided\n"
        "- No line breaks inside JSON string values — use spaces between sentences\n"
        "- Return ONLY the JSON object."
    )




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

  # ── NEW RULES — Item #3 ──────────────────────────────────────────────────

  "cfpb_udaap": {
    "id": "cfpb_udaap",
    "authority": "CFPB 12 U.S.C. § 5531 (UDAAP)",
    "severity": "fail",
    "terms": [
      "easy to qualify", "anyone can get approved", "no credit check",
      "instant pre-approval", "guaranteed financing", "guaranteed approval",
      "anyone qualifies", "everyone qualifies", "no income verification",
      "approval guaranteed",
    ],
    "message": "CFPB UDAAP: language implying guaranteed or easy financing approval is an unfair, deceptive, or abusive act. Legal review required.",
  },
  "hud_advertising": {
    "id": "hud_advertising",
    "authority": "HUD 24 C.F.R. Part 100 Subpart C",
    "severity": "warn",
    "terms": [
      "no pets", "no animals", "no dogs", "no cats",
      "perfect for single person", "ideal for single person",
      "adults preferred", "mature community",
    ],
    "message": "HUD Advertising: 'no pets' language may violate assistance animal requirements under FHA. Equal Housing Opportunity statement recommended.",
  },
  "epa_lead_paint": {
    "id": "epa_lead_paint",
    "authority": "EPA 40 C.F.R. Part 745 / TSCA Title X",
    "severity": "fail",
    "terms": [
      "original hardwood", "historic details", "original features",
      "built in the 1960s", "built in the 1950s", "built in the 1940s",
      "built in the 1930s", "1960s home", "1950s home", "1940s home",
      "1930s home", "pre-war home", "original woodwork", "original windows",
      "charming older", "vintage details", "classic older",
    ],
    "message": "EPA Lead Paint (TSCA Title X): pre-1978 property language detected without lead paint disclosure. Federal law requires disclosure for properties built before 1978.",
  },
  "fha_advertising": {
    "id": "fha_advertising",
    "authority": "HUD Handbook 4000.1 / CFPB Regulation Z",
    "severity": "warn",
    "terms": [
      "fha approved", "fha loans available", "3.5% down", "3.5 percent down",
      "fha financing available", "fha eligible", "fha ready",
    ],
    "message": "FHA Advertising: referencing FHA loan terms without lender attribution may trigger Regulation Z disclosure requirements. Include licensed lender name and NMLS number.",
  },
  "ada_disability": {
    "id": "ada_disability",
    "authority": "Fair Housing Act 42 U.S.C. § 3604(f) / ADA",
    "severity": "warn",
    "terms": [
      "wheelchair accessible", "handicap accessible", "ada compliant",
      "accessible home", "disability friendly", "mobility accessible",
      "fully accessible",
    ],
    "message": "ADA / FHA § 3604(f): accessibility claims should be supported by documentation. Unverified accessibility claims may create liability.",
  },
  "doj_steering": {
    "id": "doj_steering",
    "authority": "DOJ 28 C.F.R. Part 42 / Fair Housing Act",
    "severity": "warn",
    "terms": [
      "you'll love the neighbors", "great neighbors", "wonderful neighbors",
      "this area is changing", "neighborhood is improving", "area is up and coming",
      "perfect for your community", "community you'll fit in",
      "you'll fit right in", "people like you",
    ],
    "message": "DOJ Steering: language referencing neighborhood demographics or suggesting buyer-community fit may constitute illegal steering under the Fair Housing Act.",
  },
  "flood_zone": {
    "id": "flood_zone",
    "authority": "FEMA NFIP 44 C.F.R. / FIRM Map Standards",
    "severity": "warn",
    "terms": [
      "no flood risk", "low flood zone", "never flooded",
      "out of flood zone", "flood free", "not in a flood zone",
      "minimal flood risk", "no flood concern",
    ],
    "message": "FEMA / NFIP: flood zone statements require current FEMA FIRM map verification. Unverified flood zone claims create material misrepresentation liability.",
  },
  "nar_article2": {
    "id": "nar_article2",
    "authority": "NAR Code of Ethics Article 2",
    "severity": "warn",
    "terms": [
      "no issues", "nothing to disclose", "perfect condition",
      "no problems", "nothing wrong", "issue free", "problem free",
      "no defects", "defect free", "nothing needs repair",
    ],
    "message": "NAR Article 2: language implying no material facts to disclose may constitute concealment. Avoid blanket 'no issues' statements.",
  },
  "nar_article11": {
    "id": "nar_article11",
    "authority": "NAR Code of Ethics Article 11",
    "severity": "warn",
    "terms": [
      "expert in", "specialist in", "i specialize exclusively",
      "only expert", "leading expert", "foremost expert",
      "certified expert", "the expert on",
    ],
    "message": "NAR Article 11: competency claims should be supported by verified designations or documented experience. Unsubstantiated 'expert' claims may violate Article 11.",
  },
  "nar_article15": {
    "id": "nar_article15",
    "authority": "NAR Code of Ethics Article 15",
    "severity": "warn",
    "terms": [
      "the only agent who", "unlike other agents", "better than other agents",
      "unlike my competitors", "other agents don't", "no other agent",
      "agents won't tell you", "what agents hide",
    ],
    "message": "NAR Article 15: comparative claims disparaging other agents or brokers may violate Article 15. Focus on your own value, not competitor criticism.",
  },
  "local_zoning": {
    "id": "local_zoning",
    "authority": "State Real Estate Commission / State Tort Law",
    "severity": "warn",
    "terms": [
      "can be converted to", "commercial potential", "development opportunity",
      "adu possible", "adu potential", "zoning allows", "zoning permits",
      "can build", "buildable lot", "development ready",
      "convert to commercial", "commercial conversion",
    ],
    "message": "Zoning / State Commission: zoning claims require verified municipal records. Unverified development or conversion claims may constitute material misrepresentation.",
  },

  # ── EXISTING RULES (unchanged) ───────────────────────────────────────────

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
  # ── residential: 5 → 16 rules (Item #3) ─────────────────────────────────
  "residential": [
    "fair_housing",
    "nar_article12",
    "respa_section8",
    "clear_cooperation",
    "state_commission",
    "cfpb_udaap",
    "hud_advertising",
    "epa_lead_paint",
    "fha_advertising",
    "ada_disability",
    "doj_steering",
    "flood_zone",
    "nar_article2",
    "nar_article11",
    "nar_article15",
    "local_zoning",
  ],
  # ── commercial: add cfpb_udaap, ada_disability, local_zoning, nar_article2
  "commercial": [
    "nar_article12",
    "respa_section8",
    "state_commission",
    "sec_investment_disclosure",
    "sec_investment_risk",
    "finra_communications",
    "fincen_aml",
    "cercla_environmental",
    "commercial_investment_disclaimer",
    "cfpb_udaap",
    "ada_disability",
    "local_zoning",
    "nar_article2",
  ],
  "data_center": [
    "nar_article12",
    "state_commission",
    "sec_investment_disclosure",
    "sec_investment_risk",
    "finra_communications",
    "fincen_aml",
    "tier_certification_claims",
    "soc2_claims",
    "ferc_power_claims",
    "cfius_awareness",
    "critical_infrastructure_disclosure",
    "ppa_claims",
    "commercial_investment_disclaimer",
  ],
  # ── investment: add cfpb_udaap, fha_advertising, local_zoning, nar_article2
  "investment": [
    "nar_article12",
    "state_commission",
    "sec_investment_disclosure",
    "sec_investment_risk",
    "fincen_aml",
    "commercial_investment_disclaimer",
    "cfpb_udaap",
    "fha_advertising",
    "local_zoning",
    "nar_article2",
  ],
  # ── mortgage: add cfpb_udaap, fha_advertising, hud_advertising, ada_disability
  "mortgage": [
    "nmls_disclosure",
    "regulation_z",
    "respa_section8",
    "fair_housing",
    "state_commission",
    "cfpb_udaap",
    "fha_advertising",
    "hud_advertising",
    "ada_disability",
  ],
  "b2b_saas": [
    "ftc_endorsement",
    "ftc_claims",
    "can_spam",
    "nar_article12",
  ],
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
  "FSBO (For Sale By Owner)": "residential",
  "Expired Listings": "residential",
  "Circle Prospecting & Geographic Farming": "residential",
  "Sphere of Influence & Database Reactivation": "residential",
  "New Agent Sphere & First Contacts": "residential",
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


def _run_compliance_check(
    content, agent_name, brokerage, mls_names=None,
    niche="", custom_rule_ids=None, content_mode="agent",
    state=""
):
    content_lower = content.lower()
    notes         = []
    statuses      = {}
    # disclosureChecks carries per-rule results for the PDF sub-row (Item #2)
    disclosure_checks = []

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
        rule_authority = rule.get("authority", rule["id"])

        # Personalise state_commission message with the agent's state (Item #3)
        if rule["id"] == "state_commission" and state:
            rule_authority = f"{state} Real Estate Commission"
            msg = f"{state} Real Estate Commission: language may conflict with {state} state advertising standards."
        else:
            msg = rule["message"]

        if triggered:
            statuses[rule["id"]] = rule["severity"]
            flag = "⚠ fail" if rule["severity"] == "fail" else "⚠ warn"
            notes.append(f"[{rule_authority}] {msg} (triggered: '{triggered[0]}')")
            disclosure_checks.append(f"{flag} | {rule_authority} | {msg}")
        else:
            statuses[rule["id"]] = "pass"
            disclosure_checks.append(f"✓ pass | {rule_authority}")

    if brokerage and content_mode == "agent":
        brokerage_words = [w.lower() for w in brokerage.split() if len(w) > 3]
        if not any(w in content_lower for w in brokerage_words):
            statuses["brokerage_disclosure"] = "warn"
            notes.append(f"Brokerage disclosure: '{brokerage}' not detected. Verify brokerage name appears before publishing.")
            disclosure_checks.append(f"⚠ warn | Brokerage Disclosure | '{brokerage}' not detected in content.")
        else:
            statuses["brokerage_disclosure"] = "pass"
            disclosure_checks.append(f"✓ pass | Brokerage Disclosure")

    if agent_name and content_mode == "agent":
        name_parts = [p.lower() for p in agent_name.split() if len(p) > 2]
        if not any(p in content_lower for p in name_parts):
            statuses["agent_disclosure"] = "warn"
            notes.append(f"Licensee disclosure: '{agent_name}' not detected. State law requires licensee name on all advertising.")
            disclosure_checks.append(f"⚠ warn | Licensee Disclosure | '{agent_name}' not detected.")
        else:
            statuses["agent_disclosure"] = "pass"
            disclosure_checks.append(f"✓ pass | Licensee Disclosure")

    if content_mode == "b2b":
        company_name = agent_name or "HomeBridge"
        company_parts = [p.lower() for p in company_name.split() if len(p) > 3]
        if not any(p in content_lower for p in company_parts):
            statuses["company_disclosure"] = "warn"
            notes.append(f"Company disclosure: '{company_name}' not detected in content.")
            disclosure_checks.append(f"⚠ warn | Company Disclosure | '{company_name}' not detected.")
        else:
            statuses["company_disclosure"] = "pass"
            disclosure_checks.append(f"✓ pass | Company Disclosure")

    mls_list = [m.strip() for m in (mls_names or []) if m and m.strip()]
    if mls_list and content_mode == "agent":
        mls_str = ", ".join(mls_list)
        notes.append(f"MLS reminder: Verify advertising standards for {mls_str} before publishing.")
        disclosure_checks.append(f"ℹ info | MLS Standards | Verify {mls_str} advertising rules before publishing.")

    # Jurisdiction / profile reminder note
    if content_mode == "b2b":
        notes.append("FTC reminder: B2B marketing content should avoid unsubstantiated performance claims. Testimonials require FTC-compliant disclosure.")
        disclosure_checks.append("ℹ info | FTC Act | B2B content: substantiate all performance claims.")
    elif profile_name == "data_center":
        notes.append("Jurisdiction note: Data center transactions may involve additional federal and international regulatory review.")
        disclosure_checks.append("ℹ info | Federal / International | Data center transactions may require additional regulatory review.")
    elif profile_name == "commercial":
        notes.append("Jurisdiction note: Commercial real estate advertising may be subject to state securities laws.")
        disclosure_checks.append("ℹ info | State Securities | Commercial advertising may be subject to state securities laws.")
    else:
        state_label = f"{state} Real Estate Commission" if state else "State Real Estate Commission"
        notes.append(f"State rules: Automated checks cover federal and NAR standards. Verify {state_label} advertising requirements.")
        disclosure_checks.append(f"ℹ info | {state_label} | Verify state-specific advertising requirements.")

    def _worst(ids):
        vals = [statuses.get(i, "pass") for i in ids]
        if "fail" in vals: return "fail"
        if "warn" in vals: return "warn"
        return "pass"

    fair_housing_status = _worst(["fair_housing", "doj_steering", "hud_advertising"])
    disclosure_status   = _worst(["brokerage_disclosure", "agent_disclosure", "company_disclosure"])
    nar_status          = _worst(["nar_article12", "nar_article2", "nar_article11", "nar_article15"])
    state_status        = _worst(["state_commission", "local_zoning", "flood_zone"])
    mls_status          = _worst(["clear_cooperation"])
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
        stateCompliance=state_status,
        mlsCompliance=mls_status,
        disclosureChecks=disclosure_checks,
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
  "FSBO (For Sale By Owner)": [
    "Why FSBOs sell for less than listed — and what sellers don't want to hear",
    "The week 3 reality check that changes most FSBO sellers' minds",
    "What a FSBO seller actually saves (and what they actually lose)",
    "Legal exposure FSBOs take on that most sellers don't realize",
    "The paperwork problem — what happens when an offer comes in without an agent",
    "Why buyers' agents avoid showing FSBOs to their clients",
    "The pricing trap most FSBO sellers fall into on day one",
    "What I tell every FSBO seller before they make a decision either way",
  ],
  "Expired Listings": [
    "Why a home expires off the market — the real reasons agents don't say out loud",
    "What to do differently the second time a home goes on market",
    "The pricing conversation that should have happened in week one",
    "Condition issues that killed the deal before the first showing",
    "Why days on market hurt a relisting — and how to reset perception",
    "What buyers think when they see 'back on market' — and how to overcome it",
    "The agent relationship problem that leads to expired listings",
    "How to relaunch a listing and actually get traction this time",
  ],
  "Circle Prospecting & Geographic Farming": [
    "Just listed — what this means for values on your street",
    "Just sold — here's what it says about demand in this neighborhood",
    "What's happening to home values in this specific zip code right now",
    "Why your neighborhood is getting more attention from buyers than you'd expect",
    "The development being approved nearby that will change this area",
    "How many homes have sold in this neighborhood in the last 90 days",
    "What a buyer offered over asking in your area this week",
    "Why investors are targeting this specific zip code right now",
  ],
  "Sphere of Influence & Database Reactivation": [
    "Checking in on your home equity — what your property is worth today",
    "For the people in my network thinking about making a move this year",
    "What I'd tell a close friend who asked me if now is a good time to sell",
    "The question I get most from people I know: should I wait or move now?",
    "A note to past clients — here's what's changed since we last worked together",
    "Why people I've worked with before keep referring their friends and family",
    "The market update I wish more people in my network would see",
    "For anyone in my sphere who bought 5+ years ago — your equity story",
  ],
  "New Agent Sphere & First Contacts": [
    "Starting out in real estate — what I wish I'd known sooner",
    "Building trust before asking for business — the long game in real estate",
    "Why relationships beat transactions in this industry every time",
    "What I learned in my first year that changed how I work with clients",
    "The difference between an agent who lasts and one who doesn't",
    "How I approach every new client relationship from day one",
    "What being a new agent in this market has taught me about buyers",
    "The referral culture in real estate — how it actually works",
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


# ─────────────────────────────────────────────────────────
# LIGHTER SIDE — occasional humor to break up the feed
# ─────────────────────────────────────────────────────────
LIGHTER_SIDE_SITUATIONS = [
    "Lighter Side: Why real estate agents make great comedians — we always have an open house",
    "Lighter Side: The five stages of buying a home (hint: stage 3 is eating cereal on the floor)",
    "Lighter Side: Things buyers say that agents hear differently — a translation guide",
    "Lighter Side: You know it's a seller's market when... (a list only insiders will recognize)",
    "Lighter Side: The honest timeline of every home renovation project ever",
    "Lighter Side: What HGTV taught buyers vs. what actually happens at closing",
    "Lighter Side: Signs you've been in real estate too long (affectionate edition)",
    "Lighter Side: A field guide to open house visitors — the archetypes every agent knows",
    "Lighter Side: Why moving is basically just paying people to judge how much stuff you own",
    "Lighter Side: Real estate terms translated into plain English for the first-time buyer",
    "Lighter Side: The emotional stages of making an offer in today's market",
    "Lighter Side: Things I've seen at inspections that I cannot legally describe but will never forget",
]

@router.get("/situations")
async def get_situations(niche: Optional[str] = None, include_lighter: bool = True):
    if niche and niche in NICHE_SITUATIONS:
        situations = list(NICHE_SITUATIONS[niche])
    else:
        matched = next(
            (v for k, v in NICHE_SITUATIONS.items() if niche and niche.lower() in k.lower()),
            None
        )
        situations = list(matched) if matched else list(DEFAULT_SITUATIONS)

    # Inject one Lighter Side situation roughly every 6 items
    if include_lighter and len(situations) >= 5:
        import random
        lighter = random.choice(LIGHTER_SIDE_SITUATIONS)
        insert_at = min(5, len(situations) - 1)
        situations.insert(insert_at, lighter)

    return {"niche": niche, "situations": situations}


@router.get("/situations/multi")
async def get_situations_multi(niches: Optional[str] = None, include_lighter: bool = True):
    """
    Returns merged situations for multiple niches (comma-separated).
    Used by the frontend when no single niche chip is active but the
    agent has multiple primary niches selected in Setup.
    e.g. GET /content/situations/multi?niches=Residential+Buying+%26+Selling,First-Time+Homebuyers
    """
    import random
    if not niches:
        return {"niches": [], "situations": list(DEFAULT_SITUATIONS)}

    niche_list = [n.strip() for n in niches.split(",") if n.strip()]
    merged = []
    seen   = set()
    for n in niche_list:
        pool = NICHE_SITUATIONS.get(n)
        if not pool:
            # fuzzy match
            pool = next((v for k, v in NICHE_SITUATIONS.items() if n.lower() in k.lower()), None)
        if pool:
            for s in pool:
                if s not in seen:
                    merged.append(s)
                    seen.add(s)

    if not merged:
        merged = list(DEFAULT_SITUATIONS)

    if include_lighter and len(merged) >= 5:
        lighter = random.choice(LIGHTER_SIDE_SITUATIONS)
        insert_at = min(5, len(merged) - 1)
        merged.insert(insert_at, lighter)

    return {"niches": niche_list, "situations": merged}


@router.post("/generate-content", response_model=ContentResponse)
async def generate_content(payload: ContentRequest, request: Request) -> ContentResponse:
    # ── Usage limit gate ──────────────────────────────────────────────────────
    # Enforce monthly generation limits before calling Claude.
    # super_admin and admin are always unlimited.
    try:
        from database import usage_check, usage_increment
        import os as _os
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip() if auth_header else ""
        if token and token != "demo-token":
            import sqlite3 as _sq
            db_path = _os.getenv("DB_PATH", "/data/homebridge.db")
            _conn = _sq.connect(db_path)
            _conn.row_factory = _sq.Row
            _c = _conn.cursor()
            # Decode JWT to get user_id
            try:
                import jwt as _jwt
                SECRET = _os.getenv("JWT_SECRET", "homebridge-secret-change-in-production")
                decoded = _jwt.decode(token, SECRET, algorithms=["HS256"])
                uid = decoded.get("user_id") or decoded.get("sub")
                if uid:
                    _c.execute("SELECT id, role, plan FROM users WHERE id = ?", (int(uid),))
                    urow = _c.fetchone()
                    if urow:
                        check = usage_check(urow["id"], urow["role"] or "agent", urow["plan"] or "trial")
                        if not check["allowed"]:
                            _conn.close()
                            from fastapi import HTTPException as _HTTPEx
                            raise _HTTPEx(
                                status_code=429,
                                detail={
                                    "error":      "generation_limit_reached",
                                    "message":    f"You've used all {check['limit']} posts included in your plan this month.",
                                    "used":       check["used"],
                                    "limit":      check["limit"],
                                    "resets_on":  check["resets_on"],
                                    "upgrade_msg":"Contact us to add more generations or upgrade your plan.",
                                }
                            )
                        if urow["role"] not in ("super_admin", "admin"):
                            usage_increment(urow["id"])
            except Exception:
                pass  # Limit check failure never blocks generation
            _conn.close()
    except Exception:
        pass  # Usage check is best-effort — never blocks a legitimate request
    # ─────────────────────────────────────────────────────────────────────────
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
    state      = profile.state      or ""
    niche_for_check = ", ".join(payload.identity.primaryCategories) if payload.identity.primaryCategories else ""

    compliance = _run_compliance_check(
        raw_text, agent_name, brokerage, mls_names,
        niche=niche_for_check, content_mode=content_mode,
        state=state,
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
    mls_names=None, content_mode="agent", state="",
    cta_type="", cta_url="", cta_label="",
    mls_data="", origin_story="", unfair_advantage="",
    signature_perspective="", not_for_client="",
):
    profile = AgentProfileModel(
        agentName=agent_name, brokerage=brokerage, market=market,
        brandVoice=brand_voice, shortBio=short_bio,
        audienceDescription=audience, wordsAvoid=words_avoid,
        wordsPrefer=words_prefer, mlsNames=mls_names or [],
        state=state,
        ctaType=cta_type or None,
        ctaUrl=cta_url or None,
        ctaLabel=cta_label or None,
        mlsData=mls_data or None,
        originStory=origin_story or None,
        unfairAdvantage=unfair_advantage or None,
        signaturePerspective=signature_perspective or None,
        notForClient=not_for_client or None,
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
    compliance = _run_compliance_check(
        raw_text, agent_name, brokerage, mls_names or [],
        niche=niche, content_mode=mode, state=state,
    )
    content_response = _parse_claude_output(raw_text, compliance)
    return {"content": content_response.dict(), "compliance": compliance.dict()}


# ─────────────────────────────────────────────
# LOCAL INTEL ENDPOINT
# POST /content/local-intel
# ─────────────────────────────────────────────
class LocalIntelRequest(BaseModel):
    location:     str
    niche:        Optional[str] = "Residential Buying & Selling"
    market:       Optional[str] = None
    agentProfile: Optional[AgentProfileModel] = None


@router.post("/local-intel")
async def local_intel(payload: LocalIntelRequest):
    """
    Researches a location, address, or development using Claude's web search tool,
    then generates a hyper-local impact post in the agent's voice.
    Returns the same shape as /generate-content so the frontend handler is identical.
    """
    try:
        client = _get_anthropic_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    profile  = payload.agentProfile or AgentProfileModel()
    agent_name   = profile.agentName or "the agent"
    brokerage    = profile.brokerage or ""
    market       = payload.market or profile.market or "their local market"
    niche        = payload.niche or "Residential Buying & Selling"
    service_areas = profile.serviceAreas or []
    cta_url      = profile.ctaUrl or ""
    cta_label    = profile.ctaLabel or ""
    cta_type     = profile.ctaType or ""
    origin       = profile.originStory or ""
    perspective  = profile.signaturePerspective or ""
    advantage    = profile.unfairAdvantage or ""
    brand_voice  = profile.brandVoice or "conversational and genuine"

    brokerage_footer = f" | {brokerage}" if brokerage else ""

    if cta_url:
        cta_instruction = (
            f'CTA REQUIREMENT: End the cta field with this link verbatim: {cta_url}\n'
            f'Label: "{cta_label or "Get in touch"}"'
        )
    else:
        cta_instruction = "CTA REQUIREMENT: Write a low-pressure genuine invitation to a conversation."

    voice_block = ""
    if any([origin, perspective, advantage]):
        parts = []
        if origin:      parts.append(f"Why {agent_name} does this: {origin}")
        if perspective: parts.append(f"Signature belief: {perspective}")
        if advantage:   parts.append(f"Unfair advantage: {advantage}")
        voice_block = (
            f"\nAGENT VOICE — {agent_name.upper()}\n"
            + "─" * 40 + "\n"
            + "\n".join(parts) + "\n"
            "Write in this agent's specific voice. The post should feel like it could only come from them.\n"
        )

    market_display = f"{market} (serving: {', '.join(service_areas)})" if service_areas else market
    market_str     = market or "the local area"

    research_prompt = f"""You are a local real estate market researcher and ghostwriter for {agent_name}, a real estate professional serving {market_display}.

RESEARCH TASK — THREE-TIER FALLBACK:
Search the web for information about: "{payload.location}"

Follow this exact research hierarchy:

TIER 1 — HYPER-LOCAL (try this first):
Search specifically for: building permits, planning commission approvals, zoning changes, development announcements, or neighborhood news directly about "{payload.location}".
If you find 2 or more specific, recent (last 90 days), factual results → use them and skip Tiers 2 and 3.

TIER 2 — METRO LEVEL (if Tier 1 is thin):
If Tier 1 yields fewer than 2 strong specific results, widen your search to the broader {market_str} metro area.
Look for: major development trends, market data, policy changes, or infrastructure news affecting {market_str} broadly.
If you find 2 or more metro-level results → use them and skip Tier 3.

TIER 3 — NATIONAL NICHE (last resort):
If both Tier 1 and Tier 2 are thin, search for national trends relevant to {niche} that a {market_str} agent could give a local angle on.
Examples: NAR data releases, regulatory changes, demographic shifts, interest rate impacts on this niche nationally.

AFTER RESEARCHING:
Write a social media post in {agent_name}'s voice that:
- Uses the MOST SPECIFIC data you found — prefer Tier 1 over Tier 2 over Tier 3
- Is honest about the scope: if using metro or national data, frame it that way ("Across {market_str}..." or "A national trend worth knowing...")
- NEVER fabricates local specifics that weren't in your search results
- Takes a clear position on what this means for buyers and sellers in {market_str}
- Ends with a genuine local question only someone who knows this market would ask

{voice_block}

VOICE: {brand_voice}
MARKET: {market_display}
NICHE AUDIENCE: {niche}

{cta_instruction}

COMPLIANCE RULES:
- Fair Housing Act: No language implying preference by protected class
- NAR Article 12: Truthful only. No guaranteed outcomes
- Brokerage disclosure: End post with — {agent_name}{brokerage_footer}
- No specific financial predictions or guaranteed investment returns
- post MUST end with a genuine local question

Include a sources line at the end of the post body.
Format: "📍 Sources: [list what you found and at what tier — e.g. 'Denver Planning Dept permit record' or 'NAR Q1 2026 report']"

OUTPUT FORMAT — RETURN ONLY VALID JSON, NOTHING ELSE:
{{
  "headline": "A specific headline reflecting the most local data you found. One sentence, no period.",
  "thumbnailIdea": "A realistic visual concept tied to the research. 1-2 sentences.",
  "hashtags": "#hashtag1 #hashtag2 (8-10 tags — include {market_str.split()[0]}-specific tags)",
  "post": "Full social post in {agent_name}'s voice. Uses real data from research. Takes a position. Includes 📍 Sources line. Ends with genuine local question. Ends with: — {agent_name}{brokerage_footer}",
  "cta": "The CTA as specified — include booking URL if provided.",
  "script": "News-anchor teleprompter script covering the research findings. Include [B-ROLL: local footage suggestion] and [GREEN SCREEN: background suggestion]."
}}

HARD RULES:
- Use real data from your searches — never invent facts
- post MUST contain {agent_name}{brokerage_footer if brokerage else ""}
- If data is metro or national, say so in the post — agents build trust through honesty
- Return ONLY the JSON object"""

    try:
        response = client.messages.create(
            model    = "claude-sonnet-4-6",
            max_tokens = 2000,
            tools    = [{"type": "web_search_20250305", "name": "web_search"}],
            messages = [{"role": "user", "content": research_prompt}],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error calling Claude: {str(e)}")

    # Extract text from response — may contain tool_use and tool_result blocks
    try:
        text_chunks = [
            b.text for b in (response.content or [])
            if getattr(b, "type", "") == "text"
        ]
        raw_text = "\n\n".join(text_chunks).strip()
        if not raw_text:
            raise ValueError("Claude returned empty content after research.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing Claude response: {str(e)}")

    # Run compliance check
    mls_names = profile.mlsNames or []
    state     = profile.state or ""
    compliance = _run_compliance_check(
        raw_text, agent_name, brokerage, mls_names,
        niche=niche, content_mode="agent", state=state,
    )

    try:
        return _parse_claude_output(raw_text, compliance)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error structuring response: {str(e)}")
