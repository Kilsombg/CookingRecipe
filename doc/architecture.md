# Architecture

## Overview

```
 Browser (localhost:5000)
        │  HTML forms / links
        ▼
 Flask app (app.py + routes)
        │  Jinja2 templates render the pages
        │  sqlite3 runs SQL
        ▼
 recipes.db  (SQLite file)        images/  (photo files)
        ▲
        │  applied on startup
 migrations/*.sql
```

Pages are rendered on the server: Flask builds the HTML with Jinja2 templates, and forms send data back with normal POST requests. JavaScript is only used for small conveniences:
- adding/removing ingredient rows on the recipe form
- ticking shopping-list items without reloading the page

Ingredient autocomplete uses a plain HTML `<datalist>` filled with all the catalogue names. A personal catalogue holds a few hundred items at most, so no search API is needed.

## Tech stack

| Layer | Tool | Version |
|-------|------|---------|
| Language | Python | 3.12+ |
| Web framework | Flask | 3.x |
| Templates | Jinja2 (comes with Flask) | — |
| Database | SQLite through Python's `sqlite3` module (no ORM) | — |
| Image resizing | Pillow | latest |
| CSS | Pico.css, saved in `static/` | 2.x |

Dependencies (`requirements.txt`): `flask`, `pillow`, plus `pytest` for tests.

Raw SQL instead of an ORM such as SQLAlchemy keeps the project small and easy to understand. All SQL lives in `db.py`, and all changes to the database structure live in `migrations/`.

## Folder layout

```
CookingRecipe/
├── app.py                 # creates the Flask app, registers routes, runs the server
├── db.py                  # connection setup, migration runner, query functions
├── config.py              # paths (DB file, images, backups, migrations), upload limits
├── i18n.py                # UI language: current language, t() lookup, language switch route
├── translations.py        # UI texts: {"en": {...}, "bg": {...}}
├── migrations/            # numbered SQL files, applied in order on startup
│   └── 0001_initial.sql
├── routes/
│   ├── recipes.py         # recipe list, detail, create/edit/delete, photo upload
│   ├── ingredients.py     # ingredient catalogue
│   ├── units.py           # units page
│   ├── menus.py           # menus and menu items
│   └── shopping.py        # shopping list from a menu
├── services/
│   ├── text.py            # name_key() / casefold helpers for Cyrillic
│   ├── forms.py           # form parsing/validation (numbers accept "0,5" and "0.5"), errors as translation keys
│   ├── macros.py          # grams conversion, recipe and menu macro totals
│   └── shopping_list.py   # merging and scaling ingredients
├── templates/
│   ├── base.html          # layout, navigation, flash messages, <meta charset="utf-8">
│   ├── macros.html        # form error helpers
│   ├── recipes/           # list.html, detail.html, form.html
│   ├── ingredients/       # list.html, form.html
│   ├── units/             # list.html
│   ├── menus/             # list.html, detail.html, form.html
│   └── shopping/          # list.html
├── static/
│   ├── pico.min.css
│   ├── app.css            # small custom styles (card grid, print styles)
│   ├── app.js             # ingredient rows, shopping-list ticks
│   └── placeholder.png    # shown when a recipe has no photo
├── images/                # uploaded photos (not committed to git)
├── backups/               # automatic DB copies made before migrations (not committed)
├── tests/                 # pytest tests for services/ and db.py
├── recipes.db             # created on first run (not committed to git)
├── requirements.txt
├── start.bat              # double-click launcher
└── doc/                   # this documentation
```

`services/` contains plain functions: data goes in, results come out, with no Flask or database code. That keeps the calculations easy to test.

## Pages and routes

| Method | URL | Purpose |
|--------|-----|---------|
| GET | `/` | Redirects to `/recipes` |
| GET | `/recipes?q=&tag=` | Recipe card grid, with search and tag filter |
| GET | `/recipes/new` | New recipe form |
| POST | `/recipes` | Create a recipe (adds new ingredient names to the catalogue) |
| GET | `/recipes/<id>` | Recipe detail with calculated macros |
| GET | `/recipes/<id>/edit` | Edit form |
| POST | `/recipes/<id>` | Update a recipe |
| POST | `/recipes/<id>/delete` | Delete a recipe (and its photo file) |
| GET | `/images/<filename>` | Serve an uploaded photo |
| GET | `/ingredients?q=&missing=1` | Ingredient catalogue, with search and a "missing macros" filter |
| GET | `/ingredients/new` | New ingredient form |
| POST | `/ingredients` | Create an ingredient |
| GET | `/ingredients/<id>/edit` | Edit form (macros per 100 g, grams per piece) |
| POST | `/ingredients/<id>` | Update an ingredient |
| POST | `/ingredients/<id>/delete` | Delete, only if no recipe uses it |
| GET | `/units` | List of units, with an inline add/rename form |
| POST | `/units` | Add a unit |
| POST | `/units/<id>` | Rename a unit or change its grams |
| GET | `/menus` | List of menus |
| POST | `/menus` | Create a menu |
| GET | `/menus/<id>` | Menu detail, grouped by day/meal, with macro totals |
| POST | `/menus/<id>` | Rename a menu |
| POST | `/menus/<id>/delete` | Delete a menu |
| POST | `/menus/<id>/items` | Add a recipe to a menu |
| POST | `/menus/<id>/items/<item_id>/delete` | Remove a recipe from a menu |
| GET | `/menus/<id>/shopping` | Shopping list for the menu |
| POST | `/menus/<id>/shopping/regenerate` | Rebuild the list from the current menu |
| POST | `/shopping/items` | Add an item by hand |
| POST | `/shopping/items/<id>/toggle` | Tick or untick an item (called from JS) |
| POST | `/language` | Switch the UI language (`en` / `bg`), then go back to the same page |

HTML forms can only send GET and POST, so updates and deletes use POST with `/delete` or a plain POST to the resource URL.

## Cyrillic text handling

| Where | What we do |
|-------|------------|
| HTML | `<meta charset="utf-8">` in `base.html`. Flask sends UTF-8 by default |
| Forms | The browser sends UTF-8 and Flask decodes it, so nothing extra is needed |
| Database | SQLite `TEXT` is UTF-8. Every connection registers a `casefold()` SQL function for case-insensitive search and sorting |
| Files | Always `open(..., encoding="utf-8")`. `start.bat` sets `PYTHONUTF8=1` |
| Names | `services/text.py: name_key(s)` = `" ".join(s.split()).casefold()`, used for ingredient uniqueness and tags |
| URLs | Pages use numeric ids, never names, so Cyrillic never appears in URLs |
| Photos | Saved under random UUID file names, so a Bulgarian original file name doesn't matter |

## Interface language (English / Bulgarian)

Only the app's own UI texts are translated. Everything the user enters (recipes, ingredients, tags, menu names, units, shopping items) is shown exactly as stored, in both languages. The name "CookingRecipe" is never translated.

A small home-made solution, with no extra dependency (Flask-Babel and `.po` files would be overkill for two languages and one user):

- **`translations.py`** holds one dictionary per language with the same keys:
  ```python
  TEXTS = {
      "en": {"nav.recipes": "Recipes", "nav.ingredients": "Ingredients", "nav.menus": "Menus",
             "btn.save": "Save", "day.0": "Monday", "meal.breakfast": "Breakfast", ...},
      "bg": {"nav.recipes": "Рецепти", "nav.ingredients": "Съставки", "nav.menus": "Менюта",
             "btn.save": "Запази", "day.0": "Понеделник", "meal.breakfast": "Закуска", ...},
  }
  ```
  Keys are grouped by prefix: `nav.`, `btn.`, `label.`, `msg.`, `day.`, `meal.`, and one prefix per page (`recipes.`, `menus.`…).
- **`i18n.py`**:
  - `get_lang()` reads the `lang` cookie; anything other than `en`/`bg` falls back to `en` (the default).
  - `t(key, **params)` returns the text for the current language, filling in `{placeholders}` (e.g. `t("msg.deleted", name=recipe.title)`). A key missing in Bulgarian falls back to English, and a key missing everywhere shows the key itself, so a gap is visible but never crashes the page.
  - `t` and the current `lang` are registered as Jinja globals, so templates use `{{ t("nav.recipes") }}`.
  - `POST /language` sets the `lang` cookie (valid 1 year) and redirects back to the page it came from.
- **Templates**: `base.html` sets `<html lang="{{ lang }}">` and shows the `EN | БГ` switch in the navigation. No UI text is written directly in a template; it always goes through `t()`.
- **Python code**: flash messages and validation errors use `t()` too.
- **JavaScript**: confirmation texts are passed from the template in `data-` attributes (`data-confirm="{{ t('recipes.confirm_delete') }}"`), so `app.js` has no texts of its own.
- **Numbers** are shown with the language's decimal separator through the `num` Jinja filter (`0.5` → `0,5` in Bulgarian). Forms accept either separator.
- **Stored values stay language-neutral**: meals are stored as `breakfast`/`lunch`/… and days as `0`–`6`, and are shown through `t("meal." + meal)` and `t("day." + day)`. Changing the language never touches the database.

Tests check that `en` and `bg` in `translations.py` have exactly the same keys, and that every key used in templates, routes and `services/forms.py` exists.

## Photo handling

1. The form uploads a file. Only `jpg`, `jpeg`, `png` and `webp` are accepted, up to 10 MB.
2. Pillow opens it, fixes the rotation from phone photos (EXIF), resizes it to at most 1600 px, and saves it as JPEG.
3. The file name is a random UUID, e.g. `images/3f2a…c1.jpg`. Only the file name is stored in `recipes.photo_filename`.
4. When a photo is replaced or its recipe deleted, the old file is deleted from disk.
5. If `photo_filename` is NULL, the page shows `static/placeholder.png`.

## Running

- `python app.py` starts Flask on `127.0.0.1:5000`, so it is only reachable from this PC.
- On start, `db.py`:
  1. creates `images/` and `backups/` if they don't exist
  2. opens `recipes.db` (SQLite creates the file if needed)
  3. runs any migrations from `migrations/` that haven't been applied yet, after backing up the database (see [database.md](database.md#migrations))
- `start.bat` activates the virtual environment, starts the app, and opens the browser:

```bat
@echo off
cd /d %~dp0
set PYTHONUTF8=1
call .venv\Scripts\activate
start "" http://localhost:5000
python app.py
```

## Testing

- `pytest` tests the logic in `services/`:
  - `macros.py`: converting to grams for every kind of unit, `бр.` with and without grams per piece, missing macros, NULL quantities, per-serving division
  - `shopping_list.py`: merging, scaling, NULL quantities
  - `text.py`: Cyrillic case folding (`"  Пилешко   ФИЛЕ " → "пилешко филе"`)
- `translations.py`: English and Bulgarian have the same set of keys. `i18n.py`: fallback to English, unknown cookie value, placeholders.
- `db.py` tests use a temporary SQLite file. They check that all migrations apply cleanly to an empty database, and that Bulgarian text is saved and loaded correctly.
- `tests/test_routes.py` drives the main flows through Flask's test client (create/edit/delete, validation errors, blocked ingredient delete). Layout and JavaScript are checked by hand in the browser.
