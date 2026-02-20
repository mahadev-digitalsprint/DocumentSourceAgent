"""
FinWatch Documents page.
"""
import os

import pandas as pd
import requests
import streamlit as st

from api_client import api

st.set_page_config(page_title="FinWatch · Documents", page_icon="📄", layout="wide")

st.title("Documents")
st.caption("Browse financial and non-financial documents with fast filters.")

all_docs = api("GET", "/documents/") or []
companies = api("GET", "/companies/") or []
co_map = {c["id"]: c["company_name"] for c in companies}

fin_docs = [d for d in all_docs if (d.get("doc_type", "")).startswith("FINANCIAL")]
nonfin_docs = [d for d in all_docs if (d.get("doc_type", "")).startswith("NON_FINANCIAL")]
unk_docs = [d for d in all_docs if d not in fin_docs and d not in nonfin_docs]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total", len(all_docs))
m2.metric("Financial", len(fin_docs))
m3.metric("Non-Financial", len(nonfin_docs))
m4.metric("Unclassified", len(unk_docs))
st.divider()

f1, f2, f3, f4 = st.columns(4)
search = f1.text_input("Search", placeholder="URL, type, or company")
co_filter = f2.selectbox("Company", ["All"] + [c["company_name"] for c in companies])
status_filter = f3.selectbox("Status", ["All", "NEW", "UPDATED", "UNCHANGED", "FAILED"])
meta_filter = f4.selectbox("Metadata", ["All", "Extracted", "Not Extracted"])


def _filter(docs):
    rows = docs
    if search:
        s = search.lower().strip()
        rows = [
            d for d in rows
            if s in (d.get("document_url", "")).lower()
            or s in (d.get("doc_type", "")).lower()
            or s in (co_map.get(d.get("company_id"), "").lower())
        ]
    if co_filter != "All":
        rows = [d for d in rows if co_map.get(d.get("company_id")) == co_filter]
    if status_filter != "All":
        rows = [d for d in rows if d.get("status") == status_filter]
    if meta_filter == "Extracted":
        rows = [d for d in rows if d.get("metadata_extracted")]
    elif meta_filter == "Not Extracted":
        rows = [d for d in rows if not d.get("metadata_extracted")]
    return rows


def _to_df(docs):
    data = []
    for d in docs:
        parts = (d.get("doc_type") or "UNKNOWN|OTHER").split("|")
        data.append(
            {
                "Company": co_map.get(d.get("company_id"), "Unknown"),
                "Category": parts[0],
                "Type": parts[-1],
                "Status": d.get("status", ""),
                "Pages": d.get("page_count", ""),
                "Size (KB)": round((d.get("file_size_bytes") or 0) / 1024, 1),
                "Metadata": "Yes" if d.get("metadata_extracted") else "No",
                "URL": d.get("document_url", ""),
            }
        )
    return pd.DataFrame(data)


t1, t2, t3 = st.tabs([f"Financial ({len(fin_docs)})", f"Non-Financial ({len(nonfin_docs)})", f"All ({len(all_docs)})"])

with t1:
    df = _to_df(_filter(fin_docs))
    if df.empty:
        st.info("No financial documents for current filters.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

with t2:
    df = _to_df(_filter(nonfin_docs))
    if df.empty:
        st.info("No non-financial documents for current filters.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

with t3:
    df = _to_df(_filter(all_docs))
    if df.empty:
        st.info("No documents for current filters.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
if st.button("Generate Excel Report", type="primary"):
    api_base = os.getenv("FINWATCH_API_BASE", "http://localhost:8080/api")
    try:
        with st.spinner("Generating workbook..."):
            response = requests.post(f"{api_base}/jobs/generate-excel", timeout=180)
        if not response.ok:
            st.error(f"Excel generation failed: {response.status_code}")
        else:
            st.download_button(
                "Download Workbook",
                data=response.content,
                file_name="finwatch_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    except Exception as exc:
        st.error(f"Excel generation failed: {exc}")
