
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class MockApiHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlsplit(self.path).path

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
        else:
            self._respond(404, {"error": "Not found"})

    def _respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), MockApiHandler)
    print("Mock API listening on http://127.0.0.1:8765", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping mock API.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
