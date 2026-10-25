import secrets

from flask import Flask, redirect, render_template, send_from_directory, url_for

import config
import db
import i18n
from routes import data, ingredients, menus, recipes, shopping, units, wanted
from services.forms import url_host
from services.macros import MACROS
from services.text import split_steps, tag_icon


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_mapping(
        # Only signs the flash-message cookie, so a new random key on every start is fine
        SECRET_KEY=secrets.token_hex(),
        DB_PATH=config.DB_PATH,
        MIGRATIONS_DIR=config.MIGRATIONS_DIR,
        BACKUPS_DIR=config.BACKUPS_DIR,
        IMAGES_DIR=config.IMAGES_DIR,
        MAX_PHOTO_BYTES=config.MAX_PHOTO_BYTES,
        # Room for the rest of the recipe form; a bigger photo is rejected with a message by the form
        MAX_CONTENT_LENGTH=config.MAX_PHOTO_BYTES + 1024 * 1024,
    )
    app.config.update(overrides or {})

    db.init_db(app.config["DB_PATH"], app.config["MIGRATIONS_DIR"],
               app.config["BACKUPS_DIR"], app.config["IMAGES_DIR"])
    db.init_app(app)
    i18n.init_app(app)
    app.jinja_env.globals["macro_names"] = MACROS
    app.jinja_env.filters["host"] = url_host
    app.jinja_env.filters["tag_icon"] = tag_icon
    app.jinja_env.filters["steps"] = split_steps
    app.register_blueprint(recipes.bp)
    app.register_blueprint(wanted.bp)
    app.register_blueprint(ingredients.bp)
    app.register_blueprint(units.bp)
    app.register_blueprint(menus.bp)
    app.register_blueprint(shopping.bp)
    app.register_blueprint(data.bp)

    @app.get("/")
    def index():
        return redirect(url_for("recipes.index"))

    @app.get("/images/<filename>")
    def image(filename):
        return send_from_directory(app.config["IMAGES_DIR"], filename)

    @app.errorhandler(413)
    def too_large(e):
        return render_template("error.html", message=i18n.t("recipes.error_photo_too_large")), 413

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
