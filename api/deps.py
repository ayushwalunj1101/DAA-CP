"""Shared API dependencies."""
from __future__ import annotations

import sqlite3
from typing import Iterator

from pipeline.config import DB_PATH


def read_connection() -> Iterator[sqlite3.Connection]:
    """A read-only SQLite connection per request (cheap for SQLite, safe across threads)."""
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    try:
        yield con
    finally:
        con.close()
