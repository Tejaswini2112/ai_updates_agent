"""
Session 7 test — verifies the rank LangGraph node.

Tests:
  1. Scores sort descending
  2. TOP_N cap is enforced
  3. Tiebreaker: same score, Tier 1 beats Tier 2
  4. categorized_articles is rebuilt from top_10 (not full filtered list)
  5. categorized_articles articles have summaries (confirms it uses post-summarize data)
  6. Full pipeline: fetch -> dedup -> score -> categorize -> summarize -> rank
"""
from agent.nodes.fetch import fetch_news
from agent.nodes.deduplicate import deduplicate
from agent.nodes.score import score_relevance
from agent.nodes.categorize import categorize
from agent.nodes.summarize import summarize
from agent.nodes.rank import rank
from agent.state import AgentState, Article
from config import TOP_N


def make_article(**overrides) -> Article:
    base: Article = {
        "title": "Default Title",
        "url": "https://example.com/1",
        "description": "A description.",
        "source_name": "TechCrunch AI",
        "source_tier": 1,
        "published_at": "2026-05-02T00:00:00+00:00",
        "score": 7,
        "score_reason": "Relevant",
        "category": "ai_news",
        "summary": "A summary.",
    }
    base.update(overrides)
    return base


def base_state(articles: list[Article]) -> AgentState:
    return {
        "user_preferences": {},
        "raw_articles": [],
        "filtered_articles": articles,
        "categorized_articles": {},
        "top_10": [],
        "retry_count": 0,
        "run_timestamp": "",
        "email_sent": False,
    }


# ── Test 1: scores sort descending ────────────────────────────────────────────
print("=== Test 1: scores sort descending ===")

articles = [
    make_article(title="Low",    score=3, url="https://a.com/1"),
    make_article(title="High",   score=9, url="https://a.com/2"),
    make_article(title="Medium", score=6, url="https://a.com/3"),
]
result = rank(base_state(articles))
top = result["top_10"]
assert top[0]["score"] == 9, f"Expected 9 first, got {top[0]['score']}"
assert top[1]["score"] == 6
assert top[2]["score"] == 3
print(f"  Scores in order: {[a['score'] for a in top]} OK")

# ── Test 2: TOP_N cap ─────────────────────────────────────────────────────────
print("\n=== Test 2: TOP_N cap ===")

many = [make_article(title=f"Article {i}", score=i % 10 + 1, url=f"https://a.com/{i}")
        for i in range(25)]
result = rank(base_state(many))
assert len(result["top_10"]) == TOP_N, f"Expected {TOP_N}, got {len(result['top_10'])}"
print(f"  25 articles -> top {len(result['top_10'])} (TOP_N={TOP_N}) OK")

# ── Test 3: tiebreaker — Tier 1 beats Tier 2 at same score ───────────────────
print("\n=== Test 3: tiebreaker ===")

tied = [
    make_article(title="HN article",  score=8, source_tier=2, url="https://a.com/hn"),
    make_article(title="TC article",  score=8, source_tier=1, url="https://a.com/tc"),
]
result = rank(base_state(tied))
assert result["top_10"][0]["source_tier"] == 1, "Tier 1 should beat Tier 2 at same score"
assert result["top_10"][0]["title"] == "TC article"
print(f"  Tier 1 wins tiebreak at same score OK")

# ── Test 4: categorized_articles uses top_10, not full filtered list ──────────
print("\n=== Test 4: categorized_articles from top_10 ===")

# ai_news scores 10..3 (8 articles), career all score 2, ceo_update all score 1.
# Top 10 = all 8 ai_news + 2 career — ceo_update (score 1) never makes it in.
mix = (
    [make_article(title=f"AI {i}",     score=10-i, category="ai_news",    url=f"https://a.com/ai{i}")  for i in range(8)] +
    [make_article(title=f"Career {i}", score=2,    category="career",     url=f"https://a.com/c{i}")   for i in range(5)] +
    [make_article(title=f"CEO {i}",    score=1,    category="ceo_update", url=f"https://a.com/ceo{i}") for i in range(5)]
)
result = rank(base_state(mix))
top_10 = result["top_10"]
cat_dict = result["categorized_articles"]

total_in_cat = sum(len(v) for v in cat_dict.values())
assert total_in_cat == len(top_10), (
    f"categorized_articles total ({total_in_cat}) != top_10 count ({len(top_10)})"
)
print(f"  categorized_articles sums to {total_in_cat} == len(top_10) OK")

assert len(cat_dict["ai_news"]) == 8, f"Expected 8 ai_news, got {len(cat_dict['ai_news'])}"
assert len(cat_dict["career"]) == 2, f"Expected 2 career, got {len(cat_dict['career'])}"
assert len(cat_dict["ceo_update"]) == 0, f"Expected 0 ceo_update, got {len(cat_dict['ceo_update'])}"
print(f"  Category split correct: ai_news=8, career=2, ceo_update=0 OK")

# ── Test 5: categorized_articles articles have summaries ─────────────────────
print("\n=== Test 5: categorized_articles has summaries ===")

with_summaries = [
    make_article(title="A", score=9, url="https://a.com/s1", summary="Real summary here."),
    make_article(title="B", score=8, url="https://a.com/s2", summary="Another summary."),
]
result = rank(base_state(with_summaries))
for cat, arts in result["categorized_articles"].items():
    for a in arts:
        assert a["summary"], f"Article in categorized_articles missing summary: {a['title']}"
print("  All articles in categorized_articles have summaries OK")

# ── Test 6: full pipeline ─────────────────────────────────────────────────────
print("\n=== Test 6: full pipeline (all 6 nodes) ===")
print("  Making 3 Claude Haiku API calls...\n")

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

for node_fn in [fetch_news, deduplicate, score_relevance, categorize, summarize, rank]:
    state.update(node_fn(state))

top_10 = state["top_10"]
cat_dict = state["categorized_articles"]

assert len(top_10) <= TOP_N
assert len(top_10) > 0
# Scores must be descending
for i in range(len(top_10) - 1):
    assert top_10[i]["score"] >= top_10[i+1]["score"], \
        f"Score out of order at position {i}: {top_10[i]['score']} < {top_10[i+1]['score']}"
# Every field populated
for a in top_10:
    assert a["score"] is not None
    assert a["category"] is not None
    assert a["summary"] is not None and len(a["summary"]) > 10

print(f"\nFinal top {len(top_10)} articles (score DESC):\n")
for i, a in enumerate(top_10, 1):
    print(f"  #{i:2d} [{a['score']:2d}] [{a['category']:10s}] [{a['source_name'][:14]:14s}] {a['title'][:55]}")
    print(f"         {a['summary'][:100]}...")
    print()

print("All assertions passed.")
