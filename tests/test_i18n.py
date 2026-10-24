import pytest
from flask import Flask, render_template_string

import i18n

TEST_TEXTS = {
    "en": {"greet": "Hello, {name}!", "only_en": "English only"},
    "bg": {"greet": "Здравей, {name}!"},
}


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(i18n, "TEXTS", TEST_TEXTS)
    app = Flask(__name__)
    i18n.init_app(app)

    @app.get("/page")
    def page():
        return render_template_string('{{ lang }}: {{ t("greet", name="Мария") }}')

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def t_with_cookie(app, lang, key, **params):
    headers = {"Cookie": f"lang={lang}"} if lang else {}
    with app.test_request_context(headers=headers):
        return i18n.t(key, **params)


def test_default_language_is_english(app):
    assert t_with_cookie(app, None, "greet", name="Ann") == "Hello, Ann!"


def test_bulgarian_from_cookie(app):
    assert t_with_cookie(app, "bg", "greet", name="Мария") == "Здравей, Мария!"


def test_unknown_cookie_value_falls_back_to_english(app):
    assert t_with_cookie(app, "de", "greet", name="Ann") == "Hello, Ann!"


def test_missing_bulgarian_text_falls_back_to_english(app):
    assert t_with_cookie(app, "bg", "only_en") == "English only"


def test_missing_key_shows_the_key(app):
    assert t_with_cookie(app, "bg", "no.such.key") == "no.such.key"


def test_templates_get_t_and_lang(client):
    client.set_cookie("lang", "bg")
    assert client.get("/page").get_data(as_text=True) == "bg: Здравей, Мария!"


def test_switch_language_sets_cookie_and_redirects_back(client):
    response = client.post("/language", data={"lang": "bg", "next": "/page?x=1"})
    assert response.status_code == 302
    assert response.headers["Location"] == "/page?x=1"
    assert client.get_cookie("lang").value == "bg"


def test_switch_to_unknown_language_keeps_cookie_unset(client):
    client.post("/language", data={"lang": "de", "next": "/page"})
    assert client.get_cookie("lang") is None


@pytest.mark.parametrize("next_url", [None, "", "https://evil.example", "//evil.example", "/\\evil.example"])
def test_switch_never_redirects_to_another_site(client, next_url):
    data = {"lang": "bg"}
    if next_url is not None:
        data["next"] = next_url
    response = client.post("/language", data=data)
    assert response.headers["Location"] == "/"
