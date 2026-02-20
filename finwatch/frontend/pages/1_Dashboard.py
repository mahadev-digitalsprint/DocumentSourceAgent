"""Page 1 — Dashboard: KPIs, recent changes, run pipeline."""
import time
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import get, post

st.set_page_config(page_title="Dashboard — FinWatch", page_icon="📈", layout="wide")
st.title("📈 Dashboard")

# ── KPI row ───────────────────────────────────────────────────────────────────
companies = get("/companies/") or []
docs      = get("/documents/") or []
changes   = get("/documents/changes/") or []
page_chgs = get("/webwatch/changes?hours=24") or []

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Companies",       len(companies) if isinstance(companies, list) else "—")
c2.metric("Total Docs",      len(docs)      if isinstance(docs, list)      else "—")
c3.metric("New (24h)",       sum(1 for c in (changes if isinstance(changes, list) else []) if c.get("change_type") == "NEW"))
c4.metric("Updated (24h)",   sum(1 for c in (changes if isinstance(changes, list) else []) if c.get("change_type") == "UPDATED"))
c5.metric("Page Changes",    len(page_chgs) if isinstance(page_chgs, list) else "—")
c6.metric("Scanned PDFs",    sum(1 for d in (docs if isinstance(docs, list) else []) if d.get("is_scanned")))

st.divider()

# ── Pipeline trigger ──────────────────────────────────────────────────────────
st.subheader("🚀 Run Pipeline")
col_a, col_b, col_c = st.columns(3)

with col_a:
    if isinstance(companies, list) and companies:
        sel = st.selectbox("Select Company", ["All"] + [c["company_name"] for c in companies])
        if st.button("▶ Run Selected Pipeline", type="primary", use_container_width=True):
            if sel == "All":
                res = post("/jobs/run-all")
            else:
                cid = next(c["id"] for c in companies if c["company_name"] == sel)
                res = post(f"/jobs/run/{cid}")
            if res and "task_id" in res:
                st.success(f"Pipeline queued: `{res['task_id']}`")
                # Poll status
                with st.spinner("Running pipeline…"):
                    for _ in range(30):
                        time.sleep(2)
                        status = get(f"/jobs/status/{res['task_id']}")
                        if status.get("status") in ("SUCCESS", "FAILURE"):
                            break
                if status.get("status") == "SUCCESS":
                    st.balloons()
                    st.success("Pipeline completed!")
                else:
                    st.warning(f"Status: {status.get('status')}")

with col_b:
    if st.button("🌐 Run WebWatch Now", use_container_width=True):
        res = post("/jobs/webwatch-now")
        st.info(f"WebWatch queued: `{res.get('task_id')}`")

with col_c:
    if st.button("📧 Send Digest Now", use_container_width=True):
        res = post("/jobs/digest-now")
        st.info(f"Digest queued: `{res.get('task_id')}`")

st.divider()

# ── Company Overview table ─────────────────────────────────────────────────────
st.subheader("🏢 Company Overview")
if isinstance(companies, list) and companies:
    rows = []
    for c in companies:
        cdocs = [d for d in (docs if isinstance(docs, list) else []) if d.get("company_id") == c["id"]]
        rows.append({
            "Company": c["company_name"],
            "Website": c["website_url"],
            "Total Docs": len(cdocs),
            "Extracted": sum(1 for d in cdocs if d.get("metadata_extracted")),
            "New (24h)": sum(1 for ch in (changes if isinstance(changes, list) else [])
                            if any(d.get("id") == ch.get("document_id") and d.get("company_id") == c["id"] for d in cdocs)
                            and ch.get("change_type") == "NEW"),
            "Status": "✅ Active" if c.get("active") else "⏸ Paused",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── Recent changes feed ────────────────────────────────────────────────────────
st.subheader("🔔 Recent Changes (24h)")
if isinstance(changes, list) and changes:
    df = pd.DataFrame(changes[:50])
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No document changes in the last 24 hours")
