"""Optional local language model (Ollama) for nicer wording of drafts (TRD 7, MODEL_SETUP).

Off unless ``OLLAMA_MODEL`` is set and Ollama runs on this computer. Only a loopback address is
accepted, so draft text never leaves the computer. The model only *rewrites* an existing draft:
its suggestion is never saved by itself, it goes through the same claim check as any edit, and
the user decides whether to use it. The job posting text is not sent to the model (it is
untrusted and could carry instructions); only the job title and employer are.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import Settings
from app.core.errors import AppError

SYSTEM_PROMPT = (
    "You edit job application documents for clarity and flow. Rules, all mandatory: "
    "1) Do not add any fact, name, number, date, skill, tool, employer, title, achievement or claim that is "
    "not already in the text. 2) Do not remove facts. 3) Keep every line that starts with #, ##, ### or -, "
    "and every line in *asterisks*, in place; you may only reword normal sentences. 4) Keep any text in "
    "[square brackets] exactly as it is. 5) Plain English, no superlatives, no clichés. "
    "Reply with the revised document only, no comments."
)
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class LlmStatus:
    enabled: bool
    model: str | None
    reachable: bool
    message: str | None


class OllamaProvider:
    def __init__(self, settings: Settings, http: httpx.Client | None = None) -> None:
        self.url = settings.ollama_url.rstrip("/")
        self.model = settings.ollama_model
        self.embed_model = settings.ollama_embed_model
        self.http = http or httpx.Client(timeout=settings.ollama_timeout_seconds)
        host = urlparse(self.url).hostname or ""
        self.local = host in LOOPBACK

    def status(self) -> LlmStatus:
        if not self.model:
            return LlmStatus(False, None, False, "Local AI is off. Set OLLAMA_MODEL to use it.")
        if not self.local:
            return LlmStatus(False, self.model, False, "OLLAMA_URL must point to this computer (127.0.0.1).")
        try:
            response = self.http.get(f"{self.url}/api/tags", timeout=3)
            names = {m.get("name") for m in response.json().get("models", [])} if response.status_code == 200 else set()
        except (httpx.HTTPError, ValueError):
            return LlmStatus(True, self.model, False, "Ollama is not running on this computer.")
        if self.model not in names and f"{self.model}:latest" not in names:
            return LlmStatus(True, self.model, False, f"The model {self.model} is not downloaded in Ollama.")
        return LlmStatus(True, self.model, True, None)

    def rewrite(self, text: str, context: str) -> str:
        state = self.status()
        if not state.reachable:
            raise AppError(409, "ai_unavailable", state.message or "Local AI is not available.")
        try:
            response = self.http.post(f"{self.url}/api/generate", json={
                "model": self.model,
                "system": SYSTEM_PROMPT,
                "prompt": f"{context}\n\nDocument:\n{text}",
                "stream": False,
                "options": {"temperature": 0.2},
            })
        except httpx.HTTPError as exc:
            raise AppError(502, "ai_error", "The local model did not answer.") from exc
        if response.status_code != 200:
            raise AppError(502, "ai_error", "The local model did not answer.")
        return str(response.json().get("response", "")).strip() + "\n"

    # ----- structured answers and embeddings (screenshot import, RAG) -----

    def _models(self) -> set[str]:
        try:
            response = self.http.get(f"{self.url}/api/tags", timeout=3)
            if response.status_code != 200:
                return set()
            names = {m.get("name", "") for m in response.json().get("models", [])}
            return names | {n.removesuffix(":latest") for n in names}
        except (httpx.HTTPError, ValueError):
            return set()

    def available(self) -> bool:
        return bool(self.model and self.local and self.model in self._models())

    def embeddings_available(self) -> bool:
        return bool(self.embed_model and self.local and self.embed_model in self._models())

    def chat_json(self, system: str, user: str, schema: dict) -> dict:
        """One structured answer that must match ``schema`` (Ollama structured outputs)."""
        if not self.available():
            raise AppError(409, "ai_unavailable", self.status().message or "Local AI is not available.")
        try:
            response = self.http.post(f"{self.url}/api/chat", json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "format": schema,
                "stream": False,
                "options": {"temperature": 0},
            })
        except httpx.HTTPError as exc:
            raise AppError(502, "ai_error", "The local model did not answer.") from exc
        if response.status_code != 200:
            raise AppError(502, "ai_error", "The local model did not answer.")
        import json

        try:
            return json.loads(response.json()["message"]["content"])
        except (KeyError, ValueError) as exc:
            raise AppError(502, "ai_error", "The local model gave an unreadable answer.") from exc

    def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        if not self.available():
            raise AppError(409, "ai_unavailable", self.status().message or "Local AI is not available.")
        try:
            response = self.http.post(f"{self.url}/api/chat", json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "stream": False,
                "options": {"temperature": temperature},
            })
        except httpx.HTTPError as exc:
            raise AppError(502, "ai_error", "The local model did not answer.") from exc
        if response.status_code != 200:
            raise AppError(502, "ai_error", "The local model did not answer.")
        return str(response.json().get("message", {}).get("content", "")).strip()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embeddings_available():
            raise AppError(409, "ai_unavailable", "The embedding model is not available in Ollama.")
        try:
            response = self.http.post(f"{self.url}/api/embed", json={"model": self.embed_model, "input": texts})
        except httpx.HTTPError as exc:
            raise AppError(502, "ai_error", "The embedding model did not answer.") from exc
        if response.status_code != 200:
            raise AppError(502, "ai_error", "The embedding model did not answer.")
        return response.json().get("embeddings", [])
