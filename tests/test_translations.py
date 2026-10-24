import re

import config
from translations import TEXTS

# t("key") in templates and Python code, and error keys returned by services/forms.py
T_CALL = re.compile(r"""\bt\(\s*["']([\w.]+)["']""")
FORM_ERROR_KEY = re.compile(r"""["']((?:error|recipes|ingredients)\.\w+)["']""")


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
    used |= set(FORM_ERROR_KEY.findall((base / "services" / "forms.py").read_text(encoding="utf-8")))

    assert used, "the patterns found nothing"
    assert sorted(used - set(TEXTS["en"])) == []
