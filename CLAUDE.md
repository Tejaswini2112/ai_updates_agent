# AI Daily Briefing Agent — Project Context

## What This Is
A personal AI news agent built with LangGraph. Fetches AI/career news from 4 sources every morning, scores relevance with Claude Haiku, deduplicates, categorizes, summarizes, ranks top 10, saves to SQLite, and sends an email digest. Portfolio project + real daily tool.

## Current Status
**Phase 1, Week 1 — COMPLETE** ✓
- [x] Session 1: Environment setup, folder structure, `state.py`, `config.py`
- [x] Session 2: `agent/tools/rss_reader.py`, `agent/tools/hackernews.py`, `test_tools.py`
- [x] Session 3: `agent/nodes/fetch.py` (parallel fetch node, first LangGraph node)
- [x] Session 4: `agent/nodes/deduplicate.py`
- [x] Session 5: `agent/nodes/score.py` (batched Claude Haiku call)
- [x] Session 6: `agent/nodes/categorize.py` + `agent/nodes/summarize.py`
- [x] Session 7: `agent/nodes/rank.py` (Python sort, zero LLM calls)
- [x] Session 8: `agent/graph.py` — wire all nodes, run end-to-end

## Architecture (v2 Plan)
Build plan: `AI_Briefing_Agent_Project_Plan_v2.pdf` — use v2 as authoritative.

### Pipeline
```
load_preferences → fetch_news → deduplicate → score_relevance
  → [CONDITIONAL EDGE 1: retry if 0 articles pass, max 2 retries]
  → categorize → summarize → rank_top_10 → save_to_db
  → [CONDITIONAL EDGE 2: send_email if scheduled, skip if on-demand]
  → END
```

### State (agent/state.py)
```python
AgentState = {
    user_preferences: dict,
    raw_articles: list[Article],       # filled by fetch node
    filtered_articles: list[Article],  # filled by score node (score >= threshold)
    categorized_articles: dict,        # {ai_news, career, ceo_update}
    top_10: list[Article],             # sorted by score DESC
    retry_count: int,                  # guards fetch→score loop (max 2)
    run_timestamp: str,
    email_sent: bool,
}
```

### Article shape (agent/state.py)
```python
Article = {
    title, url, description, source_name, source_tier,
    published_at,         # ISO 8601
    score,                # None until score node; int 1-10 after
    score_reason,         # None until score node
    category,             # None until categorize node
    summary,              # None until summarize node
}
```

## Sources (config.py)
| Source | Tier | Type | Notes |
|---|---|---|---|
| VentureBeat AI | 1 | RSS | ~7 articles/day |
| TechCrunch AI | 1 | RSS | ~18 articles/day |
| arXiv cs.AI | 1 | RSS | Capped at 30 (publishes 300+/day) |
| HackerNews | 2 | API | Algolia, 2 queries × 20 results, 48h window |

Phase 2 adds: Reddit RSS (3 subs), Google News RSS.
Official company blogs (OpenAI, Anthropic) deferred — no standard RSS.

## Key Config Values (config.py)
```python
LLM_MODEL = "claude-haiku-4-5-20251001"
RELEVANCE_THRESHOLD = 6      # articles scoring below this are dropped
TOP_N = 10                   # final stories in briefing
MAX_FETCH_RETRIES = 2        # retry loop guard
HN_QUERIES = ["AI", "LLM"]  # two simple queries, merged + deduped
HN_RESULTS_PER_QUERY = 20
_MAX_ARTICLES_PER_SOURCE = 30   # in rss_reader.py
```

## LLM Strategy (v2 — critical)
- **3 batched calls total per run** (not 1 per article):
  - `score.py`: all ~40-60 articles → JSON `[{score, reason}]`
  - `categorize.py`: filtered articles → JSON `[{category}]`
  - `summarize.py`: filtered articles → JSON `[{summary}]`
- **rank.py uses zero LLM calls** — Python sort by score DESC
- **Scoring prompt includes source tier weights**: Tier 1 articles weighted higher

## Bugs Found and Fixed (Session 2)
1. **arXiv returns 322 articles/day** — fixed with `feed.entries[:30]` cap in rss_reader.py
2. **HTML entities** (`&#x27;` etc.) — fixed with `html.unescape()` in `_clean_html()`
3. **arXiv boilerplate prefix** ("arXiv:XXXX Announce Type: new Abstract:") — stripped with regex `_ARXIV_PREFIX`
4. **HackerNews Algolia `numericFilters`** — `requests` percent-encodes `>` to `%3E`; Algolia's HN API needs raw `>`. Fixed by building URL manually: `f"{_HN_API}?{safe_params}&numericFilters=created_at_i>{cutoff}"`
5. **Complex OR queries break HN Algolia + date filter** — returns 0 results. Fixed by switching to two simple queries (`"AI"`, `"LLM"`) merged and deduped by `objectID`

## Tech Decisions and Why
- **LangGraph** over plain Python functions: state management, explicit conditional edges, LangSmith tracing, inspectable graph
- **Claude Haiku** (not GPT-4o-mini): already have Anthropic key, prompt caching available, same model family as dev tooling
- **Batched LLM calls**: 3-4 calls/run vs 90+ in naive approach. Not just cost — latency and debuggability.
- **Score-then-sort** (v2 change from v1): LLM scores 1-10, Python sorts. Deterministic. Same scores = same ranking every time.
- **No scheduler in Phase 1**: `python run_agent.py` manually until pipeline is fully validated
- **SQLite not Postgres**: zero setup, local file, upgrade later if needed
- **No official company blogs (Phase 1)**: no standard RSS, adds complexity before core pipeline is validated

## Folder Structure
```
AI_News_Agent/
├── CLAUDE.md               ← this file
├── config.py               ← all tunable values (sources, model, thresholds)
├── agent/
│   ├── state.py            ← AgentState + Article TypedDicts
│   ├── graph.py            ← LangGraph graph definition (Session 8)
│   ├── nodes/
│   │   ├── fetch.py        ← parallel fetch, concurrent.futures ✅ DONE
│   │   ├── deduplicate.py  ← fuzzy title matching ✅ DONE
│   │   ├── score.py        ← batched LLM call #1 ✅ DONE
│   │   ├── categorize.py   ← batched LLM call #2 ✅ DONE
│   │   ├── summarize.py    ← batched LLM call #3 ✅ DONE
│   │   ├── rank.py         ← Python sort, 0 LLM calls ✅ DONE
│   │   └── deliver.py      ← save_to_db + send_email (Phase 2)
│   ├── graph.py            ← LangGraph StateGraph, conditional retry edge ✅ DONE
│   └── tools/
│       ├── rss_reader.py   ← generic RSS → list[Article] ✅ DONE
│       └── hackernews.py   ← HN Algolia API → list[Article] ✅ DONE
├── dashboard/              ← Streamlit (Phase 1 Week 2)
│   ├── app.py
│   └── pages/today.py
├── database.py             ← SQLite helpers (Phase 1 Week 2)
├── test_tools.py           ← Session 2 test ✅ DONE
├── run_agent.py            ← entry point ✅ DONE
├── requirements.txt
└── .env                    ← ANTHROPIC_API_KEY + LANGCHAIN_API_KEY set
```

## Environment
- Python 3.13.2, venv at `venv/`
- Activate: `source venv/Scripts/activate` (bash) or `venv\Scripts\Activate.ps1` (PowerShell)
- VSCode interpreter: `venv\Scripts\python.exe` (select via Ctrl+Shift+P → Python: Select Interpreter)
- LangSmith tracing: configured, traces to project `ai-briefing-agent`

## Build Rule
One node at a time. Get it working. Test it. Only then move to the next.
