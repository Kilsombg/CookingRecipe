from translations import TEXTS


def test_en_and_bg_have_the_same_keys():
    assert set(TEXTS) == {"en", "bg"}
    assert set(TEXTS["en"]) == set(TEXTS["bg"])


def test_no_empty_texts():
    for lang, texts in TEXTS.items():
        empty = [key for key, text in texts.items() if not text.strip()]
        assert empty == [], lang
