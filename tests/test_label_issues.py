"""Tests for the auto-label issues feature."""

import pytest
from unittest.mock import MagicMock, patch

from features.label_issues import LabelIssuesFeature


@pytest.fixture
def config():
    return {
        "openai_api_key": "sk-test",
        "model": "gpt-4o-mini",
        "label_confidence": 0.7,
        "custom_labels": "",
    }


@pytest.fixture
def mock_gh():
    gh = MagicMock()
    gh.dry_run = False
    return gh


def test_labels_bug_issue(config, mock_gh):
    """High-confidence bug issue should receive 'bug' label."""
    feature = LabelIssuesFeature(config, mock_gh)

    with patch.object(feature.llm, "complete_json", return_value={
        "labels": ["bug"],
        "confidence": 0.92,
        "reasoning": "Describes unexpected crash behavior",
    }):
        result = feature.run({
            "number": 42,
            "title": "App crashes when I click submit",
            "body": "Steps to reproduce: 1. Open app 2. Click submit 3. App crashes",
        })

    assert result == ["bug"]
    mock_gh.add_labels.assert_called_once_with(42, ["bug"])
    mock_gh.post_comment.assert_called_once()


def test_skips_low_confidence(config, mock_gh):
    """Low-confidence classification should not apply any labels."""
    feature = LabelIssuesFeature(config, mock_gh)

    with patch.object(feature.llm, "complete_json", return_value={
        "labels": ["feature"],
        "confidence": 0.45,
        "reasoning": "Unclear if bug or feature",
    }):
        result = feature.run({
            "number": 43,
            "title": "Something about the button",
            "body": "I'm not sure if this is a bug",
        })

    assert result == []
    mock_gh.add_labels.assert_not_called()


def test_filters_invalid_labels(config, mock_gh):
    """LLM-returned labels not in allowed set should be filtered out."""
    feature = LabelIssuesFeature(config, mock_gh)

    with patch.object(feature.llm, "complete_json", return_value={
        "labels": ["bug", "wontfix"],  # wontfix is not in DEFAULT_LABELS
        "confidence": 0.9,
        "reasoning": "Valid bug with wontfix status",
    }):
        result = feature.run({
            "number": 44,
            "title": "Old bug that won't be fixed",
            "body": "This is a known issue.",
        })

    assert "wontfix" not in result
    assert "bug" in result


def test_handles_empty_llm_response(config, mock_gh):
    """Empty LLM response should not crash and return empty list."""
    feature = LabelIssuesFeature(config, mock_gh)

    with patch.object(feature.llm, "complete_json", return_value={}):
        result = feature.run({
            "number": 45,
            "title": "Unclear issue",
            "body": None,
        })

    assert result == []
    mock_gh.add_labels.assert_not_called()
