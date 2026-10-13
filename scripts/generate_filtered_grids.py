#!/usr/bin/env python3
"""
Pre-renders the post-card grid on the three *filtered* catalog pages — the
ones where sections.json groups posts by country/language instead of a flat
"slugs" list — as real, static <a href="/site/{slug}/"> links baked into the
committed HTML, same goal as generate_static_grids.py but for a different
data shape.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REEL_SECTIONS = ["idiomy", "yazyki", "strany"]

GRID_RE = re.compile(r'<div class="grid" id="post-grid">.*?</div>', re.S)

OLD_SCRIPT_RE = re.compile(r"<script>\s*\n\s*const COLOR_ORDER.*?</script>", re.S)

SHUFFLE_JS = """<script>
  const COLOR_ORDER = ['pink', 'lilac', 'blue', 'green'];

  function colorRespectingShuffle(cards) {
    const buckets = { pink: [], lilac: [], blue: [], green: [] };
    cards.forEach(c => buckets[c.dataset.bg].push(c));
    Object.values(buckets).forEach(arr => {
      for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
      }
    });
    const pointers = { pink: 0, lilac: 0, blue: 0, green: 0 };
    const result = [];
    let colorIdx = 0;
    let remaining = cards.length;
    while (remaining > 0) {
      let placed = false;
      for (let attempt = 0; attempt < 4; attempt++) {
        const color = COLOR_ORDER[colorIdx % 4];
        colorIdx++;
        if (pointers[color] < buckets[color].length) {
          result.push(buckets[color][pointers[color]++]);
          remaining--;
          placed = true;
          break;
        }
      }
      if (!placed) break;
    }
    return result;
  }

  const grid = document.getElementById('post-grid');
  const emptyMsg = document.getElementById('empty-msg');
  const ALL_CARDS = Array.from(grid.children);

  // Reverse index built from the data-langs baked into each card by
  // generate_filtered_grids.py — replaces the old fetch('sections.json').
  const LANG_TO_CARDS = {};
  ALL_CARDS.forEach(card => {
    (card.dataset.langs || '').split('|').filter(Boolean).forEach(lang => {
      (LANG_TO_CARDS[lang] = LANG_TO_CARDS[lang] || []).push(card);
    });
  });
  const LANG_NAMES = Object.keys(LANG_TO_CARDS).sort((a, b) => a.localeCompare(b, 'ru'));
"""

# --- idiomy / yazyki / strany: reel + search widget ------------------------

REEL_SCRIPT_BODY = """
  function renderGrid(lang, cardsOverride) {{
    const cards = cardsOverride !== undefined
      ? cardsOverride
      : ((lang && LANG_TO_CARDS[lang]) ? LANG_TO_CARDS[lang] : ALL_CARDS);

{title_update}

    emptyMsg.style.display = cards.length === 0 ? 'block' : 'none';

    const ordered = colorRespectingShuffle(cards);
    const shown = new Set(ordered);
    ALL_CARDS.forEach(c => {{ c.style.display = shown.has(c) ? '' : 'none'; }});
    ordered.forEach(c => grid.appendChild(c));
  }}

  const reel = document.getElementById('reel');
  const searchInput = document.getElementById('lang-search');
  const arrowUp = document.querySelector('.reel-arrow.up');
  const arrowDown = document.querySelector('.reel-arrow.down');
  const ITEM_HEIGHT = 44;
  let reelItems = [];
  let suppressAutoSelect = false;

  arrowUp.addEventListener('click', () => {{
    reel.scrollBy({{ top: -ITEM_HEIGHT, behavior: 'smooth' }});
  }});
  arrowDown.addEventListener('click', () => {{
    reel.scrollBy({{ top: ITEM_HEIGHT, behavior: 'smooth' }});
  }});

{display_name_fn}

  function buildReel(langNames) {{
    reel.innerHTML = '';
    reelItems = [];

    langNames.forEach(lang => {{
      const div = document.createElement('div');
      div.className = 'reel-item';
      div.textContent = displayName(lang);
      div.dataset.lang = lang;
      reel.appendChild(div);
      reelItems.push(div);
    }});

    reelItems.forEach(item => {{
      item.addEventListener('click', () => {{
        item.scrollIntoView({{ block: 'center', behavior: 'smooth' }});
        selectLang(item.dataset.lang, true);
      }});
    }});
  }}

  function markActive(activeItem) {{
    reelItems.forEach(item => item.classList.remove('active'));
    if (activeItem) activeItem.classList.add('active');
  }}

  function selectLang(lang, updateHistory) {{
    renderGrid(lang);
    if (updateHistory) {{
      const url = new URL(location.href);
      url.searchParams.set('lang', lang);
      history.pushState({{}}, '', url);
    }}
    const activeItem = reelItems.find(item => item.dataset.lang === lang);
    markActive(activeItem);
  }}

  function centeredItem() {{
    const reelRect = reel.getBoundingClientRect();
    const centerY = reelRect.top + reelRect.height / 2;
    let closest = null;
    let minDist = Infinity;
    reelItems.forEach(item => {{
      if (item.style.display === 'none') return;
      const r = item.getBoundingClientRect();
      const itemCenter = r.top + r.height / 2;
      const dist = Math.abs(itemCenter - centerY);
      if (dist < minDist) {{ minDist = dist; closest = item; }}
    }});
    return closest;
  }}

  let scrollEndTimer;
  reel.addEventListener('scroll', () => {{
    if (suppressAutoSelect) return;
    // While the search box has text, the search input alone drives selection.
    // A smooth-scroll animation kicked off by an earlier keystroke (e.g. a
    // scrollIntoView toward a match several items away) can still be
    // settling well after suppressAutoSelect's timeout has lifted and the
    // user has kept typing — without this guard, this handler would then
    // re-select that stale item and silently undo whatever the search logic
    // has since decided (including a correct "no matches" empty state).
    if (searchInput.value.trim()) return;
    const closest = centeredItem();
    markActive(closest);
    clearTimeout(scrollEndTimer);
    scrollEndTimer = setTimeout(() => {{
      if (closest) selectLang(closest.dataset.lang, true);
    }}, 180);
  }});

  searchInput.addEventListener('input', () => {{
    const q = searchInput.value.trim().toLowerCase();
    if (!q) {{
      reelItems.forEach(item => {{ item.style.display = 'flex'; item.classList.remove('dim'); }});
      // Restore whatever the reel is currently centered on, rather than
      // leaving the grid stuck on a stale "no match" state from the search
      // that just got cleared.
      const closest = centeredItem();
      if (closest) {{
        markActive(closest);
        renderGrid(closest.dataset.lang);
      }} else {{
        markActive(null);
        renderGrid(null);
      }}
      return;
    }}
    let firstMatch = null;
    reelItems.forEach(item => {{
      const matches = item.textContent.toLowerCase().includes(q);
      item.style.display = 'flex';
      item.classList.toggle('dim', !matches);
      if (matches && !firstMatch) firstMatch = item;
    }});
    if (firstMatch) {{
      suppressAutoSelect = true;
      firstMatch.scrollIntoView({{ block: 'center', behavior: 'smooth' }});
      selectLang(firstMatch.dataset.lang, true);
      setTimeout(() => {{ suppressAutoSelect = false; }}, 400);
    }} else {{
      // Nothing matches the search query (e.g. a language/country that has
      // no posts yet) — show no cards at all instead of silently leaving
      // whatever was selected before the search on screen.
      markActive(null);
      renderGrid(null, []);
    }}
  }});

  buildReel(LANG_NAMES);

  const params = new URLSearchParams(location.search);
  const currentLang = params.get('lang');
  const targetItem = (currentLang && LANG_TO_CARDS[currentLang])
    ? reelItems.find(item => item.dataset.lang === currentLang)
    : null;

  suppressAutoSelect = true;
  if (targetItem) {{
    targetItem.scrollIntoView({{ block: 'center', behavior: 'instant' }});
    markActive(targetItem);
    renderGrid(currentLang);
  }} else {{
    reel.scrollTo({{ top: 0, behavior: 'auto' }});
    markActive(null);
    renderGrid(null);
  }}
  setTimeout(() => {{ suppressAutoSelect = false; }}, 300);
</script>"""

TITLE_UPDATE_IDIOMY = """    document.getElementById('title').textContent =
      lang ? `Идиомы: ${lang}` : `Идиомы`;"""

TITLE_UPDATE_YAZYKI = """    const titleEl = document.getElementById('title');
    if (lang) {
      titleEl.innerHTML = `Языки: <span class="lang-name">${lang}</span>`;
    } else {
      titleEl.textContent = 'Языки';
    }"""

TITLE_UPDATE_STRANY = """    const titleEl = document.getElementById('title');
    if (lang) {
      titleEl.innerHTML = `Страны: <span class="lang-name">${displayName(lang)}</span>`;
    } else {
      titleEl.textContent = 'Страны';
    }"""

# Idiomy/yazyki: language names are common nouns in Russian ("армянский",
# "жестовые языки") — only the first word is capitalized for display.
DISPLAY_NAME_FIRST_WORD = """  function displayName(lang) {
    return lang.charAt(0).toUpperCase() + lang.slice(1);
  }"""

# Strany: country names are proper nouns, and a multi-word country name
# capitalizes every word ("новая зеландия" -> "Новая Зеландия"); a name
# that's already all-caps (e.g. "США") is left untouched by this logic.
DISPLAY_NAME_EVERY_WORD = """  function displayName(lang) {
    return lang.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  }"""


def load_json(relpath):
    return json.loads((ROOT / relpath).read_text(encoding="utf-8"))


def reverse_index(languages):
    rev = {}
    for lang, slugs in languages.items():
        for slug in slugs:
            rev.setdefault(slug, []).append(lang)
    return rev


def card_html(post, langs_for_slug):
    slug = post["slug"]
    bg = post["bg"]
    alt = html.escape(post["title"], quote=True)
    langs_attr = html.escape("|".join(langs_for_slug), quote=True)
    return (
        f'<a class="card" data-bg="{bg}" data-langs="{langs_attr}" href="/site/{slug}/">'
        f'<img src="/images/posts/{slug}.png" alt="{alt}" loading="lazy">'
        f"</a>"
    )


def render_grid(posts_with_langs):
    cards = "".join(card_html(p, langs) for p, langs in posts_with_langs)
    return f'<div class="grid" id="post-grid">{cards}</div>'


def apply_to_file(path, posts_with_langs, new_script):
    text = path.read_text(encoding="utf-8")
    original = text

    text, n_grid = GRID_RE.subn(render_grid(posts_with_langs), text, count=1)
    if n_grid != 1:
        raise RuntimeError(f"{path}: post-grid div not found/not unique")

    text, n_script = OLD_SCRIPT_RE.subn(new_script, text, count=1)
    if n_script != 1:
        raise RuntimeError(f"{path}: COLOR_ORDER script block not found/not unique")

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    posts = load_json("links/site/posts.json")
    sections = load_json("links/site/sections.json")

    changed = []

    for key in REEL_SECTIONS:
        languages = sections[key]["languages"]
        rev = reverse_index(languages)

        posts_with_langs = [
            (post, rev[post["slug"]]) for post in posts if post["slug"] in rev
        ]

        if key == "idiomy":
            new_script = SHUFFLE_JS + REEL_SCRIPT_BODY.format(
                title_update=TITLE_UPDATE_IDIOMY, display_name_fn=DISPLAY_NAME_FIRST_WORD
            )
        elif key == "yazyki":
            new_script = SHUFFLE_JS + REEL_SCRIPT_BODY.format(
                title_update=TITLE_UPDATE_YAZYKI, display_name_fn=DISPLAY_NAME_FIRST_WORD
            )
        elif key == "strany":
            new_script = SHUFFLE_JS + REEL_SCRIPT_BODY.format(
                title_update=TITLE_UPDATE_STRANY, display_name_fn=DISPLAY_NAME_EVERY_WORD
            )
        else:
            raise AssertionError(key)

        path = ROOT / f"links/site/section/{key}/index.html"
        if apply_to_file(path, posts_with_langs, new_script):
            changed.append(str(path.relative_to(ROOT)))

    if changed:
        print("Updated:")
        for c in changed:
            print(" ", c)
    else:
        print("No changes.")


if __name__ == "__main__":
    main()
