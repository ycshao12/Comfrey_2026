import hashlib
import json
import math
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List


HOST = "127.0.0.1"
PORT = 8765
EMBEDDING_DIM = 128


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _deterministic_embedding(text: str) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    for index in range(EMBEDDING_DIM):
        byte = digest[index % len(digest)]
        centered = (byte - 127.5) / 127.5
        values.append(centered)

    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [round(value / norm, 8) for value in values]


def _chat_reply(payload: Dict[str, Any]) -> str:
    messages = payload.get("messages", [])
    user_content = ""
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, str):
                    user_content = content.strip()
                    break

    lowered = user_content.lower()
    if "say ok" in lowered or "return only the word ok" in lowered:
        return "ok"

    if "\n\n" in user_content:
        return user_content.rsplit("\n\n", 1)[-1].strip() or user_content
    return user_content or "ok"


class MockYunqiaoHandler(BaseHTTPRequestHandler):
    server_version = "MockYunqiao/1.0"

    def do_GET(self) -> None:
        if self.path == "/health":
            _json_response(self, 200, {"status": "ok"})
            return
        _json_response(self, 404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            _json_response(self, 400, {"error": {"message": "invalid json"}})
            return

        if self.path == "/v1/embeddings":
            input_value = payload.get("input", "")
            texts = input_value if isinstance(input_value, list) else [str(input_value)]
            data = [
                {
                    "object": "embedding",
                    "index": index,
                    "embedding": _deterministic_embedding(str(text)),
                }
                for index, text in enumerate(texts)
            ]
            _json_response(
                self,
                200,
                {
                    "object": "list",
                    "model": payload.get("model", "text-embedding-ada-002"),
                    "data": data,
                    "usage": {"prompt_tokens": 0, "total_tokens": 0},
                },
            )
            return

        if self.path == "/v1/chat/completions":
            _json_response(
                self,
                200,
                {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": payload.get("model", "gpt-4.1-mini"),
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": _chat_reply(payload),
                            },
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                },
            )
            return

        _json_response(self, 404, {"error": {"message": "not found"}})

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MockYunqiaoHandler)
    print(f"Mock Yunqiao server listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
