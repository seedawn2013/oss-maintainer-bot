"""Release Notes Generator feature."""

import logging

from llm.client import LLMClient
from llm.prompts import RELEASE_NOTES_SYSTEM, RELEASE_NOTES_USER

logger = logging.getLogger("oss-maintainer-bot.release_notes")


class ReleaseNotesFeature:
    """Generates structured release notes from commits since the last tag."""

    def __init__(self, config: dict, gh_client):
        self.config = config
        self.gh = gh_client
        self.llm = LLMClient(
            api_key=config["openai_api_key"],
            model=config["model"],
        )

    def run(self, tag: str) -> bool:
        """
        Generate and create a draft release for the given tag.
        Returns True if release was created.
        """
        logger.info("Generating release notes for tag: %s", tag)

        # Find the previous tag to diff against
        prev_tag = self._get_previous_tag(tag)
        commits = self.gh.get_commits_since_tag(prev_tag) if prev_tag else []

        if not commits:
            logger.warning("No commits found for tag %s — skipping release notes", tag)
            return False

        logger.info("Collected %d commits for release notes", len(commits))

        commit_list = "\n".join(f"- {c}" for c in commits[:80])
        user = RELEASE_NOTES_USER.format(version=tag, commits=commit_list)

        notes = self.llm.complete(
            system_prompt=RELEASE_NOTES_SYSTEM,
            user_prompt=user,
            temperature=0.3,
            max_tokens=1000,
        )

        if not notes:
            logger.warning("LLM returned empty release notes for %s", tag)
            return False

        release_name = f"Release {tag}"
        self.gh.create_draft_release(tag=tag, name=release_name, body=notes)
        logger.info("Created draft release: %s", release_name)
        return True

    def _get_previous_tag(self, current_tag: str) -> str:
        """Attempt to find the previous semver tag."""
        # Simple heuristic: strip 'v' prefix and decrement patch
        try:
            clean = current_tag.lstrip("v")
            parts = clean.split(".")
            if len(parts) == 3:
                patch = int(parts[2])
                if patch > 0:
                    prev = f"v{parts[0]}.{parts[1]}.{patch - 1}"
                    return prev
                minor = int(parts[1])
                if minor > 0:
                    return f"v{parts[0]}.{minor - 1}.0"
        except (ValueError, IndexError):
            pass
        return ""
