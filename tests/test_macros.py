import pytest

from services.macros import line_grams, recipe_macros

# Grams of the starting units (see migrations/0001_initial.sql); None = a piece unit (бр.)
G, KG, ML, TBSP, CUP, PIECE = 1, 1000, 1, 15, 200, None

CHICKEN = {"ingredient_id": 1, "name": "Пилешко филе", "grams_per_piece": None,
           "calories_100g": 110, "protein_100g": 23, "carbs_100g": 0, "fat_100g": 1.5}
EGGS = {"ingredient_id": 2, "name": "Яйца", "grams_per_piece": 55,
        "calories_100g": 143, "protein_100g": 12.6, "carbs_100g": 0.7, "fat_100g": 9.5}
OIL = {"ingredient_id": 3, "name": "Зехтин", "grams_per_piece": None,
       "calories_100g": None, "protein_100g": None, "carbs_100g": None, "fat_100g": None}
SALT = {"ingredient_id": 4, "name": "Сол", "grams_per_piece": None,
        "calories_100g": None, "protein_100g": None, "carbs_100g": None, "fat_100g": None}


def line(ingredient, quantity, unit_grams, **overrides):
    return {**ingredient, "quantity": quantity, "unit_grams": unit_grams, **overrides}


@pytest.mark.parametrize("quantity, unit_grams, expected", [
    (200, G, 200), (0.5, KG, 500), (250, ML, 250), (2, TBSP, 30), (1.5, CUP, 300),
])
def test_grams_from_unit(quantity, unit_grams, expected):
    assert line_grams(line(CHICKEN, quantity, unit_grams)) == expected


def test_grams_from_pieces():
    assert line_grams(line(EGGS, 2, PIECE)) == 110


def test_grams_unknown_without_grams_per_piece():
    assert line_grams(line(CHICKEN, 2, PIECE)) is None


def test_unit_grams_win_over_grams_per_piece():
    assert line_grams(line(EGGS, 100, G)) == 100


def test_grams_unknown_without_quantity():
    assert line_grams(line(SALT, None, None)) is None


def test_example_from_the_docs():
    # 200 г пилешко филе + 2 бр. яйца: 220 + 157.3 kcal
    result = recipe_macros([line(CHICKEN, 200, G), line(EGGS, 2, PIECE)], servings=1)
    assert result["total"]["calories"] == pytest.approx(377.3)
    assert result["total"]["protein"] == pytest.approx(46 + 13.86)
    assert result["incomplete"] == []


def test_per_serving():
    result = recipe_macros([line(CHICKEN, 400, G)], servings=4)
    assert result["total"]["calories"] == pytest.approx(440)
    assert result["per_serving"] == pytest.approx({"calories": 110, "protein": 23, "carbs": 0, "fat": 1.5})


def test_lines_without_quantity_are_skipped_silently():
    result = recipe_macros([line(CHICKEN, 100, G), line(SALT, None, None)], servings=1)
    assert result["total"]["calories"] == pytest.approx(110)
    assert result["incomplete"] == []


def test_missing_macros_give_a_partial_total():
    result = recipe_macros([line(CHICKEN, 100, G), line(OIL, 2, TBSP)], servings=1)
    assert result["total"]["calories"] == pytest.approx(110)
    assert result["incomplete"] == [
        {"ingredient_id": 3, "name": "Зехтин", "missing": ["calories", "protein", "carbs", "fat"]}]


def test_one_missing_macro_only_affects_that_macro():
    no_fat = {**CHICKEN, "fat_100g": None}
    result = recipe_macros([line(no_fat, 100, G)], servings=1)
    assert result["total"] == pytest.approx({"calories": 110, "protein": 23, "carbs": 0, "fat": None})
    assert result["incomplete"][0]["missing"] == ["fat"]


def test_missing_grams_per_piece():
    result = recipe_macros([line(CHICKEN, 2, PIECE)], servings=2)
    assert result["total"] == {"calories": None, "protein": None, "carbs": None, "fat": None}
    assert result["per_serving"] == result["total"]
    assert result["incomplete"] == [{"ingredient_id": 1, "name": "Пилешко филе", "missing": ["grams_per_piece"]}]


def test_an_ingredient_is_listed_once():
    no_fat = {**CHICKEN, "fat_100g": None}
    result = recipe_macros([line(no_fat, 100, G), line(no_fat, 1, PIECE)], servings=1)
    assert result["incomplete"] == [
        {"ingredient_id": 1, "name": "Пилешко филе", "missing": ["fat", "grams_per_piece"]}]


def test_zero_is_data_not_missing():
    result = recipe_macros([line(CHICKEN, 100, G)], servings=1)
    assert result["total"]["carbs"] == 0


def test_no_lines():
    result = recipe_macros([], servings=1)
    assert result["total"] == {"calories": None, "protein": None, "carbs": None, "fat": None}
    assert result["incomplete"] == []
