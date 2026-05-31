"""Stale Issue Responder feature."""

import logging
from datetime import datetime, timezone

from llm.client import LLMClient
from llm.prompts import STALE_RESPONSE_SYSTEM, STALE_RESPONSE_USER

logger = logging.getLogger("oss-maintainer-bot.stale_responder")

LANGUAGE_NAMES = {
    "en": "English",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "es": "Spanish",
    "fr": "French",
}


class StaleResponderFeature:
    """Detects stale issues and posts polite, context-aware follow-up comments."""

    def __init__(self, config: dict, gh_client):
        self.config = config
        self.gh = gh_client
        self.llm = LLMClient(
            api_key=config["openai_api_key"],
            model=config["model"],
        )
        self.stale_days: int = config.get("stale_days", 30)
        self.language: str = config.get("language", "en")

    def run(self) -> int:
        """
        Scan for stale issues and respond to each.
        Returns the number of issues responded to.
        """
        stale_issues = self.gh.get_stale_issues(self.stale_days)
        logger.info("Found %d stale issues (threshold: %d days)",
                    len(stale_issues), self.stale_days)

        responded = 0
        for issue in stale_issues:
            try:
                self._respond(issue)
                responded += 1
            except Exception as exc:
                logger.error("Failed to respond to stale issue #%d: %s",
                             issue.number, exc)

        return responded

    def _respond(self, issue):
        """Generate and post a context-aware stale response."""
        now = datetime.now(timezone.utc)
        last_activity = (now - issue.updated_at.replace(tzinfo=timezone.utc)).days
        body_snippet = (issue.body or "")[:300]
        lang_name = LANGUAGE_NAMES.get(self.language, "English")

        system = STALE_RESPONSE_SYSTEM.format(language=lang_name)
        user = STALE_RESPONSE_USER.format(
            title=issue.title,
            last_activity=last_activity,
            body_snippet=body_snippet or "(no description)",
        )

        response = self.llm.complete(
            system_prompt=system,
            user_prompt=user,
            temperature=0.6,
            max_tokens=200,
        )

        if not response:
            logger.warning("LLM returned empty stale response for issue #%d", issue.number)
            return

        # Append stale label
        self.gh.add_labels(issue.number, ["stale"])
        self.gh.post_comment(issue.number, response)
        logger.info("Responded to stale issue #%d (inactive %d days)",
                    issue.number, last_activity)
