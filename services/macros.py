"""Macro calculations: ingredient lines in, grams and macro totals out.

A line is a mapping with: ingredient_id, name, quantity, unit_grams, grams_per_piece,
and <macro>_100g for every macro. None means "not known", as NULL does in the database.
"""

MACROS = ("calories", "protein", "carbs", "fat")


def line_grams(line):
    """Grams of one ingredient line, or None when they can't be known.

    The unit's grams win; a piece unit (no grams) uses the ingredient's grams per piece.
    """
    quantity = line["quantity"]
    if quantity is None:
        return None
    if line["unit_grams"] is not None:
        return quantity * line["unit_grams"]
    if line["grams_per_piece"] is not None:
        return quantity * line["grams_per_piece"]
    return None


def recipe_macros(lines, servings):
    """Macros of the whole recipe and per serving, plus the ingredients that couldn't be counted.

    Returns {"total": {macro: value}, "per_serving": {macro: value}, "incomplete": [...]}.
    A macro is None when no line had data for it. Lines without a quantity ("to taste") are
    skipped without a warning. Each incomplete entry is {"ingredient_id", "name", "missing"},
    where "missing" lists what to fill in on the ingredient: "grams_per_piece" and/or macro names.
    """
    total = dict.fromkeys(MACROS)
    incomplete = {}
    for line in lines:
        if line["quantity"] is None:
            continue
        grams = line_grams(line)
        missing = [] if grams is not None else ["grams_per_piece"]
        for macro in MACROS:
            per_100g = line[f"{macro}_100g"]
            if per_100g is None:
                missing.append(macro)
            elif grams is not None:
                total[macro] = (total[macro] or 0) + grams / 100 * per_100g
        if missing:
            entry = incomplete.setdefault(line["ingredient_id"], {
                "ingredient_id": line["ingredient_id"], "name": line["name"], "missing": []})
            entry["missing"] += [m for m in missing if m not in entry["missing"]]

    per_serving = {macro: None if value is None else value / servings for macro, value in total.items()}
    return {"total": total, "per_serving": per_serving, "incomplete": list(incomplete.values())}
