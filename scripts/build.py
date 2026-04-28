#!/usr/bin/env python3
"""
Build data.json from upstream sources.

Sources:
  - SP12 difficulty table:    https://iidx-sp12.github.io/songs.json
  - INFINITAS music packs:    https://p.eagate.573.jp/game/infinitas/2/music/index.html

Sections covered:
  - 新規追加曲 (#newsong)            flat
  - 初期収録曲 (#default)            grouped by IIDX version
  - DJP解禁曲 (#djp)                 flat
  - BIT解禁曲 (#bit)                 grouped by IIDX version
  - 楽曲パック (#pac)                each pack listed individually

LEGGENDARIA (#leg) charts whose source category is one of the above are attached
to the corresponding section (with version subgroup matched when applicable).

Output:
  data.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

SCHEMA_VERSION = 2
SONGS_URL = "https://iidx-sp12.github.io/songs.json"
PACKS_URL = "https://p.eagate.573.jp/game/infinitas/2/music/index.html"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

# ── Section IDs in source order (excluding trial) ──
SECTION_FLOW = [
    ("newsong", "trial"),
    ("default", "djp"),
    ("djp",     "bit"),
    ("bit",     "pac"),
]
CATEGORY_NAMES = {
    "newsong": "新規追加曲",
    "default": "初期収録曲",
    "djp":     "DJP解禁曲",
    "bit":     "BIT解禁曲",
}
GROUPED_SECTIONS = {"default", "bit"}


# ────────────────────────────────────────────────────────────────────
def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def norm(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", "", s)
    return s.lower()


def tier_of(label: str | None) -> str:
    if not label:
        return ""
    m = re.search(r"(S\+|S|A\+|A|B\+|B|C|D|E|F)", label)
    return m.group(1) if m else ""


def is_kojinsa(label: str | None) -> bool:
    return bool(label) and label.startswith("個人差")


def clean(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


# ────────────────────────────────────────────────────────────────────
# Pack section parser
# ────────────────────────────────────────────────────────────────────
def parse_packs(html_text: str) -> list[dict]:
    try:
        m_start = html_text.index('id="pac"')
        m_leg = html_text.index('id="leg"')
    except ValueError as e:
        raise RuntimeError(f"Pack section markers not found: {e}")
    pac_html = html_text[m_start:m_leg]

    header_re = re.compile(
        r'<div class="cat"(?:\s+id="[^"]*")?>\s*<strong>(.*?)</strong>(.*?)</div>',
        re.DOTALL,
    )
    table_re = re.compile(r"<table>(.*?)</table>", re.DOTALL)
    row_re = re.compile(
        r'<tr(\s+bgcolor="([^"]+)")?>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>',
        re.DOTALL,
    )

    headers = list(header_re.finditer(pac_html))
    tables = [(m.start(), m.group(1)) for m in table_re.finditer(pac_html)]

    packs: list[dict] = []
    for hm in headers:
        name = clean(hm.group(1))
        if name == "楽曲パック":
            continue
        t = next(((s, body) for s, body in tables if s > hm.end()), None)
        if not t:
            continue
        rows = []
        for r in row_re.finditer(t[1]):
            bg = (r.group(2) or "").lower()
            title = clean(r.group(3))
            rows.append({"title": title, "kind": "A", "yellow": bg == "lightyellow"})
        packs.append({
            "type": "pack",
            "name": name,
            "_songs": rows,
            "_total": len(rows),
        })
    if not packs:
        raise RuntimeError("No packs parsed.")
    return packs


# ────────────────────────────────────────────────────────────────────
# Category parser (newsong / default / djp / bit)
# ────────────────────────────────────────────────────────────────────
def parse_category(html_text: str, sec_id: str, next_id: str) -> dict:
    s = html_text.index(f'id="{sec_id}"')
    e = html_text.index(f'id="{next_id}"')
    body = html_text[s:e]

    sub_match = re.search(
        r'<div class="cat"\s+id="' + re.escape(sec_id) + r'">(.*?)</div>',
        body, re.DOTALL,
    )
    subtitle = ""
    if sub_match:
        spans = re.findall(r"<span>(.*?)</span>", sub_match.group(1), re.DOTALL)
        if spans:
            subtitle = clean(spans[0])

    tbl = re.search(r"<table>(.*?)</table>", body, re.DOTALL)
    if not tbl:
        return {"id": sec_id, "name": CATEGORY_NAMES[sec_id], "subtitle": subtitle,
                "_songs": [], "_groups": [], "_total": 0}
    tbl_html = tbl.group(1)

    row_re = re.compile(
        r'<tr(?:\s+bgcolor="([^"]+)")?>\s*<t([dh])>(.*?)</t[dh]>\s*<t[dh]>(.*?)</t[dh]>\s*</tr>',
        re.DOTALL,
    )

    grouped = sec_id in GROUPED_SECTIONS
    flat_songs: list[dict] = []
    groups: list[dict] = []
    current_group: dict | None = None

    for m in row_re.finditer(tbl_html):
        bg = (m.group(1) or "").lower()
        kind = m.group(2)
        c1 = clean(m.group(3))
        if kind == "h":
            if c1 == "タイトル":
                continue
            if grouped:
                current_group = {"label": c1, "_songs": []}
                groups.append(current_group)
        else:
            song = {"title": c1, "kind": "A", "yellow": bg == "lightyellow"}
            if grouped:
                if current_group is None:
                    current_group = {"label": "", "_songs": []}
                    groups.append(current_group)
                current_group["_songs"].append(song)
            else:
                flat_songs.append(song)

    total = sum(len(g["_songs"]) for g in groups) if grouped else len(flat_songs)
    return {
        "id": sec_id,
        "name": CATEGORY_NAMES[sec_id],
        "subtitle": subtitle,
        "_songs": flat_songs,
        "_groups": groups,
        "_total": total,
    }


# ────────────────────────────────────────────────────────────────────
# LEGGENDARIA parser
# ────────────────────────────────────────────────────────────────────
def parse_leggendaria(html_text: str) -> list[dict]:
    try:
        m_leg = html_text.index('id="leg"')
        m_end = html_text.index("</table>", m_leg)
    except ValueError:
        return []
    leg = html_text[m_leg:m_end]
    row_re = re.compile(
        r'<tr(?:\s+bgcolor="([^"]+)")?>\s*<t([dh])>(.*?)</t[dh]>\s*<t[dh]>(.*?)</t[dh]>\s*</tr>',
        re.DOTALL,
    )
    out = []
    current_ver = ""
    for m in row_re.finditer(leg):
        kind = m.group(2)
        c1 = clean(m.group(3))
        c2 = clean(m.group(4))
        if kind == "h":
            if c1 == "タイトル":
                continue
            current_ver = c1
        else:
            out.append({"title": c1, "version": current_ver, "category": c2})
    return out


def short_pack_key(name: str) -> str:
    s = name.replace("beatmania IIDX INFINITAS ", "").strip()
    s = re.sub(r"\s*\(.*?\)\s*$", "", s).strip()
    return s


def attach_leggendaria(packs: list[dict], categories: dict[str, dict],
                       leg_rows: list[dict]) -> dict:
    pack_keys = [(short_pack_key(p["name"]), p) for p in packs]
    counts = {"pack": 0, "default": 0, "bit": 0, "skipped": 0}

    for r in leg_rows:
        title, ver, cat = r["title"], r["version"], r["category"]
        target = None

        if "楽曲パック" in cat or "セレクション" in cat:
            target = next((p for k, p in pack_keys if k == cat), None)
            if target is None:
                target = next((p for k, p in pack_keys if cat in k or k in cat), None)
            if target is not None:
                target["_songs"].append({"title": title, "kind": "L", "yellow": False})
                counts["pack"] += 1
                continue

        elif cat in ("初期収録曲", "BIT解禁曲"):
            cat_id = "default" if cat == "初期収録曲" else "bit"
            section = categories.get(cat_id)
            if section is None:
                counts["skipped"] += 1
                continue
            grp = next((g for g in section["_groups"] if g["label"] == ver), None)
            if grp is None:
                grp = {"label": ver, "_songs": []}
                section["_groups"].append(grp)
            grp["_songs"].append({"title": title, "kind": "L", "yellow": False})
            section["_total"] += 1
            counts[cat_id] += 1
            continue

        counts["skipped"] += 1
    return counts


# ────────────────────────────────────────────────────────────────────
# Merge with difficulty table
# ────────────────────────────────────────────────────────────────────
def make_row(song: dict, by_key: dict) -> dict | None:
    entry = by_key.get((norm(song["title"]), song["kind"]))
    if entry is None:
        return None
    n_label = entry.get("normal") or ""
    h_label = entry.get("hard") or ""
    return {
        "t": song["title"],
        "k": song["kind"],
        "y": 1 if song.get("yellow") else 0,
        "n": n_label,
        "h": h_label,
        "nt": tier_of(n_label),
        "ht": tier_of(h_label),
        "nk": 1 if is_kojinsa(n_label) else 0,
        "hk": 1 if is_kojinsa(h_label) else 0,
        "v": entry.get("version"),
    }


def merge_pack(pack: dict, by_key: dict) -> dict:
    rows = [r for r in (make_row(s, by_key) for s in pack["_songs"]) if r is not None]
    return {
        "type": "pack",
        "name": pack["name"],
        "rows": rows,
        "total": pack["_total"],
    }


def merge_category(cat: dict, by_key: dict) -> dict:
    out = {
        "type": "category",
        "id": cat["id"],
        "name": cat["name"],
        "subtitle": cat.get("subtitle", ""),
        "total": cat["_total"],
    }
    if cat["_groups"]:
        merged_groups = []
        for g in cat["_groups"]:
            rows = [r for r in (make_row(s, by_key) for s in g["_songs"]) if r is not None]
            if rows:
                merged_groups.append({"label": g["label"], "rows": rows})
        out["groups"] = merged_groups
    else:
        out["rows"] = [r for r in (make_row(s, by_key) for s in cat["_songs"]) if r is not None]
    return out


def section_chart_count(sec: dict) -> int:
    if "groups" in sec:
        return sum(len(g["rows"]) for g in sec["groups"])
    return len(sec.get("rows", []))


# ────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data.json")
    ap.add_argument("--cache-dir", default=None)
    args = ap.parse_args()

    try:
        print(f"Fetching {SONGS_URL}", file=sys.stderr)
        songs_raw = fetch(SONGS_URL)
        print(f"  → {len(songs_raw):,} bytes", file=sys.stderr)
        print(f"Fetching {PACKS_URL}", file=sys.stderr)
        packs_raw = fetch(PACKS_URL)
        print(f"  → {len(packs_raw):,} bytes", file=sys.stderr)
    except Exception as e:
        print(f"FETCH ERROR: {e}", file=sys.stderr)
        return 1

    if args.cache_dir:
        cd = Path(args.cache_dir)
        cd.mkdir(parents=True, exist_ok=True)
        (cd / "songs.json").write_bytes(songs_raw)
        (cd / "infinitas_music.html").write_bytes(packs_raw)

    try:
        songs = json.loads(songs_raw.decode("utf-8"))
        page = packs_raw.decode("utf-8")

        categories: dict[str, dict] = {}
        for sec_id, next_id in SECTION_FLOW:
            categories[sec_id] = parse_category(page, sec_id, next_id)

        packs = parse_packs(page)

        leg = parse_leggendaria(page)
        attach_counts = attach_leggendaria(packs, categories, leg)

        print(f"Parsed:", file=sys.stderr)
        for sid in CATEGORY_NAMES:
            c = categories[sid]
            n = c["_total"]
            ng = len(c["_groups"])
            if ng:
                print(f"  {c['name']:8s} {n:4d} songs / {ng} version-groups", file=sys.stderr)
            else:
                print(f"  {c['name']:8s} {n:4d} songs (flat)", file=sys.stderr)
        print(f"  楽曲パック   {len(packs)} packs", file=sys.stderr)
        print(f"  LEGGENDARIA attached: {attach_counts}", file=sys.stderr)

    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"PARSE ERROR: {e}", file=sys.stderr)
        return 2

    by_key = {(norm(s["name"]), s["difficulty"]): s for s in songs}

    sections: list[dict] = []
    for sid in ("newsong", "default", "djp", "bit"):
        sections.append(merge_category(categories[sid], by_key))
    for p in packs:
        sections.append(merge_pack(p, by_key))

    total_charts = sum(section_chart_count(s) for s in sections)
    pack_count = sum(1 for s in sections if s["type"] == "pack")
    cat_count = sum(1 for s in sections if s["type"] == "category")
    print(f"Merged: {len(sections)} sections, {total_charts} ☆12 chart entries", file=sys.stderr)

    doc = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sources": {
            "songs": {"url": SONGS_URL, "sha256": hashlib.sha256(songs_raw).hexdigest(), "size": len(songs_raw)},
            "packs": {"url": PACKS_URL, "sha256": hashlib.sha256(packs_raw).hexdigest(), "size": len(packs_raw)},
        },
        "stats": {
            "section_count": len(sections),
            "category_count": cat_count,
            "pack_count": pack_count,
            "chart_count": total_charts,
        },
        "sections": sections,
    }

    out_path = Path(args.out)
    new_text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))

    changed = True
    if out_path.exists():
        try:
            old = json.loads(out_path.read_text(encoding="utf-8"))
            old_data = {"sources": old.get("sources"), "sections": old.get("sections")}
            new_data = {"sources": doc["sources"], "sections": doc["sections"]}
            changed = old_data != new_data
        except Exception:
            changed = True

    out_path.write_text(new_text, encoding="utf-8")
    print(f"Wrote {out_path} ({len(new_text):,} bytes) — changed={changed}", file=sys.stderr)

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")
            f.write(f"chart_count={total_charts}\n")
            f.write(f"pack_count={pack_count}\n")
            f.write(f"section_count={len(sections)}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
