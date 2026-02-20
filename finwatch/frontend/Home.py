"""
FinWatch — Home / Dashboard (combined entry point)
Full KPI overview, charts, pipeline trigger, and recent changes feed.
"""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from api_client import api

st.set_page_config(
    page_title="FinWatch · Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  /* Sidebar */
  [data-testid="stSidebar"] { background: #0d1117; }
  [data-testid="stSidebar"] * { color: #c9d1d9 !important; }

  /* KPI cards */
  .kpi-box {
    background:#161b22; border:1px solid #30363d; border-radius:10px;
    padding:1rem 0.75rem; text-align:center; margin-bottom:8px;
  }
  .kpi-val { font-size:2rem; font-weight:700; color:#58a6ff; }
  .kpi-fin { color:#3fb950; }
  .kpi-non { color:#58a6ff; }
  .kpi-chg { color:#ffa657; }
  .kpi-lbl { font-size:0.78rem; color:#8b949e; margin-top:4px; }

  /* Header banner */
  .hero {
    background: linear-gradient(135deg, #0d1117 0%, #1a2332 50%, #162032 100%);
    border: 1px solid #30363d; border-radius:12px;
    padding:24px 28px; margin-bottom:20px;
    display:flex; align-items:center; gap:16px;
  }
  .hero-title { font-size:1.8rem; font-weight:700; color:#e6edf3; margin:0; }
  .hero-sub   { color:#8b949e; font-size:0.9rem; margin:4px 0 0; }

  /* Change feed cards */
  .chg-new  { border-left:3px solid #3fb950; background:#0e1f14; }
  .chg-upd  { border-left:3px solid #ffa657; background:#1f1200; }
  .chg-del  { border-left:3px solid #f85149; background:#1f0000; }
  .chg-oth  { border-left:3px solid #8b949e; background:#161b22; }
  .chg-card { padding:7px 11px; border-radius:0 7px 7px 0; margin:4px 0; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <span style="font-size:2.4rem">📊</span>
  <div>
    <div class="hero-title">FinWatch Dashboard</div>
    <div class="hero-sub">Financial Document Intelligence &amp; Website Monitoring — live overview</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Fetch data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading data…"):
    companies = api("GET", "/companies/") or []
    docs      = api("GET", "/documents/") or []
    changes   = api("GET", "/documents/changes/", params={"hours": 24}) or []
    pg_chgs   = api("GET", "/webwatch/changes",   params={"hours": 24}) or []

if not isinstance(companies, list): companies = []
if not isinstance(docs, list):      docs = []
if not isinstance(changes, list):   changes = []
if not isinstance(pg_chgs, list):   pg_chgs = []

active_cos  = [c for c in companies if c.get("active")]
fin_docs    = [d for d in docs if (d.get("doc_type","")).startswith("FINANCIAL")]
nonfin_docs = [d for d in docs if (d.get("doc_type","")).startswith("NON_FINANCIAL")]

# ── KPI Row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5, k6 = st.columns(6)
kpis = [
    (k1, len(active_cos),       "🏢 Active Companies", "kpi-val"),
    (k2, len(fin_docs),         "💰 Financial Docs",    "kpi-val kpi-fin"),
    (k3, len(nonfin_docs),      "📋 Non-Financial Docs","kpi-val kpi-non"),
    (k4, len(docs),             "📄 Total Docs",         "kpi-val"),
    (k5, len(changes),          "🔔 Doc Changes 24h",   "kpi-val kpi-chg"),
    (k6, len(pg_chgs),          "🌐 Page Changes 24h",  "kpi-val kpi-chg"),
]
for col, val, label, cls in kpis:
    col.markdown(
        f'<div class="kpi-box"><div class="{cls}">{val}</div>'
        f'<div class="kpi-lbl">{label}</div></div>',
        unsafe_allow_html=True,
    )

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
if docs:
    ch1, ch2, ch3 = st.columns(3)

    with ch1:
        st.subheader("📊 Category Split")
        cat_data = pd.Series({
            "Financial":     len(fin_docs),
            "Non-Financial": len(nonfin_docs),
            "Unknown":       max(0, len(docs) - len(fin_docs) - len(nonfin_docs)),
        })
        st.bar_chart(cat_data, color="#58a6ff")

    with ch2:
        st.subheader("📂 Top Document Types")
        type_counts: dict = {}
        for d in docs:
            t = (d.get("doc_type") or "UNKNOWN").split("|")[-1]
            type_counts[t] = type_counts.get(t, 0) + 1
        top_types = dict(sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:8])
        st.bar_chart(pd.Series(top_types), color="#3fb950")

    with ch3:
        st.subheader("🏢 Docs per Company")
        co_map = {c["id"]: c["company_name"] for c in companies}
        co_counts: dict = {}
        for d in docs:
            name = co_map.get(d.get("company_id"), "Unknown")
            co_counts[name] = co_counts.get(name, 0) + 1
        top_cos = dict(sorted(co_counts.items(), key=lambda x: x[1], reverse=True)[:8])
        if top_cos:
            st.bar_chart(pd.Series(top_cos), color="#ffa657")
        else:
            st.info("No data yet")
else:
    st.info("📭 No documents yet — add a company and run the pipeline to get started.")

st.divider()

# ── Pipeline Trigger ───────────────────────────────────────────────────────────
st.subheader("🚀 Run Pipeline")
p1, p2, p3, p4 = st.columns([2, 2, 2, 2])

with p1:
    run_mode = st.radio("Selection", ["All active companies", "Single company"], horizontal=True)

with p2:
    engine_mode = st.radio("Engine", ["Redis (Async)", "Direct (Sync)"], horizontal=True, index=1, 
                           help="Redis mode requires a running Redis/Celery worker. Direct mode runs synchronously but might be slower.")

with p3:
    co_map_name = {c["company_name"]: c["id"] for c in active_cos}
    if run_mode == "Single company" and co_map_name:
        sel_co = st.selectbox("Company", list(co_map_name.keys()))
    elif run_mode == "Single company":
        st.warning("No active companies.")
        sel_co = None
    else:
        st.write("")

with p4:
    st.write("")
    st.write("")
    is_direct = (engine_mode == "Direct (Sync)")
    if st.button("▶ Start Pipeline", type="primary", use_container_width=True):
        with st.spinner("Pipeline running (this may take a few minutes in Direct mode)..."):
            if run_mode == "All active companies":
                endpoint = "/jobs/run-all-direct" if is_direct else "/jobs/run-all"
                r = api("POST", endpoint)
            elif sel_co:
                co_id = co_map_name[sel_co]
                endpoint = f"/jobs/run-direct/{co_id}" if is_direct else f"/jobs/run/{co_id}"
                r = api("POST", endpoint)
            else:
                r = None
            
        if r:
            if is_direct:
                st.success("✅ Direct Pipeline Complete!")
                st.json(r.get("result", {}))
            else:
                st.success(f"✅ Pipeline queued! Job: `{r.get('job_id', 'N/A')}`")
        else:
            if not is_direct:
                st.error("❌ Pipeline trigger failed. Is Redis running? Use 'Direct (Sync)' mode instead.")
            else:
                st.error("❌ Direct Pipeline failed. Check backend logs.")

st.divider()

# ── Recent Changes Feed ────────────────────────────────────────────────────────
f1, f2 = st.columns(2)

with f1:
    st.subheader("🔔 Recent Document Changes")
    if changes:
        for chg in changes[:12]:
            ct    = chg.get("change_type", "")
            cls   = "chg-new" if ct == "NEW" else "chg-upd" if ct == "UPDATED" else "chg-del" if ct == "REMOVED" else "chg-oth"
            co    = chg.get("company_name", "")
            dtype = (chg.get("doc_type") or "").split("|")[-1]
            ts    = chg.get("detected_at", "")[:19]
            st.markdown(f"""
            <div class="chg-card {cls}">
              <strong>{ct}</strong>
              <span style="color:#8b949e;font-size:.82rem"> · {co} · {dtype}</span><br/>
              <span style="color:#6e7681;font-size:.75rem">{ts}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No document changes in the last 24 hours.")

with f2:
    st.subheader("🌐 Recent Page Changes")
    if pg_chgs:
        for pc in pg_chgs[:12]:
            ct    = pc.get("change_type", "")
            cls   = "chg-new" if "ADDED" in ct else "chg-del" if "DELETED" in ct else "chg-upd" if "CHANGED" in ct else "chg-oth"
            url   = (pc.get("page_url") or "")[:60]
            ts    = pc.get("detected_at", "")[:19]
            st.markdown(f"""
            <div class="chg-card {cls}">
              <strong>{ct.replace('_',' ')}</strong><br/>
              <code style="font-size:.75rem">{url}</code><br/>
              <span style="color:#6e7681;font-size:.75rem">{ts}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No page changes in the last 24 hours.")

# ── Quick nav ──────────────────────────────────────────────────────────────────
st.divider()
st.caption("**Quick links** → use the sidebar to navigate to Companies · WebWatch · Documents · Metadata · Changes · Analytics")
