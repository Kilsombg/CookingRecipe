from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "recipes.db"
MIGRATIONS_DIR = BASE_DIR / "migrations"
BACKUPS_DIR = BASE_DIR / "backups"
IMAGES_DIR = BASE_DIR / "images"

MAX_PHOTO_BYTES = 10 * 1024 * 1024  # largest photo upload accepted
PHOTO_MAX_SIDE = 1600               # photos are resized to fit in this many pixels
