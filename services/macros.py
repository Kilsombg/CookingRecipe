"""Macro calculations: ingredient lines in, grams and macro totals out (per recipe and per menu).

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


def menu_macros(items, lines_by_recipe):
    """Macros of a menu: each item's recipe per-serving macros × the item's servings.

    items: menu entries with recipe_id, title, recipe_servings, day and servings.
    lines_by_recipe: {recipe_id: [ingredient lines]}.
    Returns {"total": {macro: value}, "days": {day: {macro: value}}, "incomplete": [...]}, where
    "days" has a key for every day used, None for items without a day. Each incomplete entry is
    {"recipe_id", "title"}: a recipe with ingredients missing data, so the totals are partial.
    """
    total = dict.fromkeys(MACROS)
    days = {}
    incomplete = {}
    for item in items:
        recipe = recipe_macros(lines_by_recipe.get(item["recipe_id"], []), item["recipe_servings"])
        day = days.setdefault(item["day"], dict.fromkeys(MACROS))
        for macro, per_serving in recipe["per_serving"].items():
            if per_serving is not None:
                amount = per_serving * item["servings"]
                total[macro] = (total[macro] or 0) + amount
                day[macro] = (day[macro] or 0) + amount
        if recipe["incomplete"]:
            incomplete.setdefault(item["recipe_id"], {"recipe_id": item["recipe_id"], "title": item["title"]})
    return {"total": total, "days": days, "incomplete": list(incomplete.values())}
