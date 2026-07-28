# TODO — Energy Map (Phase 1 : crude oil + LNG)

## Session 1 — Fondations du pipeline

### Setup repo
- [x] Structure repo : /data-pipeline, /data, /app (placeholder)
- [x] .gitignore, requirements.txt, .env.example, README
- [x] git init (pas de commit tant que non demandé)

### Base de données (SQLite)
- [x] `db.py` — schéma `export_flows` + `production` avec contraintes UNIQUE (idempotence)

### Ingestion
- [x] `config.py` — chargement .env, codes HS, facets EIA, constantes
- [x] `country_maps.py` — set d'agrégats + exceptions EIA→ISO3 + référentiel ISO3
- [x] `fetch_comtrade.py` — HS + années en paramètre, flux bilatéraux, rate limit 1 req/s, pagination/cap 100k, filtre agrégats
- [x] `fetch_eia.py` — production annuelle pétrole (route international) + gaz (natural-gas), pagination offset EIA
- [x] `normalize_countries.py` — harmonisation codes pays, suppression agrégats, rapport de réconciliation
- [x] `run_all.py` — orchestration + résumé (lignes, pays, anomalies) + `--selftest`

### Données miroir (découverte session 1)
- [x] Comtrade : filtrer motCode=0 & customsCode=C00 (1 ligne/paire, plus de collapse)
- [x] Augmenter flux directs (X) avec miroir (M) — reconstruit SAU/RUS/IRN/etc.
- [x] Schéma : colonne flow_source (direct/mirror), vue résolue (année récente > direct > miroir)

### Vérification
- [x] Self-test synthétique : schéma + normalisation + résolution direct/miroir + résumé
- [x] **Run live tâche 5** — FAIT sur 2025+2024 (2026 vide). Top exportateurs cohérents
      (SAU 164Md$, USA 138, RUS 133, ARE 112, CAN 104 ; GNL : USA/AUS/QAT en tête)

### Frontend /app (session 2 — FAIT)
- [x] build_data.py : SQLite (vues résolues) → public/data.json + vendorise D3 + GeoJSON
- [x] Planisphère D3 : projection Natural Earth, choroplèthe, arcs great-circle animés
- [x] Interactions : toggle commodité, métrique, slider routes, filtre source, clic pays → fiche
- [x] Fiche pays : production, exports/imports/net, top partenaires + badge direct/mirror
- [x] serve.py + README, responsive mobile, offline
- [x] Vérifié dans un vrai navigateur (0 erreur console, screenshots) ; bugs corrigés
      (fill CSS>attr, ordre leaderboard, échelle divergente sqrt)

### Frontend v2 (session 2 — améliorations focus)
- [x] Clic pays : top 10 partenaires surlignés + étiquetés (cercle proche visible)
- [x] Focus limité à 20 flèches sur la carte (fiche gauche = tous les partenaires)

### Frontend v3 — voies de transit (session 2)
- [x] routes_def.py : 15 voies (8 maritimes + 5 oléoducs + Gibraltar/Lombok), géométrie + méta
- [x] build_data.py : attribution heuristique flux→voies, top 10 users + part %/volume
- [x] Vue Trade/Routes ; en Routes : arcs masqués, voies + chokepoints affichés
- [x] Fiche voie : nom, départ/arrivée, transit, détroits, pays traversés, volume, top 10 users
- [x] Tag "estimation modèle" ; gazoducs exclus (gaz pipeline hors dataset LNG)
- [x] Vérifié navigateur (Hormuz 413Md$, SAU 100%, etc.) ; 0 erreur console

### Phase 2 — 10 métaux (session 3)
- [x] Vérifié les 18 codes HS via Comtrade includeDesc (table reçue corrompue, reconstruite Li=283691 / Ni=2604+7502)
- [x] Trouvé + inspecté le CSV USGS MCS 2025 (World Production) ; structure documentée
- [x] fetch_usgs.py : CSV→production (mine), 10 métaux, mapping noms→ISO3, anomalies loggées (242 lignes)
- [x] config.METAL_HS + fetch_comtrade sur 18 codes (2023, direct+miroir) → 28 727 flux
- [x] country_maps : mapping noms pays USGS→ISO3
- [x] Résumé par métal fourni ; schéma inchangé ; oil/LNG intacts
- [x] Métaux rafraîchis sur 2024+2025 (comme oil/LNG) — vues résolues prennent 2025 en priorité
- [x] Frontend métaux : build_data registre 20 commodités ; sélecteur déroulant groupé ;
      choroplèthe/arcs/couleurs par commodité ; production USGS ; routes gated sur oil/LNG

### Frontend v4 (session 3)
- [x] Flèche de repli du panneau gauche (‹/›)
- [x] Fiche route : libellé reflète le filtre commodité (crude vs crude+LNG), plus "both" trompeur
- [x] Filtre Source clarifié (Direct exporter-reported / Mirror importer-reported + infobulle)

### Frontend v5 (session 4)
- [x] Routes par commodité : détroits agnostiques (règles géographiques élargies),
      oléoducs restent brut ; stats/couleurs par commodité ; vue Routes ouverte à tout
- [x] Écart minerai↔raffiné : métrique "Ore → refined" (choroplèthe divergente contrastée
      ocre=extracteur / cyan=transformateur) + cellules ore/refined exports dans la fiche pays

### Session 5 — table facility (À FAIRE, demandé pendant session 4)
- [ ] Table facility (sites physiques : puits, terminaux GNL, mines)
- [ ] fetch_gem_oil_gas.py (GEM GOGET puits + GGIT terminaux LNG, operating, top 20/commodity)
- [ ] fetch_mrds_candidates.py (USGS MRDS, top 20 candidats/métal par complétude)
- [ ] Résumé complétude + métaux manquant de candidats fiables ; PAS de frontend, PAS de Wikidata/photos

## À NE PAS FAIRE (rappel)
- Pas d'auth / déploiement

## Prochaine session (après obtention des clés)
1. Remplir `.env` (COMTRADE_KEY, EIA_KEY)
2. `python data-pipeline/run_all.py --years 2023` (année complète pour valider)
3. Lire le résumé, traiter les anomalies
4. Décider stack /app une fois la donnée validée
