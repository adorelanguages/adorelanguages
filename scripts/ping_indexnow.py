#!/usr/bin/env python3
"""
Notifies Yandex (via the IndexNow protocol) about NEW post URLs only.

Reads the same source of truth as generate_sitemap.py:
- links/site/posts.json  -> /site/{slug}/

Keeps a small state file (scripts/.indexnow_state.json) listing every
slug that has already been successfully submitted to IndexNow. On each
run it computes the diff against the current posts.json, submits only
the slugs that are new, and — only if the submission succeeds — updates
the state file so those slugs aren't resubmitted next time.

If the request fails, the state file is left untouched so the same
slugs are retried on the next run instead of being silently dropped.

This keeps requests small regardless of how many posts the site has
accumulated, and stays well under IndexNow's 10,000-URLs-per-request
limit even at large scale.

Run automatically by .github/workflows/update-sitemap.yml on every
push to main that changes links/site/posts.json or links/fb/posts.json.
"""
import json
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "adorelanguages.com"
BASE = f"https://{HOST}"
KEY = "aa2827456c5d824183a4db57d6fa0b4c"
KEY_LOCATION = f"{BASE}/{KEY}.txt"
ENDPOINT = "https://yandex.com/indexnow"
STATE_FILE = ROOT / "scripts" / ".indexnow_state.json"


def load_slugs(posts_json_path):
    data = json.loads(Path(posts_json_path).read_text(encoding="utf-8"))
    return [post["slug"] for post in data]


def load_state():
    if not STATE_FILE.exists():
        return set()
    try:
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValueError):
        return set()


def save_state(slugs):
    STATE_FILE.write_text(
        json.dumps(sorted(slugs), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
            return True
    except urllib.error.HTTPError as e:
        print(f"IndexNow ping failed: HTTP {e.code} {e.reason}")
        return False
    except Exception as e:
        print(f"IndexNow ping failed: {e}")
        return False


if __name__ == "__main__":
    current_slugs = set(load_slugs(ROOT / "links/site/posts.json"))
    already_submitted = load_state()

    new_slugs = current_slugs - already_submitted

    if not new_slugs:
        print("No new posts since last IndexNow submission. Nothing to do.")
    else:
        new_urls = [f"{BASE}/site/{slug}/" for slug in sorted(new_slugs)]
        print(f"Submitting {len(new_urls)} new URL(s) to IndexNow...")
        success = ping_indexnow(new_urls)

        if success:
            save_state(current_slugs)
            print(f"State updated: {len(current_slugs)} slugs now marked as submitted.")
        else:
            print("Submission failed — state left unchanged, will retry these slugs next run.")
