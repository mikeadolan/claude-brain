#!/usr/bin/env python3
"""
brain_decide.py - Fast decision lookup by number or keyword.

Looks up locked decisions from the brain database. Accepts a decision
number for exact lookup or a keyword string for search.

Usage:
    python3 brain_decide.py 76
    python3 brain_decide.py hooks
    python3 brain_decide.py semantic search

Exit codes: 0 success, 1 error
"""

import argparse
import os
import pathlib
import sqlite3
import sys

import yaml

# ---------------------------------------------------------------------------
# Config / DB
# ---------------------------------------------------------------------------

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
# Lookup functions
# ---------------------------------------------------------------------------

def lookup_by_number(conn, num):
    """Look up a single decision by number."""
    row = conn.execute(
        """SELECT decision_number, project, description, rationale,
                  session_id, created_at
           FROM decisions WHERE decision_number = ?""",
        (num,)
    ).fetchone()
    return row


def search_by_keyword(conn, keywords):
    """Search decisions by keyword(s) in description and rationale."""
    conditions = []
    params = []
    for kw in keywords:
        conditions.append("(d.description LIKE ? OR d.rationale LIKE ?)")
        params.extend([f"%{kw}%", f"%{kw}%"])

    sql = f"""
        SELECT d.decision_number, d.project, d.description, d.rationale,
               d.session_id, d.created_at
        FROM decisions d
        WHERE {" AND ".join(conditions)}
        ORDER BY d.decision_number ASC
    """
    return conn.execute(sql, params).fetchall()


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_date(ts):
    """Extract date from ISO timestamp."""
    if not ts:
        return "unknown"
    return ts[:10]


def print_full_decision(row):
    """Print a single decision with full detail."""
    num, project, desc, rationale, session_id, created_at = row
    date = format_date(created_at)
    sid = session_id[:8] if session_id else "unknown"

    print(f"Decision {num} ({date}, {project}, Session {sid}):")
    print(desc)
    if rationale:
        print()
        print(f"Rationale: {rationale}")


def print_search_results(rows, query):
    """Print multiple matching decisions in compact format."""
    print(f'Found {len(rows)} decision{"s" if len(rows) != 1 else ""} matching "{query}":')
    print()
    for row in rows:
        num, project, desc, rationale, session_id, created_at = row
        date = format_date(created_at)
        # Truncate description for list view
        short = desc.strip().split("\n")[0]
        if len(short) > 120:
            short = short[:117] + "..."
        print(f"  #{num} [{project}] - {short} ({date})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fast decision lookup by number or keyword",
        usage="python3 brain_decide.py NUMBER_OR_KEYWORD"
    )
    parser.add_argument("query", nargs="*", help="Decision number or keyword(s)")
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query:
        print("Usage: /brain-decide NUMBER or KEYWORD")
        print()
        print("Examples:")
        print("  /brain-decide 76")
        print("  /brain-decide hooks")
        print("  /brain-decide semantic search")
        sys.exit(0)

    root_path = get_root_path()
    config = load_config(root_path)
    db_path = config["storage"]["local_db_path"]
    conn = connect_db(db_path)

    try:
        # Check if query is a number
        try:
            num = int(query)
            row = lookup_by_number(conn, num)
            if row:
                print_full_decision(row)
            else:
                print(f"No decision found with number {num}.")
            return
        except ValueError:
            pass

        # Keyword search
        keywords = query.split()
        rows = search_by_keyword(conn, keywords)

        if not rows:
            print(f'No decisions found matching "{query}".')
        elif len(rows) == 1:
            print_full_decision(rows[0])
        else:
            print_search_results(rows, query)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
