"""
fetch_results.py — Lezart meccsek eredmenyenek automatikus rogzitese.

Mukodes:
  1. Betolti a data/history/YYYY-MM-DD.json napi pillanatkepet
     (ezt a main.py menti el meccs elott: MINDEN meccs, nem csak a jeloltek).
  2. Lehuzza a TennisExplorer eredmeny-oldalat az adott napra.
  3. Osszeparositja a jatekosneveket, es bejegyzi:
        winner (1/2), score ("6-4 7-6"), sets ([2,1]), tiebreaks
  4. Visszamenti a fajlt.

Igy visszamenoleg elemezheto: a badge-es (kivalasztott) meccsek hogyan
teljesitettek a badge nelkuliekhez (kihagyottakhoz) kepest.
"""
import re, sys, json, time, random, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

ROOT     = Path(__file__).parent
HIST_DIR = ROOT / "data" / "history"
BASE     = "https://www.tennisexplorer.com/results/"

sys.path.insert(0, str(ROOT))
from value_calc import _key   # normalizalt nevkulcs (ekezet/aposztrof nelkul)


# ══ Letoltes ═════════════════════════════════════════════════════════════

def get_html(url):
    try:
        import cloudscraper
        s = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False})
        time.sleep(random.uniform(2.0, 4.0))
        r = s.get(url, timeout=30)
        if r.status_code == 200 and len(r.text) > 2000:
            print("[results] cloudscraper OK (%d kar)" % len(r.text))
            return r.text
    except Exception as e:
        print("[results] cloudscraper: %s" % e)
    import requests
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
         "Referer": "https://www.google.com/"}
    r = requests.get(url, headers=h, timeout=30)
    r.raise_for_status()
    return r.text


# ══ Parse ════════════════════════════════════════════════════════════════

def _player_name(row):
    bad = ["live stream", "bet365", "unibet", "1xbet", "bwin", "eurosport"]
    for a in row.find_all("a"):
        if "/player/" in a.get("href", ""):
            n = re.sub(r"\s+", " ", a.get_text(strip=True)).strip()
            if n and len(n) > 3 and not any(b in n.lower() for b in bad):
                return n
    return None


def _numeric_cells(row):
    """
    Szett- es jatekszamok kinyerese egy sorbol.
    Kihagyja: idopont (19:20), oddsok (1.72), ures cellak.
    Kezeli: tiebreak felso index (<sup>) -> csak az alapszam.
    """
    out = []
    for td in row.find_all("td"):
        raw = td.get_text(strip=True)
        if not raw:
            continue
        if re.match(r"^\d{1,2}:\d{2}$", raw):      # idopont
            continue
        if "." in raw or "," in raw:               # odds
            continue
        # tiebreak: a <sup> tartalmat levagjuk
        sup = td.find("sup")
        if sup:
            sup_txt = sup.get_text(strip=True)
            if sup_txt and raw.endswith(sup_txt):
                raw = raw[: -len(sup_txt)]
        if re.match(r"^\d{1,2}$", raw):
            out.append(int(raw))
    return out


def parse_results(html):
    """
    Visszaad: [{player1, player2, sets1, sets2, score, winner}, ...]
    """
    soup    = BeautifulSoup(html, "lxml")
    rows    = soup.find_all("tr")
    matches = []
    cur_tournament = ""

    i = 0
    while i < len(rows):
        row     = rows[i]
        classes = set(row.get("class", []))

        if "head" in classes and "flags" in classes:
            lnk = row.find("a")
            cur_tournament = re.sub(
                r"\s+", " ",
                (lnk.get_text(strip=True) if lnk else row.get_text(strip=True))).strip()
            cur_tournament = re.split(r"\s+S\s+\d", cur_tournament)[0].strip()
            i += 1
            continue

        if classes & {"month"}:
            i += 1
            continue

        if "bott" in classes:
            p1 = _player_name(row)
            if not p1:
                i += 1
                continue
            nums1 = _numeric_cells(row)

            p2, nums2 = None, []
            j = i + 1
            while j < min(i + 5, len(rows)):
                cj = set(rows[j].get("class", []))
                if cj & {"head", "month", "flags"}:
                    break
                cand = _player_name(rows[j])
                if cand:
                    p2    = cand
                    nums2 = _numeric_cells(rows[j])
                    i     = j + 1
                    break
                j += 1
            else:
                i += 1
                continue

            if not p2 or not nums1 or not nums2:
                continue

            sets1, sets2 = nums1[0], nums2[0]
            games1, games2 = nums1[1:], nums2[1:]
            n = min(len(games1), len(games2))
            score = " ".join("%d-%d" % (games1[k], games2[k]) for k in range(n))

            if sets1 == sets2:
                winner = None          # feladas / felbeszakadas
            else:
                winner = 1 if sets1 > sets2 else 2

            matches.append({
                "tournament": cur_tournament,
                "player1": p1, "player2": p2,
                "sets1": sets1, "sets2": sets2,
                "score": score, "winner": winner,
            })
        else:
            i += 1

    return matches


def fetch_day(date_str):
    """date_str: 'YYYY-MM-DD'. Visszaad ATP+WTA eredmenylistat."""
    y, mth, d = date_str.split("-")
    qs  = "year=%s&month=%s&day=%s" % (y, mth, d)
    out = []
    for typ in ("atp-single", "wta-single"):
        url = "%s?type=%s&%s" % (BASE, typ, qs)
        print("\n[results] %s" % url)
        try:
            res = parse_results(get_html(url))
            print("[results] %s: %d meccs" % (typ, len(res)))
            out.extend(res)
        except Exception as e:
            print("[results] %s HIBA: %s" % (typ, e))
    return out


# ══ Osszefuzes a pillanatkeppel ══════════════════════════════════════════

def merge_into_history(date_str):
    path = HIST_DIR / ("%s.json" % date_str)
    if not path.exists():
        print("[merge] Nincs pillanatkep: %s" % path)
        return False

    snap = json.loads(path.read_text())
    rows = snap.get("matches", [])
    if not rows:
        print("[merge] Ures pillanatkep")
        return False

    # Ha mar minden meccsnek van eredmenye, ne terheljuk a szervert.
    pending = [m for m in rows
               if m.get("winner") is None and not m.get("retired")]
    if not pending:
        print("[merge] %s — mar teljes (%d meccs), kihagyva" % (date_str, len(rows)))
        return True

    print("[merge] %s — %d/%d meccs var eredmenyre"
          % (date_str, len(pending), len(rows)))
    results = fetch_day(date_str)
    if not results:
        print("[merge] Nincs eredmeny adat")
        return False

    # index: (kulcs1, kulcs2) -> eredmeny
    index = {}
    for r in results:
        k1, k2 = _key(r["player1"]), _key(r["player2"])
        index[(k1, k2)] = (r, False)   # False = nem forditott
        index[(k2, k1)] = (r, True)    # True  = forditott sorrend

    matched = 0
    for m in rows:
        if m.get("winner") is not None:
            matched += 1
            continue
        k1, k2 = _key(m.get("player1", "")), _key(m.get("player2", ""))
        hit = index.get((k1, k2))
        if not hit:
            continue
        r, flipped = hit
        if r["winner"] is None:
            m["winner"] = None
            m["score"]  = r["score"]
            m["retired"] = True
            continue
        w = r["winner"]
        if flipped:
            w = 1 if w == 2 else 2
            m["sets"]  = [r["sets2"], r["sets1"]]
            m["score"] = " ".join(
                "-".join(reversed(s.split("-"))) for s in r["score"].split() if "-" in s)
        else:
            m["sets"]  = [r["sets1"], r["sets2"]]
            m["score"] = r["score"]
        m["winner"] = w
        m["retired"] = False
        matched += 1

    snap["results_fetched_at"] = datetime.now(timezone.utc).isoformat()
    snap["matched"] = matched
    snap["total"]   = len(rows)
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False))
    print("\n[merge] %s — %d/%d meccs eredmennyel" % (date_str, matched, len(rows)))
    return True


# ══ Osszesito statisztika ════════════════════════════════════════════════

def summary():
    """Kivalasztott (badge-es) vs kihagyott meccsek osszehasonlitasa."""
    files = sorted(HIST_DIR.glob("*.json"))
    if not files:
        print("Nincs elozmeny adat.")
        return

    buckets = {"A": [], "B": [], "AB": [], "none": []}
    for f in files:
        try:
            snap = json.loads(f.read_text())
        except Exception:
            continue
        for m in snap.get("matches", []):
            w = m.get("winner")
            if w is None or not m.get("elo_found"):
                continue
            s1 = set(m.get("sigs1") or [])
            s2 = set(m.get("sigs2") or [])
            # melyik jatekost jelolte a badge?
            for pick, sigs in ((1, s1), (2, s2)):
                if not sigs:
                    continue
                odds = m.get("book_odds_home") if pick == 1 else m.get("book_odds_away")
                if not odds:
                    continue
                key = "AB" if len(sigs) > 1 else list(sigs)[0]
                buckets[key].append((odds, w == pick))
            if not s1 and not s2:
                # kihagyott meccs: a bukmekeri favorit teljesitmenye
                bo1 = m.get("book_odds_home")
                bo2 = m.get("book_odds_away")
                if bo1 and bo2:
                    fav = 1 if bo1 < bo2 else 2
                    buckets["none"].append((min(bo1, bo2), w == fav))

    print("\n" + "=" * 64)
    print("OSSZESITO — kivalasztott vs kihagyott")
    print("=" * 64)
    print("%-22s %6s %8s %9s %9s" % ("Csoport", "N", "Talalat", "Elvart", "ROI"))
    print("-" * 64)
    labels = {"A": "🎯 A jelolt", "B": "🔮 B jelolt",
              "AB": "🎯+🔮 mindketto", "none": "kihagyott (favorit)"}
    for k in ("A", "B", "AB", "none"):
        rows = buckets[k]
        if not rows:
            print("%-22s %6s %8s %9s %9s" % (labels[k], 0, "—", "—", "—"))
            continue
        n   = len(rows)
        w   = sum(1 for _, ok in rows if ok)
        exp = sum(1 / o for o, _ in rows) / n
        roi = sum((o - 1) if ok else -1 for o, ok in rows) / n * 100
        print("%-22s %6d %7.1f%% %8.1f%% %+8.1f%%" %
              (labels[k], n, w / n * 100, exp * 100, roi))
    print("-" * 64)
    print("Elvart = a bukmekeri odds alapjan varhato talalati arany.")
    print("Ha a jelolt csoportok tartosan az elvart folott vannak, a szures mukodik.")


# ══ CLI ══════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (alap: tegnap)")
    ap.add_argument("--days", type=int, default=7,
                    help="hany napra visszamenoleg (alap: 7 — automatikus potlas)")
    ap.add_argument("--summary", action="store_true",
                    help="csak osszesito statisztika")
    args = ap.parse_args()

    HIST_DIR.mkdir(parents=True, exist_ok=True)

    if args.summary:
        summary()
        return

    if args.date:
        dates = [args.date]
    else:
        base  = datetime.now(timezone.utc) + timedelta(hours=2)
        dates = [(base - timedelta(days=k)).strftime("%Y-%m-%d")
                 for k in range(1, args.days + 1)]

    for d in dates:
        merge_into_history(d)

    summary()


if __name__ == "__main__":
    main()
