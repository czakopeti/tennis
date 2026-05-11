"""
Generates index.html from today's match analyses.
Cards show: cElo, hElo, surface score (1–5), fair decimal odds, win probability bar.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_HTML  = Path(__file__).parent.parent / "index.html"
RESULTS_PATH = Path(__file__).parent.parent / "data" / "results.json"

SURFACE_META = {
    "clay":  {"icon":"🧱", "label":"Salak",  "color":"#ea580c", "bg":"#ea580c22", "border":"#ea580c50"},
    "hard":  {"icon":"💙", "label":"Kemény", "color":"#3b82f6", "bg":"#3b82f620", "border":"#3b82f640"},
    "grass": {"icon":"🌿", "label":"Fű",     "color":"#22c55e", "bg":"#22c55e20", "border":"#22c55e40"},
}

SURFACE_SCORE_META = {
    1: {"icon":"🧱🧱", "label":"Salakos spec.",  "color":"#fb923c"},
    2: {"icon":"🧱",   "label":"Salak-hajlam",  "color":"#fbbf24"},
    3: {"icon":"⚖",    "label":"All-rounder",   "color":"#94a3b8"},
    4: {"icon":"💙",   "label":"Kemény-hajlam", "color":"#60a5fa"},
    5: {"icon":"💙💙", "label":"Kemény spec.",  "color":"#818cf8"},
}


def load_results():
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return []


def compute_stats(results):
    bets = [r for r in results if r.get("settled")]
    if not bets:
        return {"total":0,"won":0,"roi":0.0,"profit":0.0,"staked":0.0,"win_rate":0.0}
    won    = sum(1 for b in bets if b["outcome"]=="win")
    staked = sum(b.get("stake",0) for b in bets)
    profit = sum(b.get("profit",0) for b in bets)
    return {"total":len(bets),"won":won,"roi":round(profit/staked*100,1) if staked else 0,
            "profit":round(profit,2),"staked":round(staked,2),
            "win_rate":round(won/len(bets)*100,1)}


def pct(v):
    return f"{v*100:.1f}%" if v is not None else "N/A"


def render_surface_dot(score: int) -> str:
    """Renders 5-dot visual indicator."""
    m = SURFACE_SCORE_META.get(score, SURFACE_SCORE_META[3])
    dots = ""
    for i in range(1, 6):
        if score <= 2:       # clay side
            filled = i <= (3 - score)
            dot_col = "#fb923c" if filled else "#1e3050"
            label = "salak"
        elif score >= 4:     # hard side
            filled = i > (3 - (5 - score))
            dot_col = "#60a5fa" if filled else "#1e3050"
            label = "kemény"
        else:                # 3 = all-rounder, middle dot
            filled = i == 3
            dot_col = "#94a3b8" if filled else "#1e3050"
            label = "all-rounder"
        dots += f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{dot_col};margin:0 1px" title="{label}"></span>'
    return f'<div style="display:flex;align-items:center;gap:3px">{dots}<span style="font-size:10px;color:{m["color"]};margin-left:4px">{m["icon"]} {m["label"]}</span></div>'


def render_player_block(name, atp_rank, c_elo, h_elo, surf_score, seed=None, align="left") -> str:
    seed_str = f" · [{seed}]" if seed else ""
    ta = "right" if align == "right" else "left"
    sc_meta = SURFACE_SCORE_META.get(surf_score, SURFACE_SCORE_META[3])
    dots_html = render_surface_dot(surf_score)
    if align == "right":
        # reverse dots order for right-aligned player
        dots_html_r = f'<div style="display:flex;align-items:center;gap:3px;justify-content:flex-end">' \
                      f'<span style="font-size:10px;color:{sc_meta["color"]};margin-right:4px">{sc_meta["icon"]} {sc_meta["label"]}</span>'
        for i in range(1, 6):
            if surf_score <= 2:
                filled = i <= (3 - surf_score); dot_col = "#fb923c" if filled else "#1e3050"
            elif surf_score >= 4:
                filled = i > (3 - (5 - surf_score)); dot_col = "#60a5fa" if filled else "#1e3050"
            else:
                filled = i == 3; dot_col = "#94a3b8" if filled else "#1e3050"
            dots_html_r += f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{dot_col};margin:0 1px"></span>'
        dots_html_r += '</div>'
        dots_html = dots_html_r

    return f"""<div style="text-align:{ta}">
      <div style="font-weight:600;font-size:.92rem">{name}</div>
      <div style="font-size:11px;color:#64748b;margin-top:1px">ATP #{atp_rank}{seed_str}</div>
      <div style="font-size:11px;color:#38bdf8;margin-top:1px">cElo <strong>{c_elo:.1f}</strong> &nbsp;|&nbsp; hElo {h_elo:.1f}</div>
      <div style="margin-top:4px">{dots_html}</div>
    </div>"""


def render_match_card(m: dict) -> str:
    surface = m.get("surface", "hard")
    sm      = SURFACE_META.get(surface, SURFACE_META["hard"])
    cat     = m.get("category", "ATP")
    tourn   = m.get("tournament", "ATP")

    status  = m.get("status", "upcoming")
    if status == "live":
        pill = '<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;background:#eab30820;border:1px solid #eab30845;color:#eab308;animation:pulse 2s infinite">● LIVE</span>'
    else:
        pill = '<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;background:#3b82f620;border:1px solid #3b82f640;color:#3b82f6">Upcoming</span>'

    if not m.get("elo_found"):
        return f"""<div style="background:#111d30;border:1px solid #1e3050;border-radius:11px;overflow:hidden;opacity:.55;padding:.75rem 1rem">
          <div style="display:flex;gap:.4rem;align-items:center;margin-bottom:.4rem">
            <span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;background:{sm['bg']};border:1px solid {sm['border']};color:{sm['color']}">{sm['icon']} {sm['label']}</span>
            <span style="font-size:10px;color:#64748b">{cat} · {m.get('time','')}</span>
          </div>
          <div style="font-size:.92rem;font-weight:600">{m['player1']} <span style="color:#64748b">vs</span> {m['player2']}</div>
          <div style="font-size:11px;color:#ef4444;margin-top:.3rem">⚠ {m.get('error','Elo nem elérhető')}</div>
        </div>"""

    p1, p2   = m["name1"], m["name2"]
    r1, r2   = m["r1"],    m["r2"]
    c1, h1   = m["c_elo1"], m["h_elo1"]
    c2, h2   = m["c_elo2"], m["h_elo2"]
    sc1, sc2 = m["surf_score1"], m["surf_score2"]
    prob1    = m["prob1"]
    prob2    = 1 - prob1
    odds1    = m["odds1"]
    odds2    = m["odds2"]
    delta    = c1 - c2

    fav1 = prob1 >= prob2
    o1_color = "#22c55e" if fav1 else "#e2e8f0"
    o2_color = "#22c55e" if not fav1 else "#e2e8f0"

    bar_width = f"{prob1*100:.1f}"
    bar_col   = "linear-gradient(90deg,#15803d,#22c55e)" if prob1 > 0.65 else \
                "linear-gradient(90deg,#1d4ed8,#38bdf8)" if prob1 > 0.50 else \
                "linear-gradient(90deg,#92400e,#d97706)"

    coin_note = ""
    if abs(delta) < 10:
        coin_note = '<div style="font-size:10px;color:#eab308;text-align:center;margin-top:.35rem">⚠ Szinte teljesen nyílt meccs (ΔcElo &lt; 10)</div>'

    p1_block = render_player_block(p1, r1.get("atp_rank","?"), c1, h1, sc1, m.get("seed1"))
    p2_block = render_player_block(p2, r2.get("atp_rank","?"), c2, h2, sc2, m.get("seed2"), align="right")

    live_border = f"border-color:#eab30850" if status == "live" else ""

    return f"""<div style="background:#111d30;border:1px solid #1e3050;{live_border};border-radius:11px;overflow:hidden;transition:border-color .15s">
  <div style="display:flex;justify-content:space-between;align-items:center;padding:.5rem 1rem .25rem;flex-wrap:wrap;gap:.3rem">
    <div style="display:flex;gap:.4rem;align-items:center">
      <span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;text-transform:uppercase;letter-spacing:1px;background:{sm['bg']};border:1px solid {sm['border']};color:{sm['color']}">{sm['icon']} {sm['label']}</span>
      <span style="font-size:10px;color:#64748b;padding:2px 6px;border:1px solid #1e3050;border-radius:4px">{cat} · R</span>
      <span style="font-size:11px;color:#64748b">{m.get('time','')} UTC+1</span>
    </div>
    {pill}
  </div>
  <div style="padding:.65rem 1rem .9rem">
    <div style="display:grid;grid-template-columns:1fr 28px 1fr;gap:.4rem;align-items:start;margin-bottom:.65rem">
      {p1_block}
      <div style="text-align:center;font-size:10px;font-weight:700;color:#64748b;padding-top:.5rem">VS</div>
      {p2_block}
    </div>
    <!-- odds boxes -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
      <div style="background:#162038;border:1px solid #1e3050;border-radius:8px;padding:.55rem .75rem;display:flex;align-items:center;gap:.5rem">
        <div style="font-size:1.5rem;font-weight:800;color:{o1_color};min-width:52px">{odds1}</div>
        <div>
          <div style="font-size:11px;font-weight:600">{p1.split()[-1]}</div>
          <div style="font-size:11px;color:#64748b">{prob1*100:.1f}% esély</div>
          <div style="font-size:10px;color:#38bdf8">Δ cElo {delta:+.1f}</div>
        </div>
      </div>
      <div style="background:#162038;border:1px solid #1e3050;border-radius:8px;padding:.55rem .75rem;display:flex;align-items:center;flex-direction:row-reverse;gap:.5rem">
        <div style="font-size:1.5rem;font-weight:800;color:{o2_color};min-width:52px;text-align:right">{odds2}</div>
        <div style="text-align:right">
          <div style="font-size:11px;font-weight:600">{p2.split()[-1]}</div>
          <div style="font-size:11px;color:#64748b">{prob2*100:.1f}% esély</div>
          <div style="font-size:10px;color:#38bdf8">cElo Δ {-delta:+.1f}</div>
        </div>
      </div>
    </div>
    <!-- prob bar -->
    <div style="display:flex;align-items:center;gap:.4rem;margin-top:.5rem">
      <span style="font-size:11px;font-weight:700;min-width:38px">{prob1*100:.1f}%</span>
      <div style="flex:1;height:6px;background:#1e3050;border-radius:6px;overflow:hidden">
        <div style="height:100%;width:{bar_width}%;background:{bar_col};border-radius:6px"></div>
      </div>
      <span style="font-size:11px;font-weight:700;min-width:38px;text-align:right">{prob2*100:.1f}%</span>
    </div>
    {coin_note}
  </div>
</div>"""


def analyze_matches(matches: list, elo_players: dict) -> list:
    """Enrich match list with Elo data."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from value_calc import find_player_in_elo_db, elo_win_prob, get_surface_elo, prob_to_decimal_odds

    results = []
    for m in matches:
        surface = m.get("surface", "hard")
        n1, r1  = find_player_in_elo_db(m["player1"], elo_players)
        n2, r2  = find_player_in_elo_db(m["player2"], elo_players)

        if not (r1 and r2):
            missing = m["player1"] if not r1 else m["player2"]
            results.append({**m, "elo_found": False, "error": f"Nem található: {missing}",
                            "status": m.get("status","upcoming")})
            continue

        c1, h1 = get_surface_elo(r1, "clay"), r1.get("hElo")
        c2, h2 = get_surface_elo(r2, "clay"), r2.get("hElo")
        e1      = get_surface_elo(r1, surface)
        e2      = get_surface_elo(r2, surface)
        p1      = elo_win_prob(e1, e2)

        results.append({
            **m,
            "name1": n1, "name2": n2, "r1": r1, "r2": r2,
            "c_elo1": c1, "h_elo1": h1 or c1,
            "c_elo2": c2, "h_elo2": h2 or c2,
            "surf_score1": r1.get("surface_score", 3),
            "surf_score2": r2.get("surface_score", 3),
            "prob1": p1,
            "odds1": prob_to_decimal_odds(p1),
            "odds2": prob_to_decimal_odds(1 - p1),
            "elo_found": True, "error": None,
            "status": m.get("status", "upcoming"),
        })
    return results


def generate_html(analyses: list, elo_meta: dict = None, bankroll: float = 1000.0):
    results   = load_results()
    stats     = compute_stats(results)
    updated   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    scraped   = (elo_meta or {}).get("scraped_at", "?")[:10]

    live_cards     = [m for m in analyses if m.get("status") == "live"]
    upcoming_cards = [m for m in analyses if m.get("status") != "live"]

    def cards_html(lst):
        if not lst:
            return '<p style="color:#64748b;padding:1rem 0">Nincs meccs ebben a kategóriában.</p>'
        return "\n".join(render_match_card(m) for m in lst)

    total_found = sum(1 for m in analyses if m.get("elo_found"))

    HTML = f"""<!DOCTYPE html>
<html lang="hu">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ATP Value Bet Dashboard</title>
  <style>
    :root{{--bg:#0b1525;--bg2:#111d30;--bg3:#162038;--border:#1e3050;--text:#e2e8f0;--muted:#64748b;--accent:#3b82f6;--cyan:#38bdf8;--green:#22c55e;--red:#ef4444;--yellow:#eab308}}
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:var(--bg);color:var(--text);font-family:-apple-system,system-ui,sans-serif;font-size:14px;line-height:1.5}}
    header{{background:linear-gradient(135deg,#091220,#162038);border-bottom:1px solid var(--border);padding:.9rem 1.5rem;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:.6rem}}
    .logo{{font-size:1.15rem;font-weight:700}}.logo span{{color:var(--accent)}}
    .hb{{font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;padding:3px 9px;border-radius:4px;background:#1e3050;border:1px solid var(--border);color:var(--muted)}}
    main{{max-width:920px;margin:0 auto;padding:1.25rem 1rem 3rem}}
    .sec{{font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border);padding-bottom:.4rem;margin-bottom:.75rem;margin-top:1.5rem}}
    .sec:first-child{{margin-top:.25rem}}
    .sg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.6rem;margin-bottom:.25rem}}
    .sc{{background:var(--bg2);border:1px solid var(--border);border-radius:9px;padding:.75rem 1rem}}
    .sl{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px}}
    .sv{{font-size:1.35rem;font-weight:700;margin-top:2px}}
    .cards{{display:flex;flex-direction:column;gap:.6rem;margin-bottom:.5rem}}
    .legend{{background:var(--bg2);border:1px solid var(--border);border-radius:9px;padding:.75rem 1rem;font-size:12px;color:var(--muted);line-height:1.8;margin-bottom:1rem}}
    footer{{border-top:1px solid var(--border);padding:1rem 1.5rem;color:var(--muted);font-size:11px;text-align:center}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.55}}}}
    @media(max-width:540px){{.sg{{grid-template-columns:repeat(2,1fr)}}}}
  </style>
</head>
<body>
<header>
  <div class="logo">ATP <span>Value</span> Bet</div>
  <div style="display:flex;gap:.4rem;flex-wrap:wrap;align-items:center">
    <span class="hb">🔄 {updated}</span>
    <span class="hb">Elo: {scraped}</span>
    <span class="hb">tennisabstract.com</span>
  </div>
</header>
<main>

<div class="sec">Összesítő</div>
<div class="sg">
  <div class="sc"><div class="sl">Meccsek ma</div><div class="sv" style="color:var(--accent)">{len(analyses)}</div></div>
  <div class="sc"><div class="sl">Élő</div><div class="sv" style="color:var(--yellow)">{len(live_cards)}</div></div>
  <div class="sc"><div class="sl">Elo lefedve</div><div class="sv" style="color:var(--green)">{total_found}/{len(analyses)}</div></div>
  <div class="sc"><div class="sl">Track record</div><div class="sv" style="color:var(--accent)">{stats['total']} fogadás</div></div>
  <div class="sc"><div class="sl">ROI</div><div class="sv" style="color:{'var(--green)' if stats['roi']>=0 else 'var(--red)'}">{stats['roi']:+.1f}%</div></div>
  <div class="sc"><div class="sl">P&L</div><div class="sv" style="color:{'var(--green)' if stats['profit']>=0 else 'var(--red)'}">${stats['profit']:+.2f}</div></div>
</div>

<div class="legend">
  <strong style="color:var(--text)">Surface score (1–5):</strong> &nbsp;
  🧱🧱 Erős salakos (1) · 🧱 Salak-hajlam (2) · ⚖ All-rounder (3) · 💙 Kemény-hajlam (4) · 💙💙 Erős keménypályás (5)<br>
  Számítás: cElo − hElo különbség alapján. &nbsp;|&nbsp; 
  <strong style="color:var(--text)">Fair odds</strong> = 1/P, margin nélkül (P₁+P₂=100%).
</div>

{"<div class='sec'>● Folyamatban</div><div class='cards'>" + cards_html(live_cards) + "</div>" if live_cards else ""}

<div class="sec">{"Várható" if live_cards else "Mai meccsek"}</div>
<div class="cards">{cards_html(upcoming_cards)}</div>

</main>
<footer>Adatforrás: kizárólag tennisabstract.com · cElo/hElo = surface Elo (Sackmann-módszer) · Fair odds = 1/P · Nem befektetési tanácsadás.</footer>
</body>
</html>"""

    OUTPUT_HTML.write_text(HTML, encoding="utf-8")
    print(f"[generate_html] → {OUTPUT_HTML}")


if __name__ == "__main__":
    # test with empty data
    generate_html([], bankroll=1000)
