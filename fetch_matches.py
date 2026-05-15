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
    (["acapulco","abierto mexicano"],          "hard",  "A500",  "ATP"),
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

ATP_VALID = {"GS", "M1000", "A500"}
WTA_VALID = {"GS", "W1000", "W500"}
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
            print("[fetch] cloudscraper OK (%d kar)" % len(r.text))
            return r.text
    except Exception as e:
        print("[fetch] cloudscraper: %s" % e)
    import requests
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }
    r = requests.get(url, headers=h, timeout=30)
    r.raise_for_status()
    return r.text


def get_player_link(row):
    bad = ["live stream","bet365","unibet","1xbet","bwin","sky sports","bein","eurosport"]
    for a in row.find_all("a"):
        if "/player/" in a.get("href", ""):
            n = re.sub(r'\s+', ' ', a.get_text(strip=True)).strip()
            if n and len(n) > 3 and not any(b in n.lower() for b in bad):
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


def parse_match_rows(rows):
    # Pairing by 'bott' CSS class:
    # 'bott' in classes = player1 row (works for upcoming, live, finished)
    # next row with player link = player2 row
    matches = []
    i = 0
    while i < len(rows):
        row = rows[i]
        classes = set(row.get("class", []))

        if classes & {"head", "month", "flags"}:
            i += 1
            continue

        if "bott" in classes:
            p1 = get_player_link(row)
            if not p1:
                i += 1
                continue

            match_time = get_time(row) or ""
            h_o, a_o   = extract_odds(row)
            seed1      = get_seed(row)

            p2    = None
            seed2 = None
            j     = i + 1
            while j < min(i + 5, len(rows)):
                cj = set(rows[j].get("class", []))
                if cj & {"head", "month", "flags"}:
                    break
                p2c = get_player_link(rows[j])
                if p2c:
                    p2    = p2c
                    seed2 = get_seed(rows[j])
                    i     = j + 1
                    break
                j += 1
            else:
                i += 1
                continue

            if p2:
                matches.append({
                    "time":           match_time,
                    "player1":        p1,
                    "player2":        p2,
                    "seed1":          seed1,
                    "seed2":          seed2,
                    "book_odds_home": h_o,
                    "book_odds_away": a_o,
                })
        else:
            i += 1

    return matches


def scrape_tour(url, tour_map, valid_cats, label):
    print("\n[fetch_%s] %s" % (label, url))
    try:
        html = get_html(url)
    except Exception as e:
        print("[fetch_%s] ERROR: %s" % (label, e))
        return []

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
            print("  OK [%s|%s] %s: %d match" % (cur_c, cur_s, cur_t, len(parsed)))
            for m in parsed:
                o = " %s/%s" % (m['book_odds_home'], m['book_odds_away']) if m.get('book_odds_home') else ""
                t = m['time'] or "live"
                print("    %s %s vs %s%s" % (t, m['player1'], m['player2'], o))
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
            status = "OK" if cat in valid_cats else "skip"
            print("  %s [%s|%s] %s" % (status, cat, surf, name))
        elif "month" in classes:
            continue
        else:
            cur_rows.append(row)

    flush()
    print("[fetch_%s] %d matches total" % (label, len(all_matches)))
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
    print("\n[fetch_matches] Saved -> %s (%d matches)" % (OUTPUT_PATH, len(matches)))


if __name__ == "__main__":
    save_matches(scrape_matches())
