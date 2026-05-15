"""
ATP + WTA meccsek - TennisExplorer.com
"""
import re, time, random, json
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "data" / "todays_matches.json"

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
    (["rotterdam"],                            "hard",  "A500",  "ATP"),
    (["qatar open","doha"],                    "hard",  "A500",  "ATP"),
    (["dubai"],                                "hard",  "A500",  "ATP"),
    (["rio open","rio de janeiro"],            "clay",  "A500",  "ATP"),
    (["acapulco","abierto mexicano","mexican open"], "hard","A500","ATP"),
    (["barcelona"],                            "clay",  "A500",  "ATP"),
    (["munich","bmw open"],                    "clay",  "A500",  "ATP"),
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

WTA_MAP = [
    (["australian open","melbourne"],          "hard",  "GS",    "WTA"),
    (["roland garros","french open"],          "clay",  "GS",    "WTA"),
    (["wimbledon"],                            "grass", "GS",    "WTA"),
    (["us open","flushing"],                   "hard",  "GS",    "WTA"),
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
    (["brisbane"],                             "hard",  "W500",  "WTA"),
    (["abu dhabi"],                            "hard",  "W500",  "WTA"),
    (["charleston"],                           "clay",  "W500",  "WTA"),
    (["stuttgart"],                            "clay",  "W500",  "WTA"),
    (["berlin"],                               "grass", "W500",  "WTA"),
    (["bad homburg"],                          "grass", "W500",  "WTA"),
    (["hamburg"],                              "clay",  "W500",  "WTA"),
    (["washington"],                           "hard",  "W500",  "WTA"),
    (["linz"],                                 "hard",  "W500",  "WTA"),
    (["guadalajara"],                          "hard",  "W500",  "WTA"),
]

ATP_VALID = {"GS","M1000","A500"}
WTA_VALID = {"GS","W1000","W500"}
EXCLUDE   = ["challenger","futures","utr","itf","satellite","125","doubles",
             "h2h","main tournaments","lower level","motuwethfr","wta elite"]


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
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }
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


def get_player_link(row):
    for a in row.find_all("a"):
        href = a.get("href", "")
        # TennisExplorer player links: /player/surname-firstname/
        if "/player/" in href:
            n = re.sub(r'\s+', ' ', a.get_text(strip=True)).strip()
            if is_player(n):
                return n
    return None


def get_time(row):
    for cell in row.find_all("td"):
        txt = cell.get_text(strip=True)
        if re.match(r'^\d{1,2}:\d{2}$', txt):
            return txt
    return None


def get_seed(row):
    m = re.search(r'\((\d+)\)', row.get_text())
    return int(m.group(1)) if m else None


def parse_match_rows(rows, tourn_name=""):
    """
    Párkeresés: az első sor amiben van idő = r1 (player1),
    a következő player-linkes sor = r2 (player2).
    Kihagyja a month/head sorokat és a link nélküli dekor sorokat.
    """
    # Szűrés: csak sorok amikben van idő VAGY player link
    useful = []
    for row in rows:
        classes = set(row.get("class", []))
        # Kihagyjuk a dátumfejlécet és torna fejlécet
        if "month" in classes or "head" in classes:
            continue
        has_t = get_time(row) is not None
        has_p = get_player_link(row) is not None
        if has_t or has_p:
            useful.append(row)

    # Debug: első néhány hasznos sor
    if useful:
        print(f"    [debug] {tourn_name}: {len(useful)} hasznos sor, első 6:")
        for row in useful[:6]:
            t = get_time(row) or ""
            p = get_player_link(row) or ""
            cls = row.get("class", [])
            print(f"      class={cls} | t={t} | p={p}")
    else:
        print(f"    [debug] {tourn_name}: 0 hasznos sor a {len(rows)} sorból")
        # Extra debug: első 4 sor
        for row in rows[:4]:
            cls = row.get("class", [])
            txt = row.get_text(separator=" ", strip=True)[:80]
            links = [(a.get("href","")[:40], a.get_text(strip=True)[:20])
                     for a in row.find_all("a")]
            print(f"      class={cls} | {txt}")
            if links: print(f"        links: {links}")

    matches = []
    i = 0
    while i < len(useful) - 1:
        r1 = useful[i]
        t  = get_time(r1)
        if t is None:
            i += 1
            continue
        p1 = get_player_link(r1)
        if p1 is None:
            i += 1
            continue
        # Következő player-linkes sor (akár i+1, akár i+2 ha TV-ikon sor közbejön)
        r2 = None
        for j in range(i + 1, min(i + 5, len(useful))):
            if get_player_link(useful[j]):
                r2 = useful[j]
                i  = j + 1
                break
        if r2 is None:
            i += 1
            continue
        p2 = get_player_link(r2)
        h_o, a_o = extract_odds(r1)
        matches.append({
            "time": t, "player1": p1, "player2": p2,
            "seed1": get_seed(r1), "seed2": get_seed(r2),
            "book_odds_home": h_o, "book_odds_away": a_o,
        })
    return matches


def scrape_tour(url, tour_map, valid_cats, label):
    print(f"\n[fetch_{label}] {url}")
    try:
        html = get_html(url)
    except Exception as e:
        print(f"[fetch_{label}] HIBA: {e}")
        return []

    soup = BeautifulSoup(html, "lxml")
    all_matches = []
    cur_t = cur_s = cur_c = cur_tour = None
    cur_rows = []

    def flush():
        nonlocal cur_rows
        if cur_t and cur_c in valid_cats and cur_rows:
            parsed = parse_match_rows(cur_rows, cur_t)
            for m in parsed:
                m.update({"tournament":cur_t,"surface":cur_s,
                          "category":cur_c,"tour":cur_tour})
                all_matches.append(m)
            print(f"  ✅ [{cur_c}|{cur_s}] {cur_t}: {len(parsed)} meccs")
            for m in parsed:
                o = f" {m['book_odds_home']}/{m['book_odds_away']}" if m.get('book_odds_home') else ""
                print(f"    {m['time']} {m['player1']} vs {m['player2']}{o}")
        cur_rows = []

    for row in soup.find_all("tr"):
        classes = row.get("class", [])
        if "head" in classes and "flags" in classes:
            flush()
            lnk  = row.find("a")
            name = re.sub(r'\s+', ' ',
                         (lnk.get_text(strip=True) if lnk
                          else row.get_text(strip=True))).strip()
            name = re.split(r'\s+S\s+\d', name)[0].strip()
            surf, cat, tour = classify(name, tour_map, valid_cats)
            cur_t, cur_s, cur_c, cur_tour = name, surf, cat, tour
            cur_rows = []
            print(f"  {'✅' if cat in valid_cats else '⏭'} [{cat}|{surf}] {name}")
        elif "month" in classes:
            continue  # dátumfejléc kihagyása
        else:
            cur_rows.append(row)

    flush()
    print(f"[fetch_{label}] {len(all_matches)} meccs összesen")
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
