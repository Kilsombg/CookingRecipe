import sqlite3

import pytest

import config
import db


@pytest.fixture
def conn(tmp_path):
    paths = {"db_path": tmp_path / "test.db", "migrations_dir": config.MIGRATIONS_DIR,
             "backups_dir": tmp_path / "backups", "images_dir": tmp_path / "images"}
    db.init_db(**paths)
    conn = db.connect(paths["db_path"])
    yield conn
    conn.close()


def unit_id(conn, name):
    return conn.execute("SELECT id FROM units WHERE name = ?", (name,)).fetchone()["id"]


def recipe(**overrides):
    return {"title": "Пиле с ориз", "servings": 2, "prep_minutes": None, "cook_minutes": 30,
            "instructions": "Сварете ориза.", "notes": None} | overrides


def line(name, quantity=None, unit=None, note=None):
    return {"name": name, "quantity": quantity, "unit_id": unit, "note": note}


def test_find_ingredient_ignores_case_and_spaces(conn):
    ingredient_id = db.create_ingredient(conn, "Пилешко филе")
    assert db.find_ingredient(conn, "  ПИЛЕШКО   филе ")["id"] == ingredient_id
    assert db.find_ingredient(conn, "Пилешко") is None


def test_duplicate_ingredient_is_rejected(conn):
    db.create_ingredient(conn, "Яйца")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_ingredient(conn, "яйца")


def test_list_and_search_ingredients(conn):
    for name in ["Яйца", "агнешко", "Брашно", "Пилешко филе"]:
        db.create_ingredient(conn, name)
    assert [r["name"] for r in db.list_ingredients(conn)] == ["агнешко", "Брашно", "Пилешко филе", "Яйца"]
    assert [r["name"] for r in db.list_ingredients(conn, "ШКО")] == ["агнешко", "Пилешко филе"]
    assert db.list_ingredients(conn, "%") == []


def test_create_recipe_adds_unknown_ingredients(conn):
    existing = db.create_ingredient(conn, "Ориз")
    g = unit_id(conn, "г")
    recipe_id = db.create_recipe(conn, recipe(), [
        line("ориз", 200, g),
        line("Пилешко филе", 300, g, "на кубчета"),
        line("Сол"),
    ])

    lines = db.get_recipe_lines(conn, recipe_id)
    assert [(r["name"], r["quantity"], r["unit"], r["note"]) for r in lines] == [
        ("Ориз", 200, "г", None),
        ("Пилешко филе", 300, "г", "на кубчета"),
        ("Сол", None, None, None),
    ]
    assert lines[0]["ingredient_id"] == existing
    assert db.ingredient_names(conn) == ["Ориз", "Пилешко филе", "Сол"]
    assert db.list_ingredients(conn)[0]["recipe_count"] == 1


def test_update_recipe_replaces_lines(conn):
    recipe_id = db.create_recipe(conn, recipe(), [line("Ориз"), line("Сол")])
    db.update_recipe(conn, recipe_id, recipe(title="Ориз със зеленчуци", servings=4),
                     [line("Моркови"), line("Ориз")])

    saved = db.get_recipe(conn, recipe_id)
    assert (saved["title"], saved["servings"]) == ("Ориз със зеленчуци", 4)
    assert [r["name"] for r in db.get_recipe_lines(conn, recipe_id)] == ["Моркови", "Ориз"]


def test_failed_recipe_save_leaves_nothing_behind(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.create_recipe(conn, recipe(), [line("Ориз"), line("Мляко", 200, 999)])  # no such unit
    assert db.list_recipes(conn) == []
    assert db.ingredient_names(conn) == []


def test_ingredient_in_use_cannot_be_deleted(conn):
    recipe_id = db.create_recipe(conn, recipe(), [line("Ориз")])
    rice = db.find_ingredient(conn, "Ориз")["id"]
    assert [r["title"] for r in db.recipes_using_ingredient(conn, rice)] == ["Пиле с ориз"]
    with pytest.raises(sqlite3.IntegrityError):
        db.delete_ingredient(conn, rice)

    db.delete_recipe(conn, recipe_id)
    assert db.recipes_using_ingredient(conn, rice) == []
    db.delete_ingredient(conn, rice)
    assert db.get_ingredient(conn, rice) is None
