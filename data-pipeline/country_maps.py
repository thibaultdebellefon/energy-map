"""Country code harmonisation reference data.

Both Comtrade (partnerISO/reporterISO) and EIA (countryRegionId) mostly emit
ISO 3166-1 alpha-3 codes, but each also emits *aggregates* (World, OPEC, EU…)
and a handful of non-standard codes. This module holds the reference sets used
by normalize_countries.py.
"""
from __future__ import annotations

# Non-country aggregate / grouping codes to exclude from bilateral analysis.
# Comtrade uses "W00"/"WLD" (World) and various "nes" areas; EIA uses region
# labels. We drop these rows and report them rather than mixing them with
# real country flows.
AGGREGATE_CODES = {
    # Comtrade
    "W00", "WLD", "_X", "XX", "X1", "X2", "R91", "A49", "F19", "F49", "E29",
    "O19", "S19",
    # EIA international regions
    "WORL", "OPEC", "OECD", "NOPC", "EURA", "EURO", "PERG", "R4", "R5",
    "R6", "R7", "AFRC", "ASOC", "CSAM", "MIDE", "NAMR", "EU27", "EU28",
}

# EIA countryRegionId -> ISO 3166-1 alpha-3, for the cases where EIA diverges
# from ISO3. Codes not listed are assumed already-valid ISO3 and validated
# against ISO3_ALPHA3 below.
EIA_TO_ISO3 = {
    "USA": "USA",
    "RUS": "RUS",
    "SAU": "SAU",
    # Known EIA-specific spellings:
    "KSV": "XKX",   # Kosovo (EIA KSV -> user-assigned XKX)
    "IRN": "IRN",
    "CHN2": "CHN",  # some EIA series suffix mainland China
}

# ISO 3166-1 alpha-3 canonical set (used to flag unknown codes).
ISO3_ALPHA3 = {
    "ABW", "AFG", "AGO", "AIA", "ALA", "ALB", "AND", "ARE", "ARG", "ARM",
    "ASM", "ATA", "ATF", "ATG", "AUS", "AUT", "AZE", "BDI", "BEL", "BEN",
    "BES", "BFA", "BGD", "BGR", "BHR", "BHS", "BIH", "BLM", "BLR", "BLZ",
    "BMU", "BOL", "BRA", "BRB", "BRN", "BTN", "BVT", "BWA", "CAF", "CAN",
    "CCK", "CHE", "CHL", "CHN", "CIV", "CMR", "COD", "COG", "COK", "COL",
    "COM", "CPV", "CRI", "CUB", "CUW", "CXR", "CYM", "CYP", "CZE", "DEU",
    "DJI", "DMA", "DNK", "DOM", "DZA", "ECU", "EGY", "ERI", "ESH", "ESP",
    "EST", "ETH", "FIN", "FJI", "FLK", "FRA", "FRO", "FSM", "GAB", "GBR",
    "GEO", "GGY", "GHA", "GIB", "GIN", "GLP", "GMB", "GNB", "GNQ", "GRC",
    "GRD", "GRL", "GTM", "GUF", "GUM", "GUY", "HKG", "HMD", "HND", "HRV",
    "HTI", "HUN", "IDN", "IMN", "IND", "IOT", "IRL", "IRN", "IRQ", "ISL",
    "ISR", "ITA", "JAM", "JEY", "JOR", "JPN", "KAZ", "KEN", "KGZ", "KHM",
    "KIR", "KNA", "KOR", "KWT", "LAO", "LBN", "LBR", "LBY", "LCA", "LIE",
    "LKA", "LSO", "LTU", "LUX", "LVA", "MAC", "MAF", "MAR", "MCO", "MDA",
    "MDG", "MDV", "MEX", "MHL", "MKD", "MLI", "MLT", "MMR", "MNE", "MNG",
    "MNP", "MOZ", "MRT", "MSR", "MTQ", "MUS", "MWI", "MYS", "MYT", "NAM",
    "NCL", "NER", "NFK", "NGA", "NIC", "NIU", "NLD", "NOR", "NPL", "NRU",
    "NZL", "OMN", "PAK", "PAN", "PCN", "PER", "PHL", "PLW", "PNG", "POL",
    "PRI", "PRK", "PRT", "PRY", "PSE", "PYF", "QAT", "REU", "ROU", "RUS",
    "RWA", "SAU", "SDN", "SEN", "SGP", "SGS", "SHN", "SJM", "SLB", "SLE",
    "SLV", "SMR", "SOM", "SPM", "SRB", "SSD", "STP", "SUR", "SVK", "SVN",
    "SWE", "SWZ", "SXM", "SYC", "SYR", "TCA", "TCD", "TGO", "THA", "TJK",
    "TKL", "TKM", "TLS", "TON", "TTO", "TUN", "TUR", "TUV", "TWN", "TZA",
    "UGA", "UKR", "UMI", "URY", "USA", "UZB", "VAT", "VCT", "VEN", "VGB",
    "VIR", "VNM", "VUT", "WLF", "WSM", "XKX", "YEM", "ZAF", "ZMB", "ZWE",
}


# USGS Mineral Commodity Summaries uses country *names*, not codes, and its own
# spellings. Map them to ISO 3166-1 alpha-3. Aggregates/rollups are dropped.
USGS_AGGREGATES = {"Other Countries", "World total (rounded)", "World total",
                   "Other"}
USGS_NAME_TO_ISO3 = {
    "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT", "Bahrain": "BHR",
    "Bolivia": "BOL", "Brazil": "BRA", "Burma": "MMR", "Canada": "CAN",
    "Chile": "CHL", "China": "CHN", "Congo (Kinshasa)": "COD",
    "Congo (Brazzaville)": "COG", "Cuba": "CUB", "Cote d'Ivoire": "CIV",
    "Gabon": "GAB", "Germany": "DEU", "Ghana": "GHA", "Greece": "GRC",
    "Greenland": "GRL", "Guinea": "GIN", "Iceland": "ISL", "India": "IND",
    "Indonesia": "IDN", "Ireland": "IRL", "Jamaica": "JAM", "Japan": "JPN",
    "Kazakhstan": "KAZ", "Korea, North": "PRK", "Korea, Republic of": "KOR",
    "Laos": "LAO", "Madagascar": "MDG", "Malaysia": "MYS", "Mexico": "MEX",
    "Mozambique": "MOZ", "Namibia": "NAM", "New Caledonia": "NCL",
    "Nigeria": "NGA", "Norway": "NOR", "Papua New Guinea": "PNG", "Peru": "PER",
    "Philippines": "PHL", "Poland": "POL", "Portugal": "PRT", "Russia": "RUS",
    "Rwanda": "RWA", "Saudi Arabia": "SAU", "South Africa": "ZAF", "Spain": "ESP",
    "Sri Lanka": "LKA", "Sweden": "SWE", "Tanzania": "TZA", "Thailand": "THA",
    "Turkey": "TUR", "Turkiye": "TUR", "Ukraine": "UKR",
    "United Arab Emirates": "ARE", "United States": "USA", "Vietnam": "VNM",
    "Zambia": "ZMB", "Zimbabwe": "ZWE",
}


def is_aggregate(code: str) -> bool:
    return bool(code) and code.strip().upper() in AGGREGATE_CODES


def usgs_to_iso3(name: str) -> str | None:
    """USGS country name -> ISO3, or None if it's an aggregate/unknown."""
    if not name:
        return None
    clean = name.strip().replace("’", "'").replace("ô", "o")  # curly ', ô
    if clean in USGS_AGGREGATES:
        return None
    return USGS_NAME_TO_ISO3.get(clean)


# Broader English country-name -> ISO3, for GEM (oil/gas fields, LNG terminals)
# and USGS MRDS. Extends the USGS names above.
COMMON_NAME_TO_ISO3 = {
    **USGS_NAME_TO_ISO3,
    "Algeria": "DZA", "Azerbaijan": "AZE", "Bangladesh": "BGD", "Belgium": "BEL",
    "Brunei": "BRN", "Chad": "TCD", "Colombia": "COL", "Croatia": "HRV",
    "Denmark": "DNK", "Dominican Republic": "DOM", "Egypt": "EGY",
    "El Salvador": "SLV", "Equatorial Guinea": "GNQ", "Finland": "FIN",
    "Gibraltar": "GIB", "Guatemala": "GTM", "Guyana": "GUY", "Hong Kong": "HKG",
    "Hungary": "HUN", "Iran": "IRN", "Iraq": "IRQ", "Israel": "ISR",
    "Italy": "ITA", "Jordan": "JOR", "Kuwait": "KWT", "Libya": "LBY",
    "Lithuania": "LTU", "Malta": "MLT", "Netherlands": "NLD", "Oman": "OMN",
    "Panama": "PAN", "Qatar": "QAT", "Romania": "ROU", "Senegal": "SEN",
    "Singapore": "SGP", "South Sudan": "SSD", "Timor-Leste": "TLS",
    "Trinidad and Tobago": "TTO", "Turkmenistan": "TKM", "Turkiye": "TUR",
    "United Kingdom": "GBR", "Venezuela": "VEN", "Cuba": "CUB",
    "United States of America": "USA", "Viet Nam": "VNM",
    "Congo": "COG", "DR Congo": "COD", "Democratic Republic of the Congo": "COD",
    "Bolivia": "BOL", "Ecuador": "ECU", "Peru": "PER",
}


def name_to_iso3(name: str) -> str | None:
    """English country name -> ISO3. Skips shared/neutral zones ('Iran-Iraq')
    and unknown names (returns None)."""
    if not name:
        return None
    clean = name.strip().replace("’", "'").replace("ô", "o")
    if "-" in clean or clean in USGS_AGGREGATES:   # joint/neutral zone
        return None
    return COMMON_NAME_TO_ISO3.get(clean)


def to_iso3(code: str, source: str) -> str | None:
    """Return canonical ISO3, or None if the code is an aggregate/unknown.

    `source` is "comtrade" or "eia" — only affects which exception map applies.
    """
    if not code:
        return None
    code = code.upper().strip()
    if is_aggregate(code):
        return None
    if source == "eia" and code in EIA_TO_ISO3:
        code = EIA_TO_ISO3[code]
    return code if code in ISO3_ALPHA3 else None
