import streamlit as st
import sqlite3
import pandas as pd
import urllib.request
import json
import os
from datetime import date, datetime, timedelta

st.set_page_config(
    page_title="Covered Calls Tracker — Kyle",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── Dark theme base ── */
.stApp { background-color: #0d0f12; }
section[data-testid="stSidebar"] { background-color: #151820; border-right: 1px solid #262d3d; }
.stTabs [data-baseweb="tab-list"] { background-color: #151820; border-bottom: 1px solid #262d3d; gap: 0; }
.stTabs [data-baseweb="tab"] { background-color: transparent; color: #7a8299; font-family: 'DM Mono', monospace; font-size: 11px; font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase; padding: 10px 20px; border: none; border-bottom: 2px solid transparent; }
.stTabs [aria-selected="true"] { color: #4f8ef7 !important; border-bottom: 2px solid #4f8ef7 !important; background: transparent !important; }
.stTabs [data-baseweb="tab-panel"] { background-color: #0d0f12; padding-top: 1.5rem; }

/* ── Metric cards ── */
div[data-testid="metric-container"] {
  background: #151820;
  border: 1px solid #262d3d;
  border-radius: 12px;
  padding: 14px;
  position: relative;
  overflow: hidden;
}
div[data-testid="metric-container"]::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: #4f8ef7;
}
div[data-testid="stMetricLabel"] { font-size: 10px !important; letter-spacing: 0.08em; text-transform: uppercase; color: #7a8299 !important; font-family: 'DM Mono', monospace; }
div[data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 600 !important; color: #e8eaf0 !important; font-family: 'DM Mono', monospace; }
div[data-testid="stMetricDelta"] { font-size: 11px !important; font-family: 'DM Mono', monospace; }

/* ── Dataframe ── */
.stDataFrame { border: 1px solid #262d3d; border-radius: 10px; overflow: hidden; }
div[data-testid="stDataFrame"] { background: #151820; }

/* ── Forms and inputs ── */
div[data-testid="stForm"] { background: #151820; border: 1px solid #262d3d; border-radius: 12px; padding: 1.25rem; }
.stTextInput input, .stNumberInput input, .stDateInput input, .stSelectbox select {
  background: #1c2030 !important;
  border: 1px solid #262d3d !important;
  border-radius: 8px !important;
  color: #e8eaf0 !important;
  font-family: 'DM Mono', monospace !important;
}
.stTextInput input:focus, .stNumberInput input:focus { border-color: #4f8ef7 !important; }
label[data-testid="stWidgetLabel"] { color: #7a8299 !important; font-size: 11px !important; font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase; font-family: 'DM Mono', monospace; }
.stButton button { background: transparent; border: 1px solid #262d3d; border-radius: 8px; color: #7a8299; font-size: 13px; }
.stButton button:hover { border-color: #4f8ef7; color: #4f8ef7; }
button[kind="primary"] { background: #4f8ef7 !important; border: none !important; color: white !important; border-radius: 10px !important; font-weight: 600 !important; }
button[kind="primary"]:hover { background: #6ba3ff !important; }

/* ── Alerts ── */
.alert-warn { background: rgba(245,166,35,0.1); border: 1px solid rgba(245,166,35,0.3); border-radius: 8px; padding: 8px 14px; color: #f5a623; font-size: 13px; margin-bottom: 6px; font-family: 'DM Mono', monospace; }
.alert-danger { background: rgba(242,107,107,0.1); border: 1px solid rgba(242,107,107,0.3); border-radius: 8px; padding: 8px 14px; color: #f26b6b; font-size: 13px; margin-bottom: 6px; font-family: 'DM Mono', monospace; }

/* ── Summary chips ── */
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 1rem; }
.chip { background: #1c2030; border: 1px solid #262d3d; border-radius: 8px; padding: 8px 14px; font-size: 12px; font-family: 'DM Mono', monospace; color: #e8eaf0; }
.chip span { color: #7a8299; margin-right: 6px; }

/* ── Section headers ── */
.section-hdr { font-size: 10px; font-weight: 500; letter-spacing: 0.1em; text-transform: uppercase; color: #7a8299; font-family: 'DM Mono', monospace; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #262d3d; }

/* ── Position bar ── */
.pos-bar { background: #151820; border: 1px solid #262d3d; border-radius: 12px; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.pos-item { text-align: center; }
.pos-lbl { font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: #7a8299; font-family: 'DM Mono', monospace; margin-bottom: 4px; }
.pos-val { font-size: 18px; font-weight: 600; font-family: 'DM Mono', monospace; color: #e8eaf0; }
.pos-sub { font-size: 10px; color: #7a8299; font-family: 'DM Mono', monospace; }

/* ── Preview card ── */
.preview-card { background: #151820; border: 1px solid #262d3d; border-radius: 12px; padding: 16px; margin-top: 1rem; }

/* ── General text ── */
p, li, span { color: #e8eaf0; }
h1, h2, h3 { color: #e8eaf0 !important; }
.stMarkdown { color: #e8eaf0; }
hr { border-color: #262d3d; }
</style>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
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
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
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
    for k, v in [("ticker","AMZN"),("shares_owned","2186"),("pct_hold","60"),("pct_write","40")]:
        conn.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)", (k,v))
    conn.commit(); conn.close()

init_db()

def get_setting(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def save_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, str(value)))
    conn.commit(); conn.close()

def load_transactions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM transactions ORDER BY date_opened DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_transaction(data):
    conn = get_db()
    conn.execute("""INSERT INTO transactions
        (date_opened,price_at_open,num_contracts,expiration,strike,option_premium,dte,
         btc_price,date_closed,status,assigned,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data["date_opened"],data["price_at_open"],data["num_contracts"],data["expiration"],
         data["strike"],data["option_premium"],data["dte"],data.get("btc_price"),
         data.get("date_closed"),data.get("status","Open"),data.get("assigned","N"),data.get("notes","")))
    conn.commit(); conn.close()

def update_transaction(tid, data):
    conn = get_db()
    conn.execute("""UPDATE transactions SET date_opened=?,price_at_open=?,num_contracts=?,
        expiration=?,strike=?,option_premium=?,dte=?,btc_price=?,date_closed=?,
        status=?,assigned=?,notes=? WHERE id=?""",
        (data["date_opened"],data["price_at_open"],data["num_contracts"],data["expiration"],
         data["strike"],data["option_premium"],data["dte"],data.get("btc_price"),
         data.get("date_closed"),data.get("status","Open"),data.get("assigned","N"),
         data.get("notes",""),tid))
    conn.commit(); conn.close()

def delete_transaction(tid):
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
    conn.commit(); conn.close()

@st.cache_data(ttl=300)
def fetch_price(ticker):
    try:
        end   = date.today().strftime("%Y-%m-%d")
        start = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
        url   = (f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
                 f"?adjusted=true&sort=desc&limit=1&apiKey={API_KEY}")
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        r = data.get("results", [])
        return float(r[0]["c"]) if r else None
    except:
        return None

def calc_tx(t, current_price=None):
    contracts = t["num_contracts"]; strike = t["strike"]
    premium   = t["option_premium"]; price_open = t["price_at_open"]
    dte = t["dte"]; btc = t["btc_price"]; status = t["status"]
    premium_total       = round(premium * 100 * contracts, 2)
    btc_total           = round(btc * 100 * contracts, 2) if btc else None
    cost_basis          = strike * 100 * contracts
    premium_roi         = round((premium_total / cost_basis) * 100, 2) if cost_basis else 0
    roi_annual          = round((premium_roi / dte * 365), 2) if dte else 0
    premium_if_assigned = round((strike - price_open) * 100 * contracts, 2)
    total_if_assigned   = round(premium_if_assigned + premium_total, 2)
    assigned_roi        = round((total_if_assigned / cost_basis) * 100, 2) if cost_basis else 0
    assigned_roi_annual = round((assigned_roi / dte * 365), 2) if dte else 0
    d1 = datetime.strptime(t["date_opened"], "%Y-%m-%d").date()
    if t["date_closed"]:
        days_open = (datetime.strptime(t["date_closed"], "%Y-%m-%d").date() - d1).days
    else:
        days_open = (date.today() - d1).days
    if status == "Expired":
        profit_loss = premium_total; final_roi = premium_roi
    elif status == "BTC" and btc_total:
        profit_loss = round(premium_total - btc_total, 2)
        final_roi   = round((profit_loss / cost_basis) * 100, 2) if cost_basis else 0
    elif status == "Assigned":
        profit_loss = total_if_assigned; final_roi = assigned_roi
    else:
        profit_loss = None; final_roi = None
    exp_date      = datetime.strptime(t["expiration"], "%Y-%m-%d").date()
    dte_remaining = (exp_date - date.today()).days
    alerts = []
    if status == "Open":
        if dte_remaining <= 7:
            alerts.append(("warn", f"Expiring in {dte_remaining}d — {t['expiration']} ${strike}"))
        if current_price and current_price >= strike:
            alerts.append(("danger", f"ITM — price ${current_price:.2f} at/above strike ${strike} exp {t['expiration']}"))
    return {**t, "premium_total":premium_total,"btc_total":btc_total,"premium_roi":premium_roi,
            "roi_annual":roi_annual,"premium_if_assigned":premium_if_assigned,
            "total_if_assigned":total_if_assigned,"assigned_roi":assigned_roi,
            "assigned_roi_annual":assigned_roi_annual,"days_open":days_open,
            "dte_remaining":dte_remaining if status=="Open" else None,
            "profit_loss":profit_loss,"final_roi":final_roi,"alerts":alerts}

def fd(d):
    if not d: return "—"
    try: p=d.split("-"); return f"{p[1]}/{p[2]}/{p[0]}"
    except: return d

def fu(v): return f"${v:,.2f}" if v is not None else "—"
def fp(v): return f"{v:.1f}%" if v is not None else "—"

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="font-size:18px;font-weight:600;color:#e8eaf0;margin-bottom:4px;">⚙️ Settings</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px;color:#7a8299;font-family:DM Mono,monospace;margin-bottom:16px;">Position configuration</div>', unsafe_allow_html=True)
    ticker       = st.text_input("Ticker", value=get_setting("ticker","AMZN")).upper()
    shares_owned = st.number_input("Shares owned", value=int(get_setting("shares_owned","0")), min_value=0, step=100)
    pct_hold     = st.slider("% to hold", 0, 100, int(get_setting("pct_hold","60")), step=5)
    pct_write    = 100 - pct_hold
    st.markdown(f'<div style="font-size:11px;color:#7a8299;font-family:DM Mono,monospace;">% available to write: <strong style="color:#3ecf8e">{pct_write}%</strong></div>', unsafe_allow_html=True)
    if st.button("💾 Save settings", use_container_width=True):
        save_setting("ticker", ticker); save_setting("shares_owned", shares_owned)
        save_setting("pct_hold", pct_hold); save_setting("pct_write", pct_write)
        st.success("Saved."); st.cache_data.clear()
    st.divider()
    current_price = fetch_price(ticker)
    if current_price:
        st.markdown(f"""
        <div style="background:#1c2030;border:1px solid #262d3d;border-radius:10px;padding:12px 14px;position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;background:#3ecf8e;"></div>
          <div style="font-size:10px;letter-spacing:0.08em;text-transform:uppercase;color:#7a8299;font-family:DM Mono,monospace;margin-bottom:4px;">{ticker} live price</div>
          <div style="font-size:24px;font-weight:600;font-family:DM Mono,monospace;color:#3ecf8e;">${current_price:.2f}</div>
          <div style="font-size:10px;color:#7a8299;font-family:DM Mono,monospace;margin-top:3px;">Refreshes every 5 min</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.warning("Price unavailable")
    if st.button("🔄 Refresh price", use_container_width=True):
        st.cache_data.clear(); st.rerun()

# ── Load data ─────────────────────────────────────────────────
raw_txs    = load_transactions()
txs        = [calc_tx(t, current_price) for t in raw_txs]
open_txs   = [t for t in txs if t["status"] == "Open"]
closed_txs = [t for t in txs if t["status"] != "Open"]

contracts_to_write = int((shares_owned * (pct_write / 100)) / 100)
active_contracts   = sum(t["num_contracts"] for t in open_txs)
avail_to_write     = max(0, contracts_to_write - active_contracts)
port_value         = round(shares_owned * current_price, 2) if current_price else 0
total_premium      = sum(t["premium_total"] for t in txs)
total_gains        = sum(t["profit_loss"] for t in closed_txs if t["profit_loss"] is not None)

# ── Header ────────────────────────────────────────────────────
st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:1.5rem;">
  <div style="width:36px;height:36px;background:#3ecf8e;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:#0d0f12;">CC</div>
  <div>
    <div style="font-size:18px;font-weight:600;color:#e8eaf0;">Covered Calls Tracker</div>
    <div style="font-size:11px;color:#7a8299;font-family:DM Mono,monospace;">Kyle · {ticker} · {date.today().strftime('%B %d, %Y')}</div>
  </div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Add Trade", "History", "Export"])

# ════════════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ════════════════════════════════════════════════════════════════
with tab1:
    # Metrics row
    c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
    c1.metric("Portfolio value",    fu(port_value))
    c2.metric("Shares owned",       f"{shares_owned:,}")
    c3.metric("Hold / Write split", f"{pct_hold}% / {pct_write}%")
    c4.metric("Contracts to write", contracts_to_write)
    c5.metric("Active contracts",   active_contracts)
    c6.metric("Avail to write",     avail_to_write)
    c7.metric("Total gains",        fu(total_gains))

    st.divider()

    # Alerts
    all_alerts = [(lvl, msg) for t in open_txs for lvl, msg in t["alerts"]]
    if all_alerts:
        st.markdown('<div class="section-hdr">⚠️ Alerts</div>', unsafe_allow_html=True)
        for lvl, msg in all_alerts:
            cls = "alert-danger" if lvl == "danger" else "alert-warn"
            icon = "🔴" if lvl == "danger" else "🟡"
            st.markdown(f'<div class="{cls}">{icon} {msg}</div>', unsafe_allow_html=True)
        st.divider()

    # Open positions
    st.markdown('<div class="section-hdr">Open positions</div>', unsafe_allow_html=True)
    if not open_txs:
        st.markdown('<div style="color:#7a8299;font-size:13px;font-family:DM Mono,monospace;padding:20px 0;">No open positions.</div>', unsafe_allow_html=True)
    else:
        rows = []
        for t in open_txs:
            itm = current_price and current_price >= t["strike"]
            rows.append({
                "ID":           t["id"],
                "Opened":       fd(t["date_opened"]),
                "Price@Open":   fu(t["price_at_open"]),
                "Contracts":    t["num_contracts"],
                "Expiration":   fd(t["expiration"]),
                "DTE Left":     f"{t['dte_remaining']}d{'  ⚠️' if t['dte_remaining']<=7 else ''}",
                "Strike":       fu(t["strike"]) + (" 🔴" if itm else ""),
                "Premium":      fu(t["option_premium"]),
                "Prem Total":   fu(t["premium_total"]),
                "Prem ROI":     fp(t["premium_roi"]),
                "ROI Ann":      fp(t["roi_annual"]),
                "If Assigned":  fu(t["premium_if_assigned"]),
                "Total If Asgn":fu(t["total_if_assigned"]),
                "Asgn ROI":     fp(t["assigned_roi"]),
                "Asgn ROI Ann": fp(t["assigned_roi_annual"]),
                "Notes":        t["notes"] or "",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    s1,s2,s3 = st.columns(3)
    s1.metric("Total premium collected", fu(total_premium))
    s2.metric("Total P&L (closed)",      fu(total_gains))
    s3.metric("Total transactions",      len(txs))

# ════════════════════════════════════════════════════════════════
# TAB 2 — ADD TRADE
# ════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-hdr">Add / Edit transaction</div>', unsafe_allow_html=True)
    edit_id = None
    if txs:
        opts = ["— New transaction —"] + [f"#{t['id']} | {fd(t['date_opened'])} | ${t['strike']} | {t['status']}" for t in txs]
        sel  = st.selectbox("Edit existing or add new:", opts)
        if sel != "— New transaction —":
            edit_id = int(sel.split("#")[1].split(" ")[0])
    edit_t = next((t for t in txs if t["id"] == edit_id), None) if edit_id else None

    with st.form("trade_form", clear_on_submit=False):
        st.markdown('<div style="font-size:11px;color:#7a8299;font-family:DM Mono,monospace;margin-bottom:12px;">Fill in the fields below. DTE is calculated automatically.</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            date_opened   = st.date_input("Date opened", value=datetime.strptime(edit_t["date_opened"],"%Y-%m-%d").date() if edit_t else date.today())
            price_open    = st.number_input("Price at open ($)", value=float(edit_t["price_at_open"]) if edit_t else (current_price or 0.0), min_value=0.0, step=0.01, format="%.2f")
            num_contracts = st.number_input("# Contracts", value=int(edit_t["num_contracts"]) if edit_t else 1, min_value=1, step=1)
        with col2:
            expiration    = st.date_input("Expiration", value=datetime.strptime(edit_t["expiration"],"%Y-%m-%d").date() if edit_t else date.today()+timedelta(days=30))
            strike        = st.number_input("Strike ($)", value=float(edit_t["strike"]) if edit_t else 0.0, min_value=0.0, step=0.50, format="%.2f")
            option_premium= st.number_input("Option premium ($)", value=float(edit_t["option_premium"]) if edit_t else 0.0, min_value=0.0, step=0.01, format="%.2f")
        with col3:
            dte_calc = (expiration - date_opened).days
            st.markdown(f"""
            <div style="background:#1c2030;border:1px solid #262d3d;border-radius:8px;padding:12px;margin-top:28px;">
              <div style="font-size:10px;letter-spacing:0.08em;text-transform:uppercase;color:#7a8299;font-family:DM Mono,monospace;margin-bottom:4px;">DTE (auto)</div>
              <div style="font-size:22px;font-weight:600;font-family:DM Mono,monospace;color:#f5a623;">{dte_calc}</div>
            </div>""", unsafe_allow_html=True)
            status = st.selectbox("Status", ["Open","Expired","BTC","Assigned"],
                index=["Open","Expired","BTC","Assigned"].index(edit_t["status"]) if edit_t else 0)
            notes  = st.text_input("Notes", value=edit_t["notes"] or "" if edit_t else "")

        btc_price = None; date_closed = None
        if status in ["BTC","Expired","Assigned"]:
            cl1, cl2 = st.columns(2)
            with cl1:
                btc_price = st.number_input("BTC price ($)", value=float(edit_t["btc_price"]) if (edit_t and edit_t["btc_price"]) else 0.0, min_value=0.0, step=0.01, format="%.2f") if status=="BTC" else None
            with cl2:
                date_closed = st.date_input("Date closed", value=datetime.strptime(edit_t["date_closed"],"%Y-%m-%d").date() if (edit_t and edit_t["date_closed"]) else date.today())

        submitted = st.form_submit_button("💾 Save transaction", type="primary", use_container_width=True)

    # Live preview
    if option_premium > 0 and strike > 0 and num_contracts > 0 and dte_calc > 0:
        prem_total   = option_premium * 100 * num_contracts
        cost_basis_p = strike * 100 * num_contracts
        prem_roi_p   = (prem_total / cost_basis_p * 100) if cost_basis_p else 0
        roi_ann_p    = (prem_roi_p / dte_calc * 365)
        if_asgn_p    = (strike - price_open) * 100 * num_contracts
        tot_asgn_p   = if_asgn_p + prem_total
        asgn_roi_p   = (tot_asgn_p / cost_basis_p * 100) if cost_basis_p else 0
        asgn_ann_p   = (asgn_roi_p / dte_calc * 365)
        btc_pnl_p    = (prem_total - btc_price * 100 * num_contracts) if (btc_price and btc_price > 0) else None

        st.markdown('<div class="section-hdr" style="margin-top:1rem;">Live calculation preview</div>', unsafe_allow_html=True)
        p1,p2,p3,p4 = st.columns(4)
        p1.metric("Premium total",    fu(prem_total))
        p2.metric("Premium ROI",      fp(prem_roi_p))
        p3.metric("ROI Annual",       fp(roi_ann_p))
        p4.metric("If Assigned",      fu(if_asgn_p))
        p5,p6,p7,p8 = st.columns(4)
        p5.metric("Total if Assigned", fu(tot_asgn_p))
        p6.metric("Assigned ROI",      fp(asgn_roi_p))
        p7.metric("Assigned ROI Ann",  fp(asgn_ann_p))
        if btc_pnl_p is not None:
            p8.metric("P&L after BTC", fu(btc_pnl_p))

    if submitted:
        if dte_calc <= 0:
            st.error("Expiration must be after date opened.")
        elif strike <= 0 or option_premium <= 0:
            st.error("Strike and premium must be > 0.")
        else:
            tx = {"date_opened":date_opened.strftime("%Y-%m-%d"),"price_at_open":price_open,
                  "num_contracts":num_contracts,"expiration":expiration.strftime("%Y-%m-%d"),
                  "strike":strike,"option_premium":option_premium,"dte":dte_calc,
                  "btc_price":(btc_price if btc_price and btc_price>0 else None),
                  "date_closed":date_closed.strftime("%Y-%m-%d") if date_closed else None,
                  "status":status,"assigned":"Y" if status=="Assigned" else "N","notes":notes}
            if edit_id:
                update_transaction(edit_id, tx); st.success(f"Transaction #{edit_id} updated.")
            else:
                add_transaction(tx); st.success("Transaction added.")
            st.rerun()

    if edit_id:
        st.divider()
        if st.button(f"🗑️ Delete transaction #{edit_id}"):
            delete_transaction(edit_id); st.success("Deleted."); st.rerun()

# ════════════════════════════════════════════════════════════════
# TAB 3 — HISTORY
# ════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-hdr">Transaction history</div>', unsafe_allow_html=True)
    status_filter = st.multiselect("Filter by status:", ["Open","Expired","BTC","Assigned"], default=["Open","Expired","BTC","Assigned"])
    filtered = [t for t in txs if t["status"] in status_filter]

    if not filtered:
        st.info("No transactions match the filter.")
    else:
        status_icons = {"Open":"🔵","Expired":"🟢","BTC":"🟡","Assigned":"🔴"}
        rows = []
        for t in filtered:
            rows.append({
                "ID":           t["id"],
                "Opened":       fd(t["date_opened"]),
                "Closed":       fd(t["date_closed"]),
                "Days":         t["days_open"],
                "Contracts":    t["num_contracts"],
                "Strike":       fu(t["strike"]),
                "Premium":      fu(t["option_premium"]),
                "Prem Total":   fu(t["premium_total"]),
                "BTC":          fu(t["btc_price"]) if t["btc_price"] else "—",
                "Prem ROI":     fp(t["premium_roi"]),
                "ROI Ann":      fp(t["roi_annual"]),
                "If Assigned":  fu(t["premium_if_assigned"]),
                "Asgn ROI":     fp(t["assigned_roi"]),
                "Asgn ROI Ann": fp(t["assigned_roi_annual"]),
                "Status":       status_icons.get(t["status"],"") + " " + t["status"],
                "P&L":          fu(t["profit_loss"]),
                "Final ROI":    fp(t["final_roi"]),
                "Notes":        t["notes"] or "",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.divider()
        t1,t2,t3,t4 = st.columns(4)
        t1.metric("Total premium",   fu(sum(t["premium_total"] for t in filtered)))
        t2.metric("Total P&L",       fu(sum(t["profit_loss"] for t in filtered if t["profit_loss"] is not None)))
        t3.metric("Closed trades",   len([t for t in filtered if t["status"]!="Open"]))
        closed_rois = [t["final_roi"] for t in filtered if t["final_roi"] is not None]
        t4.metric("Avg final ROI",   fp(sum(closed_rois)/len(closed_rois) if closed_rois else None))

# ════════════════════════════════════════════════════════════════
# TAB 4 — EXPORT
# ════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-hdr">Export data</div>', unsafe_allow_html=True)
    if not txs:
        st.info("No transactions to export.")
    else:
        export_rows = []
        for t in txs:
            export_rows.append({
                "ID":t["id"],"Date Opened":t["date_opened"],"Date Closed":t["date_closed"] or "",
                "Days Open":t["days_open"],"Contracts":t["num_contracts"],
                "Price at Open":t["price_at_open"],"Strike":t["strike"],
                "Option Premium":t["option_premium"],"Premium Total":t["premium_total"],
                "DTE":t["dte"],"BTC Price":t["btc_price"] or "",
                "Premium ROI%":t["premium_roi"],"ROI Annual%":t["roi_annual"],
                "Premium if Assigned":t["premium_if_assigned"],"Total if Assigned":t["total_if_assigned"],
                "Assigned ROI%":t["assigned_roi"],"Assigned ROI Annual%":t["assigned_roi_annual"],
                "Status":t["status"],"Assigned Y/N":t["assigned"],
                "P&L":t["profit_loss"] or "","Final ROI%":t["final_roi"] or "","Notes":t["notes"] or "",
            })
        df_exp = pd.DataFrame(export_rows)
        csv    = df_exp.to_csv(index=False)
        st.download_button("⬇️ Download CSV", data=csv,
            file_name=f"covered_calls_{date.today()}.csv", mime="text/csv", use_container_width=True)
        st.divider()
        st.dataframe(df_exp, use_container_width=True, hide_index=True)
