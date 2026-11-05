import json
import tempfile
import unittest
from pathlib import Path

from exporter import export_dashboard
from storage import database, upsert_fund_nav_observations, upsert_observations


class ExporterTest(unittest.TestCase):
    def test_export_dashboard_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "test.db"
            observations = []
            for index, day in enumerate(range(1, 8), start=0):
                for metric, tenor, rating, base in [
                    ("cdb_yield", 5.0, "", 1.5),
                    ("bank_t2_yield", 5.0, "AAA-", 1.8),
                ]:
                    observations.append(
                        {
                            "metric": metric,
                            "observation_date": f"2026-08-{day:02d}",
                            "tenor": tenor,
                            "rating": rating,
                            "value": base + index * 0.01,
                            "unit": "percent",
                            "source": "ChinaBond",
                            "source_url": "https://example.invalid",
                            "source_tier": "official",
                            "fetched_at": "2026-08-25T00:00:00+00:00",
                            "quality": "ok",
                        }
                    )
            with database(db_path) as conn:
                upsert_observations(conn, observations)
            dashboard = export_dashboard(db_path=db_path, output_dir=root / "web-data")
            self.assertEqual(dashboard["meta"]["latest_data_date"], "2026-08-07")
            spread_points = dashboard["series"]["spread_t2_cdb_5"]["points"]
            self.assertTrue(spread_points)
            self.assertAlmostEqual(spread_points[-1]["value"], 30.0)
            self.assertAlmostEqual(spread_points[-1]["change_1d_bp"], 0.0)
            self.assertTrue((root / "web-data" / "market-history.csv").exists())
            payload = json.loads((root / "web-data" / "dashboard.json").read_text())
            self.assertEqual(len(payload["funds"]), 3)
            xingquan = next(fund for fund in payload["funds"] if fund["code"] == "006985")
            self.assertEqual(xingquan["report_period_end"], "2026-09-30")
            self.assertGreater(
                xingquan["bond_composition"]["credit"]["weight_pct"],
                xingquan["bond_composition"]["rate"]["weight_pct"],
            )
            self.assertEqual(
                {holding["classification"] for holding in xingquan["top_holdings"]},
                {"credit", "rate"},
            )

    def test_exports_fund_nav_and_correlations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "test.db"
            market = []
            nav = []
            for index in range(25):
                day = f"2026-07-{index + 1:02d}"
                nav.append(
                    {
                        "fund_code": "006985",
                        "nav_date": day,
                        "unit_nav": 1.2 + index / 10000,
                        "cumulative_nav": 1.3 + index / 10000,
                        "daily_return_pct": float(index),
                        "source": "Eastmoney",
                        "source_url": "https://example.invalid/fund",
                        "source_tier": "fallback",
                        "fetched_at": "2026-08-26T00:00:00+00:00",
                        "quality": "ok",
                    }
                )
                for metric, tenor, rating, value in [
                    ("cdb_yield", 5.0, "", 1.5 + index * index / 10000),
                    ("cdb_yield", 10.0, "", 1.6 + index / 100),
                    ("bank_t2_yield", 3.0, "AAA-", 1.8 + index / 50),
                    ("bank_t2_yield", 5.0, "AAA-", 1.9 + index / 50),
                    ("dr007", 7 / 365, "", 1.4 + index / 100),
                ]:
                    market.append(
                        {
                            "metric": metric,
                            "observation_date": day,
                            "tenor": tenor,
                            "rating": rating,
                            "value": value,
                            "unit": "percent",
                            "source": "Official",
                            "source_url": "https://example.invalid/market",
                            "source_tier": "official",
                            "fetched_at": "2026-08-26T00:00:00+00:00",
                            "quality": "ok",
                        }
                    )
            with database(db_path) as conn:
                upsert_observations(conn, market)
                upsert_fund_nav_observations(conn, nav)
            dashboard = export_dashboard(db_path=db_path, output_dir=root / "web-data")
            comparison = dashboard["fund_nav_comparison"]["006985"]
            self.assertEqual(comparison["latest_nav_date"], "2026-07-25")
            self.assertEqual(len(comparison["nav_points"]), 25)
            self.assertEqual(
                comparison["correlations"]["20"]["cdb_yield_5"]["strength"],
                "very_strong",
            )


if __name__ == "__main__":
    unittest.main()
