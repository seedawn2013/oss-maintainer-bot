"""Auto-label Issues feature using LLM classification."""

import logging
from typing import Optional

from llm.client import LLMClient
from llm.prompts import LABEL_SYSTEM, LABEL_USER

logger = logging.getLogger("oss-maintainer-bot.label_issues")

DEFAULT_LABELS = {
    "bug", "feature", "question", "documentation",
    "invalid", "security", "performance"
}


class LabelIssuesFeature:
    """Classifies new issues and applies appropriate labels via LLM."""

    def __init__(self, config: dict, gh_client):
        self.config = config
        self.gh = gh_client
        self.llm = LLMClient(
            api_key=config["openai_api_key"],
            model=config["model"],
        )
        self.min_confidence: float = config.get("label_confidence", 0.7)
        self._parse_custom_labels(config.get("custom_labels", ""))

    def _parse_custom_labels(self, raw: str):
        """Parse custom label JSON string if provided."""
        import json
        if raw.strip():
            try:
                self.custom_labels = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Could not parse custom_labels JSON: %s", raw)
                self.custom_labels = {}
        else:
            self.custom_labels = {}

    def run(self, issue: dict) -> list[str]:
        """
        Classify the issue and apply labels.
        Returns list of applied label names.
        """
        number = issue.get("number", 0)
        title = issue.get("title", "").strip()
        body = (issue.get("body") or "").strip()[:3000]

        logger.info("Classifying issue #%d: %s", number, title)

        user_prompt = LABEL_USER.format(title=title, body=body or "(no body provided)")

        result = self.llm.complete_json(
            system_prompt=LABEL_SYSTEM,
            user_prompt=user_prompt,
        )

        if not result:
            logger.warning("LLM returned empty result for issue #%d", number)
            return []

        labels: list = result.get("labels", [])
        confidence: float = float(result.get("confidence", 0.0))
        reasoning: str = result.get("reasoning", "")

        logger.info(
            "Issue #%d classified as %s (confidence=%.2f): %s",
            number, labels, confidence, reasoning
        )

        if confidence < self.min_confidence:
            logger.info(
                "Confidence %.2f below threshold %.2f — skipping auto-label for #%d",
                confidence, self.min_confidence, number
            )
            return []

        # Filter to valid labels
        valid = DEFAULT_LABELS | set(self.custom_labels.keys())
        labels = [lb for lb in labels if lb in valid]

        if labels:
            self.gh.add_labels(number, labels)
            self._post_acknowledgment(number, labels, reasoning)

        return labels

    def _post_acknowledgment(self, issue_number: int, labels: list, reasoning: str):
        """Post a brief acknowledgment comment on the labeled issue."""
        label_str = ", ".join(f"`{lb}`" for lb in labels)
        body = (
            f"Thank you for opening this issue! 🤖\n\n"
            f"I've automatically labeled it as {label_str} based on the content.\n\n"
            f"A maintainer will review it shortly."
        )
        self.gh.post_comment(issue_number, body)
