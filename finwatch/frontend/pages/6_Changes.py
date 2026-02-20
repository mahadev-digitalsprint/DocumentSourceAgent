"""
FinWatch — Changes Page
Document & page-level change log with company/time filters and diff viewer.
"""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import api

st.set_page_config(page_title="FinWatch · Changes", page_icon="🔔", layout="wide")

st.markdown("""
<style>
  .chg-new  {border-left:4px solid #3fb950;background:#0e4429;padding:8px 12px;border-radius:0 8px 8px 0;margin:4px 0;}
  .chg-upd  {border-left:4px solid #ffa657;background:#3d2100;padding:8px 12px;border-radius:0 8px 8px 0;margin:4px 0;}
  .chg-del  {border-left:4px solid #f85149;background:#3d0000;padding:8px 12px;border-radius:0 8px 8px 0;margin:4px 0;}
  .chg-add  {border-left:4px solid #58a6ff;background:#0c1e3c;padding:8px 12px;border-radius:0 8px 8px 0;margin:4px 0;}
  .chg-oth  {border-left:4px solid #8b949e;background:#0d1117;padding:8px 12px;border-radius:0 8px 8px 0;margin:4px 0;}
</style>
""", unsafe_allow_html=True)

st.title("🔔 Change Log")
st.caption("Track new, updated, and removed documents — plus WebWatch page-level changes.")

# ── Filters ────────────────────────────────────────────────────────────────────
companies = api("GET", "/companies/") or []
co_map = {"All": None}
if isinstance(companies, list):
    co_map.update({c["company_name"]: c["id"] for c in companies})

f1, f2, f3 = st.columns(3)
sel_co  = f1.selectbox("Company", list(co_map.keys()))
hours   = f2.selectbox("Time Window", [6, 12, 24, 48, 72, 168], index=2,
                        format_func=lambda h: f"Last {h}h" if h < 48 else f"Last {h//24}d")
cat_filt = f3.selectbox("Category", ["All", "💰 Financial", "📋 Non-Financial"])
cid = co_map[sel_co]

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_docs, tab_pages = st.tabs(["📄 Document Changes", "🌐 Page Changes (WebWatch)"])

# ── Document Changes ───────────────────────────────────────────────────────────
with tab_docs:
    params = {"hours": hours}
    if cid:
        params["company_id"] = cid
    changes = api("GET", "/documents/changes/", params=params) or []

    if not isinstance(changes, list):
        changes = []

    # Category filter
    if cat_filt == "💰 Financial":
        changes = [c for c in changes if (c.get("doc_type","")).startswith("FINANCIAL")]
    elif cat_filt == "📋 Non-Financial":
        changes = [c for c in changes if (c.get("doc_type","")).startswith("NON_FINANCIAL")]

    new_ct = sum(1 for c in changes if c.get("change_type") == "NEW")
    upd_ct = sum(1 for c in changes if c.get("change_type") == "UPDATED")
    del_ct = sum(1 for c in changes if c.get("change_type") == "REMOVED")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Changes", len(changes))
    m2.metric("🟢 New", new_ct)
    m3.metric("🟡 Updated", upd_ct)
    m4.metric("🔴 Removed", del_ct)

    if changes:
        # Table view
        rows = []
        for c in changes:
            parts = (c.get("doc_type") or "UNKNOWN|OTHER").split("|")
            rows.append({
                "Detected At":  c.get("detected_at","")[:19],
                "Company":      c.get("company_name",""),
                "Change Type":  c.get("change_type",""),
                "Category":     parts[0] if len(parts) > 1 else "UNKNOWN",
                "Doc Type":     parts[-1],
                "URL":          c.get("document_url",""),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True, height=300,
            column_config={"URL": st.column_config.LinkColumn("URL", display_text="🔗 Open")})

        # Card feed
        st.subheader("📋 Change Feed")
        for c in changes[:50]:
            ct = c.get("change_type","")
            css = "chg-new" if ct == "NEW" else "chg-upd" if ct == "UPDATED" else "chg-del" if ct == "REMOVED" else "chg-oth"
            url = c.get("document_url","")
            parts = (c.get("doc_type") or "UNKNOWN|OTHER").split("|")
            st.markdown(f"""
            <div class="{css}">
              <strong>{ct}</strong> &nbsp;·&nbsp;
              <span style="color:#ccc">{c.get('company_name','')} — {parts[-1]}</span><br/>
              <a href="{url}" target="_blank" style="color:#79c0ff;font-size:0.78rem">{url[:100]}</a><br/>
              <small style="color:#8b949e">{c.get('detected_at','')[:19]}</small>
            </div>""", unsafe_allow_html=True)
    else:
        st.info(f"No document changes in the last {hours} hours.")

# ── Page Changes ───────────────────────────────────────────────────────────────
with tab_pages:
    params2 = {"hours": hours}
    if cid:
        params2["company_id"] = cid
    page_changes = api("GET", "/webwatch/changes", params=params2) or []
    if not isinstance(page_changes, list):
        page_changes = []

    if page_changes:
        pa_ct = sum(1 for p in page_changes if p.get("change_type") == "PAGE_ADDED")
        pd_ct = sum(1 for p in page_changes if p.get("change_type") == "PAGE_DELETED")
        cc_ct = sum(1 for p in page_changes if p.get("change_type") == "CONTENT_CHANGED")
        np_ct = sum(1 for p in page_changes if p.get("change_type") == "NEW_DOC_LINKED")

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("🆕 Pages Added",   pa_ct)
        p2.metric("🗑 Pages Deleted", pd_ct)
        p3.metric("✏️ Content Changed", cc_ct)
        p4.metric("📎 New PDFs Linked", np_ct)

        for pc in page_changes[:100]:
            ct = pc.get("change_type","")
            css = ("chg-add" if "ADDED" in ct else "chg-del" if "DELETED" in ct
                   else "chg-upd" if "CHANGED" in ct else "chg-new" if "DOC" in ct else "chg-oth")
            new_pdfs = pc.get("new_pdf_urls") or []
            pdf_count = len(new_pdfs) if isinstance(new_pdfs, list) else 0
            st.markdown(f"""
            <div class="{css}">
              <strong>{ct.replace('_',' ')}</strong>
              {f'&nbsp;·&nbsp;<span style="color:#3fb950">+{pdf_count} PDFs</span>' if pdf_count else ''}
              <br/>
              <code style="font-size:0.78rem">{(pc.get("page_url") or "")[:100]}</code><br/>
              <small style="color:#8b949e">{pc.get("detected_at","")[:19]}</small>
              {f'<br/><small style="color:#8b949e">{(pc.get("diff_summary") or "")[:150]}</small>' if pc.get("diff_summary") else ""}
            </div>""", unsafe_allow_html=True)
    else:
        st.info(f"No page changes in the last {hours} hours.")

# ── Trigger WebWatch ───────────────────────────────────────────────────────────
st.divider()
if st.button("🔍 Run WebWatch Now", help="Trigger an immediate page scan for all companies"):
    r = api("POST", "/jobs/webwatch-now")
    if r:
        st.success(f"✅ WebWatch triggered! Job: `{r.get('job_id','N/A')}`")
    else:
        st.error("Failed — is Celery running?")
