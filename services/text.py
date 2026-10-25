"""Text helpers for Cyrillic names.

Python's str.casefold() understands Cyrillic; SQLite's LOWER() does not.
"""

import re


def casefold(s):
    """Casefold a string, passing None (and non-strings) through unchanged.

    Registered as the `casefold` SQL function on every connection.
    """
    return s.casefold() if isinstance(s, str) else s


def name_key(s):
    """Key used to detect duplicate names: extra spaces removed, then casefolded.

    "  Пилешко   ФИЛЕ " -> "пилешко филе"
    """
    return " ".join(s.split()).casefold()


# Tags that name a meal or a kind of dish get their own icon (an id in static/icons.svg); others get "tag".
# A tag matches when one of its words starts with a stem, so "закуски" and "бърза закуска" match too.
TAG_ICONS = {
    "sunrise": ("breakfast", "закуск"),
    "sun": ("lunch", "обяд"),
    "moon": ("dinner", "supper", "вечер"),
    "apple": ("snack", "междин"),
    "cake": ("dessert", "sweet", "cake", "десерт", "сладк", "торт"),
    "soup": ("soup", "супа", "супи"),
    "salad": ("salad", "салат"),
}


def tag_icon(name):
    """Icon id for a tag: "Закуска" -> "sunrise", "бързо" -> "tag"."""
    words = name_key(name).split()
    for icon, stems in TAG_ICONS.items():
        if any(word.startswith(stem) for word in words for stem in stems):
            return icon
    return "tag"


STEP_NUMBER = re.compile(r"^\s*(\d+\s*[.)]|[-*•])\s*")


def split_steps(text):
    """Instructions as a list of steps: one per non-empty line, without numbers or bullets typed in front.

    "1. Boil water\n\n2) Add pasta" -> ["Boil water", "Add pasta"]
    """
    return [step for line in text.splitlines() if (step := STEP_NUMBER.sub("", line).strip())]
