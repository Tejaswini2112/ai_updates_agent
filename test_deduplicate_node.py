"""
Session 4 test — verifies the deduplicate LangGraph node.

Tests:
  1. Real pipeline: fetch_news → deduplicate (smoke test on live data)
  2. URL dedup: exact-URL duplicate is removed, better tier wins
  3. Title dedup: similar-title articles collapse to one, better tier wins
  4. No false positives: distinct articles are NOT merged
"""
from agent.nodes.fetch import fetch_news
from agent.nodes.deduplicate import deduplicate, _title_similarity
from agent.state import AgentState, Article


def make_article(**overrides) -> Article:
    """Helper: build a minimal Article with sensible defaults."""
    base: Article = {
        "title": "Default Title",
        "url": "https://example.com/article",
        "description": "A description.",
        "source_name": "TestSource",
        "source_tier": 1,
        "published_at": "2026-05-02T00:00:00+00:00",
        "score": None,
        "score_reason": None,
        "category": None,
        "summary": None,
    }
    base.update(overrides)
    return base


def base_state(articles: list[Article]) -> AgentState:
    return {
        "user_preferences": {},
        "raw_articles": articles,
        "filtered_articles": [],
        "categorized_articles": {},
        "top_10": [],
        "retry_count": 0,
        "run_timestamp": "",
        "email_sent": False,
    }


# ── Test 1: title similarity function sanity check ────────────────────────────
print("=== Test 1: similarity function ===")

pairs = [
    ("OpenAI announces GPT-5", "OpenAI announces GPT-5", 0.95),
    ("Meta acquires robotics startup", "Meta acquires robotics startup for humanoid AI", 0.80),
    ("AI startup raises $100M funding", "AI company raises $200M in Series B", 0.50),
    ("Google releases Gemini 2.0", "Anthropic releases Claude 4", 0.40),
]
for a, b, min_expected in pairs:
    score = _title_similarity(a, b)
    print(f"  {score:.2f}  '{a[:40]}' vs '{b[:40]}'")

print()

# ── Test 2: URL dedup ─────────────────────────────────────────────────────────
print("=== Test 2: URL dedup ===")

url_dupes = [
    make_article(title="Meta buys robotics startup", url="https://tc.com/meta",
                 source_name="TechCrunch AI", source_tier=1, description="Short desc."),
    make_article(title="Meta buys robotics startup", url="https://tc.com/meta",
                 source_name="HackerNews",    source_tier=2, description="Even shorter."),
    make_article(title="Unrelated story",           url="https://vb.com/other",
                 source_name="VentureBeat AI", source_tier=1, description="Different story."),
]
result = deduplicate(base_state(url_dupes))
out = result["raw_articles"]
assert len(out) == 2, f"Expected 2, got {len(out)}"
meta_article = next(a for a in out if "Meta" in a["title"])
assert meta_article["source_tier"] == 1, "Tier 1 should win URL dedup"
assert meta_article["source_name"] == "TechCrunch AI", "TechCrunch (tier 1) should beat HN (tier 2)"
print(f"  URL dedup: 3 -> {len(out)} articles. Winner: {meta_article['source_name']} (tier {meta_article['source_tier']}) OK")

# ── Test 3: title similarity dedup ───────────────────────────────────────────
print("\n=== Test 3: title similarity dedup ===")

title_dupes = [
    make_article(title="OpenAI releases GPT-5 model",
                 url="https://techcrunch.com/openai-gpt5",
                 source_name="TechCrunch AI", source_tier=1,
                 description="Detailed editorial description with lots of context about the release."),
    make_article(title="OpenAI releases GPT-5 model",   # same normalized title → similarity = 1.0
                 url="https://news.ycombinator.com/item?id=99999",
                 source_name="HackerNews", source_tier=2,
                 description="HN thread."),
    make_article(title="Anthropic launches Claude 4",
                 url="https://venturebeat.com/claude4",
                 source_name="VentureBeat AI", source_tier=1,
                 description="A completely different story."),
]
result = deduplicate(base_state(title_dupes))
out = result["raw_articles"]
assert len(out) == 2, f"Expected 2, got {len(out)}"
gpt5_article = next(a for a in out if "GPT" in a["title"])
assert gpt5_article["source_tier"] == 1, "Tier 1 should win title dedup"
assert gpt5_article["source_name"] == "TechCrunch AI"
assert "Detailed editorial" in gpt5_article["description"], "Longer description should be kept"
print(f"  Title dedup: 3 -> {len(out)} articles. Winner: {gpt5_article['source_name']} OK")

# ── Test 4: no false positives ────────────────────────────────────────────────
print("\n=== Test 4: no false positives ===")

distinct = [
    make_article(title="OpenAI announces new reasoning model",    url="https://a.com/1"),
    make_article(title="Google DeepMind releases Gemini update",  url="https://b.com/2"),
    make_article(title="Anthropic raises $2B Series E funding",   url="https://c.com/3"),
    make_article(title="Meta open-sources new vision model",      url="https://d.com/4"),
    make_article(title="Nvidia announces new AI chip architecture", url="https://e.com/5"),
]
result = deduplicate(base_state(distinct))
out = result["raw_articles"]
assert len(out) == 5, f"Expected 5 distinct articles, got {len(out)}"
print(f"  5 distinct articles -> {len(out)} (no false merges) OK")

# ── Test 5: real pipeline (fetch → deduplicate) ───────────────────────────────
print("\n=== Test 5: real pipeline (fetch -> deduplicate) ===")

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

print("Fetching live articles...")
fetch_result = fetch_news(minimal_state)
minimal_state["raw_articles"] = fetch_result["raw_articles"]
before = len(minimal_state["raw_articles"])

dedup_result = deduplicate(minimal_state)
after = len(dedup_result["raw_articles"])

assert after <= before, "Dedup should never increase article count"
assert after > 0, "Should have at least some articles remaining"
assert "raw_articles" in dedup_result
assert "run_timestamp" not in dedup_result, "deduplicate should only update raw_articles"

print(f"\nPipeline result: {before} fetched -> {after} after dedup")
print(f"Dupes removed: {before - after}")

print("\nAll assertions passed.")
