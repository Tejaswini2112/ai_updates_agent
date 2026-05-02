"""
Session 9 test — verifies database.py SQLite persistence.

Tests:
  1. init_db creates tables without error
  2. save_run inserts run + articles, returns run_id
  3. save_run is idempotent (same timestamp -> same run_id, no duplicate)
  4. get_latest_run returns most recent run
  5. get_run_history returns list of run summaries, newest first
  6. get_run_articles returns articles for a specific run_id

Uses a temp DB so it does not touch data/briefings.db.
"""
import tempfile
from pathlib import Path

# Patch DB_PATH before any database function is called.
# Python module cache means this affects all subsequent calls in this process.
import database
_tmp = tempfile.mktemp(suffix=".db")
database.DB_PATH = Path(_tmp)

from database import init_db, save_run, get_latest_run, get_run_history, get_run_articles
from agent.state import Article


def make_article(n: int) -> Article:
    return {
        "title":        f"Article {n}",
        "url":          f"https://example.com/{n}",
        "description":  "A description.",
        "source_name":  "TechCrunch AI",
        "source_tier":  1,
        "published_at": "2026-05-02T10:00:00+00:00",
        "score":        10 - n,
        "score_reason": "Very relevant.",
        "category":     "ai_news",
        "summary":      f"Summary for article {n}.",
    }


# ── Test 1: init_db ───────────────────────────────────────────────────────────
print("=== Test 1: init_db creates tables ===")
init_db()
init_db()  # safe to call twice
print("  init_db (called twice) OK")

# ── Test 2: save_run inserts run + articles ───────────────────────────────────
print("\n=== Test 2: save_run inserts run and articles ===")

articles_a = [make_article(i) for i in range(5)]
run_id_a = save_run("2026-05-01T08:00:00+00:00", articles_a)
assert isinstance(run_id_a, int) and run_id_a > 0, f"Expected positive int, got {run_id_a}"

# Verify articles were inserted
saved = get_run_articles(run_id_a)
assert len(saved) == 5, f"Expected 5 articles, got {len(saved)}"
assert saved[0]["score"] >= saved[-1]["score"], "Articles should be sorted by score DESC"
assert saved[0]["title"] == "Article 0"
print(f"  run_id={run_id_a}, {len(saved)} articles saved and retrieved OK")

# ── Test 3: idempotency — same timestamp returns same run_id ──────────────────
print("\n=== Test 3: save_run idempotency ===")

run_id_a2 = save_run("2026-05-01T08:00:00+00:00", articles_a)
assert run_id_a2 == run_id_a, f"Expected same run_id {run_id_a}, got {run_id_a2}"
all_articles = get_run_articles(run_id_a)
assert len(all_articles) == 5, f"Duplicate save should not add more articles, got {len(all_articles)}"
print(f"  Same timestamp -> same run_id={run_id_a} OK, no duplicate articles OK")

# ── Test 4: get_latest_run ────────────────────────────────────────────────────
print("\n=== Test 4: get_latest_run returns most recent run ===")

# Add a newer run
articles_b = [make_article(i) for i in range(3)]
run_id_b = save_run("2026-05-02T08:00:00+00:00", articles_b)
assert run_id_b != run_id_a

result = get_latest_run()
assert result is not None, "get_latest_run should not return None after saves"
run_info, arts = result
assert run_info["run_timestamp"] == "2026-05-02T08:00:00+00:00", (
    f"Expected 2026-05-02 run, got {run_info['run_timestamp']}"
)
assert len(arts) == 3, f"Expected 3 articles for latest run, got {len(arts)}"
print(f"  Latest run = {run_info['run_timestamp'][:10]}, {len(arts)} articles OK")

# ── Test 5: get_run_history ───────────────────────────────────────────────────
print("\n=== Test 5: get_run_history returns newest first ===")

history = get_run_history()
assert len(history) == 2, f"Expected 2 runs in history, got {len(history)}"
assert history[0]["run_timestamp"] > history[1]["run_timestamp"], "Should be newest first"
assert history[0]["article_count"] == 3
assert history[1]["article_count"] == 5
print(f"  {len(history)} runs, newest first: {[r['run_timestamp'][:10] for r in history]} OK")

# ── Test 6: get_run_articles for a specific run ───────────────────────────────
print("\n=== Test 6: get_run_articles for specific run_id ===")

arts_for_a = get_run_articles(run_id_a)
arts_for_b = get_run_articles(run_id_b)
assert len(arts_for_a) == 5
assert len(arts_for_b) == 3
# Scores should be DESC
for i in range(len(arts_for_a) - 1):
    assert arts_for_a[i]["score"] >= arts_for_a[i + 1]["score"]
print(f"  run_id={run_id_a}: {len(arts_for_a)} articles, run_id={run_id_b}: {len(arts_for_b)} articles OK")
print("  Scores sorted DESC OK")

print("\nAll assertions passed.")
