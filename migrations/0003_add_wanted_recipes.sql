CREATE TABLE wanted_recipes (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    source_url  TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
