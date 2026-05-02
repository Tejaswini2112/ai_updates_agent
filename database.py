"""
SQLite persistence for the AI Daily Briefing Agent.

Schema:
  runs     — one row per pipeline execution
  articles — one row per article in each run's top_10

DB file: data/briefings.db  (created automatically on first use)
"""
import sqlite3
from pathlib import Path

from agent.state import Article

DB_PATH = Path(__file__).parent / "data" / "briefings.db"

_CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp  TEXT    NOT NULL UNIQUE,
    article_count  INTEGER NOT NULL
);
"""

_CREATE_ARTICLES = """
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL REFERENCES runs(id),
    title         TEXT,
    url           TEXT,
    description   TEXT,
    source_name   TEXT,
    source_tier   INTEGER,
    published_at  TEXT,
    score         INTEGER,
    score_reason  TEXT,
    category      TEXT,
    summary       TEXT
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't already exist. Safe to call on every startup."""
    with _connect() as conn:
        conn.execute(_CREATE_RUNS)
        conn.execute(_CREATE_ARTICLES)


def save_run(run_timestamp: str, top_10: list[Article]) -> int:
    """Persist one pipeline run. Returns the run_id. Idempotent on same timestamp."""
    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM runs WHERE run_timestamp = ?", (run_timestamp,)
        ).fetchone()
        if existing:
            print(f"  [db] Run {run_timestamp} already saved (run_id={existing['id']})")
            return existing["id"]

        cur = conn.execute(
            "INSERT INTO runs (run_timestamp, article_count) VALUES (?, ?)",
            (run_timestamp, len(top_10)),
        )
        run_id = cur.lastrowid

        conn.executemany(
            """
            INSERT INTO articles
              (run_id, title, url, description, source_name, source_tier,
               published_at, score, score_reason, category, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    a["title"],
                    a["url"],
                    a["description"],
                    a["source_name"],
                    a["source_tier"],
                    a["published_at"],
                    a["score"],
                    a["score_reason"],
                    a["category"],
                    a["summary"],
                )
                for a in top_10
            ],
        )

    print(f"  [db] Saved run {run_timestamp[:10]} - {len(top_10)} articles (run_id={run_id})")
    return run_id


def get_latest_run() -> tuple[dict, list[Article]] | None:
    """Return (run_info, articles) for the most recent run, or None if DB is empty."""
    with _connect() as conn:
        run_row = conn.execute(
            "SELECT * FROM runs ORDER BY run_timestamp DESC LIMIT 1"
        ).fetchone()
        if run_row is None:
            return None

        run_info = dict(run_row)
        article_rows = conn.execute(
            "SELECT * FROM articles WHERE run_id = ? ORDER BY score DESC",
            (run_info["id"],),
        ).fetchall()

        articles: list[Article] = [dict(row) for row in article_rows]  # type: ignore[assignment]
        return run_info, articles


def get_run_history(limit: int = 30) -> list[dict]:
    """Return run summaries (id, run_timestamp, article_count), newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, run_timestamp, article_count FROM runs "
            "ORDER BY run_timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_run_articles(run_id: int) -> list[Article]:
    """Return all articles for a given run_id, sorted by score DESC."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM articles WHERE run_id = ? ORDER BY score DESC",
            (run_id,),
        ).fetchall()
        return [dict(row) for row in rows]  # type: ignore[return-value]
