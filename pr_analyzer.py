# pr_analyzer.py
from typing import List, Dict, Any, Tuple
from datetime import datetime
from collections import Counter, defaultdict
from github import PullRequest
from config import (
    AI_DETECTION_ENABLED,
    AI_BRANCH_PREFIXES,
    AI_AUTHOR_PATTERNS
)


def is_ai_pr(pr: PullRequest) -> bool:
    """Check if PR is AI-generated based on configurable branch prefixes or author patterns."""
    # If AI detection is disabled, always return False
    if not AI_DETECTION_ENABLED:
        return False

    branch = pr.head.ref.lower()
    author = pr.user.login.lower()

    # Check branch prefixes
    for prefix in AI_BRANCH_PREFIXES:
        if branch.startswith(prefix):
            return True

    # Check author patterns (substring match)
    for pattern in AI_AUTHOR_PATTERNS:
        if pattern in author:
            return True

    return False


def calculate_merge_time_hours(pr: PullRequest) -> float:
    """Calculate merge time in hours."""
    if pr.merged_at and pr.created_at:
        delta = pr.merged_at - pr.created_at
        return delta.total_seconds() / 3600
    return 0


def get_pr_labels(pr: PullRequest) -> List[str]:
    """Get list of label names from PR."""
    return [label.name for label in pr.labels]


def analyze_prs(prs: List[PullRequest], start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
    """Analyze PRs and return comprehensive metrics."""
    total = len(prs)
    merged = 0
    open_count = 0
    closed = 0
    ai_prs = 0
    human_prs = 0
    ai_merged = 0
    human_merged = 0
    merge_times = []
    ai_merge_times = []
    human_merge_times = []
    contributors = Counter()
    ai_contributors = Counter()
    human_contributors = Counter()
    labels_counter = Counter()
    prs_by_date = {}

    for pr in prs:
        is_ai = is_ai_pr(pr)
        author = pr.user.login

        # Count by state
        if pr.merged_at is not None:
            merged += 1
            merge_time = calculate_merge_time_hours(pr)
            merge_times.append(merge_time)

            if is_ai:
                ai_merged += 1
                ai_merge_times.append(merge_time)
            else:
                human_merged += 1
                human_merge_times.append(merge_time)
        elif pr.state == 'open':
            open_count += 1
        else:
            closed += 1

        # Count AI vs Human
        if is_ai:
            ai_prs += 1
            ai_contributors[author] += 1
        else:
            human_prs += 1
            human_contributors[author] += 1

        # Count all contributors
        contributors[author] += 1

        # Count labels
        for label in get_pr_labels(pr):
            labels_counter[label] += 1

        # Count by date
        date_key = pr.created_at.strftime('%Y-%m-%d')
        prs_by_date[date_key] = prs_by_date.get(date_key, 0) + 1

    # Calculate averages and percentages
    avg_merge_time = sum(merge_times) / len(merge_times) if merge_times else 0
    ai_avg_merge_time = sum(ai_merge_times) / len(ai_merge_times) if ai_merge_times else 0
    human_avg_merge_time = sum(human_merge_times) / len(human_merge_times) if human_merge_times else 0

    ai_merge_rate = (ai_merged / ai_prs * 100) if ai_prs > 0 else 0
    human_merge_rate = (human_merged / human_prs * 100) if human_prs > 0 else 0

    ai_contribution_pct = (ai_prs / total * 100) if total > 0 else 0

    # PR velocity (PRs per day)
    if prs_by_date:
        days_with_prs = len(prs_by_date)
        pr_velocity = total / days_with_prs if days_with_prs > 0 else 0
    else:
        pr_velocity = 0

    # All contributors (sorted by PR count)
    top_contributors = contributors.most_common()
    top_ai_contributors = ai_contributors.most_common()
    top_human_contributors = human_contributors.most_common()

    # Top labels
    top_labels = labels_counter.most_common(10)

    # Split PRs into AI and Human lists
    ai_pr_list = [pr for pr in prs if is_ai_pr(pr)]
    human_pr_list = [pr for pr in prs if not is_ai_pr(pr)]

    # Add contributor stats
    contributors_stats = analyze_contributors(prs, start_date, end_date)

    return {
        'total': total,
        'merged': merged,
        'open': open_count,
        'closed': closed,
        'ai_prs': ai_prs,
        'human_prs': human_prs,
        'ai_merged': ai_merged,
        'human_merged': human_merged,
        'avg_merge_time_hours': avg_merge_time,
        'ai_avg_merge_time_hours': ai_avg_merge_time,
        'human_avg_merge_time_hours': human_avg_merge_time,
        'ai_merge_rate': ai_merge_rate,
        'human_merge_rate': human_merge_rate,
        'ai_contribution_pct': ai_contribution_pct,
        'pr_velocity': pr_velocity,
        'top_contributors': top_contributors,
        'top_ai_contributors': top_ai_contributors,
        'top_human_contributors': top_human_contributors,
        'top_labels': top_labels,
        'prs_by_date': prs_by_date,
        'ai_pr_list': ai_pr_list,
        'human_pr_list': human_pr_list,
        'all_prs': prs,
        'contributors': contributors_stats,
    }


def analyze_comparison(prs_month1: List[PullRequest], prs_month2: List[PullRequest],
                       month1_name: str, month2_name: str) -> Dict[str, Any]:
    """Compare PRs between two months."""
    metrics1 = analyze_prs(prs_month1)
    metrics2 = analyze_prs(prs_month2)

    return {
        'month1': {'name': month1_name, 'metrics': metrics1},
        'month2': {'name': month2_name, 'metrics': metrics2},
        'comparison': {
            'total_diff': metrics2['total'] - metrics1['total'],
            'merged_diff': metrics2['merged'] - metrics1['merged'],
            'ai_prs_diff': metrics2['ai_prs'] - metrics1['ai_prs'],
            'ai_contribution_diff': metrics2['ai_contribution_pct'] - metrics1['ai_contribution_pct'],
            'velocity_diff': metrics2['pr_velocity'] - metrics1['pr_velocity'],
        }
    }


def analyze_contributors(prs: List[PullRequest], start_date: datetime = None, end_date: datetime = None) -> Dict[str, Dict[str, Any]]:
    """Calculate statistics for each contributor.

    Returns dict mapping username to their stats.
    """
    stats = defaultdict(lambda: {
        'total_prs': 0,
        'merged': 0,
        'open': 0,
        'closed': 0,
        'ai_prs': 0,
        'merge_times': [],  # List of hours for calculating average
    })

    for pr in prs:
        username = pr.user.login
        stats[username]['total_prs'] += 1

        # Count by state
        if pr.merged_at is not None:
            stats[username]['merged'] += 1
            merge_time = calculate_merge_time_hours(pr)
            stats[username]['merge_times'].append(merge_time)
        elif pr.state == 'open':
            stats[username]['open'] += 1
        else:
            stats[username]['closed'] += 1

        # Count AI PRs
        if is_ai_pr(pr):
            stats[username]['ai_prs'] += 1

    # Calculate derived metrics
    # Calculate weeks in period
    weeks = 1.0
    if start_date and end_date:
        delta = end_date - start_date
        weeks = max(1.0, delta.days / 7)

    result = {}
    for username, user_stats in stats.items():
        total = user_stats['total_prs']
        merged = user_stats['merged']

        result[username] = {
            'username': username,
            'total_prs': total,
            'merged': merged,
            'open': user_stats['open'],
            'closed': user_stats['closed'],
            'merge_rate': (merged / total * 100) if total > 0 else 0.0,
            'avg_merge_time_hours': sum(user_stats['merge_times']) / len(user_stats['merge_times']) if user_stats['merge_times'] else 0.0,
            'ai_prs': user_stats['ai_prs'],
            'prs_per_week': total / weeks,
            'comments_per_pr': None,  # Lazy loaded
        }

    return result
