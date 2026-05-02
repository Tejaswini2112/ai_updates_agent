"""
AI Daily Briefing Agent — entry point.

Usage:
    source venv/Scripts/activate   (bash)
    python run_agent.py
"""
from agent.graph import create_graph
from agent.state import AgentState
from database import init_db, save_run


def main() -> None:
    init_db()
    graph = create_graph()

    initial_state: AgentState = {
        "user_preferences": {
            "topics": ["LLMs", "AI agents", "RAG", "machine learning"],
        },
        "raw_articles":        [],
        "filtered_articles":   [],
        "categorized_articles": {},
        "top_10":              [],
        "retry_count":         0,
        "run_timestamp":       "",
        "email_sent":          False,
    }

    print("Starting AI Daily Briefing Agent...\n")
    result = graph.invoke(initial_state)

    if result["top_10"]:
        save_run(result["run_timestamp"], result["top_10"])

    top_10         = result["top_10"]
    run_date       = result["run_timestamp"][:10]
    fetched        = len(result["raw_articles"])
    after_scoring  = len(result["filtered_articles"])
    retries        = result["retry_count"]

    print()
    print("=" * 65)
    print(f"  AI DAILY BRIEFING  |  {run_date}")
    print("=" * 65)
    print(f"  Fetched: {fetched}  |  Passed scoring: {after_scoring}  |  Retries: {retries}")
    print("=" * 65)

    if not top_10:
        print("\n  No articles passed the relevance threshold today.")
        print("  Try lowering RELEVANCE_THRESHOLD in config.py.")
        return

    # Group by category for display
    categories = {
        "ai_news":    ("AI NEWS",    []),
        "career":     ("CAREER",     []),
        "ceo_update": ("CEO UPDATE", []),
    }
    for a in top_10:
        cat = a.get("category") or "ai_news"
        if cat in categories:
            categories[cat][1].append(a)

    rank_num = 1
    for cat_key, (cat_label, articles) in categories.items():
        if not articles:
            continue
        print(f"\n  --- {cat_label} ---")
        for a in articles:
            print(f"\n  #{rank_num}  [{a['score']:2d}/10]  {a['title']}")
            print(f"       {a['summary']}")
            print(f"       {a['url']}")
            rank_num += 1

    print("\n" + "=" * 65)
    print(f"  {len(top_10)} stories | run: {result['run_timestamp']}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
