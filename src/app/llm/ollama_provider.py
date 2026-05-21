"""LLMProvider backed by a local Ollama daemon.

POSTs to ``{base_url}/api/generate`` with ``format=json`` and the locked
prompt. Validates the returned CatID is in the candidate list, retries
once on hallucinations with a corrective note, and falls back to CLAP
top-1 if the second attempt is still invalid.

Mirrors the call pattern proven in ``dev/ollama_tests/ollama_client.py``
and ``dev/ollama_tests/run_comparison.py:_call``.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from app.llm.prompt_renderer import PromptConfig, load_prompt, render_prompt
from app.llm.provider import PickResult
from app.models import ClassificationMatch

logger = logging.getLogger(__name__)


class OllamaProvider:
    """HTTP-based provider hitting a local Ollama daemon."""

    def __init__(self, model: str, base_url: str, timeout: float = 300.0) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._prompt: PromptConfig | None = None

    @property
    def model_version(self) -> str:
        return f"ollama:{self._model}"

    def is_reachable(self) -> bool:
        """Return True if the Ollama daemon responds to /api/tags."""
        try:
            with urllib.request.urlopen(
                f"{self._base_url}/api/tags", timeout=3.0
            ) as resp:
                return resp.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def pick(
        self,
        *,
        filename: str,
        metadata: dict[str, str],
        candidates: list[ClassificationMatch],
    ) -> PickResult:
        if not candidates:
            raise ValueError("pick() requires at least one candidate")
        if self._prompt is None:
            self._prompt = load_prompt()

        valid_cat_ids = [c.cat_id for c in candidates]
        system, user = render_prompt(
            self._prompt,
            filename=filename,
            metadata=metadata,
            candidates=candidates,
        )

        t0 = time.monotonic()
        choice, ok = self._one_call(system, user)
        retried = False
        fallback = False

        if ok and choice not in valid_cat_ids:
            retried = True
            retry_user = (
                user
                + f"\n\nNote: your previous answer {choice!r} is not in the candidate list."
                + " Pick a CatID that appears verbatim in the list above."
            )
            retry_choice, retry_ok = self._one_call(system, retry_user)
            if retry_ok:
                choice = retry_choice
                if choice not in valid_cat_ids:
                    fallback = True
                    choice = valid_cat_ids[0]
            else:
                fallback = True
                choice = valid_cat_ids[0]
        elif not ok:
            fallback = True
            choice = valid_cat_ids[0]

        latency_ms = int((time.monotonic() - t0) * 1000)
        return PickResult(
            cat_id=choice,
            retried=retried,
            fallback_to_clap_top1=fallback,
            latency_ms=latency_ms,
        )

    def _one_call(self, system: str, user: str) -> tuple[str, bool]:
        """Single Ollama call. Return (choice, ok). ok=False on transport/JSON failure."""
        payload = {
            "model": self._model,
            "prompt": user,
            "system": system,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0},
            "think": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            logger.exception("Ollama transport failed")
            return "", False

        inner_text = body.get("response", "")
        if not inner_text:
            logger.warning("Ollama returned empty response")
            return "", False
        try:
            parsed = json.loads(inner_text)
        except json.JSONDecodeError:
            logger.warning("Ollama returned non-JSON: %r", inner_text[:200])
            return "", False
        choice = parsed.get("choice")
        return (choice.strip() if isinstance(choice, str) else ""), True
