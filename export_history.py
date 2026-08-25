"""
export_history.py — A teljes data/history/ egyetlen tomor CSV-be.

Futtatas:
    python export_history.py                  # csak lezart meccsek
    python export_history.py --all            # a meg nem jatszottak is
    python export_history.py --days 14        # csak az utolso 14 nap
    python export_history.py --quiet          # ne irja a kepernyore

Kimenet:
    data/history_export.csv   (a repoban megnyithato / letoltheto)
    + a kepernyore is kiirja, hogy az Actions logbol masolhato legyen
"""
import json, csv, io, sys, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT     = Path(__file__).parent
HIST_DIR = ROOT / "data" / "history"
OUT_CSV  = ROOT / "data" / "history_export.csv"

COLS = [
    "date", "tour", "cat", "surf", "cpi", "tourn",
    "p1", "p2", "rk1", "rk2",
    "celo1", "helo1", "celo2", "helo2", "selo1", "selo2", "sdelta",
    "ss1", "ss2", "prob1", "fair1", "fair2",
    "book1", "book2", "edge1", "edge2",
    "sig1", "sig2", "win", "sets", "score", "tomorrow",
]


def _n(v, d=0):
    """Szam formazasa, None -> ures."""
    if v is None:
        return ""
    try:
        return ("%%.%df" % d) % float(v)
    except (TypeError, ValueError):
        return ""


def collect(days=None, include_pending=False):
    if not HIST_DIR.exists():
        print("[export] Nincs data/history/ mappa.")
        return []

    cutoff = None
    if days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    rows = []
    for f in sorted(HIST_DIR.glob("*.json")):
        date_str = f.stem
        if cutoff and date_str < cutoff:
            continue
        try:
            snap = json.loads(f.read_text())
        except Exception as e:
            print("[export] %s olvasasi hiba: %s" % (f.name, e))
            continue

        for m in snap.get("matches", []):
            if not m.get("elo_found"):
                continue
            win = m.get("winner")
            if win is None and not include_pending:
                continue

            sets = m.get("sets")
            sets_s = "%d-%d" % (sets[0], sets[1]) if isinstance(sets, list) and len(sets) == 2 else ""

            rows.append({
                "date":  snap.get("date", date_str),
                "tour":  m.get("tour", ""),
                "cat":   m.get("category", ""),
                "surf":  m.get("surface", ""),
                "cpi":   _n(m.get("court_cpi")),
                "tourn": (m.get("tournament") or "")[:22],
                "p1":    m.get("name1") or m.get("player1", ""),
                "p2":    m.get("name2") or m.get("player2", ""),
                "rk1":   _n(m.get("rank1")),
                "rk2":   _n(m.get("rank2")),
                "celo1": _n(m.get("c_elo1")),
                "helo1": _n(m.get("h_elo1")),
                "celo2": _n(m.get("c_elo2")),
                "helo2": _n(m.get("h_elo2")),
                "selo1": _n(m.get("surf_elo1")),
                "selo2": _n(m.get("surf_elo2")),
                "sdelta": _n(m.get("surf_delta")),
                "ss1":   _n(m.get("ss1")),
                "ss2":   _n(m.get("ss2")),
                "prob1": _n(m.get("prob1"), 4),
                "fair1": _n(m.get("odds1"), 2),
                "fair2": _n(m.get("odds2"), 2),
                "book1": _n(m.get("book_odds_home"), 2),
                "book2": _n(m.get("book_odds_away"), 2),
                "edge1": _n(m.get("edge1"), 4),
                "edge2": _n(m.get("edge2"), 4),
                "sig1":  "|".join(m.get("sigs1") or []),
                "sig2":  "|".join(m.get("sigs2") or []),
                "win":   "" if win is None else win,
                "sets":  sets_s,
                "score": m.get("score") or "",
                "tomorrow": "1" if m.get("is_tomorrow") else "",
            })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None, help="csak az utolso N nap")
    ap.add_argument("--all", action="store_true", help="a meg nem jatszottakat is")
    ap.add_argument("--quiet", action="store_true", help="ne irja a kepernyore")
    args = ap.parse_args()

    rows = collect(days=args.days, include_pending=args.all)
    if not rows:
        print("[export] Nincs exportalhato adat.")
        return

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    dates    = sorted({r["date"] for r in rows})
    played   = [r for r in rows if r["win"] != ""]
    with_sig = [r for r in rows if r["sig1"] or r["sig2"]]

    print("=" * 62)
    print("EXPORT KESZ -> %s" % OUT_CSV)
    print("=" * 62)
    print("  Napok:            %d  (%s .. %s)" % (len(dates), dates[0], dates[-1]))
    print("  Meccsek:          %d" % len(rows))
    print("  Eredmennyel:      %d" % len(played))
    print("  Badge-es (A/B):   %d" % len(with_sig))
    print("  Fajlmeret:        %.1f KB" % (OUT_CSV.stat().st_size / 1024))

    if not args.quiet:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
        print("\n" + "-" * 62)
        print("CSV (masolhato):")
        print("-" * 62)
        print(buf.getvalue().rstrip())


if __name__ == "__main__":
    main()
