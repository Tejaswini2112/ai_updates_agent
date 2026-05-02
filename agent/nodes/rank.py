from agent.state import AgentState, Article
from config import TOP_N

_VALID_CATEGORIES = {"ai_news", "career", "ceo_update"}


def rank(state: AgentState) -> dict:
    """
    LangGraph node: sort filtered_articles by score, keep top TOP_N.
    Zero LLM calls — Python sort on the scores the LLM already assigned.

    Also rebuilds categorized_articles from top_10 so the dashboard gets
    fully-populated articles (with summaries) grouped by category.
    """
    articles = state["filtered_articles"]

    if not articles:
        print("  [rank] No articles to rank")
        empty_grouped: dict[str, list[Article]] = {k: [] for k in _VALID_CATEGORIES}
        return {"top_10": [], "categorized_articles": empty_grouped}

    # Sort: score DESC, then source_tier ASC (Tier 1 before Tier 2 as tiebreaker).
    # Negating score turns "highest first" into a standard ascending sort.
    ranked = sorted(
        articles,
        key=lambda a: (-(a["score"] or 0), a["source_tier"] or 3),
    )

    top: list[Article] = ranked[:TOP_N]

    # Rebuild categorized_articles from top_10.
    # The version built by categorize.py lacks summaries; this one has everything.
    grouped: dict[str, list[Article]] = {k: [] for k in _VALID_CATEGORIES}
    for a in top:
        cat = a.get("category") or "ai_news"
        bucket = cat if cat in _VALID_CATEGORIES else "ai_news"
        grouped[bucket].append(a)

    print(f"  [rank] {len(articles)} articles -> top {len(top)}")
    for cat, arts in grouped.items():
        if arts:
            print(f"  [rank] {cat}: {len(arts)}")

    return {
        "top_10": top,
        "categorized_articles": grouped,
    }
