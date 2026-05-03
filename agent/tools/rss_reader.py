import re
import html
import feedparser
from datetime import datetime, timezone, timedelta
from agent.state import Article

# arXiv RSS descriptions always start with this boilerplate — strip it
_ARXIV_PREFIX = re.compile(r"^arXiv:\S+\s+Announce Type:\s+\w+\s+Abstract:\s*", re.IGNORECASE)

# Cap per-source to avoid flooding the pipeline (arXiv publishes 300+ papers/day)
_MAX_ARTICLES_PER_SOURCE = 30

# Drop articles older than this — prevents stale arXiv revisions and old feed entries
_MAX_AGE_DAYS = 7


def _clean_html(text: str) -> str:
    text = html.unescape(text)                    # decode &#x27; → ' etc.
    text = re.sub(r"<[^>]+>", " ", text)          # strip HTML tags
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _get_description(entry) -> str:
    # content[] holds full text on some feeds; summary/description is the excerpt
    if hasattr(entry, "content") and entry.content:
        text = _clean_html(entry.content[0].value)
    elif hasattr(entry, "summary") and entry.summary:
        text = _clean_html(entry.summary)
    elif hasattr(entry, "description") and entry.description:
        text = _clean_html(entry.description)
    else:
        return ""

    # Strip arXiv boilerplate prefix so the LLM sees only the abstract
    text = _ARXIV_PREFIX.sub("", text)
    return text[:500]


def _parse_date(entry) -> str:
    # feedparser gives published_parsed as time.struct_time (UTC)
    if getattr(entry, "published_parsed", None):
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    # fallback: raw string → let dateutil handle it
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw:
        try:
            from dateutil import parser as dp
            return dp.parse(raw).isoformat()
        except Exception:
            pass
    return datetime.now(timezone.utc).isoformat()


def fetch_rss(source: dict) -> list[Article]:
    """Parse an RSS feed and return a normalised list of Article dicts."""
    try:
        feed = feedparser.parse(source["url"])
    except Exception as e:
        print(f"  [rss_reader] ERROR fetching {source['name']}: {e}")
        return []

    if feed.bozo and not feed.entries:
        print(f"  [rss_reader] WARNING: {source['name']} returned a malformed feed")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=_MAX_AGE_DAYS)

    articles: list[Article] = []
    for entry in feed.entries[:_MAX_ARTICLES_PER_SOURCE]:
        title = getattr(entry, "title", "").strip()
        url = getattr(entry, "link", "").strip()
        if not title or not url:
            continue

        published_at = _parse_date(entry)
        try:
            pub_dt = datetime.fromisoformat(published_at)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            if pub_dt < cutoff:
                continue
        except Exception:
            pass

        articles.append(
            Article(
                title=title,
                url=url,
                description=_get_description(entry),
                source_name=source["name"],
                source_tier=source["tier"],
                published_at=published_at,
                score=None,
                score_reason=None,
                category=None,
                summary=None,
            )
        )

    return articles
