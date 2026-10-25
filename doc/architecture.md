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
│   ├── 0001_initial.sql
│   └── 0002_add_favourite.sql
├── routes/
│   ├── recipes.py         # recipe list, detail, create/edit/delete, photo upload
│   ├── ingredients.py     # ingredient catalogue
│   ├── units.py           # units page
│   ├── menus.py           # menus and menu items
│   ├── shopping.py        # shopping list from a menu
│   └── data.py            # JSON export / import
├── services/
│   ├── text.py            # name_key() / casefold helpers for Cyrillic
│   ├── forms.py           # form parsing/validation (numbers accept "0,5" and "0.5"), errors as translation keys
│   ├── photos.py          # photo check/resize with Pillow, saving and deleting the files
│   ├── macros.py          # grams conversion, recipe and menu macro totals
│   ├── shopping_list.py   # merging and scaling ingredients
│   ├── pagination.py      # ?page= / ?per_page= on the recipe and ingredient lists, which page links to show
│   └── backup.py          # JSON export file format, checking an uploaded file
├── templates/
│   ├── base.html          # layout, navigation, flash messages, <meta charset="utf-8">
│   ├── error.html         # simple error page (upload over the size limit)
│   ├── macros.html        # form error helpers, icon(), macro badges, pagination
│   ├── recipes/           # list.html, detail.html, form.html
│   ├── ingredients/       # list.html, form.html
│   ├── units/             # list.html
│   ├── menus/             # list.html (with the new-menu form), detail.html (add recipe, rename)
│   ├── shopping/          # list.html
│   └── data/              # index.html (export / import)
├── static/
│   ├── pico.min.css
│   ├── app.css            # the app's look: honey/paper colours over Pico, menu-style recipe list, cookbook recipe page, print styles
│   ├── app.js             # ingredient rows, shopping-list ticks
│   ├── icons.svg          # icon sprite (navigation, actions, recipe facts, macros, meals), used through icon() in macros.html
│   └── placeholder.svg    # shown on recipe plates without a photo
├── images/                # uploaded photos (not committed to git)
├── backups/               # automatic DB copies made before migrations (not committed)
├── tests/                 # pytest tests for services/ and db.py
├── recipes.db             # created on first run (not committed to git)
├── requirements.txt
├── start.bat              # double-click launcher
└── doc/                   # this documentation
```

`services/` contains plain functions: data goes in, results come out, with no Flask or database code. That keeps the calculations easy to test. (`photos.py` also writes and deletes files in the folder it is given.)

## Pages and routes

| Method | URL | Purpose |
|--------|-----|---------|
| GET | `/` | Redirects to `/recipes` |
| GET | `/recipes?q=&tag=&fav=1` | Recipe card grid. `q` searches titles and ingredient names (ignoring case); `tag` is a tag id; `fav=1` shows only favourites |
| GET | `/recipes/new` | New recipe form |
| POST | `/recipes` | Create a recipe (adds new ingredient names to the catalogue), with an optional photo |
| GET | `/recipes/<id>` | Recipe detail with calculated macros |
| GET | `/recipes/<id>/edit` | Edit form |
| POST | `/recipes/<id>` | Update a recipe; a new photo replaces the old one, `remove_photo=1` removes it |
| POST | `/recipes/<id>/favourite` | Mark (`favourite=1`) or unmark (`favourite=0`) a favourite |
| POST | `/recipes/<id>/delete` | Delete a recipe (and its photo file) |
| GET | `/images/<filename>` | Serve an uploaded photo |
| GET | `/ingredients?q=&missing=1` | Ingredient catalogue, with search and a "missing data" filter (a macro is empty, or a recipe uses it in pieces without grams per piece) |
| GET | `/ingredients/new` | New ingredient form |
| POST | `/ingredients` | Create an ingredient |
| GET | `/ingredients/<id>/edit?next=` | Edit form (macros per 100 g, grams per piece). `next` (a path on this site) is where Save and Cancel go back to, e.g. the recipe that linked here |
| POST | `/ingredients/<id>` | Update an ingredient |
| POST | `/ingredients/<id>/delete` | Delete, only if no recipe uses it |
| GET | `/units` | List of units with how many recipes use each, an inline edit form per unit, and an add form |
| POST | `/units` | Add a unit (name unique ignoring case; empty grams = a piece unit) |
| POST | `/units/<id>` | Rename a unit or change its grams |
| POST | `/units/<id>/delete` | Delete a unit, only if no recipe uses it |
| GET | `/menus` | List of menus |
| POST | `/menus` | Create a menu |
| GET | `/menus/<id>?day=&meal=` | Menu detail, grouped by day/meal, with macro totals. `day`/`meal` preselect the add-recipe form (set after adding a recipe) |
| POST | `/menus/<id>` | Rename a menu |
| POST | `/menus/<id>/copy` | Copy a menu with its recipes as "Name (copy)", then open the copy |
| POST | `/menus/<id>/delete` | Delete a menu |
| POST | `/menus/<id>/items` | Add a recipe to a menu |
| POST | `/menus/<id>/items/<item_id>/delete` | Remove a recipe from a menu |
| GET | `/menus/<id>/shopping` | Shopping list for the menu, built and saved on the first visit |
| POST | `/menus/<id>/shopping/regenerate` | Rebuild the list from the current menu |
| POST | `/shopping/items` | Add an item by hand (`menu_id` in the form) |
| POST | `/shopping/items/<id>/toggle` | Tick (`checked=1`) or untick (`checked=0`) an item; called from JS, answers 204 |
| POST | `/shopping/items/<id>/delete` | Remove an item added by hand |
| GET | `/data` | Export and import page |
| GET | `/data/export` | Download everything (except photos and shopping lists) as `cookingrecipe-YYYYMMDD-HHMMSS.json` |
| POST | `/data/import` | Add the contents of an exported file (`file` in the form), after backing up the database |
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
| URLs | Pages use numeric ids, never names, so Cyrillic never appears in URLs (the tag filter is `?tag=<id>` too). Only a typed search text can |
| Tags | Split on commas, each passed through `name_key()`, so "Закуска" and "закуска" are the same tag. A tag no recipe uses any more is deleted |
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

1. The form uploads a file. Only JPEG, PNG and WebP images are accepted (checked by what Pillow finds in the file, not by its name), up to 10 MB (`config.MAX_PHOTO_BYTES`). A request bigger than that plus 1 MB is stopped by Flask's `MAX_CONTENT_LENGTH` and shows `error.html`.
2. Pillow opens it, fixes the rotation from phone photos (EXIF), resizes it to at most 1600 px (`config.PHOTO_MAX_SIDE`), fills transparent parts with white, and saves it as JPEG.
3. The file name is a random UUID, e.g. `images/3f2a…c1.jpg`. Only the file name is stored in `recipes.photo_filename`.
4. When a photo is replaced or removed, or its recipe deleted, the old file is deleted from disk. If saving the recipe fails, the new file is deleted again.
5. If the form has other errors the photo isn't saved, and the form asks to choose it again (browsers can't refill a file input).
6. If `photo_filename` is NULL, recipe cards show `static/placeholder.svg`; the detail page just has no photo.

The source link is stored only when it is an `http`/`https` address (`youtube.com/…` gets `https://` added). It opens in a new tab with `rel="noopener noreferrer"`, and its text is the site name (`youtube.com`).

## JSON export / import

The file format is described at the top of `services/backup.py`. In short: one object with `units`, `ingredients`, `recipes` (with their ingredient lines and tags) and `menus`, plus a `format`/`version` header. Everything is referred to by name, except menu items, which point at a recipe's `id` inside the same file, because two recipes can have the same title. The file is UTF-8 with Cyrillic written as is, not as `\u` escapes, so it can be read in Notepad.

- **Not included:** photos (they would make the file huge; the photo files are in `images/`) and shopping lists (they are rebuilt from the menu).
- **Import adds, never replaces.** A unit, ingredient, recipe or menu that already exists with the same name (ignoring case) is kept exactly as it is, and the file's recipes and menus use the one that is already here. So importing the same file twice adds nothing the second time.
- **Checked first, saved in one go.** `parse_import()` checks the whole file with the same rules as the forms (required fields, numbers in range, `http`/`https` source links only, a quantity needs a unit), and reports the first problem with its place in the file, e.g. `recipes[2].servings`. Only a valid file is saved, in one transaction, after a copy of the database is made in `backups/`.

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
  - `backup.py`: every kind of bad value in an import file is rejected with its place in the file
  - `text.py`: Cyrillic case folding (`"  Пилешко   ФИЛЕ " → "пилешко филе"`)
  - `photos.py`: accepted formats, resizing, EXIF rotation, transparency, size limit
  - `pagination.py`: page slices, bad or unknown `?page=` / `?per_page=`, which page links and ellipses show
- `translations.py`: English and Bulgarian have the same set of keys. `i18n.py`: fallback to English, unknown cookie value, placeholders.
- `db.py` tests use a temporary SQLite file. They check that all migrations apply cleanly to an empty database, and that Bulgarian text is saved and loaded correctly.
- `tests/test_routes.py` drives the main flows through Flask's test client (create/edit/delete, validation errors, blocked ingredient delete). Layout and JavaScript are checked by hand in the browser.
