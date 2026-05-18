import json
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_HTML  = Path(__file__).parent / "index.html"
RESULTS_PATH = Path(__file__).parent / "data" / "results.json"

SURFACE_META = {
    "clay":  {"icon":"🧱","label":"Salak",  "col":"#fb923c","bg":"#ea580c1a","bd":"#ea580c40"},
    "hard":  {"icon":"💙","label":"Kemeny", "col":"#60a5fa","bg":"#3b82f61a","bd":"#3b82f640"},
    "grass": {"icon":"🌿","label":"Fu",     "col":"#4ade80","bg":"#22c55e1a","bd":"#22c55e40"},
}
SS_META = {
    1:{"icon":"🧱🧱","col":"#fb923c"},
    2:{"icon":"🧱",  "col":"#fbbf24"},
    3:{"icon":"⚖",   "col":"#94a3b8"},
    4:{"icon":"💙",  "col":"#60a5fa"},
    5:{"icon":"💙💙","col":"#818cf8"},
}
TOUR_META = {
    "ATP": {"label":"ATP","col":"#3b82f6","bg":"#3b82f618","bd":"#3b82f640"},
    "WTA": {"label":"WTA","col":"#ec4899","bg":"#ec489918","bd":"#ec489940"},
}


def load_results():
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f: return json.load(f)
    return []

def compute_stats(results):
    bets = [r for r in results if r.get("settled")]
    if not bets: return {"total":0,"roi":0.0,"profit":0.0}
    staked = sum(b.get("stake",0) for b in bets)
    profit = sum(b.get("profit",0) for b in bets)
    return {"total":len(bets),
            "roi":round(profit/staked*100,1) if staked else 0,
            "profit":round(profit,2)}


def ss_dots(score, align="left"):
    m = SS_META.get(score, SS_META[3])
    dots = ""
    for i in range(1,6):
        if score<=2:   filled=i<=(3-score); col="#fb923c" if filled else "#1e3a5f"
        elif score>=4: filled=i>(3-(5-score)); col="#60a5fa" if filled else "#1e3a5f"
        else:          filled=i==3; col="#94a3b8" if filled else "#1e3a5f"
        dots += '<span style="width:7px;height:7px;border-radius:50%;display:inline-block;margin:0 1px;background:%s"></span>' % col
    lbl = '<span style="font-size:9px;color:%s;margin-%s:3px">%s</span>' % (m["col"], "left" if align=="left" else "right", m["icon"])
    if align=="left":
        return '<div style="display:flex;align-items:center;gap:1px">%s%s</div>' % (lbl, dots)
    return '<div style="display:flex;align-items:center;gap:1px;justify-content:flex-end">%s%s</div>' % (dots, lbl)


def edge_badge(edge):
    if edge is None: return ""
    col = "#22c55e" if edge>=0.04 else ("#94a3b8" if edge>=0 else "#ef4444")
    bg  = "#22c55e18" if edge>=0.04 else "#1e3050"
    bd  = "#22c55e40" if edge>=0.04 else "#1e3050"
    lbl = " VALUE" if edge>=0.04 else ""
    return '<span style="font-size:9px;font-weight:700;padding:2px 5px;border-radius:4px;background:%s;border:1px solid %s;color:%s">%+.1f%%%s</span>' % (bg, bd, col, edge*100, lbl)


def adv_badge(adv, player_num, surface):
    if adv != player_num: return ""
    sl = {"clay":"salakon","hard":"keményen","grass":"füvön"}.get(surface, surface)
    return ('<div style="margin-top:3px;padding:2px 6px;border-radius:4px;'
            'background:#f59e0b15;border:1px solid #f59e0b35;'
            'font-size:9px;font-weight:700;color:#f59e0b">'
            '⚡ Felületi előny — jobb %s</div>') % sl


def sm_badge(sm, player_num, surface):
    """Surface Match: all 3 conditions met."""
    if sm != player_num: return ""
    sl = {"clay":"salakon","hard":"keményen","grass":"füvön"}.get(surface, surface)
    return ('<div style="margin-top:3px;padding:2px 6px;border-radius:4px;'
            'background:#a855f718;border:1px solid #a855f740;'
            'font-size:9px;font-weight:700;color:#c084fc">'
            '🎯 SURFACE MATCH — erősebb %s, piac aluláraz</div>') % sl


def render_card(m):
    surf = m.get("surface","hard")
    sm_s = SURFACE_META.get(surf, SURFACE_META["hard"])
    cat  = m.get("category","ATP")
    tour = m.get("tour","ATP")
    tm   = TOUR_META.get(tour, TOUR_META["ATP"])

    pill = ('<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;'
            'background:#eab30818;border:1px solid #eab30840;color:#eab308;animation:pulse 2s infinite">● LIVE</span>'
            if m.get("status")=="live" else
            '<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;'
            'background:#3b82f618;border:1px solid #3b82f640;color:#3b82f6">Upcoming</span>')

    if not m.get("elo_found"):
        return ('<div class="card" style="opacity:.5"><div class="ctop">'
                '<div class="tags"><span class="surf-tag" style="background:%s;border-color:%s;color:%s">%s %s</span>'
                '<span class="cat-tag" style="color:%s;border-color:%s">%s %s</span>'
                '<span class="t-tag">%s</span></div>%s</div>'
                '<div class="cbody"><div style="font-weight:600">%s <span style="color:#64748b">vs</span> %s</div>'
                '<div style="font-size:11px;color:#ef4444;margin-top:.3rem">⚠ %s</div></div></div>') % (
            sm_s["bg"],sm_s["bd"],sm_s["col"],sm_s["icon"],sm_s["label"],
            tm["col"],tm["bd"],tour,cat,
            m.get("time",""), pill,
            m["player1"],m["player2"],m.get("error","Elo N/A"))

    p1,p2   = m["name1"],m["name2"]
    r1,r2   = m["r1"],m["r2"]
    c1,h1   = m["c_elo1"],m["h_elo1"]
    c2,h2   = m["c_elo2"],m["h_elo2"]
    sc1,sc2 = m["surf_score1"],m["surf_score2"]
    prob1   = m["prob1"]; prob2=1-prob1
    o1=m["odds1"]; o2=m["odds2"]
    bo1=m.get("book_odds_home"); bo2=m.get("book_odds_away")
    e1=m.get("edge1"); e2=m.get("edge2")
    adv=m.get("surface_advantage")
    sm =m.get("surface_match")       # NEW
    delta=(c1-c2) if surf=="clay" else (h1-h2)

    oc1="#22c55e" if prob1>=prob2 else "#e2e8f0"
    oc2="#22c55e" if prob1<prob2  else "#e2e8f0"
    bw="%s" % round(prob1*100,1)
    bcol=("linear-gradient(90deg,#15803d,#22c55e)" if prob1>0.65 else
          "linear-gradient(90deg,#92400e,#d97706)" if prob1<0.40 else
          "linear-gradient(90deg,#1d4ed8,#38bdf8)")

    def short(n):
        pts=n.split()
        return "%s. %s" % (pts[0][0], ' '.join(pts[1:])) if len(pts)>2 and len(n)>20 else n
    p1s,p2s=short(p1),short(p2)
    s1="[%s] " % m["seed1"] if m.get("seed1") else ""
    s2=" [%s]" % m["seed2"] if m.get("seed2") else ""

    book_row=""
    if bo1 or bo2:
        book_row=('<div style="display:flex;align-items:center;justify-content:space-between;'
                  'background:#0d1e35;border:1px solid #1e3050;border-radius:7px;padding:.35rem .6rem;margin-top:.35rem;gap:.3rem">'
                  '<div style="display:flex;align-items:center;gap:.35rem">'
                  '<span style="font-size:9px;color:#64748b">Bukmeker</span>'
                  '<span style="font-size:1.1rem;font-weight:800;color:#e2e8f0">%s</span>%s</div>'
                  '<span style="font-size:9px;color:#64748b">TE odds</span>'
                  '<div style="display:flex;align-items:center;gap:.35rem">%s'
                  '<span style="font-size:1.1rem;font-weight:800;color:#e2e8f0">%s</span></div></div>') % (
            bo1 or "—", edge_badge(e1),
            edge_badge(e2), bo2 or "—")

    coin=('<div style="font-size:10px;color:#eab308;text-align:center;margin-top:.3rem;'
          'padding:2px .5rem;background:#eab30810;border-radius:4px">⚠ Nyilt meccs — ΔElo &lt; 10</div>'
          if abs(delta)<10 else "")

    return """<div class="card">
  <div class="ctop">
    <div class="tags">
      <span class="surf-tag" style="background:{sbg};border-color:{sbd};color:{scol}">{sicon} {slabel}</span>
      <span class="cat-tag" style="color:{tcol};border-color:{tbd}">{tour} {cat}</span>
      <span class="t-tag">{time} UTC+1</span>
    </div>{pill}
  </div>
  <div class="cbody">
    <div class="prow">
      <div class="pinfo">
        <div class="pname">{s1}{p1s}</div>
        <div class="pmeta">#{r1rank} · c{c1:.0f} · h{h1:.0f}</div>
        {dots1}{adv1}{sm1}
      </div>
      <div class="vs">VS</div>
      <div class="pinfo" style="text-align:right">
        <div class="pname">{p2s}{s2}</div>
        <div class="pmeta">#{r2rank} · c{c2:.0f} · h{h2:.0f}</div>
        {dots2}{adv2}{sm2}
      </div>
    </div>
    <div class="odds-row">
      <div class="obox"><div class="odec" style="color:{oc1}">{o1}</div>
        <div class="oinfo"><span style="font-size:9px;color:#64748b">Fair</span><br>{p1last}<br><span style="color:#64748b">{prob1:.1f}%</span></div></div>
      <div class="odelta">Δ {delta:+.0f}</div>
      <div class="obox" style="flex-direction:row-reverse;text-align:right">
        <div class="odec" style="color:{oc2}">{o2}</div>
        <div class="oinfo"><span style="font-size:9px;color:#64748b">Fair</span><br>{p2last}<br><span style="color:#64748b">{prob2:.1f}%</span></div></div>
    </div>
    {book_row}{coin}
    <div class="bar-row">
      <span class="bar-pct">{prob1:.1f}%</span>
      <div class="bar-out"><div class="bar-in" style="width:{bw}%;background:{bcol}"></div></div>
      <span class="bar-pct" style="text-align:right">{prob2:.1f}%</span>
    </div>
  </div>
</div>""".format(
        sbg=sm_s["bg"],sbd=sm_s["bd"],scol=sm_s["col"],sicon=sm_s["icon"],slabel=sm_s["label"],
        tcol=tm["col"],tbd=tm["bd"],tour=tour,cat=cat,
        time=m.get("time",""),pill=pill,
        s1=s1,p1s=p1s,r1rank=r1.get("atp_rank","?"),c1=c1,h1=h1,
        dots1=ss_dots(sc1),
        adv1=adv_badge(adv,1,surf),
        sm1=sm_badge(sm,1,surf),
        s2=s2,p2s=p2s,r2rank=r2.get("atp_rank","?"),c2=c2,h2=h2,
        dots2=ss_dots(sc2,"right"),
        adv2=adv_badge(adv,2,surf),
        sm2=sm_badge(sm,2,surf),
        oc1=oc1,o1=o1,p1last=p1s.split()[-1],prob1=prob1*100,
        delta=delta,
        oc2=oc2,o2=o2,p2last=p2s.split()[-1],prob2=prob2*100,
        book_row=book_row,coin=coin,bw=bw,bcol=bcol)


def analyze_matches(matches, elo_players):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from value_calc import (find_player_in_elo_db, elo_win_prob,
                            get_surface_elo, prob_to_decimal_odds,
                            surface_advantage, compute_edge, surface_match)
    results = []
    for m in matches:
        surf = m.get("surface","hard")
        n1,r1 = find_player_in_elo_db(m["player1"], elo_players)
        n2,r2 = find_player_in_elo_db(m["player2"], elo_players)
        if not (r1 and r2):
            miss = m["player1"] if not r1 else m["player2"]
            results.append({**m,"elo_found":False,
                            "error":"N/A: %s" % miss,
                            "status":m.get("status","upcoming")}); continue

        c1=get_surface_elo(r1,"clay"); h1=r1.get("hElo") or c1
        c2=get_surface_elo(r2,"clay"); h2=r2.get("hElo") or c2
        e1=get_surface_elo(r1,surf);   e2=get_surface_elo(r2,surf)
        p1=elo_win_prob(e1,e2)

        bo1=m.get("book_odds_home"); bo2=m.get("book_odds_away")
        edge1=compute_edge(p1,      bo1) if bo1 else None
        edge2=compute_edge(1-p1,    bo2) if bo2 else None

        adv = surface_advantage(r1, r2, surf)
        sm  = surface_match(r1, r2, surf, edge1, edge2)  # NEW

        results.append({**m,
            "name1":n1,"name2":n2,"r1":r1,"r2":r2,
            "c_elo1":c1,"h_elo1":h1,"c_elo2":c2,"h_elo2":h2,
            "surf_score1":r1.get("surface_score",3),
            "surf_score2":r2.get("surface_score",3),
            "prob1":p1,
            "odds1":prob_to_decimal_odds(p1),
            "odds2":prob_to_decimal_odds(1-p1),
            "book_odds_home":bo1,"book_odds_away":bo2,
            "edge1":edge1,"edge2":edge2,
            "surface_advantage":adv,
            "surface_match":sm,          # NEW
            "elo_found":True,"error":None,
            "status":m.get("status","upcoming")})
    return results


def generate_html(atp_analyses, wta_analyses=None, elo_meta=None, bankroll=1000.0):
    wta_analyses = wta_analyses or []
    stats   = compute_stats(load_results())
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    scraped = (elo_meta or {}).get("scraped_at","?")[:10]

    all_live = [m for m in atp_analyses+wta_analyses if m.get("status")=="live"]
    all_rest_atp = [m for m in atp_analyses if m.get("status")!="live"]
    all_rest_wta = [m for m in wta_analyses if m.get("status")!="live"]

    def count(lst, key): return sum(1 for m in lst if m.get(key))
    atp_sm = count(atp_analyses,"surface_match")
    wta_sm = count(wta_analyses,"surface_match")
    total_sm = atp_sm + wta_sm
    total_adv = count(atp_analyses+wta_analyses,"surface_advantage")
    total_val = sum(1 for m in atp_analyses+wta_analyses
                    if (m.get("edge1") or 0)>=0.04 or (m.get("edge2") or 0)>=0.04)

    def cards(lst):
        if not lst: return '<p style="color:#64748b;padding:.5rem 0;font-size:12px">Nincs meccs.</p>'
        return "".join(render_card(m) for m in lst)

    def section(title, lst, color="#94a3b8"):
        if not lst: return ""
        return '<div class="sec" style="color:%s">%s</div><div class="cards">%s</div>' % (color, title, cards(lst))

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
    .sec:first-child{margin-top:.1rem}
    .statbar{display:flex;gap:.4rem;overflow-x:auto;padding-bottom:.25rem;margin-bottom:.15rem;scrollbar-width:none}
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
    .bar-in{height:100%;border-radius:4px}
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
  <div class="stat"><div class="sl">⚡ Felületi</div><div class="sv" style="color:#f59e0b">%d</div></div>
  <div class="stat"><div class="sl">🎯 SM</div><div class="sv" style="color:#c084fc">%d</div></div>
  <div class="stat"><div class="sl">Value</div><div class="sv" style="color:var(--gr)">%d</div></div>
  <div class="stat"><div class="sl">ROI</div><div class="sv" style="color:%s">%+.1f%%</div></div>
</div>
<div class="legend">
  <strong style="color:var(--tx)">⚡ Felületi előny</strong>: jobb ezen a borításon + ez az ő jobb borítása + ellenfélnél fordítva<br>
  <strong style="color:#c084fc">🎯 Surface Match</strong>: borításon erősebb + legalább annyira "otthon" + piac aluláraz ≥3%%<br>
  🧱🧱(1) 🧱(2) ⚖(3) 💙(4) 💙💙(5) · Value = edge ≥ 4%%
</div>
%s%s%s
</main>
<footer>tennisabstract.com Elo (ATP+WTA) · TennisExplorer odds · Nem befektetési tanácsos.</footer>
</body>
</html>""" % (
        updated, scraped,
        len(atp_analyses), len(wta_analyses), len(all_live),
        total_adv, total_sm, total_val,
        'var(--gr)' if stats['roi']>=0 else 'var(--rd)', stats['roi'],
        ('<div class="sec" style="color:var(--ye)">● Élő</div><div class="cards">%s</div>' % cards(all_live)) if all_live else "",
        section("ATP — Mai meccsek", all_rest_atp, "var(--ac)"),
        section("WTA — Mai meccsek", all_rest_wta, "var(--pink)")
    )

    OUTPUT_HTML.write_text(HTML, encoding="utf-8")
    print("[generate_html] -> %s" % OUTPUT_HTML)


if __name__ == "__main__":
    generate_html([], [], bankroll=1000)
