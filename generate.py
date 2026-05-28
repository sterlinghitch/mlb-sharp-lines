"""
MLB Sharp Lines -- Daily Generator
Enhanced model v2: park factors, SP quality, bullpen fatigue,
injuries, umpire zone, wind. Free tier only.
"""
import os, sys, time, requests
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
    all_games = r.json()
    now_et = datetime.now(EASTERN)
    today_et = now_et.date()
    yesterday_et = today_et - timedelta(days=1)
    live_yesterday = fetch_live_mlb_games(yesterday_et.strftime("%Y-%m-%d"))
    games = []
    for g in all_games:
        try:
            start = datetime.fromisoformat(g["commence_time"].replace("Z","+00:00"))
            start_date = start.astimezone(EASTERN).date()
            if start_date >= today_et:
                games.append(g)
            elif start_date == yesterday_et:
                aid = MLB_IDS.get(g["away_team"])
                hid = MLB_IDS.get(g["home_team"])
                if aid and hid and (aid,hid) in live_yesterday:
                    print(f"  Live past-midnight: {g['away_team']} @ {g['home_team']}")
                    games.append(g)
                else:
                    print(f"  Skipping finished: {g['away_team']} @ {g['home_team']}")
            else:
                print(f"  Skipping old: {g['away_team']} @ {g['home_team']}")
        except Exception:
            games.append(g)
    print(f"Got {len(all_games)} total, {len(games)} upcoming")
    return games


# =============================================================
# MLB DATA FETCHERS
# =============================================================
def fetch_pitcher_stats(pitcher_id):
    if not pitcher_id:
        return {"name":"TBD","era":"N/A","whip":"N/A","k9":"N/A","id":None,"quality":0.0}
    data = mlb_get(f"/people/{pitcher_id}",
                   {"hydrate":"stats(group=pitching,type=season,season=2026)"})
    if not data:
        return {"name":"TBD","era":"N/A","whip":"N/A","k9":"N/A","id":pitcher_id,"quality":0.0}
    person = data.get("people",[{}])[0]
    name = person.get("fullName","TBD")
    era = whip = k9 = "N/A"
    for sg in person.get("stats",[]):
        splits = sg.get("splits",[])
        if not splits: continue
        s = splits[0].get("stat",{})
        era  = str(s.get("era","N/A"))
        whip = str(s.get("whip","N/A"))
        ip   = float(s.get("inningsPitched",0) or 0)
        k    = float(s.get("strikeOuts",0) or 0)
        k9   = f"{round(k/ip*9,1)}" if ip>0 else "N/A"
    quality = 0.0
    try:
        quality = max(-0.08, min(0.08, (4.20 - float(era)) * 0.04))
    except Exception: pass
    return {"name":name,"era":era,"whip":whip,"k9":k9,"id":pitcher_id,"quality":round(quality,3)}

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
        return {"games":last5,"wins":wins,"losses":len(last5)-wins}
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
# WEATHER
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
def build_matchup_data(odds_games, date_str):
    print("Fetching matchup data...")
    mlb_sched = mlb_get("/schedule",{"sportId":1,"date":date_str,"hydrate":"probablePitcher,lineups,team"})
    mlb_games = [] if not mlb_sched else [
        g for db in mlb_sched.get("dates",[]) for g in db.get("games",[])
        if g.get("status",{}).get("abstractGameState","") not in ("Final","Live")
    ]
    mlb_lookup = {}
    for g in mlb_games:
        aid = g.get("teams",{}).get("away",{}).get("team",{}).get("id")
        hid = g.get("teams",{}).get("home",{}).get("team",{}).get("id")
        if aid and hid: mlb_lookup[(aid,hid)] = g

    matchups = []
    for og in odds_games:
        away_name = og["away_team"]; home_name = og["home_team"]
        away_id = MLB_IDS.get(away_name); home_id = MLB_IDS.get(home_name)
        if not away_id or not home_id: continue
        mlb_game = mlb_lookup.get((away_id,home_id)) or mlb_lookup.get((home_id,away_id))
        away_p_raw = mlb_game.get("teams",{}).get("away",{}).get("probablePitcher") if mlb_game else None
        home_p_raw = mlb_game.get("teams",{}).get("home",{}).get("probablePitcher") if mlb_game else None
        away_pitcher = fetch_pitcher_stats(away_p_raw["id"] if away_p_raw else None)
        home_pitcher = fetch_pitcher_stats(home_p_raw["id"] if home_p_raw else None)

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

        matchups.append({"game":f"{away_name} @ {home_name}",
                         "away":away_name,"home":home_name,
                         "away_pitcher":away_pitcher,"home_pitcher":home_pitcher,
                         "away_batters":away_vs_hp,"home_batters":home_vs_ap,
                         "away_source":away_source,"home_source":home_source,
                         "away_last5":away_last5,"home_last5":home_last5})
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
        bet_play="Pass -- near coin flip"; bet_sub="If forced: use BetOnline for lowest vig"
        bet_edge="None"; bet_fair="N/A"; bet_true="N/A"; bet_is_pass=True
    else:
        best_c   = max(candidates,key=lambda c:c["edge_val"])
        bet_play = best_c["play"]; bet_sub = best_c["sub"]
        bet_edge = best_c["edge_label"]; bet_fair = best_c["fair_line"]
        bet_true = best_c["true_pct"]; bet_is_pass = best_c["edge_val"]<-3

    discs = []
    for team,gap,best,worst,pk in [
        (away,away_gap,best_away,worst_away,"away_price"),
        (home,home_gap,best_home,worst_home,"home_price"),
    ]:
        if gap>=8:
            discs.append({"team":team,"best_price":fmt(best[pk]),"worst_price":fmt(worst[pk]),
                          "gap":gap,"best_book":best["name"],"worst_book":worst["name"]})

    value_play = None
    if signal in ("fire","value","sharp") and not bet_is_pass:
        fav_t = home if adj_ht>adj_at else away
        fav_p = max(adj_at,adj_ht); dog_p = min(adj_at,adj_ht)
        dog_t = away if fav_t==home else home
        dp    = best_away["away_price"] if dog_t==away else best_home["home_price"]
        db    = best_away["name"]       if dog_t==away else best_home["name"]
        di    = american_to_implied(dp); de = round((dog_p-(di or 0))*100,1)
        if de>0:
            vt=dog_t; vp=fmt(dp); vb=db; vtp=round(dog_p*100,1); vi=round((di or 0)*100,1); ve=de
        else:
            fp=best_home["home_price"] if fav_t==home else best_away["away_price"]
            fb=best_home["name"]       if fav_t==home else best_away["name"]
            fi=american_to_implied(fp)
            vt=fav_t; vp=fmt(fp); vb=fb; vtp=round(fav_p*100,1); vi=round((fi or 0)*100,1)
            ve=round((fav_p-(fi or 0))*100,1)
        # Build reasoning string
        reason_parts = [f"{vt} at {vp} ({vtp}% true vs {vi}% implied -- {'+' if ve>0 else ''}{ve}% edge)."]
        if adjustments:
            reason_parts.append("Adj: " + " | ".join(f"{a[0]}" for a in adjustments[:2]) + ".")
        if split_market: reason_parts.append("Split market -- sharp divergence across books.")
        elif max(away_gap,home_gap)>=15:
            reason_parts.append(f"Line discrepancy {max(away_gap,home_gap)}c -- shop books.")
        value_play = {"game":f"{away} @ {home}","signal":signal,"team":vt,
                      "best_price":vp,"best_book":vb,"true_pct":vtp,
                      "implied_pct":vi,"edge":ve,"reasoning":" ".join(reason_parts)}

    try:
        t = datetime.fromisoformat(game.get("commence_time","").replace("Z","+00:00")).astimezone(EASTERN)
        time_display=t.strftime("%-I:%M %p ET"); date_et=t.strftime("%A, %B %d"); date_sort=t.strftime("%Y-%m-%d")
    except Exception:
        time_display=""; date_et="Today"; date_sort="9999-99-99"

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
        "best_away":best_away,"best_home":best_home,
        "worst_away":worst_away,"worst_home":worst_home,
        "away_gap":away_gap,"home_gap":home_gap,"props":[],
        "away_pitcher":context.get("away_pitcher",{}),
        "home_pitcher":context.get("home_pitcher",{}),
        "away_injuries":context.get("away_injuries",[]),
        "home_injuries":context.get("home_injuries",[]),
        "away_bullpen":context.get("away_bullpen",{}),
        "home_bullpen":context.get("home_bullpen",{}),
        "umpire":context.get("umpire",{}),
    }

def fetch_game_context(game, matchup_data, weather_data, mlb_schedule_games):
    away=game["away_team"]; home=game["home_team"]
    away_id=MLB_IDS.get(away); home_id=MLB_IDS.get(home)
    m=next((x for x in matchup_data if x["game"]==f"{away} @ {home}"),{})
    mlb_gid=None
    for g in mlb_schedule_games:
        aid=g.get("teams",{}).get("away",{}).get("team",{}).get("id")
        hid=g.get("teams",{}).get("home",{}).get("team",{}).get("id")
        if aid==away_id and hid==home_id: mlb_gid=g.get("gamePk"); break
    return {
        "away_pitcher": m.get("away_pitcher",{}),
        "home_pitcher": m.get("home_pitcher",{}),
        "away_injuries":fetch_injuries(away_id),
        "home_injuries":fetch_injuries(home_id),
        "away_bullpen": fetch_bullpen_fatigue(away_id),
        "home_bullpen": fetch_bullpen_fatigue(home_id),
        "umpire":       fetch_umpire(mlb_gid),
        "weather":      weather_data.get(home,{}),
    }


# =============================================================
# HTML BUILDER
# =============================================================
def build_html(analyzed_games, matchups, weather, date_str, time_str):
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

    def alert_cards():
        top=[p for p in all_plays if p["signal"] in ("fire","sharp","value")][:4]
        if not top: return '<p style="color:var(--muted);font-size:13px;padding:1rem 0">No sharp alerts today.</p>'
        html='<div class="alert-grid">'
        for p in top:
            sig=p["signal"]; ec="green" if (p.get("edge") or 0)>0 else "red"
            ap=p["best_price"]; ab=p["best_book"]; at=p.get("true_pct","?"); ai=p.get("implied_pct","?")
            html+=(f'<div class="alert-card {alert_cls.get(sig,"value")}">'
                   f'<span class="badge {sig_cls.get(sig,"b-value")}">{sig.upper()}</span>'
                   f'<div class="alert-game">{p["game"]}</div>'
                   f'<div class="alert-rec">{p["team"]} -- {ap} @ {ab}</div>'
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
        rows=""
        for p in all_plays:
            ec="c-green" if (p.get("edge") or 0)>0 else "c-red"
            rows+=(f'<tr><td>{p["game"]}</td><td class="mono">{p["team"]} ML</td>'
                   f'<td><span class="pill pill-n">{p["best_price"]}</span></td>'
                   f'<td class="c-accent mono" style="font-size:11px">{p["best_book"]}</td>'
                   f'<td class="mono">{p["implied_pct"]}%</td><td class="mono">{p["true_pct"]}%</td>'
                   f'<td class="mono {ec}">{("+" if (p.get("edge") or 0)>0 else "")}{p.get("edge","N/A")}%</td>'
                   f'<td><span class="badge {sig_cls.get(p["signal"],"b-watch")}" style="margin:0">{p["signal"].upper()}</span></td></tr>')
        return (f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:1.75rem">'
                f'<table class="dtable"><thead><tr><th>Game</th><th>Play</th><th>Best Line</th><th>Best Book</th>'
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
        mlookup={m["game"]:m for m in matchups}
        html=""
        for i,g in enumerate(analyzed_games):
            sig=g["signal"]; bc=sig_cls.get(sig,"b-watch")
            open_cls="open" if i<2 else ""
            sig_badge=(f'<span class="badge {bc}" style="font-size:9px">{g["signal_label"]}</span>'
                       if g["signal_label"] else "")
            away_fav="fav" if g["away_true"]>g["home_true"] else ""
            home_fav="fav" if g["home_true"]>g["away_true"] else ""
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
                      f'</div></div>')

            html+=(day_header+
                   f'<div class="game-block {open_cls}" onclick="toggleGame(this)">'
                   f'<div class="game-header">'
                   f'<div><div class="game-teams">{g["away"]} @ {g["home"]}</div>'
                   f'<div class="game-time">{g["time"]}</div></div>'
                   f'<div class="game-right">{sig_badge}<span class="toggle">v</span></div>'
                   f'</div>'
                   f'<div class="game-body">'
                   f'{pitcher_strip}{ump_strip}{inj_row}{adj_row}{adj_note}'
                   f'<table class="otable" style="margin-top:10px">'
                   f'<thead><tr><th>Book</th><th>{g["away"]}</th><th>Implied%</th>'
                   f'<th>{g["home"]}</th><th>Implied%</th><th>Total O/U</th></tr></thead>'
                   f'<tbody>{book_rows}</tbody></table>'
                   f'<div class="claude-box">'
                   f'<div class="cb-header">Adjusted True Odds</div>'
                   f'<div class="cb-grid">'
                   f'<div class="cb-team"><div class="cb-name">{g["away"]}</div>'
                   f'<div class="cb-pct {away_fav}">{g["away_true"]}%</div>'
                   f'<div class="cb-line">Fair: {g["away_fair"]}</div></div>'
                   f'<div class="cb-vs">vs</div>'
                   f'<div class="cb-team"><div class="cb-name">{g["home"]}</div>'
                   f'<div class="cb-pct {home_fav}">{g["home_true"]}%</div>'
                   f'<div class="cb-line">Fair: {g["home_fair"]}</div></div>'
                   f'</div>'
                   f'<div class="cb-method">Adjusted for: SP ERA/WHIP, bullpen fatigue, injuries, park factor, umpire zone, wind.</div>'
                   f'</div>'
                   f'{last5_section}'
                   f'{best_bet}'
                   f'</div></div>')
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
        def last5_html(record, tname):
            if not record or not record.get("games"):
                return f'<div style="font-size:12px;color:var(--muted);margin-bottom:10px">{tname}: record unavailable</div>'
            w=record["wins"]; l=record["losses"]
            wl_col="var(--green)" if w>l else ("var(--red)" if l>w else "var(--amber)")
            dots=""
            for r in record["games"]:
                loc="vs" if r["home"] else "@"; tip=f'{loc} {r["opp"]} {r["my_runs"]}-{r["op_runs"]}'
                col="var(--green)" if r["won"] else "var(--red)"; lbl="W" if r["won"] else "L"
                dots+=(f'<span title="{tip}" style="display:inline-flex;align-items:center;justify-content:center;'
                       f'width:24px;height:24px;border-radius:50%;background:{col};color:#000;font-size:10px;'
                       f'font-weight:700;font-family:monospace;cursor:default">{lbl}</span>')
            return (f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;'
                    f'background:var(--bg3);border-radius:8px;padding:8px 12px">'
                    f'<span style="font-size:11px;color:var(--muted);font-family:monospace;'
                    f'text-transform:uppercase;letter-spacing:0.5px;white-space:nowrap">Last 5:</span>'
                    f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:16px;font-weight:700;color:{wl_col}">{w}-{l}</span>'
                    f'<div style="display:flex;gap:4px">{dots}</div></div>')
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
        html=""
        for i,m in enumerate(matchups):
            open_cls="open" if i<1 else ""
            ap=m["away_pitcher"]; hp=m["home_pitcher"]
            ap_era=f'ERA {ap["era"]}' if ap.get("era","N/A")!="N/A" else "ERA N/A"
            hp_era=f'ERA {hp["era"]}' if hp.get("era","N/A")!="N/A" else "ERA N/A"
            html+=(f'<div class="game-block {open_cls}" onclick="toggleGame(this)">'
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
                   f'{last5_html(m.get("away_last5"),m["away"])}'
                   f'<div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin:12px 0 6px">{m["home"]} Batters vs {ap["name"]}</div>'
                   f'{batter_table(m["home_batters"],ap,m["home"],m["home_source"])}'
                   f'</div>'
                   f'<div>'
                   f'<div class="pitcher-card">'
                   f'<div class="pitcher-role">HOME STARTER</div>'
                   f'<div class="pitcher-name">{hp["name"]}</div>'
                   f'<div class="pitcher-team">{m["home"]} - {hp_era} - WHIP {hp.get("whip","N/A")} - K/9 {hp.get("k9","N/A")}</div>'
                   f'</div>'
                   f'{last5_html(m.get("home_last5"),m["home"])}'
                   f'<div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin:12px 0 6px">{m["away"]} Batters vs {hp["name"]}</div>'
                   f'{batter_table(m["away_batters"],hp,m["away"],m["away_source"])}'
                   f'</div>'
                   f'</div>'
                   f'<div style="margin-top:10px;padding:8px 12px;background:var(--bg3);border-radius:6px;font-size:11px;color:var(--muted);line-height:1.6">'
                   f'Green = .300+ BA (batter owns pitcher) - Amber = .250-.299 - Red = under .250 (pitcher has edge) - Min 3 AB'
                   f'</div>'
                   f'</div></div>')
        return html

    def weather_page():
        if not weather:
            return '<p style="color:var(--muted);font-size:13px;padding:2rem 0;text-align:center">Weather data unavailable.</p>'
        html=""
        for g in analyzed_games:
            home=g["home"]; away=g["away"]; w=weather.get(home)
            if not w: continue
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
.alert-reasoning{font-size:12px;color:#888;line-height:1.6;border-top:1px solid var(--border);padding-top:8px;margin-top:4px}
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
@media(max-width:768px){
  .sidebar{transform:translateX(-100%)}.sidebar.mobile-open{transform:translateX(0)}
  .main{margin-left:0}footer{margin-left:0}.hamburger{display:flex}.topbar-meta{display:none}
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

  <div class="page" id="page-games"><div class="page-inner">{game_blocks()}</div></div>

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
</div>

<footer>MLB Sharp Lines - The Gambling Cave - {date_str} - Enhanced model: SP quality, bullpen fatigue, injuries, park factors, umpire zone, wind - Gamble responsibly</footer>

<script>
  function showPage(name,el){{
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
    document.getElementById('page-'+name).classList.add('active');
    if(el)el.classList.add('active');
    const t={{home:'Home',plays:'Top Value Plays',games:'All Games',matchups:'Pitcher / Batter',weather:'Weather & Wind'}};
    document.getElementById('topbar-title').textContent=t[name]||name;
    window.scrollTo(0,0);closeSidebar();
  }}
  function toggleGame(el){{el.classList.toggle('open');}}
  function openSidebar(){{document.getElementById('sidebar').classList.add('mobile-open');document.getElementById('overlay').classList.add('show');}}
  function closeSidebar(){{document.getElementById('sidebar').classList.remove('mobile-open');document.getElementById('overlay').classList.remove('show');}}
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
        games_raw = fetch_odds()
    except Exception as e:
        print(f"ERROR fetching odds: {e}"); sys.exit(1)

    if not games_raw:
        with open("index.html","w",encoding="utf-8") as f:
            f.write(f"<html><body style='background:#09090b;color:#e4e4e7;font-family:monospace;"
                    f"padding:3rem;text-align:center'><h1 style='color:#a3e635'>MLB Sharp Lines</h1>"
                    f"<p style='color:#71717a;margin-top:1rem'>No upcoming games on {date_str}.</p></body></html>")
        return

    try:
        matchups = build_matchup_data(games_raw, mlb_date)
    except Exception as e:
        print(f"Matchup error: {e}"); matchups=[]

    try:
        weather = fetch_weather_for_games(games_raw)
    except Exception as e:
        print(f"Weather error: {e}"); weather={}

    mlb_sched_data = mlb_get("/schedule",{"sportId":1,"date":mlb_date,"hydrate":"officials,team"})
    mlb_sched_games = []
    if mlb_sched_data:
        for db in mlb_sched_data.get("dates",[]):
            mlb_sched_games.extend(db.get("games",[]))

    analyzed = []
    for g in games_raw:
        print(f"Analyzing {g['away_team']} @ {g['home_team']}...")
        try:
            ctx    = fetch_game_context(g, matchups, weather, mlb_sched_games)
            result = analyze_game(g, ctx)
            if result: analyzed.append(result)
        except Exception as e:
            print(f"  Error: {e}")

    signal_order = {"fire":0,"sharp":1,"value":2,"watch":3,"pass":4}
    analyzed.sort(key=lambda x:(x["date_sort"],signal_order.get(x["signal"],3)))

    html = build_html(analyzed, matchups, weather, date_str, time_str)
    with open("index.html","w",encoding="utf-8") as f:
        f.write(html)

    print(f"Done -- {len(analyzed)} games, {len(matchups)} matchups, {len(html):,} chars")

if __name__ == "__main__":
    main()
