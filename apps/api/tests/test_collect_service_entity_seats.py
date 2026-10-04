from unittest.mock import Mock

import pytest

from app import municipalities
from app.collect_service_entity_seats import collect_seats

ENTITY = {
    "source_key": "test:seat",
    "locality": "Kraków",
    "street": "Centralna",
    "house_number": "53",
    "postal_code": "31-586",
    "teryt_code": "0201011",
    "source_urls": ["https://example.com/contact"],
}
REVIEW = {
    "source_key": "test:seat",
    "address": ["Kraków", "Centralna", "53"],
    "location": {"longitude": 20.006, "latitude": 50.064},
    "source_urls": ["https://example.com/map"],
    "verified_on": "2026-10-03",
    "note": "Published office map pin.",
}


def test_reviewed_pin_uses_actual_boundary_and_keeps_original_review_date(monkeypatch):
    resolve = Mock(return_value=municipalities.Municipality("1261011", "Kraków", "Kraków"))
    monkeypatch.setattr(municipalities, "resolve_municipality", resolve)
    connection = Mock()
    seat = collect_seats(connection, [ENTITY], [REVIEW], "2026-10-04")[0]
    assert seat["municipality_teryt"] == "1261011"
    assert seat["verified_on"] == "2026-10-03"
    assert seat["location"] == REVIEW["location"]
    assert REVIEW["source_urls"][0] in seat["source_urls"]
    connection.execute.assert_not_called()
    resolve.assert_called_once()


def test_changed_address_invalidates_review_before_network_requests(monkeypatch):
    resolve = Mock()
    monkeypatch.setattr(municipalities, "resolve_municipality", resolve)
    with pytest.raises(ValueError, match="address changed"):
        collect_seats(Mock(), [ENTITY | {"house_number": "54"}], [REVIEW], "2026-10-04")
    resolve.assert_not_called()


def test_unresolved_region_aborts_instead_of_using_related_catalog_teryt(monkeypatch):
    monkeypatch.setattr(municipalities, "resolve_municipality", lambda _: None)
    with pytest.raises(ValueError, match="No municipality"):
        collect_seats(Mock(), [ENTITY], [REVIEW], "2026-10-04")
