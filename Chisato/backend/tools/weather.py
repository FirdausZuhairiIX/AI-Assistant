"""
Example external-tool hook for weather and time lookups.

This module is intentionally simple: it exposes a weather lookup (using a
pluggable API endpoint) and a helper for current local time.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


def get_local_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fetch_weather(city: str, api_url: str | None = None, api_key: str | None = None) -> Dict[str, Any]:
    """
    Fetch weather for a city using a configurable endpoint.
    By default, this returns a stubbed payload to avoid hard API dependencies.
    Supply api_url/api_key to hit a real service (e.g., OpenWeather).
    """
    if api_url:
        try:
            import requests  # type: ignore

            params = {"q": city, "appid": api_key} if api_key else {"q": city}
            resp = requests.get(api_url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "city": city}

    # Stubbed response
    return {
        "city": city,
        "condition": "clear",
        "temp_c": 22,
        "temp_f": 71.6,
        "note": "Using stubbed weather; provide api_url/api_key for live data.",
    }


def format_weather_report(data: Dict[str, Any]) -> str:
    if "error" in data:
        return f"Weather lookup failed: {data['error']}"
    city = data.get("city", "Unknown")
    condition = data.get("condition") or data.get("weather", "N/A")
    temp_c = data.get("temp_c") or data.get("temp")
    return f"{city}: {condition}, {temp_c}°C"
