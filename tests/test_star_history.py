import datetime
import importlib.util
import sys
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "star_history.py"
_SPEC = importlib.util.spec_from_file_location("rebiber_star_history", _SCRIPT)
star_history = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("rebiber_star_history", star_history)
_SPEC.loader.exec_module(star_history)


class _FakeResponse(object):
    def __init__(self, body, link=""):
        self._body = body.encode("utf-8")
        self.headers = {"Link": link}

    def read(self):
        return self._body

    def close(self):
        return None


def test_cumulative_daily_counts_and_order():
    series = star_history.cumulative_daily(
        [
            "2021-01-25T23:22:35Z",
            "2021-01-25T23:59:00Z",
            "2022-06-01T00:00:00Z",
        ]
    )
    assert [day.isoformat() for day, _count in series] == ["2021-01-25", "2022-06-01"]
    assert [count for _day, count in series] == [2, 3]


def test_downsample_keeps_ends():
    start = datetime.date(2020, 1, 1)
    series = [(start + datetime.timedelta(days=i), i + 1) for i in range(50)]
    out = star_history.downsample(series, max_points=5)
    assert out[0] == series[0]
    assert out[-1] == series[-1]
    assert len(out) <= 5


def test_ytd_series_carries_baseline_and_counts_gain():
    series = [
        (datetime.date(2025, 12, 31), 100),
        (datetime.date(2026, 1, 2), 103),
        (datetime.date(2026, 3, 1), 110),
    ]
    points, gained = star_history.ytd_series(
        series, 2026, today=datetime.date(2026, 8, 10)
    )
    assert points[0] == (datetime.date(2026, 1, 1), 100)
    assert (datetime.date(2026, 1, 2), 103) in points
    assert points[-1] == (datetime.date(2026, 8, 10), 110)
    assert gained == 10


def test_ytd_series_empty_before_year_starts_at_zero():
    series = [(datetime.date(2026, 2, 1), 4)]
    points, gained = star_history.ytd_series(
        series, 2026, today=datetime.date(2026, 2, 1)
    )
    assert points[0] == (datetime.date(2026, 1, 1), 0)
    assert points[-1] == (datetime.date(2026, 2, 1), 4)
    assert gained == 4


def test_x_ticks_use_months_for_short_spans():
    ticks, label = star_history._x_tick_dates(
        datetime.date(2026, 1, 1), datetime.date(2026, 8, 10)
    )
    assert ticks[0] == datetime.date(2026, 1, 1)
    assert datetime.date(2026, 6, 1) in ticks
    assert label(datetime.date(2026, 6, 1)) == "Jun"


def test_render_svg_contains_title_and_total():
    series = [
        (datetime.date(2021, 1, 25), 1),
        (datetime.date(2022, 6, 1), 10),
        (datetime.date(2026, 8, 10), 42),
    ]
    svg = star_history.render_svg(
        series, repo="yuchenlin/rebiber", generated_on=datetime.date(2026, 8, 10)
    )
    assert svg.startswith("<svg")
    assert "yuchenlin/rebiber star history" in svg
    assert "42 stars" in svg
    assert "2026-08-10" in svg
    assert "polyline" in svg


def test_fetch_follows_next_link_and_collects_starred_at():
    pages = {
        "https://api.github.com/repos/yuchenlin/rebiber/stargazers?per_page=2": _FakeResponse(
            '[{"starred_at":"2021-01-25T23:22:35Z","user":{"login":"a"}}]',
            link='<https://api.github.com/repos/yuchenlin/rebiber/stargazers?page=2>; rel="next"',
        ),
        "https://api.github.com/repos/yuchenlin/rebiber/stargazers?page=2": _FakeResponse(
            '[{"starred_at":"2022-06-01T00:00:00Z","user":{"login":"b"}}]'
        ),
    }

    def opener(request):
        return pages[request.full_url]

    starred = star_history.fetch_starred_at(
        "yuchenlin", "rebiber", token="test-token", opener=opener, per_page=2
    )
    assert starred == ["2021-01-25T23:22:35Z", "2022-06-01T00:00:00Z"]
