import json
from datetime import datetime

import pytest

from services.backup import BackupError, build_export, parse_import


def export_file(**overrides):
    data = {
        "units": [{"name": "г", "grams": 1}, {"name": "бр.", "grams": None}],
        "ingredients": [{"name": "Яйца", "calories_100g": 143, "protein_100g": 12.6, "carbs_100g": 0.7,
                         "fat_100g": 9.5, "grams_per_piece": 55}],
        "recipes": [{"id": 7, "title": "  Омлет ", "source_url": "youtube.com/watch?v=1", "servings": 1,
                     "prep_minutes": 5, "cook_minutes": None, "instructions": "Разбийте яйцата.", "notes": None,
                     "is_favourite": True, "tags": ["Закуска", "закуска", "бързо"],
                     "ingredients": [{"name": "Яйца", "quantity": 3, "unit": "БР.", "note": None},
                                     {"name": "Сол", "quantity": None, "unit": None, "note": "на вкус"}]}],
        "menus": [{"name": "Седмица", "items": [{"recipe": 7, "day": 0, "meal": "breakfast", "servings": 2}]}],
    } | overrides
    return build_export(data, datetime(2026, 10, 24, 18, 30))


def parse(data):
    return parse_import(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def where(data):
    with pytest.raises(BackupError) as e:
        parse(data)
    return e.value.where


def test_header():
    assert export_file()["format"] == "CookingRecipe"
    assert export_file()["exported_at"] == "2026-10-24T18:30:00"


def test_valid_file_is_cleaned():
    data = parse(export_file())
    recipe = data["recipes"][0]
    assert recipe["title"] == "Омлет"
    assert recipe["source_url"] == "https://youtube.com/watch?v=1"
    assert recipe["tags"] == ["закуска", "бързо"]
    assert recipe["ingredients"][0] == {"name": "Яйца", "quantity": 3, "unit": "БР.", "note": None}
    assert data["menus"][0]["items"] == [{"recipe": 7, "day": 0, "meal": "breakfast", "servings": 2}]
    assert data["ingredients"][0]["grams_per_piece"] == 55


def test_bom_and_missing_lists_are_fine():
    raw = "﻿" + json.dumps({"format": "CookingRecipe", "version": 1})
    assert parse_import(raw.encode("utf-8")) == {"units": [], "ingredients": [], "recipes": [], "menus": []}


@pytest.mark.parametrize("raw, key", [
    (b"not json", "data.error_not_json"),
    (b"\xff\xfe", "data.error_not_json"),
    (b"[]", "data.error_not_export"),
    (b'{"format": "Other", "version": 1}', "data.error_not_export"),
    (b'{"format": "CookingRecipe", "version": 2}', "data.error_not_export"),
])
def test_not_an_export(raw, key):
    with pytest.raises(BackupError) as e:
        parse_import(raw)
    assert e.value.key == key


def recipe(**overrides):
    return export_file()["recipes"][0] | overrides


@pytest.mark.parametrize("change, expected", [
    ({"units": [{"name": " ", "grams": 1}]}, "units[0].name"),
    ({"units": [{"name": "г", "grams": 0}]}, "units[0].grams"),
    ({"units": {"name": "г"}}, "units"),
    ({"ingredients": [{"name": "Яйца", "fat_100g": -1}]}, "ingredients[0].fat_100g"),
    ({"ingredients": [{"name": "Яйца", "grams_per_piece": 0}]}, "ingredients[0].grams_per_piece"),
    ({"ingredients": ["Яйца"]}, "ingredients[0]"),
    ({"recipes": [recipe(servings=0)]}, "recipes[0].servings"),
    ({"recipes": [recipe(servings=1.5)]}, "recipes[0].servings"),
    ({"recipes": [recipe(servings=True)]}, "recipes[0].servings"),
    ({"recipes": [recipe(servings="2")]}, "recipes[0].servings"),
    ({"recipes": [recipe(title="")]}, "recipes[0].title"),
    ({"recipes": [recipe(instructions=None)]}, "recipes[0].instructions"),
    ({"recipes": [recipe(source_url="javascript://alert(1)")]}, "recipes[0].source_url"),
    ({"recipes": [recipe(is_favourite=1)]}, "recipes[0].is_favourite"),
    ({"recipes": [recipe(tags="закуска")]}, "recipes[0].tags"),
    ({"recipes": [recipe(id="7")]}, "recipes[0].id"),
    ({"recipes": [recipe(), recipe()]}, "recipes[1].id"),
    ({"recipes": [recipe(ingredients=[])]}, "recipes[0].ingredients"),
    ({"recipes": [recipe(ingredients=[{"name": "Яйца", "quantity": 3, "unit": "чаша"}])]},
     "recipes[0].ingredients[0].unit"),
    ({"recipes": [recipe(ingredients=[{"name": "Яйца", "quantity": 3}])]}, "recipes[0].ingredients[0].unit"),
    ({"recipes": [recipe(ingredients=[{"name": "Яйца", "unit": "г"}])]}, "recipes[0].ingredients[0].unit"),
    ({"recipes": [recipe(ingredients=[{"name": "Яйца", "quantity": 0, "unit": "г"}])]},
     "recipes[0].ingredients[0].quantity"),
    ({"menus": [{"name": "М", "items": [{"recipe": 8, "servings": 1}]}]}, "menus[0].items[0].recipe"),
    ({"menus": [{"name": "М", "items": [{"recipe": [7], "servings": 1}]}]}, "menus[0].items[0].recipe"),
    ({"menus": [{"name": "М", "items": [{"recipe": 7, "day": 7, "servings": 1}]}]}, "menus[0].items[0].day"),
    ({"menus": [{"name": "М", "items": [{"recipe": 7, "meal": "brunch", "servings": 1}]}]},
     "menus[0].items[0].meal"),
    ({"menus": [{"name": "М", "items": [{"recipe": 7}]}]}, "menus[0].items[0].servings"),
    ({"menus": [{"name": None, "items": []}]}, "menus[0].name"),
])
def test_invalid_values_say_where(change, expected):
    assert where(export_file(**change)) == expected
