from __future__ import annotations

from ..config import load_config
from ..db import get_setting, set_setting
from ..utils import now_local, to_utc_iso
from .arxiv_client import fetch_arxiv
from .gemini_client import analyze_paper
from .paper_service import store_paper, update_analysis
from .semantic_client import fetch_semantic_scholar


CONFIG = load_config()


def _load_keywords() -> list[str]:
    stored = get_setting("paper_keywords")
    if stored:
        return [kw.strip() for kw in stored.split(",") if kw.strip()]
    return CONFIG.paper_keywords


def _load_thesis_topic() -> str:
    return get_setting("thesis_topic") or CONFIG.thesis_topic


def scan_papers() -> dict:
    keywords = _load_keywords()
    fetched_at = to_utc_iso(now_local())

    max_results = CONFIG.max_papers_per_day if CONFIG.max_papers_per_day > 0 else 200

    try:
        arxiv_papers = fetch_arxiv(keywords, max_results=max_results)
    except Exception:
        arxiv_papers = []

    try:
        semantic_papers = fetch_semantic_scholar(
            keywords,
            max_results=max_results,
            api_key=CONFIG.semantic_scholar_api_key,
        )
    except Exception:
        semantic_papers = []

    new_papers = 0
    analyzed = 0
    analysis_budget = CONFIG.max_papers_per_day

    for paper in arxiv_papers:
        paper_id = store_paper(
            "arxiv",
            paper["source_id"],
            paper["title"],
            paper.get("abstract"),
            paper.get("url"),
            paper.get("authors"),
            paper.get("published_at"),
            fetched_at,
        )
        if paper_id:
            new_papers += 1
            if analysis_budget > 0:
                try:
                    score, summary, tags = analyze_paper(
                        CONFIG.gemini_api_key,
                        _load_thesis_topic(),
                        paper["title"],
                        paper.get("abstract") or "",
                    )
                    update_analysis(paper_id, score, summary, tags)
                    analyzed += 1
                    analysis_budget -= 1
                except Exception:
                    pass

    for paper in semantic_papers:
        paper_id = store_paper(
            "semantic_scholar",
            paper["source_id"],
            paper["title"],
            paper.get("abstract"),
            paper.get("url"),
            paper.get("authors"),
            paper.get("published_at"),
            fetched_at,
        )
        if paper_id:
            new_papers += 1
            if analysis_budget > 0:
                try:
                    score, summary, tags = analyze_paper(
                        CONFIG.gemini_api_key,
                        _load_thesis_topic(),
                        paper["title"],
                        paper.get("abstract") or "",
                    )
                    update_analysis(paper_id, score, summary, tags)
                    analyzed += 1
                    analysis_budget -= 1
                except Exception:
                    pass

    set_setting("last_scan", fetched_at)
    return {"new_papers": new_papers, "analyzed": analyzed}
