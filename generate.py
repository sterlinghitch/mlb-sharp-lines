"""
MLB Sharp Lines — Free Daily Generator
No Claude API needed. Uses pure math to analyze odds.
Costs: $0.00/month
"""

import os, json, sys, requests
from datetime import datetime
from zoneinfo import ZoneInfo

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
EASTERN      = ZoneInfo("America/New_York")

# ─────────────────────────────────────────────────────────────
# STEP 1: FETCH ODDS
# ─────────────────────────────────────────────────────────────
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
        timeout=30
    )
    r.raise_for_status()
    games = r.json()
    print(f"Got {len(games)} games")
    return games


# ─────────────────────────────────────────────────────────────
# STEP 2: MATH HELPERS
# ─────────────────────────────────────────────────────────────
def american_to_implied(price):
    """Convert American odds to implied probability (includes vig)."""
    try:
        p = float(price)
        if p > 0:
            return 100 / (p + 100)
        else:
            return abs(p) / (abs(p) + 100)
    except:
        return None

def implied_to_american(prob):
    """Convert true probability back to American odds."""
    if prob is None or prob <= 0 or prob >= 1:
        return "—"
    if prob >= 0.5:
        return f"-{round((prob / (1 - prob)) * 100)}"
    else:
        return f"+{round(((1 - prob) / prob) * 100)}"

def remove_vig(imp_a, imp_b):
    """Remove the bookmaker's vig to get true probabilities."""
    if imp_a is None or imp_b is None:
        return None, None
    total = imp_a + imp_b
    if total <= 0:
        return None, None
    return imp_a / total, imp_b / total


# ─────────────────────────────────────────────────────────────
# STEP 3: ANALYZE A SINGLE GAME
# ─────────────────────────────────────────────────────────────
def analyze_game(game):
    away = game["away_team"]
    home = game["home_team"]
    books = game.get("bookmakers", [])

    # Collect all moneylines per team per book
    book_data = []
    for b in books:
        h2h = next((m for m in b.get("markets", []) if m["key"] == "h2h"), None)
        total = next((m for m in b.get("markets", []) if m["key"] == "totals"), None)
        if not h2h:
            continue
        away_out = next((o for o in h2h["outcomes"] if o["name"] == away), None)
        home_out = next((o for o in h2h["outcomes"] if o["name"] == home), None)
        if not away_out or not home_out:
            continue
        over_out = next((o for o in (total or {}).get("outcomes", []) if o["name"] == "Over"), None)
        under_out= next((o for o in (total or {}).get("outcomes", []) if o["name"] == "Under"), None)

        away_price = away_out["price"]
        home_price = home_out["price"]
        away_imp   = american_to_implied(away_price)
        home_imp   = american_to_implied(home_price)
        away_true, home_true = remove_vig(away_imp, home_imp)

        book_data.append({
            "name":       b["title"],
            "away_price": away_price,
            "home_price": home_price,
            "away_imp":   round(away_imp * 100, 1)  if away_imp else None,
            "home_imp":   round(home_imp * 100, 1)  if home_imp else None,
            "away_true":  away_true,
            "home_true":  home_true,
            "total_line": over_out["point"] if over_out else None,
            "over_price": over_out["price"] if over_out else None,
            "under_price":under_out["price"] if under_out else None,
        })

    if not book_data:
        return None

    # ── CALCULATE TRUE ODDS ──────────────────────────────────
    # Detect if any book has the opposite team as favorite
    away_favored_books = [b for b in book_data if b["away_price"] < 0]
    home_favored_books = [b for b in book_data if b["home_price"] < 0]
    split_market = len(away_favored_books) > 0 and len(home_favored_books) > 0

    # Find outliers: books more than 15 cents off the median
    away_prices = sorted([b["away_price"] for b in book_data])
    home_prices = sorted([b["home_price"] for b in book_data])
    
    def median(lst):
        n = len(lst)
        if n == 0: return 0
        s = sorted(lst)
        return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2

    away_median = median(away_prices)
    home_median = median(home_prices)

    def cents_off(price, ref):
        """How many cents is this price off the reference in terms of vig value."""
        imp_price = american_to_implied(price)
        imp_ref   = american_to_implied(ref)
        if imp_price is None or imp_ref is None: return 0
        return abs(imp_price - imp_ref) * 100

    # Exclude outliers from true odds calculation
    clean_books = [b for b in book_data
                   if cents_off(b["away_price"], away_median) < 12
                   and cents_off(b["home_price"], home_median) < 12]
    if not clean_books:
        clean_books = book_data  # fallback: use all

    avg_away_true = sum(b["away_true"] for b in clean_books if b["away_true"]) / len(clean_books)
    avg_home_true = sum(b["home_true"] for b in clean_books if b["home_true"]) / len(clean_books)

    away_fair_line = implied_to_american(avg_away_true)
    home_fair_line = implied_to_american(avg_home_true)

    # ── FIND BEST / WORST PRICES ─────────────────────────────
    best_away_book  = max(book_data, key=lambda b: american_to_implied(b["away_price"]) * -1
                          if b["away_price"] < 0
                          else american_to_implied(b["away_price"]))
    # Actually: best price for bettor = highest payout = most positive (for dogs) or least negative (for favs)
    def bettor_value(price):
        """Higher = better for bettor."""
        p = float(price)
        return p  # +150 > +120 > -110 > -150

    best_away  = max(book_data, key=lambda b: bettor_value(b["away_price"]))
    worst_away = min(book_data, key=lambda b: bettor_value(b["away_price"]))
    best_home  = max(book_data, key=lambda b: bettor_value(b["home_price"]))
    worst_home = min(book_data, key=lambda b: bettor_value(b["home_price"]))

    away_gap_cents = round(abs(american_to_implied(worst_away["away_price"]) -
                               american_to_implied(best_away["away_price"])) * 100)
    home_gap_cents = round(abs(american_to_implied(worst_home["home_price"]) -
                               american_to_implied(best_home["home_price"])) * 100)

    # ── SIGNAL DETECTION ────────────────────────────────────
    signal = "watch"
    signal_label = "👀 WATCH"

    if split_market:
        signal = "fire"
        signal_label = "🔥 SPLIT MARKET"
    elif away_gap_cents >= 18 or home_gap_cents >= 18:
        signal = "fire"
        signal_label = "🔥 DISCREPANCY"
    elif away_gap_cents >= 10 or home_gap_cents >= 10:
        signal = "value"
        signal_label = "💰 SHOP"

    # Is any book's line more than 15 cents off market on either side?
    for b in book_data:
        if cents_off(b["away_price"], away_median) > 15:
            b["outlier_away"] = True
        if cents_off(b["home_price"], home_median) > 15:
            b["outlier_home"] = True
        b["best_away"]  = b["name"] == best_away["name"]
        b["worst_away"] = b["name"] == worst_away["name"]
        b["best_home"]  = b["name"] == best_home["name"]
        b["worst_home"] = b["name"] == worst_home["name"]

    # ── BEST BET LOGIC ───────────────────────────────────────
    # Favor is team with highest true probability
    fav_team  = home if avg_home_true > avg_away_true else away
    dog_team  = away if avg_home_true > avg_away_true else home
    fav_true  = max(avg_away_true, avg_home_true)
    dog_true  = min(avg_away_true, avg_home_true)
    fav_fair  = home_fair_line if avg_home_true > avg_away_true else away_fair_line

    if fav_team == home:
        best_fav_book  = best_home["name"]
        best_fav_price = best_home["home_price"]
        best_fav_imp   = american_to_implied(best_fav_price) * 100
    else:
        best_fav_book  = best_away["name"]
        best_fav_price = best_away["away_price"]
        best_fav_imp   = american_to_implied(best_fav_price) * 100

    edge_pct = round((fav_true * 100) - best_fav_imp, 1)

    if abs(fav_true - dog_true) < 0.03:
        # Near coin flip
        bet_play    = "Pass — near coin flip"
        bet_sub     = f"If forced: either team at BetOnline / LowVig for lowest vig"
        bet_edge    = "None"
        bet_is_pass = True
    else:
        bet_price_fmt = f"{'+' if best_fav_price > 0 else ''}{best_fav_price}"
        bet_play    = f"{fav_team} Moneyline"
        bet_sub     = f"{bet_price_fmt} at {best_fav_book}"
        bet_edge    = "Slight" if edge_pct > -2 else "Fair"
        bet_is_pass = False

    # ── BUILD DISCREPANCY ENTRIES ─────────────────────────────
    discrepancies = []
    if away_gap_cents >= 8:
        discrepancies.append({
            "team":       away,
            "best_price": f"{'+' if best_away['away_price'] > 0 else ''}{best_away['away_price']}",
            "worst_price":f"{'+' if worst_away['away_price'] > 0 else ''}{worst_away['away_price']}",
            "gap":        away_gap_cents,
            "best_book":  best_away["name"],
            "worst_book": worst_away["name"],
        })
    if home_gap_cents >= 8:
        discrepancies.append({
            "team":       home,
            "best_price": f"{'+' if best_home['home_price'] > 0 else ''}{best_home['home_price']}",
            "worst_price":f"{'+' if worst_home['home_price'] > 0 else ''}{worst_home['home_price']}",
            "gap":        home_gap_cents,
            "best_book":  best_home["name"],
            "worst_book": worst_home["name"],
        })

    # ── BEST VALUE PLAY ENTRY ─────────────────────────────────
    value_play = None
    if signal in ("fire", "value", "sharp") and not bet_is_pass:
        if fav_team == home:
            best_b = best_home
            best_p = best_home["home_price"]
        else:
            best_b = best_away
            best_p = best_away["away_price"]
        value_play = {
            "game":        f"{away} @ {home}",
            "signal":      signal,
            "team":        fav_team,
            "best_price":  f"{'+' if best_p > 0 else ''}{best_p}",
            "best_book":   best_b["name"],
            "true_pct":    round(fav_true * 100, 1),
            "implied_pct": round(american_to_implied(best_p) * 100, 1),
            "edge":        edge_pct,
            "reasoning":   build_reasoning(away, home, best_away, worst_away,
                                           best_home, worst_home, away_gap_cents,
                                           home_gap_cents, split_market, avg_away_true,
                                           avg_home_true, away_fair_line, home_fair_line),
        }

    try:
        t = datetime.fromisoformat(game.get("commence_time","").replace("Z","+00:00")).astimezone(EASTERN)
        time_display = t.strftime("%-I:%M %p ET")
        date_et      = t.strftime("%A, %B %d")   # e.g. "Wednesday, May 28"
        date_sort    = t.strftime("%Y-%m-%d")     # for sorting
    except:
        time_display = ""
        date_et      = "Today"
        date_sort    = "9999-99-99"

    return {
        "game":          f"{away} @ {home}",
        "game_id":       game.get("id", ""),
        "away":          away,
        "home":          home,
        "time":          time_display,
        "date_et":       date_et,
        "date_sort":     date_sort,
        "signal":        signal,
        "signal_label":  signal_label,
        "split_market":  split_market,
        "away_true":     round(avg_away_true * 100),
        "home_true":     round(avg_home_true * 100),
        "away_fair":     away_fair_line,
        "home_fair":     home_fair_line,
        "book_data":     book_data,
        "discrepancies": discrepancies,
        "value_play":    value_play,
        "bet_play":      bet_play,
        "bet_sub":       bet_sub,
        "bet_edge":      bet_edge,
        "bet_is_pass":   bet_is_pass,
        "best_away":     best_away,
        "best_home":     best_home,
        "worst_away":    worst_away,
        "worst_home":    worst_home,
        "away_gap":      away_gap_cents,
        "home_gap":      home_gap_cents,
    }


def build_reasoning(away, home, ba, wa, bh, wh, ag, hg, split, at, ht, afl, hfl):
    parts = []
    fav  = home if ht > at else away
    dog  = away if ht > at else home
    fav_t = max(at, ht)
    dog_t = min(at, ht)
    parts.append(f"{fav} are {round(fav_t*100)}% favorites by true odds (fair line {hfl if ht>at else afl}).")
    if split:
        parts.append(f"Market is split — some books favor {away}, others favor {home}. Watch for line movement before game time.")
    elif ag >= 15 or hg >= 15:
        team  = away if ag > hg else home
        best  = ba if ag > hg else bh
        worst = wa if ag > hg else wh
        gap   = max(ag, hg)
        bp    = best["away_price"] if ag > hg else best["home_price"]
        wp    = worst["away_price"] if ag > hg else worst["home_price"]
        parts.append(f"Large discrepancy on {team}: best price {'+' if bp>0 else ''}{bp} at {best['name']} vs {'+' if wp>0 else ''}{wp} at {worst['name']} — a {gap}¢ gap.")
    else:
        if ag >= 8:
            bp = ba["away_price"]; wp = wa["away_price"]
            parts.append(f"Shop {away}: {'+' if bp>0 else ''}{bp} at {ba['name']} vs {'+' if wp>0 else ''}{wp} at {wa['name']}.")
        if hg >= 8:
            bp = bh["home_price"]; wp = wh["home_price"]
            parts.append(f"Shop {home}: {'+' if bp>0 else ''}{bp} at {bh['name']} vs {'+' if wp>0 else ''}{wp} at {wh['name']}.")
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────
# STEP 4: BUILD HTML
# ─────────────────────────────────────────────────────────────
def build_html(analyzed_games, date_str, time_str):
    all_disc   = []
    all_plays  = []
    sharp_ct   = 0
    value_ct   = 0

    for g in analyzed_games:
        all_disc.extend([{**d, "game": g["game"]} for d in g["discrepancies"]])
        if g["value_play"]:
            all_plays.append(g["value_play"])
        if g["signal"] == "fire":  sharp_ct += 1
        if g["signal"] in ("fire","value","sharp"): value_ct += 1

    all_plays.sort(key=lambda x: abs(x.get("edge", 0)), reverse=True)
    all_disc.sort(key=lambda x: -x.get("gap", 0))

    signal_cls   = {"fire":"b-fire","sharp":"b-sharp","value":"b-value","watch":"b-watch","pass":"b-pass"}
    alert_cls    = {"fire":"fire","sharp":"sharp","value":"value","watch":"watch"}

    # ── ALERT CARDS ─────────────────────────────────────────
    def alert_cards():
        top = [p for p in all_plays if p["signal"] in ("fire","sharp","value")][:4]
        if not top:
            return '<p style="color:var(--muted);font-size:13px">No sharp alerts today — efficient market across all games.</p>'
        html = '<div class="alert-grid">'
        for p in top:
            sig  = p["signal"]
            acls = alert_cls.get(sig, "value")
            bcls = signal_cls.get(sig, "b-value")
            ec   = "green" if (p.get("edge") or 0) > 0 else "red"
            html += f"""
      <div class="alert-card {acls}">
        <span class="badge {bcls}">{sig.upper()}</span>
        <div class="alert-game">{p["game"]}</div>
        <div class="alert-rec">{p["team"]} — {p["best_price"]} @ {p["best_book"]}</div>
        <div class="alert-stats">
          <div class="stat-box"><div class="sl">Best Price</div><div class="sv">{p["best_price"]}</div></div>
          <div class="stat-box"><div class="sl">My True %</div><div class="sv">{p["true_pct"]}%</div></div>
          <div class="stat-box"><div class="sl">Implied %</div><div class="sv">{p["implied_pct"]}%</div></div>
        </div>
        <div class="alert-reasoning">{p["reasoning"]}</div>
      </div>"""
        html += "</div>"
        return html

    # ── VALUE PLAYS TABLE ────────────────────────────────────
    def plays_table():
        if not all_plays:
            return "<p style='color:var(--muted);font-size:13px'>No value plays identified today.</p>"
        rows = ""
        for p in all_plays:
            bc = signal_cls.get(p["signal"], "b-watch")
            ec = "c-green" if (p.get("edge") or 0) > 0 else "c-red"
            rows += f"""<tr>
          <td>{p["game"]}</td>
          <td class="mono">{p["team"]} ML</td>
          <td><span class="pill pill-n">{p["best_price"]}</span></td>
          <td class="c-accent mono" style="font-size:11px">{p["best_book"]}</td>
          <td class="mono">{p["implied_pct"]}%</td>
          <td class="mono">{p["true_pct"]}%</td>
          <td class="mono {ec}">{'+' if (p.get('edge') or 0) > 0 else ''}{p.get('edge','—')}%</td>
          <td><span class="badge {bc}" style="margin:0">{p["signal"].upper()}</span></td>
        </tr>"""
        return f"""<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:1.75rem">
      <table class="dtable">
        <thead><tr><th>Game</th><th>Play</th><th>Best Line</th><th>Best Book</th><th>Implied %</th><th>My True %</th><th>Edge</th><th>Signal</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""

    # ── DISCREPANCY TABLE ────────────────────────────────────
    def disc_table():
        if not all_disc:
            return "<p style='color:var(--muted);font-size:13px'>No major discrepancies today — tight market.</p>"
        rows = ""
        for d in all_disc[:12]:
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
      </table>
    </div>"""

    # ── GAME BLOCKS ──────────────────────────────────────────
    def game_blocks():
        html = ""
        for i, g in enumerate(analyzed_games):
            sig      = g["signal"]
            bc       = signal_cls.get(sig, "b-watch")
            open_cls = "open" if i < 2 else ""
            sig_badge= f'<span class="badge {bc}" style="font-size:9px">{g["signal_label"]}</span>' if sig != "watch" else ""
            away_fav = "fav" if g["away_true"] > g["home_true"] else ""
            home_fav = "fav" if g["home_true"] > g["away_true"] else ""

            # Book rows
            # ── BOOK ROWS with fixed totals display ──────────────
            book_rows = ""
            for b in g["book_data"]:
                def pc(price, is_best, is_worst, is_out):
                    fp = f"{'+' if price > 0 else ''}{price}"
                    if is_best:  return f'<td class="pb">{fp} ★</td>'
                    if is_worst: return f'<td class="pw">{fp} ✗</td>'
                    if is_out:   return f'<td class="po">{fp} ⚠</td>'
                    return f'<td class="pc">{fp}</td>'

                # Fixed totals display
                if b.get("total_line") and b.get("over_price") is not None:
                    op = b["over_price"]
                    op_str = f"+{op}" if op > 0 else str(op)
                    total_str = f'O/U {b["total_line"]} &nbsp;<span style="color:var(--accent)">{op_str}</span>'
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

            # ── BEST BET BOX ──────────────────────────────────────
            bb_cls  = "best-bet pass" if g["bet_is_pass"] else "best-bet"
            hdr_col = "style='color:var(--muted)'" if g["bet_is_pass"] else ""
            pl_col  = "style='color:#777'" if g["bet_is_pass"] else ""
            sub_col = "style='color:var(--muted)'" if g["bet_is_pass"] else ""
            best_ap = f"{'+' if g['best_away']['away_price']>0 else ''}{g['best_away']['away_price']}"
            best_hp = f"{'+' if g['best_home']['home_price']>0 else ''}{g['best_home']['home_price']}"

            best_bet = f"""
          <div class="{bb_cls}">
            <div class="bb-header" {hdr_col}>★ Best Bet This Game</div>
            <div class="bb-play" {pl_col}>{g["bet_play"]}</div>
            <div class="bb-sub" {sub_col}>{g["bet_sub"]}</div>
            <div class="bb-stats">
              <div class="bbs"><div class="bbs-label">True Odds</div><div class="bbs-val">{g["away_true"]}% / {g["home_true"]}%</div></div>
              <div class="bbs"><div class="bbs-label">Best {g["away"][:12]}</div><div class="bbs-val">{best_ap} @ {g["best_away"]["name"]}</div></div>
              <div class="bbs"><div class="bbs-label">Best {g["home"][:12]}</div><div class="bbs-val">{best_hp} @ {g["best_home"]["name"]}</div></div>
              <div class="bbs"><div class="bbs-label">Edge</div><div class="bbs-val {'green' if not g['bet_is_pass'] else 'c-muted'}">{g["bet_edge"]}</div></div>
            </div>
          </div>"""

            # ── PLAYER PROPS SECTION ──────────────────────────────
            props_html = ""
            if g.get("props"):
                grouped = {}
                for p in g["props"]:
                    lbl = p["market_label"]
                    if lbl not in grouped:
                        grouped[lbl] = []
                    grouped[lbl].append(p)

                props_html = '<div class="props-section"><div class="props-header">🎯 Player Props — Best Available Lines</div>'
                for mkt_label, entries in grouped.items():
                    props_html += f'<div class="props-market-label">{mkt_label}</div>'
                    props_html += '<table class="props-table"><thead><tr><th>Player</th><th>Line</th><th>Best Over</th><th>True Over%</th><th>Best Under</th><th>True Under%</th></tr></thead><tbody>'
                    for e in entries:
                        op = e.get("best_over_price")
                        up = e.get("best_under_price")
                        op_str = (f"+{op}" if op and op > 0 else str(op)) if op else "—"
                        up_str = (f"+{up}" if up and up > 0 else str(up)) if up else "—"
                        ob = e.get("best_over_book","—")
                        ub = e.get("best_under_book","—")
                        to = f'{e["true_over_pct"]}%'  if e.get("true_over_pct")  else "—"
                        tu = f'{e["true_under_pct"]}%' if e.get("true_under_pct") else "—"
                        props_html += f'<tr><td class="book">{e["player"]}</td><td class="mono">{e["point"]}</td><td class="pb" style="font-size:11px">{op_str} <span style="color:var(--muted);font-weight:400">@ {ob}</span></td><td class="prob">{to}</td><td class="pc" style="font-size:11px">{up_str} <span style="color:var(--muted);font-weight:400">@ {ub}</span></td><td class="prob">{tu}</td></tr>'
                    props_html += '</tbody></table>'
                props_html += '</div>'
            elif FETCH_PROPS:
                props_html = '<div class="props-section"><div class="props-header">🎯 Player Props</div><p style="font-size:12px;color:var(--muted);padding:8px 0">No props available for this game.</p></div>'

            # ── DATE HEADER (inject before first game of each day) ─
            day_header = ""
            if i == 0 or g["date_et"] != analyzed_games[i-1]["date_et"]:
                day_header = f'<div class="day-header"><span class="day-label">{g["date_et"]}</span></div>'

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
              <div class="cb-header">📊 Calculated True Odds (vig removed)</div>
              <div class="cb-grid">
                <div class="cb-team">
                  <div class="cb-name">{g["away"]}</div>
                  <div class="cb-pct {away_fav}">{g["away_true"]}%</div>
                  <div class="cb-line">Fair: {g["away_fair"]}</div>
                </div>
                <div class="cb-vs">vs</div>
                <div class="cb-team">
                  <div class="cb-name">{g["home"]}</div>
                  <div class="cb-pct {home_fav}">{g["home_true"]}%</div>
                  <div class="cb-line">Fair: {g["home_fair"]}</div>
                </div>
              </div>
              <div class="cb-method">Vig removed from each book via normalization, averaged across all non-outlier books.</div>
            </div>
            {best_bet}
            {props_html}
          </div>
        </div>"""
        return html

    # ── CSS ──────────────────────────────────────────────────
    css = """<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#09090b;--bg2:#111113;--bg3:#18181b;--bg4:#1f1f23;--border:#27272a;--border2:#3f3f46;--text:#e4e4e7;--muted:#71717a;--dim:#52525b;--green:#4ade80;--green-bg:#052e16;--green-border:#166534;--red:#f87171;--red-bg:#2d0a0a;--red-border:#7f1d1d;--blue:#60a5fa;--blue-bg:#0c1a3a;--blue-border:#1e3a6e;--amber:#fbbf24;--amber-bg:#1c1400;--amber-border:#78350f;--accent:#a3e635;--sidebar:240px}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:'IBM Plex Sans',sans-serif;font-size:14px;line-height:1.6;min-height:100vh;display:flex;flex-direction:column}
.shell{display:flex;flex:1;min-height:100vh}
.sidebar{width:var(--sidebar);background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column;position:fixed;top:0;left:0;height:100vh;z-index:200;overflow-y:auto}
.sidebar-logo{padding:20px 18px 16px;border-bottom:1px solid var(--border)}
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
.main{margin-left:var(--sidebar);flex:1;display:flex;flex-direction:column;min-height:100vh}
.topbar{background:var(--bg2);border-bottom:1px solid var(--border);padding:0 2rem;height:52px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.topbar-title{font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:15px;color:#fff}
.topbar-meta{font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace}
.page{display:none;flex:1}.page.active{display:block}
.page-inner{padding:2rem}
.hero{background:linear-gradient(135deg,rgba(163,230,53,0.06) 0%,rgba(163,230,53,0.01) 60%,transparent 100%);border:1px solid rgba(163,230,53,0.12);border-radius:16px;padding:2.5rem;margin-bottom:2rem;position:relative;overflow:hidden}
.hero::before{content:'⚾';position:absolute;right:2rem;top:1.5rem;font-size:80px;opacity:0.06}
.hero-eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:var(--accent);font-family:'IBM Plex Mono',monospace;font-weight:600;margin-bottom:10px}
.hero-title{font-family:'IBM Plex Mono',monospace;font-size:32px;font-weight:700;color:#fff;line-height:1.2;margin-bottom:10px}
.hero-title span{color:var(--accent)}
.hero-sub{font-size:14px;color:var(--muted);max-width:540px;line-height:1.7;margin-bottom:20px}
.hero-badges{display:flex;flex-wrap:wrap;gap:8px}
.hero-badge{background:var(--bg3);border:1px solid var(--border);border-radius:20px;padding:5px 12px;font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace}
.hero-badge strong{color:var(--text)}
.home-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:2rem}
.home-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:18px;cursor:pointer;transition:all 0.15s}
.home-card:hover{border-color:var(--border2);background:var(--bg3)}
.home-card-icon{font-size:24px;margin-bottom:10px}
.home-card-title{font-weight:700;font-size:14px;color:#fff;margin-bottom:4px}
.home-card-desc{font-size:12px;color:var(--muted);line-height:1.5}
.home-card-stat{font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:700;margin-top:8px}
.home-card-stat.green{color:var(--green)}.home-card-stat.amber{color:var(--amber)}.home-card-stat.accent{color:var(--accent)}
.metrics-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:1.75rem}
.metric-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.metric-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-family:'IBM Plex Mono',monospace;margin-bottom:5px}
.metric-val{font-size:26px;font-weight:700;font-family:'IBM Plex Mono',monospace;color:#fff}
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
.alert-card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:1.2rem;position:relative;overflow:hidden}
.alert-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
.alert-card.fire::before{background:linear-gradient(90deg,#f87171,#fb923c)}
.alert-card.sharp::before{background:linear-gradient(90deg,#60a5fa,#a78bfa)}
.alert-card.value::before{background:linear-gradient(90deg,#4ade80,#a3e635)}
.alert-card.watch::before{background:linear-gradient(90deg,#fbbf24,#fb923c)}
.alert-game{font-weight:700;font-size:15px;color:#fff;margin:8px 0 2px}
.alert-rec{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--accent);margin-bottom:10px}
.alert-stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin-bottom:8px}
.stat-box{background:var(--bg3);border-radius:6px;padding:7px 9px}
.sl{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px}
.sv{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;color:#fff}
.sv.green{color:var(--green)}.sv.red{color:var(--red)}.sv.amber{color:var(--amber)}
.alert-reasoning{font-size:12px;color:#888;line-height:1.6;border-top:1px solid var(--border);padding-top:9px;margin-top:4px}
.dtable{width:100%;border-collapse:collapse;font-size:12px}
.dtable th{text-align:left;padding:8px 12px;font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:600;font-family:'IBM Plex Mono',monospace;background:var(--bg3);border-bottom:1px solid var(--border)}
.dtable td{padding:9px 12px;border-bottom:1px solid var(--border);vertical-align:middle}
.dtable tr:last-child td{border-bottom:none}
.dtable tr:hover td{background:rgba(255,255,255,0.015)}
.mono{font-family:'IBM Plex Mono',monospace;font-weight:600}
.c-green{color:var(--green)}.c-red{color:var(--red)}.c-amber{color:var(--amber)}.c-accent{color:var(--accent)}.c-muted{color:var(--muted)}
.pill{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:11px;padding:2px 7px;border-radius:4px;font-weight:600}
.pill-g{background:var(--green-bg);color:var(--green);border:1px solid var(--green-border)}
.pill-r{background:var(--red-bg);color:var(--red);border:1px solid var(--red-border)}
.pill-n{background:var(--bg3);color:var(--text);border:1px solid var(--border)}
.game-block{background:var(--bg2);border:1px solid var(--border);border-radius:12px;margin-bottom:10px;overflow:hidden}
.game-header{display:flex;align-items:center;justify-content:space-between;padding:13px 16px;cursor:pointer;user-select:none;transition:background 0.12s}
.game-header:hover{background:var(--bg3)}
.game-teams{font-weight:700;font-size:14px;color:#fff}
.game-time{font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace;margin-top:1px}
.game-right{display:flex;align-items:center;gap:7px;flex-shrink:0}
.toggle{font-size:12px;color:var(--muted);transition:transform 0.2s;margin-left:3px}
.game-block.open .toggle{transform:rotate(180deg)}
.game-body{display:none;padding:0 16px 16px}
.game-block.open .game-body{display:block}
.otable{width:100%;border-collapse:collapse;margin-top:12px;font-size:12px}
.otable th{text-align:left;padding:5px 9px;font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:500;font-family:'IBM Plex Mono',monospace;border-bottom:1px solid var(--border)}
.otable td{padding:7px 9px;border-bottom:1px solid rgba(39,39,42,0.6)}
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
.cb-team{background:rgba(0,0,0,0.3);border-radius:7px;padding:10px 12px;text-align:center}
.cb-name{font-size:11px;color:var(--muted);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cb-pct{font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:700;color:#fff}
.cb-pct.fav{color:var(--accent)}
.cb-line{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);margin-top:2px}
.cb-vs{text-align:center;font-size:11px;color:var(--dim);font-family:'IBM Plex Mono',monospace}
.cb-method{font-size:10px;color:#444;margin-top:8px;line-height:1.5;border-top:1px solid rgba(163,230,53,0.08);padding-top:7px}
.best-bet{background:linear-gradient(135deg,rgba(74,222,128,0.06),rgba(74,222,128,0.01));border:1px solid rgba(74,222,128,0.22);border-radius:8px;padding:13px 15px;margin-top:10px}
.best-bet.pass{background:rgba(0,0,0,0.2);border-color:var(--border)}
.bb-header{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--green);font-family:'IBM Plex Mono',monospace;font-weight:700;margin-bottom:8px}
.bb-play{font-size:14px;font-weight:700;color:#fff;margin-bottom:3px}
.bb-sub{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--accent);margin-bottom:9px}
.bb-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-bottom:9px}
.bbs{background:rgba(0,0,0,0.25);border-radius:6px;padding:7px 9px}
.bbs-label{font-size:10px;color:var(--muted);margin-bottom:2px;text-transform:uppercase;letter-spacing:0.5px}
.bbs-val{font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;color:#fff}
.bbs-val.green{color:var(--green)}
.bb-reason{display:none}
.best-bet.pass .bb-play{color:#777}
.best-bet.pass .bb-sub{color:var(--muted)}
.day-header{display:flex;align-items:center;gap:12px;margin:1.5rem 0 10px}
.day-label{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:1.5px;white-space:nowrap}
.day-header::after{content:'';flex:1;height:1px;background:rgba(163,230,53,0.2)}
.props-section{margin-top:12px;background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:12px 14px}
.props-header{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-family:'IBM Plex Mono',monospace;font-weight:700;margin-bottom:10px}
.props-market-label{font-size:11px;font-weight:700;color:var(--text);text-transform:uppercase;letter-spacing:0.5px;margin:10px 0 5px;padding-top:8px;border-top:1px solid var(--border)}
.props-market-label:first-of-type{margin-top:0;padding-top:0;border-top:none}
.props-table{width:100%;border-collapse:collapse;font-size:11px}
.props-table th{text-align:left;padding:4px 8px;font-size:10px;text-transform:uppercase;letter-spacing:0.8px;color:var(--muted);font-weight:500;font-family:'IBM Plex Mono',monospace;border-bottom:1px solid var(--border)}
.props-table td{padding:6px 8px;border-bottom:1px solid rgba(39,39,42,0.5)}
.props-table tr:last-child td{border-bottom:none}
.props-table tr:hover td{background:rgba(255,255,255,0.012)}
footer{margin-left:var(--sidebar);background:var(--bg2);border-top:1px solid var(--border);padding:1.25rem 2rem;font-size:11px;color:var(--muted);text-align:center;line-height:1.8}
@media(max-width:900px){.sidebar{transform:translateX(-100%)}.main{margin-left:0}.metrics-grid{grid-template-columns:repeat(2,1fr)}.alert-grid{grid-template-columns:1fr}.home-grid{grid-template-columns:1fr 1fr}.bb-stats{grid-template-columns:1fr 1fr}footer{margin-left:0}}
</style>"""

    total = len(analyzed_games)
    books = max((len(g["book_data"]) for g in analyzed_games), default=0)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>MLB Sharp Lines — {date_str}</title>
{css}
</head>
<body>
<div class="shell">
<div class="sidebar">
  <div class="sidebar-logo">
    <div class="sidebar-logo-title">MLB Sharp Lines</div>
    <div class="sidebar-logo-sub">Daily Value Tracker</div>
  </div>
  <div class="sidebar-date"><span class="live-dot"></span>{date_str}</div>
  <div class="sidebar-section">Navigation</div>
  <div class="nav-item active" onclick="showPage('home',this)"><span class="nav-icon">🏠</span><span class="nav-label">Home</span></div>
  <div class="nav-item" onclick="showPage('plays',this)"><span class="nav-icon">🔥</span><span class="nav-label">Top Value Plays</span><span class="nav-count">{value_ct}</span></div>
  <div class="nav-item" onclick="showPage('games',this)"><span class="nav-icon">⚾</span><span class="nav-label">All Games</span><span class="nav-count">{total}</span></div>
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
    <div class="topbar-title" id="topbar-title">Home</div>
    <div class="topbar-meta">{total} games · {date_str}</div>
  </div>

  <!-- HOME -->
  <div class="page active" id="page-home"><div class="page-inner">
    <div class="hero">
      <div class="hero-eyebrow">MLB Sharp Lines Tracker</div>
      <div class="hero-title">Find the <span>edge</span><br>before the market does.</div>
      <div class="hero-sub">Live odds from major US bookmakers. Vig-removed true probabilities, cross-book discrepancies, and a best bet for every game — auto-updated daily for free.</div>
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
        <div class="home-card-desc">Vig removed from every book and averaged to find the real win probability.</div>
        <div class="home-card-stat green">Free</div>
      </div>
    </div>
  </div></div>

  <!-- PLAYS -->
  <div class="page" id="page-plays"><div class="page-inner">
    <div class="metrics-grid">
      <div class="metric-card"><div class="metric-label">Games Today</div><div class="metric-val">{total}</div></div>
      <div class="metric-card"><div class="metric-label">Books Scanned</div><div class="metric-val">{books}</div></div>
      <div class="metric-card"><div class="metric-label">Sharp Alerts</div><div class="metric-val amber">{sharp_ct}</div></div>
      <div class="metric-card"><div class="metric-label">Value Plays</div><div class="metric-val green">{value_ct}</div></div>
      <div class="metric-card"><div class="metric-label">Cost</div><div class="metric-val" style="font-size:18px">$0 / mo</div></div>
    </div>
    <div class="sec-header"><h2>🔥 Sharp Alerts</h2><div class="sec-line"></div></div>
    {alert_cards()}
    <div class="sec-header"><h2>📊 All Value Plays</h2><div class="sec-line"></div></div>
    {plays_table()}
    <div class="sec-header"><h2>📉 Line Discrepancies</h2><div class="sec-line"></div></div>
    {disc_table()}
  </div></div>

  <!-- GAMES -->
  <div class="page" id="page-games"><div class="page-inner">
    {game_blocks()}
  </div></div>
</div>
</div>
<footer>MLB Sharp Lines · {date_str} · Auto-updated daily via GitHub Actions · The Odds API · 100% free · Gamble responsibly</footer>
<script>
function showPage(name,el){{document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));document.getElementById('page-'+name).classList.add('active');if(el)el.classList.add('active');const t={{home:'Home',plays:'Top Value Plays',games:'All Games'}};document.getElementById('topbar-title').textContent=t[name]||name;window.scrollTo(0,0);}}
function toggleGame(el){{el.classList.toggle('open');}}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    if not ODDS_API_KEY:
        print("ERROR: ODDS_API_KEY not set")
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
        print("No games today — writing placeholder")
        with open("index.html", "w") as f:
            f.write(f"<html><body style='background:#09090b;color:#e4e4e7;font-family:monospace;padding:3rem;text-align:center'><h1 style='color:#a3e635'>MLB Sharp Lines</h1><p style='color:#71717a;margin-top:1rem'>No MLB games scheduled on {date_str}. Check back tomorrow.</p></body></html>")
        return

    analyzed = []
    for g in games_raw:
        result = analyze_game(g)
        if result:
            # Attach player props if enabled
            if FETCH_PROPS:
                print(f"  Fetching props for {result['game']}...")
                raw_props = fetch_props(result["game_id"])
                result["props"] = best_props(raw_props)
            else:
                result["props"] = []
            analyzed.append(result)

    # Sort by DATE first, then by signal within each day
    signal_order = {"fire": 0, "sharp": 1, "value": 2, "watch": 3, "pass": 4}
    analyzed.sort(key=lambda x: (x["date_sort"], signal_order.get(x["signal"], 3)))

    html = build_html(analyzed, date_str, time_str)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Done — index.html written ({len(html):,} chars, {len(analyzed)} games)")


if __name__ == "__main__":
    main()
