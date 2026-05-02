import json
import re
import anthropic

from agent.state import AgentState, Article
from config import ANTHROPIC_API_KEY, LLM_MODEL, RELEVANCE_THRESHOLD

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _build_prompt(articles: list[Article]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        desc = (a["description"] or "")[:200]
        lines.append(
            f"[{i}] Source: {a['source_name']} (Tier {a['source_tier']}) | "
            f"Title: {a['title']} | "
            f"Desc: {desc}"
        )

    return (
        "You are scoring news articles for an AI/ML engineer who is actively job hunting.\n\n"
        "They care about:\n"
        "- LLM and model releases (GPT, Claude, Gemini, Llama, etc.)\n"
        "- AI agent frameworks and tools (LangGraph, LangChain, AutoGen, CrewAI, etc.)\n"
        "- RAG systems, vector databases, embeddings\n"
        "- AI research breakthroughs (especially from arXiv)\n"
        "- Career and hiring trends in AI/ML engineering\n"
        "- AI company strategy: funding rounds, acquisitions, product launches\n"
        "- AI infrastructure: GPUs, cloud AI, training costs\n\n"
        "Score each article 1-10:\n"
        "  9-10: Essential — major model release, research breakthrough, directly career-relevant\n"
        "  7-8: Highly relevant — significant AI development, useful tools or frameworks\n"
        "  5-6: Moderately relevant — tangentially related to AI, general tech with AI angle\n"
        "  3-4: Low relevance — peripheral AI connection, mostly off-topic\n"
        "  1-2: Not relevant — no meaningful AI/ML connection\n\n"
        "Tier 1 sources (VentureBeat AI, TechCrunch AI, arXiv cs.AI) are editorial or peer-reviewed. "
        "Tier 2 (HackerNews) is community-curated. "
        "Use tier as a mild tiebreaker — score based on content first.\n\n"
        "Articles to score:\n"
        + "\n".join(lines)
        + f"\n\nRespond ONLY with a JSON array of exactly {len(articles)} objects, "
        "in the same order as the input. No other text.\n"
        '[{"score": <integer 1-10>, "reason": "<one sentence>"}, ...]'
    )


def _parse_scores(text: str, expected_count: int) -> list[dict] | None:
    """Extract and validate the JSON array from Claude's response."""
    # Strip markdown code fences that Claude sometimes adds
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  [score] JSON parse error: {e}")
        return None

    if not isinstance(data, list):
        print(f"  [score] Expected JSON array, got {type(data).__name__}")
        return None

    if len(data) != expected_count:
        print(f"  [score] Expected {expected_count} scores, got {len(data)}")
        return None

    for item in data:
        if "score" not in item or "reason" not in item:
            print(f"  [score] Malformed entry (missing score or reason): {item}")
            return None

    return data


def score_relevance(state: AgentState) -> dict:
    """
    LangGraph node: score all articles with a single batched Claude Haiku call.
    Returns state update: filtered_articles (score >= RELEVANCE_THRESHOLD).
    """
    articles = state["raw_articles"]

    if not articles:
        print("  [score] No articles to score")
        return {"filtered_articles": []}

    prompt = _build_prompt(articles)
    print(f"  [score] Scoring {len(articles)} articles with {LLM_MODEL}...")

    response = _client.messages.create(
        model=LLM_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text
    scores = _parse_scores(raw_text, len(articles))

    if scores is None:
        # Fallback: pass all articles through rather than crash the pipeline.
        # The operator can inspect logs and tune the prompt.
        print("  [score] WARNING: score parsing failed — passing all articles unfiltered")
        return {"filtered_articles": list(articles)}

    # Attach scores and filter by threshold
    filtered: list[Article] = []
    score_dist: dict[int, int] = {i: 0 for i in range(1, 11)}

    for article, s in zip(articles, scores):
        article_score = max(1, min(10, int(s["score"])))  # clamp to valid range
        score_dist[article_score] += 1

        if article_score >= RELEVANCE_THRESHOLD:
            scored = dict(article)
            scored["score"] = article_score
            scored["score_reason"] = str(s["reason"])
            filtered.append(scored)

    print(
        f"  [score] {len(articles)} scored, {len(filtered)} passed "
        f"threshold (>= {RELEVANCE_THRESHOLD})"
    )
    print(f"  [score] Distribution: {score_dist}")

    return {"filtered_articles": filtered}
