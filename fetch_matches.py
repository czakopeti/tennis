"""
Scrapes today's ATP 500+ matches from TennisExplorer.com.
Covers all surfaces (clay, hard, grass) and all ATP 500+, M1000, GS tournaments.
"""
import re, time, random, json, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "todays_matches.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

TOURNAMENT_MAP = [
    # GS
    (["australian open","melbourne"],         "hard",  "GS"),
    (["roland garros","french open"],         "clay",  "GS"),
    (["wimbledon"],                           "grass", "GS"),
    (["us open","flushing"],                  "hard",  "GS"),
    # M1000
    (["indian wells"],                        "hard",  "M1000"),
    (["miami"],                               "hard",  "M1000"),
    (["monte carlo","monte-carlo"],           "clay",  "M1000"),
    (["madrid"],                              "clay",  "M1000"),
    (["rome","italian open","internazionali"],"clay",  "M1000"),
    (["canada","toronto","montreal"],         "hard",  "M1000"),
    (["cincinnati"],                          "hard",  "M1000"),
    (["shanghai"],                            "hard",  "M1000"),
    (["paris masters","paris-bercy"],         "hard",  "M1000"),
    (["nitto","atp finals","turin"],          "hard",  "M1000"),
    # A500
    (["rotterdam"],                           "hard",  "A500"),
    (["dubai"],                               "hard",  "A500"),
    (["acapulco","abierto mexicano"],         "hard",  "A500"),
    (["barcelona"],                           "clay",  "A500"),
    (["hamburg"],                             "clay",  "A500"),
    (["halle","terra wortmann"],              "grass", "A500"),
    (["queens","queen's"],                    "grass", "A500"),
    (["washington","citi open"],              "hard",  "A500"),
    (["beijing","china open"],                "hard",  "A500"),
    (["tokyo","rakuten"],                     "hard",  "A500"),
    (["vienna","erste bank"],                 "hard",  "A500"),
    (["basel"],                               "hard",  "A500"),
    (["astana"],                              "hard",  "A500"),
    (["dallas"],                              "hard",  "A500"),
    (["lyon"],                                "clay",  "A500"),
]
VALID = {"GS", "M1000", "A500"}


def classify(name: str):
    nl = name.lower()
    for kws, surf, cat in TOURNAMENT_MAP:
        if any(k in nl for k in kws):
            return surf, cat
    return None, None


def parse_rows(rows) -> list:
    matches, i = [], 0
    while i < len(rows) - 1:
        r1, r2 = rows[i], rows[i+1]
        t = None
        for cell in r1.find_all("td"):
            if re.match(r'^\d{1,2}:\d{2}$', cell.get_text(strip=True)):
                t = cell.get_text(strip=True); break
        if not t:
            i += 1; continue
        def pname(row):
            for a in row.find_all("a"):
                if "/player/" in a.get("href",""):
                    return re.sub(r'\s+',' ',a.get_text(strip=True)).strip()
        def pseed(row):
            m = re.search(r'\((\d+)\)', row.get_text())
            return int(m.group(1)) if m else None
        p1, p2 = pname(r1), pname(r2)
        if p1 and p2:
            matches.append({"time":t,"player1":p1,"player2":p2,"seed1":pseed(r1),"seed2":pseed(r2)})
        i += 2
    return matches


def scrape_matches(date: datetime = None) -> list:
    if date is None:
        date = datetime.now(timezone.utc)
    url = (f"https://www.tennisexplorer.com/matches/"
           f"?type=atp-single&year={date.year}&month={date.month:02d}&day={date.day:02d}")
    print(f"[fetch_matches] {url}")
    time.sleep(random.uniform(1.0, 2.5))
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", id="matches") or soup.find("table")
    if not table:
        return []

    all_matches, cur_t, cur_s, cur_c, cur_rows = [], None, None, None, []

    def flush():
        if cur_t and cur_c in VALID and cur_rows:
            for m in parse_rows(cur_rows):
                m["tournament"] = cur_t
                m["surface"]    = cur_s
                m["category"]   = cur_c
                all_matches.append(m)
        cur_rows.clear()

    for row in table.find_all("tr"):
        cls = " ".join(row.get("class", []))
        if "head" in cls:
            flush()
            lnk = row.find("a")
            name = re.sub(r'\s+',' ',(lnk.get_text(strip=True) if lnk else row.get_text(strip=True))).strip()
            cur_s, cur_c = classify(name)
            cur_t = name
            cur_rows = []
        elif cur_t:
            cur_rows.append(row)
    flush()

    print(f"[fetch_matches] {len(all_matches)} matches found")
    for m in all_matches:
        print(f"  [{m['category']}|{m['surface']}] {m['time']} {m['player1']} vs {m['player2']}")
    return all_matches


def save_matches(matches):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(matches, f, indent=2)

if __name__ == "__main__":
    save_matches(scrape_matches())
