"""Long lists split into pages: ?page= and ?per_page= from the URL, and which page links to show."""

from flask import request, url_for


def _whole_number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class Page:
    """One page of `items`. Out-of-range or unknown ?page= / ?per_page= fall back to something valid."""

    def __init__(self, items, page, per_page, default_per_page, per_page_options):
        self.per_page_options = per_page_options
        self.per_page = per_page if per_page in per_page_options else default_per_page
        self.total = len(items)
        self.pages = max(1, -(-self.total // self.per_page))
        self.number = min(max(page or 1, 1), self.pages)
        offset = (self.number - 1) * self.per_page
        self.items = items[offset:offset + self.per_page]
        self.start = offset + 1 if self.items else 0
        self.end = offset + len(self.items)

    @property
    def has_prev(self):
        return self.number > 1

    @property
    def has_next(self):
        return self.number < self.pages

    def links(self):
        """Page numbers to show, with None for an ellipsis: the first and last page, and the current
        one with its neighbours. 7 of 12 -> [1, None, 6, 7, 8, None, 12]; 2 of 4 -> [1, 2, 3, 4]."""
        shown = sorted({1, self.pages} | {n for n in range(self.number - 1, self.number + 2) if 1 <= n <= self.pages})
        links = []
        for n in shown:
            if links and n > links[-1] + 1:
                links.append(None)
            links.append(n)
        return links

    @property
    def kept_args(self):
        """The URL's search and filters, as (name, value) pairs for the per-page form's hidden inputs."""
        return [(name, value) for name, value in request.args.items(multi=True) if name not in ("page", "per_page")]

    def url(self, number):
        """This page's URL (search and filters kept) with another page number."""
        args = request.args.to_dict()
        args.pop("page", None)
        if number > 1:
            args["page"] = number
        return url_for(request.endpoint, **request.view_args, **args)


def paginate(items, default_per_page, per_page_options):
    """The page of `items` asked for in the URL."""
    return Page(list(items), _whole_number(request.args.get("page")), _whole_number(request.args.get("per_page")),
                default_per_page, per_page_options)
