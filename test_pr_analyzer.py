# test_pr_analyzer.py
from unittest.mock import MagicMock, patch
from datetime import datetime


def test_is_ai_pr_by_branch():
    # Mock config values
    with patch('pr_analyzer.AI_DETECTION_ENABLED', True):
        with patch('pr_analyzer.AI_BRANCH_PREFIXES', ['claude/', 'ai/', 'gpt/']):
            with patch('pr_analyzer.AI_AUTHOR_PATTERNS', ['devin-ai-integration']):
                from pr_analyzer import is_ai_pr

                pr = MagicMock()
                pr.head.ref = 'claude/feature-123'
                pr.user.login = 'human-user'

                assert is_ai_pr(pr) == True


def test_is_ai_pr_by_author():
    with patch('pr_analyzer.AI_DETECTION_ENABLED', True):
        with patch('pr_analyzer.AI_BRANCH_PREFIXES', ['claude/']):
            with patch('pr_analyzer.AI_AUTHOR_PATTERNS', ['devin-ai-integration']):
                from pr_analyzer import is_ai_pr

                pr = MagicMock()
                pr.head.ref = 'feature/abc'
                pr.user.login = 'devin-ai-integration'

                assert is_ai_pr(pr) == True


def test_is_ai_pr_by_author_with_suffix():
    with patch('pr_analyzer.AI_DETECTION_ENABLED', True):
        with patch('pr_analyzer.AI_BRANCH_PREFIXES', ['claude/']):
            with patch('pr_analyzer.AI_AUTHOR_PATTERNS', ['devin-ai-integration']):
                from pr_analyzer import is_ai_pr

                pr = MagicMock()
                pr.head.ref = 'feature/abc'
                pr.user.login = 'devin-ai-integration[bot]'

                assert is_ai_pr(pr) == True


def test_is_ai_pr_not_ai():
    with patch('pr_analyzer.AI_DETECTION_ENABLED', True):
        with patch('pr_analyzer.AI_BRANCH_PREFIXES', ['claude/']):
            with patch('pr_analyzer.AI_AUTHOR_PATTERNS', ['devin-ai-integration']):
                from pr_analyzer import is_ai_pr

                pr = MagicMock()
                pr.head.ref = 'feature/abc'
                pr.user.login = 'human-user'

                assert is_ai_pr(pr) == False


def test_is_ai_pr_disabled():
    """When AI detection is disabled, all PRs should be human."""
    with patch('pr_analyzer.AI_DETECTION_ENABLED', False):
        with patch('pr_analyzer.AI_BRANCH_PREFIXES', ['claude/']):
            with patch('pr_analyzer.AI_AUTHOR_PATTERNS', ['devin-ai-integration']):
                from pr_analyzer import is_ai_pr

                pr = MagicMock()
                pr.head.ref = 'claude/feature-123'
                pr.user.login = 'devin-ai-integration'

                assert is_ai_pr(pr) == False


def test_is_ai_pr_custom_prefix():
    """Test with custom branch prefixes."""
    with patch('pr_analyzer.AI_DETECTION_ENABLED', True):
        with patch('pr_analyzer.AI_BRANCH_PREFIXES', ['gpt/', 'copilot/']):
            with patch('pr_analyzer.AI_AUTHOR_PATTERNS', []):
                from pr_analyzer import is_ai_pr

                pr = MagicMock()
                pr.head.ref = 'gpt/feature-123'
                pr.user.login = 'human'

                assert is_ai_pr(pr) == True


def test_calculate_merge_time_hours():
    from pr_analyzer import calculate_merge_time_hours

    pr = MagicMock()
    pr.created_at = datetime(2024, 3, 1, 10, 0, 0)
    pr.merged_at = datetime(2024, 3, 1, 12, 30, 0)

    hours = calculate_merge_time_hours(pr)
    assert hours == 2.5


def test_calculate_merge_time_hours_not_merged():
    from pr_analyzer import calculate_merge_time_hours

    pr = MagicMock()
    pr.merged_at = None

    hours = calculate_merge_time_hours(pr)
    assert hours == 0


def test_analyze_prs():
    with patch('pr_analyzer.AI_DETECTION_ENABLED', True):
        with patch('pr_analyzer.AI_BRANCH_PREFIXES', ['claude/']):
            with patch('pr_analyzer.AI_AUTHOR_PATTERNS', ['devin-ai-integration']):
                from pr_analyzer import analyze_prs

                # Create mock PRs
                pr1 = MagicMock()  # Merged AI PR
                pr1.created_at = datetime(2024, 3, 1)
                pr1.merged_at = datetime(2024, 3, 2)
                pr1.state = 'closed'
                pr1.head.ref = 'claude/feature-1'
                pr1.user.login = 'human'
                pr1.labels = []

                pr2 = MagicMock()  # Open human PR
                pr2.created_at = datetime(2024, 3, 2)
                pr2.merged_at = None
                pr2.state = 'open'
                pr2.head.ref = 'feature/xyz'
                pr2.user.login = 'developer'
                pr2.labels = []

                pr3 = MagicMock()  # Closed (not merged) human PR
                pr3.created_at = datetime(2024, 3, 3)
                pr3.merged_at = None
                pr3.state = 'closed'
                pr3.head.ref = 'bugfix/abc'
                pr3.user.login = 'developer'
                pr3.labels = []

                result = analyze_prs([pr1, pr2, pr3])

                assert result['total'] == 3
                assert result['merged'] == 1
                assert result['open'] == 1
                assert result['closed'] == 1
                assert result['ai_prs'] == 1
                assert result['human_prs'] == 2
                assert result['ai_merge_rate'] == 100.0
                assert result['human_merge_rate'] == 0.0


def test_analyze_prs_with_labels():
    with patch('pr_analyzer.AI_DETECTION_ENABLED', True):
        with patch('pr_analyzer.AI_BRANCH_PREFIXES', ['claude/']):
            with patch('pr_analyzer.AI_AUTHOR_PATTERNS', ['devin-ai-integration']):
                from pr_analyzer import analyze_prs

                pr1 = MagicMock()
                pr1.created_at = datetime(2024, 3, 1)
                pr1.merged_at = None
                pr1.state = 'open'
                pr1.head.ref = 'feature/abc'
                pr1.user.login = 'user1'

                label1 = MagicMock()
                label1.name = 'bug'
                label2 = MagicMock()
                label2.name = 'enhancement'
                pr1.labels = [label1, label2]

                result = analyze_prs([pr1])

                assert result['top_labels'] == [('bug', 1), ('enhancement', 1)]


def test_analyze_prs_ai_disabled():
    """When AI detection is disabled, all PRs are human."""
    with patch('pr_analyzer.AI_DETECTION_ENABLED', False):
        with patch('pr_analyzer.AI_BRANCH_PREFIXES', ['claude/']):
            with patch('pr_analyzer.AI_AUTHOR_PATTERNS', ['devin-ai-integration']):
                from pr_analyzer import analyze_prs

                pr1 = MagicMock()
                pr1.created_at = datetime(2024, 3, 1)
                pr1.merged_at = None
                pr1.state = 'open'
                pr1.head.ref = 'claude/ai-feature'  # Would be AI if enabled
                pr1.user.login = 'devin-ai-integration'
                pr1.labels = []

                result = analyze_prs([pr1])

                assert result['ai_prs'] == 0
                assert result['human_prs'] == 1
                assert result['ai_contribution_pct'] == 0.0
