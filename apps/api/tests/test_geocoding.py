import json
from io import BytesIO
from unittest.mock import Mock
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

import pytest

from app import geocoding

RESULT = {"city": "Kraków", "number": "53", "accuracy": "1", "x": "572085.53", "y": "244516.83"}


def response(results, **extra):
    return BytesIO(json.dumps({"type": "address", "results": results, **extra}).encode())


def test_address_lookup_uses_strict_number(monkeypatch):
    fetch = Mock(return_value=response({"1": RESULT}))
    monkeypatch.setattr(geocoding, "urlopen", fetch)
    assert geocoding.address_point("Kraków", "Centralna", "53") == geocoding.AddressPoint(572085.53, 244516.83)
    fetch.assert_called_once()
    query = parse_qs(urlparse(fetch.call_args.args[0].full_url).query)
    assert query == {
        "request": ["GetAddress"],
        "address": ["Kraków, Centralna 53"],
        "accuracy": ["0.8"],
        "exact_number": ["1"],
    }
    assert fetch.call_args.kwargs["timeout"] == 5


@pytest.mark.parametrize("results", [None, {}, {"1": RESULT, "2": RESULT}])
def test_missing_or_ambiguous_addresses_are_not_chosen(monkeypatch, results):
    monkeypatch.setattr(geocoding, "urlopen", Mock(return_value=response(results, **{"returned objects": 0})))
    assert geocoding.address_point("Kraków", "Centralna", "53") is None


@pytest.mark.parametrize("change", [{"city": "Inne miasto"}, {"number": "54"}, {"accuracy": "0.79"}])
def test_inexact_addresses_are_not_chosen(monkeypatch, change):
    monkeypatch.setattr(geocoding, "urlopen", Mock(return_value=response({"1": RESULT | change})))
    assert geocoding.address_point("Kraków", "Centralna", "53") is None


@pytest.mark.parametrize("data", [b"<html>error</html>", b"{}", b"[]", b"x" * 65_537])
def test_invalid_responses_fail_instead_of_reporting_no_match(monkeypatch, data):
    monkeypatch.setattr(geocoding, "urlopen", Mock(return_value=BytesIO(data)))
    with pytest.raises(geocoding.GeocodingUnavailableError):
        geocoding.address_point("Kraków", "Centralna", "53")


@pytest.mark.parametrize("change", [{"x": "nan"}, {"y": "inf"}, {"x": "-1"}, {"accuracy": None}, {"accuracy": "nan"}])
def test_invalid_coordinates_and_scores_fail(monkeypatch, change):
    monkeypatch.setattr(geocoding, "urlopen", Mock(return_value=response({"1": RESULT | change})))
    with pytest.raises(geocoding.GeocodingUnavailableError):
        geocoding.address_point("Kraków", "Centralna", "53")


def test_network_errors_are_not_cached(monkeypatch):
    fetch = Mock(side_effect=[URLError("unavailable"), response({"1": RESULT})])
    monkeypatch.setattr(geocoding, "urlopen", fetch)
    with pytest.raises(geocoding.GeocodingUnavailableError):
        geocoding.address_point("Kraków", "Centralna", "53")
    assert geocoding.address_point("Kraków", "Centralna", "53") is not None
    assert fetch.call_count == 2
