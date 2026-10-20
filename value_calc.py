import re
import unicodedata
from difflib import SequenceMatcher

MINIMUM_EDGE   = 0.04     # zold VALUE kuszob
KELLY_FRACTION = 0.25
MAX_BET_PCT    = 0.03

# ── Badge kuszobok ────────────────────────────────────────────────────────
# A 916 soros sajat adatbazison (2026-08-19 .. 10-16) mert szabaly.
#
# ALAPBADGE   — rosszabb ranglistas helyezes
#             + a kapott bukmekeri odds >= a sajat fair oddsunk
#             + a bukmekeri odds <= 3.25
#             169 fogadas, 49.7% talalat (43.3% kellett), ROI +18.3%, p=5.2%
#
# SZUPERBADGE — ugyanaz + a ket helyezes aranya >= 1.5x
#             95 fogadas, 51.6% talalat (41.3% kellett), ROI +27.5%, p=2.3%
#             aug +41.9% / szept-okt +16.6%  (ATP +20.5% / +20.4%)
#
# A szuperbadge indoklasa nem a hozambol, hanem AR-MERESBOL jon: a piac a
# ranking-szakadek novekedesevel rendszeresen elhajlitja az arat a rosszabb
# rangsoru ellen (logit-regresszio: -0.068 / ln(arany), t=-3.64, ATP es WTA
# kulon is szignifikans). A kizart resz (arany < 1.5x) mindket felidoben
# negativ volt: szept-okt -28.8%.
#
# A ket szint EGYMASBA AGYAZOTT: SZUPER ⊂ ALAP.
# Realis varhato ROI: +3..+6%, NEM a mert +18/+27%.
BADGE_MAX_ODDS   = 3.25   # bukmekeri odds felso hatara (mindket badge)
BADGE_RANK_RATIO = 1.5    # szuperbadge: rosszabb helyezes / jobb helyezes

BADGE_META = {
    "szuper": {"icon": "🏆", "label": "SZUPER",
               "desc": "rosszabb ranking + value + odds &le;3.25 + ranking-arany &ge;1.5x"},
    "alap":   {"icon": "🎯", "label": "ALAP",
               "desc": "rosszabb ranking + value + odds &le;3.25"},
}
BADGE_ORDER = ["szuper", "alap"]   # legerosebb elol

# ── Teszt-medence ─────────────────────────────────────────────────────────
# Az ATP 250-es tornak NEM reszei annak a populacionak, amin a szabaly
# szuletett (GS / M1000 / 500).  Ott gyengebb a mezony es kevesebb meccsbol
# keszul a jatekosok Elo-ja, tehat a modellunk varhatoan pontatlanabb.
# A badge megjelenik rajtuk, de TESZT jelolessel, es kulon merjuk.
# Amig nincs sajat mintajuk, NEM fogadando.
TEST_CATEGORIES = {"A250"}


def is_test_pool(category):
    return (category or "") in TEST_CATEGORIES

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

def rank_ratio(rank_a, rank_b):
    """
    A ket ranglistas helyezes aranya: a rosszabb (nagyobb szam) / a jobb.
    Mindig >= 1.0.  Pl. 60. vs 50. -> 1.20;  170. vs 20. -> 8.50.
    None, ha valamelyik helyezes hianyzik.
    """
    try:
        a, b = int(rank_a), int(rank_b)
    except (TypeError, ValueError):
        return None
    if a <= 0 or b <= 0:
        return None
    return max(a, b) / float(min(a, b))


def player_badge(rank_self, rank_opp, book_odds, fair_odds):
    """
    Egyetlen jatekos badge-szintje.

    Feltetelek (mindket badge):
      1. a jatekos ranglistas helyezese ROSSZABB (nagyobb szam) az ellenfeleenel
      2. a kapott bukmekeri odds >= a modellbol szamolt fair odds
      3. a bukmekeri odds <= BADGE_MAX_ODDS (3.25)

    Szuperbadge: a fentiek + rank_ratio >= BADGE_RANK_RATIO (1.5x)

    Visszater: "szuper" | "alap" | None
    """
    if book_odds is None or fair_odds is None:
        return None
    if rank_self is None or rank_opp is None:
        return None
    try:
        rs, ro = int(rank_self), int(rank_opp)
    except (TypeError, ValueError):
        return None
    if rs <= 0 or ro <= 0 or rs <= ro:          # 1. rosszabb ranking kell
        return None
    if fair_odds <= 0 or book_odds < fair_odds:  # 2. value kell
        return None
    if book_odds > BADGE_MAX_ODDS:               # 3. odds-plafon
        return None
    rr = rank_ratio(rs, ro)
    if rr is not None and rr >= BADGE_RANK_RATIO:
        return "szuper"
    return "alap"


def bet_signals(r1, r2, edge1, edge2, book1, book2,
                prob1=None, fair1=None, fair2=None,
                rank1=None, rank2=None):
    """
    Badge-szintek mindket jatekosra.
    Visszater: (sigs1, sigs2) — halmazok, pl. {"szuper"} vagy ures halmaz.
    (Halmazkent adjuk vissza, hogy a history/export formatum valtozatlan
     maradjon; a regi "eros"/"kozepes"/"alap" tierek megszuntek.)
    """
    if fair1 is None or fair2 is None:
        return set(), set()
    b1 = player_badge(rank1, rank2, book1, fair1)
    b2 = player_badge(rank2, rank1, book2, fair2)
    return ({b1} if b1 else set()), ({b2} if b2 else set())
