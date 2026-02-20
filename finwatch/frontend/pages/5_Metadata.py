"""Page 5 — Metadata: LLM-extracted field table + Excel download."""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import get
import requests

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="Metadata — FinWatch", page_icon="🔍", layout="wide")
st.title("🔍 Extracted Metadata")

companies = get("/companies/") or []
company_options = {}
if isinstance(companies, list):
    company_options = {c["company_name"]: c["id"] for c in companies}

if not company_options:
    st.warning("No companies yet. Add companies first."); st.stop()

sel = st.selectbox("Company", list(company_options.keys()))
cid = company_options[sel]

docs = get("/documents/", {"company_id": cid}) or []
rows = []
for d in (docs if isinstance(docs, list) else []):
    meta = get(f"/documents/{d['id']}/metadata")
    if not meta or "error" in str(meta):
        continue
    rows.append({
        "Headline": meta.get("headline", ""),
        "Type": meta.get("document_type", ""),
        "Filing Date": meta.get("filing_date", ""),
        "Period End": meta.get("period_end_date", ""),
        "Language": meta.get("language", ""),
        "Income Stmt": "✅" if meta.get("income_statement") else "❌",
        "Preliminary": "✅" if meta.get("preliminary_document") else "❌",
        "Notes": "✅" if meta.get("note_flag") else "❌",
        "Audited": "✅" if meta.get("audit_flag") else "❌",
        "Source": meta.get("filing_data_source", ""),
    })

col1, col2 = st.columns([3, 1])
with col1:
    st.metric("Documents with Metadata", len(rows))
with col2:
    if st.button("📥 Download Excel Report", type="primary", use_container_width=True):
        r = requests.get(f"{API_BASE}/documents/{cid}/excel", timeout=60)
        if r.status_code == 200:
            st.download_button(
                "💾 Save Excel", r.content,
                file_name=f"finwatch_{sel}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.error("Failed to generate Excel")

if rows:
    # Filters
    col_a, col_b = st.columns(2)
    type_filter = col_a.multiselect("Filter by Type",
        list({r["Type"] for r in rows}),
        default=list({r["Type"] for r in rows}))
    search = col_b.text_input("Search Headline")

    filtered = [r for r in rows if r["Type"] in type_filter]
    if search:
        filtered = [r for r in filtered if search.lower() in (r["Headline"] or "").lower()]

    st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True)
else:
    st.info("No metadata extracted yet. Run the pipeline first.")
