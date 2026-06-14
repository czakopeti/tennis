"""
fetch_cpi.py — CPI (Court Pace Index) automatikus frissítés
Forrás: courtspeed.com (Google Sheets alapú, évente egyszer fut)
Kimenet: data/court_cpi.json
"""
import json, re, sys
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

OUT = Path(__file__).parent / "data" / "court_cpi.json"

# Google Sheets CSV export (courtspeed.com adatforrása)
SHEETS_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1artEsVLOOjwSEafl4RfMnLhfEUnsQKa7aQNIyaPVnLI/export?format=csv"
)

# Fallback: beégetett 3 éves átlagok (ha a Sheet nem elérhető)
HARDCODED = {
    "french open":        21.0,
    "roland garros":      21.0,
    "wimbledon":          37.0,
    "us open":            43.0,
    "australian open":    43.0,
    "monte carlo":        29.0,
    "madrid":             28.0,
    "rome":               28.0,
    "italian open":       28.0,
    "indian wells":       36.0,
    "miami":              39.0,
    "canada":             41.0,
    "montreal":           41.0,
    "toronto":            41.0,
    "cincinnati":         40.0,
    "shanghai":           38.0,
    "paris":              40.0,
    "paris masters":      40.0,
    "atp finals":         41.0,
    "halle":              38.0,
    "queens":             38.0,
    "eastbourne":         37.0,
    "s-hertogenbosch":    37.0,
    # defaults
    "default_clay":       27.0,
    "default_hard":       37.0,
    "default_indoor":     41.0,
    "default_grass":      37.0,
}

def parse_sheets_csv(text: str) -> dict:
    """CSV-ből kinyeri a tornánkénti legutóbbi CPI értéket."""
    result = {}
    lines = text.strip().splitlines()
    if not lines:
        return result
    # Header sort keresése (Tournament, year columns)
    header = None
    for i, line in enumerate(lines):
        if "tournament" in line.lower() or "court" in line.lower():
            header = i
            break
    if header is None:
        return result
    cols = [c.strip().strip('"').lower() for c in lines[header].split(",")]
    year_cols = [i for i, c in enumerate(cols) if re.match(r"'?\d{2}", c)]
    if not year_cols:
        return result

    for line in lines[header+1:]:
        parts = [p.strip().strip('"') for p in line.split(",")]
        if not parts or not parts[0]:
            continue
        name = parts[0].lower().strip()
        # Legutóbbi érvényes CPI
        cpi = None
        for ci in reversed(year_cols):
            if ci < len(parts):
                val = parts[ci].strip()
                try:
                    cpi = float(val)
                    break
                except ValueError:
                    continue
        if cpi and name:
            result[name] = cpi
    return result


def main():
    print("[fetch_cpi] CPI frissítés indítása...")
    cpi_data = dict(HARDCODED)

    try:
        r = requests.get(SHEETS_URL, timeout=15)
        if r.status_code == 200:
            parsed = parse_sheets_csv(r.text)
            if parsed:
                cpi_data.update(parsed)
                print(f"[fetch_cpi] Google Sheets: {len(parsed)} torna frissítve")
            else:
                print("[fetch_cpi] Sheets üres/nem parseable, beégetett adatok használva")
        else:
            print(f"[fetch_cpi] Sheets HTTP {r.status_code}, beégetett adatok használva")
    except Exception as e:
        print(f"[fetch_cpi] Sheets hiba: {e}, beégetett adatok használva")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(cpi_data, indent=2, ensure_ascii=False))
    print(f"[fetch_cpi] Mentve → {OUT} ({len(cpi_data)} torna)")


if __name__ == "__main__":
    main()
