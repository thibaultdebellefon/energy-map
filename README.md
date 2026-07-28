# Energy Map — Phase 1

Visualisation interactive du commerce international de commodities.
**Phase 1** : deux commodities uniquement — pétrole brut (HS 2709) et GNL (HS 271111).
Cette session pose le pipeline de données ; le frontend viendra après validation.

## Structure

```
data-pipeline/        Scripts Python d'ingestion
  config.py           Chemins, clés (.env), codes HS, facets EIA
  db.py               Schéma SQLite + upserts idempotents
  country_maps.py     Référentiel ISO3, agrégats, exceptions EIA→ISO3
  fetch_comtrade.py   Flux bilatéraux export (UN Comtrade v1)
  fetch_eia.py        Production annuelle pétrole + gaz (EIA v2)
  normalize_countries.py  Harmonisation codes pays + rapport de réconciliation
  run_all.py          Orchestration + résumé data-quality  (+ --selftest)
data/                 Base locale energy_map.db (gitignored)
app/                  Frontend (placeholder — Phase 2)
```

## Schéma de données

```sql
export_flows(reporter_iso, partner_iso, hs_code, year,
             trade_value_usd, quantity, quantity_unit)   -- UNIQUE(reporter,partner,hs,year)
production(country_iso, commodity, year, volume, unit, source)  -- UNIQUE(country,commodity,year,source)
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # puis remplir les deux clés
```

Obtenir les clés (gratuites) :
- **Comtrade** : https://comtradedeveloper.un.org/ → sign up → Subscriptions → clé primaire → `COMTRADE_KEY`
- **EIA** : https://www.eia.gov/opendata/register.php → clé par email → `EIA_KEY`

## Utilisation

```bash
# Pipeline complet (fetch + normalize + résumé) — nécessite les clés
python data-pipeline/run_all.py --years 2023

# Scripts individuels
python data-pipeline/fetch_comtrade.py --hs 2709 271111 --years 2023
python data-pipeline/fetch_eia.py --years 2023
python data-pipeline/fetch_eia.py --discover        # vérifier les facet ids EIA
python data-pipeline/normalize_countries.py

# Valider le pipeline SANS clé (données synthétiques)
python data-pipeline/run_all.py --selftest
```

## Note sur l'année

Les données **annuelles** Comtrade et EIA accusent ~1 an de retard : demander **2026**
(défaut du brief) renvoie un jeu vide jusqu'à ~2027. Les scripts sont paramétriques
(`--years`), détectent le résultat vide et suggèrent l'année complète la plus récente
(**2023**). Pour valider le pipeline maintenant, utiliser `--years 2023`.
