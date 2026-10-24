import secrets

from flask import Flask, redirect, url_for

import config
import db
import i18n
from routes import ingredients, recipes


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_mapping(
        # Only signs the flash-message cookie, so a new random key on every start is fine
        SECRET_KEY=secrets.token_hex(),
        DB_PATH=config.DB_PATH,
        MIGRATIONS_DIR=config.MIGRATIONS_DIR,
        BACKUPS_DIR=config.BACKUPS_DIR,
        IMAGES_DIR=config.IMAGES_DIR,
    )
    app.config.update(overrides or {})

    db.init_db(app.config["DB_PATH"], app.config["MIGRATIONS_DIR"],
               app.config["BACKUPS_DIR"], app.config["IMAGES_DIR"])
    db.init_app(app)
    i18n.init_app(app)
    app.register_blueprint(recipes.bp)
    app.register_blueprint(ingredients.bp)

    @app.get("/")
    def index():
        return redirect(url_for("recipes.index"))

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
