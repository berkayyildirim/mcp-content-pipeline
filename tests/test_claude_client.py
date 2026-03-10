"""Tests for the Claude client service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_content_pipeline.models.schemas import VideoAnalysis
from mcp_content_pipeline.services.claude_client import (
    SYSTEM_PROMPT,
    analyse_transcript,
    build_user_prompt,
    parse_analysis_response,
)


class TestBuildUserPrompt:
    def test_basic_prompt(self, sample_transcript, sample_video_metadata):
        prompt = build_user_prompt(sample_transcript, sample_video_metadata)
        assert "Video Title: ML in Production" in prompt
        assert "Channel: Tech Engineering Hub" in prompt
        assert "TRANSCRIPT:" in prompt
        assert sample_transcript in prompt

    def test_prompt_with_custom_instructions(self, sample_transcript, sample_video_metadata):
        prompt = build_user_prompt(
            sample_transcript,
            sample_video_metadata,
            custom_prompt="Focus on DevOps",
        )
        assert "ADDITIONAL INSTRUCTIONS:" in prompt
        assert "Focus on DevOps" in prompt

    def test_prompt_without_custom_instructions(self, sample_transcript, sample_video_metadata):
        prompt = build_user_prompt(sample_transcript, sample_video_metadata)
        assert "ADDITIONAL INSTRUCTIONS:" not in prompt


class TestParseAnalysisResponse:
    def test_parse_clean_json(self, sample_video_metadata):
        data = {
            "title": "Test",
            "channel": "Test Channel",
            "url": "https://youtube.com/watch?v=abc",
            "date_analysed": "2026-03-08T12:00:00",
            "key_takeaways": ["t1", "t2"],
            "tldr": "Summary",
            "twitter_hook": "Hook text #test",
            "topics": ["topic1"],
        }
        result = parse_analysis_response(json.dumps(data), sample_video_metadata)
        assert isinstance(result, VideoAnalysis)
        assert result.title == "Test"

    def test_parse_json_with_markdown_fences(self, sample_video_metadata):
        data = {
            "title": "Test",
            "channel": "Ch",
            "url": "https://youtube.com/watch?v=abc",
            "date_analysed": "2026-03-08T12:00:00",
            "key_takeaways": ["t1"],
            "tldr": "s",
            "twitter_hook": "h",
            "topics": ["t"],
        }
        raw = f"```json\n{json.dumps(data)}\n```"
        result = parse_analysis_response(raw, sample_video_metadata)
        assert result.title == "Test"

    def test_parse_json_with_plain_fences(self, sample_video_metadata):
        data = {
            "title": "Test",
            "channel": "Ch",
            "url": "https://youtube.com/watch?v=abc",
            "date_analysed": "2026-03-08T12:00:00",
            "key_takeaways": ["t1"],
            "tldr": "s",
            "twitter_hook": "h",
            "topics": ["t"],
        }
        raw = f"```\n{json.dumps(data)}\n```"
        result = parse_analysis_response(raw, sample_video_metadata)
        assert result.title == "Test"

    def test_parse_uses_metadata_fallback(self, sample_video_metadata):
        data = {
            "date_analysed": "2026-03-08T12:00:00",
            "key_takeaways": ["t1"],
            "tldr": "s",
            "twitter_hook": "h",
            "topics": ["t"],
        }
        result = parse_analysis_response(json.dumps(data), sample_video_metadata)
        assert result.title == "ML in Production: 3 Strategies That Actually Work"
        assert result.channel == "Tech Engineering Hub"

    def test_parse_invalid_json_raises(self, sample_video_metadata):
        with pytest.raises(Exception):
            parse_analysis_response("not json at all", sample_video_metadata)

    def test_parse_overrides_hallucinated_date(self, sample_video_metadata):
        data = {
            "title": "Test",
            "channel": "Test Channel",
            "url": "https://youtube.com/watch?v=abc",
            "date_analysed": "1999-01-01T00:00:00",
            "key_takeaways": ["t1", "t2"],
            "tldr": "Summary",
            "twitter_hook": "Hook text #test",
            "topics": ["topic1"],
        }
        result = parse_analysis_response(json.dumps(data), sample_video_metadata)
        assert "1999-01-01" not in result.date_analysed

    def test_parse_validates_pydantic(self, sample_video_metadata):
        # Missing required fields and no fallback
        data = {"title": "Test"}
        with pytest.raises(Exception):
            parse_analysis_response(json.dumps(data), {})


class TestAnalyseTranscript:
    @pytest.mark.asyncio
    async def test_analyse_transcript_success(self, sample_transcript, sample_video_metadata, mock_anthropic_response):
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=mock_anthropic_response)]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        with patch("mcp_content_pipeline.services.claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await analyse_transcript(
                api_key="test-key",
                model="claude-sonnet-4-20250514",
                transcript=sample_transcript,
                metadata=sample_video_metadata,
            )
            assert isinstance(result, VideoAnalysis)
            assert len(result.key_takeaways) > 0

    @pytest.mark.asyncio
    async def test_analyse_transcript_uses_system_prompt(self, sample_transcript, sample_video_metadata, mock_anthropic_response):
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=mock_anthropic_response)]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        with patch("mcp_content_pipeline.services.claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
            await analyse_transcript(
                api_key="test-key",
                model="claude-sonnet-4-20250514",
                transcript=sample_transcript,
                metadata=sample_video_metadata,
            )
            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["system"] == SYSTEM_PROMPT
            assert call_kwargs["model"] == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_analyse_transcript_api_error(self, sample_transcript, sample_video_metadata):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        with patch("mcp_content_pipeline.services.claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
            with pytest.raises(Exception, match="API Error"):
                await analyse_transcript(
                    api_key="test-key",
                    model="claude-sonnet-4-20250514",
                    transcript=sample_transcript,
                    metadata=sample_video_metadata,
                )
