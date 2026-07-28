"""Reverse-geocode each country's port node (from app/public/data.json) to a
nearby city/place via OpenStreetMap Nominatim (free, 1 req/s). Writes
data/port_cities.json {iso: city}. build_data.py folds it into meta.port_city.

    python enrich_ports.py
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import config

DATA_JSON = config.DATA_DIR.parent / "app" / "public" / "data.json"
OUT = config.DATA_DIR / "port_cities.json"
PLACE_KEYS = ("city", "town", "village", "municipality", "port", "suburb",
              "county", "state_district", "state", "region")


def reverse(lat: float, lon: float):
    p = {"lat": lat, "lon": lon, "format": "json", "zoom": "10",
         "addressdetails": "1", "accept-language": "en"}
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={
        "User-Agent": "energy-map/1.0 (research project; facility mapping)"})
    for attempt in range(3):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=30))
            addr = d.get("address", {})
            for k in PLACE_KEYS:
                if addr.get(k):
                    return addr[k]
            return None
        except Exception:
            time.sleep(2)
    return None


def main() -> None:
    ports = json.loads(DATA_JSON.read_text()).get("ports", {})
    cities = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = [(iso, ll) for iso, ll in ports.items() if iso not in cities]
    print(f"{len(cities)} cached · geocoding {len(todo)} ports (1/s)…")
    for iso, (lon, lat) in todo:
        city = reverse(lat, lon)
        if city:
            cities[iso] = city
            OUT.write_text(json.dumps(cities, ensure_ascii=False))  # incremental
        time.sleep(1.1)  # Nominatim usage policy
    print(f"done — {len(cities)} port cities in {OUT.name}")


if __name__ == "__main__":
    main()
