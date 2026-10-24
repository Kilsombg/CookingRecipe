# Roadmap

Each milestone ends with something you can actually use. Work through them in order.

## M0 — Project setup
- [ ] `git init`, `.gitignore` (`.venv/`, `recipes.db`, `images/`, `backups/`, `__pycache__/`)
- [ ] Virtual environment, `requirements.txt` (`flask`, `pillow`, `pytest`)
- [ ] `app.py` with a "Здравей" page on `localhost:5000` (checks that Cyrillic displays correctly)
- [ ] `base.html` layout with Pico.css, UTF-8, and navigation (Recipes · Ingredients · Menus)
- [ ] `start.bat`

## M1 — Database and migrations
- [ ] `migrations/0001_initial.sql` (all tables + starting units)
- [ ] Migration runner in `db.py`: `user_version`, one transaction per file, backup before migrating
- [ ] `casefold` SQL function registered on every connection
- [ ] `services/text.py` + tests
- [ ] Tests: migrations apply to an empty database; Bulgarian text is saved and loaded correctly

## M2 — Ingredients and recipes (core)
- [ ] Ingredient catalogue: list, add, edit, delete (blocked when the ingredient is used)
- [ ] Create / edit / delete a recipe, with ingredient rows you can add or remove (`<datalist>` autocomplete, unknown names added to the catalogue automatically)
- [ ] Recipe detail page
- [ ] Recipe list as a card grid

**Done when:** you can type in your Notepad recipes, in Bulgarian, and stop using Notepad.

## M3 — Macros
- [ ] `services/macros.py` with tests (grams conversion, missing data, per serving)
- [ ] Macros per 100 g and grams per piece on the ingredient form
- [ ] Total and per-serving macros on the recipe page, with a list of incomplete ingredients
- [ ] Calories per serving on the recipe cards
- [ ] "Missing macros" filter on the ingredients page

## M4 — Photos, links, tags, search
- [ ] Photo upload with Pillow resize, plus a placeholder when there is no photo
- [ ] Source link shown as a clickable link when present
- [ ] Tags: add on the form, filter on the list
- [ ] Search by title or ingredient, ignoring Cyrillic upper/lower case

## M5 — Menus
- [ ] Create, rename and delete menus
- [ ] Add a recipe to a menu with day, meal and servings
- [ ] Menu page grouped by day and meal
- [ ] Macro totals per day and for the whole menu

## M6 — Shopping list
- [ ] `services/shopping_list.py` with tests (merging by ingredient + unit, scaling, NULL quantities)
- [ ] Build the list from a menu and save it in `shopping_items`
- [ ] Tick items off (JS + POST), add items by hand, regenerate
- [ ] Print styles

## M7 — Units page
- [ ] View, rename and add units

## Later (pick any)
- Favourites / "last cooked"
- Copy a menu
- JSON export/import
- Density per ingredient for more accurate volume units
- Merge different weight units in the shopping list
- Access from a phone on the home Wi-Fi (run on `0.0.0.0` and allow it through Windows Firewall)
