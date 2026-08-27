import re
import unicodedata
from difflib import SequenceMatcher

MINIMUM_EDGE   = 0.04     # zold VALUE kuszob
KELLY_FRACTION = 0.25
MAX_BET_PCT    = 0.03

# ── Value-jelolt kuszobok ─────────────────────────────────────────────────
# Ket fuggetlen prospektiv teszten (aug 25-26) validalt szabalyok.
# Kozos feltetel MINDHAROMNAL: a kapott odds >= a sajat fair oddsunk.
# A harom szint egymasba agyazott: EROS ⊂ KOZEPES ⊂ ALAP.
TIER_STRONG = 0.60   # 💎 EROS    — teszt: 21/25 = 84.0%, ROI +28.8%, p=4.0%
TIER_MEDIUM = 0.55   # 🔷 KOZEPES — teszt: 25/31 = 80.6%, ROI +29.5%, p=2.6%
TIER_BASE   = 0.50   # 🔹 ALAP    — teszt: 30/42 = 71.4%, ROI +22.4%, p=4.8%

TIER_META = {
    "eros":    {"icon": "💎", "label": "EROS",    "min": TIER_STRONG},
    "kozepes": {"icon": "🔷", "label": "KOZEPES", "min": TIER_MEDIUM},
    "alap":    {"icon": "🔹", "label": "ALAP",    "min": TIER_BASE},
}

SS9_META = {
    1: {"icon": "🧱🧱🧱", "label": "Extrem salak"},
    2: {"icon": "🧱🧱",   "label": "Eros salakos"},
    3: {"icon": "🧱",     "label": "Salak-hajlam"},
    4: {"icon": "🔸",     "label": "Enyhe salak"},
    5: {"icon": "⚖",      "label": "All-rounder"},
    6: {"icon": "🔹",     "label": "Enyhe gyors"},
    7: {"icon": "💙",     "label": "Gyors-hajlam"},
    8: {"icon": "💙💙",   "label": "Eros gyors"},
    9: {"icon": "💙💙💙", "label": "Extrem gyors"},
}

COURT_CPI = {
    "french open": 21, "roland garros": 21, "wimbledon": 37,
    "us open": 43, "australian open": 43,
    "monte carlo": 29, "madrid": 28, "rome": 28, "italian open": 28,
    "indian wells": 36, "miami": 39, "canada": 41, "montreal": 41,
    "toronto": 41, "cincinnati": 40, "shanghai": 38,
    "paris": 40, "paris masters": 40, "atp finals": 41,
    "halle": 38, "queens": 38, "london": 38,
    "eastbourne": 37, "s-hertogenbosch": 37, "berlin": 37,
    "bad homburg": 37, "stuttgart": 38, "nottingham": 37,
    "default_clay": 27, "default_hard": 37,
    "default_indoor": 41, "default_grass": 37,
}


# ══ Nevegyeztetes ════════════════════════════════════════════════════════

def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def _key(s):
    """Osszehasonlitasi kulcs: ekezet / aposztrof / kotojel / szokoz nelkul."""
    return re.sub(r"[^a-z0-9]", "", _strip_accents(s).lower())


def normalize_name(name):
    return _key(name)


def find_player_in_elo_db(player_name, elo_db, threshold=0.72):
    """
    TennisExplorer nev -> tennisabstract kanonikus nev.

    Strategy A: "Vezeteknev X." alak (a TE ezt hasznalja)
                - keresztnev kezdobetu egyezes
                - vezeteknev egyezes normalizalt kulcson
                  (kezeli: O'Connell/Oconnell, McDonald/MacDonald, ekezetek)
                - ha nincs egzakt, 0.85 folotti fuzzy a vezeteknevre
    Strategy B: teljes nev egzakt egyezes normalizalva
    Strategy C: fuzzy teljes nev (threshold folott)
    """
    raw   = player_name.strip().rstrip(".")
    parts = raw.split()

    # ── A: "Lastname X." ─────────────────────────────────────────────
    if len(parts) >= 2:
        last_tok = parts[-1].replace(".", "")
        if len(last_tok) == 1:
            initial = _key(last_tok)
            te_last = _key(" ".join(parts[:-1]))
            fuzzy_hit, fuzzy_score = None, 0.0
            for canonical, data in elo_db.items():
                cparts = canonical.split()
                if len(cparts) < 2:
                    continue
                if _key(cparts[0])[:1] != initial:
                    continue
                cand_full = _key(" ".join(cparts[1:]))
                cand_last = _key(cparts[-1])
                if te_last in (cand_full, cand_last):
                    return canonical, data
                for cand in (cand_full, cand_last):
                    s = SequenceMatcher(None, te_last, cand).ratio()
                    if s > fuzzy_score:
                        fuzzy_score, fuzzy_hit = s, canonical
            if fuzzy_score >= 0.85 and fuzzy_hit:
                return fuzzy_hit, elo_db[fuzzy_hit]

    # ── B: teljes nev egzakt ─────────────────────────────────────────
    nk = _key(raw)
    for canonical, data in elo_db.items():
        if _key(canonical) == nk:
            return canonical, data

    # ── C: fuzzy teljes nev ──────────────────────────────────────────
    best_key, best_score = None, 0.0
    for canonical in elo_db:
        s = SequenceMatcher(None, nk, _key(canonical)).ratio()
        if s > best_score:
            best_score, best_key = s, canonical
    if best_score >= threshold and best_key:
        return best_key, elo_db[best_key]
    return None, None


# ══ Elo / odds ═══════════════════════════════════════════════════════════

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


def get_player_rank(record):
    for k in ("atp_rank", "wta_rank", "rank"):
        v = record.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
    return None


def get_court_cpi(tournament_name, surface):
    name = (tournament_name or "").lower().strip()
    for key, cpi in COURT_CPI.items():
        if key.startswith("default_"):
            continue
        if key in name or name in key:
            return cpi
    surf = (surface or "").lower()
    if surf == "clay":
        return COURT_CPI["default_clay"]
    if surf == "grass":
        return COURT_CPI["default_grass"]
    if "indoor" in name:
        return COURT_CPI["default_indoor"]
    return COURT_CPI["default_hard"]


def player_ss9(record, surface="clay"):
    """
    1-9 boritas-preferencia, mindig cElo - hElo alapjan.
    1-4 = salakos, 5 = all-rounder, 6-9 = gyors palyas.
    Torna boritastol fuggetlen: megmutatja, otthon van-e a jatekos.
    """
    celo  = record.get("cElo") or 1500
    helo  = record.get("hElo") or 1500
    delta = celo - helo
    if delta > 150:  return 1
    if delta > 80:   return 2
    if delta > 30:   return 3
    if delta > 10:   return 4
    if delta > -10:  return 5
    if delta > -30:  return 6
    if delta > -80:  return 7
    if delta > -150: return 8
    return 9


# ══ Badge logika ═════════════════════════════════════════════════════════

def value_tier(prob, book_odds, fair_odds):
    """
    Egyetlen jatekos value-szintje.

    Kozos feltetel: a kapott bukmekeri odds >= a modellbol szamolt fair odds.
    (Azaz a piac legalabb annyit fizet, amennyit a modell indokolna.)

    Ezen belul a modell magabiztossaga szerint harom szint:
        prob > 60%  -> "eros"
        prob > 55%  -> "kozepes"
        prob > 50%  -> "alap"

    Visszater: "eros" | "kozepes" | "alap" | None
    """
    if book_odds is None or fair_odds is None:
        return None
    if fair_odds <= 0 or book_odds < fair_odds:
        return None
    if prob > TIER_STRONG:
        return "eros"
    if prob > TIER_MEDIUM:
        return "kozepes"
    if prob > TIER_BASE:
        return "alap"
    return None


def bet_signals(r1, r2, edge1, edge2, book1, book2,
                prob1=None, fair1=None, fair2=None):
    """
    Value-jelolt szintek mindket jatekosra.
    Visszater: (sigs1, sigs2) — halmazok, pl. {"eros"} vagy ures halmaz.
    (Halmazkent adjuk vissza, hogy a korabbi history/export formatum
     valtozatlan maradjon.)
    """
    if prob1 is None or fair1 is None or fair2 is None:
        return set(), set()
    t1 = value_tier(prob1,     book1, fair1)
    t2 = value_tier(1 - prob1, book2, fair2)
    return ({t1} if t1 else set()), ({t2} if t2 else set())
