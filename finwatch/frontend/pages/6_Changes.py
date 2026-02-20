"""Page 6 — Changes: 24h document & page change log."""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import get

st.set_page_config(page_title="Changes — FinWatch", page_icon="🔄", layout="wide")
st.title("🔄 Change Log")

companies = get("/companies/") or []
cmap = {"All": None}
if isinstance(companies, list):
    cmap.update({c["company_name"]: c["id"] for c in companies})

col1, col2 = st.columns(2)
sel = col1.selectbox("Company", list(cmap.keys()))
hours = col2.selectbox("Time Window (hours)", [6, 12, 24, 48, 72, 168], index=2)
cid = cmap[sel]

# ── Doc changes ───────────────────────────────────────────────────────────────
tab_docs, tab_pages = st.tabs(["📄 Document Changes", "🌐 Page Changes"])

with tab_docs:
    params = {"hours": hours}
    if cid:
        params["company_id"] = cid
    changes = get("/documents/changes/", params) or []

    if isinstance(changes, list) and changes:
        m1, m2, m3 = st.columns(3)
        m1.metric("🟢 New Docs",     sum(1 for c in changes if c.get("change_type") == "NEW"))
        m2.metric("🟡 Updated Docs", sum(1 for c in changes if c.get("change_type") == "UPDATED"))
        m3.metric("🔴 Removed Docs", sum(1 for c in changes if c.get("change_type") == "REMOVED"))

        df = pd.DataFrame([{
            "Detected At": c.get("detected_at","")[:19],
            "Change": c.get("change_type"),
            "Doc ID": c.get("document_id"),
        } for c in changes])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No document changes in the selected window.")

# ── Page changes ──────────────────────────────────────────────────────────────
with tab_pages:
    params = {"hours": hours}
    if cid:
        params["company_id"] = cid
    page_changes = get("/webwatch/changes", params) or []

    COLOUR = {
        "PAGE_ADDED":      "#dcfce7",
        "PAGE_DELETED":    "#fee2e2",
        "CONTENT_CHANGED": "#fef9c3",
        "NEW_DOC_LINKED":  "#dbeafe",
    }

    if isinstance(page_changes, list) and page_changes:
        for pc in page_changes[:100]:
            ct = pc.get("change_type", "")
            bg = COLOUR.get(ct, "#f8fafc")
            st.markdown(f"""
            <div style="background:{bg};border-radius:8px;padding:10px 14px;margin-bottom:6px">
              <b>{ct.replace('_',' ')}</b> — <code>{pc.get('page_url','')[:80]}</code><br>
              <small style="color:#64748b">{pc.get('detected_at','')[:19]} — {(pc.get('diff_summary') or '')[:150]}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No page changes in the selected window.")
