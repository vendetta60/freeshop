"""Azerbaijani place gazetteer (FreeShop_Prompt 1, Rule B).

WHY A STATIC TABLE AND NOT A GEOCODER:
the alternatives are all worse for this application. A geocoding API is an
external paid dependency in the critical path, which plan.md 1 forbids
outright. Asking the browser for coordinates hands the server somebody's
actual doorstep, which Rule B forbids. Storing nothing at all leaves the
nearby sort with nothing to sort by.

So a place name is resolved to the CENTROID of that city or district, from
this table. Everyone in Lənkəran shares one coordinate pair. That is not an
approximation we tolerate - it is the privacy property: no row in this
database can locate a person more precisely than "somewhere in their town",
because no more precise number was ever collected.

The coordinates are town centres to about a kilometre, which is well inside
the precision the 5 km radius option needs. Names are stored FOLDED (see
app.core.text.normalise_search), so "Lenkeran", "lənkəran" and "LƏNKƏRAN"
all resolve.
"""

from __future__ import annotations

from app.core.text import normalise_search

# name (as displayed) -> (region, latitude, longitude)
#
# `region` is the economic region the place sits in. It is carried so a
# listing can say "Lənkəran" and still be grouped sensibly when a wider view
# is wanted, without a second lookup table.
CITIES: dict[str, tuple[str, float, float]] = {
    # --- Bakı and the Absheron peninsula ---
    "Bakı": ("Bakı", 40.4093, 49.8671),
    "Sumqayıt": ("Bakı", 40.5892, 49.6683),
    "Xırdalan": ("Bakı", 40.4522, 49.7561),
    "Xızı": ("Bakı", 40.9111, 49.0736),
    # --- Gəncə-Qazax ---
    "Gəncə": ("Gəncə-Qazax", 40.6828, 46.3606),
    "Naftalan": ("Gəncə-Qazax", 40.5069, 46.8231),
    "Goranboy": ("Gəncə-Qazax", 40.6103, 46.7883),
    "Samux": ("Gəncə-Qazax", 40.7642, 46.4083),
    "Şəmkir": ("Gəncə-Qazax", 40.8294, 46.0175),
    "Tovuz": ("Gəncə-Qazax", 40.9917, 45.6169),
    "Ağstafa": ("Gəncə-Qazax", 41.1189, 45.4531),
    "Qazax": ("Gəncə-Qazax", 41.0928, 45.3661),
    "Gədəbəy": ("Gəncə-Qazax", 40.5697, 45.8156),
    "Daşkəsən": ("Gəncə-Qazax", 40.5203, 46.0817),
    # --- Şəki-Zaqatala ---
    "Şəki": ("Şəki-Zaqatala", 41.1919, 47.1706),
    "Zaqatala": ("Şəki-Zaqatala", 41.6317, 46.6444),
    "Balakən": ("Şəki-Zaqatala", 41.7236, 46.4058),
    "Qax": ("Şəki-Zaqatala", 41.4211, 46.9294),
    "Oğuz": ("Şəki-Zaqatala", 41.0722, 47.4544),
    # --- Quba-Xaçmaz ---
    "Quba": ("Quba-Xaçmaz", 41.3606, 48.5128),
    "Qusar": ("Quba-Xaçmaz", 41.4275, 48.4300),
    "Xaçmaz": ("Quba-Xaçmaz", 41.4589, 48.8022),
    "Şabran": ("Quba-Xaçmaz", 41.2211, 48.9944),
    "Siyəzən": ("Quba-Xaçmaz", 41.0781, 49.1119),
    # --- Dağlıq Şirvan ---
    "Şamaxı": ("Dağlıq Şirvan", 40.6314, 48.6414),
    "İsmayıllı": ("Dağlıq Şirvan", 40.7897, 48.1519),
    "Qəbələ": ("Dağlıq Şirvan", 40.9819, 47.8456),
    "Ağsu": ("Dağlıq Şirvan", 40.5700, 48.4014),
    "Qobustan": ("Dağlıq Şirvan", 40.5333, 48.9278),
    # --- Aran ---
    "Mingəçevir": ("Aran", 40.7700, 47.0489),
    "Şirvan": ("Aran", 39.9319, 48.9203),
    "Yevlax": ("Aran", 40.6172, 47.1500),
    "Bərdə": ("Aran", 40.3744, 47.1264),
    "Ağdaş": ("Aran", 40.6503, 47.4747),
    "Göyçay": ("Aran", 40.6531, 47.7406),
    "Ucar": ("Aran", 40.5164, 47.6478),
    "Zərdab": ("Aran", 40.2192, 47.7078),
    "Kürdəmir": ("Aran", 40.3494, 48.1614),
    "Hacıqabul": ("Aran", 40.0397, 48.9186),
    "Sabirabad": ("Aran", 39.9878, 48.4694),
    "Salyan": ("Aran", 39.5958, 48.9797),
    "Neftçala": ("Aran", 39.3831, 49.2447),
    "Biləsuvar": ("Aran", 39.4589, 48.5478),
    "İmişli": ("Aran", 39.8697, 48.0658),
    "Beyləqan": ("Aran", 39.7728, 47.6153),
    "Ağcabədi": ("Aran", 40.0531, 47.4581),
    "Tərtər": ("Aran", 40.3444, 46.9319),
    # --- Lənkəran ---
    "Lənkəran": ("Lənkəran", 38.7529, 48.8475),
    "Astara": ("Lənkəran", 38.4558, 48.8756),
    "Masallı": ("Lənkəran", 39.0342, 48.6647),
    "Cəlilabad": ("Lənkəran", 39.2094, 48.5133),
    "Lerik": ("Lənkəran", 38.7736, 48.4153),
    "Yardımlı": ("Lənkəran", 38.9058, 48.2450),
    # --- Naxçıvan ---
    "Naxçıvan": ("Naxçıvan", 39.2089, 45.4122),
    "Ordubad": ("Naxçıvan", 38.9033, 46.0244),
    "Culfa": ("Naxçıvan", 38.9542, 45.6300),
    "Şərur": ("Naxçıvan", 39.5533, 44.9847),
    "Şahbuz": ("Naxçıvan", 39.4058, 45.5744),
    "Kəngərli": ("Naxçıvan", 39.3789, 45.1400),
    "Sədərək": ("Naxçıvan", 39.7100, 44.8858),
    "Babək": ("Naxçıvan", 39.1522, 45.4550),
    # --- Qarabağ / Şərqi Zəngəzur ---
    "Xankəndi": ("Qarabağ", 39.8153, 46.7519),
    "Şuşa": ("Qarabağ", 39.7597, 46.7503),
    "Ağdam": ("Qarabağ", 39.9931, 46.9294),
    "Füzuli": ("Qarabağ", 39.6014, 47.1436),
    "Xocalı": ("Qarabağ", 39.9128, 46.7942),
    "Laçın": ("Şərqi Zəngəzur", 39.6383, 46.5497),
    "Kəlbəcər": ("Şərqi Zəngəzur", 40.1053, 46.0378),
    "Cəbrayıl": ("Şərqi Zəngəzur", 39.3994, 47.0264),
    "Zəngilan": ("Şərqi Zəngəzur", 39.0833, 46.6522),
    "Qubadlı": ("Şərqi Zəngəzur", 39.3453, 46.5817),
}

# Districts inside Bakı. They are a separate table because they resolve
# WITHIN a city: a listing in Xətai and one in Qaradağ are 40 km apart, and
# treating both as "Bakı, 40.4093" would put half the capital's listings at
# the same false distance from each other.
DISTRICTS: dict[str, dict[str, tuple[float, float]]] = {
    "Bakı": {
        "Səbail": (40.3667, 49.8358),
        "Nəsimi": (40.3894, 49.8375),
        "Yasamal": (40.3819, 49.8047),
        "Nərimanov": (40.4058, 49.8631),
        "Nizami": (40.4139, 49.8878),
        "Xətai": (40.3822, 49.9053),
        "Binəqədi": (40.4611, 49.8236),
        "Sabunçu": (40.4550, 49.9483),
        "Suraxanı": (40.4128, 49.9950),
        "Xəzər": (40.4400, 50.1450),
        "Qaradağ": (40.2333, 49.5333),
        "Pirallahı": (40.4736, 50.3300),
    },
}

# Folded lookups, built once at import. The folded key is what a user's typing
# is compared against, so "lenkeran" finds "Lənkəran".
CITY_INDEX: dict[str, str] = {normalise_search(name): name for name in CITIES}
DISTRICT_INDEX: dict[str, dict[str, str]] = {
    city: {normalise_search(name): name for name in districts}
    for city, districts in DISTRICTS.items()
}
