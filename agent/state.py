from typing import TypedDict, Optional
from datetime import datetime


class Article(TypedDict):
    title: str
    url: str
    description: str          # Raw snippet/abstract from the source
    source_name: str          # e.g. "VentureBeat AI"
    source_tier: int          # 1, 2, or 3
    published_at: str         # ISO 8601 string
    score: Optional[int]      # Set by score node (1-10), None before scoring
    score_reason: Optional[str]
    category: Optional[str]   # "ai_news" | "career" | "ceo_update" — set by categorize node
    summary: Optional[str]    # 2-3 line summary — set by summarize node


class AgentState(TypedDict):
    # ── Input ────────────────────────────────────────────────────────────────
    user_preferences: dict          # topics, sources, people, frequency

    # ── Pipeline stages ──────────────────────────────────────────────────────
    raw_articles: list[Article]     # All articles from fetch node
    filtered_articles: list[Article]  # After dedup + relevance scoring
    categorized_articles: dict      # { "ai_news": [...], "career": [...], "ceo_update": [...] }
    top_10: list[Article]           # Final sorted output with summaries

    # ── Control ──────────────────────────────────────────────────────────────
    retry_count: int                # Guards the fetch → score loop (max 2 retries)
    run_timestamp: str              # ISO 8601 datetime of this run

    # ── Delivery ─────────────────────────────────────────────────────────────
    email_sent: bool
