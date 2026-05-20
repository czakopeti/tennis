import re
from difflib import SequenceMatcher

MINIMUM_EDGE   = 0.04
KELLY_FRACTION = 0.25
MAX_BET_PCT    = 0.03

SS_META = {
    1:{"icon":"🧱🧱","label":"Salakos spec.", "col":"#fb923c"},
    2:{"icon":"🧱",  "label":"Salak-hajlam",  "col":"#fbbf24"},
    3:{"icon":"⚖",   "label":"All-rounder",   "col":"#94a3b8"},
    4:{"icon":"💙",  "label":"Kemeny-hajlam",  "col":"#60a5fa"},
    5:{"icon":"💙💙","label":"Kemeny spec.",    "col":"#818cf8"},
}

SURFACE_SS_ALLOWED = {
    "clay":  {1, 2, 3},
    "hard":  {3, 4, 5},
    "grass": {2, 3, 4},
}


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
        score = SequenceMatcher(None, norm, normalize_name(canonical)).ratio()
        if score > best_score:
            best_score, best_key = score, canonical
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


def surface_advantage(r1, r2, surface):
    """Original 3-condition surface advantage flag."""
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
    Surface Match: 4 conditions simultaneously for Player 1:
      1. surface_elo1 - surface_elo2 >= 15
      2. surface_score1 <= surface_score2
      3. surface_score1 in allowed set for surface
      4. edge1 < -0.03  (book underprices player1 by >=3%)
    """
    sc1 = r1.get("surface_score", 3)
    sc2 = r2.get("surface_score", 3)
    se1 = get_surface_elo(r1, surface) or 0
    se2 = get_surface_elo(r2, surface) or 0
    if not se1 or not se2: return None
    allowed = SURFACE_SS_ALLOWED.get(surface, {1,2,3,4,5})

    if (se1 - se2 >= 15 and sc1 <= sc2 and
            sc1 in allowed and edge1 is not None and edge1 < -0.03):
        return 1
    if (se2 - se1 >= 15 and sc2 <= sc1 and
            sc2 in allowed and edge2 is not None and edge2 < -0.03):
        return 2
    return None


def extra_signals(r1, r2, surface, edge1, edge2, prob1, prob2):
    """
    3 new signals — returned as (sig1, sig2) tuple per signal.
    Each sig can be: None | "b1" | "b2" | "b3"

    BADGE 1 — for player P:
      surface_elo(P) > surface_elo(opponent) by >=1 pt
      ss(P) in allowed set for this surface
      P's ranking is WORSE (higher number) than opponent
      opponent's edge > 0%   (book underprices opponent)

    BADGE 2 — for player P:
      surface_elo(P) > surface_elo(opponent) by >=1 pt
      ss(P) in allowed set for this surface
      P's ranking is BETTER (lower number) than opponent
      opponent's edge > +7%  (book underprices opponent by >7%)

    BADGE 3 — for player P:
      P's ranking is WORSE (higher number) than opponent
      Elo says P is favorite  (prob > 50%)
      P's own edge > 0%       (book underprices P)

    Returns: (signal_for_p1, signal_for_p2)
      Each element is a set of badge names that apply, e.g. {"b1","b3"}
    """
    rank1 = r1.get("atp_rank")
    rank2 = r2.get("atp_rank")
    se1   = get_surface_elo(r1, surface) or 0
    se2   = get_surface_elo(r2, surface) or 0
    sc1   = r1.get("surface_score", 3)
    sc2   = r2.get("surface_score", 3)
    allowed = SURFACE_SS_ALLOWED.get(surface, {1,2,3,4,5})

    sigs1, sigs2 = set(), set()

    if rank1 is None or rank2 is None:
        return sigs1, sigs2

    # ── Badge 1 checks ─────────────────────────────────────────────────
    # Player 1 gets B1 if:
    #   surface Elo better by >=1, ss ok, rank WORSE, opp edge > 0
    if (se1 - se2 >= 1 and sc1 in allowed and
            rank1 > rank2 and
            edge2 is not None and edge2 > 0):
        sigs1.add("b1")
    # Player 2 gets B1
    if (se2 - se1 >= 1 and sc2 in allowed and
            rank2 > rank1 and
            edge1 is not None and edge1 > 0):
        sigs2.add("b1")

    # ── Badge 2 checks ─────────────────────────────────────────────────
    # Player 1 gets B2 if:
    #   surface Elo better by >=1, ss ok, rank BETTER, opp edge > 7%
    if (se1 - se2 >= 1 and sc1 in allowed and
            rank1 < rank2 and
            edge2 is not None and edge2 > 0.07):
        sigs1.add("b2")
    # Player 2 gets B2
    if (se2 - se1 >= 1 and sc2 in allowed and
            rank2 < rank1 and
            edge1 is not None and edge1 > 0.07):
        sigs2.add("b2")

    # ── Badge 3 checks ─────────────────────────────────────────────────
    # Player 1 gets B3 if:
    #   rank WORSE, Elo favorite, own edge > 0
    if (rank1 > rank2 and
            prob1 > 0.50 and
            edge1 is not None and edge1 > 0):
        sigs1.add("b3")
    # Player 2 gets B3
    if (rank2 > rank1 and
            prob2 > 0.50 and
            edge2 is not None and edge2 > 0):
        sigs2.add("b3")

    return sigs1, sigs2
