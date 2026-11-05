import io
import json
import unittest
import zipfile

from sources import (
    EastmoneyFundNavSource,
    annual_date_ranges,
    SourceError,
    parse_eastmoney_fund_nav_json,
    parse_chinabond_xlsx,
    parse_chinamoney_repo_csv,
    parse_chinamoney_repo_json,
)


def xlsx_fixture() -> bytes:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="inlineStr"><is><t>日期</t></is></c><c r="B1" t="inlineStr"><is><t>标准期限说明</t></is></c><c r="C1" t="inlineStr"><is><t>标准期限(年)</t></is></c><c r="D1" t="inlineStr"><is><t>收益率(%)</t></is></c></row>
<row r="2"><c r="A2" t="inlineStr"><is><t>2026/08/24</t></is></c><c r="B2" t="inlineStr"><is><t>1y</t></is></c><c r="C2" t="n"><v>1.0</v></c><c r="D2" t="inlineStr"><is><t>1.4144</t></is></c></row>
<row r="3"><c r="A3" t="inlineStr"><is><t>2026/08/24</t></is></c><c r="B3" t="inlineStr"><is><t>5y</t></is></c><c r="C3" t="n"><v>5.0</v></c><c r="D3" t="inlineStr"><is><t>1.5250</t></is></c></row>
</sheetData></worksheet>"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", xml)
    return output.getvalue()


class SourceParsingTest(unittest.TestCase):
    def test_parse_chinabond_xlsx(self) -> None:
        records = parse_chinabond_xlsx(
            xlsx_fixture(),
            metric="cdb_yield",
            tenors=(1, 5),
            source_url="https://example.invalid/cdb.xlsx",
            fetched_at="2026-08-25T00:00:00+00:00",
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].observation_date, "2026-08-24")
        self.assertAlmostEqual(records[1].value, 1.525)

    def test_reject_unexpected_header(self) -> None:
        with self.assertRaises(SourceError):
            parse_chinabond_xlsx(
                b"not a zip",
                metric="cdb_yield",
                source_url="https://example.invalid/bad.xlsx",
            )

    def test_parse_repo_latest_json(self) -> None:
        payload = json.dumps(
            {
                "records": [
                    {"date": "26-08-25", "productCode": "DR007", "weightedRate": "1.4531"}
                ]
            }
        ).encode()
        records = parse_chinamoney_repo_json(payload, source_url="https://example.invalid/latest")
        self.assertEqual(records[0].metric, "dr007")
        self.assertEqual(records[0].observation_date, "2026-08-25")

    def test_parse_repo_chart_csv(self) -> None:
        payload = b"2026-08-24,,,,,,1.4229,1.4339,1.4242\n"
        records = parse_chinamoney_repo_csv(payload, source_url="https://example.invalid/chart")
        self.assertAlmostEqual(records[0].value, 1.4339)

    def test_parse_fund_nav_json(self) -> None:
        payload = json.dumps(
            {
                "Data": {
                    "LSJZList": [
                        {
                            "FSRQ": "2026-08-25",
                            "DWJZ": "1.2112",
                            "LJJZ": "1.2772",
                            "JZZZL": "0.01",
                        }
                    ]
                },
                "ErrCode": 0,
                "TotalCount": 1,
            }
        ).encode()
        records = parse_eastmoney_fund_nav_json(
            payload,
            fund_code="006985",
            source_url="https://example.invalid/fund",
            fetched_at="2026-08-26T00:00:00+00:00",
        )
        self.assertEqual(records[0].fund_code, "006985")
        self.assertAlmostEqual(records[0].unit_nav, 1.2112)
        self.assertAlmostEqual(records[0].daily_return_pct, 0.01)
        self.assertEqual(records[0].source_tier, "fallback")

    def test_fund_nav_missing_daily_return_stays_empty(self) -> None:
        payload = json.dumps(
            {
                "Data": {"LSJZList": [{"FSRQ": "2026-08-25", "DWJZ": "1.2", "LJJZ": "1.3", "JZZZL": ""}]},
                "ErrCode": 0,
            }
        ).encode()
        records = parse_eastmoney_fund_nav_json(
            payload, fund_code="006985", source_url="https://example.invalid/fund"
        )
        self.assertIsNone(records[0].daily_return_pct)

    def test_fund_nav_empty_page_and_page_size_guard(self) -> None:
        payload = json.dumps(
            {"Data": None, "ErrCode": 0, "TotalCount": 0}
        ).encode()
        self.assertEqual(
            parse_eastmoney_fund_nav_json(
                payload, fund_code="006985", source_url="https://example.invalid/fund"
            ),
            [],
        )
        with self.assertRaises(ValueError):
            EastmoneyFundNavSource().fetch_history(
                "006985", start_date="2020-01-01", page_size=101
            )

    def test_fund_nav_ranges_are_split_by_year(self) -> None:
        self.assertEqual(
            annual_date_ranges("2020-12-30", "2022-01-02"),
            [
                ("2020-12-30", "2020-12-31"),
                ("2021-01-01", "2021-12-31"),
                ("2022-01-01", "2022-01-02"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
