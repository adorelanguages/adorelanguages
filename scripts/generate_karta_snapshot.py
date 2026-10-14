#!/usr/bin/env python3
"""
Fills golosovania/karta/index.html with a STATIC snapshot of the reader map's
country/city list and a short summary sentence, so that a search-engine
crawler (which does not run the page's JavaScript) sees real content instead
of two empty containers.

Why this exists: the live page always starts with an empty
<div id="country-accordion"></div> and an empty
<p id="country-summary-line"></p> — both are filled in by JavaScript only
after it fetches the current reader data from the Apps Script backend
(API_URL). A crawler that does not execute that JavaScript sees nothing
there, which is almost certainly why Google has flagged
golosovania/karta/ as "Insufficient content" in Search Console.

This script fetches the same data the page's own JS fetches
(?action=get_locations) and writes it into the HTML between two pairs of
HTML-comment markers:
  <!-- KARTA_SNAPSHOT:ACCORDION:START --> ... <!-- KARTA_SNAPSHOT:ACCORDION:END -->
  <!-- KARTA_SNAPSHOT:SUMMARY:START -->   ... <!-- KARTA_SNAPSHOT:SUMMARY:END -->

IMPORTANT — this only affects crawlers, not visitors: every real visitor's
browser runs the page's JavaScript, which always re-fetches live data and
overwrites both containers (renderCountryList() does
`container.innerHTML = ''` and rebuilds; updateSummaryLine() does
`el.innerHTML = ...`/`''`) before the visitor would notice the snapshot's
content. The snapshot only matters in the brief window before JS runs, and
to crawlers that never run it at all.

Mirrors the markup `renderCountryList()` builds in golosovania/karta/index.html
(same classes: country-row / name / row-right / count / chevron /
city-sublist / city-count) and the summary text `updateSummaryLine()` builds,
so the two must be kept in sync if that JS ever changes shape.

Grammar note: the summary sentence deliberately avoids phrases like "больше
всего в Германии, США и Испании" (which would need each country name
correctly declined into the prepositional case — fragile to generate from
the nominative-only COUNTRIES list) and avoids "N человек"/"M стран" as the
direct object of a sentence (which would need Russian numeral-noun
agreement, e.g. "1 страна" / "2 страны" / "5 стран"). Instead it uses the
same label-style "Label: <strong>N</strong>" pattern the page already uses
elsewhere ("Всего Обожателей Языков: N", "Список стран: N"), which needs no
agreement, plus a plain nominative list of top country names after a colon.

Safe by design: if the API is slow, unreachable, or returns something
unexpected, this script prints a warning and exits 0 WITHOUT touching the
file — exactly like scripts/ping_indexnow.py's soft-fail behaviour — so a
flaky response from the Apps Script backend never breaks the workflow run.

Run once daily by .github/workflows/update-karta-snapshot.yml (a scheduled,
not push-triggered, workflow — the map's reader data changes gradually, so a
push-triggered run on every commit would be wasted effort).
"""
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "golosovania" / "karta" / "index.html"
TIMEOUT_SECONDS = 20

ACCORDION_START = "<!-- KARTA_SNAPSHOT:ACCORDION:START -->"
ACCORDION_END = "<!-- KARTA_SNAPSHOT:ACCORDION:END -->"
SUMMARY_START = "<!-- KARTA_SNAPSHOT:SUMMARY:START -->"
SUMMARY_END = "<!-- KARTA_SNAPSHOT:SUMMARY:END -->"

# Allows overriding the API URL in tests without touching the real site file.
API_URL_OVERRIDE = None


def extract_api_url(html_text):
    if API_URL_OVERRIDE:
        return API_URL_OVERRIDE
    m = re.search(r"const API_URL = '([^']+)';", html_text)
    if not m:
        raise RuntimeError("could not find API_URL in golosovania/karta/index.html")
    return m.group(1)


def extract_id_to_name(html_text):
    m = re.search(r"const COUNTRIES = (\[.*?\]);", html_text)
    if not m:
        raise RuntimeError("could not find COUNTRIES array in golosovania/karta/index.html")
    countries = json.loads(m.group(1))
    return {c["id"]: c["ru"] for c in countries}


def fetch_countries_data(api_url):
    url = f"{api_url}?action=get_locations"
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("ok"):
        raise RuntimeError(f"API responded with ok != true: {data}")
    return data.get("countries", {}) or {}


def build_accordion_html(countries_data, id_to_name):
    """Mirrors renderCountryList() in golosovania/karta/index.html."""
    entries = sorted(
        countries_data.items(),
        key=lambda kv: id_to_name.get(kv[0], kv[0]),
    )

    if not entries:
        return '<p class="country-list-empty">Пока никто не отметился.</p>'

    parts = []
    for country_id, info in entries:
        name = id_to_name.get(country_id, country_id)
        count = info.get("count", 0)
        cities = info.get("cities", {}) or {}
        # Mirrors buildCityListItems(): sorted by city count, descending.
        city_items = sorted(cities.items(), key=lambda kv: -kv[1])
        li_html = "".join(
            f"<li><span>{html.escape(city_name)}</span>"
            f'<span class="city-count">{city_count}</span></li>'
            for city_name, city_count in city_items
        )
        parts.append(
            f'<div class="country-row" data-country-id="{html.escape(country_id)}">'
            f'<span class="name">{html.escape(name)}</span>'
            f'<span class="row-right"><span class="count">{count}</span>'
            f'<span class="chevron">›</span></span></div>'
            f'<div class="city-sublist"><ul>{li_html}</ul></div>'
        )
    return "".join(parts)


def build_summary_html(countries_data, id_to_name):
    """Mirrors updateSummaryLine() in golosovania/karta/index.html."""
    total_readers = sum(info.get("count", 0) for info in countries_data.values())
    country_count = len(countries_data)
    if not total_readers or not country_count:
        return ""

    summary = (
        f"Стран на карте: <strong>{country_count}</strong> "
        f"· Обожателей Языков: <strong>{total_readers}</strong>."
    )
    if country_count >= 2:
        top = sorted(
            countries_data.items(),
            key=lambda kv: (-kv[1].get("count", 0), id_to_name.get(kv[0], kv[0])),
        )[:3]
        top_names = [html.escape(id_to_name.get(cid, cid)) for cid, _ in top]
        summary += "<br>Больше всего участников: " + ", ".join(top_names) + "."
    return summary


def replace_between_markers(text, start_marker, end_marker, new_inner):
    pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
    replacement = start_marker + new_inner + end_marker
    new_text, n = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if n != 1:
        raise RuntimeError(
            f"expected exactly 1 occurrence of markers {start_marker} .. {end_marker}, found {n}"
        )
    return new_text


def main():
    original = TARGET.read_text(encoding="utf-8")

    try:
        api_url = extract_api_url(original)
        id_to_name = extract_id_to_name(original)
        countries_data = fetch_countries_data(api_url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as e:
        print(f"generate_karta_snapshot: could not refresh data, leaving file unchanged ({e})")
        sys.exit(0)

    accordion_html = build_accordion_html(countries_data, id_to_name)
    summary_html = build_summary_html(countries_data, id_to_name)

    updated = replace_between_markers(original, ACCORDION_START, ACCORDION_END, accordion_html)
    updated = replace_between_markers(updated, SUMMARY_START, SUMMARY_END, summary_html)

    if updated == original:
        print("No changes.")
        return

    TARGET.write_text(updated, encoding="utf-8")
    total_readers = sum(info.get("count", 0) for info in countries_data.values())
    print(
        f"Updated {TARGET.relative_to(ROOT)}: "
        f"{len(countries_data)} countries, {total_readers} total readers."
    )


if __name__ == "__main__":
    main()
