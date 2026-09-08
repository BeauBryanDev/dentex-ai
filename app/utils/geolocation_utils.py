
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
DEFAULT_TIMEOUT = 15.0


@dataclass(frozen=True, slots=True)
class GeocodedLocation:
    """A resolved town or city centre."""

    latitude: float
    longitude: float
    formatted_address: str


class GeocodingError(Exception):
    """Raised when a place name cannot be resolved to coordinates."""


def _fetch_json(url: str, *, 
                timeout: float = DEFAULT_TIMEOUT
                ) -> dict[str, Any]:
    
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            
    except HTTPError as exc:
        raise GeocodingError(f"Geocoding request failed with HTTP {exc.code}") from exc
    
    except URLError as exc:
        raise GeocodingError(f"Geocoding request failed: {exc.reason}") from exc

    import json

    try:
        data = json.loads(payload)
        
    except json.JSONDecodeError as exc:
        raise GeocodingError("Geocoding API returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise GeocodingError("Geocoding API returned an unexpected payload")
    
    
    return data


def geocode_city(
    city: str,
    *,
    api_key: str,
    region_hint: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> GeocodedLocation:
    """
    Resolve a user-provided town or city name to coordinates.

    The caller must supply the place name explicitly — this module never infers
    location from IP, GPS, or browser geolocation.
    """
    city = city.strip()
    
    if not city:
        raise GeocodingError("City or town name is required.")
    
    if not api_key:
        raise GeocodingError("Google Maps API key is not configured.")

    query = f"{city}, {region_hint.strip()}" if region_hint and region_hint.strip() else city
    params = urlencode({"address": query, "key": api_key})
    data = _fetch_json(f"{GEOCODE_URL}?{params}", timeout=timeout)

    status = data.get("status")
    
    if status == "ZERO_RESULTS":
        
        hint = f" Try adding a country or region (for example: {city!r}, France)."
        raise GeocodingError(f"No location matched {city!r}.{hint if not region_hint else ''}")
    
    if status != "OK":
        
        message = data.get("error_message") or status or "unknown error"
        raise GeocodingError(f"Geocoding failed: {message}")

    results = data.get("results") or []
    
    if not results:
        raise GeocodingError(f"No location matched {city!r}.")

    top = results[0]
    
    location = (top.get("geometry") or {}).get("location") or {}
    lat = location.get("lat")
    lng = location.get("lng")
    
    if lat is None or lng is None:
        raise GeocodingError(f"Geocoding returned no coordinates for {city!r}.")

    formatted = str(top.get("formatted_address") or query)
    
    logger.info("Geocoded %r -> %s (%.5f, %.5f)", 
                city, 
                formatted, 
                lat, lng)
    
    return GeocodedLocation(
        latitude=float(lat),
        longitude=float(lng),
        formatted_address=formatted,
    )
