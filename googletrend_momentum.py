# googletrend_momentum.py
"""
Fetch Google Trends (best-effort) + NSE pre-open. Optionally fetch LTP at 9:20.
Write outputs:
  - data/trending_momentum_stocks.xlsx
  - data/trending.json
Designed to run in CI (GitHub Actions) or locally.
"""

import requests
import re
import json
import time
import os
from datetime import datetime, timedelta
import pandas as pd

# -------- CONFIG ----------
# If you want the script to wait until 9:20 IST and fetch LTP/volume, set to True.
# In GitHub Actions this run should be scheduled at 09:10 IST so waiting ~10 minutes is okay.
FETCH_LTP_AT_920 = True

# NSE endpoints
NSE_PREOPEN_URL = "https://www.nseindia.com/api/market-data-pre-open?key=ALL"
NSE_QUOTE_URL = "https://www.nseindia.com/api/quote-equity?symbol={symbol}"

# output paths
os.makedirs("data", exist_ok=True)
OUT_XLSX = "data/trending_momentum_stocks.xlsx"
OUT_JSON = "data/trending.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

# --------------------------
def get_google_trending_terms():
    """Try Google Trends RSS (best-effort). Returns list of terms (strings)."""
    print("Fetching Google Trends (RSS, best-effort)")
    rss_url = "https://trends.google.com/trends/trendingsearches/daily?geo=IN&hl=en-IN"
    try:
        # Try RSS endpoint (some endpoints behave differently; try daily RSS)
        resp = requests.get("https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN",
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if resp.status_code == 200 and resp.text:
            titles = re.findall(r"<title>(.*?)</title>", resp.text)
            terms = [t.strip() for t in titles[1:]]  # skip feed title
            print(f"Google RSS fetched {len(terms)} terms")
            return terms
        else:
            print(f"Google RSS returned status {resp.status_code}")
    except Exception as e:
        print("Google Trends RSS error:", e)

    # fallback: return empty list
    return []

def fetch_nse_preopen(session):
    """Fetch NSE pre-open JSON and return DataFrame of symbols with open vs prev close."""
    print("Fetching NSE pre-open data...")
    # ensure we have cookies by visiting homepage
    try:
        session.get("https://www.nseindia.com", headers=HEADERS, timeout=10)
        time.sleep(1.2)
        r = session.get(NSE_PREOPEN_URL, headers=HEADERS, timeout=15)
    except Exception as e:
        print("NSE connection error:", e)
        return pd.DataFrame()

    if r.status_code != 200:
        print("NSE pre-open returned status", r.status_code)
        return pd.DataFrame()

    try:
        data = r.json()
    except Exception as e:
        print("Error parsing NSE JSON:", e)
        return pd.DataFrame()

    rows = []
    for item in data.get("data", []):
        meta = item.get("metadata", {})
        symbol = meta.get("symbol")
        prev_close = meta.get("previousClose")
        open_price = meta.get("iep")
        if symbol and prev_close and open_price and prev_close > 0:
            change_pct = ((open_price - prev_close) / prev_close) * 100
            rows.append({
                "Symbol": symbol,
                "PrevClose": prev_close,
                "OpenPrice": open_price,
                "%Change": round(change_pct, 2)
            })

    df = pd.DataFrame(rows).sort_values("%Change", ascending=False).reset_index(drop=True)
    print(f"Fetched {len(df)} pre-open records")
    return df

def fetch_live_quote(session, symbol):
    """Fetch NSE live quote (returns dict with LTP and totalTradedVolume if available)."""
    url = NSE_QUOTE_URL.format(symbol=symbol)
    try:
        r = session.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200 and r.text:
            j = r.json()
            # structure can vary; check for 'priceInfo' etc
            priceInfo = j.get("priceInfo", {})
            ltp = priceInfo.get("lastPrice") or priceInfo.get("lastPrice")
            volume = j.get("metadata", {}).get("totalTradedVolume") or priceInfo.get("totalTradedVolume")
            # sometimes volume under priceInfo -> totalTradedVolume
            if ltp is None and 'lastPrice' in priceInfo:
                ltp = priceInfo['lastPrice']
            return {"LTP": ltp, "Volume": volume, "raw": j}
        else:
            print(f"Quote for {symbol} returned status {r.status_code}")
    except Exception as e:
        print(f"Error fetching quote for {symbol}:", e)
    return {"LTP": None, "Volume": None, "raw": None}

def main():
    start_ts = datetime.utcnow().isoformat()
    session = requests.Session()

    # 1) Google Trends (best-effort)
    trends = get_google_trending_terms()
    # Normalize trends to lowercase for matching
    trends_lower = [t.lower() for t in trends]

    # 2) NSE pre-open
    nse_df = fetch_nse_preopen(session)

    if nse_df.empty:
        print("No NSE pre-open data. Exiting.")
        out = {
            "generated_at": start_ts,
            "error": "No NSE pre-open data",
            "trends": trends
        }
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        return

    # 3) Match with Google trends
    def matched(symbol):
        # try matching by symbol appearing in trend title
        s = symbol.lower()
        # direct match symbol in any trend term OR company name in trend term (simple)
        return any(s in t for t in trends_lower)

    if trends:
        nse_df["Matched"] = nse_df["Symbol"].apply(lambda x: matched(x))
    else:
        nse_df["Matched"] = False

    # 4) Prepare base output list
    out_list = []
    # We'll take top 200 movers to possibly fetch LTP later
    top_df = nse_df.head(200).copy()

    # 5) Optionally wait until 9:20 IST to fetch live LTP and volume
    # Determine current time in IST
    now_utc = datetime.utcnow()
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    # target 09:20 IST today
    target_ist = now_ist.replace(hour=9, minute=20, second=0, microsecond=0)
    if now_ist > target_ist:
        # if it's already past 9:20 IST, don't wait (fetch now)
        wait = 0
    else:
        wait = (target_ist - now_ist).total_seconds()

    if FETCH_LTP_AT_920 and wait > 0:
        print(f"Waiting {int(wait)} seconds until 09:20 IST to fetch LTPs...")
        time.sleep(wait + 2)  # small cushion

    # fetch LTPs for top symbols
    print("Fetching live quotes for top symbols (best-effort)...")
    for _, row in top_df.iterrows():
        symbol = row["Symbol"]
        quote = fetch_live_quote(session, symbol)
        ltp = quote.get("LTP")
        volume = quote.get("Volume")
        open_price = row["OpenPrice"]
        pct_from_open = None
        if ltp and open_price:
            try:
                pct_from_open = round(((ltp - open_price) / open_price) * 100, 2)
            except:
                pct_from_open = None

        out_item = {
            "Symbol": symbol,
            "PrevClose": row["PrevClose"],
            "OpenPrice": row["OpenPrice"],
            "%ChangePreOpen": row["%Change"],
            "Matched": bool(row["Matched"]),
            "LTP": ltp,
            "Volume": volume,
            "%FromOpen": pct_from_open
        }
        out_list.append(out_item)
        # small delay to be polite
        time.sleep(0.6)

    # 6) Write outputs (JSON + Excel)
    result = {
        "generated_at_utc": start_ts,
        "generated_at_ist": (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat(),
        "google_trends": trends,
        "results": out_list
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Excel
    df_out = pd.DataFrame(out_list)
    df_out.to_excel(OUT_XLSX, index=False)

    print("Saved JSON ->", OUT_JSON)
    print("Saved Excel ->", OUT_XLSX)

if __name__ == "__main__":
    main()
