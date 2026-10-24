"""UI texts in every supported language.

Both dictionaries must have exactly the same keys (checked by a test).
Keys are grouped by prefix: nav., btn., label., msg., day., meal., and one prefix per page.
"""

TEXTS = {
    "en": {
        "nav.recipes": "Recipes",
        "nav.ingredients": "Ingredients",
        "nav.menus": "Menus",
        "nav.language": "Language",

        "home.title": "Hello!",
        "home.cyrillic_check": "If the Bulgarian text below looks right, Cyrillic works:",
    },
    "bg": {
        "nav.recipes": "Рецепти",
        "nav.ingredients": "Съставки",
        "nav.menus": "Менюта",
        "nav.language": "Език",

        "home.title": "Здравей!",
        "home.cyrillic_check": "Ако текстът по-долу се вижда правилно, кирилицата работи:",
    },
}
