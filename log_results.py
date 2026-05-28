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
def grade_pick(pick, scores):
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
        print("No picks.json found — nothing to grade. Did generate.py run today?")
        sys.exit(0)

    picks_date = picks_data.get("date", "")
    if picks_date != yesterday_str:
        print(f"picks.json is from {picks_date}, expected {yesterday_str}.")
        print("This can happen if the site ran but picks are from a different day.")
        print("Continuing anyway — will match on team IDs not date.")

    bets = picks_data.get("bets", [])
    if not bets:
        print("picks.json has no bets recorded — nothing to grade.")
        sys.exit(0)

    print(f"Found {len(bets)} best bets to grade.")

    # Fetch final scores from MLB API
    print(f"\nFetching final scores for {yesterday_str}...")
    scores = fetch_final_scores(yesterday_str)

    # Also check today in case a game ran past midnight into today
    today_str = now_et.strftime("%Y-%m-%d")
    print(f"Also checking late games finishing today ({today_str})...")
    scores.update(fetch_final_scores(today_str))

    if not scores:
        print("No final scores found. Games may still be in progress — try running later.")
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
        graded_bets.append({
            "game":   game,
            "play":   play,
            "price":  pick.get("price", "?"),
            "book":   pick.get("book", "?"),
            "result": result,
            "signal": pick.get("signal", ""),
            "date":   display_date,
            "note":   note,
        })
        time.sleep(0.1)

    print(f"\nResults: {wins}W / {losses}L / {pushes}P / {skipped} skipped")

    if not graded_bets:
        print("No graded bets — not updating results.json")
        sys.exit(0)

    # Load existing results.json
    results_data = load_json("results.json") or {"days": []}

    # Check if this date already exists in results (avoid duplicates on re-run)
    existing_dates = [d.get("date", "") for d in results_data.get("days", [])]
    if display_date in existing_dates:
        print(f"results.json already has an entry for {display_date} — updating it.")
        results_data["days"] = [d for d in results_data["days"] if d.get("date") != display_date]

    # Prepend today's results (most recent at top)
    results_data["days"].insert(0, {
        "date": display_date,
        "bets": graded_bets,
    })

    save_json("results.json", results_data)
    print(f"results.json updated — {display_date} logged ({wins}W/{losses}L/{pushes}P)")

    # Clear picks.json so it doesn't get double-graded
    save_json("picks.json", {"date": picks_date, "bets": [], "graded": True})
    print("picks.json cleared (marked graded)")


if __name__ == "__main__":
    main()
