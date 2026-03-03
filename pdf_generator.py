"""PDF Report Generator for GitHub PR Analyzer."""

import re
from datetime import datetime
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# Register Japanese font
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))


def contains_japanese(text):
    """Check if text contains Japanese characters."""
    if not text:
        return False
    # Japanese Unicode ranges
    japanese_pattern = re.compile(
        r'[\u3040-\u309F]'  # Hiragana
        r'|[\u30A0-\u30FF]'  # Katakana
        r'|[\u4E00-\u9FFF]'  # Kanji
        r'|[\uFF00-\uFFEF]'  # Full-width chars
        r'|[\u3000-\u303F]'  # Punctuation
    )
    return bool(japanese_pattern.search(text))


# Helper function to detect AI PRs (copied from pr_analyzer to avoid circular import)
def is_ai_pr(pr):
    """Check if a PR is AI-generated based on branch name or author."""
    ai_branch_prefixes = ['claude/', 'devin/', 'ai/', 'bot/', 'gpt/']
    ai_authors = ['devin-ai-integration', 'github-actions', 'dependabot']

    branch = pr.head.ref.lower()
    author = pr.user.login.lower()

    for prefix in ai_branch_prefixes:
        if branch.startswith(prefix):
            return True

    for ai_author in ai_authors:
        if ai_author in author:
            return True

    return False


def generate_pdf_report(metrics, period_name, repo_names, aggregate_mode=False, contributors_stats=None):
    """Generate a PDF report from PR analysis metrics.

    Args:
        metrics: Dictionary containing PR analysis metrics
        period_name: String representing the analysis period
        repo_names: List of repository names analyzed
        aggregate_mode: Boolean indicating if multiple repos were aggregated
        contributors_stats: Dictionary containing detailed contributor statistics

    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    # Container for elements
    elements = []
    styles = getSampleStyleSheet()

    # Helper function to get font based on text content
    def get_font_name(text, is_bold=False):
        """Return appropriate font name based on text content."""
        if contains_japanese(text):
            return 'HeiseiKakuGo-W5'
        return 'Helvetica-Bold' if is_bold else 'Helvetica'

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1E40AF'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1E40AF'),
        spaceAfter=10,
        spaceBefore=15,
        fontName='Helvetica-Bold'
    )

    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=13,
        textColor=colors.HexColor('#3B82F6'),
        spaceAfter=8,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=6
    )

    # Title Page
    elements.append(Spacer(1, 50))
    elements.append(Paragraph("GitHub PR Analysis Report", title_style))
    elements.append(Spacer(1, 20))

    # Report metadata
    meta_data = [
        ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        ['Analysis Period:', period_name],
        ['Repository(s):', ', '.join(repo_names) if isinstance(repo_names, list) else repo_names],
        ['Mode:', 'Aggregated' if aggregate_mode else 'Individual'],
    ]

    meta_table = Table(meta_data, colWidths=[40*mm, 120*mm])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 30))

    # Executive Summary
    elements.append(Paragraph("Executive Summary", heading_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#3B82F6')))
    elements.append(Spacer(1, 10))

    summary_text = f"""
    This report analyzes <b>{metrics['total']}</b> pull requests during <b>{period_name}</b>.
    Of these, <b>{metrics['merged']}</b> were merged ({metrics['merged']/metrics['total']*100:.1f}%),
    <b>{metrics['open']}</b> are still open, and <b>{metrics['closed']}</b> were closed without merging.
    <br/><br/>
    AI-generated PRs account for <b>{metrics['ai_contribution_pct']:.1f}%</b> of all PRs,
    with an average merge rate of <b>{metrics['ai_merge_rate']:.1f}%</b> compared to
    <b>{metrics['human_merge_rate']:.1f}%</b> for human PRs.
    <br/><br/>
    The team maintains a velocity of <b>{metrics['pr_velocity']:.1f}</b> PRs per day.
    """
    elements.append(Paragraph(summary_text, normal_style))
    elements.append(PageBreak())

    # Key Metrics Section
    elements.append(Paragraph("Key Metrics", heading_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#3B82F6')))
    elements.append(Spacer(1, 15))

    # Overview Metrics Table
    elements.append(Paragraph("Overview", subheading_style))

    overview_data = [
        ['Metric', 'Value', 'Percentage'],
        ['Total PRs', f"{metrics['total']:,}", '100%'],
        ['Merged', f"{metrics['merged']:,}", f"{metrics['merged']/metrics['total']*100:.1f}%" if metrics['total'] > 0 else 'N/A'],
        ['Open', f"{metrics['open']:,}", f"{metrics['open']/metrics['total']*100:.1f}%" if metrics['total'] > 0 else 'N/A'],
        ['Closed', f"{metrics['closed']:,}", f"{metrics['closed']/metrics['total']*100:.1f}%" if metrics['total'] > 0 else 'N/A'],
    ]

    overview_table = Table(overview_data, colWidths=[50*mm, 40*mm, 40*mm])
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
    ]))
    elements.append(overview_table)
    elements.append(Spacer(1, 20))

    # AI Contribution Section
    elements.append(Paragraph("AI Contribution", subheading_style))

    ai_data = [
        ['Metric', 'AI PRs', 'Human PRs', 'Difference'],
        ['Count', f"{metrics['ai_prs']:,}", f"{metrics['human_prs']:,}", f"{metrics['ai_prs'] - metrics['human_prs']:+d}"],
        ['Percentage', f"{metrics['ai_contribution_pct']:.1f}%", f"{100 - metrics['ai_contribution_pct']:.1f}%", '-'],
        ['Merge Rate', f"{metrics['ai_merge_rate']:.1f}%", f"{metrics['human_merge_rate']:.1f}%", f"{metrics['ai_merge_rate'] - metrics['human_merge_rate']:+.1f}%"],
    ]

    ai_table = Table(ai_data, colWidths=[40*mm, 35*mm, 35*mm, 35*mm])
    ai_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#3B82F6')),
        ('TEXTCOLOR', (2, 1), (2, -1), colors.HexColor('#64748B')),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
    ]))
    elements.append(ai_table)
    elements.append(Spacer(1, 20))

    # Merge Time Analysis
    if metrics.get('avg_merge_time_hours', 0) > 0:
        elements.append(Paragraph("Merge Time Analysis", subheading_style))

        avg_time = metrics['avg_merge_time_hours']
        ai_time = metrics.get('ai_avg_merge_time_hours', 0)
        human_time = metrics.get('human_avg_merge_time_hours', 0)

        merge_time_data = [
            ['Category', 'Average Time', 'Comparison'],
            ['Overall', f"{avg_time:.1f}h", '-'],
            ['AI PRs', f"{ai_time:.1f}h" if ai_time > 0 else 'N/A', f"{ai_time - avg_time:+.1f}h" if ai_time > 0 else '-'],
            ['Human PRs', f"{human_time:.1f}h" if human_time > 0 else 'N/A', f"{human_time - avg_time:+.1f}h" if human_time > 0 else '-'],
        ]

        merge_table = Table(merge_time_data, colWidths=[50*mm, 40*mm, 50*mm])
        merge_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#1E3A8A')),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
        ]))
        elements.append(merge_table)

    elements.append(PageBreak())

    # PR Timeline Section
    if metrics.get('prs_by_date'):
        elements.append(Paragraph("PR Timeline", heading_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#3B82F6')))
        elements.append(Spacer(1, 15))

        prs_by_date = metrics['prs_by_date']
        if prs_by_date:
            dates = sorted(prs_by_date.keys())

            timeline_data = [['Date', 'PR Count']]
            for date in dates:
                timeline_data.append([str(date), str(prs_by_date[date])])

            timeline_table = Table(timeline_data, colWidths=[60*mm, 30*mm])
            timeline_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1E3A8A')),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
            ]))
            elements.append(timeline_table)
            elements.append(Spacer(1, 20))

    # Top Contributors Section
    if metrics.get('top_contributors'):
        elements.append(Paragraph("Top Contributors", heading_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#3B82F6')))
        elements.append(Spacer(1, 15))

        contributors_data = [['Rank', 'Contributor', 'PRs', 'Percentage']]
        total_prs = sum(count for _, count in metrics['top_contributors'])

        for rank, (author, count) in enumerate(metrics['top_contributors'], 1):  # ALL contributors
            percentage = (count / total_prs * 100) if total_prs > 0 else 0
            contributors_data.append([str(rank), author, f"{count:,}", f"{percentage:.1f}%"])

        contrib_table = Table(contributors_data, colWidths=[20*mm, 70*mm, 25*mm, 30*mm])
        contrib_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1E3A8A')),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
        ]))
        elements.append(contrib_table)
        elements.append(Spacer(1, 20))

    # PR Details Section
    if metrics.get('all_prs'):
        elements.append(PageBreak())
        elements.append(Paragraph("Pull Request Details", heading_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#3B82F6')))
        elements.append(Spacer(1, 15))

        all_prs = metrics['all_prs']  # Include ALL PRs

        # Create cell styles for title wrapping
        title_style = ParagraphStyle(
            'TableTitle',
            parent=normal_style,
            fontSize=8,
            leading=10,
            wordWrap='CJK',
            alignment=TA_LEFT
        )

        # Style for clickable PR links
        link_style = ParagraphStyle(
            'LinkStyle',
            parent=normal_style,
            fontSize=8,
            textColor=colors.HexColor('#3B82F6'),
            alignment=TA_CENTER
        )

        pr_data = [['#', 'Title', 'Author', 'State', 'AI']]
        for pr in all_prs:
            # Create a title style with Japanese font support if needed
            title_font = get_font_name(pr.title)
            title_style_jp = ParagraphStyle(
                f'TableTitle_{id(pr)}',
                parent=normal_style,
                fontSize=8,
                leading=10,
                wordWrap='CJK',
                alignment=TA_LEFT,
                fontName=title_font
            )
            # Use Paragraph for title to handle long text with proper wrapping
            title_para = Paragraph(pr.title, title_style_jp)
            # Create clickable link for PR number
            pr_link = Paragraph(f'<a href="{pr.html_url}" color="blue">#{pr.number}</a>', link_style)
            pr_data.append([
                pr_link,
                title_para,
                pr.user.login,
                'Merged' if pr.merged_at else pr.state.capitalize(),
                'Yes' if is_ai_pr(pr) else 'No'
            ])

        # Adjust column widths - give more space to title
        pr_table = Table(pr_data, colWidths=[15*mm, 95*mm, 30*mm, 20*mm, 15*mm], repeatRows=1)
        pr_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (1, 1), (-1, -1), colors.HexColor('#334155')),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (2, 1), (4, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
        ]))
        elements.append(pr_table)
        elements.append(Spacer(1, 20))

    # Detailed Contributor Statistics Section
    if contributors_stats:
        elements.append(PageBreak())
        elements.append(Paragraph("Detailed Contributor Statistics", heading_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#3B82F6')))
        elements.append(Spacer(1, 15))

        # Sort by Total PRs descending
        sorted_contributors = dict(sorted(
            contributors_stats.items(),
            key=lambda x: x[1]['total_prs'],
            reverse=True
        ))

        contrib_detail_data = [['Username', 'Total', 'Merged', 'Open', 'Closed', 'Merge %', 'Avg Time', 'AI PRs', 'PRs/Wk']]

        for username, stats in sorted_contributors.items():  # ALL contributors
            avg_time = stats['avg_merge_time_hours']
            avg_time_str = f"{avg_time:.1f}h" if avg_time > 0 else "N/A"

            contrib_detail_data.append([
                username,
                f"{stats['total_prs']}",
                f"{stats['merged']}",
                f"{stats['open']}",
                f"{stats['closed']}",
                f"{stats['merge_rate']:.1f}%",
                avg_time_str,
                f"{stats['ai_prs']}",
                f"{stats['prs_per_week']:.2f}"
            ])

        # Use smaller font and column widths to fit all columns
        contrib_detail_table = Table(
            contrib_detail_data,
            colWidths=[32*mm, 16*mm, 16*mm, 14*mm, 16*mm, 18*mm, 18*mm, 14*mm, 16*mm],
            repeatRows=1
        )
        contrib_detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (1, 1), (-1, -1), colors.HexColor('#334155')),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
        ]))
        elements.append(contrib_detail_table)
        elements.append(Spacer(1, 20))

    # Top Labels Section
    if metrics.get('top_labels'):
        elements.append(Paragraph("Top Labels", heading_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#3B82F6')))
        elements.append(Spacer(1, 15))

        labels_data = [['Label', 'Count']]
        for label, count in metrics['top_labels']:  # ALL labels
            labels_data.append([label, f"{count:,}"])

        labels_table = Table(labels_data, colWidths=[100*mm, 45*mm])
        labels_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1E3A8A')),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
        ]))
        elements.append(labels_table)

    # Footer
    elements.append(Spacer(1, 40))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
    elements.append(Spacer(1, 10))
    footer_text = f"Generated by GitHub PR Analyzer • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    elements.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#94A3B8'),
        alignment=TA_CENTER
    )))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
