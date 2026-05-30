"""
MLB Sharp Lines -- Daily Generator
Enhanced model v2: park factors, SP quality, bullpen fatigue,
injuries, umpire zone, wind. Free tier only.
"""
import os, sys, time, requests, json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
EASTERN      = ZoneInfo("America/New_York")
FETCH_PROPS  = False
EXCLUDED_BOOKS = {"betrivers", "lowvig", "bovada"}

MLB_IDS = {
    "New York Yankees":147,"Boston Red Sox":111,"Tampa Bay Rays":139,
    "Baltimore Orioles":110,"Toronto Blue Jays":141,"Chicago White Sox":145,
    "Cleveland Guardians":114,"Detroit Tigers":116,"Kansas City Royals":118,
    "Minnesota Twins":142,"Houston Astros":117,"Los Angeles Angels":108,
    "Athletics":133,"Oakland Athletics":133,"Seattle Mariners":136,
    "Texas Rangers":140,"Atlanta Braves":144,"Miami Marlins":146,
    "New York Mets":121,"Philadelphia Phillies":143,"Washington Nationals":120,
    "Chicago Cubs":112,"Cincinnati Reds":113,"Milwaukee Brewers":158,
    "Pittsburgh Pirates":134,"St. Louis Cardinals":138,"Arizona Diamondbacks":109,
    "Colorado Rockies":115,"Los Angeles Dodgers":119,"San Diego Padres":135,
    "San Francisco Giants":137,
}

PARK_FACTORS = {
    "Colorado Rockies":1.28,"Cincinnati Reds":1.10,"Boston Red Sox":1.08,
    "Philadelphia Phillies":1.06,"Chicago Cubs":1.05,"Texas Rangers":1.05,
    "Kansas City Royals":1.04,"Detroit Tigers":1.03,"Baltimore Orioles":1.03,
    "Minnesota Twins":1.02,"New York Yankees":1.01,"Atlanta Braves":1.00,
    "Washington Nationals":1.00,"Chicago White Sox":0.99,"Pittsburgh Pirates":0.99,
    "St. Louis Cardinals":0.98,"Cleveland Guardians":0.98,"Tampa Bay Rays":0.97,
    "Los Angeles Angels":0.97,"Toronto Blue Jays":0.97,"New York Mets":0.96,
    "Houston Astros":0.96,"Milwaukee Brewers":0.96,"Miami Marlins":0.95,
    "Seattle Mariners":0.95,"Arizona Diamondbacks":0.95,"Athletics":0.95,
    "Oakland Athletics":0.95,"Los Angeles Dodgers":0.95,"San Francisco Giants":0.93,
    "San Diego Padres":0.91,
}

STADIUMS = {
    "New York Yankees":     {"name":"Yankee Stadium",         "lat":40.8296,"lon":-73.9262,"orientation":45, "roof":False},
    "Boston Red Sox":       {"name":"Fenway Park",            "lat":42.3467,"lon":-71.0972,"orientation":95, "roof":False},
    "Tampa Bay Rays":       {"name":"Tropicana Field",        "lat":27.7683,"lon":-82.6534,"orientation":0,  "roof":True},
    "Baltimore Orioles":    {"name":"Camden Yards",           "lat":39.2838,"lon":-76.6218,"orientation":55, "roof":False},
    "Toronto Blue Jays":    {"name":"Rogers Centre",          "lat":43.6414,"lon":-79.3894,"orientation":0,  "roof":True},
    "Chicago White Sox":    {"name":"Guaranteed Rate Field",  "lat":41.8300,"lon":-87.6338,"orientation":4,  "roof":False},
    "Cleveland Guardians":  {"name":"Progressive Field",      "lat":41.4962,"lon":-81.6852,"orientation":8,  "roof":False},
    "Detroit Tigers":       {"name":"Comerica Park",          "lat":42.3390,"lon":-83.0485,"orientation":6,  "roof":False},
    "Kansas City Royals":   {"name":"Kauffman Stadium",       "lat":39.0517,"lon":-94.4803,"orientation":7,  "roof":False},
    "Minnesota Twins":      {"name":"Target Field",           "lat":44.9817,"lon":-93.2781,"orientation":355,"roof":False},
    "Houston Astros":       {"name":"Minute Maid Park",       "lat":29.7573,"lon":-95.3555,"orientation":35, "roof":True},
    "Los Angeles Angels":   {"name":"Angel Stadium",          "lat":33.8003,"lon":-117.8827,"orientation":0, "roof":False},
    "Athletics":            {"name":"Sutter Health Park",     "lat":38.5803,"lon":-121.5008,"orientation":20,"roof":False},
    "Oakland Athletics":    {"name":"Sutter Health Park",     "lat":38.5803,"lon":-121.5008,"orientation":20,"roof":False},
    "Seattle Mariners":     {"name":"T-Mobile Park",          "lat":47.5914,"lon":-122.3325,"orientation":10,"roof":True},
    "Texas Rangers":        {"name":"Globe Life Field",       "lat":32.7473,"lon":-97.0830, "orientation":35,"roof":True},
    "Atlanta Braves":       {"name":"Truist Park",            "lat":33.8908,"lon":-84.4678,"orientation":5,  "roof":False},
    "Miami Marlins":        {"name":"LoanDepot Park",         "lat":25.7781,"lon":-80.2197,"orientation":310,"roof":True},
    "New York Mets":        {"name":"Citi Field",             "lat":40.7571,"lon":-73.8458,"orientation":5,  "roof":False},
    "Philadelphia Phillies":{"name":"Citizens Bank Park",     "lat":39.9061,"lon":-75.1665,"orientation":333,"roof":False},
    "Washington Nationals": {"name":"Nationals Park",         "lat":38.8730,"lon":-77.0074,"orientation":356,"roof":False},
    "Chicago Cubs":         {"name":"Wrigley Field",          "lat":41.9484,"lon":-87.6553,"orientation":305,"roof":False},
    "Cincinnati Reds":      {"name":"Great American Ball Park","lat":39.0974,"lon":-84.5082,"orientation":22, "roof":False},
    "Milwaukee Brewers":    {"name":"American Family Field",  "lat":43.0280,"lon":-87.9712,"orientation":4,  "roof":True},
    "Pittsburgh Pirates":   {"name":"PNC Park",               "lat":40.4469,"lon":-80.0057,"orientation":340,"roof":False},
    "St. Louis Cardinals":  {"name":"Busch Stadium",          "lat":38.6226,"lon":-90.1928,"orientation":3,  "roof":False},
    "Arizona Diamondbacks": {"name":"Chase Field",            "lat":33.4453,"lon":-112.0667,"orientation":356,"roof":True},
    "Colorado Rockies":     {"name":"Coors Field",            "lat":39.7559,"lon":-104.9942,"orientation":20,"roof":False},
    "Los Angeles Dodgers":  {"name":"Dodger Stadium",         "lat":34.0739,"lon":-118.2400,"orientation":25,"roof":False},
    "San Diego Padres":     {"name":"Petco Park",             "lat":32.7076,"lon":-117.1570,"orientation":23,"roof":False},
    "San Francisco Giants": {"name":"Oracle Park",            "lat":37.7786,"lon":-122.3893,"orientation":25,"roof":False},
}

MLB_BASE = "https://statsapi.mlb.com/api/v1"
WIND_DIR_DEG = {
    "N":0,"NNE":22,"NE":45,"ENE":67,"E":90,"ESE":112,"SE":135,"SSE":157,
    "S":180,"SSW":202,"SW":225,"WSW":247,"W":270,"WNW":292,"NW":315,"NNW":337,
}

# =============================================================
# HELPERS
# =============================================================
def mlb_get(path, params=None):
    try:
        r = requests.get(MLB_BASE + path, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


MLB_DIVISIONS = {
    # AL East
    "New York Yankees":147, "Boston Red Sox":111, "Tampa Bay Rays":139,
    "Baltimore Orioles":110, "Toronto Blue Jays":141,
    # AL Central
    "Chicago White Sox":145, "Cleveland Guardians":114, "Detroit Tigers":116,
    "Kansas City Royals":118, "Minnesota Twins":142,
    # AL West
    "Houston Astros":117, "Los Angeles Angels":108, "Athletics":133,
    "Oakland Athletics":133, "Seattle Mariners":136, "Texas Rangers":140,
    # NL East
    "Atlanta Braves":144, "Miami Marlins":146, "New York Mets":121,
    "Philadelphia Phillies":143, "Washington Nationals":120,
    # NL Central
    "Chicago Cubs":112, "Cincinnati Reds":113, "Milwaukee Brewers":158,
    "Pittsburgh Pirates":134, "St. Louis Cardinals":138,
    # NL West
    "Arizona Diamondbacks":109, "Colorado Rockies":115, "Los Angeles Dodgers":119,
    "San Diego Padres":135, "San Francisco Giants":137,
}

# Division groups for rivalry detection
MLB_DIVISION_GROUPS = [
    {147,111,139,110,141},   # AL East
    {145,114,116,118,142},   # AL Central
    {117,108,133,136,140},   # AL West
    {144,146,121,143,120},   # NL East
    {112,113,158,134,138},   # NL Central
    {109,115,119,135,137},   # NL West
]

def same_division(team1_id, team2_id):
    for div in MLB_DIVISION_GROUPS:
        if team1_id in div and team2_id in div:
            return True
    return False
    try:
        r = requests.get(MLB_BASE + path, params=params, timeout=15)
        if r.status_code == 200: return r.json()
    except Exception: pass
    return None

def american_to_implied(price):
    try:
        p = float(price)
        return 100/(p+100) if p>0 else abs(p)/(abs(p)+100)
    except Exception: return None

def implied_to_american(prob):
    if prob is None or prob<=0 or prob>=1: return "N/A"
    return f"-{round((prob/(1-prob))*100)}" if prob>=0.5 else f"+{round(((1-prob)/prob)*100)}"

def remove_vig(a, b):
    if a is None or b is None: return None, None
    t = a + b
    return (a/t, b/t) if t>0 else (None, None)

def fmt(price):
    try:
        p = int(price)
        return f"+{p}" if p>0 else str(p)
    except Exception: return str(price)

# =============================================================
# ODDS FETCH
# =============================================================
def fetch_live_mlb_games(yesterday_str):
    data = mlb_get("/schedule", {"sportId":1,"date":yesterday_str,"hydrate":"team"})
    if not data: return set()
    live = set()
    for db in data.get("dates",[]):
        for g in db.get("games",[]):
            if g.get("status",{}).get("abstractGameState","") == "Live":
                aid = g.get("teams",{}).get("away",{}).get("team",{}).get("id")
                hid = g.get("teams",{}).get("home",{}).get("team",{}).get("id")
                if aid and hid: live.add((aid,hid))
    return live

def fetch_odds():
    print("Fetching MLB odds...")
    r = requests.get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
        params={"apiKey":ODDS_API_KEY,"regions":"us","markets":"h2h,totals",
                "oddsFormat":"american","dateFormat":"iso"},
        timeout=30,
    )
    r.raise_for_status()
    all_games    = r.json()
    now_et       = datetime.now(EASTERN)
    now_utc      = datetime.now(timezone.utc)
    today_et     = now_et.date()
    yesterday_et = today_et - timedelta(days=1)
    live_yesterday = fetch_live_mlb_games(yesterday_et.strftime("%Y-%m-%d"))
    pregame  = []   # not yet started -- full odds analysis
    tracking = []   # started today -- show locked tracking card until midnight
    for g in all_games:
        try:
            start      = datetime.fromisoformat(g["commence_time"].replace("Z","+00:00"))
            start_et   = start.astimezone(EASTERN)
            start_date = start_et.date()
            if start_date == today_et:
                if start > now_utc:
                    pregame.append(g)
                else:
                    print(f"  Tracking (started): {g['away_team']} @ {g['home_team']} ({start_et.strftime('%-I:%M %p ET')})")
                    tracking.append(g)
            elif start_date > today_et:
                pregame.append(g)
            elif start_date == yesterday_et:
                aid = MLB_IDS.get(g["away_team"])
                hid = MLB_IDS.get(g["home_team"])
                if aid and hid and (aid,hid) in live_yesterday:
                    print(f"  Keeping live past-midnight: {g['away_team']} @ {g['home_team']}")
                    pregame.append(g)
                else:
                    print(f"  Skipping finished: {g['away_team']} @ {g['home_team']}")
            else:
                print(f"  Skipping old: {g['away_team']} @ {g['home_team']}")
        except Exception:
            pregame.append(g)
    print(f"Got {len(all_games)} total -- {len(pregame)} pre-game, {len(tracking)} tracking")
    # Deduplicate by game ID (odds API can return same game multiple times)
    seen = set()
    pregame_deduped = []
    for g in pregame:
        gid = g.get("id","") or f"{g.get('away_team','')}@{g.get('home_team','')}"
        if gid not in seen:
            seen.add(gid)
            pregame_deduped.append(g)
    if len(pregame_deduped) < len(pregame):
        print(f"  Deduped: {len(pregame)} -> {len(pregame_deduped)} pre-game games")
    return pregame_deduped, tracking


# =============================================================
# MLB DATA FETCHERS
# =============================================================
def fetch_pitcher_stats(pitcher_id):
    if not pitcher_id:
        return {"name":"TBD","era":"N/A","whip":"N/A","k9":"N/A","id":None,"quality":0.0,
                "pitch_hand":"R","last3_era":None,"days_rest":None,"last_pitch_count":None,"fatigue_adj":0.0}
    data = mlb_get(f"/people/{pitcher_id}", {
        "hydrate": "stats(group=pitching,type=season,season=2026),stats(group=pitching,type=lastXGames,limit=3)"
    })
    if not data:
        return {"name":"TBD","era":"N/A","whip":"N/A","k9":"N/A","id":pitcher_id,"quality":0.0,
                "pitch_hand":"R","last3_era":None,"days_rest":None,"last_pitch_count":None,"fatigue_adj":0.0}
    person      = data.get("people",[{}])[0]
    name        = person.get("fullName","TBD")
    pitch_hand  = person.get("pitchHand",{}).get("code","R")
    era = whip = k9 = "N/A"
    season_quality = 0.0
    last3_era      = None

    for sg in person.get("stats",[]):
        stype  = sg.get("type",{}).get("displayName","")
        splits = sg.get("splits",[])
        if not splits: continue
        s = splits[0].get("stat",{})
        if "season" in stype.lower() or stype == "":
            era  = str(s.get("era","N/A"))
            whip = str(s.get("whip","N/A"))
            ip   = float(s.get("inningsPitched",0) or 0)
            k    = float(s.get("strikeOuts",0) or 0)
            k9   = f"{round(k/ip*9,1)}" if ip>0 else "N/A"
            try: season_quality = max(-0.08, min(0.08, (4.20-float(era))*0.04))
            except Exception: pass
        elif "last" in stype.lower() or "lastX" in stype:
            raw = s.get("era")
            if raw is not None:
                try: last3_era = float(raw)
                except Exception: pass

    quality = season_quality
    if last3_era is not None:
        try:
            last3_quality = max(-0.08, min(0.08, (4.20-last3_era)*0.04))
            quality = 0.6*last3_quality + 0.4*season_quality
        except Exception:
            pass

    return {
        "name":       name,
        "era":        era,
        "whip":       whip,
        "k9":         k9,
        "id":         pitcher_id,
        "quality":    round(quality,3),
        "pitch_hand": pitch_hand,
        "last3_era":  f"{last3_era:.2f}" if last3_era is not None else None,
        "days_rest":  None,
        "last_pitch_count": None,
        "fatigue_adj": 0.0,
    }


def fetch_f5_nrfi_odds():
    """
    Fetch First 5 innings (h2h_h1, spreads_h1, totals_h1) and
    NRFI/YRFI (totals_q1) markets from the Odds API.
    Returns list of game dicts with F5/NRFI bookmaker data.
    """
    results = {}
    # F5 markets
    # Try different market key formats — Odds API support varies by plan
    market_attempts = [
        ("h2h_h1", "F5_h2h"),
        ("totals_h1", "F5_totals"),
        ("spreads_h1", "F5_spreads"),
    ]
    for market_set, label in market_attempts:
        try:
            r = requests.get(
                "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
                params={"apiKey":ODDS_API_KEY,"regions":"us","markets":market_set,
                        "oddsFormat":"american","dateFormat":"iso"},
                timeout=20,
            )
            if r.status_code != 200:
                print(f"  F5/NRFI {label}: HTTP {r.status_code}")
                continue
            for g in r.json():
                gid = g.get("id","")
                if gid not in results:
                    results[gid] = {
                        "id":           gid,
                        "away_team":    g.get("away_team",""),
                        "home_team":    g.get("home_team",""),
                        "commence_time":g.get("commence_time",""),
                        "f5_books":     [],
                        "nrfi_books":   [],
                    }
                for b in g.get("bookmakers",[]):
                    book_name = b.get("title","")
                    entry = {"name": book_name}
                    for m in b.get("markets",[]):
                        mk = m.get("key","")
                        outs = {o["name"]: o["price"] for o in m.get("outcomes",[])}
                        if mk == "h2h_h1":
                            entry["f5_away_ml"] = outs.get(g.get("away_team",""))
                            entry["f5_home_ml"] = outs.get(g.get("home_team",""))
                        elif mk == "spreads_h1":
                            for o in m.get("outcomes",[]):
                                if o["name"] == g.get("away_team",""):
                                    entry["f5_away_rl"]    = o.get("price")
                                    entry["f5_away_spread"]= o.get("point")
                                else:
                                    entry["f5_home_rl"]    = o.get("price")
                                    entry["f5_home_spread"]= o.get("point")
                        elif mk == "totals_h1":
                            for o in m.get("outcomes",[]):
                                if o["name"] == "Over":
                                    entry["f5_over_line"]  = o.get("point")
                                    entry["f5_over_price"] = o.get("price")
                                else:
                                    entry["f5_under_line"]  = o.get("point")
                                    entry["f5_under_price"] = o.get("price")
                        elif mk == "totals_q1":
                            for o in m.get("outcomes",[]):
                                if o.get("point") is not None and abs(float(o.get("point",0))) < 1:
                                    # 0.5 line = NRFI/YRFI
                                    if o["name"] == "Under":
                                        entry["nrfi_price"] = o.get("price")
                                        entry["nrfi_line"]  = o.get("point")
                                    else:
                                        entry["yrfi_price"] = o.get("price")
                    if label == "NRFI":
                        if entry.get("nrfi_price") or entry.get("yrfi_price"):
                            results[gid]["nrfi_books"].append(entry)
                    else:
                        if any(k.startswith("f5_") for k in entry):
                            results[gid]["f5_books"].append(entry)
        except Exception as e:
            print(f"  F5/NRFI {label} error: {e}")

    games = list(results.values())
    f5_ct   = sum(1 for g in games if g["f5_books"])
    nrfi_ct = sum(1 for g in games if g["nrfi_books"])
    print(f"  F5 data: {f5_ct} games | NRFI data: {nrfi_ct} games")
    return games
    if not pitcher_id:
        return {"name":"TBD","era":"N/A","whip":"N/A","k9":"N/A","id":None,"quality":0.0,
                "pitch_hand":"R","last3_era":None,"days_rest":None,"last_pitch_count":None,"fatigue_adj":0.0}
    data = mlb_get(f"/people/{pitcher_id}", {
        "hydrate": "stats(group=pitching,type=season,season=2026),stats(group=pitching,type=lastXGames,limit=3)"
    })
    if not data:
        return {"name":"TBD","era":"N/A","whip":"N/A","k9":"N/A","id":pitcher_id,"quality":0.0,
                "pitch_hand":"R","last3_era":None,"days_rest":None,"last_pitch_count":None,"fatigue_adj":0.0}
    person      = data.get("people",[{}])[0]
    name        = person.get("fullName","TBD")
    pitch_hand  = person.get("pitchHand",{}).get("code","R")
    era = whip = k9 = "N/A"
    season_quality = 0.0
    last3_era      = None

    for sg in person.get("stats",[]):
        stype  = sg.get("type",{}).get("displayName","")
        splits = sg.get("splits",[])
        if not splits: continue
        s = splits[0].get("stat",{})
        if "season" in stype.lower() or stype == "":
            era  = str(s.get("era","N/A"))
            whip = str(s.get("whip","N/A"))
            ip   = float(s.get("inningsPitched",0) or 0)
            k    = float(s.get("strikeOuts",0) or 0)
            k9   = f"{round(k/ip*9,1)}" if ip>0 else "N/A"
            try: season_quality = max(-0.08, min(0.08, (4.20-float(era))*0.04))
            except Exception: pass
        elif "last" in stype.lower() or "lastX" in stype:
            raw = s.get("era")
            if raw is not None:
                try: last3_era = float(raw)
                except Exception: pass

    quality = season_quality
    if last3_era is not None:
        try:
            last3_quality = max(-0.08, min(0.08, (4.20-last3_era)*0.04))
            quality = 0.6*last3_quality + 0.4*season_quality
        except Exception:
            pass

    # SP fatigue: fetch last start date and pitch count
    days_rest       = None
    last_pitch_count= None
    fatigue_adj     = 0.0
    try:
        now_et    = datetime.now(EASTERN)
        end_str   = now_et.strftime("%Y-%m-%d")
        start_str = (now_et - timedelta(days=10)).strftime("%Y-%m-%d")
        glogs = mlb_get(f"/people/{pitcher_id}/stats", {
            "stats":     "gameLog",
            "group":     "pitching",
            "season":    "2026",
            "startDate": start_str,
            "endDate":   end_str,
        })
        if glogs:
            splits = []
            for sg in glogs.get("stats",[]):
                splits.extend(sg.get("splits",[]))
            # Find most recent start (IP >= 3 = SP appearance)
            starts = [s for s in splits
                      if float(str(s.get("stat",{}).get("inningsPitched","0") or "0").split(".")[0]) >= 3]
            if starts:
                last = starts[-1]
                last_date_str = last.get("date","")
                pc = last.get("stat",{}).get("pitchesThrown") or last.get("stat",{}).get("numberOfPitches")
                last_pitch_count = int(pc) if pc else None
                if last_date_str:
                    try:
                        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=EASTERN)
                        days_rest = (now_et.replace(tzinfo=None) - last_date.replace(tzinfo=None)).days
                    except Exception:
                        pass
                # Fatigue adjustments
                if days_rest is not None and days_rest <= 3:
                    fatigue_adj -= 0.025   # short rest penalty
                elif days_rest is not None and days_rest >= 7:
                    fatigue_adj += 0.01    # extra rest slight boost
                if last_pitch_count and last_pitch_count >= 110:
                    fatigue_adj -= 0.015   # high pitch count last start
                fatigue_adj = round(max(-0.04, min(0.02, fatigue_adj)), 3)
    except Exception:
        pass

    return {
        "name":             name,
        "era":              era,
        "whip":             whip,
        "k9":               k9,
        "id":               pitcher_id,
        "quality":          round(quality + fatigue_adj, 3),
        "quality_base":     round(quality, 3),
        "fatigue_adj":      fatigue_adj,
        "pitch_hand":       pitch_hand,
        "last3_era":        f"{last3_era:.2f}" if last3_era is not None else None,
        "days_rest":        days_rest,
        "last_pitch_count": last_pitch_count,
    }

def fetch_injuries(team_id):
    if not team_id: return []
    data = mlb_get("/injuries", {"sportId":1,"teamId":team_id})
    if not data: return []
    out = []
    for p in data.get("injuries",[]):
        out.append({
            "name":   p.get("person",{}).get("fullName","?"),
            "pos":    p.get("position",{}).get("abbreviation",""),
            "status": p.get("status",""),
        })
    return out

def fetch_bullpen_fatigue(team_id):
    if not team_id: return {"ip":0,"fatigue":0.0,"label":"Unknown"}
    try:
        now_et = datetime.now(EASTERN)
        end_str   = now_et.strftime("%Y-%m-%d")
        start_str = (now_et - timedelta(days=3)).strftime("%Y-%m-%d")
        data = mlb_get("/schedule",{"sportId":1,"teamId":team_id,
                                    "startDate":start_str,"endDate":end_str,
                                    "hydrate":"boxscore","gameType":"R"})
        if not data: return {"ip":0,"fatigue":0.0,"label":"Fresh"}
        total_ip = 0.0
        for db in data.get("dates",[]):
            for g in db.get("games",[]):
                if g.get("status",{}).get("abstractGameState","") != "Final": continue
                box = g.get("liveData",{}).get("boxscore",{})
                for side in ["away","home"]:
                    t = box.get("teams",{}).get(side,{})
                    if t.get("team",{}).get("id") == team_id:
                        for pid, pd in t.get("players",{}).items():
                            if pd.get("position",{}).get("abbreviation","") not in ("SP",):
                                ip_str = str(pd.get("stats",{}).get("pitching",{}).get("inningsPitched","0") or "0")
                                try:
                                    parts = ip_str.split(".")
                                    ip = float(parts[0]) + (float(parts[1])/3 if len(parts)>1 else 0)
                                    total_ip += ip
                                except Exception: pass
        fatigue = min(total_ip/9.0, 1.0)
        label = "Fresh" if fatigue<0.33 else ("Moderate" if fatigue<0.67 else "Fatigued")
        return {"ip":round(total_ip,1),"fatigue":round(fatigue,2),"label":label}
    except Exception as e:
        return {"ip":0,"fatigue":0.0,"label":"Unknown"}

def fetch_umpire(game_id_mlb):
    if not game_id_mlb: return {"name":"TBD","run_impact":0}
    try:
        data = mlb_get(f"/game/{game_id_mlb}/boxscore")
        if not data: return {"name":"TBD","run_impact":0}
        hp_ump = next((o for o in data.get("officials",[])
                       if o.get("officialType","")=="Home Plate"), None)
        if not hp_ump: return {"name":"TBD","run_impact":0}
        ump_name = hp_ump.get("official",{}).get("fullName","TBD")
        try:
            resp = requests.get("https://umpscorecards.com/api/umpire/",
                                params={"name":ump_name},timeout=8)
            if resp.status_code==200:
                ri = resp.json().get("run_impact",0) or 0
                return {"name":ump_name,"run_impact":round(float(ri),2)}
        except Exception: pass
        return {"name":ump_name,"run_impact":0}
    except Exception: return {"name":"TBD","run_impact":0}

def fetch_last_five_record(team_id):
    if not team_id: return None
    try:
        now_et = datetime.now(EASTERN)
        end_str   = now_et.strftime("%Y-%m-%d")
        start_str = (now_et - timedelta(days=14)).strftime("%Y-%m-%d")
        sched = mlb_get("/schedule",{"sportId":1,"teamId":team_id,
                                     "startDate":start_str,"endDate":end_str,
                                     "hydrate":"decisions,linescore","gameType":"R"})
        if not sched: return None
        results = []
        for db in sched.get("dates",[]):
            for g in db.get("games",[]):
                if g.get("status",{}).get("abstractGameState","") != "Final": continue
                teams = g.get("teams",{})
                away_d = teams.get("away",{}); home_d = teams.get("home",{})
                is_home = home_d.get("team",{}).get("id")==team_id
                my_s = home_d if is_home else away_d
                op_s = away_d if is_home else home_d
                my_r = my_s.get("score",0); op_r = op_s.get("score",0)
                results.append({"won":my_r>op_r,"my_runs":my_r,"op_runs":op_r,
                                 "opp":op_s.get("team",{}).get("abbreviation","?"),"home":is_home})
        last5 = results[-5:] if len(results)>=5 else results
        wins  = sum(1 for r in last5 if r["won"])
        # Bounce-back detection: lost by 5+ in most recent game
        bounce_back = False
        if results:
            last = results[-1]
            if not last["won"] and (last["op_runs"] - last["my_runs"]) >= 5:
                bounce_back = True
        return {"games":last5,"wins":wins,"losses":len(last5)-wins,
                "bounce_back": bounce_back}
    except Exception: return None

def fetch_roster(team_id):
    data = mlb_get(f"/teams/{team_id}/roster",{"rosterType":"active"})
    if not data: return []
    return [{"id":p["person"]["id"],"name":p["person"]["fullName"],
             "pos":p.get("position",{}).get("abbreviation","")}
            for p in data.get("roster",[])
            if p.get("position",{}).get("abbreviation","") not in ("P","TWP")]

def fetch_batter_vs_pitcher(batter_id, pitcher_id):
    data = mlb_get(f"/people/{batter_id}/stats",
                   {"stats":"vsPlayer","opposingPlayerId":pitcher_id,"group":"hitting","sportId":1})
    if not data: return None
    for sg in data.get("stats",[]):
        splits = sg.get("splits",[])
        if splits:
            s = splits[0].get("stat",{}); ab = s.get("atBats",0)
            if ab==0: return None
            h=s.get("hits",0); hr=s.get("homeRuns",0); k=s.get("strikeOuts",0)
            avg=round(h/ab,3) if ab else 0
            return {"ab":ab,"h":h,"hr":hr,"k":k,
                    "avg":f".{str(round(avg*1000)).zfill(3)}",
                    "display":f"{h}/{ab}"}
    return None


# =============================================================
# HANDEDNESS + PLATOON
# =============================================================
def fetch_batters_handedness(batter_ids):
    """Batch fetch batting hand for multiple batters. Returns {id: 'L'/'R'/'S'}"""
    if not batter_ids: return {}
    ids_str = ",".join(str(b) for b in batter_ids)
    data = mlb_get("/people", {"personIds": ids_str})
    if not data: return {}
    result = {}
    for person in data.get("people", []):
        pid  = person.get("id")
        side = person.get("batSide", {}).get("code")
        if pid and side:
            result[pid] = side
    return result


def calc_platoon_adjustment(batter_sides, pitcher_hand):
    """
    Returns win probability adjustment for the batting team.
    Same-hand matchup = platoon disadvantage (LHB vs LHP, RHB vs RHP).
    Switch hitters (S) are neutral.
    Max adjustment: -3% (heavy disadvantage) to +1.5% (platoon advantage).
    """
    if not pitcher_hand or not batter_sides:
        return 0.0
    disadvantaged = 0; total = 0
    for side in batter_sides:
        if side == "S": continue
        total += 1
        if side == pitcher_hand:
            disadvantaged += 1
    if total == 0: return 0.0
    pct = disadvantaged / total
    if   pct > 0.65: return -0.025
    elif pct > 0.55: return -0.015
    elif pct < 0.35: return  0.015
    elif pct < 0.45: return  0.010
    return 0.0


def load_opening_lines():
    """Load the 9am line snapshot if it exists."""
    if not os.path.exists("opening_lines.json"):
        return {}
    try:
        with open("opening_lines.json") as f:
            data = json.load(f)
        return data.get("games", {})
    except Exception:
        return {}


def calc_line_movement(game_key, opening_games, current_book_data):
    """
    Compare current consensus line to 9am opening line.
    Returns dict with movement info or None.
    """
    opening = opening_games.get(game_key)
    if not opening or not opening.get("books"):
        return None

    # Median current away/home prices
    def median(lst):
        s = sorted(lst); n = len(s)
        return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2

    curr_away = median([b["away_price"] for b in current_book_data if b.get("away_price")])
    curr_home = median([b["home_price"] for b in current_book_data if b.get("home_price")])

    # Median opening prices across books
    open_away_list = [v["away_price"] for v in opening["books"].values() if v.get("away_price")]
    open_home_list = [v["home_price"] for v in opening["books"].values() if v.get("home_price")]
    if not open_away_list or not open_home_list:
        return None

    open_away = median(open_away_list)
    open_home = median(open_home_list)

    def implied_diff(p1, p2):
        """Difference in implied probability in cents (percentage points * 100)."""
        i1 = american_to_implied(p1); i2 = american_to_implied(p2)
        if i1 is None or i2 is None: return 0
        return round((i1 - i2) * 100, 1)

    away_move = implied_diff(curr_away, open_away)  # positive = line moved toward away
    home_move = implied_diff(curr_home, open_home)  # positive = line moved toward home

    # Flag meaningful movement (5+ cents / percentage points)
    if abs(away_move) >= 5 or abs(home_move) >= 5:
        moved_team  = None; move_cents = 0
        if abs(away_move) >= abs(home_move):
            moved_team = "away"; move_cents = away_move
        else:
            moved_team = "home"; move_cents = home_move
        direction   = "toward" if move_cents > 0 else "away from"
        return {
            "away_move":   away_move,
            "home_move":   home_move,
            "moved_team":  moved_team,
            "move_cents":  move_cents,
            "significant": abs(move_cents) >= 10,  # 10+ cents = sharp signal
            "open_away":   open_away,
            "open_home":   open_home,
        }
    return None
# =============================================================
def wind_vs_field(wind_dir_str, field_orientation):
    wind_deg = WIND_DIR_DEG.get(wind_dir_str.upper().replace(" ",""),None)
    if wind_deg is None: return "unknown",0
    wind_toward = (wind_deg+180)%360; cf_dir = field_orientation%360
    diff = abs(wind_toward-cf_dir)
    if diff>180: diff=360-diff
    if diff<=45: return "blowing_out",diff
    elif diff>=135: return "blowing_in",diff
    else: return "crosswind",diff

def fetch_nws_weather(lat, lon):
    try:
        meta = requests.get(f"https://api.weather.gov/points/{lat},{lon}",
                            headers={"User-Agent":"mlb-sharp-lines/1.0"},timeout=10)
        if meta.status_code!=200: return None
        fc_url = meta.json().get("properties",{}).get("forecastHourly")
        if not fc_url: return None
        fc = requests.get(fc_url,headers={"User-Agent":"mlb-sharp-lines/1.0"},timeout=10)
        if fc.status_code!=200: return None
        periods = fc.json().get("properties",{}).get("periods",[])
        if not periods: return None
        p = periods[0]
        return {"temp":p.get("temperature","?"),"temp_unit":p.get("temperatureUnit","F"),
                "wind_speed":p.get("windSpeed","0 mph").replace(" mph","").strip(),
                "wind_dir":p.get("windDirection","N"),
                "condition":p.get("shortForecast",""),
                "humidity":p.get("relativeHumidity",{}).get("value","?")}
    except Exception: return None

def fetch_weather_for_games(games_raw):
    print("Fetching weather...")
    weather = {}; seen = set()
    for g in games_raw:
        home = g["home_team"]
        if home in seen: continue
        seen.add(home)
        stadium = STADIUMS.get(home)
        if not stadium: continue
        if stadium.get("roof"):
            weather[home] = {"roof":True,"stadium_name":stadium["name"]}; continue
        print(f"  Weather: {stadium['name']}...")
        w = fetch_nws_weather(stadium["lat"],stadium["lon"])
        if w:
            effect,_ = wind_vs_field(w["wind_dir"],stadium["orientation"])
            weather[home] = {"roof":False,"stadium_name":stadium["name"],
                             "temp":w["temp"],"temp_unit":w["temp_unit"],
                             "wind_speed":w["wind_speed"],"wind_dir":w["wind_dir"],
                             "condition":w["condition"],"humidity":w["humidity"],
                             "wind_effect":effect,"orientation":stadium["orientation"]}
        time.sleep(0.3)
    print(f"  Weather done: {len(weather)} stadiums")
    return weather

# =============================================================
# MATCHUP DATA
# =============================================================
def fetch_public_betting(date_str):
    """
    Fetch public betting percentages from Action Network's unofficial API.
    Returns dict keyed by "Away @ Home" with {away_pct, home_pct, away_money_pct, home_money_pct}
    """
    result = {}
    try:
        url = f"https://api.actionnetwork.com/web/v1/scoreboard/mlb"
        r = requests.get(url, params={"period":"game","date":date_str.replace("-","")},
                         headers={"User-Agent":"Mozilla/5.0"},
                         timeout=15)
        if r.status_code != 200:
            print(f"  Public betting: HTTP {r.status_code} from Action Network")
            return result
        data = r.json()
        for game in data.get("games",[]):
            teams = game.get("teams",[])
            if len(teams) < 2: continue
            # Action Network: index 0 = away, index 1 = home
            away_t = next((t for t in teams if not t.get("is_home",True)), teams[0])
            home_t = next((t for t in teams if t.get("is_home",False)), teams[1])
            away_name = away_t.get("full_name","")
            home_name = home_t.get("full_name","")
            away_bets  = away_t.get("bettors_pct") or away_t.get("bets_pct")
            home_bets  = home_t.get("bettors_pct") or home_t.get("bets_pct")
            away_money = away_t.get("money_pct")
            home_money = home_t.get("money_pct")
            if away_name and home_name and (away_bets is not None or home_bets is not None):
                # Try to match to our team name format
                key = f"{away_name} @ {home_name}"
                result[key] = {
                    "away_bets":  round(float(away_bets  or 0)),
                    "home_bets":  round(float(home_bets  or 0)),
                    "away_money": round(float(away_money or 0)) if away_money else None,
                    "home_money": round(float(home_money or 0)) if home_money else None,
                }
        if result:
            print(f"  Public betting data: {len(result)} games from Action Network")
        else:
            print("  Public betting: no data returned (may not be available pre-game)")
    except Exception as e:
        print(f"  Public betting error: {e}")
    return result


def match_public_betting(game_key, public_data, away_name, home_name):
    """
    Fuzzy match our game key to Action Network's team names.
    Returns the public betting dict or None.
    """
    if game_key in public_data:
        return public_data[game_key]
    # Try partial name matching
    for key, val in public_data.items():
        parts = key.split(" @ ")
        if len(parts) != 2: continue
        an_away, an_home = parts
        if (any(w in an_away for w in away_name.split()[-2:]) and
            any(w in an_home for w in home_name.split()[-2:])):
            return val
    return None
    """
    Fetch probable pitchers for all games on a given date.
    Tries multiple methods since the MLB API hydration is inconsistent.
    Returns dict: {(away_team_id, home_team_id): {"away": pitcher_id, "home": pitcher_id}}
    """
    result = {}

    # Method 1: schedule with all current hydration format variants
    for hydrate in [
        "probablePitcher(note),team",
        "probablePitcher,team",
        "probablePitcher",
    ]:
        data = mlb_get("/schedule", {
            "sportId":  1,
            "date":     date_str,
            "hydrate":  hydrate,
        })
        if not data: continue
        found = 0
        for db in data.get("dates", []):
            for g in db.get("games", []):
                teams  = g.get("teams", {})
                away_t = teams.get("away", {})
                home_t = teams.get("home", {})
                aid    = away_t.get("team", {}).get("id")
                hid    = home_t.get("team", {}).get("id")
                ap     = away_t.get("probablePitcher")
                hp     = home_t.get("probablePitcher")
                if aid and hid and (ap or hp):
                    result[(aid, hid)] = {
                        "away": ap.get("id") if ap else None,
                        "home": hp.get("id") if hp else None,
                    }
                    found += 1
        if found > 0:
            print(f"  Pitchers via schedule hydrate='{hydrate}': {found} games")
            return result

    # Method 2: fetch game PKs then use per-game content endpoint
    print("  Schedule hydration returned no pitchers -- trying per-game content endpoint...")
    sched = mlb_get("/schedule", {"sportId": 1, "date": date_str})
    if sched:
        game_pks = []
        for db in sched.get("dates", []):
            for g in db.get("games", []):
                pk  = g.get("gamePk")
                aid = g.get("teams", {}).get("away", {}).get("team", {}).get("id")
                hid = g.get("teams", {}).get("home", {}).get("team", {}).get("id")
                if pk and aid and hid:
                    game_pks.append((pk, aid, hid))

        found = 0
        for pk, aid, hid in game_pks:
            try:
                content = mlb_get(f"/game/{pk}/content")
                if content:
                    preview = content.get("editorial", {}).get("preview", {}).get("articles", {}).get("items", [])
                    # Also try boxscore which sometimes has probables
                    box = mlb_get(f"/game/{pk}/boxscore")
                    if box:
                        teams = box.get("teams", {})
                        for side, team_id in [("away", aid), ("home", hid)]:
                            t = teams.get(side, {})
                            # pitchers list — first SP is usually the starter
                            pitchers = t.get("pitchers", [])
                            if pitchers:
                                if (aid, hid) not in result:
                                    result[(aid, hid)] = {"away": None, "home": None}
                                # Can't reliably get probable from boxscore alone
                time.sleep(0.05)
            except Exception:
                pass

    # Method 3: use the /people endpoint to search for probable starters by team
    # This uses the roster + recent transactions approach
    if not result:
        print("  Trying per-team probable starter lookup...")
        sched2 = mlb_get("/schedule", {"sportId": 1, "date": date_str})
        if sched2:
            for db in sched2.get("dates", []):
                for g in db.get("games", []):
                    pk  = g.get("gamePk")
                    aid = g.get("teams", {}).get("away", {}).get("team", {}).get("id")
                    hid = g.get("teams", {}).get("home", {}).get("team", {}).get("id")
                    if not pk: continue
                    # Try game feed linescore which sometimes includes probables
                    feed = mlb_get(f"/game/{pk}/linescore")
                    if feed:
                        defp = feed.get("defense", {}).get("pitcher", {})
                        offp = feed.get("offense", {}).get("pitcher", {})
                        # These are in-game, not pre-game — skip if game started
                        pass
                    # Most reliable: check if game has a note with pitcher names
                    time.sleep(0.03)

    if not result:
        print(f"  WARNING: No probable pitchers found for {date_str} -- MLB may not have announced them yet")
    return result


def fetch_probable_pitchers(date_str):
    """
    Fetch probable pitchers for all games on a given date.
    Tries multiple hydration formats since the MLB API is inconsistent.
    Returns dict: {(away_team_id, home_team_id): {"away": pitcher_id, "home": pitcher_id}}
    """
    result = {}
    for hydrate in ["probablePitcher(note),team","probablePitcher,team","probablePitcher"]:
        data = mlb_get("/schedule",{"sportId":1,"date":date_str,"hydrate":hydrate})
        if not data: continue
        found = 0
        for db in data.get("dates",[]):
            for g in db.get("games",[]):
                teams  = g.get("teams",{})
                away_t = teams.get("away",{}); home_t = teams.get("home",{})
                aid    = away_t.get("team",{}).get("id")
                hid    = home_t.get("team",{}).get("id")
                ap     = away_t.get("probablePitcher")
                hp     = home_t.get("probablePitcher")
                if aid and hid and (ap or hp):
                    result[(aid,hid)] = {
                        "away": ap.get("id") if ap else None,
                        "home": hp.get("id") if hp else None,
                    }
                    found += 1
        if found > 0:
            print(f"  Pitchers via schedule hydrate='{hydrate}': {found} games")
            return result

    # Fallback: per-game content via gamePk
    print("  Schedule hydration returned no pitchers -- trying per-game lookup...")
    sched = mlb_get("/schedule",{"sportId":1,"date":date_str})
    if sched:
        game_pks = []
        for db in sched.get("dates",[]):
            for g in db.get("games",[]):
                pk  = g.get("gamePk")
                aid = g.get("teams",{}).get("away",{}).get("team",{}).get("id")
                hid = g.get("teams",{}).get("home",{}).get("team",{}).get("id")
                if pk and aid and hid:
                    game_pks.append((pk,aid,hid))
        for pk,aid,hid in game_pks:
            for hydrate in ["probablePitcher(note),team","probablePitcher,team"]:
                gmeta = mlb_get("/schedule",{"sportId":1,"gamePks":str(pk),"hydrate":hydrate})
                if gmeta:
                    for db in gmeta.get("dates",[]):
                        for gg in db.get("games",[]):
                            ap = gg.get("teams",{}).get("away",{}).get("probablePitcher")
                            hp = gg.get("teams",{}).get("home",{}).get("probablePitcher")
                            if ap or hp:
                                result[(aid,hid)] = {
                                    "away": ap.get("id") if ap else None,
                                    "home": hp.get("id") if hp else None,
                                }
                                print(f"    Pitcher via gamePk {pk}: {result[(aid,hid)]}")
                                break
                if (aid,hid) in result: break
            time.sleep(0.05)

    if not result:
        print(f"  WARNING: No probable pitchers for {date_str} -- not announced yet")
    return result


def build_matchup_data(odds_games, date_str):
    print("Fetching matchup data...")

    # Fetch probable pitchers using all available methods
    pitcher_lookup = fetch_probable_pitchers(date_str)
    # Also check tomorrow
    from datetime import datetime as _dt2, timedelta as _td2
    tomorrow_str = (_dt2.strptime(date_str,"%Y-%m-%d") + _td2(days=1)).strftime("%Y-%m-%d")
    tmw_pitchers = fetch_probable_pitchers(tomorrow_str)
    pitcher_lookup.update({k:v for k,v in tmw_pitchers.items() if k not in pitcher_lookup})

    # Fetch lineups separately
    mlb_sched = mlb_get("/schedule",{"sportId":1,"date":date_str,"hydrate":"lineups,team"})
    mlb_games = [] if not mlb_sched else [
        g for db in mlb_sched.get("dates",[]) for g in db.get("games",[])
    ]
    lineup_lookup = {}
    for g in mlb_games:
        aid = g.get("teams",{}).get("away",{}).get("team",{}).get("id")
        hid = g.get("teams",{}).get("home",{}).get("team",{}).get("id")
        if aid and hid: lineup_lookup[(aid,hid)] = g

    matchups = []
    for og in odds_games:
        away_name = og["away_team"]; home_name = og["home_team"]
        away_id = MLB_IDS.get(away_name); home_id = MLB_IDS.get(home_name)
        if not away_id or not home_id: continue

        # Get pitcher IDs from dedicated lookup
        game_pitchers = pitcher_lookup.get((away_id,home_id)) or {}
        # Handle reversed key (home/away swapped)
        if not game_pitchers:
            swapped = pitcher_lookup.get((home_id,away_id)) or {}
            if swapped:
                game_pitchers = {"away": swapped.get("home"), "home": swapped.get("away")}

        away_pitcher_id = game_pitchers.get("away")
        home_pitcher_id = game_pitchers.get("home")

        # Final fallback: per-gamePk direct lookup
        if not away_pitcher_id and not home_pitcher_id:
            mlb_g = lineup_lookup.get((away_id,home_id)) or lineup_lookup.get((home_id,away_id))
            if mlb_g:
                pk = mlb_g.get("gamePk")
                if pk:
                    for hydrate in ["probablePitcher(note),team","probablePitcher,team"]:
                        gmeta = mlb_get("/schedule", {
                            "sportId":1, "gamePks": str(pk),
                            "hydrate": hydrate
                        })
                        if gmeta:
                            for db in gmeta.get("dates",[]):
                                for gg in db.get("games",[]):
                                    ap = gg.get("teams",{}).get("away",{}).get("probablePitcher")
                                    hp = gg.get("teams",{}).get("home",{}).get("probablePitcher")
                                    if ap or hp:
                                        away_pitcher_id = ap.get("id") if ap else None
                                        home_pitcher_id = hp.get("id") if hp else None
                                        print(f"    Pitcher via gamePk {pk}: {away_pitcher_id}/{home_pitcher_id}")
                                        break
                        if away_pitcher_id or home_pitcher_id:
                            break

        away_pitcher = fetch_pitcher_stats(away_pitcher_id)
        home_pitcher = fetch_pitcher_stats(home_pitcher_id)

        # Get lineups from lineup_lookup
        mlb_game = lineup_lookup.get((away_id,home_id)) or lineup_lookup.get((home_id,away_id))
        lineups = mlb_game.get("lineups",{}) if mlb_game else {}
        def extract(raw):
            return [{"id":p["id"],"name":p.get("fullName",str(p["id"])),"pos":""} for p in raw if isinstance(p,dict) and "id" in p]
        alr = lineups.get("awayPlayers",[]); hlr = lineups.get("homePlayers",[])
        away_batters = extract(alr)[:9] if alr else fetch_roster(away_id)[:13]
        home_batters = extract(hlr)[:9] if hlr else fetch_roster(home_id)[:13]
        away_source = "lineup" if alr else "roster"
        home_source = "lineup" if hlr else "roster"

        def get_stats(batters, pitcher_id):
            if not pitcher_id: return []
            results = []
            for b in batters:
                s = fetch_batter_vs_pitcher(b["id"], pitcher_id)
                if s and s["ab"]>=3: results.append({**b,**s})
                time.sleep(0.05)
            results.sort(key=lambda x:-x["ab"])
            return results

        print(f"  {away_name} @ {home_name}: {away_pitcher['name']} vs {home_pitcher['name']}")
        away_vs_hp = get_stats(away_batters, home_pitcher.get("id"))
        home_vs_ap = get_stats(home_batters, away_pitcher.get("id"))
        away_last5 = fetch_last_five_record(away_id)
        home_last5 = fetch_last_five_record(home_id)

        # Fetch batter handedness for platoon adjustment (batch call)
        all_batter_ids = [b["id"] for b in away_batters + home_batters if b.get("id")]
        handedness_map = fetch_batters_handedness(all_batter_ids) if all_batter_ids else {}
        away_sides = [handedness_map.get(b["id"]) for b in away_batters if handedness_map.get(b["id"])]
        home_sides = [handedness_map.get(b["id"]) for b in home_batters if handedness_map.get(b["id"])]

        matchups.append({"game":f"{away_name} @ {home_name}",
                         "away":away_name,"home":home_name,
                         "away_pitcher":away_pitcher,"home_pitcher":home_pitcher,
                         "away_batters":away_vs_hp,"home_batters":home_vs_ap,
                         "away_source":away_source,"home_source":home_source,
                         "away_last5":away_last5,"home_last5":home_last5,
                         "away_batter_sides":away_sides,"home_batter_sides":home_sides})
    print(f"  Matchups ready: {len(matchups)} games")
    return matchups


# =============================================================
# ENHANCED GAME ANALYSIS
# =============================================================
def analyze_game(game, context):
    away = game["away_team"]; home = game["home_team"]
    books = game.get("bookmakers",[])

    book_data = []
    for b in books:
        if b.get("key","").lower() in EXCLUDED_BOOKS: continue
        h2h   = next((m for m in b.get("markets",[]) if m["key"]=="h2h"),None)
        total = next((m for m in b.get("markets",[]) if m["key"]=="totals"),None)
        if not h2h: continue
        ao = next((o for o in h2h["outcomes"] if o["name"]==away),None)
        ho = next((o for o in h2h["outcomes"] if o["name"]==home),None)
        if not ao or not ho: continue
        ov = next((o for o in (total or {}).get("outcomes",[]) if o["name"]=="Over"),None)
        uv = next((o for o in (total or {}).get("outcomes",[]) if o["name"]=="Under"),None)
        ap=ao["price"]; hp=ho["price"]
        ai=american_to_implied(ap); hi=american_to_implied(hp)
        at,ht=remove_vig(ai,hi)
        book_data.append({"name":b["title"],"away_price":ap,"home_price":hp,
                          "away_imp":round(ai*100,1) if ai else None,
                          "home_imp":round(hi*100,1) if hi else None,
                          "away_true":at,"home_true":ht,
                          "total_line":ov["point"] if ov else None,
                          "over_price":ov["price"] if ov else None,
                          "under_price":uv["price"] if uv else None})
    if not book_data: return None

    split_market = (any(b["away_price"]<0 for b in book_data) and
                    any(b["home_price"]<0 for b in book_data))

    def median(lst):
        s=sorted(lst); n=len(s)
        return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2

    away_med = median([b["away_price"] for b in book_data])
    home_med = median([b["home_price"] for b in book_data])

    def cents_off(p,ref):
        i1=american_to_implied(p); i2=american_to_implied(ref)
        return abs(i1-i2)*100 if i1 and i2 else 0

    for b in book_data:
        b["outlier_away"] = cents_off(b["away_price"],away_med)>15
        b["outlier_home"] = cents_off(b["home_price"],home_med)>15

    clean = [b for b in book_data if not b["outlier_away"] and not b["outlier_home"]] or book_data
    mkt_at = sum(b["away_true"] for b in clean if b["away_true"])/len(clean)
    mkt_ht = sum(b["home_true"] for b in clean if b["home_true"])/len(clean)

    # --- ADJUSTMENTS ---
    adj_at = mkt_at; adj_ht = mkt_ht; adjustments = []

    # 1. Starting pitcher ERA vs league avg
    ap_ctx = context.get("away_pitcher",{}); hp_ctx = context.get("home_pitcher",{})
    ap_q = ap_ctx.get("quality",0.0); hp_q = hp_ctx.get("quality",0.0)
    if abs(ap_q)>0.01:
        adj_at += ap_q*0.5; adj_ht -= ap_q*0.5
        adjustments.append((f"Away SP {ap_ctx.get('name','?')} ERA {ap_ctx.get('era','?')}",ap_q*0.5,-ap_q*0.5))
    if abs(hp_q)>0.01:
        adj_ht += hp_q*0.5; adj_at -= hp_q*0.5
        adjustments.append((f"Home SP {hp_ctx.get('name','?')} ERA {hp_ctx.get('era','?')}",-hp_q*0.5,hp_q*0.5))

    # 2. Bullpen fatigue
    away_bp = context.get("away_bullpen",{}); home_bp = context.get("home_bullpen",{})
    fat_diff = home_bp.get("fatigue",0) - away_bp.get("fatigue",0)
    if abs(fat_diff)>0.2:
        delta = fat_diff*0.04; adj_at += delta; adj_ht -= delta
        adjustments.append((f"Bullpen ({away_bp.get('label','?')} vs {home_bp.get('label','?')})",delta,-delta))

    # 3. Injuries -- key position players OUT
    def count_key_inj(injuries):
        return sum(1 for inj in injuries
                   if inj.get("pos","") not in ("SP","RP","P","TWP")
                   and "out" in inj.get("status","").lower())
    away_ki = count_key_inj(context.get("away_injuries",[]))
    home_ki = count_key_inj(context.get("home_injuries",[]))
    inj_diff = home_ki - away_ki
    if inj_diff!=0:
        delta = inj_diff*0.02; adj_at += delta; adj_ht -= delta
        if abs(delta)>0.01:
            adjustments.append((f"Injuries {away_ki} away / {home_ki} home OUT",delta,-delta))

    # 4. Platoon splits -- lineup handedness vs pitcher hand
    away_sides  = context.get("away_batter_sides",[])
    home_sides  = context.get("home_batter_sides",[])
    hp_hand     = context.get("home_pitcher",{}).get("pitch_hand","R")
    ap_hand     = context.get("away_pitcher",{}).get("pitch_hand","R")
    # Away batters face home pitcher
    away_plat = calc_platoon_adjustment(away_sides, hp_hand)
    # Home batters face away pitcher
    home_plat = calc_platoon_adjustment(home_sides, ap_hand)
    net_plat  = away_plat - home_plat   # positive = away team has platoon advantage
    if abs(net_plat) >= 0.01:
        adj_at += net_plat; adj_ht -= net_plat
        adjustments.append((f"Platoon splits (away {ap_hand} vs home {hp_hand})",net_plat,-net_plat))

    # 5a. Bounce-back spot -- team blownout 5+ runs yesterday
    away_l5 = context.get("away_last5") or {}
    home_l5 = context.get("home_last5") or {}
    if isinstance(away_l5, dict) and away_l5.get("bounce_back"):
        # Away team got blown out yesterday -- bounce-back edge
        adj_at += 0.025; adj_ht -= 0.025
        adjustments.append((f"{away} bounce-back spot (blowout yesterday)", 0.025, -0.025))
    if isinstance(home_l5, dict) and home_l5.get("bounce_back"):
        adj_ht += 0.025; adj_at -= 0.025
        adjustments.append((f"{home} bounce-back spot (blowout yesterday)", -0.025, 0.025))

    # 5b. Division dog -- underdog facing a division rival
    away_id_n = MLB_IDS.get(away); home_id_n = MLB_IDS.get(home)
    is_division_game = away_id_n and home_id_n and same_division(away_id_n, home_id_n)
    if is_division_game:
        away_is_dog = adj_at < adj_ht
        home_is_dog = adj_ht < adj_at
        # Division dogs get a +1.5% boost — familiarity levels the playing field
        if away_is_dog and away_med > 0:   # away is underdog (positive ML)
            adj_at += 0.015; adj_ht -= 0.015
            adjustments.append((f"Division dog: {away} familiar with {home}", 0.015, -0.015))
        elif home_is_dog and home_med > 0: # home is underdog
            adj_ht += 0.015; adj_at -= 0.015
            adjustments.append((f"Division dog: {home} familiar with {away}", -0.015, 0.015))

    # 5c. Key number flag
    key_number_flag = None
    try:
        bst_away_ml = min((b for b in book_data if b.get("away_price")),
                          key=lambda b: abs(b["away_price"]), default=None)
        bst_home_ml = min((b for b in book_data if b.get("home_price")),
                          key=lambda b: abs(b["home_price"]), default=None)
        if bst_away_ml and bst_away_ml.get("away_price"):
            ap_val = abs(bst_away_ml["away_price"])
            if 110 <= ap_val <= 125:
                key_number_flag = f"{away} ML in key zone ({'+' if bst_away_ml['away_price']>0 else ''}{bst_away_ml['away_price']})"
        if bst_home_ml and bst_home_ml.get("home_price") and not key_number_flag:
            hp_val = abs(bst_home_ml["home_price"])
            if 110 <= hp_val <= 125:
                key_number_flag = f"{home} ML in key zone ({'+' if bst_home_ml['home_price']>0 else ''}{bst_home_ml['home_price']})"
    except Exception:
        pass

    # 5. Line movement signal -- sharp money indicator
    line_movement = None
    opening_games = context.get("opening_lines",{})
    game_key      = context.get("game_key","")
    if opening_games and game_key:
        line_movement = calc_line_movement(game_key, opening_games, book_data)
        if line_movement and line_movement.get("significant"):
            # Significant line movement (10+ cents) = sharp money signal
            # Apply a small nudge toward the team the sharp money is on
            mt   = line_movement["moved_team"]
            mc   = line_movement["move_cents"]
            delta= min(abs(mc)*0.003, 0.03)  # max 3% nudge from line movement
            if mt=="away" and mc>0:
                adj_at+=delta; adj_ht-=delta
                adjustments.append((f"Sharp line move: {away} moved {abs(mc):.0f}c",delta,-delta))
            elif mt=="home" and mc>0:
                adj_ht+=delta; adj_at-=delta
                adjustments.append((f"Sharp line move: {home} moved {abs(mc):.0f}c",-delta,delta))

    # Renormalize to sum to 1.0
    t = adj_at + adj_ht
    if t>0: adj_at=adj_at/t; adj_ht=adj_ht/t
    away_fair = implied_to_american(adj_at); home_fair = implied_to_american(adj_ht)

    best_away  = max(book_data,key=lambda b:float(b["away_price"]))
    worst_away = min(book_data,key=lambda b:float(b["away_price"]))
    best_home  = max(book_data,key=lambda b:float(b["home_price"]))
    worst_home = min(book_data,key=lambda b:float(b["home_price"]))
    for b in book_data:
        b["best_away"] =b["name"]==best_away["name"]
        b["worst_away"]=b["name"]==worst_away["name"]
        b["best_home"] =b["name"]==best_home["name"]
        b["worst_home"]=b["name"]==worst_home["name"]

    away_gap = round(abs(american_to_implied(worst_away["away_price"])-american_to_implied(best_away["away_price"]))*100)
    home_gap = round(abs(american_to_implied(worst_home["home_price"])-american_to_implied(best_home["home_price"]))*100)

    if split_market:                  signal,signal_label="fire","SPLIT MARKET"
    elif away_gap>=18 or home_gap>=18: signal,signal_label="fire","DISCREPANCY"
    elif away_gap>=10 or home_gap>=10: signal,signal_label="value","SHOP"
    else:                              signal,signal_label="watch",""

    is_coin = abs(adj_at-adj_ht)<0.03

    def ml_cand(team,true_p,best_b,pk):
        bp=best_b[pk]; imp=american_to_implied(bp)
        edge=round((true_p-imp)*100,1)
        return {"type":"ML","play":f"{team} Moneyline","sub":f"{fmt(bp)} at {best_b['name']}",
                "best_price":fmt(bp),"true_pct":f"{round(true_p*100)}%",
                "fair_line":implied_to_american(true_p),
                "edge_val":edge,"edge_label":f"+{edge}%" if edge>0 else f"{edge}%"}

    def total_cands():
        results = []
        bwt = [b for b in book_data if b.get("total_line") and
               b.get("over_price") is not None and b.get("under_price") is not None]
        if not bwt: return results
        cons_line = sorted([b["total_line"] for b in bwt])[len(bwt)//2]
        filtered  = [b for b in bwt if b["total_line"]==cons_line]
        if not filtered: return results
        # Hook detection -- check if any book offers a better half-point
        hook_note = ""
        all_lines = sorted(set(b["total_line"] for b in bwt))
        if len(all_lines) > 1:
            # Multiple lines available -- flag the half-point difference
            best_line_for_over  = min(all_lines)
            best_line_for_under = max(all_lines)
            if cons_line != best_line_for_over:
                hook_note = f"🪝 Hook: Over {best_line_for_over} available at {[b['name'] for b in bwt if b['total_line']==best_line_for_over][0]}"
            elif cons_line != best_line_for_under:
                hook_note = f"🪝 Hook: Under {best_line_for_under} available at {[b['name'] for b in bwt if b['total_line']==best_line_for_under][0]}"

        # Key total numbers -- 8, 8.5, 9 are the most common final totals
        key_total_numbers = {7.5, 8.0, 8.5, 9.0, 9.5}
        is_key_total = cons_line in key_total_numbers
        op_list = [b["over_price"] for b in filtered]
        up_list = [b["under_price"] for b in filtered]
        med_ov  = sorted(op_list)[len(op_list)//2]
        med_un  = sorted(up_list)[len(up_list)//2]
        true_ov,true_un = remove_vig(american_to_implied(med_ov),american_to_implied(med_un))
        if not true_ov: return results

        # Park factor
        pf = PARK_FACTORS.get(home,1.0)
        adj_ov = min(0.85,max(0.15, true_ov + (pf-1.0)*0.15))
        adj_un = 1.0-adj_ov

        # Umpire run impact
        ri = context.get("umpire",{}).get("run_impact",0) or 0
        adj_ov = min(0.85,max(0.15, adj_ov + ri*0.01))
        adj_un = 1.0-adj_ov

        # Wind
        wx = context.get("weather",{})
        if not wx.get("roof"):
            wind_spd = int(wx.get("wind_speed","0") or 0)
            wind_effect = wx.get("wind_effect","")
            if wind_spd>=8:
                wind_adj = (wind_spd/20.0)*0.06
                if wind_effect=="blowing_out":   adj_ov=min(0.85,adj_ov+wind_adj)
                elif wind_effect=="blowing_in":  adj_ov=max(0.15,adj_ov-wind_adj)
                adj_un = 1.0-adj_ov

            # Temperature effect on fly ball distance / HR suppression
            # Every 10F below 70F reduces fly ball distance ~4ft, suppresses scoring
            try:
                temp_f = float(str(wx.get("temp","70") or "70"))
                if temp_f < 70:
                    temp_adj = ((70 - temp_f) / 10.0) * 0.004  # -0.4% per 10F below 70
                    temp_adj = min(temp_adj, 0.04)   # cap at -4%
                    adj_ov = max(0.15, adj_ov - temp_adj)
                    adj_un = 1.0 - adj_ov
                elif temp_f > 85:
                    # Hot games slightly favor scoring
                    temp_adj = ((temp_f - 85) / 10.0) * 0.002
                    adj_ov = min(0.85, adj_ov + temp_adj)
                    adj_un = 1.0 - adj_ov
            except Exception:
                pass

        best_ov_b  = max(filtered,key=lambda b:float(b["over_price"]))
        best_un_b  = max(filtered,key=lambda b:float(b["under_price"]))
        for side,tp,best_b,pk in [("Over",adj_ov,best_ov_b,"over_price"),
                                   ("Under",adj_un,best_un_b,"under_price")]:
            bp=best_b[pk]; imp=american_to_implied(bp)
            if imp is None: continue
            edge=round((tp-imp)*100,1)
            results.append({"type":"Total","play":f"{side} {cons_line} Runs",
                            "sub":f"{fmt(bp)} at {best_b['name']}",
                            "best_price":fmt(bp),"true_pct":f"{round(tp*100)}%",
                            "fair_line":implied_to_american(tp),
                            "edge_val":edge,"edge_label":f"+{edge}%" if edge>0 else f"{edge}%"})
        return results

    candidates = []
    if not is_coin:
        candidates.append(ml_cand(away,adj_at,best_away,"away_price"))
        candidates.append(ml_cand(home,adj_ht,best_home,"home_price"))
    candidates.extend(total_cands())

    if not candidates or is_coin:
        bet_play="No Play -- near coin flip"
        bet_sub="Teams too evenly matched at current prices"
        bet_edge="None"; bet_fair="N/A"; bet_true="N/A"; bet_is_pass=True
    else:
        best_c = max(candidates, key=lambda c: c["edge_val"])
        if best_c["edge_val"] < 0:
            # Best available candidate is overpriced -- genuine no play
            bet_play    = "No Play"
            bet_sub     = f"Best option ({best_c['play']}) is overpriced at current lines"
            bet_edge    = best_c["edge_label"]
            bet_fair    = best_c["fair_line"]
            bet_true    = best_c["true_pct"]
            bet_is_pass = True
        else:
            bet_play    = best_c["play"]
            bet_sub     = best_c["sub"]
            bet_edge    = best_c["edge_label"]
            bet_fair    = best_c["fair_line"]
            bet_true    = best_c["true_pct"]
            bet_is_pass = False

    discs = []
    for team,gap,best,worst,pk in [
        (away,away_gap,best_away,worst_away,"away_price"),
        (home,home_gap,best_home,worst_home,"home_price"),
    ]:
        if gap>=8:
            discs.append({"team":team,"best_price":fmt(best[pk]),"worst_price":fmt(worst[pk]),
                          "gap":gap,"best_book":best["name"],"worst_book":worst["name"]})

    value_play = None
    # Qualify for value tab if:
    #   1. Book discrepancy signal (fire/value/sharp), OR
    #   2. Best bet has a genuine +2.5% or better edge from model adjustments
    # Either way, must not be a pass and edge must be at least -1%
    # (discrepancy plays are still shown even with slight negative edge
    #  since the discrepancy itself is the signal, but hard cap at -1%)
    best_bet_edge_val = max((c["edge_val"] for c in candidates), default=0.0)

    # Qualify for value tab:
    # Any best bet with +1.5% or better edge shows on the value tab
    # regardless of signal type — edge is the primary filter
    qualifies = (not bet_is_pass) and (best_bet_edge_val >= 1.5)

    if qualifies and candidates:
        # Always use the actual best candidate — avoids ML/total mismatch
        best_c  = max(candidates, key=lambda c: c["edge_val"])
        vp      = best_c["best_price"]
        vb      = best_c["sub"].split(" at ")[-1] if " at " in best_c["sub"] else ""
        ve      = best_c["edge_val"]
        vtp_str = best_c["true_pct"].replace("%","")
        vtp     = float(vtp_str) if vtp_str.replace(".","").isdigit() else 0.0
        play_label = best_c["play"]

        # Implied% from the best price
        try:
            vi = round((american_to_implied(float(vp.replace("+",""))) or 0)*100, 1)
        except Exception:
            vi = 0.0

        # Team label — for totals use home team as the "team" field (just for display grouping)
        if best_c["type"] == "Total":
            vt = home
        else:
            # For ML picks figure out which side was picked from the play string
            vt = away if away in play_label else home

        # Build natural language narrative — 2-3 readable sentences
        def build_narrative():
            sentences = []
            is_total   = best_c["type"] == "Total"
            is_over    = "Over" in play_label
            pick_team  = None if is_total else vt
            opp_team   = home if pick_team == away else away

            # ── Sentence 1: The core edge case ──
            edge_desc = "strong" if ve >= 4 else ("solid" if ve >= 2.5 else "slight")
            if is_total:
                direction_word = "go over" if is_over else "stay under"
                s1 = (f"The model gives this game a {vtp}% chance to {direction_word} {play_label.split()[1]} runs, "
                      f"while the book is only pricing it at {vi}% — a {edge_desc} {ve}% edge at {vp}.")
            else:
                s1 = (f"The model gives {pick_team} a {vtp}% true win probability in this matchup, "
                      f"while the market is only pricing them at {vi}% — a {edge_desc} {ve}% edge available at {vp} on {vb}.")
            sentences.append(s1)

            # ── Sentence 2: The strongest supporting factor ──
            ap = context.get("away_pitcher",{}); hp = context.get("home_pitcher",{})
            wx = context.get("weather",{})
            abp = context.get("away_bullpen",{}); hbp = context.get("home_bullpen",{})
            lm  = context.get("line_movement")

            # Find the most compelling factor
            s2 = None

            # Pitcher quality
            if not is_total:
                fav_pitcher = ap if pick_team == away else hp
                opp_pitcher = hp if pick_team == away else ap
                if fav_pitcher.get("era","N/A") != "N/A":
                    try:
                        era = float(fav_pitcher["era"])
                        name = fav_pitcher.get("name","Their starter")
                        if era < 3.50:
                            s2 = (f"{name} has been one of the better arms in the league with a {era} ERA, "
                                  f"giving {pick_team} a meaningful pitching advantage in this spot.")
                        elif era < 4.00:
                            s2 = f"{name} has been solid this season at {era} ERA, providing a slight edge on the mound."
                    except Exception: pass
                if s2 is None and opp_pitcher.get("era","N/A") != "N/A":
                    try:
                        era = float(opp_pitcher["era"])
                        name = opp_pitcher.get("name","The opposing starter")
                        if era > 5.00:
                            s2 = (f"{name} has struggled this season with a {era} ERA, "
                                  f"making {pick_team} a particularly attractive play against this pitching matchup.")
                        elif era > 4.50:
                            s2 = (f"The opposing starter {name} has been below average at {era} ERA, "
                                  f"which works in {pick_team}'s favor tonight.")
                    except Exception: pass

            # Wind/weather for totals
            if s2 is None and is_total and not wx.get("roof"):
                wind_spd = int(wx.get("wind_speed","0") or 0)
                wind_eff = wx.get("wind_effect","")
                temp     = wx.get("temp","")
                if wind_spd >= 10 and wind_eff == "blowing_out" and is_over:
                    s2 = (f"Wind is blowing out at {wind_spd} mph at {wx.get('stadium','the park')} tonight, "
                          f"which historically inflates scoring and supports the Over.")
                elif wind_spd >= 10 and wind_eff == "blowing_in" and not is_over:
                    s2 = (f"Wind is blowing in hard at {wind_spd} mph, "
                          f"creating a pitcher-friendly environment that supports the Under.")
                elif temp and int(str(temp).split(".")[0]) < 55:
                    s2 = (f"Cold game time temperature ({temp}°F) suppresses fly ball distance and run scoring, "
                          f"adding weight to the Under.")

            # Bullpen fatigue
            if s2 is None:
                fav_bp  = abp if pick_team == away else hbp
                opp_bp  = hbp if pick_team == away else abp
                if opp_bp.get("fatigue",0) > 0.6 and not is_total:
                    s2 = (f"{opp_team}'s bullpen has been heavily used over the last three days ({opp_bp.get('ip','?')} IP), "
                          f"meaning if the game gets to the back end, {pick_team} could exploit a tired relief corps.")
                elif fav_bp.get("fatigue",0) < 0.1 and not is_total:
                    s2 = (f"{pick_team}'s bullpen is well-rested heading in, "
                          f"giving them a late-game advantage if needed.")

            # Platoon splits
            if s2 is None:
                for adj_label, adj_away, adj_home in adjustments:
                    if "platoon" in adj_label.lower() or "Platoon" in adj_label:
                        if not is_total:
                            s2 = (f"The lineup matchup favors {pick_team} tonight — "
                                  f"their batting order has a meaningful handedness advantage against this starter.")
                        break

            # Park factor for totals
            if s2 is None and is_total:
                pf = PARK_FACTORS.get(home, 1.0)
                if pf > 1.15 and is_over:
                    s2 = (f"This game is being played at a hitter-friendly park (factor {pf}), "
                          f"which historically produces above-average run totals.")
                elif pf < 0.90 and not is_over:
                    s2 = (f"This is one of the more pitcher-friendly parks in baseball (factor {pf}), "
                          f"which historically suppresses scoring and supports the Under.")

            if s2:
                sentences.append(s2)

            # ── Sentence 3: Market confirmation if applicable ──
            s3 = None
            if signal == "fire" and split_market:
                s3 = ("Sharp books and recreational books are pricing this game differently — "
                      "that kind of market split is one of the strongest signals a play can have.")
            elif signal in ("fire","value","sharp") and max(away_gap, home_gap) >= 15:
                gap = max(away_gap, home_gap)
                s3  = (f"There's a {gap}-cent price gap across books on this game, "
                       f"meaning you can get meaningfully better value by shopping — {vb} currently has the best number.")
            elif lm and lm.get("significant"):
                mt  = lm.get("moved_team","")
                mc  = abs(lm.get("move_cents",0))
                if mt.lower() in play_label.lower():
                    s3 = (f"The line has moved {mc:.0f} cents toward {mt} since this morning, "
                          f"suggesting sharp money has come in on the same side the model prefers.")
                else:
                    s3 = (f"Worth noting the line has moved {mc:.0f} cents against this side since open — "
                          f"the edge is there but the market is moving the other way.")

            if s3:
                sentences.append(s3)

            return " ".join(sentences)

        narrative = build_narrative()

        value_play = {
            "game":        f"{away} @ {home}",
            "signal":      signal,
            "team":        vt,
            "play_label":  play_label,
            "best_price":  vp,
            "best_book":   vb,
            "true_pct":    vtp,
            "implied_pct": vi,
            "edge":        ve,
            "reasoning":   narrative,
        }

    # ── BET UP TO ────────────────────────────────────────
    # The price where your edge hits exactly 0% = the fair line.
    # For favorites: maximum price you should accept (e.g. "bet up to -134")
    # For underdogs: minimum price you should accept (e.g. "only if +118 or better")
    # For totals: the fair O/U price at which edge = 0%
    bet_up_to = "N/A"
    bet_up_to_label = "Bet up to"
    if not bet_is_pass and candidates:
        best_c = max(candidates, key=lambda c: c["edge_val"])
        fair = best_c.get("fair_line", "N/A")
        if fair not in ("N/A", "—", None):
            bet_up_to = fair
            try:
                price_val = int(fair.replace("+",""))
                if price_val < 0:
                    bet_up_to_label = "Bet up to"
                else:
                    bet_up_to_label = "Only at"
            except Exception:
                pass

    try:
        t = datetime.fromisoformat(game.get("commence_time","").replace("Z","+00:00")).astimezone(EASTERN)
        time_display=t.strftime("%-I:%M %p ET"); date_et=t.strftime("%A, %B %d"); date_sort=t.strftime("%Y-%m-%d")
        commence_iso = game.get("commence_time","")
    except Exception:
        time_display=""; date_et="Today"; date_sort="9999-99-99"; commence_iso=""
    # Counts how many independent signals all point the same direction
    conf = 0; conf_reasons = []
    if best_bet_edge_val >= 2.5: conf += 1; conf_reasons.append(f"Edge +{round(best_bet_edge_val,1)}%")
    if best_bet_edge_val >= 5.0: conf += 1; conf_reasons.append("Strong edge 5%+")
    if signal in ("fire","value","sharp"): conf += 1; conf_reasons.append(signal.upper())
    if line_movement and line_movement.get("significant"):
        conf += 1; conf_reasons.append(f"Sharp move {abs(line_movement.get('move_cents',0)):.0f}c")
    if len([a for a in adjustments if a[1] > 0]) >= 2 or len([a for a in adjustments if a[1] < 0]) >= 2:
        conf += 1; conf_reasons.append(f"{len(adjustments)} factors stacking")
    confidence     = min(conf, 5)
    confidence_why = " · ".join(conf_reasons) if conf_reasons else "No strong signals"

    # ── KELLY CRITERION ───────────────────────────────────
    # Quarter-Kelly bet sizing: conservative standard for sports betting
    # Kelly % = (bp - q) / b  where b=decimal odds-1, p=true prob, q=1-p
    kelly_pct = None
    kelly_units = None
    if not bet_is_pass and candidates:
        best_c_k = max(candidates, key=lambda c: c["edge_val"])
        try:
            price_str = best_c_k["best_price"]
            price_val = float(price_str.replace("+",""))
            if price_val > 0:
                decimal_odds = price_val/100 + 1
            else:
                decimal_odds = 100/abs(price_val) + 1
            b = decimal_odds - 1
            # Use true probability from the best candidate
            tp_str = best_c_k["true_pct"].replace("%","")
            p = float(tp_str) / 100
            q = 1 - p
            full_kelly = (b*p - q) / b
            quarter_kelly = max(0, full_kelly / 4)
            kelly_pct   = round(quarter_kelly * 100, 1)
            kelly_units = round(quarter_kelly * 100, 1)   # units per 100 bankroll
        except Exception:
            pass

    return {
        "game":f"{away} @ {home}","game_id":game.get("id",""),
        "away":away,"home":home,"time":time_display,"date_et":date_et,"date_sort":date_sort,
        "signal":signal,"signal_label":signal_label,"split_market":split_market,
        "away_true":round(adj_at*100),"home_true":round(adj_ht*100),
        "mkt_away":round(mkt_at*100),"mkt_home":round(mkt_ht*100),
        "away_fair":away_fair,"home_fair":home_fair,"adjustments":adjustments,
        "book_data":book_data,"discrepancies":discs,"value_play":value_play,
        "bet_play":bet_play,"bet_sub":bet_sub,"bet_edge":bet_edge,
        "bet_fair":bet_fair,"bet_true":bet_true,"bet_is_pass":bet_is_pass,
        "bet_up_to":bet_up_to,"bet_up_to_label":bet_up_to_label,
        "best_away":best_away,"best_home":best_home,
        "worst_away":worst_away,"worst_home":worst_home,
        "away_gap":away_gap,"home_gap":home_gap,"props":[],
        "confidence":confidence,"confidence_why":confidence_why,"kelly_pct":kelly_pct,
        "key_number_flag":key_number_flag,
        "is_division_game":is_division_game,
        "commence_iso":commence_iso,
        "away_pitcher":context.get("away_pitcher",{}),
        "home_pitcher":context.get("home_pitcher",{}),
        "away_injuries":context.get("away_injuries",[]),
        "home_injuries":context.get("home_injuries",[]),
        "away_bullpen":context.get("away_bullpen",{}),
        "home_bullpen":context.get("home_bullpen",{}),
        "away_last5":context.get("away_last5"),
        "home_last5":context.get("home_last5"),
        "umpire":context.get("umpire",{}),
        "line_movement":line_movement,
    }

def fetch_game_context(game, matchup_data, weather_data, mlb_schedule_games, opening_lines):
    away=game["away_team"]; home=game["home_team"]
    away_id=MLB_IDS.get(away); home_id=MLB_IDS.get(home)
    m=next((x for x in matchup_data if x["game"]==f"{away} @ {home}"),{})
    mlb_gid=None
    for g in mlb_schedule_games:
        aid=g.get("teams",{}).get("away",{}).get("team",{}).get("id")
        hid=g.get("teams",{}).get("home",{}).get("team",{}).get("id")
        if aid==away_id and hid==home_id: mlb_gid=g.get("gamePk"); break

    game_key = f"{away} @ {home}"
    return {
        "away_pitcher":       m.get("away_pitcher",{}),
        "home_pitcher":       m.get("home_pitcher",{}),
        "away_injuries":      fetch_injuries(away_id),
        "home_injuries":      fetch_injuries(home_id),
        "away_bullpen":       fetch_bullpen_fatigue(away_id),
        "home_bullpen":       fetch_bullpen_fatigue(home_id),
        "umpire":             fetch_umpire(mlb_gid),
        "weather":            weather_data.get(home,{}),
        "away_batter_sides":  m.get("away_batter_sides",[]),
        "home_batter_sides":  m.get("home_batter_sides",[]),
        "opening_lines":      opening_lines,
        "game_key":           game_key,
        "away_last5":         m.get("away_last5"),
        "home_last5":         m.get("home_last5"),
    }


# =============================================================
# HTML BUILDER
# =============================================================
def build_why_this_bet(game):
    """Build structured checklist of factors for/against the best bet."""
    items = []
    ap = game.get("away_pitcher",{}); hp = game.get("home_pitcher",{})
    away = game.get("away",""); home = game.get("home","")
    bet_play = game.get("bet_play","")
    is_total = "Runs" in bet_play
    is_over  = "Over" in bet_play

    # SP quality + fatigue
    for pitcher, side in [(ap,"away"),(hp,"home")]:
        if pitcher.get("era","N/A") != "N/A":
            try:
                era=float(pitcher["era"]); name=pitcher.get("name","SP")
                dr=pitcher.get("days_rest"); pc=pitcher.get("last_pitch_count")
                own_team = away if side=="away" else home
                helps_bet = own_team in bet_play or (is_total and era < 3.50 and not is_over)
                if era < 3.50:
                    items.append((f"{name} ERA {era}", "for" if helps_bet else "against",
                                  "Elite pitcher -- well below 4.20 avg"))
                elif era > 5.00:
                    items.append((f"{name} ERA {era}", "against" if helps_bet else "for",
                                  "Struggling pitcher -- above 4.20 avg"))
                if dr is not None and dr<=3:
                    items.append((f"{name} short rest ({dr}d)", "against", "3-day rest penalty applied"))
                if pc and pc>=110:
                    items.append((f"{name} {pc} pitches last start", "against", "High pitch count fatigue"))
            except Exception: pass

    # Bullpen
    abp=game.get("away_bullpen",{}); hbp=game.get("home_bullpen",{})
    if abp.get("fatigue",0)>0.5:
        items.append((f"{away} bullpen ({abp.get('label','?')})",
                      "against" if away in bet_play else "for",
                      f"{abp.get('ip','?')} relief IP last 3 days"))
    if hbp.get("fatigue",0)>0.5:
        items.append((f"{home} bullpen ({hbp.get('label','?')})",
                      "against" if home in bet_play else "for",
                      f"{hbp.get('ip','?')} relief IP last 3 days"))

    # Discrepancy
    max_gap=max(game.get("away_gap",0),game.get("home_gap",0))
    if max_gap>=18: items.append((f"Book discrepancy {max_gap}c","for","Major price disagreement"))
    elif max_gap>=10: items.append((f"Book discrepancy {max_gap}c","for","Worth shopping books"))

    # Sharp line movement
    lm=game.get("line_movement")
    if lm and lm.get("significant"):
        mt=lm.get("moved_team",""); mc=abs(lm.get("move_cents",0))
        items.append((f"Sharp money: {mt} +{mc:.0f}c",
                      "for" if mt.lower() in bet_play.lower() else "against",
                      "10c+ move = professional money"))

    # Umpire
    ump=game.get("umpire",{}); ri=ump.get("run_impact",0) or 0
    if abs(ri)>=0.3 and is_total:
        ump_helps=(ri>0 and is_over) or (ri<0 and not is_over)
        items.append((f"Ump {ump.get('name','?')} ({ri:+.1f} runs)",
                      "for" if ump_helps else "against",
                      "Hitter-friendly" if ri>0 else "Pitcher-friendly zone"))

    # Injuries
    for inj in game.get("away_injuries",[])[:2]:
        if "out" in inj.get("status","").lower():
            items.append((f"{away} {inj['name'].split()[-1]} OUT",
                          "against" if away in bet_play else "for",
                          inj.get("pos","?")))
    for inj in game.get("home_injuries",[])[:2]:
        if "out" in inj.get("status","").lower():
            items.append((f"{home} {inj['name'].split()[-1]} OUT",
                          "against" if home in bet_play else "for",
                          inj.get("pos","?")))
    return items


def analyze_f5_nrfi(f5_games, matchups_by_game):
    """
    Analyze First 5 innings and NRFI/YRFI bets.
    Uses SP quality as the dominant factor since starters
    control all 5 innings — bullpen is largely irrelevant.
    Returns list of play dicts.
    """
    plays = []
    now_utc = datetime.now(timezone.utc)

    for g in f5_games:
        try:
            # Skip started games
            ct = g.get("commence_time","")
            if ct:
                start = datetime.fromisoformat(ct.replace("Z","+00:00"))
                if start <= now_utc:
                    continue

            away = g.get("away_team",""); home = g.get("home_team","")
            game_key = f"{away} @ {home}"
            m = matchups_by_game.get(game_key, {})
            ap = m.get("away_pitcher",{}); hp = m.get("home_pitcher",{})

            def sp_quality(pitcher):
                """Convert ERA to a probability adjustment. F5 weights SP 2x full-game."""
                try:
                    era = float(pitcher.get("era","4.20") or "4.20")
                    diff = 4.20 - era  # positive = better than avg
                    return max(-0.06, min(0.06, diff * 0.015))
                except Exception:
                    return 0.0

            away_sp_adj = sp_quality(ap)
            home_sp_adj = sp_quality(hp)

            # ── F5 MONEYLINE ─────────────────────────────
            f5_books = g.get("f5_books",[])
            if f5_books:
                away_mls = [b["f5_away_ml"] for b in f5_books if b.get("f5_away_ml")]
                home_mls = [b["f5_home_ml"] for b in f5_books if b.get("f5_home_ml")]
                if away_mls and home_mls:
                    med_a = sorted(away_mls)[len(away_mls)//2]
                    med_h = sorted(home_mls)[len(home_mls)//2]
                    imp_a = american_to_implied(med_a)
                    imp_h = american_to_implied(med_h)
                    true_a, true_h = remove_vig(imp_a, imp_h)
                    if true_a and true_h:
                        # Adjust for SP quality
                        adj_a = true_a + away_sp_adj - home_sp_adj
                        adj_h = true_h + home_sp_adj - away_sp_adj
                        # Renormalize
                        tot = adj_a + adj_h
                        adj_a /= tot; adj_h /= tot
                        # Find best price
                        best_away_b = max(f5_books, key=lambda b: b.get("f5_away_ml",  -999) or -999)
                        best_home_b = max(f5_books, key=lambda b: b.get("f5_home_ml",  -999) or -999)
                        # Edge calculation
                        for team, true_p, mkt_p, best_price, best_book_name in [
                            (away, adj_a, imp_a, best_away_b.get("f5_away_ml"), best_away_b["name"]),
                            (home, adj_h, imp_h, best_price_h := best_home_b.get("f5_home_ml"), best_home_b["name"]),
                        ]:
                            if best_price is None: continue
                            book_imp = american_to_implied(best_price)
                            if not book_imp: continue
                            edge = round((true_p - book_imp) * 100, 1)
                            if edge >= 1.5:
                                plays.append({
                                    "type":       "f5_ml",
                                    "game":       game_key,
                                    "away":       away,
                                    "home":       home,
                                    "play":       f"{team} F5 ML",
                                    "price":      f"+{best_price}" if best_price > 0 else str(best_price),
                                    "book":       best_book_name,
                                    "true_pct":   round(true_p * 100, 1),
                                    "implied_pct":round(book_imp * 100, 1),
                                    "edge":       edge,
                                    "away_sp":    ap.get("name","TBD"),
                                    "home_sp":    hp.get("name","TBD"),
                                    "away_era":   ap.get("era","N/A"),
                                    "home_era":   hp.get("era","N/A"),
                                    "signal":     "fire" if edge >= 4 else ("value" if edge >= 2.5 else "watch"),
                                })

            # ── F5 TOTALS ────────────────────────────────
            f5_overs  = [b for b in f5_books if b.get("f5_over_price") and b.get("f5_over_line")]
            if f5_overs:
                cons_line = sorted([b["f5_over_line"] for b in f5_overs])[len(f5_overs)//2]
                filtered  = [b for b in f5_overs if b["f5_over_line"] == cons_line]
                ov_prices = [b["f5_over_price"] for b in filtered]
                un_prices = [b["f5_under_price"] for b in filtered if b.get("f5_under_price")]
                if ov_prices and un_prices:
                    med_ov = sorted(ov_prices)[len(ov_prices)//2]
                    med_un = sorted(un_prices)[len(un_prices)//2]
                    true_ov, true_un = remove_vig(american_to_implied(med_ov), american_to_implied(med_un))
                    if true_ov:
                        # SP quality affects totals — better SPs = Under lean
                        total_sp_adj = -(away_sp_adj + home_sp_adj) * 0.5
                        adj_ov = true_ov + total_sp_adj
                        adj_un = true_un - total_sp_adj
                        tot = adj_ov + adj_un; adj_ov /= tot; adj_un /= tot
                        best_ov_b = max(filtered, key=lambda b: b.get("f5_over_price",-999))
                        best_un_b = max(filtered, key=lambda b: b.get("f5_under_price",-999))
                        for side, true_p, best_price, best_bk in [
                            ("Over",  adj_ov, best_ov_b.get("f5_over_price"),  best_ov_b["name"]),
                            ("Under", adj_un, best_un_b.get("f5_under_price"), best_un_b["name"]),
                        ]:
                            if best_price is None: continue
                            book_imp = american_to_implied(best_price)
                            if not book_imp: continue
                            edge = round((true_p - book_imp) * 100, 1)
                            if edge >= 1.5:
                                plays.append({
                                    "type":       "f5_total",
                                    "game":       game_key,
                                    "away":       away,
                                    "home":       home,
                                    "play":       f"F5 {side} {cons_line}",
                                    "price":      f"+{best_price}" if best_price > 0 else str(best_price),
                                    "book":       best_bk,
                                    "true_pct":   round(true_p * 100, 1),
                                    "implied_pct":round(book_imp * 100, 1),
                                    "edge":       edge,
                                    "away_sp":    ap.get("name","TBD"),
                                    "home_sp":    hp.get("name","TBD"),
                                    "away_era":   ap.get("era","N/A"),
                                    "home_era":   hp.get("era","N/A"),
                                    "signal":     "fire" if edge >= 4 else ("value" if edge >= 2.5 else "watch"),
                                })

            # ── NRFI / YRFI ──────────────────────────────
            nrfi_books = g.get("nrfi_books",[])
            if nrfi_books:
                nrfi_prices = [b.get("nrfi_price") for b in nrfi_books if b.get("nrfi_price")]
                yrfi_prices = [b.get("yrfi_price") for b in nrfi_books if b.get("yrfi_price")]
                if nrfi_prices and yrfi_prices:
                    med_nrfi = sorted(nrfi_prices)[len(nrfi_prices)//2]
                    med_yrfi = sorted(yrfi_prices)[len(yrfi_prices)//2]
                    true_nrfi, true_yrfi = remove_vig(
                        american_to_implied(med_nrfi), american_to_implied(med_yrfi))
                    if true_nrfi:
                        # Both SPs being good = lean NRFI
                        # Both SPs bad = lean YRFI
                        nrfi_adj = (away_sp_adj + home_sp_adj) * 0.8
                        adj_nrfi = min(0.85, max(0.15, true_nrfi + nrfi_adj))
                        adj_yrfi = 1 - adj_nrfi
                        best_nrfi_b = max(nrfi_books, key=lambda b: b.get("nrfi_price",-999) or -999)
                        best_yrfi_b = max(nrfi_books, key=lambda b: b.get("yrfi_price",-999) or -999)
                        for bet_name, true_p, best_price, best_bk in [
                            ("NRFI", adj_nrfi, best_nrfi_b.get("nrfi_price"), best_nrfi_b["name"]),
                            ("YRFI", adj_yrfi, best_yrfi_b.get("yrfi_price"), best_yrfi_b["name"]),
                        ]:
                            if best_price is None: continue
                            book_imp = american_to_implied(best_price)
                            if not book_imp: continue
                            edge = round((true_p - book_imp) * 100, 1)
                            if edge >= 1.5:
                                plays.append({
                                    "type":       "nrfi",
                                    "game":       game_key,
                                    "away":       away,
                                    "home":       home,
                                    "play":       bet_name,
                                    "price":      f"+{best_price}" if best_price > 0 else str(best_price),
                                    "book":       best_bk,
                                    "true_pct":   round(true_p * 100, 1),
                                    "implied_pct":round(book_imp * 100, 1),
                                    "edge":       edge,
                                    "away_sp":    ap.get("name","TBD"),
                                    "home_sp":    hp.get("name","TBD"),
                                    "away_era":   ap.get("era","N/A"),
                                    "home_era":   hp.get("era","N/A"),
                                    "signal":     "fire" if edge >= 4 else ("value" if edge >= 2.5 else "watch"),
                                })
        except Exception as e:
            print(f"  F5/NRFI analyze error for {g.get('away_team','?')} @ {g.get('home_team','?')}: {e}")

    plays.sort(key=lambda x: -x.get("edge",0))
    return plays
    """Build structured checklist of factors for/against the best bet."""
    items = []
    ap = game.get("away_pitcher",{}); hp = game.get("home_pitcher",{})
    away = game.get("away",""); home = game.get("home","")
    bet_play = game.get("bet_play","")
    is_total = "Runs" in bet_play
    is_over  = "Over" in bet_play

    # SP quality + fatigue -- always show ERA even if average
    for pitcher, side in [(ap,"away"),(hp,"home")]:
        name = pitcher.get("name","TBD")
        if name == "TBD": continue
        era_raw = pitcher.get("era","N/A")
        dr  = pitcher.get("days_rest")
        pc  = pitcher.get("last_pitch_count")
        own_team = away if side=="away" else home
        try:
            era = float(era_raw)
            if era < 3.50:
                helps = own_team in bet_play or (is_total and not is_over)
                items.append((f"{name} ERA {era:.2f}", "for" if helps else "against",
                              f"Elite -- {era:.2f} vs 4.20 league avg"))
            elif era < 4.20:
                helps = own_team in bet_play or (is_total and not is_over)
                items.append((f"{name} ERA {era:.2f}", "for" if helps else "neutral",
                              f"Above avg -- {era:.2f} vs 4.20 league avg"))
            elif era < 5.00:
                helps = own_team not in bet_play and not (is_total and not is_over)
                items.append((f"{name} ERA {era:.2f}", "against" if own_team in bet_play else "neutral",
                              f"Below avg -- {era:.2f} vs 4.20 league avg"))
            else:
                items.append((f"{name} ERA {era:.2f}", "against" if own_team in bet_play else "for",
                              "Struggling -- above 5.00"))
            if dr is not None and dr <= 3:
                items.append((f"{name}: {dr}d rest", "against", "Short rest penalty"))
            elif dr is not None and dr >= 7:
                items.append((f"{name}: {dr}d rest", "for", "Extra rest boost"))
            if pc and pc >= 110:
                items.append((f"{name}: {pc}p last start", "against", "High pitch count"))
            elif pc and pc <= 80:
                items.append((f"{name}: {pc}p last start", "for", "Fresh arm last outing"))
        except Exception:
            if era_raw != "N/A":
                items.append((f"{name} ERA {era_raw}", "neutral", "vs 4.20 league avg"))

    # Bullpen -- show regardless of fatigue level
    abp=game.get("away_bullpen",{}); hbp=game.get("home_bullpen",{})
    for bp, team, side in [(abp,away,"away"),(hbp,home,"home")]:
        label = bp.get("label","?"); ip = bp.get("ip",0)
        fatigue = bp.get("fatigue",0)
        direction = "against" if (fatigue > 0.4 and team in bet_play) else \
                    "for"     if (fatigue > 0.4 and team not in bet_play) else \
                    "for"     if (fatigue < 0.1 and team in bet_play) else "neutral"
        items.append((f"{team} bullpen: {label}", direction, f"{ip} relief IP last 3d"))

    # Discrepancy
    max_gap = max(game.get("away_gap",0), game.get("home_gap",0))
    if max_gap >= 18:
        items.append((f"Book gap: {max_gap}c", "for", "Major discrepancy — shop books"))
    elif max_gap >= 10:
        items.append((f"Book gap: {max_gap}c", "for", "Worth shopping for better price"))
    else:
        items.append((f"Book gap: {max_gap}c", "neutral", "Books in agreement"))

    # Model edge
    edge_str = game.get("bet_edge","")
    try:
        edge_val = float(str(edge_str).replace("+","").replace("%",""))
        if edge_val >= 5:
            items.append((f"Model edge: {edge_str}", "for", "Strong edge vs book price"))
        elif edge_val >= 2.5:
            items.append((f"Model edge: {edge_str}", "for", "Solid positive edge"))
        elif edge_val > 0:
            items.append((f"Model edge: {edge_str}", "neutral", "Marginal edge"))
        else:
            items.append((f"Model edge: {edge_str}", "against", "Slim/no edge at this price"))
    except Exception:
        pass

    # Sharp line movement
    lm = game.get("line_movement")
    if lm:
        mt = lm.get("moved_team",""); mc = abs(lm.get("move_cents",0))
        if lm.get("significant"):
            items.append((f"Sharp move: {mt} +{mc:.0f}c",
                          "for" if mt.lower() in bet_play.lower() else "against",
                          "Professional money signal"))
        elif mc >= 5:
            items.append((f"Line move: {mt} +{mc:.0f}c", "neutral", "Minor movement"))
    else:
        items.append(("No line movement", "neutral", "Line stable since open"))

    # Umpire
    ump = game.get("umpire",{}); ri = ump.get("run_impact",0) or 0
    if ump.get("name") and ump["name"] != "TBD":
        if is_total:
            ump_helps = (ri > 0 and is_over) or (ri < 0 and not is_over)
            items.append((f"Ump {ump.get('name','?').split()[-1]} ({ri:+.1f} runs)",
                          "for" if ump_helps else ("against" if abs(ri)>0.2 else "neutral"),
                          "Hitter zone" if ri>0.2 else ("Pitcher zone" if ri<-0.2 else "Neutral zone")))

    # Injuries
    for inj in game.get("away_injuries",[])[:2]:
        if "out" in inj.get("status","").lower():
            items.append((f"{away}: {inj.get('name','?').split()[-1]} OUT",
                          "against" if away in bet_play else "for",
                          inj.get("pos","?")))
    for inj in game.get("home_injuries",[])[:2]:
        if "out" in inj.get("status","").lower():
            items.append((f"{home}: {inj.get('name','?').split()[-1]} OUT",
                          "against" if home in bet_play else "for",
                          inj.get("pos","?")))

    return items


def build_html(analyzed_games, matchups, weather, results_data, tracking_games, all_noon_data, public_betting, pending_picks, f5_plays, date_str, time_str):
    all_disc=[]; all_plays=[]; sharp_ct=0; value_ct=0
    for g in analyzed_games:
        for d in g["discrepancies"]: all_disc.append({**d,"game":g["game"]})
        if g["value_play"]: all_plays.append(g["value_play"])
        if g["signal"]=="fire": sharp_ct+=1
    # Use actual ET date for today/tomorrow separation — don't rely on first game
    _today_et_str = datetime.now(EASTERN).strftime("%A, %B %d")
    today_date_val = _today_et_str
    date_lookup_sort = {g["game"]: g.get("date_et","Today") for g in analyzed_games}
    all_plays.sort(key=lambda x: (
        0 if date_lookup_sort.get(x.get("game",""),"") in (_today_et_str,"Today") else 1,
        -(x.get("edge") or 0)
    ))
    value_ct = len(all_plays)
    all_disc.sort(key=lambda x:-(x.get("gap",0)))
    sig_cls={"fire":"b-fire","sharp":"b-sharp","value":"b-value","watch":"b-watch","pass":"b-pass"}
    alert_cls={"fire":"fire","sharp":"sharp","value":"value","watch":"watch"}
    total=len(analyzed_games)
    books=max((len(g["book_data"]) for g in analyzed_games),default=0)

    def alert_cards():
        if not all_plays: return '<p style="color:var(--muted);font-size:13px;padding:1rem 0">No sharp alerts today.</p>'
        date_lookup = {g["game"]: g.get("date_et","Today") for g in analyzed_games}
        time_lookup = {g["game"]: g.get("time","") for g in analyzed_games}
        today_d = datetime.now(EASTERN).strftime("%A, %B %d")
        today_plays    = [p for p in all_plays if date_lookup.get(p.get("game",""),"") in (today_d,"Today")]
        tomorrow_plays = [p for p in all_plays if date_lookup.get(p.get("game",""),"") not in (today_d,"Today")]
        html = ""

        def render_card(p):
            sig=p["signal"]; ec="green" if (p.get("edge") or 0)>0 else "red"
            ap=p["best_price"]; ab=p["best_book"]
            at_str=str(p.get("true_pct","?")) + ("%" if "%" not in str(p.get("true_pct","?")) else "")
            ai_str=str(p.get("implied_pct","?")) + ("%" if "%" not in str(p.get("implied_pct","?")) else "")
            play_lbl=p.get("play_label",p.get("team","") + " ML")
            game_time = time_lookup.get(p.get("game",""),"")
            return (f'<div class="alert-card {alert_cls.get(sig,"value")}">'
                    f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">'
                    f'<span class="badge {sig_cls.get(sig,"b-value")}">{sig.upper()}</span>'
                    f'<span style="font-size:10px;color:var(--muted);font-family:monospace">{game_time}</span>'
                    f'</div>'
                    f'<div class="alert-game">{p["game"]}</div>'
                    f'<div class="alert-rec">{play_lbl} -- {ap} @ {ab}</div>'
                    f'<div class="alert-stats">'
                    f'<div class="stat-box"><div class="sl">Best Price</div><div class="sv">{ap}</div></div>'
                    f'<div class="stat-box"><div class="sl">Adj True%</div><div class="sv">{at_str}</div></div>'
                    f'<div class="stat-box"><div class="sl">Implied%</div><div class="sv {ec}">{ai_str}</div></div>'
                    f'</div>'
                    f'<div class="alert-reasoning">{p.get("reasoning","")}</div>'
                    f'</div>')

        if today_plays:
            html += '<div class="alert-grid">'
            for p in today_plays[:6]:
                html += render_card(p)
            html += "</div>"
        elif not tomorrow_plays:
            return '<p style="color:var(--muted);font-size:13px;padding:1rem 0">No sharp alerts today.</p>'

        if tomorrow_plays:
            html += (f'<div class="sec-header" style="margin-top:1.5rem">'
                     f'<h2>Tomorrow\'s Best Plays</h2><div class="sec-line"></div></div>'
                     f'<div class="alert-grid">')
            for p in tomorrow_plays[:6]:
                html += render_card(p)
            html += "</div>"
        return html

    def parlay_legs_html(plays):
        if not plays:
            return '<div style="color:var(--muted);font-size:13px">No value plays available today to add as legs.</div>'

        # Build date lookup from analyzed_games
        date_lookup = {g["game"]: g.get("date_et","Today") for g in analyzed_games}
        time_lookup = {g["game"]: g.get("time","") for g in analyzed_games}

        # Group plays by date
        from collections import OrderedDict
        grouped = OrderedDict()
        for p in plays[:12]:
            game_date = date_lookup.get(p.get("game",""), "Today")
            grouped.setdefault(game_date, []).append(p)

        rows = ""
        for date_lbl, date_plays in grouped.items():
            rows += (f'<div style="font-size:10px;font-family:monospace;text-transform:uppercase;'
                     f'letter-spacing:1.5px;color:var(--accent);padding:8px 4px 4px;'
                     f'font-weight:700">{date_lbl}</div>')
            for p in date_plays:
                play  = p.get("play_label", p.get("team","") + " ML")
                price = p.get("best_price","?")
                tp    = p.get("true_pct",0)
                game  = p.get("game","")
                edge  = p.get("edge",0)
                gtime = time_lookup.get(game,"")
                ec    = "var(--green)" if edge>0 else "var(--muted)"
                rows += (f'<div style="display:flex;align-items:center;gap:10px;background:var(--bg2);'
                         f'border:1px solid var(--border);border-radius:8px;padding:8px 12px">'
                         f'<div style="flex:1">'
                         f'<div style="font-size:13px;font-weight:700;color:var(--text)">{play}</div>'
                         f'<div style="font-size:11px;color:var(--muted)">{game}</div>'
                         f'<div style="font-size:10px;color:var(--dim);font-family:monospace">{gtime}</div>'
                         f'</div>'
                         f'<span style="font-family:monospace;color:var(--accent)">{price}</span>'
                         f'<span style="font-family:monospace;font-size:11px;color:{ec}">'
                         f'{("+" if edge>0 else "")}{edge}%</span>'
                         f'<button onclick="addParlayLeg(\'{game.replace(chr(39),"")}\',\'{play.replace(chr(39),"")}\',\'{price}\',\'{tp}\')" '
                         f'style="background:var(--green-bg);border:1px solid var(--green-border);color:var(--green);'
                         f'border-radius:4px;padding:3px 10px;cursor:pointer;font-size:12px;font-weight:700">+</button>'
                         f'</div>')
        return rows

    def best_bet_of_day():
        if not all_plays:
            return ""

        # Build game date/time lookup from analyzed_games
        date_lookup = {g["game"]: g.get("date_et","Today") for g in analyzed_games}
        time_lookup = {g["game"]: g.get("time","") for g in analyzed_games}
        today_date  = datetime.now(EASTERN).strftime("%A, %B %d")

        # Only consider today's games with positive edge
        positive = [
            p for p in all_plays
            if (p.get("edge") or 0) > 0
            and date_lookup.get(p.get("game",""), "") in (today_date,"Today")
        ]
        # If no today plays, fall back to any positive-edge play but note it
        if not positive:
            positive = [p for p in all_plays if (p.get("edge") or 0) > 0]
        if not positive:
            return ""

        best    = positive[0]  # already sorted by edge descending
        sig     = best.get("signal","watch")
        sig_col = {"fire":"var(--red)","sharp":"var(--blue)","value":"var(--green)","watch":"var(--amber)"}.get(sig,"var(--amber)")
        play    = best.get("play_label", best.get("team","") + " ML")
        price   = best.get("best_price","?")
        book    = best.get("best_book","?")
        edge    = best.get("edge",0)
        tp      = best.get("true_pct",0)
        ip      = best.get("implied_pct",0)
        reason  = best.get("reasoning","")
        game    = best.get("game","")
        gtime   = time_lookup.get(game,"")
        gdate   = date_lookup.get(game, today_date)
        is_tomorrow = gdate != today_date

        tomorrow_note = ""
        if is_tomorrow:
            tomorrow_note = (f'<div style="font-size:10px;background:var(--amber-bg);border:1px solid var(--amber-border);'
                             f'border-radius:4px;padding:3px 10px;color:var(--amber);font-family:monospace;'
                             f'display:inline-block;margin-bottom:8px">TOMORROW\'S GAME</div>')

        return (
            f'<div style="background:linear-gradient(135deg,rgba(163,230,53,0.08),rgba(163,230,53,0.02));'
            f'border:2px solid rgba(163,230,53,0.3);border-radius:16px;padding:1.5rem;margin-bottom:2rem;position:relative;overflow:hidden">'
            f'<div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,{sig_col},var(--accent))"></div>'
            f'<div style="font-size:10px;font-family:monospace;text-transform:uppercase;letter-spacing:2px;color:var(--accent);margin-bottom:6px">Best Bet of the Day</div>'
            f'{tomorrow_note}'
            f'<div style="font-size:14px;color:var(--muted);margin-bottom:4px;font-family:monospace">'
            f'{game} &nbsp;·&nbsp; {gdate}{(" · " + gtime) if gtime else ""}</div>'
            f'<div style="font-size:22px;font-weight:700;color:#fff;margin-bottom:4px">{play}</div>'
            f'<div style="font-size:15px;color:var(--accent);font-family:monospace;margin-bottom:12px">{price} at {book}</div>'
            f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px">'
            f'<div style="background:rgba(0,0,0,0.3);border-radius:6px;padding:6px 12px;text-align:center">'
            f'<div style="font-size:10px;color:var(--muted)">EDGE</div>'
            f'<div style="font-family:monospace;font-size:18px;font-weight:700;color:var(--green)">+{edge}%</div></div>'
            f'<div style="background:rgba(0,0,0,0.3);border-radius:6px;padding:6px 12px;text-align:center">'
            f'<div style="font-size:10px;color:var(--muted)">TRUE PROB</div>'
            f'<div style="font-family:monospace;font-size:18px;font-weight:700;color:var(--text)">{tp}%</div></div>'
            f'<div style="background:rgba(0,0,0,0.3);border-radius:6px;padding:6px 12px;text-align:center">'
            f'<div style="font-size:10px;color:var(--muted)">IMPLIED</div>'
            f'<div style="font-family:monospace;font-size:18px;font-weight:700;color:var(--muted)">{ip}%</div></div>'
            f'</div>'
            f'<div style="font-size:12px;color:#888;line-height:1.6">{reason}</div>'
            f'</div>'
        )
        top = all_plays[:6]  # sorted by edge, all passed 1.5% threshold
        if not top: return '<p style="color:var(--muted);font-size:13px;padding:1rem 0">No sharp alerts today.</p>'
        html='<div class="alert-grid">'
        for p in top:
            sig=p["signal"]; ec="green" if (p.get("edge") or 0)>0 else "red"
            ap=p["best_price"]; ab=p["best_book"]; at=p.get("true_pct","?"); ai=p.get("implied_pct","?")
            html+=(f'<div class="alert-card {alert_cls.get(sig,"value")}">'
                   f'<span class="badge {sig_cls.get(sig,"b-value")}">{sig.upper()}</span>'
                   f'<div class="alert-game">{p["game"]}</div>'
                   f'<div class="alert-rec">{p.get("play_label", p["team"] + " ML")} -- {ap} @ {ab}</div>'
                   f'<div class="alert-stats">'
                   f'<div class="stat-box"><div class="sl">Best Price</div><div class="sv">{ap}</div></div>'
                   f'<div class="stat-box"><div class="sl">Adj True%</div><div class="sv">{at}%</div></div>'
                   f'<div class="stat-box"><div class="sl">Implied%</div><div class="sv {ec}">{ai}%</div></div>'
                   f'</div>'
                   f'<div class="alert-reasoning">{p["reasoning"]}</div>'
                   f'</div>')
        html+="</div>"; return html

    def plays_table():
        if not all_plays: return "<p style='color:var(--muted);font-size:13px;padding:1rem 0'>No value plays today.</p>"
        date_lookup = {g["game"]: g.get("date_et","Today") for g in analyzed_games}
        time_lookup = {g["game"]: g.get("time","") for g in analyzed_games}

        # Group by date
        from collections import OrderedDict
        grouped = OrderedDict()
        for p in all_plays:
            d = date_lookup.get(p.get("game",""),"Today")
            grouped.setdefault(d,[]).append(p)

        rows=""
        for date_lbl, plays in grouped.items():
            # Date separator row
            rows+=(f'<tr><td colspan="9" style="background:var(--bg3);padding:6px 12px;'
                   f'font-family:monospace;font-size:10px;font-weight:700;text-transform:uppercase;'
                   f'letter-spacing:1.5px;color:var(--accent)">{date_lbl}</td></tr>')
            for p in plays:
                ec="c-green" if (p.get("edge") or 0)>0 else "c-red"
                gtime = time_lookup.get(p.get("game",""),"")
                rows+=(f'<tr>'
                       f'<td style="font-size:10px;color:var(--muted);font-family:monospace;white-space:nowrap">{gtime}</td>'
                       f'<td>{p["game"]}</td>'
                       f'<td class="mono">{p.get("play_label", p["team"] + " ML")}</td>'
                       f'<td><span class="pill pill-n">{p["best_price"]}</span></td>'
                       f'<td class="c-accent mono" style="font-size:11px">{p["best_book"]}</td>'
                       f'<td class="mono">{p["implied_pct"]}%</td>'
                       f'<td class="mono">{p["true_pct"]}%</td>'
                       f'<td class="mono {ec}">{("+" if (p.get("edge") or 0)>0 else "")}{p.get("edge","N/A")}%</td>'
                       f'<td><span class="badge {sig_cls.get(p["signal"],"b-watch")}" style="margin:0">{p["signal"].upper()}</span></td>'
                       f'</tr>')
        return (f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:1.75rem">'
                f'<table class="dtable"><thead><tr><th>Time</th><th>Game</th><th>Play</th><th>Best Line</th><th>Best Book</th>'
                f'<th>Implied%</th><th>Adj True%</th><th>Edge</th><th>Signal</th></tr></thead>'
                f'<tbody>{rows}</tbody></table></div>')

    def disc_table():
        if not all_disc: return "<p style='color:var(--muted);font-size:13px;padding:1rem 0'>No major discrepancies today.</p>"
        rows=""
        for d in all_disc[:14]:
            gap=d.get("gap",0); gc="c-red" if gap>=18 else ("c-amber" if gap>=10 else "")
            rows+=(f'<tr><td>{d["game"]}</td><td>{d["team"]}</td>'
                   f'<td><span class="pill pill-g">{d["best_price"]}</span></td>'
                   f'<td><span class="pill pill-r">{d["worst_price"]}</span></td>'
                   f'<td class="mono {gc}">{gap}c</td>'
                   f'<td class="mono c-accent" style="font-size:11px">{d["best_book"]}</td>'
                   f'<td class="mono c-red" style="font-size:11px">{d["worst_book"]}</td></tr>')
        return (f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden">'
                f'<table class="dtable"><thead><tr><th>Game</th><th>Team</th><th>Best Price</th><th>Worst Price</th>'
                f'<th>Gap</th><th>Best Book</th><th>Worst Book</th></tr></thead>'
                f'<tbody>{rows}</tbody></table></div>')

    def render_l5(record, team):
        if not record or not record.get("games"):
            return f'<div style="font-size:11px;color:var(--muted)">{team}: unavailable</div>'
        w=record["wins"]; l=record["losses"]
        wl_col="var(--green)" if w>l else ("var(--red)" if l>w else "var(--amber)")
        dots=""
        for r in record["games"]:
            loc="vs" if r["home"] else "@"; tip=f'{loc} {r["opp"]} {r["my_runs"]}-{r["op_runs"]}'
            col="var(--green)" if r["won"] else "var(--red)"; lbl="W" if r["won"] else "L"
            dots+=(f'<span title="{tip}" style="display:inline-flex;align-items:center;justify-content:center;'
                   f'width:22px;height:22px;border-radius:50%;background:{col};color:#000;font-size:10px;'
                   f'font-weight:700;font-family:monospace;cursor:default;flex-shrink:0">{lbl}</span>')
        return (f'<div style="display:flex;align-items:center;gap:8px">'
                f'<span style="font-size:11px;color:var(--muted);font-family:monospace;min-width:90px;white-space:nowrap">{team[:14]}:</span>'
                f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:14px;font-weight:700;color:{wl_col};min-width:32px">{w}-{l}</span>'
                f'<div style="display:flex;gap:3px">{dots}</div></div>')

    def game_blocks():
        opening_lines = all_noon_data  # will be replaced by actual opening lines if available
        try:
            if os.path.exists("opening_lines.json"):
                with open("opening_lines.json") as f:
                    ol = json.load(f)
                if ol.get("date","") == date_str[:10]:
                    opening_lines = ol.get("games",{})
        except Exception:
            pass
        mlookup={m["game"]:m for m in matchups}
        html=""
        for i,g in enumerate(analyzed_games):
            sig=g["signal"]; bc=sig_cls.get(sig,"b-watch")
            open_cls="open" if i<2 else ""
            sig_badge=(f'<span class="badge {bc}" style="font-size:9px">{g["signal_label"]}</span>'
                       if g["signal_label"] else "")
            # Confidence meter (filled/empty stars)
            conf = g.get("confidence",0)
            conf_why = g.get("confidence_why","")
            tooltip_text = f"{conf}/5: {conf_why}" if conf_why else f"Confidence: {conf}/5"
            conf_stars = "".join(
                f'<span style="color:{"var(--accent)" if ci<conf else "var(--border2)"}">●</span>'
                for ci in range(5)
            )
            conf_badge = (f'<span class="conf-tooltip-wrap" style="position:relative;cursor:help">'
                          f'<span style="font-size:10px;letter-spacing:1px;font-family:monospace">{conf_stars}</span>'
                          f'<span class="conf-tooltip">{tooltip_text}</span>'
                          f'</span>')
            # Countdown timer uses commence_iso stored on each game
            commence_iso = g.get("commence_iso","")
            countdown_id = f'cd_{g["game"].replace(" ","_").replace("@","at")[:20]}'
            countdown_html = (f'<span id="{countdown_id}" data-commence="{commence_iso}" '
                              f'style="font-size:10px;color:var(--muted);font-family:monospace;margin-left:6px"></span>'
                              if commence_iso else "")
            away_fav="fav" if g["away_true"]>g["home_true"] else ""
            home_fav="fav" if g["home_true"]>g["away_true"] else ""
            at = g["away_true"]; ht = g["home_true"]
            away_bar_w = at; home_bar_w = ht
            away_bar_col = "var(--accent)" if g["away_true"]>g["home_true"] else "var(--muted)"
            home_bar_col = "var(--accent)" if g["home_true"]>g["away_true"] else "var(--muted)"
            day_header=""
            if i==0 or g["date_et"]!=analyzed_games[i-1]["date_et"]:
                day_header=f'<div class="day-header"><span class="day-label">{g["date_et"]}</span></div>'

            md=mlookup.get(g["game"],{})
            away_l5=md.get("away_last5"); home_l5=md.get("home_last5")
            last5_section=""
            if away_l5 or home_l5:
                last5_section=(f'<div style="background:var(--bg3);border:1px solid var(--border);border-radius:8px;'
                               f'padding:10px 14px;margin-top:12px;display:flex;flex-direction:column;gap:7px">'
                               f'<div style="font-size:10px;font-family:monospace;text-transform:uppercase;'
                               f'letter-spacing:1px;color:var(--muted);margin-bottom:2px">Last 5 Games</div>'
                               f'{render_l5(away_l5,g["away"])}'
                               f'{render_l5(home_l5,g["home"])}'
                               f'</div>')

            adj_pills=""
            for adj in g.get("adjustments",[]):
                col="var(--green)" if adj[1]>0 else "var(--red)"
                adj_pills+=(f'<span style="font-size:10px;background:var(--bg3);border:1px solid var(--border2);'
                            f'border-radius:4px;padding:2px 7px;color:{col};font-family:monospace">{adj[0]}</span>')
            adj_row=f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px">{adj_pills}</div>' if adj_pills else ""

            inj_html=""
            for inj in g.get("away_injuries",[])[:2]:
                inj_html+=(f'<span style="font-size:10px;background:var(--red-bg);border:1px solid var(--red-border);'
                           f'border-radius:4px;padding:2px 7px;color:var(--red);font-family:monospace">'
                           f'WARNING {g["away"][:8]}: {inj["name"].split()[-1]} {inj["pos"]} {inj["status"]}</span>')
            for inj in g.get("home_injuries",[])[:2]:
                inj_html+=(f'<span style="font-size:10px;background:var(--red-bg);border:1px solid var(--red-border);'
                           f'border-radius:4px;padding:2px 7px;color:var(--red);font-family:monospace">'
                           f'WARNING {g["home"][:8]}: {inj["name"].split()[-1]} {inj["pos"]} {inj["status"]}</span>')
            inj_row=f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:6px">{inj_html}</div>' if inj_html else ""

            ap=g.get("away_pitcher",{}); hp=g.get("home_pitcher",{})
            abp=g.get("away_bullpen",{}); hbp=g.get("home_bullpen",{})
            ump=g.get("umpire",{})
            pitcher_strip=""
            if ap.get("name") and ap["name"]!="TBD":
                pitcher_strip=(f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;font-size:11px">'
                               f'<div style="background:var(--bg3);border-radius:6px;padding:7px 10px">'
                               f'<div style="color:var(--muted);margin-bottom:2px;font-family:monospace;font-size:10px;text-transform:uppercase">Away SP</div>'
                               f'<div style="font-weight:700;color:var(--text)">{ap.get("name","N/A")}</div>'
                               f'<div style="color:var(--muted)">ERA {ap.get("era","N/A")} - WHIP {ap.get("whip","N/A")} - K/9 {ap.get("k9","N/A")} - BP: {abp.get("label","?")}</div>'
                               f'</div>'
                               f'<div style="background:var(--bg3);border-radius:6px;padding:7px 10px">'
                               f'<div style="color:var(--muted);margin-bottom:2px;font-family:monospace;font-size:10px;text-transform:uppercase">Home SP</div>'
                               f'<div style="font-weight:700;color:var(--text)">{hp.get("name","N/A")}</div>'
                               f'<div style="color:var(--muted)">ERA {hp.get("era","N/A")} - WHIP {hp.get("whip","N/A")} - K/9 {hp.get("k9","N/A")} - BP: {hbp.get("label","?")}</div>'
                               f'</div></div>')
            ump_strip=""
            if ump.get("name") and ump["name"]!="TBD":
                ri=ump.get("run_impact",0) or 0
                ri_col="var(--red)" if ri>0.2 else ("var(--green)" if ri<-0.2 else "var(--muted)")
                ri_lbl=f"+{ri}" if ri>0 else str(ri)
                ump_strip=(f'<div style="font-size:11px;color:var(--muted);margin-top:6px;font-family:monospace">'
                           f'HP Ump: <span style="color:var(--text)">{ump["name"]}</span> '
                           f'- Run impact: <span style="color:{ri_col}">{ri_lbl}</span></div>')

            # Define lm once — used by both pub_strip and lm_strip
            lm = g.get("line_movement")
            lm_strip = ""

            # Public betting indicator
            pb_data = match_public_betting(g["game"], public_betting, g["away"], g["home"])
            pub_strip = ""
            if pb_data:
                ab = pb_data.get("away_bets",50); hb = pb_data.get("home_bets",50)
                am = pb_data.get("away_money"); hm = pb_data.get("home_money")
                # Reverse line movement detection (lm already defined above)
                rlm_note = ""
                if lm and abs(lm.get("move_cents",0)) >= 8:
                    moved_away = lm.get("moved_team","") == "away"
                    public_away = ab > hb
                    if moved_away != public_away:
                        rlm_note = '<span style="color:var(--red);font-weight:700;margin-left:8px">⚡ REVERSE LINE MOVEMENT</span>'
                # Bar widths
                away_w = ab; home_w = hb
                away_col = "#4ade80" if ab < 45 else ("#f87171" if ab > 65 else "#fbbf24")
                home_col = "#4ade80" if hb < 45 else ("#f87171" if hb > 65 else "#fbbf24")
                money_row = ""
                if am is not None and hm is not None:
                    money_row = (f'<div style="display:flex;align-items:center;gap:6px;margin-top:4px">'
                                 f'<span style="font-size:10px;color:var(--muted);width:60px">Money:</span>'
                                 f'<div style="flex:1;height:3px;background:var(--border2);border-radius:2px">'
                                 f'<div style="height:3px;width:{am}%;background:#60a5fa;border-radius:2px"></div></div>'
                                 f'<span style="font-size:10px;font-family:monospace;color:#60a5fa">{am}%</span>'
                                 f'<span style="font-size:10px;color:var(--muted)">vs</span>'
                                 f'<span style="font-size:10px;font-family:monospace;color:#60a5fa">{hm}%</span>'
                                 f'</div>')
                pub_strip = (
                    f'<div style="margin-top:6px;padding:8px 10px;background:var(--bg3);border-radius:6px">'
                    f'<div style="font-size:10px;font-family:monospace;text-transform:uppercase;'
                    f'letter-spacing:1px;color:var(--muted);margin-bottom:6px">Public Betting{rlm_note}</div>'
                    f'<div style="display:flex;align-items:center;gap:6px">'
                    f'<span style="font-size:11px;color:var(--muted);width:60px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{g["away"][:12]}</span>'
                    f'<div style="flex:1;height:6px;background:var(--border2);border-radius:3px">'
                    f'<div style="height:6px;width:{away_w}%;background:{away_col};border-radius:3px"></div></div>'
                    f'<span style="font-size:11px;font-family:monospace;font-weight:700;color:{away_col};width:32px;text-align:right">{ab}%</span>'
                    f'<span style="font-size:10px;color:var(--muted)">vs</span>'
                    f'<span style="font-size:11px;font-family:monospace;font-weight:700;color:{home_col};width:32px">{hb}%</span>'
                    f'<div style="flex:1;height:6px;background:var(--border2);border-radius:3px">'
                    f'<div style="height:6px;width:{home_w}%;background:{home_col};border-radius:3px;float:right"></div></div>'
                    f'<span style="font-size:11px;color:var(--muted);width:60px;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{g["home"][:12]}</span>'
                    f'</div>'
                    f'{money_row}'
                    f'</div>'
                )
            if lm:
                mc   = lm.get("move_cents",0)
                mt   = lm.get("moved_team","")
                team = g["away"] if mt=="away" else g["home"]
                sig  = lm.get("significant",False)
                col  = "var(--red)" if sig else "var(--amber)"
                icon = "🔥" if sig else "📈"
                oa   = fmt(lm.get("open_away",0)); oh = fmt(lm.get("open_home",0))
                direction = "toward" if mc>0 else "away from"
                sharp_badge = '<span style="color:var(--red);margin-left:8px;font-weight:700"> SHARP SIGNAL</span>' if sig else ""
                lm_strip = (
                    f'<div style="font-size:11px;margin-top:6px;padding:6px 10px;'
                    f'background:var(--bg3);border-radius:6px;border-left:3px solid {col};font-family:monospace">'
                    f'<span style="color:{col};font-weight:700">{icon} Line moved {abs(mc):.0f}c {direction} {team}</span>'
                    f'<span style="color:var(--muted);margin-left:10px">Open: {g["away"][:8]} {oa} / {g["home"][:8]} {oh}</span>'
                    f'{sharp_badge}'
                    f'</div>'
                )

            mkt_at=g.get("mkt_away",g["away_true"]); mkt_ht=g.get("mkt_home",g["home_true"])
            adj_note=""
            if abs(g["away_true"]-mkt_at)>=1 or abs(g["home_true"]-mkt_ht)>=1:
                adj_note=(f'<div style="font-size:10px;color:var(--muted);margin-top:5px;font-family:monospace">'
                          f'Market: {g["away"][:10]} {mkt_at}% / {g["home"][:10]} {mkt_ht}% '
                          f'After adjustments: {g["away_true"]}% / {g["home_true"]}%</div>')

            book_rows=""
            for b in g["book_data"]:
                def pc(price,is_best,is_worst,is_out):
                    fp=fmt(price)
                    if is_best:  return f'<td class="pb">{fp} *</td>'
                    if is_worst: return f'<td class="pw">{fp} x</td>'
                    if is_out:   return f'<td class="po">{fp} !</td>'
                    return f'<td class="pc">{fp}</td>'
                if b.get("total_line") and b.get("over_price") is not None:
                    ops=fmt(b["over_price"])
                    total_str=(f'<span style="color:var(--muted)">O/U</span> '
                               f'<strong style="color:var(--text)">{b["total_line"]}</strong> '
                               f'<span style="color:var(--accent)">{ops}</span>')
                else:
                    total_str='<span style="color:var(--dim)">N/A</span>'
                book_rows+=(f'<tr><td class="book">{b["name"]}</td>'
                            f'{pc(b["away_price"],b.get("best_away"),b.get("worst_away"),b.get("outlier_away"))}'
                            f'<td class="prob">{b["away_imp"]}%</td>'
                            f'{pc(b["home_price"],b.get("best_home"),b.get("worst_home"),b.get("outlier_home"))}'
                            f'<td class="prob">{b["home_imp"]}%</td>'
                            f'<td class="prob">{total_str}</td></tr>')

            bb_cls="best-bet pass" if g["bet_is_pass"] else "best-bet"
            up_to      = g.get("bet_up_to","N/A")
            up_to_lbl  = g.get("bet_up_to_label","Bet up to")
            kelly      = g.get("kelly_pct")
            up_to_note = ""
            if not g["bet_is_pass"] and up_to not in ("N/A","—"):
                kelly_str = f"{kelly}% of bankroll" if kelly and kelly>0 else "N/A"
                up_to_note = (
                    f'<div style="margin-top:9px;padding:8px 12px;background:rgba(0,0,0,0.25);'
                    f'border-radius:6px;display:grid;grid-template-columns:1fr 1fr;gap:8px">'
                    f'<div>'
                    f'<div style="font-size:10px;color:var(--muted);font-family:monospace;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px">{up_to_lbl}</div>'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:20px;font-weight:700;color:var(--amber)">{up_to}</div>'
                    f'<div style="font-size:10px;color:var(--muted)">{"Worse = overpaying" if "-" in str(up_to) else "Better = value"}</div>'
                    f'</div>'
                    f'<div>'
                    f'<div style="font-size:10px;color:var(--muted);font-family:monospace;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px">Kelly Bet Size</div>'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:20px;font-weight:700;color:var(--blue)">{kelly_str}</div>'
                    f'<div style="font-size:10px;color:var(--muted)">Quarter-Kelly (conservative)</div>'
                    f'</div>'
                    f'</div>'
                )
            # Why This Bet checklist
            why_items = build_why_this_bet(g) if not g["bet_is_pass"] else []
            why_html = ""
            if why_items:
                rows_html = ""
                for label, direction, detail in why_items:
                    icon = "✓" if direction=="for" else ("✗" if direction=="against" else "·")
                    col  = "var(--green)" if direction=="for" else ("var(--red)" if direction=="against" else "var(--muted)")
                    rows_html += (f'<div style="display:flex;align-items:baseline;gap:8px;padding:3px 0">'
                                  f'<span style="font-size:13px;font-weight:700;color:{col};flex-shrink:0;width:16px">{icon}</span>'
                                  f'<span style="font-size:12px;color:var(--text);font-weight:600">{label}</span>'
                                  f'<span style="font-size:11px;color:var(--muted);margin-left:auto;white-space:nowrap;padding-left:8px">{detail}</span>'
                                  f'</div>')
                why_html = (f'<div style="margin-top:9px;background:rgba(0,0,0,0.2);border-radius:6px;padding:10px 12px">'
                            f'<div style="font-size:10px;font-family:monospace;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px">Why This Bet</div>'
                            f'{rows_html}</div>')

            # Opening line toggle (from opening_lines.json)
            opening_games = all_noon_data  # proxy — opening lines stored separately
            open_toggle = ""
            if opening_lines and g.get("game") in {k for k in opening_lines}:
                og_data  = opening_lines.get(g["game"],{})
                og_books = og_data.get("books",{})
                if og_books:
                    og_prices = [(bname, bdata.get("away_price"), bdata.get("home_price"))
                                 for bname, bdata in og_books.items()
                                 if bdata.get("away_price") and bdata.get("home_price")]
                    if og_prices:
                        open_rows = "".join(
                            f'<tr><td class="book">{bn}</td>'
                            f'<td class="pc">{fmt(ap) if ap else "N/A"}</td>'
                            f'<td class="pc">{fmt(hp) if hp else "N/A"}</td></tr>'
                            for bn,ap,hp in og_prices[:5]
                        )
                        open_toggle = (
                            f'<details style="margin-top:8px">'
                            f'<summary style="font-size:11px;color:var(--muted);cursor:pointer;font-family:monospace;'
                            f'text-transform:uppercase;letter-spacing:1px;padding:4px 0">▶ Opening Lines (9am)</summary>'
                            f'<table class="otable" style="margin-top:6px">'
                            f'<thead><tr><th>Book</th><th>{g["away"]}</th><th>{g["home"]}</th></tr></thead>'
                            f'<tbody>{open_rows}</tbody></table>'
                            f'</details>'
                        )

            # Situational angles strip
            sit_strip = ""
            try:
                sit_parts = []
                if isinstance(g.get("away_last5"),dict) and g["away_last5"].get("bounce_back"):
                    sit_parts.append(f'<span style="color:var(--green)">🔄 {g["away"]} bounce-back spot</span>')
                if isinstance(g.get("home_last5"),dict) and g["home_last5"].get("bounce_back"):
                    sit_parts.append(f'<span style="color:var(--green)">🔄 {g["home"]} bounce-back spot</span>')
                if g.get("is_division_game"):
                    sit_parts.append(f'<span style="color:#60a5fa">⚔️ Division rivalry</span>')
                if g.get("key_number_flag"):
                    sit_parts.append(f'<span style="color:var(--amber)">🎯 {g["key_number_flag"]}</span>')
                if sit_parts:
                    sit_strip = (
                        f'<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;'
                        f'padding:6px 10px;background:var(--bg3);border-radius:6px;font-size:11px;'
                        f'font-family:monospace">'
                        + " · ".join(sit_parts) +
                        f'</div>'
                    )
            except Exception:
                sit_strip = ""

            best_bet=(f'<div class="{bb_cls}">'
                      f'<div class="bb-header">Best Bet This Game</div>'
                      f'<div class="bb-play">{g["bet_play"]}</div>'
                      f'<div class="bb-sub">{g["bet_sub"]}</div>'
                      f'<div class="bb-stats">'
                      f'<div class="bbs"><div class="bbs-label">Adj True%</div><div class="bbs-val">{g.get("bet_true","N/A")}</div></div>'
                      f'<div class="bbs"><div class="bbs-label">Fair Line</div><div class="bbs-val">{g.get("bet_fair","N/A")}</div></div>'
                      f'<div class="bbs"><div class="bbs-label">Away/Home</div><div class="bbs-val">{g["away_true"]}%/{g["home_true"]}%</div></div>'
                      f'<div class="bbs"><div class="bbs-label">Edge</div>'
                      f'<div class="bbs-val {"green" if not g["bet_is_pass"] else "c-muted"}">{g["bet_edge"]}</div></div>'
                      f'</div>'
                      f'{up_to_note}'
                      f'{why_html}'
                      f'</div>')

            html+=(day_header+
                   f'<div class="game-block {open_cls}" onclick="toggleGame(this)">'
                   f'<div class="game-header">'
                   f'<div><div class="game-teams">{g["away"]} @ {g["home"]}</div>'
                   f'<div class="game-time">{g["time"]}{countdown_html}</div></div>'
                   f'<div class="game-right">{conf_badge}{sig_badge}<span class="toggle">v</span></div>'
                   f'</div>'
                   f'<div class="game-body">'
                   f'{pitcher_strip}{ump_strip}{lm_strip}{pub_strip}{sit_strip}{inj_row}{adj_row}{adj_note}'
                   f'<table class="otable" style="margin-top:10px">'
                   f'<thead><tr><th>Book</th><th>{g["away"]}</th><th>Implied%</th>'
                   f'<th>{g["home"]}</th><th>Implied%</th><th>Total O/U</th></tr></thead>'
                   f'<tbody>{book_rows}</tbody></table>'
                   f'<div class="claude-box">'
                   f'<div class="cb-header">Adjusted True Odds</div>'
                   f'<div class="cb-grid">'
                   f'<div class="cb-team"><div class="cb-name">{g["away"]}</div>'
                   f'<div class="cb-pct {away_fav}">{g["away_true"]}%</div>'
                   f'<div style="height:4px;background:var(--border2);border-radius:2px;margin:4px 0">'
                   f'<div style="height:4px;width:{away_bar_w}%;background:{away_bar_col};border-radius:2px"></div></div>'
                   f'<div class="cb-line">Fair: {g["away_fair"]}</div></div>'
                   f'<div class="cb-vs">vs</div>'
                   f'<div class="cb-team"><div class="cb-name">{g["home"]}</div>'
                   f'<div class="cb-pct {home_fav}">{g["home_true"]}%</div>'
                   f'<div style="height:4px;background:var(--border2);border-radius:2px;margin:4px 0">'
                   f'<div style="height:4px;width:{home_bar_w}%;background:{home_bar_col};border-radius:2px"></div></div>'
                   f'<div class="cb-line">Fair: {g["home_fair"]}</div></div>'
                   f'</div>'
                   f'<div class="cb-method">Adjusted for: SP ERA/WHIP, bullpen fatigue, injuries, park factor, umpire zone, wind.</div>'
                   f'</div>'
                   f'{last5_section}'
                   f'{open_toggle}'
                   f'{best_bet}'
                   f'</div></div>')
        return html

    def tracking_cards():
        """Locked cards for games already started today — shown for tracking until midnight."""
        if not tracking_games:
            return ""

        # Fetch live scores for in-progress games
        live_scores = {}
        mlb_today = mlb_get("/schedule",{"sportId":1,"date":datetime.now(EASTERN).strftime("%Y-%m-%d"),"hydrate":"linescore,team"})
        if mlb_today:
            for db in mlb_today.get("dates",[]):
                for g in db.get("games",[]):
                    state = g.get("status",{}).get("abstractGameState","")
                    teams = g.get("teams",{})
                    away_name = teams.get("away",{}).get("team",{}).get("name","")
                    home_name = teams.get("home",{}).get("team",{}).get("name","")
                    away_score= teams.get("away",{}).get("score")
                    home_score= teams.get("home",{}).get("score")
                    inning    = g.get("linescore",{}).get("currentInning")
                    inn_half  = g.get("linescore",{}).get("inningHalf","")
                    key = f"{away_name} @ {home_name}"
                    if away_score is not None and home_score is not None:
                        live_scores[key] = {
                            "away_score": away_score,
                            "home_score": home_score,
                            "inning":     inning,
                            "inn_half":   inn_half,
                            "final":      state == "Final",
                        }

        noon_picks = all_noon_data
        html = '<div class="day-header"><span class="day-label" style="color:var(--muted)">In Progress / Completed Today</span></div>'

        for g in tracking_games:
            away = g["away_team"]; home = g["home_team"]
            game_key = f"{away} @ {home}"
            try:
                start = datetime.fromisoformat(g["commence_time"].replace("Z","+00:00")).astimezone(EASTERN)
                time_display = start.strftime("%-I:%M %p ET")
            except Exception:
                time_display = ""

            # Live score
            score_data = live_scores.get(game_key,{})
            if score_data:
                as_ = score_data.get("away_score","?"); hs_ = score_data.get("home_score","?")
                inn = score_data.get("inning",""); ih = score_data.get("inn_half","")
                if score_data.get("final"):
                    score_html = (f'<div style="background:var(--bg3);border-radius:8px;padding:10px 14px;'
                                  f'margin-top:10px;text-align:center">'
                                  f'<div style="font-size:10px;color:var(--muted);font-family:monospace;margin-bottom:4px">FINAL</div>'
                                  f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:22px;font-weight:700;color:#fff">'
                                  f'{away} {as_} &nbsp;·&nbsp; {hs_} {home}</div></div>')
                else:
                    inn_str = f"{ih[:3] if ih else ''} {inn}".strip() if inn else "In Progress"
                    score_html = (f'<div style="background:linear-gradient(135deg,rgba(74,222,128,0.06),rgba(74,222,128,0.01));'
                                  f'border:1px solid rgba(74,222,128,0.2);border-radius:8px;padding:10px 14px;margin-top:10px;text-align:center">'
                                  f'<div style="display:flex;align-items:center;justify-content:center;gap:6px;margin-bottom:3px">'
                                  f'<span class="live-dot"></span>'
                                  f'<span style="font-size:10px;color:var(--green);font-family:monospace;text-transform:uppercase;letter-spacing:1px">Live &middot; {inn_str}</span>'
                                  f'</div><div style="font-family:\'IBM Plex Mono\',monospace;font-size:22px;font-weight:700;color:#fff">'
                                  f'{away} {as_} &nbsp;·&nbsp; {hs_} {home}</div></div>')
            else:
                score_html = ""

            pick = noon_picks.get(game_key)

            if pick:
                is_pass = pick.get("is_pass", False)
                play    = pick.get("play","")
                price   = pick.get("price","")
                book    = pick.get("book","")
                edge    = pick.get("edge","")
                sig_lbl = pick.get("signal_label","")

                if is_pass or not play or "Pass" in play or "coin flip" in play.lower():
                    # Model had no play for this game
                    bet_box = (
                        f'<div style="background:var(--bg3);border:1px solid var(--border);'
                        f'border-radius:8px;padding:10px 14px;margin-top:10px">'
                        f'<div style="font-size:10px;font-family:monospace;text-transform:uppercase;'
                        f'letter-spacing:1px;color:var(--muted);margin-bottom:5px">Noon Assessment</div>'
                        f'<div style="font-size:14px;font-weight:700;color:var(--muted)">No Play</div>'
                        f'<div style="font-size:12px;color:var(--dim);margin-top:3px">'
                        f'Model did not find sufficient edge for this game at pre-game lines.</div>'
                        f'</div>'
                    )
                else:
                    edge_col = "var(--green)" if str(edge).startswith("+") else "var(--amber)"
                    sig_html = f'<span style="font-size:10px;color:var(--muted)"> · {sig_lbl}</span>' if sig_lbl else ""
                    bet_box = (
                        f'<div style="background:rgba(163,230,53,0.04);border:1px solid rgba(163,230,53,0.18);'
                        f'border-radius:8px;padding:10px 14px;margin-top:10px">'
                        f'<div style="font-size:10px;font-family:monospace;text-transform:uppercase;'
                        f'letter-spacing:1px;color:var(--accent);margin-bottom:6px">Noon Best Bet{sig_html}</div>'
                        f'<div style="font-size:16px;font-weight:700;color:#fff;margin-bottom:3px">{play}</div>'
                        f'<div style="font-size:13px;color:var(--accent);font-family:monospace;margin-bottom:8px">'
                        f'{price} at {book}</div>'
                        f'<div style="display:flex;gap:10px">'
                        f'<div style="background:rgba(0,0,0,0.3);border-radius:6px;padding:5px 10px">'
                        f'<div style="font-size:10px;color:var(--muted);margin-bottom:2px">EDGE</div>'
                        f'<div style="font-family:monospace;font-size:13px;font-weight:700;color:{edge_col}">{edge}</div>'
                        f'</div>'
                        f'<div style="background:rgba(0,0,0,0.3);border-radius:6px;padding:5px 10px">'
                        f'<div style="font-size:10px;color:var(--muted);margin-bottom:2px">TRUE ODDS</div>'
                        f'<div style="font-family:monospace;font-size:13px;font-weight:700;color:var(--text)">'
                        f'{pick.get("away_true","?")}% / {pick.get("home_true","?")}%</div>'
                        f'</div>'
                        f'<div style="background:rgba(0,0,0,0.3);border-radius:6px;padding:5px 10px">'
                        f'<div style="font-size:10px;color:var(--muted);margin-bottom:2px">FAIR LINE</div>'
                        f'<div style="font-family:monospace;font-size:13px;font-weight:700;color:var(--text)">'
                        f'{pick.get("away_fair","?")} / {pick.get("home_fair","?")}</div>'
                        f'</div>'
                        f'</div>'
                        f'</div>'
                    )
            else:
                bet_box = (
                    f'<div style="background:var(--bg3);border:1px solid var(--border);'
                    f'border-radius:8px;padding:10px 14px;margin-top:10px">'
                    f'<div style="font-size:12px;color:var(--muted)">Pre-game analysis not available for this game.</div>'
                    f'</div>'
                )

            html += (
                f'<div class="game-block" onclick="toggleGame(this)">'
                f'<div class="game-header" style="opacity:0.8">'
                f'<div><div class="game-teams">{away} @ {home}</div>'
                f'<div class="game-time">{time_display}</div></div>'
                f'<div class="game-right">'
                f'<span class="badge b-pass" style="font-size:9px">IN PROGRESS</span>'
                f'<span class="toggle">v</span></div>'
                f'</div>'
                f'<div class="game-body">{score_html}{bet_box}</div>'
                f'</div>'
            )
        return html

    def matchup_page():
        if not matchups:
            return '<p style="color:var(--muted);font-size:13px;padding:2rem 0;text-align:center">Matchup data unavailable -- probable pitchers may not be announced yet.</p>'
        def avg_color(avg_str):
            try:
                v=float(avg_str)
                if v>=0.300: return "#f87171"
                if v>=0.250: return "#fbbf24"
                return "#4ade80"
            except Exception: return "var(--text)"
        def bar(avg_str):
            try:
                v=float(avg_str); pct=min(int(v*333),100)
                return f'<div style="height:3px;background:var(--border);border-radius:2px;margin-top:3px"><div style="height:3px;width:{pct}%;background:{avg_color(avg_str)};border-radius:2px"></div></div>'
            except Exception: return ""
        def batter_table(batters,pitcher,batting_team,source):
            if not batters:
                sn="Official lineup" if source=="lineup" else "Roster (lineup not posted)"
                return f'<p style="color:var(--muted);font-size:12px;padding:8px 0">{sn} -- no batters with 3+ AB vs {pitcher["name"]}.</p>'
            sn="Official lineup" if source=="lineup" else "Roster (lineup not yet posted)"
            rows=""
            for b in batters:
                ac=avg_color(b["avg"])
                rows+=(f'<tr><td class="book">{b["name"]}</td>'
                       f'<td class="mono" style="color:var(--muted)">{b.get("pos","")}</td>'
                       f'<td class="mono">{b["ab"]}</td><td class="mono">{b["h"]}</td>'
                       f'<td class="mono">{b["hr"]}</td><td class="mono">{b["k"]}</td>'
                       f'<td><span class="mono" style="color:{ac};font-weight:700">{b["avg"]}</span>'
                       f'<span style="color:var(--muted);font-size:11px"> ({b["h"]}/{b["ab"]})</span>'
                       f'{bar(b["avg"])}</td></tr>')
            return (f'<div style="font-size:10px;color:var(--muted);margin-bottom:6px;font-family:monospace">{sn}</div>'
                    f'<table class="dtable"><thead><tr><th>Batter</th><th>Pos</th><th>AB</th>'
                    f'<th>H</th><th>HR</th><th>K</th><th>Career BA</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table>')
        # Build date lookup from analyzed_games
        date_lookup = {g["game"]: g.get("date_et","Today") for g in analyzed_games}

        def matchup_strength(batters):
            if not batters: return ""
            total=len(batters); dominated=0; neutral=0; owned=0
            for b in batters:
                try:
                    avg=float(b.get("avg","0"))
                    if avg<0.200: dominated+=1
                    elif avg>0.299: owned+=1
                    else: neutral+=1
                except Exception: pass
            if total==0: return ""
            dom_pct=dominated/total; own_pct=owned/total
            if dom_pct>=0.6:   score=5; label="Pitcher dominates"
            elif dom_pct>=0.4: score=4; label="Pitcher has edge"
            elif own_pct>=0.4: score=2; label="Lineup has edge"
            elif own_pct>=0.6: score=1; label="Lineup owns pitcher"
            else:              score=3; label="Even matchup"
            col="#4ade80" if score>=4 else ("#fbbf24" if score==3 else "#f87171")
            dots="".join(
                f'<span style="display:inline-block;width:11px;height:11px;border-radius:50%;'
                f'background:{"#4ade80" if i<score else "#27272a"};margin-right:3px"></span>'
                for i in range(5))
            return (f'<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;'
                    f'background:var(--bg3);border-radius:6px;margin-top:6px">'
                    f'<span style="font-size:10px;color:var(--muted);white-space:nowrap">vs lineup:</span>'
                    f'<div>{dots}</div>'
                    f'<span style="font-size:11px;font-weight:700;color:{col}">{label}</span>'
                    f'<span style="font-size:10px;color:var(--muted);margin-left:auto">'
                    f'{dominated} dominated / {owned} owned</span></div>')
        html = ""
        prev_date = None
        for i,m in enumerate(matchups):
            open_cls="open" if i<1 else ""
            ap=m["away_pitcher"]; hp=m["home_pitcher"]
            ap_era=f'ERA {ap["era"]}' if ap.get("era","N/A")!="N/A" else "ERA N/A"
            hp_era=f'ERA {hp["era"]}' if hp.get("era","N/A")!="N/A" else "ERA N/A"
            # Day header
            game_date = date_lookup.get(m["game"], "Today")
            day_hdr = ""
            if game_date != prev_date:
                day_hdr = f'<div class="day-header"><span class="day-label">{game_date}</span></div>'
                prev_date = game_date
            html+=(day_hdr+
                   f'<div class="game-block {open_cls}" onclick="toggleGame(this)">'
                   f'<div class="game-header">'
                   f'<div><div class="game-teams">{m["away"]} @ {m["home"]}</div>'
                   f'<div class="game-time">{ap["name"]} vs {hp["name"]}</div></div>'
                   f'<div class="game-right"><span class="toggle">v</span></div>'
                   f'</div>'
                   f'<div class="game-body" style="padding:0 15px 20px">'
                   f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px">'
                   f'<div>'
                   f'<div class="pitcher-card">'
                   f'<div class="pitcher-role">AWAY STARTER</div>'
                   f'<div class="pitcher-name">{ap["name"]}</div>'
                   f'<div class="pitcher-team">{m["away"]} - {ap_era} - WHIP {ap.get("whip","N/A")} - K/9 {ap.get("k9","N/A")}</div>'
                   f'</div>'
                   f'<div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin:12px 0 6px">{m["home"]} Batters vs {ap["name"]}</div>'
                   f'{batter_table(m["home_batters"],ap,m["home"],m["home_source"])}'
                   f'{matchup_strength(m["home_batters"])}'
                   f'</div>'
                   f'<div>'
                   f'<div class="pitcher-card">'
                   f'<div class="pitcher-role">HOME STARTER</div>'
                   f'<div class="pitcher-name">{hp["name"]}</div>'
                   f'<div class="pitcher-team">{m["home"]} - {hp_era} - WHIP {hp.get("whip","N/A")} - K/9 {hp.get("k9","N/A")}</div>'
                   f'</div>'
                   f'<div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin:12px 0 6px">{m["away"]} Batters vs {hp["name"]}</div>'
                   f'{batter_table(m["away_batters"],hp,m["away"],m["away_source"])}'
                   f'{matchup_strength(m["away_batters"])}'
                   f'</div>'
                   f'</div>'
                   f'<div style="margin-top:10px;padding:8px 12px;background:var(--bg3);border-radius:6px;font-size:11px;color:var(--muted);line-height:1.6">'
                   f'Green = .300+ BA (batter owns pitcher) - Amber = .250-.299 - Red = under .250 (pitcher has edge) - Min 3 AB'
                   f'</div></div></div>')
        return html

    def weather_page():
        if not weather:
            return '<p style="color:var(--muted);font-size:13px;padding:2rem 0;text-align:center">Weather data unavailable.</p>'
        html=""
        prev_date = None
        for g in analyzed_games:
            home=g["home"]; away=g["away"]; w=weather.get(home)
            if not w: continue
            # Day header
            game_date = g.get("date_et","Today")
            if game_date != prev_date:
                html += f'<div class="day-header"><span class="day-label">{game_date}</span></div>'
                prev_date = game_date
            if w.get("roof"):
                html+=(f'<div class="game-block" onclick="toggleGame(this)">'
                       f'<div class="game-header">'
                       f'<div><div class="game-teams">{away} @ {home}</div>'
                       f'<div class="game-time">{w["stadium_name"]} - {g["time"]}</div></div>'
                       f'<div class="game-right"><span class="badge b-pass" style="font-size:9px">DOME</span>'
                       f'<span class="toggle">v</span></div>'
                       f'</div>'
                       f'<div class="game-body"><div style="padding:1rem;background:var(--bg3);border-radius:8px;'
                       f'margin-top:12px;font-size:13px;color:var(--muted);text-align:center">'
                       f'{w["stadium_name"]} has a roof -- weather does not affect this game.</div></div></div>')
                continue
            effect=w.get("wind_effect","unknown"); wind_spd=int(w.get("wind_speed","0") or 0)
            wind_dir=w.get("wind_dir","N/A"); temp=w.get("temp","?"); cond=w.get("condition",""); humidity=w.get("humidity","?")
            if wind_spd<5:
                effect_badge='<span class="badge b-pass">CALM</span>'; effect_label="Calm winds"; effect_color="var(--muted)"
            elif effect=="blowing_out":
                effect_badge='<span class="badge b-fire">BLOWING OUT</span>'; effect_label=f"Wind OUT at {wind_spd} mph -- Over lean"; effect_color="var(--red)"
            elif effect=="blowing_in":
                effect_badge='<span class="badge b-value">BLOWING IN</span>'; effect_label=f"Wind IN at {wind_spd} mph -- Under lean"; effect_color="var(--green)"
            else:
                effect_badge='<span class="badge b-watch">CROSSWIND</span>'; effect_label=f"Crosswind {wind_spd} mph"; effect_color="var(--amber)"
            if wind_spd>=12: bet_note=f"Strong wind ({wind_spd} mph) already factored into model totals calculation."
            elif wind_spd>=8: bet_note=f"Moderate wind ({wind_spd} mph) factored into totals analysis."
            else: bet_note="Light winds -- not a significant factor."
            orient=w.get("orientation",0)
            wind_deg_abs=WIND_DIR_DEG.get(wind_dir.upper().replace(" ",""),0)
            arrow_rotate=((wind_deg_abs+180)%360-orient)%360
            ec=effect_color
            html+=(f'<div class="game-block" onclick="toggleGame(this)">'
                   f'<div class="game-header">'
                   f'<div><div class="game-teams">{away} @ {home}</div>'
                   f'<div class="game-time">{w["stadium_name"]} - {g["time"]}</div></div>'
                   f'<div class="game-right">{effect_badge}<span class="toggle">v</span></div>'
                   f'</div>'
                   f'<div class="game-body">'
                   f'<div style="display:grid;grid-template-columns:1fr 220px;gap:16px;margin-top:14px;align-items:start">'
                   f'<div>'
                   f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">'
                   f'<div class="stat-box"><div class="sl">Temp</div><div class="sv">{temp}F</div></div>'
                   f'<div class="stat-box"><div class="sl">Wind</div><div class="sv">{wind_spd} mph {wind_dir}</div></div>'
                   f'<div class="stat-box"><div class="sl">Humidity</div><div class="sv">{humidity}%</div></div>'
                   f'<div class="stat-box"><div class="sl">Condition</div><div class="sv" style="font-size:11px">{cond or "N/A"}</div></div>'
                   f'</div>'
                   f'<div style="background:var(--bg3);border-radius:8px;padding:12px 14px;border-left:3px solid {ec}">'
                   f'<div style="font-size:12px;font-weight:600;color:{ec};margin-bottom:4px">{effect_label}</div>'
                   f'<div style="font-size:12px;color:#888;line-height:1.6">{bet_note}</div>'
                   f'</div>'
                   f'</div>'
                   f'<div style="display:flex;flex-direction:column;align-items:center;gap:8px">'
                   f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-family:monospace">Wind Direction</div>'
                   f'<svg viewBox="0 0 180 180" width="180" height="180" xmlns="http://www.w3.org/2000/svg">'
                   f'<circle cx="90" cy="90" r="80" fill="none" stroke="#27272a" stroke-width="1"/>'
                   f'<path d="M90,90 L30,30 A85,85 0 0,1 150,30 Z" fill="#1a2e1a" opacity="0.6"/>'
                   f'<rect x="72" y="72" width="36" height="36" fill="#2d2010" transform="rotate(45,90,90)" rx="2"/>'
                   f'<rect x="88" y="66" width="6" height="6" fill="#e8e8e8" transform="rotate(45,91,69)" rx="1"/>'
                   f'<rect x="108" y="86" width="6" height="6" fill="#e8e8e8" transform="rotate(45,111,89)" rx="1"/>'
                   f'<rect x="88" y="106" width="6" height="6" fill="#e8e8e8" transform="rotate(45,91,109)" rx="1"/>'
                   f'<polygon points="90,124 85,129 90,132 95,129" fill="#e8e8e8"/>'
                   f'<text x="90" y="22" text-anchor="middle" fill="#555" font-size="10" font-family="monospace">CF</text>'
                   f'<g transform="rotate({arrow_rotate}, 90, 90)">'
                   f'<line x1="90" y1="90" x2="90" y2="42" stroke="{ec}" stroke-width="3" stroke-linecap="round"/>'
                   f'<polygon points="90,36 84,50 96,50" fill="{ec}"/>'
                   f'</g>'
                   f'<text x="90" y="168" text-anchor="middle" fill="{ec}" font-size="11" font-family="monospace" font-weight="bold">{wind_spd} mph {wind_dir}</text>'
                   f'</svg>'
                   f'</div>'
                   f'</div>'
                   f'</div></div>')
        return html or '<p style="color:var(--muted);text-align:center;padding:2rem">No weather data.</p>'


    def f5_page():
        sig_cls  = {"fire":"b-fire","sharp":"b-sharp","value":"b-value","watch":"b-watch"}
        sig_col  = {"fire":"var(--red)","sharp":"var(--blue)","value":"var(--green)","watch":"var(--amber)"}
        type_lbl = {"f5_ml":"F5 Moneyline","f5_total":"F5 Total","nrfi":"1st Inning"}

        nrfi_plays = [p for p in f5_plays if p["type"] == "nrfi"]
        f5_ml_plays= [p for p in f5_plays if p["type"] == "f5_ml"]
        f5_tot_plays=[p for p in f5_plays if p["type"] == "f5_total"]

        def play_card(p):
            sig   = p.get("signal","watch")
            edge  = p.get("edge",0)
            ec    = "var(--green)" if edge > 0 else "var(--muted)"
            away_era = p.get("away_era","N/A"); home_era = p.get("home_era","N/A")
            away_sp  = p.get("away_sp","TBD");  home_sp  = p.get("home_sp","TBD")
            sp_note  = f"{away_sp} ({away_era} ERA) vs {home_sp} ({home_era} ERA)"
            return (
                f'<div style="background:var(--bg2);border:1px solid var(--border);'
                f'border-left:3px solid {sig_col.get(sig,"var(--amber)")};'
                f'border-radius:10px;padding:14px 16px;margin-bottom:8px">'
                f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">'
                f'<div>'
                f'<div style="font-size:11px;color:var(--muted);margin-bottom:2px">{p["game"]}</div>'
                f'<div style="font-size:16px;font-weight:700;color:#fff">{p["play"]}</div>'
                f'</div>'
                f'<div style="text-align:right">'
                f'<div style="font-family:monospace;font-size:16px;font-weight:700;color:var(--accent)">{p["price"]}</div>'
                f'<div style="font-size:11px;color:var(--muted)">{p["book"]}</div>'
                f'</div>'
                f'</div>'
                f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
                f'<div style="background:var(--bg3);border-radius:6px;padding:5px 10px;text-align:center">'
                f'<div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px">True %</div>'
                f'<div style="font-family:monospace;font-size:13px;font-weight:700;color:#fff">{p["true_pct"]}%</div>'
                f'</div>'
                f'<div style="background:var(--bg3);border-radius:6px;padding:5px 10px;text-align:center">'
                f'<div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px">Implied %</div>'
                f'<div style="font-family:monospace;font-size:13px;font-weight:700;color:#fff">{p["implied_pct"]}%</div>'
                f'</div>'
                f'<div style="background:var(--bg3);border-radius:6px;padding:5px 10px;text-align:center">'
                f'<div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px">Edge</div>'
                f'<div style="font-family:monospace;font-size:13px;font-weight:700;color:{ec}">'
                f'{("+" if edge>0 else "")}{edge}%</div>'
                f'</div>'
                f'<span class="badge {sig_cls.get(sig,"b-watch")}" style="align-self:center">{sig.upper()}</span>'
                f'</div>'
                f'<div style="font-size:11px;color:var(--muted);font-family:monospace">'
                f'SP: {sp_note}</div>'
                f'</div>'
            )

        def section(plays, title, icon, description):
            if not plays:
                return (f'<div class="sec-header"><h2>{icon} {title}</h2><div class="sec-line"></div></div>'
                        f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;'
                        f'padding:1.5rem;text-align:center;color:var(--muted);margin-bottom:1.5rem">'
                        f'No qualifying {title} plays today (1.5%+ edge required)</div>')
            html = (f'<div class="sec-header"><h2>{icon} {title}</h2><div class="sec-line"></div></div>'
                    f'<div style="font-size:12px;color:var(--muted);margin-bottom:1rem;line-height:1.6">'
                    f'{description}</div>')
            for p in plays:
                html += play_card(p)
            return html

        if not f5_plays:
            return (f'<div style="text-align:center;padding:4rem 2rem">'
                    f'<div style="font-size:48px;margin-bottom:1rem">⏱️</div>'
                    f'<div style="font-size:18px;font-weight:700;color:var(--text);margin-bottom:8px">'
                    f'No F5 / NRFI plays found</div>'
                    f'<div style="font-size:13px;color:var(--muted);max-width:480px;margin:0 auto;line-height:1.8">'
                    f'This could mean:<br>'
                    f'<strong style="color:var(--text)">1.</strong> Your Odds API plan doesn\'t include half-game markets '
                    f'(h2h_h1, totals_h1). These require a paid tier upgrade.<br>'
                    f'<strong style="color:var(--text)">2.</strong> F5 lines haven\'t been posted yet '
                    f'(typically 2-3 hours before first pitch).<br>'
                    f'<strong style="color:var(--text)">3.</strong> No plays cleared the +1.5% edge threshold today.<br><br>'
                    f'<span style="color:var(--accent)">The main game model is completely unaffected.</span>'
                    f'</div>'
                    f'</div>')

        html = (f'<div style="margin-bottom:1.5rem">'
                f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:22px;font-weight:700;'
                f'color:#fff;margin-bottom:4px">⏱️ F5 & 1st Inning Bets</div>'
                f'<div style="font-size:13px;color:var(--muted);line-height:1.6">'
                f'First 5 innings and NRFI/YRFI plays. F5 model weights starting pitcher quality '
                f'2x higher than the full-game model since starters control all 5 innings. '
                f'Bullpen fatigue is excluded. Only plays with +1.5% edge shown.</div>'
                f'</div>')

        # Summary bar
        total_plays = len(f5_plays)
        fire_ct = sum(1 for p in f5_plays if p["signal"]=="fire")
        best_edge = max((p["edge"] for p in f5_plays), default=0)
        html += (f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:2rem">'
                 f'<div class="metric-card" style="text-align:center">'
                 f'<div class="metric-label">Total Plays</div>'
                 f'<div class="metric-val">{total_plays}</div></div>'
                 f'<div class="metric-card" style="text-align:center">'
                 f'<div class="metric-label">Fire Signals</div>'
                 f'<div class="metric-val" style="color:var(--red)">{fire_ct}</div></div>'
                 f'<div class="metric-card" style="text-align:center">'
                 f'<div class="metric-label">Best Edge</div>'
                 f'<div class="metric-val" style="color:var(--green)">+{best_edge}%</div></div>'
                 f'</div>')

        html += section(nrfi_plays,   "NRFI / YRFI",     "🎯",
                        "First inning only. No Run First Inning (NRFI) benefits from elite starting pitchers "
                        "— both starters being above average ERA creates a strong NRFI lean. "
                        "YRFI benefits from weak starters or hitter-friendly parks.")
        html += section(f5_ml_plays,  "F5 Moneyline",    "📋",
                        "First 5 innings winner. SP quality weighted heavily — the starter who "
                        "pitches deeper into the game with lower ERA has a compounding advantage.")
        html += section(f5_tot_plays, "F5 Totals",       "📊",
                        "First 5 innings over/under. Two dominant starters = Under lean. "
                        "Weak starters or Coors/hitter parks = Over lean.")
        return html

    def betting_trends_page(results_data):
        days     = results_data.get("days",[])
        all_bets = [b for day in days for b in day.get("bets",[])
                    if b.get("result") in ("W","L","P")]

        if not all_bets:
            return (
                f'<div style="text-align:center;padding:4rem 2rem">'
                f'<div style="font-size:48px;margin-bottom:1rem">📈</div>'
                f'<div style="font-size:18px;font-weight:700;color:var(--text);margin-bottom:8px">No results yet</div>'
                f'<div style="font-size:14px;color:var(--muted)">Betting trends will appear here once the nightly '
                f'logger starts grading your picks. Check back tomorrow.</div>'
                f'</div>'
            )

        # Last 7 days only
        from datetime import datetime as _dt, timedelta as _td
        today     = _dt.now().date()
        week_ago  = today - _td(days=7)
        week_bets = []
        for day in days:
            try:
                d = _dt.strptime(day.get("date",""), "%B %d, %Y").date()
                if d >= week_ago:
                    for b in day.get("bets",[]):
                        if b.get("result") in ("W","L","P"):
                            week_bets.append({**b, "_date": d, "_date_lbl": day.get("date","")})
            except Exception:
                pass

        # ── SUMMARY STATS BAR ──────────────────────────────
        def wl(bets):
            w=sum(1 for b in bets if b.get("result")=="W")
            l=sum(1 for b in bets if b.get("result")=="L")
            return w,l

        w7,l7  = wl(week_bets)
        wall,lall = wl(all_bets)
        pct7   = round(w7/(w7+l7)*100) if w7+l7>0 else 0
        pctall = round(wall/(wall+lall)*100) if wall+lall>0 else 0
        streak = 0; streak_type = ""
        for b in reversed(all_bets):
            r = b.get("result","")
            if not streak_type and r in ("W","L"):
                streak_type = r; streak = 1
            elif r == streak_type:
                streak += 1
            else:
                break
        streak_col  = "var(--green)" if streak_type=="W" else "var(--red)"
        streak_lbl  = f"{streak}{'W' if streak_type=='W' else 'L'} streak"

        pct7_col = "var(--green)" if pct7>=55 else ("var(--red)" if pct7<45 else "var(--amber)")
        summary_bar = (
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:2rem">'
            f'<div class="metric-card" style="text-align:center">'
            f'<div class="metric-label">Last 7 Days</div>'
            f'<div class="metric-val" style="color:{pct7_col};font-size:24px">{pct7}%</div>'
            f'<div style="font-size:11px;color:var(--muted)">{w7}W - {l7}L</div>'
            f'</div>'
            f'<div class="metric-card" style="text-align:center">'
            f'<div class="metric-label">All Time</div>'
            f'<div class="metric-val" style="font-size:24px">{pctall}%</div>'
            f'<div style="font-size:11px;color:var(--muted)">{wall}W - {lall}L</div>'
            f'</div>'
            f'<div class="metric-card" style="text-align:center">'
            f'<div class="metric-label">Current Streak</div>'
            f'<div class="metric-val" style="color:{streak_col};font-size:24px">{streak_lbl if streak_type else "—"}</div>'
            f'<div style="font-size:11px;color:var(--muted)">{"Active" if streak_type else "No bets yet"}</div>'
            f'</div>'
            f'<div class="metric-card" style="text-align:center">'
            f'<div class="metric-label">Total Tracked</div>'
            f'<div class="metric-val" style="font-size:24px">{len(all_bets)}</div>'
            f'<div style="font-size:11px;color:var(--muted)">best bets graded</div>'
            f'</div>'
            f'</div>'
        )

        # ── TREND CARDS ────────────────────────────────────
        # Show last 7 days in reverse order, each bet as a rich card
        sig_colors = {
            "fire":  ("#7f1d1d","#f87171","🔥"),
            "sharp": ("#1e3a5f","#60a5fa","⚡"),
            "value": ("#14532d","#4ade80","💰"),
            "watch": ("#27272a","#a1a1aa","👁"),
        }

        def edge_sentence(b):
            """Extract a clean edge sentence from the stored note or edge field."""
            note = b.get("note","")
            edge = b.get("edge","")
            if edge and "%" in str(edge):
                return f"Edge was {edge}"
            return ""

        def result_why(b):
            """Generate a brief post-result context note."""
            note = b.get("note","")
            result = b.get("result","")
            # Extract final score from note
            if "Final:" in note:
                score_part = note.split("Final:")[-1].strip()
                return f"Final: {score_part}"
            return note[:80] if note else ""

        def signal_reason(sig):
            reasons = {
                "fire":  "Sharp market split + model edge",
                "sharp": "Book discrepancy + model edge",
                "value": "Book discrepancy flagged",
                "watch": "Model edge, books in agreement",
            }
            return reasons.get(sig,"")

        if not week_bets:
            trend_html = (
                f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;'
                f'padding:2rem;text-align:center;color:var(--muted)">'
                f'No bets in the last 7 days yet.</div>'
            )
        else:
            trend_html = ""
            # Group by date
            from collections import OrderedDict
            date_groups = OrderedDict()
            for b in sorted(week_bets, key=lambda x: x["_date"], reverse=True):
                d = b["_date_lbl"]
                date_groups.setdefault(d,[]).append(b)

            for date_lbl, bets in date_groups.items():
                dw,dl = wl(bets)
                dcol  = "var(--green)" if dw>dl else ("var(--red)" if dl>dw else "var(--amber)")

                trend_html += (
                    f'<div style="margin-bottom:1.5rem">'
                    f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">'
                    f'<div style="font-size:13px;font-weight:700;color:var(--text);font-family:monospace">{date_lbl}</div>'
                    f'<div style="height:1px;flex:1;background:var(--border)"></div>'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:13px;font-weight:700;color:{dcol}">{dw}W-{dl}L</div>'
                    f'</div>'
                )

                for b in bets:
                    res    = b.get("result","?")
                    sig    = b.get("signal","watch")
                    bg,col,icon = sig_colors.get(sig,sig_colors["watch"])
                    play   = b.get("play","?")
                    price  = b.get("price","?")
                    book   = b.get("book","?")
                    game   = b.get("game","?")
                    note   = result_why(b)
                    es     = edge_sentence(b)
                    sr     = signal_reason(sig)

                    if res == "W":
                        res_bg  = "rgba(74,222,128,0.08)"
                        res_bdr = "rgba(74,222,128,0.3)"
                        res_lbl = "✓ WIN"
                        res_col = "var(--green)"
                    elif res == "L":
                        res_bg  = "rgba(248,113,113,0.08)"
                        res_bdr = "rgba(248,113,113,0.3)"
                        res_lbl = "✗ LOSS"
                        res_col = "var(--red)"
                    else:
                        res_bg  = "rgba(161,161,170,0.08)"
                        res_bdr = "rgba(161,161,170,0.3)"
                        res_lbl = "· PUSH"
                        res_col = "var(--muted)"

                    # Build the context line
                    context_parts = []
                    if note: context_parts.append(note)
                    if es:   context_parts.append(es)
                    if sr:   context_parts.append(sr)
                    context_line = " · ".join(context_parts)

                    context_html = (f'<div style="font-size:12px;color:#aaa;line-height:1.6;font-style:italic">'
                                    f'{context_line}</div>') if context_line else ""
                    trend_html += (
                        f'<div style="background:{res_bg};border:1px solid {res_bdr};border-radius:10px;'
                        f'padding:12px 16px;margin-bottom:8px;display:grid;'
                        f'grid-template-columns:auto 1fr auto;gap:12px;align-items:start">'
                        f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px;min-width:52px">'
                        f'<span style="font-size:18px">{icon}</span>'
                        f'<span style="font-size:11px;font-weight:700;color:{res_col};font-family:monospace;white-space:nowrap">{res_lbl}</span>'
                        f'</div>'
                        f'<div>'
                        f'<div style="font-size:11px;color:var(--muted);margin-bottom:2px">{game}</div>'
                        f'<div style="font-size:15px;font-weight:700;color:#fff;margin-bottom:3px">{play}</div>'
                        f'<div style="font-size:12px;color:{col};font-family:monospace;margin-bottom:6px">{price} at {book}</div>'
                        f'{context_html}'
                        f'</div>'
                        f'<div style="text-align:right">'
                        f'<span style="background:{bg};border:1px solid {col};border-radius:4px;'
                        f'padding:2px 8px;font-size:10px;font-family:monospace;color:{col};font-weight:700">{sig.upper()}</span>'
                        f'</div>'
                        f'</div>'
                    )

                trend_html += f'</div>'  # close date group

        return (
            f'<div style="margin-bottom:1.5rem">'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:22px;font-weight:700;'
            f'color:#fff;margin-bottom:4px">📈 Betting Trends</div>'
            f'<div style="font-size:13px;color:var(--muted)">Last 7 days of model picks with results and context. '
            f'Pushes and ungraded bets are excluded from percentage calculations.</div>'
            f'</div>'
            + summary_bar
            + f'<div class="sec-header"><h2>This Week\'s Picks</h2><div class="sec-line"></div></div>'
            + trend_html
        )

    def accuracy_page(results_data):
        days     = results_data.get("days", [])
        all_bets = [b for day in days for b in day.get("bets", [])]

        # ── STAT HELPERS ─────────────────────────────────
        def wl(bets):
            w = sum(1 for b in bets if b.get("result","")=="W")
            l = sum(1 for b in bets if b.get("result","")=="L")
            return w, l

        def pct(w, l):
            return round(w/(w+l)*100) if (w+l)>0 else 0

        def make_circle(w, l, size=200, label="Overall"):
            p     = pct(w,l)
            r     = 70; circ=round(2*3.14159*r,1)
            fill  = round(circ*p/100,1); gap=round(circ-fill,1)
            col   = "#4ade80" if p>=55 else ("#fbbf24" if p>=45 else "#f87171")
            return (
                f'<div style="display:flex;flex-direction:column;align-items:center;gap:6px">'
                f'<svg viewBox="0 0 180 180" width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">'
                f'<circle cx="90" cy="90" r="{r}" fill="none" stroke="#27272a" stroke-width="14"/>'
                f'<circle cx="90" cy="90" r="{r}" fill="none" stroke="{col}" stroke-width="14"'
                f' stroke-dasharray="{fill} {gap}" stroke-dashoffset="{round(circ*0.25,1)}" stroke-linecap="round"/>'
                f'<text x="90" y="82" text-anchor="middle" fill="#fff" font-size="30"'
                f' font-family="IBM Plex Mono,monospace" font-weight="700">{p}%</text>'
                f'<text x="90" y="104" text-anchor="middle" fill="#71717a" font-size="12"'
                f' font-family="IBM Plex Mono,monospace">{w}W - {l}L</text>'
                f'</svg>'
                f'<div style="font-size:11px;color:var(--muted);font-family:monospace;'
                f'text-transform:uppercase;letter-spacing:1px">{label}</div>'
                f'</div>'
            )

        wins_all, losses_all = wl(all_bets)
        total_all = wins_all + losses_all

        # Signal-filtered bets
        # "signal" field logged by log_results.py — fall back gracefully if missing
        def sig_bets(signal_list):
            return [b for b in all_bets if b.get("signal","") in signal_list]

        sharp_bets = sig_bets(["fire"])
        value_bets = sig_bets(["fire","value","sharp"])  # all flagged plays
        w_sharp, l_sharp = wl(sharp_bets)
        w_value, l_value = wl(value_bets)

        if total_all == 0:
            return (
                f'{make_circle(0,0,label="All Bets")}'
                f'<div style="text-align:center;padding:3rem 2rem;color:var(--muted);font-size:14px">'
                f'No results recorded yet. The nightly workflow logs results automatically, '
                f'or edit <code style="color:var(--accent)">results.json</code> in your repo.'
                f'</div>'
            )

        # CLV stats
        clv_bets     = [b for b in all_bets if b.get("clv") and b["clv"].get("clv_cents") is not None]
        clv_positive = sum(1 for b in clv_bets if b["clv"]["clv_cents"] > 0)
        clv_avg      = round(sum(b["clv"]["clv_cents"] for b in clv_bets)/len(clv_bets),1) if clv_bets else None

        # CLV summary strip
        clv_section = ""
        if clv_bets:
            clv_col  = "var(--green)" if (clv_avg or 0)>0 else "var(--red)"
            clv_beat = round(clv_positive/len(clv_bets)*100) if clv_bets else 0
            clv_section = (
                f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;'
                f'padding:14px 18px;margin-bottom:1.5rem">'
                f'<div style="font-size:10px;font-family:monospace;text-transform:uppercase;'
                f'letter-spacing:1.5px;color:var(--muted);margin-bottom:10px">Closing Line Value (CLV)</div>'
                f'<div style="display:flex;gap:20px;flex-wrap:wrap">'
                f'<div class="metric-card" style="min-width:120px;text-align:center">'
                f'<div class="metric-label">Avg CLV</div>'
                f'<div class="metric-val" style="color:{clv_col};font-size:20px">{("+" if (clv_avg or 0)>0 else "")}{clv_avg}c</div>'
                f'</div>'
                f'<div class="metric-card" style="min-width:120px;text-align:center">'
                f'<div class="metric-label">Beat Close %</div>'
                f'<div class="metric-val" style="font-size:20px">{clv_beat}%</div>'
                f'</div>'
                f'<div class="metric-card" style="min-width:120px;text-align:center">'
                f'<div class="metric-label">CLV Tracked</div>'
                f'<div class="metric-val" style="font-size:20px">{len(clv_bets)}</div>'
                f'</div>'
                f'</div>'
                f'<div style="font-size:11px;color:var(--muted);margin-top:10px;line-height:1.6">'
                f'Positive avg CLV = you are consistently finding better prices than the market closes at. '
                f'This is the strongest indicator of genuine edge, independent of short-term win/loss noise.'
                f'</div>'
                f'</div>'
            )

        # CLV Feedback Loop -- which adjustment types produce positive CLV?
        clv_feedback = ""
        if total_all >= 75 and clv_bets:
            adj_types = {
                "SP Quality":     lambda b: any(k in b.get("play","") for k in ["ERA","Pitcher"]),
                "Bullpen":        lambda b: "bullpen" in b.get("note","").lower(),
                "Park Factor":    lambda b: "park" in b.get("note","").lower() or "Over" in b.get("play","") or "Under" in b.get("play",""),
                "Platoon Splits": lambda b: "platoon" in b.get("note","").lower(),
                "Line Movement":  lambda b: "moved" in b.get("note","").lower() or "sharp" in b.get("note","").lower(),
            }
            fb_rows = ""
            for adj_name, matcher in adj_types.items():
                matched = [b for b in clv_bets if matcher(b)]
                if not matched: continue
                avg_c = round(sum(b["clv"]["clv_cents"] for b in matched)/len(matched),1)
                beat  = sum(1 for b in matched if b["clv"]["clv_cents"]>0)
                col   = "var(--green)" if avg_c>0 else "var(--red)"
                rec   = "Amplify weight" if avg_c>1.5 else ("Reduce weight" if avg_c<-1.5 else "Keep as-is")
                fb_rows += (f'<tr><td>{adj_name}</td>'
                            f'<td class="mono">{len(matched)}</td>'
                            f'<td class="mono" style="color:{col}">{("+") if avg_c>0 else ""}{avg_c}c</td>'
                            f'<td class="mono">{round(beat/len(matched)*100)}%</td>'
                            f'<td style="font-size:11px;color:{col}">{rec}</td></tr>')
            if fb_rows:
                clv_feedback = (
                    f'<div class="sec-header"><h2>CLV Feedback Loop</h2><div class="sec-line"></div></div>'
                    f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:2rem">'
                    f'<div style="padding:10px 14px;background:var(--bg3);font-size:11px;color:var(--muted)">'
                    f'Which model adjustments consistently beat the closing line? Positive avg CLV = that factor finds real edge. '
                    f'Use this to tune adjustment weights in generate.py.</div>'
                    f'<table class="dtable"><thead><tr><th>Adjustment</th><th>Bets</th>'
                    f'<th>Avg CLV</th><th>Beat Close%</th><th>Recommendation</th></tr></thead>'
                    f'<tbody>{fb_rows}</tbody></table></div>'
                )

        # Calibration audit at 75 bets
        AUDIT_THRESHOLD = 75
        calib_section = ""
        if total_all >= AUDIT_THRESHOLD:
            # Group bets by model-predicted probability bucket
            # Bets need a "true_pct" field logged -- we add this to picks below
            bucket_bets = {}
            for b in all_bets:
                tp = b.get("true_pct")
                if tp is None: continue
                try:
                    tp_f = float(str(tp).replace("%",""))
                    bucket = round(tp_f/5)*5   # round to nearest 5% bucket
                    bucket_bets.setdefault(bucket,[]).append(b)
                except Exception:
                    continue

            if len(bucket_bets) >= 3:
                rows = ""
                for bucket in sorted(bucket_bets.keys()):
                    bets_in = bucket_bets[bucket]
                    bw,bl   = wl(bets_in); bt=bw+bl
                    actual  = pct(bw,bl)
                    diff    = actual - bucket
                    col     = "var(--green)" if diff>3 else ("var(--red)" if diff<-3 else "var(--muted)")
                    note    = "Model UNDER-claiming edge" if diff>3 else ("Model OVER-claiming edge" if diff<-3 else "Well calibrated")
                    rows   += (f'<tr>'
                               f'<td class="mono">{bucket}%</td>'
                               f'<td class="mono">{bt}</td>'
                               f'<td class="mono c-green">{bw}W</td>'
                               f'<td class="mono c-red">{bl}L</td>'
                               f'<td class="mono" style="color:{col}">{actual}%</td>'
                               f'<td style="font-size:11px;color:{col}">{note}</td>'
                               f'</tr>')

                calib_section = (
                    f'<div class="sec-header"><h2>Calibration Audit ({total_all} bets)</h2>'
                    f'<div class="sec-line"></div></div>'
                    f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;'
                    f'overflow:hidden;margin-bottom:2rem">'
                    f'<div style="padding:10px 14px;background:var(--bg3);font-size:11px;color:var(--muted)">'
                    f'When the model says a team has X% true probability, do they actually win X% of the time? '
                    f'Rows where "Actual Win%" deviates from "Model%" by 3+ points indicate the adjustment '
                    f'multipliers need tuning.</div>'
                    f'<table class="dtable">'
                    f'<thead><tr><th>Model%</th><th>Bets</th><th>Wins</th><th>Losses</th>'
                    f'<th>Actual Win%</th><th>Assessment</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table></div>'
                )
            else:
                calib_section = (
                    f'<div class="sec-header"><h2>Calibration Audit</h2><div class="sec-line"></div></div>'
                    f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;'
                    f'padding:1rem 1.25rem;margin-bottom:2rem;color:var(--muted);font-size:13px">'
                    f'You have {total_all} bets logged -- need true_pct data on bets to run calibration. '
                    f'This will populate automatically as new bets are logged.</div>'
                )
        elif total_all > 0:
            remaining = AUDIT_THRESHOLD - total_all
            calib_section = (
                f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;'
                f'padding:12px 16px;margin-bottom:1.5rem;display:flex;align-items:center;gap:12px">'
                f'<div style="font-size:11px;color:var(--muted);flex:1">'
                f'Calibration audit unlocks at <strong style="color:var(--text)">{AUDIT_THRESHOLD} bets</strong>. '
                f'It will analyze whether the model is over- or under-claiming edge on each probability bucket '
                f'and tell you exactly which adjustment multipliers to tune.</div>'
                f'<div style="text-align:center;flex-shrink:0">'
                f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:22px;font-weight:700;color:var(--accent)">'
                f'{total_all}/{AUDIT_THRESHOLD}</div>'
                f'<div style="font-size:10px;color:var(--muted)">{remaining} to go</div>'
                f'</div></div>'
            )
        circles = (
            f'<div style="display:flex;justify-content:center;flex-wrap:wrap;gap:32px;margin-bottom:2rem">'
            f'{make_circle(wins_all, losses_all, 200, "All Bets")}'
            f'{make_circle(w_value, l_value, 160, "Value Plays")}'
            f'{make_circle(w_sharp, l_sharp, 160, "Fire Alerts Only")}'
            f'</div>'
        )

        # ── STAT ROW ──────────────────────────────────────
        def stat_row(label, w, l):
            p   = pct(w,l)
            col = "var(--green)" if p>=55 else ("var(--red)" if p<45 else "var(--amber)")
            t   = w+l
            return (
                f'<div style="display:flex;align-items:center;justify-content:space-between;'
                f'padding:10px 14px;border-bottom:1px solid var(--border)">'
                f'<span style="font-size:13px;color:var(--text)">{label}</span>'
                f'<div style="display:flex;align-items:center;gap:20px">'
                f'<span class="mono c-green">{w}W</span>'
                f'<span class="mono c-red">{l}L</span>'
                f'<span class="mono" style="color:var(--muted)">{t} bets</span>'
                f'<span class="mono" style="color:{col};font-size:16px;min-width:50px;text-align:right">{p}%</span>'
                f'</div></div>'
            )

        stats_table = (
            f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;'
            f'overflow:hidden;margin-bottom:2rem">'
            f'<div style="padding:10px 14px;background:var(--bg3);font-size:10px;'
            f'font-family:monospace;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted)">'
            f'Performance Breakdown</div>'
            f'{stat_row("All Best Bets", wins_all, losses_all)}'
            f'{stat_row("Value + Sharp + Fire Plays", w_value, l_value)}'
            f'{stat_row("Fire Alerts Only (DISCREPANCY / SPLIT)", w_sharp, l_sharp)}'
            f'</div>'
        )

        # ── ALL BETS DROPDOWN ────────────────────────────
        def res_badge(res):
            if res=="W": return '<span class="badge b-value" style="font-size:10px">W</span>'
            if res=="L": return '<span class="badge b-fire" style="font-size:10px">L</span>'
            return '<span class="badge b-pass" style="font-size:10px">PUSH</span>'

        def sig_badge(sig):
            cls = {"fire":"b-fire","value":"b-value","sharp":"b-sharp","watch":"b-watch"}.get(sig,"b-pass")
            return f'<span class="badge {cls}" style="font-size:9px;margin-left:4px">{sig.upper()}</span>' if sig else ""

        # Wins dropdown
        def clv_cell(b):
            clv = b.get("clv")
            if not clv or clv.get("clv_cents") is None:
                return '<td style="font-size:11px;color:var(--dim)">-</td>'
            c   = clv["clv_cents"]
            col = "var(--green)" if c>0 else "var(--red)"
            return f'<td class="mono" style="color:{col};font-size:11px">{("+" if c>0 else "")}{c}c</td>'

        win_rows = "".join(
            f'<tr>'
            f'<td>{b.get("game","?")}</td>'
            f'<td class="mono">{b.get("play","?")}{sig_badge(b.get("signal",""))}</td>'
            f'<td class="mono">{b.get("price","?")}</td>'
            f'<td style="font-size:11px;color:var(--muted)">{b.get("book","?")}</td>'
            f'{clv_cell(b)}'
            f'<td style="font-size:11px;color:var(--muted)">{b.get("date","")}</td>'
            f'<td style="font-size:11px;color:#888">{b.get("note","")}</td>'
            f'</tr>'
            for b in all_bets if b.get("result","")=="W"
        )
        loss_rows = "".join(
            f'<tr>'
            f'<td>{b.get("game","?")}</td>'
            f'<td class="mono">{b.get("play","?")}{sig_badge(b.get("signal",""))}</td>'
            f'<td class="mono">{b.get("price","?")}</td>'
            f'<td style="font-size:11px;color:var(--muted)">{b.get("book","?")}</td>'
            f'{clv_cell(b)}'
            f'<td style="font-size:11px;color:var(--muted)">{b.get("date","")}</td>'
            f'<td style="font-size:11px;color:#888">{b.get("note","")}</td>'
            f'</tr>'
            for b in all_bets if b.get("result","")=="L"
        )

        table_header = '<thead><tr><th>Game</th><th>Play</th><th>Price</th><th>Book</th><th>CLV</th><th>Date</th><th>Note</th></tr></thead>'

        all_bets_section = (
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:2rem">'

            # Wins block
            f'<div class="game-block open" onclick="toggleGame(this)">'
            f'<div class="game-header" style="background:rgba(74,222,128,0.05)">'
            f'<div><div class="game-teams" style="color:var(--green)">All Wins</div>'
            f'<div class="game-time">{wins_all} correct bets</div></div>'
            f'<div class="game-right"><span class="toggle">v</span></div>'
            f'</div>'
            f'<div class="game-body">'
            f'{"<p style=padding:1rem;color:var(--muted)>No wins recorded yet.</p>" if not win_rows else ""}'
            f'<table class="dtable" style="margin-top:8px">{table_header}<tbody>{win_rows}</tbody></table>'
            f'</div></div>'

            # Losses block
            f'<div class="game-block open" onclick="toggleGame(this)">'
            f'<div class="game-header" style="background:rgba(248,113,113,0.05)">'
            f'<div><div class="game-teams" style="color:var(--red)">All Losses</div>'
            f'<div class="game-time">{losses_all} incorrect bets</div></div>'
            f'<div class="game-right"><span class="toggle">v</span></div>'
            f'</div>'
            f'<div class="game-body">'
            f'{"<p style=padding:1rem;color:var(--muted)>No losses recorded yet.</p>" if not loss_rows else ""}'
            f'<table class="dtable" style="margin-top:8px">{table_header}<tbody>{loss_rows}</tbody></table>'
            f'</div></div>'

            f'</div>'
        )

        # ── BY DAY DROPDOWN ───────────────────────────────
        day_blocks = ""
        for day in reversed(days):
            date_lbl = day.get("date","?")
            bets     = day.get("bets",[])
            dw,dl    = wl(bets)
            dcol     = "var(--green)" if dw>dl else ("var(--red)" if dl>dw else "var(--amber)")
            rows = "".join(
                f'<tr>'
                f'<td>{b.get("game","?")}</td>'
                f'<td class="mono">{b.get("play","?")}{sig_badge(b.get("signal",""))}</td>'
                f'<td class="mono">{b.get("price","?")}</td>'
                f'<td style="font-size:11px;color:var(--muted)">{b.get("book","?")}</td>'
                f'<td>{res_badge(b.get("result","?"))}</td>'
                f'<td style="font-size:11px;color:var(--muted)">{b.get("note","")}</td>'
                f'</tr>'
                for b in bets
            )
            day_blocks += (
                f'<div class="game-block" onclick="toggleGame(this)">'
                f'<div class="game-header">'
                f'<div><div class="game-teams">{date_lbl}</div>'
                f'<div class="game-time">{len(bets)} best bets</div></div>'
                f'<div class="game-right">'
                f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:14px;font-weight:700;color:{dcol}">{dw}W-{dl}L</span>'
                f'<span class="toggle">v</span></div>'
                f'</div>'
                f'<div class="game-body">'
                f'<table class="dtable" style="margin-top:10px">'
                f'<thead><tr><th>Game</th><th>Play</th><th>Price</th><th>Book</th><th>Result</th><th>Note</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>'
                f'</div></div>'
            )

        hint = (
            f'<div style="font-size:12px;color:var(--muted);text-align:center;margin-bottom:1.5rem;font-family:monospace">'
            f'Results logged automatically nightly. To manually add: edit '
            f'<code style="color:var(--accent)">results.json</code> in your GitHub repo.</div>'
        )

        roi_rows = "".join(
            f'<tr class="roi-bet-row" data-result="{b.get("result","")}" data-price="{b.get("price","")}">'
            f'<td>{b.get("date","")}</td>'
            f'<td>{b.get("game","")}</td>'
            f'<td class="mono">{b.get("play","")}</td>'
            f'<td class="mono">{b.get("price","")}</td>'
            f'<td>{res_badge(b.get("result","?"))}</td>'
            f'</tr>'
            for b in all_bets if b.get("result") in ("W","L","P")
        )
        roi_section = (
            f'<div class="sec-header"><h2>ROI Tracker</h2><div class="sec-line"></div></div>'
            f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:1.25rem;margin-bottom:2rem">'
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:1rem;flex-wrap:wrap">'
            f'<div style="font-size:13px;color:var(--muted)">Unit size ($):</div>'
            f'<input id="roi-unit" type="number" value="100" min="1" '
            f'style="background:var(--bg3);border:1px solid var(--border2);border-radius:6px;'
            f'padding:6px 10px;color:var(--text);font-family:monospace;width:100px"/>'
            f'<button onclick="calcROI()" style="background:var(--accent);color:#000;border:none;'
            f'border-radius:6px;padding:6px 16px;font-weight:700;font-family:monospace;cursor:pointer">Calculate</button>'
            f'<span style="font-family:monospace;font-size:20px;font-weight:700" id="roi-total">--</span>'
            f'<span style="font-family:monospace;font-size:13px;color:var(--muted)" id="roi-units"></span>'
            f'</div>'
            f'<div id="roi-chart" style="margin-bottom:10px"></div>'
            f'<table class="dtable">'
            f'<thead><tr><th>Date</th><th>Game</th><th>Play</th><th>Price</th><th>Result</th></tr></thead>'
            f'<tbody>{roi_rows}</tbody></table>'
            f'</div>'
        )

        # ── CALENDAR HEATMAP ─────────────────────────────
        from calendar import monthcalendar, month_abbr
        import re as _re

        def build_calendar():
            if not days: return ""
            # Build day lookup: {date_str: (wins, losses)}
            day_map = {}
            for day in days:
                date_lbl = day.get("date","")
                dw,dl = wl(day.get("bets",[]))
                if dw+dl > 0:
                    # Parse date label "May 29, 2026" -> "2026-05-29"
                    try:
                        from datetime import datetime as _dt
                        parsed = _dt.strptime(date_lbl, "%B %d, %Y")
                        day_map[parsed.strftime("%Y-%m-%d")] = (dw,dl)
                    except Exception:
                        pass

            if not day_map: return ""

            # Group by month
            from datetime import datetime as _dt, date as _date
            sorted_keys = sorted(day_map.keys())
            first_date  = _dt.strptime(sorted_keys[0], "%Y-%m-%d").date()
            last_date   = _dt.strptime(sorted_keys[-1],"%Y-%m-%d").date()

            html = f'<div class="sec-header"><h2>Best Bet Calendar</h2><div class="sec-line"></div></div>'
            html += '<div style="overflow-x:auto;margin-bottom:2rem">'

            year = first_date.year; month = first_date.month
            while (year, month) <= (last_date.year, last_date.month):
                html += (f'<div style="margin-bottom:1.5rem">'
                         f'<div style="font-size:12px;font-family:monospace;font-weight:700;color:var(--text);'
                         f'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">'
                         f'{month_abbr[month]} {year}</div>'
                         f'<div style="display:flex;gap:3px;flex-wrap:wrap">')

                # Day-of-week headers
                html += '<div style="display:grid;grid-template-columns:repeat(7,28px);gap:3px;margin-bottom:3px">'
                for d in ["Su","Mo","Tu","We","Th","Fr","Sa"]:
                    html += f'<div style="width:28px;text-align:center;font-size:9px;color:var(--muted);font-family:monospace">{d}</div>'
                html += '</div>'

                # Calendar grid
                html += '<div style="display:grid;grid-template-columns:repeat(7,28px);gap:3px">'
                import calendar as _cal
                # Get first day of month weekday (0=Mon, 6=Sun) convert to Sun=0
                first_weekday = (_cal.weekday(year, month, 1) + 1) % 7
                days_in_month = _cal.monthrange(year, month)[1]

                # Empty cells before first day
                for _ in range(first_weekday):
                    html += '<div style="width:28px;height:28px"></div>'

                for day_num in range(1, days_in_month + 1):
                    date_key = f"{year:04d}-{month:02d}-{day_num:02d}"
                    if date_key in day_map:
                        dw, dl = day_map[date_key]
                        if dw > dl:
                            bg = "#166534"; border = "#4ade80"; tc = "#4ade80"
                        elif dl > dw:
                            bg = "#7f1d1d"; border = "#f87171"; tc = "#f87171"
                        else:
                            bg = "#3f3f00"; border = "#fbbf24"; tc = "#fbbf24"
                        tip = f"{dw}W-{dl}L"
                        html += (f'<div title="{date_key}: {tip}" style="width:28px;height:28px;'
                                 f'background:{bg};border:1px solid {border};border-radius:4px;'
                                 f'display:flex;align-items:center;justify-content:center;'
                                 f'font-size:9px;font-family:monospace;color:{tc};font-weight:700;cursor:default">'
                                 f'{day_num}</div>')
                    else:
                        # Check if it's a future date
                        try:
                            from datetime import date as _d2
                            is_future = _date(year, month, day_num) > _date.today()
                        except Exception:
                            is_future = False
                        bg = "transparent" if is_future else "var(--bg3)"
                        html += (f'<div style="width:28px;height:28px;background:{bg};'
                                 f'border:1px solid {"transparent" if is_future else "var(--border)"};'
                                 f'border-radius:4px;display:flex;align-items:center;justify-content:center;'
                                 f'font-size:9px;color:{"var(--dim)" if not is_future else "transparent"};font-family:monospace">'
                                 f'{"" if is_future else day_num}</div>')
                html += '</div></div>'

                # Move to next month
                if month == 12: year += 1; month = 1
                else: month += 1

            # Legend
            html += ('<div style="display:flex;gap:16px;margin-top:8px;flex-wrap:wrap">'
                     '<div style="display:flex;align-items:center;gap:5px">'
                     '<div style="width:14px;height:14px;background:#166534;border:1px solid #4ade80;border-radius:3px"></div>'
                     '<span style="font-size:11px;color:var(--muted)">Positive day</span></div>'
                     '<div style="display:flex;align-items:center;gap:5px">'
                     '<div style="width:14px;height:14px;background:#7f1d1d;border:1px solid #f87171;border-radius:3px"></div>'
                     '<span style="font-size:11px;color:var(--muted)">Negative day</span></div>'
                     '<div style="display:flex;align-items:center;gap:5px">'
                     '<div style="width:14px;height:14px;background:#3f3f00;border:1px solid #fbbf24;border-radius:3px"></div>'
                     '<span style="font-size:11px;color:var(--muted)">Split day</span></div>'
                     '<div style="display:flex;align-items:center;gap:5px">'
                     '<div style="width:14px;height:14px;background:var(--bg3);border:1px solid var(--border);border-radius:3px"></div>'
                     '<span style="font-size:11px;color:var(--muted)">No bets</span></div>'
                     '</div></div>')
            return html

        calendar_section = build_calendar()

        # ── PENDING PICKS (today's locked bets waiting for results) ──
        pending_section = ""
        try:
            graded_games = {b.get("game","") for b in all_bets}
            ungraded = [b for b in pending_picks
                        if b.get("game","") not in graded_games]

            if ungraded:
                rows = ""
                for b in ungraded:
                    sig     = b.get("signal","watch")
                    sig_col = {"fire":"var(--red)","sharp":"#60a5fa",
                               "value":"var(--green)","watch":"var(--muted)"}.get(sig,"var(--muted)")
                    edge    = b.get("edge","")
                    rows += (
                        f'<div style="display:flex;align-items:center;gap:12px;'
                        f'padding:12px 16px;border-bottom:1px solid var(--border)">'
                        f'<div style="flex:1">'
                        f'<div style="font-size:14px;font-weight:700;color:#fff">{b.get("play","?")}</div>'
                        f'<div style="font-size:11px;color:var(--muted);margin-top:2px">{b.get("game","?")}</div>'
                        f'</div>'
                        f'<div style="text-align:right;flex-shrink:0">'
                        f'<div style="font-family:monospace;font-size:13px;font-weight:700;color:var(--accent)">'
                        f'{b.get("price","?")} @ {b.get("book","?")}</div>'
                        f'<div style="font-size:10px;color:{sig_col};margin-top:2px">'
                        f'{sig.upper()} · {edge}</div>'
                        f'</div>'
                        f'<div style="background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.4);'
                        f'border-radius:6px;padding:5px 12px;font-size:11px;font-weight:700;'
                        f'color:var(--amber);font-family:monospace;white-space:nowrap;flex-shrink:0">'
                        f'⏳ PENDING</div>'
                        f'</div>'
                    )
                pending_section = (
                    f'<div class="sec-header"><h2>Awaiting Results</h2><div class="sec-line"></div></div>'
                    f'<div style="background:var(--bg2);border:2px solid rgba(251,191,36,0.3);'
                    f'border-radius:12px;overflow:hidden;margin-bottom:2rem">'
                    f'<div style="padding:12px 16px;background:rgba(251,191,36,0.06);'
                    f'border-bottom:1px solid rgba(251,191,36,0.2);'
                    f'display:flex;align-items:center;justify-content:space-between">'
                    f'<div style="display:flex;align-items:center;gap:10px">'
                    f'<span class="live-dot" style="background:var(--amber)"></span>'
                    f'<span style="font-size:12px;color:var(--amber);font-family:monospace;font-weight:700">'
                    f'{len(ungraded)} PICKS LOCKED IN — WAITING FOR RESULTS</span>'
                    f'</div>'
                    f'<div style="font-size:10px;color:var(--muted)">{date_str}</div>'
                    f'</div>'
                    f'{rows}'
                    f'<div style="padding:10px 16px;font-size:11px;color:var(--muted)">'
                    f'Picks are saved in picks.json. The nightly logger checks scores every 30 min '
                    f'from 6pm–2am ET and will flip these to ✓ WIN or ✗ LOSS automatically. '
                    f'This page auto-refreshes every 5 minutes.</div>'
                    f'</div>'
                )
            else:
                # Show a "waiting for noon picks" message before the daily run
                pending_section = (
                    f'<div class="sec-header"><h2>Awaiting Results</h2><div class="sec-line"></div></div>'
                    f'<div style="background:var(--bg2);border:1px solid var(--border);'
                    f'border-radius:12px;padding:1.5rem;margin-bottom:2rem;text-align:center">'
                    f'<div style="font-size:32px;margin-bottom:8px">⏳</div>'
                    f'<div style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:4px">'
                    f'No pending picks yet</div>'
                    f'<div style="font-size:12px;color:var(--muted);line-height:1.6">'
                    f'Today\'s picks will appear here after the noon workflow runs (~12pm ET). '
                    f'Once picks are locked in they stay visible until graded tonight.</div>'
                    f'</div>'
                )
        except Exception:
            pending_section = ""

        return (
            circles
            + hint
            + pending_section
            + calendar_section
            + calib_section
            + clv_feedback
            + clv_section
            + stats_table
            + roi_section
            + f'<div class="sec-header"><h2>Wins vs Losses</h2><div class="sec-line"></div></div>'
            + all_bets_section
            + f'<div class="sec-header"><h2>Results by Day</h2><div class="sec-line"></div></div>'
            + day_blocks
        )

    css = """<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#09090b;--bg2:#111113;--bg3:#18181b;--bg4:#1f1f23;--border:#27272a;--border2:#3f3f46;--text:#e4e4e7;--muted:#71717a;--dim:#52525b;--green:#4ade80;--green-bg:#052e16;--green-border:#166534;--red:#f87171;--red-bg:#2d0a0a;--red-border:#7f1d1d;--blue:#60a5fa;--blue-bg:#0c1a3a;--blue-border:#1e3a6e;--amber:#fbbf24;--amber-bg:#1c1400;--amber-border:#78350f;--accent:#a3e635;--sidebar:240px}
html{scroll-behavior:smooth}body{background:var(--bg);color:var(--text);font-family:'IBM Plex Sans',sans-serif;font-size:14px;line-height:1.6;min-height:100vh}
.sidebar{width:var(--sidebar);background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column;position:fixed;top:0;left:0;height:100vh;z-index:300;overflow-y:auto;transition:transform 0.25s ease}
.sidebar-logo{padding:20px 18px 14px;border-bottom:1px solid var(--border)}.sidebar-logo-title{font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:16px;color:var(--accent);letter-spacing:-0.5px}.sidebar-logo-sub{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:4px}
.sidebar-date{padding:10px 18px;font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:6px}
.live-dot{display:inline-block;width:6px;height:6px;background:var(--green);border-radius:50%;animation:pulse 2s infinite;flex-shrink:0}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
.sidebar-section{padding:10px 10px 4px;font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:1.5px;font-family:'IBM Plex Mono',monospace;font-weight:600}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 14px;margin:1px 6px;border-radius:8px;cursor:pointer;font-size:13px;color:var(--muted);transition:all 0.15s;user-select:none;border:1px solid transparent}
.nav-item:hover{background:var(--bg3);color:var(--text)}.nav-item.active{background:rgba(163,230,53,0.08);color:var(--accent);border-color:rgba(163,230,53,0.15)}
.nav-icon{font-size:15px;flex-shrink:0;width:18px;text-align:center}.nav-label{font-weight:500}
.nav-count{margin-left:auto;font-size:10px;font-family:'IBM Plex Mono',monospace;background:var(--bg4);padding:1px 6px;border-radius:10px;color:var(--muted)}
.nav-item.active .nav-count{background:rgba(163,230,53,0.15);color:var(--accent)}
.sidebar-stats{margin-top:auto;padding:14px 14px 20px;border-top:1px solid var(--border)}
.sidebar-stat{display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:11px}
.sidebar-stat-label{color:var(--muted)}.sidebar-stat-val{font-family:'IBM Plex Mono',monospace;font-weight:600;color:var(--text)}
.sidebar-stat-val.green{color:var(--green)}.sidebar-stat-val.amber{color:var(--amber)}
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:200}.overlay.show{display:block}
.main{margin-left:var(--sidebar);min-height:100vh}
.topbar{background:var(--bg2);border-bottom:1px solid var(--border);padding:0 1.5rem;height:52px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.topbar-left{display:flex;align-items:center;gap:12px}
.hamburger{display:none;flex-direction:column;gap:4px;cursor:pointer;padding:4px;background:none;border:none}
.hamburger span{display:block;width:20px;height:2px;background:var(--text);border-radius:2px}
.topbar-title{font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:15px;color:#fff}
.topbar-meta{font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace}
.page{display:none}.page.active{display:block}.page-inner{padding:2rem}
.hero{background:linear-gradient(135deg,rgba(163,230,53,0.06) 0%,rgba(163,230,53,0.01) 60%,transparent 100%);border:1px solid rgba(163,230,53,0.12);border-radius:16px;padding:2.5rem;margin-bottom:2rem;position:relative;overflow:hidden}
.hero::before{content:'X';position:absolute;right:2rem;top:1.5rem;font-size:80px;opacity:0.06}
.hero-eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:var(--accent);font-family:'IBM Plex Mono',monospace;font-weight:600;margin-bottom:10px}
.hero-title{font-family:'IBM Plex Mono',monospace;font-size:30px;font-weight:700;color:#fff;line-height:1.2;margin-bottom:10px}
.hero-title span{color:var(--accent)}.hero-sub{font-size:14px;color:var(--muted);max-width:520px;line-height:1.7;margin-bottom:18px}
.hero-badges{display:flex;flex-wrap:wrap;gap:8px}
.hero-badge{background:var(--bg3);border:1px solid var(--border);border-radius:20px;padding:5px 12px;font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace}
.hero-badge strong{color:var(--text)}
.home-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:2rem}
.home-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;cursor:pointer;transition:all 0.15s}
.home-card:hover{border-color:var(--border2);background:var(--bg3)}
.home-card-icon{font-size:22px;margin-bottom:8px}.home-card-title{font-weight:700;font-size:13px;color:#fff;margin-bottom:3px}
.home-card-desc{font-size:12px;color:var(--muted);line-height:1.5}
.home-card-stat{font-family:'IBM Plex Mono',monospace;font-size:20px;font-weight:700;margin-top:6px}
.home-card-stat.green{color:var(--green)}.home-card-stat.amber{color:var(--amber)}.home-card-stat.accent{color:var(--accent)}.home-card-stat.blue{color:var(--blue)}
.metrics-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:1.75rem}
.metric-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:13px 15px}
.metric-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-family:'IBM Plex Mono',monospace;margin-bottom:5px}
.metric-val{font-size:24px;font-weight:700;font-family:'IBM Plex Mono',monospace;color:#fff}
.metric-val.green{color:var(--green)}.metric-val.amber{color:var(--amber)}
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
.alert-reasoning{font-size:12.5px;color:#aaa;line-height:1.75;border-top:1px solid var(--border);padding-top:10px;margin-top:8px;font-style:italic}
.dtable{width:100%;border-collapse:collapse;font-size:12px}
.dtable th{text-align:left;padding:8px 12px;font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:600;font-family:'IBM Plex Mono',monospace;background:var(--bg3);border-bottom:1px solid var(--border)}
.dtable td{padding:8px 12px;border-bottom:1px solid var(--border);vertical-align:middle}
.dtable tr:last-child td{border-bottom:none}.dtable tr:hover td{background:rgba(255,255,255,0.015)}
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
.game-header:hover{background:var(--bg3)}.game-teams{font-weight:700;font-size:14px;color:#fff}
.game-time{font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace;margin-top:1px}
.game-right{display:flex;align-items:center;gap:7px;flex-shrink:0}
.toggle{font-size:12px;color:var(--muted);transition:transform 0.2s;margin-left:3px}
.game-block.open .toggle{transform:rotate(180deg)}.game-body{display:none;padding:0 15px 15px}
.game-block.open .game-body{display:block}
.otable{width:100%;border-collapse:collapse;margin-top:12px;font-size:12px}
.otable th{text-align:left;padding:5px 9px;font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:500;font-family:'IBM Plex Mono',monospace;border-bottom:1px solid var(--border)}
.otable td{padding:7px 9px;border-bottom:1px solid rgba(39,39,42,0.5)}
.otable tr:last-child td{border-bottom:none}.otable tr:hover td{background:rgba(255,255,255,0.015)}
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
.cb-pct.fav{color:var(--accent)}.cb-line{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);margin-top:2px}
.cb-vs{text-align:center;font-size:11px;color:var(--dim);font-family:'IBM Plex Mono',monospace}
.cb-method{font-size:10px;color:#444;margin-top:8px;line-height:1.5;border-top:1px solid rgba(163,230,53,0.08);padding-top:7px}
.best-bet{background:linear-gradient(135deg,rgba(74,222,128,0.06),rgba(74,222,128,0.01));border:1px solid rgba(74,222,128,0.22);border-radius:8px;padding:12px 14px;margin-top:10px}
.best-bet.pass{background:rgba(0,0,0,0.2);border-color:var(--border)}
.bb-header{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--green);font-family:'IBM Plex Mono',monospace;font-weight:700;margin-bottom:7px}
.best-bet.pass .bb-header{color:var(--muted)}.bb-play{font-size:14px;font-weight:700;color:#fff;margin-bottom:3px}
.best-bet.pass .bb-play{color:#777}.bb-sub{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--accent);margin-bottom:8px}
.best-bet.pass .bb-sub{color:var(--muted)}.bb-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.bbs{background:rgba(0,0,0,0.25);border-radius:6px;padding:6px 8px}
.bbs-label{font-size:10px;color:var(--muted);margin-bottom:2px;text-transform:uppercase;letter-spacing:0.5px}
.bbs-val{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;color:#fff}
.bbs-val.green{color:var(--green)}.bbs-val.c-muted{color:var(--muted)}
.pitcher-card{background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin-bottom:10px}
.pitcher-role{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-family:'IBM Plex Mono',monospace;margin-bottom:4px}
.pitcher-name{font-size:17px;font-weight:700;color:#fff;margin-bottom:2px}.pitcher-team{font-size:12px;color:var(--muted)}
footer{background:var(--bg2);border-top:1px solid var(--border);padding:1.25rem 2rem;font-size:11px;color:var(--muted);text-align:center;line-height:1.8;margin-left:var(--sidebar)}
.mobile-bottom-nav{display:none;position:fixed;bottom:0;left:0;right:0;background:var(--bg2);border-top:1px solid var(--border);z-index:400;padding:6px 0 8px}
.conf-tooltip-wrap:hover .conf-tooltip{opacity:1;pointer-events:none}
.conf-tooltip{position:absolute;bottom:calc(100% + 6px);right:0;background:#1a1a2e;border:1px solid var(--border2);border-radius:8px;padding:7px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:var(--text);white-space:nowrap;opacity:0;transition:opacity 0.15s;pointer-events:none;z-index:200;min-width:180px;line-height:1.6;box-shadow:0 4px 20px rgba(0,0,0,0.4)}
.mbn-item{display:flex;flex-direction:column;align-items:center;flex:1;cursor:pointer;padding:4px 0;color:var(--muted);transition:color 0.15s}
.mbn-item.active{color:var(--accent)}
.mbn-icon{font-size:18px;margin-bottom:2px}
.mbn-label{font-size:9px;font-family:monospace;text-transform:uppercase;letter-spacing:0.5px}
@media(max-width:768px){
  .sidebar{transform:translateX(-100%)}.sidebar.mobile-open{transform:translateX(0)}
  .main{margin-left:0}footer{margin-left:0}.hamburger{display:flex}.topbar-meta{display:none}
  .mobile-bottom-nav{display:flex}
  .main{padding-bottom:65px}
  .metrics-grid{grid-template-columns:repeat(2,1fr)}.alert-grid{grid-template-columns:1fr}
  .home-grid{grid-template-columns:1fr 1fr}.bb-stats{grid-template-columns:1fr 1fr}
  .alert-stats{grid-template-columns:1fr 1fr}.page-inner{padding:1rem}
  .hero{padding:1.5rem}.hero-title{font-size:22px}
  .otable th:nth-child(3),.otable td:nth-child(3),.otable th:nth-child(5),.otable td:nth-child(5){display:none}
}
</style>"""

    vc=value_ct; sc=sharp_ct; tot=total; bks=books; lm=len(matchups); lw=len(weather)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>MLB Sharp Lines -- {date_str}</title>
{css}
</head>
<body>
<div class="overlay" id="overlay" onclick="closeSidebar()"></div>
<div class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <div class="sidebar-logo-title">MLB Sharp Lines</div>
    <div class="sidebar-logo-sub">The Gambling Cave</div>
  </div>
  <div class="sidebar-date"><span class="live-dot"></span>{date_str}</div>
  <div class="sidebar-section">Navigation</div>
  <div class="nav-item active" onclick="showPage('home',this)"><span class="nav-icon">&#127968;</span><span class="nav-label">Home</span></div>
  <div class="nav-item" onclick="showPage('plays',this)"><span class="nav-icon">&#128293;</span><span class="nav-label">Top Value Plays</span><span class="nav-count">{vc}</span></div>
  <div class="nav-item" onclick="showPage('games',this)"><span class="nav-icon">&#9918;</span><span class="nav-label">All Games</span><span class="nav-count">{tot}</span></div>
  <div class="nav-item" onclick="showPage('matchups',this)"><span class="nav-icon">&#9889;</span><span class="nav-label">Pitcher / Batter</span><span class="nav-count">{lm}</span></div>
  <div class="nav-item" onclick="showPage('weather',this)"><span class="nav-icon">&#127780;</span><span class="nav-label">Weather</span><span class="nav-count">{lw}</span></div>
  <div class="nav-item" onclick="showPage('parlay',this)"><span class="nav-icon">&#127922;</span><span class="nav-label">Parlay Analyzer</span></div>
  <div class="nav-item" onclick="showPage('f5',this)"><span class="nav-icon">&#9201;</span><span class="nav-label">F5 & 1st Inning</span><span class="nav-count">{len(f5_plays)}</span></div>
  <div class="nav-item" onclick="showPage('trends',this)"><span class="nav-icon">&#128200;</span><span class="nav-label">Betting Trends</span></div>
  <div class="nav-item" onclick="showPage('accuracy',this)"><span class="nav-icon">&#127919;</span><span class="nav-label">Model Accuracy</span></div>
  <div class="sidebar-section" style="margin-top:8px">Today</div>
  <div class="sidebar-stats">
    <div class="sidebar-stat"><span class="sidebar-stat-label">Games</span><span class="sidebar-stat-val">{tot}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Sharp alerts</span><span class="sidebar-stat-val amber">{sc}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Value plays</span><span class="sidebar-stat-val green">{vc}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Updated</span><span class="sidebar-stat-val">{time_str}</span></div>
  </div>
</div>
<div class="main">
  <div class="topbar">
    <div class="topbar-left">
      <button class="hamburger" onclick="openSidebar()" aria-label="Open menu"><span></span><span></span><span></span></button>
      <div class="topbar-title" id="topbar-title">Home</div>
    </div>
    <div class="topbar-meta">{tot} games - {date_str}</div>
  </div>

  <div class="page active" id="page-home"><div class="page-inner">
    {best_bet_of_day()}
    <div class="hero">
      <div class="hero-eyebrow">MLB Sharp Lines Tracker</div>
      <div class="hero-title">Welcome to the <span>Gambling Cave</span></div>
      <div class="hero-sub">Enhanced model: market true odds adjusted for SP quality, bullpen fatigue, injuries, park factors, umpire zone, and wind -- all factored automatically into every best bet.</div>
      <div class="hero-badges">
        <div class="hero-badge"><strong>{tot}</strong> games today</div>
        <div class="hero-badge"><strong>{sc}</strong> sharp alerts</div>
        <div class="hero-badge"><strong>{vc}</strong> value plays</div>
        <div class="hero-badge">Updated <strong>{time_str}</strong></div>
      </div>
    </div>
    <div class="home-grid">
      <div class="home-card" onclick="showPage('plays',document.querySelectorAll('.nav-item')[1])">
        <div class="home-card-icon">&#128293;</div><div class="home-card-title">Top Value Plays</div>
        <div class="home-card-desc">Discrepancy flags and best plays ranked by adjusted edge.</div>
        <div class="home-card-stat amber">{sc} alerts</div>
      </div>
      <div class="home-card" onclick="showPage('games',document.querySelectorAll('.nav-item')[2])">
        <div class="home-card-icon">&#9918;</div><div class="home-card-title">All Games</div>
        <div class="home-card-desc">Full odds, adjusted true probability, injuries, SP stats, and best bet.</div>
        <div class="home-card-stat accent">{tot} games</div>
      </div>
      <div class="home-card" onclick="showPage('matchups',document.querySelectorAll('.nav-item')[3])">
        <div class="home-card-icon">&#9889;</div><div class="home-card-title">Pitcher / Batter</div>
        <div class="home-card-desc">Career BA, HR, K for every batter vs today's probable starters.</div>
        <div class="home-card-stat blue">{lm} games</div>
      </div>
      <div class="home-card" onclick="showPage('weather',document.querySelectorAll('.nav-item')[4])">
        <div class="home-card-icon">&#127780;</div><div class="home-card-title">Weather</div>
        <div class="home-card-desc">Wind vs field orientation -- baked into total edge calculations.</div>
        <div class="home-card-stat blue">{lw} parks</div>
      </div>
    </div>
    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:18px;font-size:13px;line-height:2;color:var(--muted)">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:700;color:var(--text);margin-bottom:8px;text-transform:uppercase;letter-spacing:1px">How the Enhanced Model Works</div>
      <strong style="color:var(--text)">Step 1 - Market true odds:</strong> Vig stripped and averaged across FD, DK, MGM, BetOnline, MyBookie, BetUS. Outliers excluded.<br>
      <strong style="color:var(--text)">Step 2 - SP adjustment:</strong> Each starter ERA vs league avg (4.20) shifts win probability up to +/-4%.<br>
      <strong style="color:var(--text)">Step 3 - Bullpen fatigue:</strong> Relief IP last 3 days -- fatigued pen shifts opponent probability up to +/-4%.<br>
      <strong style="color:var(--text)">Step 4 - Injury penalty:</strong> Key position players OUT shift win probability ~2% per player.<br>
      <strong style="color:var(--text)">Step 5 - Park factor:</strong> Applied to Over/Under true probability (Coors +28%, Petco -9%, etc).<br>
      <strong style="color:var(--text)">Step 6 - Umpire zone:</strong> Run impact from UmpScorecards shifts Over/Under probability 1% per run unit.<br>
      <strong style="color:var(--text)">Step 7 - Wind:</strong> 8+ mph blowing out/in shifts total probability up to +/-6%.<br>
      <strong style="color:var(--text)">Step 8 - Best bet:</strong> Away ML, home ML, and Over/Under all scored by edge -- highest wins.
    </div>
  </div></div>

  <div class="page" id="page-plays"><div class="page-inner">
    <div class="metrics-grid">
      <div class="metric-card"><div class="metric-label">Games</div><div class="metric-val">{tot}</div></div>
      <div class="metric-card"><div class="metric-label">Books</div><div class="metric-val">{bks}</div></div>
      <div class="metric-card"><div class="metric-label">Sharp Alerts</div><div class="metric-val amber">{sc}</div></div>
      <div class="metric-card"><div class="metric-label">Value Plays</div><div class="metric-val green">{vc}</div></div>
      <div class="metric-card"><div class="metric-label">Updated</div><div class="metric-val" style="font-size:14px">{time_str}</div></div>
    </div>
    <div class="sec-header"><h2>Sharp Alerts</h2><div class="sec-line"></div></div>
    {alert_cards()}
    <div class="sec-header"><h2>All Value Plays</h2><div class="sec-line"></div></div>
    {plays_table()}
    <div class="sec-header"><h2>Line Discrepancies</h2><div class="sec-line"></div></div>
    {disc_table()}
  </div></div>

  <div class="page" id="page-games"><div class="page-inner">{game_blocks()}{tracking_cards()}</div></div>

  <div class="page" id="page-matchups"><div class="page-inner">
    <div style="margin-bottom:1.5rem">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:700;color:#fff;margin-bottom:6px">Pitcher / Batter Matchups</div>
      <div style="font-size:13px;color:var(--muted)">Career all-time stats for each batter vs today's probable starting pitcher. Min 3 AB. Green = batter owns this pitcher historically.</div>
    </div>
    {matchup_page()}
  </div></div>

  <div class="page" id="page-weather"><div class="page-inner">
    <div style="margin-bottom:1.5rem">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:700;color:#fff;margin-bottom:6px">Weather and Wind</div>
      <div style="font-size:13px;color:var(--muted)">Wind direction vs field orientation. Blowing out = Over lean. Blowing in = Under lean. Wind already factored into model totals calculations.</div>
    </div>
    {weather_page()}
  </div></div>

  <div class="page" id="page-f5"><div class="page-inner">
    {f5_page()}
  </div></div>

  <div class="page" id="page-trends"><div class="page-inner">
    {betting_trends_page(results_data)}
  </div></div>

  <div class="page" id="page-accuracy"><div class="page-inner">
    {accuracy_page(results_data)}
  </div></div>

  <div class="page" id="page-parlay"><div class="page-inner">
    <div style="margin-bottom:1.5rem">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:700;color:#fff;margin-bottom:6px">&#127922; Parlay Analyzer</div>
      <div style="font-size:13px;color:var(--muted)">Select up to 4 legs from today's plays. The analyzer calculates true parlay probability vs book price and shows whether the parlay has positive or negative EV.</div>
    </div>
    <div id="parlay-legs" style="display:flex;flex-direction:column;gap:8px;margin-bottom:1rem"></div>
    <div style="display:flex;gap:8px;margin-bottom:1.5rem">
      <input id="parlay-odds" type="text" placeholder="Parlay price (e.g. +600)" style="background:var(--bg3);border:1px solid var(--border2);border-radius:8px;padding:8px 12px;color:var(--text);font-family:monospace;font-size:14px;flex:1"/>
      <button onclick="calcParlay()" style="background:var(--accent);color:#000;border:none;border-radius:8px;padding:8px 18px;font-weight:700;font-family:monospace;cursor:pointer">Calculate</button>
    </div>
    <div id="parlay-result" style="display:none;background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:1.25rem"></div>
    <div class="sec-header"><h2>Add Legs from Today</h2><div class="sec-line"></div></div>
    <div id="parlay-available" style="display:flex;flex-direction:column;gap:6px">{parlay_legs_html(all_plays)}</div>
  </div></div>
</div>

<!-- MOBILE BOTTOM NAV -->
<nav class="mobile-bottom-nav">
  <div class="mbn-item" onclick="showPage('home',null);updateBottomNav('home')">
    <div class="mbn-icon">&#127968;</div><div class="mbn-label">Home</div>
  </div>
  <div class="mbn-item" onclick="showPage('plays',null);updateBottomNav('plays')">
    <div class="mbn-icon">&#128293;</div><div class="mbn-label">Plays</div>
  </div>
  <div class="mbn-item" onclick="showPage('games',null);updateBottomNav('games')">
    <div class="mbn-icon">&#9918;</div><div class="mbn-label">Games</div>
  </div>
  <div class="mbn-item" onclick="showPage('matchups',null);updateBottomNav('matchups')">
    <div class="mbn-icon">&#9889;</div><div class="mbn-label">Matchups</div>
  </div>
  <div class="mbn-item" onclick="showPage('accuracy',null);updateBottomNav('accuracy')">
    <div class="mbn-icon">&#127919;</div><div class="mbn-label">Record</div>
  </div>
</nav>

<footer>MLB Sharp Lines - The Gambling Cave - {date_str} - Enhanced model: SP quality, bullpen fatigue, injuries, park factors, umpire zone, wind - Gamble responsibly</footer>

<script>
  // ── AUTO REFRESH every 5 minutes ──
  // Keeps the site current without manual reload
  setTimeout(function(){{ window.location.reload(); }}, 5 * 60 * 1000);

  // ── NOTIFICATION BADGE ──
  (function(){{
    const playCount = {value_ct};
    if(playCount > 0){{
      document.title = playCount + ' plays | The Gambling Cave';
    }}
  }})();

  // ── PAGE NAVIGATION ──
  function showPage(name,el){{
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
    document.getElementById('page-'+name).classList.add('active');
    if(el)el.classList.add('active');
    const t={{home:'Home',plays:'Top Value Plays',games:'All Games',matchups:'Pitcher / Batter',weather:'Weather & Wind',parlay:'Parlay Analyzer',f5:'F5 & 1st Inning',trends:'Betting Trends',accuracy:'Model Accuracy'}};
    document.getElementById('topbar-title').textContent=t[name]||name;
    window.scrollTo(0,0);closeSidebar();
  }}
  function updateBottomNav(name){{
    document.querySelectorAll('.mbn-item').forEach(i=>i.classList.remove('active'));
    const items=document.querySelectorAll('.mbn-item');
    const map={{home:0,plays:1,games:2,matchups:3,accuracy:4}};
    if(map[name]!==undefined) items[map[name]].classList.add('active');
  }}
  function toggleGame(el){{el.classList.toggle('open');}}
  function openSidebar(){{document.getElementById('sidebar').classList.add('mobile-open');document.getElementById('overlay').classList.add('show');}}
  function closeSidebar(){{document.getElementById('sidebar').classList.remove('mobile-open');document.getElementById('overlay').classList.remove('show');}}

  // ── COUNTDOWN TIMERS ──
  function updateCountdowns(){{
    document.querySelectorAll('[data-commence]').forEach(el=>{{
      const iso=el.getAttribute('data-commence');
      if(!iso) return;
      const diff=new Date(iso)-new Date();
      if(diff<=0){{el.textContent=''; return;}}
      const h=Math.floor(diff/3600000);
      const m=Math.floor((diff%3600000)/60000);
      el.textContent=h>0?`in ${{h}}h ${{m}}m`:`in ${{m}}m`;
    }});
  }}
  updateCountdowns();
  setInterval(updateCountdowns,60000);

  // ── PARLAY ANALYZER ──
  let parlayLegs=[];
  function addParlayLeg(game,play,price,truePct){{
    if(parlayLegs.length>=4){{alert('Max 4 legs');return;}}
    if(parlayLegs.find(l=>l.game===game)){{alert('Already added');return;}}
    parlayLegs.push({{game,play,price,truePct:parseFloat(truePct)}});
    renderParlayLegs();
  }}
  function removeLeg(i){{parlayLegs.splice(i,1);renderParlayLegs();}}
  function renderParlayLegs(){{
    const el=document.getElementById('parlay-legs');
    if(!parlayLegs.length){{el.innerHTML='<div style="color:var(--muted);font-size:13px">No legs added yet. Click + on any play below.</div>';return;}}
    el.innerHTML=parlayLegs.map((l,i)=>
      `<div style="display:flex;align-items:center;gap:10px;background:var(--bg3);border-radius:8px;padding:8px 12px">
        <span style="font-size:12px;flex:1"><strong style="color:var(--text)">${{l.play}}</strong> <span style="color:var(--muted)">${{l.game}}</span></span>
        <span style="font-family:monospace;color:var(--accent)">${{l.price}}</span>
        <span style="font-family:monospace;color:var(--muted);font-size:11px">${{l.truePct}}% true</span>
        <button onclick="removeLeg(${{i}})" style="background:var(--red-bg);border:1px solid var(--red-border);color:var(--red);border-radius:4px;padding:2px 8px;cursor:pointer;font-size:11px">✕</button>
      </div>`
    ).join('');
  }}
  function calcParlay(){{
    if(!parlayLegs.length){{alert('Add at least 1 leg');return;}}
    const bookOddsStr=document.getElementById('parlay-odds').value.trim();
    // True probability = product of all legs' true probabilities
    const trueProb=parlayLegs.reduce((acc,l)=>acc*(l.truePct/100),1);
    const truePct=Math.round(trueProb*10000)/100;
    // Fair parlay odds
    const fairDecimal=1/trueProb;
    const fairAmerican=fairDecimal>=2?`+${{Math.round((fairDecimal-1)*100)}}`:`-${{Math.round(100/(fairDecimal-1))}}`;
    let evHtml='';
    if(bookOddsStr){{
      const bookOddsNum=parseFloat(bookOddsStr.replace('+',''));
      const bookImp=bookOddsNum>0?100/(bookOddsNum+100):Math.abs(bookOddsNum)/(Math.abs(bookOddsNum)+100);
      const ev=((trueProb-bookImp)*100).toFixed(1);
      const evCol=parseFloat(ev)>0?'var(--green)':'var(--red)';
      evHtml=`<div style="margin-top:10px;padding:10px;background:rgba(0,0,0,0.3);border-radius:6px">
        <span style="font-size:11px;color:var(--muted)">Book implied: </span><span style="font-family:monospace">${{(bookImp*100).toFixed(1)}}%</span>
        <span style="font-size:11px;color:var(--muted);margin-left:12px">EV: </span>
        <span style="font-family:monospace;color:${{evCol}};font-weight:700">${{parseFloat(ev)>0?'+':''}}${{ev}}%</span>
        <span style="font-size:11px;color:var(--muted);margin-left:8px">(${{parseFloat(ev)>0?'POSITIVE EV - TAKE IT':'NEGATIVE EV - PASS'}})</span>
      </div>`;
    }}
    document.getElementById('parlay-result').style.display='block';
    document.getElementById('parlay-result').innerHTML=`
      <div style="font-family:monospace;font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:10px">${{parlayLegs.length}}-Leg Parlay Analysis</div>
      <div style="display:flex;gap:16px;flex-wrap:wrap">
        <div class="metric-card" style="min-width:110px;text-align:center"><div class="metric-label">True Prob</div><div class="metric-val" style="font-size:20px">${{truePct}}%</div></div>
        <div class="metric-card" style="min-width:110px;text-align:center"><div class="metric-label">Fair Odds</div><div class="metric-val" style="font-size:20px;color:var(--accent)">${{fairAmerican}}</div></div>
        <div class="metric-card" style="min-width:110px;text-align:center"><div class="metric-label">Legs</div><div class="metric-val" style="font-size:20px">${{parlayLegs.length}}</div></div>
      </div>
      ${{evHtml}}
    `;
  }}

  // ── ROI TRACKER ──
  function calcROI(){{
    const unit=parseFloat(document.getElementById('roi-unit').value)||100;
    const rows=document.querySelectorAll('.roi-bet-row');
    let profit=0; let history=[0];
    rows.forEach(row=>{{
      const res=row.getAttribute('data-result');
      const priceStr=row.getAttribute('data-price');
      if(!priceStr||res==='P') return;
      const price=parseFloat(priceStr.replace('+',''));
      const winAmt=price>0?(price/100)*unit:unit*(100/Math.abs(price));
      if(res==='W') profit+=winAmt;
      else profit-=unit;
      history.push(Math.round(profit*100)/100);
    }});
    document.getElementById('roi-total').textContent=(profit>=0?'+':'')+profit.toFixed(2);
    document.getElementById('roi-total').style.color=profit>=0?'var(--green)':'var(--red)';
    document.getElementById('roi-units').textContent=(profit/unit>=0?'+':'')+(profit/unit).toFixed(1)+' units';
    // Simple sparkline
    if(history.length>1){{
      const max=Math.max(...history); const min=Math.min(...history);
      const range=max-min||1;
      const w=300; const h=60;
      const pts=history.map((v,i)=>{{
        const x=i*(w/(history.length-1));
        const y=h-((v-min)/range*h);
        return `${{x}},${{y}}`;
      }}).join(' ');
      document.getElementById('roi-chart').innerHTML=
        `<svg viewBox="0 0 ${{w}} ${{h}}" width="100%" height="60" xmlns="http://www.w3.org/2000/svg">
          <polyline points="${{pts}}" fill="none" stroke="${{profit>=0?'#4ade80':'#f87171'}}" stroke-width="2" stroke-linejoin="round"/>
        </svg>`;
    }}
  }}

  renderParlayLegs();
</script>
</body>
</html>"""


# =============================================================
# MAIN
# =============================================================
def main():
    if not ODDS_API_KEY:
        print("ERROR: ODDS_API_KEY not set"); sys.exit(1)

    now_et   = datetime.now(EASTERN)
    date_str = now_et.strftime("%B %d, %Y")
    time_str = now_et.strftime("%-I:%M %p ET")
    mlb_date = now_et.strftime("%Y-%m-%d")

    try:
        games_raw, tracking_games = fetch_odds()
    except Exception as e:
        print(f"ERROR fetching odds: {e}"); sys.exit(1)

    if not games_raw and not tracking_games:
        with open("index.html","w",encoding="utf-8") as f:
            f.write(f"<html><body style='background:#09090b;color:#e4e4e7;font-family:monospace;"
                    f"padding:3rem;text-align:center'><h1 style='color:#a3e635'>MLB Sharp Lines</h1>"
                    f"<p style='color:#71717a;margin-top:1rem'>No upcoming games on {date_str}.</p></body></html>")
        return

    try:
        matchups = build_matchup_data(games_raw, mlb_date)
    except Exception as e:
        print(f"Matchup error: {e}"); matchups=[]

    # Weather needs all games (pre-game + tracking) for stadium lookups
    all_games_for_weather = games_raw + tracking_games
    try:
        weather = fetch_weather_for_games(all_games_for_weather)
    except Exception as e:
        print(f"Weather error: {e}"); weather={}

    mlb_sched_data = mlb_get("/schedule",{"sportId":1,"date":mlb_date,"hydrate":"officials,team"})
    mlb_sched_games = []
    if mlb_sched_data:
        for db in mlb_sched_data.get("dates",[]):
            mlb_sched_games.extend(db.get("games",[]))

    # Load opening lines snapshot (saved by 9am workflow)
    opening_lines = load_opening_lines()
    if opening_lines:
        print(f"Loaded opening_lines.json: {len(opening_lines)} games")
    else:
        print("No opening_lines.json found -- line movement signals disabled today")

    analyzed = []
    for g in games_raw:
        print(f"Analyzing {g['away_team']} @ {g['home_team']}...")
        try:
            ctx    = fetch_game_context(g, matchups, weather, mlb_sched_games, opening_lines)
            result = analyze_game(g, ctx)
            if result: analyzed.append(result)
        except Exception as e:
            print(f"  Error: {e}")

    signal_order = {"fire":0,"sharp":1,"value":2,"watch":3,"pass":4}
    analyzed.sort(key=lambda x:(x["date_sort"],signal_order.get(x["signal"],3)))

    # Build all_noon_data: every game analyzed today keyed by "Away @ Home"
    # This is passed directly into build_html so tracking_cards always has data
    # regardless of whether noon_analysis.json exists yet.
    all_noon_data = {}
    for g in analyzed:
        all_noon_data[g["game"]] = {
            "play":        g["bet_play"],
            "price":       g["bet_sub"].split(" at ")[0] if " at " in g["bet_sub"] else g["bet_sub"],
            "book":        g["bet_sub"].split(" at ")[1] if " at " in g["bet_sub"] else "",
            "is_pass":     g["bet_is_pass"],
            "edge":        g["bet_edge"],
            "away_true":   g["away_true"],
            "home_true":   g["home_true"],
            "away_fair":   g["away_fair"],
            "home_fair":   g["home_fair"],
            "signal":      g["signal"],
            "signal_label":g["signal_label"],
        }
    # Merge in noon_analysis.json so the 4pm run can see games
    # that were pre-game at noon but are now in tracking
    if os.path.exists("noon_analysis.json"):
        try:
            with open("noon_analysis.json") as f:
                existing_na = json.load(f)
            if existing_na.get("date") == mlb_date:
                for gk, gdata in existing_na.get("games",{}).items():
                    if gk not in all_noon_data:
                        all_noon_data[gk] = gdata
                        print(f"  Restored tracking data for: {gk}")
        except Exception as e:
            print(f"  noon_analysis.json read error: {e}")

    # Load results.json for accuracy tracking
    results_data = {"days": []}
    try:
        if os.path.exists("results.json"):
            with open("results.json") as f:
                results_data = json.load(f)
            print(f"Loaded results.json: {sum(len(d.get('bets',[])) for d in results_data.get('days',[]))} bets")
        else:
            print("No results.json found -- accuracy tab will be empty")
    except Exception as e:
        print(f"results.json error: {e}")

    # Fetch public betting percentages (Action Network)
    public_betting = fetch_public_betting(mlb_date)

    # Build pending picks for display — show everything in picks.json as pending
    # This is purely for display, not for grading logic
    pending_picks_for_display = []
    graded_games_today = {b.get("game","") for day in results_data.get("days",[]) for b in day.get("bets",[])}

    # PRIMARY: read from picks.json which has the locked-in noon picks
    if os.path.exists("picks.json"):
        try:
            with open("picks.json") as f:
                ep = json.load(f)
            # Show picks from today OR yesterday (in case of overnight run)
            if ep.get("date") in (mlb_date, (datetime.now(EASTERN) - timedelta(days=1)).strftime("%Y-%m-%d")):
                for b in ep.get("bets",[]):
                    if b.get("game","") not in graded_games_today:
                        pending_picks_for_display.append(b)
                print(f"  Pending from picks.json: {len(pending_picks_for_display)} bets")
        except Exception as e:
            print(f"  picks.json read error: {e}")

    # SECONDARY: add any current pre-game picks not already in picks.json
    existing_games = {p["game"] for p in pending_picks_for_display}
    for g in analyzed:
        if g["game"] in existing_games or g["game"] in graded_games_today:
            continue
        if not g["bet_is_pass"] and "No Play" not in g["bet_play"]:
            try:
                edge_num = float(str(g["bet_edge"]).replace("+","").replace("%",""))
                if edge_num > 0:
                    pending_picks_for_display.append({
                        "game":   g["game"],
                        "play":   g["bet_play"],
                        "price":  g["bet_sub"].split(" at ")[0] if " at " in g["bet_sub"] else g["bet_sub"],
                        "book":   g["bet_sub"].split(" at ")[1] if " at " in g["bet_sub"] else "",
                        "edge":   g["bet_edge"],
                        "signal": g["signal"],
                    })
            except Exception:
                pass

    print(f"Pending picks for display: {len(pending_picks_for_display)}")

    # Fetch F5 and NRFI/YRFI odds
    print("Fetching F5 / NRFI odds...")
    try:
        f5_raw = fetch_f5_nrfi_odds()
        matchups_by_game = {m["game"]: m for m in matchups}
        f5_plays = analyze_f5_nrfi(f5_raw, matchups_by_game)
        print(f"  F5/NRFI plays found: {len(f5_plays)}")
    except Exception as e:
        print(f"  F5/NRFI error: {e}")
        f5_plays = []

    html = build_html(analyzed, matchups, weather, results_data, tracking_games, all_noon_data, public_betting, pending_picks_for_display, f5_plays, date_str, time_str)
    with open("index.html","w",encoding="utf-8") as f:
        f.write(html)

    # Save picks.json — skip during overnight nightly rebuilds
    is_nightly_rebuild = os.environ.get("NIGHTLY_REBUILD","") == "1"

    # Always build noon_analysis (tracking cards need it regardless)
    noon_analysis = {"date": mlb_date, "games": {}}
    if os.path.exists("noon_analysis.json"):
        try:
            with open("noon_analysis.json") as f:
                existing_na = json.load(f)
            if existing_na.get("date") == mlb_date:
                noon_analysis["games"] = existing_na.get("games", {})
        except Exception:
            pass

    for g in analyzed:
        noon_analysis["games"][g["game"]] = {
            "play":        g["bet_play"],
            "price":       g["bet_sub"].split(" at ")[0] if " at " in g["bet_sub"] else g["bet_sub"],
            "book":        g["bet_sub"].split(" at ")[1] if " at " in g["bet_sub"] else "",
            "is_pass":     g["bet_is_pass"],
            "edge":        g["bet_edge"],
            "away_true":   g["away_true"],
            "home_true":   g["home_true"],
            "away_fair":   g["away_fair"],
            "home_fair":   g["home_fair"],
            "signal":      g["signal"],
            "signal_label":g["signal_label"],
        }

    with open("noon_analysis.json","w",encoding="utf-8") as f:
        json.dump(noon_analysis, f, indent=2)

    if not is_nightly_rebuild:
        # Build picks.json — merge with existing so 4pm preserves noon picks
        picks = {"date": mlb_date, "date_display": date_str, "bets": []}
        existing_picks_by_game = {}
        if os.path.exists("picks.json"):
            try:
                with open("picks.json") as f:
                    existing_picks = json.load(f)
                if existing_picks.get("date") == mlb_date:
                    for b in existing_picks.get("bets", []):
                        existing_picks_by_game[b.get("game","")] = b
                    print(f"  Loaded {len(existing_picks_by_game)} existing picks to merge")
            except Exception:
                pass

        for g in analyzed:
            if g["game"] in existing_picks_by_game:
                continue  # locked from noon run
            if not g["bet_is_pass"] and "No Play" not in g["bet_play"]:
                try:
                    edge_num = float(str(g["bet_edge"]).replace("+","").replace("%",""))
                    if edge_num <= 0:
                        continue
                except Exception:
                    pass
                bet_type   = "total" if "Runs" in g["bet_play"] else "ml"
                side       = None; total_line = None
                if bet_type == "total":
                    parts      = g["bet_play"].split()
                    side       = parts[0] if len(parts)>0 else None
                    total_line = float(parts[1]) if len(parts)>1 else None
                picks["bets"].append({
                    "game":       g["game"],
                    "away":       g["away"],
                    "home":       g["home"],
                    "away_id":    MLB_IDS.get(g["away"]),
                    "home_id":    MLB_IDS.get(g["home"]),
                    "play":       g["bet_play"],
                    "price":      g["bet_sub"].split(" at ")[0] if " at " in g["bet_sub"] else g["bet_sub"],
                    "book":       g["bet_sub"].split(" at ")[1] if " at " in g["bet_sub"] else "",
                    "type":       bet_type,
                    "pick_team":  g["away"] if g["away"] in g["bet_play"] else (g["home"] if bet_type=="ml" else None),
                    "side":       side,
                    "total_line": total_line,
                    "edge":       g["bet_edge"],
                    "signal":     g["signal"],
                })

        # Add back preserved picks for started games
        for game_key, existing_bet in existing_picks_by_game.items():
            if not any(b["game"] == game_key for b in picks["bets"]):
                picks["bets"].append(existing_bet)
                print(f"  Preserved pick for started game: {game_key}")

        with open("picks.json","w",encoding="utf-8") as f:
            json.dump(picks, f, indent=2)
        print(f"Saved picks.json: {len(picks['bets'])} best bets")

    # Save to permanent picks history (never overwritten, accumulates forever)
    history_path = "picks_history.json"
    history = {"picks": []}
    if os.path.exists(history_path):
        try:
            with open(history_path) as f:
                history = json.load(f)
        except Exception:
            pass

    # Only add today's picks if this date isn't already in history
    existing_dates = {p.get("date") for p in history.get("picks",[])}
    if mlb_date not in existing_dates:
        for b in picks["bets"]:
            history["picks"].append({
                "date":       mlb_date,
                "date_display": date_str,
                "game":       b["game"],
                "play":       b["play"],
                "price":      b["price"],
                "book":       b["book"],
                "type":       b["type"],
                "edge":       b["edge"],
                "signal":     b["signal"],
            })
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        print(f"Saved picks_history.json: {len(history['picks'])} total picks on record")
    else:
        print(f"picks_history.json already has picks for {mlb_date} -- not overwriting")

if __name__ == "__main__":
    main()
