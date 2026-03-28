"""
Tests for GenerationServiceLLM and GenerationServiceEmbedding.
Spins up the mock server in a background thread.

Run:
    cd memory_service
    source .venv/bin/activate
    python -m pytest test/test_generation_service.py -v
  or directly:
    python test/test_generation_service.py
"""

import sys
import threading
import time
import unittest
from pathlib import Path

# Make mem0 importable
sys.path.insert(0, str(Path(__file__).parent.parent))

sys.path.insert(0, str(Path(__file__).parent))
from mock_ai_service import run as run_mock

MOCK_PORT = 18099
MOCK_URL = f"http://127.0.0.1:{MOCK_PORT}"
_mock_started = False


def start_mock_server():
    global _mock_started
    if _mock_started:
        return
    _mock_started = True
    t = threading.Thread(target=run_mock, args=(MOCK_PORT,), daemon=True)
    t.start()
    time.sleep(0.3)  # let it bind


# Start once at import time
start_mock_server()


class TestGenerationServiceLLM(unittest.TestCase):

    def _make_llm(self):
        from mem0.llms.generation_service import GenerationServiceLLM
        return GenerationServiceLLM({
            "service_url": MOCK_URL,
            "temperature": 0.2,
            "max_tokens": 100,
        })

    def test_template_registered_on_init(self):
        """Service marks itself available after successful template registration."""
        llm = self._make_llm()
        self.assertTrue(llm.available, "LLM should be available after successful template registration")

    def test_generate_response_plain(self):
        """Plain generate_response returns a string."""
        llm = self._make_llm()
        result = llm.generate_response(
            messages=[{"role": "user", "content": "Hello"}]
        )
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_generate_response_json_mode(self):
        """JSON mode injects instruction and response contains JSON."""
        llm = self._make_llm()
        result = llm.generate_response(
            messages=[{"role": "user", "content": "Extract facts"}],
            response_format={"type": "json_object"},
        )
        import json
        parsed = json.loads(result)
        self.assertIn("facts", parsed)

    def test_json_instruction_injected_into_system(self):
        """_inject_json_instruction modifies system message correctly."""
        from mem0.llms.generation_service import GenerationServiceLLM
        llm = GenerationServiceLLM.__new__(GenerationServiceLLM)
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ]
        result = llm._inject_json_instruction(msgs)
        self.assertIn("valid JSON", result[0]["content"])
        self.assertEqual(result[0]["content"], "You are helpful.\nRespond with valid JSON only.")

    def test_json_instruction_no_system_message(self):
        """_inject_json_instruction prepends system message when absent."""
        from mem0.llms.generation_service import GenerationServiceLLM
        llm = GenerationServiceLLM.__new__(GenerationServiceLLM)
        msgs = [{"role": "user", "content": "Hi"}]
        result = llm._inject_json_instruction(msgs)
        self.assertEqual(result[0]["role"], "system")
        self.assertIn("valid JSON", result[0]["content"])

    def test_tools_routes_to_tool_completion(self):
        """Passing tools= routes to /tool-completion and returns tool_calls."""
        llm = self._make_llm()
        tools = [{"type": "function", "function": {"name": "some_tool", "parameters": {}}}]
        result = llm.generate_response(
            messages=[{"role": "user", "content": "Hi"}],
            tools=tools,
        )
        self.assertIn("tool_calls", result)
        self.assertIsInstance(result["tool_calls"], list)
        self.assertEqual(result["tool_calls"][0]["name"], "some_tool")

    def test_unavailable_with_no_fallback(self):
        """Unavailable service with no fallback raises RuntimeError."""
        from mem0.llms.generation_service import GenerationServiceLLM
        llm = GenerationServiceLLM.__new__(GenerationServiceLLM)
        llm.available = False
        llm._fallback = None
        with self.assertRaises(RuntimeError):
            llm.generate_response(messages=[{"role": "user", "content": "Hi"}])

    def test_double_registration_is_idempotent(self):
        """Registering twice (409) still marks service as available."""
        llm1 = self._make_llm()
        llm2 = self._make_llm()  # will get 409, should still be available
        self.assertTrue(llm1.available)
        self.assertTrue(llm2.available)


class TestGenerationServiceEmbedding(unittest.TestCase):

    def _make_embedder(self):
        from mem0.embeddings.generation_service import GenerationServiceEmbedding
        return GenerationServiceEmbedding({
            "service_url": MOCK_URL,
            "embedding_dims": 1024,
        })

    def test_embed_returns_vector(self):
        """embed() returns a list of 1024 floats."""
        embedder = self._make_embedder()
        vector = embedder.embed("Hello world")
        self.assertIsInstance(vector, list)
        self.assertEqual(len(vector), 1024)
        self.assertIsInstance(vector[0], float)

    def test_embed_memory_action_ignored(self):
        """memory_action parameter is accepted without error."""
        embedder = self._make_embedder()
        vector = embedder.embed("test text", memory_action="add")
        self.assertEqual(len(vector), 1024)

    def test_embed_different_texts_differ(self):
        """Two different texts produce different vectors (mock uses random)."""
        embedder = self._make_embedder()
        v1 = embedder.embed("hello")
        v2 = embedder.embed("world")
        self.assertNotEqual(v1, v2)


class TestFactoryRegistration(unittest.TestCase):

    def test_llm_factory_knows_generation_service(self):
        """LlmFactory has generation_service registered."""
        from mem0.utils.factory import LlmFactory
        self.assertIn("generation_service", LlmFactory.provider_to_class)

    def test_embedder_factory_knows_generation_service(self):
        """EmbedderFactory has generation_service registered."""
        from mem0.utils.factory import EmbedderFactory
        self.assertIn("generation_service", EmbedderFactory.provider_to_class)

    def test_llm_factory_creates_instance(self):
        """LlmFactory.create() returns a GenerationServiceLLM instance."""
        from mem0.llms.generation_service import GenerationServiceLLM
        from mem0.utils.factory import LlmFactory
        llm = LlmFactory.create("generation_service", {
            "service_url": MOCK_URL,
            "temperature": 0.2,
            "max_tokens": 100,
        })
        self.assertIsInstance(llm, GenerationServiceLLM)


if __name__ == "__main__":
    unittest.main(verbosity=2)
