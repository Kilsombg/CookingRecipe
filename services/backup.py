"""JSON export / import: the file format, and checking an uploaded file before anything is saved.

    {"format": "CookingRecipe", "version": 1, "exported_at": "2026-10-24T18:30:00",
     "units":       [{"name": "г", "grams": 1}, ...],
     "ingredients": [{"name": "Яйца", "calories_100g": 143, ..., "grams_per_piece": 55}, ...],
     "recipes":     [{"id": 1, "title": "Омлет", "servings": 1, ..., "is_favourite": false,
                      "tags": ["закуска"],
                      "ingredients": [{"name": "Яйца", "quantity": 3, "unit": "бр.", "note": null}, ...]}, ...],
     "menus":       [{"name": "Седмица 12 ноември",
                      "items": [{"recipe": 1, "day": 0, "meal": "breakfast", "servings": 2}, ...]}, ...]}

Units, ingredients and tags are referred to by name. Menu items point at a recipe's "id" inside the
same file, because recipe titles don't have to be unique. Photos and shopping lists aren't included.

An imported file is checked with the same rules as the forms (texts are cleaned, numbers must be in
range, source links must be http/https), so the database never gets a value the app couldn't have saved.
"""

import json
import math

from services.forms import (DAYS, INGREDIENT_VALUE_FIELDS, MEALS, clean_name, clean_text, parse_source_url,
                            parse_tags)
from services.text import casefold

FORMAT = "CookingRecipe"
VERSION = 1


class BackupError(Exception):
    """`key` is a translation key; `where` is the part of the file that is wrong, e.g. "recipes[2].servings"."""

    def __init__(self, key, where=""):
        super().__init__(key, where)
        self.key = key
        self.where = where


def build_export(data, exported_at):
    """The whole file: the header, then `data` from db.export_data()."""
    return {"format": FORMAT, "version": VERSION, "exported_at": exported_at.isoformat(timespec="seconds"), **data}


def parse_import(raw):
    """Check an uploaded export file (bytes) and return its data, cleaned, in the shape db.import_data() takes.
    Raises BackupError for the first problem found. A missing list (e.g. no "menus") counts as empty."""
    try:
        data = json.loads(raw.decode("utf-8-sig"))  # -sig: a file saved by Notepad may start with a BOM
    except ValueError:  # bad UTF-8 or bad JSON
        raise BackupError("data.error_not_json") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT or data.get("version") != VERSION:
        raise BackupError("data.error_not_export")

    units = [_unit(u, where) for u, where in _items(data, "units", "")]
    unit_names = {casefold(u["name"]) for u in units}
    ingredients = [_ingredient(i, where) for i, where in _items(data, "ingredients", "")]
    recipes, recipe_ids = [], set()
    for obj, where in _items(data, "recipes", ""):
        recipe = _recipe(obj, where, unit_names)
        if recipe["id"] in recipe_ids:
            _fail(f"{where}.id")
        recipe_ids.add(recipe["id"])
        recipes.append(recipe)
    menus = [_menu(m, where, recipe_ids) for m, where in _items(data, "menus", "")]
    return {"units": units, "ingredients": ingredients, "recipes": recipes, "menus": menus}


def _fail(where):
    raise BackupError("data.error_invalid", where)


def _items(obj, key, prefix):
    """[(item, "prefix.key[i]")] for the list `obj[key]`; every item must be an object."""
    where = f"{prefix}.{key}" if prefix else key
    items = obj.get(key, [])
    if not isinstance(items, list):
        _fail(where)
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            _fail(f"{where}[{i}]")
    return [(item, f"{where}[{i}]") for i, item in enumerate(items)]


def _text(obj, key, where, clean=clean_text, required=False):
    value = obj.get(key)
    if value is not None and not isinstance(value, str):
        _fail(f"{where}.{key}")
    value = clean(value)
    if value is None and required:
        _fail(f"{where}.{key}")
    return value


def _number(obj, key, where, positive, whole=False, required=False):
    """An optional number, > 0 (`positive`) or >= 0. JSON true/false aren't numbers here."""
    value = obj.get(key)
    if value is None:
        if required:
            _fail(f"{where}.{key}")
        return None
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            or value < 0 or (positive and value == 0) or (whole and value != int(value))):
        _fail(f"{where}.{key}")
    return int(value) if whole else value


def _unit(obj, where):
    return {"name": _text(obj, "name", where, clean_name, required=True),
            "grams": _number(obj, "grams", where, positive=True)}


def _ingredient(obj, where):
    values = {field: _number(obj, field, where, positive=field == "grams_per_piece")
              for field in INGREDIENT_VALUE_FIELDS}
    return {"name": _text(obj, "name", where, clean_name, required=True), **values}


def _recipe(obj, where, unit_names):
    """Checked in the order the fields are written in an export, so the first problem is the one reported."""
    recipe_id = obj.get("id")
    if isinstance(recipe_id, bool) or not isinstance(recipe_id, int):
        _fail(f"{where}.id")
    recipe = {"id": recipe_id, "title": _text(obj, "title", where, clean_name, required=True)}

    recipe["source_url"], error = parse_source_url(_text(obj, "source_url", where))
    if error:
        _fail(f"{where}.source_url")

    recipe |= {"servings": _number(obj, "servings", where, positive=True, whole=True, required=True),
               "prep_minutes": _number(obj, "prep_minutes", where, positive=False, whole=True),
               "cook_minutes": _number(obj, "cook_minutes", where, positive=False, whole=True),
               "instructions": _text(obj, "instructions", where, required=True),
               "notes": _text(obj, "notes", where)}

    recipe["is_favourite"] = obj.get("is_favourite", False)
    if not isinstance(recipe["is_favourite"], bool):
        _fail(f"{where}.is_favourite")

    tags = obj.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        _fail(f"{where}.tags")
    recipe["tags"] = parse_tags(",".join(tags))

    recipe["ingredients"] = [_line(line, line_where, unit_names)
                             for line, line_where in _items(obj, "ingredients", where)]
    if not recipe["ingredients"]:
        _fail(f"{where}.ingredients")
    return recipe


def _line(obj, where, unit_names):
    """Like a row of the recipe form: a quantity needs a unit and a unit needs a quantity. The unit
    must be one of the file's units."""
    name = _text(obj, "name", where, clean_name, required=True)
    quantity = _number(obj, "quantity", where, positive=True)
    unit = _text(obj, "unit", where, clean_name)
    if (quantity is None) != (unit is None) or (unit is not None and casefold(unit) not in unit_names):
        _fail(f"{where}.unit")
    return {"name": name, "quantity": quantity, "unit": unit, "note": _text(obj, "note", where)}


def _menu(obj, where, recipe_ids):
    items = []
    for item, item_where in _items(obj, "items", where):
        recipe = item.get("recipe")
        if isinstance(recipe, bool) or not isinstance(recipe, int) or recipe not in recipe_ids:
            _fail(f"{item_where}.recipe")
        day = item.get("day")
        if day is not None and (isinstance(day, bool) or day not in DAYS):
            _fail(f"{item_where}.day")
        meal = item.get("meal")
        if meal is not None and meal not in MEALS:
            _fail(f"{item_where}.meal")
        items.append({"recipe": recipe, "day": day, "meal": meal,
                      "servings": _number(item, "servings", item_where, positive=True, required=True)})
    return {"name": _text(obj, "name", where, clean_name, required=True), "items": items}
