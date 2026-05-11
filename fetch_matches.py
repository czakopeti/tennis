"""
ATP + WTA meccsek scrape-elése TennisExplorer.com-ról.
Mindkét tour egységes TOURNAMENT_MAP-pel, class="head flags" szűréssel.
"""
import re, time, random, json
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "data" / "todays_matches.json"

# ── ATP 500+ torna térkép (2026-os naptár alapján) ───────────────────────────
ATP_MAP = [
    # Grand Slam
    (["australian open","melbourne"],          "hard",  "GS",    "ATP"),
    (["roland garros","french open"],          "clay",  "GS",    "ATP"),
    (["wimbledon"],                            "grass", "GS",    "ATP"),
    (["us open","flushing"],                   "hard",  "GS",    "ATP"),
    # Masters 1000
    (["indian wells"],                         "hard",  "M1000", "ATP"),
    (["miami"],                                "hard",  "M1000", "ATP"),
    (["monte carlo","monte-carlo"],            "clay",  "M1000", "ATP"),
    (["madrid"],                               "clay",  "M1000", "ATP"),
    (["rome","italian open","internazionali"], "clay",  "M1000", "ATP"),
    (["canada","toronto","montreal"],          "hard",  "M1000", "ATP"),
    (["cincinnati"],                           "hard",  "M1000", "ATP"),
    (["shanghai"],                             "hard",  "M1000", "ATP"),
    (["paris masters","paris-bercy"],          "hard",  "M1000", "ATP"),
    (["nitto","atp finals","turin"],           "hard",  "M1000", "ATP"),
    # ATP 500 — teljes 2026-os lista
    (["rotterdam"],                            "hard",  "A500",  "ATP"),
    (["qatar open","doha"],                    "hard",  "A500",  "ATP"),  # 2026-ban 500-ra emelve
    (["dubai"],                                "hard",  "A500",  "ATP"),
    (["rio open","rio de janeiro"],            "clay",  "A500",  "ATP"),  # febr., salak
    (["acapulco","abierto mexicano","mexican open"], "hard", "A500", "ATP"),
    (["barcelona"],                            "clay",  "A500",  "ATP"),
    (["munich","bmw open"],                    "clay",  "A500",  "ATP"),  # ápr., salak
    (["madrid"],                               "clay",  "A500",  "ATP"),
    (["hamburg"],                              "clay",  "A500",  "ATP"),
    (["halle","terra wortmann"],               "grass", "A500",  "ATP"),
    (["queens","queen's"],                     "grass", "A500",  "ATP"),
    (["washington","citi open"],               "hard",  "A500",  "ATP"),
    (["beijing","china open"],                 "hard",  "A500",  "ATP"),
    (["tokyo","rakuten"],                      "hard",  "A500",  "ATP"),
    (["vienna","erste bank"],                  "hard",  "A500",  "ATP"),
    (["basel"],                                "hard",  "A500",  "ATP"),
    (["astana"],                               "hard",  "A500",  "ATP"),
    (["dallas"],                               "hard",  "A500",  "ATP"),
    (["lyon"],                                 "clay",  "A500",  "ATP"),
]

# ── WTA 500+ torna térkép (2026-os naptár) ───────────────────────────────────
WTA_MAP = [
    # Grand Slam (közös)
    (["australian open","melbourne"],          "hard",  "GS",    "WTA"),
    (["roland garros","french open"],          "clay",  "GS",    "WTA"),
    (["wimbledon"],                            "grass", "GS",    "WTA"),
    (["us open","flushing"],                   "hard",  "GS",    "WTA"),
    # WTA 1000
    (["qatar open","doha"],                    "hard",  "W1000", "WTA"),
    (["dubai tennis"],                         "hard",  "W1000", "WTA"),
    (["indian wells"],                         "hard",  "W1000", "WTA"),
    (["miami"],                                "hard",  "W1000", "WTA"),
    (["madrid"],                               "clay",  "W1000", "WTA"),
    (["rome","italian open","internazionali"], "clay",  "W1000", "WTA"),
    (["canada","toronto","montreal"],          "hard",  "W1000", "WTA"),
    (["cincinnati"],                           "hard",  "W1000", "WTA"),
    (["china open","beijing"],                 "hard",  "W1000", "WTA"),
    (["wuhan"],                                "hard",  "W1000", "WTA"),
    # WTA 500
    (["brisbane"],                             "hard",  "W500",  "WTA"),
    (["adelaide"],                             "hard",  "W500",  "WTA"),
    (["abu dhabi"],                            "hard",  "W500",  "WTA"),
    (["charleston"],                           "clay",  "W500",  "WTA"),
    (["stuttgart"],                            "clay",  "W500",  "WTA"),
    (["berlin"],                               "grass", "W500",  "WTA"),
    (["bad homburg"],                          "grass", "W500",  "WTA"),
    (["hamburg"],                              "clay",  "W500",  "WTA"),
    (["washington"],                           "hard",  "W500",  "WTA"),
    (["linz"],                                 "hard",  "W500",  "WTA"),
    (["ostrava"],                              "hard",  "W500",  "WTA"),
    (["guadalajara"],                          "hard",  "W500",  "WTA"),
]

ATP_VALID  = {"GS", "M1000", "A500"}
WTA_VALID  = {"GS", "W1000", "W500"}
EXCLUDE    = ["challenger","futures","utr","itf","satellite","125","doubles","h2h",
              "main tournaments","lower level","motuwethfr"]


def classify(name, tour_map, valid_cats):
    nl = name.lower()
    if any(x in nl for x in EXCLUDE):
        return None, None, None
    for kws, surf, cat, tour in tour_map:
        if any(k in nl for k in kws):
            return surf, cat, tour
    return None, None, None


def get_html(url):
    try:
        import cloudscraper
        s = cloudscraper.create_scraper(
            browser={"browser":"chrome","platform":"windows","mobile":False})
        time.sleep(random.uniform(2.0, 4.0))
        r = s.get(url, timeout=30)
        if r.status_code == 200 and len(r.text) > 2000:
            print(f"[fetch] cloudscraper OK ({len(r.text):,} kar)")
            return r.text
    except Exception as e:
        print(f"[fetch] cloudscraper: {e}")
    import requests
    h = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
         "Accept":"text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
         "Referer":"https://www.google.com/"}
    r = requests.get(url, headers=h, timeout=30)
    r.raise_for_status()
    return r.text


def extract_odds(row):
    odds = []
    for td in row.find_all("td"):
        txt = td.get_text(strip=True)
        if re.match(r'^\d{1,2}\.\d{2}$', txt):
            v = float(txt)
            if 1.01 <= v <= 99.0:
                odds.append(v)
    if len(odds) >= 2: return odds[-2], odds[-1]
    if len(odds) == 1: return odds[0], None
    return None, None


def is_player(text):
    if not text or len(text) < 3: return False
    bad = ["live stream","bet365","unibet","1xbet","bwin","sky sports",
           "bein","eurosport","dazn","betway","ladbrokes"]
    return not any(b in text.lower() for b in bad)


def parse_player(row):
    for a in row.find_all("a"):
        if "player" in a.get("href",""):
            n = re.sub(r'\s+',' ', a.get_text(strip=True)).strip()
            if is_player(n): return n
    return None


def parse_seed(row):
    m = re.search(r'\((\d+)\)', row.get_text())
    return int(m.group(1)) if m else None


def parse_match_rows(rows):
    matches, i = [], 0
    while i < len(rows)-1:
        r1, r2 = rows[i], rows[i+1]
        t = next((c.get_text(strip=True) for c in r1.find_all("td")
                  if re.match(r'^\d{1,2}:\d{2}$', c.get_text(strip=True))), None)
        if not t: i+=1; continue
        p1, p2 = parse_player(r1), parse_player(r2)
        h_o, a_o = extract_odds(r1)
        if p1 and p2:
            matches.append({"time":t,"player1":p1,"player2":p2,
                            "seed1":parse_seed(r1),"seed2":parse_seed(r2),
                            "book_odds_home":h_o,"book_odds_away":a_o})
        i += 2
    return matches


def scrape_tour(url, tour_map, valid_cats, tour_label):
    print(f"\n[fetch_{tour_label}] {url}")
    try:
        html = get_html(url)
    except Exception as e:
        print(f"[fetch_{tour_label}] HIBA: {e}"); return []

    soup = BeautifulSoup(html, "lxml")
    all_matches = []
    cur_t = cur_s = cur_c = cur_tour = None
    cur_rows = []

    def flush():
        nonlocal cur_rows
        if cur_t and cur_c in valid_cats and cur_rows:
            parsed = parse_match_rows(cur_rows)
            for m in parsed:
                m.update({"tournament":cur_t,"surface":cur_s,
                          "category":cur_c,"tour":cur_tour})
                all_matches.append(m)
            print(f"  ✅ [{cur_c}|{cur_s}] {cur_t}: {len(parsed)} meccs")
        cur_rows = []

    for row in soup.find_all("tr"):
        classes = row.get("class",[])
        if "head" in classes and "flags" in classes:
            flush()
            lnk  = row.find("a")
            name = re.sub(r'\s+',' ',
                         (lnk.get_text(strip=True) if lnk
                          else row.get_text(strip=True))).strip()
            name = re.split(r'\s+S\s+\d', name)[0].strip()
            surf, cat, tour = classify(name, tour_map, valid_cats)
            cur_t, cur_s, cur_c, cur_tour = name, surf, cat, tour
            cur_rows = []
            if cat not in valid_cats:
                print(f"  ⏭ {name}")
        elif cur_c in valid_cats:
            cur_rows.append(row)
    flush()

    print(f"[fetch_{tour_label}] {len(all_matches)} meccs összesen")
    return all_matches


def scrape_matches():
    atp = scrape_tour(
        "https://www.tennisexplorer.com/matches/?type=atp-single",
        ATP_MAP, ATP_VALID, "ATP")
    wta = scrape_tour(
        "https://www.tennisexplorer.com/matches/?type=wta-single",
        WTA_MAP, WTA_VALID, "WTA")
    return atp + wta


def save_matches(matches):
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(matches, indent=2))
    print(f"\n[fetch_matches] Mentve -> {OUTPUT_PATH} ({len(matches)} meccs)")


if __name__ == "__main__":
    save_matches(scrape_matches())
