"""
Napi ATP 500+ meccsek - TennisExplorer.com
Javítások:
- Csak class="head flags" sorok = torna fejlécek (sidebar kizárva)
- "challenger" / "futures" / "utr" explicit kizárás
- "Live streams" szöveg kiszűrése a játékosnevekből
- Dátum: span.tab alapú szűrés
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

# Szavak amik garantáltan NEM ATP500+ tornák
EXCLUDE_KEYWORDS = [
    "challenger", "futures", "utr", "itf", "satellite",
    "wta", "doubles", "h2h", "main tournaments",
    "lower level", "motuwethfr",
]


def classify(name: str):
    nl = name.lower()
    # Kizárás: challenger/futures/utr stb.
    if any(kw in nl for kw in EXCLUDE_KEYWORDS):
        return None, None
    for kws, surf, cat in TOURNAMENT_MAP:
        if any(k in nl for k in kws):
            return surf, cat
    return None, None


def get_html(url: str) -> str:
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
        print(f"[fetch_matches] cloudscraper HTTP {resp.status_code}")
    except Exception as e:
        print(f"[fetch_matches] cloudscraper hiba: {e}")

    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def is_player_name(text: str) -> bool:
    """Kiszűri a 'Live streams', reklám, stb. sorokat."""
    if not text or len(text) < 3:
        return False
    bad = ["live stream", "bet365", "unibet", "1xbet", "bwin", "sky sports",
           "bein", "eurosport", "dazn", "tv", "info", "h2h"]
    tl = text.lower()
    if any(b in tl for b in bad):
        return False
    return True


def parse_player(row) -> str | None:
    for a in row.find_all("a"):
        if "player" in a.get("href", ""):
            n = re.sub(r'\s+', ' ', a.get_text(strip=True)).strip()
            if is_player_name(n):
                return n
    return None


def parse_seed(row) -> int | None:
    m = re.search(r'\((\d+)\)', row.get_text())
    return int(m.group(1)) if m else None


def parse_match_rows(rows: list) -> list:
    matches = []
    i = 0
    while i < len(rows) - 1:
        r1, r2 = rows[i], rows[i + 1]

        # Időpont az első sorban
        t = None
        for cell in r1.find_all("td"):
            txt = cell.get_text(strip=True)
            if re.match(r'^\d{1,2}:\d{2}$', txt):
                t = txt
                break
        if not t:
            i += 1
            continue

        p1 = parse_player(r1)
        p2 = parse_player(r2)

        if p1 and p2:
            matches.append({
                "time":    t,
                "player1": p1,  "player2": p2,
                "seed1":   parse_seed(r1),
                "seed2":   parse_seed(r2),
            })
        i += 2
    return matches


def get_today_str(html: str, target_date: str) -> str:
    """
    A TennisExplorer <span class="tab"> elemekben tárolja a dátumokat.
    Visszaadja hogy a célzott dátum megjelenik-e a lapon.
    """
    soup = BeautifulSoup(html, "lxml")
    for span in soup.find_all("span", class_="tab"):
        txt = span.get_text(strip=True)
        m = re.search(r'(\d{1,2})\.\s*(\d{2})\.\s*(\d{4})', txt)
        if m:
            d = f"{m.group(3)}-{m.group(2)}-{int(m.group(1)):02d}"
            print(f"[fetch_matches] Dátum tab: '{txt}' → {d}")
    return target_date


def scrape_matches(date: datetime = None) -> list:
    if date is None:
        date = datetime.now(timezone.utc)

    today_str = date.strftime("%Y-%m-%d")
    url = "https://www.tennisexplorer.com/matches/?type=atp-single"
    print(f"[fetch_matches] {url} | dátum: {today_str}")

    try:
        html = get_html(url)
    except Exception as e:
        print(f"[fetch_matches] HIBA: {e}")
        return []

    get_today_str(html, today_str)

    soup = BeautifulSoup(html, "lxml")

    # ── Fő logika: csak class="head flags" = torna fejléc ───────────────
    # Ez kizárja a sidebar táblák head sorait, amik csak class="head"-et kapnak
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

        # ── Torna fejléc: CSAK "head" ÉS "flags" együtt ─────────────────
        if "head" in classes and "flags" in classes:
            flush()
            lnk  = row.find("a")
            name = re.sub(r'\s+', ' ',
                          (lnk.get_text(strip=True) if lnk
                           else row.get_text(strip=True))).strip()
            # Levágja a "S 1 2 3 4 5 H2H H A" részt a torna névből
            name = re.split(r'\s+S\s+\d', name)[0].strip()
            surf, cat = classify(name)
            cur_t, cur_s, cur_c = name, surf, cat
            if cat in VALID:
                print(f"  ✅ Torna: [{cat}|{surf}] {name}")
            else:
                print(f"  ⏭ Kihagyva: {name}")
            cur_rows = []
        else:
            # Meccs sor (csak ha van aktív ATP500+ torna)
            if cur_c in VALID:
                cur_rows.append(row)

    flush()

    print(f"\n[fetch_matches] Összesen: {len(all_matches)} ATP500+ meccs")
    for m in all_matches:
        print(f"  {m['time']} {m['player1']} vs {m['player2']}")

    return all_matches


def save_matches(matches: list):
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(matches, indent=2))
    print(f"[fetch_matches] Mentve -> {OUTPUT_PATH}")


if __name__ == "__main__":
    save_matches(scrape_matches())
