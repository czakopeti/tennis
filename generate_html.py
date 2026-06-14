import json
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_HTML  = Path(__file__).parent / "index.html"
RESULTS_PATH = Path(__file__).parent / "data" / "results.json"
CPI_PATH     = Path(__file__).parent / "data" / "court_cpi.json"

SURFACE_META = {
    "clay":  {"icon": "🧱", "label": "Salak",  "col": "#fb923c", "bg": "#ea580c1a", "bd": "#ea580c40"},
    "hard":  {"icon": "💙", "label": "Kemény", "col": "#60a5fa", "bg": "#3b82f61a", "bd": "#3b82f640"},
    "grass": {"icon": "🌿", "label": "Fű",     "col": "#4ade80", "bg": "#22c55e1a", "bd": "#22c55e40"},
}
TOUR_META = {
    "ATP": {"col": "#3b82f6", "bg": "#3b82f618", "bd": "#3b82f640"},
    "WTA": {"col": "#ec4899", "bg": "#ec489918", "bd": "#ec489940"},
}

# SS9 ikonok + színek
SS9 = {
    1: {"icon": "🧱🧱🧱", "col": "#c2410c"},
    2: {"icon": "🧱🧱",   "col": "#ea580c"},
    3: {"icon": "🧱",     "col": "#f97316"},
    4: {"icon": "🔸",     "col": "#fbbf24"},
    5: {"icon": "⚖",      "col": "#94a3b8"},
    6: {"icon": "🔹",     "col": "#60a5fa"},
    7: {"icon": "💙",     "col": "#3b82f6"},
    8: {"icon": "💙💙",   "col": "#2563eb"},
    9: {"icon": "💙💙💙", "col": "#1d4ed8"},
}

SS9_LABEL = {
    1:"Extrém salak",2:"Erős salakos",3:"Salak-hajlam",4:"Enyhe salak",
    5:"All-rounder",6:"Enyhe gyors",7:"Gyors-hajlam",8:"Erős gyors",9:"Extrém gyors"
}


def load_cpi() -> dict:
    if CPI_PATH.exists():
        return json.loads(CPI_PATH.read_text())
    return {}


def load_results():
    if RESULTS_PATH.exists():
        return json.load(open(RESULTS_PATH))
    return []


def compute_stats(results):
    bets = [r for r in results if r.get("settled")]
    if not bets:
        return {"total": 0, "roi": 0.0, "profit": 0.0}
    staked = sum(b.get("stake", 0) for b in bets)
    profit = sum(b.get("profit", 0) for b in bets)
    return {"total": len(bets),
            "roi": round(profit / staked * 100, 1) if staked else 0,
            "profit": round(profit, 2)}


def ss9_display(ss: int) -> str:
    m = SS9.get(ss, SS9[5])
    return (f'<span style="font-size:11px;font-weight:700;color:{m["col"]}">'
            f'{m["icon"]}</span>')


def cpi_badge(cpi: float) -> str:
    if cpi < 30:
        col, lbl = "#f97316", "Lassú"
    elif cpi < 35:
        col, lbl = "#fbbf24", "Köz-lassú"
    elif cpi < 40:
        col, lbl = "#94a3b8", "Közepes"
    elif cpi < 45:
        col, lbl = "#60a5fa", "Köz-gyors"
    else:
        col, lbl = "#818cf8", "Gyors"
    return (f'<span style="font-size:9px;font-weight:700;padding:1px 5px;'
            f'border-radius:3px;background:{col}18;border:1px solid {col}40;color:{col}">'
            f'CPI {cpi:.0f} · {lbl}</span>')


def edge_badge(edge) -> str:
    if edge is None:
        return ""
    col = "#22c55e" if edge >= 0.04 else ("#94a3b8" if edge >= 0 else "#ef4444")
    bg  = "#22c55e18" if edge >= 0.04 else "#1e3050"
    bd  = "#22c55e40" if edge >= 0.04 else "#1e3050"
    lbl = " VALUE" if edge >= 0.04 else ""
    return (f'<span style="font-size:9px;font-weight:700;padding:2px 5px;'
            f'border-radius:4px;background:{bg};border:1px solid {bd};color:{col}">'
            f'{edge*100:+.1f}%%{lbl}</span>')


def render_card(m: dict) -> str:
    surf = m.get("surface", "hard")
    sm_s = SURFACE_META.get(surf, SURFACE_META["hard"])
    tour = m.get("tour", "ATP")
    tm   = TOUR_META.get(tour, TOUR_META["ATP"])
    cat  = m.get("category", "")
    tourn = m.get("tournament", "")
    cpi  = m.get("court_cpi", 0)

    pill = ('<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;'
            'background:#eab30818;border:1px solid #eab30840;color:#eab308;animation:pulse 2s infinite">'
            '● LIVE</span>'
            if m.get("status") == "live" else
            '<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;'
            'background:#3b82f618;border:1px solid #3b82f640;color:#3b82f6">Upcoming</span>')

    # Helyszín + torna sor
    tourn_str = f'<span style="font-size:10px;color:#64748b">{tourn}</span> ' if tourn else ""
    cpi_str   = cpi_badge(cpi) if cpi else ""

    if not m.get("elo_found"):
        return (f'<div class="card" style="opacity:.5"><div class="ctop">'
                f'<div class="tags">'
                f'<span class="surf-tag" style="background:{sm_s["bg"]};border-color:{sm_s["bd"]};color:{sm_s["col"]}">'
                f'{sm_s["icon"]} {sm_s["label"]}</span>'
                f'<span class="cat-tag" style="color:{tm["col"]};border-color:{tm["bd"]}">{tour} {cat}</span>'
                f'<span class="t-tag">{m.get("time","")}</span></div>{pill}</div>'
                f'<div style="padding:.4rem .75rem;font-size:11px">{tourn_str}{cpi_str}</div>'
                f'<div class="cbody"><div style="font-weight:600">'
                f'{m["player1"]} <span style="color:#64748b">vs</span> {m["player2"]}</div>'
                f'<div style="font-size:11px;color:#ef4444;margin-top:.3rem">⚠ {m.get("error","Elo N/A")}'
                f'</div></div></div>')

    p1, p2     = m["name1"], m["name2"]
    r1, r2     = m["r1"], m["r2"]
    c1, h1     = m["c_elo1"], m["h_elo1"]
    c2, h2     = m["c_elo2"], m["h_elo2"]
    ss1, ss2   = m["ss1"], m["ss2"]
    prob1      = m["prob1"]; prob2 = 1 - prob1
    o1, o2     = m["odds1"], m["odds2"]
    bo1, bo2   = m.get("book_odds_home"), m.get("book_odds_away")
    e1, e2     = m.get("edge1"), m.get("edge2")
    delta      = (c1 - c2) if surf == "clay" else (h1 - h2)

    oc1 = "#22c55e" if prob1 >= prob2 else "#e2e8f0"
    oc2 = "#22c55e" if prob1 < prob2  else "#e2e8f0"
    bw  = f"{round(prob1*100,1)}"
    bcol = ("linear-gradient(90deg,#15803d,#22c55e)" if prob1 > 0.65
            else "linear-gradient(90deg,#92400e,#d97706)" if prob1 < 0.40
            else "linear-gradient(90deg,#1d4ed8,#38bdf8)")

    def short(n):
        pts = n.split()
        return f"{pts[0][0]}. {' '.join(pts[1:])}" if len(pts) > 2 and len(n) > 20 else n

    p1s, p2s = short(p1), short(p2)
    s1 = f"[{m['seed1']}] " if m.get("seed1") else ""
    s2 = f" [{m['seed2']}]" if m.get("seed2") else ""

    book_row = ""
    if bo1 or bo2:
        book_row = (
            '<div style="display:flex;align-items:center;justify-content:space-between;'
            'background:#0d1e35;border:1px solid #1e3050;border-radius:7px;padding:.35rem .6rem;'
            'margin-top:.35rem;gap:.3rem">'
            '<div style="display:flex;align-items:center;gap:.35rem">'
            '<span style="font-size:9px;color:#64748b">Bukméker</span>'
            f'<span style="font-size:1.1rem;font-weight:800;color:#e2e8f0">{bo1 or "—"}</span>'
            f'{edge_badge(e1)}</div>'
            '<span style="font-size:9px;color:#64748b">TE odds</span>'
            f'<div style="display:flex;align-items:center;gap:.35rem">{edge_badge(e2)}'
            f'<span style="font-size:1.1rem;font-weight:800;color:#e2e8f0">{bo2 or "—"}</span>'
            '</div></div>')

    coin = ('<div style="font-size:10px;color:#eab308;text-align:center;margin-top:.3rem;'
            'padding:2px .5rem;background:#eab30810;border-radius:4px">'
            '⚠ Nyílt meccs — ΔElo &lt; 10</div>'
            if abs(delta) < 10 else "")

    return f"""<div class="card">
  <div class="ctop">
    <div class="tags">
      <span class="surf-tag" style="background:{sm_s["bg"]};border-color:{sm_s["bd"]};color:{sm_s["col"]}">{sm_s["icon"]} {sm_s["label"]}</span>
      <span class="cat-tag" style="color:{tm["col"]};border-color:{tm["bd"]}">{tour} {cat}</span>
      <span class="t-tag">{m.get("time","")} UTC+1</span>
    </div>{pill}
  </div>
  <div style="padding:2px .75rem 4px;display:flex;align-items:center;gap:6px;flex-wrap:wrap">
    {tourn_str}{cpi_str}
  </div>
  <div class="cbody">
    <div class="prow">
      <div class="pinfo">
        <div class="pname">{s1}{p1s}</div>
        <div class="pmeta">#{r1.get("atp_rank","?")} · c{c1:.0f} · h{h1:.0f}</div>
        <div style="margin-top:3px">{ss9_display(ss1)} <span style="font-size:9px;color:{SS9[ss1]["col"]}">{ss1} · {SS9_LABEL[ss1]}</span></div>
      </div>
      <div class="vs">VS</div>
      <div class="pinfo" style="text-align:right">
        <div class="pname">{p2s}{s2}</div>
        <div class="pmeta">#{r2.get("atp_rank","?")} · c{c2:.0f} · h{h2:.0f}</div>
        <div style="margin-top:3px"><span style="font-size:9px;color:{SS9[ss2]["col"]}">{SS9_LABEL[ss2]} · {ss2}</span> {ss9_display(ss2)}</div>
      </div>
    </div>
    <div class="odds-row">
      <div class="obox"><div class="odec" style="color:{oc1}">{o1}</div>
        <div class="oinfo"><span style="font-size:9px;color:#64748b">Fair</span><br>{p1s.split()[-1]}<br><span style="color:#64748b">{prob1*100:.1f}%%</span></div></div>
      <div class="odelta">Δ {delta:+.0f}</div>
      <div class="obox" style="flex-direction:row-reverse;text-align:right">
        <div class="odec" style="color:{oc2}">{o2}</div>
        <div class="oinfo"><span style="font-size:9px;color:#64748b">Fair</span><br>{p2s.split()[-1]}<br><span style="color:#64748b">{prob2*100:.1f}%%</span></div></div>
    </div>
    {book_row}{coin}
    <div class="bar-row">
      <span class="bar-pct">{prob1*100:.1f}%%</span>
      <div class="bar-out"><div class="bar-in" style="width:{bw}%%;background:{bcol}"></div></div>
      <span class="bar-pct" style="text-align:right">{prob2*100:.1f}%%</span>
    </div>
  </div>
</div>"""


def analyze_matches(matches, elo_players):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from value_calc import (find_player_in_elo_db, elo_win_prob,
                            get_surface_elo, prob_to_decimal_odds,
                            compute_edge, player_ss9, get_court_cpi)
    cpi_db = load_cpi()
    results = []
    for m in matches:
        surf  = m.get("surface", "hard")
        tourn = m.get("tournament", "")
        n1, r1 = find_player_in_elo_db(m["player1"], elo_players)
        n2, r2 = find_player_in_elo_db(m["player2"], elo_players)
        if not (r1 and r2):
            miss = m["player1"] if not r1 else m["player2"]
            results.append({**m, "elo_found": False,
                            "error": f"N/A: {miss}",
                            "status": m.get("status", "upcoming")})
            continue

        c1 = get_surface_elo(r1, "clay");  h1 = r1.get("hElo") or c1
        c2 = get_surface_elo(r2, "clay");  h2 = r2.get("hElo") or c2
        e1 = get_surface_elo(r1, surf);    e2 = get_surface_elo(r2, surf)
        p1 = elo_win_prob(e1, e2)

        bo1 = m.get("book_odds_home"); bo2 = m.get("book_odds_away")
        edge1 = compute_edge(p1,     bo1) if bo1 else None
        edge2 = compute_edge(1 - p1, bo2) if bo2 else None

        ss1 = player_ss9(r1, surf)
        ss2 = player_ss9(r2, surf)

        # CPI: előbb a betöltött JSON-ból, fallback a value_calc-ból
        cpi_val = None
        if cpi_db:
            tl = tourn.lower()
            for k, v in cpi_db.items():
                if not k.startswith("default_") and (k in tl or tl in k):
                    cpi_val = v; break
        if cpi_val is None:
            cpi_val = get_court_cpi(tourn, surf)

        results.append({**m,
            "name1": n1, "name2": n2, "r1": r1, "r2": r2,
            "c_elo1": c1, "h_elo1": h1, "c_elo2": c2, "h_elo2": h2,
            "ss1": ss1, "ss2": ss2,
            "prob1": p1,
            "odds1": prob_to_decimal_odds(p1),
            "odds2": prob_to_decimal_odds(1 - p1),
            "book_odds_home": bo1, "book_odds_away": bo2,
            "edge1": edge1, "edge2": edge2,
            "court_cpi": cpi_val,
            "tournament": tourn,
            "elo_found": True, "error": None,
            "status": m.get("status", "upcoming")})
    return results


def generate_html(atp_analyses, wta_analyses=None, elo_meta=None, bankroll=1000.0):
    wta_analyses = wta_analyses or []
    stats   = compute_stats(load_results())
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    scraped = (elo_meta or {}).get("scraped_at", "?")[:10]

    all_live    = [m for m in atp_analyses + wta_analyses if m.get("status") == "live"]
    rest_atp    = [m for m in atp_analyses if m.get("status") != "live"]
    rest_wta    = [m for m in wta_analyses if m.get("status") != "live"]

    def cards(lst):
        if not lst:
            return '<p style="color:#64748b;padding:.5rem 0;font-size:12px">Nincs meccs.</p>'
        return "".join(render_card(m) for m in lst)

    def section(title, lst, color="#94a3b8"):
        if not lst:
            return ""
        return (f'<div class="sec" style="color:{color}">{title}</div>'
                f'<div class="cards">{cards(lst)}</div>')

    total_val = sum(1 for m in atp_analyses + wta_analyses
                    if (m.get("edge1") or 0) >= 0.04 or (m.get("edge2") or 0) >= 0.04)

    HTML = """<!DOCTYPE html>
<html lang="hu">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="theme-color" content="#0b1525">
  <title>ATP WTA Value Bet</title>
  <style>
    :root{--bg:#0b1525;--bg2:#111d30;--bg3:#162038;--bd:#1e3050;--tx:#e2e8f0;--mu:#64748b;--ac:#3b82f6;--cy:#38bdf8;--gr:#22c55e;--rd:#ef4444;--ye:#eab308;--pink:#ec4899}
    *{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
    body{background:var(--bg);color:var(--tx);font-family:-apple-system,system-ui,sans-serif;font-size:14px;line-height:1.5;min-height:100vh}
    header{background:linear-gradient(135deg,#091220,#162038);border-bottom:1px solid var(--bd);padding:.75rem 1rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.4rem;position:sticky;top:0;z-index:100;backdrop-filter:blur(12px)}
    .logo{font-size:1.1rem;font-weight:700}.logo .atp{color:var(--ac)}.logo .wta{color:var(--pink)}
    .hmeta{display:flex;gap:.3rem;flex-wrap:wrap}
    .hb{font-size:9px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:2px 7px;border-radius:4px;background:#1e3050;border:1px solid var(--bd);color:var(--mu)}
    main{max-width:600px;margin:0 auto;padding:.75rem .75rem 5rem}
    .sec{font-size:9px;font-weight:700;letter-spacing:2px;text-transform:uppercase;border-bottom:1px solid var(--bd);padding-bottom:.35rem;margin:.75rem 0 .5rem}
    .statbar{display:flex;gap:.4rem;overflow-x:auto;padding-bottom:.25rem;margin-bottom:.25rem;scrollbar-width:none}
    .statbar::-webkit-scrollbar{display:none}
    .stat{background:var(--bg2);border:1px solid var(--bd);border-radius:8px;padding:.5rem .75rem;flex-shrink:0;min-width:82px}
    .sl{font-size:9px;color:var(--mu);text-transform:uppercase;letter-spacing:.8px}
    .sv{font-size:1.1rem;font-weight:700;margin-top:1px}
    .legend{background:var(--bg2);border:1px solid var(--bd);border-radius:9px;padding:.6rem .75rem;font-size:11px;color:var(--mu);line-height:1.7;margin-bottom:.25rem}
    .cards{display:flex;flex-direction:column;gap:.5rem}
    .card{background:var(--bg2);border:1px solid var(--bd);border-radius:12px;overflow:hidden}
    .ctop{display:flex;justify-content:space-between;align-items:center;padding:.45rem .75rem .2rem;flex-wrap:wrap;gap:.25rem}
    .tags{display:flex;gap:.3rem;align-items:center;flex-wrap:wrap}
    .surf-tag{font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px;text-transform:uppercase;letter-spacing:.8px;border:1px solid}
    .cat-tag{font-size:9px;padding:2px 6px;border:1px solid var(--bd);border-radius:4px;font-weight:600}
    .t-tag{font-size:10px;color:var(--mu)}
    .cbody{padding:.5rem .75rem .7rem}
    .prow{display:grid;grid-template-columns:1fr auto 1fr;gap:.3rem;align-items:start;margin-bottom:.5rem}
    .pinfo{min-width:0}
    .pname{font-weight:600;font-size:.88rem;line-height:1.25;word-break:break-word}
    .pmeta{font-size:9px;color:var(--cy);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .vs{font-size:9px;font-weight:700;color:var(--mu);padding:.3rem .1rem 0;white-space:nowrap}
    .odds-row{display:grid;grid-template-columns:1fr auto 1fr;gap:.3rem;align-items:center;margin-bottom:.3rem}
    .obox{background:var(--bg3);border:1px solid var(--bd);border-radius:7px;padding:.4rem .5rem;display:flex;align-items:center;gap:.35rem}
    .odec{font-size:1.3rem;font-weight:800;line-height:1}
    .oinfo{font-size:10px;line-height:1.4}
    .odelta{font-size:9px;color:var(--mu);text-align:center;white-space:nowrap}
    .bar-row{display:flex;align-items:center;gap:.35rem;margin-top:.4rem}
    .bar-pct{font-size:10px;font-weight:700;min-width:36px}
    .bar-out{flex:1;height:5px;background:#1e3050;border-radius:4px;overflow:hidden}
    .bar-in{height:100%%;border-radius:4px}
    footer{border-top:1px solid var(--bd);padding:.75rem 1rem;color:var(--mu);font-size:10px;text-align:center}
    @keyframes pulse{0%%,100%%{opacity:1}50%%{opacity:.5}}
    @supports(padding:max(0px)){main{padding-bottom:max(5rem,calc(5rem + env(safe-area-inset-bottom)))}}
  </style>
</head>
<body>
<header>
  <div class="logo"><span class="atp">ATP</span> · <span class="wta">WTA</span> Value Bet</div>
  <div class="hmeta">
    <span class="hb">🔄 %s</span>
    <span class="hb">Elo: %s</span>
  </div>
</header>
<main>
<div class="sec" style="margin-top:.1rem;color:#94a3b8">Összesítő</div>
<div class="statbar">
  <div class="stat"><div class="sl">ATP</div><div class="sv" style="color:var(--ac)">%d</div></div>
  <div class="stat"><div class="sl">WTA</div><div class="sv" style="color:var(--pink)">%d</div></div>
  <div class="stat"><div class="sl">Élő</div><div class="sv" style="color:var(--ye)">%d</div></div>
  <div class="stat"><div class="sl">Value</div><div class="sv" style="color:var(--gr)">%d</div></div>
  <div class="stat"><div class="sl">ROI</div><div class="sv" style="color:%s">%+.1f%%</div></div>
</div>
<div class="legend">
  🧱🧱🧱(1) 🧱🧱(2) 🧱(3) 🔸(4) ⚖(5) 🔹(6) 💙(7) 💙💙(8) 💙💙💙(9) — borítás preferencia<br>
  CPI = Court Pace Index (ITF) · &lt;30 lassú · 30-34 köz-lassú · 35-39 közepes · 40-44 köz-gyors · &gt;44 gyors<br>
  Value = Elo alapú fair odds vs bukméker odds, edge ≥ 4%%
</div>
%s%s%s
</main>
<footer>tennisabstract.com Elo (ATP+WTA) · TennisExplorer odds · CPI: courtspeed.com · Nem befektetési tanácsos.</footer>
</body>
</html>""" % (
        updated, scraped,
        len(atp_analyses), len(wta_analyses), len(all_live), total_val,
        "var(--gr)" if stats["roi"] >= 0 else "var(--rd)", stats["roi"],
        (f'<div class="sec" style="color:var(--ye)">● Élő</div>'
         f'<div class="cards">{cards(all_live)}</div>') if all_live else "",
        section("ATP — Mai meccsek", rest_atp, "var(--ac)"),
        section("WTA — Mai meccsek", rest_wta, "var(--pink)"),
    )

    OUTPUT_HTML.write_text(HTML, encoding="utf-8")
    print(f"[generate_html] → {OUTPUT_HTML}")


if __name__ == "__main__":
    generate_html([], [], bankroll=1000)
