"""Page 1 — Dashboard (redirects to Home which is now the dashboard)."""
import streamlit as st
st.set_page_config(page_title="FinWatch · Dashboard", page_icon="📊", layout="wide")
st.switch_page("Home.py")
