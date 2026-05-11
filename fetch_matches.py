"""
Napi ATP 500+ meccsek - TennisExplorer.com
Alap URL (/matches/ dátum-param nélkül), majd dátum-szekció + torna alapú szűrés.
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


def classify(name: str):
    nl = name.lower()
    for kws, surf, cat in TOURNAMENT_MAP:
        if any(k in nl for k in kws):
            return surf, cat
    return None, None


def get_html(url: str) -> str:
    """cloudscraper -> requests fallback"""
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


def parse_date_header(row) -> str | None:
    """
    Felismeri a dátum-szekció fejlécet.
    TennisExplorer formátum: '11. 05. 2026' vagy '11.05.2026'
    """
    txt = row.get_text(strip=True)
    m = re.search(r'(\d{1,2})\.\s*(\d{2})\.\s*(\d{4})', txt)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{int(m.group(1)):02d}"
    return None


def parse_match_rows(rows: list) -> list:
    matches = []
    i = 0
    while i < len(rows) - 1:
        r1, r2 = rows[i], rows[i + 1]
        # Időpont keresése az első sorban
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
                if "player" in href:
                    n = re.sub(r'\s+', ' ', a.get_text(strip=True)).strip()
                    if n and len(n) > 3:
                        return n
            return None

        def pseed(row):
            m = re.search(r'\((\d+)\)', row.get_text())
            return int(m.group(1)) if m else None

        p1, p2 = pname(r1), pname(r2)
        if p1 and p2:
            matches.append({
                "time": t,
                "player1": p1, "player2": p2,
                "seed1": pseed(r1), "seed2": pseed(r2),
            })
        i += 2
    return matches


def scrape_matches(date: datetime = None) -> list:
    if date is None:
        date = datetime.now(timezone.utc)

    today_str = date.strftime("%Y-%m-%d")

    # ── Fő URL: paraméter nélkül, ATP singles tab ──────────────────────
    # A TennisExplorer dátum-szekciókra bontva mutatja a meccseket
    url = "https://www.tennisexplorer.com/matches/?type=atp-single"
    print(f"[fetch_matches] {url}")
    print(f"[fetch_matches] Keresett dátum: {today_str}")

    try:
        html = get_html(url)
    except Exception as e:
        print(f"[fetch_matches] HIBA: {e}")
        return []

    soup  = BeautifulSoup(html, "lxml")

    # A teljes tartalom táblázatban van
    # Struktúra: date-header sor → torna-header sorok → meccs sorok
    # Keressük az összes <tr>-t, és dátum szerint szűrjük

    all_rows = soup.find_all("tr")
    print(f"[fetch_matches] Összes sor: {len(all_rows)}")

    # Gyűjtsük össze a dátum-szekciókra bontott sorokat
    sections = {}   # date_str -> [rows]
    current_date = None
    for row in all_rows:
        cls = " ".join(row.get("class", []))
        txt = row.get_text(strip=True)

        # Dátum fejléc felismerése
        d = parse_date_header(row)
        if d:
            current_date = d
            sections[d] = []
            print(f"[fetch_matches] Dátum szekció: {d}")
            continue

        if current_date:
            sections[current_date].append(row)

    print(f"[fetch_matches] Talált dátumok: {list(sections.keys())}")

    # Ha nincs mai dátum, próbáljuk a holnapit is (időzóna eltérés)
    tomorrow_str = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    target_dates = [today_str, tomorrow_str]
    print(f"[fetch_matches] Célzott dátumok: {target_dates}")

    all_matches = []
    for target_date in target_dates:
        if target_date not in sections:
            continue

        rows = sections[target_date]
        print(f"[fetch_matches] {target_date}: {len(rows)} sor feldolgozása")

        # Torna-szekciókra bontás a dátumon belül
        cur_t = cur_s = cur_c = None
        cur_rows = []

        def flush(t, s, c, rows):
            if t and c in VALID and rows:
                parsed = parse_match_rows(rows)
                for m in parsed:
                    m["tournament"] = t
                    m["surface"]    = s
                    m["category"]   = c
                    all_matches.append(m)
                if parsed:
                    print(f"  [{c}|{s}] {t}: {len(parsed)} meccs")

        for row in rows:
            cls = " ".join(row.get("class", []))
            if "head" in cls:
                flush(cur_t, cur_s, cur_c, cur_rows)
                lnk  = row.find("a")
                name = re.sub(r'\s+', ' ',
                              (lnk.get_text(strip=True) if lnk
                               else row.get_text(strip=True))).strip()
                # Torna neve: vegyük az első 40 karaktert (nem kell a S/1/2/3... rész)
                name = re.split(r'\s+[S]\s+', name)[0].strip()
                surf, cat = classify(name)
                cur_t, cur_s, cur_c = name, surf, cat
                cur_rows = []
                print(f"  Torna: [{cat}|{surf}] {name}")
            else:
                cur_rows.append(row)

        flush(cur_t, cur_s, cur_c, cur_rows)

    print(f"[fetch_matches] Összesen {len(all_matches)} ATP500+ meccs")
    return all_matches


def save_matches(matches: list):
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(matches, indent=2))
    print(f"[fetch_matches] Mentve -> {OUTPUT_PATH}")


if __name__ == "__main__":
    save_matches(scrape_matches())
