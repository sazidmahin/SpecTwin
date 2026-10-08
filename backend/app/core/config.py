from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "SRS Diagram Platform"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "change-this-development-secret"
    access_token_expire_minutes: int = 60
    password_reset_token_expire_minutes: int = 15
    email_delivery_mode: str = "console"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@srs-platform.local"
    smtp_from_name: str = "SRS Diagram Platform"
    smtp_use_tls: bool = True
    # Used when EMAIL_DELIVERY_MODE=resend. The sender address must belong to a
    # domain verified in Resend; onboarding@resend.dev only delivers to the
    # Resend account owner's own address (fine for testing).
    resend_api_key: str | None = None
    resend_api_url: str = "https://api.resend.com/emails"
    resend_from_email: str = "onboarding@resend.dev"
    resend_from_name: str = "SRS Diagram Platform"
    resend_timeout_seconds: int = 15
    email_verification_code_expire_minutes: int = 10
    email_verification_resend_cooldown_seconds: int = 60
    # Where the web app is served; workspace invitation emails link back to it.
    frontend_url: str = "http://localhost:5173"
    workspace_invitation_expire_days: int = 7
    openai_model: str = "gpt-5.6"
    openai_models: str = "gpt-5.6,gpt-5.6-sol,gpt-5.6-terra,gpt-5.6-luna,gpt-5.5,gpt-5.5-2026-04-23,gpt-5.4,gpt-5.4-2026-03-05,gpt-5.4-pro,gpt-5.4-mini,gpt-5.2,gpt-4.1,gpt-4.1-mini,gpt-4.1-nano,gpt-4o,gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-5"
    anthropic_models: str = "claude-fable-5,claude-opus-5,claude-sonnet-5,claude-haiku-4-5-20251001,claude-opus-4-8,claude-opus-4-7,claude-opus-4-6,claude-sonnet-4-6"
    gemini_model: str = "gemini-3.6-flash"
    gemini_models: str = "gemini-3.6-flash,gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-pro-preview,gemini-3.1-flash-lite,gemini-3-flash-preview,gemini-2.5-pro,gemini-2.5-flash,gemini-2.5-flash-lite"
    openai_temperature: float = 0
    openai_timeout_seconds: int = 20
    openai_max_retries: int = 0
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = "llama3.2:1b"
    ollama_models: str = "llama3.2:1b,llama3.2,llama3.1,qwen2.5,qwen2.5-coder,mistral,phi3"
    # At temperature 0 (greedy decoding), a small model that starts repeating a
    # phrase has no randomness to break out of it - the repeated pattern stays
    # the single highest-probability next token forever. repeat_penalty=1.3 alone
    # was not enough to prevent this (observed: Ollama's own hard circuit
    # breaker aborted a generation entirely with "token repeat limit reached")
    # - a small amount of temperature is the standard companion to repeat_penalty
    # for escaping a loop a purely greedy sampler cannot break out of on its own.
    ollama_temperature: float = 0.2
    ollama_timeout_seconds: int = 600
    # Keep the model resident while a user reviews a stage (often several minutes);
    # reloading a model from disk on a CPU-only laptop costs seconds every stage.
    ollama_keep_alive: str = "30m"
    # One fixed context window for every call. Ollama restarts its runner (a full
    # model reload) whenever num_ctx changes between requests, so a per-call window
    # cost a reload on most stages. 8192 fits CPU laptops (KV cache ~0.5 GB for a
    # 1-3B model) and is large enough for chunked inputs.
    ollama_num_ctx: int = 8192
    ollama_num_predict: int = 1024
    # Largest slice of user text/items sent in one call. Inputs beyond this are
    # split into chunks and merged: small models answer shorter prompts better, and
    # nothing is silently cut off (Ollama drops the *start* of an over-long prompt,
    # which is where the instructions are).
    ollama_chunk_tokens: int = 2000
    # CPU threads for inference; unset lets Ollama pick (physical cores).
    ollama_num_thread: int | None = None
    # A strong repeat penalty fights JSON, which must repeat quotes, keys and
    # braces; with schema-constrained output it produced mangled keys. Keep it mild
    # and over a short window - output length is bounded by num_predict instead.
    ollama_repeat_penalty: float = 1.1
    ollama_repeat_last_n: int = 64
    ollama_embed_model: str = "nomic-embed-text"
    # Platform-managed hosted "AI generation" mode (app/services/hosted_ai_service.py).
    # One server-side key serves every user; the mode is hidden when it is unset.
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"
    # Comma-separated models tried in order when the primary one is rate-limited or down.
    openrouter_fallback_models: str = ""
    openrouter_temperature: float = 0.2
    openrouter_timeout_seconds: int = 120
    openrouter_max_tokens: int = 4096
    openrouter_max_retries: int = 2
    openrouter_site_url: str | None = None
    rag_enabled: bool = False
    rag_top_k: int = 2
    rag_min_similarity: float = 0.55
    # Which embedder the correction memory uses: "auto" prefers Ollama and falls
    # back to the built-in lexical one, "ollama" or "lexical" force a single one.
    # The fallback matters because the hosted AI engine needs no local setup.
    rag_embedder: str = "auto"
    ai_credential_encryption_key: str = "change-this-development-ai-credential-key"
    srsgen_base_model: str = "Qwen/Qwen1.5-1.8B-Chat"
    srsgen_artifact_path: str = "model_artifacts/srsgen-qwen1.5"
    srsgen_load_in_4bit: bool = True
    srsgen_max_new_tokens: int = 2048
    srsgen_temperature: float = 0
    backend_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="BACKEND_CORS_ORIGINS",
    )
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/srs_diagram_platform",
        alias="DATABASE_URL",
    )
    super_admin_email: str | None = None
    super_admin_password: str | None = None
    super_admin_full_name: str = "Platform Super Admin"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    def provider_models(self, provider: str) -> list[str]:
        raw = {
            "openai": self.openai_models,
            "anthropic": self.anthropic_models,
            "gemini": self.gemini_models,
            "ollama": self.ollama_models,
        }.get(provider, "")
        return list(dict.fromkeys(model.strip() for model in raw.split(",") if model.strip()))

    @property
    def openrouter_models(self) -> list[str]:
        """The hosted "AI generation" model, then its configured fallbacks, de-duplicated.

        Not part of provider_models(): those are the BYOK providers a user picks
        in AI Settings, and the hosted vendor is never one of them.
        """
        raw = f"{self.openrouter_model},{self.openrouter_fallback_models}"
        return list(dict.fromkeys(model.strip() for model in raw.split(",") if model.strip()))

    @field_validator("ollama_num_thread", mode="before")
    @classmethod
    def _blank_num_thread_is_auto(cls, value: object) -> object:
        # OLLAMA_NUM_THREAD= (empty, as in .env.example / docker-compose) means "let Ollama decide".
        return None if isinstance(value, str) and not value.strip() else value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
