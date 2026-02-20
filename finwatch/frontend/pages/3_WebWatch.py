"""
FinWatch — WebWatch Page
IR website page change monitor: snapshots, change feed, diff viewer.
"""
import streamlit as st
import difflib
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import api

st.set_page_config(page_title="FinWatch · WebWatch", page_icon="🌐", layout="wide")
st.title("🌐 WebWatch — Page Change Monitor")
st.caption("Monitors IR website pages for additions, deletions, and content changes.")

# ── Filters ────────────────────────────────────────────────────────────────────
companies = api("GET", "/companies/") or []
company_options = {"All": None}
if isinstance(companies, list):
    company_options.update({c["company_name"]: c["id"] for c in companies})

col1, col2, col3 = st.columns(3)
sel_company = col1.selectbox("Company", list(company_options.keys()))
change_types = col2.multiselect(
    "Change Types",
    ["PAGE_ADDED", "PAGE_DELETED", "CONTENT_CHANGED", "NEW_DOC_LINKED"],
    default=["PAGE_ADDED", "PAGE_DELETED", "CONTENT_CHANGED", "NEW_DOC_LINKED"],
)
hours = col3.selectbox("Time Window", [6, 12, 24, 48, 72, 168], index=2,
                        format_func=lambda h: f"Last {h}h" if h < 48 else f"Last {h//24}d")

company_id = company_options[sel_company]
params = {"hours": hours}
if company_id:
    params["company_id"] = company_id

# ── WebWatch tabs ──────────────────────────────────────────────────────────────
tab_changes, tab_snapshots = st.tabs(["🔔 Page Changes", "📸 Page Snapshots"])

with tab_changes:
    changes = api("GET", "/webwatch/changes", params=params) or []
    if not isinstance(changes, list):
        changes = []

    if changes:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🟢 Pages Added",     sum(1 for c in changes if c.get("change_type") == "PAGE_ADDED"))
        m2.metric("🔴 Pages Deleted",   sum(1 for c in changes if c.get("change_type") == "PAGE_DELETED"))
        m3.metric("🟡 Content Changed", sum(1 for c in changes if c.get("change_type") == "CONTENT_CHANGED"))
        m4.metric("🔵 New PDFs Linked", sum(1 for c in changes if c.get("change_type") == "NEW_DOC_LINKED"))
        st.divider()

    BADGES = {
        "PAGE_ADDED":      ("🟢", "#0e4429", "#3fb950"),
        "PAGE_DELETED":    ("🔴", "#3d0000", "#f85149"),
        "CONTENT_CHANGED": ("🟡", "#3d2100", "#ffa657"),
        "NEW_DOC_LINKED":  ("🔵", "#0c1e3c", "#58a6ff"),
    }

    filtered = [c for c in changes if c.get("change_type") in change_types]

    if not filtered:
        st.info("No changes found for the selected filters.")
    else:
        for c in filtered[:100]:
            ct = c.get("change_type", "")
            icon, bg, fg = BADGES.get(ct, ("⚪", "#0d1117", "#8b949e"))
            new_pdfs = c.get("new_pdf_urls") or []
            pdf_notice = f'&nbsp;<span style="color:#3fb950">+{len(new_pdfs)} PDFs</span>' if new_pdfs else ""

            st.markdown(f"""
            <div style="background:{bg};border-radius:8px;padding:12px 16px;margin-bottom:8px;border-left:4px solid {fg}">
              <b style="color:{fg}">{icon} {ct.replace('_', ' ')}</b>{pdf_notice}
              &nbsp;&nbsp;<span style="color:#8b949e;font-size:.8em">{c.get('detected_at','')[:19]}</span><br/>
              <code style="font-size:.82em;color:#c9d1d9">{(c.get('page_url') or '')[:100]}</code><br/>
              <em style="font-size:.8em;color:#8b949e">{(c.get('diff_summary') or '')[:200]}</em>
            </div>
            """, unsafe_allow_html=True)

            if new_pdfs:
                with st.expander(f"📎 {len(new_pdfs)} new PDF(s) discovered"):
                    for u in new_pdfs:
                        st.markdown(f"- [{u[:80]}]({u})" if isinstance(u, str) else f"- {u}")

            if ct == "CONTENT_CHANGED":
                with st.expander("🔍 View Diff"):
                    diff_data = api("GET", f"/webwatch/changes/{c['id']}/diff") or {}
                    if isinstance(diff_data, dict) and "old_text" in diff_data:
                        old_lines = (diff_data.get("old_text") or "").splitlines()
                        new_lines = (diff_data.get("new_text") or "").splitlines()
                        diff = "\n".join(difflib.unified_diff(old_lines, new_lines, lineterm="", n=3))
                        st.code(diff[:5000], language="diff")
                    else:
                        st.info("Diff data not available.")

with tab_snapshots:
    params2 = {}
    if company_id:
        params2["company_id"] = company_id
    snaps = api("GET", "/webwatch/snapshots", params=params2) or []
    if not isinstance(snaps, list):
        snaps = []

    if snaps:
        s1, s2, s3 = st.columns(3)
        s1.metric("Pages Tracked", len(snaps))
        s2.metric("Active Pages", sum(1 for s in snaps if s.get("is_active")))
        s3.metric("Total PDFs Found", sum(s.get("pdf_count", 0) for s in snaps))
        st.divider()

        import pandas as pd
        rows = [{
            "Page URL":         s.get("page_url",""),
            "PDFs Found":       s.get("pdf_count", 0),
            "Status Code":      s.get("status_code",""),
            "Active":           "✅" if s.get("is_active") else "❌",
            "Last Seen":        s.get("last_seen","")[:19],
        } for s in snaps]
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True,
            column_config={"Page URL": st.column_config.LinkColumn("Page URL", display_text="🔗 Open")})
    else:
        st.info("No page snapshots yet — run the pipeline to start monitoring.")

# ── Trigger scan ───────────────────────────────────────────────────────────────
st.divider()
c1, c2 = st.columns([3, 1])
c1.markdown("**Run an immediate WebWatch scan** for all active companies.")
if c2.button("🔍 Scan Now", type="primary", use_container_width=True):
    r = api("POST", "/jobs/webwatch-now")
    if r:
        st.success(f"✅ WebWatch scan triggered! Job: `{r.get('job_id','N/A')}`")
    else:
        st.warning("Scan triggered but Celery may not be running.")
