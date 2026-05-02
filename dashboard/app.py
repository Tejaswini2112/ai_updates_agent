"""
AI Daily Briefing — Streamlit dashboard.

Run with:
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

# Make project root importable regardless of working directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from database import init_db, get_latest_run, get_run_history, get_run_articles

st.set_page_config(
    page_title="AI Daily Briefing",
    page_icon=":newspaper:",
    layout="wide",
)

init_db()

_CATEGORY_LABELS = {
    "ai_news":    "AI News",
    "career":     "Career",
    "ceo_update": "CEO Updates",
}

_CATEGORY_ORDER = ["ai_news", "career", "ceo_update"]


def _render_articles(articles: list[dict]) -> None:
    """Render a list of articles grouped by category."""
    grouped: dict[str, list[dict]] = {k: [] for k in _CATEGORY_ORDER}
    for a in articles:
        cat = a.get("category") or "ai_news"
        bucket = cat if cat in grouped else "ai_news"
        grouped[bucket].append(a)

    rank = 1
    for cat_key in _CATEGORY_ORDER:
        cat_articles = grouped[cat_key]
        if not cat_articles:
            continue
        st.subheader(_CATEGORY_LABELS[cat_key])
        for a in cat_articles:
            score = a.get("score") or 0
            label = f"#{rank}  ⭐ {score}/10  {a['title']}"
            with st.expander(label, expanded=False):
                if a.get("summary"):
                    st.write(a["summary"])
                cols = st.columns([2, 2, 1])
                cols[0].caption(f"**Source:** {a.get('source_name', '')}")
                cols[1].caption(f"**Published:** {str(a.get('published_at', ''))[:10]}")
                if a.get("score_reason"):
                    cols[2].caption(f"*{a['score_reason']}*")
                st.markdown(f"[Read article]({a['url']})")
            rank += 1


# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_today, tab_history = st.tabs(["Today's Briefing", "Run History"])

# ── Today tab ────────────────────────────────────────────────────────────────
with tab_today:
    result = get_latest_run()

    if result is None:
        st.info(
            "No briefings saved yet. Run `python run_agent.py` to fetch your first briefing.",
            icon="ℹ️",
        )
    else:
        run_info, articles = result
        run_date = str(run_info["run_timestamp"])[:10]

        st.title(f"AI Daily Briefing — {run_date}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Top Stories", run_info["article_count"])
        col2.metric("Run Date", run_date)
        col3.metric("Run Time", str(run_info["run_timestamp"])[11:19] + " UTC")

        st.divider()
        _render_articles(articles)

# ── History tab ───────────────────────────────────────────────────────────────
with tab_history:
    history = get_run_history()

    if not history:
        st.info("No run history yet.", icon="ℹ️")
    else:
        st.subheader("Past Runs")

        selected_id = st.selectbox(
            "Select a run to view",
            options=[r["id"] for r in history],
            format_func=lambda rid: next(
                f"{str(r['run_timestamp'])[:10]}  ({r['article_count']} articles)"
                for r in history
                if r["id"] == rid
            ),
        )

        if selected_id is not None:
            past_articles = get_run_articles(selected_id)
            selected_run = next(r for r in history if r["id"] == selected_id)
            st.caption(f"Full timestamp: {selected_run['run_timestamp']}")
            st.divider()
            _render_articles(past_articles)
