"""溯源库初始化：按 schema.sql 建库。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = Path(__file__).with_name("schema.sql")


def init_db(db_path: str | Path) -> str:
    """建库（幂等）。返回 db 路径。"""
    db_path = str(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    return db_path
