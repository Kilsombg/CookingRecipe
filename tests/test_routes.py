import io
import re

import pytest
from markupsafe import escape
from PIL import Image

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
@pytest.mark.parametrize("url", ["/recipes", "/recipes/new", "/ingredients", "/ingredients/new", "/menus", "/units",
                                 "/data"])
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


def test_recipe_keeps_ingredient_order(app, client):
    # Dragging rows on the form only changes the order they are sent in
    client.post("/recipes", data=recipe_form(ing_name=["Сол", "Пилешко филе", "Магданоз"],
                                             ing_quantity=["", "0,5", ""], ing_unit=["", "2", ""],
                                             ing_note=["", "", ""]))
    recipe_id = query(app, db.list_recipes)[0]["id"]
    assert [r["name"] for r in query(app, db.get_recipe_lines, recipe_id)] == ["Сол", "Пилешко филе", "Магданоз"]

    client.post(f"/recipes/{recipe_id}", data=recipe_form(ing_name=["Пилешко филе", "Сол", "Магданоз"],
                                                          ing_quantity=["0,5", "", ""], ing_unit=["2", "", ""],
                                                          ing_note=["", "", ""]))
    assert [r["name"] for r in query(app, db.get_recipe_lines, recipe_id)] == ["Пилешко филе", "Сол", "Магданоз"]
    form = client.get(f"/recipes/{recipe_id}/edit").get_data(as_text=True)
    assert form.index('value="Пилешко филе"') < form.index('value="Сол"') < form.index('value="Магданоз"')


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


def ingredient_form(**overrides):
    return {"name": "Пилешко филе", "calories_100g": "110", "protein_100g": "23", "carbs_100g": "0",
            "fat_100g": "1,5", "grams_per_piece": ""} | overrides


@pytest.mark.parametrize("lang", ["en", "bg"])
def test_more_pages_render(client, lang):
    client.set_cookie("lang", lang)
    client.post("/ingredients", data=ingredient_form())
    client.post("/recipes", data=recipe_form())
    for url in ["/ingredients?missing=1", "/ingredients/1/edit", "/recipes/1", "/recipes"]:
        assert client.get(url).status_code == 200, url


def test_lists_are_paged(app, client):
    for i in range(1, 13):
        client.post("/ingredients", data={"name": f"Item {i:02}"})
    page = client.get("/ingredients?per_page=10&page=2&q=item").get_data(as_text=True)
    assert "11–12 of 12" in page
    assert ">Item 11</a>" in page and ">Item 10</a>" not in page
    assert 'href="/ingredients?per_page=10&amp;q=item"' in page  # page 1, filters kept
    assert '<input type="hidden" name="q" value="item">' in page

    page = client.get("/ingredients").get_data(as_text=True)
    assert "1–12 of 12" in page
    assert '<option value="50" selected>' in page

    client.post("/recipes", data=recipe_form())
    page = client.get("/recipes").get_data(as_text=True)
    assert "1–1 of 1" in page
    assert '<option value="20" selected>' in page


def test_ingredient_macros_are_saved_and_listed(app, client):
    client.set_cookie("lang", "bg")
    assert client.post("/ingredients", data=ingredient_form()).status_code == 302
    chicken = query(app, db.find_ingredient, "Пилешко филе")
    assert (chicken["calories_100g"], chicken["fat_100g"], chicken["grams_per_piece"]) == (110, 1.5, None)

    page = client.get("/ingredients").get_data(as_text=True)
    assert "1,5" in page
    form = client.get(f"/ingredients/{chicken['id']}/edit").get_data(as_text=True)
    assert 'value="1,5"' in form


def test_invalid_ingredient_macros(app, client):
    response = client.post("/ingredients", data=ingredient_form(protein_100g="-1", carbs_100g="много"))
    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert "Enter a number, 0 or more." in page
    assert 'value="много"' in page
    assert query(app, db.find_ingredient, "Пилешко филе") is None


def test_recipe_macros_and_incomplete_ingredients(app, client):
    # 0,5 кг chicken (110 kcal / 100 g) for 2 servings = 550 kcal, 275 per serving; salt has no quantity
    client.post("/ingredients", data=ingredient_form())
    client.post("/recipes", data=recipe_form(ing_name=["Пилешко филе", "Сол", "Яйца"],
                                             ing_quantity=["0,5", "", "2"], ing_unit=["2", "", "8"]))
    recipe_id = query(app, db.list_recipes)[0]["id"]

    page = client.get(f"/recipes/{recipe_id}").get_data(as_text=True)
    assert '≥</span>275</strong>' in page          # per serving badge, at least: the eggs have no data
    assert "550 kcal" in page                      # whole recipe
    assert '≥</span>58<small>g</small>' in page   # protein per serving: 500 g × 23 / 100 / 2 = 57.5
    assert "115 g" in page
    eggs = query(app, db.find_ingredient, "Яйца")["id"]
    assert f"/ingredients/{eggs}/edit?next=/recipes/{recipe_id}" in page
    assert "grams per piece, calories, protein, carbs, fat" in page
    assert "Сол" not in page.split("missing data:")[1].split("</div>")[0]

    assert '≥</span>275</strong>' in client.get("/recipes").get_data(as_text=True)
    assert [r["name"] for r in query(app, db.list_ingredients, "", True)] == ["Сол", "Яйца"]

    # Filling in the eggs from the recipe page goes back to the recipe, now complete
    response = client.post(f"/ingredients/{eggs}", data=ingredient_form(
        name="Яйца", calories_100g="143", protein_100g="12,6", carbs_100g="0,7", fat_100g="9,5",
        grams_per_piece="55", next=f"/recipes/{recipe_id}"))
    assert response.headers["Location"] == f"/recipes/{recipe_id}"
    page = client.get(f"/recipes/{recipe_id}").get_data(as_text=True)
    assert "missing data" not in page
    assert '<strong class="macro-value">354</strong>' in page   # (550 + 110 × 1.43) / 2 = 353.65
    assert '<strong class="macro-value">354</strong>' in client.get("/recipes").get_data(as_text=True)


def test_ingredient_form_next_cannot_leave_the_site(app, client):
    client.post("/ingredients", data=ingredient_form())
    chicken = query(app, db.find_ingredient, "Пилешко филе")["id"]
    response = client.post(f"/ingredients/{chicken}", data=ingredient_form(next="https://example.com"))
    assert response.headers["Location"] == "/"


def test_recipe_without_data_shows_no_card_calories(client):
    client.post("/recipes", data=recipe_form())
    assert "kcal" not in client.get("/recipes").get_data(as_text=True)


def png(size=(2000, 1000)):
    out = io.BytesIO()
    Image.new("RGB", size, "green").save(out, "PNG")
    return out.getvalue()


def post_with_photo(client, url, data, photo_bytes, filename="снимка.png"):
    return client.post(url, data=data | {"photo": (io.BytesIO(photo_bytes), filename)},
                       content_type="multipart/form-data")


def test_photo_upload_replace_remove_and_delete(app, client):
    images = app.config["IMAGES_DIR"]
    response = post_with_photo(client, "/recipes", recipe_form(), png())
    assert response.status_code == 302
    recipe_id = query(app, db.list_recipes)[0]["id"]
    first = query(app, db.get_recipe, recipe_id)["photo_filename"]
    with Image.open(images / first) as img:
        assert (img.format, img.size) == ("JPEG", (1600, 800))

    assert f"/images/{first}" in client.get("/recipes").get_data(as_text=True)
    assert f"/images/{first}" in client.get(f"/recipes/{recipe_id}").get_data(as_text=True)
    assert client.get(f"/images/{first}").status_code == 200

    # Saving without choosing a file keeps the photo
    client.post(f"/recipes/{recipe_id}", data=recipe_form())
    assert query(app, db.get_recipe, recipe_id)["photo_filename"] == first

    # A new photo replaces the old file
    post_with_photo(client, f"/recipes/{recipe_id}", recipe_form(), png((300, 200)))
    second = query(app, db.get_recipe, recipe_id)["photo_filename"]
    assert second != first
    assert not (images / first).exists()

    client.post(f"/recipes/{recipe_id}", data=recipe_form(remove_photo="1"))
    assert query(app, db.get_recipe, recipe_id)["photo_filename"] is None
    assert not (images / second).exists()
    assert "placeholder.svg" in client.get("/recipes").get_data(as_text=True)

    post_with_photo(client, f"/recipes/{recipe_id}", recipe_form(), png())
    third = query(app, db.get_recipe, recipe_id)["photo_filename"]
    client.post(f"/recipes/{recipe_id}/delete")
    assert not (images / third).exists()
    assert list(images.iterdir()) == []


def test_invalid_photo_is_rejected(app, client):
    response = post_with_photo(client, "/recipes", recipe_form(), b"GIF89a not really", "снимка.gif")
    assert response.status_code == 400
    assert "Choose a JPG, PNG or WebP image." in response.get_data(as_text=True)
    assert query(app, db.list_recipes) == []
    assert list(app.config["IMAGES_DIR"].iterdir()) == []


def test_other_errors_ask_to_choose_the_photo_again(app, client):
    response = post_with_photo(client, "/recipes", recipe_form(title=""), png())
    assert response.status_code == 400
    assert "Choose the photo again" in response.get_data(as_text=True)
    assert list(app.config["IMAGES_DIR"].iterdir()) == []


def test_request_over_the_size_limit(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 1000
    response = post_with_photo(client, "/recipes", recipe_form(), png())
    assert response.status_code == 413
    assert "The photo is too large" in response.get_data(as_text=True)


def test_image_route_stays_in_the_images_folder(client):
    assert client.get("/images/..%2Fapp.py").status_code == 404
    assert client.get("/images/missing.jpg").status_code == 404


def test_source_link(app, client):
    client.post("/recipes", data=recipe_form(source_url="www.youtube.com/watch?v=abc"))
    recipe_id = query(app, db.list_recipes)[0]["id"]
    page = client.get(f"/recipes/{recipe_id}").get_data(as_text=True)
    assert ('<a href="https://www.youtube.com/watch?v=abc" target="_blank" rel="noopener noreferrer">'
            "youtube.com <svg") in page

    form = client.get(f"/recipes/{recipe_id}/edit").get_data(as_text=True)
    assert 'value="https://www.youtube.com/watch?v=abc"' in form

    response = client.post(f"/recipes/{recipe_id}", data=recipe_form(source_url="javascript://alert(1)"))
    assert response.status_code == 400
    assert 'value="javascript://alert(1)"' in response.get_data(as_text=True)


def test_tags_on_form_cards_and_filter(app, client):
    client.post("/recipes", data=recipe_form(tags="Обяд, бързо"))
    client.post("/recipes", data=recipe_form(title="Омлет", tags="закуска, БЪРЗО"))
    lunch = query(app, db.list_recipes, "Пиле с ориз")[0]["id"]
    tags = {t["name"]: t["id"] for t in query(app, db.list_tags)}
    assert set(tags) == {"обяд", "бързо", "закуска"}

    assert 'value="бързо, обяд"' in client.get(f"/recipes/{lunch}/edit").get_data(as_text=True)
    assert f"/recipes?tag={tags['обяд']}" in client.get(f"/recipes/{lunch}").get_data(as_text=True)

    page = client.get(f"/recipes?tag={tags['закуска']}").get_data(as_text=True)
    assert "Омлет" in page and "Пиле с ориз" not in page
    page = client.get(f"/recipes?tag={tags['бързо']}").get_data(as_text=True)
    assert "Омлет" in page and "Пиле с ориз" in page
    # An unknown tag id shows everything rather than an error
    assert "Пиле с ориз" in client.get("/recipes?tag=999").get_data(as_text=True)
    assert "Пиле с ориз" in client.get("/recipes?tag=abc").get_data(as_text=True)


def test_search_recipes(client):
    client.set_cookie("lang", "bg")
    client.post("/recipes", data=recipe_form(ing_name=["Ориз"], ing_quantity=["200"], ing_unit=["1"], ing_note=[""]))
    client.post("/recipes", data=recipe_form(title="Омлет", ing_name=["Яйца", "Пилешко филе"],
                                             ing_quantity=["3", ""], ing_unit=["8", ""], ing_note=["", ""]))
    client.get("/recipes")  # shows the flash messages, which contain the titles

    page = client.get("/recipes?q=ОРИЗ").get_data(as_text=True)
    assert "Пиле с ориз" in page and "Омлет" not in page
    page = client.get("/recipes?q=яйца").get_data(as_text=True)
    assert "Омлет" in page and "Пиле с ориз" not in page
    page = client.get("/recipes?q=пиле").get_data(as_text=True)   # a title, and an ingredient of the omelette
    assert "Омлет" in page and "Пиле с ориз" in page
    page = client.get("/recipes?q=торта").get_data(as_text=True)
    assert "Няма намерени рецепти." in page


def create_menu(client, name="Седмица 12 ноември"):
    response = client.post("/menus", data={"name": name})
    assert response.status_code == 302
    return int(response.headers["Location"].rsplit("/", 1)[1])


def test_create_rename_and_delete_menu(app, client):
    client.set_cookie("lang", "bg")
    assert client.post("/menus", data={"name": "  "}).status_code == 400
    menu_id = create_menu(client)
    page = client.get(f"/menus/{menu_id}").get_data(as_text=True)
    assert "Менюто „Седмица 12 ноември“ е създадено." in page
    assert "Седмица 12 ноември" in client.get("/menus").get_data(as_text=True)

    assert client.post(f"/menus/{menu_id}", data={"name": ""}).status_code == 400
    client.post(f"/menus/{menu_id}", data={"name": "Рожден ден"})
    assert query(app, db.get_menu, menu_id)["name"] == "Рожден ден"

    client.post(f"/menus/{menu_id}/delete")
    assert client.get(f"/menus/{menu_id}").status_code == 404
    assert query(app, db.list_menus) == []


@pytest.mark.parametrize("lang", ["en", "bg"])
def test_menu_grouped_by_day_and_meal_with_macros(app, client, lang):
    client.set_cookie("lang", lang)
    # 0,5 кг chicken (110 kcal / 100 g) for 2 servings = 275 kcal per serving
    client.post("/ingredients", data=ingredient_form())
    client.post("/recipes", data=recipe_form())
    recipe_id = query(app, db.list_recipes)[0]["id"]
    menu_id = create_menu(client)

    response = client.post(f"/menus/{menu_id}/items",
                           data={"recipe_id": recipe_id, "day": "2", "meal": "dinner", "servings": ""})
    assert response.headers["Location"] == f"/menus/{menu_id}?day=2&meal=dinner"
    client.post(f"/menus/{menu_id}/items", data={"recipe_id": recipe_id, "day": "0", "meal": "lunch", "servings": "1"})
    client.post(f"/menus/{menu_id}/items", data={"recipe_id": recipe_id, "day": "0", "meal": "", "servings": "1"})

    page = client.get(f"/menus/{menu_id}?day=2&meal=dinner").get_data(as_text=True)
    # Monday, then Wednesday, before the macros; without the icons in front of the headings
    items = [re.sub(r"<svg.*?</svg>\s*", "", item) for item in page.split("<h2>")[1:3]]
    if lang == "bg":
        assert items[0].startswith("Понеделник") and items[1].startswith("Сряда")
        assert items[0].index("Обяд") < items[0].index("Друго")
        assert "Вечеря" in items[1]
    else:
        assert items[0].startswith("Monday") and items[1].startswith("Wednesday")
        assert items[0].index("Lunch") < items[0].index("Other")
        assert "Dinner" in items[1]
    assert '<option value="2" selected>' in page and '<option value="dinner" selected>' in page
    kcal = "ккал" if lang == "bg" else "kcal"
    assert f"550 {kcal}" in page    # Monday: 2 × 275, and Wednesday: the recipe's 2 servings
    assert f"1100 {kcal}" in page   # whole menu
    assert "macros-incomplete" not in page  # the salt has no quantity, so it doesn't count as missing


def test_menu_without_days_is_a_plain_list(app, client):
    client.post("/recipes", data=recipe_form())
    recipe_id = query(app, db.list_recipes)[0]["id"]
    menu_id = create_menu(client, "Рожден ден")
    client.post(f"/menus/{menu_id}/items", data={"recipe_id": recipe_id, "day": "", "meal": "", "servings": "6"})
    page = client.get(f"/menus/{menu_id}").get_data(as_text=True)
    assert "No specific day" not in page.split("<h2>Add a recipe</h2>")[0]
    assert "6 servings" in page
    # The recipe has no macro data, so it is listed as incomplete
    assert "these recipes have ingredients with missing data" in page


def test_invalid_menu_item_and_remove_item(app, client):
    client.post("/recipes", data=recipe_form())
    recipe_id = query(app, db.list_recipes)[0]["id"]
    menu_id = create_menu(client)
    response = client.post(f"/menus/{menu_id}/items",
                           data={"recipe_id": recipe_id, "day": "0", "meal": "lunch", "servings": "0"})
    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert "Enter a number greater than 0." in page
    assert '<option value="lunch" selected>' in page
    assert query(app, db.get_menu_items, menu_id) == []

    client.post(f"/menus/{menu_id}/items", data={"recipe_id": recipe_id, "day": "0", "meal": "lunch", "servings": "1"})
    item_id = query(app, db.get_menu_items, menu_id)[0]["id"]
    other_menu = create_menu(client, "Друго")
    assert client.post(f"/menus/{other_menu}/items/{item_id}/delete").status_code == 404
    client.post(f"/menus/{menu_id}/items/{item_id}/delete")
    assert query(app, db.get_menu_items, menu_id) == []


@pytest.mark.parametrize("lang", ["en", "bg"])
def test_shopping_list_is_built_from_the_menu(app, client, lang):
    client.set_cookie("lang", lang)
    # 0,5 кг chicken and salt to taste, for 2 servings; cooked for 2 and for 1 servings
    client.post("/recipes", data=recipe_form())
    recipe_id = query(app, db.list_recipes)[0]["id"]
    menu_id = create_menu(client)
    for servings in ("", "1"):
        client.post(f"/menus/{menu_id}/items", data={"recipe_id": recipe_id, "day": "", "meal": "", "servings": servings})
    assert f"/menus/{menu_id}/shopping" in client.get(f"/menus/{menu_id}").get_data(as_text=True)

    page = client.get(f"/menus/{menu_id}/shopping").get_data(as_text=True)
    amount = "0,75 кг" if lang == "bg" else "0.75 кг"
    assert f"Пилешко филе <small>{amount}</small>" in page
    assert "Сол</span>" in page
    assert [(i["name"], i["quantity"], i["unit"]) for i in query(app, db.get_shopping_items, menu_id)] == [
        ("Пилешко филе", 0.75, "кг"), ("Сол", None, None)]


def test_shopping_list_ticks_manual_items_and_rebuild(app, client):
    client.post("/recipes", data=recipe_form())
    recipe_id = query(app, db.list_recipes)[0]["id"]
    menu_id = create_menu(client)
    client.post(f"/menus/{menu_id}/items", data={"recipe_id": recipe_id, "day": "", "meal": "", "servings": ""})
    client.get(f"/menus/{menu_id}/shopping")
    chicken, salt = query(app, db.get_shopping_items, menu_id)

    assert client.post(f"/shopping/items/{chicken['id']}/toggle", data={"checked": "1"}).status_code == 204
    assert client.post("/shopping/items/999/toggle", data={"checked": "1"}).status_code == 404
    assert query(app, db.get_shopping_item, chicken["id"])["checked"] == 1

    response = client.post("/shopping/items", data={"menu_id": menu_id, "name": "", "quantity": "0", "unit": ""})
    assert response.status_code == 400
    assert "Enter a number greater than 0." in response.get_data(as_text=True)
    assert client.post("/shopping/items", data={"menu_id": 999, "name": "Мляко"}).status_code == 404
    response = client.post("/shopping/items", data={"menu_id": menu_id, "name": "Мляко", "quantity": "1", "unit": "л"})
    assert response.headers["Location"] == f"/menus/{menu_id}/shopping"
    page = client.get(f"/menus/{menu_id}/shopping").get_data(as_text=True)
    assert "Мляко <small>1 л</small>" in page and "Added by hand" in page

    # Doubling the servings changes the chicken (so its tick goes); the milk stays
    item_id = query(app, db.get_menu_items, menu_id)[0]["id"]
    client.post(f"/menus/{menu_id}/items/{item_id}/delete")
    client.post(f"/menus/{menu_id}/items", data={"recipe_id": recipe_id, "day": "", "meal": "", "servings": "4"})
    assert query(app, db.get_shopping_items, menu_id)[0]["quantity"] == 0.5  # not rebuilt by itself
    client.post(f"/menus/{menu_id}/shopping/regenerate")
    items = query(app, db.get_shopping_items, menu_id)
    assert [(i["name"], i["quantity"], i["checked"]) for i in items] == [
        ("Пилешко филе", 1, 0), ("Сол", None, 0), ("Мляко", 1, 0)]

    assert client.post(f"/shopping/items/{items[0]['id']}/delete").status_code == 404
    client.post(f"/shopping/items/{items[2]['id']}/delete")
    assert len(query(app, db.get_shopping_items, menu_id)) == 2
    assert client.get("/menus/999/shopping").status_code == 404


def test_shopping_list_of_an_empty_menu(client):
    menu_id = create_menu(client)
    page = client.get(f"/menus/{menu_id}/shopping").get_data(as_text=True)
    assert "Nothing to buy yet." in page


def test_add_rename_and_delete_unit(app, client):
    client.set_cookie("lang", "bg")
    response = client.post("/units", data={"name": "чаша", "grams": "240"})
    assert response.headers["Location"] == "/units"
    page = client.get("/units").get_data(as_text=True)
    assert "Мерната единица „чаша“ е добавена." in page
    cup = query(app, db.find_unit, "чаша")["id"]

    # The new name shows on recipes that use it, and its grams count for the macros
    client.post("/ingredients", data=ingredient_form(name="Ориз"))
    client.post("/recipes", data=recipe_form(ing_name=["Ориз"], ing_quantity=["1"], ing_unit=[str(cup)], ing_note=[""]))
    client.post(f"/units/{cup}", data={"name": "Чаша", "grams": "0,5"})
    assert dict(query(app, db.get_unit, cup)) == {"id": cup, "name": "Чаша", "grams": 0.5}
    assert "1 Чаша" in client.get("/recipes/1").get_data(as_text=True)

    client.post(f"/units/{cup}/delete")
    assert query(app, db.get_unit, cup) is not None
    assert "не може да се изтрие" in client.get("/units").get_data(as_text=True)

    spare = query(app, db.create_unit, {"name": "глава", "grams": None})
    client.post(f"/units/{spare}/delete")
    assert query(app, db.get_unit, spare) is None
    assert client.post("/units/999", data={"name": "x", "grams": ""}).status_code == 404


def test_invalid_unit_keeps_what_was_typed(app, client):
    response = client.post("/units", data={"name": "Г", "grams": "0"})
    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert "A unit with this name already exists." in page
    assert "Enter a number greater than 0." in page
    assert 'value="Г"' in page

    # Editing a row: only that row shows the typed values; keeping its own name is fine
    grams_id = query(app, db.find_unit, "г")["id"]
    response = client.post(f"/units/{grams_id}", data={"name": "кг", "grams": "1"})
    assert response.status_code == 400
    assert response.get_data(as_text=True).count('value="кг"') == 2   # the edited row and the real кг
    assert client.post(f"/units/{grams_id}", data={"name": "г", "grams": "1"}).status_code == 302


def test_favourite_toggle_card_star_and_filter(app, client):
    client.post("/recipes", data=recipe_form())
    client.post("/recipes", data=recipe_form(title="Омлет"))
    lunch = query(app, db.list_recipes, "Пиле с ориз")[0]["id"]
    assert 'href="/recipes?fav=1"' not in client.get("/recipes").get_data(as_text=True)  # offered once there is one
    assert "Add to favourites" in client.get(f"/recipes/{lunch}").get_data(as_text=True)

    response = client.post(f"/recipes/{lunch}/favourite", data={"favourite": "1"})
    assert response.headers["Location"] == f"/recipes/{lunch}"
    assert 'aria-pressed="true"' in client.get(f"/recipes/{lunch}").get_data(as_text=True)
    page = client.get("/recipes").get_data(as_text=True)
    assert 'href="/recipes?fav=1"' in page and page.count('class="favourite-star is-favourite"') == 1
    assert page.count('class="favourite-star"') == 1   # the other card offers an empty star

    # The card star comes back to the list it was clicked on, never to another site
    omelette = query(app, db.list_recipes, "Омлет")[0]["id"]
    response = client.post(f"/recipes/{omelette}/favourite",
                           data={"favourite": "1", "next": f"/recipes?q=x#recipe-{omelette}"})
    assert response.headers["Location"] == f"/recipes?q=x#recipe-{omelette}"
    response = client.post(f"/recipes/{omelette}/favourite", data={"favourite": "0", "next": "//evil.example"})
    assert response.headers["Location"] == "/"

    # app.js saves it without a reload: no redirect, just "done"
    response = client.post(f"/recipes/{omelette}/favourite", data={"favourite": "1"},
                           headers={"X-Requested-With": "fetch"})
    assert response.status_code == 204
    assert query(app, db.get_recipe, omelette)["is_favourite"]
    client.post(f"/recipes/{omelette}/favourite", data={"favourite": "0"})

    page = client.get("/recipes?fav=1").get_data(as_text=True)
    assert "Пиле с ориз" in page and "Омлет" not in page
    assert 'name="fav" value="1"' in page   # a search keeps the filter

    client.post(f"/recipes/{lunch}/favourite", data={"favourite": "0"})
    assert "No recipes match." in client.get("/recipes?fav=1").get_data(as_text=True)
    assert client.post("/recipes/999/favourite", data={"favourite": "1"}).status_code == 404


def test_copy_menu(app, client):
    client.set_cookie("lang", "bg")
    client.post("/recipes", data=recipe_form())
    recipe_id = query(app, db.list_recipes)[0]["id"]
    menu_id = create_menu(client)
    client.post(f"/menus/{menu_id}/items", data={"recipe_id": recipe_id, "day": "4", "meal": "dinner", "servings": "3"})

    response = client.post(f"/menus/{menu_id}/copy")
    copy_id = int(response.headers["Location"].rsplit("/", 1)[1])
    assert copy_id != menu_id
    page = client.get(f"/menus/{copy_id}").get_data(as_text=True)
    assert "Менюто е копирано като „Седмица 12 ноември (копие)“." in page
    assert "Петък" in page and "порции: 3" in page
    assert client.post("/menus/999/copy").status_code == 404


def test_export_then_import_into_a_new_app(app, client, tmp_path):
    client.post("/recipes", data=recipe_form(tags="обяд"))
    recipe_id = query(app, db.list_recipes)[0]["id"]
    client.post(f"/recipes/{recipe_id}/favourite", data={"favourite": "1"})
    menu_id = create_menu(client)
    client.post(f"/menus/{menu_id}/items", data={"recipe_id": recipe_id, "day": "0", "meal": "", "servings": ""})

    response = client.get("/data/export")
    assert response.mimetype == "application/json"
    assert response.headers["Content-Disposition"].startswith("attachment; filename=cookingrecipe-")
    exported = response.get_data()
    assert "Пиле с ориз".encode("utf-8") in exported  # readable, not \u escapes

    other = create_app({"TESTING": True, "DB_PATH": tmp_path / "other.db", "MIGRATIONS_DIR": config.MIGRATIONS_DIR,
                        "BACKUPS_DIR": tmp_path / "other-backups", "IMAGES_DIR": tmp_path / "other-images"})
    other_client = other.test_client()
    response = other_client.post("/data/import", data={"file": (io.BytesIO(exported), "export.json")})
    assert response.headers["Location"] == "/data"
    page = other_client.get("/data").get_data(as_text=True)
    assert "Added recipes: 1, ingredients: 2, units: 0, menus: 1." in page
    assert len(list((tmp_path / "other-backups").iterdir())) == 1

    imported = query(other, db.list_recipes, "", None, True)
    assert [r["title"] for r in imported] == ["Пиле с ориз"]
    assert [t["name"] for t in query(other, db.get_recipe_tags, imported[0]["id"])] == ["обяд"]
    assert [m["item_count"] for m in query(other, db.list_menus)] == [1]


@pytest.mark.parametrize("content, message", [
    (None, "Choose a file to import."),
    (b"hello", "This isn't a JSON file."),
    (b'{"recipes": []}', "This file wasn't exported from CookingRecipe."),
    (b'{"format": "CookingRecipe", "version": 1, "recipes": [{"id": 1}]}',
     "The file has a wrong or missing value at recipes[0].title. Nothing was imported."),
])
def test_bad_import_files(app, client, content, message):
    data = {} if content is None else {"file": (io.BytesIO(content), "export.json")}
    response = client.post("/data/import", data=data)
    assert response.status_code == 400
    assert str(escape(message)) in response.get_data(as_text=True)
    assert query(app, db.list_recipes) == []
    assert list(app.config["BACKUPS_DIR"].iterdir()) == []
