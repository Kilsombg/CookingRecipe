"""Data page: download everything as a JSON file, and add the contents of such a file."""

import json
from datetime import datetime

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for

import db
from i18n import t
from services.backup import BackupError, build_export, parse_import

bp = Blueprint("data", __name__, url_prefix="/data")


@bp.get("")
def index():
    return render_template("data/index.html")


@bp.get("/export")
def export():
    now = datetime.now()
    body = json.dumps(build_export(db.export_data(db.get_db()), now), ensure_ascii=False, indent=2)
    return Response(body, mimetype="application/json", headers={
        "Content-Disposition": f"attachment; filename=cookingrecipe-{now:%Y%m%d-%H%M%S}.json"})


@bp.post("/import")
def import_file():
    upload = request.files.get("file")
    if not upload:
        return render_template("data/index.html", error=t("data.error_no_file")), 400
    try:
        data = parse_import(upload.read())
    except BackupError as e:
        return render_template("data/index.html", error=t(e.key, where=e.where)), 400

    conn = db.get_db()
    db.backup(conn, current_app.config["BACKUPS_DIR"])
    added = db.import_data(conn, data)
    flash(t("data.msg_imported", **added), "success")
    return redirect(url_for(".index"))
