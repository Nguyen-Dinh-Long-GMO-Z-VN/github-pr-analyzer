# GitHub PR Analyzer

A comprehensive Streamlit application to analyze GitHub Pull Requests for any repository with advanced metrics and visualizations.

<img width="1850" height="5362" alt="image" src="https://github.com/user-attachments/assets/705e5156-aab6-40b3-9ec6-a0653cb6654c" />


## Features

### Core Analytics
- **PR Counts**: Total, Merged, Open, Closed PRs
- **AI Detection**: Automatically identifies AI-generated PRs (branch prefix `claude/` or author containing `devin-ai-integration`)
- **Merge Time Analysis**: Average merge time overall, for AI PRs, and Human PRs
- **Merge Rates**: AI vs Human merge success rates
- **PR Velocity**: PRs created per day
- **AI Contribution %**: Percentage of PRs created by AI

### Visualizations
- **PR Timeline**: Line chart showing PR activity over time
- **Status Distribution**: Bar chart of Merged/Open/Closed PRs
- **AI vs Human**: Comparison chart
- **Top Contributors**: Leaderboards for overall, AI, and Human contributors
- **Label Analysis**: Breakdown by PR labels (bug, feature, etc.)

### Interactive Features
- **Filter Tabs**: View All PRs, AI PRs only, or Human PRs only
- **Export CSV**: Download PR data for any category
- **Dark Mode**: Toggle between light and dark themes
- **Auto Refresh**: Automatically refresh data every 5 minutes

### Analysis Modes
- **Single Month**: Analyze one month in detail
- **Compare Months**: Compare metrics between two different months
- **Multiple Repos**: Analyze multiple repositories at once

### Contributor Analysis
- **Per-User Stats**: Table view showing metrics for each contributor
  - Total PRs, Merged, Open, Closed counts
  - Merge Rate percentage
  - Average Merge Time
  - AI PRs count
  - PRs per Week frequency
  - Comments per PR (lazy loaded)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure GitHub Token

Create a `.env` file with your GitHub Personal Access Token:

```
GITHUB_TOKEN=ghp_your_token_here
```

To create a token:
1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token with `repo` scope (for private repos) or `public_repo` (for public repos only)

### 3. (Optional) Configure AI PR Detection

Edit `.env` to customize AI detection rules:

```bash
# Enable/disable AI detection (default: true)
AI_DETECTION_ENABLED=true

# Branch prefixes that indicate AI PRs (comma-separated)
AI_BRANCH_PREFIXES=claude/,ai/,gpt/,copilot/

# Author patterns that indicate AI PRs (comma-separated)
AI_AUTHOR_PATTERNS=devin-ai-integration,github-copilot,claude-bot
```

**For projects without AI PRs**, set `AI_DETECTION_ENABLED=false` to disable AI analysis.

### 4. Run the App

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

## Usage Guide

### Single Month Analysis

1. Select "Single Month" mode
2. Enter repository URL(s) - one per line for multiple repos
3. Select Month and Year
4. Click "Analyze"

### Compare Two Months

1. Select "Compare Months" mode
2. Enter repository URL(s)
3. Select Month 1 and Month 2 (can be different months or years)
4. Click "Analyze"

### Understanding the Metrics

| Metric | Description |
|--------|-------------|
| **Total PRs** | Total number of PRs created in the selected period |
| **Merged** | PRs that were successfully merged |
| **Open** | PRs still open at the end of the period |
| **Closed** | PRs closed without merging |
| **AI PRs** | PRs identified as AI-generated |
| **AI %** | Percentage of PRs that are AI-generated |
| **Merge Rate** | Percentage of PRs that were merged |
| **Avg Merge Time** | Average time from creation to merge (hours) |
| **PR Velocity** | Average PRs created per day |

### AI PR Detection

AI PRs are identified by configurable rules in `.env`:

| Config | Description | Example |
|--------|-------------|---------|
| `AI_BRANCH_PREFIXES` | Branch name starts with any of these prefixes | `claude/`, `ai/`, `gpt/` |
| `AI_AUTHOR_PATTERNS` | PR author contains any of these substrings | `devin-ai-integration`, `copilot` |

**Default rules:**
- Branch prefix: `claude/`
- Author pattern: `devin-ai-integration`

**To disable AI detection completely**, set `AI_DETECTION_ENABLED=false` in `.env`.

### Exporting Data

Each tab (All PRs, AI PRs, Human PRs) has a download button to export data as CSV for:
- Further analysis in Excel/Google Sheets
- Reporting
- Archival

## Architecture

```
app.py              # Streamlit UI with all visualizations
├── pr_fetcher.py   # GitHub API integration
├── pr_analyzer.py  # Analytics and metrics calculation
├── github_client.py # GitHub client initialization
└── config.py       # Environment configuration
```

## Testing

Run the test suite:

```bash
pytest test_*.py -v
```

## Requirements

- Python 3.9+
- GitHub Personal Access Token
- Dependencies in `requirements.txt`:
  - streamlit >= 1.28.0
  - PyGithub >= 2.1.0
  - python-dotenv >= 1.0.0
  - pandas >= 2.0.0

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "GITHUB_TOKEN not found" | Check `.env` file exists and contains valid token |
| "Repo not found" | Verify repo URL and token permissions |
| "Rate limit exceeded" | Wait an hour or use a different token |
| No PRs found | Check if the month/year has any PR activity |

## Contributing

Feel free to submit issues or PRs to enhance the tool!

## License

MIT License
