from __future__ import annotations

import sqlite3

import pytest

from pipeline.config import DB_PATH


@pytest.fixture(scope="session")
def real_db() -> sqlite3.Connection:
    """Read-only connection to the imported database; tests using it are skipped if it is missing."""
    if not DB_PATH.exists():
        pytest.skip("data/momentum.db not built; run python -m pipeline.import_local")
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    yield con
    con.close()
