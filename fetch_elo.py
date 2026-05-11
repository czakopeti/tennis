"""
ATP + WTA Elo tábla mentése tennisabstract.com-ról.
Két külön JSON: elo_ratings_atp.json, elo_ratings_wta.json
"""
import re, json, time, random
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
URLS = {
    "atp": "https://tennisabstract.com/reports/atp_elo_ratings.html",
    "wta": "https://tennisabstract.com/reports/wta_elo_ratings.html",
}


def surface_score(c, h):
    d = c - h
    if d >  100: return 1
    if d >   40: return 2
    if d >  -40: return 3
    if d > -100: return 4
    return 5


def get_html(url):
    try:
        import cloudscraper
        s = cloudscraper.create_scraper(
            browser={"browser":"chrome","platform":"windows","mobile":False})
        time.sleep(random.uniform(2.0, 4.0))
        r = s.get(url, timeout=30)
        if r.status_code == 200 and len(r.text) > 5000:
            print(f"[fetch_elo] cloudscraper OK ({len(r.text):,} kar)")
            return r.text
        print(f"[fetch_elo] cloudscraper HTTP {r.status_code}")
    except Exception as e:
        print(f"[fetch_elo] cloudscraper: {e}")
    import requests
    h = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
         "Accept":"text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"}
    try:
        requests.get("https://tennisabstract.com/", headers=h, timeout=10)
        time.sleep(random.uniform(1.5,3.0))
    except: pass
    r = requests.get(url, headers=h, timeout=30)
    r.raise_for_status()
    return r.text


def parse_table(html):
    soup  = BeautifulSoup(html, "lxml")
    # Find table with player.cgi links
    table = next((t for t in soup.find_all("table")
                  if t.find("a", href=lambda h: h and "player.cgi" in h)), None)
    if not table:
        table = next((t for t in soup.find_all("table")
                      if len(t.find_all("tr")) > 10), None)
    if not table:
        raise RuntimeError("Táblázat nem található")

    ratings = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 16: continue
        link = cells[1].find("a")
        if not link: continue
        name = link.get_text(strip=True)
        if not name or len(name) < 3: continue

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


def scrape_with_fallback(tour: str) -> bool:
    url      = URLS[tour]
    out_path = DATA_DIR / f"elo_ratings_{tour}.json"
    print(f"[fetch_elo_{tour.upper()}] {url}")
    try:
        html    = get_html(url)
        ratings = parse_table(html)
        if len(ratings) < 50:
            raise RuntimeError(f"Csak {len(ratings)} játékos")
        DATA_DIR.mkdir(exist_ok=True)
        out_path.write_text(json.dumps({
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "tour": tour.upper(),
            "source": url,
            "players": ratings,
        }, indent=2))
        print(f"[fetch_elo_{tour.upper()}] ✅ {len(ratings)} játékos mentve")
        return True
    except Exception as e:
        print(f"[fetch_elo_{tour.upper()}] HIBA: {e}")
        if out_path.exists():
            data = json.loads(out_path.read_text())
            data["last_attempt"] = datetime.now(timezone.utc).isoformat()
            data["last_error"]   = str(e)
            out_path.write_text(json.dumps(data, indent=2))
            print(f"[fetch_elo_{tour.upper()}] 📦 Cached: {data.get('scraped_at','?')[:10]}")
            return False
        raise


if __name__ == "__main__":
    scrape_with_fallback("atp")
    time.sleep(3)
    scrape_with_fallback("wta")
