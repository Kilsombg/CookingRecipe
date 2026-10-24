import sqlite3

import pytest

import config
import db


@pytest.fixture
def paths(tmp_path):
    return {
        "db_path": tmp_path / "test.db",
        "migrations_dir": config.MIGRATIONS_DIR,
        "backups_dir": tmp_path / "backups",
        "images_dir": tmp_path / "images",
    }


@pytest.fixture
def conn(paths):
    db.init_db(**paths)
    conn = db.connect(paths["db_path"])
    yield conn
    conn.close()


def user_version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def test_migrations_apply_to_empty_database(conn, paths):
    latest = db.list_migrations(config.MIGRATIONS_DIR)[-1][0]
    assert user_version(conn) == latest

    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"ingredients", "units", "recipes", "recipe_ingredients", "tags", "recipe_tags",
            "menus", "menu_items", "shopping_items"} <= tables

    assert paths["images_dir"].is_dir()
    # A brand-new database has nothing to back up
    assert list(paths["backups_dir"].iterdir()) == []


def test_starting_units(conn):
    units = {r["name"]: r["grams"] for r in conn.execute("SELECT name, grams FROM units")}
    assert units == {"г": 1, "кг": 1000, "мл": 1, "л": 1000,
                     "ч.л.": 5, "с.л.": 15, "ч.ч.": 200, "бр.": None}


def test_running_again_does_nothing(conn, paths):
    assert db.migrate(conn, paths["migrations_dir"], paths["backups_dir"]) == []
    assert list(paths["backups_dir"].iterdir()) == []


def test_bulgarian_text_round_trip(conn):
    title = "Пиле с ориз"
    instructions = "Запържете лука…\nДобавете 200 г брашно."
    conn.execute("INSERT INTO recipes (title, instructions) VALUES (?, ?)", (title, instructions))
    conn.commit()

    row = conn.execute("SELECT title, instructions FROM recipes").fetchone()
    assert row["title"] == title
    assert row["instructions"] == instructions


def test_casefold_sql_function(conn):
    assert conn.execute("SELECT LOWER('Яйца')").fetchone()[0] == "Яйца"  # why we need it
    assert conn.execute("SELECT casefold('Яйца')").fetchone()[0] == "яйца"
    assert conn.execute("SELECT casefold(NULL)").fetchone()[0] is None


def test_casefold_search_and_sort(conn):
    for title in ["яйца на очи", "Баница", "Пиле с ориз", "агнешко"]:
        conn.execute("INSERT INTO recipes (title, instructions) VALUES (?, '')", (title,))

    found = conn.execute("SELECT title FROM recipes WHERE casefold(title) LIKE ?",
                         ("%" + "ПИЛЕ".casefold() + "%",)).fetchall()
    assert [r["title"] for r in found] == ["Пиле с ориз"]

    ordered = conn.execute("SELECT title FROM recipes ORDER BY casefold(title)").fetchall()
    assert [r["title"] for r in ordered] == ["агнешко", "Баница", "Пиле с ориз", "яйца на очи"]


def test_foreign_keys_enabled(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id, position) VALUES (999, 999, 1)")


def test_backup_before_migrating_existing_database(paths, tmp_path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_first.sql").write_text("CREATE TABLE t (name TEXT);", encoding="utf-8")
    paths["migrations_dir"] = migrations
    db.init_db(**paths)

    (migrations / "0002_second.sql").write_text(
        "INSERT INTO t (name) VALUES ('Здравей');", encoding="utf-8")
    db.init_db(**paths)

    backups = list(paths["backups_dir"].iterdir())
    assert len(backups) == 1
    old = sqlite3.connect(backups[0])
    assert old.execute("PRAGMA user_version").fetchone()[0] == 1
    old.close()

    conn = db.connect(paths["db_path"])
    assert user_version(conn) == 2
    assert conn.execute("SELECT name FROM t").fetchone()[0] == "Здравей"
    conn.close()


def test_failed_migration_is_rolled_back(paths, tmp_path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_ok.sql").write_text("CREATE TABLE a (x);", encoding="utf-8")
    (migrations / "0002_broken.sql").write_text(
        "CREATE TABLE b (x);\nINSERT INTO missing_table VALUES (1);", encoding="utf-8")
    paths["migrations_dir"] = migrations

    with pytest.raises(db.MigrationError, match="0002_broken.sql"):
        db.init_db(**paths)

    conn = db.connect(paths["db_path"])
    assert user_version(conn) == 1
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"a"}
    conn.close()


def test_bad_migration_file_name(paths, tmp_path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "1_oops.sql").write_text("", encoding="utf-8")
    paths["migrations_dir"] = migrations

    with pytest.raises(db.MigrationError, match="1_oops.sql"):
        db.init_db(**paths)
