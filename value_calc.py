"""Name matching + Elo calculations."""
import re
from difflib import SequenceMatcher

MINIMUM_EDGE   = 0.04
KELLY_FRACTION = 0.25
MAX_BET_PCT    = 0.03

SURFACE_LABELS = {
    1: ("🧱🧱", "Salakos spec."),
    2: ("🧱",   "Salak-hajlam"),
    3: ("⚖",    "All-rounder"),
    4: ("💙",   "Kemény-hajlam"),
    5: ("💙💙", "Kemény spec."),
}

def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def find_player_in_elo_db(player_name: str, elo_db: dict, threshold: float = 0.75):
    """
    Pass 1 – TennisExplorer 'Lastname F.' format:
      Strategy A: initial=firstname[0], te_lastname=everything after firstname
      Strategy B: initial=firstname[0], te_lastname matches LAST token only
                  (handles middle names: 'Tirante T.' → 'Thiago Agustin Tirante')
    Pass 2 – normalized exact match
    Pass 3 – fuzzy fallback
    """
    name  = player_name.strip().rstrip('.')
    parts = name.split()

    if len(parts) >= 2:
        last = parts[-1].replace('.', '')
        if len(last) == 1:
            initial     = last.upper()
            te_lastname = ' '.join(parts[:-1]).lower()
            for canonical, data in elo_db.items():
                cparts = canonical.split()
                if len(cparts) < 2 or cparts[0][0].upper() != initial:
                    continue
                if ' '.join(cparts[1:]).lower() == te_lastname:   # Strategy A
                    return canonical, data
                if cparts[-1].lower() == te_lastname:             # Strategy B
                    return canonical, data

    norm = normalize_name(player_name)
    for canonical, data in elo_db.items():
        if normalize_name(canonical) == norm:
            return canonical, data

    best_key, best_score = None, 0.0
    for canonical, data in elo_db.items():
        score = SequenceMatcher(None, norm, normalize_name(canonical)).ratio()
        if score > best_score:
            best_score, best_key = score, canonical
    if best_score >= threshold:
        return best_key, elo_db[best_key]
    return None, None


def elo_win_prob(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def get_surface_elo(record: dict, surface: str) -> float:
    key = {"clay": "cElo", "grass": "gElo", "hard": "hElo"}.get(surface, "elo")
    return record.get(key) or record.get("elo")


def prob_to_decimal_odds(prob: float) -> float:
    if prob <= 0: return 999.0
    return round(1.0 / prob, 2)


def surface_score(record: dict) -> int:
    return record.get("surface_score", 3)
