from __future__ import annotations

import urllib.parse
from datetime import datetime

import feedparser
import requests


def _build_query(keywords: list[str]) -> str:
    quoted = [f'"{kw}"' if " " in kw else kw for kw in keywords]
    query = " OR ".join([f"all:{kw}" for kw in quoted])
    return query


def fetch_arxiv(keywords: list[str], max_results: int = 50) -> list[dict]:
    query = _build_query(keywords)
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "PersonalResearchAssistant/1.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    feed = feedparser.parse(response.text)
    papers = []
    for entry in feed.entries:
        paper_id = entry.get("id")
        title = " ".join(entry.get("title", "").split())
        summary = " ".join(entry.get("summary", "").split())
        authors = ", ".join([author.name for author in entry.get("authors", [])])
        published = entry.get("published")
        link = entry.get("link")
        papers.append(
            {
                "source_id": paper_id,
                "title": title,
                "abstract": summary,
                "authors": authors,
                "published_at": published,
                "url": link,
            }
        )
    return papers
