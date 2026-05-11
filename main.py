"""
Napi orchestrator. GitHub Actions futtatja.
python main.py [--bankroll 1000] [--skip-elo] [--skip-matches]
"""
import json, argparse, sys
from pathlib import Path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from fetch_elo     import scrape_with_fallback, scrape_elo_ratings, save_elo_ratings
from fetch_matches import scrape_matches, save_matches
from generate_html import analyze_matches, generate_html

DATA_DIR = ROOT / "data"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bankroll",     type=float, default=1000.0)
    p.add_argument("--skip-elo",     action="store_true")
    p.add_argument("--skip-matches", action="store_true")
    args = p.parse_args()
    DATA_DIR.mkdir(exist_ok=True)

    elo_path     = DATA_DIR / "elo_ratings.json"
    matches_path = DATA_DIR / "todays_matches.json"

    # ── 1. Elo ──────────────────────────────────────────────────────────
    print("\n=== 1. Elo Ratings ===")
    if args.skip_elo and elo_path.exists():
        print("[main] Cached Elo")
    else:
        scrape_with_fallback()  # nem crashel ha 403

    if not elo_path.exists():
        print("[main] HIBA: nincs elo_ratings.json - pipeline leáll")
        sys.exit(1)

    elo_data    = json.loads(elo_path.read_text())
    elo_players = elo_data.get("players", elo_data)
    elo_meta    = {k: v for k, v in elo_data.items() if k != "players"}

    # ── 2. Meccsek ──────────────────────────────────────────────────────
    print("\n=== 2. Mai meccsek ===")
    if args.skip_matches and matches_path.exists():
        print("[main] Cached meccsek")
        matches = json.loads(matches_path.read_text())
    else:
        matches = scrape_matches()
        save_matches(matches)

    # ── 3. HTML ─────────────────────────────────────────────────────────
    print("\n=== 3. HTML generálás ===")
    analyses = analyze_matches(matches, elo_players)
    (DATA_DIR / "todays_analysis.json").write_text(
        json.dumps(analyses, indent=2, default=str))
    generate_html(analyses, elo_meta=elo_meta, bankroll=args.bankroll)

    found   = sum(1 for a in analyses if a.get("elo_found"))
    missing = [a for a in analyses if not a.get("elo_found")]
    print(f"\n✅ Kész: {len(analyses)} meccs, {found} Elo lefedve")
    if missing:
        print(f"⚠  Hiányzó: {[m['player1']+'/'+m['player2'] for m in missing]}")


if __name__ == "__main__":
    main()
