"""
Perplexity Sonar — Strands Model Integration

Implements the Strands `Model` interface so Perplexity can be used directly
as an agent's model (Agent(model=PerplexitySonar(...))).

Usage:
    from agentic_email_campaign.models import PerplexitySonar

    research_agent = Agent(model=PerplexitySonar("sonar"), ...)
    verifier_agent = Agent(model=PerplexitySonar("sonar"), ...)
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests
from strands.models import Model

PPLX_URL: str = "https://api.perplexity.ai/chat/completions"


class PerplexitySonar(Model):
    """
    Wraps the Perplexity Sonar API as a Strands-compatible Model.

    Args:
        model:       Perplexity model ID (default: "sonar").
                     - "sonar" — fast and effective for all research tasks.
        temperature: Sampling temperature (default: 0.2 for factual research).
    """

    def __init__(self, model: str = "sonar", temperature: float = 0.2) -> None:
        self.model       = model
        self.temperature = temperature

    # ── Required Model interface ─────────────────────────────────────────────

    def get_config(self) -> Any:
        return {"model": self.model, "temperature": self.temperature}

    def update_config(self, **kwargs) -> None:
        if "model" in kwargs:
            self.model = kwargs["model"]
        if "temperature" in kwargs:
            self.temperature = kwargs["temperature"]

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        yield {}

    # ── Streaming generator (required by Strands ≥ 1.26) ────────────────────

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tool_specs: Optional[Any] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Convert Strands messages to OpenAI-compatible format, call Perplexity,
        then yield the mandatory Strands streaming event sequence.
        """
        # Read key lazily so load_dotenv() has already run
        api_key = os.environ.get("PPLX_API_KEY", "")
        if not api_key:
            raise ValueError("PPLX_API_KEY is not set in environment variables.")

        openai_messages: List[Dict[str, str]] = []

        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

        for m in messages:
            content = getattr(m, "content", "") if not isinstance(m, dict) else m.get("content", "")
            role    = getattr(m, "role",    "user") if not isinstance(m, dict) else m.get("role", "user")
            text    = self._to_text(content)
            openai_messages.append({
                "role":    "user" if role == "user" else "assistant",
                "content": text,
            })

        response = requests.post(
            PPLX_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       self.model,
                "messages":    openai_messages,
                "temperature": self.temperature,
                "stream":      False,
            },
            timeout=90,
        )
        response.raise_for_status()
        final_text: str = response.json()["choices"][0]["message"]["content"]

        # Yield mandatory Strands streaming event sequence
        yield {"messageStart":      {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {"text": ""}}}
        yield {"contentBlockDelta": {"delta": {"text": final_text}}}
        yield {"contentBlockStop":  {}}
        yield {"messageStop":       {"stopReason": "end_turn", "additionalModelResponseFields": None}}

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")
            return str(content)
        return str(content)
