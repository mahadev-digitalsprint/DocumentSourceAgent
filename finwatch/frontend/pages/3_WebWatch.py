"""Page 3 — WebWatch: page change feed with diff viewer."""
import streamlit as st
import pandas as pd
import difflib
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import get

st.set_page_config(page_title="WebWatch — FinWatch", page_icon="🌐", layout="wide")
st.title("🌐 WebWatch — Page Change Monitor")

# ── Filters ───────────────────────────────────────────────────────────────────
companies = get("/companies/") or []
company_options = {"All": None}
if isinstance(companies, list):
    company_options.update({c["company_name"]: c["id"] for c in companies})

col1, col2, col3 = st.columns(3)
sel_company = col1.selectbox("Company", list(company_options.keys()))
change_types = col2.multiselect("Change Types",
    ["PAGE_ADDED", "PAGE_DELETED", "CONTENT_CHANGED", "NEW_DOC_LINKED"],
    default=["PAGE_ADDED", "PAGE_DELETED", "CONTENT_CHANGED", "NEW_DOC_LINKED"])
hours = col3.selectbox("Time Window", [6, 12, 24, 48, 72, 168], index=2)

company_id = company_options[sel_company]
params = {"hours": hours}
if company_id:
    params["company_id"] = company_id

changes = get("/webwatch/changes", params) or []

# ── Summary metrics ───────────────────────────────────────────────────────────
if isinstance(changes, list):
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🟢 Pages Added",    sum(1 for c in changes if c.get("change_type") == "PAGE_ADDED"))
    m2.metric("🔴 Pages Deleted",  sum(1 for c in changes if c.get("change_type") == "PAGE_DELETED"))
    m3.metric("🟡 Content Changed",sum(1 for c in changes if c.get("change_type") == "CONTENT_CHANGED"))
    m4.metric("🔵 New Docs Linked",sum(1 for c in changes if c.get("change_type") == "NEW_DOC_LINKED"))
    st.divider()

# ── Change feed ───────────────────────────────────────────────────────────────
BADGES = {
    "PAGE_ADDED":       ("🟢", "#dcfce7", "#166534"),
    "PAGE_DELETED":     ("🔴", "#fee2e2", "#991b1b"),
    "CONTENT_CHANGED":  ("🟡", "#fef9c3", "#854d0e"),
    "NEW_DOC_LINKED":   ("🔵", "#dbeafe", "#1e40af"),
}

filtered = [c for c in (changes if isinstance(changes, list) else []) if c.get("change_type") in change_types]

if not filtered:
    st.info("No changes found for the selected filters.")
else:
    for c in filtered[:100]:
        ct = c.get("change_type", "")
        icon, bg, fg = BADGES.get(ct, ("⚪", "#f1f5f9", "#374151"))
        with st.container():
            st.markdown(f"""
            <div style="background:{bg};border-radius:8px;padding:12px 16px;margin-bottom:8px;border-left:4px solid {fg}">
              <b style="color:{fg}">{icon} {ct.replace('_', ' ')}</b>
              &nbsp;&nbsp;<span style="color:#374151;font-size:.85em">{c.get('detected_at','')}</span><br>
              <span style="font-size:.9em;color:#374151">{c.get('page_url','')}</span><br>
              <em style="font-size:.82em;color:#64748b">{(c.get('diff_summary') or '')[:200]}</em>
            </div>
            """, unsafe_allow_html=True)

            if c.get("new_pdf_urls"):
                with st.expander(f"📎 {len(c['new_pdf_urls'])} new PDF(s) discovered"):
                    for u in c["new_pdf_urls"]:
                        st.write(u)

            # Diff viewer
            if ct == "CONTENT_CHANGED":
                with st.expander("🔍 View Diff"):
                    diff_data = get(f"/webwatch/changes/{c['id']}/diff")
                    if "old_text" in diff_data and "new_text" in diff_data:
                        old_lines = (diff_data["old_text"] or "").splitlines()
                        new_lines = (diff_data["new_text"] or "").splitlines()
                        diff = "\n".join(difflib.unified_diff(old_lines, new_lines, lineterm="", n=3))
                        st.code(diff[:5000], language="diff")
