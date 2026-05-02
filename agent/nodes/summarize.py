import json
import re
import anthropic

from agent.state import AgentState, Article
from config import ANTHROPIC_API_KEY, LLM_MODEL

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _build_prompt(articles: list[Article]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        desc = (a["description"] or "")[:200]
        reason = a["score_reason"] or ""
        line = (
            f"[{i}] Source: {a['source_name']} (score {a['score']}) | "
            f"Title: {a['title']} | Desc: {desc}"
        )
        if reason:
            line += f" | Why relevant: {reason}"
        lines.append(line)

    return (
        "Write a 2-3 sentence summary for each article. "
        "The reader is a busy AI/ML engineer scanning a morning briefing.\n\n"
        "Guidelines:\n"
        "- First sentence: what happened (the core news fact)\n"
        "- Second/third sentence: why it matters to an AI engineer or someone job hunting in AI\n"
        "- Be specific and concrete — reference the actual technology, company, or number involved\n"
        "- Do not start with 'This article', 'The article', or restate the title verbatim\n"
        "- 2-3 sentences maximum — no bullet points, no headers\n\n"
        "Articles:\n"
        + "\n".join(lines)
        + f"\n\nRespond ONLY with a JSON array of exactly {len(articles)} strings. "
        "Each string is the complete summary for that article. No other text.\n"
        '["Summary for article 1.", "Summary for article 2.", ...]'
    )


def _parse_summaries(text: str, expected_count: int) -> list[str] | None:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  [summarize] JSON parse error: {e}")
        return None

    if not isinstance(data, list):
        print(f"  [summarize] Expected JSON array, got {type(data).__name__}")
        return None

    if len(data) != expected_count:
        print(f"  [summarize] Expected {expected_count} summaries, got {len(data)}")
        return None

    return data


def summarize(state: AgentState) -> dict:
    """
    LangGraph node: generate a 2-3 sentence summary for each filtered article.
    Returns state update: filtered_articles (with summary set).
    """
    articles = state["filtered_articles"]

    if not articles:
        print("  [summarize] No articles to summarize")
        return {"filtered_articles": []}

    prompt = _build_prompt(articles)
    print(f"  [summarize] Summarizing {len(articles)} articles with {LLM_MODEL}...")

    response = _client.messages.create(
        model=LLM_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text
    summaries = _parse_summaries(raw_text, len(articles))

    if summaries is None:
        print("  [summarize] WARNING: parsing failed — summaries will be empty strings")
        summaries = [""] * len(articles)

    result: list[Article] = []
    for article, summary_text in zip(articles, summaries):
        updated = dict(article)
        updated["summary"] = str(summary_text).strip()
        result.append(updated)

    print(f"  [summarize] Done")
    return {"filtered_articles": result}
