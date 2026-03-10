"""Tests for the sync_to_github tool and GitHub client."""

from __future__ import annotations

import pytest

from mcp_content_pipeline.models.schemas import VideoAnalysis
from mcp_content_pipeline.services.github_client import (
    generate_filename,
    generate_index,
    generate_markdown,
)
from mcp_content_pipeline.tools.sync_to_github import sync_to_github


@pytest.fixture
def analysis():
    return VideoAnalysis(
        title="ML in Production: 3 Strategies",
        channel="Tech Hub",
        url="https://www.youtube.com/watch?v=abc123",
        date_analysed="2026-03-08T12:00:00",
        key_takeaways=["Takeaway 1", "Takeaway 2", "Takeaway 3"],
        tldr="A short summary of the video content.",
        twitter_hook="Bold claim about ML #MLOps #AI",
        topics=["MLOps", "AI"],
    )


class TestGenerateMarkdown:
    def test_markdown_contains_title(self, analysis):
        md = generate_markdown(analysis)
        assert "# ML in Production: 3 Strategies" in md

    def test_markdown_contains_channel(self, analysis):
        md = generate_markdown(analysis)
        assert "**Channel:** Tech Hub" in md

    def test_markdown_contains_url(self, analysis):
        md = generate_markdown(analysis)
        assert "**URL:** https://www.youtube.com/watch?v=abc123" in md

    def test_markdown_contains_takeaways(self, analysis):
        md = generate_markdown(analysis)
        assert "- Takeaway 1" in md
        assert "- Takeaway 2" in md
        assert "- Takeaway 3" in md

    def test_markdown_contains_tldr(self, analysis):
        md = generate_markdown(analysis)
        assert "A short summary of the video content." in md

    def test_markdown_contains_social_hook(self, analysis):
        md = generate_markdown(analysis)
        assert "## Social Hook" in md
        assert "> Bold claim about ML #MLOps #AI" in md

    def test_markdown_contains_topics(self, analysis):
        md = generate_markdown(analysis)
        assert "**Topics:** MLOps, AI" in md


class TestGenerateFilename:
    def test_filename_format(self, analysis):
        filename = generate_filename(analysis, "content/videos")
        assert filename == "content/videos/2026-03-08-ml-in-production-3-strategies.md"

    def test_filename_slugification(self):
        a = VideoAnalysis(
            title="What's the Deal with AI? A Deep Dive!!!",
            channel="Test",
            url="https://youtube.com/watch?v=abc",
            date_analysed="2026-01-15T10:00:00",
            key_takeaways=["t1"],
            tldr="summary",
            twitter_hook="hook",
            topics=["AI"],
        )
        filename = generate_filename(a, "output")
        assert "what-s-the-deal-with-ai-a-deep-dive" in filename
        assert filename.endswith(".md")
        assert filename.startswith("output/2026-01-15-")

    def test_filename_long_title_truncated(self):
        a = VideoAnalysis(
            title="A" * 200,
            channel="Test",
            url="https://youtube.com/watch?v=abc",
            date_analysed="2026-01-01T00:00:00",
            key_takeaways=["t1"],
            tldr="s",
            twitter_hook="h",
            topics=["t"],
        )
        filename = generate_filename(a, "out")
        # slug max_length=80, so filename should be reasonable length
        slug_part = filename.split("/")[-1]
        assert len(slug_part) < 120


class TestGenerateIndex:
    def test_index_contains_header(self, analysis):
        index = generate_index([analysis], "content/videos")
        assert "# Video Analyses Index" in index

    def test_index_contains_table_headers(self, analysis):
        index = generate_index([analysis], "content/videos")
        assert "| Date | Title | File |" in index

    def test_index_contains_entry(self, analysis):
        index = generate_index([analysis], "content/videos")
        assert "ML in Production: 3 Strategies" in index
        assert "2026-03-08" in index

    def test_index_multiple_entries(self, analysis):
        analyses = [analysis, analysis]
        index = generate_index(analyses, "content/videos")
        lines = [line for line in index.split("\n") if line.startswith("| 2026")]
        assert len(lines) == 2

    def test_index_empty_list(self):
        index = generate_index([], "content/videos")
        assert "# Video Analyses Index" in index


class TestSyncToGithub:
    @pytest.mark.asyncio
    async def test_sync_commit_message_too_long(self, analysis):
        from mcp_content_pipeline.config import Settings

        settings = Settings(
            anthropic_api_key="test",
            github_token="token",
            github_repo="owner/repo",
        )
        with pytest.raises(ValueError, match="500 characters or fewer"):
            await sync_to_github(
                analyses=[analysis], settings=settings, commit_message="A" * 501
            )

    @pytest.mark.asyncio
    async def test_sync_commit_message_empty(self, analysis):
        from mcp_content_pipeline.config import Settings

        settings = Settings(
            anthropic_api_key="test",
            github_token="token",
            github_repo="owner/repo",
        )
        with pytest.raises(ValueError, match="must not be empty"):
            await sync_to_github(
                analyses=[analysis], settings=settings, commit_message="   "
            )

    @pytest.mark.asyncio
    async def test_sync_commit_message_at_limit(self, analysis):
        from mcp_content_pipeline.config import Settings

        settings = Settings(
            anthropic_api_key="test",
            github_token="token",
            github_repo="owner/repo",
        )
        # Should not raise for commit_message validation — will fail on GitHub call instead
        with pytest.raises(Exception):
            await sync_to_github(
                analyses=[analysis], settings=settings, commit_message="A" * 500
            )

    @pytest.mark.asyncio
    async def test_sync_missing_token(self, analysis):
        from mcp_content_pipeline.config import Settings

        settings = Settings(
            anthropic_api_key="test",
            github_token="",
            github_repo="owner/repo",
        )
        with pytest.raises(ValueError, match="GitHub token not configured"):
            await sync_to_github(analyses=[analysis], settings=settings)

    @pytest.mark.asyncio
    async def test_sync_missing_repo(self, analysis):
        from mcp_content_pipeline.config import Settings

        settings = Settings(
            anthropic_api_key="test",
            github_token="token",
            github_repo="",
        )
        with pytest.raises(ValueError, match="GitHub repo not configured"):
            await sync_to_github(analyses=[analysis], settings=settings)
