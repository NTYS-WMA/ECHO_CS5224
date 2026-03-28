"""
Mock server simulating ai_generation_service endpoints.
Used for local testing of GenerationServiceLLM and GenerationServiceEmbedding.

Endpoints:
  POST /api/v1/templates              - template registration
  POST /api/v1/generation/execute     - LLM generation
  POST /api/v1/generation/embeddings  - text embedding
  GET  /health                        - health check
"""

import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

REGISTERED_TEMPLATES = {}


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[mock] {self.path} - {args[0]}")

    def _send_json(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "mock-ai-generation-service"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/api/v1/templates":
            tid = body.get("template_id")
            if tid in REGISTERED_TEMPLATES:
                self._send_json(409, {"error": "template already exists", "template_id": tid})
            else:
                REGISTERED_TEMPLATES[tid] = body
                self._send_json(201, {"template_id": tid, "message": "Template registered successfully."})

        elif path == "/api/v1/generation/execute":
            # Return a mock JSON response for memory/profile operations
            messages = body.get("messages", [])
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

            # Detect JSON mode from injected instruction
            is_json_mode = any(
                "valid JSON" in (m.get("content") or "") for m in messages
            )

            if is_json_mode:
                mock_content = json.dumps({"facts": ["mock fact from ai_generation_service"]})
            else:
                mock_content = f"Mock response to: {last_user[:80]}"

            self._send_json(200, {
                "response_id": "mock-gen-001",
                "template_id": body.get("template_id"),
                "output": [{"type": "text", "content": mock_content}],
                "model": "mock-claude",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            })

        elif path == "/api/v1/generation/tool-completion":
            messages = body.get("messages", [])
            tools = body.get("tools", [])
            # Simulate a tool call response using the first tool provided
            if tools:
                first_fn = tools[0].get("function", {})
                fn_name = first_fn.get("name", "unknown_tool")
                # Return a mock tool call
                self._send_json(200, {
                    "content": None,
                    "tool_calls": [
                        {
                            "name": fn_name,
                            "arguments": {"mock_param": "mock_value"},
                        }
                    ],
                })
            else:
                self._send_json(200, {"content": "No tools provided", "tool_calls": []})

        elif path == "/api/v1/generation/embeddings":
            # Return a random 1024-dim vector
            vector = [round(random.gauss(0, 0.1), 6) for _ in range(1024)]
            self._send_json(200, {
                "response_id": "mock-emb-001",
                "embedding": vector,
                "dimension": 1024,
                "model": "mock-titan",
                "usage": {"input_tokens": 5, "output_tokens": 0},
            })

        else:
            self._send_json(404, {"error": "not found"})


def run(port: int = 8003):
    server = HTTPServer(("127.0.0.1", port), MockHandler)
    print(f"[mock] ai_generation_service mock running on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
