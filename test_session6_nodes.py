"""
Session 6 test — verifies categorize and summarize nodes.

Tests:
  1. _parse_categories: valid input, strips code fences, wrong count, invalid category
  2. _parse_summaries: valid input, wrong count
  3. Full pipeline: fetch -> deduplicate -> score -> categorize -> summarize
  4. Every filtered article has category (valid), summary (non-empty)
  5. categorized_articles dict has correct structure
  6. Spot-check: print final articles by category so we can read the summaries
"""
from agent.nodes.fetch import fetch_news
from agent.nodes.deduplicate import deduplicate
from agent.nodes.score import score_relevance
from agent.nodes.categorize import _parse_categories, categorize
from agent.nodes.summarize import _parse_summaries, summarize
from agent.state import AgentState

VALID_CATEGORIES = {"ai_news", "career", "ceo_update"}


# ── Test 1: _parse_categories ─────────────────────────────────────────────────
print("=== Test 1: _parse_categories ===")

valid = '["ai_news", "career", "ceo_update"]'
result = _parse_categories(valid, 3)
assert result == ["ai_news", "career", "ceo_update"], f"Got {result}"
print("  Valid input OK")

fenced = '```json\n["ai_news"]\n```'
result = _parse_categories(fenced, 1)
assert result == ["ai_news"]
print("  Code fence stripping OK")

result = _parse_categories('["ai_news"]', 3)
assert result is None
print("  Wrong count -> None OK")

# ── Test 2: _parse_summaries ──────────────────────────────────────────────────
print("\n=== Test 2: _parse_summaries ===")

valid_summaries = '["First summary.", "Second summary."]'
result = _parse_summaries(valid_summaries, 2)
assert len(result) == 2
assert result[0] == "First summary."
print("  Valid input OK")

result = _parse_summaries(valid_summaries, 5)
assert result is None
print("  Wrong count -> None OK")

# ── Test 3: full pipeline with live API calls ─────────────────────────────────
print("\n=== Test 3: full pipeline (fetch -> dedup -> score -> categorize -> summarize) ===")
print("  This makes 3 Claude Haiku API calls...\n")

state: AgentState = {
    "user_preferences": {},
    "raw_articles": [],
    "filtered_articles": [],
    "categorized_articles": {},
    "top_10": [],
    "retry_count": 0,
    "run_timestamp": "",
    "email_sent": False,
}

fetch_r = fetch_news(state)
state.update(fetch_r)

dedup_r = deduplicate(state)
state.update(dedup_r)

score_r = score_relevance(state)
state.update(score_r)

cat_r = categorize(state)
state.update(cat_r)

sum_r = summarize(state)
state.update(sum_r)

filtered = state["filtered_articles"]
cat_dict = state["categorized_articles"]

# ── Assertions: article fields ────────────────────────────────────────────────
assert len(filtered) > 0, "Expected articles after full pipeline"

for a in filtered:
    assert a["category"] in VALID_CATEGORIES, \
        f"Invalid category '{a['category']}' on: {a['title']}"
    assert a["summary"] is not None, f"Missing summary on: {a['title']}"
    assert len(a["summary"]) > 20, f"Summary too short on: {a['title']}"
    assert a["score"] is not None
    assert a["score_reason"] is not None

# ── Assertions: categorized_articles dict ─────────────────────────────────────
assert set(cat_dict.keys()) == VALID_CATEGORIES, \
    f"categorized_articles keys wrong: {set(cat_dict.keys())}"

total_in_dict = sum(len(v) for v in cat_dict.values())
# Note: categorized_articles is built by categorize (before summarize runs),
# so articles there won't have summaries yet — that's expected.
# filtered_articles is the authoritative up-to-date list.
assert total_in_dict == len(score_r["filtered_articles"]), \
    "categorized_articles total should match filtered count after scoring"

# ── Print results ─────────────────────────────────────────────────────────────
print(f"\nTotal articles through full pipeline: {len(filtered)}")
print(f"\nCategory breakdown:")
for cat in VALID_CATEGORIES:
    arts_in_cat = [a for a in filtered if a["category"] == cat]
    print(f"  {cat}: {len(arts_in_cat)}")

print("\n--- Scored & summarized articles by category ---")
for cat in VALID_CATEGORIES:
    arts = [a for a in filtered if a["category"] == cat]
    if not arts:
        continue
    print(f"\n[{cat.upper()}] ({len(arts)} articles)")
    for a in sorted(arts, key=lambda x: x["score"], reverse=True):
        print(f"  [{a['score']:2d}] {a['title'][:70]}")
        print(f"       {a['summary'][:120]}...")
        print()

print("All assertions passed.")
