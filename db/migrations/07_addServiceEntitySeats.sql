-- migrate:up
ALTER TABLE service_entities
    ADD COLUMN seat_location GEOGRAPHY(POINT, 4326),
    ADD COLUMN seat_teryt TEXT,
    ADD COLUMN seat_geocoded_at TIMESTAMPTZ,
    ADD COLUMN seat_address JSONB,
    ADD CONSTRAINT service_entities_seat_check CHECK (
        num_nonnulls(seat_location, seat_teryt, seat_geocoded_at, seat_address) = 0
        OR (
            num_nonnulls(seat_location, seat_teryt, seat_geocoded_at, seat_address) = 4
            AND seat_teryt ~ '^[0-9]{7}$'
            AND jsonb_typeof(seat_address) = 'array'
        )
    );

-- migrate:down
ALTER TABLE service_entities
    DROP CONSTRAINT service_entities_seat_check,
    DROP COLUMN seat_address,
    DROP COLUMN seat_geocoded_at,
    DROP COLUMN seat_teryt,
    DROP COLUMN seat_location;
