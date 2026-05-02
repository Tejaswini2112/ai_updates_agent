from difflib import SequenceMatcher
import re

from agent.state import AgentState, Article

# 80% character-sequence overlap = same story, different headline phrasing.
# Conservative on purpose: better to keep a near-dupe than to wrongly merge
# two distinct stories that share common news-headline words.
_TITLE_SIMILARITY_THRESHOLD = 0.80


def _normalize_title(title: str) -> str:
    """Lowercase and strip punctuation so 'GPT-5' and 'GPT5' compare fairly."""
    return re.sub(r"[^a-z0-9\s]", "", title.lower()).strip()


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()


def _better_article(a: Article, b: Article) -> Article:
    """Return the higher-quality version of two duplicate articles.

    Tier 1 (editorial) beats Tier 2 (community). Same tier → longer description wins.
    """
    if a["source_tier"] != b["source_tier"]:
        return a if a["source_tier"] < b["source_tier"] else b
    return a if len(a["description"]) >= len(b["description"]) else b


def deduplicate(state: AgentState) -> dict:
    """
    LangGraph node: remove duplicate articles from raw_articles.

    Two passes:
      1. Exact URL match  — same link shared by multiple sources
      2. Title similarity — same story, different editorial headline
    """
    articles = state["raw_articles"]

    # ── Pass 1: exact URL dedup ───────────────────────────────────────────────
    seen_urls: dict[str, int] = {}   # url → index in `after_url_dedup`
    after_url_dedup: list[Article] = []

    for article in articles:
        url = article["url"]
        if url in seen_urls:
            idx = seen_urls[url]
            after_url_dedup[idx] = _better_article(after_url_dedup[idx], article)
        else:
            seen_urls[url] = len(after_url_dedup)
            after_url_dedup.append(article)

    url_dupes = len(articles) - len(after_url_dedup)

    # ── Pass 2: title similarity dedup ───────────────────────────────────────
    final: list[Article] = []
    for article in after_url_dedup:
        matched = False
        for i, existing in enumerate(final):
            if _title_similarity(article["title"], existing["title"]) >= _TITLE_SIMILARITY_THRESHOLD:
                final[i] = _better_article(existing, article)
                matched = True
                break
        if not matched:
            final.append(article)

    title_dupes = len(after_url_dedup) - len(final)

    print(
        f"  [deduplicate] {len(articles)} -> {len(final)} articles "
        f"({url_dupes} URL dupes, {title_dupes} title dupes removed)"
    )

    return {"raw_articles": final}
