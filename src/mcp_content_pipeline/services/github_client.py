"""GitHub API client for markdown storage."""

from __future__ import annotations

from datetime import datetime

from github import Github, GithubException
from slugify import slugify

from mcp_content_pipeline.models.schemas import SyncFileResult, SyncResult, VideoAnalysis


def generate_markdown(analysis: VideoAnalysis) -> str:
    """Generate a markdown file from an analysis result."""
    takeaways = "\n".join(f"- {t}" for t in analysis.key_takeaways)
    topics = ", ".join(analysis.topics)

    return f"""# {analysis.title}

**Channel:** {analysis.channel}
**URL:** {analysis.url}
**Analysed:** {analysis.date_analysed}
**Topics:** {topics}

---

## Key Takeaways

{takeaways}

## TLDR

{analysis.tldr}

## Social Hook

> {analysis.twitter_hook}
"""


def generate_filename(analysis: VideoAnalysis, output_dir: str) -> str:
    """Generate a filename for the analysis markdown file."""
    try:
        date_str = datetime.fromisoformat(analysis.date_analysed).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        date_str = datetime.now().strftime("%Y-%m-%d")

    slug = slugify(analysis.title, max_length=80)
    return f"{output_dir}/{date_str}-{slug}.md"


def generate_index(analyses: list[VideoAnalysis], output_dir: str) -> str:
    """Generate an index.md listing all analyses as a table."""
    lines = [
        "# Video Analyses Index",
        "",
        "| Date | Title | File |",
        "|------|-------|------|",
    ]

    for analysis in analyses:
        filename = generate_filename(analysis, output_dir)
        basename = filename.split("/")[-1]
        try:
            date_str = datetime.fromisoformat(analysis.date_analysed).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date_str = "Unknown"
        lines.append(f"| {date_str} | {analysis.title} | [{basename}](./{basename}) |")

    lines.append("")
    return "\n".join(lines)


async def sync_to_github(
    token: str,
    repo_name: str,
    branch: str,
    output_dir: str,
    analyses: list[VideoAnalysis],
    commit_message: str = "Add video analyses",
) -> SyncResult:
    """Push analysis markdown files to GitHub."""
    g = Github(token)
    repo = g.get_repo(repo_name)

    file_results: list[SyncFileResult] = []

    for analysis in analyses:
        filepath = generate_filename(analysis, output_dir)
        content = generate_markdown(analysis)

        try:
            existing = repo.get_contents(filepath, ref=branch)
            repo.update_file(
                filepath,
                commit_message,
                content,
                existing.sha,  # type: ignore[union-attr]
                branch=branch,
            )
            file_results.append(SyncFileResult(path=filepath, action="updated"))
        except GithubException:
            repo.create_file(filepath, commit_message, content, branch=branch)
            file_results.append(SyncFileResult(path=filepath, action="created"))

    # Update index.md
    index_path = f"{output_dir}/index.md"
    index_content = generate_index(analyses, output_dir)

    try:
        existing_index = repo.get_contents(index_path, ref=branch)
        result = repo.update_file(
            index_path,
            f"{commit_message} (update index)",
            index_content,
            existing_index.sha,  # type: ignore[union-attr]
            branch=branch,
        )
    except GithubException:
        result = repo.create_file(
            index_path,
            f"{commit_message} (update index)",
            index_content,
            branch=branch,
        )

    commit_sha = result["commit"].sha if result else None

    return SyncResult(
        files=file_results,
        commit_sha=commit_sha,
        index_path=index_path,
    )
