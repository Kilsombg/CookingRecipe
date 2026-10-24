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
