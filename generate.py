"""
MLB Sharp Lines — Daily Generator
Free: no API keys needed beyond Odds API.
MLB Stats API is free and public (no key required).
"""

import os, sys, time, requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
EASTERN      = ZoneInfo("America/New_York")
FETCH_PROPS  = False   # set True only with $19/mo Odds API plan

# ── MLB team name → MLB Stats API team ID ─────────────────────
MLB_IDS = {
    "New York Yankees":       147, "Boston Red Sox":       111,
    "Tampa Bay Rays":         139, "Baltimore Orioles":    110,
    "Toronto Blue Jays":      141, "Chicago White Sox":    145,
    "Cleveland Guardians":    114, "Detroit Tigers":       116,
    "Kansas City Royals":     118, "Minnesota Twins":      142,
    "Houston Astros":         117, "Los Angeles Angels":   108,
    "Athletics":              133, "Oakland Athletics":    133,
    "Seattle Mariners":       136, "Texas Rangers":        140,
    "Atlanta Braves":         144, "Miami Marlins":        146,
    "New York Mets":          121, "Philadelphia Phillies":143,
    "Washington Nationals":   120, "Chicago Cubs":         112,
    "Cincinnati Reds":        113, "Milwaukee Brewers":    158,
    "Pittsburgh Pirates":     134, "St. Louis Cardinals":  138,
    "Arizona Diamondbacks":   109, "Colorado Rockies":     115,
    "Los Angeles Dodgers":    119, "San Diego Padres":     135,
    "San Francisco Giants":   137,
}


# ═════════════════════════════════════════════════════════════
# ODDS FETCH
# ═════════════════════════════════════════════════════════════
def fetch_live_mlb_games(yesterday_str):
    """
    Returns a set of (away_team_id, home_team_id) tuples for MLB games
    that are currently Live on yesterday's date (handles past-midnight west coast games).
    """
    data = mlb_get("/schedule", {
        "sportId": 1,
        "date":    yesterday_str,
        "hydrate": "team",
    })
    if not data:
        return set()
    live = set()
    for date_block in data.get("dates", []):
        for g in date_block.get("games", []):
            state = g.get("status", {}).get("abstractGameState", "")
            if state == "Live":
                aid = g.get("teams", {}).get("away", {}).get("team", {}).get("id")
                hid = g.get("teams", {}).get("home", {}).get("team", {}).get("id")
                if aid and hid:
                    live.add((aid, hid))
    return live


def fetch_odds():
    print("Fetching MLB odds...")
    r = requests.get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
        params={
            "apiKey":     ODDS_API_KEY,
            "regions":    "us",
            "markets":    "h2h,totals",
            "oddsFormat": "american",
            "dateFormat": "iso",
        },
        timeout=30,
    )
    r.raise_for_status()
    all_games = r.json()

    now_et      = datetime.now(EASTERN)
    today_et    = now_et.date()
    yesterday_et= today_et - timedelta(days=1)

    # Fetch live game IDs for yesterday (catches west coast games running past midnight ET)
    live_yesterday = fetch_live_mlb_games(yesterday_et.strftime("%Y-%m-%d"))

    games = []
    for g in all_games:
        try:
            start      = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
            start_et   = start.astimezone(EASTERN)
            start_date = start_et.date()

            if start_date >= today_et:
                # Future games AND today's games (started or not) — always show.
                # A 1pm game that's already in progress stays until midnight ET
                # because its date still equals today_et.
                games.append(g)

            elif start_date == yesterday_et:
                # Yesterday's game — only keep if it's still Live in the MLB API.
                # This handles west coast games (e.g. Dodgers 10pm PT = 1am ET)
                # that run past midnight and should stay until they finish.
                away_id = MLB_IDS.get(g["away_team"])
                home_id = MLB_IDS.get(g["home_team"])
                if away_id and home_id and (away_id, home_id) in live_yesterday:
                    print(f"  Keeping live past-midnight game: {g['away_team']} @ {g['home_team']}")
                    games.append(g)
                else:
                    print(f"  Skipping finished: {g['away_team']} @ {g['home_team']}")

            else:
                # Older than yesterday — skip entirely
                print(f"  Skipping old game: {g['away_team']} @ {g['home_team']}")

        except Exception:
            games.append(g)   # include if we can't parse the time
    print(f"Got {len(all_games)} total, {len(games)} not yet started")
    return games


# ═════════════════════════════════════════════════════════════
# MLB MATCHUP FETCH  (free, no API key)
# ═════════════════════════════════════════════════════════════
MLB_BASE = "https://statsapi.mlb.com/api/v1"

def mlb_get(path, params=None):
    try:
        r = requests.get(MLB_BASE + path, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def fetch_mlb_schedule(date_str):
    """Get today's games with probable pitchers and lineups from MLB API."""
    data = mlb_get("/schedule", {
        "sportId": 1,
        "date": date_str,
        "hydrate": "probablePitcher,lineups,team",
    })
    if not data:
        return []
    games = []
    for date in data.get("dates", []):
        for g in date.get("games", []):
            status = g.get("status", {}).get("abstractGameState", "")
            if status in ("Final", "Live"):
                continue   # skip finished / in-progress
            games.append(g)
    return games


def fetch_roster(team_id):
    """Get active position player roster for a team."""
    data = mlb_get(f"/teams/{team_id}/roster", {"rosterType": "active"})
    if not data:
        return []
    players = []
    for p in data.get("roster", []):
        pos = p.get("position", {}).get("abbreviation", "")
        if pos not in ("P", "TWP"):   # exclude pitchers
            players.append({
                "id":   p["person"]["id"],
                "name": p["person"]["fullName"],
                "pos":  pos,
            })
    return players


def fetch_batter_vs_pitcher(batter_id, pitcher_id):
    """Career stats for one batter against one pitcher."""
    data = mlb_get(f"/people/{batter_id}/stats", {
        "stats":            "vsPlayer",
        "opposingPlayerId": pitcher_id,
        "group":            "hitting",
        "sportId":          1,
    })
    if not data:
        return None
    for split_group in data.get("stats", []):
        splits = split_group.get("splits", [])
        if splits:
            s = splits[0].get("stat", {})
            ab = s.get("atBats", 0)
            if ab == 0:
                return None
            h  = s.get("hits",      0)
            hr = s.get("homeRuns",  0)
            k  = s.get("strikeOuts",0)
            bb = s.get("baseOnBalls", 0)
            avg = round(h / ab, 3) if ab else 0
            return {
                "ab":  ab,
                "h":   h,
                "hr":  hr,
                "k":   k,
                "bb":  bb,
                "avg": f".{str(round(avg * 1000)).zfill(3)}",
                "display": f"{h}/{ab} ({'.'+str(round(avg*1000)).zfill(3)})",
            }
    return None


def fetch_pitcher_info(pitcher_id):
    """Get pitcher name and season ERA."""
    data = mlb_get(f"/people/{pitcher_id}", {"hydrate": "stats(group=pitching,type=season,season=2026)"})
    if not data:
        return {"name": "TBD", "era": "—", "id": pitcher_id}
    person = data.get("people", [{}])[0]
    name   = person.get("fullName", "TBD")
    era    = "—"
    for sg in person.get("stats", []):
        splits = sg.get("splits", [])
        if splits:
            era_val = splits[0].get("stat", {}).get("era")
            if era_val:
                era = era_val
                break
    return {"name": name, "era": str(era), "id": pitcher_id}


def build_matchup_data(odds_games, date_str):
    """
    For each upcoming game, fetch probable pitchers and batter vs pitcher history.
    Returns a list of matchup dicts, one per game.
    """
    print("Fetching MLB matchup data...")
    mlb_games = fetch_mlb_schedule(date_str)

    if not mlb_games:
        print("  No MLB schedule data available")
        return []

    # Build a lookup: (away_team_id, home_team_id) -> game data
    mlb_lookup = {}
    for g in mlb_games:
        aid = g.get("teams", {}).get("away", {}).get("team", {}).get("id")
        hid = g.get("teams", {}).get("home", {}).get("team", {}).get("id")
        if aid and hid:
            mlb_lookup[(aid, hid)] = g

    matchups = []

    for og in odds_games:
        away_name = og["away_team"]
        home_name = og["home_team"]
        away_id   = MLB_IDS.get(away_name)
        home_id   = MLB_IDS.get(home_name)

        if not away_id or not home_id:
            print(f"  No MLB ID for: {away_name} or {home_name}")
            continue

        mlb_game = mlb_lookup.get((away_id, home_id))
        if not mlb_game:
            # try reverse just in case
            mlb_game = mlb_lookup.get((home_id, away_id))

        # Probable pitchers
        away_pitcher_raw = mlb_game.get("teams", {}).get("away", {}).get("probablePitcher") if mlb_game else None
        home_pitcher_raw = mlb_game.get("teams", {}).get("home", {}).get("probablePitcher") if mlb_game else None

        away_pitcher = fetch_pitcher_info(away_pitcher_raw["id"]) if away_pitcher_raw else {"name": "TBD", "era": "—", "id": None}
        home_pitcher = fetch_pitcher_info(home_pitcher_raw["id"]) if home_pitcher_raw else {"name": "TBD", "era": "—", "id": None}

        # Lineups (if posted) or rosters (fallback)
        lineups = mlb_game.get("lineups", {}) if mlb_game else {}
        away_lineup_raw = lineups.get("awayPlayers", [])
        home_lineup_raw = lineups.get("homePlayers", [])

        def extract_lineup(lineup_raw):
            return [{"id": p["id"], "name": p.get("fullName", str(p["id"])), "pos": ""} for p in lineup_raw if isinstance(p, dict) and "id" in p]

        if away_lineup_raw:
            away_batters = [b for b in extract_lineup(away_lineup_raw) if b][:9]
            away_source  = "lineup"
        else:
            away_batters = fetch_roster(away_id)[:13]
            away_source  = "roster"

        if home_lineup_raw:
            home_batters = [b for b in extract_lineup(home_lineup_raw) if b][:9]
            home_source  = "lineup"
        else:
            home_batters = fetch_roster(home_id)[:13]
            home_source  = "roster"

        # Batter vs pitcher stats
        def get_matchup_stats(batters, pitcher_id):
            if not pitcher_id:
                return []
            results = []
            for b in batters:
                stats = fetch_batter_vs_pitcher(b["id"], pitcher_id)
                if stats and stats["ab"] >= 3:
                    results.append({**b, **stats})
                time.sleep(0.05)   # be respectful of MLB API
            results.sort(key=lambda x: -x["ab"])
            return results

        print(f"  {away_name} @ {home_name}: {away_pitcher['name']} vs {home_pitcher['name']}")
        away_vs_home_p = get_matchup_stats(away_batters, home_pitcher.get("id"))
        home_vs_away_p = get_matchup_stats(home_batters, away_pitcher.get("id"))

        matchups.append({
            "game":          f"{away_name} @ {home_name}",
            "away":          away_name,
            "home":          home_name,
            "away_pitcher":  away_pitcher,
            "home_pitcher":  home_pitcher,
            "away_batters":  away_vs_home_p,   # away batters vs home pitcher
            "home_batters":  home_vs_away_p,   # home batters vs away pitcher
            "away_source":   away_source,
            "home_source":   home_source,
        })

    print(f"  Matchup data ready for {len(matchups)} games")
    return matchups


# ═════════════════════════════════════════════════════════════
# MATH
# ═════════════════════════════════════════════════════════════
def american_to_implied(price):
    try:
        p = float(price)
        return 100 / (p + 100) if p > 0 else abs(p) / (abs(p) + 100)
    except Exception:
        return None

def implied_to_american(prob):
    if prob is None or prob <= 0 or prob >= 1:
        return "—"
    return f"-{round((prob/(1-prob))*100)}" if prob >= 0.5 else f"+{round(((1-prob)/prob)*100)}"

def remove_vig(a, b):
    if a is None or b is None: return None, None
    t = a + b
    return (a/t, b/t) if t > 0 else (None, None)

def fmt(price):
    try:
        p = int(price)
        return f"+{p}" if p > 0 else str(p)
    except Exception:
        return str(price)


# ═════════════════════════════════════════════════════════════
# ANALYZE GAME
# ═════════════════════════════════════════════════════════════
def analyze_game(game):
    away  = game["away_team"]
    home  = game["home_team"]
    books = game.get("bookmakers", [])

    book_data = []
    for b in books:
        h2h   = next((m for m in b.get("markets",[]) if m["key"]=="h2h"),    None)
        total = next((m for m in b.get("markets",[]) if m["key"]=="totals"), None)
        if not h2h: continue
        ao = next((o for o in h2h["outcomes"] if o["name"]==away), None)
        ho = next((o for o in h2h["outcomes"] if o["name"]==home), None)
        if not ao or not ho: continue
        ov = next((o for o in (total or {}).get("outcomes",[]) if o["name"]=="Over"),  None)
        uv = next((o for o in (total or {}).get("outcomes",[]) if o["name"]=="Under"), None)
        ap=ao["price"]; hp=ho["price"]
        ai=american_to_implied(ap); hi=american_to_implied(hp)
        at,ht=remove_vig(ai,hi)
        book_data.append({
            "name":b["title"],"away_price":ap,"home_price":hp,
            "away_imp":round(ai*100,1) if ai else None,
            "home_imp":round(hi*100,1) if hi else None,
            "away_true":at,"home_true":ht,
            "total_line":ov["point"] if ov else None,
            "over_price":ov["price"] if ov else None,
            "under_price":uv["price"] if uv else None,
        })

    if not book_data: return None

    split_market = (any(b["away_price"]<0 for b in book_data) and
                    any(b["home_price"]<0 for b in book_data))

    def median(lst):
        s=sorted(lst); n=len(s)
        return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2

    away_med=median([b["away_price"] for b in book_data])
    home_med=median([b["home_price"] for b in book_data])

    def cents_off(price,ref):
        i1=american_to_implied(price); i2=american_to_implied(ref)
        return abs(i1-i2)*100 if i1 and i2 else 0

    for b in book_data:
        b["outlier_away"]=cents_off(b["away_price"],away_med)>15
        b["outlier_home"]=cents_off(b["home_price"],home_med)>15

    clean=[b for b in book_data if not b["outlier_away"] and not b["outlier_home"]] or book_data
    avg_at=sum(b["away_true"] for b in clean if b["away_true"])/len(clean)
    avg_ht=sum(b["home_true"] for b in clean if b["home_true"])/len(clean)
    away_fair=implied_to_american(avg_at)
    home_fair=implied_to_american(avg_ht)

    best_away =max(book_data,key=lambda b:float(b["away_price"]))
    worst_away=min(book_data,key=lambda b:float(b["away_price"]))
    best_home =max(book_data,key=lambda b:float(b["home_price"]))
    worst_home=min(book_data,key=lambda b:float(b["home_price"]))

    for b in book_data:
        b["best_away"] =b["name"]==best_away["name"]
        b["worst_away"]=b["name"]==worst_away["name"]
        b["best_home"] =b["name"]==best_home["name"]
        b["worst_home"]=b["name"]==worst_home["name"]

    away_gap=round(abs(american_to_implied(worst_away["away_price"])-american_to_implied(best_away["away_price"]))*100)
    home_gap=round(abs(american_to_implied(worst_home["home_price"])-american_to_implied(best_home["home_price"]))*100)

    if split_market:            signal,signal_label="fire","🔥 SPLIT MARKET"
    elif away_gap>=18 or home_gap>=18: signal,signal_label="fire","🔥 DISCREPANCY"
    elif away_gap>=10 or home_gap>=10: signal,signal_label="value","💰 SHOP"
    else:                       signal,signal_label="watch",""

    fav_team=home if avg_ht>avg_at else away
    fav_true=max(avg_at,avg_ht); dog_true=min(avg_at,avg_ht)
    if fav_team==home:  bf_book=best_home["name"];  bf_price=best_home["home_price"]
    else:               bf_book=best_away["name"];  bf_price=best_away["away_price"]
    edge_pct=round((fav_true*100)-american_to_implied(bf_price)*100,1)

    if abs(fav_true-dog_true)<0.03:
        bet_play="Pass — near coin flip"
        bet_sub="If forced: use BetOnline/LowVig for lowest vig"
        bet_edge="None"; bet_is_pass=True
    else:
        bet_play=f"{fav_team} Moneyline"
        bet_sub=f"{fmt(bf_price)} at {bf_book}"
        bet_edge="Slight"; bet_is_pass=False

    discs=[]
    for team,gap,best,worst,pk in [
        (away,away_gap,best_away,worst_away,"away_price"),
        (home,home_gap,best_home,worst_home,"home_price"),
    ]:
        if gap>=8:
            discs.append({"team":team,"best_price":fmt(best[pk]),"worst_price":fmt(worst[pk]),
                          "gap":gap,"best_book":best["name"],"worst_book":worst["name"]})

    value_play=None
    if signal in ("fire","value","sharp") and not bet_is_pass:
        best_b=best_home if fav_team==home else best_away
        best_p=best_b["home_price"] if fav_team==home else best_b["away_price"]
        value_play={
            "game":f"{away} @ {home}","signal":signal,"team":fav_team,
            "best_price":fmt(best_p),"best_book":best_b["name"],
            "true_pct":round(fav_true*100,1),"implied_pct":round(american_to_implied(best_p)*100,1),
            "edge":edge_pct,
            "reasoning":build_reasoning(away,home,best_away,worst_away,best_home,worst_home,
                                        away_gap,home_gap,split_market,avg_at,avg_ht,away_fair,home_fair),
        }

    try:
        t=datetime.fromisoformat(game.get("commence_time","").replace("Z","+00:00")).astimezone(EASTERN)
        time_display=t.strftime("%-I:%M %p ET")
        date_et=t.strftime("%A, %B %d")
        date_sort=t.strftime("%Y-%m-%d")
    except Exception:
        time_display=""; date_et="Today"; date_sort="9999-99-99"

    return {
        "game":f"{away} @ {home}","game_id":game.get("id",""),
        "away":away,"home":home,"time":time_display,"date_et":date_et,"date_sort":date_sort,
        "signal":signal,"signal_label":signal_label,"split_market":split_market,
        "away_true":round(avg_at*100),"home_true":round(avg_ht*100),
        "away_fair":away_fair,"home_fair":home_fair,
        "book_data":book_data,"discrepancies":discs,"value_play":value_play,
        "bet_play":bet_play,"bet_sub":bet_sub,"bet_edge":bet_edge,"bet_is_pass":bet_is_pass,
        "best_away":best_away,"best_home":best_home,
        "worst_away":worst_away,"worst_home":worst_home,
        "away_gap":away_gap,"home_gap":home_gap,"props":[],
    }


def build_reasoning(away,home,ba,wa,bh,wh,ag,hg,split,at,ht,afl,hfl):
    fav=home if ht>at else away; fav_t=max(at,ht)
    parts=[f"{fav} are {round(fav_t*100)}% favorites by true odds (fair line {hfl if ht>at else afl})."]
    if split:
        parts.append(f"Market is split — some books favor {away}, others favor {home}.")
    elif ag>=15 or hg>=15:
        team=away if ag>hg else home
        best=ba if ag>hg else bh; worst=wa if ag>hg else wh
        bp=best["away_price"] if ag>hg else best["home_price"]
        wp=worst["away_price"] if ag>hg else worst["home_price"]
        parts.append(f"Large discrepancy on {team}: {fmt(bp)} at {best['name']} vs {fmt(wp)} at {worst['name']} — a {max(ag,hg)}¢ gap.")
    else:
        if ag>=8: parts.append(f"Shop {away}: {fmt(ba['away_price'])} at {ba['name']} vs {fmt(wa['away_price'])} at {wa['name']}.")
        if hg>=8: parts.append(f"Shop {home}: {fmt(bh['home_price'])} at {bh['name']} vs {fmt(wh['home_price'])} at {wh['name']}.")
    return " ".join(parts)


# ═════════════════════════════════════════════════════════════
# BUILD HTML
# ═════════════════════════════════════════════════════════════
def build_html(analyzed_games, matchups, date_str, time_str):
    all_disc=[]; all_plays=[]; sharp_ct=0; value_ct=0
    for g in analyzed_games:
        for d in g["discrepancies"]: all_disc.append({**d,"game":g["game"]})
        if g["value_play"]: all_plays.append(g["value_play"])
        if g["signal"]=="fire": sharp_ct+=1
        if g["signal"] in ("fire","value","sharp"): value_ct+=1
    all_plays.sort(key=lambda x:-abs(x.get("edge",0)))
    all_disc.sort(key=lambda x:-(x.get("gap",0)))

    sig_cls={"fire":"b-fire","sharp":"b-sharp","value":"b-value","watch":"b-watch","pass":"b-pass"}
    alert_cls={"fire":"fire","sharp":"sharp","value":"value","watch":"watch"}
    total=len(analyzed_games)
    books=max((len(g["book_data"]) for g in analyzed_games),default=0)

    # ── ALERT CARDS ──────────────────────────────────────────
    def alert_cards():
        top=[p for p in all_plays if p["signal"] in ("fire","sharp","value")][:4]
        if not top: return '<p style="color:var(--muted);font-size:13px;padding:1rem 0">No sharp alerts today.</p>'
        html='<div class="alert-grid">'
        for p in top:
            sig=p["signal"]; ec="green" if (p.get("edge") or 0)>0 else "red"
            html+=f"""
      <div class="alert-card {alert_cls.get(sig,'value')}">
        <span class="badge {sig_cls.get(sig,'b-value')}">{sig.upper()}</span>
        <div class="alert-game">{p["game"]}</div>
        <div class="alert-rec">{p["team"]} — {p["best_price"]} @ {p["best_book"]}</div>
        <div class="alert-stats">
          <div class="stat-box"><div class="sl">Best Price</div><div class="sv">{p["best_price"]}</div></div>
          <div class="stat-box"><div class="sl">True %</div><div class="sv">{p["true_pct"]}%</div></div>
          <div class="stat-box"><div class="sl">Implied %</div><div class="sv {ec}">{p["implied_pct"]}%</div></div>
        </div>
        <div class="alert-reasoning">{p["reasoning"]}</div>
      </div>"""
        html+="</div>"; return html

    # ── PLAYS TABLE ──────────────────────────────────────────
    def plays_table():
        if not all_plays: return "<p style='color:var(--muted);font-size:13px;padding:1rem 0'>No value plays today.</p>"
        rows=""
        for p in all_plays:
            ec="c-green" if (p.get("edge") or 0)>0 else "c-red"
            rows+=f"""<tr>
          <td>{p["game"]}</td><td class="mono">{p["team"]} ML</td>
          <td><span class="pill pill-n">{p["best_price"]}</span></td>
          <td class="c-accent mono" style="font-size:11px">{p["best_book"]}</td>
          <td class="mono">{p["implied_pct"]}%</td><td class="mono">{p["true_pct"]}%</td>
          <td class="mono {ec}">{'+' if (p.get('edge') or 0)>0 else ''}{p.get('edge','—')}%</td>
          <td><span class="badge {sig_cls.get(p['signal'],'b-watch')}" style="margin:0">{p["signal"].upper()}</span></td>
        </tr>"""
        return f"""<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:1.75rem">
      <table class="dtable"><thead><tr><th>Game</th><th>Play</th><th>Best Line</th><th>Best Book</th><th>Implied%</th><th>True%</th><th>Edge</th><th>Signal</th></tr></thead>
      <tbody>{rows}</tbody></table></div>"""

    # ── DISC TABLE ───────────────────────────────────────────
    def disc_table():
        if not all_disc: return "<p style='color:var(--muted);font-size:13px;padding:1rem 0'>No major discrepancies today.</p>"
        rows=""
        for d in all_disc[:14]:
            gap=d.get("gap",0); gc="c-red" if gap>=18 else ("c-amber" if gap>=10 else "")
            rows+=f"""<tr>
          <td>{d["game"]}</td><td>{d["team"]}</td>
          <td><span class="pill pill-g">{d["best_price"]}</span></td>
          <td><span class="pill pill-r">{d["worst_price"]}</span></td>
          <td class="mono {gc}">{gap}¢</td>
          <td class="mono c-accent" style="font-size:11px">{d["best_book"]}</td>
          <td class="mono c-red" style="font-size:11px">{d["worst_book"]}</td>
        </tr>"""
        return f"""<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden">
      <table class="dtable"><thead><tr><th>Game</th><th>Team</th><th>Best Price</th><th>Worst Price</th><th>Gap</th><th>Best Book</th><th>Worst Book</th></tr></thead>
      <tbody>{rows}</tbody></table></div>"""

    # ── GAME BLOCKS ──────────────────────────────────────────
    def game_blocks():
        html=""
        for i,g in enumerate(analyzed_games):
            sig=g["signal"]; bc=sig_cls.get(sig,"b-watch")
            open_cls="open" if i<2 else ""
            sig_badge=f'<span class="badge {bc}" style="font-size:9px">{g["signal_label"]}</span>' if g["signal_label"] else ""
            away_fav="fav" if g["away_true"]>g["home_true"] else ""
            home_fav="fav" if g["home_true"]>g["away_true"] else ""
            day_header=""
            if i==0 or g["date_et"]!=analyzed_games[i-1]["date_et"]:
                day_header=f'<div class="day-header"><span class="day-label">{g["date_et"]}</span></div>'
            book_rows=""
            for b in g["book_data"]:
                def pc(price,is_best,is_worst,is_out):
                    fp=fmt(price)
                    if is_best:  return f'<td class="pb">{fp} ★</td>'
                    if is_worst: return f'<td class="pw">{fp} ✗</td>'
                    if is_out:   return f'<td class="po">{fp} ⚠</td>'
                    return f'<td class="pc">{fp}</td>'
                if b.get("total_line") and b.get("over_price") is not None:
                    op=b["over_price"]; ops=fmt(op)
                    total_str=f'<span style="color:var(--muted)">O/U</span> <strong style="color:var(--text)">{b["total_line"]}</strong> <span style="color:var(--accent)">{ops}</span>'
                else:
                    total_str='<span style="color:var(--dim)">—</span>'
                book_rows+=f"""<tr>
              <td class="book">{b["name"]}</td>
              {pc(b["away_price"],b.get("best_away"),b.get("worst_away"),b.get("outlier_away"))}
              <td class="prob">{b["away_imp"]}%</td>
              {pc(b["home_price"],b.get("best_home"),b.get("worst_home"),b.get("outlier_home"))}
              <td class="prob">{b["home_imp"]}%</td>
              <td class="prob">{total_str}</td>
            </tr>"""
            bb_cls="best-bet pass" if g["bet_is_pass"] else "best-bet"
            best_ap=fmt(g["best_away"]["away_price"]); best_hp=fmt(g["best_home"]["home_price"])
            best_bet=f"""<div class="{bb_cls}">
            <div class="bb-header">★ Best Bet This Game</div>
            <div class="bb-play">{g["bet_play"]}</div>
            <div class="bb-sub">{g["bet_sub"]}</div>
            <div class="bb-stats">
              <div class="bbs"><div class="bbs-label">True Odds</div><div class="bbs-val">{g["away_true"]}% / {g["home_true"]}%</div></div>
              <div class="bbs"><div class="bbs-label">Best {g["away"][:11]}</div><div class="bbs-val">{best_ap} @ {g["best_away"]["name"]}</div></div>
              <div class="bbs"><div class="bbs-label">Best {g["home"][:11]}</div><div class="bbs-val">{best_hp} @ {g["best_home"]["name"]}</div></div>
              <div class="bbs"><div class="bbs-label">Edge</div><div class="bbs-val {'green' if not g['bet_is_pass'] else 'c-muted'}">{g["bet_edge"]}</div></div>
            </div></div>"""
            html+=day_header+f"""
        <div class="game-block {open_cls}" onclick="toggleGame(this)">
          <div class="game-header">
            <div><div class="game-teams">{g["away"]} @ {g["home"]}</div><div class="game-time">{g["time"]}</div></div>
            <div class="game-right">{sig_badge}<span class="toggle">▼</span></div>
          </div>
          <div class="game-body">
            <table class="otable">
              <thead><tr><th>Book</th><th>{g["away"]}</th><th>Implied%</th><th>{g["home"]}</th><th>Implied%</th><th>Total O/U</th></tr></thead>
              <tbody>{book_rows}</tbody>
            </table>
            <div class="claude-box">
              <div class="cb-header">📊 True Odds (vig removed &amp; averaged)</div>
              <div class="cb-grid">
                <div class="cb-team"><div class="cb-name">{g["away"]}</div><div class="cb-pct {away_fav}">{g["away_true"]}%</div><div class="cb-line">Fair: {g["away_fair"]}</div></div>
                <div class="cb-vs">vs</div>
                <div class="cb-team"><div class="cb-name">{g["home"]}</div><div class="cb-pct {home_fav}">{g["home_true"]}%</div><div class="cb-line">Fair: {g["home_fair"]}</div></div>
              </div>
              <div class="cb-method">Vig removed from each book via normalization, averaged across non-outlier books.</div>
            </div>
            {best_bet}
          </div>
        </div>"""
        return html

    # ── MATCHUP PAGE ─────────────────────────────────────────
    def matchup_page():
        if not matchups:
            return '<p style="color:var(--muted);font-size:13px;padding:2rem 0;text-align:center">Matchup data unavailable — probable pitchers may not be announced yet. Check back closer to game time.</p>'

        def avg_color(avg_str):
            try:
                v = float(avg_str)
                if v >= 0.300: return "#f87171"   # red = hot against this pitcher
                if v >= 0.250: return "#fbbf24"   # amber = decent
                return "#4ade80"                   # green = struggling vs pitcher
            except Exception:
                return "var(--text)"

        def bar(avg_str):
            try:
                v = float(avg_str)
                pct = min(int(v * 333), 100)
                color = avg_color(avg_str)
                return f'<div style="height:3px;background:var(--border);border-radius:2px;margin-top:3px"><div style="height:3px;width:{pct}%;background:{color};border-radius:2px"></div></div>'
            except Exception:
                return ""

        def batter_table(batters, pitcher, batting_team, source):
            if not batters:
                source_note = "Official lineup" if source == "lineup" else "Roster-based (lineup not posted)"
                return f'<p style="color:var(--muted);font-size:12px;padding:8px 0">{source_note} — no batters with 3+ career AB vs {pitcher["name"]}.</p>'
            source_note = "✅ Official lineup" if source == "lineup" else "📋 Roster (lineup not yet posted)"
            rows = ""
            for b in batters:
                ac = avg_color(b["avg"])
                rows += f"""<tr>
                  <td class="book">{b["name"]}</td>
                  <td class="mono" style="color:var(--muted)">{b.get("pos","")}</td>
                  <td class="mono">{b["ab"]}</td>
                  <td class="mono">{b["h"]}</td>
                  <td class="mono">{b["hr"]}</td>
                  <td class="mono">{b["k"]}</td>
                  <td>
                    <span class="mono" style="color:{ac};font-weight:700">{b["avg"]}</span>
                    <span style="color:var(--muted);font-size:11px"> ({b["h"]}/{b["ab"]})</span>
                    {bar(b["avg"])}
                  </td>
                </tr>"""
            return f"""<div style="font-size:10px;color:var(--muted);margin-bottom:6px;font-family:monospace">{source_note}</div>
            <table class="dtable"><thead><tr><th>Batter</th><th>Pos</th><th>AB</th><th>H</th><th>HR</th><th>K</th><th>Career BA vs Pitcher</th></tr></thead>
            <tbody>{rows}</tbody></table>"""

        html = ""
        for i, m in enumerate(matchups):
            open_cls = "open" if i < 1 else ""
            ap = m["away_pitcher"]; hp = m["home_pitcher"]
            ap_era = f'ERA {ap["era"]}' if ap["era"] != "—" else "ERA N/A"
            hp_era = f'ERA {hp["era"]}' if hp["era"] != "—" else "ERA N/A"

            html += f"""
        <div class="game-block {open_cls}" onclick="toggleGame(this)">
          <div class="game-header">
            <div>
              <div class="game-teams">{m["away"]} @ {m["home"]}</div>
              <div class="game-time">{ap["name"]} vs {hp["name"]}</div>
            </div>
            <div class="game-right"><span class="toggle">▼</span></div>
          </div>
          <div class="game-body" style="padding:0 15px 20px">

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px">

              <div>
                <div class="pitcher-card">
                  <div class="pitcher-role">AWAY STARTER</div>
                  <div class="pitcher-name">{ap["name"]}</div>
                  <div class="pitcher-team">{m["away"]} &nbsp;·&nbsp; {ap_era}</div>
                </div>
                <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin:12px 0 6px">
                  {m["home"]} Batters vs {ap["name"]}
                </div>
                {batter_table(m["home_batters"], ap, m["home"], m["home_source"])}
              </div>

              <div>
                <div class="pitcher-card">
                  <div class="pitcher-role">HOME STARTER</div>
                  <div class="pitcher-name">{hp["name"]}</div>
                  <div class="pitcher-team">{m["home"]} &nbsp;·&nbsp; {hp_era}</div>
                </div>
                <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin:12px 0 6px">
                  {m["away"]} Batters vs {hp["name"]}
                </div>
                {batter_table(m["away_batters"], hp, m["away"], m["away_source"])}
              </div>

            </div>

            <div style="margin-top:10px;padding:8px 12px;background:var(--bg3);border-radius:6px;font-size:11px;color:var(--muted);line-height:1.6">
              <span style="color:var(--green)">■</span> .300+ BA = batter has historically hit this pitcher well &nbsp;
              <span style="color:var(--amber)">■</span> .250–.299 = moderate history &nbsp;
              <span style="color:var(--red)">■</span> Under .250 = pitcher has the edge &nbsp;·&nbsp; Min 3 AB shown
            </div>
          </div>
        </div>"""
        return html

    # ── CSS ──────────────────────────────────────────────────
    css = """<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#09090b;--bg2:#111113;--bg3:#18181b;--bg4:#1f1f23;
  --border:#27272a;--border2:#3f3f46;
  --text:#e4e4e7;--muted:#71717a;--dim:#52525b;
  --green:#4ade80;--green-bg:#052e16;--green-border:#166534;
  --red:#f87171;--red-bg:#2d0a0a;--red-border:#7f1d1d;
  --blue:#60a5fa;--blue-bg:#0c1a3a;--blue-border:#1e3a6e;
  --amber:#fbbf24;--amber-bg:#1c1400;--amber-border:#78350f;
  --accent:#a3e635;--sidebar:240px;
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:'IBM Plex Sans',sans-serif;font-size:14px;line-height:1.6;min-height:100vh}
.sidebar{width:var(--sidebar);background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column;position:fixed;top:0;left:0;height:100vh;z-index:300;overflow-y:auto;transition:transform 0.25s ease}
.sidebar-logo{padding:20px 18px 14px;border-bottom:1px solid var(--border)}
.sidebar-logo-title{font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:16px;color:var(--accent);letter-spacing:-0.5px}
.sidebar-logo-sub{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:4px}
.sidebar-date{padding:10px 18px;font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:6px}
.live-dot{display:inline-block;width:6px;height:6px;background:var(--green);border-radius:50%;animation:pulse 2s infinite;flex-shrink:0}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
.sidebar-section{padding:10px 10px 4px;font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:1.5px;font-family:'IBM Plex Mono',monospace;font-weight:600}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 14px;margin:1px 6px;border-radius:8px;cursor:pointer;font-size:13px;color:var(--muted);transition:all 0.15s;user-select:none;border:1px solid transparent}
.nav-item:hover{background:var(--bg3);color:var(--text)}
.nav-item.active{background:rgba(163,230,53,0.08);color:var(--accent);border-color:rgba(163,230,53,0.15)}
.nav-icon{font-size:15px;flex-shrink:0;width:18px;text-align:center}
.nav-label{font-weight:500}
.nav-count{margin-left:auto;font-size:10px;font-family:'IBM Plex Mono',monospace;background:var(--bg4);padding:1px 6px;border-radius:10px;color:var(--muted)}
.nav-item.active .nav-count{background:rgba(163,230,53,0.15);color:var(--accent)}
.sidebar-stats{margin-top:auto;padding:14px 14px 20px;border-top:1px solid var(--border)}
.sidebar-stat{display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:11px}
.sidebar-stat-label{color:var(--muted)}
.sidebar-stat-val{font-family:'IBM Plex Mono',monospace;font-weight:600;color:var(--text)}
.sidebar-stat-val.green{color:var(--green)}.sidebar-stat-val.amber{color:var(--amber)}
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:200}
.overlay.show{display:block}
.main{margin-left:var(--sidebar);min-height:100vh}
.topbar{background:var(--bg2);border-bottom:1px solid var(--border);padding:0 1.5rem;height:52px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.topbar-left{display:flex;align-items:center;gap:12px}
.hamburger{display:none;flex-direction:column;gap:4px;cursor:pointer;padding:4px;background:none;border:none}
.hamburger span{display:block;width:20px;height:2px;background:var(--text);border-radius:2px}
.topbar-title{font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:15px;color:#fff}
.topbar-meta{font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace}
.page{display:none}.page.active{display:block}
.page-inner{padding:2rem}
.hero{background:linear-gradient(135deg,rgba(163,230,53,0.06) 0%,rgba(163,230,53,0.01) 60%,transparent 100%);border:1px solid rgba(163,230,53,0.12);border-radius:16px;padding:2.5rem;margin-bottom:2rem;position:relative;overflow:hidden}
.hero::before{content:'⚾';position:absolute;right:2rem;top:1.5rem;font-size:80px;opacity:0.06}
.hero-eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:var(--accent);font-family:'IBM Plex Mono',monospace;font-weight:600;margin-bottom:10px}
.hero-title{font-family:'IBM Plex Mono',monospace;font-size:30px;font-weight:700;color:#fff;line-height:1.2;margin-bottom:10px}
.hero-title span{color:var(--accent)}
.hero-sub{font-size:14px;color:var(--muted);max-width:520px;line-height:1.7;margin-bottom:18px}
.hero-badges{display:flex;flex-wrap:wrap;gap:8px}
.hero-badge{background:var(--bg3);border:1px solid var(--border);border-radius:20px;padding:5px 12px;font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace}
.hero-badge strong{color:var(--text)}
.home-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:2rem}
.home-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;cursor:pointer;transition:all 0.15s}
.home-card:hover{border-color:var(--border2);background:var(--bg3)}
.home-card-icon{font-size:22px;margin-bottom:8px}
.home-card-title{font-weight:700;font-size:13px;color:#fff;margin-bottom:3px}
.home-card-desc{font-size:12px;color:var(--muted);line-height:1.5}
.home-card-stat{font-family:'IBM Plex Mono',monospace;font-size:20px;font-weight:700;margin-top:6px}
.home-card-stat.green{color:var(--green)}.home-card-stat.amber{color:var(--amber)}.home-card-stat.accent{color:var(--accent)}.home-card-stat.blue{color:var(--blue)}
.metrics-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:1.75rem}
.metric-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:13px 15px}
.metric-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-family:'IBM Plex Mono',monospace;margin-bottom:5px}
.metric-val{font-size:24px;font-weight:700;font-family:'IBM Plex Mono',monospace;color:#fff}
.metric-val.green{color:var(--green)}.metric-val.amber{color:var(--amber)}
.metric-sub{font-size:11px;color:var(--muted);margin-top:2px}
.sec-header{display:flex;align-items:center;gap:10px;margin-bottom:1rem;margin-top:2rem}
.sec-header:first-of-type{margin-top:0}
.sec-header h2{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);white-space:nowrap}
.sec-line{flex:1;height:1px;background:var(--border)}
.badge{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;padding:3px 8px;border-radius:5px;font-family:'IBM Plex Mono',monospace}
.b-fire{background:var(--red-bg);color:var(--red);border:1px solid var(--red-border)}
.b-sharp{background:var(--blue-bg);color:var(--blue);border:1px solid var(--blue-border)}
.b-value{background:var(--green-bg);color:var(--green);border:1px solid var(--green-border)}
.b-watch{background:var(--amber-bg);color:var(--amber);border:1px solid var(--amber-border)}
.b-pass{background:var(--bg4);color:var(--muted);border:1px solid var(--border)}
.alert-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:1.75rem}
.alert-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:1.1rem;position:relative;overflow:hidden}
.alert-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
.alert-card.fire::before{background:linear-gradient(90deg,#f87171,#fb923c)}
.alert-card.sharp::before{background:linear-gradient(90deg,#60a5fa,#a78bfa)}
.alert-card.value::before{background:linear-gradient(90deg,#4ade80,#a3e635)}
.alert-card.watch::before{background:linear-gradient(90deg,#fbbf24,#fb923c)}
.alert-game{font-weight:700;font-size:14px;color:#fff;margin:7px 0 2px}
.alert-rec{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--accent);margin-bottom:9px}
.alert-stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:7px}
.stat-box{background:var(--bg3);border-radius:6px;padding:6px 8px}
.sl{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px}
.sv{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;color:#fff}
.sv.green{color:var(--green)}.sv.red{color:var(--red)}.sv.amber{color:var(--amber)}
.alert-reasoning{font-size:12px;color:#888;line-height:1.6;border-top:1px solid var(--border);padding-top:8px;margin-top:4px}
.dtable{width:100%;border-collapse:collapse;font-size:12px}
.dtable th{text-align:left;padding:8px 12px;font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:600;font-family:'IBM Plex Mono',monospace;background:var(--bg3);border-bottom:1px solid var(--border)}
.dtable td{padding:8px 12px;border-bottom:1px solid var(--border);vertical-align:middle}
.dtable tr:last-child td{border-bottom:none}
.dtable tr:hover td{background:rgba(255,255,255,0.015)}
.mono{font-family:'IBM Plex Mono',monospace;font-weight:600}
.c-green{color:var(--green)}.c-red{color:var(--red)}.c-amber{color:var(--amber)}.c-accent{color:var(--accent)}.c-muted{color:var(--muted)}
.pill{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:11px;padding:2px 7px;border-radius:4px;font-weight:600}
.pill-g{background:var(--green-bg);color:var(--green);border:1px solid var(--green-border)}
.pill-r{background:var(--red-bg);color:var(--red);border:1px solid var(--red-border)}
.pill-n{background:var(--bg3);color:var(--text);border:1px solid var(--border)}
.day-header{display:flex;align-items:center;gap:12px;margin:1.5rem 0 10px}
.day-label{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:1.5px;white-space:nowrap}
.day-header::after{content:'';flex:1;height:1px;background:rgba(163,230,53,0.2)}
.game-block{background:var(--bg2);border:1px solid var(--border);border-radius:12px;margin-bottom:10px;overflow:hidden}
.game-header{display:flex;align-items:center;justify-content:space-between;padding:12px 15px;cursor:pointer;user-select:none;transition:background 0.12s}
.game-header:hover{background:var(--bg3)}
.game-teams{font-weight:700;font-size:14px;color:#fff}
.game-time{font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace;margin-top:1px}
.game-right{display:flex;align-items:center;gap:7px;flex-shrink:0}
.toggle{font-size:12px;color:var(--muted);transition:transform 0.2s;margin-left:3px}
.game-block.open .toggle{transform:rotate(180deg)}
.game-body{display:none;padding:0 15px 15px}
.game-block.open .game-body{display:block}
.otable{width:100%;border-collapse:collapse;margin-top:12px;font-size:12px}
.otable th{text-align:left;padding:5px 9px;font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:500;font-family:'IBM Plex Mono',monospace;border-bottom:1px solid var(--border)}
.otable td{padding:7px 9px;border-bottom:1px solid rgba(39,39,42,0.5)}
.otable tr:last-child td{border-bottom:none}
.otable tr:hover td{background:rgba(255,255,255,0.015)}
.book{color:#888;font-size:12px}
.pc{font-family:'IBM Plex Mono',monospace;font-weight:600;color:#aaa;font-size:12px}
.pb{font-family:'IBM Plex Mono',monospace;font-weight:700;color:var(--accent);background:rgba(163,230,53,0.07);padding:2px 7px;border-radius:4px;font-size:12px}
.pw{font-family:'IBM Plex Mono',monospace;font-weight:700;color:var(--red);font-size:12px}
.po{font-family:'IBM Plex Mono',monospace;font-weight:700;color:var(--amber);font-size:12px}
.prob{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted)}
.claude-box{background:linear-gradient(135deg,rgba(163,230,53,0.05),rgba(163,230,53,0.01));border:1px solid rgba(163,230,53,0.18);border-radius:8px;padding:12px 14px;margin-top:12px}
.cb-header{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--accent);font-family:'IBM Plex Mono',monospace;font-weight:700;margin-bottom:10px}
.cb-grid{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:center}
.cb-team{background:rgba(0,0,0,0.3);border-radius:7px;padding:9px 11px;text-align:center}
.cb-name{font-size:11px;color:var(--muted);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cb-pct{font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:700;color:#fff}
.cb-pct.fav{color:var(--accent)}
.cb-line{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);margin-top:2px}
.cb-vs{text-align:center;font-size:11px;color:var(--dim);font-family:'IBM Plex Mono',monospace}
.cb-method{font-size:10px;color:#444;margin-top:8px;line-height:1.5;border-top:1px solid rgba(163,230,53,0.08);padding-top:7px}
.best-bet{background:linear-gradient(135deg,rgba(74,222,128,0.06),rgba(74,222,128,0.01));border:1px solid rgba(74,222,128,0.22);border-radius:8px;padding:12px 14px;margin-top:10px}
.best-bet.pass{background:rgba(0,0,0,0.2);border-color:var(--border)}
.bb-header{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--green);font-family:'IBM Plex Mono',monospace;font-weight:700;margin-bottom:7px}
.best-bet.pass .bb-header{color:var(--muted)}
.bb-play{font-size:14px;font-weight:700;color:#fff;margin-bottom:3px}
.best-bet.pass .bb-play{color:#777}
.bb-sub{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--accent);margin-bottom:8px}
.best-bet.pass .bb-sub{color:var(--muted)}
.bb-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.bbs{background:rgba(0,0,0,0.25);border-radius:6px;padding:6px 8px}
.bbs-label{font-size:10px;color:var(--muted);margin-bottom:2px;text-transform:uppercase;letter-spacing:0.5px}
.bbs-val{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;color:#fff}
.bbs-val.green{color:var(--green)}.bbs-val.c-muted{color:var(--muted)}
.pitcher-card{background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin-bottom:10px}
.pitcher-role{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-family:'IBM Plex Mono',monospace;margin-bottom:4px}
.pitcher-name{font-size:17px;font-weight:700;color:#fff;margin-bottom:2px}
.pitcher-team{font-size:12px;color:var(--muted)}
footer{background:var(--bg2);border-top:1px solid var(--border);padding:1.25rem 2rem;font-size:11px;color:var(--muted);text-align:center;line-height:1.8;margin-left:var(--sidebar)}
@media(max-width:768px){
  .sidebar{transform:translateX(-100%)}
  .sidebar.mobile-open{transform:translateX(0)}
  .main{margin-left:0}
  footer{margin-left:0}
  .hamburger{display:flex}
  .topbar-meta{display:none}
  .metrics-grid{grid-template-columns:repeat(2,1fr)}
  .alert-grid{grid-template-columns:1fr}
  .home-grid{grid-template-columns:1fr 1fr}
  .bb-stats{grid-template-columns:1fr 1fr}
  .alert-stats{grid-template-columns:1fr 1fr}
  .page-inner{padding:1rem}
  .hero{padding:1.5rem}
  .hero-title{font-size:22px}
  .otable th:nth-child(3),.otable td:nth-child(3),
  .otable th:nth-child(5),.otable td:nth-child(5){display:none}
}
</style>"""

    # ── FULL HTML ────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>MLB Sharp Lines — {date_str}</title>
{css}
</head>
<body>
<div class="overlay" id="overlay" onclick="closeSidebar()"></div>
<div class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <div class="sidebar-logo-title">MLB Sharp Lines</div>
    <div class="sidebar-logo-sub">Daily Value Tracker</div>
  </div>
  <div class="sidebar-date"><span class="live-dot"></span>{date_str}</div>
  <div class="sidebar-section">Navigation</div>
  <div class="nav-item active" onclick="showPage('home',this)"><span class="nav-icon">🏠</span><span class="nav-label">Home</span></div>
  <div class="nav-item" onclick="showPage('plays',this)"><span class="nav-icon">🔥</span><span class="nav-label">Top Value Plays</span><span class="nav-count">{value_ct}</span></div>
  <div class="nav-item" onclick="showPage('games',this)"><span class="nav-icon">⚾</span><span class="nav-label">All Games</span><span class="nav-count">{total}</span></div>
  <div class="nav-item" onclick="showPage('matchups',this)"><span class="nav-icon">⚡</span><span class="nav-label">Pitcher / Batter</span><span class="nav-count">{len(matchups)}</span></div>
  <div class="sidebar-section" style="margin-top:8px">Today</div>
  <div class="sidebar-stats">
    <div class="sidebar-stat"><span class="sidebar-stat-label">Games</span><span class="sidebar-stat-val">{total}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Sharp alerts</span><span class="sidebar-stat-val amber">{sharp_ct}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Value plays</span><span class="sidebar-stat-val green">{value_ct}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Updated</span><span class="sidebar-stat-val">{time_str}</span></div>
  </div>
</div>
<div class="main">
  <div class="topbar">
    <div class="topbar-left">
      <button class="hamburger" onclick="openSidebar()" aria-label="Open menu">
        <span></span><span></span><span></span>
      </button>
      <div class="topbar-title" id="topbar-title">Home</div>
    </div>
    <div class="topbar-meta">{total} games &nbsp;·&nbsp; {date_str}</div>
  </div>

  <!-- HOME -->
  <div class="page active" id="page-home"><div class="page-inner">
    <div class="hero">
      <div class="hero-eyebrow">MLB Sharp Lines Tracker</div>
      <div class="hero-title">Find the <span>edge</span><br>before the market does.</div>
      <div class="hero-sub">Pre-game odds from major US bookmakers. Vig-removed true probabilities, cross-book discrepancies, best bet per game, and historical pitcher/batter matchup data — auto-updated daily.</div>
      <div class="hero-badges">
        <div class="hero-badge"><strong>{total}</strong> games today</div>
        <div class="hero-badge"><strong>{sharp_ct}</strong> 🔥 sharp alerts</div>
        <div class="hero-badge"><strong>{value_ct}</strong> value plays</div>
        <div class="hero-badge">Updated <strong>{time_str}</strong></div>
        <div class="hero-badge">Cost: <strong>$0.00</strong></div>
      </div>
    </div>
    <div class="home-grid">
      <div class="home-card" onclick="showPage('plays',document.querySelectorAll('.nav-item')[1])">
        <div class="home-card-icon">🔥</div><div class="home-card-title">Top Value Plays</div>
        <div class="home-card-desc">Discrepancy flags and best plays ranked by edge.</div>
        <div class="home-card-stat amber">{sharp_ct} alerts</div>
      </div>
      <div class="home-card" onclick="showPage('games',document.querySelectorAll('.nav-item')[2])">
        <div class="home-card-icon">⚾</div><div class="home-card-title">All Games</div>
        <div class="home-card-desc">Full odds, true probability, and best bet for every game.</div>
        <div class="home-card-stat accent">{total} games</div>
      </div>
      <div class="home-card" onclick="showPage('matchups',document.querySelectorAll('.nav-item')[3])">
        <div class="home-card-icon">⚡</div><div class="home-card-title">Pitcher / Batter</div>
        <div class="home-card-desc">Career BA, HR, K for every batter against today's probable starters.</div>
        <div class="home-card-stat blue">{len(matchups)} games</div>
      </div>
      <div class="home-card">
        <div class="home-card-icon">🧮</div><div class="home-card-title">True Odds</div>
        <div class="home-card-desc">Vig stripped from every book, averaged for real win probability.</div>
        <div class="home-card-stat green">Free</div>
      </div>
    </div>
  </div></div>

  <!-- VALUE PLAYS -->
  <div class="page" id="page-plays"><div class="page-inner">
    <div class="metrics-grid">
      <div class="metric-card"><div class="metric-label">Games</div><div class="metric-val">{total}</div></div>
      <div class="metric-card"><div class="metric-label">Books</div><div class="metric-val">{books}</div></div>
      <div class="metric-card"><div class="metric-label">Sharp Alerts</div><div class="metric-val amber">{sharp_ct}</div></div>
      <div class="metric-card"><div class="metric-label">Value Plays</div><div class="metric-val green">{value_ct}</div></div>
      <div class="metric-card"><div class="metric-label">Cost</div><div class="metric-val" style="font-size:16px">$0/mo</div></div>
    </div>
    <div class="sec-header"><h2>🔥 Sharp Alerts</h2><div class="sec-line"></div></div>
    {alert_cards()}
    <div class="sec-header"><h2>📊 All Value Plays</h2><div class="sec-line"></div></div>
    {plays_table()}
    <div class="sec-header"><h2>📉 Line Discrepancies</h2><div class="sec-line"></div></div>
    {disc_table()}
  </div></div>

  <!-- ALL GAMES -->
  <div class="page" id="page-games"><div class="page-inner">
    {game_blocks()}
  </div></div>

  <!-- PITCHER / BATTER MATCHUPS -->
  <div class="page" id="page-matchups"><div class="page-inner">
    <div style="margin-bottom:1.5rem">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:700;color:#fff;margin-bottom:6px">⚡ Pitcher / Batter Matchups</div>
      <div style="font-size:13px;color:var(--muted)">Career all-time stats for each batter vs today's probable starting pitcher. Min 3 AB shown. Color = how well the batter has historically hit this pitcher.</div>
    </div>
    {matchup_page()}
  </div></div>

</div>
<footer>
  MLB Sharp Lines &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; Pre-game lines only &nbsp;·&nbsp; Matchup data: MLB Stats API &nbsp;·&nbsp; Auto-updated daily &nbsp;·&nbsp; Gamble responsibly
</footer>
<script>
  function showPage(name, el) {{
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    if (el) el.classList.add('active');
    const titles = {{home:'Home',plays:'Top Value Plays',games:'All Games',matchups:'Pitcher / Batter Matchups'}};
    document.getElementById('topbar-title').textContent = titles[name] || name;
    window.scrollTo(0, 0);
    closeSidebar();
  }}
  function toggleGame(el) {{ el.classList.toggle('open'); }}
  function openSidebar() {{
    document.getElementById('sidebar').classList.add('mobile-open');
    document.getElementById('overlay').classList.add('show');
  }}
  function closeSidebar() {{
    document.getElementById('sidebar').classList.remove('mobile-open');
    document.getElementById('overlay').classList.remove('show');
  }}
</script>
</body>
</html>"""


# ═════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════
def main():
    if not ODDS_API_KEY:
        print("ERROR: ODDS_API_KEY not set")
        sys.exit(1)

    now_et   = datetime.now(EASTERN)
    date_str = now_et.strftime("%B %d, %Y")
    time_str = now_et.strftime("%-I:%M %p ET")
    mlb_date = now_et.strftime("%Y-%m-%d")

    try:
        games_raw = fetch_odds()
    except Exception as e:
        print(f"ERROR fetching odds: {e}")
        sys.exit(1)

    if not games_raw:
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(f"<html><body style='background:#09090b;color:#e4e4e7;font-family:monospace;padding:3rem;text-align:center'><h1 style='color:#a3e635'>MLB Sharp Lines</h1><p style='color:#71717a;margin-top:1rem'>No upcoming games on {date_str}.</p></body></html>")
        return

    analyzed = []
    for g in games_raw:
        result = analyze_game(g)
        if result:
            analyzed.append(result)

    signal_order = {"fire": 0, "sharp": 1, "value": 2, "watch": 3, "pass": 4}
    analyzed.sort(key=lambda x: (x["date_sort"], signal_order.get(x["signal"], 3)))

    # Fetch pitcher/batter matchup data (free MLB Stats API)
    try:
        matchups = build_matchup_data(games_raw, mlb_date)
    except Exception as e:
        print(f"  Matchup fetch error: {e}")
        matchups = []

    html = build_html(analyzed, matchups, date_str, time_str)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Done — {len(analyzed)} games, {len(matchups)} matchups, {len(html):,} chars")


if __name__ == "__main__":
    main()
