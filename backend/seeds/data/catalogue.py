"""Curated demo fixtures (plan.md 8.1.4, 8.1.5).

Real Azerbaijani text, not lorem: lorem hides exactly the bugs this data
exists to expose - diacritic rendering, real word lengths against the 2-line
clamp, and price alignment under tabular numerals.

Photography is hotlinked from Unsplash's CDN. Every photo was downloaded and
visually checked against its title before being listed here; photo IDs are
opaque, so wiring one in without looking at it is guesswork.
"""

from __future__ import annotations

from typing import TypedDict


def photo(photo_id: str, width: int, height: int) -> str:
    return f"https://images.unsplash.com/{photo_id}?w={width}&h={height}&q=75&auto=format&fit=crop"


class CategorySeed(TypedDict):
    slug: str
    name_az: str
    name_en: str
    children: list[dict[str, str]]


# Eight parents x three children, exactly two levels (plan.md D11).
CATEGORIES: list[CategorySeed] = [
    {
        "slug": "elektronika",
        "name_az": "Elektronika",
        "name_en": "Electronics",
        "children": [
            {"slug": "telefonlar", "name_az": "Telefonlar", "name_en": "Phones"},
            {"slug": "noutbuklar", "name_az": "Noutbuklar", "name_en": "Laptops"},
            {"slug": "audio", "name_az": "Audio", "name_en": "Audio"},
        ],
    },
    {
        "slug": "ev-ve-bagca",
        "name_az": "Ev və bağça",
        "name_en": "Home & Garden",
        "children": [
            {"slug": "mebel", "name_az": "Mebel", "name_en": "Furniture"},
            {"slug": "isiqlandirma", "name_az": "İşıqlandırma", "name_en": "Lighting"},
            {"slug": "metbex", "name_az": "Mətbəx", "name_en": "Kitchen"},
        ],
    },
    {
        "slug": "geyim",
        "name_az": "Geyim",
        "name_en": "Clothing",
        "children": [
            {"slug": "kisi", "name_az": "Kişi", "name_en": "Men"},
            {"slug": "qadin", "name_az": "Qadın", "name_en": "Women"},
            {"slug": "ayaqqabi", "name_az": "Ayaqqabı", "name_en": "Shoes"},
        ],
    },
    {
        "slug": "gozellik",
        "name_az": "Gözəllik",
        "name_en": "Beauty",
        "children": [
            {"slug": "deri-baximi", "name_az": "Dəri baxımı", "name_en": "Skincare"},
            {"slug": "etir", "name_az": "Ətir", "name_en": "Fragrance"},
            {"slug": "sac", "name_az": "Saç", "name_en": "Hair"},
        ],
    },
    {
        "slug": "idman",
        "name_az": "İdman",
        "name_en": "Sports",
        "children": [
            {"slug": "fitnes", "name_az": "Fitnes", "name_en": "Fitness"},
            {"slug": "velosiped", "name_az": "Velosiped", "name_en": "Cycling"},
            {"slug": "turizm", "name_az": "Turizm", "name_en": "Outdoor"},
        ],
    },
    {
        "slug": "usaq",
        "name_az": "Uşaq",
        "name_en": "Kids",
        "children": [
            {"slug": "oyuncaqlar", "name_az": "Oyuncaqlar", "name_en": "Toys"},
            {"slug": "korpe", "name_az": "Körpə", "name_en": "Baby"},
            {"slug": "mekteb", "name_az": "Məktəb", "name_en": "School"},
        ],
    },
    {
        "slug": "dekorasiya",
        "name_az": "Dekorasiya",
        "name_en": "Decor",
        "children": [
            {"slug": "suvenir", "name_az": "Suvenir", "name_en": "Souvenirs"},
            {"slug": "divar-dekoru", "name_az": "Divar dekoru", "name_en": "Wall decor"},
            {"slug": "kitab", "name_az": "Kitab", "name_en": "Books"},
        ],
    },
    {
        "slug": "tekstil",
        "name_az": "Tekstil",
        "name_en": "Textiles",
        # Deliberately EMPTY: exercises the empty-category state and the
        # 9.5 delete rule (plan.md 8.1.4).
        "children": [],
    },
]


class ProductSeed(TypedDict, total=False):
    slug: str
    title_az: str
    title_en: str | None
    description_az: str
    description_en: str | None
    price_minor: int
    old_price_minor: int | None
    category: str
    stock_status: str
    is_featured: bool
    images: list[tuple[str, int, int]]


# Each entry earns its place: the set carries the named edge cases from
# plan.md 8.1.5 rather than twelve interchangeable rows.
#
# The copy is what a neighbour actually writes when they pass something on -
# why they no longer need it, what is wrong with it, and whether you have to
# collect it. Shop copy ("finished with natural oil, resists marks") described
# a product nobody on this board is selling, and made the seeded catalogue
# read like the storefront this stopped being (plan.md 13.7).
#
# Ten of the twelve are free, which is the ratio the real board should have.
PRODUCTS: list[ProductSeed] = [
    {
        # Edge case: 80-character title with diacritics -> 2-line clamp.
        "slug": "qoz-agacindan-jurnal-masasi",
        "title_az": "Qoz ağacından əl işi jurnal masası, yumşaq kətan örtüklü oturacaqla birlikdə",
        "title_en": "Handmade walnut coffee table with a linen-topped stool",
        "description_az": (
            "Nənəmdən qalıb, evi dəyişəndə yeni mənzilə sığmadı. Masiv qoz ağacıdır, "
            "ağırdır - maşınla gəlin. Səthində bir neçə cızıq var, ayaqları möhkəmdir. "
            "Dəstdəki oturacaq da birlikdə gedir."
        ),
        "description_en": (
            "It was my grandmother's and it does not fit the new flat. Solid walnut and "
            "heavy, so bring a car. A few scratches on the top, legs are sound. The "
            "matching stool goes with it."
        ),
        "price_minor": 0,
        "category": "mebel",
        "is_featured": True,
        "images": [("photo-1550581190-9c1c48d21d6c", 1200, 800)],
    },
    {
        "slug": "mis-asma-chiraq",
        "title_az": "Mis asma çıraq, üç ədədlik dəst",
        "title_en": "Copper pendant lamp, set of three",
        "description_az": (
            "Mətbəxi təmir etdik, yeni çıraqlar aldıq, bunlar qaldı. Üçü də işləyir, "
            "E27 patrondur. Lampalar daxil deyil."
        ),
        "price_minor": 0,
        "category": "isiqlandirma",
        "is_featured": True,
        "images": [("photo-1540932239986-30128078f3c5", 800, 1200)],
    },
    {
        # Edge cases: 9-character title AND out_of_stock - here that means
        # somebody has already come for it.
        "slug": "divar-saati",
        "title_az": "Divar saatı",
        "title_en": "Wall clock",
        "description_az": "Ağac korpus, səssiz mexanizm. Batareya ilə işləyir.",
        "price_minor": 0,
        "category": "divar-dekoru",
        "stock_status": "out_of_stock",
        "images": [("photo-1533090161767-e6ffed986c88", 1000, 1000)],
    },
    {
        "slug": "ketan-yastiq-desti",
        "title_az": "Kətan yastıq dəsti, 2 ədəd",
        # Edge case: NO English translation -> must fall back to AZ.
        "title_en": None,
        "description_az": (
            "Divanı dəyişdik, rəngi uyğun gəlmədi. Yuyulub, ləkəsi yoxdur. 45×45 sm."
        ),
        "price_minor": 0,
        "category": "tekstil",
        "is_featured": True,
        "images": [("photo-1567016432779-094069958ea5", 1200, 900)],
    },
    {
        # Edge case: the highest price on the board -> tabular-nums column
        # alignment. A token price, not a shop price: the board allows asking
        # for something, it just does not expect it.
        "slug": "palid-kitab-refi",
        "title_az": "Palıd ağacından kitab rəfi, üç bölməli",
        "title_en": "Three-bay oak bookshelf",
        "description_az": (
            "Ofisi bağladıq, rəf qaldı. Masiv palıd, divara bərkidilir, hündürlüyü "
            "180 sm. Sökülmüş haldadır, bütün vintlər var. Daşınma xərci üçün simvolik "
            "məbləğ istəyirəm."
        ),
        "price_minor": 25000,
        "category": "mebel",
        "images": [("photo-1513475382585-d06e58bcb0e0", 900, 1200)],
    },
    {
        # Edge case: third stock status.
        "slug": "polaroid-ani-kamera",
        "title_az": "Polaroid ani kamera",
        "title_en": "Polaroid instant camera",
        "description_az": (
            "Telefonla çəkirəm, kamera bir ildir şkafdadır. İşləyir, film ayrıca "
            "alınmalıdır. Növbəti həftə şəhərdə olacağam, onda götürə bilərsiniz."
        ),
        "price_minor": 0,
        "category": "audio",
        "stock_status": "on_order",
        "images": [("photo-1526170375885-4d8ecf77b99f", 1000, 1000)],
    },
    {
        # Edge case: multiple images -> gallery with a thumbnail strip.
        "slug": "mexmer-divan",
        "title_az": "Məxmər üçyerlik divan, zümrüd yaşıl",
        "title_en": "Emerald velvet three-seat sofa",
        "description_az": (
            "Köçürük, divan yeni evə sığmır. Bir küncündə pişik cızığı var, şəkildə "
            "göründüyü kimi. Yastıq üzləri çıxarılıb yuyulur. Özünüz qaldırmalısınız - "
            "üçüncü mərtəbə, lift yoxdur."
        ),
        "price_minor": 0,
        "category": "mebel",
        "is_featured": True,
        "images": [
            ("photo-1555041469-a586c61ea9bc", 1400, 900),
            ("photo-1567538096630-e0c55bd6374c", 1000, 1250),
            ("photo-1519710164239-da123dc03ef4", 1200, 800),
        ],
    },
    {
        # Edge case: NO image at all -> placeholder, never a broken <img>.
        "slug": "yun-xalca",
        "title_az": "Əl toxuması yun xalça, 120×180 sm",
        "title_en": "Handwoven wool rug, 120×180 cm",
        "description_az": (
            "Şəkil çəkə bilmirəm, telefonun kamerası sınıb. Yun xalçadır, təbii boya, "
            "bir küncü azca solub. Gəlib baxa bilərsiniz."
        ),
        "price_minor": 0,
        "category": "tekstil",
        "images": [],
    },
    {
        "slug": "divar-refi",
        "title_az": "Divar rəfi, altı bölməli",
        "title_en": "Six-compartment wall shelf",
        "description_az": "Şam ağacı. Divardan çıxarılıb, dübelləri də verirəm.",
        "price_minor": 0,
        "category": "mebel",
        "images": [("photo-1595428774223-ef52624120d2", 900, 1100)],
    },
    {
        # Edge cases: the lowest non-zero price (0.50) AND a tiny 400x400
        # source image. Kept priced so the board proves it can render both a
        # real price and "Pulsuz" side by side.
        "slug": "bar-ketili",
        "title_az": "Ağac bar kətili",
        "title_en": "Wooden bar stool",
        "description_az": "Hündürlüyü 65 sm. Bir ayağı azca laxlayır, vint bərkidilməlidir.",
        "price_minor": 50,
        "category": "mebel",
        "images": [("photo-1503602642458-232111445657", 400, 400)],
    },
    {
        # Edge case: 900+ character description -> detail-page overflow.
        "slug": "krem-kreslo",
        "title_az": "Krem rəngli klassik kreslo",
        "title_en": "Cream classic armchair",
        "description_az": (
            "Bu kresloları cütlükdə almışdıq, biri qalıb. Otağı uşaq üçün hazırlayırıq "
            "və yer çatmır, ona görə pulsuz verirəm. Karkas bərk ağacdandır, heç yeri "
            "laxlamır - oturanda səs çıxarmır. Üzü sıx pambıq qarışığıdır; açıq rəng "
            "olduğu üçün oturacaq hissəsində zamanla açılmış bir ləkə var, şəkildə "
            "görünür, amma uzaqdan seçilmir. Kimyəvi təmizləmə ilə çıxa bilər, mən "
            "sınamamışam. Ayaqları masivdir, altlıqlarına keçə vurulub, parketi "
            "cızmır. Ölçüləri: en 78 sm, dərinlik 82 sm, hündürlük 96 sm - qapıdan "
            "keçmək üçün ayaqlarını açmaq lazım gələ bilər, açar var. Şənbə və bazar "
            "günləri evdəyəm, digər günlər axşam saat altıdan sonra. Özünüz "
            "götürməlisiniz, mənim maşınım yoxdur."
        ),
        "price_minor": 0,
        "category": "mebel",
        "images": [("photo-1567538096630-e0c55bd6374c", 1000, 1250)],
    },
    {
        "slug": "ketan-koynek",
        "title_az": "Kətan köynək, nanə yaşılı",
        "title_en": "Linen shirt, mint green",
        "description_az": "Ölçü M. Bir dəfə geyinilib, mənə kiçik gəldi. Yuyulub.",
        "price_minor": 0,
        "category": "kisi",
        "images": [("photo-1523381210434-271e8be1f52b", 1200, 800)],
    },
]
