#!/usr/bin/env python3
"""
Notifies Yandex (via the IndexNow protocol) about URLs that changed in the
latest push. Submitting to Yandex's IndexNow endpoint shares the URL with
every other IndexNow-participating search engine (Bing, Naver, Seznam.cz,
Amazon, Yep, etc.) automatically — see https://www.indexnow.org/faq.

Two kinds of URLs are submitted:

1. NEW post pages (/site/{slug}/), found by diffing links/site/posts.json
   against a small state file (scripts/.indexnow_state.json) listing every
   slug already submitted. Only slugs not yet in the state file are sent,
   and — only if the submission succeeds — the state file is updated so
   they aren't resubmitted next time.

2. CHANGED section pages (/links/site/section/{key}/), found by diffing the
   git commit range of the push (BEFORE_SHA..AFTER_SHA, passed in via
   environment variables by the workflow) for any modified
   links/site/section/<key>/index.html file. These are submitted every time
   they change — no state tracking needed, since re-submitting an unchanged
   URL to IndexNow is harmless, and each push naturally only picks up
   section files touched by that push.

If the request fails, the post-slug state file is left untouched so the
same slugs are retried on the next run instead of being silently dropped.
Changed-section URLs are NOT retried on the next run if a submission fails
(the git diff range moves on) — this is a minor, accepted gap; a manual
IndexNow ping (see CONTRIBUTING.md) always covers it.

This keeps requests small regardless of how many posts/sections the site
has accumulated, and stays well under IndexNow's 10,000-URLs-per-request
limit even at large scale.

Run automatically by .github/workflows/update-sitemap.yml on every push to
main that changes links/site/posts.json, links/fb/posts.json, or any file
under links/site/section/.
"""
import json
import os
import re
import subprocess
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

# Matches e.g. "links/site/section/etimologiya/index.html" -> "etimologiya"
SECTION_PAGE_RE = re.compile(r"^links/site/section/([^/]+)/index\.html$")

# Git uses this all-zero SHA as "before" for the first push to a new branch —
# there's nothing to diff against in that case.
NULL_SHA = "0000000000000000000000000000000000000000"


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


def find_changed_section_urls():
    """Diff BEFORE_SHA..AFTER_SHA (set by the workflow from the push event)
    for changed links/site/section/<key>/index.html files, and return their
    public URLs. Returns [] if the SHAs aren't set/usable (e.g. a manual
    workflow_dispatch run, or the first push to a new branch)."""
    before = os.environ.get("BEFORE_SHA", "")
    after = os.environ.get("AFTER_SHA", "")
    if not before or not after or before == NULL_SHA:
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", before, after],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"git diff failed, skipping changed-section detection: {e}")
        return []

    urls = []
    for path in result.stdout.splitlines():
        m = SECTION_PAGE_RE.match(path)
        if m:
            urls.append(f"{BASE}/links/site/section/{m.group(1)}/")
    return urls


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
    new_post_urls = [f"{BASE}/site/{slug}/" for slug in sorted(new_slugs)]

    changed_section_urls = find_changed_section_urls()

    all_urls = new_post_urls + changed_section_urls

    if not all_urls:
        print("Nothing new to submit to IndexNow.")
    else:
        print(
            f"Submitting {len(all_urls)} URL(s) to IndexNow "
            f"({len(new_post_urls)} new post(s), "
            f"{len(changed_section_urls)} changed section page(s))..."
        )
        success = ping_indexnow(all_urls)

        if success:
            if new_slugs:
                save_state(current_slugs)
                print(f"State updated: {len(current_slugs)} slugs now marked as submitted.")
        else:
            print("Submission failed — post-slug state left unchanged, will retry those next run.")
