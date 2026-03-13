#!/usr/bin/env python3
"""
impact_check.py -- Pre-change impact analysis for claude-brain.

Run BEFORE any code change to see every file that references the terms
you're about to modify. Run AFTER with the OLD terms to confirm zero
stale references remain.

Usage:
    python3 scripts/impact_check.py "search_term1" "search_term2" ...
    python3 scripts/impact_check.py --category code "generate_summary"
    python3 scripts/impact_check.py --count-only "mcp"

Examples:
    # Before removing a function:
    python3 scripts/impact_check.py "generate_summary" "summary_llm"

    # Before renaming a table:
    python3 scripts/impact_check.py "sys_session_summaries"

    # Quick count -- how widespread is this term?
    python3 scripts/impact_check.py --count-only "brain-server"
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {
    '.git', '__pycache__', 'node_modules', 'chat-logs', 'jsonl-archive',
    'exports', 'mike-brain', 'chat-files', 'claude-brain-local',
    'memory', '.claude',
}

SKIP_FILES = {
    'impact_check.py',  # don't report ourselves
}

CATEGORIES = {
    'CODE': {'.py'},
    'CONFIG': {'.yaml', '.json', '.example', '.cfg', '.ini', '.toml'},
    'DOCS': {'.md', '.txt'},
    'SCRIPTS (shell)': {'.sh'},
    'OTHER': set(),
}

VERIFICATION_DIR = 'verification'


def categorize(filepath):
    """Categorize a file by its extension and location."""
    rel = os.path.relpath(filepath, ROOT)
    ext = os.path.splitext(filepath)[1].lower()

    if rel.startswith(VERIFICATION_DIR + os.sep):
        return 'TESTS'

    for cat, extensions in CATEGORIES.items():
        if cat == 'OTHER':
            continue
        if ext in extensions:
            return cat

    return 'OTHER'


def search(terms, category_filter=None):
    """Search all files for all terms. Returns {category: [(file, line_num, line, term)]}."""
    results = {}

    for dirpath, dirnames, filenames in os.walk(ROOT):
        # prune skipped directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            if filename in SKIP_FILES:
                continue

            filepath = os.path.join(dirpath, filename)
            cat = categorize(filepath)

            if category_filter and cat != category_filter:
                continue

            # skip binary files
            try:
                with open(filepath, 'r', encoding='utf-8', errors='strict') as f:
                    lines = f.readlines()
            except (UnicodeDecodeError, PermissionError):
                continue

            for i, line in enumerate(lines, 1):
                for term in terms:
                    if term.lower() in line.lower():
                        if cat not in results:
                            results[cat] = []
                        results[cat].append((
                            os.path.relpath(filepath, ROOT),
                            i,
                            line.rstrip(),
                            term,
                        ))
                        break  # one match per line is enough

    return results


def print_report(results, terms, count_only=False):
    """Print categorized impact report."""
    total = sum(len(hits) for hits in results.values())

    print()
    print("=" * 70)
    print(f"  IMPACT ANALYSIS: {', '.join(terms)}")
    print("=" * 70)

    if total == 0:
        print("\n  No references found. Safe to proceed.\n")
        return

    # sort categories in display order
    order = ['CODE', 'CONFIG', 'SCRIPTS (shell)', 'DOCS', 'TESTS', 'OTHER']
    sorted_cats = sorted(results.keys(), key=lambda c: order.index(c) if c in order else 99)

    for cat in sorted_cats:
        hits = results[cat]
        print(f"\n  {cat} ({len(hits)} references):")
        print("  " + "-" * 50)

        if count_only:
            # group by file, show count per file
            file_counts = {}
            for filepath, _, _, _ in hits:
                file_counts[filepath] = file_counts.get(filepath, 0) + 1
            for filepath, count in sorted(file_counts.items()):
                print(f"    {filepath}: {count}")
        else:
            # group by file, show each line
            current_file = None
            for filepath, line_num, line, term in hits:
                if filepath != current_file:
                    if current_file is not None:
                        print()
                    print(f"    {filepath}:")
                    current_file = filepath
                # truncate long lines
                display = line.strip()
                if len(display) > 100:
                    display = display[:97] + "..."
                print(f"      L{line_num}: {display}")

    print()
    print("  " + "=" * 50)
    print(f"  TOTAL: {total} references across {len(set(h[0] for hits in results.values() for h in hits))} files")
    print("  " + "=" * 50)
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Pre-change impact analysis for claude-brain.',
        epilog='Run BEFORE changes to see what is affected. Run AFTER with OLD terms to verify cleanup.',
    )
    parser.add_argument('terms', nargs='+', help='Search terms (case-insensitive)')
    parser.add_argument('--category', choices=['CODE', 'CONFIG', 'DOCS', 'TESTS', 'OTHER'],
                        help='Filter to one category')
    parser.add_argument('--count-only', action='store_true',
                        help='Show file counts only, not individual lines')

    args = parser.parse_args()

    results = search(args.terms, category_filter=args.category)
    print_report(results, args.terms, count_only=args.count_only)

    # exit code: 0 if no references (safe), 1 if references found
    total = sum(len(hits) for hits in results.values())
    sys.exit(0 if total == 0 else 1)


if __name__ == '__main__':
    main()
