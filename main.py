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
    "match_date", "is_tomorrow", "time", "tournament", "surface", "category",
    "tour", "player1", "player2", "name1", "name2", "seed1", "seed2",
    "rank1", "rank2", "c_elo1", "h_elo1", "c_elo2", "h_elo2",
    "surf_elo1", "surf_elo2", "surf_delta", "ss1", "ss2",
    "prob1", "odds1", "odds2", "book_odds_home", "book_odds_away",
    "edge1", "edge2", "sigs1", "sigs2", "court_cpi", "elo_found", "error",
]


def load_elo(tour):
    p = DATA_DIR / ("elo_ratings_%s.json" % tour)
    if not p.exists():
        return {}, {}
    d = json.loads(p.read_text())
    return d.get("players", d), {k: v for k, v in d.items() if k != "players"}


def hungarian_today():
    return (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%d")


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
        prev_results = {}
        if path.exists():
            try:
                old = json.loads(path.read_text())
                for m in old.get("matches", []):
                    if m.get("winner") is not None or m.get("retired"):
                        k = (m.get("player1"), m.get("player2"))
                        prev_results[k] = {
                            "winner":  m.get("winner"),
                            "score":   m.get("score"),
                            "sets":    m.get("sets"),
                            "retired": m.get("retired"),
                        }
            except Exception:
                pass

        for m in rows:
            hit = prev_results.get((m.get("player1"), m.get("player2")))
            if hit:
                m.update(hit)
            else:
                m.setdefault("winner", None)
                m.setdefault("score", None)

        path.write_text(json.dumps(
            {"date": date_str, "saved_at": datetime.now(timezone.utc).isoformat(),
             "matches": rows}, indent=2, ensure_ascii=False))
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

    # ── 4. Napi pillanatkep (backtesthez) ────────────────────────────
    print("\n=== 4. Elozmeny pillanatkep ===")
    save_history_snapshot(all_analyses)

    generate_html(atp_analyses, wta_analyses,
                  elo_meta=atp_meta, bankroll=args.bankroll)

    n_a = sum(1 for m in all_analyses
              if "A" in (m.get("sigs1") or []) or "A" in (m.get("sigs2") or []))
    n_b = sum(1 for m in all_analyses
              if "B" in (m.get("sigs1") or []) or "B" in (m.get("sigs2") or []))
    print("\n✅ ATP: %d | WTA: %d | 🎯 A: %d | 🔮 B: %d"
          % (len(atp_analyses), len(wta_analyses), n_a, n_b))


if __name__ == "__main__":
    main()
