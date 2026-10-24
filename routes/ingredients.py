"""Ingredient catalogue: list, add, edit, delete."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import db
from i18n import t
from services.forms import clean_name

bp = Blueprint("ingredients", __name__, url_prefix="/ingredients")


def _load(ingredient_id):
    ingredient = db.get_ingredient(db.get_db(), ingredient_id)
    if ingredient is None:
        abort(404)
    return ingredient


def _validate(conn, ingredient_id=None):
    """Return (name, errors) from the submitted form."""
    name = clean_name(request.form.get("name"))
    if name is None:
        return name, {"name": "error.required"}
    existing = db.find_ingredient(conn, name)
    if existing and existing["id"] != ingredient_id:
        return name, {"name": "ingredients.error_exists"}
    return name, {}


def _render_form(ingredient, errors, status=200):
    used_in = db.recipes_using_ingredient(db.get_db(), ingredient["id"]) if ingredient else []
    form = {"name": request.form.get("name", ingredient["name"] if ingredient else "")}
    return render_template("ingredients/form.html", ingredient=ingredient, form=form,
                           errors=errors, used_in=used_in), status


@bp.get("")
def index():
    q = request.args.get("q", "").strip()
    return render_template("ingredients/list.html", ingredients=db.list_ingredients(db.get_db(), q), q=q)


@bp.get("/new")
def new():
    return _render_form(None, {})


@bp.post("")
def create():
    conn = db.get_db()
    name, errors = _validate(conn)
    if errors:
        return _render_form(None, errors, 400)
    db.create_ingredient(conn, name)
    flash(t("ingredients.msg_created", name=name), "success")
    return redirect(url_for(".index"))


@bp.get("/<int:ingredient_id>/edit")
def edit(ingredient_id):
    return _render_form(_load(ingredient_id), {})


@bp.post("/<int:ingredient_id>")
def update(ingredient_id):
    ingredient = _load(ingredient_id)
    conn = db.get_db()
    name, errors = _validate(conn, ingredient_id)
    if errors:
        return _render_form(ingredient, errors, 400)
    db.update_ingredient(conn, ingredient_id, name)
    flash(t("ingredients.msg_updated", name=name), "success")
    return redirect(url_for(".index"))


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
