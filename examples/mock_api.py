import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class MockApiHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/status/200":
            self._respond(200, {"status": "ok"})
        elif path == "/status/503":
            self._respond(503, {"error": "Service unavailable"})
        elif path == "/json":
            self._respond(
                200,
                {
                    "slideshow": {
                        "author": "Yours Truly",
                        "title": "Sample Slide Show",
                        "slides": 2,
                    }
                },
            )
        elif path == "/users":
            self._respond(
                200,
                {
                    "users": [
                        {
                            "id": 7,
                            "email": "ada@example.com",
                            "profile": {"display_name": "Ada"},
                        }
                    ]
                },
            )
        elif path == "/users/invalid-email":
            self._respond(
                200,
                {"users": [{"id": 7, "email": "not-an-email"}]},
            )
        elif path == "/security/sql-error":
            self._respond(
                500,
                {
                    "error": (
                        "Database error: You have an error in your SQL syntax; "
                        "check the manual for your MySQL server version"
                    )
                },
            )
        elif path == "/security/reflect":
            marker = params.get("marker", [""])[0]
            body = f"<html><body>Search result: {marker}</body></html>"
            self._respond(200, body, content_type="text/html")
        elif path == "/security/reflect-escaped":
            marker = params.get("marker", [""])[0]
            escaped = (
                marker.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;")
            )
            body = f"<html><body>Search result: {escaped}</body></html>"
            self._respond(200, body, content_type="text/html")
        else:
            self._respond(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/users":
            self._respond(404, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length))
        except (ValueError, UnicodeDecodeError):
            self._respond(
                400,
                {"error": {"code": "invalid_json", "field": "body"}},
            )
            return

        if not isinstance(payload, dict):
            self._respond(
                400,
                {"error": {"code": "object_required", "field": "body"}},
            )
            return

        for field in ("name", "role"):
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                self._respond(
                    400,
                    {"error": {"code": f"invalid_{field}", "field": field}},
                )
                return

        if "nickname" in payload:
            nickname = payload["nickname"]
            if not isinstance(nickname, str) or not nickname.strip():
                self._respond(
                    400,
                    {"error": {"code": "invalid_nickname", "field": "nickname"}},
                )
                return

        user = {"id": 1, "name": payload["name"], "role": payload["role"]}
        if "nickname" in payload:
            user["nickname"] = payload["nickname"]
        self._respond(201, {"user": user})

    def _respond(
        self,
        status: int,
        payload: dict | str,
        content_type: str = "application/json",
    ) -> None:
        if isinstance(payload, str):
            body = payload.encode("utf-8")
        else:
            body = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    port = int(os.environ.get("API_SENTINEL_MOCK_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), MockApiHandler)
    bound_port = server.server_address[1]
    print(f"Mock API listening on http://127.0.0.1:{bound_port}", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping mock API.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
