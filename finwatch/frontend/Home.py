"""FinWatch — Home Page"""
import streamlit as st

st.set_page_config(page_title="FinWatch", page_icon="📊", layout="wide")

st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #1e3a5f; }
  [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  .hero { background: linear-gradient(135deg,#1e3a5f,#2563eb); border-radius:12px;
          padding:40px 32px; color:white; margin-bottom:24px; }
  .hero h1 { font-size:2.4em; margin:0 }
  .hero p  { opacity:.85; font-size:1.1em; margin-top:8px }
  .nav-card { background:white; border-radius:10px; padding:20px 16px;
              border:1px solid #e2e8f0; text-align:center; cursor:pointer;
              transition:.2s; box-shadow:0 2px 8px rgba(0,0,0,.06) }
  .nav-card:hover { box-shadow:0 8px 24px rgba(30,58,95,.12); transform:translateY(-2px) }
  .nav-card .icon { font-size:2em }
  .nav-card h3  { margin:8px 0 4px; color:#1e3a5f }
  .nav-card p   { color:#64748b; font-size:.85em; margin:0 }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>📊 FinWatch</h1>
  <p>Financial Document Intelligence & Website Monitoring System</p>
</div>
""", unsafe_allow_html=True)

pages = [
    ("📈", "Dashboard",   "KPI overview & run pipeline"),
    ("🏢", "Companies",   "Add & manage tracked companies"),
    ("🌐", "WebWatch",    "Real-time page change feed"),
    ("📄", "Documents",   "Browse all harvested PDFs"),
    ("🔍", "Metadata",    "LLM-extracted financial metadata"),
    ("🔄", "Changes",     "24-hour document change log"),
    ("📧", "Email Alerts","Configure email digest recipients"),
    ("⚙️", "Settings",   "System configuration"),
]

cols = st.columns(4)
for i, (icon, name, desc) in enumerate(pages):
    with cols[i % 4]:
        st.markdown(f"""
        <div class="nav-card">
          <div class="icon">{icon}</div>
          <h3>{name}</h3>
          <p>{desc}</p>
        </div><br>
        """, unsafe_allow_html=True)
