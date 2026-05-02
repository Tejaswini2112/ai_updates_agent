"""
Session 5 test — verifies the score_relevance LangGraph node.

Tests:
  1. _parse_scores: valid JSON array passes through
  2. _parse_scores: markdown code fences are stripped
  3. _parse_scores: wrong count returns None
  4. _parse_scores: malformed entry returns None
  5. Full pipeline: fetch -> deduplicate -> score (live API call, real articles)
  6. Threshold filtering: articles below RELEVANCE_THRESHOLD are dropped
  7. Scored articles have score and score_reason populated
"""
from agent.nodes.score import _build_prompt, _parse_scores, score_relevance
from agent.nodes.fetch import fetch_news
from agent.nodes.deduplicate import deduplicate
from agent.state import AgentState, Article
from config import RELEVANCE_THRESHOLD


def make_article(**overrides) -> Article:
    base: Article = {
        "title": "Default Title",
        "url": "https://example.com/article",
        "description": "A description.",
        "source_name": "TechCrunch AI",
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


# ── Test 1: _parse_scores — valid input ──────────────────────────────────────
print("=== Test 1: _parse_scores valid input ===")

valid_json = '[{"score": 8, "reason": "Major LLM release"}, {"score": 3, "reason": "Off topic"}]'
result = _parse_scores(valid_json, 2)
assert result is not None
assert len(result) == 2
assert result[0]["score"] == 8
assert result[1]["reason"] == "Off topic"
print("  Parsed correctly OK")

# ── Test 2: _parse_scores — strips markdown code fences ──────────────────────
print("\n=== Test 2: _parse_scores strips code fences ===")

fenced = '```json\n[{"score": 7, "reason": "Relevant"}]\n```'
result = _parse_scores(fenced, 1)
assert result is not None
assert result[0]["score"] == 7
print("  Stripped code fences OK")

# ── Test 3: _parse_scores — wrong count returns None ─────────────────────────
print("\n=== Test 3: _parse_scores wrong count ===")

wrong_count = '[{"score": 5, "reason": "ok"}]'
result = _parse_scores(wrong_count, 3)
assert result is None
print("  Wrong count -> None OK")

# ── Test 4: _parse_scores — malformed entry returns None ─────────────────────
print("\n=== Test 4: _parse_scores malformed entry ===")

missing_reason = '[{"score": 5}]'
result = _parse_scores(missing_reason, 1)
assert result is None
print("  Missing 'reason' -> None OK")

# ── Test 5: _build_prompt includes all articles ───────────────────────────────
print("\n=== Test 5: _build_prompt structure ===")

articles = [
    make_article(title="GPT-5 Released",       source_name="TechCrunch AI",  source_tier=1),
    make_article(title="Cooking Recipe Blog",  source_name="HackerNews",     source_tier=2),
]
prompt = _build_prompt(articles)
assert "[1]" in prompt
assert "[2]" in prompt
assert "GPT-5 Released" in prompt
assert "Cooking Recipe Blog" in prompt
assert "exactly 2" in prompt
print("  Prompt contains all articles and correct count OK")

# ── Test 6: full pipeline with live API call ──────────────────────────────────
print("\n=== Test 6: full pipeline (fetch -> deduplicate -> score) ===")
print("  This makes a real Claude Haiku API call...\n")

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

fetch_result    = fetch_news(minimal_state)
minimal_state["raw_articles"] = fetch_result["raw_articles"]
minimal_state["run_timestamp"] = fetch_result["run_timestamp"]

dedup_result    = deduplicate(minimal_state)
minimal_state["raw_articles"] = dedup_result["raw_articles"]

score_result    = score_relevance(minimal_state)

filtered = score_result["filtered_articles"]

# ── Assertions ────────────────────────────────────────────────────────────────
assert "filtered_articles" in score_result
assert isinstance(filtered, list)
assert len(filtered) > 0, "Expected at least some articles to pass scoring"

for a in filtered:
    assert a["score"] is not None,        f"Article missing score: {a['title']}"
    assert a["score_reason"] is not None, f"Article missing score_reason: {a['title']}"
    assert 1 <= a["score"] <= 10,         f"Score out of range: {a['score']}"
    assert a["score"] >= RELEVANCE_THRESHOLD, (
        f"Article below threshold slipped through: {a['title']} scored {a['score']}"
    )

# ── Print top 10 scored articles ──────────────────────────────────────────────
print(f"\nArticles passing threshold (score >= {RELEVANCE_THRESHOLD}): {len(filtered)}")
print("\nTop 10 by score:")
for a in sorted(filtered, key=lambda x: x["score"], reverse=True)[:10]:
    print(f"  [{a['score']:2d}] [{a['source_name'][:15]:15s}] {a['title'][:65]}")
    print(f"        {a['score_reason']}")

print("\nAll assertions passed.")
