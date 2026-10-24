import json
import sqlite3
from datetime import datetime

import pytest

import config
import db
from services.backup import build_export, parse_import


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


def test_ingredient_values_are_saved(conn):
    eggs = db.create_ingredient(conn, "Яйца", {"calories_100g": 143, "grams_per_piece": 55})
    saved = db.get_ingredient(conn, eggs)
    assert (saved["calories_100g"], saved["protein_100g"], saved["grams_per_piece"]) == (143, None, 55)

    db.update_ingredient(conn, eggs, "Яйца", {"calories_100g": 140, "protein_100g": 12.6, "carbs_100g": 0.7,
                                              "fat_100g": 9.5, "grams_per_piece": None})
    saved = db.get_ingredient(conn, eggs)
    assert (saved["calories_100g"], saved["protein_100g"], saved["grams_per_piece"]) == (140, 12.6, None)


def test_missing_data_filter(conn):
    full = {"calories_100g": 110, "protein_100g": 23, "carbs_100g": 0, "fat_100g": 1.5}
    db.create_ingredient(conn, "Пилешко филе", full)
    db.create_ingredient(conn, "Зехтин", full | {"fat_100g": None})
    db.create_ingredient(conn, "Яйца", full)           # used in pieces below, without grams per piece
    db.create_ingredient(conn, "Лимон", full)          # has grams per piece, so pieces are fine
    db.create_ingredient(conn, "Тиквичка", full)       # no grams per piece, but only used in grams
    db.update_ingredient(conn, db.find_ingredient(conn, "Лимон")["id"], "Лимон", full | {"grams_per_piece": 100})
    db.create_recipe(conn, recipe(), [
        line("Яйца", 2, unit_id(conn, "бр.")),
        line("Лимон", 1, unit_id(conn, "бр.")),
        line("Тиквичка", 300, unit_id(conn, "г")),
    ])

    assert [r["name"] for r in db.list_ingredients(conn, missing=True)] == ["Зехтин", "Яйца"]
    assert [r["name"] for r in db.list_ingredients(conn, "яй", missing=True)] == ["Яйца"]
    assert len(db.list_ingredients(conn)) == 5


def titles(rows):
    return [r["title"] for r in rows]


def test_search_recipes_by_title_or_ingredient(conn):
    db.create_recipe(conn, recipe(title="Пиле с ориз"), [line("Ориз")])
    db.create_recipe(conn, recipe(title="Омлет"), [line("Яйца"), line("Пилешко филе")])
    db.create_recipe(conn, recipe(title="Боб чорба"), [line("Боб")])

    assert titles(db.list_recipes(conn)) == ["Боб чорба", "Омлет", "Пиле с ориз"]
    assert titles(db.list_recipes(conn, "ПИЛЕ")) == ["Омлет", "Пиле с ориз"]   # title, or the ingredient
    assert titles(db.list_recipes(conn, "яйца")) == ["Омлет"]
    assert titles(db.list_recipes(conn, "  боб   чорба ")) == ["Боб чорба"]
    assert titles(db.list_recipes(conn, "%")) == []


def test_recipe_tags_are_saved_replaced_and_filtered(conn):
    lunch = db.create_recipe(conn, recipe(tags=["обяд", "бързо"]), [line("Ориз")])
    omelette = db.create_recipe(conn, recipe(title="Омлет", tags=["закуска", "бързо"]), [line("Яйца")])

    assert [t["name"] for t in db.list_tags(conn)] == ["бързо", "закуска", "обяд"]
    assert [t["name"] for t in db.get_recipe_tags(conn, lunch)] == ["бързо", "обяд"]
    tag_ids = {t["name"]: t["id"] for t in db.list_tags(conn)}
    assert titles(db.list_recipes(conn, tag_id=tag_ids["бързо"])) == ["Омлет", "Пиле с ориз"]
    assert titles(db.list_recipes(conn, "ориз", tag_ids["бързо"])) == ["Пиле с ориз"]
    assert titles(db.list_recipes(conn, "ориз", tag_ids["закуска"])) == []
    assert [t["name"] for t in db.tags_by_recipe(conn)[omelette]] == ["бързо", "закуска"]

    # A tag no recipe uses any more is removed
    db.update_recipe(conn, lunch, recipe(tags=["вечеря"]), [line("Ориз")])
    assert [t["name"] for t in db.get_recipe_tags(conn, lunch)] == ["вечеря"]
    assert [t["name"] for t in db.list_tags(conn)] == ["бързо", "вечеря", "закуска"]
    db.delete_recipe(conn, omelette)
    assert [t["name"] for t in db.list_tags(conn)] == ["вечеря"]
    assert conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0] == 1


def test_recipe_photo_and_source_are_saved(conn):
    recipe_id = db.create_recipe(conn, recipe(photo_filename="abc.jpg", source_url="https://youtube.com/x"),
                                 [line("Ориз")])
    saved = db.get_recipe(conn, recipe_id)
    assert (saved["photo_filename"], saved["source_url"]) == ("abc.jpg", "https://youtube.com/x")
    assert db.list_recipes(conn)[0]["photo_filename"] == "abc.jpg"

    db.update_recipe(conn, recipe_id, recipe(photo_filename=None), [line("Ориз")])
    saved = db.get_recipe(conn, recipe_id)
    assert (saved["photo_filename"], saved["source_url"]) == (None, None)


def test_lines_carry_macro_data(conn):
    db.create_ingredient(conn, "Яйца", {"calories_100g": 143, "grams_per_piece": 55})
    first = db.create_recipe(conn, recipe(), [line("Яйца", 2, unit_id(conn, "бр.")), line("Сол")])
    second = db.create_recipe(conn, recipe(title="Омлет"), [line("Яйца", 3, unit_id(conn, "бр."))])

    eggs = db.get_recipe_lines(conn, first)[0]
    assert (eggs["unit_grams"], eggs["grams_per_piece"], eggs["calories_100g"]) == (None, 55, 143)

    grouped = db.lines_by_recipe(conn)
    assert [r["name"] for r in grouped[first]] == ["Яйца", "Сол"]
    assert [r["quantity"] for r in grouped[second]] == [3]


def test_menus_and_items(conn):
    recipe_id = db.create_recipe(conn, recipe(), [line("Ориз")])
    first = db.create_menu(conn, "Седмица 12 ноември")
    second = db.create_menu(conn, "Рожден ден")
    db.add_menu_item(conn, first, {"recipe_id": recipe_id, "day": 0, "meal": "lunch", "servings": 2})
    db.add_menu_item(conn, first, {"recipe_id": recipe_id, "day": None, "meal": None, "servings": 1.5})

    assert [(m["name"], m["item_count"]) for m in db.list_menus(conn)] == [
        ("Рожден ден", 0), ("Седмица 12 ноември", 2)]
    items = db.get_menu_items(conn, first)
    assert [(i["title"], i["recipe_servings"], i["day"], i["meal"], i["servings"]) for i in items] == [
        ("Пиле с ориз", 2, 0, "lunch", 2), ("Пиле с ориз", 2, None, None, 1.5)]

    assert not db.delete_menu_item(conn, second, items[0]["id"])  # not an item of that menu
    assert db.delete_menu_item(conn, first, items[0]["id"])
    db.rename_menu(conn, first, "Седмица 19 ноември")
    assert db.get_menu(conn, first)["name"] == "Седмица 19 ноември"


def test_deleting_a_recipe_or_menu_removes_its_items(conn):
    recipe_id = db.create_recipe(conn, recipe(), [line("Ориз")])
    menu_id = db.create_menu(conn, "Седмица")
    db.add_menu_item(conn, menu_id, {"recipe_id": recipe_id, "day": 0, "meal": None, "servings": 1})
    db.delete_recipe(conn, recipe_id)
    assert db.get_menu_items(conn, menu_id) == []

    db.add_menu_item(conn, menu_id, {"recipe_id": db.create_recipe(conn, recipe(), [line("Ориз")]),
                                     "day": 0, "meal": None, "servings": 1})
    db.delete_menu(conn, menu_id)
    assert conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0] == 0


def shopping(conn, menu_id):
    return [(i["name"], i["quantity"], i["unit"], i["checked"], i["is_manual"])
            for i in db.get_shopping_items(conn, menu_id)]


def test_shopping_items_rebuild_keeps_manual_items_and_unchanged_ticks(conn):
    menu_id = db.create_menu(conn, "Седмица")
    assert not db.has_built_shopping_items(conn, menu_id)
    db.replace_shopping_items(conn, menu_id, [{"name": "Ориз", "quantity": 200, "unit": "г"},
                                              {"name": "Сол", "quantity": None, "unit": None}])
    manual_id = db.add_shopping_item(conn, menu_id, {"name": "Тоалетна хартия", "quantity": None, "unit": None})
    assert db.has_built_shopping_items(conn, menu_id)
    rice, salt, _ = [i["id"] for i in db.get_shopping_items(conn, menu_id)]
    for item_id in (rice, salt, manual_id):
        assert db.set_shopping_item_checked(conn, item_id, True)
    assert not db.set_shopping_item_checked(conn, 999, True)

    # The rice amount changed, so it needs buying again; the salt is the same and stays ticked
    db.replace_shopping_items(conn, menu_id, [{"name": "Сол", "quantity": None, "unit": None},
                                              {"name": "Ориз", "quantity": 300, "unit": "г"}])
    assert shopping(conn, menu_id) == [("Сол", None, None, 1, 0), ("Ориз", 300, "г", 0, 0),
                                       ("Тоалетна хартия", None, None, 1, 1)]


def test_only_manual_shopping_items_can_be_deleted(conn):
    menu_id = db.create_menu(conn, "Седмица")
    db.replace_shopping_items(conn, menu_id, [{"name": "Ориз", "quantity": 200, "unit": "г"}])
    manual_id = db.add_shopping_item(conn, menu_id, {"name": "Мляко", "quantity": 1, "unit": "л"})
    built_id = db.get_shopping_items(conn, menu_id)[0]["id"]
    assert not db.delete_shopping_item(conn, built_id)
    assert db.delete_shopping_item(conn, manual_id)
    assert shopping(conn, menu_id) == [("Ориз", 200, "г", 0, 0)]

    db.delete_menu(conn, menu_id)
    assert conn.execute("SELECT COUNT(*) FROM shopping_items").fetchone()[0] == 0


def test_units_add_rename_and_usage(conn):
    cup = db.create_unit(conn, {"name": "Чаша", "grams": 240})
    assert db.find_unit(conn, "чаша")["id"] == cup   # ignoring case
    assert db.find_unit(conn, "чаени чаши") is None
    db.create_recipe(conn, recipe(), [line("Брашно", 2, cup), line("Захар", 1, cup)])

    db.update_unit(conn, cup, {"name": "ч. чаша", "grams": 250})
    assert dict(db.get_unit(conn, cup)) == {"id": cup, "name": "ч. чаша", "grams": 250}
    usage = {u["name"]: u["recipe_count"] for u in db.list_units_with_usage(conn)}
    assert usage["ч. чаша"] == 1 and usage["г"] == 0
    assert len(usage) == len(db.list_units(conn)) == 9


def test_unit_in_use_cannot_be_deleted(conn):
    cup = db.create_unit(conn, {"name": "чаша", "grams": 240})
    spare = db.create_unit(conn, {"name": "глава", "grams": None})
    db.create_recipe(conn, recipe(), [line("Брашно", 2, cup)])
    with pytest.raises(sqlite3.IntegrityError):
        db.delete_unit(conn, cup)
    db.delete_unit(conn, spare)
    assert db.get_unit(conn, spare) is None and db.get_unit(conn, cup) is not None


def test_favourites(conn):
    lunch = db.create_recipe(conn, recipe(), [line("Ориз")])
    db.create_recipe(conn, recipe(title="Омлет"), [line("Яйца")])
    assert not db.has_favourites(conn)
    before = db.get_recipe(conn, lunch)["updated_at"]

    db.set_favourite(conn, lunch, True)
    assert db.has_favourites(conn)
    assert titles(db.list_recipes(conn, favourites=True)) == ["Пиле с ориз"]
    assert titles(db.list_recipes(conn, "омлет", favourites=True)) == []
    assert db.get_recipe(conn, lunch)["updated_at"] == before

    # Editing the recipe keeps the mark
    db.update_recipe(conn, lunch, recipe(title="Пиле с ориз и грах"), [line("Ориз")])
    assert db.get_recipe(conn, lunch)["is_favourite"] == 1
    db.set_favourite(conn, lunch, False)
    assert db.list_recipes(conn, favourites=True) == []


def test_copy_menu(conn):
    recipe_id = db.create_recipe(conn, recipe(), [line("Ориз")])
    menu_id = db.create_menu(conn, "Седмица")
    db.add_menu_item(conn, menu_id, {"recipe_id": recipe_id, "day": 0, "meal": "lunch", "servings": 2})
    db.add_menu_item(conn, menu_id, {"recipe_id": recipe_id, "day": None, "meal": None, "servings": 1.5})
    db.add_shopping_item(conn, menu_id, {"name": "Мляко", "quantity": None, "unit": None})

    copy_id = db.copy_menu(conn, menu_id, "Седмица (копие)")
    assert db.get_menu(conn, copy_id)["name"] == "Седмица (копие)"
    entries = lambda m: [(i["recipe_id"], i["day"], i["meal"], i["servings"]) for i in db.get_menu_items(conn, m)]
    assert entries(copy_id) == entries(menu_id)
    assert db.get_shopping_items(conn, copy_id) == []

    # The copy is independent of the original
    db.delete_menu(conn, menu_id)
    assert len(entries(copy_id)) == 2


def fill(conn):
    """Some of everything, for the export / import tests."""
    cup = db.create_unit(conn, {"name": "чаша", "grams": 240})
    db.create_ingredient(conn, "Яйца", {"calories_100g": 143, "grams_per_piece": 55})
    omelette = db.create_recipe(conn, recipe(title="Омлет", servings=1, tags=["закуска"],
                                             source_url="https://youtube.com/x"),
                                [line("Яйца", 3, unit_id(conn, "бр.")), line("Мляко", 0.5, cup), line("Сол")])
    db.set_favourite(conn, omelette, True)
    lunch = db.create_recipe(conn, recipe(), [line("Ориз", 200, unit_id(conn, "г"), "измит")])
    menu_id = db.create_menu(conn, "Седмица")
    db.add_menu_item(conn, menu_id, {"recipe_id": omelette, "day": 0, "meal": "breakfast", "servings": 2})
    db.add_menu_item(conn, menu_id, {"recipe_id": lunch, "day": None, "meal": None, "servings": 1.5})


def without_ids(data):
    """The export, with recipe ids replaced by their position, so two databases can be compared."""
    position = {r["id"]: i for i, r in enumerate(data["recipes"])}
    return {**data,
            "recipes": [{**r, "id": position[r["id"]]} for r in data["recipes"]],
            "menus": [{**m, "items": [{**item, "recipe": position[item["recipe"]]} for item in m["items"]]}
                      for m in data["menus"]]}


def test_export_and_import_into_an_empty_database(conn, tmp_path):
    fill(conn)
    data = db.export_data(conn)
    assert data["recipes"][0]["is_favourite"] is True
    assert data["recipes"][0]["ingredients"][1] == {"name": "Мляко", "quantity": 0.5, "unit": "чаша", "note": None}
    raw = json.dumps(build_export(data, datetime.now()), ensure_ascii=False).encode("utf-8")

    db.init_db(tmp_path / "other.db", config.MIGRATIONS_DIR, tmp_path / "backups", tmp_path / "images")
    other = db.connect(tmp_path / "other.db")
    added = db.import_data(other, parse_import(raw))
    assert added == {"units": 1, "ingredients": 4, "recipes": 2, "menus": 1}  # the 8 starting units are there
    assert without_ids(db.export_data(other)) == without_ids(data)
    other.close()


def test_import_keeps_what_is_already_there(conn):
    fill(conn)
    raw = json.dumps({"format": "CookingRecipe", "version": 1, **db.export_data(conn)}).encode("utf-8")
    before = db.export_data(conn)
    db.update_unit(conn, db.find_unit(conn, "чаша")["id"], {"name": "Чаша", "grams": 250})
    db.update_ingredient(conn, db.find_ingredient(conn, "Яйца")["id"], "ЯЙЦА", {"calories_100g": 150})

    # Importing the same file again adds nothing, and changes nothing that was edited since
    assert db.import_data(conn, parse_import(raw)) == {"units": 0, "ingredients": 0, "recipes": 0, "menus": 0}
    assert db.find_unit(conn, "чаша")["grams"] == 250
    assert db.find_ingredient(conn, "яйца")["calories_100g"] == 150
    assert len(db.export_data(conn)["recipes"]) == len(before["recipes"])

    # A new menu in the file that uses an existing recipe points at the one already here
    data = json.loads(raw)
    data["menus"] = [{"name": "Рожден ден", "items": [{"recipe": data["recipes"][0]["id"], "servings": 6}]}]
    data["recipes"].append({**data["recipes"][1], "id": 99, "title": "Баница"})
    assert db.import_data(conn, parse_import(json.dumps(data).encode("utf-8"))) == {
        "units": 0, "ingredients": 0, "recipes": 1, "menus": 1}
    party = next(m for m in db.list_menus(conn) if m["name"] == "Рожден ден")
    assert [i["title"] for i in db.get_menu_items(conn, party["id"])] == ["Омлет"]
