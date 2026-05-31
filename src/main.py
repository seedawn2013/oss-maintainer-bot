#!/usr/bin/env python3
"""
OSS Maintainer Bot - Main Entry Point

Routes GitHub events to the appropriate feature handler.
"""

import json
import logging
import os
import sys

from router import EventRouter
from github_utils import GitHubClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("oss-maintainer-bot")


def load_config() -> dict:
    """Load configuration from environment variables set by action.yml."""
    return {
        "github_token": os.environ["GITHUB_TOKEN"],
        "openai_api_key": os.environ["OPENAI_API_KEY"],
        "model": os.environ.get("INPUT_MODEL", "gpt-4o-mini"),
        "features": os.environ.get("INPUT_FEATURES", "all"),
        "stale_days": int(os.environ.get("INPUT_STALE_DAYS", "30")),
        "label_confidence": float(os.environ.get("INPUT_LABEL_CONFIDENCE", "0.7")),
        "language": os.environ.get("INPUT_LANGUAGE", "en"),
        "dry_run": os.environ.get("INPUT_DRY_RUN", "false").lower() == "true",
        "custom_labels": os.environ.get("INPUT_CUSTOM_LABELS", ""),
        "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
        "event_path": os.environ.get("GITHUB_EVENT_PATH", ""),
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
    }


def load_event(event_path: str) -> dict:
    """Load the GitHub event payload from disk."""
    if not event_path or not os.path.exists(event_path):
        logger.warning("Event path not found: %s", event_path)
        return {}
    with open(event_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_features(features_str: str) -> set:
    """Parse comma-separated feature flags."""
    if features_str.strip().lower() == "all":
        return {"label-issues", "summarize-prs", "respond-stale",
                "release-notes", "detect-duplicates"}
    return {f.strip().lower() for f in features_str.split(",") if f.strip()}


def main():
    logger.info("OSS Maintainer Bot starting...")

    config = load_config()
    event_payload = load_event(config["event_path"])
    features = parse_features(config["features"])

    if config["dry_run"]:
        logger.info("DRY RUN mode enabled — no GitHub write calls will be made.")

    logger.info("Event: %s | Features: %s | Repo: %s",
                config["event_name"], features, config["repository"])

    gh_client = GitHubClient(
        token=config["github_token"],
        repository=config["repository"],
        dry_run=config["dry_run"],
    )

    router = EventRouter(
        config=config,
        gh_client=gh_client,
        features=features,
    )

    try:
        results = router.route(config["event_name"], event_payload)
        logger.info("Bot completed successfully. Results: %s", results)

        # Set Action outputs
        _set_output("labels-applied", results.get("labels_applied", ""))
        _set_output("prs-summarized", str(results.get("prs_summarized", 0)))
        _set_output("stale-issues-responded", str(results.get("stale_responded", 0)))
        _set_output("release-notes-generated", str(results.get("release_notes", False)).lower())

    except Exception as exc:
        logger.error("Bot encountered an error: %s", exc, exc_info=True)
        sys.exit(1)


def _set_output(name: str, value: str):
    """Write a GitHub Actions output variable."""
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    else:
        logger.debug("OUTPUT %s=%s", name, value)


if __name__ == "__main__":
    main()
