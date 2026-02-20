"""Streamlit shared API client."""
import requests
from typing import Any, Dict, Optional

API_BASE = "http://localhost:8000/api"


def get(path: str, params: Optional[Dict] = None) -> Any:
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def post(path: str, json: Optional[Dict] = None) -> Any:
    try:
        r = requests.post(f"{API_BASE}{path}", json=json, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def delete(path: str) -> Any:
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=10)
        return r.status_code
    except Exception as e:
        return {"error": str(e)}
