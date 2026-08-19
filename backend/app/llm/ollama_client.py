# Creado por Aldo Garcia.
"""Cliente unico hacia Ollama local.

Toda llamada a un modelo pasa por aqui: un solo punto para timeouts, reintentos,
keep-alive, metricas de latencia y preflight. Ningun otro modulo abre conexiones
HTTP hacia Ollama.

Reglas del proyecto que este cliente hace cumplir:

* los modelos son exactamente ``gemma4:latest``, ``qwen3.6:latest`` y
  ``embeddinggemma:latest``; no hay sustitucion por modelos cloud;
* la dimension de embeddings se **comprueba en runtime**: si no coincide con la
  configurada se lanza ``EmbeddingDimensionMismatchError``. Jamas se trunca ni se
  rellena un vector;
* solo se reintentan errores transitorios (timeout / error de red / 5xx), nunca
  un 4xx, que indica una peticion incorrecta.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import Any

import httpx

from app.common.errors import EmbeddingDimensionMismatchError, OllamaUnavailableError
from app.common.logging import get_logger
from app.config import get_settings

logger = get_logger(__name__)

MAX_TRANSIENT_RETRIES = 2
RETRY_BACKOFF_SECONDS = 0.75


@dataclass(frozen=True, slots=True)
class ChatResult:
    """Respuesta de generacion mas metricas para auditoria."""

    content: str
    model: str
    latency_ms: int
    prompt_eval_count: int | None = None
    eval_count: int | None = None


@dataclass(frozen=True, slots=True)
class ModelInventory:
    """Inventario de modelos disponibles en la instancia Ollama."""

    names: tuple[str, ...]

    def has(self, model: str) -> bool:
        return model in self.names


class OllamaClient:
    """Cliente sincrono. FastAPI ejecuta las rutas de chat en threadpool."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.ollama_timeout_seconds
        self.keep_alive = settings.ollama_keep_alive
        self.embedding_model = settings.ollama_embedding_model
        self.expected_dimension = settings.ollama_embedding_dimension
        self.embedding_cache_size = settings.ollama_embedding_cache_size
        self._embedding_cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._embedding_cache_lock = Lock()
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(self.timeout, connect=min(10.0, self.timeout)),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    # ------------------------------------------------------------------ HTTP
    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST con reintentos limitados a errores transitorios."""
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(MAX_TRANSIENT_RETRIES + 1):
            try:
                response = self._client.post(url, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt < MAX_TRANSIENT_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                break
            if response.status_code >= 500:
                last_error = OllamaUnavailableError(detail=f"HTTP {response.status_code}")
                if attempt < MAX_TRANSIENT_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                break
            if response.status_code >= 400:
                # 4xx no se reintenta: es un problema de la peticion (por ejemplo
                # modelo inexistente) y reintentar solo esconde el diagnostico.
                raise OllamaUnavailableError(
                    "La peticion al modelo local fue rechazada.",
                    detail=f"HTTP {response.status_code} en {path}",
                )
            return response.json()

        if isinstance(last_error, OllamaUnavailableError):
            detail = last_error.detail or last_error.message
        else:
            detail = str(last_error)
        raise OllamaUnavailableError(
            "No fue posible contactar el servicio de IA local.", detail=detail
        )

    def _get(self, path: str) -> dict[str, Any]:
        try:
            response = self._client.get(f"{self.base_url}{path}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError(
                "No fue posible contactar el servicio de IA local.", detail=str(exc)
            ) from exc

    # --------------------------------------------------------------- salud
    def ping(self) -> bool:
        try:
            response = self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def list_models(self) -> ModelInventory:
        data = self._get("/api/tags")
        names = tuple(str(m.get("name", "")) for m in data.get("models", []))
        return ModelInventory(names=names)

    # ----------------------------------------------------------- generacion
    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        num_ctx: int | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> ChatResult:
        """Genera una respuesta con la API ``/api/chat``.

        La temperatura por defecto es baja a proposito: Matrix RH responde sobre
        politicas de RH y debe ceñirse a la evidencia, no producir variedad.
        """
        options: dict[str, Any] = {"temperature": temperature}
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if stop:
            options["stop"] = stop

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": options,
        }
        started = time.perf_counter()
        data = self._post("/api/chat", payload)
        latency_ms = int((time.perf_counter() - started) * 1000)

        content = str((data.get("message") or {}).get("content", "")).strip()
        logger.info(
            "llm.chat",
            extra={
                "selected_model": model,
                "latency_ms": latency_ms,
                "response_chars": len(content),
            },
        )
        return ChatResult(
            content=content,
            model=model,
            latency_ms=latency_ms,
            prompt_eval_count=data.get("prompt_eval_count"),
            eval_count=data.get("eval_count"),
        )

    # ----------------------------------------------------------- embeddings
    def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        """Genera embeddings y **verifica la dimension real** de cada vector."""
        if not texts:
            return []
        target_model = model or self.embedding_model
        data = self._post(
            "/api/embed",
            {"model": target_model, "input": texts, "keep_alive": self.keep_alive},
        )
        raw = data.get("embeddings")
        if not isinstance(raw, list) or len(raw) != len(texts):
            raise EmbeddingDimensionMismatchError(
                "La respuesta de embeddings no tiene la forma esperada.",
                detail=f"esperados={len(texts)} recibidos={len(raw) if isinstance(raw, list) else 'n/a'}",
            )
        vectors: list[list[float]] = []
        for vector in raw:
            if not isinstance(vector, list) or len(vector) != self.expected_dimension:
                actual = len(vector) if isinstance(vector, list) else "desconocida"
                raise EmbeddingDimensionMismatchError(
                    "La dimension de embeddings no coincide con la configurada.",
                    detail=(
                        f"modelo={target_model} esperada={self.expected_dimension} real={actual}. "
                        "No se trunca ni se rellena el vector."
                    ),
                )
            vectors.append([float(v) for v in vector])
        return vectors

    def embed_one(self, text: str, *, model: str | None = None) -> list[float]:
        target_model = model or self.embedding_model
        if self.embedding_cache_size <= 0:
            return self.embed([text], model=target_model)[0]

        # La clave no conserva la pregunta del usuario: solo modelo + SHA-256.
        cache_key = f"{target_model}:{sha256(text.encode('utf-8')).hexdigest()}"
        with self._embedding_cache_lock:
            cached = self._embedding_cache.get(cache_key)
            if cached is not None:
                self._embedding_cache.move_to_end(cache_key)
                return list(cached)

        vector = self.embed([text], model=target_model)[0]
        with self._embedding_cache_lock:
            self._embedding_cache[cache_key] = tuple(vector)
            self._embedding_cache.move_to_end(cache_key)
            while len(self._embedding_cache) > self.embedding_cache_size:
                self._embedding_cache.popitem(last=False)
        return vector

    def probe_embedding_dimension(self, *, model: str | None = None) -> int:
        """Devuelve la dimension real observada (preflight y diagnostico).

        No usa ``embed`` porque ese metodo ya exige que la dimension coincida; el
        preflight necesita poder **reportar** la discrepancia.
        """
        target_model = model or self.embedding_model
        data = self._post(
            "/api/embed",
            {
                "model": target_model,
                "input": ["matrix rh dimension probe"],
                "keep_alive": self.keep_alive,
            },
        )
        vectors = data.get("embeddings") or []
        if not vectors or not isinstance(vectors[0], list):
            raise EmbeddingDimensionMismatchError(
                "El endpoint de embeddings no devolvio ningun vector.", detail=f"modelo={target_model}"
            )
        return len(vectors[0])

    def close(self) -> None:
        self._client.close()


_client: OllamaClient | None = None


def get_ollama_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def reset_ollama_client() -> None:
    global _client
    if _client is not None:
        _client.close()
    _client = None
