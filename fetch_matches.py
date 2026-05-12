"""
ATP + WTA meccsek - TennisExplorer.com
Javítások:
- Debug sorok hozzáadva a hibakereséshez
- scrape_matches függvény visszaállítva a main.py-hoz
- Fájlnevek szinkronizálva
"""
import re, time, random, json
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "data" / "todays_matches.json"

# --- TORNATÁBLÁZATOK ---
ATP_MAP = [
    (["australian open","melbourne"],          "hard",  "GS",    "ATP"),
    (["roland garros","french open"],          "clay",  "GS",    "ATP"),
    (["wimbledon"],                            "grass", "GS",    "ATP"),
    (["us open","flushing"],                   "hard",  "GS",    "ATP"),
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
    (["rotterdam","abn amro"],                 "hard",  "A500",  "ATP"),
    (["rio open","rio de janeiro"],            "clay",  "A500",  "ATP"),
    (["acapulco","mexicano telcel"],           "hard",  "A500",  "ATP"),
    (["dubai duty free"],                      "hard",  "A500",  "ATP"),
    (["barcelona open","banc sabadell"],       "clay",  "A500",  "ATP"),
    (["halle","terra wortmann"],               "grass", "A500",  "ATP"),
    (["queen's club","queens club"],           "grass", "A500",  "ATP"),
    (["hamburg open"],                         "clay",  "A500",  "ATP"),
    (["washington","mubadala citi"],           "hard",  "A500",  "ATP"),
    (["beijing","china open"],                 "hard",  "A500",  "ATP"),
    (["tokyo","japan open"],                   "hard",  "A500",  "ATP"),
    (["vienna","erstebank"],                   "hard",  "A500",  "ATP"),
    (["basel","swiss indoors"],                "hard",  "A500",  "ATP"),
]

WTA_MAP = [
    (["australian open","melbourne"], "hard",  "GS",    "WTA"),
    (["roland garros","french open"], "clay",  "GS",    "WTA"),
    (["wimbledon"],                   "grass", "GS",    "WTA"),
    (["us open","flushing"],          "hard",  "GS",    "WTA"),
    (["doha","qatar open"],           "hard",  "M1000", "WTA"),
    (["dubai"],                       "hard",  "M1000", "WTA"),
    (["indian wells"],                "hard",  "M1000", "WTA"),
    (["miami"],                       "hard",  "M1000", "WTA"),
    (["madrid"],                      "clay",  "M1000", "WTA"),
    (["rome","italian open"],         "clay",  "M1000", "WTA"),
    (["toronto","montreal","canada"], "hard",  "M1000", "WTA"),
    (["cincinnati"],                  "hard",  "M1000", "WTA"),
    (["beijing","china open"],        "hard",  "M1000", "WTA"),
    (["wuhan"],                       "hard",  "M1000", "WTA"),
    (["brisbane"],                    "hard",  "A500",  "WTA"),
    (["adelaide"],                    "hard",  "A500",  "WTA"),
    (["abu dhabi"],                   "hard",  "A500",  "WTA"),
    (["charleston"],                  "clay",  "A500",  "WTA"),
    (["stuttgart"],                   "clay",  "A500",  "WTA"),
    (["berlin"],                      "grass", "A500",  "WTA"),
    (["eastbourne"],                  "grass", "A500",  "WTA"),
    (["washington"],                  "hard",  "A500",  "WTA"),
    (["seoul"],                       "hard",  "A500",  "WTA"),
    (["tokyo"],                       "hard",  "A500",  "WTA"),
]

ATP_VALID = ["GS", "M1000", "A500"]
WTA_VALID = ["GS", "M1000", "A500"]

def classify(name, tour_map, valid_cats):
    n = name.lower()
    for keys, surf, cat, tour in tour_map:
        if any(k in n for k in keys):
            return surf, cat, tour
    return None, "Other", None

def get_html(url):
    scraper = cloudscraper.create_scraper()
    time.sleep(random.uniform(1, 3))
    r = scraper.get(url, timeout=20)
    return r.text

def parse_match_rows(rows):
    res = []
    # Kettesével nézzük a sorokat (Player 1 és Player 2)
    for i in range(0, len(rows)-1, 2):
        r1, r2 = rows[i], rows[i+1]
        tds1 = r1.find_all("td")
        tds2 = r2.find_all("td")
        if len(tds1) < 8 or len(tds2) < 5: continue
        
        # Idő és nevek kinyerése
        time_str = tds1[0].get_text(strip=True)
        p1_link = tds1[1].find("a")
        p2_link = tds2[0].find("a")
        
        if not p1_link or not p2_link: continue
        
        # Oddsok (H/A oszlopok)
        o_h = tds1[-2].get_text(strip=True)
        o_a = tds1[-1].get_text(strip=True)
        
        try:
            res.append({
                "time": time_str,
                "p1": p1_link.get_text(strip=True),
                "p2": p2_link.get_text(strip=True),
                "book_odds_home": float(o_h) if o_h and o_h != "-" else None,
                "book_odds_away": float(o_a) if o_a and o_a != "-" else None
            })
        except: continue
    return res

def scrape_tour(url, tour_map, valid_cats, label):
    print(f"\n[fetch_{label}] Indítás: {url}")
    html = get_html(url)
    soup = BeautifulSoup(html, "lxml")
    
    all_tr = soup.find_all("tr")
    print(f"[debug] Összesen {len(all_tr)} sort találtam az oldalon.")

    all_matches = []
    cur_t = cur_s = cur_c = cur_tour = None
    cur_rows = []

    def flush():
        nonlocal cur_rows
        if cur_t and cur_c in valid_cats and cur_rows:
            parsed = parse_match_rows(cur_rows)
            for m in parsed:
                m.update({"tournament": cur_t, "surface": cur_s, "category": cur_c, "tour": cur_tour})
                all_matches.append(m)
            print(f"  ✅ [{cur_c}] {cur_t}: {len(parsed)} meccs hozzáadva")
        cur_rows = []

    for row in all_tr:
        classes = row.get("class", [])
        if "head" in classes:
            flush()
            lnk = row.find("a")
            name = lnk.get_text(strip=True) if lnk else row.get_text(strip=True)
            surf, cat, tour = classify(name, tour_map, valid_cats)
            
            # DEBUG SOR: Lássuk, miért nem fogja meg a tornát
            if cat in valid_cats:
                print(f"[debug] MEGTALÁLT TORNA: '{name}' -> Kategória: {cat}")
            
            cur_t, cur_s, cur_c, cur_tour = name, surf, cat, tour
            cur_rows = []
        elif cur_c in valid_cats:
            cur_rows.append(row)

    flush()
    print(f"[debug] {label} összesen: {len(all_matches)} meccs.")
    return all_matches

# EZ A FÜGGVÉNY KELL A MAIN.PY-NAK
def scrape_matches():
    atp = scrape_tour("https://www.tennisexplorer.com/matches/?type=atp-single", ATP_MAP, ATP_VALID, "ATP")
    wta = scrape_tour("https://www.tennisexplorer.com/matches/?type=wta-single", WTA_MAP, WTA_VALID, "WTA")
    return atp + wta

def save_matches(matches):
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(matches, indent=2))
    print(f"[fetch_matches] Mentve: {OUTPUT_PATH}")

if __name__ == "__main__":
    m = scrape_matches()
    save_matches(m)
