#!/usr/bin/env python3
"""user-prompt-submit.py - Claude Code UserPromptSubmit hook for claude-brain.

Fires before every user message is sent to Claude.
1. Extracts user prompt text from stdin JSON
2. Searches for relevant memories (FTS5 search)
3. Returns top 3 relevant memories as additionalContext

RULE: stdout is SACRED. Only valid JSON goes to stdout.
"""

import json
import os
import re
import sqlite3
import sys

import yaml

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "can", "may", "might", "shall", "not", "no", "yes", "ok",
    "okay", "this", "that", "it", "i", "you", "we", "they", "me", "my",
    "your", "our", "their", "and", "or", "but", "if", "then", "so", "for",
    "of", "to", "in", "on", "at", "by", "with", "from", "up", "out",
    "into", "about", "what", "how", "when", "where", "which", "who",
    "go", "just", "let", "get", "make", "know", "think", "want", "need",
    "use", "try", "see", "look", "tell", "give", "take", "come", "also",
    "now", "here", "there", "than", "more", "some", "any", "all", "each",
    "very", "much", "well", "still", "already", "please", "thanks",
    "sure", "right", "good", "new", "first", "last", "next", "other",
}

# ---------------------------------------------------------------------------
# Frustration detection - circuit breaker
# ---------------------------------------------------------------------------

FRUSTRATION_PATTERNS = [
    r"\bwhat the hell\b",
    r"\bwhy the hell\b",
    r"\bhow the hell\b",
    r"\bfor god'?s? sake",
    r"\bstupid\b",
    r"\bdumb\b",
    r"\bidiot\b",
    r"\bretard",
    r"\bare you even\b",
    r"\bwhy didn'?t you\b",
    r"\bhow can you\b",
    r"\bwhat are you doing\b",
    r"\bstop being\b",
    r"\bfix it\b",
    r"\bwast(?:ed?|ing)\s+(?:my\s+)?time\b",
    r"\bhow many times\b",
    r"\bnot listen",
    r"\bcan'?t you\b",
    r"\bfor (?:fuck|christ)\b",
]

FRUSTRATION_WORDS = {
    "hell", "stupid", "dumb", "idiot", "retard", "retarded",
    "god", "sakes", "sake", "damn", "crap", "shit", "fuck",
    "why", "how", "what", "come", "stop", "being", "even",
    "fix", "wasted", "waste", "wasting", "time", "christ",
    "listen", "listening", "cant",
}


def detect_frustration(text):
    """Check if the user's message indicates frustration."""
    text_lower = text.lower()

    # Check explicit patterns
    for pattern in FRUSTRATION_PATTERNS:
        if re.search(pattern, text_lower):
            return True

    # Check high caps ratio (>50% uppercase, message > 20 chars)
    if len(text) > 20:
        alpha_chars = [c for c in text if c.isalpha()]
        if alpha_chars:
            upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if upper_ratio > 0.5:
                return True

    # Check multiple exclamation/question marks
    if text.count("!") >= 3 or text.count("?") >= 3:
        return True

    return False


def extract_topic_keywords(text):
    """Extract topic keywords from a frustrated message, stripping frustration words."""
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    keywords = [w for w in words if w not in STOP_WORDS and w not in FRUSTRATION_WORDS]
    return keywords[:8]


def handle_frustration(prompt_text, root):
    """When frustration detected: search brain for topic context, return STOP directive."""
    topic_keywords = extract_topic_keywords(prompt_text)

    context_lines = [
        "## FRUSTRATION DETECTED - STOP AND REASSESS",
        "Something is wrong with your current approach.",
        "Do NOT continue what you were doing. Instead:",
        "1. Review the brain context below",
        "2. Verify your assumptions are correct",
        "3. Present your findings to Mike BEFORE taking any action",
        "",
    ]

    try:
        config_path = os.path.join(root, "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        db_path = config["storage"]["local_db_path"]
        if not os.path.exists(db_path):
            return "\n".join(context_lines)

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA busy_timeout=5000;")

        # Search transcripts for topic keywords
        if topic_keywords:
            fts_query = " OR ".join(f'"{kw}"' for kw in topic_keywords)
            try:
                rows = conn.execute(
                    """SELECT t.project, t.timestamp,
                              substr(t.content, 1, 600) as preview
                       FROM transcripts_fts fts
                       JOIN transcripts t ON t.rowid = fts.rowid
                       WHERE transcripts_fts MATCH ?
                       ORDER BY fts.rank
                       LIMIT 5""",
                    (fts_query,),
                ).fetchall()
                if rows:
                    context_lines.append("## Brain Context for Current Topic")
                    for proj, ts, preview in rows:
                        date = ts[:10] if ts else "?"
                        text = (preview or "").replace("\n", " ").strip()
                        context_lines.append(f"- [{date}, {proj}] {text}")
                    context_lines.append("")
            except Exception:
                pass

        # Get last 3 session notes for broader context
        try:
            notes_rows = conn.execute(
                """SELECT notes, started_at FROM sys_sessions
                   WHERE notes IS NOT NULL AND notes != ''
                   ORDER BY started_at DESC LIMIT 3"""
            ).fetchall()
            if notes_rows:
                context_lines.append("## Recent Session Notes")
                for notes, date in notes_rows:
                    d = date[:10] if date else "?"
                    context_lines.append(f"### [{d}]")
                    context_lines.append((notes or "")[:500])
                    context_lines.append("")
        except Exception:
            pass

        conn.close()

    except Exception:
        pass

    return "\n".join(context_lines)


# ---------------------------------------------------------------------------
# GO check - Rule #2 enforcement
# Detects "discussion" messages that do NOT contain explicit GO trigger.
# Prevents Claude from coding when Mike is asking for thoughts/opinions.
# ---------------------------------------------------------------------------

DISCUSSION_PATTERNS = [
    r"\bthoughts\b",
    r"\bwhat do you think\b",
    r"\bwhat would you\b",
    r"\bhow would you\b",
    r"\bideas\b",
    r"\bpropose\b",
    r"\boptions\b",
    r"\bapproach\b",
    r"\bwhat.{0,20}best practice\b",
    r"\bshould we\b",
    r"\bcould we\b",
    r"\bother ideas\b",
    r"\bwhich.{0,15}easier\b",
    r"\bwhich.{0,15}better\b",
]

GO_PATTERNS = [
    r"\bgo\b",
    r"\bgo,",
    r"\bbuild it\b",
    r"\bdo it\b",
    r"\bexecute\b",
    r"\bstart\b",
    r"\bship it\b",
    r"\bmake it\b",
    r"\bimplement\b",
    r"\bcreate it\b",
    r"\bwrite it\b",
]


def detect_discussion_not_go(text):
    """Return True if message looks like a discussion request WITHOUT a GO trigger."""
    text_lower = text.lower()

    has_discussion = any(re.search(p, text_lower) for p in DISCUSSION_PATTERNS)
    if not has_discussion:
        return False

    has_go = any(re.search(p, text_lower) for p in GO_PATTERNS)
    if has_go:
        return False

    return True


def main():
    # Read stdin (hook protocol sends prompt data)
    raw_input = sys.stdin.read()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    try:
        # 1. Extract prompt text
        try:
            input_data = json.loads(raw_input)
        except json.JSONDecodeError:
            print("{}")
            return

        prompt_text = input_data.get("user_prompt", "")
        if not isinstance(prompt_text, str):
            prompt_text = ""
        prompt_text = prompt_text.strip()

        # Frustration circuit breaker - check BEFORE length filter
        if prompt_text and detect_frustration(prompt_text):
            context = handle_frustration(prompt_text, root)
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}))
            return

        # GO check - prevent coding without explicit GO (Rule #2 enforcement)
        if prompt_text and detect_discussion_not_go(prompt_text):
            context = (
                "## RULE #2 REMINDER - DO NOT CODE\n"
                "Mike is asking for your THOUGHTS, not code.\n"
                "PRESENT the plan. Do NOT write, edit, or create any files.\n"
                "Wait for Mike to say 'GO' + name the specific step.\n"
                "Violated in sessions 17, 19, 21, 25, 36. ZERO TOLERANCE."
            )
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}))
            return

        # Skip short/trivial prompts
        if len(prompt_text) < 15:
            print("{}")
            return

        # 2. Load config and connect to DB
        config_path = os.path.join(root, "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        db_path = config["storage"]["local_db_path"]
        if not os.path.exists(db_path):
            print("{}")
            return

        # 3. FTS5 search (semantic search available via MCP search_semantic on demand)

        # Extract keywords from prompt
        words = re.findall(r'[a-zA-Z]{3,}', prompt_text.lower())
        keywords = [w for w in words if w not in STOP_WORDS]
        keywords = keywords[:8]  # Cap at 8 keywords

        if not keywords:
            print("{}")
            return

        fts_query = " OR ".join(f'"{kw}"' for kw in keywords)

        # Detect current project from CWD for result biasing
        cwd_project = None
        cwd = os.environ.get("CWD", os.getcwd())
        mapping = config.get("jsonl_project_mapping", {})
        for folder, prefix in mapping.items():
            if folder in cwd:
                cwd_project = prefix
                break

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA busy_timeout=5000;")

        # Search with project bias: get 2 from current project + 3 global, dedup to top 3
        rows = []
        if cwd_project:
            rows = conn.execute("""
                SELECT t.project, t.timestamp, t.content
                FROM transcripts_fts fts
                JOIN transcripts t ON t.rowid = fts.rowid
                WHERE transcripts_fts MATCH ? AND t.project = ?
                ORDER BY fts.rank
                LIMIT 2
            """, (fts_query, cwd_project)).fetchall()

        # Fill remaining slots with global results
        global_rows = conn.execute("""
            SELECT t.project, t.timestamp, t.content
            FROM transcripts_fts fts
            JOIN transcripts t ON t.rowid = fts.rowid
            WHERE transcripts_fts MATCH ?
            ORDER BY fts.rank
            LIMIT 5
        """, (fts_query,)).fetchall()

        # Merge: project-biased first, then global (dedup by content prefix)
        seen = set()
        merged = []
        for r in list(rows) + list(global_rows):
            key = (r[0], (r[2] or "")[:50])
            if key not in seen:
                seen.add(key)
                merged.append(r)
            if len(merged) >= 3:
                break
        rows = merged

        conn.close()

        if not rows:
            print("{}")
            return

        semantic_results = []
        for project, timestamp, content in rows:
            semantic_results.append({
                "content": (content or "")[:200].replace("\n", " "),
                "project": project or "",
                "timestamp": (timestamp or "")[:10],
            })

        # 4. Format results
        if not semantic_results:
            print("{}")
            return

        lines = ["## Relevant Memories", ""]
        for i, r in enumerate(semantic_results, 1):
            lines.append(f"{i}. [{r['timestamp']}, {r['project']}] {r['content']}")
        lines.append("")

        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "\n".join(lines)}}))

    except Exception:
        print("{}")


if __name__ == "__main__":
    main()
