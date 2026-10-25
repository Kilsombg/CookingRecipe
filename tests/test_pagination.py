import pytest
from flask import Flask

from services.pagination import paginate


@pytest.fixture
def app():
    app = Flask(__name__)
    app.add_url_rule("/things", "things")
    return app


def page_of(app, url, total, default=20, options=(10, 20, 50)):
    with app.test_request_context(url):
        return paginate(range(1, total + 1), default, options)


def test_first_page_by_default(app):
    page = page_of(app, "/things", 45)
    assert (page.number, page.pages, page.per_page) == (1, 3, 20)
    assert page.items == list(range(1, 21))
    assert (page.start, page.end, page.total) == (1, 20, 45)
    assert not page.has_prev and page.has_next


def test_last_page_is_partial(app):
    page = page_of(app, "/things?page=3", 45)
    assert page.items == list(range(41, 46))
    assert (page.start, page.end) == (41, 45)
    assert page.has_prev and not page.has_next


@pytest.mark.parametrize("url, number, per_page", [
    ("/things?page=99", 3, 20),       # past the end: the last page
    ("/things?page=0", 1, 20),
    ("/things?page=abc", 1, 20),
    ("/things?per_page=50", 1, 50),
    ("/things?per_page=7", 1, 20),    # not one of the options: the default
    ("/things?per_page=x", 1, 20),
])
def test_bad_or_unknown_values_fall_back(app, url, number, per_page):
    page = page_of(app, url, 45)
    assert (page.number, page.per_page) == (number, per_page)


def test_empty_list_has_one_empty_page(app):
    page = page_of(app, "/things", 0)
    assert (page.number, page.pages, page.items) == (1, 1, [])
    assert (page.start, page.end) == (0, 0)
    assert page.links() == [1]
    assert not page.has_prev and not page.has_next


@pytest.mark.parametrize("number, pages, links", [
    (1, 1, [1]),
    (1, 2, [1, 2]),
    (1, 12, [1, 2, None, 12]),
    (2, 4, [1, 2, 3, 4]),
    (3, 12, [1, 2, 3, 4, None, 12]),           # 2 touches page 1: no ellipsis
    (4, 12, [1, None, 3, 4, 5, None, 12]),
    (7, 12, [1, None, 6, 7, 8, None, 12]),
    (10, 12, [1, None, 9, 10, 11, 12]),        # 11 touches the last page
    (12, 12, [1, None, 11, 12]),
])
def test_links(app, number, pages, links):
    assert page_of(app, f"/things?page={number}&per_page=10", pages * 10).links() == links


def test_urls_keep_filters(app):
    with app.test_request_context("/things?q=egg&per_page=10&page=2"):
        page = paginate(range(45), 20, (10, 20, 50))
        assert page.url(3) == "/things?q=egg&per_page=10&page=3"
        assert page.url(1) == "/things?q=egg&per_page=10"
        assert page.kept_args == [("q", "egg")]
