# Email Digest Design Specification

## AI Coding Session Activity - Three Template System

**Version:** 1.0
**Date:** 2026-03-12
**Purpose:** Production-ready design spec for automated email digests in an open-source developer tool that tracks AI coding session activity.

---

## Table of Contents

1. [Design Philosophy & Principles](#1-design-philosophy--principles)
2. [Template 1: Daily Standup](#2-template-1-daily-standup)
3. [Template 2: Weekly Digest](#3-template-2-weekly-digest)
4. [Template 3: Project Deep Dive](#4-template-3-project-deep-dive)
5. [HTML Email Technical Constraints](#5-html-email-technical-constraints)
6. [Subject Line Formulas](#6-subject-line-formulas)
7. [Psychology of Status Email Engagement](#7-psychology-of-status-email-engagement)
8. [10 Email Use Case Ideas for AI Memory Systems](#8-10-email-use-case-ideas-for-ai-memory-systems)

---

## 1. Design Philosophy & Principles

### BLUF (Bottom Line Up Front)

Every template in this system follows BLUF methodology, originating from U.S. military communication doctrine (Army Regulation 25-50). The core principle: state the conclusion, recommendation, or key status in the first line - then provide supporting context below.

**Implementation rules:**

- The hero section of every email answers: "What is the ONE thing the reader needs to know?"
- Subject line IS the BLUF - it must convey the core status without opening the email
- Preview text (preheader) reinforces the BLUF - never repeats the subject line
- Body content follows the inverted pyramid: most important → least important
- Readers who stop after the first 3 lines should still understand the state of the world

### Developer Tool Email Design Principles (Drawn from Stripe, GitHub, Linear, Vercel patterns)

| Principle | Implementation |
|---|---|
| **Information density over decoration** | No hero images, no marketing fluff. Data-first layout. |
| **Scannable in < 10 seconds** | F-pattern reading: left-aligned labels, right-aligned values. Monospace for code/numbers. |
| **Single primary CTA** | One button per email. Every other link is secondary (text link, not button). |
| **Light branding** | Logo in header only. No heavy footer chrome. Brand color used sparingly (1 accent color). |
| **Plain-text readable** | Must degrade gracefully. All content understandable in plain-text fallback. |
| **Mobile-first** | 600px max-width. Single column. Touch-target CTAs (min 44x44px). |
| **Frequency-adjusted design** | Daily = minimal chrome. Weekly = moderate structure. Deep dive = full report treatment. |

### Postmark's Frequency Rule

From Postmark's transactional email best practices: the more frequently an email is sent, the less branding and chrome it should carry. Daily notifications should feel like a quick tap on the shoulder. Weekly digests get moderate structure. Monthly/on-demand reports get the full report treatment.

---

## 2. Template 1: Daily Standup

### Purpose

Automated async standup replacement. Tells the developer and their team what happened in the last 24 hours across all AI coding sessions, what's in-progress, and what might be blocked.

### Real-World Pattern Sources

- **Geekbot**: Three-question format (yesterday / today / blockers) posted to Slack. Used by GitHub, Shopify, Airbnb, GitLab. 200K+ users.
- **Range**: Check-ins with mood tracking, icebreakers, and meeting agendas alongside standups.
- **Standuply**: Scrum-focused with optional video/voice responses. Supports retrospectives and sprint ceremonies.
- **DailyBot**: Combines standups with kudos, mood surveys, and wellness checks.
- **Status Hero**: Activity-aware check-ins with blocker tracking and project context.
- **Weekdone**: PPP framework (Plans, Progress, Problems) used internally at Skype.

### Subject Line Formula

```
[Project] Daily: {summary_stat} | {date_short}
```

**Examples:**
- `[myapp] Daily: 14 files changed, 2 sessions | Mar 12`
- `[myapp] Daily: Quiet day - no sessions | Mar 12`
- `[myapp] Daily: 3 blockers flagged | Mar 12`

**Variables:**
- `{project}` - project name or repo shortname
- `{summary_stat}` - the single most important metric (files changed, sessions count, or blocker count)
- `{date_short}` - abbreviated date

**Preheader:** `{top_accomplishment_or_status_phrase}`

### Section Order (with rationale)

| # | Section | Rationale |
|---|---------|-----------|
| 1 | **BLUF Hero** (1-2 sentences) | Immediate status. Reader gets the point without scrolling. Answers "should I care?" |
| 2 | **Key Metrics Bar** (inline stats) | Quantitative snapshot. Numbers are processed faster than prose. |
| 3 | **Completed** (yesterday's done items) | Mirrors classic standup "what did I do yesterday." Satisfies accountability. |
| 4 | **In Progress** (active work) | "What am I doing today." Keeps team aligned on current focus. |
| 5 | **Blockers / Flags** (if any) | Only shown when populated. Red-highlighted. Demands attention last = lingers in memory (recency effect). |
| 6 | **CTA Button** | Single action: "View Full Session Log →" or "Open Dashboard →" |
| 7 | **Footer** (minimal) | Unsubscribe / notification preferences link. No heavy branding. |

### BLUF / Hero Section Spec

**Content:** A single natural-language sentence summarizing the day's AI coding activity.

**Formula:**
```
{user} had {session_count} session(s) across {project_count} project(s) yesterday,
touching {files_changed} files with {net_lines} net lines changed.
```

**Quiet-day variant:**
```
No AI coding sessions were recorded yesterday for {project}.
```

**Examples:**
- "You had 3 sessions across 2 projects yesterday, touching 14 files with +187 / -42 net lines."
- "Quiet day - no AI coding sessions recorded for myapp."

**Visual treatment:** 16px font, bold, dark gray (#1a1a1a) on white. No background color on the hero - let it breathe.

### Key Metrics Bar Spec

Horizontal row of 3-4 metric cards, displayed inline.

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  3 Sessions  │  │  14 Files    │  │  +187 / -42  │  │  0 Blockers  │
│  ↑1 vs avg   │  │  Changed     │  │  Lines       │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

**Implementation:** Use a 4-column table with light gray (#F5F5F5) cell backgrounds, centered text. Each metric has a large number (24px bold) and a label below (12px, muted gray).

**Delta indicators:** Show ↑ or ↓ vs. 7-day rolling average when available. Green for improvement, amber for flat, red for decline.

### Handling "Nothing Happened" (Quiet Day)

This is critical - most tools get this wrong by either skipping the email (breaking habit) or sending an empty shell.

**Strategy:** Always send the daily email to preserve the habit loop. But adapt the content:

1. **BLUF states the quiet explicitly:** "No AI coding sessions recorded yesterday for {project}."
2. **Replace sections 3-5 with a single "Quiet Day" block:**
   - Show last activity date: "Last session: 2 days ago (Mar 10)"
   - Show streak data: "Current quiet streak: 2 days"
   - Optional: Show project health context: "3 open items from last session still unresolved"
3. **CTA changes to:** "Review Last Session →" (not "View Dashboard" - give them somewhere specific to go)
4. **Tone:** Neutral, not judgmental. No "You've been quiet!" gamification unless user opts in.

### Actionability - CTA Design

| Scenario | Primary CTA | Secondary Link |
|---|---|---|
| Normal day | "View Full Session Log →" | "Open in IDE" (deep-link) |
| Blockers flagged | "Review Blockers →" | "View Full Log" |
| Quiet day | "Review Last Session →" | "View Project Dashboard" |

**CTA button spec:** 44px tall minimum, 200px wide, brand accent color, white text, 4px border-radius. Centered.

### Ideal Length

- **Target:** 150-250 words max
- **Screen size:** Should fit in one mobile viewport scroll (< 600px height of content)
- **Scan time:** < 15 seconds
- **Philosophy:** This is a notification, not a report. If someone spends more than 30 seconds reading it, the template has failed.

---

## 3. Template 2: Weekly Digest

### Purpose

Portfolio-level summary. Shows the week's activity across all projects/repos, surfaces trends, flags dormant work, and is designed to be forwardable to a manager or stakeholder.

### Real-World Pattern Sources

- **Weekdone**: PPP methodology (Plans, Progress, Problems). Automatic email reports for team and company. Used at Skype internally. Emphasizes reports that managers "actually have time to read."
- **Status Hero**: Aggregated team activity check-ins with project context and analytics.
- **15Five**: 15-minute weekly check-in that takes 5 minutes to review. Focuses on wins, challenges, and priorities.
- **Friday.com**: Async status updates with goal tracking and weekly review workflows.
- **Range**: Weekly summaries alongside daily check-ins with team sentiment.

### Subject Line Formula

```
[Weekly] {date_range}: {headline_stat} across {project_count} projects
```

**Examples:**
- `[Weekly] Mar 3-9: 47 sessions, +2,841 lines across 3 projects`
- `[Weekly] Mar 3-9: Activity down 34% - 2 projects dormant`
- `[Weekly] Mar 3-9: All green - steady progress on 4 projects`

**Preheader:** `{executive_summary_phrase}`

### Section Order (with rationale)

| # | Section | Rationale |
|---|---------|-----------|
| 1 | **Executive Summary** (BLUF, 2-3 sentences) | The "forwardable paragraph." If a manager reads only this, they know the state of the world. |
| 2 | **Week-over-Week Trend Bar** | Visual comparison. Humans process trends faster than absolute numbers. Answers "are things getting better or worse?" |
| 3 | **Project Portfolio Table** | One row per project. RAG indicator + key metric + trend arrow. This is the "glanceable dashboard." |
| 4 | **Top Accomplishments** (3-5 bullet max) | Highlights wins. Provides "proof of work" for forwarding to leadership. |
| 5 | **Dormant Project Alerts** (conditional) | Only shown when a project has had no activity for 3+ days. Orange/amber treatment. Prevents silent drift. |
| 6 | **Upcoming / Next Week Preview** (optional) | If the system can infer planned work from context, show it. Otherwise, omit. |
| 7 | **CTA Button** | "View Weekly Dashboard →" |
| 8 | **Footer** | Notification preferences. "Forward this email" nudge text. |

### Executive Summary Spec

**Content:** 2-3 sentences that answer:
1. What was the overall activity level? (compared to prior week)
2. Which project had the most activity?
3. Are there any alerts? (dormant projects, declining trends)

**Formula:**
```
This week you logged {session_count} sessions across {project_count} projects
({delta_pct}% {up/down} from last week). Most active: {top_project} ({top_project_files} files changed).
{alert_sentence_if_any}
```

**Examples:**
- "This week you logged 47 sessions across 3 projects (up 12% from last week). Most active: myapp (34 files changed). No alerts."
- "This week you logged 18 sessions across 4 projects (down 34% from last week). Most active: api-service (12 files changed). Alert: frontend and docs have been dormant for 5+ days."

### Week-over-Week Trend Comparison

**Visual: Mini bar chart or comparison row**

```
           This Week    Last Week    Δ
Sessions:     47           42       ↑ 12%
Files:        89           71       ↑ 25%
Lines:     +2,841       +2,104      ↑ 35%
Blockers:      2            5       ↓ 60%  ✓
```

**Implementation:** Table with 4 columns. Use color on the delta column only: green for favorable changes (more activity, fewer blockers), red for unfavorable.

### Project Portfolio Table (Forwardable View)

This is the core of the weekly email. One row per project.

```
┌─────────────────┬────────┬───────────┬──────────┬─────────────┐
│ Project         │ Status │ Sessions  │ Files Δ  │ Trend (7d)  │
├─────────────────┼────────┼───────────┼──────────┼─────────────┤
│ myapp           │  🟢    │    28     │   +54    │   ↑ 15%     │
│ api-service     │  🟡    │    12     │   +22    │   ↓ 8%      │
│ frontend        │  🔴    │     0     │    0     │   dormant   │
│ docs            │  🟡    │     7     │   +13    │   ── flat   │
└─────────────────┴────────┴───────────┴──────────┴─────────────┘
```

**RAG logic for weekly:**
- 🟢 Green: Active this week AND trending up or flat
- 🟡 Amber: Active but trending down, OR low activity relative to project baseline
- 🔴 Red: Zero sessions this week (dormant), OR blocker count > threshold

**Implementation note for HTML email:** Do NOT use emoji circles for RAG. Use small colored `<td>` cells with inline background-color (8px wide column with `background-color: #22C55E` / `#F59E0B` / `#EF4444`). Emoji rendering is inconsistent across email clients.

### Dormant Project Alerts

**Trigger:** Any project with 0 sessions in the past 3+ business days.

**Visual treatment:** Amber (#FFF3CD) background block with left border (#F59E0B, 4px solid).

**Content per alert:**
```
⚠ {project_name} - No activity for {days} days
   Last session: {date} ({summary_of_last_session})
   Open items from last session: {count}
```

### Forwardability Design

The weekly email is explicitly designed to be forwarded to a manager or stakeholder. Design considerations:

1. **Executive summary reads as a standalone paragraph** - no context needed from the rest of the email
2. **Portfolio table is self-contained** - column headers are descriptive, not abbreviated
3. **No internal jargon** - "sessions" not "ctx windows," "files changed" not "diffs"
4. **"Forward this report" text link** in the footer to nudge sharing behavior
5. **Branding is moderate** - professional enough to forward, not so heavy it looks like marketing

### Ideal Length

- **Target:** 300-500 words
- **Screen size:** 1.5-2 mobile viewport scrolls
- **Scan time:** < 30 seconds for executive summary + portfolio table
- **Deep read time:** < 2 minutes for the entire email

---

## 4. Template 3: Project Deep Dive

### Purpose

Single-project status report with full context. Triggered on-demand or on a configurable schedule (weekly/biweekly). Designed for project leads, tech leads, or stakeholders who need comprehensive visibility into one specific project.

### Real-World Pattern Sources

- **Monday.com**: Project status dashboards with timeline views, RAG indicators, and owner attribution.
- **Asana**: Portfolio status reports with milestones, progress percentages, and risk flags.
- **Jira**: Sprint reports, velocity charts, and burndown visualizations in status pages.
- **Linear**: Cycle progress reports with project-level health indicators and issue analytics.

### Subject Line Formula

```
[{project}] Status: {rag_emoji} {rag_word} - {headline_metric} | {date}
```

**Examples:**
- `[myapp] Status: 🟢 On Track - 78% milestone complete | Mar 12`
- `[api-service] Status: 🟡 At Risk - 3 blockers, velocity declining | Mar 12`
- `[frontend] Status: 🔴 Blocked - no activity for 7 days | Mar 12`

**Preheader:** `{one_line_summary_of_project_state}`

### Section Order (with rationale)

| # | Section | Rationale |
|---|---------|-----------|
| 1 | **Project Header + RAG Badge** | Instant visual indicator. The RAG color IS the BLUF. Reader knows health in < 1 second. |
| 2 | **Executive Summary** (BLUF, 2-3 sentences) | Narrative context for the RAG. What specifically is on track / at risk / blocked? |
| 3 | **Health Metrics Dashboard** (4-6 KPIs) | Quantitative evidence supporting the RAG rating. Replaces gut-feel with data. |
| 4 | **Timeline / Milestone Progress** | Shows where the project is relative to plan. Progress bars or milestone checklist. |
| 5 | **Recent Activity Feed** (last 5-7 sessions) | Chronological log of what actually happened. Proves the metrics. |
| 6 | **Risks & Blockers** (structured table) | Dedicated section with owner + severity + age. Demands action by isolating blockers from noise. |
| 7 | **AI Session Insights** (optional) | AI-generated observations: patterns, anomalies, suggestions. Differentiator for an AI-powered tool. |
| 8 | **CTA Button** | "Open Project Dashboard →" or "Address Top Blocker →" |
| 9 | **Footer** | Report frequency settings. Notification preferences. |

### RAG Status Implementation

**Criteria definitions - be explicit and quantitative:**

| Status | Color | Hex | Criteria |
|---|---|---|---|
| **Green** | On Track | `#22C55E` | All milestones on schedule. Blockers = 0 or resolved within 24h. Velocity within 15% of baseline. Activity in last 48h. |
| **Amber** | At Risk | `#F59E0B` | 1+ milestones slipping but recoverable. Blockers exist but have owners. Velocity declining. No activity for 3-5 days. |
| **Red** | Blocked / Off Track | `#EF4444` | Milestone missed. Unresolved blockers > 48h old. Velocity dropped > 30%. No activity for 5+ days. Critical path affected. |

**RAG badge HTML (inline, Outlook-safe):**
```html
<td style="background-color:#22C55E; color:#FFFFFF; font-weight:bold;
    padding:6px 16px; border-radius:4px; font-size:14px; font-family:Arial,sans-serif;">
  ● ON TRACK
</td>
```

**Critical rule:** Never let RAG be manually overridden without leaving an audit trail. If the system says Red but the user reports Green, log the discrepancy.

### Health Metrics Dashboard

**6 KPI cards for single-project health:**

| Metric | What It Measures | Display |
|---|---|---|
| **Sessions (7d)** | Volume of AI coding activity | Count + sparkline or trend arrow |
| **Files Changed (7d)** | Breadth of work | Count + delta vs prior 7d |
| **Net Lines (7d)** | Depth of changes | +additions / -deletions |
| **Avg Session Duration** | Engagement depth | Minutes, with trend |
| **Open Blockers** | Impediments to progress | Count, red if > 0 |
| **Milestone Progress** | % toward next milestone | Progress bar or fraction |

**Layout:** 2x3 grid of metric cards, each with: large number (24px bold), label (12px muted), trend indicator (arrow + color).

### Timeline / Milestone Progress

**Option A: Milestone Checklist**

Best for projects with defined milestones:

```
✅ Phase 1: Auth system          - Completed Mar 1
✅ Phase 2: API endpoints        - Completed Mar 7
🔄 Phase 3: Frontend integration - 60% (target: Mar 15)
⬜ Phase 4: Testing & QA         - Not started (target: Mar 22)
⬜ Phase 5: Deploy               - Not started (target: Mar 29)
```

**Option B: Progress Bar**

Best for continuous work without formal milestones:

```
Overall Progress: ████████████░░░░░░░░ 62%
                  ↑ Was 48% last week
```

**Implementation:** Use table cells with background colors for progress bars. Avoid CSS `width: X%` - Outlook ignores it on non-table elements.

### Risks & Blockers (Structured for Action)

This section must DEMAND action, not just inform. Structure each blocker as an actionable item:

```
┌──────┬────────────────────────────────┬──────────┬─────────┬───────────┐
│ Sev  │ Blocker                        │ Owner    │ Age     │ Status    │
├──────┼────────────────────────────────┼──────────┼─────────┼───────────┤
│ 🔴   │ API rate limit hitting in prod │ @mike    │ 3 days  │ OPEN      │
│ 🟡   │ Flaky test suite on CI         │ @sarah   │ 1 day   │ INVESTIGATING │
│ 🟡   │ Dependency upgrade needed      │ unassigned│ 5 days │ STALE     │
└──────┴────────────────────────────────┴──────────┴─────────┴───────────┘
```

**Design rules for blockers that demand action:**

1. **Severity column is visual** - colored dot, not text
2. **Age column creates urgency** - "3 days" feels more urgent than "opened Mar 9"
3. **"STALE" status** - any unassigned blocker older than 3 days gets flagged as stale with amber highlight
4. **Owner column** - "unassigned" in red text is a silent call to action
5. **Sort order:** Red → Amber, then oldest-first within severity. Oldest unresolved items float to top.

### Ideal Length

- **Target:** 500-800 words
- **Screen size:** 2-3 mobile viewport scrolls
- **Scan time:** < 45 seconds for header + RAG + executive summary + blocker table
- **Deep read time:** < 3-4 minutes for the entire email

---

## 5. HTML Email Technical Constraints

### The Rendering Landscape (2026)

| Client | Engine | Key Constraints |
|---|---|---|
| **Gmail (web)** | Custom DOM sanitizer | Strips `<style>` in `<head>`. Inline styles only. No media queries. Class names prefixed/mangled. |
| **Gmail (mobile)** | Aggressive dark mode | Full color inversion on Android. Small images (<100px) may get color-inverted. |
| **Outlook (desktop, classic)** | Microsoft Word HTML engine | No `border-radius`, `background-image`, `max-width`, `flexbox`, `grid`, or media queries. Tables-only layout. Uses VML for backgrounds. |
| **Outlook (new/web)** | Chromium-based | Better CSS support. Does NOT support MSO conditional comments (they're ignored). 2025-2026 is "dual Outlook" transition - code for both. |
| **Apple Mail** | WebKit | Most standards-compliant. Supports flexbox, grid, media queries, web fonts, animations. Does NOT invert HTML emails in dark mode (only plain-text). |
| **Yahoo Mail** | Custom | Supports `<style>` in `<head>` but rewrites class names. Attribute selectors work. |
| **Samsung Mail** | Chromium | Generally well-behaved. Test for dark mode. |

### Common Pitfalls & Fixes

**1. Outlook ignores `max-width`**
```html
<!-- WRONG -->
<div style="max-width: 600px;">

<!-- RIGHT: Use MSO conditional comment + table wrapper -->
<!--[if mso]>
<table cellpadding="0" cellspacing="0" border="0" width="600"><tr><td>
<![endif]-->
<div style="max-width: 600px; margin: 0 auto;">
  <!-- content -->
</div>
<!--[if mso]>
</td></tr></table>
<![endif]-->
```

**2. Dark mode color inversion**
- Never use `#000000` for text - use `#1a1a1a` (dark gray). Pure black triggers aggressive inversion in some clients.
- Never use `#FFFFFF` for backgrounds without also setting it explicitly. Let it inherit where possible.
- Use transparent PNGs for logos. Add a 1-2px white drop shadow or stroke to dark logos so they remain visible on dark backgrounds.
- Include `<meta name="color-scheme" content="light dark">` and `<meta name="supported-color-schemes" content="light dark">` in `<head>`.
- For clients that support it, use `@media (prefers-color-scheme: dark)` to provide alternate colors.

**3. Gmail strips `<style>` blocks**
- ALL styles must be inlined on elements. Tooling: use a CSS inliner (e.g., `juice`, `inline-css`) as a build step.
- Exception: Gmail supports `<style>` in `<head>` on Android and iOS apps (not web). Don't rely on it.

**4. Outlook ignores `padding` on most elements**
- Use `cellpadding` on `<td>` elements or add an inner `<div>` with `margin` for spacing.
- For cell padding, use the `padding` property on `<td>` only - it's the one place Outlook respects it.

**5. Animated GIFs don't play in Outlook desktop**
- Outlook shows only the first frame. Ensure the first frame is a meaningful static fallback.

**6. Images blocked by default in many corporate Outlook setups**
- Always include `alt` text with `font-size`, `color`, and `font-family` styling so the alt text is readable when images are blocked.
- Never convey critical information solely via images.

**7. `width: X%` breaks on non-table elements in Outlook**
- Use fixed widths in DXA/pixels on tables. Percentage widths only work on `<table>` and `<td>`.

**8. Responsive design without media queries (Gmail web)**
- Use "hybrid" or "spongy" layout: `display: inline-block` divs inside a container with `max-width`. They stack naturally on small screens.
- Or use the "fluid" method: `width: 100%; max-width: 600px;` with MSO fixed-width fallback.

**9. Fonts**
- Stick to system fonts: Arial, Helvetica, Georgia, Verdana, Tahoma. Web fonts are unreliable.
- `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;` for a modern system stack.
- For monospace (code/metrics): `'Courier New', Courier, monospace`.

**10. Preheader text hack**
```html
<!-- Hidden preheader that shows in inbox preview -->
<div style="display:none; max-height:0; overflow:hidden; mso-hide:all;">
  Your preheader text here (40-100 chars recommended)
  <!-- Fill with whitespace to prevent body text leaking into preview -->
  &nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj; <!-- repeat ~100x -->
</div>
```

### Safe HTML Email Skeleton

```html
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>Email Title</title>
  <!--[if mso]>
  <noscript><xml>
    <o:OfficeDocumentSettings>
      <o:PixelsPerInch>96</o:PixelsPerInch>
    </o:OfficeDocumentSettings>
  </xml></noscript>
  <![endif]-->
  <style>
    /* Only for clients that support <style> - Gmail web ignores this */
    @media (prefers-color-scheme: dark) {
      .dark-bg { background-color: #1a1a1a !important; }
      .dark-text { color: #e0e0e0 !important; }
    }
  </style>
</head>
<body style="margin:0; padding:0; background-color:#F5F5F5; font-family:Arial,Helvetica,sans-serif;">
  <!-- Preheader -->
  <div style="display:none; max-height:0; overflow:hidden; mso-hide:all;">
    Preheader text here
  </div>

  <!-- Outer wrapper -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#F5F5F5;">
    <tr>
      <td align="center" style="padding: 20px 10px;">
        <!--[if mso]>
        <table cellpadding="0" cellspacing="0" border="0" width="600"><tr><td>
        <![endif]-->
        <div style="max-width:600px; margin:0 auto; background-color:#FFFFFF;">

          <!-- EMAIL CONTENT HERE -->

        </div>
        <!--[if mso]>
        </td></tr></table>
        <![endif]-->
      </td>
    </tr>
  </table>
</body>
</html>
```

---

## 6. Subject Line Formulas

### General Principles

- 40 characters or fewer is optimal for mobile (Gmail cuts off beyond that)
- 43% of recipients open emails based on subject line alone
- Subject lines with numbers outperform those without
- Never start with the product name (the From field already signals that). Put it at the end if needed.
- Use brackets `[ ]` for categorization - developers are trained to parse them (think: `[PATCH]`, `[RFC]`)

### Formulas for Each Template

**Daily Standup:**
```
Formula:  [{project}] Daily: {key_number} {unit} | {date}
Examples: [myapp] Daily: 14 files changed | Mar 12
          [myapp] Daily: Quiet day | Mar 12
          [myapp] Daily: 1 blocker flagged | Mar 12
```

**Weekly Digest:**
```
Formula:  [{cadence}] {date_range}: {headline_number} across {N} projects
Examples: [Weekly] Mar 3-9: 47 sessions across 3 projects
          [Weekly] Mar 3-9: Activity ↓34% - 2 projects dormant
```

**Project Deep Dive:**
```
Formula:  [{project}] Status: {RAG_emoji} {RAG_word} - {headline} | {date}
Examples: [myapp] Status: 🟢 On Track - 78% complete | Mar 12
          [api] Status: 🔴 Blocked - 3 unresolved issues | Mar 12
```

### Anti-Patterns (What NOT to Do)

| Bad Pattern | Why It Fails |
|---|---|
| `Your Weekly Update` | Generic. No information conveyed. Gets auto-filtered. |
| `Important: Please Read` | Spam trigger. Violates trust. |
| `Update from [ToolName]` | Wastes precious characters on branding. From field covers this. |
| `Here's what happened...` | Teaser without substance. Developers hate clickbait. |
| Same subject every day | Visually identical in inbox = pattern blindness = auto-ignore. |

### Key Rule: Every Subject Line Must Contain a Variable

If the subject line is the same two days in a row, it will be ignored. Always include at least one dynamic element: a number, a date, a project name, or a status word.

---

## 7. Psychology of Status Email Engagement

### Why People Ignore Status Emails

| Cause | Mechanism | Fix |
|---|---|---|
| **No new information** | If today's email looks identical to yesterday's, the brain classifies it as noise via the reticular activating system - the brain's filter for what deserves attention. | Always include at least one variable delta. Show change, not just state. |
| **Too long** | Cognitive load exceeds the perceived value. The reader subconsciously calculates effort vs. reward in < 2 seconds. | Cap word counts ruthlessly. Daily = 150-250 words. Weekly = 300-500. |
| **No action required** | If the email never requires action, the brain trains itself to skip it (operant conditioning - no reward for opening). | Include conditional sections that only appear when action is needed. Blockers = built-in call to action. |
| **Arrives at wrong time** | Status emails that arrive at 5 PM are dead on arrival. Developers check email at start-of-day. | Send daily at 8-9 AM local time. Weekly on Monday AM. |
| **Pattern blindness** | Same visual template, same subject, same cadence = wallpaper. The brain's novelty detection (reticular activating system) ignores it. | Vary subject lines with dynamic content. Change the BLUF sentence every day. Conditional sections alter the visual shape of the email. |
| **Feels like surveillance** | If the email reads like a performance report, trust erodes. Developers resent tools that feel like monitoring. | Frame as "your personal briefing," not "what you did." Use "you" language, not "we noticed." Never include comparative metrics against teammates. |
| **Information overload** | When everything feels urgent, nothing feels important. Too many status emails across too many tools. | Consolidate. One tool, one daily email. Batch notifications. Frequency controls per-user. |

### Design Principles That Fight Ignore Behavior

1. **Variable content creates novelty.** The brain's reticular activating system flags things that are different. Every email must have visible differences from the last one - different numbers, different status, different section visibility.

2. **Conditional sections create surprise.** When a blocker section appears on a day it normally doesn't, it breaks the pattern and demands attention. Absence is also information - when the "Blockers" section is gone, that's a positive signal.

3. **Urgency only when earned.** Reserve red/urgent treatment for actual blockers. If every email looks urgent, nothing is urgent. Amber and red should appear rarely enough to maintain their signal strength.

4. **Single-CTA focus.** Emails with one call to action outperform those with multiple options. Each template gets ONE primary button. Everything else is a text link.

5. **Send time matters.** Research and tool defaults converge on: daily standups at 8-9 AM local time (start of workday), weekly digests on Monday mornings, deep dives on request or Friday afternoons (reflection time).

6. **Respect the unsubscribe.** Always include per-email-type frequency controls. Let users downgrade from daily to weekly, or mute specific projects. A user who controls their notification preferences stays engaged longer than one who feels trapped.

---

## 8. 10 Email Use Case Ideas for AI Memory Systems

These go beyond basic status updates. Each leverages an AI memory system's ability to recall context across sessions.

| # | Use Case | Trigger | Content |
|---|----------|---------|---------|
| 1 | **Context Resume Digest** | User starts a new session after 48+ hours | "Here's where you left off: {last_session_summary}. Open files: {files}. Unresolved items: {items}." |
| 2 | **Decision Log Weekly** | Weekly cadence | Summary of all architectural/design decisions made in AI sessions that week. Links to session transcripts. |
| 3 | **Technical Debt Radar** | Weekly or threshold-based | AI identifies TODO/FIXME/HACK patterns, repeated workaround discussions, and areas flagged but never addressed. |
| 4 | **Knowledge Gap Alert** | After N sessions on the same topic | "You've asked about {topic} in 5 sessions this month. Here's a consolidated reference: {synthesized_answer}." |
| 5 | **Dependency Drift Report** | Weekly or on-detect | AI notices package versions discussed vs. installed, flags stale dependencies or security advisories. |
| 6 | **Code Review Prep Email** | Before a PR review or merge | Summarizes all AI sessions related to the branch/PR. What was discussed, what tradeoffs were made, what to watch for. |
| 7 | **Onboarding Digest for New Team Members** | On-demand or when new member joins | AI generates a "project primer" email from accumulated session context: architecture decisions, conventions, gotchas. |
| 8 | **Sprint Retrospective Summary** | End of sprint/cycle | AI analyzes all sessions in the sprint period. Identifies: time distribution across files/features, recurring blockers, velocity trends. |
| 9 | **Personal Productivity Insights** | Monthly | Your coding patterns: peak hours, average session length, most productive days, focus areas. Private to the individual. |
| 10 | **Stale Context Cleanup Reminder** | Monthly | "These 7 memory entries are > 30 days old and haven't been referenced. Review and archive?" |

---

## Appendix A: Email Template Data Contract

Each template should be powered by a JSON payload. Here are the minimum required fields:

### Daily Standup Payload

```json
{
  "template": "daily_standup",
  "date": "2026-03-12",
  "user": {
    "name": "Mike",
    "email": "mike@example.com",
    "timezone": "America/New_York"
  },
  "projects": [
    {
      "name": "myapp",
      "sessions": [
        {
          "id": "sess_abc123",
          "start": "2026-03-11T14:00:00Z",
          "end": "2026-03-11T15:32:00Z",
          "files_changed": 8,
          "lines_added": 142,
          "lines_removed": 31,
          "summary": "Refactored auth middleware, added rate limiting",
          "blockers": []
        }
      ],
      "totals": {
        "session_count": 2,
        "files_changed": 14,
        "lines_added": 187,
        "lines_removed": 42
      },
      "averages_7d": {
        "session_count": 1.7,
        "files_changed": 11.3
      }
    }
  ],
  "quiet_day": false,
  "last_activity_date": "2026-03-11"
}
```

### Weekly Digest Payload

```json
{
  "template": "weekly_digest",
  "date_range": { "start": "2026-03-03", "end": "2026-03-09" },
  "user": { "name": "Mike", "email": "mike@example.com" },
  "portfolio": [
    {
      "project": "myapp",
      "rag": "green",
      "sessions_this_week": 28,
      "sessions_last_week": 24,
      "files_changed": 54,
      "lines_net": 1847,
      "trend_pct": 16.7,
      "dormant": false,
      "last_activity": "2026-03-09"
    }
  ],
  "totals": {
    "sessions": 47,
    "sessions_last_week": 42,
    "projects_active": 3,
    "projects_dormant": 1,
    "blockers_open": 2
  },
  "top_accomplishments": [
    "Completed auth system refactor (myapp)",
    "Deployed API v2 endpoints (api-service)",
    "Fixed 12 flaky tests (myapp)"
  ],
  "dormant_alerts": [
    {
      "project": "frontend",
      "days_inactive": 5,
      "last_session_summary": "Started component library migration",
      "open_items": 3
    }
  ]
}
```

### Project Deep Dive Payload

```json
{
  "template": "project_deep_dive",
  "date": "2026-03-12",
  "project": {
    "name": "myapp",
    "rag": "green",
    "rag_reasons": ["All milestones on schedule", "0 open blockers", "Velocity +15% WoW"]
  },
  "metrics": {
    "sessions_7d": 28,
    "files_changed_7d": 54,
    "lines_added_7d": 1847,
    "lines_removed_7d": 312,
    "avg_session_minutes": 47,
    "open_blockers": 0,
    "milestone_progress_pct": 78
  },
  "milestones": [
    { "name": "Phase 1: Auth", "status": "complete", "date": "2026-03-01" },
    { "name": "Phase 2: API", "status": "complete", "date": "2026-03-07" },
    { "name": "Phase 3: Frontend", "status": "in_progress", "progress_pct": 60, "target": "2026-03-15" },
    { "name": "Phase 4: QA", "status": "not_started", "target": "2026-03-22" }
  ],
  "recent_sessions": [
    {
      "date": "2026-03-11",
      "duration_min": 52,
      "summary": "Refactored auth middleware",
      "files": ["src/middleware/auth.ts", "src/routes/api.ts"]
    }
  ],
  "blockers": [
    {
      "severity": "amber",
      "description": "Flaky test suite on CI",
      "owner": "sarah",
      "age_days": 1,
      "status": "investigating"
    }
  ]
}
```

---

## Appendix B: Quick Reference Card

### Template Comparison Matrix

| Attribute | Daily Standup | Weekly Digest | Project Deep Dive |
|---|---|---|---|
| **Cadence** | Every workday, 8-9 AM | Monday AM | On-demand or configurable |
| **Audience** | Individual dev + team | Dev + manager | Project lead + stakeholders |
| **Word count** | 150-250 | 300-500 | 500-800 |
| **Sections** | 5-6 | 7-8 | 8-9 |
| **RAG status** | No (too granular) | Yes (portfolio level) | Yes (detailed with criteria) |
| **Trends** | vs. 7d rolling avg | Week-over-week | 7d with sparklines |
| **Forwardable** | No (personal) | Yes (portfolio view) | Yes (project report) |
| **Quiet day handling** | Yes (special treatment) | N/A (always has data) | N/A (triggered only when relevant) |
| **Primary CTA** | View Session Log | View Dashboard | Open Project / Address Blocker |
| **Branding level** | Minimal | Moderate | Full |

### Rendering Test Checklist

Before shipping any template, test in:

- [ ] Gmail (web, Chrome)
- [ ] Gmail (Android app, dark mode ON)
- [ ] Gmail (iOS app, dark mode ON)
- [ ] Outlook 365 desktop (Windows, classic Word engine)
- [ ] Outlook new (Windows, Chromium-based)
- [ ] Outlook.com (web)
- [ ] Apple Mail (macOS)
- [ ] Apple Mail (iOS)
- [ ] Yahoo Mail (web)
- [ ] Images-blocked mode (any client)
- [ ] Plain-text fallback
- [ ] 320px viewport (smallest mobile)
- [ ] 600px viewport (desktop render)

### Tools for Testing

- **Litmus** - cross-client rendering previews, dark mode simulation
- **Email on Acid** - rendering + accessibility + deliverability testing
- **mailpeek** - dev-environment previews with dark mode simulation and compatibility scoring
- **Can I Email (caniemail.com)** - the "Can I Use" for HTML email CSS property support
