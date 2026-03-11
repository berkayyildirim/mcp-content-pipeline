"""Tests for the sync_to_github tool and GitHub client."""

from __future__ import annotations

import pytest

from mcp_content_pipeline.models.schemas import VideoAnalysis
from mcp_content_pipeline.services.github_client import (
    generate_filename,
    generate_index,
    generate_markdown,
    parse_index_entries,
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

    def test_index_multiple_distinct_entries(self):
        a1 = VideoAnalysis(
            title="Video One",
            channel="C",
            url="https://youtube.com/watch?v=1",
            date_analysed="2026-03-08T12:00:00",
            key_takeaways=["t"],
            tldr="s",
            twitter_hook="h",
            topics=["t"],
        )
        a2 = VideoAnalysis(
            title="Video Two",
            channel="C",
            url="https://youtube.com/watch?v=2",
            date_analysed="2026-03-09T12:00:00",
            key_takeaways=["t"],
            tldr="s",
            twitter_hook="h",
            topics=["t"],
        )
        index = generate_index([a1, a2], "content/videos")
        lines = [line for line in index.split("\n") if line.startswith("| 2026")]
        assert len(lines) == 2

    def test_index_empty_list(self):
        index = generate_index([], "content/videos")
        assert "# Video Analyses Index" in index


class TestIndexMergeBehavior:
    """Tests for merging new analyses with existing index.md entries."""

    def _make_analysis(self, title: str, date: str) -> VideoAnalysis:
        return VideoAnalysis(
            title=title,
            channel="Channel",
            url=f"https://youtube.com/watch?v={title}",
            date_analysed=date,
            key_takeaways=["t"],
            tldr="s",
            twitter_hook="h",
            topics=["t"],
        )

    def test_existing_entries_preserved(self):
        existing_index = (
            "# Video Analyses Index\n\n"
            "| Date | Title | File |\n"
            "|------|-------|------|\n"
            "| 2026-03-01 | Old Video | [2026-03-01-old-video.md](./2026-03-01-old-video.md) |\n"
        )
        new_analysis = self._make_analysis("New Video", "2026-03-10T12:00:00")
        index = generate_index([new_analysis], "content/videos", existing_index)

        assert "Old Video" in index
        assert "New Video" in index

    def test_duplicates_deduplicated(self):
        existing_index = (
            "# Video Analyses Index\n\n"
            "| Date | Title | File |\n"
            "|------|-------|------|\n"
            "| 2026-03-08 | ML in Production: 3 Strategies | "
            "[2026-03-08-ml-in-production-3-strategies.md]"
            "(./2026-03-08-ml-in-production-3-strategies.md) |\n"
        )
        # Same analysis again — should deduplicate, not create two rows
        dup_analysis = self._make_analysis(
            "ML in Production: 3 Strategies", "2026-03-08T12:00:00"
        )
        index = generate_index([dup_analysis], "content/videos", existing_index)

        data_rows = [
            line for line in index.split("\n") if line.startswith("|") and "Date" not in line and "---" not in line
        ]
        assert len(data_rows) == 1

    def test_new_entries_added(self):
        existing_index = (
            "# Video Analyses Index\n\n"
            "| Date | Title | File |\n"
            "|------|-------|------|\n"
            "| 2026-03-01 | First | [2026-03-01-first.md](./2026-03-01-first.md) |\n"
        )
        a1 = self._make_analysis("Second", "2026-03-05T12:00:00")
        a2 = self._make_analysis("Third", "2026-03-10T12:00:00")
        index = generate_index([a1, a2], "content/videos", existing_index)

        assert "First" in index
        assert "Second" in index
        assert "Third" in index
        data_rows = [
            line for line in index.split("\n") if line.startswith("|") and "Date" not in line and "---" not in line
        ]
        assert len(data_rows) == 3

    def test_sorted_by_date_descending(self):
        existing_index = (
            "# Video Analyses Index\n\n"
            "| Date | Title | File |\n"
            "|------|-------|------|\n"
            "| 2026-03-01 | Oldest | [2026-03-01-oldest.md](./2026-03-01-oldest.md) |\n"
        )
        middle = self._make_analysis("Middle", "2026-03-05T12:00:00")
        newest = self._make_analysis("Newest", "2026-03-10T12:00:00")
        index = generate_index([middle, newest], "content/videos", existing_index)

        data_rows = [
            line for line in index.split("\n") if line.startswith("|") and "Date" not in line and "---" not in line
        ]
        assert len(data_rows) == 3
        assert "Newest" in data_rows[0]
        assert "Middle" in data_rows[1]
        assert "Oldest" in data_rows[2]

    def test_no_existing_index(self):
        """When there's no existing index, behaves like before."""
        analysis = self._make_analysis("Only Video", "2026-03-08T12:00:00")
        index = generate_index([analysis], "content/videos", None)

        assert "Only Video" in index
        data_rows = [
            line for line in index.split("\n") if line.startswith("|") and "Date" not in line and "---" not in line
        ]
        assert len(data_rows) == 1

    def test_parse_index_entries(self):
        content = (
            "# Video Analyses Index\n\n"
            "| Date | Title | File |\n"
            "|------|-------|------|\n"
            "| 2026-03-01 | Vid A | [2026-03-01-vid-a.md](./2026-03-01-vid-a.md) |\n"
            "| 2026-03-05 | Vid B | [2026-03-05-vid-b.md](./2026-03-05-vid-b.md) |\n"
        )
        entries = parse_index_entries(content)
        assert len(entries) == 2
        assert "2026-03-01-vid-a.md" in entries
        assert "2026-03-05-vid-b.md" in entries


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
