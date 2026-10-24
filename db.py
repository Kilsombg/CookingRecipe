import re
import sqlite3
from datetime import datetime

from flask import current_app, g

import config
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


# --- Ingredients ---

def list_ingredients(conn, q=""):
    """All ingredients (or those whose name contains `q`), with how many recipes use each."""
    sql = """SELECT i.id, i.name, COUNT(DISTINCT ri.recipe_id) AS recipe_count
             FROM ingredients i
             LEFT JOIN recipe_ingredients ri ON ri.ingredient_id = i.id"""
    params = []
    if q:
        sql += " WHERE i.name_key LIKE ? ESCAPE '\\'"
        params.append(_contains(q))
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


def create_ingredient(conn, name):
    with conn:
        return _insert_ingredient(conn, name)


def _insert_ingredient(conn, name):
    cur = conn.execute("INSERT INTO ingredients (name, name_key) VALUES (?, ?)", (name, name_key(name)))
    return cur.lastrowid


def update_ingredient(conn, ingredient_id, name):
    with conn:
        conn.execute("UPDATE ingredients SET name = ?, name_key = ? WHERE id = ?",
                     (name, name_key(name), ingredient_id))


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

def list_recipes(conn):
    return conn.execute(
        """SELECT id, title, servings, prep_minutes, cook_minutes
           FROM recipes ORDER BY casefold(title)""").fetchall()


def get_recipe(conn, recipe_id):
    return conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()


def get_recipe_lines(conn, recipe_id):
    """The recipe's ingredient lines in order, with ingredient and unit names."""
    return conn.execute(
        """SELECT ri.quantity, ri.unit_id, ri.note,
                  i.id AS ingredient_id, i.name, u.name AS unit
           FROM recipe_ingredients ri
           JOIN ingredients i ON i.id = ri.ingredient_id
           LEFT JOIN units u ON u.id = ri.unit_id
           WHERE ri.recipe_id = ?
           ORDER BY ri.position""", (recipe_id,)).fetchall()


def create_recipe(conn, recipe, lines):
    """Insert a recipe and its lines; unknown ingredient names are added to the catalogue."""
    with conn:
        cur = conn.execute(
            """INSERT INTO recipes (title, servings, prep_minutes, cook_minutes, instructions, notes)
               VALUES (:title, :servings, :prep_minutes, :cook_minutes, :instructions, :notes)""",
            recipe)
        _save_lines(conn, cur.lastrowid, lines)
    return cur.lastrowid


def update_recipe(conn, recipe_id, recipe, lines):
    with conn:
        conn.execute(
            """UPDATE recipes
               SET title = :title, servings = :servings, prep_minutes = :prep_minutes,
                   cook_minutes = :cook_minutes, instructions = :instructions, notes = :notes,
                   updated_at = datetime('now')
               WHERE id = :id""",
            {**recipe, "id": recipe_id})
        conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
        _save_lines(conn, recipe_id, lines)


def delete_recipe(conn, recipe_id):
    with conn:
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))


def _save_lines(conn, recipe_id, lines):
    for position, line in enumerate(lines, start=1):
        existing = find_ingredient(conn, line["name"])
        ingredient_id = existing["id"] if existing else _insert_ingredient(conn, line["name"])
        conn.execute(
            """INSERT INTO recipe_ingredients (recipe_id, ingredient_id, position, quantity, unit_id, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (recipe_id, ingredient_id, position, line["quantity"], line["unit_id"], line["note"]))
