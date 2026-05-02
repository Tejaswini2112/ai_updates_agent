import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ─── Source definitions ────────────────────────────────────────────────────────
#
# Each source is a dict with:
#   name  - human-readable label used in logs and the scoring prompt
#   url   - RSS feed URL or API endpoint
#   tier  - credibility weight (1=highest, 3=lowest)
#   type  - "rss" or "api" — tells the fetch node which tool to use
#
SOURCES = [
    # Tier 1 — Primary (editorial + research, real-time RSS)
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "tier": 1,
        "type": "rss",
    },
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "tier": 1,
        "type": "rss",
    },
    {
        "name": "arXiv cs.AI",
        "url": "https://rss.arxiv.org/rss/cs.AI",
        "tier": 1,
        "type": "rss",
    },
    # Tier 2 — Community (fresh signal, query-based API)
    {
        "name": "HackerNews",
        "url": "https://hn.algolia.com/api/v1/search_by_date",
        "tier": 2,
        "type": "api",
    },
]

# ─── LLM ──────────────────────────────────────────────────────────────────────
LLM_MODEL = "claude-haiku-4-5-20251001"

# ─── Pipeline settings ─────────────────────────────────────────────────────────
RELEVANCE_THRESHOLD = 6      # Articles scoring below this are dropped
TOP_N = 10                   # Final stories to keep
MAX_FETCH_RETRIES = 2        # Max times to retry fetch if nothing passes scoring
# Two focused queries — merged and deduped by the fetch node.
# Complex OR queries break Algolia's HN API when combined with numericFilters.
HN_QUERIES = ["AI", "LLM"]
HN_RESULTS_PER_QUERY = 20   # 20 × 2 queries = up to 40 HN candidates
