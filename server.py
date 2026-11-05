from __future__ import annotations

import json
import threading
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from exporter import export_dashboard
from storage import database, get_state, set_state
from updater import run_update


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "web"


class BondMonitorHandler(SimpleHTTPRequestHandler):
    db_path: Path | str | None = None
    refresh_lock = threading.Lock()

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory or str(WEB_ROOT), **kwargs)

    def _json(self, payload: object, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/status":
            with database(self.db_path) as conn:
                state = get_state(conn, "update_status", {"state": "never"})
            self._json(state)
            return
        if self.path.split("?", 1)[0] == "/download/market-history.csv":
            self.path = "/data/market-history.csv"
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/refresh":
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        if not self.refresh_lock.acquire(blocking=False):
            self._json({"state": "running", "message": "更新已在进行中"}, HTTPStatus.CONFLICT)
            return

        def refresh() -> None:
            try:
                run_update(db_path=self.db_path, start_year=2020)
            except Exception as exc:  # 保证 UI 能读取到失败状态，异常不泄漏到请求线程。
                with database(self.db_path) as conn:
                    set_state(conn, "update_status", {"state": "failed", "errors": [str(exc)]})
            finally:
                self.refresh_lock.release()

        threading.Thread(target=refresh, name="bond-monitor-refresh", daemon=True).start()
        self._json({"state": "running", "message": "已开始更新"}, HTTPStatus.ACCEPTED)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(f"[web] {self.address_string()} {format % args}")


def create_server(*, port: int = 8765, db_path: Path | str | None = None) -> ThreadingHTTPServer:
    handler = type("ConfiguredBondMonitorHandler", (BondMonitorHandler,), {"db_path": db_path})
    return ThreadingHTTPServer(("127.0.0.1", port), partial(handler, directory=str(WEB_ROOT)))


def serve(*, port: int = 8765, db_path: Path | str | None = None) -> None:
    export_dashboard(db_path=db_path)
    server = create_server(port=port, db_path=db_path)
    print(f"债市监测已启动：http://127.0.0.1:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止…")
    finally:
        server.server_close()

