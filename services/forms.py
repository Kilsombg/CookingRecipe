"""Form parsing and validation: raw strings in, clean values and error keys out.

Errors are translation keys, so the routes can show them with t().
"""

import math
from urllib.parse import urlsplit

from services.text import name_key

RECIPE_FIELDS = ("title", "source_url", "servings", "prep_minutes", "cook_minutes", "instructions", "notes", "tags")
ROW_FIELDS = ("name", "quantity", "unit", "note")
INGREDIENT_FIELDS = ("name", "calories_100g", "protein_100g", "carbs_100g", "fat_100g", "grams_per_piece")
INGREDIENT_VALUE_FIELDS = INGREDIENT_FIELDS[1:]
GRAM_MACRO_FIELDS = ("protein_100g", "carbs_100g", "fat_100g")
MENU_ITEM_FIELDS = ("recipe_id", "day", "meal", "servings")
SHOPPING_ITEM_FIELDS = ("name", "quantity", "unit")
DAYS = range(7)  # 0 = Monday … 6 = Sunday, as stored in menu_items.day
MEALS = ("breakfast", "lunch", "dinner", "snack")  # stored in English, shown translated


def clean_text(s):
    """Strip surrounding whitespace; empty -> None."""
    s = (s or "").strip()
    return s or None


def clean_name(s):
    """Extra spaces removed; empty -> None. "  Пилешко   филе " -> "Пилешко филе"."""
    s = " ".join((s or "").split())
    return s or None


def parse_number(s):
    """'0,5' or '0.5' -> 0.5; empty -> None. Raises ValueError for anything else."""
    s = (s or "").strip().replace(",", ".")
    if not s:
        return None
    value = float(s)
    if not math.isfinite(value):
        raise ValueError(s)
    return value


def format_number(x, decimal_sep="."):
    """200.0 -> "200", 0.5 -> "0,5" (with decimal_sep=","), None -> ""."""
    if x is None:
        return ""
    if x == int(x):
        return str(int(x))
    return f"{x:.3f}".rstrip("0").rstrip(".").replace(".", decimal_sep)


def _decimal(raw, allow_zero):
    """Return (value, error_key) for an optional decimal field that can't be negative."""
    try:
        value = parse_number(raw)
    except ValueError:
        return None, "error.number"
    if value is None:
        return None, None
    if value < 0 or (value == 0 and not allow_zero):
        return None, "error.non_negative_number" if allow_zero else "error.positive_number"
    return value, None


def _whole_number(raw, minimum, required=False):
    """Return (value, error_key) for a whole-number field."""
    raw = (raw or "").strip()
    if not raw:
        return None, "error.required" if required else None
    try:
        value = int(raw)
    except ValueError:
        value = None
    if value is None or value < minimum:
        return None, "error.positive_whole_number" if minimum > 0 else "error.non_negative_whole_number"
    return value, None


def parse_source_url(raw):
    """Return (url, error_key) for the optional source link.

    "youtube.com/watch?v=1" -> "https://youtube.com/watch?v=1"; only http(s) links are accepted,
    so the link can't run a script when clicked.
    """
    url = clean_text(raw)
    if url is None:
        return None, None
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc or any(c.isspace() for c in url):
        return None, "recipes.error_source_url"
    return url, None


def url_host(url):
    """"https://www.youtube.com/watch?v=1" -> "youtube.com", to show as the link text."""
    host = urlsplit(url or "").hostname or ""
    return host.removeprefix("www.")


def parse_tags(raw):
    """"Закуска, бързо,, закуска" -> ["закуска", "бързо"]: casefolded, no repeats, in typed order."""
    tags = []
    for part in (raw or "").split(","):
        tag = name_key(part)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def parse_ingredient_row(row, unit_ids):
    """Return (line, error_key) for one ingredient row; (None, None) for a blank row."""
    name = clean_name(row.get("name"))
    quantity_raw = (row.get("quantity") or "").strip()
    unit_raw = (row.get("unit") or "").strip()
    note = clean_text(row.get("note"))
    if not (name or quantity_raw or unit_raw or note):
        return None, None
    if not name:
        return None, "recipes.error_row_name"

    quantity, error = _decimal(quantity_raw, allow_zero=False)
    if error:
        return None, error

    unit_id = int(unit_raw) if unit_raw.isdigit() else None
    if unit_raw and unit_id not in unit_ids:
        return None, "recipes.error_unknown_unit"
    if quantity is None and unit_id is not None:
        return None, "recipes.error_unit_without_quantity"
    if quantity is not None and unit_id is None:
        return None, "recipes.error_quantity_without_unit"

    return {"name": name, "quantity": quantity, "unit_id": unit_id, "note": note}, None


def parse_recipe(fields, rows, unit_ids):
    """Validate the recipe form.

    fields: raw strings keyed by RECIPE_FIELDS.
    rows: one dict of raw strings (keyed by ROW_FIELDS) per ingredient row; blank rows are skipped.
    Returns (recipe, lines, errors). `recipe["tags"]` is a list of tag names. `errors` maps a
    field name to a key, and "rows" to {row index: key}; it is empty when the form is valid.
    """
    errors = {}
    recipe = {
        "title": clean_name(fields.get("title")),
        "instructions": clean_text(fields.get("instructions")),
        "notes": clean_text(fields.get("notes")),
        "tags": parse_tags(fields.get("tags")),
    }
    for field in ("title", "instructions"):
        if recipe[field] is None:
            errors[field] = "error.required"

    recipe["source_url"], error = parse_source_url(fields.get("source_url"))
    if error:
        errors["source_url"] = error

    for field, minimum, required in (("servings", 1, True), ("prep_minutes", 0, False),
                                     ("cook_minutes", 0, False)):
        recipe[field], error = _whole_number(fields.get(field), minimum, required)
        if error:
            errors[field] = error

    lines, row_errors = [], {}
    for i, row in enumerate(rows):
        line, error = parse_ingredient_row(row, unit_ids)
        if error:
            row_errors[i] = error
        elif line:
            lines.append(line)
    if row_errors:
        errors["rows"] = row_errors
    elif not lines:
        errors["ingredients"] = "recipes.error_no_ingredients"

    return recipe, lines, errors


def parse_ingredient(fields):
    """Validate the ingredient form.

    fields: raw strings keyed by INGREDIENT_FIELDS. Every value except the name is optional.
    Returns (name, values, errors): `values` maps INGREDIENT_VALUE_FIELDS to numbers or None,
    `errors` maps a field name (or "macros" for the protein + carbs + fat check) to a key.
    """
    errors = {}
    name = clean_name(fields.get("name"))
    if name is None:
        errors["name"] = "error.required"

    values = {}
    for field in INGREDIENT_VALUE_FIELDS:
        values[field], error = _decimal(fields.get(field), allow_zero=field != "grams_per_piece")
        if error:
            errors[field] = error

    # Rounded so that 33.3 + 33.3 + 33.4 isn't rejected for a floating-point leftover
    if round(sum(values[f] or 0 for f in GRAM_MACRO_FIELDS), 6) > 100:
        errors["macros"] = "ingredients.error_macros_over_100"

    return name, values, errors


def parse_menu_name(raw):
    """Return (name, error_key) for the menu name, which is required."""
    name = clean_name(raw)
    return name, None if name else "error.required"


def parse_menu_item(fields, recipe_servings):
    """Validate the "add a recipe to the menu" form.

    fields: raw strings keyed by MENU_ITEM_FIELDS. Day and meal are optional.
    recipe_servings: {recipe_id: servings} of every recipe; empty servings means the recipe's own.
    Returns (item, errors), with errors keyed by field name.
    """
    errors = {}
    raw_recipe = (fields.get("recipe_id") or "").strip()
    recipe_id = int(raw_recipe) if raw_recipe.isdigit() else None
    if recipe_id not in recipe_servings:
        recipe_id = None
        errors["recipe_id"] = "menus.error_choose_recipe"

    raw_day = (fields.get("day") or "").strip()
    day = int(raw_day) if raw_day.isdigit() else None
    if raw_day and day not in DAYS:
        day = None
        errors["day"] = "menus.error_choose_from_list"

    meal = (fields.get("meal") or "").strip() or None
    if meal is not None and meal not in MEALS:
        meal = None
        errors["meal"] = "menus.error_choose_from_list"

    servings, error = _decimal(fields.get("servings"), allow_zero=False)
    if error:
        errors["servings"] = error
    elif servings is None and recipe_id is not None:
        servings = recipe_servings[recipe_id]

    return {"recipe_id": recipe_id, "day": day, "meal": meal, "servings": servings}, errors


def parse_shopping_item(fields):
    """Validate the "add an item by hand" form.

    fields: raw strings keyed by SHOPPING_ITEM_FIELDS. Quantity and unit are optional and free:
    "тоалетна хартия", "2 пакета" and "1 кг" are all fine.
    Returns (item, errors), with errors keyed by field name.
    """
    errors = {}
    name = clean_name(fields.get("name"))
    if name is None:
        errors["name"] = "error.required"
    quantity, error = _decimal(fields.get("quantity"), allow_zero=False)
    if error:
        errors["quantity"] = error
    return {"name": name, "quantity": quantity, "unit": clean_name(fields.get("unit"))}, errors
