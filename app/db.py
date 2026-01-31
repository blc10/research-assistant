from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .config import load_config


CONFIG = load_config()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(CONFIG.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due_at TEXT,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            source TEXT,
            reminded_at TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_id TEXT NOT NULL,
            title TEXT NOT NULL,
            abstract TEXT,
            url TEXT,
            authors TEXT,
            published_at TEXT,
            fetched_at TEXT NOT NULL,
            relevance_score REAL,
            summary TEXT,
            tags TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            UNIQUE(source, source_id)
        );

        CREATE TABLE IF NOT EXISTS reads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER NOT NULL,
            read_at TEXT NOT NULL,
            FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            progress INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pending_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def get_setting(key: str, default: str | None = None) -> str | None:
    conn = get_connection()
    cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row["value"]
    return default


def set_setting(key: str, value: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    conn = get_connection()
    cur = conn.execute(query, params)
    row = cur.fetchone()
    conn.close()
    return row


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    conn = get_connection()
    cur = conn.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    conn = get_connection()
    cur = conn.execute(query, params)
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def execute_many(query: str, params: list[tuple[Any, ...]]) -> None:
    conn = get_connection()
    conn.executemany(query, params)
    conn.commit()
    conn.close()


def ensure_defaults() -> None:
    from .config import load_config

    cfg = load_config()
    if get_setting("thesis_topic") is None:
        set_setting("thesis_topic", cfg.thesis_topic)
    if get_setting("paper_keywords") is None:
        set_setting("paper_keywords", ",".join(cfg.paper_keywords))
    if cfg.telegram_chat_id and get_setting("telegram_chat_id") is None:
        set_setting("telegram_chat_id", cfg.telegram_chat_id)
