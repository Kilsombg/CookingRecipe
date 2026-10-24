import pytest

from services.shopping_list import build_shopping_list

# Unit ids and labels of some starting units (see migrations/0001_initial.sql)
G, KG, TBSP, PIECE = (1, "г"), (2, "кг"), (6, "с.л."), (8, "бр.")


def line(ingredient_id, name, quantity=None, unit=(None, None)):
    return {"ingredient_id": ingredient_id, "name": name, "quantity": quantity, "unit_id": unit[0], "unit": unit[1]}


def item(recipe_id, servings, recipe_servings):
    return {"recipe_id": recipe_id, "servings": servings, "recipe_servings": recipe_servings}


def entries(result):
    return [(e["name"], e["quantity"], e["unit"]) for e in result]


def test_empty_menu():
    assert build_shopping_list([], {}) == []


def test_same_ingredient_and_unit_are_added_up():
    lines = {1: [line(1, "Пилешко филе", 300, G)], 2: [line(1, "Пилешко филе", 200, G)]}
    assert entries(build_shopping_list([item(1, 2, 2), item(2, 2, 2)], lines)) == [("Пилешко филе", 500, "г")]


def test_same_recipe_twice_is_added_up():
    lines = {1: [line(2, "Яйца", 2, PIECE)]}
    assert entries(build_shopping_list([item(1, 1, 1), item(1, 1, 1)], lines)) == [("Яйца", 4, "бр.")]


def test_different_units_stay_separate():
    lines = {1: [line(1, "Пилешко филе", 500, G)], 2: [line(1, "Пилешко филе", 1, KG)]}
    assert entries(build_shopping_list([item(1, 1, 1), item(2, 1, 1)], lines)) == [
        ("Пилешко филе", 500, "г"), ("Пилешко филе", 1, "кг")]


@pytest.mark.parametrize("servings, recipe_servings, expected", [
    (4, 2, 400), (1, 2, 100), (3, 4, 150), (2, 2, 200),
])
def test_quantities_are_scaled_by_servings(servings, recipe_servings, expected):
    lines = {1: [line(1, "Ориз", 200, G)]}
    [entry] = build_shopping_list([item(1, servings, recipe_servings)], lines)
    assert entry["quantity"] == pytest.approx(expected)


def test_each_item_is_scaled_on_its_own():
    # 2 tbsp for 2 servings, cooked for 1 and for 6: 1 + 6 = 7 tbsp
    lines = {1: [line(3, "Зехтин", 2, TBSP)]}
    [entry] = build_shopping_list([item(1, 1, 2), item(1, 6, 2)], lines)
    assert entry["quantity"] == pytest.approx(7)


def test_no_quantity_is_listed_once_without_a_quantity():
    lines = {1: [line(4, "Сол")], 2: [line(4, "Сол")]}
    assert entries(build_shopping_list([item(1, 1, 1), item(2, 3, 1)], lines)) == [("Сол", None, None)]


def test_no_quantity_is_dropped_when_the_ingredient_is_also_needed_with_one():
    lines = {1: [line(5, "Магданоз")], 2: [line(5, "Магданоз", 20, G)]}
    assert entries(build_shopping_list([item(1, 1, 1), item(2, 1, 1)], lines)) == [("Магданоз", 20, "г")]


def test_matching_is_by_ingredient_not_by_name():
    # Two catalogue ingredients can't share a name, but a renamed one keeps its id
    lines = {1: [line(1, "Яйца", 2, PIECE)], 2: [line(1, "яйца", 3, PIECE)]}
    assert entries(build_shopping_list([item(1, 1, 1), item(2, 1, 1)], lines)) == [("Яйца", 5, "бр.")]


def test_sorted_by_name_ignoring_case():
    lines = {1: [line(1, "яйца", 2, PIECE), line(2, "Ориз", 200, G), line(3, "Брашно", 1, KG)]}
    assert [e["name"] for e in build_shopping_list([item(1, 1, 1)], lines)] == ["Брашно", "Ориз", "яйца"]


def test_recipe_without_lines():
    assert build_shopping_list([item(1, 1, 1)], {}) == []
