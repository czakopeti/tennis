"""
Teljes ATP Elo tábla mentése tennisabstract.com-ról.
cloudscraper-t használ a GitHub Actions IP-blokk megkerüléséhez.
Ha a scrape meghiúsul, a cached adatot tartja meg (nem töri el a pipeline-t).
"""
import re, json, time, random
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

ELO_URL     = "https://tennisabstract.com/reports/atp_elo_ratings.html"
OUTPUT_PATH = Path(__file__).parent / "data" / "elo_ratings.json"


def surface_score(c, h):
    d = c - h
    if d >  100: return 1
    if d >   40: return 2
    if d >  -40: return 3
    if d > -100: return 4
    return 5


def get_html(url: str) -> str:
    """
    1. cloudscraper (megkerüli bot-védelmet)
    2. requests + Chrome headers (fallback)
    """
    # Próba 1: cloudscraper
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        time.sleep(random.uniform(2.0, 4.0))
        resp = scraper.get(url, timeout=30)
        if resp.status_code == 200 and len(resp.text) > 5000:
            print(f"[fetch_elo] cloudscraper OK ({len(resp.text):,} kar)")
            return resp.text
        print(f"[fetch_elo] cloudscraper: HTTP {resp.status_code}, fallback...")
    except Exception as e:
        print(f"[fetch_elo] cloudscraper hiba: {e}, fallback...")

    # Próba 2: requests + teljes Chrome headers
    import requests
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    # Látogassuk meg a főoldalt először (session, cookie)
    try:
        session.get("https://tennisabstract.com/", headers=headers, timeout=15)
        time.sleep(random.uniform(1.5, 3.0))
    except Exception:
        pass

    resp = session.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    print(f"[fetch_elo] requests fallback OK ({len(resp.text):,} kar)")
    return resp.text


def parse_elo_table(html: str) -> dict:
    soup  = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        raise RuntimeError("Tábla nem található")

    ratings = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 16:
            continue
        link = cells[1].find("a")
        if not link:
            continue
        name = link.get_text(strip=True)
        if not name:
            continue

        def sf(i):
            try: return float(cells[i].get_text(strip=True))
            except: return None
        def si(i):
            try: return int(cells[i].get_text(strip=True))
            except: return None

        c, h = sf(8), sf(6)
        ratings[name] = {
            "elo_rank": si(0), "age": sf(2), "elo": sf(3),
            "hElo": h, "cElo": c, "gElo": sf(10),
            "atp_rank": si(15),
            "surface_score": surface_score(c, h) if (c and h) else 3,
        }
    return ratings


def scrape_elo_ratings() -> dict:
    print(f"[fetch_elo] {ELO_URL}")
    html    = get_html(ELO_URL)
    ratings = parse_elo_table(html)
    print(f"[fetch_elo] {len(ratings)} játékos")
    return ratings


def save_elo_ratings(ratings: dict):
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": ELO_URL,
        "players": ratings,
    }, indent=2))
    print(f"[fetch_elo] Mentve -> {OUTPUT_PATH}")


def scrape_with_fallback() -> bool:
    """
    Megpróbálja frissíteni az Elo-t.
    Ha sikertelen: cached adatot hagyja, NEM töri el a pipeline-t.
    """
    try:
        ratings = scrape_elo_ratings()
        if len(ratings) < 50:
            raise RuntimeError(f"Csak {len(ratings)} játékos - valószínűleg részleges adat")
        save_elo_ratings(ratings)
        return True
    except Exception as e:
        print(f"[fetch_elo] HIBA: {e}")
        if OUTPUT_PATH.exists():
            data = json.loads(OUTPUT_PATH.read_text())
            data["last_attempt"] = datetime.now(timezone.utc).isoformat()
            data["last_error"]   = str(e)
            OUTPUT_PATH.write_text(json.dumps(data, indent=2))
            scraped = data.get("scraped_at","?")[:10]
            print(f"[fetch_elo] Cached adat hasznalata ({scraped})")
            return False
        raise  # Ha nincs cache sem, valódi hiba


if __name__ == "__main__":
    scrape_with_fallback()
