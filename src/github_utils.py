"""
GitHub API utility wrapper using PyGithub.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from github import Github, GithubException
from github.Repository import Repository
from github.Issue import Issue
from github.PullRequest import PullRequest

logger = logging.getLogger("oss-maintainer-bot.github")


class GitHubClient:
    """Thin wrapper around PyGithub for OSS Maintainer Bot operations."""

    def __init__(self, token: str, repository: str, dry_run: bool = False):
        self._gh = Github(token)
        self._repo: Repository = self._gh.get_repo(repository)
        self.dry_run = dry_run
        logger.info("GitHub client initialized for repo: %s", repository)

    # ── Issues ────────────────────────────────────────────────────────────────

    def get_issue(self, number: int) -> Issue:
        return self._repo.get_issue(number)

    def add_labels(self, issue_number: int, labels: list[str]):
        """Add labels to an issue, creating missing ones with a default color."""
        if self.dry_run:
            logger.info("[DRY RUN] Would add labels %s to issue #%d", labels, issue_number)
            return
        issue = self._repo.get_issue(issue_number)
        existing = {lb.name for lb in self._repo.get_labels()}
        for label in labels:
            if label not in existing:
                self._repo.create_label(name=label, color="ededed")
        issue.add_to_labels(*labels)
        logger.info("Added labels %s to issue #%d", labels, issue_number)

    def post_comment(self, issue_number: int, body: str):
        """Post a comment on an issue or PR."""
        if self.dry_run:
            logger.info("[DRY RUN] Would comment on #%d: %s", issue_number, body[:80])
            return
        issue = self._repo.get_issue(issue_number)
        issue.create_comment(body)
        logger.info("Posted comment on #%d", issue_number)

    def get_stale_issues(
        self,
        stale_days: int,
        state: str = "open",
        exclude_labels: Optional[list] = None,
    ) -> list[Issue]:
        """Return open issues with no activity in the last `stale_days` days."""
        now = datetime.now(timezone.utc)
        stale = []
        exclude_labels = exclude_labels or ["stale", "pinned", "security"]

        for issue in self._repo.get_issues(state=state, sort="updated", direction="asc"):
            if issue.pull_request:
                continue  # skip PRs
            labels = {lb.name for lb in issue.labels}
            if labels & set(exclude_labels):
                continue
            delta = (now - issue.updated_at.replace(tzinfo=timezone.utc)).days
            if delta >= stale_days:
                stale.append(issue)
        return stale

    # ── Pull Requests ─────────────────────────────────────────────────────────

    def get_pr(self, number: int) -> PullRequest:
        return self._repo.get_pull(number)

    def get_pr_diff(self, pr: PullRequest) -> str:
        """Return a truncated diff for LLM context (max 8000 chars)."""
        files = pr.get_files()
        diff_parts = []
        total = 0
        for f in files:
            patch = getattr(f, "patch", "") or ""
            header = f"--- {f.filename} (+{f.additions} -{f.deletions})\n"
            chunk = header + patch[:2000] + "\n"
            diff_parts.append(chunk)
            total += len(chunk)
            if total > 8000:
                diff_parts.append("... (diff truncated for length) ...")
                break
        return "\n".join(diff_parts)

    def post_pr_comment(self, pr_number: int, body: str):
        self.post_comment(pr_number, body)

    # ── Releases ──────────────────────────────────────────────────────────────

    def get_commits_since_tag(self, since_tag: str) -> list[str]:
        """Return commit messages since the given tag."""
        try:
            tag_ref = self._repo.get_git_ref(f"tags/{since_tag}")
            tag_sha = tag_ref.object.sha
        except GithubException:
            logger.warning("Tag %s not found, returning last 50 commits.", since_tag)
            tag_sha = None

        messages = []
        for commit in self._repo.get_commits():
            if tag_sha and commit.sha == tag_sha:
                break
            messages.append(commit.commit.message.split("\n")[0])
            if len(messages) >= 100:
                break
        return messages

    def create_draft_release(self, tag: str, name: str, body: str):
        """Create a draft GitHub Release."""
        if self.dry_run:
            logger.info("[DRY RUN] Would create draft release: %s", name)
            return
        self._repo.create_git_release(
            tag=tag, name=name, message=body, draft=True, prerelease=False
        )
        logger.info("Created draft release: %s", name)

    # ── Search ────────────────────────────────────────────────────────────────

    def get_open_issues_summary(self, limit: int = 50) -> list[dict]:
        """Return a list of open issue summaries for duplicate detection."""
        result = []
        for issue in self._repo.get_issues(state="open"):
            if issue.pull_request:
                continue
            result.append({
                "number": issue.number,
                "title": issue.title,
                "body": (issue.body or "")[:500],
            })
            if len(result) >= limit:
                break
        return result
