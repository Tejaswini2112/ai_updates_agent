"""
Session 2 test — run both fetch tools and print results to terminal.
Usage: python test_tools.py
"""
from config import SOURCES
from agent.tools.rss_reader import fetch_rss
from agent.tools.hackernews import fetch_hackernews


def print_articles(articles, source_name):
    print(f"\n{'='*60}")
    print(f"  {source_name}  —  {len(articles)} articles")
    print(f"{'='*60}")
    for i, a in enumerate(articles[:5], 1):   # show first 5 per source
        date = a["published_at"][:10]
        desc_preview = a["description"][:80] + "..." if a["description"] else "(no description)"
        print(f"\n  [{i}] {a['title']}")
        print(f"       date : {date}")
        print(f"       tier : {a['source_tier']}")
        print(f"       desc : {desc_preview}")
        print(f"       url  : {a['url'][:70]}")
    if len(articles) > 5:
        print(f"\n  ... and {len(articles) - 5} more")


def main():
    all_articles = []

    print("\n>>> Fetching from RSS sources ...")
    for source in SOURCES:
        if source["type"] != "rss":
            continue
        print(f"  Fetching {source['name']} ...")
        articles = fetch_rss(source)
        print(f"  Got {len(articles)} articles")
        all_articles.extend(articles)
        print_articles(articles, f"{source['name']} (Tier {source['tier']})")

    print("\n>>> Fetching from HackerNews ...")
    hn_articles = fetch_hackernews()
    print(f"  Got {len(hn_articles)} articles")
    all_articles.extend(hn_articles)
    print_articles(hn_articles, "HackerNews (Tier 2)")

    print(f"\n{'='*60}")
    print(f"  TOTAL ARTICLES FETCHED: {len(all_articles)}")
    print(f"  These will flow into the deduplicate node next.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
