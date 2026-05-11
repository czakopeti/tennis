"""
Daily orchestrator. Run via GitHub Actions cron.
Usage: python scripts/main.py [--bankroll 1000] [--skip-elo] [--skip-matches]
"""
import json, argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fetch_elo     import scrape_elo_ratings, save_elo_ratings
from fetch_matches import scrape_matches, save_matches
from generate_html import analyze_matches, generate_html

DATA_DIR = Path(__file__).parent.parent / "data"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bankroll",     type=float, default=1000.0)
    p.add_argument("--skip-elo",     action="store_true")
    p.add_argument("--skip-matches", action="store_true")
    args = p.parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    elo_path     = DATA_DIR / "elo_ratings.json"
    matches_path = DATA_DIR / "todays_matches.json"

    # ── Step 1: Elo (weekly, or forced) ──────────────────────────────────
    print("\n=== Elo Ratings ===")
    if args.skip_elo and elo_path.exists():
        print("[main] Using cached Elo")
        with open(elo_path) as f:
            elo_data = json.load(f)
    else:
        elo_players = scrape_elo_ratings()
        save_elo_ratings(elo_players)
        with open(elo_path) as f:
            elo_data = json.load(f)

    elo_players = elo_data.get("players", elo_data)  # backward compat
    elo_meta    = {k: v for k, v in elo_data.items() if k != "players"}

    # ── Step 2: Today's matches ───────────────────────────────────────────
    print("\n=== Today's Matches ===")
    if args.skip_matches and matches_path.exists():
        print("[main] Using cached matches")
        with open(matches_path) as f:
            matches = json.load(f)
    else:
        matches = scrape_matches()
        save_matches(matches)

    # ── Step 3: Enrich with Elo ───────────────────────────────────────────
    print("\n=== Analysis ===")
    analyses = analyze_matches(matches, elo_players)

    with open(DATA_DIR / "todays_analysis.json", "w") as f:
        json.dump(analyses, f, indent=2, default=str)

    # ── Step 4: Generate HTML ─────────────────────────────────────────────
    print("\n=== Generating HTML ===")
    generate_html(analyses, elo_meta=elo_meta, bankroll=args.bankroll)

    found   = sum(1 for a in analyses if a.get("elo_found"))
    missing = [a for a in analyses if not a.get("elo_found")]
    print(f"\n✅ Done: {len(analyses)} meccs, {found} Elo lefedve")
    if missing:
        print(f"⚠  Hiányzó Elo: {', '.join(m['player1']+' / '+m['player2'] for m in missing)}")


if __name__ == "__main__":
    main()
