# CookingRecipe — Project Documentation

A personal recipe manager for one user, running locally on a Windows 10 PC.
It replaces keeping recipes in Notepad.

## What it is

- A **local web app**: a small Python server runs on your PC and you open it in the browser at `http://localhost:5000`.
- Nothing is published or hosted. There are no accounts and no login, and it doesn't need the internet (apart from opening the source links of recipes).
- All data lives in one SQLite file (`recipes.db`) plus an `images/` folder for photos.

## Documents

| File | Contents |
|------|----------|
| [requirements.md](requirements.md) | Features: what the app must do |
| [architecture.md](architecture.md) | Tech stack, folder layout, pages and routes |
| [database.md](database.md) | SQLite schema, Cyrillic handling, macro calculations, migrations |
| [roadmap.md](roadmap.md) | Build order, split into small milestones |

## Key decisions

| Decision | Choice | Why |
|----------|--------|-----|
| App type | Local web app | HTML/CSS makes photo cards and menus easy to lay out; it runs in any browser |
| Backend | Python 3.12 + Flask | Simple, beginner-friendly, renders HTML pages directly |
| Database | SQLite (`sqlite3`, built into Python) | No server to install; one file you can copy as a backup |
| UI | Jinja2 templates + Pico.css + a little vanilla JS | Looks clean with very little CSS work |
| Photos | Files in `images/`; the database stores only the file name | Keeps the database small; photos are easy to browse |
| Language | Recipe content in Bulgarian (Cyrillic), stored as UTF-8 | Search and sorting handle Cyrillic upper/lower case correctly |
| Interface language | English and Bulgarian, switchable in the navigation bar | Only UI texts are translated; recipes, ingredients and other content stay exactly as entered, and "CookingRecipe" keeps its name |
| Macros | Entered per 100 g on each ingredient; recipe and menu totals are calculated | Enter an ingredient's macros once and every recipe that uses it gets them |
| Database changes | Numbered SQL files in `migrations/`, applied automatically on startup | Every change is tracked, and the DB is backed up before each one |
| Optional data | Photo, source link and every macro value can be empty (NULL) | You often won't have all of them |

## Quick start (once the code exists)

```powershell
cd D:\Programming\Projects\CookingRecipe
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000`. Later, a `start.bat` launcher will run these steps with a double-click (see [roadmap.md](roadmap.md)).

## Backup

Copy `recipes.db` and the `images/` folder somewhere safe. That's everything.
The app also copies `recipes.db` into `backups/` automatically before it applies a new migration.
