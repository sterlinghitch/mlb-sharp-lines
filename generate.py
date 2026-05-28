"""
MLB Sharp Lines — Daily Generator
Free version: no Claude API needed, pure math analysis.
Costs: $0.00/month
"""

import os, sys, requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ── CONFIG ────────────────────────────────────────────────────
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
EASTERN      = ZoneInfo("America/New_York")

# ── PROPS CONFIG ──────────────────────────────────────────────
# Set to True only if you have the $19/month Odds API Starter plan.
# Free tier (500 credits/month) is NOT enough for daily prop fetching.
FETCH_PROPS  = False
PROP_MARKETS = [
    "batter_hits",
    "batter_home_runs",
    "batter_rbis",
    "batter_hits_runs_rbis",
    "pitcher_strikeouts",
]


# ═════════════════════════════════════════════════════════════
# FETCH
# ═════════════════════════════════════════════════════════════
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

    # Filter out games that have already started (live lines are useless for pre-game analysis)
    now_utc = datetime.now(timezone.utc)
    games   = []
    for g in all_games:
        try:
            start = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
            if start > now_utc:
                games.append(g)
            else:
                print(f"  Skipping started: {g['away_team']} @ {g['home_team']}")
        except Exception:
            games.append(g)

    print(f"Got {len(all_games)} total, {len(games)} not yet started")
    return games


def fetch_props(event_id):
    if not FETCH_PROPS:
        return []
    try:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{event_id}/odds",
            params={
                "apiKey":     ODDS_API_KEY,
                "regions":    "us",
                "markets":    ",".join(PROP_MARKETS),
                "oddsFormat": "american",
            },
            timeout=30,
        )
        if r.status_code != 200:
            return []
        data   = r.json()
        props  = []
        for book in data.get("bookmakers", []):
            for market in book.get("markets", []):
                for outcome in market.get("outcomes", []):
                    props.append({
                        "book":    book["title"],
                        "market":  market["key"],
                        "player":  outcome.get("description", outcome["name"]),
                        "side":    outcome["name"],
                        "point":   outcome.get("point"),
                        "price":   outcome["price"],
                    })
        return props
    except Exception as e:
        print(f"  Props error for {event_id}: {e}")
        return []


# ═════════════════════════════════════════════════════════════
# MATH HELPERS
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
    if prob >= 0.5:
        return f"-{round((prob / (1 - prob)) * 100)}"
    return f"+{round(((1 - prob) / prob) * 100)}"


def remove_vig(imp_a, imp_b):
    if imp_a is None or imp_b is None:
        return None, None
    total = imp_a + imp_b
    if total <= 0:
        return None, None
    return imp_a / total, imp_b / total


def fmt(price):
    try:
        p = int(price)
        return f"+{p}" if p > 0 else str(p)
    except Exception:
        return str(price)


# ═════════════════════════════════════════════════════════════
# ANALYZE ONE GAME
# ═════════════════════════════════════════════════════════════
def analyze_game(game):
    away  = game["away_team"]
    home  = game["home_team"]
    books = game.get("bookmakers", [])

    book_data = []
    for b in books:
        h2h   = next((m for m in b.get("markets", []) if m["key"] == "h2h"),    None)
        total = next((m for m in b.get("markets", []) if m["key"] == "totals"), None)
        if not h2h:
            continue
        away_out  = next((o for o in h2h["outcomes"] if o["name"] == away), None)
        home_out  = next((o for o in h2h["outcomes"] if o["name"] == home), None)
        if not away_out or not home_out:
            continue
        over_out  = next((o for o in (total or {}).get("outcomes", []) if o["name"] == "Over"),  None)
        under_out = next((o for o in (total or {}).get("outcomes", []) if o["name"] == "Under"), None)

        ap = away_out["price"]
        hp = home_out["price"]
        ai = american_to_implied(ap)
        hi = american_to_implied(hp)
        at, ht = remove_vig(ai, hi)

        book_data.append({
            "name":        b["title"],
            "away_price":  ap,
            "home_price":  hp,
            "away_imp":    round(ai * 100, 1) if ai else None,
            "home_imp":    round(hi * 100, 1) if hi else None,
            "away_true":   at,
            "home_true":   ht,
            "total_line":  over_out["point"] if over_out else None,
            "over_price":  over_out["price"] if over_out else None,
            "under_price": under_out["price"] if under_out else None,
        })

    if not book_data:
        return None

    # Detect split market
    split_market = (
        any(b["away_price"] < 0 for b in book_data) and
        any(b["home_price"] < 0 for b in book_data)
    )

    # Median helper
    def median(lst):
        s = sorted(lst); n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

    away_med = median([b["away_price"] for b in book_data])
    home_med = median([b["home_price"] for b in book_data])

    def cents_off(price, ref):
        i1 = american_to_implied(price)
        i2 = american_to_implied(ref)
        return abs(i1 - i2) * 100 if i1 and i2 else 0

    # Mark outliers
    for b in book_data:
        b["outlier_away"] = cents_off(b["away_price"], away_med) > 15
        b["outlier_home"] = cents_off(b["home_price"], home_med) > 15

    # True odds from clean books
    clean = [b for b in book_data if not b["outlier_away"] and not b["outlier_home"]]
    if not clean:
        clean = book_data
    avg_at = sum(b["away_true"] for b in clean if b["away_true"]) / len(clean)
    avg_ht = sum(b["home_true"] for b in clean if b["home_true"]) / len(clean)
    away_fair = implied_to_american(avg_at)
    home_fair = implied_to_american(avg_ht)

    # Best / worst per side
    def bv(price): return float(price)
    best_away  = max(book_data, key=lambda b: bv(b["away_price"]))
    worst_away = min(book_data, key=lambda b: bv(b["away_price"]))
    best_home  = max(book_data, key=lambda b: bv(b["home_price"]))
    worst_home = min(book_data, key=lambda b: bv(b["home_price"]))

    for b in book_data:
        b["best_away"]  = b["name"] == best_away["name"]
        b["worst_away"] = b["name"] == worst_away["name"]
        b["best_home"]  = b["name"] == best_home["name"]
        b["worst_home"] = b["name"] == worst_home["name"]

    away_gap = round(abs(
        american_to_implied(worst_away["away_price"]) -
        american_to_implied(best_away["away_price"])
    ) * 100)
    home_gap = round(abs(
        american_to_implied(worst_home["home_price"]) -
        american_to_implied(best_home["home_price"])
    ) * 100)

    # Signal
    if split_market:
        signal, signal_label = "fire",  "🔥 SPLIT MARKET"
    elif away_gap >= 18 or home_gap >= 18:
        signal, signal_label = "fire",  "🔥 DISCREPANCY"
    elif away_gap >= 10 or home_gap >= 10:
        signal, signal_label = "value", "💰 SHOP"
    else:
        signal, signal_label = "watch", ""

    # Best bet
    fav_team  = home if avg_ht > avg_at else away
    fav_true  = max(avg_at, avg_ht)
    dog_true  = min(avg_at, avg_ht)

    if fav_team == home:
        bf_book  = best_home["name"]
        bf_price = best_home["home_price"]
    else:
        bf_book  = best_away["name"]
        bf_price = best_away["away_price"]

    bf_imp   = american_to_implied(bf_price) * 100
    edge_pct = round((fav_true * 100) - bf_imp, 1)

    if abs(fav_true - dog_true) < 0.03:
        bet_play, bet_sub, bet_edge, bet_is_pass = (
            "Pass — near coin flip",
            "If forced: use BetOnline / LowVig for lowest vig",
            "None", True,
        )
    else:
        bet_play    = f"{fav_team} Moneyline"
        bet_sub     = f"{fmt(bf_price)} at {bf_book}"
        bet_edge    = "Slight"
        bet_is_pass = False

    # Discrepancies
    discs = []
    for team, gap, best, worst, price_key in [
        (away, away_gap, best_away,  worst_away,  "away_price"),
        (home, home_gap, best_home,  worst_home,  "home_price"),
    ]:
        if gap >= 8:
            discs.append({
                "team":       team,
                "best_price": fmt(best[price_key]),
                "worst_price":fmt(worst[price_key]),
                "gap":        gap,
                "best_book":  best["name"],
                "worst_book": worst["name"],
            })

    # Value play entry
    value_play = None
    if signal in ("fire", "value", "sharp") and not bet_is_pass:
        best_b = best_home if fav_team == home else best_away
        best_p = best_b["home_price"] if fav_team == home else best_b["away_price"]
        reasoning = build_reasoning(
            away, home, best_away, worst_away, best_home, worst_home,
            away_gap, home_gap, split_market, avg_at, avg_ht, away_fair, home_fair,
        )
        value_play = {
            "game":        f"{away} @ {home}",
            "signal":      signal,
            "team":        fav_team,
            "best_price":  fmt(best_p),
            "best_book":   best_b["name"],
            "true_pct":    round(fav_true * 100, 1),
            "implied_pct": round(american_to_implied(best_p) * 100, 1),
            "edge":        edge_pct,
            "reasoning":   reasoning,
        }

    # Time + date
    try:
        t            = datetime.fromisoformat(game.get("commence_time", "").replace("Z", "+00:00")).astimezone(EASTERN)
        time_display = t.strftime("%-I:%M %p ET")
        date_et      = t.strftime("%A, %B %d")
        date_sort    = t.strftime("%Y-%m-%d")
    except Exception:
        time_display = ""
        date_et      = "Today"
        date_sort    = "9999-99-99"

    return {
        "game":         f"{away} @ {home}",
        "game_id":      game.get("id", ""),
        "away":         away,
        "home":         home,
        "time":         time_display,
        "date_et":      date_et,
        "date_sort":    date_sort,
        "signal":       signal,
        "signal_label": signal_label,
        "split_market": split_market,
        "away_true":    round(avg_at * 100),
        "home_true":    round(avg_ht * 100),
        "away_fair":    away_fair,
        "home_fair":    home_fair,
        "book_data":    book_data,
        "discrepancies":discs,
        "value_play":   value_play,
        "bet_play":     bet_play,
        "bet_sub":      bet_sub,
        "bet_edge":     bet_edge,
        "bet_is_pass":  bet_is_pass,
        "best_away":    best_away,
        "best_home":    best_home,
        "worst_away":   worst_away,
        "worst_home":   worst_home,
        "away_gap":     away_gap,
        "home_gap":     home_gap,
        "props":        [],
    }


def build_reasoning(away, home, ba, wa, bh, wh, ag, hg, split, at, ht, afl, hfl):
    fav   = home if ht > at else away
    fav_t = max(at, ht)
    parts = [f"{fav} are {round(fav_t*100)}% favorites by true odds (fair line {hfl if ht>at else afl})."]
    if split:
        parts.append(f"Market is split — some books favor {away}, others favor {home}. Watch for movement before game time.")
    elif ag >= 15 or hg >= 15:
        team  = away if ag > hg else home
        best  = ba   if ag > hg else bh
        worst = wa   if ag > hg else wh
        gap   = max(ag, hg)
        bp    = best["away_price"]  if ag > hg else best["home_price"]
        wp    = worst["away_price"] if ag > hg else worst["home_price"]
        parts.append(f"Large discrepancy on {team}: {fmt(bp)} at {best['name']} vs {fmt(wp)} at {worst['name']} — a {gap}¢ gap.")
    else:
        if ag >= 8:
            parts.append(f"Shop {away}: {fmt(ba['away_price'])} at {ba['name']} vs {fmt(wa['away_price'])} at {wa['name']}.")
        if hg >= 8:
            parts.append(f"Shop {home}: {fmt(bh['home_price'])} at {bh['name']} vs {fmt(wh['home_price'])} at {wh['name']}.")
    return " ".join(parts)


# ═════════════════════════════════════════════════════════════
# PROCESS PROPS
# ═════════════════════════════════════════════════════════════
def best_props(props_list):
    if not props_list:
        return []
    groups = {}
    for p in props_list:
        key = (p["player"], p["market"], p["side"], p.get("point"))
        groups.setdefault(key, []).append(p)

    results = []
    label_map = {
        "batter_hits":           "Hits",
        "batter_home_runs":      "Home Runs",
        "batter_rbis":           "RBIs",
        "batter_hits_runs_rbis": "H+R+RBI",
        "pitcher_strikeouts":    "Strikeouts",
        "batter_total_bases":    "Total Bases",
    }
    over_groups  = {k: v for k, v in groups.items() if k[2] == "Over"}
    under_groups = {k: v for k, v in groups.items() if k[2] == "Under"}

    for ok, over_list in over_groups.items():
        player, market, _, point = ok
        under_list = under_groups.get((player, market, "Under", point), [])
        best_over  = max(over_list,  key=lambda x: x["price"]) if over_list  else None
        best_under = max(under_list, key=lambda x: x["price"]) if under_list else None
        if not best_over:
            continue

        to = tu = None
        if best_over and best_under:
            oi = american_to_implied(best_over["price"])
            ui = american_to_implied(best_under["price"])
            ro, ru = remove_vig(oi, ui)
            to = round(ro * 100, 1) if ro else None
            tu = round(ru * 100, 1) if ru else None

        results.append({
            "player":           player,
            "market_label":     label_map.get(market, market),
            "point":            point,
            "best_over_price":  best_over["price"]  if best_over  else None,
            "best_over_book":   best_over["book"]   if best_over  else None,
            "best_under_price": best_under["price"] if best_under else None,
            "best_under_book":  best_under["book"]  if best_under else None,
            "true_over_pct":    to,
            "true_under_pct":   tu,
        })

    results.sort(key=lambda x: (x["market_label"], x["player"]))
    return results


# ═════════════════════════════════════════════════════════════
# BUILD HTML
# ═════════════════════════════════════════════════════════════
def build_html(analyzed_games, date_str, time_str):
    all_disc  = []
    all_plays = []
    sharp_ct  = 0
    value_ct  = 0

    for g in analyzed_games:
        for d in g["discrepancies"]:
            all_disc.append({**d, "game": g["game"]})
        if g["value_play"]:
            all_plays.append(g["value_play"])
        if g["signal"] == "fire":
            sharp_ct += 1
        if g["signal"] in ("fire", "value", "sharp"):
            value_ct += 1

    all_plays.sort(key=lambda x: -abs(x.get("edge", 0)))
    all_disc.sort(key=lambda x: -(x.get("gap", 0)))

    sig_cls   = {"fire":"b-fire","sharp":"b-sharp","value":"b-value","watch":"b-watch","pass":"b-pass"}
    alert_cls = {"fire":"fire","sharp":"sharp","value":"value","watch":"watch"}

    # ── ALERT CARDS ─────────────────────────────────────────
    def alert_cards():
        top = [p for p in all_plays if p["signal"] in ("fire","sharp","value")][:4]
        if not top:
            return '<p style="color:var(--muted);font-size:13px;padding:1rem 0">No sharp alerts today — efficient market.</p>'
        html = '<div class="alert-grid">'
        for p in top:
            sig  = p["signal"]
            ec   = "green" if (p.get("edge") or 0) > 0 else "red"
            html += f"""
      <div class="alert-card {alert_cls.get(sig,'value')}">
        <span class="badge {sig_cls.get(sig,'b-value')}">{sig.upper()}</span>
        <div class="alert-game">{p["game"]}</div>
        <div class="alert-rec">{p["team"]} — {p["best_price"]} @ {p["best_book"]}</div>
        <div class="alert-stats">
          <div class="stat-box"><div class="sl">Best Price</div><div class="sv">{p["best_price"]}</div></div>
          <div class="stat-box"><div class="sl">My True %</div><div class="sv">{p["true_pct"]}%</div></div>
          <div class="stat-box"><div class="sl">Implied %</div><div class="sv {ec}">{p["implied_pct"]}%</div></div>
        </div>
        <div class="alert-reasoning">{p["reasoning"]}</div>
      </div>"""
        html += "</div>"
        return html

    # ── PLAYS TABLE ──────────────────────────────────────────
    def plays_table():
        if not all_plays:
            return "<p style='color:var(--muted);font-size:13px;padding:1rem 0'>No value plays today.</p>"
        rows = ""
        for p in all_plays:
            ec = "c-green" if (p.get("edge") or 0) > 0 else "c-red"
            rows += f"""<tr>
          <td>{p["game"]}</td><td class="mono">{p["team"]} ML</td>
          <td><span class="pill pill-n">{p["best_price"]}</span></td>
          <td class="c-accent mono" style="font-size:11px">{p["best_book"]}</td>
          <td class="mono">{p["implied_pct"]}%</td>
          <td class="mono">{p["true_pct"]}%</td>
          <td class="mono {ec}">{'+' if (p.get('edge') or 0) > 0 else ''}{p.get('edge','—')}%</td>
          <td><span class="badge {sig_cls.get(p['signal'],'b-watch')}" style="margin:0">{p["signal"].upper()}</span></td>
        </tr>"""
        return f"""<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:1.75rem">
      <table class="dtable">
        <thead><tr><th>Game</th><th>Play</th><th>Best Line</th><th>Best Book</th><th>Implied%</th><th>True%</th><th>Edge</th><th>Signal</th></tr></thead>
        <tbody>{rows}</tbody>
      </table></div>"""

    # ── DISC TABLE ───────────────────────────────────────────
    def disc_table():
        if not all_disc:
            return "<p style='color:var(--muted);font-size:13px;padding:1rem 0'>No major discrepancies today.</p>"
        rows = ""
        for d in all_disc[:14]:
            gap = d.get("gap", 0)
            gc  = "c-red" if gap >= 18 else ("c-amber" if gap >= 10 else "")
            rows += f"""<tr>
          <td>{d["game"]}</td><td>{d["team"]}</td>
          <td><span class="pill pill-g">{d["best_price"]}</span></td>
          <td><span class="pill pill-r">{d["worst_price"]}</span></td>
          <td class="mono {gc}">{gap}¢</td>
          <td class="mono c-accent" style="font-size:11px">{d["best_book"]}</td>
          <td class="mono c-red" style="font-size:11px">{d["worst_book"]}</td>
        </tr>"""
        return f"""<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden">
      <table class="dtable">
        <thead><tr><th>Game</th><th>Team</th><th>Best Price</th><th>Worst Price</th><th>Gap</th><th>Best Book</th><th>Worst Book</th></tr></thead>
        <tbody>{rows}</tbody>
      </table></div>"""

    # ── GAME BLOCKS ──────────────────────────────────────────
    def game_blocks():
        html = ""
        for i, g in enumerate(analyzed_games):
            sig      = g["signal"]
            bc       = sig_cls.get(sig, "b-watch")
            open_cls = "open" if i < 2 else ""
            sig_badge= f'<span class="badge {bc}" style="font-size:9px">{g["signal_label"]}</span>' if g["signal_label"] else ""
            away_fav = "fav" if g["away_true"] > g["home_true"] else ""
            home_fav = "fav" if g["home_true"] > g["away_true"] else ""

            # ── DATE HEADER when date changes ────────────────
            day_header = ""
            if i == 0 or g["date_et"] != analyzed_games[i - 1]["date_et"]:
                day_header = f'<div class="day-header"><span class="day-label">{g["date_et"]}</span></div>'

            # ── BOOK ROWS ────────────────────────────────────
            book_rows = ""
            for b in g["book_data"]:
                def pc(price, is_best, is_worst, is_out):
                    fp = fmt(price)
                    if is_best:  return f'<td class="pb">{fp} ★</td>'
                    if is_worst: return f'<td class="pw">{fp} ✗</td>'
                    if is_out:   return f'<td class="po">{fp} ⚠</td>'
                    return f'<td class="pc">{fp}</td>'

                if b.get("total_line") and b.get("over_price") is not None:
                    op  = b["over_price"]
                    ops = fmt(op)
                    total_str = f'<span style="color:var(--muted)">O/U</span> <strong style="color:var(--text)">{b["total_line"]}</strong> <span style="color:var(--accent)">{ops}</span>'
                else:
                    total_str = '<span style="color:var(--dim)">—</span>'

                book_rows += f"""<tr>
              <td class="book">{b["name"]}</td>
              {pc(b["away_price"], b.get("best_away"), b.get("worst_away"), b.get("outlier_away"))}
              <td class="prob">{b["away_imp"]}%</td>
              {pc(b["home_price"], b.get("best_home"), b.get("worst_home"), b.get("outlier_home"))}
              <td class="prob">{b["home_imp"]}%</td>
              <td class="prob">{total_str}</td>
            </tr>"""

            # ── BEST BET BOX ──────────────────────────────────
            bb_cls  = "best-bet pass" if g["bet_is_pass"] else "best-bet"
            best_ap = fmt(g["best_away"]["away_price"])
            best_hp = fmt(g["best_home"]["home_price"])

            best_bet = f"""<div class="{bb_cls}">
            <div class="bb-header">★ Best Bet This Game</div>
            <div class="bb-play">{g["bet_play"]}</div>
            <div class="bb-sub">{g["bet_sub"]}</div>
            <div class="bb-stats">
              <div class="bbs"><div class="bbs-label">True Odds</div><div class="bbs-val">{g["away_true"]}% / {g["home_true"]}%</div></div>
              <div class="bbs"><div class="bbs-label">Best {g["away"][:11]}</div><div class="bbs-val">{best_ap} @ {g["best_away"]["name"]}</div></div>
              <div class="bbs"><div class="bbs-label">Best {g["home"][:11]}</div><div class="bbs-val">{best_hp} @ {g["best_home"]["name"]}</div></div>
              <div class="bbs"><div class="bbs-label">Edge</div><div class="bbs-val {'green' if not g['bet_is_pass'] else 'c-muted'}">{g["bet_edge"]}</div></div>
            </div>
          </div>"""

            # ── PROPS BOX ────────────────────────────────────
            props_html = ""
            if g.get("props"):
                grouped = {}
                for p in g["props"]:
                    grouped.setdefault(p["market_label"], []).append(p)
                props_html = '<div class="props-section"><div class="props-header">🎯 Player Props — Best Lines</div>'
                for mkt, entries in grouped.items():
                    props_html += f'<div class="props-mkt">{mkt}</div>'
                    props_html += '<table class="props-table"><thead><tr><th>Player</th><th>Line</th><th>Best Over</th><th>Over%</th><th>Best Under</th><th>Under%</th></tr></thead><tbody>'
                    for e in entries:
                        op  = e.get("best_over_price")
                        up  = e.get("best_under_price")
                        ops = fmt(op) if op else "—"
                        ups = fmt(up) if up else "—"
                        props_html += f'<tr><td class="book">{e["player"]}</td><td class="mono">{e["point"]}</td><td class="pb" style="font-size:11px">{ops} <span style="color:var(--muted);font-weight:400">@ {e.get("best_over_book","")}</span></td><td class="prob">{str(e["true_over_pct"])+"%"  if e.get("true_over_pct")  else "—"}</td><td class="pc" style="font-size:11px">{ups} <span style="color:var(--muted);font-weight:400">@ {e.get("best_under_book","")}</span></td><td class="prob">{str(e["true_under_pct"])+"%"  if e.get("true_under_pct") else "—"}</td></tr>'
                    props_html += '</tbody></table>'
                props_html += '</div>'

            html += day_header + f"""
        <div class="game-block {open_cls}" onclick="toggleGame(this)">
          <div class="game-header">
            <div>
              <div class="game-teams">{g["away"]} @ {g["home"]}</div>
              <div class="game-time">{g["time"]}</div>
            </div>
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
              <div class="cb-method">Vig removed from each book via normalization, averaged across all non-outlier books.</div>
            </div>
            {best_bet}
            {props_html}
          </div>
        </div>"""
        return html

    # ── CSS ──────────────────────────────────────────────────
    total = len(analyzed_games)
    books = max((len(g["book_data"]) for g in analyzed_games), default=0)

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
/* ── SIDEBAR ── */
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
/* ── OVERLAY (mobile) ── */
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:200}
.overlay.show{display:block}
/* ── MAIN ── */
.main{margin-left:var(--sidebar);min-height:100vh}
.topbar{background:var(--bg2);border-bottom:1px solid var(--border);padding:0 1.5rem;height:52px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.topbar-left{display:flex;align-items:center;gap:12px}
.hamburger{display:none;flex-direction:column;gap:4px;cursor:pointer;padding:4px;background:none;border:none}
.hamburger span{display:block;width:20px;height:2px;background:var(--text);border-radius:2px;transition:all 0.2s}
.topbar-title{font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:15px;color:#fff}
.topbar-meta{font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace}
/* ── PAGES ── */
.page{display:none}.page.active{display:block}
.page-inner{padding:2rem}
/* ── HERO ── */
.hero{background:linear-gradient(135deg,rgba(163,230,53,0.06) 0%,rgba(163,230,53,0.01) 60%,transparent 100%);border:1px solid rgba(163,230,53,0.12);border-radius:16px;padding:2.5rem;margin-bottom:2rem;position:relative;overflow:hidden}
.hero::before{content:'⚾';position:absolute;right:2rem;top:1.5rem;font-size:80px;opacity:0.06}
.hero-eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:var(--accent);font-family:'IBM Plex Mono',monospace;font-weight:600;margin-bottom:10px}
.hero-title{font-family:'IBM Plex Mono',monospace;font-size:30px;font-weight:700;color:#fff;line-height:1.2;margin-bottom:10px}
.hero-title span{color:var(--accent)}
.hero-sub{font-size:14px;color:var(--muted);max-width:520px;line-height:1.7;margin-bottom:18px}
.hero-badges{display:flex;flex-wrap:wrap;gap:8px}
.hero-badge{background:var(--bg3);border:1px solid var(--border);border-radius:20px;padding:5px 12px;font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace}
.hero-badge strong{color:var(--text)}
.home-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:2rem}
.home-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;cursor:pointer;transition:all 0.15s}
.home-card:hover{border-color:var(--border2);background:var(--bg3)}
.home-card-icon{font-size:22px;margin-bottom:8px}
.home-card-title{font-weight:700;font-size:13px;color:#fff;margin-bottom:3px}
.home-card-desc{font-size:12px;color:var(--muted);line-height:1.5}
.home-card-stat{font-family:'IBM Plex Mono',monospace;font-size:20px;font-weight:700;margin-top:6px}
.home-card-stat.green{color:var(--green)}.home-card-stat.amber{color:var(--amber)}.home-card-stat.accent{color:var(--accent)}
/* ── METRICS ── */
.metrics-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:1.75rem}
.metric-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:13px 15px}
.metric-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-family:'IBM Plex Mono',monospace;margin-bottom:5px}
.metric-val{font-size:24px;font-weight:700;font-family:'IBM Plex Mono',monospace;color:#fff}
.metric-val.green{color:var(--green)}.metric-val.amber{color:var(--amber)}
.metric-sub{font-size:11px;color:var(--muted);margin-top:2px}
/* ── SECTION HEADERS ── */
.sec-header{display:flex;align-items:center;gap:10px;margin-bottom:1rem;margin-top:2rem}
.sec-header:first-of-type{margin-top:0}
.sec-header h2{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);white-space:nowrap}
.sec-line{flex:1;height:1px;background:var(--border)}
/* ── BADGES ── */
.badge{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;padding:3px 8px;border-radius:5px;font-family:'IBM Plex Mono',monospace}
.b-fire{background:var(--red-bg);color:var(--red);border:1px solid var(--red-border)}
.b-sharp{background:var(--blue-bg);color:var(--blue);border:1px solid var(--blue-border)}
.b-value{background:var(--green-bg);color:var(--green);border:1px solid var(--green-border)}
.b-watch{background:var(--amber-bg);color:var(--amber);border:1px solid var(--amber-border)}
.b-pass{background:var(--bg4);color:var(--muted);border:1px solid var(--border)}
/* ── ALERT CARDS ── */
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
/* ── DATA TABLE ── */
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
/* ── DAY HEADER ── */
.day-header{display:flex;align-items:center;gap:12px;margin:1.5rem 0 10px}
.day-label{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:1.5px;white-space:nowrap}
.day-header::after{content:'';flex:1;height:1px;background:rgba(163,230,53,0.2)}
/* ── GAME BLOCKS ── */
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
/* ── ODDS TABLE ── */
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
/* ── TRUE ODDS BOX ── */
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
/* ── BEST BET ── */
.best-bet{background:linear-gradient(135deg,rgba(74,222,128,0.06),rgba(74,222,128,0.01));border:1px solid rgba(74,222,128,0.22);border-radius:8px;padding:12px 14px;margin-top:10px}
.best-bet.pass{background:rgba(0,0,0,0.2);border-color:var(--border)}
.bb-header{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--green);font-family:'IBM Plex Mono',monospace;font-weight:700;margin-bottom:7px}
.best-bet.pass .bb-header{color:var(--muted)}
.bb-play{font-size:14px;font-weight:700;color:#fff;margin-bottom:3px}
.best-bet.pass .bb-play{color:#777}
.bb-sub{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--accent);margin-bottom:8px}
.best-bet.pass .bb-sub{color:var(--muted)}
.bb-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:0}
.bbs{background:rgba(0,0,0,0.25);border-radius:6px;padding:6px 8px}
.bbs-label{font-size:10px;color:var(--muted);margin-bottom:2px;text-transform:uppercase;letter-spacing:0.5px}
.bbs-val{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;color:#fff}
.bbs-val.green{color:var(--green)}.bbs-val.c-muted{color:var(--muted)}
/* ── PROPS ── */
.props-section{margin-top:10px;background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:11px 13px}
.props-header{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-family:'IBM Plex Mono',monospace;font-weight:700;margin-bottom:8px}
.props-mkt{font-size:11px;font-weight:700;color:var(--text);text-transform:uppercase;letter-spacing:0.5px;margin:8px 0 4px;padding-top:7px;border-top:1px solid var(--border)}
.props-mkt:first-of-type{margin-top:0;padding-top:0;border-top:none}
.props-table{width:100%;border-collapse:collapse;font-size:11px}
.props-table th{text-align:left;padding:4px 8px;font-size:10px;text-transform:uppercase;letter-spacing:0.8px;color:var(--muted);font-weight:500;font-family:'IBM Plex Mono',monospace;border-bottom:1px solid var(--border)}
.props-table td{padding:5px 8px;border-bottom:1px solid rgba(39,39,42,0.5)}
.props-table tr:last-child td{border-bottom:none}
/* ── FOOTER ── */
footer{background:var(--bg2);border-top:1px solid var(--border);padding:1.25rem 2rem;font-size:11px;color:var(--muted);text-align:center;line-height:1.8;margin-left:var(--sidebar)}
/* ── MOBILE ── */
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

    # ── HTML ─────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>MLB Sharp Lines — {date_str}</title>
{css}
</head>
<body>

<!-- MOBILE OVERLAY -->
<div class="overlay" id="overlay" onclick="closeSidebar()"></div>

<!-- SIDEBAR -->
<div class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <div class="sidebar-logo-title">MLB Sharp Lines</div>
    <div class="sidebar-logo-sub">Daily Value Tracker</div>
  </div>
  <div class="sidebar-date"><span class="live-dot"></span>{date_str}</div>
  <div class="sidebar-section">Navigation</div>
  <div class="nav-item active" onclick="showPage('home',this)">
    <span class="nav-icon">🏠</span><span class="nav-label">Home</span>
  </div>
  <div class="nav-item" onclick="showPage('plays',this)">
    <span class="nav-icon">🔥</span><span class="nav-label">Top Value Plays</span>
    <span class="nav-count">{value_ct}</span>
  </div>
  <div class="nav-item" onclick="showPage('games',this)">
    <span class="nav-icon">⚾</span><span class="nav-label">All Games</span>
    <span class="nav-count">{total}</span>
  </div>
  <div class="sidebar-section" style="margin-top:8px">Today</div>
  <div class="sidebar-stats">
    <div class="sidebar-stat"><span class="sidebar-stat-label">Games</span><span class="sidebar-stat-val">{total}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Sharp alerts</span><span class="sidebar-stat-val amber">{sharp_ct}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Value plays</span><span class="sidebar-stat-val green">{value_ct}</span></div>
    <div class="sidebar-stat"><span class="sidebar-stat-label">Updated</span><span class="sidebar-stat-val">{time_str}</span></div>
  </div>
</div>

<!-- MAIN -->
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
      <div class="hero-sub">Live pre-game odds from major US bookmakers. Vig-removed true probabilities, cross-book discrepancies, and a best bet for every game — auto-updated daily at noon ET.</div>
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
        <div class="home-card-icon">🔥</div>
        <div class="home-card-title">Top Value Plays</div>
        <div class="home-card-desc">Discrepancy flags and best plays ranked by edge.</div>
        <div class="home-card-stat amber">{sharp_ct} alerts</div>
      </div>
      <div class="home-card" onclick="showPage('games',document.querySelectorAll('.nav-item')[2])">
        <div class="home-card-icon">⚾</div>
        <div class="home-card-title">All Games</div>
        <div class="home-card-desc">Full odds, true probability, and best bet for every game.</div>
        <div class="home-card-stat accent">{total} games</div>
      </div>
      <div class="home-card">
        <div class="home-card-icon">🧮</div>
        <div class="home-card-title">True Odds</div>
        <div class="home-card-desc">Vig stripped from every book, averaged to find real win probability.</div>
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
</div>

<footer>
  MLB Sharp Lines &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; Pre-game lines only &nbsp;·&nbsp; Auto-updated daily &nbsp;·&nbsp; Gamble responsibly
</footer>

<script>
  function showPage(name, el) {{
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    if (el) el.classList.add('active');
    const titles = {{home:'Home', plays:'Top Value Plays', games:'All Games'}};
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
        print("ERROR: ODDS_API_KEY environment variable not set")
        sys.exit(1)

    now_et   = datetime.now(EASTERN)
    date_str = now_et.strftime("%B %d, %Y")
    time_str = now_et.strftime("%-I:%M %p ET")

    try:
        games_raw = fetch_odds()
    except Exception as e:
        print(f"ERROR fetching odds: {e}")
        sys.exit(1)

    if not games_raw:
        print("No upcoming games found — writing placeholder page")
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html><html><body style='background:#09090b;color:#e4e4e7;
            font-family:monospace;padding:3rem;text-align:center'>
            <h1 style='color:#a3e635'>MLB Sharp Lines</h1>
            <p style='color:#71717a;margin-top:1rem'>No upcoming MLB games on {date_str}. Check back tomorrow.</p>
            </body></html>""")
        return

    # Analyze each game
    analyzed = []
    for g in games_raw:
        result = analyze_game(g)
        if not result:
            continue
        # Fetch props if enabled
        if FETCH_PROPS:
            print(f"  Fetching props for {result['game']}...")
            result["props"] = best_props(fetch_props(result["game_id"]))
        analyzed.append(result)

    # Sort by date first, then by signal urgency within each day
    signal_order = {"fire": 0, "sharp": 1, "value": 2, "watch": 3, "pass": 4}
    analyzed.sort(key=lambda x: (x["date_sort"], signal_order.get(x["signal"], 3)))

    html = build_html(analyzed, date_str, time_str)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Done — index.html written ({len(html):,} chars, {len(analyzed)} games)")


if __name__ == "__main__":
    main()
