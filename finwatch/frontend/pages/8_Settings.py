"""Page 8 — Settings: download path, crawl depth, system health."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import get, post

st.set_page_config(page_title="Settings — FinWatch", page_icon="⚙️", layout="wide")
st.title("⚙️ System Settings")

settings = get("/settings/") or {}

col1, col2 = st.columns(2)

with col1:
    st.subheader("📁 Download Path")
    path = st.text_input("Base Download Path",
                         value=settings.get("base_path", "/app/downloads"))
    if st.button("Save Path"):
        post("/settings/", {"key": "base_path", "value": path})
        st.success("✅ Saved")

    st.subheader("🕷️ Default Crawl Depth")
    depth = st.slider("Depth (1 = homepage only)", 1, 5,
                      int(settings.get("crawl_depth", 3)))
    if st.button("Save Depth"):
        post("/settings/", {"key": "crawl_depth", "value": str(depth)})
        st.success("✅ Saved")

with col2:
    st.subheader("🩺 Health Check")
    if st.button("Check API Health", use_container_width=True):
        res = get("/health")
        if res and "status" in res:
            st.success(f"✅ API: {res['status']}")
        else:
            st.error("❌ API unreachable")

    st.subheader("🗄️ Database")
    st.markdown("""
    ```
    Host:     thub-postgres-db.postgres.database.azure.com
    Database: postgres
    User:     gs
    SSL:      required
    ```
    """)

    st.subheader("ℹ️ Version")
    st.write("**FinWatch v2.0**")
    st.write("LangGraph + FastAPI + Streamlit")
    st.write("GMT+5:30 (IST)")
