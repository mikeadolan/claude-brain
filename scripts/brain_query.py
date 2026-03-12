#!/usr/bin/env python3
"""
brain_query.py — Search the brain database and return formatted results.

Takes a natural language question, extracts keywords, runs FTS5 + semantic
search, and returns formatted results for Claude to synthesize. All search
happens locally (zero API tokens).

Usage:
    python3 brain_query.py "What did we work on for Mom and Nadene?"
    python3 brain_query.py "What was decided about the Teamsters?" --project jg
    python3 brain_query.py "YubiKey setup" --project gen --limit 5

Exit codes: 0 success, 1 error
"""

import argparse
import os
import pathlib
import re
import sqlite3
import sys
import yaml

from fuzzy_search import fuzzy_correct

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
    "discuss", "discussed", "talk", "talked", "did", "do", "done",
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


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

def extract_keywords(question):
    """Extract search keywords from natural language question."""
    # Remove punctuation except apostrophes inside words
    cleaned = re.sub(r"[^\w\s']", " ", question)
    # Split and lowercase
    words = cleaned.lower().split()
    # Filter stop words and short words
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    # Deduplicate preserving order
    seen = set()
    unique = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique[:MAX_KEYWORDS]


def build_fts_query(keywords):
    """Build FTS5 OR query from keywords, escaping special characters."""
    escaped = []
    for kw in keywords:
        # Escape apostrophes for FTS5
        safe = kw.replace("'", "''")
        # Quote keywords that might be FTS5 operators
        if safe.upper() in ("OR", "AND", "NOT", "NEAR"):
            safe = f'"{safe}"'
        escaped.append(safe)
    return " OR ".join(escaped)


# ---------------------------------------------------------------------------
# Search functions
# ---------------------------------------------------------------------------

def search_fts(conn, keywords, project=None, limit=15):
    """FTS5 keyword search across transcripts."""
    if not keywords:
        return []

    fts_query = build_fts_query(keywords)
    sql = """
        SELECT t.session_id, t.project, t.role, t.content,
               t.timestamp, t.type,
               rank
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


def search_semantic(conn, question, project=None, limit=10):
    """Semantic search using embeddings + cosine similarity."""
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return []

    # Check if embeddings exist
    count = conn.execute("SELECT COUNT(*) FROM transcript_embeddings").fetchone()[0]
    if count == 0:
        return []

    # Load model and encode query
    try:
        model = SentenceTransformer("all-MiniLM-L6-v2")
        query_emb = model.encode(question, normalize_embeddings=True)
    except Exception as e:
        print(f"Semantic model error: {e}", file=sys.stderr)
        return []

    # Fetch all embeddings
    sql = """
        SELECT e.transcript_id, e.embedding, t.session_id, t.project,
               t.role, t.content, t.timestamp
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

    # Compute cosine similarities
    results = []
    for row in rows:
        emb = np.frombuffer(row[1], dtype=np.float32)
        sim = float(np.dot(query_emb, emb))
        results.append((sim, row))

    # Sort by similarity, return top N
    results.sort(key=lambda x: x[0], reverse=True)
    return results[:limit]


def search_decisions(conn, keywords, project=None):
    """Search decisions table by keywords."""
    if not keywords:
        return []
    conditions = []
    params = []
    for kw in keywords:
        conditions.append("(d.description LIKE ? OR d.rationale LIKE ?)")
        params.extend([f"%{kw}%", f"%{kw}%"])

    sql = f"""
        SELECT d.decision_number, d.project, d.description, d.rationale
        FROM decisions d
        WHERE ({" OR ".join(conditions)})
    """
    if project:
        sql += " AND d.project = ?"
        params.append(project)

    sql += " ORDER BY d.decision_number DESC LIMIT 10"

    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        return []


def search_facts(conn, keywords, project=None):
    """Search facts table by keywords."""
    if not keywords:
        return []
    conditions = []
    params = []
    for kw in keywords:
        conditions.append("(f.key LIKE ? OR f.value LIKE ?)")
        params.extend([f"%{kw}%", f"%{kw}%"])

    sql = f"""
        SELECT f.project, f.category, f.key, f.value
        FROM facts f
        WHERE ({" OR ".join(conditions)})
    """
    if project:
        sql += " AND f.project = ?"
        params.append(project)

    sql += " LIMIT 10"

    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        return []


def search_brain_facts(conn, keywords):
    """Search brain_facts table by keywords."""
    if not keywords:
        return []
    conditions = []
    params = []
    for kw in keywords:
        conditions.append("(bf.key LIKE ? OR bf.value LIKE ? OR bf.category LIKE ?)")
        params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])

    sql = f"""
        SELECT bf.category, bf.key, bf.value
        FROM brain_facts bf
        WHERE ({" OR ".join(conditions)})
        LIMIT 10
    """
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def truncate(text, max_len=300):
    """Truncate text to max length, adding ellipsis."""
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def format_results(question, keywords, fts_results, semantic_results,
                   decision_results, fact_results, brain_fact_results,
                   project, corrections=None):
    """Format all results into clean text for Claude to synthesize."""
    lines = []
    lines.append(f"## Brain Query Results")
    lines.append(f"Question: {question}")
    lines.append(f"Keywords: {', '.join(keywords)}")
    if corrections:
        parts = [f"'{orig}' → '{fixed}'" for orig, fixed in corrections.items()]
        lines.append(f"Did you mean: {', '.join(parts)}")
    if project:
        lines.append(f"Project filter: {project}")
    lines.append("")

    # Brain facts
    if brain_fact_results:
        lines.append(f"### Personal Facts ({len(brain_fact_results)} matches)")
        for row in brain_fact_results:
            lines.append(f"- [{row[0]}] {row[1]}: {row[2]}")
        lines.append("")

    # Project facts
    if fact_results:
        lines.append(f"### Project Facts ({len(fact_results)} matches)")
        for row in fact_results:
            lines.append(f"- [{row[0]}/{row[1]}] {row[2]}: {truncate(row[3], 200)}")
        lines.append("")

    # Decisions
    if decision_results:
        lines.append(f"### Decisions ({len(decision_results)} matches)")
        for row in decision_results:
            lines.append(f"- Decision {row[0]} [{row[1]}]: {truncate(row[2], 200)}")
        lines.append("")

    # FTS5 transcript matches
    if fts_results:
        lines.append(f"### Transcript Matches — Keyword ({len(fts_results)} results)")
        for row in fts_results:
            date = (row[4] or "")[:10]
            lines.append(f"- [{date}, {row[1]}, {row[2]}] {truncate(row[3])}")
        lines.append("")

    # Semantic matches
    if semantic_results:
        lines.append(f"### Transcript Matches — Semantic ({len(semantic_results)} results)")
        for sim, row in semantic_results:
            date = (row[6] or "")[:10]
            lines.append(f"- [{date}, {row[3]}, {row[4]}, sim={sim:.3f}] {truncate(row[5])}")
        lines.append("")

    if not any([fts_results, semantic_results, decision_results,
                fact_results, brain_fact_results]):
        lines.append("No results found in the brain database for this query.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Search the brain database")
    parser.add_argument("question", help="Natural language question to search for")
    parser.add_argument("--project", "-p", default=None,
                        help="Filter by project prefix (jg, gen, mb, etc.)")
    parser.add_argument("--limit", "-l", type=int, default=10,
                        help="Max results per search type (default: 10)")
    parser.add_argument("--no-semantic", action="store_true",
                        help="Skip semantic search (faster)")
    args = parser.parse_args()

    root_path = get_root_path()
    config = load_config(root_path)
    db_path = config["storage"]["local_db_path"]
    conn = connect_db(db_path)

    try:
        # Extract keywords and fuzzy-correct before searching
        keywords = extract_keywords(args.question)
        if not keywords:
            # Fallback: use all non-trivial words
            keywords = [w.lower() for w in args.question.split() if len(w) > 2][:MAX_KEYWORDS]

        corrected, corrections = fuzzy_correct(keywords, db_path)
        keywords = corrected

        # Run all searches
        fts_results = search_fts(conn, keywords, args.project, args.limit)
        decision_results = search_decisions(conn, keywords, args.project)
        fact_results = search_facts(conn, keywords, args.project)
        brain_fact_results = search_brain_facts(conn, keywords)

        # Semantic search (optional, slower due to model load)
        semantic_results = []
        sem_config = config.get("semantic_search", {})
        if sem_config.get("enabled", False) and not args.no_semantic:
            semantic_results = search_semantic(
                conn, args.question, args.project, min(args.limit, 5)
            )

        # Format and print
        output = format_results(
            args.question, keywords, fts_results, semantic_results,
            decision_results, fact_results, brain_fact_results,
            args.project, corrections
        )
        print(output)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
