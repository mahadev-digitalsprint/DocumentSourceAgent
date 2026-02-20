"""
FinWatch — Documents Page
Full document browser: Financial / Non-Financial tabs, type filter, metadata panel.
"""
import streamlit as st
import pandas as pd
from api_client import api

st.set_page_config(page_title="FinWatch · Documents", page_icon="📄", layout="wide")

st.markdown("""
<style>
  .doc-card{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:0.8rem;margin:4px 0;}
  .fin-badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:0.72rem;font-weight:700;}
  .fin{background:#1B4F72;color:#fff;} .non{background:#1D6A39;color:#fff;}
  .new{background:#0e4429;color:#3fb950;} .upd{background:#3d2100;color:#ffa657;}
  .unc{background:#161b22;color:#8b949e;}
</style>
""", unsafe_allow_html=True)

st.title("📄 Documents")
st.caption("Browse all harvested PDFs. Filter by category, type, company, and status.")

# ── Fetch ──────────────────────────────────────────────────────────────────────
all_docs    = api("GET", "/documents/") or []
companies   = api("GET", "/companies/") or []
co_map      = {c["id"]: c["company_name"] for c in companies}

fin_docs    = [d for d in all_docs if (d.get("doc_type","")).startswith("FINANCIAL")]
nonfin_docs = [d for d in all_docs if (d.get("doc_type","")).startswith("NON_FINANCIAL")]
unk_docs    = [d for d in all_docs if not (d.get("doc_type","")).startswith("FINANCIAL") and not (d.get("doc_type","")).startswith("NON_FINANCIAL")]

# ── Summary metrics ────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Documents", len(all_docs))
m2.metric("💰 Financial", len(fin_docs))
m3.metric("📋 Non-Financial", len(nonfin_docs))
m4.metric("❓ Unclassified", len(unk_docs))

st.divider()

# ── Filters ────────────────────────────────────────────────────────────────────
f1, f2, f3, f4 = st.columns([2, 2, 2, 2])
search      = f1.text_input("🔍 Search URL / Headline")
co_filter   = f2.selectbox("Company", ["All"] + [c["company_name"] for c in companies])
status_filt = f3.selectbox("Status", ["All", "NEW", "UPDATED", "UNCHANGED", "FAILED"])
meta_filt   = f4.selectbox("Metadata", ["All", "Extracted", "Not Extracted"])

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_fin, tab_nonfin, tab_all = st.tabs([
    f"💰 Financial ({len(fin_docs)})",
    f"📋 Non-Financial ({len(nonfin_docs)})",
    f"📁 All ({len(all_docs)})",
])

DOC_TYPE_LABELS = {
    "ANNUAL_REPORT": "Annual Report", "QUARTERLY_RESULTS": "Quarterly Results",
    "HALF_YEAR_RESULTS": "Half Year", "EARNINGS_RELEASE": "Earnings Release",
    "INVESTOR_PRESENTATION": "Investor Pres.", "FINANCIAL_STATEMENT": "Financial Stmt",
    "IPO_PROSPECTUS": "IPO/Prospectus", "RIGHTS_ISSUE": "Rights Issue",
    "DIVIDEND_NOTICE": "Dividend", "CONCALL_TRANSCRIPT": "Concall Transcript",
    "ESG_REPORT": "ESG Report", "CORPORATE_GOVERNANCE": "Corp. Gov.",
    "PRESS_RELEASE": "Press Release", "REGULATORY_FILING": "Regulatory",
    "LEGAL_DOCUMENT": "Legal", "HR_PEOPLE": "HR/People",
    "PRODUCT_BROCHURE": "Product", "OTHER": "Other",
}


def _filter_docs(docs):
    result = docs
    if search:
        sl = search.lower()
        result = [d for d in result if sl in (d.get("document_url","")).lower() or sl in (d.get("first_page_text","")).lower()]
    if co_filter != "All":
        result = [d for d in result if co_map.get(d.get("company_id")) == co_filter]
    if status_filt != "All":
        result = [d for d in result if d.get("status") == status_filt]
    if meta_filt == "Extracted":
        result = [d for d in result if d.get("metadata_extracted")]
    elif meta_filt == "Not Extracted":
        result = [d for d in result if not d.get("metadata_extracted")]
    return result


def _render_doc_type_filter(docs, is_financial=True):
    types = sorted(set((d.get("doc_type","")).split("|")[-1] for d in docs))
    sel = st.multiselect("Filter by doc type", types, default=types, key=f"type_{'fin' if is_financial else 'non'}")
    return [d for d in docs if (d.get("doc_type","")).split("|")[-1] in sel]


def _render_table(docs):
    if not docs:
        st.info("No documents match the current filters.")
        return

    # sub-type filter
    types = sorted(set((d.get("doc_type","")).split("|")[-1] for d in docs))
    sel_types = st.multiselect("📂 Filter by sub-type", types, default=types, key=f"sub_{id(docs)}")
    docs = [d for d in docs if (d.get("doc_type","")).split("|")[-1] in sel_types]

    rows = []
    for d in docs:
        parts = (d.get("doc_type") or "UNKNOWN|OTHER").split("|")
        rows.append({
            "Company": co_map.get(d.get("company_id"), "?"),
            "Category": parts[0],
            "Type": DOC_TYPE_LABELS.get(parts[-1], parts[-1]),
            "Status": d.get("status", ""),
            "Pages": d.get("page_count", ""),
            "Size (KB)": round((d.get("file_size_bytes") or 0) / 1024, 1),
            "Metadata": "✅" if d.get("metadata_extracted") else "⏳",
            "URL": d.get("document_url", ""),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, height=400,
        column_config={"URL": st.column_config.LinkColumn("URL", display_text="🔗 Open")})

    # Detail panel
    with st.expander("🔎 View Document Detail"):
        sel = st.selectbox("Select document", [d["document_url"] for d in docs])
        doc = next((d for d in docs if d["document_url"] == sel), None)
        if doc:
            d1, d2 = st.columns(2)
            d1.json({k: v for k, v in doc.items() if k not in ["first_page_text"]})
            if doc.get("first_page_text"):
                d2.text_area("First Page Text", doc["first_page_text"][:2000], height=300)


with tab_fin:
    _render_table(_filter_docs(fin_docs))

with tab_nonfin:
    _render_table(_filter_docs(nonfin_docs))

with tab_all:
    _render_table(_filter_docs(all_docs))

# ── Excel download ─────────────────────────────────────────────────────────────
st.divider()
if st.button("📥 Download Excel Report", type="primary"):
    r = api("POST", "/jobs/generate-excel")
    if r and r.get("excel_url"):
        st.success(f"✅ Excel generated. [Download]({r['excel_url']})")
    else:
        st.warning("Excel generation queued — check back in a moment.")
