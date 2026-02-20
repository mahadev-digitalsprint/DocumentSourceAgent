"""
FinWatch — Metadata Page
Shows all LLM-extracted metadata: financial fields (revenue, profit, EPS) +
non-financial fields (topics, regulatory body, certifications).
"""
import io
import streamlit as st
import pandas as pd
from api_client import api

st.set_page_config(page_title="FinWatch · Metadata", page_icon="🔬", layout="wide")

st.title("🔬 Extracted Metadata")
st.caption("LLM-extracted structured fields from all documents — financial and non-financial.")

# ── Fetch ──────────────────────────────────────────────────────────────────────
docs      = api("GET", "/documents/") or []
companies = api("GET", "/companies/") or []
co_map    = {c["id"]: c["company_name"] for c in companies}

fin_docs    = [d for d in docs if (d.get("doc_type","")).startswith("FINANCIAL") and d.get("metadata_extracted")]
nonfin_docs = [d for d in docs if (d.get("doc_type","")).startswith("NON_FINANCIAL") and d.get("metadata_extracted")]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total with Metadata", len([d for d in docs if d.get("metadata_extracted")]))
m2.metric("💰 Financial", len(fin_docs))
m3.metric("📋 Non-Financial", len(nonfin_docs))
m4.metric("⏳ Pending Extraction", len([d for d in docs if not d.get("metadata_extracted")]))

st.divider()

# ── Filters ────────────────────────────────────────────────────────────────────
f1, f2, f3 = st.columns(3)
co_filt   = f1.selectbox("Company", ["All"] + [c["company_name"] for c in companies])
audit_filt = f2.selectbox("Audit Status", ["All", "Audited", "Unaudited"])
src_filt  = f3.text_input("Search headline / type")

# ── Fetch full metadata from API ───────────────────────────────────────────────
all_meta = api("GET", "/metadata/") or []

tab_fin, tab_nonfin = st.tabs([
    f"💰 Financial Metadata ({len(fin_docs)})",
    f"📋 Non-Financial Metadata ({len(nonfin_docs)})",
])


def _filter_meta(meta_list, category):
    result = meta_list
    if co_filt != "All":
        result = [m for m in result if m.get("company_name") == co_filt]
    if audit_filt != "All":
        result = [m for m in result if m.get("audit_status") == audit_filt]
    if src_filt:
        sl = src_filt.lower()
        result = [m for m in result if sl in (m.get("headline") or "").lower()
                  or sl in (m.get("document_type") or "").lower()]
    return [m for m in result if (m.get("document_category") or "").startswith(category)]


with tab_fin:
    fin_meta = _filter_meta(all_meta, "FINANCIAL")
    if fin_meta:
        fin_rows = []
        for m in fin_meta:
            raw = m.get("raw_llm_response") or {}
            fin_rows.append({
                "Company":       m.get("company_name", ""),
                "Doc Type":      m.get("document_type", ""),
                "Headline":      m.get("headline", ""),
                "Filing Date":   m.get("filing_date", ""),
                "Period End":    m.get("period_end_date", ""),
                "Fiscal Year":   raw.get("fiscal_year", ""),
                "Quarter":       raw.get("fiscal_quarter", ""),
                "Currency":      raw.get("currency", ""),
                "Revenue":       raw.get("revenue", ""),
                "Net Profit":    raw.get("net_profit", ""),
                "EBITDA":        raw.get("ebitda", ""),
                "EPS":           raw.get("eps", ""),
                "Audit Status":  raw.get("audit_status", ""),
                "Preliminary":   "Yes" if raw.get("is_preliminary") else "No",
                "Language":      m.get("language", ""),
                "Notes":         raw.get("financial_notes", ""),
            })
        df_fin = pd.DataFrame(fin_rows)

        # Sort options
        sort_col = st.selectbox("Sort by", df_fin.columns.tolist(), index=0, key="sort_fin")
        df_fin = df_fin.sort_values(sort_col, ascending=True)

        st.dataframe(df_fin, use_container_width=True, height=420)

        # Download
        buf = io.BytesIO()
        df_fin.to_excel(buf, index=False, sheet_name="Financial Metadata")
        st.download_button("📥 Download Financial Metadata (Excel)", buf.getvalue(),
                          file_name="finwatch_financial_metadata.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No financial metadata extracted yet. Run the pipeline on companies with annual reports, results, etc.")

with tab_nonfin:
    nf_meta = _filter_meta(all_meta, "NON_FINANCIAL")
    if nf_meta:
        nf_rows = []
        for m in nf_meta:
            raw = m.get("raw_llm_response") or {}
            topics = raw.get("key_topics", [])
            certs  = raw.get("certifications", [])
            nf_rows.append({
                "Company":          m.get("company_name", ""),
                "Doc Type":         m.get("document_type", ""),
                "Headline":         m.get("headline", ""),
                "Filing Date":      m.get("filing_date", ""),
                "Regulatory Body":  raw.get("regulatory_body", ""),
                "Compliance Period":raw.get("compliance_period", ""),
                "Scope":            raw.get("document_scope", ""),
                "Audience":         raw.get("target_audience", ""),
                "Key Topics":       ", ".join(topics) if isinstance(topics, list) else str(topics),
                "Key Findings":     raw.get("key_findings", ""),
                "Certifications":   ", ".join(certs) if isinstance(certs, list) else str(certs),
                "Language":         m.get("language", ""),
            })
        df_nf = pd.DataFrame(nf_rows)

        sort_col2 = st.selectbox("Sort by", df_nf.columns.tolist(), index=0, key="sort_nf")
        df_nf = df_nf.sort_values(sort_col2, ascending=True)

        st.dataframe(df_nf, use_container_width=True, height=420)

        buf2 = io.BytesIO()
        df_nf.to_excel(buf2, index=False, sheet_name="Non-Financial Metadata")
        st.download_button("📥 Download Non-Financial Metadata (Excel)", buf2.getvalue(),
                          file_name="finwatch_nonfin_metadata.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No non-financial metadata extracted yet.")
