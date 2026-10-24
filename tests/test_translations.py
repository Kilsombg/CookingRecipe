import re

import config
from services.macros import MACROS
from translations import TEXTS

# t("key") in templates and Python code, and error keys returned by services/forms.py, photos.py and backup.py
T_CALL = re.compile(r"""\bt\(\s*["']([\w.]+)["']\s*[,)]""")
FORM_ERROR_KEY = re.compile(r"""["']((?:error|recipes|ingredients|data)\.\w+)["']""")


def test_en_and_bg_have_the_same_keys():
    assert set(TEXTS) == {"en", "bg"}
    assert set(TEXTS["en"]) == set(TEXTS["bg"])


def test_no_empty_texts():
    for lang, texts in TEXTS.items():
        empty = [key for key, text in texts.items() if not text.strip()]
        assert empty == [], lang


def test_every_used_key_exists():
    base = config.BASE_DIR
    used = set()
    for path in [*base.glob("templates/**/*.html"), base / "app.py", *base.glob("routes/*.py")]:
        used |= set(T_CALL.findall(path.read_text(encoding="utf-8")))
    for name in ("forms.py", "photos.py", "backup.py"):
        used |= set(FORM_ERROR_KEY.findall((base / "services" / name).read_text(encoding="utf-8")))

    assert used, "the patterns found nothing"
    assert sorted(used - set(TEXTS["en"])) == []


def test_keys_built_in_templates_exist():
    # t("label." ~ macro) and t("macros.missing_" ~ missing), which the pattern above can't see
    built = {f"label.{m}" for m in MACROS} | {f"macros.missing_{m}" for m in (*MACROS, "grams_per_piece")}
    assert sorted(built - set(TEXTS["en"])) == []
