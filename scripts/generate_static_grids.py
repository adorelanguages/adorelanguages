#!/usr/bin/env python3
"""
Pre-renders the post-card grid on catalog/section pages as real, static
<a href="/site/{slug}/"> links baked into the committed HTML, instead of
leaving the grid empty for crawlers that don't execute the page's JS.

Covers:
- links/site/all/index.html            -> every post on the site
- links/site/section/<key>/index.html  -> the 14 sections that use a flat
  "slugs" list in links/site/sections.json (NOT the 3 sections that filter
  by language/country - strany, idiomy, yazyki - those have their own,
  more involved generator; see the project notes).

For each covered page this script:
1. Rewrites the contents of <div class="grid" id="post-grid"> ... </div>
   with one <a class="card" data-bg="..."> per post, in posts.json order.
2. Replaces the page's old "fetch JSON, build cards from scratch" <script>
   block with one that instead re-shuffles the cards that are now already
   in the DOM (same color-respecting-shuffle algorithm, just reordering
   existing nodes instead of creating new ones from fetched data). Visible
   behavior for a visitor with JS enabled is unchanged.
- links/site/all/index.html additionally gets its <h1 id="title"> baked
  in with the live post count, since that no longer needs to come from JS.

Run automatically by .github/workflows/update-sitemap.yml whenever
links/site/posts.json or links/site/sections.json changes.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FLAT_SECTIONS = [
    "brendy", "osobyeslova", "etimologiya", "illyustraciiayu", "lingvistika",
    "igraslov", "zagadki", "toponimy", "knigi", "edanapitki", "rasteniya",
    "zhivotnye", "sport", "lingvoprosiki",
]

NEW_SCRIPT_BLOCK = """<script>
  const COLOR_ORDER = ['pink', 'lilac', 'blue', 'green'];
  const grid = document.getElementById('post-grid');
  const cards = Array.from(grid.children);
  const emptyMsg = document.getElementById('empty-msg');
  if (emptyMsg) emptyMsg.style.display = cards.length === 0 ? 'block' : 'none';

  const buckets = { pink: [], lilac: [], blue: [], green: [] };
  cards.forEach(c => buckets[c.dataset.bg].push(c));
  Object.values(buckets).forEach(arr => {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
  });
  const pointers = { pink: 0, lilac: 0, blue: 0, green: 0 };
  let colorIdx = 0;
  let remaining = cards.length;
  while (remaining > 0) {
    let placed = false;
    for (let attempt = 0; attempt < 4; attempt++) {
      const color = COLOR_ORDER[colorIdx % 4];
      colorIdx++;
      if (pointers[color] < buckets[color].length) {
        grid.appendChild(buckets[color][pointers[color]++]);
        remaining--;
        placed = true;
        break;
      }
    }
    if (!placed) break;
  }
</script>"""

OLD_SCRIPT_RE = re.compile(
    r"<script>\s*\n\s*const COLOR_ORDER.*?</script>", re.S
)
GRID_RE = re.compile(
    r'<div class="grid" id="post-grid">.*?</div>', re.S
)
TITLE_RE = re.compile(r'<h1 id="title">.*?</h1>', re.S)


def load_json(relpath):
    return json.loads((ROOT / relpath).read_text(encoding="utf-8"))


def card_html(post):
    slug = post["slug"]
    bg = post["bg"]
    alt = html.escape(post["title"], quote=True)
    return (
        f'<a class="card" data-bg="{bg}" href="/site/{slug}/">'
        f'<img src="/images/posts/{slug}.png" alt="{alt}" loading="lazy">'
        f"</a>"
    )


def render_grid(posts):
    cards = "".join(card_html(p) for p in posts)
    return f'<div class="grid" id="post-grid">{cards}</div>'


def apply_to_file(path, posts, title_html=None):
    text = path.read_text(encoding="utf-8")
    original = text

    text, n_grid = GRID_RE.subn(render_grid(posts), text, count=1)
    if n_grid != 1:
        raise RuntimeError(f"{path}: post-grid div not found/not unique")

    text, n_script = OLD_SCRIPT_RE.subn(NEW_SCRIPT_BLOCK, text, count=1)
    if n_script != 1:
        raise RuntimeError(f"{path}: COLOR_ORDER script block not found/not unique")

    if title_html is not None:
        text, n_title = TITLE_RE.subn(title_html, text, count=1)
        if n_title != 1:
            raise RuntimeError(f"{path}: <h1 id=\"title\"> not found/not unique")

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    posts = load_json("links/site/posts.json")
    sections = load_json("links/site/sections.json")
    by_slug = {p["slug"]: p for p in posts}

    changed = []

    # /links/site/all/ - every post, with a live count baked into the title
    all_path = ROOT / "links/site/all/index.html"
    title_html = f'<h1 id="title">Все посты на сайте ({len(posts)})</h1>'
    if apply_to_file(all_path, posts, title_html=title_html):
        changed.append(str(all_path.relative_to(ROOT)))

    # The 14 flat-slug sections
    for key in FLAT_SECTIONS:
        slugs = sections[key]["slugs"]
        section_posts = [by_slug[s] for s in slugs if s in by_slug]
        path = ROOT / f"links/site/section/{key}/index.html"
        if apply_to_file(path, section_posts):
            changed.append(str(path.relative_to(ROOT)))

    if changed:
        print("Updated:")
        for c in changed:
            print(f"  {c}")
    else:
        print("No changes.")


if __name__ == "__main__":
    main()
