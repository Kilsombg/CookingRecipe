"""UI language: current language from the `lang` cookie, t() lookup, language switch route."""

from flask import Blueprint, redirect, request

from services.forms import format_number
from translations import TEXTS

# Code -> label in the switch. Each label is written in its own language, so it is never translated.
LANGUAGES = {"en": "EN", "bg": "БГ"}
DECIMAL_SEPARATORS = {"en": ".", "bg": ","}
DEFAULT_LANG = "en"
COOKIE_NAME = "lang"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 year

bp = Blueprint("i18n", __name__)


def get_lang():
    """Language from the cookie; anything unknown falls back to English."""
    lang = request.cookies.get(COOKIE_NAME)
    return lang if lang in LANGUAGES else DEFAULT_LANG


def t(key, **params):
    """Text for `key` in the current language, with {placeholders} filled from `params`.

    Missing in the current language -> English; missing everywhere -> the key itself,
    so a gap is visible on the page but never crashes it.
    """
    text = TEXTS.get(get_lang(), {}).get(key)
    if text is None:
        text = TEXTS[DEFAULT_LANG].get(key, key)
    return text.format(**params) if params else text


def num(x):
    """A number with the current language's decimal separator: 0.5 -> "0,5" in Bulgarian."""
    return format_number(x, DECIMAL_SEPARATORS[get_lang()])


def safe_next(url):
    """Only allow redirects to a path on this site, never to another host."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return "/"


@bp.post("/language")
def set_language():
    response = redirect(safe_next(request.form.get("next")))
    lang = request.form.get("lang")
    if lang in LANGUAGES:
        response.set_cookie(COOKIE_NAME, lang, max_age=COOKIE_MAX_AGE, httponly=True, samesite="Lax")
    return response


def init_app(app):
    app.register_blueprint(bp)
    app.jinja_env.globals.update(t=t, languages=LANGUAGES)
    app.jinja_env.filters["num"] = num

    @app.context_processor
    def inject_lang():
        return {"lang": get_lang()}
