# /app — Energy Map frontend

Interactive planisphere of global crude oil & LNG trade, built on the SQLite
pipeline. Pure D3 v7, no build step, runs fully offline once the data bundle is
generated.

## Run

```bash
# 1. Make sure the database exists (from the data pipeline)
python data-pipeline/run_all.py --years 2025 2024

# 2. Build the frontend data bundle (exports data.json, vendors D3 + world map)
python app/build_data.py

# 3. Serve it
python app/serve.py            # opens http://localhost:8000
# or:  python -m http.server -d app/public 8000
```

Then open http://localhost:8000. It must be served over HTTP (the browser blocks
`fetch` from `file://`).

## What it does

- **Choropleth**: shade countries by production, exports, imports, or net trade
  (diverging: amber = net exporter, blue = net importer).
- **Flow arcs**: great-circle routes exporter → destination, width ∝ value,
  animated in the flow direction. Crude = amber, LNG = cyan.
- **Click a country** (map or leaderboard) → focus mode: its routes only, plus a
  side profile with production, totals, and top partners. Each partner is tagged
  `direct` or `mirror` (see below).
- **Controls**: commodity (crude / LNG / both), shade-by metric, number of routes,
  and data source (all / direct / mirror). Zoom + pan on the map.

## Data provenance shown in the UI

Flows are resolved latest-year-first (2025 over 2024) and prefer a country's own
`direct` export report; where a country doesn't report (Saudi Arabia, Russia,
Iran, …), the flow is reconstructed from the importer's report (`mirror`). Mirror
values are CIF (include freight/insurance) vs FOB for direct — tagged, not
adjusted.

## Files

```
build_data.py        SQLite -> public/data.json + vendors assets
serve.py             local static server
public/index.html    layout + controls
public/style.css     design tokens (control-room dark, thermal accents)
public/app.js        D3 engine: projection, choropleth, arcs, panel, filters
public/data.json     generated bundle (gitignored)
public/world.geojson Natural Earth 110m (vendored, gitignored)
public/vendor/d3.min.js  D3 v7 (vendored, gitignored)
```

Regenerate `data.json` whenever the pipeline reloads new years or commodities.
