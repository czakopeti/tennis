import re, time, random, json
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

# ... (Az ATP_MAP és WTA_MAP részed maradjon változatlan) ...

def scrape_tour(url, tour_map, valid_cats, label):
    print(f"\n[fetch_{label}] {url}")
    try:
        html = get_html(url)
    except Exception as e:
        print(f"[fetch_{label}] HIBA: {e}")
        return []

    soup = BeautifulSoup(html, "lxml")
    
    # --- DEBUG SOR 1: Megnézzük, egyáltalán hány sort lát az oldalon ---
    all_tr = soup.find_all("tr")
    print(f"[debug] Összesen {len(all_tr)} sort találtam az oldalon.")

    all_matches = []
    cur_t = cur_s = cur_c = cur_tour = None
    cur_rows = []

    def flush():
        nonlocal cur_rows
        if cur_t and cur_c in valid_cats and cur_rows:
            parsed = parse_match_rows(cur_rows)
            for m in parsed:
                m.update({"tournament": cur_t, "surface": cur_s,
                           "category": cur_c, "tour": cur_tour})
                all_matches.append(m)
            print(f"  ✅ [{cur_c}|{cur_s}] {cur_t}: {len(parsed)} meccs")
        cur_rows = []

    for row in all_tr:
        classes = row.get("class", [])

        # Torna fejléc keresése
        if "head" in classes and ("flags" in classes or row.find("td", class_="flags")):
            flush()
            lnk  = row.find("a")
            name = re.sub(r'\s+', ' ', (lnk.get_text(strip=True) if lnk else row.get_text(strip=True))).strip()
            
            # --- DEBUG SOR 2: Kiírjuk minden talált torna nevét, mielőtt szűrnénk ---
            surf, cat, tour = classify(name, tour_map, valid_cats)
            print(f"[debug] Talált torna: '{name}' -> Besorolás: {cat}")

            cur_t, cur_s, cur_c, cur_tour = name, surf, cat, tour
            cur_rows = []
        
        elif cur_c in valid_cats:
            cur_rows.append(row)

    flush()
    
    # --- DEBUG SOR 3: A végén kiírjuk, mennyi maradt meg a szűrő után ---
    print(f"[debug] {label} szűrés után megmaradt meccsek száma: {len(all_matches)}")
    return all_matches

# ... (A többi függvényed maradjon úgy, ahogy volt) ...
