import re
import sqlite3
from collections import defaultdict
from datetime import datetime

from flask import current_app, g

import config
from services.forms import INGREDIENT_VALUE_FIELDS
from services.text import casefold, name_key

MIGRATION_NAME = re.compile(r"^(\d{4})_\w+\.sql$")


class MigrationError(Exception):
    pass


def connect(db_path=config.DB_PATH):
    """Open a connection with foreign keys on, Row results and the casefold() SQL function."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("casefold", 1, casefold, deterministic=True)
    return conn


def init_db(db_path=config.DB_PATH, migrations_dir=config.MIGRATIONS_DIR,
            backups_dir=config.BACKUPS_DIR, images_dir=config.IMAGES_DIR):
    """Create the data folders and bring the database up to the latest migration."""
    images_dir.mkdir(exist_ok=True)
    backups_dir.mkdir(exist_ok=True)
    conn = connect(db_path)
    try:
        migrate(conn, migrations_dir, backups_dir)
    finally:
        conn.close()


def list_migrations(migrations_dir):
    """Return [(number, path)] for every migration file, sorted by number."""
    migrations = {}
    for path in migrations_dir.glob("*.sql"):
        match = MIGRATION_NAME.match(path.name)
        if not match:
            raise MigrationError(f"Bad migration file name: {path.name} (expected NNNN_description.sql)")
        number = int(match.group(1))
        if number in migrations:
            raise MigrationError(f"Two migrations with number {number}: {migrations[number].name}, {path.name}")
        migrations[number] = path
    return sorted(migrations.items())


def migrate(conn, migrations_dir, backups_dir):
    """Apply pending migrations, one transaction per file. Returns the numbers applied."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    pending = [(n, p) for n, p in list_migrations(migrations_dir) if n > current]
    if not pending:
        return []

    if current > 0:
        backup(conn, backups_dir)

    applied = []
    for number, path in pending:
        sql = path.read_text(encoding="utf-8")
        try:
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
        except sqlite3.Error as e:
            conn.rollback()
            raise MigrationError(f"Migration {path.name} failed: {e}") from e
        applied.append(number)
    return applied


def backup(conn, backups_dir):
    """Copy the database to backups/recipes-YYYYMMDD-HHMMSS.db and return the path."""
    backups_dir.mkdir(exist_ok=True)
    target = backups_dir / f"recipes-{datetime.now():%Y%m%d-%H%M%S}.db"
    dest = sqlite3.connect(target)
    try:
        conn.backup(dest)
    finally:
        dest.close()
    return target


# --- Connection per request ---

def get_db():
    """The connection for the current request, opened on first use."""
    if "db" not in g:
        g.db = connect(current_app.config["DB_PATH"])
    return g.db


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def _contains(text):
    """LIKE pattern for name_key values containing `text` (use with ESCAPE '\\')."""
    escaped = name_key(text).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# --- Units ---

def list_units(conn):
    return conn.execute("SELECT id, name, grams FROM units ORDER BY id").fetchall()


def list_units_with_usage(conn):
    """Every unit, with how many recipes use it (for the units page)."""
    return conn.execute(
        """SELECT u.id, u.name, u.grams, COUNT(DISTINCT ri.recipe_id) AS recipe_count
           FROM units u LEFT JOIN recipe_ingredients ri ON ri.unit_id = u.id
           GROUP BY u.id ORDER BY u.id""").fetchall()


def get_unit(conn, unit_id):
    return conn.execute("SELECT id, name, grams FROM units WHERE id = ?", (unit_id,)).fetchone()


def find_unit(conn, name):
    """The unit with this name, ignoring case ("Чаша" = "чаша"), or None."""
    return conn.execute("SELECT id, name, grams FROM units WHERE casefold(name) = casefold(?)",
                        (name,)).fetchone()


def create_unit(conn, unit):
    """`unit`: name and grams (None = a piece unit)."""
    with conn:
        return conn.execute("INSERT INTO units (name, grams) VALUES (:name, :grams)", unit).lastrowid


def update_unit(conn, unit_id, unit):
    """Recipes that use the unit show the new name, and their macros use the new grams."""
    with conn:
        conn.execute("UPDATE units SET name = :name, grams = :grams WHERE id = :id", {**unit, "id": unit_id})


def delete_unit(conn, unit_id):
    """Raises sqlite3.IntegrityError if a recipe still uses it."""
    with conn:
        conn.execute("DELETE FROM units WHERE id = ?", (unit_id,))


# --- Ingredients ---

# An ingredient whose data can't give macros: a macro is empty, or a recipe measures it
# in a piece unit (units.grams IS NULL) while it has no grams per piece.
_MISSING_DATA = """(i.calories_100g IS NULL OR i.protein_100g IS NULL
                    OR i.carbs_100g IS NULL OR i.fat_100g IS NULL
                    OR (i.grams_per_piece IS NULL AND EXISTS (
                        SELECT 1 FROM recipe_ingredients pri JOIN units pu ON pu.id = pri.unit_id
                        WHERE pri.ingredient_id = i.id AND pu.grams IS NULL)))"""


def list_ingredients(conn, q="", missing=False):
    """All ingredients (or those whose name contains `q`, or with missing data), with
    their macros and how many recipes use each."""
    sql = """SELECT i.id, i.name, i.calories_100g, i.protein_100g, i.carbs_100g, i.fat_100g,
                    i.grams_per_piece, COUNT(DISTINCT ri.recipe_id) AS recipe_count
             FROM ingredients i
             LEFT JOIN recipe_ingredients ri ON ri.ingredient_id = i.id"""
    conditions, params = [], []
    if q:
        conditions.append("i.name_key LIKE ? ESCAPE '\\'")
        params.append(_contains(q))
    if missing:
        conditions.append(_MISSING_DATA)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " GROUP BY i.id ORDER BY casefold(i.name)"
    return conn.execute(sql, params).fetchall()


def ingredient_names(conn):
    """Every catalogue name, for the <datalist> autocomplete."""
    return [r["name"] for r in conn.execute("SELECT name FROM ingredients ORDER BY casefold(name)")]


def get_ingredient(conn, ingredient_id):
    return conn.execute("SELECT * FROM ingredients WHERE id = ?", (ingredient_id,)).fetchone()


def find_ingredient(conn, name):
    """The ingredient with this name, ignoring case and extra spaces, or None."""
    return conn.execute("SELECT * FROM ingredients WHERE name_key = ?", (name_key(name),)).fetchone()


def create_ingredient(conn, name, values=None):
    """`values`: macros per 100 g and grams per piece (see INGREDIENT_VALUE_FIELDS); missing ones stay NULL."""
    with conn:
        return _insert_ingredient(conn, name, values)


def _insert_ingredient(conn, name, values=None):
    cur = conn.execute(
        """INSERT INTO ingredients (name, name_key, calories_100g, protein_100g, carbs_100g, fat_100g,
                                    grams_per_piece)
           VALUES (:name, :name_key, :calories_100g, :protein_100g, :carbs_100g, :fat_100g, :grams_per_piece)""",
        _ingredient_params(name, values))
    return cur.lastrowid


def update_ingredient(conn, ingredient_id, name, values):
    with conn:
        conn.execute(
            """UPDATE ingredients
               SET name = :name, name_key = :name_key, calories_100g = :calories_100g,
                   protein_100g = :protein_100g, carbs_100g = :carbs_100g, fat_100g = :fat_100g,
                   grams_per_piece = :grams_per_piece
               WHERE id = :id""",
            {**_ingredient_params(name, values), "id": ingredient_id})


def _ingredient_params(name, values):
    return {**dict.fromkeys(INGREDIENT_VALUE_FIELDS), **(values or {}), "name": name, "name_key": name_key(name)}


def delete_ingredient(conn, ingredient_id):
    """Raises sqlite3.IntegrityError if a recipe still uses it."""
    with conn:
        conn.execute("DELETE FROM ingredients WHERE id = ?", (ingredient_id,))


def recipes_using_ingredient(conn, ingredient_id):
    return conn.execute(
        """SELECT DISTINCT r.id, r.title
           FROM recipes r JOIN recipe_ingredients ri ON ri.recipe_id = r.id
           WHERE ri.ingredient_id = ?
           ORDER BY casefold(r.title)""", (ingredient_id,)).fetchall()


# --- Recipes ---

def list_recipes(conn, q="", tag_id=None, favourites=False):
    """All recipes, or those whose title or an ingredient name contains `q` (ignoring case),
    and/or that have the tag `tag_id`, and/or that are favourites."""
    sql = """SELECT r.id, r.title, r.photo_filename, r.servings, r.prep_minutes, r.cook_minutes, r.is_favourite
             FROM recipes r"""
    conditions, params = [], {}
    if q:
        conditions.append("""(casefold(r.title) LIKE :q ESCAPE '\\' OR EXISTS (
                                 SELECT 1 FROM recipe_ingredients qri JOIN ingredients qi ON qi.id = qri.ingredient_id
                                 WHERE qri.recipe_id = r.id AND qi.name_key LIKE :q ESCAPE '\\'))""")
        params["q"] = _contains(q)
    if tag_id is not None:
        conditions.append("EXISTS (SELECT 1 FROM recipe_tags trt WHERE trt.recipe_id = r.id AND trt.tag_id = :tag)")
        params["tag"] = tag_id
    if favourites:
        conditions.append("r.is_favourite = 1")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY casefold(r.title)"
    return conn.execute(sql, params).fetchall()


def get_recipe(conn, recipe_id):
    return conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()


# Ingredient lines with what services/macros.py needs: unit grams, grams per piece, macros per 100 g
_LINES_SQL = """SELECT ri.recipe_id, ri.quantity, ri.unit_id, ri.note,
                       u.name AS unit, u.grams AS unit_grams,
                       i.id AS ingredient_id, i.name, i.grams_per_piece,
                       i.calories_100g, i.protein_100g, i.carbs_100g, i.fat_100g
                FROM recipe_ingredients ri
                JOIN ingredients i ON i.id = ri.ingredient_id
                LEFT JOIN units u ON u.id = ri.unit_id"""


def get_recipe_lines(conn, recipe_id):
    """The recipe's ingredient lines in order, with ingredient and unit data."""
    return conn.execute(_LINES_SQL + " WHERE ri.recipe_id = ? ORDER BY ri.position", (recipe_id,)).fetchall()


def lines_by_recipe(conn):
    """{recipe_id: [lines]} for every recipe, in one query (for the recipe cards)."""
    grouped = defaultdict(list)
    for line in conn.execute(_LINES_SQL + " ORDER BY ri.recipe_id, ri.position"):
        grouped[line["recipe_id"]].append(line)
    return grouped


def _recipe_params(recipe):
    """The optional columns (photo, source link) default to NULL, and a new recipe isn't a favourite."""
    return {"photo_filename": None, "source_url": None, "is_favourite": False, **recipe}


def create_recipe(conn, recipe, lines):
    """Insert a recipe, its lines and its tags (`recipe["tags"]`, optional); unknown ingredient
    names are added to the catalogue."""
    with conn:
        return _insert_recipe(conn, recipe, lines)


def _insert_recipe(conn, recipe, lines):
    cur = conn.execute(
        """INSERT INTO recipes (title, photo_filename, source_url, servings, prep_minutes, cook_minutes,
                                instructions, notes, is_favourite)
           VALUES (:title, :photo_filename, :source_url, :servings, :prep_minutes, :cook_minutes,
                   :instructions, :notes, :is_favourite)""",
        _recipe_params(recipe))
    _save_lines(conn, cur.lastrowid, lines)
    _save_tags(conn, cur.lastrowid, recipe.get("tags", []))
    return cur.lastrowid


def has_favourites(conn):
    return conn.execute("SELECT 1 FROM recipes WHERE is_favourite = 1").fetchone() is not None


def set_favourite(conn, recipe_id, favourite):
    """Doesn't change `updated_at`: starring a recipe isn't editing it."""
    with conn:
        conn.execute("UPDATE recipes SET is_favourite = ? WHERE id = ?", (int(favourite), recipe_id))


def update_recipe(conn, recipe_id, recipe, lines):
    """Replace everything, including the photo: pass the current `photo_filename` to keep it.
    The favourite mark is kept."""
    with conn:
        conn.execute(
            """UPDATE recipes
               SET title = :title, photo_filename = :photo_filename, source_url = :source_url,
                   servings = :servings, prep_minutes = :prep_minutes, cook_minutes = :cook_minutes,
                   instructions = :instructions, notes = :notes, updated_at = datetime('now')
               WHERE id = :id""",
            {**_recipe_params(recipe), "id": recipe_id})
        conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
        _save_lines(conn, recipe_id, lines)
        conn.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
        _save_tags(conn, recipe_id, recipe.get("tags", []))
        _delete_unused_tags(conn)


def delete_recipe(conn, recipe_id):
    with conn:
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        _delete_unused_tags(conn)


def _save_lines(conn, recipe_id, lines):
    for position, line in enumerate(lines, start=1):
        existing = find_ingredient(conn, line["name"])
        ingredient_id = existing["id"] if existing else _insert_ingredient(conn, line["name"])
        conn.execute(
            """INSERT INTO recipe_ingredients (recipe_id, ingredient_id, position, quantity, unit_id, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (recipe_id, ingredient_id, position, line["quantity"], line["unit_id"], line["note"]))


# --- Tags ---
# Tag names are stored casefolded (services/forms.py: parse_tags), so "Закуска" and "закуска" are one tag.

def _save_tags(conn, recipe_id, tags):
    for tag in tags:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        conn.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) SELECT ?, id FROM tags WHERE name = ?",
                     (recipe_id, tag))


def _delete_unused_tags(conn):
    conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM recipe_tags)")


def list_tags(conn):
    """Every tag used by a recipe, for the filter on the recipe list."""
    return conn.execute(
        """SELECT DISTINCT t.id, t.name FROM tags t JOIN recipe_tags rt ON rt.tag_id = t.id
           ORDER BY casefold(t.name)""").fetchall()


def get_recipe_tags(conn, recipe_id):
    return conn.execute(
        """SELECT t.id, t.name FROM tags t JOIN recipe_tags rt ON rt.tag_id = t.id
           WHERE rt.recipe_id = ? ORDER BY casefold(t.name)""", (recipe_id,)).fetchall()


def tags_by_recipe(conn):
    """{recipe_id: [tags]} for every recipe, in one query (for the recipe cards)."""
    grouped = defaultdict(list)
    for row in conn.execute(
            """SELECT rt.recipe_id, t.id, t.name FROM tags t JOIN recipe_tags rt ON rt.tag_id = t.id
               ORDER BY casefold(t.name)"""):
        grouped[row["recipe_id"]].append(row)
    return grouped


# --- Menus ---

def list_menus(conn):
    """Every menu, newest first, with how many recipes it has."""
    return conn.execute(
        """SELECT m.id, m.name, COUNT(mi.id) AS item_count
           FROM menus m LEFT JOIN menu_items mi ON mi.menu_id = m.id
           GROUP BY m.id ORDER BY m.id DESC""").fetchall()


def get_menu(conn, menu_id):
    return conn.execute("SELECT * FROM menus WHERE id = ?", (menu_id,)).fetchone()


def create_menu(conn, name):
    with conn:
        return conn.execute("INSERT INTO menus (name) VALUES (?)", (name,)).lastrowid


def rename_menu(conn, menu_id, name):
    with conn:
        conn.execute("UPDATE menus SET name = ? WHERE id = ?", (name, menu_id))


def delete_menu(conn, menu_id):
    """Its items and shopping list go with it."""
    with conn:
        conn.execute("DELETE FROM menus WHERE id = ?", (menu_id,))


def copy_menu(conn, menu_id, name):
    """A new menu called `name` with the same entries. The shopping list isn't copied: it is built
    from the new menu on its first visit."""
    with conn:
        new_id = conn.execute("INSERT INTO menus (name) VALUES (?)", (name,)).lastrowid
        conn.execute(
            """INSERT INTO menu_items (menu_id, recipe_id, day, meal, servings)
               SELECT ?, recipe_id, day, meal, servings FROM menu_items WHERE menu_id = ? ORDER BY id""",
            (new_id, menu_id))
    return new_id


def get_menu_items(conn, menu_id):
    """The menu's entries in the order they were added, with the recipe's title and servings."""
    return conn.execute(
        """SELECT mi.id, mi.recipe_id, mi.day, mi.meal, mi.servings,
                  r.title, r.servings AS recipe_servings
           FROM menu_items mi JOIN recipes r ON r.id = mi.recipe_id
           WHERE mi.menu_id = ? ORDER BY mi.id""", (menu_id,)).fetchall()


def add_menu_item(conn, menu_id, item):
    """`item`: recipe_id, day (0 = Monday … 6, or None), meal (or None), servings."""
    with conn:
        return conn.execute(
            """INSERT INTO menu_items (menu_id, recipe_id, day, meal, servings)
               VALUES (:menu_id, :recipe_id, :day, :meal, :servings)""",
            {**item, "menu_id": menu_id}).lastrowid


def delete_menu_item(conn, menu_id, item_id):
    """Returns False when the menu has no such item."""
    with conn:
        return conn.execute("DELETE FROM menu_items WHERE id = ? AND menu_id = ?",
                            (item_id, menu_id)).rowcount > 0


# --- Shopping list ---
# Names and units are copied in as text, so editing an ingredient later doesn't change the list.

def get_shopping_items(conn, menu_id):
    """The menu's list: the items built from the menu in their saved order, then those added by hand."""
    return conn.execute(
        """SELECT id, name, quantity, unit, checked, is_manual FROM shopping_items
           WHERE menu_id = ? ORDER BY is_manual, id""", (menu_id,)).fetchall()


def has_built_shopping_items(conn, menu_id):
    return conn.execute("SELECT 1 FROM shopping_items WHERE menu_id = ? AND is_manual = 0",
                        (menu_id,)).fetchone() is not None


def replace_shopping_items(conn, menu_id, items):
    """Replace the items built from the menu with `items` ({"name", "quantity", "unit"}); items added
    by hand are kept. An item that is exactly as before keeps its tick."""
    with conn:
        ticked = {(r["name"], r["quantity"], r["unit"]) for r in conn.execute(
            "SELECT name, quantity, unit FROM shopping_items WHERE menu_id = ? AND is_manual = 0 AND checked = 1",
            (menu_id,))}
        conn.execute("DELETE FROM shopping_items WHERE menu_id = ? AND is_manual = 0", (menu_id,))
        conn.executemany(
            "INSERT INTO shopping_items (menu_id, name, quantity, unit, checked) VALUES (?, ?, ?, ?, ?)",
            [(menu_id, i["name"], i["quantity"], i["unit"], (i["name"], i["quantity"], i["unit"]) in ticked)
             for i in items])


def get_shopping_item(conn, item_id):
    return conn.execute("SELECT * FROM shopping_items WHERE id = ?", (item_id,)).fetchone()


def add_shopping_item(conn, menu_id, item):
    """An item added by hand: `item` has name, quantity and unit (both may be None)."""
    with conn:
        return conn.execute(
            """INSERT INTO shopping_items (menu_id, name, quantity, unit, is_manual)
               VALUES (:menu_id, :name, :quantity, :unit, 1)""", {**item, "menu_id": menu_id}).lastrowid


def set_shopping_item_checked(conn, item_id, checked):
    """Returns False when there is no such item."""
    with conn:
        return conn.execute("UPDATE shopping_items SET checked = ? WHERE id = ?",
                            (int(checked), item_id)).rowcount > 0


def delete_shopping_item(conn, item_id):
    """Only items added by hand can be deleted (the others come back on rebuild). Returns False otherwise."""
    with conn:
        return conn.execute("DELETE FROM shopping_items WHERE id = ? AND is_manual = 1", (item_id,)).rowcount > 0


# --- JSON export / import (the file format is described in services/backup.py) ---

def export_data(conn):
    """Units, ingredients, recipes and menus as plain lists and dicts. Photos and shopping lists are left out."""
    lines, tags = lines_by_recipe(conn), tags_by_recipe(conn)
    return {
        "units": [{"name": u["name"], "grams": u["grams"]} for u in list_units(conn)],
        "ingredients": [{"name": i["name"], **{field: i[field] for field in INGREDIENT_VALUE_FIELDS}}
                        for i in conn.execute("SELECT * FROM ingredients ORDER BY casefold(name)")],
        "recipes": [{"id": r["id"], "title": r["title"], "source_url": r["source_url"], "servings": r["servings"],
                     "prep_minutes": r["prep_minutes"], "cook_minutes": r["cook_minutes"],
                     "instructions": r["instructions"], "notes": r["notes"],
                     "is_favourite": bool(r["is_favourite"]), "tags": [tag["name"] for tag in tags[r["id"]]],
                     "ingredients": [{"name": line["name"], "quantity": line["quantity"], "unit": line["unit"],
                                      "note": line["note"]} for line in lines[r["id"]]]}
                    for r in conn.execute("SELECT * FROM recipes ORDER BY id")],
        "menus": [{"name": m["name"],
                   "items": [{"recipe": item["recipe_id"], "day": item["day"], "meal": item["meal"],
                              "servings": item["servings"]} for item in get_menu_items(conn, m["id"])]}
                  for m in conn.execute("SELECT id, name FROM menus ORDER BY id")],
    }


def import_data(conn, data):
    """Add the contents of a checked export file (services/backup.py: parse_import), all in one transaction.

    Nothing already here is changed: a unit, ingredient, recipe or menu with the same name (ignoring
    case) is kept as it is, and the file's recipes and menus use the one already here. Returns how many
    of each were added.
    """
    added = dict.fromkeys(("units", "ingredients", "recipes", "menus"), 0)
    with conn:
        unit_ids = {}
        for unit in data["units"]:
            existing = find_unit(conn, unit["name"])
            if existing is None:
                unit_ids[casefold(unit["name"])] = conn.execute(
                    "INSERT INTO units (name, grams) VALUES (:name, :grams)", unit).lastrowid
                added["units"] += 1
            else:
                unit_ids[casefold(unit["name"])] = existing["id"]

        for ingredient in data["ingredients"]:
            if find_ingredient(conn, ingredient["name"]) is None:
                _insert_ingredient(conn, ingredient["name"], ingredient)
                added["ingredients"] += 1

        # Only recipes and menus from before the import count, so two with the same title in the file are both added
        existing_recipes = {}
        for row in conn.execute("SELECT id, title FROM recipes ORDER BY id"):
            existing_recipes.setdefault(name_key(row["title"]), row["id"])
        existing_menus = {name_key(row["name"]) for row in conn.execute("SELECT name FROM menus")}

        recipe_ids = {}  # id in the file -> id here
        for recipe in data["recipes"]:
            existing = existing_recipes.get(name_key(recipe["title"]))
            if existing is not None:
                recipe_ids[recipe["id"]] = existing
                continue
            lines = [{**line, "unit_id": unit_ids[casefold(line["unit"])] if line["unit"] else None}
                     for line in recipe["ingredients"]]
            recipe_ids[recipe["id"]] = _insert_recipe(conn, recipe, lines)
            added["recipes"] += 1

        for menu in data["menus"]:
            if name_key(menu["name"]) in existing_menus:
                continue
            menu_id = conn.execute("INSERT INTO menus (name) VALUES (?)", (menu["name"],)).lastrowid
            conn.executemany(
                "INSERT INTO menu_items (menu_id, recipe_id, day, meal, servings) VALUES (?, ?, ?, ?, ?)",
                [(menu_id, recipe_ids[item["recipe"]], item["day"], item["meal"], item["servings"])
                 for item in menu["items"]])
            added["menus"] += 1
    return added
