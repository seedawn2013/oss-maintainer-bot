"""Tests for the PR summarization feature."""

import pytest
from unittest.mock import MagicMock, patch

from features.summarize_prs import SummarizePRsFeature


@pytest.fixture
def config():
    return {
        "openai_api_key": "sk-test",
        "model": "gpt-4o-mini",
        "language": "en",
    }


@pytest.fixture
def mock_gh():
    gh = MagicMock()
    gh.dry_run = False
    mock_pr = MagicMock()
    mock_pr.get_commits.return_value = [
        MagicMock(commit=MagicMock(message="feat: add new endpoint\ndetailed body")),
        MagicMock(commit=MagicMock(message="fix: correct null check")),
    ]
    gh.get_pr.return_value = mock_pr
    gh.get_pr_diff.return_value = "--- src/api.py\n+++ src/api.py\n@@ -1,3 +1,5 @@\n+def new_endpoint():\n+    pass"
    return gh


def test_generates_and_posts_summary(config, mock_gh):
    """Should generate a summary and post it as a PR comment."""
    feature = SummarizePRsFeature(config, mock_gh)

    with patch.object(feature.llm, "complete",
                      return_value="This PR adds a new API endpoint and fixes a null check."):
        result = feature.run({"number": 10, "title": "Add new API endpoint"})

    assert result is True
    mock_gh.post_pr_comment.assert_called_once()
    comment_body = mock_gh.post_pr_comment.call_args[0][1]
    assert "AI-Generated PR Summary" in comment_body
    assert "OSS Maintainer Bot" in comment_body


def test_returns_false_on_empty_summary(config, mock_gh):
    """Should return False if LLM returns empty response."""
    feature = SummarizePRsFeature(config, mock_gh)

    with patch.object(feature.llm, "complete", return_value=""):
        result = feature.run({"number": 11, "title": "Minor refactor"})

    assert result is False
    mock_gh.post_pr_comment.assert_not_called()


def test_returns_false_on_github_error(config, mock_gh):
    """Should return False if GitHub API call fails."""
    feature = SummarizePRsFeature(config, mock_gh)
    mock_gh.get_pr.side_effect = Exception("GitHub API error")

    result = feature.run({"number": 12, "title": "Something"})

    assert result is False
