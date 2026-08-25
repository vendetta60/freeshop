"""Admin-editable site settings (plan.md 7.3, 8).

A single key/value table rather than columns: contacts, appearance, default
language and page copy all change without a migration, which is the whole
point of letting the admin edit them.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# Every key the application reads, with its default. Seeding from this dict
# means a fresh install is never missing a setting, and the list doubles as
# documentation of what the admin panel must expose.
DEFAULT_SETTINGS: dict[str, Any] = {
    # --- contact (plan.md 18/W5) ---
    "contact_phone": "+994 50 000 00 42",
    "whatsapp": "994500000042",
    "telegram": "@example_az",
    "email": "salam@example.az",
    "address_az": "Bakı, Nizami küçəsi 1, Azərbaycan",
    "address_en": "1 Nizami Street, Baku, Azerbaijan",
    "working_hours_az": "Hər gün 10:00 — 19:00",
    "working_hours_en": "Every day 10:00 — 19:00",
    "socials": {"instagram": "", "facebook": ""},
    # --- appearance (plan.md 3.2) ---
    "accent": "azure",
    "default_theme": "system",
    # --- language (plan.md 7.3) ---
    "default_lang": "az",
    "enabled_langs": ["az", "en"],
    # --- page copy ---
    "hero_title_az": "Seçilmiş məhsullar, birbaşa satıcıdan",
    "hero_title_en": "Curated products, straight from the seller",
    "hero_subtitle_az": (
        "Kataloqa baxın, bəyəndiklərinizi səbətə yığın və bir sorğu ilə satıcı ilə "
        "əlaqə saxlayın. Ödəniş yoxdur — sadəcə birbaşa əlaqə."
    ),
    "hero_subtitle_en": (
        "Browse the catalogue, build a basket, and reach the seller with a single "
        "request. No payment — just a direct conversation."
    ),
    "about_az": "",
    "about_en": "",
    "contact_intro_az": "Məhsul haqqında sualınız var? Bizə yazın və ya zəng edin.",
    "contact_intro_en": "Questions about a product? Message or call us.",
    "footer_note_az": "Ödəniş sistemi yoxdur — sifariş sorğusu göndərin.",
    "footer_note_en": "No payment system — send an order request.",
}


class Setting(Base, TimestampMixin):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=False)
