"""
FinWatch — Dashboard Page
Improved: financial/non-financial KPIs, charts, pipeline trigger with live status.
"""
import time
import streamlit as st
import pandas as pd
from api_client import api

st.set_page_config(page_title="FinWatch · Dashboard", page_icon="📊", layout="wide")

st.markdown("""
<style>
  .kpi-box {background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:1rem;text-align:center;}
  .kpi-val {font-size:2rem;font-weight:700;color:#58a6ff;}
  .kpi-fin {color:#39d353;}
  .kpi-non {color:#3fb950;}
  .kpi-chg {color:#f85149;}
  .kpi-lbl {font-size:0.8rem;color:#8b949e;margin-top:4px;}
  .change-row {border-left:3px solid #58a6ff;padding-left:8px;margin:4px 0;}
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard")
st.caption("Real-time financial intelligence pipeline overview.")

# ── Fetch data ─────────────────────────────────────────────────────────────────
companies = api("GET", "/companies/") or []
docs      = api("GET", "/documents/") or []
changes   = api("GET", "/changes/document?hours=24") or []
pg_chgs   = api("GET", "/webwatch/changes?hours=24") or []
active_cos = [c for c in companies if c.get("active")]

# ── KPI Row ────────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5, k6 = st.columns(6)
fin_docs    = [d for d in docs if (d.get("doc_type","")).startswith("FINANCIAL")]
nonfin_docs = [d for d in docs if (d.get("doc_type","")).startswith("NON_FINANCIAL")]

with k1: st.markdown(f'<div class="kpi-box"><div class="kpi-val">{len(active_cos)}</div><div class="kpi-lbl">🏢 Active Companies</div></div>', unsafe_allow_html=True)
with k2: st.markdown(f'<div class="kpi-box"><div class="kpi-val kpi-fin">{len(fin_docs)}</div><div class="kpi-lbl">💰 Financial Docs</div></div>', unsafe_allow_html=True)
with k3: st.markdown(f'<div class="kpi-box"><div class="kpi-val kpi-non">{len(nonfin_docs)}</div><div class="kpi-lbl">📋 Non-Financial Docs</div></div>', unsafe_allow_html=True)
with k4: st.markdown(f'<div class="kpi-box"><div class="kpi-val">{len(docs)}</div><div class="kpi-lbl">📄 Total Documents</div></div>', unsafe_allow_html=True)
with k5: st.markdown(f'<div class="kpi-box"><div class="kpi-val kpi-chg">{len(changes)}</div><div class="kpi-lbl">🔔 Doc Changes 24h</div></div>', unsafe_allow_html=True)
with k6: st.markdown(f'<div class="kpi-box"><div class="kpi-val kpi-chg">{len(pg_chgs)}</div><div class="kpi-lbl">🌐 Page Changes 24h</div></div>', unsafe_allow_html=True)

st.divider()

# ── Charts row ────────────────────────────────────────────────────────────────
if docs:
    chart1, chart2 = st.columns(2)

    with chart1:
        st.subheader("📊 Document Category Breakdown")
        cat_counts = {"Financial": len(fin_docs), "Non-Financial": len(nonfin_docs),
                      "Unknown": len(docs) - len(fin_docs) - len(nonfin_docs)}
        st.bar_chart(pd.Series(cat_counts), color="#58a6ff")

    with chart2:
        st.subheader("📂 Document Types")
        type_counts = {}
        for d in docs:
            t = (d.get("doc_type") or "UNKNOWN").split("|")[-1]
            type_counts[t] = type_counts.get(t, 0) + 1
        top_types = dict(sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        st.bar_chart(pd.Series(top_types), color="#3fb950")

    st.divider()

# ── Pipeline trigger ───────────────────────────────────────────────────────────
st.subheader("🚀 Run Pipeline")
p1, p2, p3 = st.columns([3, 2, 2])

with p1:
    run_mode = st.radio("Run mode", ["All active companies", "Single company"], horizontal=True)

with p2:
    if run_mode == "Single company":
        co_names = {c["company_name"]: c["id"] for c in active_cos}
        sel_co = st.selectbox("Select company", list(co_names.keys()))
    else:
        sel_co = None

with p3:
    if st.button("▶ Start Pipeline", type="primary", use_container_width=True):
        if run_mode == "All active companies":
            r = api("POST", "/jobs/run-all")
        else:
            co_id = co_names[sel_co]
            r = api("POST", f"/jobs/run/{co_id}")
        if r:
            st.success(f"✅ Pipeline started! Job: `{r.get('job_id','N/A')}`")
        else:
            st.error("Pipeline trigger failed.")

st.divider()

# ── Recent changes feed ────────────────────────────────────────────────────────
ch1, ch2 = st.columns(2)

with ch1:
    st.subheader("🔔 Recent Document Changes")
    if changes:
        for chg in changes[:10]:
            chg_type = chg.get("change_type", "")
            color = "#f85149" if chg_type == "NEW" else "#ffa657" if chg_type == "UPDATED" else "#8b949e"
            st.markdown(f"""
            <div style="border-left:3px solid {color};padding:6px 10px;margin:4px 0;background:#0d1117;border-radius:0 6px 6px 0;">
              <span style="color:{color};font-weight:600;">{chg_type}</span>
              <span style="color:#c9d1d9;font-size:0.85rem;"> · {chg.get('company_name','')} · {chg.get('doc_type','').split('|')[-1]}</span><br/>
              <span style="color:#8b949e;font-size:0.75rem;">{chg.get('detected_at','')[:19]}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No document changes in last 24 hours.")

with ch2:
    st.subheader("🌐 Recent Page Changes (WebWatch)")
    if pg_chgs:
        for pc in pg_chgs[:10]:
            ct = pc.get("change_type", "")
            badge_col = "#58a6ff" if "ADDED" in ct else "#f85149" if "DELETED" in ct else "#ffa657"
            st.markdown(f"""
            <div style="border-left:3px solid {badge_col};padding:6px 10px;margin:4px 0;background:#0d1117;border-radius:0 6px 6px 0;">
              <span style="color:{badge_col};font-weight:600;">{ct}</span>
              <span style="color:#8b949e;font-size:0.75rem;"> · {pc.get('page_url','')[:50]}</span><br/>
              <span style="color:#8b949e;font-size:0.75rem;">{pc.get('detected_at','')[:19]}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No page changes in last 24 hours.")
