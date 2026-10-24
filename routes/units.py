"""Units page: list, add, rename / change grams, delete while no recipe uses it."""

import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import db
from i18n import t
from services.forms import UNIT_FIELDS, parse_unit

bp = Blueprint("units", __name__, url_prefix="/units")


def _load(unit_id):
    unit = db.get_unit(db.get_db(), unit_id)
    if unit is None:
        abort(404)
    return unit


def _validate(conn, unit_id=None):
    """Return (unit, errors) from the submitted form."""
    unit, errors = parse_unit(request.form)
    if unit["name"] is not None:
        existing = db.find_unit(conn, unit["name"])
        if existing and existing["id"] != unit_id:
            errors["name"] = "units.error_exists"
    return unit, errors


def _render(edit_id=None, errors=None, status=200):
    """The list with an edit form per unit and the add form. After a failed save, the form that was
    sent (unit `edit_id`, or the add form when it is None) keeps what was typed and shows `errors`."""
    typed = {field: request.form.get(field, "") for field in UNIT_FIELDS} if errors else None
    return render_template("units/list.html", units=db.list_units_with_usage(db.get_db()),
                           edit_id=edit_id, typed=typed, errors=errors or {}), status


@bp.get("")
def index():
    return _render()


@bp.post("")
def create():
    conn = db.get_db()
    unit, errors = _validate(conn)
    if errors:
        return _render(errors=errors, status=400)
    db.create_unit(conn, unit)
    flash(t("units.msg_created", name=unit["name"]), "success")
    return redirect(url_for(".index"))


@bp.post("/<int:unit_id>")
def update(unit_id):
    _load(unit_id)
    conn = db.get_db()
    unit, errors = _validate(conn, unit_id)
    if errors:
        return _render(unit_id, errors, 400)
    db.update_unit(conn, unit_id, unit)
    flash(t("units.msg_updated", name=unit["name"]), "success")
    return redirect(url_for(".index"))


@bp.post("/<int:unit_id>/delete")
def delete(unit_id):
    unit = _load(unit_id)
    try:
        db.delete_unit(db.get_db(), unit_id)
    except sqlite3.IntegrityError:
        flash(t("units.error_in_use", name=unit["name"]), "error")
    else:
        flash(t("units.msg_deleted", name=unit["name"]), "success")
    return redirect(url_for(".index"))
