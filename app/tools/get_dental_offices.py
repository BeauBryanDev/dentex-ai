from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.utils.geolocation_utils import GeocodedLocation, GeocodingError, geocode_city

logger = logging.getLogger(__name__)

PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DEFAULT_TIMEOUT = 15.0


@dataclass(frozen=True, slots=True)
class DentalOffice:
    """One dental practice returned by Places Nearby Search."""

    name: str
    address: str
    rating: float | None
    user_ratings_total: int | None
    open_now: bool | None
    maps_url: str | None


@dataclass(frozen=True, slots=True)
class DentalOfficeSearchResult:
    """Rendered tool output plus metadata for the UI."""

    text: str
    office_count: int
    resolved_location: str
    offices: tuple[DentalOffice, ...] = ()


class DentalOfficeSearchError(Exception):
    """Raised when the office search cannot complete."""


def _fetch_json(url: str, 
                *, 
                timeout: float = DEFAULT_TIMEOUT
                ) -> dict[str, Any]:
    
    request = Request(url,
                      headers={"Accept": "application/json"}
                      )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            
    except HTTPError as exc:
        raise DentalOfficeSearchError(
            f"Places search failed with HTTP {exc.code}"
        ) from exc
        
    except URLError as exc:
        raise DentalOfficeSearchError(f"Places search failed: {exc.reason}") from exc

    import json

    try:
        data = json.loads(payload)
        
    except json.JSONDecodeError as exc:
        raise DentalOfficeSearchError("Places API returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise DentalOfficeSearchError("Places API returned an unexpected payload")
    
    return data


def _parse_office(raw: dict[str, Any]) -> DentalOffice:
    # TODO: add more fields
    rating = raw.get("rating")
    total_ratings = raw.get("user_ratings_total")
    opening = raw.get("opening_hours") or {}
    place_id = raw.get("place_id")
    maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else None

    return DentalOffice(
        
        name=str(raw.get("name") or "Unknown practice"),
        address=str(raw.get("vicinity") or raw.get("formatted_address") or "Address unavailable"),
        rating=float(rating) if rating is not None else None,
        user_ratings_total=int(total_ratings) if total_ratings is not None else None,
        open_now=opening.get("open_now") if isinstance(opening, dict) else None,
        maps_url=maps_url,
    )


def _format_office(rank: int, office: DentalOffice) -> str:
    
    rating_bits: list[str] = []
    if office.rating is not None: # star rating
        rating_bits.append(f"rating {office.rating:.1f}/5")
        
    if office.user_ratings_total is not None:
        rating_bits.append(f"{office.user_ratings_total} reviews")
        
    if office.open_now is True:
        rating_bits.append("open now")
        
    elif office.open_now is False:
        rating_bits.append("closed now")

    meta = " | ".join(rating_bits) if rating_bits else "no rating data"
    lines = [f"[{rank}] {office.name}", f"    {office.address}", f"    {meta}"]
    
    if office.maps_url:
        
        lines.append(f"    map: {office.maps_url}")
        
    return "\n".join(lines)


def search_dental_offices_near_city(
    city: str,
    *,
    api_key: str,
    region_hint: str | None = None,
    radius_m: int = 10_000,
    max_results: int = 5,
    timeout: float = DEFAULT_TIMEOUT,
) -> DentalOfficeSearchResult:
    """
    Find dental offices near the centre of a user-provided town or city.

    Location must come from the conversation — never from IP or device GPS.
    """
    try:
        location = geocode_city(
            city,
            api_key=api_key,
            region_hint=region_hint,
            timeout=timeout,
        )
    except GeocodingError as exc:
        raise DentalOfficeSearchError(str(exc)) from exc

    offices = _nearby_dental_offices(
        location,
        api_key=api_key,
        radius_m=radius_m,
        max_results=max_results,
        timeout=timeout,
    )

    if not offices:
        
        text = (
            f"No dental offices were found within {radius_m // 1000} km of "
            f"{location.formatted_address!r}.\n"
            "Suggest the user try a nearby larger town, widen the search area, "
            "or check the spelling of their city."
        )
        return DentalOfficeSearchResult(
            text=text,
            office_count=0,
            resolved_location=location.formatted_address,
            offices=(),
        )

    header = (
        f"{len(offices)} dental office(s) near {location.formatted_address!r} "
        f"(searched within {radius_m // 1000} km of the city centre):\n"
        "These are third-party listings — remind the user to verify hours, "
        "insurance acceptance, and availability before booking.\n"
    )
    body = "\n\n".join(_format_office(i, office) for i, office in enumerate(offices, 1))
    
    return DentalOfficeSearchResult(
        text=header + body,
        office_count=len(offices),
        resolved_location=location.formatted_address,
        offices=tuple(offices),
    )


def _nearby_dental_offices(
    location: GeocodedLocation,
    *,
    api_key: str,
    radius_m: int,
    max_results: int,
    timeout: float,
) -> list[DentalOffice]:
    params = urlencode(
        {
            "location": f"{location.latitude},{location.longitude}",
            "radius": radius_m,
            "type": "dentist",
            "key": api_key,
        }
    )
    data = _fetch_json(f"{PLACES_NEARBY_URL}?{params}", timeout=timeout)

    status = data.get("status")
    
    if status not in {"OK", "ZERO_RESULTS"}:
        
        message = data.get("error_message") or status or "unknown error"
        raise DentalOfficeSearchError(f"Places search failed: {message}")

    results = data.get("results") or []
    
    offices = [_parse_office(item) for item in results[:max_results]]
    
    logger.info(
        
        "Found %d dental office(s) near %s",
        len(offices),
        location.formatted_address,
    )
    
    return offices
