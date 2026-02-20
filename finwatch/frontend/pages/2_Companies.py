"""
FinWatch — Companies Page
Multi-company management: add single, add multiple inline rows, bulk CSV import.
"""
import io
import time
import pandas as pd
import streamlit as st
from api_client import api

st.set_page_config(page_title="FinWatch · Companies", page_icon="🏢", layout="wide")

st.markdown("""
<style>
  .fin-card  {background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:1.2rem;margin-bottom:0.8rem;}
  .fin-badge {display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;}
  .badge-fin {background:#1B4F72;color:#fff;}
  .badge-non {background:#1D6A39;color:#fff;}
  .badge-active {background:#0e4429;color:#3fb950;}
  .badge-inactive{background:#3d1f00;color:#f85149;}
  .stButton>button{width:100%;}
</style>
""", unsafe_allow_html=True)

st.title("🏢 Companies")
st.caption("Monitor financial & non-financial documents across all tracked companies.")

# ── Fetch companies ────────────────────────────────────────────────────────────
companies = api("GET", "/companies/") or []
total = len(companies)
active = sum(1 for c in companies if c.get("active"))

col1, col2, col3 = st.columns(3)
col1.metric("Total Companies", total)
col2.metric("Active", active)
col3.metric("Inactive", total - active)

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# ADD COMPANIES SECTION
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("➕ Add Companies", expanded=(total == 0)):
    tab1, tab2, tab3 = st.tabs(["Single Company", "Multiple Companies (Form)", "Bulk CSV Upload"])

    # ── Tab 1: Single ─────────────────────────────────────────────────────────
    with tab1:
        with st.form("add_single"):
            c1, c2, c3 = st.columns([3, 3, 1])
            name   = c1.text_input("Company Name *", placeholder="Reliance Industries Ltd")
            url    = c2.text_input("Investor Relations URL *", placeholder="https://www.ril.com/ir")
            depth  = c3.number_input("Crawl Depth", min_value=1, max_value=5, value=3)
            if st.form_submit_button("➕ Add Company", type="primary"):
                if name and url:
                    r = api("POST", "/companies/", json={"company_name": name, "website_url": url, "crawl_depth": depth})
                    if r and r.get("id"):
                        st.success(f"✅ Added **{r['company_name']}** (slug: `{r['company_slug']}`)")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Failed to add company. Check if URL is valid and company doesn't already exist.")
                else:
                    st.warning("Company name and URL are required.")

    # ── Tab 2: Multiple inline ────────────────────────────────────────────────
    with tab2:
        st.markdown("Fill in as many rows as you need. Leave empty rows blank — they'll be skipped.")
        NUM_ROWS = st.number_input("Number of rows to add", min_value=1, max_value=20, value=5)

        with st.form("add_multiple"):
            entries = []
            for i in range(int(NUM_ROWS)):
                c1, c2, c3 = st.columns([3, 4, 1])
                n = c1.text_input(f"Name #{i+1}", key=f"mn_{i}", label_visibility="collapsed" if i > 0 else "visible")
                u = c2.text_input(f"URL #{i+1}", key=f"mu_{i}", label_visibility="collapsed" if i > 0 else "visible")
                d = c3.number_input(f"Depth #{i+1}", min_value=1, max_value=5, value=3, key=f"md_{i}", label_visibility="collapsed" if i > 0 else "visible")
                entries.append((n, u, d))
                if i == 0:
                    st.caption("Name | IR Website URL | Crawl Depth")

            if st.form_submit_button("➕ Add All Companies", type="primary"):
                added, skipped = 0, 0
                for n, u, d in entries:
                    if n.strip() and u.strip():
                        r = api("POST", "/companies/", json={"company_name": n.strip(), "website_url": u.strip(), "crawl_depth": d})
                        if r and r.get("id"):
                            added += 1
                        else:
                            skipped += 1
                st.success(f"✅ Added {added} companies. {skipped} failed or were duplicates.")
                if added > 0:
                    time.sleep(0.5)
                    st.rerun()

    # ── Tab 3: CSV Upload ─────────────────────────────────────────────────────
    with tab3:
        st.markdown("""
        **CSV format** (comma-separated, header required):
        ```
        company_name,website_url,crawl_depth
        Apple Inc,https://investor.apple.com,3
        TCS,https://www.tcs.com/investor-relations,3
        ```
        """)
        csv_file = st.file_uploader("Upload CSV", type=["csv"])
        if csv_file:
            df = pd.read_csv(csv_file)
            st.dataframe(df, use_container_width=True)
            if st.button("📤 Import All from CSV", type="primary"):
                added, failed = 0, []
                for _, row in df.iterrows():
                    payload = {
                        "company_name": str(row.get("company_name", "")).strip(),
                        "website_url":  str(row.get("website_url", "")).strip(),
                        "crawl_depth":  int(row.get("crawl_depth", 3)),
                    }
                    if payload["company_name"] and payload["website_url"]:
                        r = api("POST", "/companies/", json=payload)
                        if r and r.get("id"):
                            added += 1
                        else:
                            failed.append(payload["company_name"])
                st.success(f"✅ Imported {added} companies.")
                if failed:
                    st.warning(f"⚠️ Failed/duplicate: {', '.join(failed)}")
                if added > 0:
                    time.sleep(0.5)
                    st.rerun()

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# COMPANY LIST
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader(f"📋 All Companies ({total})")

if not companies:
    st.info("No companies tracked yet. Add your first company above.")
else:
    # Filters
    fc1, fc2, fc3 = st.columns([2, 2, 1])
    search = fc1.text_input("🔍 Search", placeholder="Filter by name or URL...")
    status_filter = fc2.selectbox("Status", ["All", "Active", "Inactive"])
    sort_by = fc3.selectbox("Sort", ["Name A-Z", "Name Z-A", "Newest"])

    filtered = companies
    if search:
        filtered = [c for c in filtered if search.lower() in c["company_name"].lower() or search.lower() in c["website_url"].lower()]
    if status_filter == "Active":
        filtered = [c for c in filtered if c["active"]]
    elif status_filter == "Inactive":
        filtered = [c for c in filtered if not c["active"]]
    if sort_by == "Name Z-A":
        filtered = sorted(filtered, key=lambda x: x["company_name"], reverse=True)
    elif sort_by == "Name A-Z":
        filtered = sorted(filtered, key=lambda x: x["company_name"])

    # Table header
    h0, h1, h2, h3, h4, h5 = st.columns([3, 4, 1, 1, 1, 1])
    h0.markdown("**Company**")
    h1.markdown("**Website**")
    h2.markdown("**Depth**")
    h3.markdown("**Status**")
    h4.markdown("**Toggle**")
    h5.markdown("**Delete**")
    st.divider()

    for co in filtered:
        cid = co["id"]
        is_active = co["active"]
        badge = '<span class="fin-badge badge-active">Active</span>' if is_active else '<span class="fin-badge badge-inactive">Paused</span>'

        r0, r1, r2, r3, r4, r5 = st.columns([3, 4, 1, 1, 1, 1])
        r0.markdown(f"**{co['company_name']}**")
        r1.markdown(f"[{co['website_url'][:40]}...]({co['website_url']})" if len(co['website_url']) > 40 else f"[{co['website_url']}]({co['website_url']})")
        r2.write(co.get("crawl_depth", 3))
        r3.markdown(badge, unsafe_allow_html=True)

        if r4.button("⏸ Pause" if is_active else "▶ Resume", key=f"toggle_{cid}"):
            api("PATCH", f"/companies/{cid}/toggle")
            st.rerun()

        if r5.button("🗑️", key=f"del_{cid}", help="Delete this company"):
            api("DELETE", f"/companies/{cid}")
            st.success(f"Deleted {co['company_name']}")
            time.sleep(0.3)
            st.rerun()

# ── Run pipeline for all companies ────────────────────────────────────────────
st.divider()
st.subheader("🚀 Run Pipeline")
rc1, rc2 = st.columns([3, 1])
rc1.markdown("Trigger the full crawl → classify → extract → email pipeline for **all active companies**.")
if rc2.button("▶ Run All Companies", type="primary", use_container_width=True):
    r = api("POST", "/jobs/run-all")
    if r:
        st.success(f"✅ Pipeline started! Job ID: `{r.get('job_id','N/A')}`")
    else:
        st.error("Failed to start pipeline.")
