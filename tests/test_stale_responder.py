"""Tests for the stale issue responder feature."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

from features.stale_responder import StaleResponderFeature


@pytest.fixture
def config():
    return {
        "openai_api_key": "sk-test",
        "model": "gpt-4o-mini",
        "stale_days": 30,
        "language": "en",
    }


@pytest.fixture
def mock_gh():
    gh = MagicMock()
    gh.dry_run = False
    return gh


def _make_stale_issue(number: int, days_old: int):
    issue = MagicMock()
    issue.number = number
    issue.title = f"Stale issue #{number}"
    issue.body = "This is an old issue that has not been updated."
    issue.updated_at = datetime.now(timezone.utc) - timedelta(days=days_old)
    return issue


def test_responds_to_stale_issues(config, mock_gh):
    """Should respond to all stale issues returned by GitHub client."""
    stale = [_make_stale_issue(1, 45), _make_stale_issue(2, 60)]
    mock_gh.get_stale_issues.return_value = stale

    feature = StaleResponderFeature(config, mock_gh)

    with patch.object(feature.llm, "complete",
                      return_value="Hi! Is this issue still relevant?"):
        count = feature.run()

    assert count == 2
    assert mock_gh.post_comment.call_count == 2
    assert mock_gh.add_labels.call_count == 2


def test_handles_no_stale_issues(config, mock_gh):
    """Should return 0 if there are no stale issues."""
    mock_gh.get_stale_issues.return_value = []

    feature = StaleResponderFeature(config, mock_gh)
    count = feature.run()

    assert count == 0
    mock_gh.post_comment.assert_not_called()


def test_continues_on_individual_error(config, mock_gh):
    """Should continue processing even if one issue fails."""
    stale = [_make_stale_issue(1, 35), _make_stale_issue(2, 40)]
    mock_gh.get_stale_issues.return_value = stale

    feature = StaleResponderFeature(config, mock_gh)

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("GitHub API error")
        return "Hi, is this still relevant?"

    with patch.object(feature.llm, "complete", side_effect=side_effect):
        count = feature.run()

    # Second issue should still be processed
    assert count == 1
