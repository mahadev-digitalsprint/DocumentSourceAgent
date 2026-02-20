"""Page 4 — Documents: full browser with filters."""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import get

st.set_page_config(page_title="Documents — FinWatch", page_icon="📄", layout="wide")
st.title("📄 Document Browser")

companies = get("/companies/") or []
company_options = {"All": None}
if isinstance(companies, list):
    company_options.update({c["company_name"]: c["id"] for c in companies})

col1, col2, col3, col4 = st.columns(4)
sel_company = col1.selectbox("Company", list(company_options.keys()))
sel_type    = col2.selectbox("Document Type", ["All", "Annual Report", "Quarterly Report",
                                               "Financial Statement", "ESG Report", "Unknown"])
sel_status  = col3.selectbox("Status", ["All", "NEW", "UPDATED", "UNCHANGED", "FAILED"])
sel_scanned = col4.selectbox("Scanned PDF?", ["All", "Yes", "No"])

params = {}
if company_options[sel_company]:
    params["company_id"] = company_options[sel_company]
if sel_type != "All":
    params["doc_type"] = sel_type
if sel_status != "All":
    params["status"] = sel_status

docs = get("/documents/", params) or []

if isinstance(docs, list):
    if sel_scanned == "Yes":
        docs = [d for d in docs if d.get("is_scanned")]
    elif sel_scanned == "No":
        docs = [d for d in docs if not d.get("is_scanned")]

    # Summary
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shown", len(docs))
    c2.metric("Extracted", sum(1 for d in docs if d.get("metadata_extracted")))
    c3.metric("Scanned", sum(1 for d in docs if d.get("is_scanned")))
    c4.metric("Failed", sum(1 for d in docs if d.get("status") == "FAILED"))
    st.divider()

    if docs:
        df = pd.DataFrame([{
            "Status": d.get("status"), "Type": d.get("doc_type"),
            "Language": d.get("language"), "Pages": d.get("page_count"),
            "Size (KB)": d.get("file_size_kb"), "Scanned": "✅" if d.get("is_scanned") else "",
            "Extracted": "✅" if d.get("metadata_extracted") else "❌",
            "URL": d.get("url"), "Last Checked": d.get("last_checked", "")[:10],
        } for d in docs])

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn("URL"),
                "Status": st.column_config.TextColumn("Status", width="small"),
            }
        )

        # Detailed view
        st.subheader("🔍 Document Detail")
        selected_url = st.selectbox("Select document", [d.get("url") for d in docs])
        if selected_url:
            doc = next((d for d in docs if d.get("url") == selected_url), None)
            if doc:
                meta = get(f"/documents/{doc['id']}/metadata")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write("**Document Info**")
                    st.json({"Type": doc.get("doc_type"), "Status": doc.get("status"),
                             "Pages": doc.get("page_count"), "Language": doc.get("language"),
                             "Scanned": doc.get("is_scanned"), "Size KB": doc.get("file_size_kb")})
                with col_b:
                    if "error" not in str(meta).lower() and meta:
                        st.write("**Extracted Metadata**")
                        st.json(meta)
    else:
        st.info("No documents match the selected filters.")
