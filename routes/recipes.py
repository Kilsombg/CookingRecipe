"""Recipes: paged card list with search, tag and favourites filter, detail, create/edit/delete, favourite, photo upload."""

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

import db
from i18n import num, safe_next, t
from services import photos
from services.forms import RECIPE_FIELDS, ROW_FIELDS, parse_recipe
from services.macros import recipe_macros
from services.pagination import paginate

bp = Blueprint("recipes", __name__, url_prefix="/recipes")

NEW_FORM_ROWS = 3  # blank ingredient rows on a new recipe; "Add ingredient" adds more
PER_PAGE_DEFAULT, PER_PAGE_OPTIONS = 20, (10, 20, 50)  # recipe cards per page on the list


def _load(recipe_id):
    recipe = db.get_recipe(db.get_db(), recipe_id)
    if recipe is None:
        abort(404)
    return recipe


def _blank_row():
    return dict.fromkeys(ROW_FIELDS, "")


def _submitted():
    """Raw (fields, rows) from the form, as strings."""
    form = request.form
    fields = {name: form.get(name, "") for name in RECIPE_FIELDS}
    columns = [form.getlist(f"ing_{name}") for name in ROW_FIELDS]
    rows = [dict(zip(ROW_FIELDS, values)) for values in zip(*columns)]
    return fields, rows


def _render_form(recipe, fields, rows, errors, status=200):
    conn = db.get_db()
    photo_dropped = bool(errors) and bool(request.files.get("photo"))  # browsers can't refill a file input
    return render_template("recipes/form.html", recipe=recipe, form=fields,
                           rows=rows or [_blank_row()], blank_row=_blank_row(), errors=errors,
                           photo_dropped=photo_dropped, remove_photo=request.form.get("remove_photo") == "1",
                           units=db.list_units(conn), ingredient_names=db.ingredient_names(conn)), status


def _uploaded_photo():
    """(jpeg bytes or None, error key or None) for the photo chosen on the form."""
    upload = request.files.get("photo")
    if not upload:
        return None, None
    try:
        return photos.process_photo(upload.read(current_app.config["MAX_PHOTO_BYTES"] + 1)), None
    except photos.PhotoError as e:
        return None, e.key


def _save(recipe_id=None):
    """Validate and save the submitted form; re-render it with errors if invalid."""
    conn = db.get_db()
    images_dir = current_app.config["IMAGES_DIR"]
    existing = db.get_recipe(conn, recipe_id) if recipe_id else None
    fields, rows = _submitted()
    unit_ids = {u["id"] for u in db.list_units(conn)}
    recipe, lines, errors = parse_recipe(fields, rows, unit_ids)
    jpeg, photo_error = _uploaded_photo()
    if photo_error:
        errors["photo"] = photo_error
    if errors:
        return _render_form(existing, fields, rows, errors, 400)

    old_photo = existing["photo_filename"] if existing else None
    if jpeg:
        recipe["photo_filename"] = photos.save_photo(images_dir, jpeg)
    elif request.form.get("remove_photo") == "1":
        recipe["photo_filename"] = None
    else:
        recipe["photo_filename"] = old_photo

    try:
        if recipe_id:
            db.update_recipe(conn, recipe_id, recipe, lines)
        else:
            recipe_id = db.create_recipe(conn, recipe, lines)
    except Exception:
        if jpeg:
            photos.delete_photo(images_dir, recipe["photo_filename"])
        raise
    if old_photo != recipe["photo_filename"]:
        photos.delete_photo(images_dir, old_photo)

    flash(t("recipes.msg_updated" if existing else "recipes.msg_created", title=recipe["title"]), "success")
    return redirect(url_for(".detail", recipe_id=recipe_id))


@bp.get("")
def index():
    conn = db.get_db()
    q = request.args.get("q", "").strip()
    tags = db.list_tags(conn)
    tag = next((tag for tag in tags if str(tag["id"]) == request.args.get("tag")), None)
    favourites = request.args.get("fav") == "1"
    page = paginate(db.list_recipes(conn, q, tag["id"] if tag else None, favourites),
                    PER_PAGE_DEFAULT, PER_PAGE_OPTIONS)
    lines = db.lines_by_recipe(conn)
    macros = {r["id"]: recipe_macros(lines.get(r["id"], []), r["servings"]) for r in page.items}
    return render_template("recipes/list.html", recipes=page.items, page=page, macros=macros, q=q, tags=tags,
                           tag=tag, favourites=favourites, has_favourites=db.has_favourites(conn),
                           recipe_tags=db.tags_by_recipe(conn))


@bp.get("/new")
def new():
    fields = dict.fromkeys(RECIPE_FIELDS, "") | {"servings": "1"}
    return _render_form(None, fields, [_blank_row() for _ in range(NEW_FORM_ROWS)], {})


@bp.post("")
def create():
    return _save()


@bp.get("/<int:recipe_id>")
def detail(recipe_id):
    recipe = _load(recipe_id)
    conn = db.get_db()
    lines = db.get_recipe_lines(conn, recipe_id)
    return render_template("recipes/detail.html", recipe=recipe, lines=lines,
                           tags=db.get_recipe_tags(conn, recipe_id),
                           macros=recipe_macros(lines, recipe["servings"]))


@bp.get("/<int:recipe_id>/edit")
def edit(recipe_id):
    recipe = _load(recipe_id)
    conn = db.get_db()
    fields = {name: "" if recipe[name] is None else str(recipe[name]) for name in RECIPE_FIELDS if name != "tags"}
    fields["tags"] = ", ".join(tag["name"] for tag in db.get_recipe_tags(conn, recipe_id))
    rows = [{"name": line["name"], "quantity": num(line["quantity"]),
             "unit": "" if line["unit_id"] is None else str(line["unit_id"]),
             "note": line["note"] or ""}
            for line in db.get_recipe_lines(conn, recipe_id)]
    return _render_form(recipe, fields, rows, {})


@bp.post("/<int:recipe_id>")
def update(recipe_id):
    _load(recipe_id)
    return _save(recipe_id)


@bp.post("/<int:recipe_id>/favourite")
def favourite(recipe_id):
    _load(recipe_id)
    db.set_favourite(db.get_db(), recipe_id, request.form.get("favourite") == "1")
    # app.js saves the list's card star without reloading; it flips the star itself
    if request.headers.get("X-Requested-With") == "fetch":
        return "", 204
    # Without JavaScript the card star sends ?next= so the list (with its filters) comes back
    next_url = request.form.get("next")
    return redirect(safe_next(next_url) if next_url else url_for(".detail", recipe_id=recipe_id))


@bp.post("/<int:recipe_id>/delete")
def delete(recipe_id):
    recipe = _load(recipe_id)
    db.delete_recipe(db.get_db(), recipe_id)
    photos.delete_photo(current_app.config["IMAGES_DIR"], recipe["photo_filename"])
    flash(t("recipes.msg_deleted", title=recipe["title"]), "success")
    return redirect(url_for(".index"))
