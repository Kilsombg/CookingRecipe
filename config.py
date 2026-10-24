from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "recipes.db"
MIGRATIONS_DIR = BASE_DIR / "migrations"
BACKUPS_DIR = BASE_DIR / "backups"
IMAGES_DIR = BASE_DIR / "images"
