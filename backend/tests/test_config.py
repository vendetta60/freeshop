"""Configuration guards - these must fail loudly at boot, never at runtime."""

from __future__ import annotations

import pytest

from app.config import PLACEHOLDER_SECRET, Settings


def _prod(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "env": "production",
        "jwt_secret": "a-real-looking-secret-value-of-sufficient-length",
        "otp_channel": "telegram",
        "cors_origins": "http://localhost",
        # Pinned explicitly: the repository .env sets DEMO_MODE=true for the
        # local Docker demo, and pydantic-settings reads that file. Leaving it
        # implicit made these assertions depend on a developer's environment.
        "demo_mode": False,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_production_rejects_placeholder_secret() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        _prod(jwt_secret=PLACEHOLDER_SECRET)


def test_production_rejects_short_secret() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        _prod(jwt_secret="too-short")


def test_production_rejects_console_otp_channel_when_phone_auth_is_on() -> None:
    """Console prints codes to the log - fine for a demo, never for prod."""
    with pytest.raises(ValueError, match="console"):
        _prod(otp_channel="console", auth_phone_enabled=True)


def test_demo_mode_permits_console_otp_in_production() -> None:
    """The local-demo escape hatch (plan.md 18/W1).

    Without it the Docker stack has no working sign-in at all: Google has no
    credentials and the guard blocks the console channel, so the entire
    authenticated half of the app becomes undemonstrable.
    """
    settings = _prod(otp_channel="console", auth_phone_enabled=True, demo_mode=True)
    assert settings.demo_mode is True


def test_demo_mode_is_opt_in_not_the_default() -> None:
    """A weakened posture must never be reachable by accident."""
    # The DECLARED default, not a constructed instance: constructing reads the
    # repository .env, which enables demo mode for the local Docker stack. The
    # property under test is what ships in code.
    assert Settings.model_fields["demo_mode"].default is False

    # And without it, production still refuses the console channel.
    with pytest.raises(ValueError, match="DEMO_MODE"):
        _prod(otp_channel="console", auth_phone_enabled=True)


def test_production_allows_console_channel_when_phone_auth_is_off() -> None:
    """With the feature disabled no code is ever generated, so nothing leaks.

    Found by actually running the container: guarding unconditionally blocked
    a legitimate Google-only production deploy over a setting with no effect.
    """
    settings = _prod(otp_channel="console", auth_phone_enabled=False)
    assert settings.is_production is True


def test_wildcard_cors_is_rejected_everywhere() -> None:
    """'*' plus credentials silently disables CORS in Starlette."""
    with pytest.raises(ValueError, match="allowlist"):
        Settings(env="development", cors_origins="*")  # type: ignore[arg-type]


def test_development_tolerates_defaults() -> None:
    """A fresh clone with no .env must still boot."""
    settings = Settings(env="development")  # type: ignore[call-arg]
    assert settings.google_configured is False
    assert settings.is_development is True


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(  # type: ignore[call-arg]
        env="development",
        cors_origins="http://localhost:5173, http://localhost ",
    )
    assert settings.cors_origin_list == ["http://localhost:5173", "http://localhost"]
