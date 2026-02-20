"""
FinWatch shared API client for Streamlit frontend.
Adds retries and short-lived caching to reduce UI latency and API load.
"""
import os
import time
from typing import Any, Optional

import requests
import streamlit as st

API_BASE = os.getenv("FINWATCH_API_BASE", "http://localhost:8080/api")
REQUEST_RETRIES = 2
DEFAULT_CACHE_TTL_SEC = 20


def _cache_get(key: str, ttl: int = DEFAULT_CACHE_TTL_SEC):
    store = st.session_state.setdefault("_api_cache", {})
    item = store.get(key)
    if not item:
        return None
    if time.time() - item["ts"] > ttl:
        store.pop(key, None)
        return None
    return item["value"]


def _cache_set(key: str, value: Any):
    store = st.session_state.setdefault("_api_cache", {})
    store[key] = {"value": value, "ts": time.time()}


def api(method: str, path: str, json: Optional[dict] = None, params: Optional[dict] = None, timeout: int = 30) -> Any:
    """Universal API call: returns JSON, True, or None on error."""
    method = method.upper()
    url = f"{API_BASE}{path}"

    try:
        if timeout == 30 and method in ["POST", "PATCH"]:
            timeout = 300

        cache_key = f"{method}|{url}|{params}"
        if method == "GET":
            cached = _cache_get(cache_key)
            if cached is not None:
                return cached

        response = None
        for attempt in range(REQUEST_RETRIES + 1):
            try:
                if method == "GET":
                    response = requests.get(url, params=params, timeout=timeout)
                elif method == "POST":
                    response = requests.post(url, json=json, timeout=timeout)
                elif method == "PATCH":
                    response = requests.patch(url, json=json, timeout=timeout)
                elif method == "DELETE":
                    response = requests.delete(url, timeout=10)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                break
            except requests.exceptions.RequestException:
                if attempt >= REQUEST_RETRIES:
                    raise
                time.sleep(0.25 * (attempt + 1))

        if method == "DELETE":
            ok = bool(response and response.status_code < 300)
            if ok:
                st.session_state.pop("_api_cache", None)
            return ok

        if not response or not response.ok:
            status = response.status_code if response is not None else "N/A"
            msg = (response.text[:200] if response is not None else "No response")
            st.error(f"API {method} {path} -> {status}: {msg}")
            return None

        if response.status_code == 204 or not response.content:
            return True

        data = response.json()
        if method == "GET":
            _cache_set(cache_key, data)
        else:
            st.session_state.pop("_api_cache", None)
        return data

    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to FinWatch backend on port 8080.")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def get(path: str, params: Optional[dict] = None) -> Any:
    return api("GET", path, params=params)


def post(path: str, json: Optional[dict] = None) -> Any:
    return api("POST", path, json=json)


def delete(path: str) -> Any:
    return api("DELETE", path)
