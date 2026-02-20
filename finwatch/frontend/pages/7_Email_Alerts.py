"""Page 7 — Email Alerts: configure SMTP + recipients, send test."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import get, post

st.set_page_config(page_title="Email Alerts — FinWatch", page_icon="📧", layout="wide")
st.title("📧 Email Alert Configuration")

st.info("""
**Gmail via Google OAuth2 is the primary email method.**
To activate it, run `python finwatch_auth.py` once on your machine to generate `google_token.json`.
The SMTP settings below are used as a fallback only.
""")

config = get("/alerts/") or {}

with st.form("email_config"):
    st.subheader("SMTP Fallback Settings")
    smtp_host = st.text_input("SMTP Host", value=config.get("smtp_host", "smtp.gmail.com"))
    smtp_port = st.number_input("SMTP Port", value=int(config.get("smtp_port", 587)), min_value=25, max_value=9999)
    smtp_user = st.text_input("SMTP Username / Gmail Address", value=config.get("smtp_user", ""))
    smtp_pass = st.text_input("SMTP Password / App Password", type="password")
    email_from = st.text_input("From Address", value=config.get("email_from", ""))

    st.subheader("Recipients")
    existing = "\n".join(config.get("recipients", []))
    recipients_raw = st.text_area("One email per line", value=existing, height=100)

    st.subheader("Digest Schedule")
    send_on_change = st.toggle("Send email when changes are detected", value=config.get("send_on_change", True))
    digest_hour = st.slider("Daily digest hour (UTC)", 0, 23, value=int(config.get("daily_digest_hour", 0)))
    st.caption(f"IST: {(digest_hour + 5) % 24}:{30:02d}")

    if st.form_submit_button("💾 Save Configuration", type="primary"):
        recipients = [r.strip() for r in recipients_raw.splitlines() if r.strip()]
        payload = {
            "smtp_host": smtp_host, "smtp_port": smtp_port,
            "smtp_user": smtp_user, "smtp_password": smtp_pass,
            "email_from": email_from, "recipients": recipients,
            "send_on_change": send_on_change, "daily_digest_hour": digest_hour,
        }
        res = post("/alerts/", payload)
        if res.get("saved"):
            st.success("✅ Email configuration saved!")
        else:
            st.error("Failed to save")

st.divider()
if st.button("📨 Send Test Email Now"):
    res = post("/alerts/test")
    if res.get("sent"):
        st.success("✅ Test email sent successfully!")
    else:
        st.error(f"Failed: {res.get('error', 'Unknown error')}")
