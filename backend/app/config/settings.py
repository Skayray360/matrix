# Creado por Aldo Garcia.
"""Configuracion tipada y validada de Matrix RH.

Todos los parametros operativos (RAG, Ollama, auth, uploads) viven aqui y no en
constantes dispersas, porque la seccion 9 exige que sean auditables y que se
puedan mostrar en un endpoint administrativo de diagnostico.

Las invariantes de seguridad se validan al construir el objeto: si la
configuracion es insegura el proceso no arranca, en lugar de degradarse en
silencio.
"""

from __future__ import annotations

import secrets
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.common.errors import ConfigurationError

#: Raiz del repositorio: <repo>/backend/app/config/settings.py -> <repo>
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class AuthProvider(StrEnum):
    ENTRA = "entra"
    LOCAL_TEST = "local_test"


class QdrantMode(StrEnum):
    """Modo de operacion del vector store.

    ``embedded`` usa el almacenamiento local persistente del cliente oficial de
    Qdrant (mismo API, mismos filtros de metadata, persistencia en disco).
    ``server`` apunta a una instancia Qdrant dedicada. No existe fallback
    automatico entre modos: el modo es explicito y ``/ready`` falla si el modo
    configurado no esta operativo.
    """

    EMBEDDED = "embedded"
    SERVER = "server"


def _resolve(path_value: str | Path) -> Path:
    """Resuelve rutas relativas contra la raiz del repositorio."""
    path = Path(path_value)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


class Settings(BaseSettings):
    """Configuracion completa de la aplicacion."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------- app ---
    app_env: AppEnv = AppEnv.DEVELOPMENT
    app_name: str = "Matrix RH"
    app_base_url: str = "http://127.0.0.1:8000"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_log_level: str = "INFO"
    app_secret_key: SecretStr = SecretStr("")

    # ------------------------------------------------------------- ollama ---
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_fast_model: str = "gemma4:latest"
    ollama_deep_model: str = "qwen3.6:latest"
    ollama_embedding_model: str = "embeddinggemma:latest"
    ollama_embedding_dimension: int = 768
    #: Generoso a proposito: el modelo profundo de 24 GB puede ejecutarse
    #: parcialmente en CPU si no cabe en la GPU del equipo destino.
    ollama_timeout_seconds: float = 600.0
    ollama_keep_alive: str = "15m"
    #: Presupuestos distintos evitan reservar el contexto profundo para cada
    #: saludo, pero permiten que Qwen procese documentos extensos cuando aporta
    #: valor. ``num_predict`` acotado evita respuestas errantes y mejora el TTFT.
    ollama_fast_num_ctx: Annotated[int, Field(ge=2048, le=131072)] = 8192
    ollama_deep_num_ctx: Annotated[int, Field(ge=4096, le=262144)] = 32768
    ollama_fast_max_tokens: Annotated[int, Field(ge=64, le=8192)] = 768
    ollama_deep_max_tokens: Annotated[int, Field(ge=128, le=16384)] = 2048
    ollama_embedding_cache_size: Annotated[int, Field(ge=0, le=4096)] = 256
    ollama_summary_parallel_batches: Annotated[int, Field(ge=1, le=8)] = 2

    # ---------------------------------------------------------------- rag ---
    rag_vector_store: Literal["qdrant"] = "qdrant"
    rag_chunk_size_tokens: Annotated[int, Field(ge=64, le=8000)] = 900
    rag_chunk_overlap_tokens: Annotated[int, Field(ge=0, le=4000)] = 120
    rag_embedding_dimension: Annotated[int, Field(ge=1)] = 768
    rag_top_k: Annotated[int, Field(ge=1, le=50)] = 6
    rag_fetch_k: Annotated[int, Field(ge=1, le=500)] = 24
    rag_min_similarity: Annotated[float, Field(ge=0.0, le=1.0)] = 0.35
    rag_mmr_lambda: Annotated[float, Field(ge=0.0, le=1.0)] = 0.65
    rag_search_strategy: str = "cosine_hnsw_metadata_filter_mmr"
    rag_reindex_interval_hours: Annotated[int, Field(ge=1, le=168)] = 24
    rag_knowledge_root: Path = Path("./data/knowledge")
    rag_collection_corporate: str = "matrix_rh_corporate"
    rag_collection_private: str = "matrix_rh_private"
    #: Un resumen de adjuntos recupera por ACL/metadata, no por similitud. El
    #: primer limite acota el scroll y el segundo el material entregado al LLM.
    rag_summary_scan_max_chunks: Annotated[int, Field(ge=1, le=2000)] = 256
    rag_summary_max_chunks: Annotated[int, Field(ge=1, le=128)] = 24

    # --------------------------------------------------------------- auth ---
    auth_provider: AuthProvider = AuthProvider.LOCAL_TEST
    local_test_auth_enabled: bool = True
    local_test_seed_users_enabled: bool = True
    local_test_seed_profile: str = "matrix_demo"
    session_cookie_name: str = "matrixrh_session"
    session_ttl_minutes: Annotated[int, Field(ge=1, le=10080)] = 480
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # -------------------------------------------------------------- entra ---
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_client_secret: SecretStr = SecretStr("")
    entra_redirect_uri: str = ""
    entra_post_logout_redirect_uri: str = ""
    entra_allowed_groups: str = ""
    entra_role_mapping_file: Path = Path("./config/authorization/entra-role-mapping.yaml")

    # ----------------------------------------------------------- database ---
    database_url: SecretStr = SecretStr("mysql+pymysql://root:@127.0.0.1:3306/matrix_rh?charset=utf8mb4")
    database_pool_size: Annotated[int, Field(ge=1, le=50)] = 5
    database_echo: bool = False

    # --------------------------------------------------------- structured ---
    structured_sources_config: Path = Path("./config/data_sources/sources.yaml")
    structured_query_timeout_seconds: Annotated[int, Field(ge=1, le=120)] = 15
    structured_max_rows: Annotated[int, Field(ge=1, le=10000)] = 200

    # ------------------------------------------------------------- qdrant ---
    qdrant_mode: QdrantMode = QdrantMode.EMBEDDED
    qdrant_path: Path = Path("./var/qdrant")
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: SecretStr = SecretStr("")

    # ------------------------------------------------------ authorization ---
    authorization_policy_file: Path = Path("./config/authorization/categories.yaml")

    # ------------------------------------------------------------ uploads ---
    upload_max_bytes: Annotated[int, Field(ge=1024)] = 26_214_400
    upload_max_files_per_request: Annotated[int, Field(ge=1, le=50)] = 5
    upload_storage_root: Path = Path("./var/uploads")
    upload_allowed_extensions: str = ".docx,.md,.pdf,.txt,.xlsx,.csv"

    # -------------------------------------------------------- rate limits ---
    rate_limit_login_per_minute: Annotated[int, Field(ge=1, le=1000)] = 5
    rate_limit_chat_per_minute: Annotated[int, Field(ge=1, le=10000)] = 30

    # ---------------------------------------------------------- scheduler ---
    scheduler_enabled: bool = True

    # ------------------------------------------------------------ windows ---
    matrix_install_mode: str = "windows_local"
    matrix_use_wamp_mysql: bool = True
    matrix_external_connectors_required: bool = False
    #: Permite usar una base que YA existia antes de que Matrix RH la tocara.
    #: Por defecto False: una base preexistente puede pertenecer a otra
    #: aplicacion aunque en este momento este vacia, y apropiarse de ella en
    #: silencio es un riesgo que no se asume. El instalador prefiere crear una
    #: base nueva con un nombre libre antes que activar esta opcion.
    matrix_adopt_existing_database: bool = False

    # ------------------------------------------------------------------------
    # Validaciones de campo
    # ------------------------------------------------------------------------
    @field_validator("app_log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"APP_LOG_LEVEL invalido: {value}")
        return upper

    @field_validator("ollama_base_url", "qdrant_url", "app_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    # ------------------------------------------------------------------------
    # Invariantes de modelo (fallan el arranque)
    # ------------------------------------------------------------------------
    @model_validator(mode="after")
    def _validate_rag_invariants(self) -> Settings:
        """Seccion 9: relaciones entre parametros del RAG."""
        if self.rag_chunk_size_tokens <= self.rag_chunk_overlap_tokens:
            raise ValueError(
                "RAG_CHUNK_SIZE_TOKENS debe ser estrictamente mayor que RAG_CHUNK_OVERLAP_TOKENS"
            )
        if self.rag_fetch_k < self.rag_top_k:
            raise ValueError("RAG_FETCH_K debe ser mayor o igual que RAG_TOP_K")
        if self.rag_embedding_dimension != self.ollama_embedding_dimension:
            raise ValueError(
                "RAG_EMBEDDING_DIMENSION y OLLAMA_EMBEDDING_DIMENSION deben coincidir"
            )
        if self.rag_summary_scan_max_chunks < self.rag_summary_max_chunks:
            raise ValueError(
                "RAG_SUMMARY_SCAN_MAX_CHUNKS debe ser mayor o igual que RAG_SUMMARY_MAX_CHUNKS"
            )
        return self

    @model_validator(mode="after")
    def _validate_environment_safety(self) -> Settings:
        """Requisitos 32 y 58: el modo local jamas puede vivir en produccion."""
        is_prod_like = self.app_env in (AppEnv.PRODUCTION, AppEnv.STAGING)

        if self.app_env is AppEnv.PRODUCTION:
            if self.local_test_auth_enabled:
                raise ValueError(
                    "LOCAL_TEST_AUTH_ENABLED=true es incompatible con APP_ENV=production. "
                    "El proveedor local de pruebas debe estar deshabilitado."
                )
            if self.auth_provider is AuthProvider.LOCAL_TEST:
                raise ValueError(
                    "AUTH_PROVIDER=local_test es incompatible con APP_ENV=production. "
                    "Use AUTH_PROVIDER=entra."
                )
            if self.local_test_seed_users_enabled:
                raise ValueError(
                    "LOCAL_TEST_SEED_USERS_ENABLED=true es incompatible con APP_ENV=production."
                )
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE debe ser true en production.")

        if is_prod_like and not self.app_secret_key.get_secret_value():
            raise ValueError("APP_SECRET_KEY es obligatoria fuera de development/test.")

        if self.auth_provider is AuthProvider.LOCAL_TEST and not self.local_test_auth_enabled:
            raise ValueError(
                "AUTH_PROVIDER=local_test requiere LOCAL_TEST_AUTH_ENABLED=true."
            )

        if self.auth_provider is AuthProvider.ENTRA:
            faltantes = [
                name
                for name, value in (
                    ("ENTRA_TENANT_ID", self.entra_tenant_id),
                    ("ENTRA_CLIENT_ID", self.entra_client_id),
                    ("ENTRA_REDIRECT_URI", self.entra_redirect_uri),
                )
                if not value or value == "replace_me"
            ]
            if faltantes:
                raise ValueError(
                    "AUTH_PROVIDER=entra requiere configurar: " + ", ".join(faltantes)
                )
        return self

    @model_validator(mode="after")
    def _autogenerate_dev_secret(self) -> Settings:
        """En development/test se genera una clave efimera para no obligar a
        escribir un secreto en el .env de un entorno de pruebas."""
        if not self.app_secret_key.get_secret_value():
            object.__setattr__(self, "app_secret_key", SecretStr(secrets.token_hex(32)))
        return self

    # ------------------------------------------------------------------------
    # Propiedades derivadas
    # ------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION

    @property
    def is_local_auth_allowed(self) -> bool:
        """El proveedor local solo existe en development/test."""
        return self.app_env in (AppEnv.DEVELOPMENT, AppEnv.TEST) and self.local_test_auth_enabled

    @property
    def knowledge_root_path(self) -> Path:
        return _resolve(self.rag_knowledge_root)

    @property
    def upload_storage_path(self) -> Path:
        return _resolve(self.upload_storage_root)

    @property
    def qdrant_storage_path(self) -> Path:
        return _resolve(self.qdrant_path)

    @property
    def authorization_policy_path(self) -> Path:
        return _resolve(self.authorization_policy_file)

    @property
    def structured_sources_path(self) -> Path:
        return _resolve(self.structured_sources_config)

    @property
    def entra_role_mapping_path(self) -> Path:
        return _resolve(self.entra_role_mapping_file)

    @property
    def allowed_upload_extensions(self) -> frozenset[str]:
        return frozenset(
            ext.strip().lower()
            for ext in self.upload_allowed_extensions.split(",")
            if ext.strip()
        )

    @property
    def entra_allowed_group_list(self) -> tuple[str, ...]:
        return tuple(g.strip() for g in self.entra_allowed_groups.split(",") if g.strip())

    def rag_parameters_snapshot(self) -> dict[str, object]:
        """Vista auditable de los parametros del RAG (seccion 9 y 24).

        La usa el endpoint administrativo ``/api/v1/admin/diagnostics`` y la
        documentacion generada, de modo que documentacion y codigo no puedan
        divergir.
        """
        return {
            "RAG_VECTOR_STORE": self.rag_vector_store,
            "RAG_CHUNK_SIZE_TOKENS": self.rag_chunk_size_tokens,
            "RAG_CHUNK_OVERLAP_TOKENS": self.rag_chunk_overlap_tokens,
            "RAG_EMBEDDING_DIMENSION": self.rag_embedding_dimension,
            "RAG_TOP_K": self.rag_top_k,
            "RAG_FETCH_K": self.rag_fetch_k,
            "RAG_MIN_SIMILARITY": self.rag_min_similarity,
            "RAG_MMR_LAMBDA": self.rag_mmr_lambda,
            "RAG_SEARCH_STRATEGY": self.rag_search_strategy,
            "RAG_REINDEX_INTERVAL_HOURS": self.rag_reindex_interval_hours,
            "OLLAMA_FAST_MODEL": self.ollama_fast_model,
            "OLLAMA_DEEP_MODEL": self.ollama_deep_model,
            "OLLAMA_EMBEDDING_MODEL": self.ollama_embedding_model,
            "OLLAMA_FAST_NUM_CTX": self.ollama_fast_num_ctx,
            "OLLAMA_DEEP_NUM_CTX": self.ollama_deep_num_ctx,
            "OLLAMA_FAST_MAX_TOKENS": self.ollama_fast_max_tokens,
            "OLLAMA_DEEP_MAX_TOKENS": self.ollama_deep_max_tokens,
            "OLLAMA_SUMMARY_PARALLEL_BATCHES": self.ollama_summary_parallel_batches,
            "OLLAMA_KEEP_ALIVE": self.ollama_keep_alive,
            "OLLAMA_EMBEDDING_CACHE_SIZE": self.ollama_embedding_cache_size,
            "RAG_SUMMARY_SCAN_MAX_CHUNKS": self.rag_summary_scan_max_chunks,
            "RAG_SUMMARY_MAX_CHUNKS": self.rag_summary_max_chunks,
            "source_of_truth": "backend/app/config/settings.py::Settings",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Instancia unica de configuracion.

    Se envuelve el ``ValidationError`` de pydantic en ``ConfigurationError`` para
    que el mensaje que llega al operador sea accionable y no un volcado interno.
    """
    try:
        return Settings()
    except Exception as exc:  # noqa: BLE001 - se re-lanza como error tipado
        raise ConfigurationError(
            "La configuracion de Matrix RH es invalida.", detail=str(exc)
        ) from exc


def reload_settings() -> Settings:
    """Reinicia la cache de configuracion (usado por pruebas y por preflight)."""
    get_settings.cache_clear()
    return get_settings()
