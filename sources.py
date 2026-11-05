from __future__ import annotations

import csv
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Mapping
from xml.etree import ElementTree as ET


USER_AGENT = "BondMonitor/1.0 (+local personal research tool)"


class SourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Observation:
    metric: str
    observation_date: str
    tenor: float
    rating: str
    value: float
    unit: str
    source: str
    source_url: str
    source_tier: str
    fetched_at: str
    quality: str = "ok"

    def as_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FundNavObservation:
    fund_code: str
    nav_date: str
    unit_nav: float
    cumulative_nav: float | None
    daily_return_pct: float | None
    source: str
    source_url: str
    source_tier: str
    fetched_at: str
    quality: str = "ok"

    def as_record(self) -> dict[str, object]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch_bytes(
    url: str,
    *,
    method: str = "GET",
    timeout: int = 30,
    headers: Mapping[str, str] | None = None,
) -> bytes:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url,
        method=method,
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            if response.status != 200:
                raise SourceError(f"HTTP {response.status}: {url}")
            return payload
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SourceError(f"request failed: {url}: {exc}") from exc


def _cell_text(cell: ET.Element, namespace: str) -> str:
    inline = cell.find(f"{namespace}is/{namespace}t")
    if inline is not None and inline.text is not None:
        return inline.text.strip()
    value = cell.find(f"{namespace}v")
    return value.text.strip() if value is not None and value.text else ""


def parse_chinabond_xlsx(
    payload: bytes,
    *,
    metric: str,
    rating: str = "",
    tenors: Iterable[float] = (1.0, 3.0, 5.0, 10.0),
    source_url: str,
    fetched_at: str | None = None,
) -> list[Observation]:
    wanted = {round(float(value), 6) for value in tenors}
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            sheet = archive.open("xl/worksheets/sheet1.xml")
            tree = ET.parse(sheet)
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise SourceError(f"invalid ChinaBond xlsx: {exc}") from exc

    root = tree.getroot()
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rows = root.findall(f".//{namespace}row")
    if not rows:
        raise SourceError("ChinaBond xlsx contains no rows")

    header = [_cell_text(cell, namespace) for cell in rows[0].findall(f"{namespace}c")]
    expected = ["日期", "标准期限说明", "标准期限(年)", "收益率(%)"]
    if header[:4] != expected:
        raise SourceError(f"unexpected ChinaBond header: {header[:4]}")

    timestamp = fetched_at or utc_now()
    observations: list[Observation] = []
    for row in rows[1:]:
        cells = [_cell_text(cell, namespace) for cell in row.findall(f"{namespace}c")]
        if len(cells) < 4 or not cells[0] or not cells[2] or not cells[3]:
            continue
        try:
            tenor = round(float(cells[2]), 6)
            value = float(cells[3])
        except ValueError:
            continue
        if tenor not in wanted:
            continue
        if not 0 <= value <= 20:
            raise SourceError(f"yield out of range: {value}")
        date = cells[0].replace("/", "-")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise SourceError(f"invalid date: {date}")
        observations.append(
            Observation(
                metric=metric,
                observation_date=date,
                tenor=tenor,
                rating=rating,
                value=value,
                unit="percent",
                source="ChinaBond",
                source_url=source_url,
                source_tier="official",
                fetched_at=timestamp,
            )
        )
    if not observations:
        raise SourceError("ChinaBond xlsx produced no requested observations")
    return observations


class ChinaBondAnnualSource:
    BASE = "https://yield.chinabond.com.cn/cbweb-mn/yc/downYearBzqx"
    CURVES = {
        "cgb_yield": {
            "id": "2c9081e50a2f9606010a3068cae70001",
            "rating": "",
            "tenors": (1.0, 3.0, 5.0, 10.0),
        },
        "cdb_yield": {
            "id": "8a8b2ca037a7ca910137bfaa94fa5057",
            "rating": "",
            "tenors": (1.0, 3.0, 5.0, 10.0),
        },
        "bank_t2_yield": {
            "id": "8a8b2cee67a9cd3a0167ac48fc234850",
            "rating": "AAA-",
            "tenors": (1.0, 3.0, 5.0),
        },
        "mtm_aaa_yield": {
            "id": "2c9081880fa9d507010fb8505b393fe7",
            "rating": "AAA",
            "tenors": (1.0, 3.0, 5.0),
        },
    }

    def url_for(self, metric: str, year: int) -> str:
        if metric not in self.CURVES:
            raise KeyError(metric)
        curve_id = self.CURVES[metric]["id"]
        return (
            f"{self.BASE}?year={year}&wrjxCBFlag=0&zblx=txy"
            f"&ycDefId={curve_id}&locale=zh_CN"
        )

    def fetch_year(self, metric: str, year: int) -> list[Observation]:
        config = self.CURVES[metric]
        url = self.url_for(metric, year)
        return parse_chinabond_xlsx(
            fetch_bytes(url),
            metric=metric,
            rating=str(config["rating"]),
            tenors=config["tenors"],
            source_url=url,
        )


def parse_chinamoney_repo_json(payload: bytes, *, source_url: str) -> list[Observation]:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(f"invalid ChinaMoney repo json: {exc}") from exc
    timestamp = utc_now()
    observations: list[Observation] = []
    for record in data.get("records", []):
        code = str(record.get("productCode", ""))
        if code != "DR007":
            continue
        date_raw = str(record.get("date", ""))
        match = re.fullmatch(r"(\d{2})-(\d{2})-(\d{2})", date_raw)
        if not match:
            raise SourceError(f"invalid ChinaMoney date: {date_raw}")
        date = f"20{match.group(1)}-{match.group(2)}-{match.group(3)}"
        value = float(record["weightedRate"])
        observations.append(
            Observation(
                metric="dr007",
                observation_date=date,
                tenor=7 / 365,
                rating="",
                value=value,
                unit="percent",
                source="ChinaMoney",
                source_url=source_url,
                source_tier="official",
                fetched_at=timestamp,
            )
        )
    if not observations:
        raise SourceError("ChinaMoney repo json contains no DR007 weighted rate")
    return observations


def parse_chinamoney_repo_csv(payload: bytes, *, source_url: str) -> list[Observation]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceError(f"invalid ChinaMoney repo csv encoding: {exc}") from exc
    timestamp = utc_now()
    observations: list[Observation] = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 9 or not row[0] or not row[7]:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[0]):
            continue
        observations.append(
            Observation(
                metric="dr007",
                observation_date=row[0],
                tenor=7 / 365,
                rating="",
                value=float(row[7]),
                unit="percent",
                source="ChinaMoney",
                source_url=source_url,
                source_tier="official",
                fetched_at=timestamp,
            )
        )
    if not observations:
        raise SourceError("ChinaMoney repo csv contains no DR007 data")
    return observations


class ChinaMoneyRepoSource:
    LATEST_URL = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/prr-md.json"
    CHART_URL = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/prr-chrt.csv"

    def fetch_recent(self) -> list[Observation]:
        chart = parse_chinamoney_repo_csv(fetch_bytes(self.CHART_URL), source_url=self.CHART_URL)
        latest = parse_chinamoney_repo_json(fetch_bytes(self.LATEST_URL), source_url=self.LATEST_URL)
        by_date = {obs.observation_date: obs for obs in chart}
        by_date.update({obs.observation_date: obs for obs in latest})
        return [by_date[date] for date in sorted(by_date)]


def parse_eastmoney_fund_nav_json(
    payload: bytes,
    *,
    fund_code: str,
    source_url: str,
    fetched_at: str | None = None,
) -> list[FundNavObservation]:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(f"invalid Eastmoney fund NAV json: {exc}") from exc
    if data.get("ErrCode") == 0 and data.get("Data") is None and data.get("TotalCount") == 0:
        return []
    if data.get("ErrCode") != 0 or not isinstance(data.get("Data"), dict):
        raise SourceError(f"Eastmoney fund NAV error: {data.get('ErrMsg') or data.get('ErrCode')}")
    rows = data["Data"].get("LSJZList")
    if not isinstance(rows, list):
        raise SourceError("Eastmoney fund NAV response has no LSJZList")
    timestamp = fetched_at or utc_now()
    observations: list[FundNavObservation] = []
    for row in rows:
        date_value = str(row.get("FSRQ", ""))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
            raise SourceError(f"invalid fund NAV date: {date_value}")
        try:
            unit_nav = float(row["DWJZ"])
            cumulative_raw = str(row.get("LJJZ", "")).strip()
            return_raw = str(row.get("JZZZL", "")).strip()
            cumulative_nav = float(cumulative_raw) if cumulative_raw else None
            daily_return = float(return_raw) if return_raw else None
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceError(f"invalid fund NAV values on {date_value}") from exc
        if not 0 < unit_nav < 100:
            raise SourceError(f"unit NAV out of range: {unit_nav}")
        if cumulative_nav is not None and not 0 < cumulative_nav < 1000:
            raise SourceError(f"cumulative NAV out of range: {cumulative_nav}")
        if daily_return is not None and not -50 < daily_return < 50:
            raise SourceError(f"daily return out of range: {daily_return}")
        observations.append(
            FundNavObservation(
                fund_code=fund_code,
                nav_date=date_value,
                unit_nav=unit_nav,
                cumulative_nav=cumulative_nav,
                daily_return_pct=daily_return,
                source="Eastmoney",
                source_url=source_url,
                source_tier="fallback",
                fetched_at=timestamp,
            )
        )
    return observations


class EastmoneyFundNavSource:
    BASE = "https://api.fund.eastmoney.com/f10/lsjz"
    SUPPORTED_FUNDS = {"006985", "007744", "012591"}

    def url_for(
        self,
        fund_code: str,
        *,
        page_index: int,
        page_size: int,
        start_date: str,
        end_date: str = "",
    ) -> str:
        if fund_code not in self.SUPPORTED_FUNDS:
            raise KeyError(fund_code)
        query = urllib.parse.urlencode(
            {
                "fundCode": fund_code,
                "pageIndex": page_index,
                "pageSize": page_size,
                "startDate": start_date,
                "endDate": end_date,
            }
        )
        return f"{self.BASE}?{query}"

    def fetch_history(
        self,
        fund_code: str,
        *,
        start_date: str,
        end_date: str = "",
        page_size: int = 100,
    ) -> list[FundNavObservation]:
        if not 1 <= page_size <= 100:
            raise ValueError("Eastmoney page_size must be between 1 and 100")
        effective_end_date = end_date or datetime.now(timezone.utc).date().isoformat()
        observations: list[FundNavObservation] = []
        for range_start, range_end in annual_date_ranges(start_date, effective_end_date):
            page = 1
            while True:
                url = self.url_for(
                    fund_code,
                    page_index=page,
                    page_size=page_size,
                    start_date=range_start,
                    end_date=range_end,
                )
                payload = fetch_bytes(
                    url,
                    headers={"Referer": "https://fundf10.eastmoney.com/"},
                )
                parsed = parse_eastmoney_fund_nav_json(
                    payload,
                    fund_code=fund_code,
                    source_url=url,
                )
                try:
                    metadata = json.loads(payload.decode("utf-8"))
                    total = int(metadata.get("TotalCount", 0))
                    returned_page = int(metadata.get("PageIndex", page) or page)
                    returned_page_size = int(
                        metadata.get("PageSize", len(parsed)) or len(parsed) or page_size
                    )
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                    raise SourceError("invalid Eastmoney pagination metadata") from exc
                observations.extend(parsed)
                if not parsed or returned_page * returned_page_size >= total:
                    break
                page += 1
                if page > 100:
                    raise SourceError("Eastmoney annual pagination exceeded safety limit")
        by_date = {item.nav_date: item for item in observations}
        return [by_date[date_value] for date_value in sorted(by_date)]


def annual_date_ranges(start_date: str, end_date: str) -> list[tuple[str, str]]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("fund NAV start_date must not exceed end_date")
    ranges: list[tuple[str, str]] = []
    cursor = start
    while cursor <= end:
        year_end = min(end, date(cursor.year, 12, 31))
        ranges.append((cursor.isoformat(), year_end.isoformat()))
        cursor = year_end + timedelta(days=1)
    return ranges
