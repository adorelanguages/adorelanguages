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

BUTTON_SECTIONS = ["strany"]
REEL_SECTIONS = ["idiomy", "yazyki"]

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

# --- strany: button filters ------------------------------------------------

BUTTONS_SCRIPT = SHUFFLE_JS + """
  function renderGrid(lang) {
    const cards = (lang && LANG_TO_CARDS[lang]) ? LANG_TO_CARDS[lang] : ALL_CARDS;

    document.getElementById('title').textContent =
      lang ? `Страны: ${lang.charAt(0).toUpperCase() + lang.slice(1)}` : `Страны`;

    emptyMsg.style.display = cards.length === 0 ? 'block' : 'none';

    const ordered = colorRespectingShuffle(cards);
    const shown = new Set(ordered);
    ALL_CARDS.forEach(c => { c.style.display = shown.has(c) ? '' : 'none'; });
    ordered.forEach(c => grid.appendChild(c));
  }

  const params = new URLSearchParams(location.search);
  const currentLang = params.get('lang');

  const langContainer = document.getElementById('languages');
  LANG_NAMES.forEach(lang => {
    const btn = document.createElement('button');
    btn.textContent = lang.charAt(0).toUpperCase() + lang.slice(1);
    if (lang === currentLang) btn.classList.add('active');
    btn.addEventListener('click', () => {
      const url = new URL(location.href);
      if (btn.classList.contains('active')) {
        btn.classList.remove('active');
        url.searchParams.delete('lang');
        history.pushState({}, '', url);
        renderGrid(null);
      } else {
        [...langContainer.children].forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        url.searchParams.set('lang', lang);
        history.pushState({}, '', url);
        renderGrid(lang);
      }
    });
    langContainer.appendChild(btn);
  });

  renderGrid(currentLang);
</script>"""

# --- idiomy / yazyki: reel + search widget ---------------------------------

REEL_SCRIPT_BODY = """
  function renderGrid(lang) {{
    const cards = (lang && LANG_TO_CARDS[lang]) ? LANG_TO_CARDS[lang] : ALL_CARDS;

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

  function displayName(lang) {{
    return lang.charAt(0).toUpperCase() + lang.slice(1);
  }}

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

    for key in BUTTON_SECTIONS + REEL_SECTIONS:
        languages = sections[key]["languages"]
        rev = reverse_index(languages)

        posts_with_langs = [
            (post, rev[post["slug"]]) for post in posts if post["slug"] in rev
        ]

        if key in BUTTON_SECTIONS:
            new_script = BUTTONS_SCRIPT
        elif key == "idiomy":
            new_script = SHUFFLE_JS + REEL_SCRIPT_BODY.format(title_update=TITLE_UPDATE_IDIOMY)
        elif key == "yazyki":
            new_script = SHUFFLE_JS + REEL_SCRIPT_BODY.format(title_update=TITLE_UPDATE_YAZYKI)
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
