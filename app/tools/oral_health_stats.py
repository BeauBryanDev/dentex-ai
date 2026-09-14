
import os

import pycountry
import requests
 
# WHO Global Health Observatory (GHO) oral health access tool.
GHO_BASE_URL = "https://ghoapi.azureedge.net/api"
 
# Queries the GHO OData API for country-level oral health system indicators
INDICATORS = {
    "national_policy": "NCD_CCS_oralhealthplan",
    "screening_availability": "ORALHEALTH_AVAILABILITY_SCREENING",
    "urgent_care_availability": "ORALHEALTH_AVAILABILITY_URGENTCARE",
    "restorative_care_availability": "ORALHEALTH_AVAILABILITY_RESTORATIVE",
    "public_coverage_percent": "ORALHEALTH_UHC_GOVSCHEME",
}
 
# return ISO3 country code, or None if not found
def _resolve_iso3(country: str) -> str | None:
    """Resolve a country name to its ISO3 code using pycountry's fuzzy search."""
    try:
        match = pycountry.countries.search_fuzzy(country)
        return match[0].alpha_3
    
    except LookupError:
        return None
 
 
def _fetch_indicator(indicator_code: str, 
                     iso3: str
                     ) -> dict | None:
    """Fetch the most recent data point for one indicator in one country."""
    url = f"{GHO_BASE_URL}/{indicator_code}"
    params = {"$filter": f"SpatialDim eq '{iso3}'"}
 
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    records = response.json().get("value", [])
 
    if not records:
        return None
 
    latest = max(records, 
                 key=lambda r: r.get("TimeDim", 0)
                 )
    
    return {"value": latest.get("Value"), 
            "year": latest.get("TimeDim")}
 
 
# Agent-callable: called only when the user asks about oral health access,
# policy, or coverage in a given country.
def get_oral_health_access(country: str) -> dict:
    """
    Return oral health system access indicators for a given country.
 
    Args:
        country: country name as given by the user (e.g. "Colombia").
 
    Returns:
        dict with one entry per indicator, or an error message if the
        country could not be resolved.
    """
    iso3 = _resolve_iso3(country)
    
    if iso3 is None:
        return {"error": f"Could not resolve country: {country}"}
 
    results = {}
    
    for label, code in INDICATORS.items():
        
        data = _fetch_indicator(code, iso3)
        
        results[label] = data if data is not None else {"value": "no data available", "year": None}
 
    results["country"] = country
    results["iso3"] = iso3
    
    return results
 
# these are the best fields i coud get from the API, but they are not
# available in the OData API, so we have to fetch them from the HTML
_LABELS = {
    "national_policy": "National oral health plan",
    "screening_availability": "Screening available in the public system",
    "urgent_care_availability": "Urgent dental care available in the public system",
    "restorative_care_availability": "Restorative care available in the public system",
    "public_coverage_percent": "Oral care covered by a government scheme (%)",
}


def format_oral_health_access(results: dict) -> tuple[str, int]:
    """
    Render `get_oral_health_access` output as the plain text Claude reads back.

    Returns (text, reported_count) where reported_count is the number of indicators
    that actually carried a value — 0 means WHO has nothing on file for this country,
    which the agent must say rather than fill in from memory.
    """
    if "error" in results:
        return results["error"], 0

    lines = [f"WHO Global Health Observatory — oral health system access, "
             f"{results['country']} ({results['iso3']}):"]
    reported = 0

    for key, label in _LABELS.items():
        
        entry = results.get(key) or {}
        value = entry.get("value")
        year = entry.get("year")

        if value in (None, "no data available"):
            lines.append(f"- {label}: no data reported")
            continue

        reported += 1
        lines.append(f"- {label}: {value}" + (f" (reported {year})" if year else ""))

    lines.append(
        "Source: WHO GHO, country-reported. Describes the national public system, "
        "not any individual's insurance."
    )
    return "\n".join(lines), reported
