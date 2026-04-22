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
    # Per-domain status: "pass" | "warn" | "fail"
    fairHousing: str
    brokerageDisclosure: str
    narStandards: str
    stateCompliance: str = Field(default="pass")
    mlsCompliance: str = Field(default="pass")

    # Overall result
    # "reviewed"            — no flags detected across both passes
    # "review-recommended"  — one or more warn-level flags
    # "attention-required"  — one or more fail-level flags
    overallStatus: str

    # UI display fields
    statusLabel: str = Field(default="AI-Reviewed")
    disclaimer: str  = Field(default="")

    # Pass 1 — rule-based flags
    notes: List[str] = Field(default_factory=list)
    disclosureChecks: List[str] = Field(default_factory=list)

    # Pass 2 — semantic flags from Claude review
    semanticFlags: List[Dict[str, Any]] = Field(default_factory=list)
    semanticAssessment: str = Field(default="")

    # Rule provenance — version stamp and verification dates
    # rules_version: the quarter in which the active rule set was last fully verified
    # rules_verified_dates: per-source last-verified month {"federal": "2026-04", "CO": "2026-04"}
    rules_version: str = Field(default="2026-Q2")
    rules_verified_dates: Dict[str, str] = Field(default_factory=dict)


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



# ─────────────────────────────────────────────────────────────────────────────
# COMPLIANCE ENGINE v2
# Rebuilt against actual law — not phrase guesses.
#
# Sources for every rule in this file:
#   FHA      — Fair Housing Act, 42 U.S.C. § 3604(c)
#   HUD75    — HUD 24 C.F.R. § 100.75 (Discriminatory Advertisements)
#   HUD109   — HUD 24 C.F.R. Part 109 (withdrawn 1996, still operative guidance)
#   ACHT     — Achtenberg Memo, Jan. 9, 1995 (HUD FHEO internal enforcement guidance)
#   HUD2024  — HUD FHEO Digital Advertising Guidance, April 29, 2024
#   NAR10    — NAR Code of Ethics Article 10 / SOP 10-3 (2026 edition)
#   NAR12    — NAR Code of Ethics Article 12 (2026 edition)
#   CO610    — Colorado 4 CCR 725-1, Rule 6.10
#
# PHRASE LIST POLICY:
#   Each term appears here because HUD formal guidance, administrative case law,
#   or a federal court has identified it as presumptively problematic under
#   § 3604(c). Terms that HUD has explicitly cleared — "master bedroom",
#   "master bath", "desirable neighborhood", "quiet street", "walk-in closets"
#   (Achtenberg 1995; HUD Part 109) — are NOT in any rule list below.
#   Context-dependent language ("safe neighborhood", "school district",
#   "up and coming") is evaluated in Pass 2 (semantic), not here.
# ─────────────────────────────────────────────────────────────────────────────

COMPLIANCE_RULES = {

  # ── FAIR HOUSING — PASS 1 catches explicit, unambiguous phrase violations ──
  # Source: FHA § 3604(c); HUD 24 C.F.R. § 100.75(c)(1)–(3); HUD word/phrase guidance
  # Severity: FAIL — federal law violation; not a warning
  "fair_housing": {
    "id": "fair_housing",
    "authority": "Fair Housing Act, 42 U.S.C. § 3604(c) / HUD 24 C.F.R. § 100.75",
    "severity": "fail",
    "terms": [
      # Familial status — explicit exclusion
      # Source: FHA § 3604(c); HUD 24 C.F.R. § 100.75(c)(2); HUD Part 109 guidance
      "no children", "no kids", "adults only", "adults-only", "adults preferred",
      "no families", "no children allowed", "child-free community",
      "children not permitted", "adults over 55 only",

      # Familial status — preference signaling (implies non-preferred group excluded)
      # Source: HUD Part 109; HUD fair housing advertising word/phrase lists
      # "perfect for families" signals a familial status preference under § 3604(c)
      "perfect for families", "ideal for families", "great for families",
      "families preferred", "perfect for a family",

      # Familial status — couple/single preference (implies exclusion of families)
      # Source: HUD advertising guidance; equivalent to familial status signal
      "ideal for a couple", "perfect for couples", "perfect for singles",
      "ideal for single person",

      # Race / national origin — explicit neighborhood demographic descriptor
      # Source: HUD 24 C.F.R. § 100.75(c)(1): words conveying availability by race prohibited
      "hispanic neighborhood", "latino neighborhood", "asian neighborhood",
      "black neighborhood", "white neighborhood", "african american neighborhood",
      "hispanic community", "asian community", "latin neighborhood",
      "minority neighborhood", "predominantly white", "predominantly black",

      # Religion — explicit neighborhood religious preference signaling
      # Source: HUD Part 109 guidance; § 3604(c)
      "christian neighborhood", "jewish area", "jewish neighborhood",
      "muslim community", "catholic neighborhood", "faith-based neighborhood",

      # Sex — explicit preference
      # Source: FHA § 3604(c); HUD 24 C.F.R. § 100.75
      "women only", "men only", "female only", "male only",
      "no women", "no men",

      # Disability — exclusionary language
      # Source: FHA § 3604(f); HUD 24 C.F.R. § 100.75
      "no handicapped", "not for disabled",
    ],
    "message": (
        "Fair Housing Act § 3604(c): language detected that may indicate a preference, "
        "limitation, or discrimination based on a protected class. Federal law prohibits "
        "any notice, statement, or advertisement that indicates preference by race, color, "
        "religion, sex, handicap, familial status, or national origin. "
        "Cite: 42 U.S.C. § 3604(c); 24 C.F.R. § 100.75."
    ),
  },

  # ── STEERING — DOJ / HUD
  # Source: FHA § 3604(a); HUD 24 C.F.R. § 100.75(c)(3); DOJ enforcement pattern
  # Steering = directing buyers toward/away from areas by protected class composition
  # Severity: FAIL — active enforcement category
  "doj_steering": {
    "id": "doj_steering",
    "authority": "Fair Housing Act § 3604(a)–(c) / DOJ 28 C.F.R. Part 42 / HUD 24 C.F.R. § 100.75(c)(3)",
    "severity": "fail",
    "terms": [
      # Neighborhood demographic transition references
      # Source: HUD Part 109; DOJ steering enforcement cases
      "neighborhood is changing", "area is changing", "this area is improving",
      "neighborhood is improving", "area is transitioning", "transitional neighborhood",
      "gentrifying", "in transition", "neighborhood in transition",

      # Buyer-community matching language
      # Source: HUD Part 109 guidance; steering enforcement pattern
      "you'll love the neighbors", "you'll fit right in", "people like you",
      "perfect for your community", "community you'll fit into",
      "neighbors you'll relate to", "your kind of neighborhood",

      # Panic selling / blockbusting language
      # Source: FHA § 3604(e); HUD Part 109
      "act before it changes", "buy before the neighborhood changes",
    ],
    "message": (
        "Fair Housing Act § 3604(c) / Steering: language may steer buyers toward or away "
        "from a neighborhood based on its demographic composition, or imply buyer-community "
        "matching based on a protected characteristic. "
        "Cite: 42 U.S.C. § 3604(a),(c); 24 C.F.R. § 100.75(c)(3)."
    ),
  },

  # ── HUD ADVERTISING — EHO logo / selective media
  # Source: HUD 24 C.F.R. § 100.75(c); HUD Part 109 § 109.30; Achtenberg 1995
  "hud_advertising": {
    "id": "hud_advertising",
    "authority": "HUD 24 C.F.R. § 100.75 / 24 C.F.R. Part 109 (1989 guidance)",
    "severity": "warn",
    "terms": [
      # Assistance animal / disability intersection
      # "no pets" alone does not violate FHA, but these compound formulations do
      # Source: HUD guidance on assistance animals; FHA § 3604(f)
      "no pets allowed", "strictly no pets", "no animals of any kind",
      "no service animals", "no assistance animals",
      # Age-based preference without 55+ qualification
      "mature community preferred", "seniors preferred", "adults 50 and over preferred",
    ],
    "message": (
        "HUD 24 C.F.R. § 100.75: language may conflict with FHA advertising standards. "
        "'No pets' policies require case-by-case review for assistance animals under "
        "FHA § 3604(f). Age-preference language requires qualification as a valid "
        "55+ or 62+ community under 42 U.S.C. § 3607(b). "
        "Equal Housing Opportunity statement recommended on all housing advertising."
    ),
  },

  # ── NAR ARTICLE 12 — Truth in advertising
  # Source: NAR Code of Ethics Article 12 (2026); SOP 12-1, 12-4, 12-5
  # Severity: WARN — ethics violation; not federal law
  "nar_article12": {
    "id": "nar_article12",
    "authority": "NAR Code of Ethics Article 12 (2026) / SOP 12-1, 12-4, 12-5",
    "severity": "warn",
    "terms": [
      # Unverifiable performance claims
      # Source: NAR Article 12; SOP 12-1 ("true picture" requirement)
      "i guarantee", "i promise", "guaranteed results", "promise you",
      "100% success", "never fails", "always sells",
      # Unverifiable superiority claims
      # Source: NAR Article 12; SOP 12-2 (case interpretations)
      "best agent in", "best in the city", "number one agent", "#1 agent",
      "top agent in", "number 1 agent", "highest rated agent",
      "best agent", "the only agent who",
      # Authority violations — advertising without authority
      # Source: NAR SOP 12-4
      "will sell your home for", "will get you", "will net you",
    ],
    "message": (
        "NAR Code of Ethics Article 12: unverifiable or potentially misleading claim detected. "
        "REALTORS must 'present a true picture in their advertising, marketing, and other "
        "representations.' Remove or substantiate the claim. "
        "Cite: NAR CoE Article 12 (Amended 1/08); SOP 12-1."
    ),
  },

  # ── RESPA SECTION 8
  # Source: RESPA 12 U.S.C. § 2607; HUD Regulation X
  "respa_section8": {
    "id": "respa_section8",
    "authority": "RESPA Section 8, 12 U.S.C. § 2607 / HUD Regulation X (24 C.F.R. Part 3500)",
    "severity": "warn",
    "terms": [
      "referral fee", "kickback", "split the commission", "finder's fee",
      "paid for referral", "referral payment", "split my commission",
      "receive a fee for referring", "compensation for referral",
      "refer and earn", "pay you for referrals",
    ],
    "message": (
        "RESPA Section 8 (12 U.S.C. § 2607): language may imply a referral fee or kickback "
        "arrangement. RESPA prohibits giving or accepting fees for referrals in connection "
        "with a federally related mortgage loan. Legal review required. "
        "Cite: 12 U.S.C. § 2607; 24 C.F.R. § 3500.14."
    ),
  },

  # ── MLS CLEAR COOPERATION
  # Source: NAR Clear Cooperation Policy (MLS Policy Statement 8.0)
  "clear_cooperation": {
    "id": "clear_cooperation",
    "authority": "NAR Clear Cooperation Policy (MLS Policy Statement 8.0)",
    "severity": "warn",
    "terms": [
      "pocket listing", "off-market exclusive", "coming soon exclusive",
      "pre-mls", "pre mls", "off mls", "not on the mls",
      "exclusive off-market", "private listing", "silent listing",
      "never hitting the mls", "bypassing the mls",
    ],
    "message": (
        "NAR Clear Cooperation Policy: language may conflict with MLS Policy Statement 8.0, "
        "which requires listing submission to the MLS within one business day of marketing. "
        "Verify with your MLS before using this language publicly."
    ),
  },

  # ── CFPB UDAAP
  # Source: Consumer Financial Protection Act, 12 U.S.C. § 5531
  "cfpb_udaap": {
    "id": "cfpb_udaap",
    "authority": "Consumer Financial Protection Act, 12 U.S.C. § 5531 (UDAAP)",
    "severity": "fail",
    "terms": [
      "easy to qualify", "anyone can get approved", "no credit check needed",
      "instant pre-approval", "guaranteed financing", "guaranteed approval",
      "anyone qualifies", "everyone qualifies", "no income verification",
      "approval guaranteed", "guaranteed loan", "pre-approved for anyone",
    ],
    "message": (
        "CFPB UDAAP (12 U.S.C. § 5531): language implying guaranteed or unrestricted "
        "financing approval is an unfair, deceptive, or abusive act. "
        "No lender can guarantee approval in advertising. Legal review required."
    ),
  },

  # ── EPA LEAD PAINT
  # Source: TSCA Title X; EPA 40 C.F.R. Part 745; HUD 24 C.F.R. Part 35
  "epa_lead_paint": {
    "id": "epa_lead_paint",
    "authority": "TSCA Title X / EPA 40 C.F.R. Part 745 / HUD 24 C.F.R. Part 35",
    "severity": "fail",
    "terms": [
      "built in the 1960s", "built in the 1950s", "built in the 1940s",
      "built in the 1930s", "1960s home", "1950s home", "1940s home",
      "1930s home", "pre-war home", "original woodwork", "original windows",
      "original hardwood", "historic details", "original features",
      "charming older home", "vintage details", "classic older home",
      "built before 1978",
    ],
    "message": (
        "EPA / TSCA Title X (40 C.F.R. § 745): language suggesting a pre-1978 property "
        "without lead paint disclosure. Federal law requires sellers and landlords to "
        "disclose known lead-based paint hazards in housing built before 1978. "
        "Ensure Lead Paint Disclosure form is completed before listing goes live. "
        "Cite: 40 C.F.R. § 745.107."
    ),
  },

  # ── FHA LOAN ADVERTISING / REGULATION Z
  # Source: CFPB Regulation Z, 12 C.F.R. § 1026; FHA Handbook 4000.1
  "fha_advertising": {
    "id": "fha_advertising",
    "authority": "CFPB Regulation Z, 12 C.F.R. § 1026 / FHA Handbook 4000.1",
    "severity": "warn",
    "terms": [
      "fha approved", "fha loans available", "3.5% down", "3.5 percent down",
      "fha financing available", "fha eligible", "fha ready",
      "fha loan option", "3.5% minimum down",
    ],
    "message": (
        "Regulation Z (12 C.F.R. § 1026): referencing FHA loan terms or specific down "
        "payment percentages in advertising may trigger Truth in Lending Act disclosure "
        "requirements. Include the licensed lender's name and NMLS number, and confirm "
        "whether full APR disclosure is required."
    ),
  },

  # ── REGULATION Z — rate/payment triggers
  # Source: CFPB Regulation Z, 12 C.F.R. § 1026.24
  "regulation_z": {
    "id": "regulation_z",
    "authority": "CFPB Regulation Z, 12 C.F.R. § 1026.24",
    "severity": "fail",
    "terms": [
      "rates as low as", "payment of only", "payments starting at",
      "% interest rate", "% apr", "only $ per month", "monthly payment of",
      "payment as low as",
    ],
    "message": (
        "Regulation Z (12 C.F.R. § 1026.24): quoting specific interest rates, APRs, or "
        "monthly payment amounts in advertising triggers mandatory full APR disclosure "
        "requirements. Remove specific rate/payment figures or include full required disclosures. "
        "Cite: 12 C.F.R. § 1026.24(c)."
    ),
  },

  # ── ADA / FHA ACCESSIBILITY CLAIMS
  # Source: FHA § 3604(f); ADA 42 U.S.C. § 12101
  "ada_disability": {
    "id": "ada_disability",
    "authority": "Fair Housing Act § 3604(f) / ADA 42 U.S.C. § 12101",
    "severity": "warn",
    "terms": [
      "wheelchair accessible", "handicap accessible", "ada compliant",
      "fully accessible", "disability friendly", "mobility accessible",
    ],
    "message": (
        "FHA § 3604(f) / ADA: accessibility claims should be verified against current "
        "FHA accessibility standards (24 C.F.R. Part 100, Subpart D) or ADA requirements. "
        "Unverified accessibility claims may create liability if the property does not "
        "meet the stated standard."
    ),
  },

  # ── FLOOD ZONE
  # Source: FEMA NFIP 44 C.F.R.; FIRM map standards; state disclosure laws
  "flood_zone": {
    "id": "flood_zone",
    "authority": "FEMA NFIP / 44 C.F.R. Part 59 / State Material Disclosure Laws",
    "severity": "warn",
    "terms": [
      "no flood risk", "low flood zone", "never flooded",
      "out of flood zone", "flood free", "not in a flood zone",
      "minimal flood risk", "no flood concern", "flood zone x",
      "outside the flood plain",
    ],
    "message": (
        "FEMA / NFIP: flood zone statements require current FEMA FIRM map verification. "
        "Flood zone designations change with map updates. Unverified flood zone claims "
        "may constitute material misrepresentation. Verify current FIRM map status at "
        "msc.fema.gov before publishing flood zone claims."
    ),
  },

  # ── NAR ARTICLE 2 — No concealment of material facts
  # Source: NAR Code of Ethics Article 2 (2026)
  "nar_article2": {
    "id": "nar_article2",
    "authority": "NAR Code of Ethics Article 2 (2026)",
    "severity": "warn",
    "terms": [
      "no issues", "nothing to disclose", "perfect condition",
      "no problems whatsoever", "issue free", "problem free",
      "no defects", "defect free", "nothing needs repair",
      "zero issues",
    ],
    "message": (
        "NAR Code of Ethics Article 2: language implying no material facts exist to "
        "disclose may constitute concealment of pertinent facts. REALTORS must not "
        "misrepresent or conceal pertinent facts relating to the property. "
        "Avoid blanket 'no issues' statements."
    ),
  },

  # ── NAR ARTICLE 11 — Competency
  # Source: NAR Code of Ethics Article 11 (2026)
  "nar_article11": {
    "id": "nar_article11",
    "authority": "NAR Code of Ethics Article 11 (2026)",
    "severity": "warn",
    "terms": [
      "only expert", "leading expert", "foremost expert",
      "certified expert in", "the expert on", "exclusive expert",
    ],
    "message": (
        "NAR Code of Ethics Article 11: competency claims should be supported by verified "
        "designations or documented experience in that property or service type. "
        "Unsubstantiated 'expert' claims may violate Article 11."
    ),
  },

  # ── NAR ARTICLE 15 — No false statements about other professionals
  # Source: NAR Code of Ethics Article 15 (2026)
  "nar_article15": {
    "id": "nar_article15",
    "authority": "NAR Code of Ethics Article 15 (2026)",
    "severity": "warn",
    "terms": [
      "unlike other agents", "better than other agents",
      "unlike my competitors", "other agents don't",
      "agents won't tell you", "what agents hide",
      "agents lie about", "agents never",
    ],
    "message": (
        "NAR Code of Ethics Article 15: comparative claims that disparage other real estate "
        "professionals may violate Article 15. REALTORS must not knowingly make false "
        "or misleading statements about other real estate professionals. "
        "Focus on your own value proposition."
    ),
  },

  # ── ZONING / DEVELOPMENT CLAIMS
  # Source: State Real Estate Commission rules; state tort law (misrepresentation)
  "local_zoning": {
    "id": "local_zoning",
    "authority": "State Real Estate Commission / State Misrepresentation Law",
    "severity": "warn",
    "terms": [
      "can be converted to", "commercial potential", "commercial conversion possible",
      "adu possible", "adu potential", "zoning allows", "zoning permits",
      "can build", "buildable lot", "development ready",
      "convert to commercial", "zoned for commercial",
    ],
    "message": (
        "State Commission / Misrepresentation: zoning and development claims require "
        "verification against current municipal records. Unverified development or "
        "conversion claims may constitute material misrepresentation under state law "
        "and NAR Article 12. Verify current zoning with the municipality before publishing."
    ),
  },

  # ── STATE COMMISSION — generic placeholder for states not yet built
  # Colorado has dedicated logic below via STATE_RULES; this fires for all others
  "state_commission": {
    "id": "state_commission",
    "authority": "State Real Estate Commission",
    "severity": "warn",
    "terms": [
      "as-is no inspection", "no inspection needed", "skip the inspection",
      "guaranteed to appreciate", "will increase in value", "guaranteed roi",
      "investment guaranteed", "never lose money", "risk free investment",
      "zero risk", "perfect investment",
    ],
    "message": (
        "State Real Estate Commission: language may conflict with state advertising "
        "standards requiring truthful and non-misleading representations."
    ),
  },

  # ── INVESTMENT / SECURITIES
  "sec_investment_disclosure": {
    "id": "sec_investment_disclosure",
    "authority": "SEC Rule 10b-5 / Securities Act § 17(b)",
    "severity": "fail",
    "terms": [
      "projected return of", "expected annual return", "irr of",
      "cap rate guarantee", "guaranteed cap rate", "regulation d offering",
      "accredited investors only", "annual return of",
    ],
    "message": (
        "SEC Rule 10b-5: securities-adjacent language detected. Projecting specific "
        "returns or referencing Regulation D in advertising may constitute an unlawful "
        "securities offering. Legal review required before publishing."
    ),
  },

  "sec_investment_risk": {
    "id": "sec_investment_risk",
    "authority": "SEC General Anti-Fraud / Rule 10b-5",
    "severity": "warn",
    "terms": [
      "safe investment", "guaranteed income", "passive income guaranteed",
      "risk-free", "risk free", "certain returns", "will cash flow",
      "guaranteed cash flow", "will appreciate",
    ],
    "message": "SEC / State Securities: language implying guaranteed investment outcomes may violate securities anti-fraud rules.",
  },

  "fincen_aml": {
    "id": "fincen_aml",
    "authority": "FinCEN Geographic Targeting Orders / Bank Secrecy Act, 31 U.S.C. § 5311",
    "severity": "warn",
    "terms": [
      "cash only", "cash buyers preferred", "no financing required",
      "anonymous buyer", "no questions asked", "wire transfer only",
    ],
    "message": "FinCEN / BSA: language may attract AML scrutiny. Cash-only and anonymous-buyer language in housing ads has been the subject of FinCEN Geographic Targeting Orders.",
  },

  "cercla_environmental": {
    "id": "cercla_environmental",
    "authority": "CERCLA, 42 U.S.C. § 9601 / ASTM E1527 Phase I Standards",
    "severity": "fail",
    "terms": [
      "clean site", "no environmental issues", "environmentally clean",
      "no contamination", "no phase i needed", "environmentally clear",
    ],
    "message": (
        "CERCLA (42 U.S.C. § 9601): representing a property as environmentally clean "
        "without a Phase I ESA is a material misrepresentation. Remove environmental "
        "clean claims or reference the Phase I ESA that supports them."
    ),
  },

  "commercial_investment_disclaimer": {
    "id": "commercial_investment_disclaimer",
    "authority": "State Real Estate Commission / NAR Code of Ethics Article 12",
    "severity": "warn",
    "terms": [
      "guaranteed noi", "noi will be", "income guaranteed",
      "lease guaranteed", "tenant guaranteed", "guaranteed occupancy",
      "will produce income",
    ],
    "message": "Commercial / Investment: projecting guaranteed income in advertising may violate state advertising standards and NAR Article 12.",
  },

  # ── MORTGAGE / LENDING
  "nmls_disclosure": {
    "id": "nmls_disclosure",
    "authority": "SAFE Act, 12 U.S.C. § 5101 / CFPB Regulation Z",
    "severity": "warn",
    "terms": [
      "loan officer", "mortgage advisor", "mortgage broker",
      "i can get you a loan", "my lender can",
    ],
    "message": (
        "SAFE Act: content referencing mortgage professional services must include "
        "the NMLS license number of the individual and/or company. "
        "Cite: 12 U.S.C. § 5101 et seq."
    ),
  },

  # ── FTC
  "ftc_endorsement": {
    "id": "ftc_endorsement",
    "authority": "FTC Endorsement Guides, 16 C.F.R. Part 255",
    "severity": "warn",
    "terms": [
      "results not typical", "typical results", "customers report",
      "studies show", "proven to", "clinically proven", "endorsed by",
      "as seen in", "featured in",
    ],
    "message": "FTC Endorsement Guides (16 C.F.R. Part 255): performance claims and endorsements must be substantiated and reflect typical results.",
  },

  "ftc_claims": {
    "id": "ftc_claims",
    "authority": "FTC Act Section 5, 15 U.S.C. § 45",
    "severity": "warn",
    "terms": [
      "100% guarantee", "never fails", "always works",
      "the only platform", "the only tool", "no other platform",
    ],
    "message": "FTC Act Section 5: absolute claims must be substantiated. Remove or qualify.",
  },

  "can_spam": {
    "id": "can_spam",
    "authority": "CAN-SPAM Act, 15 U.S.C. § 7701",
    "severity": "warn",
    "terms": ["unsubscribe", "opt out", "remove me from", "stop emails"],
    "message": "CAN-SPAM Act: email content must include a functioning opt-out mechanism and physical mailing address.",
  },

  # ── DATA CENTER / TECH (unchanged from v1 — not housing advertising rules)
  "tier_certification_claims": {
    "id": "tier_certification_claims",
    "authority": "Uptime Institute Tier Certification Standards",
    "severity": "fail",
    "terms": ["tier iv certified", "tier 4 certified", "tier iii certified", "tier 3 certified",
              "uptime certified", "certified tier", "tier-certified"],
    "message": "Uptime Institute: tier certification claims require active audited certification. Do not claim certification without current audit.",
  },

  "soc2_claims": {
    "id": "soc2_claims",
    "authority": "AICPA SOC 2 Standards / FTC Act Section 5",
    "severity": "warn",
    "terms": ["soc 2 compliant", "soc2 compliant", "soc 2 certified", "fully soc compliant"],
    "message": "SOC 2: use 'SOC 2 Type II audited' not 'SOC 2 compliant' — 'compliant' is not a recognized SOC 2 designation.",
  },

  "ferc_power_claims": {
    "id": "ferc_power_claims",
    "authority": "FERC / Federal Power Act",
    "severity": "warn",
    "terms": ["guaranteed power", "power guaranteed", "100% uptime power", "unlimited power"],
    "message": "FERC: absolute power guarantees require qualification. No utility can guarantee 100% uptime.",
  },

  "cfius_awareness": {
    "id": "cfius_awareness",
    "authority": "CFIUS, 50 U.S.C. § 4565 / FIRRMA",
    "severity": "warn",
    "terms": ["foreign investor welcome", "open to foreign capital",
              "no restrictions on foreign", "foreign ownership available"],
    "message": "CFIUS / FIRRMA: data center and critical infrastructure assets are subject to foreign investment review.",
  },

  "critical_infrastructure_disclosure": {
    "id": "critical_infrastructure_disclosure",
    "authority": "DHS Critical Infrastructure Framework / FISMA",
    "severity": "warn",
    "terms": ["government tenant", "dod tenant", "federal government client",
              "classified facility", "scif", "clearance required", "cleared facility"],
    "message": "Critical Infrastructure: references to government or cleared tenants require additional security review before publication.",
  },

  "ppa_claims": {
    "id": "ppa_claims",
    "authority": "FERC / State PUC Regulations / FTC Green Guides, 16 C.F.R. Part 260",
    "severity": "warn",
    "terms": ["100% renewable", "fully renewable", "carbon neutral facility",
              "net zero facility", "zero carbon data center"],
    "message": "FTC Green Guides (16 C.F.R. Part 260): renewable and sustainability claims must be supported by verified PPAs or RECs.",
  },

  "finra_communications": {
    "id": "finra_communications",
    "authority": "FINRA Rule 2210",
    "severity": "warn",
    "terms": ["financial advisor recommends", "strong buy", "must buy investment"],
    "message": "FINRA Rule 2210: content referencing specific financial recommendations may trigger broker-dealer communications standards.",
  },
}


# ─────────────────────────────────────────────────────────────────────────────
# STATE-SPECIFIC RULE OVERLAYS
# Built from state real estate commission research.
# Structure: each state entry adds notes and/or additional phrase checks
# that run on top of the federal floor when agent.state matches.
#
# Colorado is fully built from 4 CCR 725-1 research (Rule 6.10).
# All other states use a "federal floor" stub with a reminder note.
# States will be populated as research completes.
# ─────────────────────────────────────────────────────────────────────────────

STATE_RULES: Dict[str, Dict] = {

  # ── COLORADO — Source: 4 CCR 725-1, Colorado Real Estate Commission Rules
  "CO": {
    "label": "Colorado Real Estate Commission",
    "authority": "4 CCR 725-1 (Colorado Real Estate Commission Rules Regarding Real Estate Brokers)",
    "notes": [
        # 4 CCR 725-1, Rule 6.10.4
        "Colorado 4 CCR 725-1 Rule 6.10.4: All advertising must be done clearly and conspicuously "
        "in the name of the Broker's Brokerage Firm. A Broker who advertises real property owned "
        "by the Broker and not listed with the Firm is exempt.",
        # 4 CCR 725-1, Rule 6.10.2
        "Colorado 4 CCR 725-1 Rule 6.10.2: No Broker or Brokerage Firm may conduct or promote "
        "Real Estate Brokerage Services except in the name under which they appear in the records "
        "of the Colorado Real Estate Commission.",
        # 4 CCR 725-1, Rule 6.10.3
        "Colorado 4 CCR 725-1 Rule 6.10.3: Brokers will not advertise so as to mislead the public "
        "concerning the identity of the Broker or the Broker's Brokerage Firm.",
        # 4 CCR 725-1, Rule 6.23.B
        "Colorado 4 CCR 725-1 Rule 6.23.B: A Fair Housing violation or aiding and abetting in a "
        "violation of Colorado or federal fair housing laws must be reported to the Commission "
        "in writing within 30 calendar days.",
    ],
    # Colorado-specific phrase checks (run in addition to federal rules)
    "extra_rules": [
      {
        "id": "co_sq_ft_disclosure",
        "authority": "4 CCR 725-1, Rule 6.x (Square Footage Measurement and Disclosure)",
        "severity": "warn",
        # Regex-style check handled separately in _run_compliance_check
        "pattern_hint": "square_footage",
        "message": (
            "Colorado 4 CCR 725-1: When advertising square footage, you must disclose the "
            "source and methodology of measurement. Verify source is disclosed in your full "
            "listing or that the post does not make the square footage figure the primary claim."
        ),
      },
      {
        "id": "co_franchise_legend",
        "authority": "4 CCR 725-1, Rule 6.10.5 (Franchise/Trade Name Legend Requirement)",
        "severity": "warn",
        "terms": [],   # No phrase trigger — this is a process reminder
        "message": (
            "Colorado 4 CCR 725-1 Rule 6.10.5: If your brokerage uses a trade name or trademark "
            "owned by a third party (franchise), advertising must include the legend: "
            "'Each [trade name] brokerage business is independently owned and operated.' "
            "Verify this appears where required."
        ),
      },
    ],
  },

  # ── STUB ENTRIES — federal floor + commission reminder
  # These will be replaced with specific rules as state research completes.

  # ── WYOMING — Source: W.S. § 33-28-119 (Wyoming Real Estate License Act)
  "WY": {
    "label": "Wyoming Real Estate Commission",
    "authority": "W.S. § 33-28-119 (Wyoming Statutes Title 33, Chapter 28)",
    "notes": [
        # W.S. § 33-28-119(a)
        "Wyoming W.S. § 33-28-119(a): Every real estate licensee, when promoting or advertising "
        "real estate activities, shall use the real estate company name under which they are licensed "
        "by the Commission. No slogans may imply real estate is being offered by an unlicensed private party.",
        # W.S. § 33-28-119(g)
        "Wyoming W.S. § 33-28-119(g): A licensed associate broker or salesperson shall not advertise "
        "the sale, purchase, exchange, or lease of real estate without including in the advertisement "
        "the real estate company name under which they are licensed.",
        # W.S. § 33-28-119(h)
        "Wyoming W.S. § 33-28-119(h): A licensee advertising real estate owned by the licensee must "
        "include in the advertisement the fact that an owner of the real estate is a licensee.",
        # W.S. § 33-28-119(j)
        "Wyoming W.S. § 33-28-119(j): If a licensee uses their individual name in advertising, "
        "both the first and last name must be included. Common shortened spellings or license-reflected "
        "nicknames are permitted.",
    ],
    "extra_rules": [],
  },

  # ── MONTANA — Source: ARM 24.210.641(dd)–(ee); MCA § 37-51-321(1)(a), (2)
  "MT": {
    "label": "Montana Board of Realty Regulation",
    "authority": "ARM 24.210.641 / MCA § 37-51-321 (Montana Code Annotated Title 37, Chapter 51)",
    "notes": [
        # ARM 24.210.641(dd)
        "Montana ARM 24.210.641(dd): It is unprofessional conduct to fail to disclose in advertising "
        "the licensee's name and to fail to identify that the advertisement is made by a real estate "
        "licensee or by a brokerage company.",
        # ARM 24.210.641(ee)
        "Montana ARM 24.210.641(ee): All licensees must comply with internet advertising rules "
        "under ARM 24.210.430.",
        # MCA § 37-51-321(1)(a)
        "Montana MCA § 37-51-321(1)(a): Intentionally misleading, untruthful, or inaccurate "
        "advertising is unprofessional conduct. A broker operating under a franchise name must incorporate "
        "the broker's own name or trade name into the franchise name or logotype — failure to do so "
        "is misleading advertising.",
        # MCA § 37-51-321(2)(a)
        "Montana MCA § 37-51-321(2)(a): It is unlawful to openly advertise property belonging to others "
        "unless the broker or salesperson has a signed listing agreement from the owner valid as of the "
        "date of advertisement.",
    ],
    "extra_rules": [],
  },

  # ── IDAHO — Source: Idaho Code § 54-2038; IDAPA 24.37.01 (formerly 33.01.01); IREC Guideline 13
  "ID": {
    "label": "Idaho Real Estate Commission",
    "authority": "Idaho Code § 54-2038 / IDAPA 24.37.01 / IREC Guideline 13",
    "notes": [
        # IREC Guideline 13 / Idaho Code § 54-2038(4)
        "Idaho IREC Guideline 13: All advertising shall clearly and conspicuously contain the broker's "
        "licensed business name in all media advertising including social media, Facebook, newspaper, "
        "and brochures. The licensed brokerage name must appear on all ads, emails, and internet advertising.",
        # IREC Guideline 13 — branch offices
        "Idaho IREC Guideline 13: All advertising by branch offices shall clearly state the name of "
        "the main licensed real estate office that the branch is part of.",
        # IREC Guideline 13 — franchise
        "Idaho IREC Guideline 13: Designated brokers must ensure franchise advertising does not imply "
        "that agents affiliated with another office under the same franchise are associated with the "
        "designated broker's office. Franchise advertising must not mingle licensees across offices.",
        # Idaho Code § 54-2038(4)
        "Idaho Code § 54-2038(4): A broker may not allow any person who is not properly licensed to "
        "represent that broker or be advertised as a sales associate before they are officially licensed "
        "at the brokerage.",
    ],
    "extra_rules": [],
  },

  # ── UTAH — Source: Utah Admin. Code R162-2f-401h (current through Bulletin 2024-24)
  "UT": {
    "label": "Utah Division of Real Estate",
    "authority": "Utah Admin. Code R162-2f-401h (Real Estate Licensing and Practices Rules)",
    "notes": [
        # R162-2f-401h(1)
        "Utah R162-2f-401h(1): A licensee shall not advertise or permit any person affiliated with "
        "the licensee to advertise real estate services or property in any medium without clearly and "
        "conspicuously identifying the name of the brokerage with which the licensee is affiliated.",
        # R162-2f-401h(2)
        "Utah R162-2f-401h(2): When it is not reasonable to identify the brokerage name in an "
        "electronic advertisement (e.g., character-limited platforms), the advertisement must directly "
        "link to a display that clearly and conspicuously identifies the brokerage name.",
        # R162-2f-401h(4)
        "Utah R162-2f-401h(4): The brokerage name in advertising must be the name as shown on "
        "division records — not a team name or assumed name unless registered.",
        # R162-2f-401h(5)
        "Utah R162-2f-401h(5): A team, group, or other marketing entity that includes one or more "
        "licensees is subject to the same advertising requirements as an individual licensee.",
        # R162-2f-401h(6)(a)
        "Utah R162-2f-401h(6)(a): If a licensee advertises a guaranteed sales plan, the advertisement "
        "must clearly and conspicuously include: (i) a statement that costs and conditions may apply; "
        "and (ii) contact information so consumers can obtain full disclosures.",
    ],
    "extra_rules": [],
  },

  # ── NEW MEXICO — Source: NMAC 16.61.32.8 (New Mexico Real Estate Commission)
  "NM": {
    "label": "New Mexico Real Estate Commission",
    "authority": "NMAC 16.61.32.8 (New Mexico Administrative Code Title 16, Chapter 61, Part 32)",
    "notes": [
        # 16.61.32.8(B)
        "New Mexico NMAC 16.61.32.8(B): Every qualifying broker advertising real property for others "
        "(including short-term or vacation rentals) or advertising real estate services must at minimum "
        "use the trade name and current brokerage office telephone number as registered with the Commission.",
        # 16.61.32.8(C)
        "New Mexico NMAC 16.61.32.8(C): Associate brokers must include the trade name and telephone "
        "number of the brokerage with which they are affiliated. Effective January 1, 2017, the "
        "brokerage trade name and telephone number shall be in a type size not less than 33% of the "
        "type size of the associate broker's name or team name.",
        # 16.61.32.8(D)
        "New Mexico NMAC 16.61.32.8(D): A broker advertising real property that the broker owns or "
        "partially owns must indicate within the advertising — including signs — that the broker owns "
        "the real property.",
        # 16.61.32.8(G) — electronic exemption
        "New Mexico NMAC 16.61.32.8(G): All advertising requirements apply to print, audio, video, "
        "computer, online, and electronic media. For electronic displays of limited information (thumbnails, "
        "text messages, links, tweets of 200 characters or less), brokerage name and phone number "
        "disclosure is exempt ONLY if such displays link to a page that includes all required disclosures.",
        # 16.61.17.9(R)
        "New Mexico NMAC 16.61.17.9(R): Associate brokers must submit all advertising not prepared "
        "by the brokerage to the qualifying broker for review and approval prior to public release.",
    ],
    "extra_rules": [],
  },

  # ── TEXAS — Source: TREC Rules 22 TAC §535.155 and §535.154 (effective May 15, 2018)
  "TX": {
    "label": "Texas Real Estate Commission (TREC)",
    "authority": "22 TAC §535.155 and §535.154 (Texas Administrative Code Title 22, Part 23, Chapter 535)",
    "notes": [
        # §535.155(a)
        "Texas TREC Rule §535.155(a): Each advertisement must include in a readily noticeable location: "
        "(1) the name of the license holder or team placing the advertisement; and (2) the broker's "
        "name in at least half the size of the largest contact information for any sales agent, "
        "associated broker, or team name in the advertisement.",
        # TRELA §1101.652(b)(23)
        "Texas TRELA §1101.652(b)(23): Advertising is misleading if it fails to include the broker's "
        "name or implies that a sales agent is responsible for the operation of a brokerage. "
        "A sales agent cannot use a title suggesting they are in charge of a brokerage (e.g., 'president,' "
        "'CEO,' 'owner').",
        # §535.155(b)
        "Texas TREC Rule §535.155(b): 'Advertisement' includes any form of communication designed to "
        "attract the public to use real estate brokerage services — including all publications, brochures, "
        "radio, television, email, text messages, social media, internet, business stationery, business "
        "cards, displays, signs, and billboards.",
        # SB 2212 (2017)
        "Texas (SB 2212, 2017): TREC may NOT require a license number, the terms 'broker' or 'agent,' "
        "or reference to the Commission in advertisements. However, broker's name must still appear. "
        "License holders may voluntarily include these if they choose.",
        # §535.155(d)(4)/(6)
        "Texas TREC Rule §535.155(d): Advertising is misleading if it: implies the property value "
        "without a supporting appraisal; advertises a listed property without listing broker permission; "
        "fails to remove closed or expired listings within 10 days; or causes a member of the public "
        "to believe a person not licensed is engaged in real estate brokerage.",
        # Social media exception
        "Texas TREC §535.155(c): For social media or text advertising, the required information may be "
        "located on the license holder's account user profile page if readily accessible by direct link.",
    ],
    "extra_rules": [],
  },

  # ── ARIZONA — Source: A.A.C. R4-28-502 (updated December 13, 2025)
  "AZ": {
    "label": "Arizona Department of Real Estate",
    "authority": "A.A.C. R4-28-502 (Arizona Administrative Code Title 4, Chapter 28, Article 5 — as amended Dec. 13, 2025)",
    "notes": [
        # R4-28-502(A) — no blind ads
        "Arizona A.A.C. R4-28-502(A): A salesperson or broker acting as an agent shall not advertise "
        "property in a manner that implies no salesperson or broker is taking part in the offer — "
        "'blind ads' are prohibited.",
        # R4-28-502(B) — owner/agent (expanded Dec 2025)
        "Arizona A.A.C. R4-28-502(B) (eff. Dec. 13, 2025): Any licensee advertising their own or "
        "another licensee's property for sale, lease, or exchange in Arizona must disclose they are "
        "licensed and include the words 'owner/agent' in the advertisement.",
        # R4-28-502(C)
        "Arizona A.A.C. R4-28-502(C): All advertising must contain accurate claims and representations "
        "and fully state factual material. A licensee shall not misrepresent facts or create "
        "misleading or ambiguous impressions.",
        # R4-28-502(E) — broker name required
        "Arizona A.A.C. R4-28-502(E): A salesperson or broker shall ensure that all advertising "
        "identifies in a clear and prominent manner the employing broker's legal name or the DBA name "
        "contained on the employing broker's license certificate. This applies to print, TV, email, "
        "social media, and all other advertising.",
        # R4-28-502(F) — third-party listing
        "Arizona A.A.C. R4-28-502(F): A licensee who advertises property that is the subject of "
        "another person's real estate employment agreement shall display the name of the listing broker "
        "in a clear and prominent manner.",
        # R4-28-502(G) — designated broker responsible
        "Arizona A.A.C. R4-28-502(G) (eff. Dec. 13, 2025): The designated broker is responsible for "
        "the advertising of all real estate activity — the term 'responsible' implies liability even "
        "if the designated broker took reasonable steps toward compliance.",
        # R4-28-502(I) — written consent for signs
        "Arizona A.A.C. R4-28-502(I): Before placing or publishing any notice that specific property "
        "is offered for sale, lease, rent, or exchange, the licensee must secure the written consent "
        "of the property owner; the advertisement must be promptly removed upon request.",
        # R4-28-502(K) — franchise legend
        "Arizona A.A.C. R4-28-502(K): Brokers using a trade name owned by another person must place "
        "their own licensed name on signs and include the following legend in advertising: "
        "'Each [TRADE NAME or FRANCHISE] office is independently owned and operated.'",
        # R4-28-502(L) — internet
        "Arizona A.A.C. R4-28-502(L): The use of an electronic medium (internet, website) that targets "
        "Arizona residents with the offering of a property interest or real estate brokerage services "
        "constitutes the dissemination of advertising under A.R.S. § 32-2101(2).",
    ],
    "extra_rules": [],
  },

  # ── NEVADA — Source: NAC 645.610; NRS 645.315
  "NV": {
    "label": "Nevada Real Estate Division",
    "authority": "NAC 645.610 / NRS 645.315 (Nevada Administrative Code / Nevada Revised Statutes Chapter 645)",
    "notes": [
        # NAC 645.610(1)(a)
        "Nevada NAC 645.610(1)(a): All advertising of services for which a license is required must "
        "not be false or misleading.",
        # NAC 645.610(1)(c)
        "Nevada NAC 645.610(1)(c): The name of the brokerage firm under which a real estate broker "
        "does business or with which a broker-salesperson or salesperson is associated must be clearly "
        "identified with prominence in all advertising. The Division considers style, size, color, and "
        "location of the brokerage name when evaluating prominence.",
        # NAC 645.610(1)(e) — license number
        "Nevada NAC 645.610(1)(e): Except as provided, a licensee shall conspicuously include their "
        "license number in any advertisement. (Preceding zeros may be omitted.)",
        # NAC 645.610(2) — franchise
        "Nevada NAC 645.610(2): If advertising under a franchise name, a broker must incorporate in a "
        "conspicuous way in the advertisement the real, fictitious, or corporate name under which the "
        "broker is licensed AND include an acknowledgment that each office is independently owned "
        "and operated.",
        # NRS 645.315
        "Nevada NRS 645.315: A licensee shall not advertise solely under their own name when acting "
        "as a broker-salesperson or salesperson — the brokerage firm's name must be identified.",
        # No FSBO
        "Nevada NAC 645.610(1)(b): A licensee shall not use their name or telephone number in any "
        "advertisement that contains the words 'for sale by owner,' 'for lease by owner,' or similar "
        "words — unless the licensee has an ownership interest and includes 'owner-broker' or "
        "'owner-agent' disclosure.",
    ],
    "extra_rules": [],
  },

  # ── OREGON — Source: OAR 863-015-0125 (updated 2022 and 2025)
  "OR": {
    "label": "Oregon Real Estate Agency",
    "authority": "OAR 863-015-0125 (Oregon Administrative Rules, Chapter 863, Division 15 — updated 2022, 2025)",
    "notes": [
        # OAR 863-015-0125(2)
        "Oregon OAR 863-015-0125(2): All real estate advertising must: (a) be identifiable as that of "
        "a real estate licensee; (b) be truthful and not deceptive or misleading; (c) not state or imply "
        "a broker is in charge of the business when they are not the authorized principal broker; "
        "(d) not state or imply a level of expertise not currently maintained; and (e) be done only with "
        "the property owner's written permission when offering property for sale, exchange, or lease.",
        # OAR 863-015-0125(4)
        "Oregon OAR 863-015-0125(4): The registered business name, as registered with the Agency, "
        "shall be immediately noticeable in all advertising.",
        # Individual broker responsibility (2022 change)
        "Oregon OAR 863-015-0125 (2022 amendment): Individual real estate brokers are now legally "
        "responsible for their own advertising — principal broker pre-approval is no longer required "
        "by rule (though firm office policies may still require it).",
        # OAR 863-015-0125(5)(b) — electronic
        "Oregon OAR 863-015-0125(5)(b): Advertising in electronic media must include on its first page: "
        "the licensee's licensed name; the registered business name; and a statement that the licensee "
        "is licensed in Oregon. Sponsored search links are exempt if the destination page complies. "
        "Social media is exempt if the advertising links to the account profile page that complies.",
        # OAR 863-015-0125(6) — no guaranteed profits
        "Oregon OAR 863-015-0125(6): No advertising may guarantee future profits from any real estate activity.",
    ],
    "extra_rules": [],
  },

  # ── WASHINGTON — Source: WAC 308-124B-210; DOL Real Estate Advertising Guidelines
  "WA": {
    "label": "Washington Department of Licensing — Real Estate",
    "authority": "WAC 308-124B-210 / RCW 18.85 (Washington Administrative Code / Washington Real Estate Licensing Law)",
    "notes": [
        # WAC 308-124B-210
        "Washington WAC 308-124B-210: Advertising in any manner must include the firm's name, or "
        "assumed name as licensed, in a clear and conspicuous manner. Advertising cannot be false, "
        "deceptive, or misleading.",
        # Online advertising requirement
        "Washington DOL Advertising Guidelines: When advertising online, each standalone unit of "
        "content — individual webpage, email, social media post, or banner ad — must display the "
        "firm's licensed name and the broker's or managing broker's licensed name. This requirement "
        "applies until an agency relationship is established with a buyer or seller.",
        # Specialty claim substantiation
        "Washington DOL Advertising Guidelines: Specialty claims such as 'VA Loan Specialist' or "
        "'Condo Specialist' must be supported by relevant training, expertise, or substantial experience. "
        "Stating that a commission rate is 'established by law' is a material misrepresentation.",
        # RCW 18.85 — unbranded websites
        "Washington RCW 18.85: A licensee who uses an unbranded or misleading website subjects "
        "not only their own license to disciplinary action, but also the licenses of their delegated "
        "managing broker, designated broker, and the firm.",
    ],
    "extra_rules": [],
  },

  # ── CALIFORNIA — Source: Cal. B&P Code §10140.6 (AB 1650, eff. Jan. 1, 2018); 10 CCR §2770.1; DRE RE 559
  "CA": {
    "label": "California Department of Real Estate (DRE)",
    "authority": "Cal. Bus. & Prof. Code §10140.6 / 10 CCR §2770.1 / DRE Commissioner's Regulations §2773",
    "notes": [
        # B&P §10140.6 — first point of contact (AB 1650)
        "California B&P Code §10140.6 (AB 1650, eff. Jan. 1, 2018): All 'first point of contact' "
        "solicitation materials must disclose the licensee's name, their 8-digit DRE license number, "
        "and the responsible broker's identity. This applies to business cards, stationery, websites, "
        "flyers, advertisements on TV, print, and electronic media. The license number exception "
        "for print ads was eliminated effective January 1, 2018.",
        # Broker's identity definition
        "California DRE: The responsible broker's identity means the broker's name or name and license "
        "number — NOT merely a team name or fictitious business name filed by the sales agent. "
        "The broker's name must be as prominent and conspicuous as any team name included.",
        # Team name rules
        "California DRE RE 559: When advertising includes a team name, the advertisement must include: "
        "team name; salesperson's name; broker's name with license number for both agent and broker "
        "(optional); and the license numbers must be conspicuous and prominent.",
        # Social media
        "California DRE: For social media compliance, add the broker name and DRE license number to "
        "the bio/intro section of social media profiles. Every real estate-related post must include "
        "these disclosures.",
        # Sign exception
        "California DRE: 'For sale,' 'for rent,' 'for lease,' 'open house,' and directional signs are "
        "exempt from agent/licensee information disclosure ONLY if they display the responsible broker's "
        "name (or name + license number) and contain no information identifying a licensee.",
        # 10 CCR §2770 — internet
        "California 10 CCR §2770: Licensees who advertise on the Internet must indicate their license "
        "status in compliance with B&P §§10235.5 and 10140.6. False or misleading advertising can "
        "result in administrative, civil, and/or criminal penalties.",
    ],
    "extra_rules": [],
  },

  # ── ALASKA — Source: AS 08.88 / 12 AAC 64; Alaska REC Best Practice Advertising
  "AK": {
    "label": "Alaska Real Estate Commission",
    "authority": "AS 08.88 / 12 AAC 64.110, 64.112, 64.120, 64.127, 64.128, 64.130 (Alaska Real Estate Commission)",
    "notes": [
        # 12 AAC 64 / Best Practice
        "Alaska Real Estate Commission Best Practice — Advertising: The brokerage's principal office "
        "name must be identifiable to the public in any advertising for all licensees, whether working "
        "as a single licensee or as part of a team.",
        # Best Practice — brokerage name in all media
        "Alaska 12 AAC 64: All advertising must include the brokerage name as registered with the "
        "Commission regardless of whether the licensee is a member of a real estate team. This "
        "requirement includes internet marketing, all social media platforms, classified ads, signs, "
        "business cards, and the recruitment of licensees.",
        # AS 08.88.311(b) — branch offices
        "Alaska AS 08.88.311(b): A branch office shall be advertised only in the name of the principal "
        "office, though it may also indicate the branch location.",
        # Written consent
        "Alaska 12 AAC 64: Licensees cannot advertise a property for sale, lease, or rent without "
        "first obtaining the owner's written permission. A licensee cannot advertise another licensee's "
        "listings unless expressly permitted to do so by the owner in writing.",
        # AS 08.88.071(a)(3)(D) — false advertising
        "Alaska AS 08.88.071(a)(3)(D): Grounds for license discipline include knowingly authorizing, "
        "directing, or aiding in publishing any material false statement or misrepresentation concerning "
        "the licensee's business or real estate offered for sale, rent, lease, or management.",
    ],
    "extra_rules": [],
  },

  # ── HAWAII — Source: HAR 16-99-11 (Hawaii Administrative Rules, Chapter 99)
  "HI": {
    "label": "Hawaii Real Estate Commission",
    "authority": "HAR § 16-99-11 (Hawaii Administrative Rules, Title 16, Chapter 99 — Real Estate Brokers and Salespersons)",
    "notes": [
        # HAR 16-99-11(a)
        "Hawaii HAR § 16-99-11(a): All real estate advertising and promotional materials shall include "
        "the legal name of the brokerage firm or a trade name previously registered by the brokerage "
        "firm with the business registration division and with the real estate commission.",
        # HAR 16-99-11(b) — no FSBO
        "Hawaii HAR § 16-99-11(b): No licensee shall advertise 'For Sale by Owner,' 'For Rent by Owner,' "
        "'For Lease by Owner,' or 'For Exchange by Owner.'",
        # HAR 16-99-11(c) — licensee status disclosure
        "Hawaii HAR § 16-99-11(c): Current individual real estate licensees — whether active or "
        "inactive — shall disclose their status as a real estate licensee in all advertising and "
        "promotional material.",
        # HAR 16-99-11(d) — leasehold disclosure (Hawaii-specific)
        "Hawaii HAR § 16-99-11(d): A leasehold property advertised for sale in any medium must be "
        "identified by the word 'leasehold.' This is a Hawaii-specific requirement reflecting the "
        "prevalence of leasehold interests in the state.",
        # HAR 16-99-11(e)
        "Hawaii HAR § 16-99-11(e): All advertising and promotional materials that reference the "
        "individual licensee's name must: (1) include the licensee's legal name or Commission-registered "
        "name; (2) identify the licensee with their associating or employing brokerage firm; and "
        "(3) specify license type: Broker (B), Salesperson (S), Realtor (R), or Realtor-Associate (RA).",
        # Fair Housing logo
        "Hawaii HAR § 16-99-11 / Federal FHA: All advertising must include the HUD Equal Housing "
        "Opportunity logotype, statement, or slogan as required under the Fair Housing Act. Hawaii "
        "specifically lists this requirement in its advertising guidelines.",
    ],
    "extra_rules": [],
  },

  # ── FLORIDA — Source: Fla. Admin. Code R. 61J2-10.025 / 61J2-10.026
  "FL": {
    "label": "Florida Real Estate Commission (FREC)",
    "authority": "Fla. Admin. Code R. 61J2-10.025 and 61J2-10.026 (Ch. 475, Florida Statutes)",
    "notes": [
        # 61J2-10.025(1)
        "Florida 61J2-10.025(1): All real estate advertisements must include the licensed name of the "
        "brokerage firm as registered with FREC/DBPR. No advertisement placed or caused to be placed "
        "by a licensee shall be fraudulent, false, deceptive, or misleading.",
        # 61J2-10.025(2)
        "Florida 61J2-10.025(2): When a licensee's personal name appears in an advertisement, at "
        "minimum the licensee's last name must be used as registered with the Commission. The broker "
        "associate's or sales associate's name shall be no larger than the name of the registered brokerage.",
        # 61J2-10.025(3)(a)
        "Florida 61J2-10.025(3)(a): When advertising on the internet (including Google, Facebook, "
        "Instagram, etc.), the brokerage firm name must be placed adjacent to or immediately above or "
        "below the 'point of contact information' — any means by which to contact the licensee including "
        "mailing address, email, telephone, or fax.",
        # 61J2-10.026 — team advertising (eff. July 1, 2019)
        "Florida 61J2-10.026 (Team/Group Advertising): Team or group names may not be in larger print "
        "than the name of the registered brokerage. Team names may include 'team' or 'group' but may NOT "
        "include: 'realty,' 'real estate,' 'company,' 'associates,' 'brokerage,' 'properties,' or other "
        "words that imply the team is an independent brokerage. Penalty for violations: up to $5,000 "
        "fine, license suspension, or revocation.",
    ],
    "extra_rules": [],
  },

  # ── GEORGIA — Source: Ga. Comp. R. & Regs. Rule 520-1-.09
  "GA": {
    "label": "Georgia Real Estate Commission (GREC)",
    "authority": "Ga. Comp. R. & Regs. Rule 520-1-.09 (Georgia Real Estate Commission Advertising Rules)",
    "notes": [
        # 520-1-.09(2.1)
        "Georgia Rule 520-1-.09(2.1): All advertising by associate brokers, salespersons, and community "
        "association managers must be under the direct supervision of their broker and in the name of "
        "their firm. No independent advertising by associate licensees.",
        # 520-1-.09(b)(c)(d)
        "Georgia Rule 520-1-.09(b): The name of the firm advertising real estate for sale, rent, or "
        "exchange shall appear in equal or greater size, prominence, and frequency than the name of any "
        "affiliated licensees or groups of licensees. The firm's telephone number must also appear in "
        "equal or greater size, prominence, and frequency than any affiliated licensee's phone number.",
        # 520-1-.09(3)
        "Georgia Rule 520-1-.09(3): A licensee shall not advertise any real estate for sale, rent, "
        "lease, or exchange unless the licensee has first secured the written permission of the owner, "
        "the owner's authorized agent, or the owner of a leasehold estate.",
        # 520-1-.09(8)
        "Georgia Rule 520-1-.09(8): A licensee shall not advertise to sell, buy, exchange, rent, or "
        "lease real estate in a manner indicating the offer is being made by a private party not licensed "
        "by the Commission. When advertising licensee-owned property (not under brokerage engagement), "
        "the advertisement must include the legend 'seller/buyer holds a real estate license' or "
        "'Georgia Real Estate License # [6-digit number].'",
        # Website requirement
        "Georgia O.C.G.A. § 43-40-25: Licensees advertising on websites for sale, rent, or exchange "
        "shall disclose the name and telephone number of the licensee's firm on every viewable web page.",
    ],
    "extra_rules": [],
  },

  # ── NORTH CAROLINA — Source: 21 NCAC 58A .0105 (eff. July 1, 2015)
  "NC": {
    "label": "North Carolina Real Estate Commission (NCREC)",
    "authority": "21 NCAC 58A .0105 (North Carolina Administrative Code — Real Estate Commission Advertising)",
    "notes": [
        # 21 NCAC 58A .0105(a)(1)
        "North Carolina 21 NCAC 58A .0105(a)(1): A broker shall not advertise any brokerage service "
        "or the sale, purchase, exchange, rent, or lease of real estate for another or others without "
        "the consent of the broker-in-charge and without including in the advertisement the name of "
        "the firm or sole proprietorship with which the broker is affiliated.",
        # 21 NCAC 58A .0105(a)(2)
        "North Carolina 21 NCAC 58A .0105(a)(2): A broker shall not advertise or display a 'for sale' "
        "or 'for rent' sign on any real estate without the written consent of the owner or the owner's "
        "authorized agent.",
        # 21 NCAC 58A .0105(b)
        "North Carolina 21 NCAC 58A .0105(b): Blind ads are prohibited. A broker shall not advertise "
        "real estate for others in a manner indicating the offer is being made by the broker's principal "
        "only. Every advertisement shall conspicuously indicate that it is the advertisement of a broker "
        "or brokerage firm and shall not be confined to publication of only a phone number, email address, "
        "or web address.",
        # NAR SOP 12-5 parallel
        "North Carolina / NAR SOP 12-5 (parallel): REALTORS® must disclose the firm name in all "
        "advertising per both NCREC Rule .0105 and NAR Standard of Practice 12-5, which requires "
        "disclosure of the REALTOR®'s firm 'in a reasonable and readily apparent manner' in all media.",
    ],
    "extra_rules": [],
  },

  # ── SOUTH CAROLINA — Source: S.C. Code § 40-57-135(E)(2) / 2024 Act No. 204 (H.4754, eff. May 21, 2024)
  "SC": {
    "label": "South Carolina Real Estate Commission",
    "authority": "S.C. Code § 40-57-135 (as amended by 2024 Act No. 204, H.4754, eff. May 21, 2024)",
    "notes": [
        # § 40-57-135(E)(1)
        "South Carolina § 40-57-135(E)(1): A licensee may not advertise, market, or offer to conduct "
        "a real estate transaction involving real estate owned by another person without first obtaining "
        "a written listing agreement between the property owner and the real estate brokerage firm.",
        # § 40-57-135(E)(2) — full firm name required
        "South Carolina § 40-57-135(E)(2): When advertising or marketing real estate owned by another "
        "person in any medium — including site signage — a licensee must clearly identify the full name "
        "of the real estate brokerage firm. For internet/electronic advertising, this requirement is met "
        "by including a link to the homepage of the brokerage firm.",
        # § 40-57-135(F)(1) — license status disclosure
        "South Carolina § 40-57-135(F)(1): A licensee must clearly reveal their licensed status in "
        "advertising or marketing in any media. When advertising another brokerage's listings on social "
        "media, the licensee must have written authorization from the listing brokerage firm, acknowledge "
        "the listing brokerage conspicuously, and have authorization from the seller.",
        # Franchise / trade name
        "South Carolina § 40-57-135(E)(3): If a real estate brokerage firm operates under a trade or "
        "franchise name, the identity of the franchisee or holder of the trade name must be clearly revealed.",
        # Team advertising (2024, 36-month implementation delay)
        "South Carolina 2024 Act No. 204 (H.4754): The brokerage name must appear on any communication "
        "at least half as many times as the team name (e.g., if the team name appears twice, the brokerage "
        "name must appear at least once). NOTE: This provision has a 36-month implementation delay — "
        "brokerages have until approximately May 2027 to achieve full compliance.",
        # AI language (2024)
        "South Carolina 2024 Act No. 204: AI language added — licensees are responsible for any work "
        "product they use that was produced by AI means, including ChatGPT. The use of AI in work "
        "product is not by itself prohibited.",
    ],
    "extra_rules": [],
  },

  # ── TENNESSEE — Source: Tenn. Comp. R. & Regs. 1260-02-.12
  "TN": {
    "label": "Tennessee Real Estate Commission (TREC)",
    "authority": "Tenn. Comp. R. & Regs. 1260-02-.12 (Rules of the Tennessee Real Estate Commission — Advertising)",
    "notes": [
        # 1260-02-.12(1)(a)
        "Tennessee 1260-02-.12(1)(a): No licensee shall advertise to sell, purchase, exchange, rent, "
        "or lease property in a manner indicating that the licensee is not engaged in the real estate "
        "business (no blind ads).",
        # 1260-02-.12(1)(b) — firm name SAME SIZE OR LARGER
        "Tennessee 1260-02-.12(1)(b): All advertising shall be under the direct supervision of the "
        "principal broker and shall list the firm name and firm telephone number as listed on file with "
        "the Commission. The firm name must appear in letters the SAME SIZE OR LARGER than those spelling "
        "out the name of a licensee or the name of any team, group, or similar entity. (This is stricter "
        "than most states, which require 'equal or greater' — Tennessee mandates the firm name be at "
        "least equal, never smaller.)",
        # 1260-02-.12(1)(c)
        "Tennessee 1260-02-.12(1)(c): Any advertising that refers to an individual licensee must list "
        "that individual licensee's name as licensed with the Commission.",
        # 1260-02-.12(5)(a) — internet
        "Tennessee 1260-02-.12(5)(a): For internet advertising, the firm name and firm telephone number "
        "listed on file with the Commission must conspicuously appear on the website. For social media, "
        "the firm name and phone number must be no more than one click away from the viewable page.",
        # 1260-02-.12(4) — franchise/cooperative
        "Tennessee 1260-02-.12(4): Licensees using a franchise trade name or advertising as a member of "
        "a cooperative group shall clearly and unmistakably indicate in the advertisement their name, "
        "firm name, and firm telephone number (all as registered with TREC) adjacent to any specific "
        "properties advertised for sale or lease.",
        # Prohibited team terms
        "Tennessee 1260-02-.12(3): Team or group names may not include terms such as 'Real Estate,' "
        "'Real Estate Brokerage,' 'Realty,' 'Company,' 'Corporation,' 'LLC,' 'Corp.,' 'Inc.,' "
        "'Associates,' or other similar terms that would lead the public to believe that those licensees "
        "are offering real estate brokerage services independent of the firm and principal broker.",
    ],
    "extra_rules": [],
  },

  # ── VIRGINIA — Source: 18 VAC 135-20-190 (UPDATED April 1, 2026)
  "VA": {
    "label": "Virginia Real Estate Board (VREB)",
    "authority": "18 VAC 135-20-190 (Virginia Administrative Code — Real Estate Board Licensing Regulations, eff. April 1, 2026)",
    "notes": [
        # April 1, 2026 updated definition
        "Virginia 18 VAC 135-20-190 (eff. April 1, 2026): Advertising is now defined as 'any marketing "
        "or promotion of real estate and real estate-related services, regardless of the media.' The "
        "prior categories distinguishing between online and print advertising have been eliminated. "
        "One universal standard now applies to all advertising formats.",
        # Universal disclosure requirement (April 2026)
        "Virginia 18 VAC 135-20-190 (eff. April 1, 2026): All advertising by a firm or affiliated "
        "licensee must contain a clear, legible, and conspicuous disclosure of BOTH the firm's name "
        "AND office contact information (telephone number, email address, or web address of the firm, "
        "or a digital link thereto). The prior 'one-click-away' rule for electronic advertising has "
        "been REMOVED — the firm name and contact info must appear in every advertisement.",
        # Pre-2026 requirement (still operative until April 1, 2026)
        "Virginia 18 VAC 135-20-190(B) (prior to April 1, 2026): All advertising must be under the "
        "direct supervision of the principal broker or supervising broker, in the name of the firm, "
        "and the firm's licensed name must be clearly and legibly displayed on all advertising.",
        # Written consent / seller verification
        "Virginia 18 VAC 135-20-190 (eff. April 1, 2026): Licensees must obtain the written consent "
        "of the seller, landlord, optionor, or licensor prior to advertising a specific identifiable "
        "property. Licensees must also take reasonable steps to verify the identity of the property "
        "owner or landlord before listing — a new requirement added to combat deed fraud scams.",
        # Team name caution
        "Virginia VREB Practice Guidance: Brokers and firms should be cautious with team names. "
        "Avoid terms that could cause consumer confusion such as 'realty,' 'real estate,' 'associates,' "
        "'partners,' 'company,' 'sales,' 'limited,' and 'properties.' Use of 'team' or 'group' is "
        "less risky. The firm name must always be clearly and legibly displayed in advertising.",
    ],
    "extra_rules": [],
  },

  # ── MARYLAND — Source: COMAR 09.11.01.16; COMAR 09.11.02.01; Md. Code Ann., Bus. Occ. & Prof. § 17-322; § 17-547(c)
  "MD": {
    "label": "Maryland Real Estate Commission (MREC)",
    "authority": "COMAR 09.11.01.16 / Md. Code Ann., Bus. Occ. & Prof. § 17-322 / § 17-547(c)",
    "notes": [
        # COMAR 09.11.01.16(C)(1)
        "Maryland COMAR 09.11.01.16(C)(1): A licensee using a trade name shall clearly and unmistakably "
        "include in all advertising the licensee's name or trade name as registered with the Commission, "
        "to ensure the licensee's identity is meaningfully and conspicuously displayed to members of the "
        "general public.",
        # COMAR 09.11.01.16(C)(2)
        "Maryland COMAR 09.11.01.16(C)(2): For sale signs, business cards, contracts, listing contracts, "
        "and other documents relating to real estate activities must clearly and unmistakably include the "
        "licensee's name or trade name as registered with the Commission.",
        # § 17-322(b)(18)–(20)
        "Maryland § 17-322(b)(18)–(20): Grounds for discipline include misleading or untruthful "
        "advertising. Where advertising is published over the name of a licensed salesperson, the "
        "advertisement must disclose the name of the broker whom the salesperson is licensed to represent.",
        # § 17-547(c) — team name rule
        "Maryland § 17-547(c) / COMAR 09.11.02.01: A team name is 'directly connected' to a brokerage "
        "name only if: (a) the ONLY word between the team name and brokerage name is 'of,' 'from,' 'with,' "
        "or 'at'; AND (b) no other word, symbol, or image is between the team name and brokerage name. "
        "Any other construction is not compliant.",
        # Internet / online chat guidance
        "Maryland MREC Online Advertising Guidance: For internet advertising, disclosure of the broker's "
        "name or company name must be made on the chat session page or on the same viewable web page as "
        "any chat session. Online consumers must be able to know when they are dealing with a licensee "
        "and identify the brokerage where the licensee can be found.",
    ],
    "extra_rules": [],
  },

}


# ─────────────────────────────────────────────────────────────────────────────
# COMPLIANCE PROFILES — which rule IDs run for each content type
# ─────────────────────────────────────────────────────────────────────────────

COMPLIANCE_PROFILES: Dict[str, List[str]] = {
  # Residential — full Fair Housing + NAR + state floor
  "residential": [
    "fair_housing", "doj_steering", "hud_advertising",
    "nar_article12", "nar_article2", "nar_article11", "nar_article15",
    "respa_section8", "clear_cooperation", "state_commission",
    "cfpb_udaap", "epa_lead_paint", "fha_advertising", "ada_disability",
    "flood_zone", "local_zoning",
  ],
  # Commercial — FH still applies; add investment/securities rules
  "commercial": [
    "fair_housing", "doj_steering",
    "nar_article12", "nar_article2", "nar_article11", "nar_article15",
    "respa_section8", "state_commission",
    "sec_investment_disclosure", "sec_investment_risk", "finra_communications",
    "fincen_aml", "cercla_environmental", "commercial_investment_disclaimer",
    "cfpb_udaap", "ada_disability", "local_zoning", "flood_zone",
  ],
  # Investment
  "investment": [
    "fair_housing", "nar_article12", "nar_article2", "state_commission",
    "sec_investment_disclosure", "sec_investment_risk",
    "fincen_aml", "commercial_investment_disclaimer",
    "cfpb_udaap", "fha_advertising", "local_zoning", "flood_zone",
  ],
  # Mortgage / lending content
  "mortgage": [
    "fair_housing", "doj_steering", "nar_article12", "state_commission",
    "cfpb_udaap", "fha_advertising", "regulation_z",
    "hud_advertising", "ada_disability", "nmls_disclosure", "respa_section8",
  ],
  # Data center — not housing; different regulatory universe
  "data_center": [
    "nar_article12", "state_commission",
    "sec_investment_disclosure", "sec_investment_risk", "finra_communications",
    "fincen_aml", "tier_certification_claims", "soc2_claims",
    "ferc_power_claims", "cfius_awareness", "critical_infrastructure_disclosure",
    "ppa_claims", "commercial_investment_disclaimer",
  ],
  # B2B SaaS — HomeBridge talking about itself
  "b2b_saas": [
    "ftc_endorsement", "ftc_claims", "can_spam", "nar_article12",
  ],
}


NICHE_COMPLIANCE_PROFILE = {
  "Residential Buying & Selling": "residential",
  "First-Time Homebuyers": "residential",
  "Luxury Real Estate": "residential",
  "Seniors & 55+ Communities": "residential",
  "Active Adult/55+": "residential",
  "Active Adult / 55+": "residential",
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


def _get_compliance_profile(niche: str) -> str:
    return NICHE_COMPLIANCE_PROFILE.get(niche, "residential")


def _get_rules_for_profile(profile_name: str) -> List[Dict]:
    rule_ids = COMPLIANCE_PROFILES.get(profile_name, COMPLIANCE_PROFILES["residential"])
    return [COMPLIANCE_RULES[rid] for rid in rule_ids if rid in COMPLIANCE_RULES]


# ─────────────────────────────────────────────────────────────────────────────
# PASS 1 — Rule-Based Phrase Matching
# Runs synchronously; no API call; catches explicit phrase violations only.
# Context-dependent language is deferred to Pass 2 (semantic).
# ─────────────────────────────────────────────────────────────────────────────

def _run_compliance_check(
    content: str,
    agent_name: str,
    brokerage: str,
    mls_names: List[str] = None,
    niche: str = "",
    custom_rule_ids: List[str] = None,
    content_mode: str = "agent",
    state: str = "",
) -> tuple:
    """
    Pass 1: phrase-match against law-grounded rule set.
    Returns (ComplianceBadge, profile_name) — badge contains Pass 1 results only.
    Pass 2 (semantic) results are merged by _build_final_badge().
    """
    import re
    content_lower = content.lower()
    notes: List[str] = []
    statuses: Dict[str, str] = {}
    disclosure_checks: List[str] = []

    # ── Select rule profile ───────────────────────────────────────────────────
    if content_mode == "b2b":
        profile_name = "b2b_saas"
    else:
        profile_name = _get_compliance_profile(niche)

    rules = _get_rules_for_profile(profile_name)
    if custom_rule_ids:
        for rid in custom_rule_ids:
            if rid in COMPLIANCE_RULES:
                rules.append(COMPLIANCE_RULES[rid])

    # ── Deduplicate rules ─────────────────────────────────────────────────────
    seen_ids: set = set()
    deduped_rules = []
    for r in rules:
        if r["id"] not in seen_ids:
            deduped_rules.append(r)
            seen_ids.add(r["id"])

    # ── Apply each rule ───────────────────────────────────────────────────────
    for rule in deduped_rules:
        triggered = [t for t in rule.get("terms", []) if t in content_lower]

        # Personalise state_commission label with agent state
        rule_authority = rule.get("authority", rule["id"])
        if rule["id"] == "state_commission" and state:
            state_label = STATE_RULES.get(state.upper(), {}).get("label", f"{state} Real Estate Commission")
            rule_authority = state_label
            msg = (
                f"{state_label}: language may conflict with {state} state advertising standards. "
                f"Verify current {state_label} requirements before publishing."
            )
        else:
            msg = rule["message"]

        if triggered:
            statuses[rule["id"]] = rule["severity"]
            flag_prefix = "⚠ FAIL" if rule["severity"] == "fail" else "⚠ WARN"
            notes.append(
                f"[{rule_authority}] {msg} "
                f"(triggered by: '{triggered[0]}')"
            )
            disclosure_checks.append(f"{flag_prefix} | {rule_authority} | {msg}")
        else:
            statuses[rule["id"]] = "pass"
            disclosure_checks.append(f"✓ pass | {rule_authority}")

    # ── Brokerage name disclosure ─────────────────────────────────────────────
    if brokerage and content_mode == "agent":
        brokerage_words = [w.lower() for w in brokerage.split() if len(w) > 3]
        if not any(w in content_lower for w in brokerage_words):
            statuses["brokerage_disclosure"] = "warn"
            notes.append(
                f"Brokerage disclosure: '{brokerage}' not detected in content. "
                f"State advertising rules generally require the licensed brokerage name "
                f"to appear clearly in all advertising."
            )
            disclosure_checks.append(
                f"⚠ WARN | Brokerage Disclosure | '{brokerage}' not detected. "
                f"Licensed brokerage name is required in advertising by most state commissions."
            )
        else:
            statuses["brokerage_disclosure"] = "pass"
            disclosure_checks.append(f"✓ pass | Brokerage Disclosure")

    # ── Agent licensed name disclosure ───────────────────────────────────────
    if agent_name and content_mode == "agent":
        name_parts = [p.lower() for p in agent_name.split() if len(p) > 2]
        if not any(p in content_lower for p in name_parts):
            statuses["agent_disclosure"] = "warn"
            notes.append(
                f"Licensee disclosure: '{agent_name}' not detected. "
                f"State law requires the licensee's name on all advertising."
            )
            disclosure_checks.append(
                f"⚠ WARN | Licensee Disclosure | '{agent_name}' not detected in content."
            )
        else:
            statuses["agent_disclosure"] = "pass"
            disclosure_checks.append(f"✓ pass | Licensee Disclosure")

    # ── B2B company disclosure ────────────────────────────────────────────────
    if content_mode == "b2b":
        company_name = agent_name or "HomeBridge"
        company_parts = [p.lower() for p in company_name.split() if len(p) > 3]
        if not any(p in content_lower for p in company_parts):
            statuses["company_disclosure"] = "warn"
            notes.append(f"Company disclosure: '{company_name}' not detected in content.")
            disclosure_checks.append(f"⚠ WARN | Company Disclosure | '{company_name}' not detected.")
        else:
            statuses["company_disclosure"] = "pass"
            disclosure_checks.append(f"✓ pass | Company Disclosure")

    # ── MLS reminder ──────────────────────────────────────────────────────────
    mls_list = [m.strip() for m in (mls_names or []) if m and m.strip()]
    if mls_list and content_mode == "agent":
        mls_str = ", ".join(mls_list)
        notes.append(f"MLS reminder: Verify advertising rules for {mls_str} before publishing.")
        disclosure_checks.append(
            f"ℹ info | MLS Standards | Verify {mls_str} advertising rules before publishing."
        )

    # ── State-specific overlay (CO fully built; others return reminder) ───────
    state_key = state.upper() if state else ""
    if state_key and state_key in STATE_RULES and content_mode == "agent":
        state_entry = STATE_RULES[state_key]
        for note in state_entry.get("notes", []):
            disclosure_checks.append(f"ℹ state | {state_entry['label']} | {note}")

        for extra in state_entry.get("extra_rules", []):
            # Square footage pattern check (CO-specific)
            if extra.get("pattern_hint") == "square_footage":
                sq_ft_pattern = re.compile(
                    r"\b\d[\d,]*\s*(?:sq\.?\s*ft\.?|square\s+feet|sqft)\b", re.IGNORECASE
                )
                if sq_ft_pattern.search(content):
                    statuses["co_sq_ft_disclosure"] = "warn"
                    notes.append(f"[{extra['authority']}] {extra['message']}")
                    disclosure_checks.append(
                        f"⚠ WARN | {extra['authority']} | {extra['message']}"
                    )
                else:
                    statuses["co_sq_ft_disclosure"] = "pass"
                    disclosure_checks.append(f"✓ pass | {extra['authority']}")
            # Franchise legend reminder (always fire for CO agents with brokerage)
            elif extra["id"] == "co_franchise_legend" and brokerage:
                notes.append(f"[{extra['authority']}] {extra['message']}")
                disclosure_checks.append(f"ℹ state | {extra['authority']} | {extra['message']}")

    # ── Profile-level contextual notes ───────────────────────────────────────
    if content_mode == "b2b":
        notes.append(
            "FTC reminder: B2B marketing content must substantiate all performance claims. "
            "Testimonials require FTC-compliant disclosure (16 C.F.R. Part 255)."
        )
        disclosure_checks.append("ℹ info | FTC Act | Substantiate all performance claims.")
    elif profile_name == "data_center":
        notes.append(
            "Jurisdiction note: Data center transactions may involve CFIUS review, "
            "federal infrastructure regulations, and state securities laws."
        )
        disclosure_checks.append("ℹ info | Federal / International | Data center transactions may require additional regulatory review.")
    elif profile_name == "commercial":
        notes.append("Jurisdiction note: Commercial advertising may be subject to state securities laws. Consult counsel on investment-related language.")
        disclosure_checks.append("ℹ info | State Securities | Verify commercial advertising against state securities laws.")
    elif content_mode == "agent":
        state_label = STATE_RULES.get(state_key, {}).get("label", f"{state} Real Estate Commission") if state_key else "State Real Estate Commission"
        disclosure_checks.append(
            f"ℹ info | {state_label} | Automated checks cover federal and NAR standards. "
            f"Verify {state_label} requirements."
        )

    # ── Roll up statuses ──────────────────────────────────────────────────────
    def _worst(ids: List[str]) -> str:
        vals = [statuses.get(i, "pass") for i in ids]
        if "fail" in vals:
            return "fail"
        if "warn" in vals:
            return "warn"
        return "pass"

    fair_housing_status = _worst(["fair_housing", "doj_steering", "hud_advertising"])
    disclosure_status   = _worst(["brokerage_disclosure", "agent_disclosure", "company_disclosure"])
    nar_status          = _worst(["nar_article12", "nar_article2", "nar_article11", "nar_article15"])
    state_status        = _worst(["state_commission", "local_zoning", "flood_zone",
                                   "co_sq_ft_disclosure"])
    mls_status          = _worst(["clear_cooperation"])
    all_vals            = list(statuses.values())

    # Pass 1 overall — will be superseded by _build_final_badge after Pass 2
    if "fail" in all_vals:
        p1_overall = "attention-required"
    elif "warn" in all_vals:
        p1_overall = "review-recommended"
    else:
        p1_overall = "reviewed"

    badge = ComplianceBadge(
        fairHousing=fair_housing_status,
        brokerageDisclosure=disclosure_status,
        narStandards=nar_status,
        overallStatus=p1_overall,
        statusLabel="AI-Reviewed",     # will be updated by _build_final_badge
        disclaimer="",                  # will be set by _build_final_badge
        notes=notes,
        stateCompliance=state_status,
        mlsCompliance=mls_status,
        disclosureChecks=disclosure_checks,
        semanticFlags=[],
        semanticAssessment="",
    )
    return badge, profile_name


# ─────────────────────────────────────────────────────────────────────────────
# PASS 2 — Semantic Compliance Review
# Calls Claude with the actual legal standard as the benchmark.
# Catches implied violations that phrase-matching cannot detect:
#   — steering by implication
#   — protected class preference through context
#   — "ordinary reader" standard violations (HUD FHEO Guidance, April 29, 2024)
#
# NOT called for b2b_saas or data_center content.
# ─────────────────────────────────────────────────────────────────────────────

_SEMANTIC_REVIEW_PROMPT = """You are a Fair Housing compliance reviewer for real estate social media content. Your role is to protect agents from liability by flagging anything an ordinary reader or a HUD investigator could reasonably interpret as discriminatory — even if discrimination was not intended.

LEGAL STANDARDS BEING ENFORCED:

[1] Fair Housing Act § 3604(c) — 42 U.S.C. § 3604(c):
"It shall be unlawful to make, print, or publish any notice, statement, or advertisement, with respect to the sale or rental of a dwelling that indicates any preference, limitation, or discrimination based on race, color, religion, sex, handicap, familial status, or national origin."

[2] HUD Ordinary Reader Standard — 24 C.F.R. § 100.75; HUD FHEO Digital Advertising Guidance (April 29, 2024):
A violation occurs if the advertisement indicates discrimination to an "ordinary reader" or "ordinary listener" — regardless of whether discrimination was intended. Intent is irrelevant. HUD prohibits using words, phrases, or descriptions which convey that dwellings are available or not available to a particular group because of protected characteristics — including through implication, imagery, or context.

[3] HUD Steering — 24 C.F.R. § 100.75(c)(3):
Steering homebuyers toward or away from areas based on demographic composition is prohibited — even when indirect, even when using proxy language that evokes a demographic without naming it. Neighborhood character descriptions that conjure a specific demographic profile are proxy steering.

[4] NAR Code of Ethics Article 10, SOP 10-3 (2026 edition):
Covers all FHA protected classes PLUS sexual orientation and gender identity. Any language that signals preference or limitation based on any of these characteristics is prohibited.

[5] NAR Code of Ethics Article 12 (2026 edition):
All claims about property, market conditions, agent performance, or results must be truthful and verifiable. Superlatives and guarantees that cannot be substantiated are violations.

PROTECTED CLASSES — check ALL of these explicitly:
— Race and color
— National origin (including language that implies ethnic composition of a neighborhood)
— Religion (including language that implies religious character of a neighborhood)
— Sex / gender
— Sexual orientation and gender identity (NAR Article 10)
— Handicap / disability (including language that implies physical ability assumptions about a neighborhood or its residents)
— Familial status (families with children under 18) — this includes language that implies a neighborhood is for families, or conversely evokes a child-free or adult lifestyle without a valid 55+ exemption
— Age (outside of legally qualified 55+ communities)

PROXY LANGUAGE — flag these even without explicit protected class mention:
— Neighborhood character descriptions that evoke a specific demographic (e.g. "where kids ride bikes," "young professionals," "quiet mature neighborhood," "active community")
— "The neighbors" described in ways that imply demographic homogeneity or compatibility
— Lifestyle descriptors that signal who does or does not belong in a neighborhood
— Any language suggesting a buyer will "fit in" or "relate to" neighbors
— School or religious institution proximity used to imply neighborhood demographic composition

EXPLICITLY CLEARED BY HUD — do NOT flag these:
— "master bedroom" / "master bath" (Achtenberg Memo, January 9, 1995)
— "desirable neighborhood" / "great neighborhood" / "beautiful area" (generic; HUD declined to prohibit)
— Property features described objectively: "walk-in closets," "great view," "quiet street," "open floor plan"
— Neutral proximity statements: "near schools," "close to shopping," "minutes from downtown"
— Pure market data: days on market, price trends, inventory levels, appreciation rates
— General investment analysis with no neighborhood demographic implication

CONTENT TO REVIEW:
{content}

AGENT CONTEXT:
State: {state}
Content niche: {niche}

REVIEW TASK:
Read this content as an ordinary person encountering it for the first time — and also as a HUD investigator looking for liability. For every protected class listed above, ask: could an ordinary reader interpret this content as signaling a preference for or against people in that class?

Evaluate:
1. Direct preference language for any protected class
2. Proxy or implied steering — neighborhood descriptions that evoke a demographic profile
3. "Fit in" / neighbor-compatibility language implying demographic matching
4. Familial status signals — language evoking families with children OR adult/child-free lifestyle (unless content niche is a legally qualified 55+ community)
5. Disability/handicap assumptions embedded in neighborhood lifestyle descriptions
6. Unverifiable claims about property, market conditions, or agent performance (Article 12)

CALIBRATION: When in doubt, flag it as "warn." A warned agent can review and decide. A missed violation can cost an agent their license. The standard here is: would a reasonable HUD investigator consider this worth a second look? If yes — warn.

Return ONLY valid JSON — no preamble, no explanation outside the JSON:
{{
  "flags": [
    {{
      "rule": "e.g. FHA § 3604(c) — Familial Status",
      "severity": "fail or warn",
      "triggered_text": "the exact phrase or sentence from the content",
      "reason": "why an ordinary reader or HUD investigator could interpret this as indicating a discriminatory preference",
      "citation": "e.g. 42 U.S.C. § 3604(c); 24 C.F.R. § 100.75"
    }}
  ],
  "overall": "pass, warn, or fail",
  "ordinary_reader_assessment": "One sentence: how an ordinary reader would interpret this content from a Fair Housing perspective."
}}

severity: "fail" = clear or near-certain violation; "warn" = language a HUD investigator would flag for review.
overall: "pass" if no flags; "warn" if any warn flags; "fail" if any fail flag.

If no concerns exist after checking all protected classes and proxy language, return exactly:
{{"flags": [], "overall": "pass", "ordinary_reader_assessment": "Content focuses on property features and market information without indicating any preference, limitation, or discrimination based on protected characteristics."}}"""

# Profiles that require semantic review (Fair Housing in scope)
_SEMANTIC_REVIEW_PROFILES = {"residential", "commercial", "investment", "mortgage"}


def _run_semantic_compliance_check(
    content: str,
    profile_name: str,
    state: str = "",
    niche: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Pass 2: Claude semantic review against the actual legal standard.
    Returns a dict {"flags": [...], "overall": "...", "ordinary_reader_assessment": "..."}
    or None if semantic review is not applicable for this content type.

    Cost: one additional Claude API call per generation for applicable profiles.
    This is intentional — phrase matching cannot catch the 'ordinary reader' standard.
    """
    if profile_name not in _SEMANTIC_REVIEW_PROFILES:
        return None

    try:
        client = _get_anthropic_client()
    except RuntimeError:
        return None  # Never let compliance pass failures block content delivery

    _, verified_dates = _get_rules_version_and_dates(state)
    federal_verified = verified_dates.get("federal", "unknown")
    verification_context = (
        f"Rules verified against primary sources as of: {federal_verified}. "
        f"If you are reviewing content published after this date, note that regulations "
        f"may have been updated and flag any areas where you believe recent rule changes "
        f"could affect your assessment."
    )

    prompt = _SEMANTIC_REVIEW_PROMPT.format(
        content=content[:4000],   # Clip to avoid token waste on very long content
        state=state or "Not specified",
        niche=niche or "Residential real estate",
    )
    # Inject verification context after the AGENT CONTEXT section
    prompt = prompt + f"\n\nVERIFICATION CONTEXT:\n{verification_context}"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(
            b.text for b in (response.content or [])
            if getattr(b, "type", "") == "text"
        ).strip()

        import re as _re
        raw = _re.sub(r'^```(?:json)?\s*', '', raw)
        raw = _re.sub(r'\s*```$', '', raw)

        result = json.loads(raw.strip())
        # Validate expected shape
        if "flags" in result and "overall" in result:
            return result
        return None
    except Exception:
        return None  # Semantic pass failure is silent — Pass 1 still stands


# ─────────────────────────────────────────────────────────────────────────────
# BADGE BUILDER — merges Pass 1 + Pass 2 into final ComplianceBadge
# Sets the status label and disclaimer text.
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# RULES VERSION METADATA
# Single source of truth for the active rule set.
# Updated by the compliance partner via POST /admin/compliance/verify-state.
# Loaded from compliance_rules_meta.json when available; these are the hardcoded
# fallback defaults that match the initial 2026-Q2 research round.
# ─────────────────────────────────────────────────────────────────────────────

_RULES_VERSION = "2026-Q2"

# Federal sources — verified April 2026
_FEDERAL_VERIFIED_DATES: Dict[str, str] = {
    "federal":      "2026-04",   # Fair Housing Act, HUD regs, FHEO guidance
    "nar":          "2026-04",   # NAR Code of Ethics 2026 edition
}

# Mountain/Western states — all verified April 2026 (initial research round)
_STATE_VERIFIED_DATES: Dict[str, str] = {
    "CO": "2026-04",  # 4 CCR 725-1, Rule 6.10 — Colorado Real Estate Commission
    "WY": "2026-04",  # W.S. § 33-28-119
    "MT": "2026-04",  # ARM 24.210.641 / MCA § 37-51-321
    "ID": "2026-04",  # Idaho Code § 54-2038 / IREC Guideline 13
    "UT": "2026-04",  # Utah Admin. Code R162-2f-401h
    "NM": "2026-04",  # NMAC 16.61.32.8
    "TX": "2026-04",  # 22 TAC §535.155 / §535.154 (TREC)
    "AZ": "2026-04",  # A.A.C. R4-28-502 (updated Dec. 13, 2025)
    "NV": "2026-04",  # NAC 645.610 / NRS 645.315
    "OR": "2026-04",  # OAR 863-015-0125
    "WA": "2026-04",  # WAC 308-124B-210
    "CA": "2026-04",  # Cal. B&P Code §10140.6 / 10 CCR §2770.1
    "AK": "2026-04",  # AS 08.88 / 12 AAC 64
    "HI": "2026-04",  # HAR § 16-99-11
}


def _load_rules_meta() -> Dict[str, Any]:
    """
    Load compliance_rules_meta.json from the same directory as this file.
    Returns an empty dict if the file does not exist or cannot be parsed.
    This is called once per compliance check and is intentionally lightweight.
    """
    from pathlib import Path
    meta_path = Path(__file__).parent / "compliance_rules_meta.json"
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_rules_version_and_dates(state: str = "") -> tuple:
    """
    Returns (rules_version: str, verified_dates: dict).
    Tries compliance_rules_meta.json first; falls back to hardcoded defaults.
    verified_dates always includes "federal", "nar", and the agent's state (if known).
    """
    meta = _load_rules_meta()

    if meta:
        version = meta.get("version", _RULES_VERSION)
        fed_dates = {
            "federal": meta.get("federal", {}).get("fair_housing_act", {}).get("verified_date", _FEDERAL_VERIFIED_DATES["federal"]),
            "nar":     meta.get("federal", {}).get("nar_code_of_ethics", {}).get("verified_date", _FEDERAL_VERIFIED_DATES["nar"]),
        }
        state_dates = {}
        for st, entry in meta.get("states", {}).items():
            state_dates[st] = entry.get("verified_date", _STATE_VERIFIED_DATES.get(st, "unknown"))
    else:
        version    = _RULES_VERSION
        fed_dates  = dict(_FEDERAL_VERIFIED_DATES)
        state_dates = dict(_STATE_VERIFIED_DATES)

    verified_dates = dict(fed_dates)
    state_key = state.upper() if state else ""
    if state_key:
        verified_dates[state_key] = state_dates.get(state_key, "unverified")

    return version, verified_dates


_DISCLAIMER_BASE = (
    "HomeBridge checks content against federal Fair Housing law (42 U.S.C. § 3604), "
    "NAR Code of Ethics standards, and state real estate commission advertising rules. "
    "This is an automated review — not legal advice. "
    "You are a licensed professional and carry final responsibility for all content you publish."
)

_STATUS_LABELS = {
    "reviewed":            "AI-Reviewed",
    "review-recommended":  "Review Recommended",
    "attention-required":  "Attention Required",
}

_STATUS_ADDENDUM = {
    "reviewed": (
        " No issues were detected. Review the checklist below and publish when ready."
    ),
    "review-recommended": (
        " One or more items were flagged. Review the notes below. "
        "Consult your broker or a real estate attorney if you have questions."
    ),
    "attention-required": (
        " One or more items require attention before publishing. "
        "We recommend reviewing these flags with your broker or a real estate attorney."
    ),
}


def _build_final_badge(
    p1_badge: ComplianceBadge,
    p1_profile: str,
    semantic_result: Optional[Dict[str, Any]],
    state: str = "",
    agent_name: str = "",
    brokerage: str = "",
) -> ComplianceBadge:
    """
    Merges Pass 1 and Pass 2 results.
    Determines final overallStatus, statusLabel, disclaimer, and version stamp.
    """
    semantic_flags: List[Dict[str, Any]] = []
    semantic_assessment: str = ""
    semantic_overall: str = "pass"

    if semantic_result:
        semantic_flags    = semantic_result.get("flags", [])
        semantic_assessment = semantic_result.get("ordinary_reader_assessment", "")
        semantic_overall  = semantic_result.get("overall", "pass")

    # Upgrade fair housing status if semantic found fair housing issues
    fair_housing_final = p1_badge.fairHousing
    if semantic_overall == "fail" and fair_housing_final != "fail":
        fair_housing_final = "fail"
    elif semantic_overall == "warn" and fair_housing_final == "pass":
        fair_housing_final = "warn"

    # Final overall — worst of Pass 1 and Pass 2
    p1_overall = p1_badge.overallStatus   # "reviewed" | "review-recommended" | "attention-required"
    if "fail" in (p1_overall, semantic_overall) or p1_overall == "attention-required":
        final_overall = "attention-required"
    elif "warn" in (p1_overall, semantic_overall) or p1_overall == "review-recommended":
        final_overall = "review-recommended"
    else:
        final_overall = "reviewed"

    # Build disclaimer with specific verification dates
    rules_version, verified_dates = _get_rules_version_and_dates(state)
    federal_date = verified_dates.get("federal", "unknown")
    state_key = state.upper() if state else ""
    state_date = verified_dates.get(state_key, "unverified") if state_key else None

    date_line = f"Federal rules verified: {federal_date}."
    if state_date and state_date not in ("unverified", "unknown"):
        state_label_short = STATE_RULES.get(state_key, {}).get("label", f"{state_key} Real Estate Commission") if state_key else ""
        date_line += f" {state_label_short} rules verified: {state_date}."
    elif state_key:
        date_line += f" {state_key} state rules: verification date unavailable — consult your broker."

    disclaimer = _DISCLAIMER_BASE + _STATUS_ADDENDUM[final_overall] + f" {date_line}"

    # Add semantic flags to disclosure_checks for frontend rendering
    updated_disclosure = list(p1_badge.disclosureChecks)
    for sf in semantic_flags:
        sev = sf.get("severity", "warn")
        prefix = "⚠ FAIL (semantic)" if sev == "fail" else "⚠ WARN (semantic)"
        rule   = sf.get("rule", "Fair Housing")
        reason = sf.get("reason", "")
        text   = sf.get("triggered_text", "")
        updated_disclosure.append(f"{prefix} | {rule} | {reason} (text: '{text[:80]}')")

    # Updated notes
    updated_notes = list(p1_badge.notes)
    for sf in semantic_flags:
        sev    = sf.get("severity", "warn")
        rule   = sf.get("rule", "Fair Housing")
        reason = sf.get("reason", "")
        cite   = sf.get("citation", "")
        text   = sf.get("triggered_text", "")
        updated_notes.append(
            f"[{rule}] {reason} — Triggered by: '{text[:100]}'. Cite: {cite}."
        )

    return ComplianceBadge(
        fairHousing=fair_housing_final,
        brokerageDisclosure=p1_badge.brokerageDisclosure,
        narStandards=p1_badge.narStandards,
        overallStatus=final_overall,
        statusLabel=_STATUS_LABELS[final_overall],
        disclaimer=disclaimer,
        notes=updated_notes,
        stateCompliance=p1_badge.stateCompliance,
        mlsCompliance=p1_badge.mlsCompliance,
        disclosureChecks=updated_disclosure,
        semanticFlags=semantic_flags,
        semanticAssessment=semantic_assessment,
        rules_version=rules_version,
        rules_verified_dates=verified_dates,
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

    # ── Pass 1: rule-based ────────────────────────────────────────────────────
    p1_badge, profile_name = _run_compliance_check(
        raw_text, agent_name, brokerage, mls_names,
        niche=niche_for_check, content_mode=content_mode,
        state=state,
    )
    # ── Pass 2: semantic ──────────────────────────────────────────────────────
    semantic = _run_semantic_compliance_check(
        raw_text, profile_name=profile_name, state=state, niche=niche_for_check
    )
    # ── Merge ──────────────────────────────────────────────────────────────────
    compliance = _build_final_badge(
        p1_badge, profile_name, semantic, state=state,
        agent_name=agent_name, brokerage=brokerage,
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
        identity       = IdentityModel(primaryCategories=[niche] if niche else []),
        situation      = situation,
        persona        = persona,
        tone           = tone,
        length         = length,
        selectedTrends = [str(t).strip() for t in (trends or []) if t and str(t).strip()],
        agentProfile   = profile,
        content_mode   = content_mode,
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

    # Pass 1
    p1_badge, profile_name = _run_compliance_check(
        raw_text, agent_name, brokerage, mls_names or [],
        niche=niche, content_mode=mode, state=state,
    )
    # Pass 2
    semantic = _run_semantic_compliance_check(
        raw_text, profile_name=profile_name, state=state, niche=niche
    )
    # Merge
    compliance = _build_final_badge(
        p1_badge, profile_name, semantic, state=state,
        agent_name=agent_name, brokerage=brokerage,
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

NICHE FRAMING LENS — NON-NEGOTIABLE:
This agent's primary niche is: {niche}
After you finish researching, you MUST frame the story through this specific lens.
Generic market commentary is not acceptable. Ask: what does this development, trend, or market shift mean specifically for {niche} buyers or sellers in {market_str}?
For example:
- If the niche is Active Adult / 55+: How does this affect where 55+ buyers want to live, their downsizing options, or the equity position of long-term homeowners in this area?
- If the niche is First-Time Homebuyers: Does this open or close doors for buyers trying to get into the market right now?
- If the niche is Relocation: What does an incoming buyer from out of state need to know about this?
- If the niche is Investment: How does this change the numbers for someone looking at this market as an investor?
Apply the same principle for any other niche — always filter the research through what it means for THIS agent's specific client type.
The post must read like it was written by a {niche} specialist, not a generalist. A reader in that niche should immediately recognize this agent as someone who understands their world.

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
    # When web_search is used, Claude emits one or more intro text blocks before
    # the final JSON block.  Joining ALL text blocks contaminates the JSON parse
    # with preamble text.  Use only the LAST text block — that is always the
    # structured JSON response regardless of how many searches Claude ran.
    try:
        text_blocks = [
            b.text for b in (response.content or [])
            if getattr(b, "type", "") == "text"
        ]
        raw_text = text_blocks[-1].strip() if text_blocks else ""
        if not raw_text:
            raise ValueError("Claude returned empty content after research.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing Claude response: {str(e)}")

    # Run compliance check
    mls_names = profile.mlsNames or []
    state     = profile.state or ""

    # Pass 1
    p1_badge, profile_name = _run_compliance_check(
        raw_text, agent_name, brokerage, mls_names,
        niche=niche, content_mode="agent", state=state,
    )
    # Pass 2
    semantic = _run_semantic_compliance_check(
        raw_text, profile_name=profile_name, state=state, niche=niche
    )
    # Merge
    compliance = _build_final_badge(
        p1_badge, profile_name, semantic, state=state,
        agent_name=agent_name, brokerage=brokerage,
    )

    try:
        return _parse_claude_output(raw_text, compliance)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error structuring response: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN COMPLIANCE PANEL
# Routes: POST /admin/compliance/verify-state
#         GET  /admin/compliance/status
#
# Authentication: JWT, admin or super_admin role only.
# These endpoints are the compliance partner's interface for running quarterly
# reviews and recording verification results against primary sources.
#
# The JSON file (compliance_rules_meta.json) is the persistent store.
# No new packages required — uses json, datetime, pathlib (stdlib).
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter as _APIRouter

admin_router = _APIRouter(prefix="/admin/compliance", tags=["admin-compliance"])

# Mountain/Western states in scope for Phase 2
_MW_STATES = {"CO", "WY", "MT", "ID", "UT", "NM", "TX", "AZ", "NV", "OR", "WA", "CA", "AK", "HI"}

# Review cadence thresholds (days) — used for overdue detection
_REVIEW_THRESHOLDS = {
    "CO": 90,    # quarterly — live state
    "default_state": 90,   # quarterly for all Mountain/Western states
    "federal": 365,        # annual
    "nar": 365,            # annual (January)
    "hud_advertising_guidance": 180,  # semi-annual
}


def _get_meta_path():
    from pathlib import Path
    return Path(__file__).parent / "compliance_rules_meta.json"


def _read_meta() -> Dict[str, Any]:
    """Read compliance_rules_meta.json. Returns default skeleton if missing."""
    try:
        with open(_get_meta_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"version": _RULES_VERSION, "federal": {}, "states": {}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read compliance_rules_meta.json: {e}")


def _write_meta(meta: Dict[str, Any]) -> None:
    """Write compliance_rules_meta.json atomically."""
    import tempfile, os
    path = _get_meta_path()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, suffix=".tmp", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(meta, tmp, indent=2)
            tmp_path = tmp.name
        os.replace(tmp_path, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write compliance_rules_meta.json: {e}")


def _bump_version_if_needed(current_version: str) -> str:
    """
    Returns a new version string if the current calendar quarter has changed.
    Format: YYYY-QN  (e.g. 2026-Q2)
    Only bumps forward — never rolls back.
    """
    now = datetime.utcnow()
    quarter = (now.month - 1) // 3 + 1
    new_version = f"{now.year}-Q{quarter}"
    # Compare as strings — YYYY-QN sorts lexicographically when year is the same
    if new_version > current_version:
        return new_version
    return current_version


def _require_admin(request: Request) -> Dict[str, Any]:
    """
    Decode JWT and verify admin or super_admin role.
    Returns the decoded token payload.
    Raises 401/403 on failure.
    """
    import os as _os
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header else ""
    if not token:
        raise HTTPException(status_code=401, detail="Authorization header required.")
    try:
        import jwt as _jwt
        SECRET = _os.getenv("JWT_SECRET", "homebridge-secret-change-in-production")
        decoded = _jwt.decode(token, SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    role = decoded.get("role", "")
    if role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="admin or super_admin role required.")
    return decoded


def _days_since(date_str: str) -> Optional[int]:
    """
    Parse a YYYY-MM date string and return days elapsed since the first of that month.
    Returns None if date_str is not parseable.
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m")
        return (datetime.utcnow() - dt).days
    except Exception:
        return None


def _is_overdue(date_str: str, threshold_days: int) -> bool:
    days = _days_since(date_str)
    return days is not None and days > threshold_days


# ─────────────────────────────────────────────────────────────────────────────
# POST /admin/compliance/verify-state
# ─────────────────────────────────────────────────────────────────────────────

class VerifyStateRequest(BaseModel):
    state: str = Field(..., description="Two-letter state code, e.g. 'CO'")
    verified_by: str = Field(..., description="Full name of the reviewer")
    notes: str = Field(..., description="What was reviewed and what was found")
    verified_date: Optional[str] = Field(
        None,
        description="Override verification date as YYYY-MM. Defaults to current month."
    )


@admin_router.post("/verify-state")
async def verify_state(payload: VerifyStateRequest, request: Request):
    """
    Record that a compliance partner has reviewed the advertising rules for a given state
    against primary sources and found them current (or noted changes).

    Updates compliance_rules_meta.json with the new verified_date, reviewer name,
    and review notes. Bumps rules_version if the current quarter has changed.

    Required role: admin or super_admin.
    """
    _require_admin(request)

    state_key = payload.state.strip().upper()
    if state_key not in _MW_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"'{state_key}' is not in the Mountain/Western scope. "
                   f"Supported states: {', '.join(sorted(_MW_STATES))}"
        )

    now = datetime.utcnow()
    verified_date = payload.verified_date or now.strftime("%Y-%m")

    # Validate date format if supplied
    if payload.verified_date:
        try:
            datetime.strptime(payload.verified_date, "%Y-%m")
        except ValueError:
            raise HTTPException(status_code=400, detail="verified_date must be in YYYY-MM format.")

    # Calculate next_review date (add 90 days, convert to YYYY-MM)
    from datetime import timedelta
    threshold = _REVIEW_THRESHOLDS.get(state_key, _REVIEW_THRESHOLDS["default_state"])
    next_dt = now + timedelta(days=threshold)
    next_review = next_dt.strftime("%Y-%m")

    meta = _read_meta()

    # Bump version if quarter has changed
    old_version = meta.get("version", _RULES_VERSION)
    new_version = _bump_version_if_needed(old_version)
    version_bumped = new_version != old_version
    meta["version"] = new_version

    # Update the state entry
    if "states" not in meta:
        meta["states"] = {}
    if state_key not in meta["states"]:
        meta["states"][state_key] = {}

    entry = meta["states"][state_key]
    entry["verified_date"]    = verified_date
    entry["last_reviewed_by"] = payload.verified_by
    entry["review_notes"]     = payload.notes
    entry["next_review"]      = next_review
    entry["last_reviewed_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Preserve existing label/citation/source_url if already present
    # (a verify call should not wipe out citation metadata set at init)

    # Append to review_history (newest first, capped at 20 entries)
    history_entry = {
        "reviewed_at":  now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verified_date": verified_date,
        "reviewed_by":  payload.verified_by,
        "notes":        payload.notes,
        "source_type":  "state",
        "source_key":   state_key,
        "source_label": STATE_RULES.get(state_key, {}).get("label", f"{state_key} Real Estate Commission"),
        "layer":        entry.get("layer", "4"),
    }
    existing_history = entry.get("review_history", [])
    entry["review_history"] = ([history_entry] + existing_history)[:20]

    _write_meta(meta)

    state_label = STATE_RULES.get(state_key, {}).get("label", f"{state_key} Real Estate Commission")

    return {
        "success": True,
        "state": state_key,
        "state_label": state_label,
        "updated": {
            "verified_date":    verified_date,
            "last_reviewed_by": payload.verified_by,
            "next_review":      next_review,
        },
        "rules_version": {
            "previous": old_version,
            "current":  new_version,
            "bumped":   version_bumped,
        },
        "message": (
            f"{state_label} rules marked as verified for {verified_date}. "
            f"Next review due by {next_review}."
            + (" rules_version bumped to " + new_version + "." if version_bumped else "")
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /admin/compliance/status
# ─────────────────────────────────────────────────────────────────────────────

@admin_router.get("/status")
async def compliance_status(request: Request):
    """
    Returns the current verification status of all states and federal sources
    in the Mountain/Western scope.

    Readable by the compliance partner to determine what needs review this quarter.
    Flags overdue items and items coming due within 30 days.

    Required role: admin or super_admin.
    """
    _require_admin(request)

    meta = _read_meta()
    now = datetime.utcnow()
    today_str = now.strftime("%Y-%m-%d")

    # ── Federal sources ───────────────────────────────────────────────────────
    federal_section = meta.get("federal", {})
    federal_summary = []

    federal_sources = [
        ("fair_housing_act",        "Fair Housing Act (42 U.S.C. § 3604)",         "federal"),
        ("hud_advertising_guidance","HUD FHEO Digital Advertising Guidance",        "hud_advertising_guidance"),
        ("hud_regulations_part109", "HUD 24 C.F.R. Part 109",                      "federal"),
        ("achtenberg_memo",         "Achtenberg Memo (1995) — Master Bedroom Rule", "federal"),
        ("nar_code_of_ethics",      "NAR Code of Ethics (2026 edition)",            "nar"),
        ("doj_steering",            "DOJ Steering Enforcement",                     "federal"),
        ("respa_section8",          "RESPA § 8",                                   "federal"),
        ("regulation_z",            "Regulation Z / TILA",                         "federal"),
        ("cfpb_udaap",              "CFPB UDAAP",                                  "federal"),
    ]

    for key, display_name, cadence_key in federal_sources:
        entry = federal_section.get(key, {})
        verified_date = entry.get("verified_date", "never")
        next_review   = entry.get("next_review", "unknown")
        days_since    = _days_since(verified_date) if verified_date != "never" else None
        threshold     = _REVIEW_THRESHOLDS.get(cadence_key, _REVIEW_THRESHOLDS["federal"])
        overdue       = _is_overdue(verified_date, threshold) if verified_date != "never" else True
        due_soon      = False
        if next_review != "unknown":
            try:
                next_dt = datetime.strptime(next_review, "%Y-%m")
                days_to_next = (next_dt - now).days
                due_soon = 0 < days_to_next <= 30
            except Exception:
                pass

        federal_summary.append({
            "source":        display_name,
            "key":           key,
            "layer":         entry.get("layer", ""),
            "verified_date": verified_date,
            "next_review":   next_review,
            "days_since_verification": days_since,
            "overdue":       overdue,
            "due_soon":      due_soon,
            "citation":      entry.get("citation", ""),
            "source_url":    entry.get("source_url", ""),
            "verified_by":   entry.get("verified_by", "unknown"),
        })

    # ── States ────────────────────────────────────────────────────────────────
    states_section = meta.get("states", {})
    state_summary = []

    for state_key in sorted(_MW_STATES):
        entry = states_section.get(state_key, {})
        verified_date = entry.get("verified_date", "never")
        next_review   = entry.get("next_review", "unknown")
        days_since    = _days_since(verified_date) if verified_date != "never" else None
        threshold     = _REVIEW_THRESHOLDS.get(state_key, _REVIEW_THRESHOLDS["default_state"])
        overdue       = _is_overdue(verified_date, threshold) if verified_date != "never" else True
        due_soon      = False
        if next_review != "unknown":
            try:
                next_dt = datetime.strptime(next_review, "%Y-%m")
                days_to_next = (next_dt - now).days
                due_soon = 0 < days_to_next <= 30
            except Exception:
                pass

        state_label = (
            entry.get("label")
            or STATE_RULES.get(state_key, {}).get("label", f"{state_key} Real Estate Commission")
        )
        status_tag = entry.get("status", "staged")

        state_summary.append({
            "state":          state_key,
            "label":          state_label,
            "layer":          entry.get("layer", "4"),
            "status":         status_tag,         # "live" | "staged"
            "verified_date":  verified_date,
            "next_review":    next_review,
            "days_since_verification": days_since,
            "overdue":        overdue,
            "due_soon":       due_soon,
            "last_reviewed_by": entry.get("last_reviewed_by", "unknown"),
            "citation":       entry.get("citation", ""),
            "source_url":     entry.get("source_url", ""),
        })

    # ── Summary counts ────────────────────────────────────────────────────────
    states_overdue  = [s for s in state_summary  if s["overdue"]]
    federal_overdue = [f for f in federal_summary if f["overdue"]]
    states_due_soon = [s for s in state_summary  if s["due_soon"] and not s["overdue"]]

    # ── Collect review_history across all states and federal sources ──────────
    all_history = []
    for _se in meta.get("states", {}).values():
        all_history.extend(_se.get("review_history", []))
    for _fe in meta.get("federal", {}).values():
        all_history.extend(_fe.get("review_history", []))
    all_history.sort(key=lambda x: x.get("reviewed_at", ""), reverse=True)

    return {
        "rules_version":       meta.get("version", _RULES_VERSION),
        "report_generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope":               "Mountain/Western Region (14 states)",
        "layers":              meta.get("layers", {}),
        "summary": {
            "total_states_in_scope": len(_MW_STATES),
            "states_overdue":        len(states_overdue),
            "states_due_within_30d": len(states_due_soon),
            "federal_sources_overdue": len(federal_overdue),
            "attention_required":    len(states_overdue) > 0 or len(federal_overdue) > 0,
        },
        "action_required": {
            "overdue_states":   [{"state": s["state"], "label": s["label"], "last_verified": s["verified_date"], "days_elapsed": s["days_since_verification"]} for s in states_overdue],
            "overdue_federal":  [{"source": f["source"], "last_verified": f["verified_date"], "days_elapsed": f["days_since_verification"]} for f in federal_overdue],
            "due_soon_states":  [{"state": s["state"], "label": s["label"], "next_review": s["next_review"]} for s in states_due_soon],
        },
        "states":         state_summary,
        "federal":        federal_summary,
        "review_history": all_history,
        "note": (
            "HomeBridge is not a legal authority. These verification dates reflect "
            "the last time a compliance partner checked each source against its primary regulatory text. "
            "Rule changes between review cycles may not be reflected. "
            "When in doubt, agents should consult their broker or a real estate attorney."
        ),
    }

