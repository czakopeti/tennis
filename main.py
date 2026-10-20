"""Napi orchestrator — ATP + WTA."""
import json, argparse, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from fetch_elo     import scrape_with_fallback
from fetch_matches import scrape_matches, save_matches
from generate_html import analyze_matches, generate_html

DATA_DIR = ROOT / "data"
HIST_DIR = DATA_DIR / "history"

# A pillanatkepbe mentendo mezok (a nyers Elo rekordokat kihagyjuk)
SNAP_FIELDS = [
    "match_date", "is_tomorrow", "time_unknown", "time", "tournament", "surface", "category",
    "tour", "player1", "player2", "name1", "name2", "seed1", "seed2",
    "rank1", "rank2", "rank_ratio", "test_pool",
    "c_elo1", "h_elo1", "c_elo2", "h_elo2",
    "surf_elo1", "surf_elo2", "surf_delta", "ss1", "ss2",
    "prob1", "odds1", "odds2", "book_odds_home", "book_odds_away",
    "edge1", "edge2", "sigs1", "sigs2", "court_cpi", "elo_found", "error",
    # ── Sticky badge: egyszer megszolal, utana nem tunik el ──────────
    # A *_odds / *_sodds a badge MEGSZOLALASAKORI bukmekeri odds — ez a
    # beszallasi ar, amivel a visszameres szamol. Soha nem iruk at.
    "badge1", "badge1_odds", "badge1_sodds", "badge1_seen", "badge1_rkr", "badge1_live",
    "badge2", "badge2_odds", "badge2_sodds", "badge2_seen", "badge2_rkr", "badge2_live",
]

# Ezeket a mezoket a sticky logika egyszeri beirás után vedi.
STICKY_KEEP = ("badge1", "badge1_odds", "badge1_sodds", "badge1_seen", "badge1_rkr",
               "badge2", "badge2_odds", "badge2_sodds", "badge2_seen", "badge2_rkr")


def load_elo(tour):
    p = DATA_DIR / ("elo_ratings_%s.json" % tour)
    if not p.exists():
        return {}, {}
    d = json.loads(p.read_text())
    return d.get("players", d), {k: v for k, v in d.items() if k != "players"}


def hungarian_today():
    return (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%d")


BADGE_RANKS = {"szuper": 2, "alap": 1}


def _badge_of(sigs):
    s = set(sigs or [])
    if "szuper" in s:
        return "szuper"
    if "alap" in s:
        return "alap"
    return None


def apply_sticky_badges(analyses):
    """
    A badge egyszer megszolal, utana NEM tunik el.

    Minden futasnal beolvassa az adott nap meglevo history fajljat, es ha ott
    mar szerepel badge, visszateszi az elemzesbe — akkor is, ha a mostani odds
    mar nem adna ki (pl. beesett az ar).

    A badge-kori bukmekeri odds / fair odds / ranking-arany SOHA nem irodik at:
    az a beszallasi ar, amivel a visszameres szamol.  Igy kulon merheto az
    ALAP es a SZUPER badge a sajat belepesi aran.

    A sigs1/sigs2 a "valaha megszolalt" badge-et hordozza — ezt latja a
    megjelenites es ezt szamolja a statisztika.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    # nap -> {(p1, p2): tortenelmi sor}
    hist = {}
    for a in analyses:
        d = a.get("match_date") or hungarian_today()
        if d in hist:
            continue
        path = HIST_DIR / ("%s.json" % d)
        rows = {}
        if path.exists():
            try:
                for m in json.loads(path.read_text()).get("matches", []):
                    rows[(m.get("player1"), m.get("player2"))] = m
            except Exception:
                pass
        hist[d] = rows

    restored = fresh = 0
    for a in analyses:
        d   = a.get("match_date") or hungarian_today()
        key = (a.get("player1"), a.get("player2"))
        old = hist.get(d, {}).get(key)
        flipped = False
        if old is None:
            old = hist.get(d, {}).get((key[1], key[0]))
            flipped = old is not None

        for side in (1, 2):
            osid = (3 - side) if flipped else side     # a tortenelmi sorban melyik oldal
            cur  = _badge_of(a.get("sigs%d" % side))
            prev = (old or {}).get("badge%d" % osid)

            def oget(suffix):
                return (old or {}).get("badge%d%s" % (osid, suffix))

            b_odds  = oget("_odds")
            b_sodds = oget("_sodds")
            b_seen  = oget("_seen")
            b_rkr   = oget("_rkr")

            # Uj ALAP megszolalas (korabban semmi): rogzitjuk a belepesi arat.
            if cur and not prev:
                b_odds = a.get("book_odds_home") if side == 1 else a.get("book_odds_away")
                b_seen = now
                b_rkr  = a.get("rank_ratio")
                fresh += 1
            # Felminosules ALAP -> SZUPER: a szuper sajat belepesi ara.
            if cur == "szuper" and b_sodds is None:
                b_sodds = a.get("book_odds_home") if side == 1 else a.get("book_odds_away")

            # A legerosebb valaha latott szint nyer.
            best = max([x for x in (cur, prev) if x],
                       key=lambda b: BADGE_RANKS[b], default=None)
            if best and not cur:
                restored += 1

            a["badge%d" % side]        = best
            a["badge%d_odds" % side]   = b_odds
            a["badge%d_sodds" % side]  = b_sodds
            a["badge%d_seen" % side]   = b_seen
            a["badge%d_rkr" % side]    = b_rkr
            a["badge%d_live" % side]   = bool(cur) and cur == best
            a["sigs%d" % side]         = [best] if best else []

    if fresh or restored:
        print("[sticky] %d uj badge rogzitve, %d megorzve a historybol"
              % (fresh, restored))
    return analyses


def save_history_snapshot(analyses):
    """
    Napi pillanatkep meccs elott — MINDEN meccs, nem csak a jeloltek.
    A fetch_results.py ezt egesziti ki masnap az eredmenyekkel.
    Ha a fajl mar letezik, a mar bejegyzett eredmenyeket megorzi.
    """
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    by_date = {}
    for a in analyses:
        d = a.get("match_date") or hungarian_today()
        by_date.setdefault(d, []).append({k: a.get(k) for k in SNAP_FIELDS})

    for date_str, rows in by_date.items():
        path = HIST_DIR / ("%s.json" % date_str)
        prev_results, prev_rows = {}, {}
        if path.exists():
            try:
                old = json.loads(path.read_text())
                for m in old.get("matches", []):
                    k = (m.get("player1"), m.get("player2"))
                    prev_rows[k] = m
                    if m.get("winner") is not None or m.get("retired"):
                        prev_results[k] = {
                            "winner":  m.get("winner"),
                            "score":   m.get("score"),
                            "sets":    m.get("sets"),
                            "retired": m.get("retired"),
                        }
            except Exception:
                pass

        seen = set()
        for m in rows:
            k = (m.get("player1"), m.get("player2"))
            seen.add(k)
            hit = prev_results.get(k)
            if hit:
                m.update(hit)
            else:
                m.setdefault("winner", None)
                m.setdefault("score", None)
            # A sticky badge mezoket, ha egyszer be voltak irva, nem engedjuk
            # None-ra visszaesni (pl. ha a jelenlegi futasban hianyos az adat).
            old_row = prev_rows.get(k)
            if old_row:
                for f in STICKY_KEEP:
                    if m.get(f) in (None, "", []) and old_row.get(f) not in (None, "", []):
                        m[f] = old_row[f]

        # Append-only: ami egyszer bekerult a naplo-ba, az nem eshet ki
        # (pl. befejezodott meccs lekerul a napi listarol). Igy sem a
        # badge, sem a mar rogzitett eredmeny nem veszik el.
        kept = 0
        for k, old_row in prev_rows.items():
            if k not in seen:
                rows.append(old_row)
                kept += 1
        if kept:
            print("[history] %s — %d korabbi sor megorizve" % (path.name, kept))

        rows.sort(key=lambda m: (str(m.get("time") or "99:99"),
                                 str(m.get("player1") or "")))

        payload = json.dumps({"date": date_str, "matches": rows},
                             indent=2, ensure_ascii=False, sort_keys=True)
        # Csak akkor irunk, ha tenylegesen valtozott a tartalom.
        # (A saved_at idobelyeg kihagyva, kulonben minden futas "valtozas" lenne.)
        if path.exists():
            try:
                old_payload = json.dumps(
                    {"date": json.loads(path.read_text()).get("date"),
                     "matches": json.loads(path.read_text()).get("matches")},
                    indent=2, ensure_ascii=False, sort_keys=True)
                if old_payload == payload:
                    print("[history] %s — valtozatlan, kihagyva" % path.name)
                    continue
            except Exception:
                pass
        path.write_text(payload)
        print("[history] %s — %d meccs mentve" % (path.name, len(rows)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bankroll",     type=float, default=1000.0)
    p.add_argument("--skip-elo",     action="store_true")
    p.add_argument("--skip-matches", action="store_true")
    p.add_argument("--no-tomorrow",  action="store_true",
                   help="ne huzza le a holnap hajnali meccseket")
    args = p.parse_args()

    DATA_DIR.mkdir(exist_ok=True)

    # ── 1. Elo ───────────────────────────────────────────────────────
    print("\n=== 1. Elo Ratings ===")
    if not args.skip_elo:
        scrape_with_fallback("atp")
        scrape_with_fallback("wta")
    else:
        print("[main] Cached Elo")

    atp_players, atp_meta = load_elo("atp")
    wta_players, wta_meta = load_elo("wta")
    if not atp_players:
        print("[main] HIBA: nincs ATP Elo adat")
        sys.exit(1)

    # ── 2. Meccsek ───────────────────────────────────────────────────
    print("\n=== 2. Meccsek ===")
    matches_path = DATA_DIR / "todays_matches.json"
    if args.skip_matches and matches_path.exists():
        matches = json.loads(matches_path.read_text())
        print("[main] Cached: %d meccs" % len(matches))
    else:
        matches = scrape_matches(include_tomorrow_early=not args.no_tomorrow)
        save_matches(matches)

    # ── 3. Elemzes ───────────────────────────────────────────────────
    print("\n=== 3. Elemzes + HTML ===")
    atp_matches = [m for m in matches if m.get("tour", "ATP") == "ATP"]
    wta_matches = [m for m in matches if m.get("tour") == "WTA"]

    atp_analyses = analyze_matches(atp_matches, atp_players)
    wta_analyses = analyze_matches(wta_matches, wta_players) if wta_players else []
    all_analyses = atp_analyses + wta_analyses

    (DATA_DIR / "todays_analysis.json").write_text(
        json.dumps(all_analyses, indent=2, default=str))

    # ── 4. Sticky badge + napi pillanatkep (backtesthez) ─────────────
    print("\n=== 4. Badge megorzes + elozmeny pillanatkep ===")
    apply_sticky_badges(all_analyses)
    save_history_snapshot(all_analyses)

    generate_html(atp_analyses, wta_analyses,
                  elo_meta=atp_meta, bankroll=args.bankroll)

    n_sz = sum(1 for m in all_analyses
               for k in ("sigs1", "sigs2") if "szuper" in (m.get(k) or []))
    n_al = sum(1 for m in all_analyses
               for k in ("sigs1", "sigs2") if "alap" in (m.get(k) or []))
    print("\n✅ ATP: %d | WTA: %d | 🏆 Szuper: %d | 🎯 Alap: %d | jeloles osszesen: %d"
          % (len(atp_analyses), len(wta_analyses), n_sz, n_al, n_sz + n_al))


if __name__ == "__main__":
    main()
