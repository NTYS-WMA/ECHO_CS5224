import logging
from typing import Dict, List, Optional, Union

import requests

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase

logger = logging.getLogger(__name__)

PASSTHROUGH_TEMPLATE_ID = "tpl_memory_passthrough"
PASSTHROUGH_TEMPLATE = {
    "template_id": PASSTHROUGH_TEMPLATE_ID,
    "name": "Memory Service Passthrough",
    "owner": "memory-service",
    "category": "utility",
    "system_prompt": "",
    "user_prompt_template": "{{user_prompt}}",
    "variables": {
        "user_prompt": {
            "type": "string",
            "required": True,
            "description": "Passthrough prompt content",
        }
    },
    "defaults": {"temperature": 0.2, "max_tokens": 2000},
    "tags": ["memory", "passthrough"],
}


class GenerationServiceLLM(LLMBase):
    """
    LLM provider that routes calls through ai_generation_service.

    Falls back to direct DeepSeek if the service is unavailable at startup.
    """

    def __init__(self, config: Optional[Union[BaseLlmConfig, Dict]] = None):
        if isinstance(config, dict):
            known_keys = set(BaseLlmConfig().__dict__.keys())
            cfg = BaseLlmConfig(**{k: v for k, v in config.items() if k in known_keys})
        elif config is None:
            cfg = BaseLlmConfig()
        else:
            cfg = config

        super().__init__(cfg)

        # Pull generation_service-specific keys from the raw dict
        raw = config if isinstance(config, dict) else {}
        self._service_url = raw.get("service_url", "http://localhost:8003").rstrip("/")
        self._temperature = raw.get("temperature", 0.2)
        self._max_tokens = raw.get("max_tokens", 2000)

        # Fallback DeepSeek client (used when service unavailable)
        self._fallback = self._build_fallback(raw)

        # Try to register passthrough template; set availability flag
        self.available = self._register_template()
        if not self.available:
            logger.error(
                "GenerationServiceLLM: template registration failed. "
                "All LLM calls will fall back to direct DeepSeek."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_fallback(self, raw: dict):
        """Build a DeepSeekLLM fallback instance from config keys."""
        try:
            from mem0.llms.deepseek import DeepSeekLLM
            fallback_cfg = {
                k: raw[k]
                for k in ("api_key", "model", "deepseek_base_url", "temperature", "max_tokens")
                if k in raw and raw[k] is not None
            }
            return DeepSeekLLM(fallback_cfg) if fallback_cfg.get("api_key") else None
        except Exception as e:
            logger.warning(f"GenerationServiceLLM: could not build DeepSeek fallback: {e}")
            return None

    def _register_template(self) -> bool:
        """Register passthrough template with ai_generation_service. Returns True on success."""
        url = f"{self._service_url}/api/v1/templates"
        try:
            resp = requests.post(url, json=PASSTHROUGH_TEMPLATE, timeout=10)
            if resp.status_code in (200, 201):
                logger.info(f"GenerationServiceLLM: passthrough template registered ({resp.status_code})")
                return True
            if resp.status_code == 409:
                logger.info("GenerationServiceLLM: passthrough template already exists, reusing.")
                return True
            logger.error(
                f"GenerationServiceLLM: template registration failed "
                f"(status={resp.status_code}, body={resp.text[:200]})"
            )
            return False
        except Exception as e:
            logger.error(f"GenerationServiceLLM: template registration error: {e}")
            return False

    def _inject_json_instruction(self, messages: List[Dict]) -> List[Dict]:
        """Append JSON-mode instruction to the system message (or prepend a new one)."""
        messages = [m.copy() for m in messages]
        json_instruction = "\nRespond with valid JSON only."
        for msg in messages:
            if msg.get("role") == "system":
                msg["content"] = (msg["content"] or "") + json_instruction
                return messages
        # No system message found – prepend one
        messages.insert(0, {"role": "system", "content": json_instruction.strip()})
        return messages

    # ------------------------------------------------------------------
    # LLMBase interface
    # ------------------------------------------------------------------

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ):
        """
        Generate a response by calling ai_generation_service.

        Falls back to direct DeepSeek if service is marked unavailable.
        """
        if tools is not None:
            raise NotImplementedError(
                "GenerationServiceLLM does not support tool/function calling. "
                "Disable graph_store or use a direct LLM provider."
            )

        if not self.available:
            if self._fallback:
                logger.warning("GenerationServiceLLM: using DeepSeek fallback (service unavailable).")
                return self._fallback.generate_response(
                    messages=messages, response_format=response_format, **kwargs
                )
            raise RuntimeError(
                "GenerationServiceLLM: service unavailable and no fallback configured."
            )

        # Inject JSON instruction when caller requests JSON mode
        if response_format and response_format.get("type") == "json_object":
            messages = self._inject_json_instruction(messages)

        payload = {
            "user_id": "memory-service",
            "template_id": PASSTHROUGH_TEMPLATE_ID,
            "messages": messages,
            "generation_config": {
                "temperature": self._temperature,
                "max_tokens": self._max_tokens,
            },
        }

        try:
            resp = requests.post(
                f"{self._service_url}/api/v1/generation/execute",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["output"][0]["content"]
        except Exception as e:
            logger.error(f"GenerationServiceLLM: request failed ({e}), falling back to DeepSeek.")
            if self._fallback:
                return self._fallback.generate_response(
                    messages=messages, response_format=response_format, **kwargs
                )
            raise
