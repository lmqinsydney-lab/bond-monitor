import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from server import create_server
from storage import database, set_state


class ServerTest(unittest.TestCase):
    def test_status_endpoint_is_local_and_returns_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with database(db_path) as conn:
                set_state(conn, "update_status", {"state": "ok", "inserted": 12})
            server = create_server(port=0, db_path=db_path)
            self.assertEqual(server.server_address[0], "127.0.0.1")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_port}/status", timeout=3
                ) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["state"], "ok")
                self.assertEqual(payload["inserted"], 12)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()

