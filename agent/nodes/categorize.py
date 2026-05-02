import json
import re
import anthropic

from agent.state import AgentState, Article
from config import ANTHROPIC_API_KEY, LLM_MODEL

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
_VALID_CATEGORIES = {"ai_news", "career", "ceo_update"}
_FALLBACK_CATEGORY = "ai_news"


def _build_prompt(articles: list[Article]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        desc = (a["description"] or "")[:150]
        lines.append(f"[{i}] Title: {a['title']} | Desc: {desc}")

    return (
        "Categorize each article into exactly one of three categories:\n"
        "  ai_news    — AI/ML research, model releases, tools, frameworks, infrastructure, AI products\n"
        "  career     — Job market trends, hiring in AI/ML, layoffs, compensation, career advice\n"
        "  ceo_update — Executive moves, company strategy, funding rounds, acquisitions, leadership news\n\n"
        "When in doubt between ai_news and ceo_update: if the story is primarily about a product or "
        "technology, use ai_news; if it is primarily about business/people/money, use ceo_update.\n\n"
        "Articles:\n"
        + "\n".join(lines)
        + f"\n\nRespond ONLY with a JSON array of exactly {len(articles)} strings. "
        'Each string must be one of: "ai_news", "career", "ceo_update". No other text.\n'
        '["ai_news", "ceo_update", ...]'
    )


def _parse_categories(text: str, expected_count: int) -> list[str] | None:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  [categorize] JSON parse error: {e}")
        return None

    if not isinstance(data, list):
        print(f"  [categorize] Expected JSON array, got {type(data).__name__}")
        return None

    if len(data) != expected_count:
        print(f"  [categorize] Expected {expected_count} categories, got {len(data)}")
        return None

    return data


def categorize(state: AgentState) -> dict:
    """
    LangGraph node: assign each filtered article to one of three categories.
    Returns state update: filtered_articles (with category set) + categorized_articles dict.
    """
    articles = state["filtered_articles"]

    if not articles:
        print("  [categorize] No articles to categorize")
        empty = {k: [] for k in _VALID_CATEGORIES}
        return {"filtered_articles": [], "categorized_articles": empty}

    prompt = _build_prompt(articles)
    print(f"  [categorize] Categorizing {len(articles)} articles with {LLM_MODEL}...")

    response = _client.messages.create(
        model=LLM_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text
    categories = _parse_categories(raw_text, len(articles))

    if categories is None:
        print(f"  [categorize] WARNING: parsing failed — assigning all to {_FALLBACK_CATEGORY}")
        categories = [_FALLBACK_CATEGORY] * len(articles)

    # Attach category to each article
    result: list[Article] = []
    for article, cat in zip(articles, categories):
        if cat not in _VALID_CATEGORIES:
            print(f"  [categorize] Unknown category '{cat}' -> falling back to {_FALLBACK_CATEGORY}")
            cat = _FALLBACK_CATEGORY
        updated = dict(article)
        updated["category"] = cat
        result.append(updated)

    # Group into the categorized_articles dict
    grouped: dict[str, list[Article]] = {k: [] for k in _VALID_CATEGORIES}
    for a in result:
        grouped[a["category"]].append(a)

    for cat, arts in grouped.items():
        print(f"  [categorize] {cat}: {len(arts)} articles")

    return {
        "filtered_articles": result,
        "categorized_articles": grouped,
    }
