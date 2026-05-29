"""
log_results.py — Nightly best-bet result checker
Runs at 1am ET (after all games finish).
Reads picks.json (saved by generate.py at noon),
checks final scores from the free MLB Stats API,
determines W / L / P (push) for every best bet,
then appends the day's results to results.json.
No API keys needed.
"""

import json, os, sys, requests, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

EASTERN  = ZoneInfo("America/New_York")
MLB_BASE = "https://statsapi.mlb.com/api/v1"

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


# =============================================================
# HELPERS
# =============================================================
def mlb_get(path, params=None):
    try:
        r = requests.get(MLB_BASE + path, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  MLB API error: {e}")
    return None


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# =============================================================
# FETCH FINAL SCORES FOR A DATE
# =============================================================
def fetch_final_scores(date_str):
    """
    Returns a dict keyed by (away_team_id, home_team_id) with final scores.
    Only includes games with abstractGameState == 'Final'.
    """
    data = mlb_get("/schedule", {
        "sportId":  1,
        "date":     date_str,
        "hydrate":  "linescore,team",
        "gameType": "R",
    })
    if not data:
        return {}

    scores = {}
    for db in data.get("dates", []):
        for g in db.get("games", []):
            state = g.get("status", {}).get("abstractGameState", "")
            if state != "Final":
                print(f"  Skipping non-final: {g.get('teams',{}).get('away',{}).get('team',{}).get('name','?')} "
                      f"@ {g.get('teams',{}).get('home',{}).get('team',{}).get('name','?')} ({state})")
                continue

            teams     = g.get("teams", {})
            away_data = teams.get("away", {})
            home_data = teams.get("home", {})
            away_id   = away_data.get("team", {}).get("id")
            home_id   = home_data.get("team", {}).get("id")
            away_runs = away_data.get("score", None)
            home_runs = home_data.get("score", None)
            away_name = away_data.get("team", {}).get("name", "?")
            home_name = home_data.get("team", {}).get("name", "?")

            if away_id and home_id and away_runs is not None and home_runs is not None:
                scores[(away_id, home_id)] = {
                    "away_runs": away_runs,
                    "home_runs": home_runs,
                    "away_name": away_name,
                    "home_name": home_name,
                    "total":     away_runs + home_runs,
                }
                print(f"  Final: {away_name} {away_runs} @ {home_name} {home_runs} "
                      f"(total {away_runs + home_runs})")

    return scores


# =============================================================
# GRADE ONE PICK
# =============================================================
def calc_clv(pick, closing_games):
    """
    Closing Line Value: compare noon pick price to closing line.
    Positive CLV = you beat the closing line (sharp signal).
    Returns cents of CLV or None if data unavailable.
    """
    if not closing_games: return None
    game_key  = pick.get("game","")
    closing   = closing_games.get(game_key,{})
    if not closing: return None

    books = closing.get("books",{})
    if not books: return None

    # Median closing price for the picked side
    bet_type  = pick.get("type","ml")
    pick_team = pick.get("pick_team","")
    away_name = pick.get("away","")
    noon_price_str = pick.get("price","")

    try:
        noon_price = float(noon_price_str.replace("+",""))
    except Exception:
        return None

    if bet_type == "ml":
        if pick_team in (away_name, pick.get("away","")):
            side_prices = [b["away_price"] for b in books.values() if b.get("away_price")]
        else:
            side_prices = [b["home_price"] for b in books.values() if b.get("home_price")]
    elif bet_type == "total":
        side     = pick.get("side","Over")
        key      = "over_price" if side=="Over" else "under_price"
        side_prices = [b[key] for b in books.values() if b.get(key)]
    else:
        return None

    if not side_prices: return None

    # Median closing price
    s = sorted(side_prices); n = len(s)
    close_price = s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2

    # CLV in cents (percentage points of implied probability)
    noon_imp  = american_to_implied(noon_price)
    close_imp = american_to_implied(close_price)
    if noon_imp is None or close_imp is None: return None

    # Positive CLV = we got better price than the market closed at = beat the line
    clv_cents = round((close_imp - noon_imp) * 100, 1)
    return {"clv_cents": clv_cents, "noon_price": noon_price_str,
            "close_price": int(close_price), "beat_close": clv_cents > 0}


def load_closing_lines():
    if not os.path.exists("closing_lines.json"): return {}
    try:
        with open("closing_lines.json") as f:
            data = json.load(f)
        return data.get("games",{})
    except Exception:
        return {}

def american_to_implied(price):
    try:
        p = float(price)
        return 100/(p+100) if p>0 else abs(p)/(abs(p)+100)
    except Exception:
        return None
    """
    Returns "W", "L", or "P" (push), or None if no final score found.

    pick keys used:
      type        -- "ml" or "total"
      away_id     -- MLB team ID for away team
      home_id     -- MLB team ID for home team
      pick_team   -- team name (for ML picks)
      away        -- away team name
      home        -- home team name
      side        -- "Over" or "Under" (for total picks)
      total_line  -- float e.g. 8.5 (for total picks)
    """
    away_id = pick.get("away_id")
    home_id = pick.get("home_id")
    if not away_id or not home_id:
        return None

    score = scores.get((away_id, home_id))
    if not score:
        # Try reversed (in case API flips home/away for doubleheaders etc.)
        score = scores.get((home_id, away_id))
        if score:
            # Swap so logic below is consistent
            score = {
                "away_runs": score["home_runs"],
                "home_runs": score["away_runs"],
                "away_name": score["home_name"],
                "home_name": score["away_name"],
                "total":     score["total"],
            }
    if not score:
        return None

    away_runs = score["away_runs"]
    home_runs = score["home_runs"]
    total     = score["total"]

    if pick["type"] == "ml":
        pick_team = pick.get("pick_team", "")
        away_name = pick.get("away", "")
        home_name = pick.get("home", "")

        # Figure out which side was picked
        if pick_team in (away_name, score["away_name"]):
            won = away_runs > home_runs
        elif pick_team in (home_name, score["home_name"]):
            won = home_runs > away_runs
        else:
            # Fallback: try to match via play string
            play = pick.get("play", "")
            if away_name in play:
                won = away_runs > home_runs
            elif home_name in play:
                won = home_runs > away_runs
            else:
                print(f"  Could not match team '{pick_team}' to score — skipping")
                return None

        if away_runs == home_runs:
            return "P"  # tie / extra innings suspended (rare)
        return "W" if won else "L"

    elif pick["type"] == "total":
        side       = pick.get("side", "")         # "Over" or "Under"
        total_line = pick.get("total_line")        # e.g. 8.5
        if total_line is None or not side:
            return None

        if total == total_line:
            return "P"  # push (only possible with whole-number lines)
        elif side == "Over":
            return "W" if total > total_line else "L"
        elif side == "Under":
            return "W" if total < total_line else "L"
        else:
            return None

    return None


# =============================================================
# MAIN
# =============================================================
def main():
    now_et = datetime.now(EASTERN)

    # We're running at 1am ET — check yesterday's games
    # (all games including west coast have finished by then)
    yesterday_et  = (now_et - timedelta(days=1)).date()
    yesterday_str = yesterday_et.strftime("%Y-%m-%d")
    display_date  = yesterday_et.strftime("%B %d, %Y")

    print(f"log_results.py — checking results for {display_date}")

    # Load picks.json
    picks_data = load_json("picks.json")
    if not picks_data:
        print("No picks.json found — nothing to grade yet. This is normal on the first run.")
        print("picks.json is created by generate.py after each noon/4pm site update.")
        sys.exit(0)  # exit 0 = success, not an error

    picks_date = picks_data.get("date", "")
    if picks_date != yesterday_str:
        print(f"picks.json is from {picks_date}, expected {yesterday_str}.")
        print("This can happen if the site ran but picks are from a different day.")
        print("Continuing anyway — will match on team IDs not date.")

    bets = picks_data.get("bets", [])
    if not bets:
        # picks.json is empty — check if there are unresolved pushes in results.json
        # that the 4am safety-net run should attempt to fix
        results_data = load_json("results.json") or {"days": []}
        existing_day = next((d for d in results_data.get("days",[])
                             if d.get("date") == display_date), None)
        if existing_day:
            unresolved = [b for b in existing_day.get("bets",[]) if b.get("result")=="P"]
            if unresolved:
                print(f"picks.json is empty but found {len(unresolved)} unresolved pushes in results.json for {display_date} -- re-grading.")
                # Reconstruct bets from results.json for re-grading
                # We can only re-grade if we have enough info (game + type fields)
                # Pushes without type info will stay as pushes
                bets = []
                for b in existing_day.get("bets",[]):
                    bets.append({
                        "game":       b.get("game",""),
                        "play":       b.get("play",""),
                        "price":      b.get("price",""),
                        "book":       b.get("book",""),
                        "signal":     b.get("signal",""),
                        "type":       "total" if "Runs" in b.get("play","") else "ml",
                        "away":       b.get("game","").split(" @ ")[0] if " @ " in b.get("game","") else "",
                        "home":       b.get("game","").split(" @ ")[1] if " @ " in b.get("game","") else "",
                        "away_id":    MLB_IDS.get(b.get("game","").split(" @ ")[0]) if " @ " in b.get("game","") else None,
                        "home_id":    MLB_IDS.get(b.get("game","").split(" @ ")[1]) if " @ " in b.get("game","") else None,
                        "side":       b.get("play","").split()[0] if "Runs" in b.get("play","") else None,
                        "total_line": float(b.get("play","").split()[1]) if "Runs" in b.get("play","") and len(b.get("play","").split())>1 else None,
                        "pick_team":  b.get("play","").replace(" Moneyline","") if "Moneyline" in b.get("play","") else None,
                    })
                picks_date = display_date
            else:
                print(f"picks.json is empty and no unresolved pushes found for {display_date} -- nothing to do.")
                sys.exit(0)
        else:
            print("picks.json has no bets recorded -- nothing to grade.")
            sys.exit(0)

    print(f"Found {len(bets)} best bets to grade.")

    # Fetch final scores from MLB API
    print(f"\nFetching final scores for {yesterday_str}...")
    scores = fetch_final_scores(yesterday_str)
    today_str = now_et.strftime("%Y-%m-%d")
    print(f"Also checking late games finishing today ({today_str})...")
    scores.update(fetch_final_scores(today_str))

    # Load closing lines for CLV tracking
    closing_games = load_closing_lines()
    if closing_games:
        print(f"Loaded closing_lines.json: {len(closing_games)} games for CLV tracking")
    else:
        print("No closing_lines.json -- CLV tracking skipped today")

    if not scores:
        print("No final scores found yet — games may still be in progress.")
        print("The next scheduled run will retry automatically.")
        sys.exit(0)

    print(f"\nGrading {len(bets)} picks against {len(scores)} final scores...")

    # Grade each pick
    graded_bets = []
    wins = losses = pushes = skipped = 0

    for pick in bets:
        result = grade_pick(pick, scores)
        game   = pick.get("game", "?")
        play   = pick.get("play", "?")

        if result is None:
            print(f"  SKIP  {game} | {play} — no final score found yet")
            skipped += 1
            # Still log it as pending so we can see it on the accuracy tab
            graded_bets.append({
                "game":   game,
                "play":   play,
                "price":  pick.get("price", "?"),
                "book":   pick.get("book", "?"),
                "result": "P",
                "signal": pick.get("signal", ""),
                "date":   display_date,
                "note":   "Score not found -- logged as push (check manually)",
            })
            continue

        if result == "W":   wins   += 1
        elif result == "L": losses += 1
        else:               pushes += 1

        # Find the score for the note
        away_id = pick.get("away_id"); home_id = pick.get("home_id")
        score   = scores.get((away_id, home_id)) or scores.get((home_id, away_id), {})
        ar = score.get("away_runs","?"); hr = score.get("home_runs","?")
        tot = score.get("total","?")
        if pick["type"] == "total":
            note = f"Final: {pick.get('away','?')} {ar} @ {pick.get('home','?')} {hr} = {tot} runs (line {pick.get('total_line','?')})"
        else:
            note = f"Final: {pick.get('away','?')} {ar} @ {pick.get('home','?')} {hr}"

        print(f"  {result}  {game} | {play} | {note}")
        clv = calc_clv(pick, closing_games)
        graded_bets.append({
            "game":   game,
            "play":   play,
            "price":  pick.get("price", "?"),
            "book":   pick.get("book", "?"),
            "result": result,
            "signal": pick.get("signal", ""),
            "date":   display_date,
            "note":   note,
            "clv":    clv,
        })
        time.sleep(0.1)

    print(f"\nResults: {wins}W / {losses}L / {pushes}P / {skipped} skipped")

    if not graded_bets:
        print("No graded bets — not updating results.json")
        sys.exit(0)

    # Load existing results.json
    results_data = load_json("results.json") or {"days": []}

    # If this date already exists, only update if we can improve on pushes/skips
    # (handles the 4am safety-net re-run upgrading pushes from the 1am run)
    existing_dates = [d.get("date", "") for d in results_data.get("days", [])]
    if display_date in existing_dates:
        existing_day = next(d for d in results_data["days"] if d.get("date") == display_date)
        existing_pushes = sum(1 for b in existing_day.get("bets",[]) if b.get("result")=="P")
        new_pushes      = sum(1 for b in graded_bets if b.get("result")=="P")
        if new_pushes >= existing_pushes and skipped == 0:
            print(f"No improvement over existing entry for {display_date} ({existing_pushes} pushes -> {new_pushes} pushes) -- skipping update")
            sys.exit(0)
        print(f"Upgrading {display_date}: {existing_pushes} pushes -> {new_pushes} pushes. Updating.")
        results_data["days"] = [d for d in results_data["days"] if d.get("date") != display_date]

    # Prepend today's results (most recent at top)
    results_data["days"].insert(0, {
        "date": display_date,
        "bets": graded_bets,
    })

    save_json("results.json", results_data)
    print(f"results.json updated — {display_date} logged ({wins}W/{losses}L/{pushes}P)")

    # Only clear picks.json on the final pass (when no skipped bets remain)
    # This lets the 4am run re-grade any pushes from the 1am run
    if skipped == 0 and pushes == 0:
        save_json("picks.json", {"date": picks_date, "bets": [], "graded": True})
        print("picks.json cleared — all bets graded cleanly")
    else:
        print(f"picks.json kept — {skipped} skipped / {pushes} pushes may resolve on next run")


if __name__ == "__main__":
    main()
