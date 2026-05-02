from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes.fetch import fetch_news
from agent.nodes.deduplicate import deduplicate
from agent.nodes.score import score_relevance
from agent.nodes.categorize import categorize
from agent.nodes.summarize import summarize
from agent.nodes.rank import rank
from config import MAX_FETCH_RETRIES


def _increment_retry(state: AgentState) -> dict:
    """Tiny node: increment retry_count before looping back to fetch.

    Conditional edge functions can only inspect state, not modify it.
    This node exists solely to make that modification in the graph's state.
    """
    new_count = state["retry_count"] + 1
    print(f"  [graph] No articles passed scoring — retrying (attempt {new_count}/{MAX_FETCH_RETRIES})")
    return {"retry_count": new_count}


def _route_after_score(state: AgentState) -> str:
    """Conditional edge: retry fetch if nothing passed scoring and retries remain."""
    if not state["filtered_articles"] and state["retry_count"] < MAX_FETCH_RETRIES:
        return "retry"
    return "continue"


def create_graph():
    """Build and compile the AI briefing agent graph.

    Pipeline:
      fetch_news -> deduplicate -> score_relevance
        -> [retry loop if 0 articles pass, max MAX_FETCH_RETRIES times]
        -> categorize -> summarize -> rank -> END
    """
    graph = StateGraph(AgentState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    graph.add_node("fetch_news",      fetch_news)
    graph.add_node("deduplicate",     deduplicate)
    graph.add_node("score_relevance", score_relevance)
    graph.add_node("increment_retry", _increment_retry)
    graph.add_node("categorize",      categorize)
    graph.add_node("summarize",       summarize)
    graph.add_node("rank",            rank)

    # ── Entry point ───────────────────────────────────────────────────────────
    graph.set_entry_point("fetch_news")

    # ── Linear edges ──────────────────────────────────────────────────────────
    graph.add_edge("fetch_news",      "deduplicate")
    graph.add_edge("deduplicate",     "score_relevance")

    # ── Conditional edge: retry or continue ───────────────────────────────────
    graph.add_conditional_edges(
        "score_relevance",
        _route_after_score,
        {
            "retry":    "increment_retry",
            "continue": "categorize",
        },
    )

    # Retry loop: after incrementing, go back to the top
    graph.add_edge("increment_retry", "fetch_news")

    # ── Rest of the pipeline ──────────────────────────────────────────────────
    graph.add_edge("categorize", "summarize")
    graph.add_edge("summarize",  "rank")
    graph.add_edge("rank",       END)

    return graph.compile()
