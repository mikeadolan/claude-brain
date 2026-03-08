#!/usr/bin/env python3
"""
brain_search.py — Raw transcript search against the brain database.

Returns matching results like a search engine: timestamp, session ID,
project prefix, and excerpt. No synthesis, no AI summary.

Uses FTS5 for keyword search. If semantic search is enabled in config,
includes semantic results in a separate section.

Usage:
    python3 brain_search.py "ASUS laptop"
    python3 brain_search.py "hooks" --project mb
    python3 brain_search.py "Fat Tony" --project jg

Exit codes: 0 success, 1 error
"""

import argparse
import os
import pathlib
import re
import sqlite3
import sys
import yaml

# Suppress HuggingFace model-loading noise (must be before any HF imports)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TQDM_DISABLE"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

# ---------------------------------------------------------------------------
# Config / DB
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "don", "now", "and", "but", "or", "if", "while", "about", "up",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "it", "its", "i", "me", "my", "we", "our", "you", "your",
    "he", "him", "his", "she", "her", "they", "them", "their",
    "tell", "show", "give", "get", "got", "find", "work", "worked",
    "discuss", "discussed", "talk", "talked", "done",
}

MAX_KEYWORDS = 10


def get_root_path():
    return str(pathlib.Path(__file__).resolve().parent.parent)


def load_config(root_path):
    config_path = os.path.join(root_path, "config.yaml")
    if not os.path.exists(config_path):
        print(f"FATAL: config.yaml not found at {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def connect_db(db_path):
    if not os.path.exists(db_path):
        print(f"FATAL: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def get_valid_projects(conn):
    """Return set of valid project prefixes from project_registry."""
    rows = conn.execute("SELECT prefix FROM project_registry").fetchall()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

def extract_keywords(query):
    """Extract search keywords from query string."""
    cleaned = re.sub(r"[^\w\s']", " ", query)
    words = cleaned.lower().split()
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    seen = set()
    unique = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique[:MAX_KEYWORDS]


def build_fts_query(keywords):
    """Build FTS5 OR query from keywords."""
    escaped = []
    for kw in keywords:
        safe = kw.replace("'", "''")
        if safe.upper() in ("OR", "AND", "NOT", "NEAR"):
            safe = f'"{safe}"'
        escaped.append(safe)
    return " OR ".join(escaped)


# ---------------------------------------------------------------------------
# Search functions
# ---------------------------------------------------------------------------

def search_fts(conn, keywords, project=None, limit=20):
    """FTS5 keyword search across transcripts."""
    if not keywords:
        return []

    fts_query = build_fts_query(keywords)
    sql = """
        SELECT t.session_id, t.project, t.content, t.timestamp, rank
        FROM transcripts_fts fts
        JOIN transcripts t ON t.rowid = fts.rowid
        WHERE transcripts_fts MATCH ?
          AND t.content IS NOT NULL
          AND length(t.content) > 30
    """
    params = [fts_query]

    if project:
        sql += " AND t.project = ?"
        params.append(project)

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    try:
        return conn.execute(sql, params).fetchall()
    except Exception as e:
        print(f"FTS5 search error: {e}", file=sys.stderr)
        return []


def search_semantic(conn, query, project=None, limit=10):
    """Semantic search using embeddings + cosine similarity."""
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return []

    count = conn.execute("SELECT COUNT(*) FROM transcript_embeddings").fetchone()[0]
    if count == 0:
        return []

    try:
        model = SentenceTransformer("all-MiniLM-L6-v2")
        query_emb = model.encode(query, normalize_embeddings=True)
    except Exception as e:
        print(f"Semantic model error: {e}", file=sys.stderr)
        return []

    sql = """
        SELECT e.transcript_id, e.embedding, t.session_id, t.project,
               t.content, t.timestamp
        FROM transcript_embeddings e
        JOIN transcripts t ON t.id = e.transcript_id
        WHERE t.content IS NOT NULL AND length(t.content) > 30
    """
    params = []
    if project:
        sql += " AND t.project = ?"
        params.append(project)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return []

    results = []
    for row in rows:
        emb = np.frombuffer(row[1], dtype=np.float32)
        sim = float(np.dot(query_emb, emb))
        results.append((sim, row))

    results.sort(key=lambda x: x[0], reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def make_excerpt(content, keywords, max_len=200):
    """Extract a 2-3 line excerpt around the first keyword match."""
    if not content:
        return ""
    # Normalize whitespace
    text = re.sub(r"\s+", " ", content).strip()

    # Find the first keyword occurrence (case-insensitive)
    best_pos = len(text)
    for kw in keywords:
        idx = text.lower().find(kw.lower())
        if idx != -1 and idx < best_pos:
            best_pos = idx

    if best_pos == len(text):
        # No keyword found in text, take from start
        best_pos = 0

    # Window around the match
    start = max(0, best_pos - 60)
    end = min(len(text), best_pos + max_len - 60)

    excerpt = text[start:end]

    # Add ellipsis
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt = excerpt + "..."

    return excerpt


def format_timestamp(ts):
    """Format ISO timestamp to [YYYY-MM-DD HH:MM]."""
    if not ts:
        return "[unknown date]"
    # Handle ISO format: 2026-03-06T17:45:00.000Z or similar
    return f"[{ts[:10]} {ts[11:16]}]"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Raw transcript search against the brain database",
        usage="python3 brain_search.py QUERY [--project PREFIX]"
    )
    parser.add_argument("query", nargs="*", help="Search query")
    parser.add_argument("--project", "-p", default=None,
                        help="Filter by project prefix (jg, gen, mb, etc.)")
    parser.add_argument("--limit", "-l", type=int, default=10,
                        help="Max results per search type (default: 10)")
    parser.add_argument("--no-semantic", action="store_true",
                        help="Skip semantic search")
    args = parser.parse_args()

    # Handle empty query
    query = " ".join(args.query).strip()
    if not query:
        print("Usage: /brain-search QUERY [--project PREFIX]")
        print()
        print("Examples:")
        print('  /brain-search ASUS laptop')
        print('  /brain-search hooks --project mb')
        print('  /brain-search "Fat Tony" --project jg')
        sys.exit(0)

    root_path = get_root_path()
    config = load_config(root_path)
    db_path = config["storage"]["local_db_path"]
    conn = connect_db(db_path)

    try:
        # Validate project prefix
        if args.project:
            valid = get_valid_projects(conn)
            if args.project not in valid:
                print(f"Error: unknown project prefix '{args.project}'")
                print(f"Valid prefixes: {', '.join(sorted(valid))}")
                sys.exit(1)

        # Extract keywords
        keywords = extract_keywords(query)
        if not keywords:
            keywords = [w.lower() for w in query.split() if len(w) > 2][:MAX_KEYWORDS]

        if not keywords:
            print(f"No searchable keywords found in: {query}")
            sys.exit(0)

        # --- FTS5 Search ---
        fts_results = search_fts(conn, keywords, args.project, args.limit)

        projects_seen = set()
        total_matches = 0

        if fts_results:
            print("## Keyword Matches")
            print()
            for row in fts_results:
                session_id = row[0]
                project = row[1]
                content = row[2]
                timestamp = row[3]

                projects_seen.add(project)
                total_matches += 1

                ts = format_timestamp(timestamp)
                sid = session_id[:8] if session_id else "unknown"
                excerpt = make_excerpt(content, keywords)
                print(f'{ts} Session {sid} ({project}) — "{excerpt}"')

            print()

        # --- Semantic Search ---
        sem_config = config.get("semantic_search", {})
        semantic_results = []
        if sem_config.get("enabled", False) and not args.no_semantic:
            semantic_results = search_semantic(
                conn, query, args.project, min(args.limit, 10)
            )

            if semantic_results:
                print("## Semantic Matches (by meaning)")
                print()
                for sim, row in semantic_results:
                    session_id = row[2]
                    project = row[3]
                    content = row[4]
                    timestamp = row[5]

                    projects_seen.add(project)
                    total_matches += 1

                    ts = format_timestamp(timestamp)
                    sid = session_id[:8] if session_id else "unknown"
                    excerpt = make_excerpt(content, keywords, 200)
                    print(f'{ts} Session {sid} ({project}) [sim={sim:.3f}] — "{excerpt}"')

                print()

        # --- Summary line ---
        if total_matches == 0:
            print(f"No matches found for: {query}")
            if args.project:
                print(f"(filtered to project: {args.project})")
        else:
            proj_list = ", ".join(sorted(projects_seen))
            print(f"Found: {total_matches} matches across {len(projects_seen)} project(s) ({proj_list})")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
