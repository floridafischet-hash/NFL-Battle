"""Tiny stand-in for the OpenAI Responses API, used only by the end-to-end test (scripts/e2e.sh).

The test tells the mock the "real" scores (POST /__mock/results {"BUF": [27, 17], ...}, keyed by the
home team's abbreviation). /v1/responses then answers like ChatGPT with web search would: a
web_search_call with the visited sources and a JSON message following the requested schema.
Standard library only.
"""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RESULTS: dict[str, list[int]] = {}
CALLS = {"responses": 0}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def _authorized(self) -> bool:
        return self.headers.get("Authorization", "").startswith("Bearer ") and len(self.headers["Authorization"]) > 12

    def do_GET(self) -> None:
        if self.path == "/__mock/calls":
            return self._send(200, CALLS)
        if self.path.startswith("/v1/models/"):
            if not self._authorized():
                return self._send(401, {"error": {"message": "missing key"}})
            return self._send(200, {"id": self.path.rsplit("/", 1)[-1], "object": "model"})
        self._send(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:
        if self.path == "/__mock/results":
            RESULTS.update(self._body())
            return self._send(200, {"results": RESULTS})
        if self.path != "/v1/responses":
            return self._send(404, {"error": {"message": "not found"}})
        if not self._authorized():
            return self._send(401, {"error": {"message": "missing key"}})
        CALLS["responses"] += 1
        request = self._body()
        home = re.search(r"Home team: .* \((\w+)\)", request["input"]).group(1)
        away = re.search(r"Away team: .* \((\w+)\)", request["input"]).group(1)
        score = RESULTS.get(home)
        slug = f"{home}-{away}".lower()
        sources = [
            ("ESPN", f"https://www.espn.com/nfl/game/_/name/{slug}"),
            ("NFL.com", f"https://www.nfl.com/games/{slug}"),
        ]
        if score:
            answer = {
                "status": "FINAL",
                "home_team": home,
                "away_team": away,
                "home_score": score[0],
                "away_score": score[1],
                "winner": home if score[0] > score[1] else away,
                "sources": [{"name": n, "url": u, "home_score": score[0], "away_score": score[1]} for n, u in sources],
                "note": "",
            }
        else:
            answer = {
                "status": "NOT_FINISHED",
                "home_team": home,
                "away_team": away,
                "home_score": None,
                "away_score": None,
                "winner": None,
                "sources": [],
                "note": "Spiel noch nicht beendet",
            }
        output = [
            {
                "type": "web_search_call",
                "id": "ws_mock",
                "status": "completed",
                "action": {"type": "search", "query": slug, "sources": [{"type": "url", "url": u} for _, u in sources]},
            },
            {
                "type": "message",
                "id": "msg_mock",
                "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(answer), "annotations": []}],
            },
        ]
        self._send(200, {"status": "completed", "output": output, "usage": {"input_tokens": 1, "output_tokens": 1}})

    def log_message(self, *args) -> None:  # keep the test output quiet
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()  # noqa: S104 - only inside the e2e network
