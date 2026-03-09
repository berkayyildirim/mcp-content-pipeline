"""Tests for the transcript service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from youtube_transcript_api._errors import NoTranscriptFound, YouTubeTranscriptApiException

from mcp_content_pipeline.services.transcript import (
    fetch_transcript,
    fetch_video_metadata,
    parse_video_id,
)


class TestFetchTranscript:
    @pytest.mark.asyncio
    async def test_fetch_transcript_english(self):
        mock_transcript = MagicMock()
        mock_ytt = MagicMock()
        mock_ytt.fetch.return_value = mock_transcript

        with patch("mcp_content_pipeline.services.transcript.YouTubeTranscriptApi") as MockApi, \
             patch("mcp_content_pipeline.services.transcript.TextFormatter") as MockFormatter:
            MockApi.return_value = mock_ytt
            formatter_instance = MockFormatter.return_value
            formatter_instance.format_transcript.return_value = "Hello this is a transcript"

            result = await fetch_transcript("dQw4w9WgXcQ")
            assert result == "Hello this is a transcript"
            mock_ytt.fetch.assert_called_once_with("dQw4w9WgXcQ", languages=["en"])

    @pytest.mark.asyncio
    async def test_fetch_transcript_fallback(self):
        mock_ytt = MagicMock()
        mock_ytt.fetch.side_effect = [
            YouTubeTranscriptApiException("No English"),
            YouTubeTranscriptApiException("No en-US/en-GB"),
        ]
        mock_transcript_obj = MagicMock()
        mock_transcript_obj.fetch.return_value = MagicMock()
        mock_ytt.list.return_value.find_transcript.return_value = mock_transcript_obj

        with patch("mcp_content_pipeline.services.transcript.YouTubeTranscriptApi") as MockApi, \
             patch("mcp_content_pipeline.services.transcript.TextFormatter") as MockFormatter:
            MockApi.return_value = mock_ytt
            formatter_instance = MockFormatter.return_value
            formatter_instance.format_transcript.return_value = "Auto-generated transcript"

            result = await fetch_transcript("dQw4w9WgXcQ")
            assert result == "Auto-generated transcript"

    @pytest.mark.asyncio
    async def test_fetch_transcript_truncation(self):
        long_text = "A" * 500000

        mock_ytt = MagicMock()
        mock_ytt.fetch.return_value = MagicMock()

        with patch("mcp_content_pipeline.services.transcript.YouTubeTranscriptApi") as MockApi, \
             patch("mcp_content_pipeline.services.transcript.TextFormatter") as MockFormatter:
            MockApi.return_value = mock_ytt
            formatter_instance = MockFormatter.return_value
            formatter_instance.format_transcript.return_value = long_text

            result = await fetch_transcript("dQw4w9WgXcQ", max_tokens=1000)
            assert len(result) < len(long_text)
            assert "[Transcript truncated due to length]" in result

    @pytest.mark.asyncio
    async def test_fetch_transcript_no_truncation_needed(self):
        short_text = "Short transcript."

        mock_ytt = MagicMock()
        mock_ytt.fetch.return_value = MagicMock()

        with patch("mcp_content_pipeline.services.transcript.YouTubeTranscriptApi") as MockApi, \
             patch("mcp_content_pipeline.services.transcript.TextFormatter") as MockFormatter:
            MockApi.return_value = mock_ytt
            formatter_instance = MockFormatter.return_value
            formatter_instance.format_transcript.return_value = short_text

            result = await fetch_transcript("dQw4w9WgXcQ")
            assert result == short_text
            assert "[Transcript truncated" not in result


    @pytest.mark.asyncio
    async def test_fetch_transcript_non_transcript_error_propagates(self):
        """Non-YouTubeTranscriptApiException errors should not be caught."""
        mock_ytt = MagicMock()
        mock_ytt.fetch.side_effect = RuntimeError("Unexpected system error")

        with patch("mcp_content_pipeline.services.transcript.YouTubeTranscriptApi") as MockApi:
            MockApi.return_value = mock_ytt
            with pytest.raises(RuntimeError, match="Unexpected system error"):
                await fetch_transcript("dQw4w9WgXcQ")


class TestParseVideoId:
    def test_live_url(self):
        url = "https://www.youtube.com/live/-c7k_MT84eQ"
        assert parse_video_id(url) == "-c7k_MT84eQ"

    def test_live_url_with_query_params(self):
        url = "https://www.youtube.com/live/-c7k_MT84eQ?si=abc123"
        assert parse_video_id(url) == "-c7k_MT84eQ"

    def test_standard_watch_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert parse_video_id(url) == "dQw4w9WgXcQ"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError):
            parse_video_id("https://example.com/notavideo")


class TestFetchTranscriptFallbackChain:
    @pytest.mark.asyncio
    async def test_turkish_transcript_translated_to_english(self):
        """When English is unavailable, a Turkish generated transcript is translated."""
        mock_ytt = MagicMock()
        mock_ytt.fetch.side_effect = YouTubeTranscriptApiException("No English")

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
            "test_id", [], MagicMock()
        )
        mock_translated = MagicMock()
        mock_translated.fetch.return_value = MagicMock()
        mock_generated = MagicMock()
        mock_generated.translate.return_value = mock_translated
        mock_transcript_list.find_generated_transcript.return_value = mock_generated

        mock_ytt.list.return_value = mock_transcript_list

        with patch("mcp_content_pipeline.services.transcript.YouTubeTranscriptApi") as MockApi, \
             patch("mcp_content_pipeline.services.transcript.TextFormatter") as MockFormatter:
            MockApi.return_value = mock_ytt
            MockFormatter.return_value.format_transcript.return_value = "Translated Turkish transcript"

            result = await fetch_transcript("test_id")
            assert result == "Translated Turkish transcript"
            mock_generated.translate.assert_called_once_with("en")

    @pytest.mark.asyncio
    async def test_manually_created_transcript_fallback(self):
        """When no generated transcript exists, falls back to manually created."""
        mock_ytt = MagicMock()
        mock_ytt.fetch.side_effect = YouTubeTranscriptApiException("No English")

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
            "test_id", [], MagicMock()
        )
        mock_transcript_list.find_generated_transcript.side_effect = NoTranscriptFound(
            "test_id", [], MagicMock()
        )
        mock_translated = MagicMock()
        mock_translated.fetch.return_value = MagicMock()
        mock_manual = MagicMock()
        mock_manual.translate.return_value = mock_translated
        mock_transcript_list.find_manually_created_transcript.return_value = mock_manual

        mock_ytt.list.return_value = mock_transcript_list

        with patch("mcp_content_pipeline.services.transcript.YouTubeTranscriptApi") as MockApi, \
             patch("mcp_content_pipeline.services.transcript.TextFormatter") as MockFormatter:
            MockApi.return_value = mock_ytt
            MockFormatter.return_value.format_transcript.return_value = "Manual transcript translated"

            result = await fetch_transcript("test_id")
            assert result == "Manual transcript translated"
            mock_manual.translate.assert_called_once_with("en")


class TestFetchVideoMetadata:
    @pytest.mark.asyncio
    async def test_fetch_metadata_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "title": "Test Video",
            "author_name": "Test Channel",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("mcp_content_pipeline.services.transcript.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await fetch_video_metadata("dQw4w9WgXcQ")
            assert result["title"] == "Test Video"
            assert result["channel"] == "Test Channel"
            assert "youtube.com/watch?v=dQw4w9WgXcQ" in result["url"]

    @pytest.mark.asyncio
    async def test_fetch_metadata_missing_fields(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("mcp_content_pipeline.services.transcript.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await fetch_video_metadata("dQw4w9WgXcQ")
            assert result["title"] == "Unknown Title"
            assert result["channel"] == "Unknown Channel"
