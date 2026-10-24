import pytest

import config
import db
from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DB_PATH": tmp_path / "test.db",
                       "MIGRATIONS_DIR": config.MIGRATIONS_DIR,
                       "BACKUPS_DIR": tmp_path / "backups", "IMAGES_DIR": tmp_path / "images"})


@pytest.fixture
def client(app):
    return app.test_client()


def query(app, fn, *args):
    with app.app_context():
        return fn(db.get_db(), *args)


def recipe_form(**overrides):
    return {"title": "Пиле с ориз", "servings": "2", "prep_minutes": "10", "cook_minutes": "",
            "instructions": "Сварете ориза.\nДобавете пилето.", "notes": "",
            "ing_name": ["Пилешко филе", "Сол", ""], "ing_quantity": ["0,5", "", ""],
            "ing_unit": ["2", "", ""], "ing_note": ["", "на вкус", ""]} | overrides


@pytest.mark.parametrize("lang", ["en", "bg"])
@pytest.mark.parametrize("url", ["/recipes", "/recipes/new", "/ingredients", "/ingredients/new"])
def test_pages_render(client, url, lang):
    client.set_cookie("lang", lang)
    assert client.get(url).status_code == 200


def test_home_redirects_to_recipes(client):
    assert client.get("/").headers["Location"] == "/recipes"


def test_create_recipe_and_view_it(app, client):
    client.set_cookie("lang", "bg")
    response = client.post("/recipes", data=recipe_form())
    assert response.status_code == 302
    recipe_id = int(response.headers["Location"].rsplit("/", 1)[1])

    page = client.get(f"/recipes/{recipe_id}").get_data(as_text=True)
    assert "Пиле с ориз" in page
    assert "0,5 кг" in page
    assert "на вкус" in page
    assert "Рецептата „Пиле с ориз“ е запазена." in page

    assert query(app, db.ingredient_names) == ["Пилешко филе", "Сол"]
    assert "Пиле с ориз" in client.get("/recipes").get_data(as_text=True)


def test_invalid_recipe_keeps_what_was_typed(app, client):
    response = client.post("/recipes", data=recipe_form(title="", ing_unit=["", "", ""]))
    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert 'value="Пилешко филе"' in page
    assert "Choose a unit for this quantity." in page
    assert query(app, db.list_recipes) == []


def test_edit_and_delete_recipe(app, client):
    client.post("/recipes", data=recipe_form())
    recipe_id = query(app, db.list_recipes)[0]["id"]

    form = client.get(f"/recipes/{recipe_id}/edit").get_data(as_text=True)
    assert 'value="0.5"' in form

    response = client.post(f"/recipes/{recipe_id}", data=recipe_form(
        title="Пиле с ориз и грах", ing_name=["Грах"], ing_quantity=["200"], ing_unit=["1"], ing_note=[""]))
    assert response.status_code == 302
    assert query(app, db.get_recipe, recipe_id)["title"] == "Пиле с ориз и грах"
    assert [r["name"] for r in query(app, db.get_recipe_lines, recipe_id)] == ["Грах"]

    client.post(f"/recipes/{recipe_id}/delete")
    assert client.get(f"/recipes/{recipe_id}").status_code == 404


def test_ingredient_crud(app, client):
    client.post("/ingredients", data={"name": " Яйца "})
    response = client.post("/ingredients", data={"name": "яйца"})
    assert response.status_code == 400
    assert "already exists" in response.get_data(as_text=True)

    eggs = query(app, db.find_ingredient, "Яйца")["id"]
    client.post(f"/ingredients/{eggs}", data={"name": "ЯЙЦА"})  # only the case changes: allowed
    assert query(app, db.get_ingredient, eggs)["name"] == "ЯЙЦА"

    client.post(f"/ingredients/{eggs}/delete")
    assert query(app, db.get_ingredient, eggs) is None


def test_ingredient_in_use_is_not_deleted(app, client):
    client.post("/recipes", data=recipe_form())
    salt = query(app, db.find_ingredient, "Сол")["id"]

    response = client.post(f"/ingredients/{salt}/delete", follow_redirects=True)
    assert "is used in: Пиле с ориз" in response.get_data(as_text=True)
    assert query(app, db.get_ingredient, salt) is not None
