"""
Napi ATP 500+ meccsek - TennisExplorer.com
DEBUG verzió: kiírja a HTML struktúrát a logba.
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


def debug_html_structure(html: str):
    """Kiírja a HTML struktúrát hogy lássuk a dátum/torna fejléceket."""
    soup = BeautifulSoup(html, "lxml")

    print("\n[DEBUG] === Első 50 TR sor class és szöveg ===")
    for i, row in enumerate(soup.find_all("tr")[:50]):
        cls  = row.get("class", [])
        txt  = row.get_text(separator=" ", strip=True)[:80]
        if cls or any(x in txt.lower() for x in ["2026","rome","madrid","atp","date","result"]):
            print(f"  [{i}] class={cls} | {txt}")

    print("\n[DEBUG] === Minden div/span/td ami dátumot tartalmaz ===")
    for el in soup.find_all(text=re.compile(r'\d{1,2}\.\s*\d{2}\.\s*20\d{2}'))[:10]:
        parent = el.parent
        print(f"  tag={parent.name} class={parent.get('class',[])} | '{el.strip()}'")

    print("\n[DEBUG] === 'rome' vagy 'Rome' előfordulások ===")
    for el in soup.find_all(text=re.compile(r'[Rr]ome'))[:5]:
        parent = el.parent
        gp     = parent.parent
        print(f"  tag={parent.name} class={parent.get('class',[])} gp={gp.name} | '{el.strip()[:60]}'")

    print("\n[DEBUG] === Összes unique TR class ===")
    classes = set()
    for row in soup.find_all("tr"):
        cls = tuple(row.get("class", []))
        classes.add(cls)
    for c in sorted(classes):
        print(f"  {c}")


def parse_match_rows(rows: list) -> list:
    matches = []
    i = 0
    while i < len(rows) - 1:
        r1, r2 = rows[i], rows[i + 1]
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
                if "player" in a.get("href", ""):
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
                "time": t, "player1": p1, "player2": p2,
                "seed1": pseed(r1), "seed2": pseed(r2),
            })
        i += 2
    return matches


def scrape_matches(date: datetime = None) -> list:
    if date is None:
        date = datetime.now(timezone.utc)

    today_str    = date.strftime("%Y-%m-%d")
    tomorrow_str = (date + timedelta(days=1)).strftime("%Y-%m-%d")

    url = "https://www.tennisexplorer.com/matches/?type=atp-single"
    print(f"[fetch_matches] {url} | keresett dátum: {today_str}")

    try:
        html = get_html(url)
    except Exception as e:
        print(f"[fetch_matches] HIBA: {e}")
        return []

    # DEBUG: térképezzük fel a struktúrát
    debug_html_structure(html)

    soup     = BeautifulSoup(html, "lxml")
    all_rows = soup.find_all("tr")

    # ── Próba 1: dátum-szekció alapú parsing ────────────────────────────
    # Dátum fejléc: <tr class="result"> vagy hasonló, szöveg: "11. 05. 2026"
    date_pattern = re.compile(r'(\d{1,2})\.\s*(\d{2})\.\s*(\d{4})')

    sections      = {}
    current_date  = None

    for row in all_rows:
        txt = row.get_text(separator=" ", strip=True)
        m   = date_pattern.search(txt)
        if m and len(txt) < 120:   # dátum fejléc rövid szövegű
            d = f"{m.group(3)}-{m.group(2)}-{int(m.group(1)):02d}"
            current_date = d
            if d not in sections:
                sections[d] = []
            continue
        if current_date:
            sections[current_date].append(row)

    print(f"[fetch_matches] Dátum szekciók (1. próba): {list(sections.keys())}")

    # ── Próba 2: ha nincs dátum-szekció, próbáljuk az összes sort ───────
    # A "Rome" előfordulástól kezdve feldolgozunk mindent
    target_rows = []
    for d in [today_str, tomorrow_str]:
        if d in sections:
            target_rows.extend(sections[d])

    if not target_rows:
        print("[fetch_matches] Dátum-szekció alapján nincs találat, próba: 'rome' keresése")
        rome_found = False
        for row in all_rows:
            txt_low = row.get_text(strip=True).lower()
            if "rome" in txt_low or "internazionali" in txt_low:
                rome_found = True
            if rome_found:
                target_rows.append(row)
        print(f"[fetch_matches] 'Rome' keresés: {len(target_rows)} sor")

    # ── Parse torna-szekciók a célzott sorokból ──────────────────────────
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
            if parsed:
                print(f"  -> [{cur_c}|{cur_s}] {cur_t}: {len(parsed)} meccs")
        cur_rows = []

    for row in target_rows:
        cls = " ".join(row.get("class", []))
        if "head" in cls:
            flush()
            lnk  = row.find("a")
            name = re.sub(r'\s+', ' ',
                          (lnk.get_text(strip=True) if lnk
                           else row.get_text(strip=True))).strip()
            name = re.split(r'\s+S\s+', name)[0].strip()
            surf, cat = classify(name)
            cur_t, cur_s, cur_c = name, surf, cat
            cur_rows = []
            print(f"  Torna: [{cat}|{surf}] {name}")
        else:
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
