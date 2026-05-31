"""Duplicate Issue Detector feature."""

import logging

from llm.client import LLMClient
from llm.prompts import DUPLICATE_SYSTEM, DUPLICATE_USER

logger = logging.getLogger("oss-maintainer-bot.duplicate_detector")

DUPLICATE_THRESHOLD = 0.85


class DuplicateDetectorFeature:
    """Detects duplicate or semantically similar issues using LLM."""

    def __init__(self, config: dict, gh_client):
        self.config = config
        self.gh = gh_client
        self.llm = LLMClient(
            api_key=config["openai_api_key"],
            model=config["model"],
        )

    def run(self, issue: dict) -> bool:
        """
        Check if the new issue duplicates an existing one.
        Returns True if a duplicate was found and flagged.
        """
        number = issue.get("number", 0)
        title = issue.get("title", "")
        body = (issue.get("body") or "")[:1000]

        existing = self.gh.get_open_issues_summary(limit=50)
        # Exclude the issue itself
        existing = [i for i in existing if i["number"] != number]

        if not existing:
            logger.info("No existing issues to compare against for #%d", number)
            return False

        existing_str = "\n".join(
            f"#{i['number']}: {i['title']} — {i['body'][:200]}"
            for i in existing[:30]
        )

        result = self.llm.complete_json(
            system_prompt=DUPLICATE_SYSTEM,
            user_prompt=DUPLICATE_USER.format(
                new_title=title,
                new_body=body,
                existing_issues=existing_str,
            ),
        )

        if not result:
            return False

        is_dup: bool = result.get("is_duplicate", False)
        dup_of: int = result.get("duplicate_of") or 0
        score: float = float(result.get("similarity_score", 0.0))
        reason: str = result.get("reason", "")

        logger.info(
            "Issue #%d duplicate check: is_dup=%s, of=#%s, score=%.2f",
            number, is_dup, dup_of, score
        )

        if is_dup and score >= DUPLICATE_THRESHOLD and dup_of:
            self.gh.add_labels(number, ["duplicate"])
            comment = (
                f"🔍 This issue appears to be a duplicate of #{dup_of}.\n\n"
                f"{reason}\n\n"
                f"Please check #{dup_of} and add a comment there if your situation is different."
            )
            self.gh.post_comment(number, comment)
            return True

        return False
