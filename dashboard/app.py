"""
AI Daily Briefing — Streamlit dashboard.

Run with:
    streamlit run dashboard/app.py
"""
import contextlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from dotenv import load_dotenv

from database import init_db, get_latest_run, get_run_history, get_run_articles, save_run

load_dotenv()

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


def _run_pipeline() -> tuple[dict, str]:
    """Invoke the full agent graph. Returns (result_state, captured_log)."""
    from agent.graph import create_graph
    from agent.state import AgentState

    initial_state: AgentState = {
        "user_preferences": {
            "topics": ["LLMs", "AI agents", "RAG", "machine learning"],
        },
        "raw_articles":         [],
        "filtered_articles":    [],
        "categorized_articles": {},
        "top_10":               [],
        "retry_count":          0,
        "run_timestamp":        "",
        "email_sent":           False,
    }

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = create_graph().invoke(initial_state)

    return result, buf.getvalue()


def _render_articles(articles: list[dict]) -> None:
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

    # Header row: title on left, last-retrieved time on right
    if result is not None:
        run_info, articles = result
        run_ts = str(run_info["run_timestamp"])
        run_date = run_ts[:10]
        run_time = run_ts[11:19]

        col_title, col_time = st.columns([3, 1])
        with col_title:
            st.title(f"AI Daily Briefing — {run_date}")
        with col_time:
            st.caption("")
            st.caption(f"Last retrieved: **{run_date}** at **{run_time} UTC**")
    else:
        st.title("AI Daily Briefing")

    # Fetch button + post-run feedback
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if "fetch_result" not in st.session_state:
        st.session_state.fetch_result = None

    # Show feedback from the previous fetch (cleared after one render)
    if st.session_state.fetch_result is not None:
        status, msg, log = st.session_state.fetch_result
        if status == "success":
            st.success(msg)
        else:
            st.warning(msg)
        if log:
            with st.expander("Pipeline log"):
                st.code(log, language="")
        st.session_state.fetch_result = None

    # Button
    btn_label = "Fetch Latest News"
    if not api_key:
        st.button(btn_label, type="primary", disabled=True)
        st.caption(
            "To enable live fetching, add `ANTHROPIC_API_KEY` in "
            "Streamlit Cloud → Settings → Secrets."
        )
    else:
        if st.button(btn_label, type="primary"):
            with st.spinner("Running AI briefing pipeline (~15 sec)..."):
                try:
                    pipeline_result, log = _run_pipeline()
                except Exception as exc:
                    st.session_state.fetch_result = (
                        "error",
                        f"Pipeline error: {exc}",
                        "",
                    )
                    st.rerun()

            top_10 = pipeline_result.get("top_10", [])
            if top_10:
                save_run(pipeline_result["run_timestamp"], top_10)
                fetched = len(pipeline_result.get("raw_articles", []))
                passed  = len(pipeline_result.get("filtered_articles", []))
                st.session_state.fetch_result = (
                    "success",
                    f"Done! {len(top_10)} stories saved "
                    f"(fetched {fetched}, scored {passed}).",
                    log,
                )
            else:
                st.session_state.fetch_result = (
                    "error",
                    "Pipeline ran but no articles passed the relevance threshold.",
                    log,
                )
            st.rerun()

    st.divider()

    # Article display
    if result is None:
        st.info(
            "No briefings saved yet. Click **Fetch Latest News** above "
            "or run `python run_agent.py` locally.",
            icon=None,
        )
    else:
        run_info, articles = result
        col1, col2, col3 = st.columns(3)
        col1.metric("Top Stories", run_info["article_count"])
        col2.metric("Run Date", run_date)
        col3.metric("Run Time", run_time + " UTC")
        st.divider()
        _render_articles(articles)

# ── History tab ───────────────────────────────────────────────────────────────
with tab_history:
    history = get_run_history()

    if not history:
        st.info("No run history yet.", icon=None)
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
