"""Shopping list of a menu: built from its recipes and saved, ticks, items added by hand, rebuild."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import db
from i18n import t
from services.forms import SHOPPING_ITEM_FIELDS, parse_shopping_item
from services.shopping_list import build_shopping_list

bp = Blueprint("shopping", __name__)


def _load_menu(menu_id):
    menu = db.get_menu(db.get_db(), menu_id)
    if menu is None:
        abort(404)
    return menu


def _rebuild(conn, menu_id):
    items = build_shopping_list(db.get_menu_items(conn, menu_id), db.lines_by_recipe(conn))
    db.replace_shopping_items(conn, menu_id, items)


def _render(menu, item_form=None, item_errors=None, status=200):
    conn = db.get_db()
    items = db.get_shopping_items(conn, menu["id"])
    return render_template("shopping/list.html", menu=menu,
                           built=[i for i in items if not i["is_manual"]],
                           manual=[i for i in items if i["is_manual"]],
                           unit_names=[u["name"] for u in db.list_units(conn)],
                           item_form=item_form or dict.fromkeys(SHOPPING_ITEM_FIELDS, ""),
                           item_errors=item_errors or {}), status


@bp.get("/menus/<int:menu_id>/shopping")
def index(menu_id):
    menu = _load_menu(menu_id)
    conn = db.get_db()
    # Built on the first visit (and while the menu gives nothing to buy); after that only on "rebuild",
    # so ticks are kept
    if not db.has_built_shopping_items(conn, menu_id):
        _rebuild(conn, menu_id)
    return _render(menu)


@bp.post("/menus/<int:menu_id>/shopping/regenerate")
def regenerate(menu_id):
    _load_menu(menu_id)
    _rebuild(db.get_db(), menu_id)
    flash(t("shopping.msg_rebuilt"), "success")
    return redirect(url_for(".index", menu_id=menu_id))


@bp.post("/shopping/items")
def add_item():
    raw_menu = request.form.get("menu_id", "")
    if not raw_menu.isdigit():
        abort(400)
    menu = _load_menu(int(raw_menu))
    fields = {name: request.form.get(name, "") for name in SHOPPING_ITEM_FIELDS}
    item, errors = parse_shopping_item(fields)
    if errors:
        return _render(menu, item_form=fields, item_errors=errors, status=400)
    db.add_shopping_item(db.get_db(), menu["id"], item)
    return redirect(url_for(".index", menu_id=menu["id"]))


@bp.post("/shopping/items/<int:item_id>/toggle")
def toggle_item(item_id):
    """Called from app.js with checked=1 or 0; sets the tick rather than flipping it, so a repeated
    request can't undo it."""
    if not db.set_shopping_item_checked(db.get_db(), item_id, request.form.get("checked") == "1"):
        abort(404)
    return "", 204


@bp.post("/shopping/items/<int:item_id>/delete")
def delete_item(item_id):
    conn = db.get_db()
    item = db.get_shopping_item(conn, item_id)
    if item is None or not db.delete_shopping_item(conn, item_id):
        abort(404)
    return redirect(url_for(".index", menu_id=item["menu_id"]))
