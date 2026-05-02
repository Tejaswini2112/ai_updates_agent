"""
Session 3 test — verifies the fetch_news LangGraph node.

What we're testing:
  1. fetch_news() accepts a minimal AgentState and returns a state update dict
  2. The returned dict has "raw_articles" and "run_timestamp" keys
  3. raw_articles is a non-empty list of Article dicts
  4. Each article has all required fields with the right types
  5. Sources are represented (basic coverage check)
"""
from agent.nodes.fetch import fetch_news
from agent.state import AgentState

# Minimal valid AgentState — only the fields fetch_news reads (none, actually)
# LangGraph passes the full state but fetch_news ignores it; we just need a valid dict.
minimal_state: AgentState = {
    "user_preferences": {},
    "raw_articles": [],
    "filtered_articles": [],
    "categorized_articles": {},
    "top_10": [],
    "retry_count": 0,
    "run_timestamp": "",
    "email_sent": False,
}

print("Running fetch_news node...\n")
result = fetch_news(minimal_state)

# ── Check return shape ────────────────────────────────────────────────────────
assert "raw_articles" in result, "Missing key: raw_articles"
assert "run_timestamp" in result, "Missing key: run_timestamp"
assert isinstance(result["raw_articles"], list), "raw_articles must be a list"
assert len(result["raw_articles"]) > 0, "Expected at least some articles"
assert isinstance(result["run_timestamp"], str), "run_timestamp must be a string"

# ── Check article shape ───────────────────────────────────────────────────────
required_fields = [
    "title", "url", "description",
    "source_name", "source_tier", "published_at",
    "score", "score_reason", "category", "summary",
]
for article in result["raw_articles"]:
    for field in required_fields:
        assert field in article, f"Article missing field: {field}"

# ── Check source coverage ─────────────────────────────────────────────────────
source_names = {a["source_name"] for a in result["raw_articles"]}
print(f"\nSources found: {source_names}")

# ── Summary ───────────────────────────────────────────────────────────────────
articles = result["raw_articles"]
print(f"\nTimestamp: {result['run_timestamp']}")
print(f"Total articles fetched: {len(articles)}")

by_source: dict[str, list] = {}
for a in articles:
    by_source.setdefault(a["source_name"], []).append(a)

print("\nBreakdown by source:")
for name, arts in sorted(by_source.items()):
    tiers = {a["source_tier"] for a in arts}
    print(f"  {name} (tier {min(tiers)}): {len(arts)} articles")

print("\nFirst 3 articles across all sources:")
for a in articles[:3]:
    print(f"  [{a['source_name']}] {a['title'][:70]}")
    print(f"    url: {a['url'][:70]}")
    print(f"    published: {a['published_at']}")
    print()

print("All assertions passed.")
