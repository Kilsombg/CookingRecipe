import re
import sqlite3
from datetime import datetime

import config
from services.text import casefold

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
