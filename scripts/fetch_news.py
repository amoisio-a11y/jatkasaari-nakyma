#!/usr/bin/env python3
"""Hakee feeds.json:ssa listatut RSS/Atom-syötteet ja kirjoittaa news.json.

Ajetaan GitHub Actionsissa ajastetusti. Yksittäisen syötteen kaatuminen ei
kaada koko ajoa – muut syötteet haetaan silti ja virhe kirjataan lokiin.
"""
import calendar
import datetime
import json
import pathlib
import sys

import feedparser

ROOT = pathlib.Path(__file__).resolve().parent.parent
FEEDS_FILE = ROOT / "feeds.json"
OUT_FILE = ROOT / "news.json"

MAX_ITEMS = 30
# Jotkin palvelimet torjuvat oletus-User-Agentin; annetaan oma.
USER_AGENT = "JatkasaariDashboard/1.0 (+https://github.com)"


def entry_iso(entry):
    """Palauttaa julkaisuajan ISO 8601 -muodossa (UTC) tai None."""
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return None
    dt = datetime.datetime.fromtimestamp(calendar.timegm(t), tz=datetime.timezone.utc)
    return dt.isoformat()


def main():
    feeds = json.loads(FEEDS_FILE.read_text(encoding="utf-8"))
    items, seen_links = [], set()
    failed = 0

    for feed in feeds:
        url = (feed.get("url") or "").strip()
        name = feed.get("name", "")
        if not url:
            continue
        try:
            parsed = feedparser.parse(url, agent=USER_AGENT)
            # bozo = jäsennysvirhe; sallitaan jos otsikoita silti löytyi
            if parsed.bozo and not parsed.entries:
                raise RuntimeError(parsed.bozo_exception)
            for e in parsed.entries:
                link = (e.get("link") or "").strip()
                title = (e.get("title") or "").strip()
                if not link or not title or link in seen_links:
                    continue
                seen_links.add(link)
                items.append({
                    "title": title,
                    "link": link,
                    "iso": entry_iso(e),
                    "src": name,
                })
        except Exception as ex:  # noqa: BLE001 – yksittäinen syöte ei saa kaataa ajoa
            failed += 1
            print(f"VAROITUS: '{name or url}' epäonnistui: {ex}", file=sys.stderr)

    # Uusin ensin; päivättömät loppuun.
    items.sort(key=lambda i: i["iso"] or "", reverse=True)
    items = items[:MAX_ITEMS]

    payload = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "count": len(items),
        "failed": failed,
        "items": items,
    }
    OUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Kirjoitettu {len(items)} otsikkoa news.json:iin "
          f"({failed} syötettä epäonnistui).")


if __name__ == "__main__":
    main()
