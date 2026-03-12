#!/usr/bin/env python3
"""
clean_transcripts.py — Find and fix misspellings in transcript content.

Auto-detects typos by scanning the FTS5 vocabulary for rare terms that have
a close match with much higher frequency. Replaces typos in the transcripts
table directly — the FTS5 UPDATE trigger rebuilds the index automatically.

This is a recurring maintenance tool. Safe to run multiple times — each run
only fixes what's currently misspelled.

Usage:
    python3 clean_transcripts.py              # Dry run — show what would change
    python3 clean_transcripts.py --apply      # Actually fix the transcripts
    python3 clean_transcripts.py --verbose     # Show per-row details

Exit codes: 0 success, 1 error
"""

import argparse
import os
import pathlib
import re
import sqlite3
import sys

from difflib import get_close_matches

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
    import yaml
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
# Typo detection — scan FTS5 vocab for likely misspellings
# ---------------------------------------------------------------------------

# Import the shared stop words list
from fuzzy_search import STOP_WORDS

# Detection thresholds — VERY STRICT for bulk cleanup (not search-time correction)
# We only fix single-character typos (ED=1) to avoid false positives between
# real word pairs. Combined with dictionary check and morphological filtering,
# this catches obvious misspellings while leaving real words alone.
_RARE_DOC_MAX = 50        # Only consider terms appearing in < 50 docs
_RATIO_THRESHOLD = 2      # Candidate must have 2x+ higher frequency (low bar —
                          # dictionary filter is the main guard against false positives)
_CANDIDATE_DOC_MIN = 5    # Candidate must appear in at least this many docs
_FUZZY_CUTOFF = 0.85      # Strict similarity — only near-identical strings
_FUZZY_MAX_MATCHES = 3    # Candidates to evaluate per term
_MIN_TERM_LEN = 5         # Skip short terms (too many false positives)
_MAX_EDIT_DISTANCE = 1    # ONLY single-character typos (strictest filter)

# Technical terms not in system dictionaries but NOT typos.
# Covers: programming terms, tool names, product names, variable patterns.
_TECH_EXCLUSIONS = {
    # Programming / variable names
    "agentid", "groupid", "requestid", "dtype", "etree", "params", "rfind",
    "qname", "csharp", "ctags", "httpx", "jsonc", "ncast", "nrate", "ntokens",
    "pstyle", "sprefix", "tokend", "wdelay", "mtime", "oneline", "hardcodes",
    # Unix/Linux tools and concepts
    "dconf", "gdisk", "pgrep", "rclone", "rsync", "uname", "uinput", "uaccess",
    "exportfs", "livecd", "crond",
    # Brand/product names
    "ebook", "ebooks", "icloud", "imessage", "iphone", "oauth", "toptal",
    "ugreen", "minimap", "kforce",
    # HTML/CSS/XML/PDF attributes
    "valign", "vlookup", "xobjects",
    # File formats
    "pipfile",
    # Linux services/daemons
    "firewalld", "xwayland",
    # Real words the system dictionary misses
    "blogging", "blogs", "sourced", "prefs", "amature", "injested",
    # Brand/product names (continued)
    "carrd", "intacct", "igaming", "magick",
    # Usernames / proper names
    "mikeadolan", "tonys", "betts",
    # Variable names (continued)
    "projectid", "nconnection",
    # Linux commands
    "umount",
    # Fragments / wrong corrections (ED=1 finds wrong target)
    "spons", "erent", "sessing", "prohect", "infor", "assing",
    # Real terms misidentified as typos
    "cpython", "popen", "printf", "sprintf", "assed",
}

# Common English suffixes/prefixes — if the edit is just adding/removing one
# of these, it's a word variant, not a typo.
_SUFFIXES = {
    "s", "es", "ed", "er", "ly", "al", "ty", "ry", "le",
    "ing", "tion", "ment", "ness", "ble", "ful", "ous", "ive",
    "ist", "ity", "ize", "ise", "ant", "ent", "dom", "age",
    "ary", "ery", "ory", "ate", "ial", "ion",
}
_PREFIXES = {"un", "re", "pre", "dis", "mis", "non", "sub", "out", "over"}


def _is_morphological_variant(term: str, candidate: str) -> bool:
    """Check if two words are likely morphological variants, not typos.

    Returns True if the difference looks like adding/removing a common
    English suffix or prefix (e.g., "accessed" vs "access").
    """
    shorter, longer = (term, candidate) if len(term) <= len(candidate) else (candidate, term)

    # If shorter is a prefix of longer, check if the tail is a common suffix
    if longer.startswith(shorter):
        tail = longer[len(shorter):]
        if tail in _SUFFIXES:
            return True
        # Doubled consonant + suffix: "planned" = "plan" + "n" + "ed"
        if len(tail) >= 2 and tail[0] == shorter[-1]:
            if tail[1:] in _SUFFIXES or tail[1:] in {"s", "ed", "er", "ing"}:
                return True

    # If shorter is a suffix of longer, check if the head is a common prefix
    if longer.endswith(shorter):
        head = longer[:len(longer) - len(shorter)]
        if head in _PREFIXES:
            return True

    # Stem variations: "running" vs "run" (double consonant stripped)
    # "applied" vs "apply" (y→i + ed)
    # These are hard to catch generically, so check a few patterns:

    # Word ending in 'e' + suffix starting without 'e': "archive" vs "archiving"
    if shorter.endswith("e") and longer.startswith(shorter[:-1]):
        tail = longer[len(shorter) - 1:]
        if tail in _SUFFIXES or tail.startswith("ing") or tail.startswith("ed"):
            return True

    # Word ending in 'y' vs 'ies', 'ied', 'ier', 'ily'
    if shorter.endswith("y") and longer.startswith(shorter[:-1]):
        tail = longer[len(shorter) - 1:]
        if tail in {"ies", "ied", "ier", "ily", "iest"}:
            return True

    return False


def _edit_distance(s1: str, s2: str) -> int:
    """Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[len(s2)]


def _load_dictionary() -> set[str]:
    """Load system dictionary for real-word verification.

    If a term is in the dictionary, it's a real word and should NOT be
    treated as a typo, even if it's rare in the corpus and close to a
    more common word.
    """
    dict_paths = [
        "/usr/share/dict/words",           # Linux (Fedora, Ubuntu, etc.)
        "/usr/share/dict/american-english", # Debian/Ubuntu
    ]
    for path in dict_paths:
        if os.path.exists(path):
            with open(path) as f:
                return {line.strip().lower() for line in f if line.strip()}
    return set()


def detect_typos(conn):
    """Scan the FTS5 vocabulary and return a dict of {typo: correction}.

    Strict detection for bulk cleanup:
    - Term must be rare (doc < 50)
    - Close match must have 5x+ higher frequency
    - Close match must have doc >= 10
    - Similarity must be >= 0.85 (near-identical strings)
    - Edit distance must be exactly 1 (single-character typos only)
    - Term must NOT be in the system dictionary (real words are never "fixed")
    - Term must NOT be a morphological variant of the candidate

    This is much stricter than search-time fuzzy correction because
    we're modifying stored data, not just adjusting a query.
    """
    # Ensure vocab table exists
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS "
        "transcripts_fts_vocab USING fts5vocab(transcripts_fts, row)"
    )

    # Load all terms and frequencies
    rows = conn.execute(
        "SELECT term, doc FROM transcripts_fts_vocab "
        "WHERE length(term) >= 3 AND doc >= 1"
    ).fetchall()

    all_terms = {}
    for term, doc in rows:
        if term.isalpha() and term not in STOP_WORDS:
            all_terms[term] = doc

    # Build vocabulary list for difflib (only established terms make good targets)
    vocab_list = sorted(t for t, d in all_terms.items() if d >= _CANDIDATE_DOC_MIN)

    if not vocab_list:
        return {}

    # Load system dictionary — real words are never treated as typos,
    # and corrections must target real words (prevents chain corrections)
    dictionary = _load_dictionary()

    typo_map = {}  # {typo: correction}

    for term, doc in all_terms.items():
        # Skip established terms
        if doc >= _RARE_DOC_MAX:
            continue
        # Skip short terms (too many false positives)
        if len(term) < _MIN_TERM_LEN:
            continue
        # Skip real English words — the key filter that prevents false positives
        if term in dictionary:
            continue
        # Skip known technical terms not in the dictionary
        if term in _TECH_EXCLUSIONS:
            continue

        matches = get_close_matches(
            term, vocab_list, n=_FUZZY_MAX_MATCHES, cutoff=_FUZZY_CUTOFF
        )

        for candidate in matches:
            if candidate == term:
                continue

            # Strict: edit distance must be small (1-2 chars off)
            ed = _edit_distance(term, candidate)
            if ed > _MAX_EDIT_DISTANCE:
                continue

            # Strict: length difference must be small
            if abs(len(term) - len(candidate)) > _MAX_EDIT_DISTANCE:
                continue

            # Filter out morphological variants (real word pairs)
            if _is_morphological_variant(term, candidate):
                continue

            # Correction target must be a real word — prevents chain corrections
            # where one typo corrects to another typo (e.g., "eveyrthing" → "eveything")
            if candidate not in dictionary and all_terms.get(candidate, 0) < _RARE_DOC_MAX:
                continue

            cand_freq = all_terms.get(candidate, 0)

            # Rare term — need higher frequency correction target
            if cand_freq >= max(doc * _RATIO_THRESHOLD, _CANDIDATE_DOC_MIN):
                typo_map[term] = candidate
                break

    return typo_map


# ---------------------------------------------------------------------------
# Transcript repair
# ---------------------------------------------------------------------------

def fix_transcripts(conn, typo_map, apply=False, verbose=False):
    """Find and replace typos in transcripts.content.

    Uses word-boundary regex for case-insensitive replacement.
    Preserves original casing of surrounding text.

    Returns: dict with stats {typo: {rows_affected, occurrences}}
    """
    stats = {}

    for typo, correction in sorted(typo_map.items()):
        # Find transcripts containing this typo (word boundary match)
        # SQLite LIKE is case-insensitive for ASCII, but we need word boundaries
        # So fetch candidates with LIKE, then filter with regex in Python
        rows = conn.execute(
            "SELECT id, content FROM transcripts "
            "WHERE content LIKE ? AND content IS NOT NULL",
            (f"%{typo}%",),
        ).fetchall()

        if not rows:
            continue

        # Word-boundary regex: match the typo as a whole word, case-insensitive
        pattern = re.compile(r'\b' + re.escape(typo) + r'\b', re.IGNORECASE)

        rows_affected = 0
        total_occurrences = 0

        for row_id, content in rows:
            # Count matches
            matches = pattern.findall(content)
            if not matches:
                continue

            new_content = pattern.sub(correction, content)
            if new_content == content:
                continue

            occurrences = len(matches)
            rows_affected += 1
            total_occurrences += occurrences

            if verbose:
                # Show first match context
                m = pattern.search(content)
                if m:
                    start = max(0, m.start() - 30)
                    end = min(len(content), m.end() + 30)
                    context = content[start:end].replace("\n", " ")
                    print(f"  Row {row_id}: ...{context}...")

            if apply:
                conn.execute(
                    "UPDATE transcripts SET content = ? WHERE id = ?",
                    (new_content, row_id),
                )

        if rows_affected > 0:
            stats[typo] = {
                "correction": correction,
                "rows": rows_affected,
                "occurrences": total_occurrences,
            }

    if apply and stats:
        conn.commit()

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Find and fix misspellings in transcript content",
        usage="python3 clean_transcripts.py [--apply] [--verbose]",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually fix transcripts (default is dry run)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show per-row match details",
    )
    args = parser.parse_args()

    root_path = get_root_path()
    config = load_config(root_path)
    db_path = config["storage"]["local_db_path"]
    conn = connect_db(db_path)

    try:
        # Step 1: Detect typos from FTS5 vocabulary
        print("Scanning FTS5 vocabulary for misspellings...")
        typo_map = detect_typos(conn)

        if not typo_map:
            print("No typos detected. Vocabulary looks clean.")
            return

        print(f"Found {len(typo_map)} likely misspelling(s):")
        print()
        for typo, correction in sorted(typo_map.items()):
            print(f"  {typo} → {correction}")
        print()

        # Step 2: Find and fix in transcripts
        mode = "APPLYING fixes" if args.apply else "DRY RUN (use --apply to fix)"
        print(f"{mode}...")
        print()

        stats = fix_transcripts(conn, typo_map, apply=args.apply, verbose=args.verbose)

        if not stats:
            print("No transcript rows contain these misspellings. Nothing to fix.")
            return

        # Step 3: Report
        total_rows = sum(s["rows"] for s in stats.values())
        total_occurrences = sum(s["occurrences"] for s in stats.values())

        print(f"{'Fixed' if args.apply else 'Would fix'} {total_occurrences} "
              f"occurrence(s) across {total_rows} row(s):")
        print()
        for typo, s in sorted(stats.items()):
            print(f"  {typo} → {s['correction']}: "
                  f"{s['occurrences']} occurrences in {s['rows']} rows")

        if args.apply:
            # Clear fuzzy search cache so next search picks up updated vocab
            from fuzzy_search import clear_cache
            clear_cache()
            print()
            print("Done. FTS5 index updated via triggers. Fuzzy cache cleared.")
        else:
            print()
            print("Re-run with --apply to fix these.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
