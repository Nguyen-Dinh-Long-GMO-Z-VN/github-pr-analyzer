# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_oauth import OAuth2Component
from github import Github
from pr_fetcher import fetch_prs_for_month, fetch_prs_for_date_range, parse_repo_url, fetch_comments_for_prs
from pr_analyzer import analyze_prs, analyze_comparison, is_ai_pr, analyze_contributors
from pdf_generator import generate_pdf_report
from config import GITHUB_TOKEN, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, REDIRECT_URI

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"


def show_login_page():
    """Show GitHub OAuth login page."""
    st.markdown("""
    <style>
        .login-wrapper {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 80vh;
            padding: 2rem;
        }
        .login-card {
            background: linear-gradient(135deg, #1E293B 0%, #0F1729 100%);
            border: 1px solid #334155;
            border-radius: 24px;
            padding: 3rem 2.5rem;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05);
        }
        .login-logo {
            width: 64px;
            height: 64px;
            margin: 0 auto 1.5rem;
            background: linear-gradient(135deg, #22C55E 0%, #16A34A 100%);
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 8px 24px rgba(34,197,94,0.3);
        }
        .login-title {
            color: #F8FAFC;
            font-size: 1.75rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            letter-spacing: -0.02em;
        }
        .login-subtitle {
            color: #94A3B8;
            font-size: 0.95rem;
            margin-bottom: 2rem;
            line-height: 1.6;
        }
        .login-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent, #334155, transparent);
            margin: 1.5rem 0;
        }
        .login-footer {
            color: #475569;
            font-size: 0.8rem;
            margin-top: 1.5rem;
        }
        /* Style the OAuth button */
        .stButton > button {
            background: #24292E !important;
            color: #F8FAFC !important;
            border: 1px solid #444D56 !important;
            border-radius: 10px !important;
            padding: 0.75rem 1.5rem !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            width: 100% !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button:hover {
            background: #2F363D !important;
            border-color: #586069 !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
            transform: translateY(-1px) !important;
        }
    </style>
    <div class="login-wrapper">
        <div class="login-card">
            <div class="login-logo">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="white">
                    <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
                </svg>
            </div>
            <div class="login-title">GitHub PR Analyzer</div>
            <div class="login-subtitle">
                Analyze pull requests, track contributors,<br>and measure your team's velocity.
            </div>
            <div class="login-divider"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1.5, 2])
    with col2:
        oauth2 = OAuth2Component(
            GITHUB_CLIENT_ID,
            GITHUB_CLIENT_SECRET,
            GITHUB_AUTHORIZE_URL,
            GITHUB_TOKEN_URL,
        )
        result = oauth2.authorize_button(
            "Continue with GitHub",
            redirect_uri=REDIRECT_URI,
            scope="repo",
            key="github_oauth",
        )
        if result and "token" in result:
            st.session_state.github_token = result["token"]["access_token"]
            st.rerun()

    st.markdown("""
    <div style="text-align:center; color:#475569; font-size:0.78rem; margin-top:0.5rem;">
        Your token is stored in session only — never saved to disk.
    </div>
    """, unsafe_allow_html=True)


def get_pr_data_for_df(prs):
    """Convert PRs to list of dictionaries for DataFrame."""
    pr_data = []
    for pr in prs:
        merge_time = ""
        if pr.merged_at and pr.created_at:
            delta = pr.merged_at - pr.created_at
            hours = delta.total_seconds() / 3600
            merge_time = f"{hours:.1f}h"

        pr_data.append({
            'Number': f"#{pr.number}",
            'Title': pr.title,
            'Author': pr.user.login,
            'Branch': pr.head.ref,
            'State': 'Merged' if pr.merged_at else pr.state.capitalize(),
            'AI': '✅' if is_ai_pr(pr) else '❌',
            'Created': pr.created_at.strftime('%Y-%m-%d'),
            'Merge Time': merge_time,
            'Labels': ', '.join([l.name for l in pr.labels]),
            'URL': pr.html_url
        })
    return pr_data


def display_metrics_cards(metrics):
    """Display metric cards in a styled grid with visual hierarchy."""

    # Section header
    st.markdown('<p style="color:#64748B; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin: 1.5rem 0 0.75rem 0;">Overview</p>', unsafe_allow_html=True)

    # Row 1: Primary metrics - Total, Merged, Open, Closed
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="📊 Total PRs",
            value=f"{metrics['total']:,}",
            help="Total number of pull requests"
        )
    with col2:
        merged_delta = metrics['merged'] - metrics['closed'] if metrics['closed'] > 0 else None
        st.metric(
            label="✅ Merged",
            value=f"{metrics['merged']:,}",
            delta=f"{metrics['merged'] / metrics['total'] * 100:.0f}%" if metrics['total'] > 0 else None,
            delta_color="normal",
            help="Successfully merged PRs"
        )
    with col3:
        st.metric(
            label="🔓 Open",
            value=f"{metrics['open']:,}",
            help="Currently open PRs"
        )
    with col4:
        st.metric(
            label="❌ Closed",
            value=f"{metrics['closed']:,}",
            help="Closed without merging"
        )

    # Row 2: AI Contribution
    st.markdown('<p style="color:#64748B; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin: 1.5rem 0 0.75rem 0;">AI Contribution</p>', unsafe_allow_html=True)

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric(
            label="🤖 AI PRs",
            value=f"{metrics['ai_prs']:,}",
            delta=f"{metrics['ai_contribution_pct']:.1f}% of total" if metrics['total'] > 0 else None,
            help="PRs created by AI"
        )
    with col6:
        st.metric(
            label="👤 Human PRs",
            value=f"{metrics['human_prs']:,}",
            delta=f"{100 - metrics['ai_contribution_pct']:.1f}% of total" if metrics['total'] > 0 else None,
            help="PRs created by humans"
        )
    with col7:
        ai_rate = metrics['ai_merge_rate']
        human_rate = metrics['human_merge_rate']
        diff = ai_rate - human_rate
        st.metric(
            label="🎯 AI Merge Rate",
            value=f"{ai_rate:.1f}%",
            delta=f"{diff:+.1f}% vs human" if diff != 0 else None,
            delta_color="normal" if diff >= 0 else "inverse",
            help="Percentage of AI PRs that were merged"
        )
    with col8:
        velocity = metrics['pr_velocity']
        st.metric(
            label="⚡ PR Velocity",
            value=f"{velocity:.1f}/day",
            delta="PRs per day" if velocity > 0 else None,
            help="Average PRs created per day"
        )

    # Row 3: Merge Time Stats
    st.markdown('<p style="color:#64748B; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin: 1.5rem 0 0.75rem 0;">Merge Time Analysis</p>', unsafe_allow_html=True)

    col9, col10, col11 = st.columns(3)
    avg_time = metrics['avg_merge_time_hours']
    ai_time = metrics['ai_avg_merge_time_hours']
    human_time = metrics['human_avg_merge_time_hours']

    with col9:
        display_time = f"{avg_time:.1f}h" if avg_time > 0 else "N/A"
        st.metric(
            label="⏱️ Overall Avg",
            value=display_time,
            help="Average time from creation to merge (all PRs)"
        )
    with col10:
        ai_display = f"{ai_time:.1f}h" if ai_time > 0 else "N/A"
        ai_diff = ai_time - avg_time if ai_time > 0 and avg_time > 0 else 0
        st.metric(
            label="🤖 AI Avg",
            value=ai_display,
            delta=f"{ai_diff:+.1f}h vs overall" if ai_diff != 0 else None,
            delta_color="inverse" if ai_diff > 0 else "normal",
            help="Average merge time for AI PRs"
        )
    with col11:
        human_display = f"{human_time:.1f}h" if human_time > 0 else "N/A"
        human_diff = human_time - avg_time if human_time > 0 and avg_time > 0 else 0
        st.metric(
            label="👤 Human Avg",
            value=human_display,
            delta=f"{human_diff:+.1f}h vs overall" if human_diff != 0 else None,
            delta_color="inverse" if human_diff > 0 else "normal",
            help="Average merge time for human PRs"
        )


def display_timeline_chart(prs_by_date):
    """Display PR timeline chart."""
    if not prs_by_date:
        st.info("No timeline data available")
        return

    # Convert to DataFrame
    dates = sorted(prs_by_date.keys())
    counts = [prs_by_date[d] for d in dates]

    timeline_df = pd.DataFrame({
        'Date': dates,
        'PRs': counts
    })

    st.line_chart(timeline_df.set_index('Date'))


def display_all_contributors(contributors, title="All Contributors", key_prefix="contrib"):
    """Display all contributors in a scrollable table with bar chart."""
    if not contributors:
        st.info(f"No {title.lower()} data")
        return

    total_prs = sum(count for _, count in contributors)

    # Create DataFrame with all contributors
    contributors_data = []
    for rank, (author, count) in enumerate(contributors, 1):
        percentage = (count / total_prs * 100) if total_prs > 0 else 0
        contributors_data.append({
            'Rank': rank,
            'Contributor': author,
            'PRs': count,
            'Percentage': f"{percentage:.1f}%"
        })

    df = pd.DataFrame(contributors_data)

    # Show bar chart for top 10
    if len(contributors) > 0:
        top_10 = contributors[:10]
        chart_df = pd.DataFrame(top_10, columns=['Contributor', 'PRs'])
        st.bar_chart(chart_df.set_index('Contributor'))

    # Show all contributors in expandable section
    with st.expander(f"📋 View All {len(contributors)} Contributors", expanded=False):
        st.dataframe(df, use_container_width=True, hide_index=True)


def display_label_analysis(top_labels):
    """Display label analysis pie chart data."""
    if not top_labels:
        st.info("No labels found")
        return

    labels_df = pd.DataFrame(
        top_labels,
        columns=['Label', 'Count']
    )

    st.bar_chart(labels_df.set_index('Label'))


def get_contributors_data_for_df(contributors_stats):
    """Convert contributor stats to list of dictionaries for DataFrame."""
    data = []
    for username, stats in contributors_stats.items():
        avg_time = stats['avg_merge_time_hours']

        data.append({
            'Username': username,
            'Total PRs': stats['total_prs'],
            'Merged': stats['merged'],
            'Open': stats['open'],
            'Closed': stats['closed'],
            'Merge Rate %': f"{stats['merge_rate']:.1f}",
            'Avg Merge Time': f"{avg_time:.1f}h" if avg_time > 0 else "N/A",
            'AI PRs': stats['ai_prs'],
            'PRs/Week': f"{stats['prs_per_week']:.2f}",
        })
    return data


def display_contributor_statistics(prs, contributors_stats=None, start_date=None, end_date=None):
    """Display contributor statistics table with enhanced styling."""
    if not prs:
        st.info("No PRs found for contributor analysis")
        return

    st.markdown("""
        <h3 style="color: #22C55E; margin: 2rem 0 1rem 0; font-weight: 700;">
            👥 Contributor Statistics
        </h3>
    """, unsafe_allow_html=True)

    # Calculate contributor stats if not provided
    if contributors_stats is None:
        contributors_stats = analyze_contributors(prs, start_date, end_date)

    if not contributors_stats:
        st.info("No contributor data available")
        return

    # Sort by Total PRs descending
    contributors_stats = dict(sorted(
        contributors_stats.items(),
        key=lambda x: x[1]['total_prs'],
        reverse=True
    ))

    # Create DataFrame
    data = get_contributors_data_for_df(contributors_stats)
    df = pd.DataFrame(data)

    # Column configuration for better display
    column_config = {
        "Username": st.column_config.TextColumn(
            "Username",
            help="Contributor's GitHub username",
            width="medium"
        ),
        "Total PRs": st.column_config.NumberColumn(
            "Total PRs",
            help="Total pull requests submitted",
            format="%d",
            width="small"
        ),
        "Merged": st.column_config.NumberColumn(
            "Merged",
            help="Successfully merged PRs",
            format="%d",
            width="small"
        ),
        "Open": st.column_config.NumberColumn(
            "Open",
            help="Currently open PRs",
            format="%d",
            width="small"
        ),
        "Closed": st.column_config.NumberColumn(
            "Closed",
            help="Closed without merging",
            format="%d",
            width="small"
        ),
        "Merge Rate %": st.column_config.NumberColumn(
            "Merge Rate",
            help="Percentage of PRs that were merged",
            format="%.1f%%",
            width="small"
        ),
        "Avg Merge Time": st.column_config.TextColumn(
            "Avg Merge Time",
            help="Average time from creation to merge",
            width="medium"
        ),
        "AI PRs": st.column_config.NumberColumn(
            "AI PRs",
            help="Number of AI-generated PRs",
            format="%d",
            width="small"
        ),
        "PRs/Week": st.column_config.NumberColumn(
            "PRs/Week",
            help="Average PRs per week",
            format="%.2f",
            width="small"
        ),
    }

    # Display table with styling
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config
    )

    # Summary stats
    total_contributors = len(df)
    total_ai_prs = df['AI PRs'].astype(int).sum()
    avg_merge_rate = df['Merge Rate %'].astype(float).mean()

    cols = st.columns(3)
    with cols[0]:
        st.metric("Total Contributors", total_contributors)
    with cols[1]:
        st.metric("Total AI PRs", total_ai_prs)
    with cols[2]:
        st.metric("Avg Merge Rate", f"{avg_merge_rate:.1f}%")


def display_analysis_results(metrics, period_name, repo_names=None, aggregate_mode=False, skip_pdf=False):
    """Display analysis results for a given time period with enhanced styling."""

    # Generate and store PDF in session state (skip on re-renders caused by search/filter)
    if repo_names and not skip_pdf:
        try:
            pdf_buffer = generate_pdf_report(
                metrics,
                period_name,
                repo_names,
                aggregate_mode,
                metrics.get('contributors')
            )
            st.session_state.last_pdf_buffer = pdf_buffer
            st.session_state.last_pdf_filename = f"pr-analysis-{period_name.replace(' ', '-').lower()}-{datetime.now().strftime('%Y%m%d')}.pdf"
        except Exception as e:
            st.error(f"Error generating PDF: {e}")

    # Period info banner
    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #1E293B 0%, #0F1729 100%);
            border: 1px solid #22C55E40;
            border-left: 3px solid #22C55E;
            color: #E2E8F0;
            padding: 0.875rem 1.25rem;
            border-radius: 10px;
            margin-bottom: 1.5rem;
            font-weight: 500;
            font-size: 0.95rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        ">
            <span style="color:#22C55E;">&#9679;</span> Analysis Period: <strong style="color:#F8FAFC;">{period_name}</strong>
        </div>
    """, unsafe_allow_html=True)

    # Export PDF button (in a row with other actions if needed)
    if st.session_state.get('last_pdf_buffer'):
        col_actions, _ = st.columns([1, 5])
        with col_actions:
            st.download_button(
                label="📄 Export PDF",
                data=st.session_state.last_pdf_buffer,
                file_name=st.session_state.get('last_pdf_filename', 'pr-analysis.pdf'),
                mime="application/pdf",
                type="primary"
            )
        st.markdown("<br>", unsafe_allow_html=True)

    # Display metrics
    display_metrics_cards(metrics)

    st.divider()

    # Charts section
    st.markdown("""
        <h3 style="color: #22C55E; margin: 2rem 0 1rem 0; font-weight: 700;">
            📈 Visualizations
        </h3>
    """, unsafe_allow_html=True)

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("""
            <h4 style="color: #475569; margin-bottom: 0.5rem; font-weight: 600;">
                PR Status Distribution
            </h4>
        """, unsafe_allow_html=True)
        status_data = pd.DataFrame({
            'Status': ['Merged', 'Open', 'Closed'],
            'Count': [metrics['merged'], metrics['open'], metrics['closed']]
        })
        st.bar_chart(status_data.set_index('Status'))

    with col_chart2:
        st.markdown("""
            <h4 style="color: #475569; margin-bottom: 0.5rem; font-weight: 600;">
                AI vs Human PRs
            </h4>
        """, unsafe_allow_html=True)
        ai_data = pd.DataFrame({
            'Type': ['AI PRs', 'Human PRs'],
            'Count': [metrics['ai_prs'], metrics['human_prs']]
        })
        st.bar_chart(ai_data.set_index('Type'))

    # Timeline
    st.markdown("""
        <h4 style="color: #475569; margin: 1.5rem 0 0.5rem 0; font-weight: 600;">
            PR Timeline
        </h4>
    """, unsafe_allow_html=True)
    display_timeline_chart(metrics['prs_by_date'])

    # Contributors section
    st.markdown("""
        <h3 style="color: #22C55E; margin: 2rem 0 1rem 0; font-weight: 700;">
            👥 Contributors
        </h3>
    """, unsafe_allow_html=True)

    tab_overall, tab_ai, tab_human = st.tabs(["📊 Overall", "🤖 AI", "👤 Human"])

    with tab_overall:
        display_all_contributors(metrics['top_contributors'], "All Contributors", "overall")

    with tab_ai:
        display_all_contributors(metrics['top_ai_contributors'], "AI Contributors", "ai")

    with tab_human:
        display_all_contributors(metrics['top_human_contributors'], "Human Contributors", "human")

    # Label analysis
    if metrics['top_labels']:
        st.markdown("""
            <h3 style="color: #22C55E; margin: 2rem 0 1rem 0; font-weight: 700;">
                🏷️ Label Analysis
            </h3>
        """, unsafe_allow_html=True)
        display_label_analysis(metrics['top_labels'])

    st.divider()

    # PR Details with tabs
    st.markdown("""
        <h3 style="color: #22C55E; margin: 2rem 0 1rem 0; font-weight: 700;">
            📝 Pull Request Details
        </h3>
    """, unsafe_allow_html=True)
    display_pr_tabs(metrics)

    # Contributor Statistics
    display_contributor_statistics(metrics['all_prs'], metrics.get('contributors'))


def display_pr_tabs(metrics):
    """Display PRs in tabs (All / AI / Human) with search and status filter."""
    col_search, col_filter = st.columns([3, 1])
    with col_search:
        search = st.text_input(
            "Search",
            placeholder="🔍 Search by author or title...",
            label_visibility="collapsed",
            key="pr_search"
        )
    with col_filter:
        status_filter = st.multiselect(
            "Status",
            options=["Open", "Merged", "Closed"],
            placeholder="Filter by status",
            label_visibility="collapsed",
            key="pr_status_filter"
        )

    def apply_filters(pr_data):
        df = pd.DataFrame(pr_data)
        if search:
            mask = (
                df['Author'].str.contains(search, case=False, na=False) |
                df['Title'].str.contains(search, case=False, na=False)
            )
            df = df[mask]
        if status_filter:
            df = df[df['State'].isin(status_filter)]
        return df

    tab1, tab2, tab3 = st.tabs(["📋 All PRs", "🤖 AI PRs", "👤 Human PRs"])

    with tab1:
        if metrics['all_prs']:
            df = apply_filters(get_pr_data_for_df(metrics['all_prs']))
            if df.empty:
                st.info("No PRs match the search/filter criteria")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No PRs found")

    with tab2:
        if metrics['ai_pr_list']:
            df = apply_filters(get_pr_data_for_df(metrics['ai_pr_list']))
            if df.empty:
                st.info("No AI PRs match the search/filter criteria")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No AI PRs found")

    with tab3:
        if metrics['human_pr_list']:
            df = apply_filters(get_pr_data_for_df(metrics['human_pr_list']))
            if df.empty:
                st.info("No Human PRs match the search/filter criteria")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No Human PRs found")


def display_comparison(comparison_data):
    """Display comparison between two months."""
    month1 = comparison_data['month1']
    month2 = comparison_data['month2']
    comp = comparison_data['comparison']

    st.subheader(f"📊 Comparison: {month1['name']} vs {month2['name']}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Total PRs",
            month2['metrics']['total'],
            delta=comp['total_diff']
        )
    with col2:
        st.metric(
            "Merged",
            month2['metrics']['merged'],
            delta=comp['merged_diff']
        )
    with col3:
        st.metric(
            "AI PRs",
            f"{month2['metrics']['ai_prs']} ({month2['metrics']['ai_contribution_pct']:.1f}%)",
            delta=f"{comp['ai_prs_diff']} ({comp['ai_contribution_diff']:+.1f}%)"
        )
    with col4:
        st.metric(
            "PR Velocity",
            f"{month2['metrics']['pr_velocity']:.1f}/day",
            delta=f"{comp['velocity_diff']:+.1f}"
        )


def main():
    # Initialize session state for theme
    if 'dark_mode' not in st.session_state:
        st.session_state.dark_mode = False
    if 'render_blocks' not in st.session_state:
        st.session_state.render_blocks = []

    # Page config
    st.set_page_config(
        page_title="GitHub PR Analyzer",
        page_icon="🔧",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS — dark theme design system
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');

        /* === GLOBAL === */
        html, body, [class*="css"] {
            font-family: 'Fira Sans', sans-serif;
        }
        code, pre, .stCodeBlock {
            font-family: 'Fira Code', monospace !important;
        }
        .main .block-container {
            padding: 1.5rem 2.5rem 3rem;
            max-width: 1400px;
        }

        /* === TYPOGRAPHY === */
        h1 {
            color: #F8FAFC !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em;
            font-size: 1.75rem !important;
        }
        h2, h3 {
            color: #E2E8F0 !important;
            font-weight: 600 !important;
            margin-top: 1.5rem !important;
        }

        /* === SIDEBAR === */
        section[data-testid="stSidebar"] {
            background: #0B1120 !important;
            border-right: 1px solid #1E293B !important;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 1.5rem;
        }

        /* === METRIC CARDS === */
        [data-testid="stMetric"] {
            background: linear-gradient(145deg, #1E293B 0%, #131D2E 100%) !important;
            border: 1px solid #334155 !important;
            border-radius: 16px !important;
            padding: 1.25rem !important;
            box-shadow: 0 4px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.04) !important;
            transition: all 0.2s ease !important;
            height: 140px !important;
            min-height: 140px !important;
            cursor: default;
        }
        [data-testid="stMetric"]:hover {
            border-color: #22C55E !important;
            box-shadow: 0 8px 32px rgba(34,197,94,0.12), inset 0 1px 0 rgba(255,255,255,0.04) !important;
            transform: translateY(-2px) !important;
        }
        [data-testid="stMetricLabel"] > div {
            color: #94A3B8 !important;
            font-size: 0.8rem !important;
            font-weight: 500 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.06em !important;
        }
        [data-testid="stMetricValue"] > div {
            color: #F8FAFC !important;
            font-size: 1.9rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
        }
        [data-testid="stMetricDelta"] {
            font-weight: 600 !important;
            font-size: 0.8rem !important;
        }
        [data-testid="column"] {
            display: flex;
            flex-direction: column;
        }
        [data-testid="column"] > div { flex: 1; }

        /* === PRIMARY BUTTON (Analyze) === */
        .stButton > button[kind="primary"],
        button[kind="primary"] {
            background: linear-gradient(135deg, #22C55E 0%, #16A34A 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 0.75rem 1.5rem !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 4px 15px rgba(34,197,94,0.25) !important;
            cursor: pointer !important;
        }
        .stButton > button[kind="primary"]:hover,
        button[kind="primary"]:hover {
            background: linear-gradient(135deg, #16A34A 0%, #15803D 100%) !important;
            box-shadow: 0 6px 20px rgba(34,197,94,0.4) !important;
            transform: translateY(-1px) !important;
        }
        .stButton > button[kind="primary"]:active {
            transform: translateY(0) !important;
        }

        /* === SECONDARY BUTTON (Logout) === */
        .stButton > button[kind="secondary"] {
            background: transparent !important;
            color: #94A3B8 !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
            cursor: pointer !important;
        }
        .stButton > button[kind="secondary"]:hover {
            background: #1E293B !important;
            color: #F8FAFC !important;
            border-color: #475569 !important;
        }

        /* === DOWNLOAD BUTTON === */
        .stDownloadButton > button {
            background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 15px rgba(59,130,246,0.25) !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
        }
        .stDownloadButton > button:hover {
            box-shadow: 0 6px 20px rgba(59,130,246,0.4) !important;
            transform: translateY(-1px) !important;
        }

        /* === TABS === */
        .stTabs [data-baseweb="tab-list"] {
            background: #1E293B !important;
            border-radius: 12px !important;
            padding: 4px !important;
            gap: 2px !important;
            border: 1px solid #334155 !important;
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent !important;
            color: #94A3B8 !important;
            border-radius: 8px !important;
            padding: 0.5rem 1.25rem !important;
            font-weight: 500 !important;
            font-size: 0.9rem !important;
            transition: all 0.15s ease !important;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background: #263147 !important;
            color: #CBD5E1 !important;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #22C55E 0%, #16A34A 100%) !important;
            color: white !important;
            box-shadow: 0 2px 8px rgba(34,197,94,0.35) !important;
            font-weight: 600 !important;
        }

        /* === DATAFRAME === */
        .stDataFrame {
            border: 1px solid #334155 !important;
            border-radius: 12px !important;
            overflow: hidden !important;
        }
        .stDataFrame thead tr th {
            background: #1E293B !important;
            color: #94A3B8 !important;
            font-size: 0.8rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            padding: 0.75rem 1rem !important;
        }

        /* === EXPANDER === */
        .streamlit-expanderHeader {
            background: #1E293B !important;
            border: 1px solid #334155 !important;
            border-radius: 10px !important;
            color: #CBD5E1 !important;
            font-weight: 600 !important;
        }
        .streamlit-expanderContent {
            border: 1px solid #334155 !important;
            border-top: none !important;
        }

        /* === INPUT / SELECT === */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            background: #1E293B !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            color: #F8FAFC !important;
            transition: border-color 0.15s ease !important;
        }
        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: #22C55E !important;
            box-shadow: 0 0 0 3px rgba(34,197,94,0.15) !important;
        }
        .stTextInput > div > div > input::placeholder {
            color: #475569 !important;
        }

        /* === ALERTS === */
        .stAlert {
            border-radius: 10px !important;
            border: 1px solid #334155 !important;
        }

        /* === DIVIDER === */
        hr {
            margin: 2rem 0 !important;
            border-color: #1E293B !important;
        }

        /* === CAPTION === */
        .stCaption {
            color: #64748B !important;
            font-size: 0.85rem !important;
        }

        /* === RADIO === */
        .stRadio > div {
            gap: 0.5rem !important;
        }

        /* === MULTISELECT === */
        [data-baseweb="tag"] {
            background: #22C55E20 !important;
            border: 1px solid #22C55E50 !important;
            border-radius: 6px !important;
            color: #22C55E !important;
        }
    </style>
    """, unsafe_allow_html=True)


    # === AUTH CHECK ===
    if GITHUB_CLIENT_ID:
        # OAuth mode: require login
        if "github_token" not in st.session_state:
            show_login_page()
            st.stop()
        github_token = st.session_state.github_token
    elif GITHUB_TOKEN:
        # Fallback: use static token from .env
        github_token = GITHUB_TOKEN
    else:
        st.error("⚠️ No auth configured. Set GITHUB_CLIENT_ID (OAuth) or GITHUB_TOKEN in your .env file.")
        st.stop()

    # Header
    st.markdown("""
        <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.25rem;">
            <div style="
                width:36px; height:36px; border-radius:10px;
                background:linear-gradient(135deg,#22C55E,#16A34A);
                display:flex; align-items:center; justify-content:center;
                box-shadow:0 4px 12px rgba(34,197,94,0.3); flex-shrink:0;
            ">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
                    <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
                </svg>
            </div>
            <h1 style="margin:0; color:#F8FAFC; font-size:1.5rem; font-weight:700; letter-spacing:-0.02em;">GitHub PR Analyzer</h1>
        </div>
        <p style="color:#64748B; font-size:0.875rem; margin:0 0 1.5rem 3rem;">Analyze pull requests, track contributors, and measure team velocity</p>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        # User info + logout (OAuth mode only)
        if GITHUB_CLIENT_ID and "github_token" in st.session_state:
            try:
                gh_user = Github(github_token).get_user()
                st.markdown(f"👤 **{gh_user.login}**")
            except Exception:
                pass
            if st.button("Logout", type="secondary"):
                del st.session_state.github_token
                st.session_state.render_blocks = []
                st.rerun()
            st.divider()

        # Analysis mode with styled header
        st.markdown('<p style="color:#64748B; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.1em; font-weight:700; margin-bottom:0.5rem;">Analysis Mode</p>', unsafe_allow_html=True)
        analysis_mode = st.radio(
            label="Analysis Mode",
            options=["Single Month", "Date Range", "Compare Months"],
            index=0,
            format_func=lambda x: {
                "Single Month": "📅 Single Month",
                "Date Range": "📆 Date Range",
                "Compare Months": "📈 Compare Months"
            }[x],
            label_visibility="collapsed"
        )

        # Multiple repos support
        st.subheader("📁 Repositories")
        repo_input = st.text_area(
            "Repository URLs (one per line)",
            placeholder="https://github.com/owner/repo\nhttps://github.com/owner/repo2",
            help="Enter one or more GitHub repository URLs"
        )

        # Parse repos
        repo_urls = [url.strip() for url in repo_input.split('\n') if url.strip()]

        # Aggregate option (only show if multiple repos)
        aggregate_repos = False
        if len(repo_urls) > 1:
            aggregate_repos = st.checkbox(
                "Aggregate all repos",
                value=False,
                help="Merge PRs from all repositories into a single analysis view"
            )

        # Date selection
        current_year = datetime.now().year
        years = list(range(current_year - 5, current_year + 1))
        months = list(range(1, 13))
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        st.subheader("📅 Time Period")

        # Initialize variables
        selected_month = None
        selected_year = None
        start_date = None
        end_date = None
        compare_month = None
        compare_year = None

        if analysis_mode == "Single Month":
            selected_month = st.selectbox(
                "Month",
                options=months,
                format_func=lambda x: month_names[x - 1],
                index=datetime.now().month - 1
            )
            selected_year = st.selectbox(
                "Year",
                options=years,
                index=len(years) - 1,
                key="year1"
            )

        elif analysis_mode == "Date Range":
            col_start, col_end = st.columns(2)
            with col_start:
                st.markdown("**Start Date**")
                start_date = st.date_input(
                    "From",
                    value=datetime.now().replace(day=1),
                    max_value=datetime.now()
                )
            with col_end:
                st.markdown("**End Date**")
                end_date = st.date_input(
                    "To",
                    value=datetime.now(),
                    max_value=datetime.now()
                )

        elif analysis_mode == "Compare Months":
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown("**Month 1**")
                selected_month = st.selectbox(
                    "Month",
                    options=months,
                    format_func=lambda x: month_names[x - 1],
                    index=datetime.now().month - 2 if datetime.now().month > 1 else 0,
                    key="month1"
                )
                selected_year = st.selectbox(
                    "Year",
                    options=years,
                    index=len(years) - 1,
                    key="year1"
                )
            with col_m2:
                st.markdown("**Month 2**")
                compare_month = st.selectbox(
                    "Month",
                    options=months,
                    format_func=lambda x: month_names[x - 1],
                    index=datetime.now().month - 1,
                    key="month2"
                )
                compare_year = st.selectbox(
                    "Year",
                    options=years,
                    index=len(years) - 1,
                    key="year2"
                )

        analyze_button = st.button("🔍 Analyze", type="primary", use_container_width=True)

    # === DATA FETCHING — only runs when Analyze button is clicked ===
    if analyze_button:
        if not repo_urls:
            st.error("Please enter at least one repository URL")
            return

        # Validate all URLs
        invalid_urls = []
        valid_repos = []
        for url in repo_urls:
            try:
                owner, repo = parse_repo_url(url)
                valid_repos.append((url, owner, repo))
            except ValueError as e:
                invalid_urls.append((url, str(e)))

        if invalid_urls:
            st.error("Invalid URLs found:")
            for url, error in invalid_urls:
                st.write(f"- `{url}`: {error}")
            return

        blocks = []
        st.session_state.last_pdf_buffer = None

        if aggregate_repos and len(valid_repos) > 1:
            repo_names = [f"{owner}/{repo}" for _, owner, repo in valid_repos]
            blocks.append({'type': 'header', 'text': f"📁 Aggregated Analysis: {len(valid_repos)} Repositories"})
            blocks.append({'type': 'caption', 'text': f"Repositories: {', '.join(repo_names)}"})

            try:
                all_prs = []
                with st.spinner(f"Fetching PR data from {len(valid_repos)} repositories..."):
                    for repo_url, owner, repo in valid_repos:
                        if analysis_mode == "Single Month":
                            prs = fetch_prs_for_month(repo_url, selected_year, selected_month, token=github_token)
                            all_prs.extend(prs)
                        elif analysis_mode == "Date Range":
                            if start_date > end_date:
                                st.error("Start date must be before or equal to end date")
                                break
                            start_datetime = datetime.combine(start_date, datetime.min.time())
                            end_datetime = datetime.combine(end_date, datetime.max.time())
                            prs = fetch_prs_for_date_range(repo_url, start_datetime, end_datetime, token=github_token)
                            all_prs.extend(prs)
                        elif analysis_mode == "Compare Months":
                            prs_month1 = fetch_prs_for_month(repo_url, selected_year, selected_month, token=github_token)
                            prs_month2 = fetch_prs_for_month(repo_url, compare_year, compare_month, token=github_token)
                            all_prs.extend([(pr, 'month1') for pr in prs_month1])
                            all_prs.extend([(pr, 'month2') for pr in prs_month2])

                if analysis_mode == "Single Month":
                    period_name = f"{month_names[selected_month - 1]} {selected_year}"
                    if not all_prs:
                        blocks.append({'type': 'warning', 'text': f"No PRs found for {period_name} across all repositories"})
                    else:
                        blocks.append({'type': 'info', 'text': f"Analyzing **{len(all_prs)} PRs** from {len(valid_repos)} repositories for {period_name}"})
                        metrics = analyze_prs(all_prs)
                        repo_names_list = [f"{owner}/{repo}" for _, owner, repo in valid_repos]
                        # Generate PDF once at fetch time
                        try:
                            pdf_buffer = generate_pdf_report(metrics, period_name, repo_names_list, aggregate_repos, metrics.get('contributors'))
                            st.session_state.last_pdf_buffer = pdf_buffer
                            st.session_state.last_pdf_filename = f"pr-analysis-{period_name.replace(' ', '-').lower()}-{datetime.now().strftime('%Y%m%d')}.pdf"
                        except Exception as e:
                            st.error(f"Error generating PDF: {e}")
                        blocks.append({'type': 'analysis', 'metrics': metrics, 'period_name': period_name, 'repo_names': repo_names_list, 'aggregate_mode': aggregate_repos})

                elif analysis_mode == "Date Range":
                    period_name = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                    if not all_prs:
                        blocks.append({'type': 'warning', 'text': f"No PRs found for {period_name} across all repositories"})
                    else:
                        blocks.append({'type': 'info', 'text': f"Analyzing **{len(all_prs)} PRs** from {len(valid_repos)} repositories for {period_name}"})
                        metrics = analyze_prs(all_prs)
                        repo_names_list = [f"{owner}/{repo}" for _, owner, repo in valid_repos]
                        try:
                            pdf_buffer = generate_pdf_report(metrics, period_name, repo_names_list, aggregate_repos, metrics.get('contributors'))
                            st.session_state.last_pdf_buffer = pdf_buffer
                            st.session_state.last_pdf_filename = f"pr-analysis-{period_name.replace(' ', '-').lower()}-{datetime.now().strftime('%Y%m%d')}.pdf"
                        except Exception as e:
                            st.error(f"Error generating PDF: {e}")
                        blocks.append({'type': 'analysis', 'metrics': metrics, 'period_name': period_name, 'repo_names': repo_names_list, 'aggregate_mode': aggregate_repos})

                elif analysis_mode == "Compare Months":
                    month1_name = f"{month_names[selected_month - 1]} {selected_year}"
                    month2_name = f"{month_names[compare_month - 1]} {compare_year}"
                    prs_m1 = [pr for pr, month in all_prs if month == 'month1']
                    prs_m2 = [pr for pr, month in all_prs if month == 'month2']
                    if not prs_m1 and not prs_m2:
                        blocks.append({'type': 'warning', 'text': f"No PRs found for either {month1_name} or {month2_name}"})
                    else:
                        blocks.append({'type': 'info', 'text': f"Analyzing **{len(prs_m1)} PRs** for {month1_name} and **{len(prs_m2)} PRs** for {month2_name}"})
                        comparison = analyze_comparison(prs_m1, prs_m2, month1_name, month2_name)
                        blocks.append({'type': 'comparison', 'comparison': comparison, 'month1_name': month1_name, 'month2_name': month2_name, 'has_month1': bool(prs_m1), 'has_month2': bool(prs_m2)})

            except Exception as e:
                blocks.append({'type': 'error', 'text': f"Error analyzing repositories: {e}"})
                blocks.append({'type': 'info', 'text': "Make sure the repositories exist and your GITHUB_TOKEN has access to them."})

        else:
            # Individual repo mode
            for repo_url, owner, repo in valid_repos:
                blocks.append({'type': 'header', 'text': f"📁 {owner}/{repo}"})
                try:
                    with st.spinner(f"Fetching PR data for {owner}/{repo}..."):
                        if analysis_mode == "Single Month":
                            prs = fetch_prs_for_month(repo_url, selected_year, selected_month, token=github_token)
                            period_name = f"{month_names[selected_month - 1]} {selected_year}"
                            if not prs:
                                blocks.append({'type': 'warning', 'text': f"No PRs found for {period_name}"})
                            else:
                                blocks.append({'type': 'info', 'text': f"Analyzing **{len(prs)} PRs** for {period_name}"})
                                metrics = analyze_prs(prs)
                                repo_names_list = [f"{owner}/{repo}"]
                                try:
                                    pdf_buffer = generate_pdf_report(metrics, period_name, repo_names_list, False, metrics.get('contributors'))
                                    st.session_state.last_pdf_buffer = pdf_buffer
                                    st.session_state.last_pdf_filename = f"pr-analysis-{period_name.replace(' ', '-').lower()}-{datetime.now().strftime('%Y%m%d')}.pdf"
                                except Exception:
                                    pass
                                blocks.append({'type': 'analysis', 'metrics': metrics, 'period_name': period_name, 'repo_names': repo_names_list, 'aggregate_mode': False})

                        elif analysis_mode == "Date Range":
                            if start_date > end_date:
                                blocks.append({'type': 'error', 'text': "Start date must be before or equal to end date"})
                            else:
                                start_datetime = datetime.combine(start_date, datetime.min.time())
                                end_datetime = datetime.combine(end_date, datetime.max.time())
                                prs = fetch_prs_for_date_range(repo_url, start_datetime, end_datetime, token=github_token)
                                period_name = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                                if not prs:
                                    blocks.append({'type': 'warning', 'text': f"No PRs found for {period_name}"})
                                else:
                                    blocks.append({'type': 'info', 'text': f"Analyzing **{len(prs)} PRs** for {period_name}"})
                                    metrics = analyze_prs(prs)
                                    repo_names_list = [f"{owner}/{repo}"]
                                    try:
                                        pdf_buffer = generate_pdf_report(metrics, period_name, repo_names_list, False, metrics.get('contributors'))
                                        st.session_state.last_pdf_buffer = pdf_buffer
                                        st.session_state.last_pdf_filename = f"pr-analysis-{period_name.replace(' ', '-').lower()}-{datetime.now().strftime('%Y%m%d')}.pdf"
                                    except Exception:
                                        pass
                                    blocks.append({'type': 'analysis', 'metrics': metrics, 'period_name': period_name, 'repo_names': repo_names_list, 'aggregate_mode': False})

                        elif analysis_mode == "Compare Months":
                            month1_name = f"{month_names[selected_month - 1]} {selected_year}"
                            month2_name = f"{month_names[compare_month - 1]} {compare_year}"
                            prs_month1 = fetch_prs_for_month(repo_url, selected_year, selected_month, token=github_token)
                            prs_month2 = fetch_prs_for_month(repo_url, compare_year, compare_month, token=github_token)
                            if not prs_month1 and not prs_month2:
                                blocks.append({'type': 'warning', 'text': f"No PRs found for either {month1_name} or {month2_name}"})
                            else:
                                comparison = analyze_comparison(prs_month1, prs_month2, month1_name, month2_name)
                                blocks.append({'type': 'comparison', 'comparison': comparison, 'month1_name': month1_name, 'month2_name': month2_name, 'has_month1': bool(prs_month1), 'has_month2': bool(prs_month2)})

                except Exception as e:
                    blocks.append({'type': 'error', 'text': f"Error analyzing {owner}/{repo}: {e}"})
                    blocks.append({'type': 'info', 'text': "Make sure the repository exists and your GITHUB_TOKEN has access to it."})

                blocks.append({'type': 'divider'})

        st.session_state.render_blocks = blocks

    # === RENDERING — always runs on every re-run (button click or widget interaction) ===
    for block in st.session_state.render_blocks:
        btype = block['type']
        if btype == 'header':
            st.header(block['text'])
        elif btype == 'caption':
            st.caption(block['text'])
        elif btype == 'info':
            st.info(block['text'])
        elif btype == 'warning':
            st.warning(block['text'])
        elif btype == 'error':
            st.error(block['text'])
        elif btype == 'analysis':
            display_analysis_results(
                block['metrics'],
                block['period_name'],
                block['repo_names'],
                block['aggregate_mode'],
                skip_pdf=True  # PDF was already generated during fetch
            )
        elif btype == 'comparison':
            comp = block['comparison']
            display_comparison(comp)
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.subheader(f"📅 {block['month1_name']}")
                if block['has_month1']:
                    m = comp['month1']['metrics']
                    st.metric("Total", m['total'])
                    st.metric("AI %", f"{m['ai_contribution_pct']:.1f}%")
                    st.metric("Velocity", f"{m['pr_velocity']:.1f}/day")
                else:
                    st.info("No data")
            with col_m2:
                st.subheader(f"📅 {block['month2_name']}")
                if block['has_month2']:
                    m = comp['month2']['metrics']
                    st.metric("Total", m['total'])
                    st.metric("AI %", f"{m['ai_contribution_pct']:.1f}%")
                    st.metric("Velocity", f"{m['pr_velocity']:.1f}/day")
                else:
                    st.info("No data")
        elif btype == 'divider':
            st.divider()


if __name__ == "__main__":
    main()
