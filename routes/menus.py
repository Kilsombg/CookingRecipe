"""Menus: list, create, rename, copy, delete; add and remove recipes by day and meal; macro totals."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import db
from i18n import t
from services.forms import DAYS, MEALS, MENU_ITEM_FIELDS, parse_menu_item, parse_menu_name
from services.macros import menu_macros

bp = Blueprint("menus", __name__, url_prefix="/menus")


def _load(menu_id):
    menu = db.get_menu(db.get_db(), menu_id)
    if menu is None:
        abort(404)
    return menu


def group_items(items):
    """[(day, [(meal, [items])])]: days Monday to Sunday, then no day; meals in MEALS order, then no meal."""
    day_order = {day: i for i, day in enumerate([*DAYS, None])}
    meal_order = {meal: i for i, meal in enumerate([*MEALS, None])}
    groups = {}
    for item in items:
        groups.setdefault(item["day"], {}).setdefault(item["meal"], []).append(item)
    return [(day, sorted(meals.items(), key=lambda m: meal_order[m[0]]))
            for day, meals in sorted(groups.items(), key=lambda d: day_order[d[0]])]


def _render_list(name="", error=None, status=200):
    return render_template("menus/list.html", menus=db.list_menus(db.get_db()),
                           name=name, error=error), status


def _render_detail(menu, item_form=None, item_errors=None, name=None, name_error=None, status=200):
    conn = db.get_db()
    items = db.get_menu_items(conn, menu["id"])
    if item_form is None:
        # After adding a recipe, the next one starts on the same day and meal
        item_form = dict.fromkeys(MENU_ITEM_FIELDS, "") | {
            "day": request.args.get("day", ""), "meal": request.args.get("meal", "")}
    return render_template("menus/detail.html", menu=menu, groups=group_items(items),
                           macros=menu_macros(items, db.lines_by_recipe(conn)),
                           recipes=db.list_recipes(conn), days=DAYS, meals=MEALS,
                           item_form=item_form, item_errors=item_errors or {},
                           name=menu["name"] if name is None else name, name_error=name_error), status


@bp.get("")
def index():
    return _render_list()


@bp.post("")
def create():
    name, error = parse_menu_name(request.form.get("name"))
    if error:
        return _render_list(request.form.get("name", ""), error, 400)
    menu_id = db.create_menu(db.get_db(), name)
    flash(t("menus.msg_created", name=name), "success")
    return redirect(url_for(".detail", menu_id=menu_id))


@bp.get("/<int:menu_id>")
def detail(menu_id):
    return _render_detail(_load(menu_id))


@bp.post("/<int:menu_id>")
def rename(menu_id):
    menu = _load(menu_id)
    name, error = parse_menu_name(request.form.get("name"))
    if error:
        return _render_detail(menu, name=request.form.get("name", ""), name_error=error, status=400)
    db.rename_menu(db.get_db(), menu_id, name)
    flash(t("menus.msg_renamed", name=name), "success")
    return redirect(url_for(".detail", menu_id=menu_id))


@bp.post("/<int:menu_id>/delete")
def delete(menu_id):
    menu = _load(menu_id)
    db.delete_menu(db.get_db(), menu_id)
    flash(t("menus.msg_deleted", name=menu["name"]), "success")
    return redirect(url_for(".index"))


@bp.post("/<int:menu_id>/copy")
def copy(menu_id):
    menu = _load(menu_id)
    name = t("menus.copy_name", name=menu["name"])
    new_id = db.copy_menu(db.get_db(), menu_id, name)
    flash(t("menus.msg_copied", name=name), "success")
    return redirect(url_for(".detail", menu_id=new_id))


@bp.post("/<int:menu_id>/items")
def add_item(menu_id):
    menu = _load(menu_id)
    conn = db.get_db()
    fields = {name: request.form.get(name, "") for name in MENU_ITEM_FIELDS}
    recipe_servings = {r["id"]: r["servings"] for r in db.list_recipes(conn)}
    item, errors = parse_menu_item(fields, recipe_servings)
    if errors:
        return _render_detail(menu, item_form=fields, item_errors=errors, status=400)
    db.add_menu_item(conn, menu_id, item)
    return redirect(url_for(".detail", menu_id=menu_id, day=fields["day"] or None, meal=fields["meal"] or None))


@bp.post("/<int:menu_id>/items/<int:item_id>/delete")
def delete_item(menu_id, item_id):
    _load(menu_id)
    if not db.delete_menu_item(db.get_db(), menu_id, item_id):
        abort(404)
    return redirect(url_for(".detail", menu_id=menu_id))
