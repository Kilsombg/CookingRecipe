"""Ingredient catalogue: paged list, add, edit (macros per 100 g, grams per piece), delete."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import db
from i18n import num, safe_next, t
from services.forms import INGREDIENT_FIELDS, INGREDIENT_VALUE_FIELDS, parse_ingredient
from services.pagination import paginate

bp = Blueprint("ingredients", __name__, url_prefix="/ingredients")

PER_PAGE_DEFAULT, PER_PAGE_OPTIONS = 50, (10, 20, 50, 100)  # table rows per page on the list


def _load(ingredient_id):
    ingredient = db.get_ingredient(db.get_db(), ingredient_id)
    if ingredient is None:
        abort(404)
    return ingredient


def _validate(conn, ingredient_id=None):
    """Return (name, values, errors) from the submitted form."""
    name, values, errors = parse_ingredient(request.form)
    if name is not None:
        existing = db.find_ingredient(conn, name)
        if existing and existing["id"] != ingredient_id:
            errors["name"] = "ingredients.error_exists"
    return name, values, errors


def _back_url():
    """Where Save and Cancel go: the page that linked here (?next=, e.g. a recipe), or the list."""
    next_url = request.values.get("next")
    return safe_next(next_url) if next_url else url_for(".index")


def _render_form(ingredient, errors, status=200):
    used_in = db.recipes_using_ingredient(db.get_db(), ingredient["id"]) if ingredient else []
    if request.method == "POST":
        form = {field: request.form.get(field, "") for field in INGREDIENT_FIELDS}
    elif ingredient:
        form = {"name": ingredient["name"]} | {field: num(ingredient[field]) for field in INGREDIENT_VALUE_FIELDS}
    else:
        form = dict.fromkeys(INGREDIENT_FIELDS, "")
    return render_template("ingredients/form.html", ingredient=ingredient, form=form, errors=errors,
                           used_in=used_in, next=request.values.get("next", ""),
                           back_url=_back_url()), status


@bp.get("")
def index():
    q = request.args.get("q", "").strip()
    missing = request.args.get("missing") == "1"
    page = paginate(db.list_ingredients(db.get_db(), q, missing), PER_PAGE_DEFAULT, PER_PAGE_OPTIONS)
    return render_template("ingredients/list.html", q=q, missing=missing, ingredients=page.items, page=page)


@bp.get("/new")
def new():
    return _render_form(None, {})


@bp.post("")
def create():
    conn = db.get_db()
    name, values, errors = _validate(conn)
    if errors:
        return _render_form(None, errors, 400)
    db.create_ingredient(conn, name, values)
    flash(t("ingredients.msg_created", name=name), "success")
    return redirect(url_for(".index"))


@bp.get("/<int:ingredient_id>/edit")
def edit(ingredient_id):
    return _render_form(_load(ingredient_id), {})


@bp.post("/<int:ingredient_id>")
def update(ingredient_id):
    ingredient = _load(ingredient_id)
    conn = db.get_db()
    name, values, errors = _validate(conn, ingredient_id)
    if errors:
        return _render_form(ingredient, errors, 400)
    db.update_ingredient(conn, ingredient_id, name, values)
    flash(t("ingredients.msg_updated", name=name), "success")
    return redirect(_back_url())


@bp.post("/<int:ingredient_id>/delete")
def delete(ingredient_id):
    ingredient = _load(ingredient_id)
    conn = db.get_db()
    used_in = db.recipes_using_ingredient(conn, ingredient_id)
    if used_in:
        flash(t("ingredients.error_in_use", name=ingredient["name"],
                recipes=", ".join(r["title"] for r in used_in)), "error")
        return redirect(url_for(".edit", ingredient_id=ingredient_id))
    db.delete_ingredient(conn, ingredient_id)
    flash(t("ingredients.msg_deleted", name=ingredient["name"]), "success")
    return redirect(url_for(".index"))
