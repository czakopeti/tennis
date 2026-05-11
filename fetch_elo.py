"""
Scrapes the FULL ATP Elo table from tennisabstract.com and saves to JSON.
Run weekly (Monday cron). Covers all players with 10+ matches in last 52 weeks.
"""
import re, time, json, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

ELO_URL     = "https://tennisabstract.com/reports/atp_elo_ratings.html"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "elo_ratings.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def surface_score(c_elo: float, h_elo: float) -> int:
    """
    1 = strong clay specialist  (cElo - hElo > 100)
    2 = clay-leaning            (40–100)
    3 = all-rounder             (-40 to +40)
    4 = hard-leaning            (-100 to -40)
    5 = strong hard specialist  (< -100)
    """
    diff = c_elo - h_elo
    if   diff >  100: return 1
    elif diff >   40: return 2
    elif diff >  -40: return 3
    elif diff > -100: return 4
    else:             return 5


def scrape_elo_ratings() -> dict:
    print(f"[fetch_elo] Fetching {ELO_URL}")
    resp = requests.get(ELO_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        raise RuntimeError("tennisabstract: ratings table not found")

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

        c_elo = sf(8)
        h_elo = sf(6)
        sc = surface_score(c_elo, h_elo) if (c_elo and h_elo) else 3

        ratings[name] = {
            "elo_rank": si(0), "age": sf(2),   "elo":  sf(3),
            "hElo":     h_elo, "cElo": c_elo,  "gElo": sf(10),
            "atp_rank": si(15), "surface_score": sc,
        }

    print(f"[fetch_elo] Scraped {len(ratings)} players")
    return ratings


def save_elo_ratings(ratings: dict):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"scraped_at": datetime.now(timezone.utc).isoformat(),
                   "source": ELO_URL, "players": ratings}, f, indent=2)
    print(f"[fetch_elo] Saved → {OUTPUT_PATH}")


if __name__ == "__main__":
    save_elo_ratings(scrape_elo_ratings())
