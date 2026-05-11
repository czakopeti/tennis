"""
Teljes ATP Elo tábla - tennisabstract.com
Fix: player link check: 'player.cgi' not '/player/'
Fallback: ha scrape sikertelen, cached adatot tart meg.
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
    """cloudscraper -> requests fallback"""
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
        print(f"[fetch_elo] cloudscraper HTTP {resp.status_code}, fallback...")
    except Exception as e:
        print(f"[fetch_elo] cloudscraper hiba: {e}, fallback...")

    import requests
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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
    try:
        session.get("https://tennisabstract.com/", headers=headers, timeout=15)
        time.sleep(random.uniform(1.5, 3.0))
    except Exception:
        pass
    resp = session.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    print(f"[fetch_elo] requests OK ({len(resp.text):,} kar)")
    return resp.text


def parse_elo_table(html: str) -> dict:
    soup  = BeautifulSoup(html, "lxml")

    # --- DEBUG: show first few links found to verify structure ---
    all_links = soup.find_all("a", href=True)[:10]
    print(f"[parse] Első 3 link a lapon: {[(l.get('href','')[:60], l.get_text(strip=True)[:20]) for l in all_links[:3]]}")

    # Find the ratings table - look for the one containing player links
    # tennisabstract player links: href contains 'player.cgi'
    table = None
    for t in soup.find_all("table"):
        if t.find("a", href=lambda h: h and "player.cgi" in h):
            table = t
            break

    # Fallback: any table with 'Sinner' in it
    if not table:
        for t in soup.find_all("table"):
            if "Sinner" in t.get_text():
                table = t
                print("[parse] Fallback: 'Sinner' alapján találva tábla")
                break

    if not table:
        # Last resort: find all tables and show debug info
        tables = soup.find_all("table")
        print(f"[parse] WARN: player.cgi link nem található. Táblák száma: {len(tables)}")
        if tables:
            print(f"[parse] Első tábla első 200 kar: {tables[0].get_text()[:200]}")
        raise RuntimeError(f"Játékos tábla nem található. Táblák: {len(tables)}")

    ratings = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 16:
            continue

        # Player name: find link with player.cgi in href
        player_link = cells[1].find("a", href=lambda h: h and "player.cgi" in h)

        # Fallback: any link in cell 1
        if not player_link:
            player_link = cells[1].find("a")

        if not player_link:
            continue

        name = player_link.get_text(strip=True)
        if not name or len(name) < 3:
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

    # If still 0, the column indices might be wrong - try to detect
    if len(ratings) == 0:
        print("[parse] 0 játékos - column debug:")
        for row in table.find_all("tr")[:3]:
            cells = row.find_all("td")
            print(f"  {len(cells)} cella: {[c.get_text(strip=True)[:15] for c in cells[:18]]}")

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
    """Megpróbálja frissíteni. Ha nem sikerül, cached adatot használ."""
    try:
        ratings = scrape_elo_ratings()
        if len(ratings) < 50:
            raise RuntimeError(
                f"Csak {len(ratings)} játékos - valószínűleg parse hiba\n"
                f"Ellenőrizd a GitHub Actions logot a '[parse]' soroknál"
            )
        save_elo_ratings(ratings)
        print(f"[fetch_elo] SIKER: {len(ratings)} játékos mentve")
        return True
    except Exception as e:
        print(f"[fetch_elo] HIBA: {e}")
        if OUTPUT_PATH.exists():
            data = json.loads(OUTPUT_PATH.read_text())
            data["last_attempt"] = datetime.now(timezone.utc).isoformat()
            data["last_error"]   = str(e)
            OUTPUT_PATH.write_text(json.dumps(data, indent=2))
            print(f"[fetch_elo] Cached adat: {data.get('scraped_at','?')[:10]}")
            return False
        raise  # Nincs cache sem


if __name__ == "__main__":
    scrape_with_fallback()
