"""Teljes ATP Elo tábla mentése tennisabstract.com-ról. Hetente fut."""
import re, json, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

ELO_URL     = "https://tennisabstract.com/reports/atp_elo_ratings.html"
OUTPUT_PATH = Path(__file__).parent / "data" / "elo_ratings.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}

def surface_score(c, h):
    d = c - h
    if d > 100: return 1
    if d >  40: return 2
    if d > -40: return 3
    if d > -100: return 4
    return 5

def scrape_elo_ratings():
    print(f"[fetch_elo] {ELO_URL}")
    resp = requests.get(ELO_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table: raise RuntimeError("Táblázat nem található")

    ratings = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 16: continue
        link = cells[1].find("a")
        if not link: continue
        name = link.get_text(strip=True)
        if not name: continue

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

    print(f"[fetch_elo] {len(ratings)} játékos")
    return ratings

def save_elo_ratings(ratings):
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": ELO_URL, "players": ratings
    }, indent=2))
    print(f"[fetch_elo] Mentve → {OUTPUT_PATH}")

if __name__ == "__main__":
    save_elo_ratings(scrape_elo_ratings())
