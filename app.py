# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pr_fetcher import fetch_prs_for_month, fetch_prs_for_date_range, parse_repo_url, fetch_comments_for_prs
from pr_analyzer import analyze_prs, analyze_comparison, is_ai_pr, analyze_contributors
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
    """Display metric cards in a grid."""
    # Row 1: Basic counts
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total PRs", metrics['total'])
    with col2:
        st.metric("Merged", metrics['merged'])
    with col3:
        st.metric("Open", metrics['open'])
    with col4:
        st.metric("Closed", metrics['closed'])

    # Row 2: AI stats
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("AI PRs", f"{metrics['ai_prs']} ({metrics['ai_contribution_pct']:.1f}%)")
    with col6:
        st.metric("Human PRs", metrics['human_prs'])
    with col7:
        ai_rate = metrics['ai_merge_rate']
        human_rate = metrics['human_merge_rate']
        st.metric("AI Merge Rate", f"{ai_rate:.1f}%", delta=f"vs {human_rate:.1f}% human")
    with col8:
        st.metric("PR Velocity", f"{metrics['pr_velocity']:.1f}/day")

    # Row 3: Merge time stats
    col9, col10, col11 = st.columns(3)
    avg_time = metrics['avg_merge_time_hours']
    with col9:
        st.metric("Avg Merge Time", f"{avg_time:.1f}h" if avg_time > 0 else "N/A")
    with col10:
        ai_time = metrics['ai_avg_merge_time_hours']
        st.metric("AI Avg Merge Time", f"{ai_time:.1f}h" if ai_time > 0 else "N/A")
    with col11:
        human_time = metrics['human_avg_merge_time_hours']
        st.metric("Human Avg Merge Time", f"{human_time:.1f}h" if human_time > 0 else "N/A")


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
        comments = stats['comments_per_pr']

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
            'Comments/PR': f"{comments:.1f}" if comments is not None else "-",
        })
    return data


def display_contributor_statistics(prs, contributors_stats=None, start_date=None, end_date=None):
    """Display contributor statistics table with lazy-loaded comments."""
    if not prs:
        st.info("No PRs found for contributor analysis")
        return

    st.subheader("Contributor Statistics")

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

    # Lazy load comments button
    comments_loaded = st.session_state.get('comments_loaded', False)

    col1, col2 = st.columns([1, 4])
    with col1:
        if not comments_loaded:
            if st.button("Load Comments", type="secondary"):
                with st.spinner("Fetching comments..."):
                    comments_map = fetch_comments_for_prs(prs)

                    # Update stats with comments
                    for username, stats in contributors_stats.items():
                        user_prs = [p for p in prs if p.user.login == username]
                        total_comments = sum(comments_map.get(p.number, 0) for p in user_prs)
                        stats['comments_per_pr'] = total_comments / len(user_prs) if user_prs else 0

                    st.session_state['comments_loaded'] = True
                    st.rerun()
        else:
            st.caption("Comments loaded")

    with col2:
        st.caption("Click 'Load Comments' to fetch average comments per PR (may take time for large repos)")

    # Create DataFrame
    data = get_contributors_data_for_df(contributors_stats)
    df = pd.DataFrame(data)

    # Display table
    st.dataframe(df, use_container_width=True, hide_index=True)


def display_analysis_results(metrics, period_name):
    """Display analysis results for a given time period."""
    # Display metrics
    st.subheader("📊 Summary Metrics")
    display_metrics_cards(metrics)

    st.divider()

    # Charts row 1
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("**PR Status Distribution**")
        status_data = pd.DataFrame({
            'Status': ['Merged', 'Open', 'Closed'],
            'Count': [metrics['merged'], metrics['open'], metrics['closed']]
        })
        st.bar_chart(status_data.set_index('Status'))

    with col_chart2:
        st.markdown("**AI vs Human PRs**")
        ai_data = pd.DataFrame({
            'Type': ['AI PRs', 'Human PRs'],
            'Count': [metrics['ai_prs'], metrics['human_prs']]
        })
        st.bar_chart(ai_data.set_index('Type'))

    # Timeline
    st.subheader("📈 PR Timeline")
    display_timeline_chart(metrics['prs_by_date'])

    # All contributors
    st.subheader("👥 All Contributors")

    tab_overall, tab_ai, tab_human = st.tabs(["📊 Overall", "🤖 AI", "👤 Human"])

    with tab_overall:
        display_all_contributors(metrics['top_contributors'], "All Contributors", "overall")

    with tab_ai:
        display_all_contributors(metrics['top_ai_contributors'], "AI Contributors", "ai")

    with tab_human:
        display_all_contributors(metrics['top_human_contributors'], "Human Contributors", "human")

    # Label analysis
    if metrics['top_labels']:
        st.subheader("🏷️ Label Analysis")
        display_label_analysis(metrics['top_labels'])

    st.divider()

    # PR Details with tabs
    st.subheader("📝 Pull Request Details")
    display_pr_tabs(metrics)

    # Contributor Statistics
    display_contributor_statistics(metrics['all_prs'], metrics.get('contributors'))


def display_pr_tabs(metrics):
    """Display PRs in tabs (All / AI / Human)."""
    tab1, tab2, tab3 = st.tabs(["📋 All PRs", "🤖 AI PRs", "👤 Human PRs"])

    with tab1:
        if metrics['all_prs']:
            pr_data = get_pr_data_for_df(metrics['all_prs'])
            df = pd.DataFrame(pr_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

        else:
            st.info("No PRs found")

    with tab2:
        if metrics['ai_pr_list']:
            pr_data = get_pr_data_for_df(metrics['ai_pr_list'])
            df = pd.DataFrame(pr_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

        else:
            st.info("No AI PRs found")

    with tab3:
        if metrics['human_pr_list']:
            pr_data = get_pr_data_for_df(metrics['human_pr_list'])
            df = pd.DataFrame(pr_data)
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

    # Page config
    st.set_page_config(
        page_title="GitHub PR Analyzer",
        page_icon="🔧",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Check for GitHub token
    if not GITHUB_TOKEN:
        st.error("⚠️ GITHUB_TOKEN not found. Please set it in your .env file.")
        st.stop()

    # Header
    st.title("🔧 GitHub PR Analyzer")
    st.markdown("Analyze Pull Requests for any GitHub repository by month")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Theme toggle
        dark_mode = st.toggle("🌙 Dark Mode", value=st.session_state.dark_mode)
        st.session_state.dark_mode = dark_mode

        # Auto refresh
        auto_refresh = st.checkbox("🔄 Auto Refresh (5 min)", value=False)
        if auto_refresh:
            st.caption("Page will auto-refresh every 5 minutes")
            st.markdown("<meta http-equiv='refresh' content='300'>", unsafe_allow_html=True)

        st.divider()

        # Analysis mode
        analysis_mode = st.radio(
            "Analysis Mode",
            ["📊 Single Month", "📅 Date Range", "📈 Compare Months"],
            index=0
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
        compare_start_date = None
        compare_end_date = None

        if analysis_mode == "📊 Single Month":
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

        elif analysis_mode == "📅 Date Range":
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

        elif analysis_mode == "📈 Compare Months":
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

    # Main content
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

        # Process each repo
        for repo_url, owner, repo in valid_repos:
            st.header(f"📁 {owner}/{repo}")

            try:
                with st.spinner(f"Fetching PR data for {owner}/{repo}..."):
                    if analysis_mode == "📊 Single Month":
                        # Single month analysis
                        prs = fetch_prs_for_month(repo_url, selected_year, selected_month)
                        period_name = f"{month_names[selected_month - 1]} {selected_year}"

                        if not prs:
                            st.warning(f"No PRs found for {period_name}")
                            continue

                        st.info(f"Analyzing **{len(prs)} PRs** for {period_name}")

                        # Analyze and display
                        metrics = analyze_prs(prs)
                        display_analysis_results(metrics, period_name)

                    elif analysis_mode == "📅 Date Range":
                        # Date range analysis
                        # Validate date range
                        if start_date > end_date:
                            st.error("Start date must be before or equal to end date")
                            continue

                        # Convert date to datetime for comparison
                        start_datetime = datetime.combine(start_date, datetime.min.time())
                        end_datetime = datetime.combine(end_date, datetime.max.time())

                        prs = fetch_prs_for_date_range(repo_url, start_datetime, end_datetime)
                        period_name = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

                        if not prs:
                            st.warning(f"No PRs found for {period_name}")
                            continue

                        st.info(f"Analyzing **{len(prs)} PRs** for {period_name}")

                        # Analyze and display
                        metrics = analyze_prs(prs)
                        display_analysis_results(metrics, period_name)

                    elif analysis_mode == "📈 Compare Months":
                        # Comparison mode
                        month1_name = f"{month_names[selected_month - 1]} {selected_year}"
                        month2_name = f"{month_names[compare_month - 1]} {compare_year}"

                        prs_month1 = fetch_prs_for_month(repo_url, selected_year, selected_month)
                        prs_month2 = fetch_prs_for_month(repo_url, compare_year, compare_month)

                        if not prs_month1 and not prs_month2:
                            st.warning(f"No PRs found for either {month1_name} or {month2_name}")
                            continue

                        # Compare
                        comparison = analyze_comparison(
                            prs_month1, prs_month2,
                            month1_name, month2_name
                        )

                        display_comparison(comparison)

                        # Show details for both months
                        col_m1, col_m2 = st.columns(2)

                        with col_m1:
                            st.subheader(f"📅 {month1_name}")
                            if prs_month1:
                                metrics1 = comparison['month1']['metrics']
                                st.metric("Total", metrics1['total'])
                                st.metric("AI %", f"{metrics1['ai_contribution_pct']:.1f}%")
                                st.metric("Velocity", f"{metrics1['pr_velocity']:.1f}/day")
                            else:
                                st.info("No data")

                        with col_m2:
                            st.subheader(f"📅 {month2_name}")
                            if prs_month2:
                                metrics2 = comparison['month2']['metrics']
                                st.metric("Total", metrics2['total'])
                                st.metric("AI %", f"{metrics2['ai_contribution_pct']:.1f}%")
                                st.metric("Velocity", f"{metrics2['pr_velocity']:.1f}/day")
                            else:
                                st.info("No data")

                st.divider()

            except Exception as e:
                st.error(f"Error analyzing {owner}/{repo}: {e}")
                st.info("Make sure the repository exists and your GITHUB_TOKEN has access to it.")


if __name__ == "__main__":
    main()
