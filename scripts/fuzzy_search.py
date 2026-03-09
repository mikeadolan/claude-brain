"""Fuzzy search module for claude-brain.

Provides vocabulary extraction from the FTS5 index and fuzzy matching
using difflib.get_close_matches(). Used by mcp/server.py, brain_search.py,
and brain_query.py to correct typos BEFORE the FTS query runs.

Correction rules:
1. Terms not in the FTS index at all → corrected to best close match (doc >= 10)
2. Terms in the index but rare (doc < 100) → corrected only if a close match
   has 20x+ higher frequency (e.g., "sesion" doc=10 → "session" doc=1700)
3. Terms with doc >= 100 → never corrected (established words)

This handles typos that accumulate in the index from past conversations
while avoiding false corrections between legitimate word variants.
"""

import sqlite3
from difflib import get_close_matches

# ---------------------------------------------------------------------------
# Stop words — superset from all search files
# ---------------------------------------------------------------------------
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
    "as", "through", "during", "before", "after", "above", "below",
    "between", "under", "over", "again", "further", "once", "both",
    "few", "own", "same", "such", "only", "too", "most",
    "down", "off", "why", "because", "until", "while",
    "him", "her", "his", "its", "them", "those", "these",
    "been", "being", "doing", "having", "he", "she",
    "himself", "herself", "itself", "themselves", "ourselves",
    "dare", "ought", "used",
}

# Correction thresholds
_ESTABLISHED_DOC_MIN = 100   # Terms with this many+ docs are never corrected
_RATIO_THRESHOLD = 20        # In-vocab terms need a close match with 20x+ freq to correct
_CANDIDATE_DOC_MIN = 10      # Candidates must appear in at least this many docs

# Module-level caches: { db_path: data }
_vocab_cache: dict[str, list[str]] = {}      # Sorted list for get_close_matches
_freq_cache: dict[str, dict[str, int]] = {}  # term → doc count


def _ensure_vocab_table(conn: sqlite3.Connection) -> None:
    """Create the FTS5 vocab table if it doesn't exist."""
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS "
        "transcripts_fts_vocab USING fts5vocab(transcripts_fts, row)"
    )


def _is_valid_term(term: str) -> bool:
    """Check if a term is a valid vocabulary word."""
    return term.isalpha() and term not in STOP_WORDS


def _load_vocab(db_path: str) -> None:
    """Load vocabulary and frequencies from FTS5 index into caches."""
    if db_path in _vocab_cache:
        return

    conn = sqlite3.connect(db_path)
    try:
        _ensure_vocab_table(conn)
        rows = conn.execute(
            "SELECT term, doc FROM transcripts_fts_vocab "
            "WHERE length(term) >= 3 AND doc >= 2"
        ).fetchall()
    finally:
        conn.close()

    vocab = set()
    freq = {}
    for term, doc in rows:
        if not _is_valid_term(term):
            continue
        vocab.add(term)
        freq[term] = doc

    _vocab_cache[db_path] = sorted(vocab)
    _freq_cache[db_path] = freq


def get_vocabulary(db_path: str) -> list[str]:
    """Extract unique meaningful terms from the FTS5 index.

    Returns a sorted list of lowercase terms (3+ chars, alpha-only,
    no stop words, appearing in 2+ docs). Cached per process.
    """
    _load_vocab(db_path)
    return _vocab_cache[db_path]


def get_frequencies(db_path: str) -> dict[str, int]:
    """Get doc frequency for each vocabulary term. Cached per process."""
    _load_vocab(db_path)
    return _freq_cache[db_path]


def clear_cache() -> None:
    """Clear all caches (useful for testing)."""
    _vocab_cache.clear()
    _freq_cache.clear()


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

FUZZY_CUTOFF = 0.6  # Minimum similarity ratio for a match
FUZZY_MAX_MATCHES = 5  # Candidates to consider per term


def fuzzy_correct(terms: list[str], db_path: str) -> tuple[list[str], dict[str, str]]:
    """Correct likely typos in search terms using vocabulary frequency.

    For each term:
    - If not in FTS index at all (doc=0): corrects to best close match
      that has doc >= 10 (clearly established in the corpus).
    - If in index but rare (doc < 100): corrects only if a close match
      has 20x+ higher doc frequency (typo vs real word).
    - If doc >= 100: never corrected (established word, even if similar
      to a higher-frequency word).

    Args:
        terms: List of search keywords (lowercase).
        db_path: Path to the brain database.

    Returns:
        (corrected_terms, corrections_map)
        - corrected_terms: list with typos replaced by best match.
        - corrections_map: {original: corrected} for terms that were changed.
          Empty dict means no corrections were needed.
    """
    vocab_list = get_vocabulary(db_path)
    freq = get_frequencies(db_path)
    if not vocab_list:
        return terms, {}

    corrected = []
    corrections = {}
    for term in terms:
        if term in STOP_WORDS:
            corrected.append(term)
            continue

        term_freq = freq.get(term, 0)

        # Established words are never corrected
        if term_freq >= _ESTABLISHED_DOC_MIN:
            corrected.append(term)
            continue

        # Find close matches
        matches = get_close_matches(
            term, vocab_list, n=FUZZY_MAX_MATCHES, cutoff=FUZZY_CUTOFF
        )
        if not matches:
            corrected.append(term)
            continue

        # Find the best candidate: first close match (by similarity) that
        # isn't the term itself and meets frequency requirements
        found = False
        for candidate in matches:
            if candidate == term:
                continue
            cand_freq = freq.get(candidate, 0)

            if term_freq == 0:
                # Term not in vocab at all — correct to any established match
                if cand_freq >= _CANDIDATE_DOC_MIN:
                    corrected.append(candidate)
                    corrections[term] = candidate
                    found = True
                    break
            else:
                # Term is in vocab but rare — need overwhelming freq difference
                if cand_freq >= term_freq * _RATIO_THRESHOLD:
                    corrected.append(candidate)
                    corrections[term] = candidate
                    found = True
                    break

        if not found:
            corrected.append(term)

    return corrected, corrections
