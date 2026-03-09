"""YouTube transcript extraction."""

from __future__ import annotations

import re

import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    YouTubeTranscriptApiException,
)
from youtube_transcript_api.formatters import TextFormatter

HTTP_TIMEOUT = 30.0


def parse_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/live/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not parse video ID from URL: {url}")


async def fetch_transcript(video_id: str, max_tokens: int = 100000) -> str:
    """Fetch transcript for a YouTube video.

    Tries English first, then falls back to auto-generated captions.
    """
    ytt_api = YouTubeTranscriptApi()
    try:
        transcript = ytt_api.fetch(video_id, languages=["en"])
    except YouTubeTranscriptApiException:
        try:
            transcript = ytt_api.fetch(video_id, languages=["en-US", "en-GB"])
        except YouTubeTranscriptApiException:
            transcript_list = ytt_api.list(video_id)
            try:
                # Try English transcript from the list
                transcript_obj = transcript_list.find_transcript(["en"])
                transcript = transcript_obj.fetch()
            except NoTranscriptFound:
                try:
                    # Try generated transcript in common languages, translate to English
                    transcript_obj = transcript_list.find_generated_transcript(
                        ["tr", "es", "fr", "de", "pt", "ja", "ko", "ar", "hi", "zh-Hans"]
                    )
                    transcript = transcript_obj.translate("en").fetch()
                except NoTranscriptFound:
                    # Last resort: any manually created transcript, translate to English
                    transcript_obj = transcript_list.find_manually_created_transcript(
                        ["tr", "es", "fr", "de", "pt", "ja", "ko", "ar", "hi", "zh-Hans"]
                    )
                    transcript = transcript_obj.translate("en").fetch()

    formatter = TextFormatter()
    text = formatter.format_transcript(transcript)

    # Truncate if too long (rough estimate: 1 token ≈ 4 chars)
    max_chars = max_tokens * 4
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Transcript truncated due to length]"

    return text


async def fetch_video_metadata(video_id: str) -> dict:
    """Fetch video metadata via oembed (no API key needed)."""
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    return {
        "title": data.get("title", "Unknown Title"),
        "channel": data.get("author_name", "Unknown Channel"),
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }
