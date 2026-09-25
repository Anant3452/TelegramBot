"""Google News RSS search: no account, no key."""

import html
import re
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from . import http

RSS_URL = "https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"


def top_story(phrase, recent_days=30):
    """Top Google News result for `phrase` from the last `recent_days`, or None."""
    query = urllib.parse.quote(f"{phrase} when:{recent_days}d")
    try:
        xml = http.request("GET", RSS_URL.format(q=query), raw=True, timeout=10)
        item = ET.fromstring(xml).find("./channel/item")
    except Exception:
        return None
    if item is None:
        return None

    title = (item.findtext("title") or "").strip()
    source = (item.findtext("source") or "").strip()
    # Google appends " - Source" to every headline; drop it since we show source separately.
    if source and title.endswith(f" - {source}"):
        title = title[: -len(f" - {source}")]

    date = item.findtext("pubDate") or ""
    try:
        date = parsedate_to_datetime(date).strftime("%d %b %Y")
    except (TypeError, ValueError):
        pass

    summary = html.unescape(re.sub(r"<[^>]+>", " ", item.findtext("description") or ""))
    summary = re.sub(r"\s+", " ", summary).strip() or title

    return {
        "headline": title,
        "source": source or "Unknown source",
        "date": date,
        "link": (item.findtext("link") or "").strip(),
        "summary": summary,
    }
