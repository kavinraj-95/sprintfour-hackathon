"""The model seam for the LLM arbitration layer (detection layer 4).

`layer-discipline` requires the model be a flag, not a fork: `MODEL=cloud` (a
hosted Claude model reached with the user's API key) and `MODEL=gemma-local`
(Gemma 3n E4B served by a local Ollama) must travel the *same* code path. That
is exactly what this module gives the layer: one `LlmClient` interface with a
single method, two interchangeable implementations behind it, and a factory that
picks one from `config.MODEL`.

The contract is deliberately tiny — `complete(system, user) -> str` returns the
model's raw text. Everything that makes the output *trustworthy* (JSON parsing,
re-anchoring spans to real offsets, dropping hallucinations) lives in
`llm_layer`, not here, so a test can swap in a deterministic stub and exercise
the whole layer offline. The clients here only know how to talk to a model; they
do not know what a Span is.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import config
from errors import AppError


@runtime_checkable
class LlmClient(Protocol):
    """A model that turns a (system, user) prompt pair into text.

    The single seam every backend implements. The arbitration layer depends on
    this Protocol, never on a concrete client, so `cloud` and `gemma-local` —
    and a deterministic test double — are interchangeable.
    """

    def complete(self, *, system: str, user: str) -> str: ...


class CloudLlmClient:
    """`MODEL=cloud`: a hosted Claude model via the official Anthropic SDK.

    Defaults to the latest, most capable model (`config.CLOUD_MODEL`). The SDK
    is imported lazily so neither the package nor an API key is required unless
    this backend is actually selected — the layer's tests never touch it.
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model or config.CLOUD_MODEL

    def complete(self, *, system: str, user: str) -> str:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on env
            raise AppError(
                status_code=500,
                error="llm_backend_unavailable",
                detail="MODEL=cloud requires the 'anthropic' package to be installed.",
            ) from exc

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY / ant profile
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in response.content if b.type == "text")


class GemmaLocalClient:
    """`MODEL=gemma-local`: Gemma 3n E4B served by a local Ollama daemon.

    Uses Ollama's `/api/chat` with `format=json` so the model is constrained to
    emit JSON, matching what the layer parses. Same method, same return type as
    the cloud client — the layer cannot tell which one it holds.
    """

    def __init__(self, host: str | None = None, model: str | None = None) -> None:
        self.host = (host or config.OLLAMA_HOST).rstrip("/")
        self.model = model or config.GEMMA_MODEL

    def complete(self, *, system: str, user: str) -> str:
        import httpx  # a project dependency; imported here to keep the seam thin

        try:
            response = httpx.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "format": "json",
                },
                timeout=120.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - depends on env
            raise AppError(
                status_code=502,
                error="llm_backend_unavailable",
                detail=f"Could not reach Ollama at {self.host}: {exc}",
            ) from exc

        return response.json().get("message", {}).get("content", "")


def get_llm_client(model: str | None = None) -> LlmClient:
    """Resolve the configured backend. `model` overrides `config.MODEL`.

    The one place the `cloud` / `gemma-local` choice is made. Everything
    downstream takes an `LlmClient` and stays oblivious to which one it got.
    """
    flag = (model or config.MODEL).strip().lower()
    if flag == "cloud":
        return CloudLlmClient()
    if flag in {"gemma-local", "gemma_local", "local"}:
        return GemmaLocalClient()
    raise AppError(
        status_code=500,
        error="unknown_model_flag",
        detail=f"MODEL must be 'cloud' or 'gemma-local', got {flag!r}.",
    )
