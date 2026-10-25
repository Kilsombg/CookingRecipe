# Database

SQLite, in a single file: `recipes.db` in the project root.

## Conventions

- Every table has `id INTEGER PRIMARY KEY`.
- Dates are stored as ISO-8601 text (`2026-10-24T18:30:00`).
- Foreign keys are enabled on every connection: `PRAGMA foreign_keys = ON;`.
- **NULL means "not known / not provided".** This applies to: photo, source link, every macro value, times, ingredient quantity and unit, and grams per piece.
- Deleting a recipe or menu deletes its child rows automatically (`ON DELETE CASCADE`). An ingredient that is used in a recipe can't be deleted (`ON DELETE RESTRICT`).
- The tables are created and changed only by the files in `migrations/` (see [Migrations](#migrations)).

## Cyrillic (Bulgarian) text

SQLite stores all `TEXT` as UTF-8, so Bulgarian text (`Пиле с ориз`, `200 г брашно`, `Запържете лука…`) is saved and loaded without any special setup. There are three things to watch out for:

1. **Upper/lower case.** SQLite's built-in `LOWER()`, `UPPER()`, `LIKE` and `COLLATE NOCASE` only understand English letters. `LOWER('Яйца')` returns `'Яйца'` unchanged. So:
   - Every connection registers a Python function: `conn.create_function("casefold", 1, lambda s: s.casefold() if s else s, deterministic=True)`.
   - Search uses it: `WHERE casefold(title) LIKE ?`, with the search text casefolded in Python first.
   - Sorting uses it too: `ORDER BY casefold(title)`. Unicode puts Cyrillic letters in Bulgarian alphabetical order (а, б, в … ю, я), so this sorts correctly.
2. **Duplicate ingredients.** "Яйца" and "яйца" must count as the same ingredient. `ingredients.name_key` holds the name casefolded in Python with extra spaces removed, and it has a `UNIQUE` constraint. (A unique index on `casefold(name)` would also work, but other tools such as DB Browser for SQLite couldn't open the database, because they don't know that function.)
3. **Reading files.** On Windows, Python reads files using the system code page unless told otherwise. Always open files with `encoding="utf-8"`; this matters for the migration files, which contain Bulgarian seed data. `start.bat` also sets `PYTHONUTF8=1` as a safety net.

## Diagram

```
recipes     1───* recipe_ingredients *───1 ingredients
                        │
                        *───1 units
recipes     *───* tags              (through recipe_tags)
menus       1───* menu_items *───1 recipes
menus       1───* shopping_items
wanted_recipes                      (on its own)
```

## Tables

### `ingredients` — the ingredient catalogue

Each ingredient is entered once, with its macros **per 100 g**, and is then reused in every recipe that needs it.

| Column | Type | Null? | Notes |
|--------|------|-------|-------|
| id | INTEGER PK | no | |
| name | TEXT | no | Shown as typed: "Пилешко филе" |
| name_key | TEXT UNIQUE | no | `name.casefold()` with extra spaces removed. Used to detect duplicates |
| calories_100g | REAL | **yes** | kcal per 100 g |
| protein_100g | REAL | **yes** | grams of protein per 100 g |
| carbs_100g | REAL | **yes** | grams of carbs per 100 g |
| fat_100g | REAL | **yes** | grams of fat per 100 g |
| grams_per_piece | REAL | yes | e.g. 1 egg ≈ 55 g. Needed only if the ingredient is measured in pieces (`бр.`) |
| created_at | TEXT | no | |

### `units`

The units you can choose for an ingredient line. Each unit knows how many grams it equals, which is what lets the app turn "2 с.л." into grams for the macro calculation. The starting units are added by the first migration, and you can rename them or add new ones on the Units page. Names are unique ignoring upper/lower case (checked by the form; the column itself is case-sensitive). A unit can be deleted only while no recipe uses it. Saved shopping lists keep the old label until they are rebuilt.

| Column | Type | Null? | Notes |
|--------|------|-------|-------|
| id | INTEGER PK | no | |
| name | TEXT UNIQUE | no | The label shown: `г`, `кг`, `мл`… |
| grams | REAL | yes | Grams in 1 unit. **NULL = a piece unit**: the ingredient's `grams_per_piece` is used instead |

Starting units:

| name | grams | Meaning |
|------|-------|---------|
| г | 1 | gram |
| кг | 1000 | kilogram |
| мл | 1 | millilitre (taken as 1 ml ≈ 1 g) |
| л | 1000 | litre (≈ 1000 g) |
| ч.л. | 5 | teaspoon (≈ 5 g) |
| с.л. | 15 | tablespoon (≈ 15 g) |
| ч.ч. | 200 | tea cup (≈ 200 g) |
| бр. | NULL | piece |

The volume units (мл, л, spoons, cups) treat everything as weighing the same as water. That's close enough for a personal tool: oil and flour will be off by about 10–40 %. If you need better accuracy, enter that ingredient in grams.

### `recipes`

| Column | Type | Null? | Notes |
|--------|------|-------|-------|
| id | INTEGER PK | no | |
| title | TEXT | no | |
| photo_filename | TEXT | **yes** | File name inside `images/` |
| source_url | TEXT | **yes** | Where you saw the recipe |
| servings | INTEGER | no | Default 1, must be > 0 |
| prep_minutes | INTEGER | yes | |
| cook_minutes | INTEGER | yes | |
| instructions | TEXT | no | One step per line |
| notes | TEXT | yes | |
| is_favourite | INTEGER | no | 0/1, default 0. Added by `0002_add_favourite.sql`. Changing it doesn't touch `updated_at` |
| created_at | TEXT | no | |
| updated_at | TEXT | no | |

There are no macro columns: a recipe's macros are **calculated** from its ingredients every time they're shown (see [Calculations](#calculations)). That way, correcting an ingredient's macros updates every recipe that uses it.

### `recipe_ingredients`

| Column | Type | Null? | Notes |
|--------|------|-------|-------|
| id | INTEGER PK | no | |
| recipe_id | INTEGER FK → recipes | no | cascade delete |
| ingredient_id | INTEGER FK → ingredients | no | restrict delete |
| position | INTEGER | no | Display order |
| quantity | REAL | yes | NULL = "to taste" / not measured |
| unit_id | INTEGER FK → units | yes | NULL together with quantity NULL |
| note | TEXT | yes | "нарязан на кубчета" |

### `tags` and `recipe_tags`

| `tags` column | Type | Notes |
|---------------|------|-------|
| id | INTEGER PK | |
| name | TEXT UNIQUE | Stored casefolded (in Python), e.g. "закуска" |

| `recipe_tags` column | Type | Notes |
|----------------------|------|-------|
| recipe_id | INTEGER FK → recipes | cascade delete |
| tag_id | INTEGER FK → tags | cascade delete |
| | PK (recipe_id, tag_id) | |

### `menus`

| Column | Type | Null? | Notes |
|--------|------|-------|-------|
| id | INTEGER PK | no | |
| name | TEXT | no | "Седмица 12 ноември" |
| created_at | TEXT | no | |

Copying a menu inserts a new `menus` row and copies its `menu_items`; the shopping list is not copied.

### `menu_items`

| Column | Type | Null? | Notes |
|--------|------|-------|-------|
| id | INTEGER PK | no | |
| menu_id | INTEGER FK → menus | no | cascade delete |
| recipe_id | INTEGER FK → recipes | no | cascade delete |
| day | INTEGER | yes | 0 = Monday … 6 = Sunday; NULL = no specific day |
| meal | TEXT | yes | `breakfast`, `lunch`, `dinner`, `snack` (stored in English, shown translated) |
| servings | REAL | no | Portions to cook, must be > 0 |

### `shopping_items`

A saved copy of a menu's shopping list. It is saved, rather than calculated every time, so that ticks and hand-added items are kept. Names and units are copied in as text, so the list doesn't change if you later edit an ingredient.

| Column | Type | Null? | Notes |
|--------|------|-------|-------|
| id | INTEGER PK | no | |
| menu_id | INTEGER FK → menus | no | cascade delete |
| name | TEXT | no | |
| quantity | REAL | yes | |
| unit | TEXT | yes | Unit label, e.g. `г` |
| checked | INTEGER | no | 0/1, default 0 |
| is_manual | INTEGER | no | 1 = added by hand; kept when the list is rebuilt |

### `wanted_recipes`

Recipes you want to cook some day, before they are written down. Added by `0003_add_wanted_recipes.sql`. Saving a new recipe deletes the entries with the same name (ignoring case), and the entry the recipe form was opened from. Names are unique ignoring case (checked by the form).

| Column | Type | Null? | Notes |
|--------|------|-------|-------|
| id | INTEGER PK | no | |
| name | TEXT | no | |
| source_url | TEXT | yes | Where you saw it; an http(s) link |
| notes | TEXT | yes | |
| created_at | TEXT | no | |

## Calculations

### Grams of one ingredient line

```
if quantity is NULL:                  -> not counted ("to taste", e.g. salt)
elif unit.grams is not NULL:          grams = quantity × unit.grams
elif ingredient.grams_per_piece set:  grams = quantity × ingredient.grams_per_piece
else:                                 -> unknown (missing grams per piece)
```

### Recipe macros

```
for each macro (calories, protein, carbs, fat):
    total = Σ over ingredient lines:  grams / 100 × ingredient.<macro>_100g
per serving = total / recipe.servings
```

A line is reported as **incomplete** when its grams are unknown or its ingredient has no value for that macro. The recipe page still shows the totals from the complete lines, followed by a note such as "Без данни: зехтин, яйца" ("no data: olive oil, eggs"). Lines without a quantity are skipped without a warning, since they are usually small amounts like salt or spices.

Example: 200 г пилешко филе (110 kcal / 100 g) + 2 бр. яйца (55 g each, 143 kcal / 100 g):
`200/100×110 + 110/100×143 = 220 + 157.3 = 377.3 kcal`.

### Menu macros

```
for each menu_item:
    total += recipe per-serving macros × menu_item.servings
```

Totals are shown per day and for the whole menu. Recipes with incomplete data are listed.

### Shopping list

```
for each menu_item in the menu:
    factor = menu_item.servings / recipe.servings
    for each ingredient line of the recipe:
        key = (ingredient_id, unit_id)
        if quantity is NULL: remember the key with no quantity
        else: total[key] += quantity × factor
```

Matching is done by `ingredient_id`, so the same ingredient is always combined, even if it was typed in a different letter case. A line without a quantity has no unit either (the recipe form requires both or neither), so an ingredient "to taste" is listed once; it is left out when the same ingredient is also needed with a quantity, since you are buying it anyway.

The list is built and saved on the first visit. After that it only changes on "Regenerate", which deletes the menu's rows where `is_manual = 0` and inserts the new totals. Items added by hand are kept, and a rebuilt item keeps its tick only if its name, quantity and unit are unchanged.

## Migrations

Every change to the database structure is a numbered SQL file in the `migrations/` folder:

```
migrations/
├── 0001_initial.sql          # all tables + starting units
├── 0002_add_favourite.sql    # recipes.is_favourite
├── 0003_add_wanted_recipes.sql # wanted_recipes
└── ...
```

### Rules

1. File names follow `NNNN_short_description.sql`: a 4-digit number, then a description in English. They run in number order.
2. **Never edit a migration that has already been applied.** To change something, add a new file.
3. Each file contains only the SQL for its change. Don't put `BEGIN`/`COMMIT` or `PRAGMA user_version` in it; the runner adds those.
4. Save files as UTF-8, because they may contain Bulgarian text.
5. Never drop data. SQLite's `ALTER TABLE` can add, rename or drop columns, but it can't change a column's type or constraints. For that, create the new table, copy the data across, drop the old table and rename the new one, all inside one migration.

### How the runner works (`db.py`, on every app start)

```
current = PRAGMA user_version           # 0 for a brand-new database
pending = files in migrations/ with number > current, sorted by number
if pending and the database already has data:
    copy recipes.db -> backups/recipes-YYYYMMDD-HHMMSS.db
for each file in pending:
    sql = read file with encoding="utf-8"
    conn.executescript("BEGIN;\n" + sql + f"\nPRAGMA user_version = {number};\nCOMMIT;")
    on error: ROLLBACK, stop the app and show which file failed
```

Each migration and its version number are saved together in one transaction, so a failed migration leaves the database exactly as it was before.

### `migrations/0001_initial.sql`

```sql
CREATE TABLE ingredients (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL,
    name_key         TEXT NOT NULL UNIQUE,
    calories_100g    REAL CHECK (calories_100g >= 0),
    protein_100g     REAL CHECK (protein_100g  >= 0),
    carbs_100g       REAL CHECK (carbs_100g    >= 0),
    fat_100g         REAL CHECK (fat_100g      >= 0),
    grams_per_piece  REAL CHECK (grams_per_piece > 0),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE units (
    id     INTEGER PRIMARY KEY,
    name   TEXT NOT NULL UNIQUE,
    grams  REAL CHECK (grams > 0)
);

INSERT INTO units (name, grams) VALUES
    ('г', 1), ('кг', 1000), ('мл', 1), ('л', 1000),
    ('ч.л.', 5), ('с.л.', 15), ('ч.ч.', 200), ('бр.', NULL);

CREATE TABLE recipes (
    id              INTEGER PRIMARY KEY,
    title           TEXT    NOT NULL,
    photo_filename  TEXT,
    source_url      TEXT,
    servings        INTEGER NOT NULL DEFAULT 1 CHECK (servings > 0),
    prep_minutes    INTEGER,
    cook_minutes    INTEGER,
    instructions    TEXT    NOT NULL,
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE recipe_ingredients (
    id             INTEGER PRIMARY KEY,
    recipe_id      INTEGER NOT NULL REFERENCES recipes(id)     ON DELETE CASCADE,
    ingredient_id  INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
    position       INTEGER NOT NULL,
    quantity       REAL    CHECK (quantity > 0),
    unit_id        INTEGER REFERENCES units(id) ON DELETE RESTRICT,
    note           TEXT
);

CREATE TABLE tags (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE recipe_tags (
    recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id)    ON DELETE CASCADE,
    PRIMARY KEY (recipe_id, tag_id)
);

CREATE TABLE menus (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE menu_items (
    id         INTEGER PRIMARY KEY,
    menu_id    INTEGER NOT NULL REFERENCES menus(id)   ON DELETE CASCADE,
    recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    day        INTEGER CHECK (day BETWEEN 0 AND 6),
    meal       TEXT    CHECK (meal IN ('breakfast','lunch','dinner','snack')),
    servings   REAL    NOT NULL CHECK (servings > 0)
);

CREATE TABLE shopping_items (
    id         INTEGER PRIMARY KEY,
    menu_id    INTEGER NOT NULL REFERENCES menus(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    quantity   REAL,
    unit       TEXT,
    checked    INTEGER NOT NULL DEFAULT 0,
    is_manual  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_recipe_ingredients_recipe     ON recipe_ingredients(recipe_id);
CREATE INDEX idx_recipe_ingredients_ingredient ON recipe_ingredients(ingredient_id);
CREATE INDEX idx_menu_items_menu               ON menu_items(menu_id);
CREATE INDEX idx_shopping_items_menu           ON shopping_items(menu_id);
```
