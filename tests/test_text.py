from services.text import casefold, name_key


def test_name_key_trims_collapses_spaces_and_casefolds():
    assert name_key("  Пилешко   ФИЛЕ ") == "пилешко филе"


def test_name_key_same_for_different_case():
    assert name_key("Яйца") == name_key("яйца") == name_key("ЯЙЦА")


def test_name_key_tabs_and_newlines_count_as_spaces():
    assert name_key("Зехтин\t extra\nвирджин") == "зехтин extra вирджин"


def test_name_key_latin():
    assert name_key("Olive  OIL") == "olive oil"


def test_casefold_cyrillic():
    assert casefold("ЩЪРКЕЛ Ю Я") == "щъркел ю я"


def test_casefold_passes_none_and_numbers_through():
    assert casefold(None) is None
    assert casefold(5) == 5
