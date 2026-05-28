"""
snapshot_lines.py -- Saves a timestamped snapshot of current MLB odds.
Usage:
  python snapshot_lines.py opening   -> saves opening_lines.json  (run 9am ET)
  python snapshot_lines.py closing   -> saves closing_lines.json  (run 6:30pm ET)
No API key needed beyond ODDS_API_KEY env var.
"""
import os, sys, json, requests
from datetime import datetime
from zoneinfo import ZoneInfo

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
EASTERN      = ZoneInfo("America/New_York")

def main():
    mode     = sys.argv[1] if len(sys.argv) > 1 else "opening"
    filename = f"{mode}_lines.json"

    if not ODDS_API_KEY:
        print(f"ERROR: ODDS_API_KEY not set — cannot snapshot {mode} lines")
        sys.exit(1)

    print(f"Snapshotting {mode} lines...")
    try:
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
    except Exception as e:
        print(f"ERROR fetching odds: {e}")
        sys.exit(1)

    games    = r.json()
    now_et   = datetime.now(EASTERN)
    snapshot = {
        "timestamp": now_et.isoformat(),
        "time_display": now_et.strftime("%I:%M %p ET"),
        "type": mode,
        "games": {}
    }

    for g in games:
        game_key = f"{g['away_team']} @ {g['home_team']}"
        books_data = {}
        for b in g.get("bookmakers", []):
            h2h   = next((m for m in b.get("markets", []) if m["key"] == "h2h"),    None)
            total = next((m for m in b.get("markets", []) if m["key"] == "totals"), None)
            if not h2h: continue
            ao = next((o for o in h2h["outcomes"] if o["name"] == g["away_team"]), None)
            ho = next((o for o in h2h["outcomes"] if o["name"] == g["home_team"]), None)
            ov = next((o for o in (total or {}).get("outcomes", []) if o["name"] == "Over"), None)
            books_data[b["title"]] = {
                "away_price": ao["price"] if ao else None,
                "home_price": ho["price"] if ho else None,
                "total_line": ov["point"] if ov else None,
                "over_price": ov["price"] if ov else None,
            }
        snapshot["games"][game_key] = {
            "away":           g["away_team"],
            "home":           g["home_team"],
            "commence_time":  g.get("commence_time", ""),
            "books":          books_data,
        }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    print(f"Saved {filename}: {len(snapshot['games'])} games at {snapshot['time_display']}")


if __name__ == "__main__":
    main()
