# pr_fetcher.py
import re
from datetime import datetime
from typing import List, Tuple, Dict
from github.PullRequest import PullRequest
from github_client import get_github_client


def parse_repo_url(url: str) -> Tuple[str, str]:
    """Parse owner and repo name from GitHub URL."""
    # Handle HTTPS: https://github.com/owner/repo
    https_match = re.match(r'https?://github\.com/([^/]+)/([^/]+)/?', url)
    if https_match:
        return https_match.group(1), https_match.group(2).replace('.git', '')

    # Handle SSH: git@github.com:owner/repo.git
    ssh_match = re.match(r'git@github\.com:([^/]+)/([^/]+)\.?', url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2).replace('.git', '')

    # Handle simple owner/repo format
    simple_match = re.match(r'^([^/]+)/([^/]+)$', url)
    if simple_match:
        return simple_match.group(1), simple_match.group(2)

    raise ValueError(f"Invalid GitHub URL format: {url}")


def is_pr_in_month(pr: PullRequest, year: int, month: int) -> bool:
    """Check if PR was created in the specified month."""
    return pr.created_at.year == year and pr.created_at.month == month


EXCLUDED_SOURCE_BRANCH_PREFIXES = ('release',)
EXCLUDED_SOURCE_BRANCHES = ('main',)


def should_exclude_pr(pr: PullRequest) -> bool:
    """Return True if PR should be excluded from statistics based on its source branch."""
    branch = pr.head.ref.lower()
    if branch in EXCLUDED_SOURCE_BRANCHES:
        return True
    if any(branch.startswith(prefix) for prefix in EXCLUDED_SOURCE_BRANCH_PREFIXES):
        return True
    return False


def is_pr_in_date_range(pr: PullRequest, start_date: datetime, end_date: datetime) -> bool:
    """Check if PR was created within the specified date range (inclusive)."""
    pr_date = pr.created_at
    # Normalize to date for comparison (ignore time component)
    pr_date_only = datetime(pr_date.year, pr_date.month, pr_date.day)
    start_date_only = datetime(start_date.year, start_date.month, start_date.day)
    end_date_only = datetime(end_date.year, end_date.month, end_date.day)
    return start_date_only <= pr_date_only <= end_date_only


def fetch_prs_for_month(repo_identifier: str, year: int, month: int, state: str = 'all', token: str = None) -> List[PullRequest]:
    """Fetch all PRs for a repo created in the specified month."""
    if '/' in repo_identifier:
        owner, repo_name = parse_repo_url(repo_identifier)
    else:
        raise ValueError(f"Invalid repo identifier: {repo_identifier}")

    client = get_github_client(token=token)
    repo = client.get_repo(f"{owner}/{repo_name}")
    all_prs = repo.get_pulls(state=state, sort='created', direction='desc')

    prs_in_month = [
        pr for pr in all_prs
        if is_pr_in_month(pr, year, month) and not should_exclude_pr(pr)
    ]

    return prs_in_month


def fetch_prs_for_date_range(repo_identifier: str, start_date: datetime, end_date: datetime, state: str = 'all', token: str = None) -> List[PullRequest]:
    """Fetch all PRs for a repo created within the specified date range."""
    if '/' in repo_identifier:
        owner, repo_name = parse_repo_url(repo_identifier)
    else:
        raise ValueError(f"Invalid repo identifier: {repo_identifier}")

    client = get_github_client(token=token)
    repo = client.get_repo(f"{owner}/{repo_name}")
    all_prs = repo.get_pulls(state=state, sort='created', direction='desc')

    prs_in_range = [
        pr for pr in all_prs
        if is_pr_in_date_range(pr, start_date, end_date) and not should_exclude_pr(pr)
    ]

    return prs_in_range


def get_pr_comments_count(pr: PullRequest) -> int:
    """Get total comments count for a PR (review comments + issue comments)."""
    try:
        review_comments = pr.get_review_comments().totalCount
        issue_comments = pr.get_comments().totalCount
        return review_comments + issue_comments
    except Exception:
        return 0


def fetch_comments_for_prs(prs: List[PullRequest]) -> Dict[int, int]:
    """Fetch comments count for all PRs.

    Returns dict mapping PR number to comments count.
    """
    comments_map = {}
    for pr in prs:
        comments_map[pr.number] = get_pr_comments_count(pr)
    return comments_map
