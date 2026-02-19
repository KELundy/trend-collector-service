import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None  # Will fail at runtime with a clear error if not installed


router = APIRouter(prefix="/content", tags=["content-engine"])


class ContentRequest(BaseModel):
    trend_situation: str = Field(..., description="The selected trend or situation text")
    niche: str = Field(..., description="The selected niche label")
    persona: Optional[str] = Field(
        None,
        description="Optional persona or audience description to further tailor the content",
    )


class ContentResponse(BaseModel):
    headline: str
    thumbnailIdea: str
    hashtags: str
    post: str
    cta: str
    script: str
    generated_at: datetime


def _get_anthropic_client() -> Anthropic:
    if Anthropic is None:
        raise RuntimeError(
            "Anthropic Python client is not installed. "
            "Add `anthropic` to requirements.txt and redeploy."
        )
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Set it in Render and redeploy."
        )
    return Anthropic(api_key=api_key)


def _build_prompt(trend_situation: str, niche: str, persona: Optional[str]) -> str:
    persona_text = (
        f"The target persona is: {persona}.\n"
        if persona
        else "The target persona is a typical homeowner or decision-maker in this niche.\n"
    )

    return f"""
You are a senior marketing strategist and copywriter for a real estate professional.

Niche: {niche}
Situation / Trend:
{trend_situation}

{persona_text}
Your job is to create a complete content package for short-form video and social media.

Return content that fits these exact fields (do NOT label them, just write the content for each in order):

1) Headline – a compelling, curiosity-driven hook for the video/post.
2) Thumbnail idea – a short visual concept or text that could appear on a thumbnail.
3) Hashtags – a concise set of relevant hashtags, separated by spaces.
4) Post – a short-form social post (for Instagram/FB/LinkedIn) that stands on its own.
5) CTA – a clear, specific call to action that feels natural and not pushy.
6) Script – a short-form video script (30–60 seconds), written as spoken dialogue.

Tone:
- Clear, confident, and empathetic.
- Specific to the niche and situation.
- Avoid generic fluff. Use concrete language and real-world phrasing.

Important:
- Do NOT explain what you are doing.
- Do NOT include numbering or labels in the output.
- Just output the six pieces of content, separated clearly with blank lines between them.
"""


def _parse_claude_output(raw_text: str) -> ContentResponse:
    """
    We expect Claude to return six blocks separated by blank lines.
    We’ll be defensive and pad missing pieces if needed.
    """
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
        generated_at=datetime.utcnow(),
    )


@router.post("/generate-content", response_model=ContentResponse)
async def generate_content(payload: ContentRequest) -> ContentResponse:
    """
    Main Content Engine endpoint.

    Frontend expects:
    - headline
    - thumbnailIdea
    - hashtags
    - post
    - cta
    - script
    """
    try:
        client = _get_anthropic_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    prompt = _build_prompt(
        trend_situation=payload.trend_situation,
        niche=payload.niche,
        persona=payload.persona,
    )

    try:
      response = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=900,
    temperature=0.7,
    messages=[
        {
            "role": "user",
            "content": prompt,
        }
    ]
)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Error calling Claude: {str(e)}",
        )

    try:
        # Anthropic messages API returns a list of content blocks; we assume first text block
        content_blocks = response.content or []
        text_chunks = [
            block.text for block in content_blocks if getattr(block, "type", "") == "text"
        ]
        raw_text = "\n\n".join(text_chunks).strip()
        if not raw_text:
            raise ValueError("Claude returned empty content.")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing Claude response: {str(e)}",
        )

    try:
        return _parse_claude_output(raw_text)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error structuring content response: {str(e)}",
        )
