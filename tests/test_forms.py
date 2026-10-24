import pytest

from services.forms import (clean_name, format_number, parse_ingredient, parse_number, parse_recipe,
                            parse_source_url, parse_tags, url_host)

UNIT_IDS = {1, 8}  # г, бр.


def fields(**overrides):
    return {"title": "Пиле с ориз", "source_url": "", "servings": "4", "prep_minutes": "", "cook_minutes": "",
            "instructions": "Сварете ориза.", "notes": "", "tags": ""} | overrides


def row(name="", quantity="", unit="", note=""):
    return {"name": name, "quantity": quantity, "unit": unit, "note": note}


def test_clean_name():
    assert clean_name("  Пилешко   филе ") == "Пилешко филе"
    assert clean_name("   ") is None
    assert clean_name(None) is None


@pytest.mark.parametrize("raw, expected", [("200", 200), ("0.5", 0.5), ("0,5", 0.5), (" 1,25 ", 1.25), ("", None)])
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


@pytest.mark.parametrize("raw", ["abc", "1/2", "nan", "inf"])
def test_parse_number_rejects(raw):
    with pytest.raises(ValueError):
        parse_number(raw)


def test_format_number():
    assert format_number(200.0) == "200"
    assert format_number(0.5) == "0.5"
    assert format_number(0.5, ",") == "0,5"
    assert format_number(1 / 3) == "0.333"
    assert format_number(None) == ""


def test_valid_recipe():
    recipe, lines, errors = parse_recipe(
        fields(title="  Пиле  с ориз ", prep_minutes="10", notes="  ", source_url="youtube.com/watch?v=1",
               tags="Обяд, бързо"),
        [row("Пилешко филе", "200", "1", "нарязано"), row(), row("Сол")],
        UNIT_IDS)
    assert errors == {}
    assert recipe == {"title": "Пиле с ориз", "servings": 4, "prep_minutes": 10, "cook_minutes": None,
                      "instructions": "Сварете ориза.", "notes": None,
                      "source_url": "https://youtube.com/watch?v=1", "tags": ["обяд", "бързо"]}
    assert lines == [
        {"name": "Пилешко филе", "quantity": 200, "unit_id": 1, "note": "нарязано"},
        {"name": "Сол", "quantity": None, "unit_id": None, "note": None},
    ]


def test_required_fields():
    _, _, errors = parse_recipe(fields(title=" ", servings="", instructions=""), [row("Сол")], UNIT_IDS)
    assert errors == {"title": "error.required", "servings": "error.required",
                      "instructions": "error.required"}


@pytest.mark.parametrize("field, value, error", [
    ("servings", "0", "error.positive_whole_number"),
    ("servings", "1.5", "error.positive_whole_number"),
    ("prep_minutes", "-5", "error.non_negative_whole_number"),
    ("cook_minutes", "abc", "error.non_negative_whole_number"),
])
def test_bad_whole_numbers(field, value, error):
    _, _, errors = parse_recipe(fields(**{field: value}), [row("Сол")], UNIT_IDS)
    assert errors == {field: error}


@pytest.mark.parametrize("raw, expected", [
    ("", None),
    ("  https://www.youtube.com/watch?v=abc  ", "https://www.youtube.com/watch?v=abc"),
    ("http://blog.bg/пиле-с-ориз", "http://blog.bg/пиле-с-ориз"),
    ("instagram.com/p/xyz", "https://instagram.com/p/xyz"),
])
def test_source_url(raw, expected):
    assert parse_source_url(raw) == (expected, None)


@pytest.mark.parametrize("raw", ["javascript://alert(1)", "ftp://example.com/a", "https://", "две думи"])
def test_bad_source_url(raw):
    assert parse_source_url(raw) == (None, "recipes.error_source_url")
    _, _, errors = parse_recipe(fields(source_url=raw), [row("Сол")], UNIT_IDS)
    assert errors == {"source_url": "recipes.error_source_url"}


def test_url_host():
    assert url_host("https://www.youtube.com/watch?v=1") == "youtube.com"
    assert url_host("https://blog.example.bg/a") == "blog.example.bg"
    assert url_host(None) == ""


def test_parse_tags():
    assert parse_tags(" Закуска,  бързо  хранене ,, ЗАКУСКА, ") == ["закуска", "бързо хранене"]
    assert parse_tags("") == []
    assert parse_tags(None) == []


def test_needs_at_least_one_ingredient():
    _, _, errors = parse_recipe(fields(), [row(), row()], UNIT_IDS)
    assert errors == {"ingredients": "recipes.error_no_ingredients"}


def test_row_errors_are_reported_by_row_index():
    rows = [
        row("Яйца", "2", "8"),                 # ok
        row("", "200", "1"),                   # no name
        row("Мляко", "много", "1"),            # not a number
        row("Мляко", "0", "1"),                # not > 0
        row("Мляко", "200", ""),               # quantity without unit
        row("Мляко", "", "1"),                 # unit without quantity
        row("Мляко", "200", "99"),             # unknown unit
    ]
    _, _, errors = parse_recipe(fields(), rows, UNIT_IDS)
    assert errors == {"rows": {
        1: "recipes.error_row_name",
        2: "error.number",
        3: "error.positive_number",
        4: "recipes.error_quantity_without_unit",
        5: "recipes.error_unit_without_quantity",
        6: "recipes.error_unknown_unit",
    }}


def ingredient_fields(**overrides):
    return {"name": "Яйца", "calories_100g": "143", "protein_100g": "12,6", "carbs_100g": "0.7",
            "fat_100g": "9,5", "grams_per_piece": "55"} | overrides


def test_valid_ingredient():
    name, values, errors = parse_ingredient(ingredient_fields(name="  Яйца  М "))
    assert errors == {}
    assert name == "Яйца М"
    assert values == {"calories_100g": 143, "protein_100g": 12.6, "carbs_100g": 0.7,
                      "fat_100g": 9.5, "grams_per_piece": 55}


def test_ingredient_values_are_optional():
    _, values, errors = parse_ingredient({"name": "Сол"})
    assert errors == {}
    assert values == {"calories_100g": None, "protein_100g": None, "carbs_100g": None,
                      "fat_100g": None, "grams_per_piece": None}


def test_zero_macros_are_allowed():
    _, values, errors = parse_ingredient(ingredient_fields(carbs_100g="0", fat_100g="0,0"))
    assert errors == {}
    assert (values["carbs_100g"], values["fat_100g"]) == (0, 0)


@pytest.mark.parametrize("field, value, error", [
    ("name", "  ", "error.required"),
    ("calories_100g", "много", "error.number"),
    ("protein_100g", "-1", "error.non_negative_number"),
    ("grams_per_piece", "0", "error.positive_number"),
    ("grams_per_piece", "-5", "error.positive_number"),
])
def test_bad_ingredient_fields(field, value, error):
    _, _, errors = parse_ingredient(ingredient_fields(**{field: value}))
    assert errors == {field: error}


def test_protein_carbs_fat_cannot_exceed_100g():
    _, _, errors = parse_ingredient(ingredient_fields(protein_100g="50", carbs_100g="40", fat_100g="10,1"))
    assert errors == {"macros": "ingredients.error_macros_over_100"}
    _, _, errors = parse_ingredient(ingredient_fields(protein_100g="33.3", carbs_100g="33.3", fat_100g="33.4"))
    assert errors == {}
