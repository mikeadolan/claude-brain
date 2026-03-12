#!/usr/bin/env python3
"""brain_digest.py — Email digests from the claude-brain database.

Three email types:
  Weekly digest (default) — full portfolio view, inception-to-date, trends, dormant alerts
  Daily standup (--daily) — compact: yesterday's sessions, decisions, where you left off

Queries brain data and sends formatted HTML email via Gmail SMTP.

Usage:
    python3 scripts/brain_digest.py                # Send weekly digest
    python3 scripts/brain_digest.py --daily        # Send daily standup
    python3 scripts/brain_digest.py --days 14      # Custom lookback
    python3 scripts/brain_digest.py --dry-run      # Print to stdout, don't send
    python3 scripts/brain_digest.py --test         # Send a short test email
"""

import argparse
import json
import os
import smtplib
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import yaml

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)


def load_config():
    config_path = os.path.join(ROOT, "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_db(config):
    db_path = config["storage"]["local_db_path"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Data queries
# ---------------------------------------------------------------------------

def get_project_labels(conn):
    """Map project prefix to human label."""
    rows = conn.execute("SELECT prefix, label FROM project_registry").fetchall()
    return {r["prefix"]: r["label"] for r in rows}


def get_weekly_stats(conn, since):
    """Per-project session/message counts for the period."""
    rows = conn.execute("""
        SELECT project,
               COUNT(*) as sessions,
               SUM(message_count) as messages,
               ROUND(AVG(message_count), 1) as avg_msgs,
               MIN(started_at) as first_session,
               MAX(started_at) as last_session
        FROM sys_sessions
        WHERE started_at >= ?
        GROUP BY project
        ORDER BY SUM(message_count) DESC
    """, (since,)).fetchall()
    return rows


def get_previous_week_stats(conn, since, before):
    """Previous period stats for comparison."""
    rows = conn.execute("""
        SELECT COUNT(*) as sessions, SUM(message_count) as messages
        FROM sys_sessions
        WHERE started_at >= ? AND started_at < ?
    """, (since, before)).fetchall()
    return rows[0] if rows else None


def get_previous_week_decisions(conn, since, before):
    """Decision count for prior period (for trend comparison)."""
    row = conn.execute(
        "SELECT COUNT(*) FROM decisions WHERE created_at >= ? AND created_at < ?",
        (since, before)
    ).fetchone()
    return row[0] if row else 0


def get_per_project_previous_stats(conn, since, before):
    """Per-project session counts for prior period (for trend arrows)."""
    rows = conn.execute("""
        SELECT project, COUNT(*) as sessions
        FROM sys_sessions
        WHERE started_at >= ? AND started_at < ?
        GROUP BY project
    """, (since, before)).fetchall()
    return {r[0]: r[1] for r in rows}


def get_session_summaries(conn, since):
    """Session notes grouped by project, ordered by date."""
    rows = conn.execute("""
        SELECT s.project, s.notes AS summary, s.started_at AS created_at,
               s.message_count, s.started_at
        FROM sys_sessions s
        WHERE s.notes IS NOT NULL AND s.notes != ''
          AND s.started_at >= ?
        ORDER BY s.started_at DESC
    """, (since,)).fetchall()
    return rows


def get_recent_decisions(conn, since):
    """Decisions made during the period."""
    rows = conn.execute("""
        SELECT decision_number, project, description, created_at
        FROM decisions
        WHERE created_at >= ?
        ORDER BY decision_number DESC
    """, (since,)).fetchall()
    return rows


def get_dormant_projects(conn, labels, dormant_days=7):
    """Projects with no activity in dormant_days."""
    dormant = []
    for prefix, label in labels.items():
        row = conn.execute("""
            SELECT MAX(started_at) as last_active, COUNT(*) as total_sessions
            FROM sys_sessions
            WHERE project = ?
        """, (prefix,)).fetchone()

        if not row or row["total_sessions"] == 0:
            continue

        last_active = row["last_active"]
        if not last_active:
            continue

        try:
            last_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
            days_idle = (datetime.now(timezone.utc) - last_dt).days
            if days_idle >= dormant_days:
                dormant.append({
                    "prefix": prefix,
                    "label": label,
                    "days_idle": days_idle,
                    "last_active": last_active[:10],
                    "total_sessions": row["total_sessions"],
                })
        except (ValueError, TypeError):
            continue

    dormant.sort(key=lambda x: x["days_idle"], reverse=True)
    return dormant


def get_brain_totals(conn):
    """Overall brain stats."""
    totals = {}
    totals["sessions"] = conn.execute("SELECT COUNT(*) FROM sys_sessions").fetchone()[0]
    totals["transcripts"] = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
    totals["notes"] = conn.execute(
        "SELECT COUNT(*) FROM sys_sessions WHERE notes IS NOT NULL AND notes != ''"
    ).fetchone()[0]
    totals["decisions"] = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    totals["facts"] = conn.execute("SELECT COUNT(*) FROM brain_facts").fetchone()[0]
    totals["embeddings"] = conn.execute("SELECT COUNT(*) FROM transcript_embeddings").fetchone()[0]
    return totals


def get_inception_stats(conn, labels):
    """Inception-to-date stats per project — the full body of work."""
    projects = []
    for prefix, label in labels.items():
        row = conn.execute("""
            SELECT COUNT(*) as sessions,
                   SUM(message_count) as messages,
                   MIN(started_at) as first_session,
                   MAX(started_at) as last_session
            FROM sys_sessions
            WHERE project = ?
        """, (prefix,)).fetchone()

        if not row or row["sessions"] == 0:
            continue

        decision_count = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE project = ?", (prefix,)
        ).fetchone()[0]

        fact_count = conn.execute(
            "SELECT COUNT(*) FROM facts WHERE project = ?", (prefix,)
        ).fetchone()[0]

        notes_count = conn.execute(
            "SELECT COUNT(*) FROM sys_sessions WHERE project = ? AND notes IS NOT NULL AND notes != ''",
            (prefix,)
        ).fetchone()[0]

        first = (row["first_session"] or "")[:10]
        last = (row["last_session"] or "")[:10]

        # Calculate span in days
        span_days = 0
        if first and last:
            try:
                d1 = datetime.strptime(first, "%Y-%m-%d")
                d2 = datetime.strptime(last, "%Y-%m-%d")
                span_days = (d2 - d1).days + 1
            except ValueError:
                pass

        # Get health and status from project_registry
        reg = conn.execute(
            "SELECT health, status FROM project_registry WHERE prefix = ?", (prefix,)
        ).fetchone()
        health = reg[0] if reg else "green"
        status = reg[1] if reg else "active"

        projects.append({
            "prefix": prefix,
            "label": label,
            "sessions": row["sessions"],
            "messages": row["messages"] or 0,
            "decisions": decision_count,
            "facts": fact_count,
            "notes": notes_count,
            "first_session": first,
            "last_session": last,
            "span_days": span_days,
            "health": health,
            "status": status,
        })

    # Sort: active first (by messages desc), then paused
    projects.sort(key=lambda x: (0 if x["status"] == "active" else 1, -x["messages"]))
    return projects


def get_project_roadmap(conn):
    """Pull roadmap items from facts table (category='roadmap')."""
    rows = conn.execute("""
        SELECT project, key, value
        FROM facts
        WHERE category = 'roadmap'
        ORDER BY project, key
    """).fetchall()

    by_project = {}
    for r in rows:
        proj = r["project"]
        if proj not in by_project:
            by_project[proj] = []
        by_project[proj].append({"key": r["key"], "value": r["value"]})
    return by_project


def get_last_session_notes(conn):
    """Most recent session notes (for 'next steps' context)."""
    row = conn.execute("""
        SELECT session_id, project, notes, started_at
        FROM sys_sessions
        WHERE notes IS NOT NULL AND notes != ''
        ORDER BY started_at DESC LIMIT 1
    """).fetchone()
    return row


def extract_topic_from_summary(summary):
    """Pull the main topic line from an LLM or pure-Python summary."""
    if not summary:
        return "No summary"
    for line in summary.split("\n"):
        line = line.strip()
        # LLM summaries often start with **Session Summary: ...**
        if line.startswith("**Session Summary:"):
            return line.replace("**", "").replace("Session Summary:", "").strip()
        if line.startswith("**Main Topic"):
            continue
        if line.startswith("Topic:"):
            return line[6:].strip()
    # Fallback: first non-empty, non-header line
    for line in summary.split("\n"):
        line = line.strip()
        if line and not line.startswith("Session:") and not line.startswith("Project:") \
                and not line.startswith("Time:") and not line.startswith("**"):
            return line[:120]
    return "No summary"


# ---------------------------------------------------------------------------
# Email formatting
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# HTML email foundation — all inline styles (Gmail web strips <style> blocks)
# Per email-digest-design-spec.md section 5
# ---------------------------------------------------------------------------

FONT = "Arial,Helvetica,sans-serif"

# Inline style constants — used directly on elements, NOT in a <style> block
S_BODY = f"margin:0; padding:0; background-color:#f5f5f5; font-family:{FONT}; color:#1a1a1a;"
S_CONTAINER = f"max-width:600px; margin:0 auto; background-color:#ffffff; padding:30px; font-family:{FONT};"
S_H1 = f"color:#2d3748; border-bottom:3px solid #4a90d9; padding-bottom:12px; font-size:22px; margin-top:0; font-family:{FONT};"
S_H2 = f"color:#2d3748; border-bottom:1px solid #e2e8f0; padding-bottom:8px; font-size:16px; margin-top:28px; font-family:{FONT};"
S_TABLE = "border-collapse:collapse; width:100%; margin:12px 0;"
S_TH = f"background:#4a90d9; color:#fff; padding:8px 12px; text-align:left; font-size:13px; font-family:{FONT};"
S_TD = f"padding:7px 12px; border-bottom:1px solid #e2e8f0; font-size:13px; font-family:{FONT};"
S_TD_EVEN = f"padding:7px 12px; border-bottom:1px solid #e2e8f0; font-size:13px; background:#f7fafc; font-family:{FONT};"
S_ALERT = "background:#fff5f5; border-left:4px solid #e53e3e; padding:12px 16px; margin:12px 0; font-size:13px;"
S_ALERT_TITLE = "color:#e53e3e; font-weight:600; margin-bottom:4px;"
S_METRIC = "display:inline-block; background:#ebf4ff; border-radius:6px; padding:10px 16px; margin:4px; text-align:center; min-width:80px;"
S_METRIC_VAL = "font-size:22px; font-weight:700; color:#2b6cb0;"
S_METRIC_LBL = "font-size:11px; color:#718096; text-transform:uppercase;"
S_SUMMARY_ITEM = "margin:8px 0; padding:8px 12px; background:#f7fafc; border-radius:4px; font-size:13px;"
S_SUMMARY_DATE = "color:#718096; font-size:11px;"
S_PROJ_BADGE = "display:inline-block; background:#4a90d9; color:#fff; padding:1px 6px; border-radius:3px; font-size:11px; font-weight:600;"
S_DECISION = "margin:6px 0; padding:6px 0; border-bottom:1px solid #f0f0f0; font-size:13px;"
S_DECISION_NUM = "font-weight:700; color:#4a90d9;"
S_FOOTER = "margin-top:30px; padding-top:16px; border-top:1px solid #e2e8f0; color:#a0aec0; font-size:11px; text-align:center;"
S_TREND_UP = "color:#38a169;"
S_TREND_DOWN = "color:#e53e3e;"
S_TREND_FLAT = "color:#718096;"


def build_email_wrapper(title, preheader, content):
    """Wrap email content in a safe HTML skeleton per design spec section 5.

    - Proper DOCTYPE with xmlns for Outlook
    - MSO conditional table wrapper for 600px max-width
    - color-scheme meta for dark mode
    - Hidden preheader div for inbox preview
    - ALL styles inline — no <style> block (Gmail web strips it)
    """
    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{title}</title>
<!--[if mso]>
<noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
<![endif]-->
</head>
<body style="{S_BODY}">
<div style="display:none; max-height:0; overflow:hidden; mso-hide:all;">{preheader}</div>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f5f5f5;">
<tr><td align="center" style="padding:20px 10px;">
<!--[if mso]><table cellpadding="0" cellspacing="0" border="0" width="600"><tr><td><![endif]-->
<div style="{S_CONTAINER}">
{content}
</div>
<!--[if mso]></td></tr></table><![endif]-->
</td></tr></table>
</body></html>"""


def format_trend(current, previous):
    """Format a comparison arrow with inline styles (no CSS classes)."""
    if previous is None or previous == 0:
        return ""
    diff = current - previous
    pct = (diff / previous) * 100 if previous else 0
    if diff > 0:
        return f' <span style="{S_TREND_UP}">+{diff} ({pct:+.0f}%)</span>'
    elif diff < 0:
        return f' <span style="{S_TREND_DOWN}">{diff} ({pct:+.0f}%)</span>'
    return f' <span style="{S_TREND_FLAT}">(unchanged)</span>'


def build_email_html(conn, days, stats, prev_stats, summaries, decisions,
                     dormant, totals, labels, last_notes, inception, roadmap):
    """Build the weekly digest HTML — BLUF first, project intelligence throughout.

    Section order per design spec section 3:
    1. Executive Summary BLUF (the "forwardable paragraph")
    2. Week-over-Week Trend Table
    3. Project Portfolio Table (with RAG, status, summary context)
    4. Top Accomplishments (3-5 bullets from session notes)
    5. Dormant Alerts (amber, conditional)
    6. Decisions Made
    7. Last Session Notes
    8. On Deck / Roadmap
    9. Brain Stats
    10. Inception-to-Date (reference, at bottom)
    11. Footer (with forward nudge)
    """
    now = datetime.now()
    period_start = now - timedelta(days=days)

    total_sessions = sum(r["sessions"] for r in stats) if stats else 0
    total_msgs = sum(r["messages"] or 0 for r in stats) if stats else 0
    active_projects = len(stats)
    prev_sessions = prev_stats["sessions"] if prev_stats else 0
    prev_msgs = prev_stats["messages"] if prev_stats else 0
    num_decisions = len(decisions) if decisions else 0

    # Compute previous week decisions + per-project previous stats for trends
    prev_since = (now - timedelta(days=days * 2)).isoformat()
    prev_before = (now - timedelta(days=days)).isoformat()
    prev_decisions = get_previous_week_decisions(conn, prev_since, prev_before)
    prev_project_stats = get_per_project_previous_stats(conn, prev_since, prev_before)

    # Top project by sessions
    top_project = max(stats, key=lambda r: r["sessions"]) if stats else None
    top_label = labels.get(top_project["project"], top_project["project"]) if top_project else "none"

    # Dormant project names for alert sentence
    dormant_names = [d["label"] for d in dormant] if dormant else []

    # --- Executive Summary BLUF ---
    delta_pct = round(((total_sessions - prev_sessions) / prev_sessions * 100) if prev_sessions else 0)
    delta_word = "up" if delta_pct > 0 else "down" if delta_pct < 0 else "flat"
    exec_summary = f"This week you logged {total_sessions} sessions across {active_projects} project{'s' if active_projects != 1 else ''}"
    if prev_sessions:
        exec_summary += f" ({delta_word} {abs(delta_pct)}% from last week)"
    exec_summary += f". Most active: {top_label}"
    if top_project:
        exec_summary += f" ({top_project['sessions']} sessions)"
    exec_summary += "."
    if dormant_names:
        exec_summary += f" Alert: {', '.join(dormant_names[:3])} dormant."
    elif total_sessions > 0:
        exec_summary += " All projects on track."

    # Subject line per spec: [Weekly] {range}: {headline} across {N} projects
    title = f"Brain Digest — {period_start.strftime('%b %d')} to {now.strftime('%b %d')}"
    preheader = exec_summary[:100]

    content = f'<h1 style="{S_H1}">{title}</h1>'

    # ── 1. Executive Summary BLUF ──
    content += f'<p style="font-size:15px; line-height:1.5; margin:8px 0 20px 0;">{exec_summary}</p>'

    # ── 2. Week-over-Week Trend Table ──
    content += f'<table style="{S_TABLE}">'
    content += f'<tr><th style="{S_TH}">Metric</th><th style="{S_TH}">This Week</th><th style="{S_TH}">Last Week</th><th style="{S_TH}">Change</th></tr>'
    trend_rows = [
        ("Sessions", total_sessions, prev_sessions or 0),
        ("Messages", total_msgs, prev_msgs or 0),
        ("Decisions", num_decisions, prev_decisions),
    ]
    for i, (metric, current, previous) in enumerate(trend_rows):
        td = S_TD_EVEN if i % 2 == 1 else S_TD
        if previous and previous > 0:
            d_pct = round((current - previous) / previous * 100)
            if d_pct > 0:
                delta_html = f'<span style="{S_TREND_UP}">+{d_pct}%</span>'
            elif d_pct < 0:
                delta_html = f'<span style="{S_TREND_DOWN}">{d_pct}%</span>'
            else:
                delta_html = f'<span style="{S_TREND_FLAT}">—</span>'
        else:
            delta_html = f'<span style="{S_TREND_FLAT}">—</span>'
        cur_fmt = f"{current:,}" if isinstance(current, int) and current > 999 else str(current)
        prev_fmt = f"{previous:,}" if isinstance(previous, int) and previous > 999 else str(previous)
        content += f'<tr><td style="{td}"><strong>{metric}</strong></td><td style="{td}">{cur_fmt}</td><td style="{td}">{prev_fmt}</td><td style="{td}">{delta_html}</td></tr>'
    content += '</table>'

    # ── 3. Project Portfolio Table (with RAG, status, context) ──
    if stats:
        content += f'<h2 style="{S_H2}">Project Portfolio</h2>'
        content += f'<table style="{S_TABLE}"><tr>'
        for hdr in ["", "Project", "Sessions", "Messages", "Trend"]:
            content += f'<th style="{S_TH}">{hdr}</th>'
        content += '</tr>'

        # Sort: active with sessions first, then others
        sorted_stats = sorted(stats, key=lambda r: r["sessions"], reverse=True)

        for i, r in enumerate(sorted_stats):
            proj = r["project"]
            label = labels.get(proj, proj)
            td = S_TD_EVEN if i % 2 == 1 else S_TD
            ctx = get_project_context(conn, proj)
            health = ctx["health"] if ctx else "green"
            status = ctx["status"] if ctx else "active"
            summary_text = ctx["summary"] if ctx else None

            # RAG cell — inline background-color, NOT emoji
            bg, fg, rag_label = RAG_COLORS.get(health, RAG_COLORS["green"])
            rag_td = f'padding:7px 4px; background-color:{bg}; text-align:center; width:8px; border-bottom:1px solid #e2e8f0;'

            # First sentence of summary for context
            context_line = ""
            if summary_text:
                summary_section = extract_section(summary_text, "summary")
                if summary_section:
                    first_sentence = summary_section.split(".")[0] + "." if "." in summary_section else summary_section[:80]
                    context_line = f'<br><span style="color:#718096; font-size:11px;">{first_sentence[:100]}</span>'

            # Trend arrow vs last week
            prev_proj_sessions = prev_project_stats.get(proj, 0)
            if prev_proj_sessions > 0:
                t_pct = round((r["sessions"] - prev_proj_sessions) / prev_proj_sessions * 100)
                if t_pct > 10:
                    trend_html = f'<span style="{S_TREND_UP}">↑{t_pct}%</span>'
                elif t_pct < -10:
                    trend_html = f'<span style="{S_TREND_DOWN}">↓{abs(t_pct)}%</span>'
                else:
                    trend_html = f'<span style="{S_TREND_FLAT}">—</span>'
            elif r["sessions"] > 0:
                trend_html = f'<span style="{S_TREND_UP}">new</span>'
            else:
                trend_html = f'<span style="{S_TREND_FLAT}">—</span>'

            # Status badge for paused projects
            status_badge = ""
            if status == "paused":
                status_badge = f' <span style="background:#F59E0B; color:#fff; padding:1px 5px; border-radius:3px; font-size:10px;">PAUSED</span>'

            content += f'<tr><td style="{rag_td}"></td>'
            content += f'<td style="{td}"><strong>{label}</strong>{status_badge}{context_line}</td>'
            content += f'<td style="{td}">{r["sessions"]}</td>'
            content += f'<td style="{td}">{r["messages"] or 0:,}</td>'
            content += f'<td style="{td}">{trend_html}</td></tr>'
        content += '</table>'
    else:
        content += '<p style="color:#718096;">No sessions this period.</p>'

    # ── 4. Top Accomplishments (from session notes "What Was Done") ──
    accomplishments = []
    for s in (summaries or []):
        done_section = extract_section(s["summary"], "what was done")
        if done_section:
            for line in done_section.split("\n"):
                line = line.strip().lstrip("- ").lstrip("* ")
                if line and len(line) > 20:
                    proj = s["project"] or "oth"
                    accomplishments.append((proj, line[:200]))
    if accomplishments:
        content += f'<h2 style="{S_H2}">Top Accomplishments</h2>'
        for proj, acc in accomplishments[:5]:
            content += f'<div style="margin:4px 0; padding:4px 0; font-size:13px;">'
            content += f'<span style="{S_PROJ_BADGE}">{proj}</span> {acc}</div>'

    # ── 5. Dormant Alerts (amber, not red — dormant ≠ blocked) ──
    S_DORMANT = "background:#FFF3CD; border-left:4px solid #F59E0B; padding:12px 16px; margin:8px 0; font-size:13px;"
    S_DORMANT_TITLE = "color:#92400E; font-weight:600; margin-bottom:4px;"
    if dormant:
        content += f'<h2 style="{S_H2}">Dormant Projects</h2>'
        for d in dormant:
            content += f'<div style="{S_DORMANT}"><div style="{S_DORMANT_TITLE}">{d["label"]} ({d["prefix"]})</div>'
            content += f'No activity in <strong>{d["days_idle"]} days</strong>. '
            content += f'Last active: {d["last_active"]}.'
            # Include next steps from project summary if available
            ctx = get_project_context(conn, d["prefix"])
            if ctx and ctx["summary"]:
                next_steps = extract_section(ctx["summary"], "next steps")
                if next_steps:
                    first_step = next_steps.split("\n")[0].strip().lstrip("- ").lstrip("1. ")
                    content += f'<br><span style="color:#92400E;">Next: {first_step[:120]}</span>'
            content += '</div>'

    # ── 6. Decisions ──
    if decisions:
        content += f'<h2 style="{S_H2}">Decisions Made</h2>'
        for d in decisions:
            proj = d["project"] or "?"
            content += f'<div style="{S_DECISION}"><span style="{S_DECISION_NUM}">#{d["decision_number"]}</span> '
            content += f'<span style="{S_PROJ_BADGE}">{proj}</span> '
            content += f'{d["description"][:200]}</div>'

    # ── 7. Last Session Notes ──
    if last_notes and last_notes["notes"]:
        content += f'<h2 style="{S_H2}">Last Session Notes</h2>'
        date_str = (last_notes["started_at"] or "")[:10]
        proj = last_notes["project"] or "?"
        notes_html = last_notes["notes"].replace("\n", "<br>")
        content += f'<div style="{S_SUMMARY_ITEM}"><span style="{S_SUMMARY_DATE}">{date_str}</span> '
        content += f'<span style="{S_PROJ_BADGE}">{proj}</span><br>{notes_html}</div>'

    # ── 8. Roadmap / On Deck ──
    if roadmap:
        content += f'<h2 style="{S_H2}">On Deck — Planned Next</h2>'
        for proj, items in roadmap.items():
            proj_label = labels.get(proj, proj)
            content += f'<div style="margin-top:10px;"><span style="{S_PROJ_BADGE}">{proj}</span> <strong>{proj_label}</strong></div>'
            for item in items:
                content += f'<div style="{S_SUMMARY_ITEM}">{item["value"]}</div>'

    # ── 9. Brain Stats ──
    content += f'<h2 style="{S_H2}">Brain Stats</h2>'
    content += '<div style="text-align:center;">'
    for val, lbl in [(totals["sessions"], "Total Sessions"), (f'{totals["transcripts"]:,}', "Transcripts"),
                     (totals["decisions"], "Decisions"), (f'{totals["embeddings"]:,}', "Embeddings")]:
        content += f'<div style="{S_METRIC}"><div style="{S_METRIC_VAL}">{val}</div><div style="{S_METRIC_LBL}">{lbl}</div></div>'
    content += '</div>'

    # ── 10. Inception-to-Date (reference data, bottom — with health + status) ──
    if inception:
        content += f'<h2 style="{S_H2}">Portfolio — Inception to Date</h2>'
        content += f'<table style="{S_TABLE}"><tr>'
        for hdr in ["", "Project", "Status", "Sessions", "Messages", "Decisions", "Since", "Span"]:
            content += f'<th style="{S_TH}">{hdr}</th>'
        content += '</tr>'
        total_itd_sessions = 0
        total_itd_msgs = 0
        total_itd_decisions = 0
        for i, p in enumerate(inception):
            total_itd_sessions += p["sessions"]
            total_itd_msgs += p["messages"]
            total_itd_decisions += p["decisions"]
            span = f'{p["span_days"]}d' if p["span_days"] else "—"
            td = S_TD_EVEN if i % 2 == 1 else S_TD

            # RAG cell
            bg, fg, rag_label = RAG_COLORS.get(p.get("health", "green"), RAG_COLORS["green"])
            rag_td = f'padding:7px 4px; background-color:{bg}; text-align:center; width:8px; border-bottom:1px solid #e2e8f0;'

            # Status badge
            status = p.get("status", "active")
            if status == "paused":
                status_html = f'<span style="background:#F59E0B; color:#fff; padding:1px 5px; border-radius:3px; font-size:10px;">PAUSED</span>'
            else:
                status_html = f'<span style="color:#22C55E; font-size:11px;">Active</span>'

            content += f'<tr><td style="{rag_td}"></td>'
            content += f'<td style="{td}"><strong>{p["label"]}</strong> ({p["prefix"]})</td>'
            content += f'<td style="{td}">{status_html}</td>'
            content += f'<td style="{td}">{p["sessions"]}</td>'
            content += f'<td style="{td}">{p["messages"]:,}</td>'
            content += f'<td style="{td}">{p["decisions"]}</td>'
            content += f'<td style="{td}">{p["first_session"]}</td>'
            content += f'<td style="{td}">{span}</td></tr>'
        content += f'<tr style="font-weight:700; background:#ebf4ff;">'
        content += f'<td style="{S_TD}"></td><td style="{S_TD}">TOTAL</td><td style="{S_TD}"></td>'
        content += f'<td style="{S_TD}">{total_itd_sessions}</td><td style="{S_TD}">{total_itd_msgs:,}</td>'
        content += f'<td style="{S_TD}">{total_itd_decisions}</td><td style="{S_TD}" colspan="2"></td></tr>'
        content += '</table>'

    # ── 11. Footer (with forward nudge) ──
    content += f'<div style="{S_FOOTER}">'
    content += f'Generated by claude-brain v0.1 &middot; {now.strftime("%Y-%m-%d %H:%M")} &middot; Local data only, zero tokens used<br>'
    content += 'This report is designed to be forwarded to stakeholders.</div>'

    return build_email_wrapper(title, preheader, content)


def extract_section(text, section_name):
    """Pull a named section (## Section Name) from notes or summary text."""
    if not text:
        return None
    lines = text.split("\n")
    capture = False
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith(f"## {section_name.lower()}") or \
           stripped.lower() == f"{section_name.lower()}:" or \
           stripped.lower().startswith(f"{section_name.lower()}:"):
            capture = True
            continue
        if capture:
            if stripped.startswith("##") or stripped.startswith("# "):
                break
            if stripped:
                result.append(stripped)
    return "\n".join(result) if result else None


def get_project_context(conn, prefix):
    """Get project summary, health, and status from project_registry."""
    row = conn.execute(
        "SELECT summary, health, status FROM project_registry WHERE prefix = ?",
        (prefix,)
    ).fetchone()
    if not row:
        return None
    return {"summary": row[0], "health": row[1], "status": row[2]}


def get_last_notes_per_project(conn, since):
    """Get the most recent session notes for each project active in the period."""
    rows = conn.execute("""
        SELECT project, notes, started_at, session_id
        FROM sys_sessions
        WHERE notes IS NOT NULL AND notes != ''
          AND started_at >= ?
        ORDER BY started_at DESC
    """, (since,)).fetchall()
    # Keep only the most recent per project
    by_project = {}
    for proj, notes, started, sid in rows:
        if proj not in by_project:
            by_project[proj] = {"notes": notes, "started_at": started, "session_id": sid}
    return by_project


RAG_COLORS = {
    "green": ("#22C55E", "#FFFFFF", "ON TRACK"),
    "yellow": ("#F59E0B", "#FFFFFF", "AT RISK"),
    "red": ("#EF4444", "#FFFFFF", "BLOCKED"),
}


def rag_badge_html(health):
    """Inline RAG badge using background-color on td (not emoji — per design spec)."""
    bg, fg, label = RAG_COLORS.get(health or "green", RAG_COLORS["green"])
    return (f'<span style="display:inline-block; background-color:{bg}; color:{fg}; '
            f'font-weight:bold; padding:2px 10px; border-radius:3px; font-size:11px; '
            f'letter-spacing:0.5px;">{label}</span>')


def build_daily_subject(stats, summaries, decisions):
    """Dynamic subject line — always includes a variable per design spec."""
    total_sessions = sum(r["sessions"] for r in stats) if stats else 0
    total_msgs = sum(r["messages"] or 0 for r in stats) if stats else 0
    num_decisions = len(decisions) if decisions else 0
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%b %d")

    if total_sessions == 0:
        return f"[brain] Daily: Quiet day — no sessions | {date_str}"
    parts = [f"{total_sessions} sessions"]
    if total_msgs:
        parts.append(f"{total_msgs:,} msgs")
    if num_decisions:
        parts.append(f"{num_decisions} decisions")
    return f"[brain] Daily: {', '.join(parts)} | {date_str}"


def build_daily_html(conn, stats, summaries, decisions, labels, since):
    """Build daily standup email — BLUF methodology, per-project structure.

    Design spec: email-digest-design-spec.md
    Key principle: answer "What should I DO today?" in the first 3 lines.

    Structure:
    1. BLUF summary sentence
    2. Per-project blocks (health + next steps + blockers + yesterday's work)
    3. Decisions (if any)
    4. Quiet projects (active but no sessions yesterday)
    5. Metrics (small, bottom)
    """
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    total_sessions = sum(r["sessions"] for r in stats) if stats else 0
    total_msgs = sum(r["messages"] or 0 for r in stats) if stats else 0
    is_quiet = total_sessions == 0

    # Gather per-project context
    project_notes = get_last_notes_per_project(conn, since)
    active_projects_in_period = set(r["project"] for r in stats)

    # Get ALL active projects for quiet project detection
    all_active = conn.execute(
        "SELECT prefix, label FROM project_registry WHERE status = 'active'"
    ).fetchall()
    all_active_prefixes = {r[0]: r[1] for r in all_active}

    title = f"Daily Standup — {yesterday.strftime('%A, %b %d')}"
    preheader_parts = []
    if not is_quiet:
        preheader_parts.append(f"{total_sessions} sessions, {total_msgs:,} msgs")
    else:
        preheader_parts.append("Quiet day — no sessions")

    html = f'<h1 style="{S_H1}">{title}</h1>'

    # ── Section 1: BLUF summary (the ONE thing to know) ──
    if is_quiet:
        html += '<p style="font-size:15px; color:#718096; margin:8px 0 20px 0;">'
        html += 'No AI sessions recorded yesterday. Here\'s where your projects stand:</p>'
    else:
        project_list = ", ".join(labels.get(r["project"], r["project"]) for r in stats)
        html += f'<p style="font-size:15px; margin:8px 0 20px 0;">'
        html += f'<strong>{total_sessions} session{"s" if total_sessions != 1 else ""}</strong> '
        html += f'across <strong>{len(stats)} project{"s" if len(stats) != 1 else ""}</strong> yesterday '
        html += f'({project_list}) with {total_msgs:,} messages exchanged.'
        if decisions:
            html += f' {len(decisions)} decision{"s" if len(decisions) != 1 else ""} made.'
        html += '</p>'

    # ── Section 2: Per-project blocks ──
    # Active projects first (had sessions), then quiet projects
    projects_to_show = []
    for r in stats:
        projects_to_show.append(r["project"])

    for proj in projects_to_show:
        proj_label = labels.get(proj, proj)
        ctx = get_project_context(conn, proj)
        health = ctx["health"] if ctx else "green"
        proj_summary = ctx["summary"] if ctx else None

        # Project header with RAG badge
        html += f'<div style="margin:20px 0 8px 0; padding-bottom:6px; border-bottom:2px solid #e2e8f0;">'
        html += f'{rag_badge_html(health)} '
        html += f'<strong style="font-size:15px; color:#2d3748;">{proj_label}</strong>'
        html += '</div>'

        # Pick Up Here — from session notes "Next Step" or project summary "Next Steps"
        next_step = None
        if proj in project_notes:
            next_step = extract_section(project_notes[proj]["notes"], "next step")
            if not next_step:
                next_step = extract_section(project_notes[proj]["notes"], "next steps")
        if not next_step and proj_summary:
            next_step = extract_section(proj_summary, "next steps")
        if next_step:
            html += '<div style="background:#ebf4ff; border-left:4px solid #4a90d9; padding:10px 14px; margin:6px 0; font-size:13px;">'
            html += '<strong style="color:#2b6cb0;">Pick Up Here:</strong> '
            # Show first 2-3 lines only
            step_lines = [l.strip() for l in next_step.split("\n") if l.strip()][:3]
            html += "<br>".join(step_lines)
            html += '</div>'

        # Blockers — from session notes or project summary "Risks & Blockers"
        blockers = None
        if proj in project_notes:
            blockers = extract_section(project_notes[proj]["notes"], "blockers")
        if not blockers and proj_summary:
            blockers = extract_section(proj_summary, "risks & blockers")
        if blockers and blockers.lower() not in ("none", "none.", "no blockers", "no blockers."):
            html += '<div style="background:#fff5f5; border-left:4px solid #e53e3e; padding:10px 14px; margin:6px 0; font-size:13px;">'
            html += '<strong style="color:#e53e3e;">Blockers:</strong> '
            blocker_lines = [l.strip() for l in blockers.split("\n") if l.strip()][:3]
            html += "<br>".join(blocker_lines)
            html += '</div>'

        # In Progress — from project summary
        in_progress = extract_section(proj_summary, "in progress") if proj_summary else None
        if in_progress:
            progress_lines = [l.strip() for l in in_progress.split("\n") if l.strip()][:3]
            html += '<div style="margin:6px 0; font-size:13px; color:#4a5568;">'
            html += '<strong>In Progress:</strong> '
            html += "<br>".join(progress_lines)
            html += '</div>'

        # Yesterday's sessions — brief topic bullets
        proj_sessions = [s for s in summaries if s["project"] == proj]
        if proj_sessions:
            html += '<div style="margin:6px 0; font-size:12px; color:#718096;">'
            html += f'<strong>Yesterday ({len(proj_sessions)} session{"s" if len(proj_sessions) != 1 else ""}):</strong> '
            topics = [extract_topic_from_summary(s["summary"]) for s in proj_sessions[:3]]
            html += " · ".join(topics)
            html += '</div>'

    # ── Section 3: Decisions (only if any) ──
    if decisions:
        html += '<h2 style="font-size:14px; margin-top:24px;">Decisions Made</h2>'
        for d in decisions:
            proj = d["project"] or "?"
            html += f'<div style="margin:4px 0; padding:4px 0; border-bottom:1px solid #f0f0f0; font-size:13px;">'
            html += f'<strong style="color:#4a90d9;">#{d["decision_number"]}</strong> '
            html += f'<span style="display:inline-block; background:#4a90d9; color:#fff; padding:1px 5px; border-radius:3px; font-size:10px;">{proj}</span> '
            html += f'{d["description"][:180]}</div>'

    # ── Section 4: Quiet projects (active but no sessions yesterday) ──
    quiet_projects = [p for p in all_active_prefixes if p not in active_projects_in_period]
    # Only show quiet projects that have actual sessions (not empty placeholders)
    if quiet_projects:
        real_quiet = []
        for qp in quiet_projects:
            row = conn.execute(
                "SELECT MAX(started_at) FROM sys_sessions WHERE project = ?", (qp,)
            ).fetchone()
            if row and row[0]:
                last_dt = row[0][:10]
                real_quiet.append((qp, all_active_prefixes[qp], last_dt))
        if real_quiet:
            html += '<h2 style="font-size:14px; margin-top:24px;">No Activity Yesterday</h2>'
            for qp, qlabel, qlast in real_quiet:
                html += f'<div style="margin:4px 0; font-size:12px; color:#a0aec0;">'
                html += f'<strong>{qlabel}</strong> — last session {qlast}</div>'

    # ── Section 5: Metrics (small, bottom — least important) ──
    if not is_quiet:
        html += '<div style="text-align:center; margin:24px 0 8px 0;">'
        for val, lbl in [(total_sessions, "Sessions"), (f"{total_msgs:,}", "Messages"), (len(stats), "Projects")]:
            html += f'<div style="display:inline-block; background:#f7fafc; border-radius:6px; padding:6px 12px; margin:3px; text-align:center;">'
            html += f'<div style="font-size:16px; font-weight:700; color:#2b6cb0;">{val}</div>'
            html += f'<div style="font-size:10px; color:#718096; text-transform:uppercase;">{lbl}</div></div>'
        html += '</div>'

    # ── Footer (minimal per Postmark frequency rule) ──
    html += f'<div style="{S_FOOTER}">'
    html += f'claude-brain &middot; {now.strftime("%Y-%m-%d %H:%M")} &middot; Local data only</div>'

    preheader = ". ".join(preheader_parts)
    return build_email_wrapper(title, preheader, html)


def build_test_html():
    """Minimal test email to verify SMTP works."""
    now = datetime.now()
    content = f'<h1 style="{S_H1}">Brain Digest &mdash; Test Email</h1>'
    content += '<p>If you\'re reading this, email delivery is working.</p>'
    content += '<div style="text-align:center; margin:16px 0;">'
    for lbl in ["SMTP", "Auth", "Delivery"]:
        content += f'<div style="{S_METRIC}"><div style="{S_METRIC_VAL}">OK</div><div style="{S_METRIC_LBL}">{lbl}</div></div>'
    content += '</div>'
    content += f'<div style="{S_FOOTER}">Generated by claude-brain v0.1 &middot; {now.strftime("%Y-%m-%d %H:%M")}</div>'
    return build_email_wrapper("Brain Digest — Test", "Testing email delivery", content)


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

def send_email(config, subject, html_body, dry_run=False):
    """Send HTML email via Gmail SMTP."""
    email_cfg = config.get("email", {})
    from_addr = email_cfg.get("from_address", "")
    to_addr = email_cfg.get("to_address", from_addr)
    app_password = email_cfg.get("gmail_app_password", "")

    if not from_addr or not app_password:
        print("ERROR: email.from_address and email.gmail_app_password required in config.yaml",
              file=sys.stderr)
        sys.exit(1)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Brain Digest <{from_addr}>"
    msg["To"] = to_addr

    # Plain text fallback
    plain = "Your weekly brain digest is ready. View this email in an HTML-capable client."
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    if dry_run:
        print(f"Subject: {subject}")
        print(f"From: {from_addr}")
        print(f"To: {to_addr}")
        print(f"HTML length: {len(html_body)} chars")
        print("---")
        print(html_body)
        return True

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(from_addr, app_password)
            server.send_message(msg)
        print(f"Digest sent to {to_addr}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"ERROR: Gmail authentication failed: {e}", file=sys.stderr)
        print("Check your app password in config.yaml (email.gmail_app_password)", file=sys.stderr)
        return False
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Brain email digest")
    parser.add_argument("--days", type=int, default=7, help="Lookback period in days (default: 7)")
    parser.add_argument("--daily", action="store_true", help="Send compact daily standup (overrides --days to 1)")
    parser.add_argument("--dry-run", action="store_true", help="Print email to stdout, don't send")
    parser.add_argument("--test", action="store_true", help="Send a short test email")
    args = parser.parse_args()

    if args.daily:
        args.days = 1

    config = load_config()

    if args.test:
        html = build_test_html()
        subject = "Brain Digest — Test"
        ok = send_email(config, subject, html, dry_run=args.dry_run)
        sys.exit(0 if ok else 1)

    conn = get_db(config)
    try:
        now = datetime.now(timezone.utc)
        since = (now - timedelta(days=args.days)).isoformat()

        labels = get_project_labels(conn)
        stats = get_weekly_stats(conn, since)
        summaries = get_session_summaries(conn, since)
        decisions = get_recent_decisions(conn, since)
        last_notes = get_last_session_notes(conn)

        if args.daily:
            # -- Daily standup: BLUF first, per-project, actionable
            subject = build_daily_subject(stats, summaries, decisions)
            html = build_daily_html(conn, stats, summaries, decisions, labels, since)
        else:
            # -- Weekly digest: full portfolio view with project intelligence
            prev_since = (now - timedelta(days=args.days * 2)).isoformat()
            prev_before = since
            prev_stats = get_previous_week_stats(conn, prev_since, prev_before)
            dormant = get_dormant_projects(conn, labels, dormant_days=3)
            totals = get_brain_totals(conn)
            inception = get_inception_stats(conn, labels)
            roadmap = get_project_roadmap(conn)

            # Dynamic subject per spec section 6
            total_s = sum(r["sessions"] for r in stats) if stats else 0
            active_p = len(stats)
            period_start = now - timedelta(days=args.days)
            subject = f"[Weekly] {period_start.strftime('%b %d')}-{now.strftime('%b %d')}: {total_s} sessions across {active_p} projects"
            html = build_email_html(
                conn, args.days, stats, prev_stats, summaries, decisions,
                dormant, totals, labels, last_notes, inception, roadmap,
            )

        ok = send_email(config, subject, html, dry_run=args.dry_run)
        sys.exit(0 if ok else 1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
