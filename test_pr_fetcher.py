# test_pr_fetcher.py
from unittest.mock import MagicMock, patch
from datetime import datetime

def test_parse_repo_url():
    from pr_fetcher import parse_repo_url

    # Test HTTPS URL
    owner, repo = parse_repo_url('https://github.com/owner/repo-name')
    assert owner == 'owner'
    assert repo == 'repo-name'

    # Test SSH URL
    owner, repo = parse_repo_url('git@github.com:owner/repo.git')
    assert owner == 'owner'
    assert repo == 'repo'

def test_is_pr_in_month():
    from pr_fetcher import is_pr_in_month
    from datetime import datetime

    # PR created in target month
    pr = MagicMock()
    pr.created_at = datetime(2024, 3, 15)

    assert is_pr_in_month(pr, 2024, 3) == True
    assert is_pr_in_month(pr, 2024, 4) == False
    assert is_pr_in_month(pr, 2023, 3) == False

def test_fetch_prs_for_month():
    from unittest.mock import MagicMock, patch
    from datetime import datetime

    with patch('pr_fetcher.get_github_client') as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_repo = MagicMock()
        mock_client.get_repo.return_value = mock_repo

        # Mock PRs
        pr1 = MagicMock()
        pr1.created_at = datetime(2024, 3, 10)
        pr1.state = 'open'

        pr2 = MagicMock()
        pr2.created_at = datetime(2024, 2, 10)  # Different month
        pr2.state = 'open'

        mock_repo.get_pulls.return_value = [pr1, pr2]

        from pr_fetcher import fetch_prs_for_month
        result = fetch_prs_for_month('owner/repo', 2024, 3)

        assert len(result) == 1
        assert result[0].created_at.month == 3


def test_is_pr_in_date_range():
    from pr_fetcher import is_pr_in_date_range
    from datetime import datetime

    pr = MagicMock()
    pr.created_at = datetime(2024, 3, 15, 10, 30, 0)

    # PR inside range
    assert is_pr_in_date_range(pr, datetime(2024, 3, 1), datetime(2024, 3, 31)) == True

    # PR at start boundary
    assert is_pr_in_date_range(pr, datetime(2024, 3, 15), datetime(2024, 3, 31)) == True

    # PR at end boundary
    assert is_pr_in_date_range(pr, datetime(2024, 3, 1), datetime(2024, 3, 15)) == True

    # PR before range
    assert is_pr_in_date_range(pr, datetime(2024, 3, 20), datetime(2024, 3, 31)) == False

    # PR after range
    assert is_pr_in_date_range(pr, datetime(2024, 3, 1), datetime(2024, 3, 10)) == False


def test_fetch_prs_for_date_range():
    from unittest.mock import MagicMock, patch
    from datetime import datetime

    with patch('pr_fetcher.get_github_client') as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_repo = MagicMock()
        mock_client.get_repo.return_value = mock_repo

        # Mock PRs
        pr1 = MagicMock()  # Inside range
        pr1.created_at = datetime(2024, 3, 10)
        pr1.state = 'open'

        pr2 = MagicMock()  # Inside range
        pr2.created_at = datetime(2024, 3, 15)
        pr2.state = 'open'

        pr3 = MagicMock()  # Outside range
        pr3.created_at = datetime(2024, 2, 10)
        pr3.state = 'open'

        pr4 = MagicMock()  # Outside range
        pr4.created_at = datetime(2024, 4, 1)
        pr4.state = 'open'

        mock_repo.get_pulls.return_value = [pr1, pr2, pr3, pr4]

        from pr_fetcher import fetch_prs_for_date_range
        result = fetch_prs_for_date_range(
            'owner/repo',
            datetime(2024, 3, 1),
            datetime(2024, 3, 31)
        )

        assert len(result) == 2
        assert result[0].created_at.month == 3
        assert result[1].created_at.month == 3


def test_get_pr_comments_count():
    from pr_fetcher import get_pr_comments_count

    pr = MagicMock()
    pr.get_review_comments.return_value.totalCount = 3
    pr.get_comments.return_value.totalCount = 2

    count = get_pr_comments_count(pr)
    assert count == 5


def test_get_pr_comments_count_error():
    from pr_fetcher import get_pr_comments_count

    pr = MagicMock()
    pr.get_review_comments.side_effect = Exception("API error")

    count = get_pr_comments_count(pr)
    assert count == 0
