"""
FinWatch — Analytics Page (NEW)
Charts, breakdowns, and trends across all companies and documents.
"""
import streamlit as st
import pandas as pd
from api_client import api

st.set_page_config(page_title="FinWatch · Analytics", page_icon="📈", layout="wide")

st.title("📈 Analytics")
st.caption("Visual breakdowns of documents, changes, and document intelligence across all companies.")

# ── Fetch ──────────────────────────────────────────────────────────────────────
docs       = api("GET", "/documents/") or []
companies  = api("GET", "/companies/") or []
changes    = api("GET", "/documents/changes/document") or []
pg_changes = api("GET", "/webwatch/changes") or []
co_map     = {c["id"]: c["company_name"] for c in companies}

if not docs and not companies:
    st.info("No data yet — add companies and run the pipeline first.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Document breakdown
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("📊 Document Breakdown")
a1, a2, a3 = st.columns(3)

with a1:
    # Financial vs Non-Financial pie-style bar
    fin_count    = sum(1 for d in docs if (d.get("doc_type","")).startswith("FINANCIAL"))
    nonfin_count = sum(1 for d in docs if (d.get("doc_type","")).startswith("NON_FINANCIAL"))
    unk_count    = len(docs) - fin_count - nonfin_count
    cat_df = pd.DataFrame({
        "Category": ["💰 Financial", "📋 Non-Financial", "❓ Unknown"],
        "Count": [fin_count, nonfin_count, unk_count]
    }).set_index("Category")
    st.bar_chart(cat_df, color="#58a6ff")
    st.caption("Financial vs Non-Financial split")

with a2:
    # Doc type breakdown
    type_counts = {}
    for d in docs:
        t = (d.get("doc_type") or "UNKNOWN|OTHER").split("|")[-1]
        type_counts[t] = type_counts.get(t, 0) + 1
    type_df = pd.DataFrame.from_dict(type_counts, orient="index", columns=["Count"]).sort_values("Count", ascending=False).head(10)
    st.bar_chart(type_df, color="#3fb950")
    st.caption("Top 10 document types")

with a3:
    # Per-company doc count
    co_counts = {}
    for d in docs:
        cn = co_map.get(d.get("company_id"), "Unknown")
        co_counts[cn] = co_counts.get(cn, 0) + 1
    co_df = pd.DataFrame.from_dict(co_counts, orient="index", columns=["Documents"]).sort_values("Documents", ascending=False)
    st.bar_chart(co_df, color="#ffa657")
    st.caption("Documents per company")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Change analytics
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("🔔 Change Analytics")

if changes:
    b1, b2 = st.columns(2)
    with b1:
        chg_types = {}
        for c in changes:
            ct = c.get("change_type","UNKNOWN")
            chg_types[ct] = chg_types.get(ct, 0) + 1
        chg_df = pd.DataFrame.from_dict(chg_types, orient="index", columns=["Count"])
        st.bar_chart(chg_df, color="#f85149")
        st.caption("Document changes by type (all time)")

    with b2:
        chg_co = {}
        for c in changes:
            cn = c.get("company_name","Unknown")
            chg_co[cn] = chg_co.get(cn, 0) + 1
        chg_co_df = pd.DataFrame.from_dict(chg_co, orient="index", columns=["Changes"]).sort_values("Changes", ascending=False)
        st.bar_chart(chg_co_df, color="#d29922")
        st.caption("Changes per company (all time)")
else:
    st.info("No change history yet.")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Metadata completeness
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("🔬 Metadata Extraction Completeness")

if docs:
    c1, c2 = st.columns(2)
    with c1:
        extracted = sum(1 for d in docs if d.get("metadata_extracted"))
        pending   = len(docs) - extracted
        ext_df = pd.DataFrame({
            "Status": ["✅ Extracted", "⏳ Pending"],
            "Count": [extracted, pending]
        }).set_index("Status")
        st.bar_chart(ext_df, color="#58a6ff")
        st.caption(f"Metadata extracted for {extracted}/{len(docs)} documents ({round(extracted/len(docs)*100) if docs else 0}%)")

    with c2:
        # Per-company extraction rate
        co_ext = {}
        co_total = {}
        for d in docs:
            cn = co_map.get(d.get("company_id"), "Unknown")
            co_total[cn] = co_total.get(cn, 0) + 1
            if d.get("metadata_extracted"):
                co_ext[cn] = co_ext.get(cn, 0) + 1
        rate_rows = []
        for cn in co_total:
            rate = round((co_ext.get(cn, 0) / co_total[cn]) * 100)
            rate_rows.append({"Company": cn, "Extraction Rate (%)": rate})
        rate_df = pd.DataFrame(rate_rows).set_index("Company")
        st.bar_chart(rate_df, color="#3fb950")
        st.caption("Extraction rate per company")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 4: WebWatch coverage
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("🌐 WebWatch — Page Change Types")
if pg_changes:
    pc_types = {}
    for pc in pg_changes:
        ct = pc.get("change_type","UNKNOWN")
        pc_types[ct] = pc_types.get(ct, 0) + 1
    pc_df = pd.DataFrame.from_dict(pc_types, orient="index", columns=["Count"])
    st.bar_chart(pc_df, color="#79c0ff")
else:
    st.info("No WebWatch page changes recorded yet.")
