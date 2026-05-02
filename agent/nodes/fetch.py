from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from agent.state import AgentState, Article
from agent.tools.rss_reader import fetch_rss
from agent.tools.hackernews import fetch_hackernews
from config import SOURCES


def fetch_news(state: AgentState) -> dict:
    """
    LangGraph node: fetch articles from all sources in parallel.
    Returns state update: raw_articles + run_timestamp.
    """
    rss_sources = [s for s in SOURCES if s["type"] == "rss"]
    api_sources = [s for s in SOURCES if s["type"] == "api"]

    all_articles: list[Article] = []
    futures = {}

    with ThreadPoolExecutor(max_workers=len(rss_sources) + len(api_sources)) as pool:
        # Submit one task per RSS source
        for source in rss_sources:
            future = pool.submit(fetch_rss, source)
            futures[future] = source["name"]

        # Submit HackerNews (single callable regardless of how many api sources exist)
        for source in api_sources:
            future = pool.submit(fetch_hackernews)
            futures[future] = source["name"]

        for future in as_completed(futures):
            source_name = futures[future]
            try:
                articles = future.result()
                print(f"  [fetch] {source_name}: {len(articles)} articles")
                all_articles.extend(articles)
            except Exception as e:
                print(f"  [fetch] ERROR from {source_name}: {e}")

    print(f"  [fetch] Total raw articles: {len(all_articles)}")

    return {
        "raw_articles": all_articles,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
    }
