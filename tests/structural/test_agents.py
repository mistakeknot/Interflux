"""Tests for Interflux agent structure."""

from pathlib import Path

import pytest

from helpers import parse_frontmatter


def _get_agent_files(agents_dir: Path) -> list[Path]:
    """Get all agent .md files from review/ and research/ directories."""
    agent_files = []
    for category in ["review", "research"]:
        category_dir = agents_dir / category
        if category_dir.is_dir():
            agent_files.extend(sorted(category_dir.glob("*.md")))
    return agent_files


def test_agent_count(agents_dir):
    """Total agent count matches expected value."""
    agent_files = _get_agent_files(agents_dir)
    assert len(agent_files) == 12, (
        f"Expected 12 agents, found {len(agent_files)}: "
        f"{[f.stem for f in agent_files]}"
    )


AGENT_FILES = _get_agent_files(Path(__file__).resolve().parent.parent.parent / "agents")


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=lambda p: p.stem)
def test_agent_is_nonempty(agent_file):
    """Agent file has content (not just frontmatter)."""
    _, body = parse_frontmatter(agent_file)
    assert len(body.strip()) > 50, f"{agent_file.name} has too little content"


def test_all_fd_agents_present(agents_dir):
    """All 7 fd-* agents exist."""
    expected = [
        "fd-architecture", "fd-safety", "fd-correctness",
        "fd-quality", "fd-user-product", "fd-performance",
        "fd-game-design",
    ]
    review_dir = agents_dir / "review"
    for name in expected:
        assert (review_dir / f"{name}.md").exists(), f"Missing agent: {name}"


def test_all_research_agents_present(agents_dir):
    """All 5 research agents exist."""
    expected = [
        "best-practices-researcher", "framework-docs-researcher",
        "git-history-analyzer", "learnings-researcher",
        "repo-research-analyst",
    ]
    research_dir = agents_dir / "research"
    for name in expected:
        assert (research_dir / f"{name}.md").exists(), f"Missing agent: {name}"


def test_concurrency_patterns_reference(agents_dir):
    """concurrency-patterns.md reference file exists."""
    ref = agents_dir / "review" / "references" / "concurrency-patterns.md"
    assert ref.exists(), "references/concurrency-patterns.md is missing"
