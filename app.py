# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pr_fetcher import fetch_prs_for_month, fetch_prs_for_date_range, parse_repo_url, fetch_comments_for_prs
from pr_analyzer import analyze_prs, analyze_comparison, is_ai_pr, analyze_contributors
from pdf_generator import generate_pdf_report
from config import GITHUB_TOKEN


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
    st.markdown("""
        <h4 style="color: #1E40AF; margin: 1.5rem 0 1rem 0; font-weight: 600;">
            Overview
        </h4>
    """, unsafe_allow_html=True)

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
    st.markdown("""
        <h4 style="color: #1E40AF; margin: 1.5rem 0 1rem 0; font-weight: 600;">
            AI Contribution
        </h4>
    """, unsafe_allow_html=True)

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
    st.markdown("""
        <h4 style="color: #1E40AF; margin: 1.5rem 0 1rem 0; font-weight: 600;">
            Merge Time Analysis
        </h4>
    """, unsafe_allow_html=True)

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
        <h3 style="color: #1E40AF; margin: 2rem 0 1rem 0; font-weight: 700;">
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
            background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            font-weight: 600;
            font-size: 1.1rem;
        ">
            📅 Analysis Period: {period_name}
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
        <h3 style="color: #1E40AF; margin: 2rem 0 1rem 0; font-weight: 700;">
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
        <h3 style="color: #1E40AF; margin: 2rem 0 1rem 0; font-weight: 700;">
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
            <h3 style="color: #1E40AF; margin: 2rem 0 1rem 0; font-weight: 700;">
                🏷️ Label Analysis
            </h3>
        """, unsafe_allow_html=True)
        display_label_analysis(metrics['top_labels'])

    st.divider()

    # PR Details with tabs
    st.markdown("""
        <h3 style="color: #1E40AF; margin: 2rem 0 1rem 0; font-weight: 700;">
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

    # Custom CSS for improved UI
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');

        /* Global font */
        html, body, [class*="css"] {
            font-family: 'Fira Sans', sans-serif;
        }

        /* Code elements */
        code, pre, .stCodeBlock {
            font-family: 'Fira Code', monospace !important;
        }

        /* Header styling */
        h1 {
            color: #1E3A8A !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em;
        }

        h2, h3 {
            color: #1E40AF !important;
            font-weight: 600 !important;
            margin-top: 1.5rem !important;
        }

        /* Metric cards styling - Fixed height */
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, #F8FAFC 0%, #FFFFFF 100%);
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            transition: all 0.2s ease;
            height: 150px !important;
            min-height: 150px !important;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        [data-testid="stMetric"]:hover {
            box-shadow: 0 4px 12px rgba(30, 64, 175, 0.15);
            border-color: #3B82F6;
        }

        /* Metric label */
        [data-testid="stMetric"] > div:first-child {
            font-size: 0.875rem;
            color: #475569;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }

        /* Metric value */
        [data-testid="stMetric"] > div:last-child {
            font-size: 1.75rem;
            font-weight: 700;
            color: #1E3A8A;
        }

        /* Delta styling */
        [data-testid="stMetricDelta"] {
            color: #059669 !important;
            font-weight: 600;
            font-size: 0.875rem;
        }

        /* Ensure columns have equal height */
        [data-testid="column"] {
            display: flex;
            flex-direction: column;
        }

        [data-testid="column"] > div {
            flex: 1;
        }

        [data-testid="stMetric"] > div:first-child {
            font-size: 0.875rem;
            color: #475569;
            font-weight: 500;
        }

        [data-testid="stMetric"] > div:last-child {
            font-size: 1.75rem;
            font-weight: 700;
            color: #1E3A8A;
        }

        /* Delta styling */
        [data-testid="stMetricDelta"] {
            color: #059669 !important;
            font-weight: 600;
        }

        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 100%);
        }

        section[data-testid="stSidebar"] .block-container {
            padding-top: 2rem;
        }

        /* Button styling - Primary (Blue) */
        .stButton > button[kind="primary"],
        button[kind="primary"] {
            background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.75rem 1.5rem !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
        }

        .stButton > button[kind="primary"]:hover,
        button[kind="primary"]:hover {
            background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%) !important;
            box-shadow: 0 4px 12px rgba(30, 64, 175, 0.3) !important;
            transform: translateY(-1px) !important;
        }

        /* Secondary button styling */
        .stButton > button[kind="secondary"] {
            background: #F1F5F9;
            color: #1E40AF;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 0.75rem 1.5rem;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        .stButton > button[kind="secondary"]:hover {
            background: #E2E8F0;
            border-color: #CBD5E1;
        }

        /* Checkbox styling */
        .stCheckbox > label {
            color: #334155;
            font-weight: 500;
        }

        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }

        .stTabs [data-baseweb="tab"] {
            background: #F1F5F9;
            border-radius: 8px 8px 0 0;
            padding: 0.75rem 1.25rem;
            font-weight: 500;
            color: #64748B;
        }

        .stTabs [aria-selected="true"] {
            background: #1E40AF !important;
            color: white !important;
        }

        /* DataFrame styling */
        .stDataFrame {
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            overflow: hidden;
        }

        /* Info/Warning boxes */
        .stAlert {
            border-radius: 8px;
        }

        /* Divider styling */
        hr {
            margin: 2rem 0;
            border-color: #E2E8F0;
        }

        /* Caption styling */
        .stCaption {
            color: #64748B;
            font-size: 0.875rem;
        }

        /* Subheader styling */
        .streamlit-expanderHeader {
            font-weight: 600;
            color: #1E40AF;
        }
    </style>
    """, unsafe_allow_html=True)

    # Check for GitHub token
    if not GITHUB_TOKEN:
        st.error("⚠️ GITHUB_TOKEN not found. Please set it in your .env file.")
        st.stop()

    # Header
    st.title("GitHub PR Analyzer")
    st.markdown("Analyze Pull Requests for any GitHub repository by month")

    # Sidebar
    with st.sidebar:
        # Analysis mode with styled header
        st.markdown("""
            <h3 style="
                color: #1E40AF;
                font-weight: 700;
                font-size: 1.1rem;
                margin-bottom: 0.75rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            ">
                📊 Analysis Mode
            </h3>
        """, unsafe_allow_html=True)
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
                            prs = fetch_prs_for_month(repo_url, selected_year, selected_month)
                            all_prs.extend(prs)
                        elif analysis_mode == "Date Range":
                            if start_date > end_date:
                                st.error("Start date must be before or equal to end date")
                                break
                            start_datetime = datetime.combine(start_date, datetime.min.time())
                            end_datetime = datetime.combine(end_date, datetime.max.time())
                            prs = fetch_prs_for_date_range(repo_url, start_datetime, end_datetime)
                            all_prs.extend(prs)
                        elif analysis_mode == "Compare Months":
                            prs_month1 = fetch_prs_for_month(repo_url, selected_year, selected_month)
                            prs_month2 = fetch_prs_for_month(repo_url, compare_year, compare_month)
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
                            prs = fetch_prs_for_month(repo_url, selected_year, selected_month)
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
                                prs = fetch_prs_for_date_range(repo_url, start_datetime, end_datetime)
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
                            prs_month1 = fetch_prs_for_month(repo_url, selected_year, selected_month)
                            prs_month2 = fetch_prs_for_month(repo_url, compare_year, compare_month)
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
