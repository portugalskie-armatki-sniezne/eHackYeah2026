from unittest.mock import Mock
from uuid import uuid4

import pytest

from app import geocoding, municipalities
from app.geocode_service_entities import geocode_entities


@pytest.fixture
def seat(connection, monkeypatch):
    connection.execute("DELETE FROM service_entities")
    identifier = connection.execute(
        "INSERT INTO service_entities (source_key, name, entity_type, locality, street, house_number, "
        "source_urls, verified_on) VALUES (%s, 'Jednostka', 'road_manager', 'Kraków', 'Centralna', '53', "
        "ARRAY['https://example.com'], '2026-10-03') RETURNING id",
        (str(uuid4()),),
    ).fetchone()["id"]
    lookup = Mock(return_value=geocoding.AddressPoint(572085.53, 244516.83))
    monkeypatch.setattr(geocoding, "address_point", lookup)
    resolve = Mock(return_value=municipalities.Municipality("1261011", "Kraków", "Kraków"))
    monkeypatch.setattr(municipalities, "resolve_municipality", resolve)
    return identifier, lookup, resolve


def test_geocoding_is_persisted_and_unchanged_seats_are_not_requested_again(connection, seat):
    identifier, lookup, resolve = seat
    assert geocode_entities(connection).saved == 1
    row = connection.execute(
        "SELECT seat_teryt, seat_geocoded_at, seat_address, ST_X(seat_location::geometry) AS longitude, "
        "ST_Y(seat_location::geometry) AS latitude FROM service_entities WHERE id = %s",
        (identifier,),
    ).fetchone()
    assert row["seat_teryt"] == "1261011"
    assert row["seat_geocoded_at"] is not None
    assert row["seat_address"] == ["Kraków", "Centralna", "53"]
    assert row["longitude"] == pytest.approx(20.006, abs=0.01)
    assert row["latitude"] == pytest.approx(50.064, abs=0.01)
    assert geocode_entities(connection).saved == 0
    lookup.assert_called_once_with("Kraków", "Centralna", "53")
    assert resolve.call_count == 1


@pytest.mark.parametrize("refresh", [False, True])
def test_changed_address_or_explicit_refresh_updates_saved_location(connection, seat, refresh):
    _, lookup, _ = seat
    geocode_entities(connection)
    if not refresh:
        connection.execute("UPDATE service_entities SET house_number = '54'")
    lookup.return_value = geocoding.AddressPoint(573085.53, 244516.83)
    assert geocode_entities(connection, refresh=refresh).saved == 1
    assert lookup.call_count == 2


def test_missing_address_is_skipped_without_network_lookup(connection, seat):
    _, lookup, resolve = seat
    connection.execute("UPDATE service_entities SET house_number = NULL")
    result = geocode_entities(connection)
    assert result.skipped == 1
    assert result.saved == result.failed == 0
    lookup.assert_not_called()
    resolve.assert_not_called()


def test_unmatched_changed_address_clears_old_location(connection, seat):
    _, lookup, _ = seat
    geocode_entities(connection)
    connection.execute("UPDATE service_entities SET house_number = '54'")
    lookup.return_value = None
    assert geocode_entities(connection).skipped == 1
    assert connection.execute("SELECT seat_location FROM service_entities").fetchone()["seat_location"] is None


def test_lookup_failure_is_retryable_and_preserves_previous_location(connection, seat):
    _, lookup, _ = seat
    geocode_entities(connection)
    lookup.side_effect = geocoding.GeocodingUnavailableError
    result = geocode_entities(connection, refresh=True)
    assert result.failed == 1
    assert connection.execute("SELECT seat_location FROM service_entities").fetchone()["seat_location"] is not None
    lookup.side_effect = None
    assert geocode_entities(connection, refresh=True).saved == 1


def test_concurrent_address_change_does_not_save_stale_coordinates(connection, seat):
    _, lookup, _ = seat

    def change_address(*args):
        connection.execute("UPDATE service_entities SET house_number = '54'")
        return geocoding.AddressPoint(572085.53, 244516.83)

    lookup.side_effect = change_address
    result = geocode_entities(connection)
    assert result.saved == 0
    assert result.skipped == 1
    assert connection.execute("SELECT seat_location FROM service_entities").fetchone()["seat_location"] is None


def test_seat_columns_must_be_saved_together(connection, seat):
    import psycopg

    with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
        connection.execute("UPDATE service_entities SET seat_teryt = '1261011'")
