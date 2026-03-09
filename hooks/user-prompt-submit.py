#!/usr/bin/env python3
"""user-prompt-submit.py — Claude Code UserPromptSubmit hook for claude-brain.

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

        prompts = input_data.get("prompts", [])
        if not prompts:
            print("{}")
            return

        prompt_text = ""
        for p in prompts:
            if isinstance(p, dict):
                prompt_text += p.get("content", "") + " "
            elif isinstance(p, str):
                prompt_text += p + " "
        prompt_text = prompt_text.strip()

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

        print(json.dumps({"additionalContext": "\n".join(lines)}))

    except Exception:
        print("{}")


if __name__ == "__main__":
    main()
