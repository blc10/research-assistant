from __future__ import annotations

import requests


def fetch_semantic_scholar(
    keywords: list[str],
    max_results: int = 50,
    api_key: str | None = None,
) -> list[dict]:
    max_results = min(max_results, 100)
    query = " OR ".join([f'"{kw}"' if " " in kw else kw for kw in keywords])
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,abstract,url,authors,venue,year,publicationDate",
    }
    headers = {"User-Agent": "PersonalResearchAssistant/1.0"}
    if api_key:
        headers["x-api-key"] = api_key

    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()
    papers = []
    for item in data.get("data", []):
        paper_id = item.get("paperId")
        title = item.get("title") or ""
        abstract = item.get("abstract") or ""
        url_value = item.get("url")
        authors = ", ".join([author.get("name", "") for author in item.get("authors", [])])
        published_at = item.get("publicationDate") or str(item.get("year") or "")
        papers.append(
            {
                "source_id": paper_id,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "published_at": published_at,
                "url": url_value,
            }
        )
    return papers
