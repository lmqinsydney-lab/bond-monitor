from __future__ import annotations

import argparse
import json
from pathlib import Path

from exporter import export_dashboard
from storage import database, get_state
from updater import run_update


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="本地债市与债券基金压力监测工具")
    parser.add_argument("--db", type=Path, help="覆盖 SQLite 数据库路径")
    sub = parser.add_subparsers(dest="command", required=True)

    update = sub.add_parser("update", help="抓取并补齐市场数据")
    update.add_argument("--from", dest="start_year", type=int, default=2020, help="起始年份")
    update.add_argument("--force", action="store_true", help="重新抓取已有历史年份")

    sub.add_parser("export", help="从数据库生成页面 JSON 和 CSV")
    sub.add_parser("status", help="输出最近更新状态")

    serve = sub.add_parser("serve", help="在 127.0.0.1 启动本地页面")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "update":
        result = run_update(
            db_path=args.db,
            start_year=args.start_year,
            force=args.force,
            on_progress=lambda label: print(f"更新：{label}", flush=True),
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status != "failed" else 1
    if args.command == "export":
        dashboard = export_dashboard(db_path=args.db)
        print(json.dumps(dashboard["meta"], ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        with database(args.db) as conn:
            print(json.dumps(get_state(conn, "update_status", {"state": "never"}), ensure_ascii=False, indent=2))
        return 0
    if args.command == "serve":
        from server import serve

        export_dashboard(db_path=args.db)
        serve(port=args.port, db_path=args.db)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

