from __future__ import annotations

from ..db import execute, fetch_all, fetch_one


def store_paper(
    source: str,
    source_id: str,
    title: str,
    abstract: str | None,
    url: str | None,
    authors: str | None,
    published_at: str | None,
    fetched_at: str,
) -> int | None:
    try:
        paper_id = execute(
            """
            INSERT INTO papers(source, source_id, title, abstract, url, authors, published_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source, source_id, title, abstract, url, authors, published_at, fetched_at),
        )
        return paper_id
    except Exception:
        return None


def list_papers(status: str | None = None, limit: int = 50) -> list[dict]:
    if status:
        rows = fetch_all(
            "SELECT * FROM papers WHERE status = ? ORDER BY relevance_score IS NULL, relevance_score DESC, published_at DESC LIMIT ?",
            (status, limit),
        )
    else:
        rows = fetch_all(
            "SELECT * FROM papers ORDER BY published_at DESC LIMIT ?",
            (limit,),
        )
    return [dict(row) for row in rows]


def list_papers_since(since_iso: str, limit: int = 20) -> list[dict]:
    rows = fetch_all(
        """
        SELECT * FROM papers
        WHERE fetched_at >= ?
        ORDER BY relevance_score IS NULL, relevance_score DESC, published_at DESC
        LIMIT ?
        """,
        (since_iso, limit),
    )
    return [dict(row) for row in rows]


def get_paper(paper_id: int) -> dict | None:
    row = fetch_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
    return dict(row) if row else None


def update_analysis(paper_id: int, score: float | None, summary: str | None, tags: str | None) -> None:
    execute(
        "UPDATE papers SET relevance_score = ?, summary = ?, tags = ? WHERE id = ?",
        (score, summary, tags, paper_id),
    )


def mark_read(paper_id: int, read_at_iso: str) -> None:
    execute("UPDATE papers SET status = 'read' WHERE id = ?", (paper_id,))
    execute("INSERT INTO reads(paper_id, read_at) VALUES (?, ?)", (paper_id, read_at_iso))


def count_papers(status: str | None = None) -> int:
    if status:
        row = fetch_one("SELECT COUNT(*) as total FROM papers WHERE status = ?", (status,))
    else:
        row = fetch_one("SELECT COUNT(*) as total FROM papers", ())
    return int(row["total"]) if row else 0


def count_tasks(status: str) -> int:
    row = fetch_one("SELECT COUNT(*) as total FROM tasks WHERE status = ?", (status,))
    return int(row["total"]) if row else 0


def latest_papers(limit: int = 5) -> list[dict]:
    rows = fetch_all(
        "SELECT * FROM papers ORDER BY published_at IS NULL, published_at DESC, fetched_at DESC LIMIT ?",
        (limit,),
    )
    return [dict(row) for row in rows]
