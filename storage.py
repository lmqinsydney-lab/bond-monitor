from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Mapping


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS market_observations (
    id INTEGER PRIMARY KEY,
    metric TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    tenor REAL NOT NULL DEFAULT -1,
    rating TEXT NOT NULL DEFAULT '',
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_tier TEXT NOT NULL CHECK(source_tier IN ('official', 'fallback')),
    fetched_at TEXT NOT NULL,
    quality TEXT NOT NULL DEFAULT 'ok',
    UNIQUE(metric, observation_date, tenor, rating, source)
);

CREATE INDEX IF NOT EXISTS idx_market_series
ON market_observations(metric, tenor, rating, observation_date);

CREATE TABLE IF NOT EXISTS source_fetches (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    request_url TEXT NOT NULL,
    records INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT
);

CREATE TABLE IF NOT EXISTS fund_reports (
    id INTEGER PRIMARY KEY,
    fund_code TEXT NOT NULL,
    report_period_end TEXT NOT NULL,
    published_at TEXT NOT NULL,
    source_url TEXT NOT NULL,
    local_path TEXT,
    parse_status TEXT NOT NULL,
    error_summary TEXT,
    UNIQUE(fund_code, report_period_end, published_at)
);

CREATE TABLE IF NOT EXISTS fund_profiles (
    id INTEGER PRIMARY KEY,
    fund_code TEXT NOT NULL,
    report_period_end TEXT NOT NULL,
    published_at TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    confidence TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(fund_code, published_at)
);

CREATE TABLE IF NOT EXISTS fund_pressure (
    id INTEGER PRIMARY KEY,
    fund_code TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    profile_published_at TEXT NOT NULL,
    formula_version TEXT NOT NULL,
    result_json TEXT NOT NULL,
    UNIQUE(fund_code, observation_date, profile_published_at, formula_version)
);

CREATE TABLE IF NOT EXISTS revisions (
    id INTEGER PRIMARY KEY,
    observation_id INTEGER NOT NULL,
    old_value REAL NOT NULL,
    new_value REAL NOT NULL,
    revised_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    FOREIGN KEY(observation_id) REFERENCES market_observations(id)
);

CREATE TABLE IF NOT EXISTS fund_nav_observations (
    id INTEGER PRIMARY KEY,
    fund_code TEXT NOT NULL,
    nav_date TEXT NOT NULL,
    unit_nav REAL NOT NULL,
    cumulative_nav REAL,
    daily_return_pct REAL,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_tier TEXT NOT NULL CHECK(source_tier IN ('official', 'fallback')),
    fetched_at TEXT NOT NULL,
    quality TEXT NOT NULL DEFAULT 'ok',
    UNIQUE(fund_code, nav_date, source)
);

CREATE INDEX IF NOT EXISTS idx_fund_nav_series
ON fund_nav_observations(fund_code, nav_date);

CREATE TABLE IF NOT EXISTS fund_nav_revisions (
    id INTEGER PRIMARY KEY,
    observation_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    old_value REAL,
    new_value REAL,
    revised_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    FOREIGN KEY(observation_id) REFERENCES fund_nav_observations(id)
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def default_db_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "bond-monitor.db"


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def database(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


def upsert_observations(
    conn: sqlite3.Connection,
    observations: Iterable[Mapping[str, object]],
    *,
    revision_reason: str = "source refresh",
) -> tuple[int, int, int]:
    inserted = unchanged = revised = 0
    with conn:
        for obs in observations:
            key = (
                obs["metric"],
                obs["observation_date"],
                float(obs.get("tenor", -1)),
                str(obs.get("rating", "")),
                obs["source"],
            )
            row = conn.execute(
                """
                SELECT id, value FROM market_observations
                WHERE metric=? AND observation_date=? AND tenor=? AND rating=? AND source=?
                """,
                key,
            ).fetchone()
            value = float(obs["value"])
            if row is None:
                conn.execute(
                    """
                    INSERT INTO market_observations (
                        metric, observation_date, tenor, rating, value, unit,
                        source, source_url, source_tier, fetched_at, quality
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        *key[:4],
                        value,
                        obs["unit"],
                        key[4],
                        obs["source_url"],
                        obs["source_tier"],
                        obs["fetched_at"],
                        obs.get("quality", "ok"),
                    ),
                )
                inserted += 1
            elif abs(float(row["value"]) - value) <= 1e-10:
                conn.execute(
                    """
                    UPDATE market_observations
                    SET fetched_at=?, quality=?, source_url=?
                    WHERE id=?
                    """,
                    (
                        obs["fetched_at"],
                        obs.get("quality", "ok"),
                        obs["source_url"],
                        row["id"],
                    ),
                )
                unchanged += 1
            else:
                conn.execute(
                    """
                    INSERT INTO revisions (
                        observation_id, old_value, new_value, revised_at, reason
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        row["value"],
                        value,
                        obs["fetched_at"],
                        revision_reason,
                    ),
                )
                conn.execute(
                    """
                    UPDATE market_observations
                    SET value=?, unit=?, source_url=?, source_tier=?, fetched_at=?, quality=?
                    WHERE id=?
                    """,
                    (
                        value,
                        obs["unit"],
                        obs["source_url"],
                        obs["source_tier"],
                        obs["fetched_at"],
                        obs.get("quality", "ok"),
                        row["id"],
                    ),
                )
                revised += 1
    return inserted, unchanged, revised


def _same_optional_number(left: object, right: object) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return abs(float(left) - float(right)) <= 1e-10


def upsert_fund_nav_observations(
    conn: sqlite3.Connection,
    observations: Iterable[Mapping[str, object]],
    *,
    revision_reason: str = "source refresh",
) -> tuple[int, int, int]:
    inserted = unchanged = revised = 0
    fields = ("unit_nav", "cumulative_nav", "daily_return_pct")
    with conn:
        for obs in observations:
            key = (str(obs["fund_code"]), str(obs["nav_date"]), str(obs["source"]))
            row = conn.execute(
                """
                SELECT id, unit_nav, cumulative_nav, daily_return_pct
                FROM fund_nav_observations
                WHERE fund_code=? AND nav_date=? AND source=?
                """,
                key,
            ).fetchone()
            values = {
                "unit_nav": float(obs["unit_nav"]),
                "cumulative_nav": (
                    None if obs.get("cumulative_nav") is None else float(obs["cumulative_nav"])
                ),
                "daily_return_pct": (
                    None if obs.get("daily_return_pct") is None else float(obs["daily_return_pct"])
                ),
            }
            if row is None:
                conn.execute(
                    """
                    INSERT INTO fund_nav_observations (
                        fund_code, nav_date, unit_nav, cumulative_nav, daily_return_pct,
                        source, source_url, source_tier, fetched_at, quality
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key[0], key[1], values["unit_nav"], values["cumulative_nav"],
                        values["daily_return_pct"], key[2], obs["source_url"],
                        obs["source_tier"], obs["fetched_at"], obs.get("quality", "ok"),
                    ),
                )
                inserted += 1
                continue
            changed_fields = [
                field for field in fields if not _same_optional_number(row[field], values[field])
            ]
            if not changed_fields:
                conn.execute(
                    """
                    UPDATE fund_nav_observations
                    SET fetched_at=?, quality=?, source_url=?, source_tier=?
                    WHERE id=?
                    """,
                    (
                        obs["fetched_at"], obs.get("quality", "ok"), obs["source_url"],
                        obs["source_tier"], row["id"],
                    ),
                )
                unchanged += 1
                continue
            for field in changed_fields:
                conn.execute(
                    """
                    INSERT INTO fund_nav_revisions (
                        observation_id, field_name, old_value, new_value, revised_at, reason
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"], field, row[field], values[field], obs["fetched_at"],
                        revision_reason,
                    ),
                )
            conn.execute(
                """
                UPDATE fund_nav_observations
                SET unit_nav=?, cumulative_nav=?, daily_return_pct=?, source_url=?,
                    source_tier=?, fetched_at=?, quality=?
                WHERE id=?
                """,
                (
                    values["unit_nav"], values["cumulative_nav"], values["daily_return_pct"],
                    obs["source_url"], obs["source_tier"], obs["fetched_at"],
                    obs.get("quality", "ok"), row["id"],
                ),
            )
            revised += 1
    return inserted, unchanged, revised


def record_fetch(
    conn: sqlite3.Connection,
    *,
    source: str,
    started_at: str,
    finished_at: str,
    status: str,
    request_url: str,
    records: int,
    error_summary: str | None = None,
) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO source_fetches (
                source, started_at, finished_at, status, request_url, records, error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source, started_at, finished_at, status, request_url, records, error_summary),
        )


def set_state(conn: sqlite3.Connection, key: str, value: object) -> None:
    payload = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    with conn:
        conn.execute(
            "INSERT INTO app_state(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, payload),
        )


def get_state(conn: sqlite3.Connection, key: str, default: object = None) -> object:
    row = conn.execute("SELECT value FROM app_state WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return row["value"]


def preferred_series(
    conn: sqlite3.Connection,
    metric: str,
    *,
    tenor: float = -1,
    rating: str = "",
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY observation_date
                ORDER BY CASE source_tier WHEN 'official' THEN 0 ELSE 1 END, fetched_at DESC
            ) AS source_rank
            FROM market_observations
            WHERE metric=? AND tenor=? AND rating=?
        )
        SELECT * FROM ranked WHERE source_rank=1 ORDER BY observation_date
        """,
        (metric, tenor, rating),
    ).fetchall()
    return [dict(row) for row in rows]


def preferred_fund_nav_series(
    conn: sqlite3.Connection, fund_code: str
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY nav_date
                ORDER BY CASE source_tier WHEN 'official' THEN 0 ELSE 1 END, fetched_at DESC
            ) AS source_rank
            FROM fund_nav_observations
            WHERE fund_code=?
        )
        SELECT * FROM ranked WHERE source_rank=1 ORDER BY nav_date
        """,
        (fund_code,),
    ).fetchall()
    return [dict(row) for row in rows]


def latest_fund_nav_date(conn: sqlite3.Connection, fund_code: str) -> str | None:
    row = conn.execute(
        "SELECT MAX(nav_date) FROM fund_nav_observations WHERE fund_code=?",
        (fund_code,),
    ).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def observation_count(
    conn: sqlite3.Connection,
    metric: str,
    *,
    year: int | None = None,
    source: str | None = None,
) -> int:
    clauses = ["metric=?"]
    params: list[object] = [metric]
    if year is not None:
        clauses.append("observation_date >= ? AND observation_date < ?")
        params.extend([f"{year:04d}-01-01", f"{year + 1:04d}-01-01"])
    if source is not None:
        clauses.append("source=?")
        params.append(source)
    sql = "SELECT COUNT(*) FROM market_observations WHERE " + " AND ".join(clauses)
    return int(conn.execute(sql, params).fetchone()[0])
