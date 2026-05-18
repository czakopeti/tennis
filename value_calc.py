import re
from difflib import SequenceMatcher

MINIMUM_EDGE   = 0.04
KELLY_FRACTION = 0.25
MAX_BET_PCT    = 0.03

SS_META = {
    1:{"icon":"🧱🧱","label":"Salakos spec.", "col":"#fb923c"},
    2:{"icon":"🧱",  "label":"Salak-hajlam", "col":"#fbbf24"},
    3:{"icon":"⚖",   "label":"All-rounder",  "col":"#94a3b8"},
    4:{"icon":"💙",  "label":"Kemeny-hajlam","col":"#60a5fa"},
    5:{"icon":"💙💙","label":"Kemeny spec.",  "col":"#818cf8"},
}


def normalize_name(name):
    return re.sub(r"[^a-z]", "", name.lower())


def find_player_in_elo_db(player_name, elo_db, threshold=0.75):
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
                if ' '.join(cparts[1:]).lower() == te_lastname:
                    return canonical, data
                if cparts[-1].lower() == te_lastname:
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


def elo_win_prob(elo_a, elo_b):
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def get_surface_elo(record, surface):
    key = {"clay":"cElo","grass":"gElo","hard":"hElo"}.get(surface, "elo")
    return record.get(key) or record.get("elo")


def prob_to_decimal_odds(prob):
    if prob <= 0: return 999.0
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


def surface_advantage(r1, r2, surface):
    """
    Original 3-condition surface advantage flag.
    Player 1 flagged if:
      (1) surface_elo1 > surface_elo2
      (2) surface_elo1 > other_elo1  (this IS their better surface)
      (3) other_elo2 > surface_elo2  (opponent is better on other surface)
    """
    c1 = r1.get("cElo") or 0; h1 = r1.get("hElo") or 0
    c2 = r2.get("cElo") or 0; h2 = r2.get("hElo") or 0
    g1 = r1.get("gElo") or 0; g2 = r2.get("gElo") or 0
    if not all([c1, h1, c2, h2]): return None
    if surface == "clay":
        if c1 > c2 and c1 > h1 and h2 > c2: return 1
        if c2 > c1 and c2 > h2 and h1 > c1: return 2
    elif surface == "hard":
        if h1 > h2 and h1 > c1 and c2 > h2: return 1
        if h2 > h1 and h2 > c2 and c1 > h1: return 2
    elif surface == "grass":
        o1 = max(c1, h1); o2 = max(c2, h2)
        if g1 and g2:
            if g1 > g2 and g1 > o1 and o2 > g2: return 1
            if g2 > g1 and g2 > o2 and o1 > g1: return 2
    return None


def surface_match(r1, r2, surface, edge1, edge2):
    """
    NEW: Surface Match signal — all 3 conditions must hold simultaneously:

    Condition 1: surface_elo(player) > surface_elo(opponent)
      -> player is stronger on this specific surface

    Condition 2: surface_score(player) <= surface_score(opponent)
      -> player is at least as "at home" on this surface
      -> lower score = better fit (1=clay spec on clay, 5=hard spec on clay=bad)
      -> equal score also counts (same comfort level but Elo still higher)

    Condition 3: edge < -0.03
      -> bookmaker UNDERPRICES the player by at least 3%
      -> book_odds < fair_odds  (market thinks player is even stronger)
      -> this is the "reverse value" signal: market knows something extra

    Returns: 1 if player1 flagged, 2 if player2 flagged, None if neither
    """
    sc1 = r1.get("surface_score", 3)
    sc2 = r2.get("surface_score", 3)

    se1 = get_surface_elo(r1, surface) or 0
    se2 = get_surface_elo(r2, surface) or 0

    if not se1 or not se2:
        return None

    # Check player 1
    cond1_p1 = se1 > se2                    # stronger on surface
    cond2_p1 = sc1 <= sc2                   # at least as comfortable on surface
    cond3_p1 = (edge1 is not None and edge1 < -0.03)  # market underprices

    if cond1_p1 and cond2_p1 and cond3_p1:
        return 1

    # Check player 2
    cond1_p2 = se2 > se1
    cond2_p2 = sc2 <= sc1
    cond3_p2 = (edge2 is not None and edge2 < -0.03)

    if cond1_p2 and cond2_p2 and cond3_p2:
        return 2

    return None
