from services.text import casefold, name_key, split_steps, tag_icon


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


def test_tag_icon_meals_in_both_languages():
    assert tag_icon("Закуска") == tag_icon("breakfast") == "sunrise"
    assert tag_icon("обяд") == tag_icon("Lunch") == "sun"
    assert tag_icon("ВЕЧЕРЯ") == tag_icon("dinner") == "moon"


def test_tag_icon_matches_any_word_and_word_forms():
    assert tag_icon("бърза закуска") == "sunrise"
    assert tag_icon("десерти") == "cake"


def test_tag_icon_other_tags():
    assert tag_icon("бързо") == "tag"
    assert tag_icon("оризова") == "tag"   # a stem only matches at the start of a word


def test_split_steps_drops_empty_lines_and_typed_numbers():
    text = "1. Сварете водата\n\n2) Добавете пастата  \n  - Посолете\r\nСервирайте"
    assert split_steps(text) == ["Сварете водата", "Добавете пастата", "Посолете", "Сервирайте"]


def test_split_steps_keeps_numbers_inside_a_step():
    assert split_steps("200 g flour") == ["200 g flour"]
    assert split_steps("") == []
