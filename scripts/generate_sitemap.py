#!/usr/bin/env python3
"""
Regenerates sitemap.xml from the site's source of truth:
- links/site/posts.json          -> /site/{slug}/
- links/site/section/<key>/      -> /links/site/section/{key}/  (auto-discovered)
- golosovania/<slug>/            -> /golosovania/{slug}/         (auto-discovered)
plus a fixed list of static/catalog pages.

Run automatically by .github/workflows/update-sitemap.yml on every push to main
that touches links/site/posts.json, links/fb/posts.json, links/site/section/**,
golosovania/**, sozdateli/**, or this script.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://adorelanguages.com"

STATIC_PAGES = [
    "/",
    "/links/site/",
    "/links/site/all/",
    "/links/fb/",
    "/links/fb/all/",
    "/tags/",
    "/golosovania/",
    "/sozdateli/",
]


def load_slugs(posts_json_path):
    data = json.loads(Path(posts_json_path).read_text(encoding="utf-8"))
    return [post["slug"] for post in data]


def discover_subpages(dir_path, url_prefix):
    """Any immediate subdirectory of dir_path that has an index.html becomes a page."""
    pages = []
    if not dir_path.is_dir():
        return pages
    for child in sorted(dir_path.iterdir()):
        if child.is_dir() and (child / "index.html").exists():
            pages.append(f"{url_prefix}{child.name}/")
    return pages


def build_sitemap():
    site_slugs = load_slugs(ROOT / "links/site/posts.json")
    section_pages = discover_subpages(ROOT / "links/site/section", "/links/site/section/")
    golosovania_pages = discover_subpages(ROOT / "golosovania", "/golosovania/")

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        "",
        "  <!-- Homepage -->",
        f"  <url>\n    <loc>{BASE}/</loc>\n  </url>",
        "",
        "  <!-- Catalog pages -->",
    ]
    for page in STATIC_PAGES[1:]:
        lines.append(f"  <url>\n    <loc>{BASE}{page}</loc>\n  </url>")

    lines += ["", "  <!-- Section pages -->"]
    for page in section_pages:
        lines.append(f"  <url>\n    <loc>{BASE}{page}</loc>\n  </url>")

    lines += ["", "  <!-- Golosovania pages -->"]
    for page in golosovania_pages:
        lines.append(f"  <url>\n    <loc>{BASE}{page}</loc>\n  </url>")

    lines += ["", "  <!-- Site posts -->"]
    for slug in site_slugs:
        lines.append(f"  <url>\n    <loc>{BASE}/site/{slug}/</loc>\n  </url>")

    lines += ["", "</urlset>", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    sitemap = build_sitemap()
    out_path = ROOT / "sitemap.xml"
    out_path.write_text(sitemap, encoding="utf-8")
    print(f"Wrote {out_path}")
