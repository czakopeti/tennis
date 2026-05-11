"""Napi orchestrator — ATP + WTA."""
import json, argparse, sys
from pathlib import Path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from fetch_elo     import scrape_with_fallback
from fetch_matches import scrape_matches, save_matches
from generate_html import analyze_matches, generate_html

DATA_DIR = ROOT / "data"


def load_elo(tour):
    p = DATA_DIR / f"elo_ratings_{tour}.json"
    if not p.exists(): return {}, {}
    d = json.loads(p.read_text())
    return d.get("players", d), {k:v for k,v in d.items() if k!="players"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bankroll",     type=float, default=1000.0)
    p.add_argument("--skip-elo",     action="store_true")
    p.add_argument("--skip-matches", action="store_true")
    args = p.parse_args()
    DATA_DIR.mkdir(exist_ok=True)

    # ── 1. Elo ──────────────────────────────────────────────────────────
    print("\n=== 1. Elo Ratings ===")
    if not args.skip_elo:
        scrape_with_fallback("atp")
        scrape_with_fallback("wta")
    else:
        print("[main] Cached Elo")

    atp_players, atp_meta = load_elo("atp")
    wta_players, wta_meta = load_elo("wta")

    if not atp_players:
        print("[main] HIBA: nincs ATP Elo adat"); sys.exit(1)

    # ── 2. Meccsek ──────────────────────────────────────────────────────
    print("\n=== 2. Meccsek ===")
    matches_path = DATA_DIR / "todays_matches.json"
    if args.skip_matches and matches_path.exists():
        matches = json.loads(matches_path.read_text())
        print(f"[main] Cached: {len(matches)} meccs")
    else:
        matches = scrape_matches()
        save_matches(matches)

    # ── 3. Elemzés ───────────────────────────────────────────────────────
    print("\n=== 3. Elemzés + HTML ===")
    atp_matches = [m for m in matches if m.get("tour","ATP") == "ATP"]
    wta_matches = [m for m in matches if m.get("tour") == "WTA"]

    atp_analyses = analyze_matches(atp_matches, atp_players)
    wta_analyses = analyze_matches(wta_matches, wta_players) if wta_players else []

    all_analyses = atp_analyses + wta_analyses
    (DATA_DIR / "todays_analysis.json").write_text(
        json.dumps(all_analyses, indent=2, default=str))

    generate_html(atp_analyses, wta_analyses,
                  elo_meta=atp_meta, bankroll=args.bankroll)

    print(f"\n✅ ATP: {len(atp_analyses)} meccs | WTA: {len(wta_analyses)} meccs")


if __name__ == "__main__":
    main()
