# Roadmap

Each milestone ends with something you can actually use. Work through them in order.

## M0 — Project setup
- [x] `git init`, `.gitignore` (`.venv/`, `recipes.db`, `images/`, `backups/`, `__pycache__/`)
- [x] Virtual environment, `requirements.txt` (`flask`, `pillow`, `pytest`)
- [x] `app.py` with a "Здравей" page on `localhost:5000` (checks that Cyrillic displays correctly)
- [x] `base.html` layout with Pico.css, UTF-8, and navigation (Recipes · Ingredients · Menus)
- [x] `start.bat`

## M1 — Database and migrations
- [x] `migrations/0001_initial.sql` (all tables + starting units)
- [x] Migration runner in `db.py`: `user_version`, one transaction per file, backup before migrating
- [x] `casefold` SQL function registered on every connection
- [x] `services/text.py` + tests
- [x] Tests: migrations apply to an empty database; Bulgarian text is saved and loaded correctly

## M2 — Interface language (English / Bulgarian)
- [x] `translations.py` with `en` and `bg` texts for everything that exists so far (navigation, home page)
- [x] `i18n.py`: `get_lang()` from the `lang` cookie (default `en`), `t()` with fallback to English, Jinja globals
- [x] `POST /language` + `EN | БГ` switch in the navigation; `<html lang>` follows the chosen language
- [x] Test: `en` and `bg` have the same keys

**From here on:** every new page, button, message and label is added to `translations.py` in both languages, never written directly in a template. Recipe content is never translated.

## M3 — Ingredients and recipes (core)
- [x] Ingredient catalogue: list, add, edit, delete (blocked when the ingredient is used)
- [x] Create / edit / delete a recipe, with ingredient rows you can add or remove (`<datalist>` autocomplete, unknown names added to the catalogue automatically)
- [x] Recipe detail page
- [x] Recipe list as a card grid

**Done when:** you can type in your Notepad recipes, in Bulgarian, and stop using Notepad.

## M4 — Macros
- [ ] `services/macros.py` with tests (grams conversion, missing data, per serving)
- [ ] Macros per 100 g and grams per piece on the ingredient form
- [ ] Total and per-serving macros on the recipe page, with a list of incomplete ingredients
- [ ] Calories per serving on the recipe cards
- [ ] "Missing macros" filter on the ingredients page

## M5 — Photos, links, tags, search
- [ ] Photo upload with Pillow resize, plus a placeholder when there is no photo
- [ ] Source link shown as a clickable link when present
- [ ] Tags: add on the form, filter on the list
- [ ] Search by title or ingredient, ignoring Cyrillic upper/lower case

## M6 — Menus
- [ ] Create, rename and delete menus
- [ ] Add a recipe to a menu with day, meal and servings
- [ ] Menu page grouped by day and meal
- [ ] Macro totals per day and for the whole menu

## M7 — Shopping list
- [ ] `services/shopping_list.py` with tests (merging by ingredient + unit, scaling, NULL quantities)
- [ ] Build the list from a menu and save it in `shopping_items`
- [ ] Tick items off (JS + POST), add items by hand, regenerate
- [ ] Print styles

## M8 — Units page
- [ ] View, rename and add units

## Later (pick any)
- Favourites / "last cooked"
- Copy a menu
- JSON export/import
- Density per ingredient for more accurate volume units
- Merge different weight units in the shopping list
- Access from a phone on the home Wi-Fi (run on `0.0.0.0` and allow it through Windows Firewall)
