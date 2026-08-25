"""Server-side message catalogue (plan.md 7.2).

The API returns a stable ``code`` plus a localised ``message``. The frontend
prefers its own translation of the code; ``message`` is the fallback and what
non-browser clients (curl, the OpenAPI docs) see.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Final

LOCALES_DIR: Final = Path(__file__).resolve().parent.parent / "locales"
DEFAULT_LANG: Final = "az"
SUPPORTED_LANGS: Final = ("az", "en")


@lru_cache(maxsize=len(SUPPORTED_LANGS))
def _catalogue(lang: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return data


def normalise_lang(raw: str | None) -> str:
    """Map anything the client sends onto a supported language."""
    if not raw:
        return DEFAULT_LANG
    head = raw.split(",")[0].strip().lower()[:2]
    return head if head in SUPPORTED_LANGS else DEFAULT_LANG


def translate_error(code: str, lang: str = DEFAULT_LANG) -> str:
    """Look up ``code`` in the catalogue, falling back az -> code itself."""
    lang = normalise_lang(lang)
    message = _catalogue(lang).get(code)
    if message:
        return message
    if lang != DEFAULT_LANG:
        fallback = _catalogue(DEFAULT_LANG).get(code)
        if fallback:
            return fallback
    return code
