"""
Napi ATP 500+ meccsek - TennisExplorer.com
cloudscraper a GitHub Actions IP-blokk megkerüléséhez.
"""
import re, time, random, json
from bs4 import BeautifulSoup
from datetime import datetime, timezone
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


def classify(name: str):
    nl = name.lower()
    for kws, surf, cat in TOURNAMENT_MAP:
        if any(k in nl for k in kws):
            return surf, cat
    return None, None


def get_html(url: str) -> str:
    """cloudscraper -> requests fallback"""
    # Próba 1: cloudscraper
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        time.sleep(random.uniform(2.0, 4.0))
        resp = scraper.get(url, timeout=30)
        if resp.status_code == 200 and len(resp.text) > 2000:
            print(f"[fetch_matches] cloudscraper OK ({len(resp.text):,} kar)")
            return resp.text
        print(f"[fetch_matches] cloudscraper HTTP {resp.status_code}, fallback...")
    except Exception as e:
        print(f"[fetch_matches] cloudscraper hiba: {e}, fallback...")

    # Próba 2: requests
    import requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    print(f"[fetch_matches] requests OK ({len(resp.text):,} kar)")
    return resp.text


def parse_rows(rows: list) -> list:
    matches = []
    i = 0
    while i < len(rows) - 1:
        r1, r2 = rows[i], rows[i + 1]
        # Find time in first row
        t = None
        for cell in r1.find_all("td"):
            txt = cell.get_text(strip=True)
            if re.match(r'^\d{1,2}:\d{2}$', txt):
                t = txt
                break
        if not t:
            i += 1
            continue

        def pname(row):
            for a in row.find_all("a"):
                href = a.get("href", "")
                if "/player/" in href or "player=" in href:
                    return re.sub(r'\s+', ' ', a.get_text(strip=True)).strip()
            # fallback: any link that looks like a player name
            for a in row.find_all("a"):
                txt = a.get_text(strip=True)
                if len(txt) > 4 and txt[0].isupper():
                    return re.sub(r'\s+', ' ', txt).strip()
            return None

        def pseed(row):
            m = re.search(r'\((\d+)\)', row.get_text())
            return int(m.group(1)) if m else None

        p1, p2 = pname(r1), pname(r2)
        if p1 and p2:
            matches.append({
                "time": t, "player1": p1, "player2": p2,
                "seed1": pseed(r1), "seed2": pseed(r2),
            })
        i += 2
    return matches


def scrape_matches(date: datetime = None) -> list:
    if date is None:
        date = datetime.now(timezone.utc)

    url = (f"https://www.tennisexplorer.com/matches/"
           f"?type=atp-single"
           f"&year={date.year}&month={date.month:02d}&day={date.day:02d}")
    print(f"[fetch_matches] {url}")

    try:
        html = get_html(url)
    except Exception as e:
        print(f"[fetch_matches] HIBA a lekéréskor: {e}")
        return []

    soup  = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="matches") or soup.find("table")

    if not table:
        print(f"[fetch_matches] Táblázat nem található. HTML méret: {len(html)}")
        print(f"[fetch_matches] HTML eleje: {html[:300]}")
        return []

    # Debug: show all tournament headers found
    heads = []
    for row in table.find_all("tr"):
        if "head" in " ".join(row.get("class", [])):
            heads.append(row.get_text(strip=True)[:80])
    print(f"[fetch_matches] Torna fejlécek: {heads}")

    all_matches = []
    current = {"t": None, "s": None, "c": None, "rows": []}

    def flush():
        if current["t"] and current["c"] in VALID and current["rows"]:
            parsed = parse_rows(current["rows"])
            for m in parsed:
                m["tournament"] = current["t"]
                m["surface"]    = current["s"]
                m["category"]   = current["c"]
                all_matches.append(m)
        current["rows"] = []

    for row in table.find_all("tr"):
        cls = " ".join(row.get("class", []))
        if "head" in cls:
            flush()
            lnk  = row.find("a")
            name = re.sub(r'\s+', ' ',
                          (lnk.get_text(strip=True) if lnk
                           else row.get_text(strip=True))).strip()
            surf, cat = classify(name)
            current["t"] = name
            current["s"] = surf
            current["c"] = cat
            current["rows"] = []
            if cat in VALID:
                print(f"[fetch_matches] Torna found: [{cat}|{surf}] {name}")
            else:
                print(f"[fetch_matches] Kihagyva (nem ATP500+): {name}")
        else:
            current["rows"].append(row)

    flush()

    print(f"[fetch_matches] Összesen {len(all_matches)} meccs")
    for m in all_matches:
        print(f"  [{m['category']}|{m['surface']}] {m['time']} "
              f"{m['player1']} vs {m['player2']}")

    return all_matches


def save_matches(matches: list):
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(matches, indent=2))
    print(f"[fetch_matches] Mentve -> {OUTPUT_PATH}")


if __name__ == "__main__":
    save_matches(scrape_matches())
