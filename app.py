from flask import Flask, request, jsonify, send_from_directory
from datetime import date, datetime, timedelta
import sqlite3
import urllib.request
import json
import os

app = Flask(__name__, static_folder="static")
DB = os.path.join(os.path.dirname(__file__), "covered_calls.db")
API_KEY = "sOQY5z1A4zx9ZK2qsA66lZ5GwlJ4_JkD"

# ── Database setup ────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_opened TEXT NOT NULL,
            price_at_open REAL NOT NULL,
            num_contracts INTEGER NOT NULL,
            expiration TEXT NOT NULL,
            strike REAL NOT NULL,
            option_premium REAL NOT NULL,
            dte INTEGER NOT NULL,
            btc_price REAL,
            date_closed TEXT,
            status TEXT DEFAULT 'Open',
            assigned TEXT DEFAULT 'N',
            notes TEXT
        );
    """)
    # Default settings
    defaults = [
        ("ticker", "AMZN"),
        ("shares_owned", "2186"),
        ("pct_hold", "60"),
        ("pct_write", "40"),
    ]
    for k, v in defaults:
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

init_db()

# ── Helpers ───────────────────────────────────────────────────────
def get_setting(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def fetch_price(ticker):
    end = date.today().strftime("%Y-%m-%d")
    start = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    url = ("https://api.polygon.io/v2/aggs/ticker/" + ticker +
           "/range/1/day/" + start + "/" + end +
           "?adjusted=true&sort=desc&limit=1&apiKey=" + API_KEY)
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    results = data.get("results", [])
    if not results:
        raise ValueError("No price data for " + ticker)
    return float(results[0]["c"])

def calc_transaction(row, current_price):
    t = dict(row)
    contracts = t["num_contracts"]
    strike = t["strike"]
    premium = t["option_premium"]
    price_open = t["price_at_open"]
    dte = t["dte"]
    btc = t["btc_price"]
    status = t["status"]
    date_opened = t["date_opened"]
    date_closed = t["date_closed"]
    expiration = t["expiration"]

    # Premium total
    premium_total = round(premium * 100 * contracts, 2)

    # BTC total
    btc_total = round(btc * 100 * contracts, 2) if btc else None

    # Premium ROI
    cost_basis = strike * 100 * contracts
    premium_roi = round((premium_total / cost_basis) * 100, 2) if cost_basis else 0

    # ROI Annual
    roi_annual = round((premium_roi / dte * 365), 2) if dte else 0

    # Premium if assigned
    premium_if_assigned = round((strike - price_open) * 100 * contracts, 2)

    # Total premium if assigned
    total_premium_if_assigned = round(premium_if_assigned + premium_total, 2)

    # Assigned ROI
    assigned_roi = round((total_premium_if_assigned / cost_basis) * 100, 2) if cost_basis else 0

    # Assigned ROI Annual
    assigned_roi_annual = round((assigned_roi / dte * 365), 2) if dte else 0

    # Days open
    if date_closed:
        d1 = datetime.strptime(date_opened, "%Y-%m-%d").date()
        d2 = datetime.strptime(date_closed, "%Y-%m-%d").date()
        days_open = (d2 - d1).days
    else:
        d1 = datetime.strptime(date_opened, "%Y-%m-%d").date()
        days_open = (date.today() - d1).days

    # Profit/Loss
    if status == "Expired":
        profit_loss = premium_total
        final_roi = premium_roi
    elif status == "BTC" and btc_total is not None:
        profit_loss = round(premium_total - btc_total, 2)
        final_roi = round((profit_loss / cost_basis) * 100, 2) if cost_basis else 0
    elif status == "Assigned":
        profit_loss = total_premium_if_assigned
        final_roi = assigned_roi
    else:
        profit_loss = None
        final_roi = None

    # Alerts
    alerts = []
    today = date.today()
    exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
    dte_remaining = (exp_date - today).days
    if status == "Open":
        if dte_remaining <= 7:
            alerts.append("Expiring soon (" + str(dte_remaining) + "d)")
        if current_price and current_price >= strike:
            alerts.append("ITM — price above strike")

    t.update({
        "premium_total": premium_total,
        "btc_total": btc_total,
        "premium_roi": premium_roi,
        "roi_annual": roi_annual,
        "premium_if_assigned": premium_if_assigned,
        "total_premium_if_assigned": total_premium_if_assigned,
        "assigned_roi": assigned_roi,
        "assigned_roi_annual": assigned_roi_annual,
        "days_open": days_open,
        "profit_loss": profit_loss,
        "final_roi": final_roi,
        "dte_remaining": dte_remaining if status == "Open" else None,
        "alerts": alerts,
    })
    return t

# ── Routes ────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    keys = ["ticker", "shares_owned", "pct_hold", "pct_write"]
    return jsonify({k: get_setting(k) for k in keys})

@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.json
    for k, v in data.items():
        set_setting(k, str(v))
    return jsonify({"ok": True})

@app.route("/api/price")
def api_price():
    ticker = get_setting("ticker", "AMZN")
    try:
        price = fetch_price(ticker)
        return jsonify({"ok": True, "price": price, "ticker": ticker})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/transactions", methods=["GET"])
def api_get_transactions():
    try:
        ticker = get_setting("ticker", "AMZN")
        try:
            current_price = fetch_price(ticker)
        except:
            current_price = None

        conn = get_db()
        rows = conn.execute("SELECT * FROM transactions ORDER BY date_opened DESC").fetchall()
        conn.close()

        transactions = [calc_transaction(r, current_price) for r in rows]

        # Summary stats
        closed = [t for t in transactions if t["status"] != "Open"]
        open_t = [t for t in transactions if t["status"] == "Open"]
        total_premium = round(sum(t["premium_total"] for t in transactions), 2)
        total_gains = round(sum(t["profit_loss"] for t in closed if t["profit_loss"] is not None), 2)
        active_contracts = sum(t["num_contracts"] for t in open_t)

        shares_owned = int(get_setting("shares_owned", "0"))
        pct_write = float(get_setting("pct_write", "40")) / 100
        pct_hold = float(get_setting("pct_hold", "60")) / 100
        price = current_price or 0
        value = round(shares_owned * price, 2)
        contracts_available_to_write = int((shares_owned * pct_write) / 100)
        contracts_avail = max(0, contracts_available_to_write - active_contracts)

        return jsonify({
            "ok": True,
            "current_price": current_price,
            "ticker": ticker,
            "shares_owned": shares_owned,
            "value": value,
            "pct_hold": int(get_setting("pct_hold", "60")),
            "pct_write": int(get_setting("pct_write", "40")),
            "contracts_to_write": contracts_available_to_write,
            "contracts_active": active_contracts,
            "contracts_avail": contracts_avail,
            "total_premium_collected": total_premium,
            "total_gains": total_gains,
            "transactions": transactions,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/transactions", methods=["POST"])
def api_add_transaction():
    try:
        d = request.json
        conn = get_db()
        conn.execute("""
            INSERT INTO transactions
            (date_opened, price_at_open, num_contracts, expiration, strike,
             option_premium, dte, btc_price, date_closed, status, assigned, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            d["date_opened"], d["price_at_open"], d["num_contracts"],
            d["expiration"], d["strike"], d["option_premium"], d["dte"],
            d.get("btc_price"), d.get("date_closed"), d.get("status", "Open"),
            d.get("assigned", "N"), d.get("notes", "")
        ))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/transactions/<int:tid>", methods=["PUT"])
def api_update_transaction(tid):
    try:
        d = request.json
        conn = get_db()
        conn.execute("""
            UPDATE transactions SET
            date_opened=?, price_at_open=?, num_contracts=?, expiration=?,
            strike=?, option_premium=?, dte=?, btc_price=?, date_closed=?,
            status=?, assigned=?, notes=?
            WHERE id=?
        """, (
            d["date_opened"], d["price_at_open"], d["num_contracts"],
            d["expiration"], d["strike"], d["option_premium"], d["dte"],
            d.get("btc_price"), d.get("date_closed"), d.get("status", "Open"),
            d.get("assigned", "N"), d.get("notes", ""), tid
        ))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/transactions/<int:tid>", methods=["DELETE"])
def api_delete_transaction(tid):
    try:
        conn = get_db()
        conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5051))
    app.run(host="0.0.0.0", port=port, debug=False)
