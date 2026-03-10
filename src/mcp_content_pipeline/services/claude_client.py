"""Anthropic API client for video analysis."""

from __future__ import annotations

import json
import re
from datetime import datetime

import anthropic

from mcp_content_pipeline.models.schemas import VideoAnalysis

SYSTEM_PROMPT = """\
You are a content analyst and social media strategist. \
Given a YouTube video transcript, produce EXACTLY this JSON structure:
{
  "title": "original video title",
  "channel": "channel name",
  "url": "original URL",
  "date_analysed": "ISO 8601 date",
  "key_takeaways": ["takeaway 1", "takeaway 2", ...],
  "tldr": "2-3 sentence summary a busy person can read in 15 seconds",
  "twitter_hook": "social hook — see rules below",
  "topics": ["topic1", "topic2"]
}

SOCIAL HOOK RULES (strictly under 280 characters including hashtags):
- Lead with a bold claim, surprising stat, or contrarian take from the video — NOT a summary
- Use a pattern like: "[Surprising insight] — here's why it matters:" or "Most people think [X]. Actually, [Y]."
- Write in a punchy, conversational tone — as if you're telling a friend the one thing they NEED to know
- End with 2-3 relevant hashtags (count towards 280 chars)
- Do NOT start with "Just watched..." or "New video from..." — go straight to the insight
- The hook must make someone stop scrolling and want to learn more

IMPORTANT: All output must be in English. If the transcript is in another language, translate all content (key_takeaways, tldr, social hook) into fluent English.

Respond ONLY with valid JSON — no markdown fences, no preamble."""


def build_user_prompt(
    transcript: str,
    metadata: dict,
    custom_prompt: str | None = None,
) -> str:
    """Build the user prompt for Claude."""
    parts = [
        f"Video Title: {metadata.get('title', 'Unknown')}",
        f"Channel: {metadata.get('channel', 'Unknown')}",
        f"URL: {metadata.get('url', '')}",
        "",
        "TRANSCRIPT:",
        transcript,
    ]
    if custom_prompt:
        parts.extend(["", "ADDITIONAL INSTRUCTIONS:", custom_prompt])
    return "\n".join(parts)


def parse_analysis_response(raw: str, metadata: dict) -> VideoAnalysis:
    """Parse Claude's response into a VideoAnalysis, handling non-clean JSON."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    data = json.loads(cleaned)

    # Ensure required fields have fallbacks from metadata
    data.setdefault("title", metadata.get("title", "Unknown"))
    data.setdefault("channel", metadata.get("channel", "Unknown"))
    data.setdefault("url", metadata.get("url", ""))
    data["date_analysed"] = datetime.now().isoformat()

    return VideoAnalysis.model_validate(data)


async def analyse_transcript(
    api_key: str,
    model: str,
    transcript: str,
    metadata: dict,
    custom_prompt: str | None = None,
) -> VideoAnalysis:
    """Send transcript to Claude for analysis."""
    client = anthropic.AsyncAnthropic(api_key=api_key)

    user_prompt = build_user_prompt(transcript, metadata, custom_prompt)

    message = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = message.content[0].text
    return parse_analysis_response(raw_text, metadata)
