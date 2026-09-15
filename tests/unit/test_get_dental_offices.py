"""Dental office search tool. Google APIs are stubbed — no network."""
from __future__ import annotations

import pytest

from app.tools.get_dental_offices import DentalOffice, DentalOfficeSearchError, search_dental_offices_near_city
from app.utils.geolocation_utils import GeocodedLocation


def test_search_renders_offices_near_the_resolved_city(monkeypatch):
    monkeypatch.setattr(
        "app.tools.get_dental_offices.geocode_city",
        lambda city, **kwargs: GeocodedLocation(
            latitude=45.0,
            longitude=4.0,
            formatted_address="Lyon, France",
        ),
    )
    monkeypatch.setattr(
        "app.tools.get_dental_offices._nearby_dental_offices",
        lambda location, **kwargs: [
            DentalOffice(
                name="Smile Clinic",
                address="12 Rue Example",
                rating=4.5,
                user_ratings_total=12,
                open_now=True,
                maps_url="https://maps.example/dentist-1",
            ),
            DentalOffice(
                name="Centre Dentaire Lyon",
                address="5 Avenue Test",
                rating=4.2,
                user_ratings_total=8,
                open_now=False,
                maps_url="https://maps.example/dentist-2",
            ),
        ],
    )

    result = search_dental_offices_near_city("Lyon", api_key="test-key", region_hint="France")
    assert result.office_count == 2
    assert len(result.offices) == 2
    assert result.offices[0].name == "Smile Clinic"
    assert result.offices[0].maps_url == "https://maps.example/dentist-1"
    assert "Lyon, France" in result.text
    assert "Smile Clinic" in result.text
    assert "Centre Dentaire Lyon" in result.text


def test_search_reports_when_no_offices_are_found(monkeypatch):
    monkeypatch.setattr(
        "app.tools.get_dental_offices.geocode_city",
        lambda city, **kwargs: GeocodedLocation(
            latitude=1.0,
            longitude=1.0,
            formatted_address="Small Town",
        ),
    )
    monkeypatch.setattr(
        "app.tools.get_dental_offices._nearby_dental_offices",
        lambda location, **kwargs: [],
    )

    result = search_dental_offices_near_city("Small Town", api_key="test-key")
    assert result.office_count == 0
    assert "No dental offices were found" in result.text


def test_search_wraps_geocoding_failures(monkeypatch):
    from app.utils.geolocation_utils import GeocodingError

    def fail(*args, **kwargs):
        raise GeocodingError("No location matched 'X'.")

    monkeypatch.setattr("app.tools.get_dental_offices.geocode_city", fail)

    with pytest.raises(DentalOfficeSearchError, match="No location matched"):
        search_dental_offices_near_city("X", api_key="test-key")
