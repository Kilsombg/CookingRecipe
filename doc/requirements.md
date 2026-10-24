# Requirements

## Scope

- **Single user**, on a single PC (Windows 10).
- Runs locally only. No authentication, no deployment, no multi-user handling.
- Small and simple. Each feature should be usable on its own.
- **Recipe content is written in Bulgarian (Cyrillic)**: titles, ingredient names, instructions, notes, tags, menu names and unit labels. Latin text works too, and both can be mixed.

Priority: **Must** = first version, **Should** = soon after, **Could** = nice to have.

---

## 1. Ingredient catalogue — Must

Every ingredient is saved once in a catalogue and reused in all recipes. Its macros are entered there, **per 100 g**.

| Field | Required | Notes |
|-------|----------|-------|
| Name | Yes | e.g. "Пилешко филе". Must be unique, ignoring upper/lower case ("Яйца" = "яйца") |
| Calories / 100 g | No | kcal |
| Protein / 100 g | No | g |
| Carbs / 100 g | No | g |
| Fat / 100 g | No | g |
| Grams per piece | No | e.g. egg ≈ 55 g. Needed only if you measure that ingredient in pieces (`бр.`) |

Each macro value can be left empty on its own.

### Actions
- Ingredients page: a list with search, showing each ingredient's macros, or "—" where a value is missing.
- Add and edit ingredients.
- Delete an ingredient only if no recipe uses it. Otherwise the app shows which recipes use it.
- Filter "missing macros" to find ingredients you still need to fill in.

## 2. Recipes — Must

### Recipe fields

| Field | Required | Notes |
|-------|----------|-------|
| Title | Yes | e.g. "Пиле с ориз" |
| Photo | No | An uploaded image (jpg/png/webp). A placeholder is shown when there is none |
| Source link | No | URL where you saw the recipe (YouTube, blog, Instagram…). Opens in a new tab |
| Servings | Yes (default 1) | How many portions the recipe makes. Used for per-serving macros and shopping lists |
| Prep / cook time | No | Minutes |
| Ingredients | Yes (at least 1) | See below |
| Instructions | Yes | How to cook it. Free text, one step per line |
| Tags | No | e.g. "закуска", "вегетарианско", "бързо" |
| Notes | No | Personal comments ("по-малко сол следващия път") |

### Ingredient lines

Each line has:
- **ingredient** (required): typed with autocomplete from the catalogue. If you type a name that isn't in the catalogue yet, it's added automatically with empty macros, which you can fill in later. You don't have to leave the recipe form to add it.
- **quantity** (optional): `200`, `0.5`. Empty for "на вкус" (to taste).
- **unit** (optional, required when a quantity is given): chosen from the units list (`г`, `кг`, `мл`, `л`, `ч.л.`, `с.л.`, `ч.ч.`, `бр.`).
- **note** (optional): "нарязан", "на вкус".

### Actions
- Add, edit and delete a recipe.
- Upload, replace or remove a photo.
- **Recipe list page**: a grid of cards showing the photo (or a placeholder), the title, the tags and the calories per serving (when known).
- **Search** by title or ingredient name, ignoring upper/lower case for Cyrillic too: "пиле" finds "Пиле с ориз".
- **Filter** by tag.
- **Recipe detail page**: everything above, with a clickable source link when there is one, and the macros (see section 5).

## 3. Menus — Must

A menu is a meal plan, e.g. "Седмица 12 ноември" or "Рожден ден".

- Create, rename and delete a menu.
- Add recipes to a menu. Each entry has:
  - **day** (optional): Monday…Sunday, or empty for menus without days
  - **meal** (optional): breakfast / lunch / dinner / snack
  - **servings**: how many portions you'll cook (defaults to the recipe's servings)
- The same recipe can appear several times in a menu.
- Show the menu grouped by day, then by meal.

## 4. Shopping list — Must

- Built **from a menu**.
- Combines matching ingredients from all recipes in the menu:
  - same catalogue ingredient **and** same unit → quantities are added up
  - same ingredient but a different unit → listed as separate lines (no unit conversion in v1)
  - no quantity ("на вкус") → listed once, without a quantity
- Scales quantities: `quantity × (menu servings / recipe servings)`.
- You can tick items off while shopping. Ticks are saved so they survive a page reload.
- You can add extra items by hand (e.g. "тоалетна хартия").
- Print-friendly view.

## 5. Macros — Must

Macros are **calculated** from the ingredients. You never type them on a recipe.

- Each ingredient line is converted to grams:
  - weight/volume units use the unit's grams (`с.л.` = 15 g, `мл` ≈ 1 g…)
  - `бр.` uses the ingredient's "grams per piece"
- Line macros = `grams / 100 × ingredient macros per 100 g`.
- **Recipe page** shows the total for the whole recipe and **per serving** (total ÷ servings) for calories, protein, carbs and fat.
- If some lines can't be calculated (the ingredient has no macros, or a `бр.` ingredient has no grams per piece), the page still shows the partial total and lists the missing ingredients, each linking to its edit page.
- Lines without a quantity (salt, spices "на вкус") are skipped.
- **Menu page** shows totals **per day** and **for the whole menu** (per-serving macros × servings), and lists recipes with incomplete data.
- Changing an ingredient's macros updates every recipe and menu that uses it automatically.

## 6. Units — Should

- Units page: view, rename and add units, e.g. add "чаша" = 240 g.
- A unit is either a fixed number of grams, or a "piece" unit with no grams.
- A unit can't be deleted while recipes use it.

## 7. Could have (later)

- Mark recipes as favourites, and sort by favourites or last cooked.
- Copy an existing menu ("repeat last week").
- Export / import all data as JSON.
- Density per ingredient (e.g. oil 0.92 g/ml) for more accurate volume units.
- Merge different weight units in the shopping list (500 г + 1 кг → 1.5 кг).
- Import ingredient macros from a public food database.
- Open the app from a phone on the home Wi-Fi.

## Non-functional requirements

- Starts with a double-click (`start.bat`).
- Works fully offline. Pico.css is saved inside the project instead of loaded from a CDN.
- **Cyrillic everywhere**: every page uses UTF-8 (`<meta charset="utf-8">`), and every file is read and written as UTF-8. Search and sorting handle Bulgarian upper/lower case and alphabetical order correctly (see [database.md](database.md#cyrillic-bulgarian-text)).
- Data survives app restarts and updates. Database changes are made only through migration files in `migrations/`, and the database is backed up automatically before they run (see [database.md](database.md#migrations)).
- Uploaded photos are resized to at most 1600 px on the longest side, so the folder stays small.
- Deleting a recipe asks for confirmation.
