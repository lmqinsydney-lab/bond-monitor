import tempfile
import unittest
from pathlib import Path

from storage import (
    database,
    preferred_fund_nav_series,
    upsert_fund_nav_observations,
    upsert_observations,
)


def observation(value: float, fetched_at: str = "2026-08-25T09:00:00+00:00") -> dict[str, object]:
    return {
        "metric": "cgb_yield",
        "observation_date": "2026-08-25",
        "tenor": 10.0,
        "rating": "",
        "value": value,
        "unit": "percent",
        "source": "ChinaBond",
        "source_url": "https://example.invalid/official",
        "source_tier": "official",
        "fetched_at": fetched_at,
        "quality": "ok",
    }


class StorageTest(unittest.TestCase):
    def test_idempotent_insert_and_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.db"
            with database(path) as conn:
                self.assertEqual(upsert_observations(conn, [observation(1.68)]), (1, 0, 0))
                self.assertEqual(upsert_observations(conn, [observation(1.68)]), (0, 1, 0))
                changed = observation(1.69, "2026-08-25T10:00:00+00:00")
                self.assertEqual(upsert_observations(conn, [changed]), (0, 0, 1))
                revisions = conn.execute("SELECT old_value, new_value FROM revisions").fetchall()
                self.assertEqual(len(revisions), 1)
                self.assertAlmostEqual(revisions[0]["old_value"], 1.68)
                self.assertAlmostEqual(revisions[0]["new_value"], 1.69)

    def test_fund_nav_idempotence_revision_and_preference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.db"
            base = {
                "fund_code": "006985",
                "nav_date": "2026-08-25",
                "unit_nav": 1.2112,
                "cumulative_nav": 1.2772,
                "daily_return_pct": 0.01,
                "source": "Eastmoney",
                "source_url": "https://example.invalid/fund",
                "source_tier": "fallback",
                "fetched_at": "2026-08-26T00:00:00+00:00",
                "quality": "ok",
            }
            with database(path) as conn:
                self.assertEqual(upsert_fund_nav_observations(conn, [base]), (1, 0, 0))
                self.assertEqual(upsert_fund_nav_observations(conn, [base]), (0, 1, 0))
                changed = {**base, "daily_return_pct": 0.02}
                self.assertEqual(upsert_fund_nav_observations(conn, [changed]), (0, 0, 1))
                revision = conn.execute(
                    "SELECT field_name, old_value, new_value FROM fund_nav_revisions"
                ).fetchone()
                self.assertEqual(revision["field_name"], "daily_return_pct")
                self.assertAlmostEqual(revision["old_value"], 0.01)
                official = {
                    **base,
                    "unit_nav": 1.2113,
                    "source": "FundManager",
                    "source_tier": "official",
                }
                upsert_fund_nav_observations(conn, [official])
                preferred = preferred_fund_nav_series(conn, "006985")
                self.assertEqual(len(preferred), 1)
                self.assertEqual(preferred[0]["source"], "FundManager")


if __name__ == "__main__":
    unittest.main()
