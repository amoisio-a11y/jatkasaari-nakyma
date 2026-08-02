#!/usr/bin/env python3
"""Hakee Helsingin satamaan saapuvat alukset porttraffic.fi:stä
(Traficomin käyttöliittymä Portnet-järjestelmään) ja kirjoittaa
ships.json, suodatettuna Länsiterminaali 2:n aluksiin.

porttraffic.fi ei salli suoraa selainkutsua (CORS), joten haku
tehdään palvelinpuolella GitHub Actionissa.

Länsiterminaali 2:ta liikennöivät alukset tunnistetaan nimen
perusteella, koska rajapinta ei palauta terminaalitietoa suoraan.
Päivitä LT2_VESSELS jos varustamo lisää tai vaihtaa aluksia.
"""
import datetime
import json
import pathlib
import sys
from zoneinfo import ZoneInfo

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "ships.json"

# Länsiterminaali 2:een liikennöivät alukset (Tallink Silja, Eckerö Line)
LT2_VESSELS = {"Megastar", "MyStar", "Victoria I", "Finlandia"}

HELSINKI = ZoneInfo("Europe/Helsinki")
UTC = datetime.timezone.utc

BASE_URL = "https://www.porttraffic.fi/rest/search/port=FIHEL&agentId=-1&startDte={start}&endDte={end}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JatkasaariDashboard/1.0)",
    "Accept": "application/json",
}


def parse_arrival_time(date_str, time_str):
    """pvArrDte='20260802', pvArrTme jokin muoto joista alku on aina HHMM.
    Palauttaa timezone-aware datetime UTC:ssa, tai None jos ei jäsentyisi."""
    try:
        year, month, day = int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8])
        hour, minute = int(time_str[0:2]), int(time_str[2:4])
        local_dt = datetime.datetime(year, month, day, hour, minute, tzinfo=HELSINKI)
        return local_dt.astimezone(UTC)
    except (ValueError, IndexError):
        return None


def main():
    now_helsinki = datetime.datetime.now(HELSINKI)
    start = now_helsinki.strftime("%d.%m.%Y")
    end = (now_helsinki + datetime.timedelta(days=3)).strftime("%d.%m.%Y")
    url = BASE_URL.format(start=start, end=end)

    arrivals = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        data = res.json()
        topics = (data.get("topicList") or {}).get("topics") or []

        for t in topics:
            name = t.get("vesselNme")
            if name not in LT2_VESSELS:
                continue
            arr_time = parse_arrival_time(t.get("pvArrDte", ""), t.get("pvArrTme", ""))
            if not arr_time:
                continue
            arrivals.append({
                "name": name,
                "agent": t.get("agentNme", ""),
                "arrTime": arr_time.isoformat().replace("+00:00", "Z"),
            })
    except Exception as ex:  # noqa: BLE001
        print(f"VAROITUS: haku epäonnistui: {ex}", file=sys.stderr)

    # Poistetaan duplikaatit (sama alus + aika voi esiintyä kahdesti eri statuksilla)
    seen = set()
    unique = []
    for a in arrivals:
        key = (a["name"], a["arrTime"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(a)
    unique.sort(key=lambda a: a["arrTime"])

    payload = {
        "generated": datetime.datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "arrivals": unique,
    }
    OUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Kirjoitettu {len(unique)} Länsiterminaali 2 -saapumista ships.json:iin.")


if __name__ == "__main__":
    main()
