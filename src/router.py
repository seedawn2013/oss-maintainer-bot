"""
Event Router - dispatches GitHub events to the correct feature handlers.
"""

import logging
from typing import Any

from features.label_issues import LabelIssuesFeature
from features.summarize_prs import SummarizePRsFeature
from features.stale_responder import StaleResponderFeature
from features.release_notes import ReleaseNotesFeature
from features.duplicate_detector import DuplicateDetectorFeature

logger = logging.getLogger("oss-maintainer-bot.router")


class EventRouter:
    """Routes incoming GitHub webhook events to the appropriate feature."""

    def __init__(self, config: dict, gh_client: Any, features: set):
        self.config = config
        self.gh_client = gh_client
        self.features = features

        # Instantiate all feature handlers
        self._label_issues = LabelIssuesFeature(config, gh_client)
        self._summarize_prs = SummarizePRsFeature(config, gh_client)
        self._stale_responder = StaleResponderFeature(config, gh_client)
        self._release_notes = ReleaseNotesFeature(config, gh_client)
        self._duplicate_detector = DuplicateDetectorFeature(config, gh_client)

    def route(self, event_name: str, payload: dict) -> dict:
        """Route the event and return aggregated results."""
        results = {
            "labels_applied": "",
            "prs_summarized": 0,
            "stale_responded": 0,
            "release_notes": False,
        }

        if event_name == "issues":
            action = payload.get("action", "")
            if action in ("opened", "reopened"):
                issue = payload.get("issue", {})
                logger.info("Routing issue #%s (action=%s)", issue.get("number"), action)

                if "label-issues" in self.features:
                    labels = self._label_issues.run(issue)
                    results["labels_applied"] = ",".join(labels)

                if "detect-duplicates" in self.features:
                    self._duplicate_detector.run(issue)

        elif event_name == "pull_request":
            action = payload.get("action", "")
            if action in ("opened", "synchronize"):
                pr = payload.get("pull_request", {})
                logger.info("Routing PR #%s (action=%s)", pr.get("number"), action)

                if "summarize-prs" in self.features:
                    summarized = self._summarize_prs.run(pr)
                    results["prs_summarized"] = 1 if summarized else 0

        elif event_name == "schedule":
            logger.info("Routing scheduled run...")

            if "respond-stale" in self.features:
                count = self._stale_responder.run()
                results["stale_responded"] = count

        elif event_name == "push":
            ref = payload.get("ref", "")
            if ref.startswith("refs/tags/") and "release-notes" in self.features:
                tag = ref.replace("refs/tags/", "")
                logger.info("Routing tag push for release notes: %s", tag)
                generated = self._release_notes.run(tag)
                results["release_notes"] = generated

        else:
            logger.info("No handler for event: %s", event_name)

        return results
