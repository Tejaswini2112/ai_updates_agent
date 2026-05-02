import re
import html
import requests
from datetime import datetime, timezone, timedelta
from agent.state import Article
from config import HN_QUERIES, HN_RESULTS_PER_QUERY

# HackerNews Algolia API docs: https://hn.algolia.com/api
_HN_API = "https://hn.algolia.com/api/v1/search_by_date"
_MIN_POINTS = 5        # discard posts with very low community engagement
_LOOKBACK_DAYS = 2     # only fetch stories from the last 48 hours


def _clean_html(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fetch_one_query(query: str, cutoff: int) -> list[dict]:
    """Run a single Algolia query and return raw hits."""
    # numericFilters uses '>' which requests would percent-encode to '%3E'.
    # Algolia's HN API requires the raw '>' character, so we build the URL manually.
    safe_params = requests.compat.urlencode({
        "query": query,
        "tags": "story",
        "hitsPerPage": HN_RESULTS_PER_QUERY,
    })
    url = f"{_HN_API}?{safe_params}&numericFilters=created_at_i>{cutoff}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("hits", [])
    except Exception as e:
        print(f"  [hackernews] ERROR on query '{query}': {e}")
        return []


def fetch_hackernews() -> list[Article]:
    """Run all HN_QUERIES, merge, deduplicate by URL, return Article list."""
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)).timestamp())

    # Collect hits from all queries, dedup by objectID so overlapping results are merged
    seen_ids: set[str] = set()
    all_hits: list[dict] = []
    for query in HN_QUERIES:
        for hit in _fetch_one_query(query, cutoff):
            oid = hit.get("objectID", "")
            if oid not in seen_ids:
                seen_ids.add(oid)
                all_hits.append(hit)

    articles: list[Article] = []
    for hit in all_hits:
        if (hit.get("points") or 0) < _MIN_POINTS:
            continue

        title = (hit.get("title") or "").strip()
        if not title:
            continue

        # Text-only HN posts have no external URL — link to HN thread instead
        article_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"

        raw_text = hit.get("story_text") or ""
        description = _clean_html(raw_text)[:500] if raw_text else ""

        created_at_i = hit.get("created_at_i") or 0
        published_at = datetime.fromtimestamp(created_at_i, tz=timezone.utc).isoformat()

        articles.append(
            Article(
                title=title,
                url=article_url,
                description=description,
                source_name="HackerNews",
                source_tier=2,
                published_at=published_at,
                score=None,
                score_reason=None,
                category=None,
                summary=None,
            )
        )

    return articles
