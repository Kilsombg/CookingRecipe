"""Form parsing and validation: raw strings in, clean values and error keys out.

Errors are translation keys, so the routes can show them with t().
"""

import math

RECIPE_FIELDS = ("title", "servings", "prep_minutes", "cook_minutes", "instructions", "notes")
ROW_FIELDS = ("name", "quantity", "unit", "note")


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

    try:
        quantity = parse_number(quantity_raw)
    except ValueError:
        return None, "error.number"
    if quantity is not None and quantity <= 0:
        return None, "error.positive_number"

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
    Returns (recipe, lines, errors). `errors` maps a field name to a key, and "rows" to
    {row index: key}; it is empty when the form is valid.
    """
    errors = {}
    recipe = {
        "title": clean_name(fields.get("title")),
        "instructions": clean_text(fields.get("instructions")),
        "notes": clean_text(fields.get("notes")),
    }
    for field in ("title", "instructions"):
        if recipe[field] is None:
            errors[field] = "error.required"

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
