#!/usr/bin/env python3
"""
Notifies Yandex (via the IndexNow protocol) about all current post URLs.

Reads the same source of truth as generate_sitemap.py:
- links/site/posts.json  -> /site/{slug}/
- links/fb/posts.json    -> /fb/{slug}/

Submits the full URL list in a single bulk POST request to Yandex's
IndexNow endpoint. Re-submitting unchanged URLs is harmless, so this
runs on every push that touches posts.json rather than trying to
diff which slugs are new.

Run automatically by .github/workflows/update-sitemap.yml on every
push to main that changes links/site/posts.json or links/fb/posts.json.
"""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "adorelanguages.com"
BASE = f"https://{HOST}"
KEY = "aa2827456c5d824183a4db57d6fa0b4c"
KEY_LOCATION = f"{BASE}/{KEY}.txt"
ENDPOINT = "https://yandex.com/indexnow"


def load_slugs(posts_json_path):
    data = json.loads(Path(posts_json_path).read_text(encoding="utf-8"))
    return [post["slug"] for post in data]


def build_url_list():
    site_slugs = load_slugs(ROOT / "links/site/posts.json")
    return [f"{BASE}/site/{slug}/" for slug in site_slugs]


def ping_indexnow(urls):
    payload = json.dumps({
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }).encode("utf-8")

    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"IndexNow ping: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        # IndexNow returns 200/202 on success; log but don't fail the workflow
        print(f"IndexNow ping failed: HTTP {e.code} {e.reason}")
    except Exception as e:
        print(f"IndexNow ping failed: {e}")


if __name__ == "__main__":
    url_list = build_url_list()
    print(f"Submitting {len(url_list)} URLs to IndexNow...")
    ping_indexnow(url_list)
