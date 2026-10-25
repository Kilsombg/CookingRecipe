"""Recipes to cook: a list of names with an optional link and notes. A name opens the new recipe form
filled from it; saving that recipe takes it off the list (routes/recipes.py)."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import db
from i18n import t
from services.forms import WANTED_FIELDS, parse_wanted

bp = Blueprint("wanted", __name__, url_prefix="/wanted")


def _load(wanted_id):
    wanted = db.get_wanted(db.get_db(), wanted_id)
    if wanted is None:
        abort(404)
    return wanted


def _validate(conn, wanted_id=None):
    """Return (wanted, errors) from the submitted form."""
    wanted, errors = parse_wanted(request.form)
    if wanted["name"] is not None:
        existing = db.find_wanted(conn, wanted["name"])
        if existing and existing["id"] != wanted_id:
            errors["name"] = "wanted.error_exists"
    return wanted, errors


def _render(edit_id=None, errors=None, status=200):
    """The list with an edit form per entry and the add form. After a failed save, the form that was
    sent (entry `edit_id`, or the add form when it is None) keeps what was typed and shows `errors`."""
    typed = {field: request.form.get(field, "") for field in WANTED_FIELDS} if errors else None
    return render_template("wanted/list.html", wanted=db.list_wanted(db.get_db()),
                           edit_id=edit_id, typed=typed, errors=errors or {}), status


@bp.get("")
def index():
    return _render()


@bp.post("")
def create():
    conn = db.get_db()
    wanted, errors = _validate(conn)
    if errors:
        return _render(errors=errors, status=400)
    db.create_wanted(conn, wanted)
    flash(t("wanted.msg_created", name=wanted["name"]), "success")
    return redirect(url_for(".index"))


@bp.post("/<int:wanted_id>")
def update(wanted_id):
    _load(wanted_id)
    conn = db.get_db()
    wanted, errors = _validate(conn, wanted_id)
    if errors:
        return _render(wanted_id, errors, 400)
    db.update_wanted(conn, wanted_id, wanted)
    flash(t("wanted.msg_updated", name=wanted["name"]), "success")
    return redirect(url_for(".index"))


@bp.post("/<int:wanted_id>/delete")
def delete(wanted_id):
    wanted = _load(wanted_id)
    db.delete_wanted(db.get_db(), wanted_id)
    flash(t("wanted.msg_deleted", name=wanted["name"]), "success")
    return redirect(url_for(".index"))
