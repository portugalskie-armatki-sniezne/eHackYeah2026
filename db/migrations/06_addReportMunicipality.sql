-- migrate:up
ALTER TABLE reports
    ADD COLUMN municipality_teryt TEXT,
    ADD COLUMN municipality_name TEXT,
    ADD COLUMN county_teryt TEXT,
    ADD COLUMN county_name TEXT,
    ADD CONSTRAINT reports_municipality_check CHECK (
        (municipality_teryt IS NULL AND municipality_name IS NULL AND county_teryt IS NULL AND county_name IS NULL)
        OR (
            municipality_teryt IS NOT NULL AND municipality_name IS NOT NULL
            AND county_teryt IS NOT NULL AND county_name IS NOT NULL
            AND municipality_teryt ~ '^12[0-9]{4}[123]$'
            AND length(btrim(municipality_name)) > 0
            AND county_teryt = left(municipality_teryt, 4)
            AND length(btrim(county_name)) > 0
        )
    );

CREATE INDEX reports_municipality_teryt_idx ON reports (municipality_teryt);
CREATE INDEX reports_county_teryt_idx ON reports (county_teryt);

-- migrate:down
ALTER TABLE reports
    DROP CONSTRAINT reports_municipality_check,
    DROP COLUMN county_name,
    DROP COLUMN county_teryt,
    DROP COLUMN municipality_name,
    DROP COLUMN municipality_teryt;
