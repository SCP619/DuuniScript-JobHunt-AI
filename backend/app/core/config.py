"""Application settings loaded from environment variables and an optional .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.paths import default_data_dir

REPO_ROOT = Path(__file__).resolve().parents[3]

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_data_dir: Path = Field(default_factory=default_data_dir)
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]
    )
    max_request_bytes: int = Field(default=1_048_576, ge=1024)
    max_upload_bytes: int = Field(default=20 * 1_048_576, ge=1024)
    url_import_enabled: bool = True
    url_import_timeout_seconds: float = Field(default=15.0, gt=0, le=60)

    # Job alert emails (read-only IMAP). The password is never a setting: it is kept in
    # Windows Credential Manager (scripts/set_mail_password.py).
    mail_imap_host: str = "imap.gmail.com"
    mail_imap_port: int = Field(default=993, ge=1, le=65535)
    mail_imap_user: str | None = None
    mail_folder: str = Field(default="DuuniScript", min_length=1, max_length=200)
    mail_sync_interval_minutes: int = Field(default=60, ge=0, le=1440)
    mail_backfill_days: int = Field(default=30, ge=1, le=365)
    mail_timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    # Official job feeds and public job APIs (adapters/job_sources/feeds.py). The timer looks
    # every N minutes for feeds that are due; each site has its own minimum interval.
    feed_sync_interval_minutes: int = Field(default=60, ge=0, le=1440)
    feed_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    # Remote jobs limited to other countries (e.g. "USA only") are not added at all.
    feed_skip_unavailable: bool = True
    # Optional comma-separated words; when set, a feed job is added only if its title or
    # description contains one of them (e.g. "python, data, analyst"). Empty = all jobs.
    feed_keywords: str = Field(default="", max_length=2000)

    # Backups (zip of database, documents and snapshots in APP_DATA_DIRackups).
    backup_interval_hours: int = Field(default=24, ge=0, le=24 * 30)  # 0 = no automatic backups
    backup_keep: int = Field(default=10, ge=1, le=100)

    # Sign-in to DuuniScript (active once a passphrase is created in the app).
    auth_session_days: int = Field(default=30, ge=1, le=365)

    # Connected accounts (optional). Gmail: OAuth client JSON of type "Desktop app" from your own
    # Google Cloud project, saved outside the repository. Microsoft 365 (e.g. UTU mail): the
    # Application (client) ID of your own app registration with public client flows allowed.
    google_oauth_client_file: Path | None = None
    ms_client_id: str | None = None
    ms_tenant: str = "organizations"
    oauth_fast_poll: bool = False  # tests only

    # Optional local AI (Ollama) for nicer wording; off unless OLLAMA_MODEL is set.
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str | None = None
    # Embedding model for RAG search (multilingual), e.g. bge-m3. Off when not set.
    ollama_embed_model: str | None = None
    # How often the search index is brought up to date while the app runs (0 = only on request).
    rag_index_interval_minutes: int = Field(default=15, ge=0, le=1440)

    # Housekeeping: archive jobs first seen more than N days ago and never acted on (0 = never).
    job_archive_days: int = Field(default=60, ge=0, le=3650)
    housekeeping_interval_minutes: int = Field(default=360, ge=0, le=10080)
    # Windows desktop notifications for new in-app notifications.
    desktop_notifications: bool = True
    desktop_notify_interval_minutes: int = Field(default=15, ge=0, le=1440)
    ollama_timeout_seconds: float = Field(default=180.0, gt=0, le=900)

    @property
    def feed_keyword_list(self) -> list[str]:
        return [w.strip().lower() for w in self.feed_keywords.split(",") if w.strip()]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @field_validator("app_data_dir", mode="after")
    @classmethod
    def _data_dir_outside_repo(cls, value: Path) -> Path:
        value = value.expanduser()
        try:
            value.resolve().relative_to(REPO_ROOT)
        except ValueError:
            return value
        raise ValueError("APP_DATA_DIR must not be inside the Git repository")

    @property
    def database_path(self) -> Path:
        return self.app_data_dir / "database" / "duuniscript.sqlite3"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def is_loopback(self) -> bool:
        return self.api_host in LOOPBACK_HOSTS


@lru_cache
def get_settings() -> Settings:
    return Settings()
