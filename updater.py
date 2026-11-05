from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from exporter import export_dashboard
from sources import (
    ChinaBondAnnualSource,
    ChinaMoneyRepoSource,
    EastmoneyFundNavSource,
    SourceError,
    utc_now,
)
from storage import (
    database,
    latest_fund_nav_date,
    observation_count,
    record_fetch,
    set_state,
    upsert_fund_nav_observations,
    upsert_observations,
)


@dataclass
class UpdateResult:
    status: str
    inserted: int
    unchanged: int
    revised: int
    sources_ok: int
    sources_failed: int
    errors: list[str]
    fund_nav_latest_dates: dict[str, str | None]
    started_at: str
    finished_at: str

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def run_update(
    *,
    db_path: Path | str | None = None,
    start_year: int = 2020,
    force: bool = False,
    chinabond: ChinaBondAnnualSource | None = None,
    repo: ChinaMoneyRepoSource | None = None,
    fund_nav: EastmoneyFundNavSource | None = None,
    current_year: int | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> UpdateResult:
    started = utc_now()
    year_now = current_year or date.today().year
    if start_year < 2000 or start_year > year_now:
        raise ValueError("start_year is outside the supported range")
    chinabond_source = chinabond or ChinaBondAnnualSource()
    repo_source = repo or ChinaMoneyRepoSource()
    fund_nav_source = fund_nav or EastmoneyFundNavSource()
    totals = [0, 0, 0]
    ok = failed = 0
    errors: list[str] = []
    fund_nav_latest_dates: dict[str, str | None] = {}

    with database(db_path) as conn:
        set_state(conn, "update_status", {"state": "running", "started_at": started})
        for metric in chinabond_source.CURVES:
            for year in range(start_year, year_now + 1):
                if not force and year < year_now and observation_count(
                    conn, metric, year=year, source="ChinaBond"
                ) >= 100:
                    continue
                url = chinabond_source.url_for(metric, year)
                fetch_started = utc_now()
                label = f"{metric} {year}"
                if on_progress:
                    on_progress(label)
                try:
                    observations = chinabond_source.fetch_year(metric, year)
                    counts = upsert_observations(
                        conn, [item.as_record() for item in observations]
                    )
                    totals = [a + b for a, b in zip(totals, counts)]
                    ok += 1
                    record_fetch(
                        conn,
                        source="ChinaBond",
                        started_at=fetch_started,
                        finished_at=utc_now(),
                        status="ok",
                        request_url=url,
                        records=len(observations),
                    )
                except (SourceError, KeyError, ValueError) as exc:
                    failed += 1
                    message = f"{label}: {exc}"
                    errors.append(message)
                    record_fetch(
                        conn,
                        source="ChinaBond",
                        started_at=fetch_started,
                        finished_at=utc_now(),
                        status="failed",
                        request_url=url,
                        records=0,
                        error_summary=str(exc),
                    )

        repo_started = utc_now()
        if on_progress:
            on_progress("dr007 recent")
        try:
            observations = repo_source.fetch_recent()
            counts = upsert_observations(conn, [item.as_record() for item in observations])
            totals = [a + b for a, b in zip(totals, counts)]
            ok += 1
            record_fetch(
                conn,
                source="ChinaMoney",
                started_at=repo_started,
                finished_at=utc_now(),
                status="ok",
                request_url=repo_source.CHART_URL,
                records=len(observations),
            )
        except (SourceError, ValueError) as exc:
            failed += 1
            errors.append(f"dr007: {exc}")
            record_fetch(
                conn,
                source="ChinaMoney",
                started_at=repo_started,
                finished_at=utc_now(),
                status="failed",
                request_url=repo_source.CHART_URL,
                records=0,
                error_summary=str(exc),
            )

        fund_start_dates = {
            "006985": f"{start_year:04d}-01-01",
            "007744": f"{start_year:04d}-01-01",
            "012591": max(f"{start_year:04d}-01-01", "2021-07-08"),
        }
        for fund_code, baseline in fund_start_dates.items():
            nav_started = utc_now()
            latest = latest_fund_nav_date(conn, fund_code)
            start_date = baseline
            if latest and not force:
                lookback = (date.fromisoformat(latest) - timedelta(days=14)).isoformat()
                start_date = max(baseline, lookback)
            label = f"fund_nav {fund_code}"
            if on_progress:
                on_progress(label)
            try:
                nav_observations = fund_nav_source.fetch_history(
                    fund_code,
                    start_date=start_date,
                )
                counts = upsert_fund_nav_observations(
                    conn, [item.as_record() for item in nav_observations]
                )
                totals = [a + b for a, b in zip(totals, counts)]
                ok += 1
                fund_nav_latest_dates[fund_code] = latest_fund_nav_date(conn, fund_code)
                record_fetch(
                    conn,
                    source="Eastmoney",
                    started_at=nav_started,
                    finished_at=utc_now(),
                    status="ok",
                    request_url=fund_nav_source.BASE,
                    records=len(nav_observations),
                )
            except (SourceError, KeyError, ValueError) as exc:
                failed += 1
                errors.append(f"{label}: {exc}")
                fund_nav_latest_dates[fund_code] = latest
                record_fetch(
                    conn,
                    source="Eastmoney",
                    started_at=nav_started,
                    finished_at=utc_now(),
                    status="failed",
                    request_url=fund_nav_source.BASE,
                    records=0,
                    error_summary=str(exc),
                )

        finished = utc_now()
        status = "ok" if failed == 0 else ("partial" if ok else "failed")
        result = UpdateResult(
            status=status,
            inserted=totals[0],
            unchanged=totals[1],
            revised=totals[2],
            sources_ok=ok,
            sources_failed=failed,
            errors=errors,
            fund_nav_latest_dates=fund_nav_latest_dates,
            started_at=started,
            finished_at=finished,
        )
        set_state(conn, "update_status", {"state": status, **result.as_dict()})

    export_dashboard(db_path=db_path)
    return result
