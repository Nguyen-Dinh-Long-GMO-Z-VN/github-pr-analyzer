# test_config.py
import os
from unittest.mock import patch, mock_open


def test_load_github_token():
    with patch('builtins.open', mock_open(read_data='GITHUB_TOKEN=ghp_test123\n')):
        with patch.dict(os.environ, {}, clear=True):
            from config import GITHUB_TOKEN
            assert GITHUB_TOKEN == 'ghp_test123'


def test_load_github_token_missing():
    with patch('builtins.open', mock_open(read_data='OTHER_VAR=value\n')):
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config
            importlib.reload(config)
            assert config.GITHUB_TOKEN is None or config.GITHUB_TOKEN == ''


def test_ai_detection_enabled_default():
    """AI detection should be enabled by default."""
    with patch.dict(os.environ, {'AI_DETECTION_ENABLED': ''}, clear=True):
        with patch('builtins.open', mock_open(read_data='')):
            import importlib
            import config
            importlib.reload(config)
            assert config.AI_DETECTION_ENABLED == True


def test_ai_detection_disabled():
    """AI detection can be disabled via env var."""
    with patch.dict(os.environ, {'AI_DETECTION_ENABLED': 'false'}, clear=True):
        with patch('builtins.open', mock_open(read_data='')):
            import importlib
            import config
            importlib.reload(config)
            assert config.AI_DETECTION_ENABLED == False


def test_ai_branch_prefixes_default():
    """Default branch prefixes should include 'claude/'."""
    with patch.dict(os.environ, {'AI_BRANCH_PREFIXES': ''}, clear=True):
        with patch('builtins.open', mock_open(read_data='')):
            import importlib
            import config
            importlib.reload(config)
            assert 'claude/' in config.AI_BRANCH_PREFIXES


def test_ai_branch_prefixes_custom():
    """Custom branch prefixes should be parsed correctly."""
    with patch.dict(os.environ, {'AI_BRANCH_PREFIXES': 'gpt/,copilot/,ai-'}, clear=True):
        with patch('builtins.open', mock_open(read_data='')):
            import importlib
            import config
            importlib.reload(config)
            assert config.AI_BRANCH_PREFIXES == ['gpt/', 'copilot/', 'ai-']


def test_ai_author_patterns_default():
    """Default author patterns should include 'devin-ai-integration'."""
    with patch.dict(os.environ, {'AI_AUTHOR_PATTERNS': ''}, clear=True):
        with patch('builtins.open', mock_open(read_data='')):
            import importlib
            import config
            importlib.reload(config)
            assert 'devin-ai-integration' in config.AI_AUTHOR_PATTERNS


def test_ai_author_patterns_custom():
    """Custom author patterns should be parsed correctly."""
    with patch.dict(os.environ, {'AI_AUTHOR_PATTERNS': 'github-copilot,claude-bot,bot-ai'}, clear=True):
        with patch('builtins.open', mock_open(read_data='')):
            import importlib
            import config
            importlib.reload(config)
            assert config.AI_AUTHOR_PATTERNS == ['github-copilot', 'claude-bot', 'bot-ai']
