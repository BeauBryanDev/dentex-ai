"""Geocoding helpers. HTTP is stubbed — no Google calls."""
from __future__ import annotations

import json

import pytest

from app.utils.geolocation_utils import GeocodingError, geocode_city


def _geo_response(*, status: str = "OK", results=None, error_message: str | None = None):
    payload = {"status": status, "results": results or []}
    if error_message:
        payload["error_message"] = error_message
    return json.dumps(payload).encode("utf-8")


def test_geocode_city_returns_coordinates(monkeypatch):
    body = _geo_response(
        results=[
            {
                "formatted_address": "Lyon, France",
                "geometry": {"location": {"lat": 45.764, "lng": 4.8357}},
            }
        ]
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return body

    monkeypatch.setattr("app.utils.geolocation_utils.urlopen", lambda *a, **k: FakeResponse())

    location = geocode_city("Lyon", api_key="test-key", region_hint="France")
    assert location.formatted_address == "Lyon, France"
    assert location.latitude == pytest.approx(45.764)
    assert location.longitude == pytest.approx(4.8357)


def test_geocode_city_requires_a_non_empty_name():
    with pytest.raises(GeocodingError, match="required"):
        geocode_city("   ", api_key="test-key")


def test_geocode_city_reports_zero_results(monkeypatch):
    body = _geo_response(status="ZERO_RESULTS")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return body

    monkeypatch.setattr("app.utils.geolocation_utils.urlopen", lambda *a, **k: FakeResponse())

    with pytest.raises(GeocodingError, match="No location matched"):
        geocode_city("Nowhereville", api_key="test-key")
