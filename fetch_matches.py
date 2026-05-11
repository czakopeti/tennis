"""
Napi ATP 500+ meccsek - TennisExplorer.com
Újdonság: bukméker odds kinyerése (H/A oszlopok)
"""
import re, time, random, json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "data" / "todays_matches.json"

TOURNAMENT_MAP = [
    (["australian open","melbourne"],          "hard",  "GS"),
    (["roland garros","french open"],          "clay",  "GS"),
    (["wimbledon"],                            "grass", "GS"),
    (["us open","flushing"],                   "hard",  "GS"),
    (["indian wells"],                         "hard",  "M1000"),
    (["miami"],                                "hard",  "M1000"),
    (["monte carlo","monte-carlo"],            "clay",  "M1000"),
    (["madrid"],                               "clay",  "M1000"),
    (["rome","italian open","internazionali"], "clay",  "M1000"),
    (["canada","toronto","montreal"],          "hard",  "M1000"),
    (["cincinnati"],                           "hard",  "M1000"),
    (["shanghai"],                             "hard",  "M1000"),
    (["paris masters","paris-bercy"],          "hard",  "M1000"),
    (["nitto","atp finals","turin"],           "hard",  "M1000"),
    (["rotterdam"],                            "hard",  "A500"),
    (["dubai"],                                "hard",  "A500"),
    (["acapulco","abierto mexicano"],          "hard",  "A500"),
    (["barcelona"],                            "clay",  "A500"),
    (["hamburg"],                              "clay",  "A500"),
    (["halle","terra wortmann"],               "grass", "A500"),
    (["queens","queen's"],                     "grass", "A500"),
    (["washington","citi open"],               "hard",  "A500"),
    (["beijing","china open"],                 "hard",  "A500"),
    (["tokyo","rakuten"],                      "hard",  "A500"),
    (["vienna","erste bank"],                  "hard",  "A500"),
    (["basel"],                                "hard",  "A500"),
    (["astana"],                               "hard",  "A500"),
    (["dallas"],                               "hard",  "A500"),
    (["lyon"],                                 "clay",  "A500"),
]
VALID = {"GS", "M1000", "A500"}
EXCLUDE = ["challenger","futures","utr","itf","satellite","wta","doubles"]


def classify(name):
    nl = name.lower()
    if any(x in nl for x in EXCLUDE):
        return None, None
    for kws, surf, cat in TOURNAMENT_MAP:
        if any(k in nl for k in kws):
            return surf, cat
    return None, None


def get_html(url):
    try:
        import cloudscraper
        s = cloudscraper.create_scraper(browser={"browser":"chrome","platform":"windows","mobile":False})
        time.sleep(random.uniform(2.0, 4.0))
        r = s.get(url, timeout=30)
        if r.status_code == 200 and len(r.text) > 2000:
            print(f"[fetch_matches] cloudscraper OK ({len(r.text):,} kar)")
            return r.text
    except Exception as e:
        print(f"[fetch_matches] cloudscraper: {e}")
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def extract_odds(row):
    """
    Kinyeri a H (home) és A (away) oddsot egy meccs-sorból.
    A TennisExplorer táblában: S 1 2 3 4 5 H2H [H-odds] [A-odds] info
    Az oddsok tizedes törtek >= 1.01, a set-számok egészek 0-7 között.
    """
    odds = []
    for td in row.find_all("td"):
        txt = td.get_text(strip=True)
        # Float, pontosan egy tizedes formátumban, 1.01 és 99.9 között
        if re.match(r'^\d{1,2}\.\d{2}$', txt):
            val = float(txt)
            if 1.01 <= val <= 99.0:
                odds.append(val)
    if len(odds) >= 2:
        return odds[-2], odds[-1]   # H, A (utolsó kettő)
    if len(odds) == 1:
        return odds[0], None
    return None, None


def is_player_name(text):
    if not text or len(text) < 3:
        return False
    bad = ["live stream","bet365","unibet","1xbet","bwin","sky sports","bein","eurosport","dazn"]
    return not any(b in text.lower() for b in bad)


def parse_player(row):
    for a in row.find_all("a"):
        if "player" in a.get("href",""):
            n = re.sub(r'\s+',' ', a.get_text(strip=True)).strip()
            if is_player_name(n):
                return n
    return None


def parse_seed(row):
    m = re.search(r'\((\d+)\)', row.get_text())
    return int(m.group(1)) if m else None


def parse_match_rows(rows):
    matches = []
    i = 0
    while i < len(rows) - 1:
        r1, r2 = rows[i], rows[i+1]
        t = next((c.get_text(strip=True) for c in r1.find_all("td")
                  if re.match(r'^\d{1,2}:\d{2}$', c.get_text(strip=True))), None)
        if not t:
            i += 1; continue

        p1 = parse_player(r1)
        p2 = parse_player(r2)

        # Odds: az első sorban vannak (H és A)
        h_odds, a_odds = extract_odds(r1)

        if p1 and p2:
            matches.append({
                "time": t, "player1": p1, "player2": p2,
                "seed1": parse_seed(r1), "seed2": parse_seed(r2),
                "book_odds_home": h_odds,   # player1 odds
                "book_odds_away": a_odds,   # player2 odds
            })
        i += 2
    return matches


def scrape_matches(date=None):
    if date is None:
        date = datetime.now(timezone.utc)
    url = "https://www.tennisexplorer.com/matches/?type=atp-single"
    print(f"[fetch_matches] {url}")
    try:
        html = get_html(url)
    except Exception as e:
        print(f"[fetch_matches] HIBA: {e}"); return []

    soup = BeautifulSoup(html, "lxml")
    all_matches = []
    cur_t = cur_s = cur_c = None
    cur_rows = []

    def flush():
        nonlocal cur_rows
        if cur_t and cur_c in VALID and cur_rows:
            parsed = parse_match_rows(cur_rows)
            for m in parsed:
                m["tournament"] = cur_t
                m["surface"]    = cur_s
                m["category"]   = cur_c
                all_matches.append(m)
            print(f"  [{cur_c}|{cur_s}] {cur_t}: {len(parsed)} meccs")
        cur_rows = []

    for row in soup.find_all("tr"):
        classes = row.get("class", [])
        if "head" in classes and "flags" in classes:   # csak torna fejléc
            flush()
            lnk  = row.find("a")
            name = re.sub(r'\s+',' ',
                          (lnk.get_text(strip=True) if lnk
                           else row.get_text(strip=True))).strip()
            name = re.split(r'\s+S\s+\d', name)[0].strip()
            surf, cat = classify(name)
            cur_t, cur_s, cur_c = name, surf, cat
            cur_rows = []
            print(f"  {'✅' if cat in VALID else '⏭'} [{cat}|{surf}] {name}")
        elif cur_c in VALID:
            cur_rows.append(row)

    flush()
    print(f"\n[fetch_matches] {len(all_matches)} ATP500+ meccs")
    for m in all_matches:
        odds_str = f"  odds: {m['book_odds_home']}/{m['book_odds_away']}" if m.get('book_odds_home') else ""
        print(f"  {m['time']} {m['player1']} vs {m['player2']}{odds_str}")
    return all_matches


def save_matches(matches):
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(matches, indent=2))
    print(f"[fetch_matches] Mentve -> {OUTPUT_PATH}")


if __name__ == "__main__":
    save_matches(scrape_matches())
