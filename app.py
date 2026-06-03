import streamlit as st
import sqlite3
import pandas as pd
import urllib.request
import json
import os
from datetime import date, datetime, timedelta

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Covered Calls Tracker — Kyle",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
.metric-container { background:#1c2030; border-radius:10px; padding:14px; border:1px solid #262d3d; }
.alert-warn { background:rgba(245,166,35,0.1); border:1px solid rgba(245,166,35,0.3); border-radius:8px; padding:8px 12px; color:#f5a623; font-size:13px; margin-bottom:6px; }
.alert-danger { background:rgba(242,107,107,0.1); border:1px solid rgba(242,107,107,0.3); border-radius:8px; padding:8px 12px; color:#f26b6b; font-size:13px; margin-bottom:6px; }
.stDataFrame { font-size:12px; }
div[data-testid="stMetricValue"] { font-size:24px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── Database ──────────────────────────────────────────────────
DB = os.path.join(os.path.dirname(__file__), "covered_calls.db")
API_KEY = "sOQY5z1A4zx9ZK2qsA66lZ5GwlJ4_JkD"

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
    defaults = [
        ("ticker", "AMZN"),
        ("shares_owned", "2186"),
        ("pct_hold", "60"),
        ("pct_write", "40"),
    ]
    for k, v in defaults:
        conn.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)", (k, v))
    conn.commit()
    conn.close()

init_db()

def get_setting(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def save_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, str(value)))
    conn.commit()
    conn.close()

def load_transactions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM transactions ORDER BY date_opened DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_transaction(data):
    conn = get_db()
    conn.execute("""
        INSERT INTO transactions
        (date_opened,price_at_open,num_contracts,expiration,strike,
         option_premium,dte,btc_price,date_closed,status,assigned,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (data["date_opened"], data["price_at_open"], data["num_contracts"],
          data["expiration"], data["strike"], data["option_premium"], data["dte"],
          data.get("btc_price"), data.get("date_closed"), data.get("status","Open"),
          data.get("assigned","N"), data.get("notes","")))
    conn.commit()
    conn.close()

def update_transaction(tid, data):
    conn = get_db()
    conn.execute("""
        UPDATE transactions SET
        date_opened=?,price_at_open=?,num_contracts=?,expiration=?,strike=?,
        option_premium=?,dte=?,btc_price=?,date_closed=?,status=?,assigned=?,notes=?
        WHERE id=?
    """, (data["date_opened"], data["price_at_open"], data["num_contracts"],
          data["expiration"], data["strike"], data["option_premium"], data["dte"],
          data.get("btc_price"), data.get("date_closed"), data.get("status","Open"),
          data.get("assigned","N"), data.get("notes",""), tid))
    conn.commit()
    conn.close()

def delete_transaction(tid):
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
    conn.commit()
    conn.close()

# ── Price fetch ───────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_price(ticker):
    try:
        end = date.today().strftime("%Y-%m-%d")
        start = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
        url = (f"https://api.polygon.io/v2/aggs/ticker/{ticker}"
               f"/range/1/day/{start}/{end}"
               f"?adjusted=true&sort=desc&limit=1&apiKey={API_KEY}")
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results", [])
        return float(results[0]["c"]) if results else None
    except:
        return None

# ── Calculations ──────────────────────────────────────────────
def calc_tx(t, current_price=None):
    contracts   = t["num_contracts"]
    strike      = t["strike"]
    premium     = t["option_premium"]
    price_open  = t["price_at_open"]
    dte         = t["dte"]
    btc         = t["btc_price"]
    status      = t["status"]

    premium_total         = round(premium * 100 * contracts, 2)
    btc_total             = round(btc * 100 * contracts, 2) if btc else None
    cost_basis            = strike * 100 * contracts
    premium_roi           = round((premium_total / cost_basis) * 100, 2) if cost_basis else 0
    roi_annual            = round((premium_roi / dte * 365), 2) if dte else 0
    premium_if_assigned   = round((strike - price_open) * 100 * contracts, 2)
    total_if_assigned     = round(premium_if_assigned + premium_total, 2)
    assigned_roi          = round((total_if_assigned / cost_basis) * 100, 2) if cost_basis else 0
    assigned_roi_annual   = round((assigned_roi / dte * 365), 2) if dte else 0

    # Days open
    d1 = datetime.strptime(t["date_opened"], "%Y-%m-%d").date()
    if t["date_closed"]:
        d2 = datetime.strptime(t["date_closed"], "%Y-%m-%d").date()
        days_open = (d2 - d1).days
    else:
        days_open = (date.today() - d1).days

    # P&L
    if status == "Expired":
        profit_loss = premium_total
        final_roi   = premium_roi
    elif status == "BTC" and btc_total is not None:
        profit_loss = round(premium_total - btc_total, 2)
        final_roi   = round((profit_loss / cost_basis) * 100, 2) if cost_basis else 0
    elif status == "Assigned":
        profit_loss = total_if_assigned
        final_roi   = assigned_roi
    else:
        profit_loss = None
        final_roi   = None

    # Alerts
    alerts = []
    exp_date = datetime.strptime(t["expiration"], "%Y-%m-%d").date()
    dte_remaining = (exp_date - date.today()).days
    if status == "Open":
        if dte_remaining <= 7:
            alerts.append(("warn", f"Expiring in {dte_remaining}d — {t['expiration']} ${strike}"))
        if current_price and current_price >= strike:
            alerts.append(("danger", f"ITM — price ${current_price:.2f} is at/above strike ${strike} — {t['expiration']}"))

    return {**t,
        "premium_total": premium_total,
        "btc_total": btc_total,
        "premium_roi": premium_roi,
        "roi_annual": roi_annual,
        "premium_if_assigned": premium_if_assigned,
        "total_if_assigned": total_if_assigned,
        "assigned_roi": assigned_roi,
        "assigned_roi_annual": assigned_roi_annual,
        "days_open": days_open,
        "dte_remaining": dte_remaining if status == "Open" else None,
        "profit_loss": profit_loss,
        "final_roi": final_roi,
        "alerts": alerts,
    }

def fmt_date(d):
    if not d: return "—"
    try:
        p = d.split("-")
        return f"{p[1]}/{p[2]}/{p[0]}"
    except:
        return d

def fmt_usd(v):
    if v is None: return "—"
    return f"${v:,.2f}"

def fmt_pct(v):
    if v is None: return "—"
    return f"{v:.1f}%"

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    ticker       = st.text_input("Ticker", value=get_setting("ticker","AMZN")).upper()
    shares_owned = st.number_input("Shares owned", value=int(get_setting("shares_owned","0")), min_value=0, step=100)
    pct_hold     = st.slider("% to hold", 0, 100, int(get_setting("pct_hold","60")), step=5)
    pct_write    = 100 - pct_hold
    st.caption(f"% available to write: **{pct_write}%**")

    if st.button("💾 Save settings"):
        save_setting("ticker", ticker)
        save_setting("shares_owned", shares_owned)
        save_setting("pct_hold", pct_hold)
        save_setting("pct_write", pct_write)
        st.success("Settings saved.")
        st.cache_data.clear()

    st.divider()
    current_price = fetch_price(ticker)
    if current_price:
        st.metric(f"{ticker} price", f"${current_price:.2f}")
        st.caption("Refreshes every 5 min. Click to force refresh:")
        if st.button("🔄 Refresh price"):
            st.cache_data.clear()
            st.rerun()
    else:
        st.warning("Could not fetch price")

# ── Load & calc all transactions ──────────────────────────────
raw_txs = load_transactions()
txs = [calc_tx(t, current_price) for t in raw_txs]
open_txs   = [t for t in txs if t["status"] == "Open"]
closed_txs = [t for t in txs if t["status"] != "Open"]

# ── Position summary ──────────────────────────────────────────
contracts_to_write = int((shares_owned * (pct_write / 100)) / 100)
active_contracts   = sum(t["num_contracts"] for t in open_txs)
avail_to_write     = max(0, contracts_to_write - active_contracts)
port_value         = round(shares_owned * current_price, 2) if current_price else 0
total_premium      = sum(t["premium_total"] for t in txs)
total_gains        = sum(t["profit_loss"] for t in closed_txs if t["profit_loss"] is not None)

# ── Tabs ──────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "➕ Add Trade", "📋 History", "📥 Export"])

# ════════════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Kyle — AMZN Covered Calls")

    # Position metrics
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    col1.metric("Portfolio value",   fmt_usd(port_value))
    col2.metric("Shares owned",      f"{shares_owned:,}")
    col3.metric("% Hold / Write",    f"{pct_hold}% / {pct_write}%")
    col4.metric("Contracts to write", contracts_to_write)
    col5.metric("Active contracts",   active_contracts)
    col6.metric("Avail to write",     avail_to_write)
    col7.metric("Total gains",        fmt_usd(total_gains))

    st.divider()

    # Alerts
    all_alerts = []
    for t in open_txs:
        for level, msg in t["alerts"]:
            all_alerts.append((level, msg))

    if all_alerts:
        st.markdown("#### ⚠️ Alerts")
        for level, msg in all_alerts:
            css = "alert-danger" if level == "danger" else "alert-warn"
            icon = "🔴" if level == "danger" else "🟡"
            st.markdown(f'<div class="{css}">{icon} {msg}</div>', unsafe_allow_html=True)
        st.divider()

    # Open positions table
    st.markdown("#### Open positions")
    if not open_txs:
        st.info("No open positions.")
    else:
        open_data = []
        for t in open_txs:
            itm = current_price and current_price >= t["strike"]
            open_data.append({
                "ID":             t["id"],
                "Opened":         fmt_date(t["date_opened"]),
                "Price@Open":     fmt_usd(t["price_at_open"]),
                "Contracts":      t["num_contracts"],
                "Expiration":     fmt_date(t["expiration"]),
                "DTE Left":       f"{t['dte_remaining']}d {'⚠️' if t['dte_remaining'] <= 7 else ''}",
                "Strike":         fmt_usd(t["strike"]) + (" 🔴ITM" if itm else ""),
                "Premium":        fmt_usd(t["option_premium"]),
                "Prem Total":     fmt_usd(t["premium_total"]),
                "Prem ROI":       fmt_pct(t["premium_roi"]),
                "ROI Ann":        fmt_pct(t["roi_annual"]),
                "If Assigned":    fmt_usd(t["premium_if_assigned"]),
                "Total If Asgn":  fmt_usd(t["total_if_assigned"]),
                "Asgn ROI":       fmt_pct(t["assigned_roi"]),
                "Asgn ROI Ann":   fmt_pct(t["assigned_roi_annual"]),
                "Notes":          t["notes"] or "",
            })
        df = pd.DataFrame(open_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Summary totals
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total premium collected", fmt_usd(total_premium))
    c2.metric("Total P&L (closed)", fmt_usd(total_gains))
    c3.metric("Total transactions", len(txs))

# ════════════════════════════════════════════════════════════════
# TAB 2 — ADD TRADE
# ════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Add / Edit transaction")

    # Edit selector
    edit_id = None
    if txs:
        edit_options = ["— New transaction —"] + [f"#{t['id']} | {fmt_date(t['date_opened'])} | ${t['strike']} | {t['status']}" for t in txs]
        edit_sel = st.selectbox("Edit existing transaction (or add new):", edit_options)
        if edit_sel != "— New transaction —":
            edit_id = int(edit_sel.split("#")[1].split(" ")[0])

    edit_t = next((t for t in txs if t["id"] == edit_id), None) if edit_id else None

    with st.form("trade_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            date_opened = st.date_input("Date opened",
                value=datetime.strptime(edit_t["date_opened"], "%Y-%m-%d").date() if edit_t else date.today())
            price_open = st.number_input("Price at open ($)",
                value=float(edit_t["price_at_open"]) if edit_t else (current_price or 0.0),
                min_value=0.0, step=0.01, format="%.2f")
            num_contracts = st.number_input("# Contracts",
                value=int(edit_t["num_contracts"]) if edit_t else 1, min_value=1, step=1)
        with col2:
            expiration = st.date_input("Expiration date",
                value=datetime.strptime(edit_t["expiration"], "%Y-%m-%d").date() if edit_t else date.today() + timedelta(days=30))
            strike = st.number_input("Strike ($)",
                value=float(edit_t["strike"]) if edit_t else 0.0,
                min_value=0.0, step=0.50, format="%.2f")
            option_premium = st.number_input("Option premium ($)",
                value=float(edit_t["option_premium"]) if edit_t else 0.0,
                min_value=0.0, step=0.01, format="%.2f")
        with col3:
            dte_calc = (expiration - date_opened).days
            st.metric("DTE (auto-calculated)", dte_calc)
            status = st.selectbox("Status",
                ["Open", "Expired", "BTC", "Assigned"],
                index=["Open","Expired","BTC","Assigned"].index(edit_t["status"]) if edit_t else 0)
            notes = st.text_input("Notes", value=edit_t["notes"] or "" if edit_t else "")

        # Close fields
        btc_price = None
        date_closed = None
        if status in ["BTC", "Expired", "Assigned"]:
            col4, col5 = st.columns(2)
            with col4:
                btc_price = st.number_input("BTC price ($)",
                    value=float(edit_t["btc_price"]) if (edit_t and edit_t["btc_price"]) else 0.0,
                    min_value=0.0, step=0.01, format="%.2f") if status == "BTC" else None
            with col5:
                date_closed = st.date_input("Date closed",
                    value=datetime.strptime(edit_t["date_closed"], "%Y-%m-%d").date() if (edit_t and edit_t["date_closed"]) else date.today())

        submitted = st.form_submit_button("💾 Save transaction", type="primary")

    # Live preview
    if option_premium > 0 and strike > 0 and num_contracts > 0 and dte_calc > 0:
        st.markdown("#### 📐 Live calculation preview")
        prem_total   = option_premium * 100 * num_contracts
        cost_basis   = strike * 100 * num_contracts
        prem_roi     = (prem_total / cost_basis * 100) if cost_basis else 0
        roi_ann      = (prem_roi / dte_calc * 365) if dte_calc else 0
        if_assigned  = (strike - price_open) * 100 * num_contracts
        total_asgn   = if_assigned + prem_total
        asgn_roi     = (total_asgn / cost_basis * 100) if cost_basis else 0
        asgn_roi_ann = (asgn_roi / dte_calc * 365) if dte_calc else 0
        btc_pnl      = (prem_total - btc_price * 100 * num_contracts) if (btc_price and btc_price > 0) else None

        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("Premium total",    fmt_usd(prem_total))
        pc2.metric("Premium ROI",      fmt_pct(prem_roi))
        pc3.metric("ROI Annual",       fmt_pct(roi_ann))
        pc4.metric("If Assigned",      fmt_usd(if_assigned))
        pc5, pc6, pc7, pc8 = st.columns(4)
        pc5.metric("Total if Assigned", fmt_usd(total_asgn))
        pc6.metric("Assigned ROI",      fmt_pct(asgn_roi))
        pc7.metric("Assigned ROI Ann",  fmt_pct(asgn_roi_ann))
        if btc_pnl is not None:
            pc8.metric("P&L after BTC", fmt_usd(btc_pnl))

    if submitted:
        if dte_calc <= 0:
            st.error("Expiration must be after date opened.")
        elif strike <= 0 or option_premium <= 0:
            st.error("Strike and premium must be greater than 0.")
        else:
            tx_data = {
                "date_opened":    date_opened.strftime("%Y-%m-%d"),
                "price_at_open":  price_open,
                "num_contracts":  num_contracts,
                "expiration":     expiration.strftime("%Y-%m-%d"),
                "strike":         strike,
                "option_premium": option_premium,
                "dte":            dte_calc,
                "btc_price":      btc_price if (btc_price and btc_price > 0) else None,
                "date_closed":    date_closed.strftime("%Y-%m-%d") if date_closed else None,
                "status":         status,
                "assigned":       "Y" if status == "Assigned" else "N",
                "notes":          notes,
            }
            if edit_id:
                update_transaction(edit_id, tx_data)
                st.success(f"Transaction #{edit_id} updated.")
            else:
                add_transaction(tx_data)
                st.success("Transaction added.")
            st.rerun()

    # Delete button
    if edit_id:
        st.divider()
        if st.button(f"🗑️ Delete transaction #{edit_id}", type="secondary"):
            delete_transaction(edit_id)
            st.success(f"Transaction #{edit_id} deleted.")
            st.rerun()

# ════════════════════════════════════════════════════════════════
# TAB 3 — HISTORY
# ════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Transaction history")

    # Filter
    status_filter = st.multiselect("Filter by status:",
        ["Open","Expired","BTC","Assigned"], default=["Open","Expired","BTC","Assigned"])
    filtered = [t for t in txs if t["status"] in status_filter]

    if not filtered:
        st.info("No transactions match the filter.")
    else:
        hist_data = []
        for t in filtered:
            hist_data.append({
                "ID":            t["id"],
                "Opened":        fmt_date(t["date_opened"]),
                "Closed":        fmt_date(t["date_closed"]),
                "Days":          t["days_open"],
                "Contracts":     t["num_contracts"],
                "Strike":        fmt_usd(t["strike"]),
                "Premium":       fmt_usd(t["option_premium"]),
                "Prem Total":    fmt_usd(t["premium_total"]),
                "BTC":           fmt_usd(t["btc_price"]) if t["btc_price"] else "—",
                "Prem ROI":      fmt_pct(t["premium_roi"]),
                "ROI Ann":       fmt_pct(t["roi_annual"]),
                "If Assigned":   fmt_usd(t["premium_if_assigned"]),
                "Asgn ROI":      fmt_pct(t["assigned_roi"]),
                "Asgn ROI Ann":  fmt_pct(t["assigned_roi_annual"]),
                "Status":        t["status"],
                "P&L":           fmt_usd(t["profit_loss"]),
                "Final ROI":     fmt_pct(t["final_roi"]),
                "Notes":         t["notes"] or "",
            })
        df_hist = pd.DataFrame(hist_data)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

        # Totals
        st.divider()
        cl1, cl2, cl3, cl4 = st.columns(4)
        cl1.metric("Total premium", fmt_usd(sum(t["premium_total"] for t in filtered)))
        cl2.metric("Total P&L",     fmt_usd(sum(t["profit_loss"] for t in filtered if t["profit_loss"] is not None)))
        cl3.metric("Closed trades", len([t for t in filtered if t["status"] != "Open"]))
        avg_roi = sum(t["final_roi"] for t in filtered if t["final_roi"] is not None)
        n_closed = len([t for t in filtered if t["final_roi"] is not None])
        cl4.metric("Avg final ROI", fmt_pct(avg_roi / n_closed if n_closed else None))

# ════════════════════════════════════════════════════════════════
# TAB 4 — EXPORT
# ════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### Export data")
    if not txs:
        st.info("No transactions to export.")
    else:
        export_data = []
        for t in txs:
            export_data.append({
                "ID": t["id"], "Date Opened": t["date_opened"], "Date Closed": t["date_closed"] or "",
                "Days Open": t["days_open"], "Contracts": t["num_contracts"],
                "Price at Open": t["price_at_open"], "Strike": t["strike"],
                "Option Premium": t["option_premium"], "Premium Total": t["premium_total"],
                "DTE": t["dte"], "BTC Price": t["btc_price"] or "",
                "Premium ROI%": t["premium_roi"], "ROI Annual%": t["roi_annual"],
                "Premium if Assigned": t["premium_if_assigned"],
                "Total if Assigned": t["total_if_assigned"],
                "Assigned ROI%": t["assigned_roi"], "Assigned ROI Annual%": t["assigned_roi_annual"],
                "Status": t["status"], "Assigned Y/N": t["assigned"],
                "P&L": t["profit_loss"] or "", "Final ROI%": t["final_roi"] or "",
                "Notes": t["notes"] or "",
            })
        df_export = pd.DataFrame(export_data)
        csv = df_export.to_csv(index=False)
        st.download_button(
            label="⬇️ Download CSV",
            data=csv,
            file_name=f"covered_calls_{date.today()}.csv",
            mime="text/csv",
        )
        st.dataframe(df_export, use_container_width=True, hide_index=True)
