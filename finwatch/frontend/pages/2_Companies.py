"""Page 2 — Companies: add, bulk import, delete, toggle active."""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import get, post, delete

st.set_page_config(page_title="Companies — FinWatch", page_icon="🏢", layout="wide")
st.title("🏢 Companies")

tab1, tab2, tab3 = st.tabs(["📋 All Companies", "➕ Add Company", "📤 Bulk Import"])

# ── Tab 1: List ───────────────────────────────────────────────────────────────
with tab1:
    companies = get("/companies/") or []
    if isinstance(companies, list) and companies:
        for c in companies:
            col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
            col1.write(f"**{c['company_name']}**")
            col2.write(c["website_url"])
            col3.write("✅ Active" if c.get("active") else "⏸ Paused")
            with col4:
                sub1, sub2 = st.columns(2)
                if sub1.button("⏯", key=f"tog_{c['id']}", help="Toggle active"):
                    post(f"/companies/{c['id']}/toggle"); st.rerun()
                if sub2.button("🗑️", key=f"del_{c['id']}", help="Delete"):
                    delete(f"/companies/{c['id']}"); st.rerun()
    else:
        st.info("No companies added yet.")

# ── Tab 2: Add single ─────────────────────────────────────────────────────────
with tab2:
    with st.form("add_company"):
        name = st.text_input("Company Name *", placeholder="Apple Inc.")
        url  = st.text_input("Website URL *",  placeholder="https://investor.apple.com")
        depth = st.slider("Crawl Depth", 1, 5, 3)
        if st.form_submit_button("Add Company", type="primary"):
            if name and url:
                res = post("/companies/", {"company_name": name, "website_url": url, "crawl_depth": depth})
                if "id" in res:
                    st.success(f"✅ Added: {name}")
                    st.rerun()
                else:
                    st.error(res.get("error", "Failed"))
            else:
                st.warning("Name and URL are required")

# ── Tab 3: Bulk upload CSV ────────────────────────────────────────────────────
with tab3:
    st.markdown("Upload a CSV with columns: **company_name**, **website_url** (optional: crawl_depth)")
    f = st.file_uploader("Upload CSV", type=["csv"])
    if f:
        df = pd.read_csv(f)
        st.dataframe(df.head(20), use_container_width=True)
        if st.button("Import All", type="primary"):
            payload = [
                {"company_name": r["company_name"], "website_url": r["website_url"],
                 "crawl_depth": int(r.get("crawl_depth", 3))}
                for _, r in df.iterrows()
                if "company_name" in r and "website_url" in r
            ]
            res = post("/companies/bulk", payload)
            if isinstance(res, list):
                st.success(f"✅ Imported {len(res)} companies")
                st.rerun()
            else:
                st.error(str(res))
