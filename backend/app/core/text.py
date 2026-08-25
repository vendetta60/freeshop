"""Search-text normalisation.

Azerbaijani is routinely typed without diacritics - "ketan" for "kətan",
"gozellik" for "gözəllik" - so a search that only matches exact characters
misses most real queries.

SQLite's LIKE cannot fold ə -> e, and its FTS5 tokenizers do not know
Azerbaijani. So we store a folded copy of the searchable text alongside the
real one and match against that. The same function normalises the needle, so
both sides are folded identically.
"""

from __future__ import annotations

import re
import unicodedata

# Characters Unicode NFD does not decompose, or decomposes wrongly for our
# purposes. 'ə' (U+0259) has no decomposition at all, and 'ı' must fold to
# 'i' rather than being dropped.
_EXPLICIT = str.maketrans(
    {
        "ə": "e",
        "Ə": "e",
        "ı": "i",
        "İ": "i",
        "ğ": "g",
        "Ğ": "g",
        "ş": "s",
        "Ş": "s",
        "ç": "c",
        "Ç": "c",
        "ö": "o",
        "Ö": "o",
        "ü": "u",
        "Ü": "u",
    }
)


def normalise_search(text: str | None) -> str:
    """Fold to lowercase ASCII-ish text for matching.

    >>> normalise_search("Kətan köynək")
    'ketan koynek'
    >>> normalise_search("GÖZƏLLİK")
    'gozellik'
    """
    if not text:
        return ""
    folded = text.translate(_EXPLICIT).lower()
    # Strip any remaining combining marks (é -> e) for imported text.
    decomposed = unicodedata.normalize("NFD", folded)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", stripped)


def build_search_text(*parts: str | None) -> str:
    """Join and fold every searchable field of a record."""
    return normalise_search(" ".join(part for part in parts if part))


def slugify(text: str, *, fallback: str = "element") -> str:
    """URL slug from Azerbaijani text.

    Reuses the same folding as search, so "Kətan köynək" and a later search
    for "ketan koynek" agree on what the characters are.

    >>> slugify("Qoz ağacından jurnal masası")
    'qoz-agacindan-jurnal-masasi'
    """
    folded = re.sub(r"[^a-z0-9]+", "-", normalise_search(text)).strip("-")
    return folded[:120] or fallback
