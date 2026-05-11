"""
Generates index.html — mobile-first, single-column cards.
Surface score 1-5 + cElo/hElo both shown.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_HTML  = Path(__file__).parent / "index.html"
RESULTS_PATH = Path(__file__).parent / "data" / "results.json"

SURFACE_META = {
    "clay":  {"icon":"🧱","label":"Salak",  "col":"#fb923c","bg":"#ea580c1a","bd":"#ea580c40"},
    "hard":  {"icon":"💙","label":"Kemény","col":"#60a5fa","bg":"#3b82f61a","bd":"#3b82f640"},
    "grass": {"icon":"🌿","label":"Fű",    "col":"#4ade80","bg":"#22c55e1a","bd":"#22c55e40"},
}
SS_META = {
    1:{"icon":"🧱🧱","label":"Salakos spec.", "col":"#fb923c"},
    2:{"icon":"🧱",  "label":"Salak-hajlam", "col":"#fbbf24"},
    3:{"icon":"⚖",   "label":"All-rounder",  "col":"#94a3b8"},
    4:{"icon":"💙",  "label":"Kemény-hajlam","col":"#60a5fa"},
    5:{"icon":"💙💙","label":"Kemény spec.",  "col":"#818cf8"},
}


def load_results():
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f: return json.load(f)
    return []

def compute_stats(results):
    bets = [r for r in results if r.get("settled")]
    if not bets: return {"total":0,"won":0,"roi":0.0,"profit":0.0,"win_rate":0.0}
    won=sum(1 for b in bets if b["outcome"]=="win"); staked=sum(b.get("stake",0) for b in bets)
    profit=sum(b.get("profit",0) for b in bets)
    return {"total":len(bets),"won":won,"roi":round(profit/staked*100,1) if staked else 0,
            "profit":round(profit,2),"win_rate":round(won/len(bets)*100,1)}


def ss_dots(score: int, align="left") -> str:
    m = SS_META.get(score, SS_META[3])
    dots = ""
    for i in range(1,6):
        if score<=2:   filled=i<=(3-score); col="#fb923c" if filled else "#243550"
        elif score>=4: filled=i>(3-(5-score)); col="#60a5fa" if filled else "#243550"
        else:          filled=i==3; col="#94a3b8" if filled else "#243550"
        dots+=f'<span style="width:8px;height:8px;border-radius:50%;background:{col};display:inline-block;margin:0 1px"></span>'
    label_pos = "margin-left:4px" if align=="left" else "margin-right:4px;order:-1"
    return (f'<div style="display:flex;align-items:center;{"justify-content:flex-end" if align=="right" else ""}">'
            f'{"" if align=="left" else dots}'
            f'<span style="font-size:9px;color:{m["col"]};{label_pos}">{m["icon"]}</span>'
            f'{"" if align=="right" else dots}'
            f'</div>')


def render_card(m: dict) -> str:
    surf = m.get("surface","hard")
    sm   = SURFACE_META.get(surf, SURFACE_META["hard"])
    cat  = m.get("category","ATP")

    # status pill
    if m.get("status")=="live":
        pill = '<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;background:#eab30818;border:1px solid #eab30840;color:#eab308;animation:pulse 2s infinite">● LIVE</span>'
    else:
        pill = '<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;background:#3b82f618;border:1px solid #3b82f640;color:#3b82f6">Upcoming</span>'

    if not m.get("elo_found"):
        return f"""<div class="card" style="opacity:.5">
  <div class="ctop"><div class="tags"><span class="surf-tag" style="background:{sm['bg']};border-color:{sm['bd']};color:{sm['col']}">{sm['icon']} {sm['label']}</span><span class="cat-tag">{cat}</span><span class="t-tag">{m.get('time','')}</span></div>{pill}</div>
  <div class="cbody"><div class="prow-names"><span class="pn">{m['player1']}</span><span class="vs">vs</span><span class="pn" style="text-align:right">{m['player2']}</span></div>
  <div style="font-size:11px;color:#ef4444;margin-top:.3rem">⚠ {m.get('error','Elo N/A')}</div></div></div>"""

    p1,p2   = m["name1"], m["name2"]
    c1,h1   = m["c_elo1"], m["h_elo1"]
    c2,h2   = m["c_elo2"], m["h_elo2"]
    sc1,sc2 = m["surf_score1"], m["surf_score2"]
    r1,r2   = m["r1"], m["r2"]
    prob1   = m["prob1"]; prob2 = 1-prob1
    o1,o2   = m["odds1"], m["odds2"]
    delta   = c1-c2

    fav1  = prob1>=prob2
    oc1   = "#22c55e" if fav1 else "#e2e8f0"
    oc2   = "#22c55e" if not fav1 else "#e2e8f0"

    bw   = f"{prob1*100:.1f}"
    bcol = "linear-gradient(90deg,#15803d,#22c55e)" if prob1>0.65 else \
           "linear-gradient(90deg,#92400e,#d97706)" if prob1<0.40 else \
           "linear-gradient(90deg,#1d4ed8,#38bdf8)"

    seed1 = f"[{m['seed1']}] " if m.get("seed1") else ""
    seed2 = f" [{m['seed2']}]" if m.get("seed2") else ""
    rank1 = r1.get("atp_rank","?"); rank2 = r2.get("atp_rank","?")

    coin = ('<div style="font-size:10px;color:#eab308;text-align:center;margin-top:.4rem;padding:.2rem .5rem;background:#eab30810;border-radius:4px">⚠ Nyílt meccs — ΔcElo &lt; 10 pt</div>'
            if abs(delta)<10 else "")

    # Shorten long names for mobile
    def short(n):
        parts = n.split()
        if len(parts)>2 and len(n)>20:
            return f"{parts[0][0]}. {' '.join(parts[1:])}"
        return n

    p1s, p2s = short(p1), short(p2)

    return f"""<div class="card">
  <div class="ctop">
    <div class="tags">
      <span class="surf-tag" style="background:{sm['bg']};border-color:{sm['bd']};color:{sm['col']}">{sm['icon']} {sm['label']}</span>
      <span class="cat-tag">{cat}</span>
      <span class="t-tag">{m.get('time','')} UTC+1</span>
    </div>
    {pill}
  </div>
  <div class="cbody">
    <!-- Player names row -->
    <div class="prow-names">
      <div class="pinfo">
        <div class="pname">{seed1}{p1s}</div>
        <div class="pmeta">ATP #{rank1} &nbsp;·&nbsp; cElo {c1:.0f} &nbsp;·&nbsp; h {h1:.0f}</div>
        {ss_dots(sc1)}
      </div>
      <div class="vs">VS</div>
      <div class="pinfo" style="text-align:right">
        <div class="pname">{p2s}{seed2}</div>
        <div class="pmeta">ATP #{rank2} &nbsp;·&nbsp; cElo {c2:.0f} &nbsp;·&nbsp; h {h2:.0f}</div>
        {ss_dots(sc2, "right")}
      </div>
    </div>
    <!-- Odds row -->
    <div class="odds-row">
      <div class="obox">
        <div class="odec" style="color:{oc1}">{o1}</div>
        <div class="oinfo">{p1s.split()[-1]}<br><span style="color:#64748b">{prob1*100:.1f}%</span></div>
      </div>
      <div class="odelta">Δ {delta:+.0f}</div>
      <div class="obox" style="flex-direction:row-reverse;text-align:right">
        <div class="odec" style="color:{oc2}">{o2}</div>
        <div class="oinfo">{p2s.split()[-1]}<br><span style="color:#64748b">{prob2*100:.1f}%</span></div>
      </div>
    </div>
    <!-- Prob bar -->
    <div class="bar-row">
      <span class="bar-pct">{prob1*100:.1f}%</span>
      <div class="bar-out"><div class="bar-in" style="width:{bw}%;background:{bcol}"></div></div>
      <span class="bar-pct" style="text-align:right">{prob2*100:.1f}%</span>
    </div>
    {coin}
  </div>
</div>"""


def analyze_matches(matches, elo_players):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from value_calc import find_player_in_elo_db, elo_win_prob, get_surface_elo, prob_to_decimal_odds

    results = []
    for m in matches:
        surface = m.get("surface","hard")
        n1,r1 = find_player_in_elo_db(m["player1"], elo_players)
        n2,r2 = find_player_in_elo_db(m["player2"], elo_players)
        if not (r1 and r2):
            miss = m["player1"] if not r1 else m["player2"]
            results.append({**m,"elo_found":False,"error":f"Nem található: {miss}","status":m.get("status","upcoming")}); continue

        c1=get_surface_elo(r1,"clay");  h1=r1.get("hElo") or c1
        c2=get_surface_elo(r2,"clay");  h2=r2.get("hElo") or c2
        e1=get_surface_elo(r1,surface); e2=get_surface_elo(r2,surface)
        p1=elo_win_prob(e1,e2)

        results.append({**m,"name1":n1,"name2":n2,"r1":r1,"r2":r2,
            "c_elo1":c1,"h_elo1":h1,"c_elo2":c2,"h_elo2":h2,
            "surf_score1":r1.get("surface_score",3),"surf_score2":r2.get("surface_score",3),
            "prob1":p1,"odds1":prob_to_decimal_odds(p1),"odds2":prob_to_decimal_odds(1-p1),
            "elo_found":True,"error":None,"status":m.get("status","upcoming")})
    return results


def generate_html(analyses, elo_meta=None, bankroll=1000.0):
    stats   = compute_stats(load_results())
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    scraped = (elo_meta or {}).get("scraped_at","?")[:10]
    live    = [m for m in analyses if m.get("status")=="live"]
    rest    = [m for m in analyses if m.get("status")!="live"]
    found   = sum(1 for m in analyses if m.get("elo_found"))

    def section(title, lst):
        if not lst: return ""
        cards = "\n".join(render_card(m) for m in lst)
        return f'<div class="sec">{title}</div><div class="cards">{cards}</div>'

    HTML = f"""<!DOCTYPE html>
<html lang="hu">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="theme-color" content="#0b1525">
  <title>ATP Value Bet</title>
  <style>
    :root{{--bg:#0b1525;--bg2:#111d30;--bg3:#162038;--bd:#1e3050;--tx:#e2e8f0;--mu:#64748b;--ac:#3b82f6;--cy:#38bdf8;--gr:#22c55e;--rd:#ef4444;--ye:#eab308}}
    *{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}}
    body{{background:var(--bg);color:var(--tx);font-family:-apple-system,'SF Pro Display',system-ui,sans-serif;font-size:14px;line-height:1.5;min-height:100vh}}

    /* ── Header ── */
    header{{background:linear-gradient(135deg,#091220,#162038);border-bottom:1px solid var(--bd);padding:.75rem 1rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.4rem;position:sticky;top:0;z-index:100;backdrop-filter:blur(12px)}}
    .logo{{font-size:1.1rem;font-weight:700;letter-spacing:-.3px}}.logo span{{color:var(--ac)}}
    .hmeta{{display:flex;gap:.3rem;flex-wrap:wrap}}
    .hb{{font-size:9px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:2px 7px;border-radius:4px;background:#1e3050;border:1px solid var(--bd);color:var(--mu)}}

    /* ── Layout ── */
    main{{max-width:600px;margin:0 auto;padding:.75rem .75rem 5rem}}
    .sec{{font-size:9px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--mu);border-bottom:1px solid var(--bd);padding-bottom:.35rem;margin:.75rem 0 .5rem}}
    .sec:first-child{{margin-top:.1rem}}

    /* ── Stats bar ── */
    .statbar{{display:flex;gap:.4rem;overflow-x:auto;padding-bottom:.25rem;margin-bottom:.15rem;scrollbar-width:none}}
    .statbar::-webkit-scrollbar{{display:none}}
    .stat{{background:var(--bg2);border:1px solid var(--bd);border-radius:8px;padding:.5rem .75rem;flex-shrink:0;min-width:90px}}
    .sl{{font-size:9px;color:var(--mu);text-transform:uppercase;letter-spacing:.8px}}
    .sv{{font-size:1.15rem;font-weight:700;margin-top:1px}}

    /* ── Cards ── */
    .cards{{display:flex;flex-direction:column;gap:.5rem}}
    .card{{background:var(--bg2);border:1px solid var(--bd);border-radius:12px;overflow:hidden}}
    .ctop{{display:flex;justify-content:space-between;align-items:center;padding:.45rem .75rem .2rem;flex-wrap:wrap;gap:.25rem}}
    .tags{{display:flex;gap:.3rem;align-items:center;flex-wrap:wrap}}
    .surf-tag{{font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px;text-transform:uppercase;letter-spacing:.8px;border:1px solid}}
    .cat-tag{{font-size:9px;color:var(--mu);padding:2px 6px;border:1px solid var(--bd);border-radius:4px}}
    .t-tag{{font-size:10px;color:var(--mu)}}

    .cbody{{padding:.5rem .75rem .7rem}}

    /* ── Players ── */
    .prow-names{{display:grid;grid-template-columns:1fr auto 1fr;gap:.3rem;align-items:start;margin-bottom:.55rem}}
    .pinfo{{min-width:0}}
    .pname{{font-weight:600;font-size:.88rem;line-height:1.25;word-break:break-word}}
    .pmeta{{font-size:9px;color:var(--cy);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .vs{{font-size:9px;font-weight:700;color:var(--mu);padding:.3rem .1rem 0;white-space:nowrap}}

    /* ── Odds ── */
    .odds-row{{display:grid;grid-template-columns:1fr auto 1fr;gap:.3rem;align-items:center;margin-bottom:.45rem}}
    .obox{{background:var(--bg3);border:1px solid var(--bd);border-radius:7px;padding:.4rem .5rem;display:flex;align-items:center;gap:.35rem}}
    .odec{{font-size:1.35rem;font-weight:800;line-height:1}}
    .oinfo{{font-size:10px;line-height:1.4}}
    .odelta{{font-size:9px;color:var(--mu);text-align:center;white-space:nowrap}}

    /* ── Bar ── */
    .bar-row{{display:flex;align-items:center;gap:.35rem}}
    .bar-pct{{font-size:10px;font-weight:700;min-width:36px}}
    .bar-out{{flex:1;height:5px;background:#1e3050;border-radius:4px;overflow:hidden}}
    .bar-in{{height:100%;border-radius:4px}}

    /* ── Legend ── */
    .legend{{background:var(--bg2);border:1px solid var(--bd);border-radius:9px;padding:.6rem .75rem;font-size:11px;color:var(--mu);line-height:1.7;margin-bottom:.25rem}}

    /* ── Footer ── */
    footer{{border-top:1px solid var(--bd);padding:.75rem 1rem;color:var(--mu);font-size:10px;text-align:center}}

    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.5}}}}

    /* ── iOS safe area ── */
    @supports(padding:max(0px)){{
      main{{padding-bottom:max(5rem,calc(5rem + env(safe-area-inset-bottom)))}}
      footer{{padding-bottom:max(.75rem,calc(.75rem + env(safe-area-inset-bottom)))}}
    }}
  </style>
</head>
<body>
<header>
  <div class="logo">ATP <span>Value</span> Bet</div>
  <div class="hmeta">
    <span class="hb">🔄 {updated}</span>
    <span class="hb">Elo: {scraped}</span>
  </div>
</header>
<main>

<div class="sec" style="margin-top:.1rem">Összesítő</div>
<div class="statbar">
  <div class="stat"><div class="sl">Meccsek</div><div class="sv" style="color:var(--ac)">{len(analyses)}</div></div>
  <div class="stat"><div class="sl">Élő</div><div class="sv" style="color:var(--ye)">{len(live)}</div></div>
  <div class="stat"><div class="sl">Elo OK</div><div class="sv" style="color:var(--gr)">{found}/{len(analyses)}</div></div>
  <div class="stat"><div class="sl">ROI</div><div class="sv" style="color:{'var(--gr)' if stats['roi']>=0 else 'var(--rd)'}">{stats['roi']:+.1f}%</div></div>
  <div class="stat"><div class="sl">P&L</div><div class="sv" style="color:{'var(--gr)' if stats['profit']>=0 else 'var(--rd)'}">${stats['profit']:+.0f}</div></div>
</div>

<div class="legend">
  <strong style="color:var(--tx)">Surface score:</strong> &nbsp;
  🧱🧱 Salak spec. (1) &nbsp;·&nbsp; 🧱 Salak-hajlam (2) &nbsp;·&nbsp; ⚖ All-rounder (3) &nbsp;·&nbsp; 💙 Kemény-hajlam (4) &nbsp;·&nbsp; 💙💙 Kemény spec. (5)<br>
  <strong style="color:var(--tx)">Odds</strong> = 1/P(Elo), margin nélkül.
</div>

{section("● Folyamatban", live)}
{section("Várható" if live else "Mai meccsek", rest)}

</main>
<footer>Forrás: tennisabstract.com · cElo/hElo · Fair odds · Nem befektetési tanácsadás.</footer>
</body>
</html>"""

    OUTPUT_HTML.write_text(HTML, encoding="utf-8")
    print(f"[generate_html] → {OUTPUT_HTML}")


if __name__ == "__main__":
    generate_html([], bankroll=1000)
