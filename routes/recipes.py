"""Recipes: card list, detail, create/edit/delete."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import db
from i18n import num, t
from services.forms import RECIPE_FIELDS, ROW_FIELDS, parse_recipe

bp = Blueprint("recipes", __name__, url_prefix="/recipes")

NEW_FORM_ROWS = 3  # blank ingredient rows on a new recipe; "Add ingredient" adds more


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
    return render_template("recipes/form.html", recipe=recipe, form=fields,
                           rows=rows or [_blank_row()], blank_row=_blank_row(), errors=errors,
                           units=db.list_units(conn), ingredient_names=db.ingredient_names(conn)), status


def _save(recipe_id=None):
    """Validate and save the submitted form; re-render it with errors if invalid."""
    conn = db.get_db()
    fields, rows = _submitted()
    unit_ids = {u["id"] for u in db.list_units(conn)}
    recipe, lines, errors = parse_recipe(fields, rows, unit_ids)
    if errors:
        existing = db.get_recipe(conn, recipe_id) if recipe_id else None
        return _render_form(existing, fields, rows, errors, 400)

    if recipe_id:
        db.update_recipe(conn, recipe_id, recipe, lines)
        flash(t("recipes.msg_updated", title=recipe["title"]), "success")
    else:
        recipe_id = db.create_recipe(conn, recipe, lines)
        flash(t("recipes.msg_created", title=recipe["title"]), "success")
    return redirect(url_for(".detail", recipe_id=recipe_id))


@bp.get("")
def index():
    return render_template("recipes/list.html", recipes=db.list_recipes(db.get_db()))


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
    return render_template("recipes/detail.html", recipe=recipe,
                           lines=db.get_recipe_lines(db.get_db(), recipe_id))


@bp.get("/<int:recipe_id>/edit")
def edit(recipe_id):
    recipe = _load(recipe_id)
    fields = {name: "" if recipe[name] is None else str(recipe[name]) for name in RECIPE_FIELDS}
    rows = [{"name": line["name"], "quantity": num(line["quantity"]),
             "unit": "" if line["unit_id"] is None else str(line["unit_id"]),
             "note": line["note"] or ""}
            for line in db.get_recipe_lines(db.get_db(), recipe_id)]
    return _render_form(recipe, fields, rows, {})


@bp.post("/<int:recipe_id>")
def update(recipe_id):
    _load(recipe_id)
    return _save(recipe_id)


@bp.post("/<int:recipe_id>/delete")
def delete(recipe_id):
    recipe = _load(recipe_id)
    db.delete_recipe(db.get_db(), recipe_id)
    flash(t("recipes.msg_deleted", title=recipe["title"]), "success")
    return redirect(url_for(".index"))
