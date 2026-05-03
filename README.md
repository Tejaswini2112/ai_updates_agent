# AI Updates Agent

A personal AI news agent that fetches, scores, categorizes, and summarizes the top AI/ML stories every morning — delivered as a terminal briefing, saved to a local database, and browsable in a Streamlit dashboard.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.1.10-1C3C3C)
![Claude Haiku](https://img.shields.io/badge/Claude-Haiku_4.5-D97757?logo=anthropic&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.57-FF4B4B?logo=streamlit&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-stdlib-003B57?logo=sqlite&logoColor=white)

**[Live Demo](https://aiupdatesagent-srfpljb2t9bwzzqk54olpn.streamlit.app)** — browse 3 days of briefings across AI News, Career, and CEO Updates categories.

---

## What It Does

Every morning, the agent pulls ~60 articles from 4 sources (VentureBeat AI, TechCrunch AI, arXiv cs.AI, HackerNews), deduplicates them, scores each one for relevance to an AI/ML engineer's interests using Claude Haiku, filters by a relevance threshold, categorizes into AI News / Career / CEO Updates, writes 2–3 sentence summaries, and ranks the top 10.

The entire LLM workload is **3 batched API calls per run** — not one call per article — regardless of how many articles are fetched.

Results are saved to a SQLite database and displayed in a Streamlit dashboard.

---

## Dashboard

**[Live demo on Streamlit Community Cloud](https://aiupdatesagent-srfpljb2t9bwzzqk54olpn.streamlit.app)**

> **Local setup:** Run `streamlit run dashboard/app.py` after at least one agent run.

The dashboard has two tabs:

- **Today's Briefing** — top 10 articles grouped by category, each expandable to show the summary, source, publish date, and a direct link
- **Run History** — all past runs selectable by date, renders the same view for any historical run

---

## Pipeline

```
fetch_news
    │  (parallel, ThreadPoolExecutor — ~1.2s vs ~3.4s sequential)
    ▼
deduplicate
    │  (Pass 1: exact URL match  |  Pass 2: title fuzzy match >= 0.80)
    ▼
score_relevance  ──────────────────────────────────────────────┐
    │                                                          │
    │  0 articles passed threshold                             │
    │  AND retry_count < MAX_FETCH_RETRIES (2)                 │
    │                                                          ▼
    │                                                  increment_retry
    │                                                          │
    │                                                          └──► fetch_news
    │
    │  articles passed threshold
    ▼
categorize
    │  (ai_news | career | ceo_update)
    ▼
summarize
    │  (2–3 sentences, informed by score_reason)
    ▼
rank
    │  (sort by score DESC, tier ASC as tiebreaker, keep top TOP_N=10)
    ▼
save to SQLite
    │
    ▼
   END
```

The **conditional retry edge** is the key agentic element: if nothing passes the relevance filter, the graph loops back to fetch rather than returning an empty result. LangGraph's routing function inspects state and returns `"retry"` or `"continue"` — a separate `increment_retry` node handles the state mutation (routing functions in LangGraph are read-only).

---

## LLM Strategy

| Node | Call # | Input | Output | Tokens (approx) |
|---|---|---|---|---|
| `score_relevance` | 1 | ~59 articles | `[{score, reason}]` | ~2,000 in / 800 out |
| `categorize` | 2 | ~35 articles (post-filter) | `["ai_news", ...]` | ~800 in / 150 out |
| `summarize` | 3 | ~35 articles | `["Summary...", ...]` | ~3,000 in / 2,000 out |

**3 API calls per run.** The naive approach (one call per article) would be 129 calls, adding ~60 seconds of latency and ~40x the cost. Batching all articles into one structured prompt and requesting a positionally-aligned JSON array response is the core LLM engineering decision in this project.

Each LLM node has a graceful fallback: if the response fails to parse, it logs the error and passes articles through rather than crashing the pipeline.

---

## Sources

| Source | Tier | Type | Articles/day |
|---|---|---|---|
| VentureBeat AI | 1 — editorial | RSS | ~7 |
| TechCrunch AI | 1 — editorial | RSS | ~18 |
| arXiv cs.AI | 1 — peer-reviewed | RSS | 30 (capped; publishes 300+) |
| HackerNews | 2 — community | Algolia API | ~4–20 |

Source tier is included in the scoring prompt as a mild tiebreaker — the LLM scores on content first.

---

## Sample Run

```
Starting AI Daily Briefing Agent...

  [fetch] TechCrunch AI: 18 articles
  [fetch] arXiv cs.AI: 30 articles
  [fetch] VentureBeat AI: 7 articles
  [fetch] HackerNews: 4 articles
  [fetch] Total raw articles: 59
  [deduplicate] 59 -> 59 articles (0 URL dupes, 0 title dupes removed)
  [score] Scoring 59 articles with claude-haiku-4-5-20251001...
  [score] 59 scored, 35 passed threshold (>= 6)
  [score] Distribution: {1: 1, 2: 3, 3: 4, 4: 7, 5: 9, 6: 11, 7: 14, 8: 10, 9: 0, 10: 0}
  [categorize] Categorizing 35 articles with claude-haiku-4-5-20251001...
  [summarize] Summarizing 35 articles with claude-haiku-4-5-20251001...
  [rank] 35 articles -> top 10
  [db] Saved run 2026-05-02 - 10 articles (run_id=1)

=================================================================
  AI DAILY BRIEFING  |  2026-05-02
=================================================================
  Fetched: 59  |  Passed scoring: 35  |  Retries: 0
=================================================================

  --- AI NEWS ---

  #1  [ 8/10]  When Your LLM Reaches End-of-Life: A Framework for Confident
               Model Migration in Production Systems
       Researchers present a Bayesian statistical framework for migrating
       production LLM systems when models reach end-of-life. This addresses
       a critical real-world challenge directly applicable to engineers
       running LLM infrastructure.
       https://arxiv.org/abs/2604.27082

  #2  [ 8/10]  Think it, Run it: Autonomous ML pipeline generation via
               self-healing multi-agent AI
       A multi-agent architecture automates end-to-end ML pipeline generation
       from natural language goals and datasets, handling feature engineering,
       model selection, and hyperparameter tuning autonomously.
       https://arxiv.org/abs/2604.27096

  --- CEO UPDATE ---

  #10 [ 8/10]  Sources: Anthropic potential $900B+ valuation round could
               happen within 2 weeks
       Anthropic is moving quickly on a $900B+ funding round. The valuation
       jump reflects explosive growth in the Claude ecosystem and signals
       strong institutional confidence in frontier models.
       https://techcrunch.com/2026/04/30/anthropic-potential-900b-valuation...

=================================================================
  10 stories | run: 2026-05-02T06:49:14.295457+00:00
=================================================================
```

---

## Project Structure

```
AI_News_Agent/
├── run_agent.py            # Entry point — runs the full pipeline
├── config.py               # Sources, model, thresholds (all tunable values)
├── database.py             # SQLite helpers: init, save_run, get_latest_run, history
├── requirements.txt
├── .env.example            # Required env vars (copy to .env and fill in)
│
├── agent/
│   ├── state.py            # AgentState + Article TypedDicts (shared data contract)
│   ├── graph.py            # LangGraph StateGraph — wires all nodes + retry edge
│   ├── nodes/
│   │   ├── fetch.py        # Parallel fetch with ThreadPoolExecutor
│   │   ├── deduplicate.py  # Two-pass dedup: URL exact + title fuzzy match
│   │   ├── score.py        # LLM call #1 — scores + filters articles
│   │   ├── categorize.py   # LLM call #2 — assigns ai_news/career/ceo_update
│   │   ├── summarize.py    # LLM call #3 — 2-3 sentence summaries
│   │   └── rank.py         # Python sort by score DESC, zero LLM calls
│   └── tools/
│       ├── rss_reader.py   # Generic RSS parser → list[Article]
│       └── hackernews.py   # HN Algolia API → list[Article]
│
├── dashboard/
│   └── app.py              # Streamlit dashboard — Today + Run History tabs
│
└── data/
    └── briefings.db        # SQLite — created automatically on first run
```

---

## Setup

**Prerequisites:** Python 3.11+, an [Anthropic API key](https://console.anthropic.com/)

```bash
git clone https://github.com/Tejaswini2112/ai_updates_agent
cd ai_updates_agent

python -m venv venv
source venv/Scripts/activate      # Windows bash
# source venv/bin/activate         # macOS / Linux

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

**Run the agent:**
```bash
python run_agent.py
```

**Open the dashboard** (after at least one agent run):
```bash
streamlit run dashboard/app.py
```

---

## Key Engineering Decisions

**Batched LLM calls** — All articles are scored in a single prompt requesting a positionally-aligned JSON array. Same for categorize and summarize. 3 calls/run vs the naive 129. Latency matters: 3 sequential calls take ~5s; 129 calls would take 30–60s even with parallelism.

**Score-then-sort** — The LLM assigns 1–10 scores; Python sorts. Deterministic: the same article corpus always produces the same ranking. No additional LLM call for ordering.

**Conditional retry loop** — If zero articles pass the relevance threshold (unusual but possible on a slow news day), the graph retries the fetch up to 2 times before accepting an empty result. This is handled as a LangGraph conditional edge with a routing function (`"retry"` / `"continue"`) and a dedicated state-mutation node — because LangGraph routing functions cannot modify state, only read it.

**Conservative dedup threshold (0.80)** — A false non-merge (keeping a near-duplicate) is less harmful than a false merge (losing a distinct story). Titles are normalized first (lowercase, punctuation stripped) before similarity is computed.

**HN Algolia URL encoding** — `requests` percent-encodes `>` to `%3E` in query parameters. Algolia's HN API requires a raw `>` in `numericFilters`. Fixed by building the URL string manually: `f"...?{safe_params}&numericFilters=created_at_i>{cutoff}"`. Complex OR queries silently break when combined with `numericFilters`, so two separate simple queries (`"AI"`, `"LLM"`) are merged and deduplicated by `objectID`.

**State immutability** — Nodes never mutate articles from `raw_articles` in place. Each node that needs to modify an article does `dict(article)` first. This prevents downstream nodes from seeing partially-mutated state if a node fails mid-loop.

---

## Observability

LangSmith tracing is configured out of the box. Add `LANGCHAIN_API_KEY` and `LANGCHAIN_TRACING_V2=true` to your `.env` to get per-node execution traces, token counts, and latency breakdowns at [smith.langchain.com](https://smith.langchain.com).

---

## Roadmap

- [x] Streamlit Community Cloud deployment — [live demo](https://aiupdatesagent-srfpljb2t9bwzzqk54olpn.streamlit.app)
- [ ] Daily scheduler (APScheduler) — run automatically at 7am
- [ ] Email digest (SendGrid) — push the briefing rather than pull

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | LangGraph 1.1.10 |
| LLM | Claude Haiku 4.5 (Anthropic SDK) |
| Data fetching | feedparser, requests |
| State contract | Python TypedDict |
| Persistence | SQLite (stdlib) |
| Dashboard | Streamlit 1.57 |
| Observability | LangSmith |
