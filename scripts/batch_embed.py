#!/usr/bin/env python3
"""
batch_embed.py - Backfill embeddings for all un-embedded transcripts.

Reuses embed_message() from write_exchange.py. Processes in batches of 500
with progress reporting. Safe to re-run (INSERT OR REPLACE).

Usage:
    python3 scripts/batch_embed.py
"""

import os
import sys
import time
import sqlite3
import yaml

# Suppress HuggingFace noise
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TQDM_DISABLE"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from write_exchange import embed_message, SEMANTIC_AVAILABLE
import logging

logger = logging.getLogger("batch_embed")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def load_config():
    config_path = os.path.join(ROOT, "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def main():
    if not SEMANTIC_AVAILABLE:
        print("ERROR: sentence-transformers or numpy not available.")
        sys.exit(1)

    config = load_config()
    db_path = config["storage"]["local_db_path"]
    conn = sqlite3.connect(db_path)

    # Find un-embedded transcripts with content >= 50 chars
    rows = conn.execute("""
        SELECT t.id, t.content
        FROM transcripts t
        LEFT JOIN transcript_embeddings te ON t.id = te.transcript_id
        WHERE te.transcript_id IS NULL
          AND t.content IS NOT NULL
          AND LENGTH(TRIM(t.content)) >= 50
        ORDER BY t.id
    """).fetchall()

    # Also count those that will be skipped (short/empty content)
    skip_count = conn.execute("""
        SELECT COUNT(*)
        FROM transcripts t
        LEFT JOIN transcript_embeddings te ON t.id = te.transcript_id
        WHERE te.transcript_id IS NULL
          AND (t.content IS NULL OR LENGTH(TRIM(t.content)) < 50)
    """).fetchone()[0]

    total = len(rows)
    print(f"Transcripts to embed: {total}")
    print(f"Skipping (short/empty): {skip_count}")

    if total == 0:
        print("Nothing to do.")
        conn.close()
        return

    embedded = 0
    failed = 0
    start = time.time()
    batch_size = 500

    for i, (tid, content) in enumerate(rows, 1):
        try:
            embed_message(config, conn, tid, content, logger)
            embedded += 1
        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  Failed transcript {tid}: {e}")

        if i % batch_size == 0:
            conn.commit()
            elapsed = time.time() - start
            rate = i / elapsed
            remaining = (total - i) / rate
            print(f"  {i}/{total} ({i*100//total}%) - {rate:.0f}/sec - ~{remaining:.0f}s remaining")

    conn.commit()
    conn.close()

    elapsed = time.time() - start
    print(f"\nDone: {embedded} embedded, {failed} failed, {elapsed:.1f}s total ({embedded/elapsed:.0f}/sec)")


if __name__ == "__main__":
    main()
