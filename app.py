from flask import Flask, render_template

import db


def create_app():
    db.init_db()

    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
