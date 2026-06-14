import re
from difflib import SequenceMatcher

MINIMUM_EDGE   = 0.04
KELLY_FRACTION = 0.25
MAX_BET_PCT    = 0.03

# ── Surface Score 1-9 ─────────────────────────────────────────────────────
# Based on cElo − hElo difference (player surface preference)
# 1 = extreme clay specialist  …  9 = extreme fast-court specialist
SS9_META = {
    1: {"icon": "🧱🧱🧱", "label": "Extrém salak",    "col": "#c2410c"},
    2: {"icon": "🧱🧱",   "label": "Erős salakos",    "col": "#ea580c"},
    3: {"icon": "🧱",     "label": "Salak-hajlam",    "col": "#f97316"},
    4: {"icon": "🔸",     "label": "Enyhe salak",     "col": "#fbbf24"},
    5: {"icon": "⚖",      "label": "All-rounder",     "col": "#94a3b8"},
    6: {"icon": "🔹",     "label": "Enyhe gyors",     "col": "#60a5fa"},
    7: {"icon": "💙",     "label": "Gyors-hajlam",    "col": "#3b82f6"},
    8: {"icon": "💙💙",   "label": "Erős gyors",      "col": "#2563eb"},
    9: {"icon": "💙💙💙", "label": "Extrém gyors",    "col": "#1d4ed8"},
}

# ── CPI adatbázis (courtspeed.com 3 éves átlag) ──────────────────────────
# Évente egyszer frissül automatikusan (fetch_cpi.py)
# Skála: <30 lassú · 30-34 közepes-lassú · 35-39 közepes · 40-44 közepes-gyors · >44 gyors
COURT_CPI = {
    # Grand Slam
    "french open":              21,
    "roland garros":            21,
    "wimbledon":                37,
    "us open":                  43,
    "australian open":          43,
    # Masters 1000 clay
    "monte carlo":              29,
    "madrid":                   28,
    "rome":                     28,
    "italian open":             28,
    # Masters 1000 hard
    "indian wells":             36,
    "miami":                    39,
    "canada":                   41,
    "montreal":                 41,
    "toronto":                  41,
    "cincinnati":               40,
    "western & southern":       40,
    "shanghai":                 38,
    "paris":                    40,
    "paris masters":            40,
    # ATP Finals
    "atp finals":               41,
    "nitto atp finals":         41,
    # Grass A500
    "halle":                    38,
    "queens":                   38,
    "london":                   38,
    "eastbourne":               37,
    "s-hertogenbosch":          37,
    # Default ha nincs adat
    "default_clay":             27,
    "default_hard":             37,
    "default_indoor":           41,
    "default_grass":            37,
}

# CPI → 1-9 konverzió (ITF kategóriák alapján)
def cpi_to_ss9(cpi: float) -> int:
    if cpi < 22:  return 1
    if cpi < 25:  return 2
    if cpi < 28:  return 3
    if cpi < 31:  return 4
    if cpi < 35:  return 5
    if cpi < 38:  return 6
    if cpi < 41:  return 7
    if cpi < 45:  return 8
    return 9


def get_court_cpi(tournament_name: str, surface: str) -> float:
    """Visszaadja a torna CPI értékét. Ha nincs mérve, borítás szerint default."""
    name = (tournament_name or "").lower().strip()
    for key, cpi in COURT_CPI.items():
        if key.startswith("default_"):
            continue
        if key in name or name in key:
            return cpi
    # Default borítás szerint
    surf = surface.lower()
    if surf == "clay":    return COURT_CPI["default_clay"]
    if surf == "grass":   return COURT_CPI["default_grass"]
    if "indoor" in name:  return COURT_CPI["default_indoor"]
    return COURT_CPI["default_hard"]


def player_ss9(record: dict, surface: str = "clay") -> int:
    """
    Játékos 1-9 borítás-preferencia pontszáma.
    Mindig cElo − hElo különbség alapján — torna borítástól független.
    Pozitív = salakos (1-4), közel 0 = all-rounder (5), negatív = gyors (6-9).
    Ez mutatja a játékos valódi profilját: pl. salakos játékos fűre = 2-3
    ami azonnal jelzi hogy "otthonán kívül" van.
    """
    celo  = record.get("cElo") or 1500
    helo  = record.get("hElo") or 1500
    delta = celo - helo
    if delta > 150:   return 1
    if delta > 80:    return 2
    if delta > 30:    return 3
    if delta > 10:    return 4
    if delta > -10:   return 5
    if delta > -30:   return 6
    if delta > -80:   return 7
    if delta > -150:  return 8
    return 9


# ── Core functions ─────────────────────────────────────────────────────────

def normalize_name(name):
    return re.sub(r"[^a-z]", "", name.lower())


def find_player_in_elo_db(player_name, elo_db, threshold=0.75):
    name  = player_name.strip().rstrip(".")
    parts = name.split()
    if len(parts) >= 2:
        last = parts[-1].replace(".", "")
        if len(last) == 1:
            initial     = last.upper()
            te_lastname = " ".join(parts[:-1]).lower()
            for canonical, data in elo_db.items():
                cparts = canonical.split()
                if len(cparts) < 2 or cparts[0][0].upper() != initial:
                    continue
                if " ".join(cparts[1:]).lower() == te_lastname:
                    return canonical, data
                if cparts[-1].lower() == te_lastname:
                    return canonical, data
    norm = normalize_name(player_name)
    for canonical, data in elo_db.items():
        if normalize_name(canonical) == norm:
            return canonical, data
    best_key, best_score = None, 0.0
    for canonical, data in elo_db.items():
        s = SequenceMatcher(None, norm, normalize_name(canonical)).ratio()
        if s > best_score:
            best_score, best_key = s, canonical
    if best_score >= threshold:
        return best_key, elo_db[best_key]
    return None, None


def elo_win_prob(elo_a, elo_b):
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def get_surface_elo(record, surface):
    key = {"clay": "cElo", "grass": "gElo", "hard": "hElo"}.get(surface, "elo")
    return record.get(key) or record.get("elo")


def prob_to_decimal_odds(prob):
    if prob <= 0:
        return 999.0
    return round(1.0 / prob, 2)


def compute_edge(model_prob, book_odds):
    if not book_odds or book_odds <= 1:
        return None
    return round(model_prob - (1.0 / book_odds), 4)


def kelly_stake(edge, decimal_odds, bankroll):
    if not edge or edge <= 0 or decimal_odds <= 1:
        return 0.0
    b = decimal_odds - 1.0
    f = min((edge / b) * KELLY_FRACTION, MAX_BET_PCT)
    return round(f * bankroll, 2)
