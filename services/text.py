"""Text helpers for Cyrillic names.

Python's str.casefold() understands Cyrillic; SQLite's LOWER() does not.
"""


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
