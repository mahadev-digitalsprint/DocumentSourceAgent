"""
FinWatch — Shared API client for Streamlit frontend.
Connects to FastAPI backend on port 8080.
"""
import requests
import streamlit as st
from typing import Any, Optional

API_BASE = "http://localhost:8080/api"


def api(method: str, path: str, json: Optional[dict] = None, params: Optional[dict] = None, timeout: int = 30) -> Any:
    """Universal API call — returns parsed JSON or None on error."""
    url = f"{API_BASE}{path}"
    try:
        method = method.upper()
        # Increase timeout for POST/PATCH if not specified, as they might be sync jobs
        if timeout == 30 and method in ["POST", "PATCH"]:
            timeout = 300 

        if method == "GET":
            r = requests.get(url, params=params, timeout=timeout)
        elif method == "POST":
            r = requests.post(url, json=json, timeout=timeout)
        elif method == "PATCH":
            r = requests.patch(url, json=json, timeout=timeout)
        elif method == "DELETE":
            r = requests.delete(url, timeout=10)
            return r.status_code < 300
        else:
            raise ValueError(f"Unsupported method: {method}")

        if not r.ok:
            st.error(f"API {method} {path} → {r.status_code}: {r.text[:200]}")
            return None
        if r.status_code == 204 or not r.content:
            return True
        return r.json()

    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to FinWatch backend (port 8080). Is the server running?")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# ── Convenience wrappers (legacy) ─────────────────────────────────────────────
def get(path: str, params: Optional[dict] = None) -> Any:
    return api("GET", path, params=params)

def post(path: str, json: Optional[dict] = None) -> Any:
    return api("POST", path, json=json)

def delete(path: str) -> Any:
    return api("DELETE", path)
