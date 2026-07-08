#!/usr/bin/env python3
"""
Regenerates sitemap.xml from the site's source of truth:
- links/site/posts.json  -> /site/{slug}/
- links/fb/posts.json    -> /fb/{slug}/
plus a fixed list of static pages.

Run automatically by .github/workflows/update-sitemap.yml on every push to main.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://www.adorelanguages.com"

STATIC_PAGES = [
    "/",
    "/links/site/",
    "/links/fb/",
    "/tags/",
]


def load_slugs(posts_json_path):
    data = json.loads(Path(posts_json_path).read_text(encoding="utf-8"))
    return [post["slug"] for post in data]


def build_sitemap():
    site_slugs = load_slugs(ROOT / "links/site/posts.json")
    fb_slugs = load_slugs(ROOT / "links/fb/posts.json")

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

    lines += ["", "  <!-- Site posts -->"]
    for slug in site_slugs:
        lines.append(f"  <url>\n    <loc>{BASE}/site/{slug}/</loc>\n  </url>")

    lines += ["", "  <!-- Facebook redirect pages -->"]
    for slug in fb_slugs:
        lines.append(f"  <url>\n    <loc>{BASE}/fb/{slug}/</loc>\n  </url>")

    lines += ["", "</urlset>", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    sitemap = build_sitemap()
    out_path = ROOT / "sitemap.xml"
    out_path.write_text(sitemap, encoding="utf-8")
    print(f"Wrote {out_path}")
