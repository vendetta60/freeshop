"""Single source of truth for configuration.

Every environment variable the application reads is declared here. Nothing
else in the codebase may call ``os.environ`` directly - that rule is what
makes ``.env.example`` trustworthy as documentation.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

PLACEHOLDER_SECRET = "change-me-min-32-bytes-use-openssl-rand-hex-32"

Env = Literal["development", "production", "test"]
OtpChannel = Literal["console", "telegram", "email", "sms"]


class Settings(BaseSettings):
    """Application settings, loaded from the environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core / brand -----------------------------------------------------
    env: Env = "development"
    app_name: str = "FreeShop"
    request_prefix: str = "SR"
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"

    # --- Security ---------------------------------------------------------
    jwt_secret: str = PLACEHOLDER_SECRET
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    # --- Database ---------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./data/freeshop.db"

    # --- Google OAuth (optional until credentials exist - plan.md 18/W2) ---
    google_client_id: str = ""
    google_client_secret: str = ""

    # --- Demo -------------------------------------------------------------
    # Explicit opt-in that lets the console OTP channel run under
    # ENV=production. Exists because this project's "production" is a local
    # Docker stack for a defence: without it there is no way to sign in at all
    # (Google has no credentials, and the guard blocks console OTP), which
    # makes the whole authenticated half of the app undemonstrable.
    #
    # It must stay an explicit opt-in, not a default: the guard is still the
    # right behaviour for anything reachable from the internet, and startup
    # logs a prominent warning whenever this is on.
    demo_mode: bool = False

    # --- Phone auth / OTP -------------------------------------------------
    auth_phone_enabled: bool = True
    otp_channel: OtpChannel = "console"
    otp_ttl_seconds: int = 300

    # Send limits (plan.md 9.4). Defaults ARE the specified values; they are
    # settings rather than constants because a demo machine that several
    # people share has one seeded admin number between them, and three sends
    # per fifteen minutes locks the room out. Loosen them in .env for a demo,
    # never in production - startup warns if you do.
    otp_max_sends_per_phone: int = 3
    otp_send_window_minutes: int = 15
    otp_max_sends_per_ip: int = 10
    otp_ip_window_minutes: int = 60
    telegram_bot_token: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # --- Uploads ----------------------------------------------------------
    upload_dir: Path = Field(default=Path("./static/uploads"))
    max_upload_mb: int = 5
    max_images_per_product: int = 8

    # --- Seed -------------------------------------------------------------
    admin_email: str = ""
    admin_phone: str = ""

    # ---------------------------------------------------------------------
    # Derived helpers
    # ---------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_development(self) -> bool:
        return self.env == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def google_configured(self) -> bool:
        """Google login is wired but credentials may not exist yet.

        The API must start and stay healthy without them; only the Google
        endpoint itself fails, with a clear error code.
        """
        return bool(self.google_client_id)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def resolved_upload_dir(self) -> Path:
        p = self.upload_dir
        return p if p.is_absolute() else (BACKEND_ROOT / p).resolve()

    # ---------------------------------------------------------------------
    # Validation - fail loudly at boot, never at request time
    # ---------------------------------------------------------------------
    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_cors(cls, v: str) -> str:
        # A wildcard origin combined with credentialed requests silently
        # disables CORS in Starlette. Ban it outright (plan.md 10).
        if "*" in v:
            raise ValueError(
                "CORS_ORIGINS must be an explicit comma-separated allowlist, never '*'."
            )
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if not self.is_production:
            return self

        problems: list[str] = []
        if self.jwt_secret == PLACEHOLDER_SECRET:
            problems.append("JWT_SECRET is still the placeholder from .env.example")
        if len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be at least 32 characters")
        # Only a hazard when phone auth is actually on: with the feature
        # disabled no code is ever generated, so there is nothing to leak.
        # Guarding unconditionally would block a legitimate Google-only
        # production deploy for a setting that has no effect.
        if self.auth_phone_enabled and self.otp_channel == "console" and not self.demo_mode:
            problems.append(
                "OTP_CHANNEL=console prints codes to the log and must never run in production "
                "while AUTH_PHONE_ENABLED=true. Set DEMO_MODE=true to allow it deliberately "
                "on a local, non-public instance."
            )
        if problems:
            raise ValueError("Refusing to start in production:\n  - " + "\n  - ".join(problems))
        return self


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    return Settings()


_override: Settings | None = None


def get_settings() -> Settings:
    """Cached settings accessor. Use this everywhere; never instantiate directly."""
    return _override if _override is not None else _load_settings()


def set_settings(settings: Settings | None) -> None:
    """Install an explicit configuration, or clear it with None.

    Needed because the whole codebase reads configuration through
    `get_settings()`. Without this, `create_app(settings)` would configure
    only the FastAPI object while every service kept reading the ambient
    .env - which is exactly the bug the auth tests caught: they passed
    auth_phone_enabled=True and still got 404s from the file on disk.
    """
    global _override
    _override = settings
    _load_settings.cache_clear()
