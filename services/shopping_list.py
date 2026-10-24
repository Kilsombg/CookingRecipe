"""Shopping list: a menu's recipes in, merged and scaled ingredient quantities out.

A line is a mapping with: ingredient_id, name, quantity, unit_id and unit (the unit's label).
None means "not known", as NULL does in the database.
"""

from services.text import name_key


def build_shopping_list(items, lines_by_recipe):
    """The shopping list for a menu, as [{"name", "quantity", "unit"}].

    items: menu entries with recipe_id, recipe_servings and servings.
    lines_by_recipe: {recipe_id: [ingredient lines]}.
    Each line is scaled by servings / recipe_servings. Lines of the same ingredient and unit are
    added up; a different unit gives a separate entry (no unit conversion). Lines without a
    quantity ("to taste") give one entry without a quantity, and none at all when the ingredient
    is also needed with a quantity. Sorted by name, ignoring case, then by unit.
    """
    totals = {}  # (ingredient_id, unit_id) -> entry
    for item in items:
        factor = item["servings"] / item["recipe_servings"]
        for line in lines_by_recipe.get(item["recipe_id"], []):
            quantity = line["quantity"]
            unit_id = line["unit_id"] if quantity is not None else None
            entry = totals.setdefault((line["ingredient_id"], unit_id), {
                "name": line["name"], "quantity": None, "unit": line["unit"] if unit_id is not None else None})
            if quantity is not None:
                entry["quantity"] = (entry["quantity"] or 0) + quantity * factor

    with_quantity = {ingredient_id for (ingredient_id, _), entry in totals.items() if entry["quantity"] is not None}
    entries = [entry for (ingredient_id, _), entry in totals.items()
               if entry["quantity"] is not None or ingredient_id not in with_quantity]
    return sorted(entries, key=lambda e: (name_key(e["name"]), e["unit"] or ""))
