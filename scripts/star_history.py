#!/usr/bin/env python3
"""Build an in-repo star-history SVG from the GitHub stargazers API.

Uses only the standard library. Intended to run in GitHub Actions with
``GITHUB_TOKEN`` (the repo token can read this repo's stars after GitHub's
2026 stargazers restriction). No star-history.com or other third party.

Usage (from repo root)::

    GITHUB_TOKEN=$(gh auth token) python scripts/star_history.py
    python scripts/star_history.py --output docs/star-history.svg
"""

from __future__ import print_function

import argparse
import datetime
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUTPUT = os.path.join(REPO_ROOT, "docs", "star-history.svg")
DEFAULT_OUTPUT_YTD = os.path.join(REPO_ROOT, "docs", "star-history-ytd.svg")
USER_AGENT = "rebiber-star-history (+https://github.com/yuchenlin/rebiber)"
API_VERSION = "2022-11-28"
LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


def parse_starred_at(value):
    """Parse a GitHub ``starred_at`` timestamp into a UTC date."""
    if not value:
        raise ValueError("empty starred_at")
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    when = datetime.datetime.fromisoformat(text)
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return when.astimezone(datetime.timezone.utc).date()


def cumulative_daily(starred_at_values):
    """Return sorted ``(date, cumulative_count)`` pairs, one per day with a star."""
    counts = {}
    for raw in starred_at_values:
        day = parse_starred_at(raw)
        counts[day] = counts.get(day, 0) + 1
    if not counts:
        return []
    days = sorted(counts)
    series = []
    total = 0
    for day in days:
        total += counts[day]
        series.append((day, total))
    return series


def ytd_series(series, year, today=None):
    """Zoom a cumulative series to calendar ``year`` (absolute totals).

    Starts at 1 Jan (carrying forward the prior-year total) and extends to
    ``today`` so a quiet end of year still fills the axis. Returns
    ``(points, gained_this_year)``.
    """
    if today is None:
        today = datetime.date.today()
    start = datetime.date(int(year), 1, 1)
    if today < start:
        return [], 0
    baseline = 0
    year_points = []
    for day, count in series:
        if day < start:
            baseline = count
        elif day <= today:
            year_points.append((day, count))
    points = []
    if not year_points or year_points[0][0] > start:
        points.append((start, baseline))
    points.extend(year_points)
    if points[-1][0] < today:
        points.append((today, points[-1][1]))
    gained = points[-1][1] - baseline
    return points, gained


def _x_tick_dates(first_day, last_day):
    """Year ticks for multi-year spans; month ticks for a YTD-sized window."""
    span_days = max((last_day - first_day).days, 1)
    ticks = []
    if span_days > 400:
        year = first_day.year
        while year <= last_day.year:
            mark = datetime.date(year, 1, 1)
            if mark < first_day:
                mark = first_day
            ticks.append(mark)
            year += 1
        label = lambda day: day.strftime("%Y")
    else:
        year, month = first_day.year, first_day.month
        ticks.append(first_day)
        while True:
            month += 1
            if month > 12:
                month = 1
                year += 1
            mark = datetime.date(year, month, 1)
            if mark > last_day:
                break
            ticks.append(mark)
        label = lambda day: (
            day.strftime("%b") if day.month != 1 else day.strftime("%b %Y")
        )
    if ticks[-1] != last_day and (last_day - ticks[-1]).days > 20:
        ticks.append(last_day)
    return ticks, label


def downsample(series, max_points=400):
    """Keep first/last and evenly spaced points so the SVG path stays small."""
    if len(series) <= max_points:
        return list(series)
    last_index = len(series) - 1
    picked = {0, last_index}
    for step in range(1, max_points - 1):
        index = int(round(step * last_index / float(max_points - 1)))
        picked.add(index)
    return [series[i] for i in sorted(picked)]


def _nice_ticks(lo, hi, target=5):
    """Return roughly ``target`` integer ticks covering ``[lo, hi]``."""
    lo = int(lo)
    hi = max(int(hi), lo + 1)
    span = hi - lo
    raw = max(span / float(target), 1.0)
    magnitude = 10 ** int(math.floor(math.log10(raw)))
    for step in (1, 2, 5, 10):
        candidate = step * magnitude
        if raw <= candidate:
            break
    else:
        candidate = 10 * magnitude
    start = (lo // candidate) * candidate
    ticks = []
    value = start
    while value <= hi + candidate * 0.01:
        ticks.append(int(value))
        value += candidate
    if ticks[-1] < hi:
        ticks.append(int(ticks[-1] + candidate))
    return ticks


def render_svg(
    series,
    repo,
    generated_on,
    width=880,
    height=420,
    title=None,
    subtitle=None,
    y_min=0,
):
    """Render a simple line chart. ``series`` is ``[(date, count), ...]``."""
    if not series:
        raise ValueError("no star events to plot")
    pad_l, pad_r, pad_t, pad_b = 64, 24, 48, 56
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    first_day, first_count = series[0]
    last_day, last_count = series[-1]
    span_days = max((last_day - first_day).days, 1)
    y_lo = int(y_min)
    y_max = max(last_count, first_count, y_lo + 1)
    y_ticks = _nice_ticks(y_lo, y_max, target=5)
    chart_top = y_ticks[-1] if y_ticks else y_max
    chart_bot = y_ticks[0] if y_ticks else y_lo
    if chart_top <= chart_bot:
        chart_top = chart_bot + 1

    def x_of(day):
        return pad_l + plot_w * ((day - first_day).days / float(span_days))

    def y_of(count):
        return pad_t + plot_h * (
            1.0 - ((count - chart_bot) / float(chart_top - chart_bot))
        )

    points = downsample(series)
    coords = [(x_of(day), y_of(count)) for day, count in points]
    line = " ".join("%.1f,%.1f" % (x, y) for x, y in coords)
    area = "M %.1f,%.1f L %s L %.1f,%.1f Z" % (
        coords[0][0],
        pad_t + plot_h,
        " ".join("%.1f,%.1f" % (x, y) for x, y in coords),
        coords[-1][0],
        pad_t + plot_h,
    )

    x_ticks, x_label = _x_tick_dates(first_day, last_day)

    grid = []
    labels = []
    for tick in y_ticks:
        y = y_of(tick)
        grid.append(
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
            'stroke="#e5e7eb" stroke-width="1"/>' % (pad_l, y, width - pad_r, y)
        )
        labels.append(
            '<text x="%.1f" y="%.1f" text-anchor="end" font-size="12" '
            'fill="#6b7280" font-family="ui-sans-serif, system-ui, sans-serif">'
            "%s</text>" % (pad_l - 8, y + 4, "{:,}".format(tick))
        )
    for mark in x_ticks:
        x = x_of(mark)
        grid.append(
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
            'stroke="#f3f4f6" stroke-width="1"/>'
            % (x, pad_t, x, pad_t + plot_h)
        )
        labels.append(
            '<text x="%.1f" y="%.1f" text-anchor="middle" font-size="12" '
            'fill="#6b7280" font-family="ui-sans-serif, system-ui, sans-serif">'
            "%s</text>" % (x, pad_t + plot_h + 20, x_label(mark))
        )

    if title is None:
        title = "%s star history" % repo
    if subtitle is None:
        subtitle = "{:,} stars · updated {}".format(
            last_count, generated_on.isoformat()
        )
    svg = """\
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="{title_x}" y="24" font-size="16" font-weight="600" fill="#111827" font-family="ui-sans-serif, system-ui, sans-serif">{title}</text>
  <text x="{title_x}" y="40" font-size="12" fill="#6b7280" font-family="ui-sans-serif, system-ui, sans-serif">{subtitle}</text>
  {grid}
  <path d="{area}" fill="#dbeafe"/>
  <polyline fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" points="{line}"/>
  {labels}
  <line x1="{plot_l}" y1="{plot_b}" x2="{plot_r}" y2="{plot_b}" stroke="#9ca3af" stroke-width="1"/>
  <line x1="{plot_l}" y1="{plot_t}" x2="{plot_l}" y2="{plot_b}" stroke="#9ca3af" stroke-width="1"/>
</svg>
""".format(
        width=width,
        height=height,
        title=title,
        subtitle=subtitle,
        title_x=pad_l,
        grid="\n  ".join(grid),
        area=area,
        line=line,
        labels="\n  ".join(labels),
        plot_l=pad_l,
        plot_r=width - pad_r,
        plot_t=pad_t,
        plot_b=pad_t + plot_h,
    )
    return svg


def _next_link(link_header):
    if not link_header:
        return None
    match = LINK_NEXT_RE.search(link_header)
    if not match:
        return None
    return match.group(1)


def fetch_starred_at(owner, repo, token, opener=None, per_page=100):
    """Return all ``starred_at`` strings. ``opener`` is injectable for tests."""
    if not token:
        raise RuntimeError("GITHUB_TOKEN / --token is required")
    url = (
        "https://api.github.com/repos/%s/%s/stargazers?per_page=%s"
        % (owner, repo, int(per_page))
    )
    headers = {
        "Accept": "application/vnd.github.star+json",
        "Authorization": "Bearer %s" % token,
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": API_VERSION,
    }
    open_fn = opener or urllib.request.urlopen
    starred = []
    while url:
        request = urllib.request.Request(url, headers=headers)
        try:
            response = open_fn(request)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(
                "GitHub stargazers API failed (%s): %s" % (exc.code, detail)
            )
        try:
            payload = response.read()
            link = ""
            if hasattr(response, "headers") and response.headers is not None:
                link = response.headers.get("Link") or response.headers.get("link") or ""
        finally:
            if hasattr(response, "close"):
                response.close()
        page = json.loads(payload.decode("utf-8"))
        if not isinstance(page, list):
            raise RuntimeError("unexpected stargazers payload: %r" % type(page))
        for row in page:
            if isinstance(row, dict) and row.get("starred_at"):
                starred.append(row["starred_at"])
        url = _next_link(link)
    return starred


def build_parser():
    parser = argparse.ArgumentParser(description="Write a local star-history SVG.")
    parser.add_argument("--owner", default="yuchenlin")
    parser.add_argument("--repo", default="rebiber")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--output-ytd",
        default=DEFAULT_OUTPUT_YTD,
        help="Year-to-date chart path (empty string to skip).",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "",
        help="GitHub token (default: GITHUB_TOKEN or GH_TOKEN).",
    )
    return parser


def _write_svg(path, svg):
    out_dir = os.path.dirname(os.path.abspath(path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf8") as handle:
        handle.write(svg)


def main(argv=None):
    args = build_parser().parse_args(argv)
    starred = fetch_starred_at(args.owner, args.repo, args.token)
    series = cumulative_daily(starred)
    if not series:
        print("No stargazer timestamps returned.", file=sys.stderr)
        return 1
    today = datetime.date.today()
    repo = "%s/%s" % (args.owner, args.repo)
    svg = render_svg(series, repo=repo, generated_on=today)
    _write_svg(args.output, svg)
    print(
        "Wrote %s (%s stars, %s events)"
        % (args.output, series[-1][1], len(starred))
    )
    if args.output_ytd:
        ytd_points, gained = ytd_series(series, today.year, today=today)
        if not ytd_points:
            print("No YTD points to plot.", file=sys.stderr)
            return 1
        ytd_svg = render_svg(
            ytd_points,
            repo=repo,
            generated_on=today,
            title="%s stars (%s YTD)" % (repo, today.year),
            subtitle="{:,} stars · {:+,} in {} · updated {}".format(
                ytd_points[-1][1], gained, today.year, today.isoformat()
            ),
            y_min=ytd_points[0][1],
        )
        _write_svg(args.output_ytd, ytd_svg)
        print(
            "Wrote %s (%s YTD, %+d this year)"
            % (args.output_ytd, today.year, gained)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
