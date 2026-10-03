-- migrate:up
-- local government offices identify local authorities and provide official contact channels.
CREATE TABLE local_government_offices (
    id BIGSERIAL PRIMARY KEY,
    -- seven-digit TERYT code, authority name, province, county, and office name.
    teryt_code TEXT NOT NULL,
    local_government_name TEXT NOT NULL,
    province TEXT,
    county TEXT,
    -- kody JST: GW = gmina wiejska, GM = gmina miejska, GMW = gmina miejsko-wiejska,
    -- pozostałe kody: P = powiat, MNP = miasto na prawach powiatu, W = województwo.
    local_government_type TEXT,
    office_name TEXT,
    -- postal address; house numbers and postal codes remain text.
    locality TEXT,
    postal_code TEXT,
    post_office TEXT,
    street TEXT,
    house_number TEXT,
    -- telephone area code, main and alternate numbers, and extension.
    phone_area_code TEXT,
    phone_number TEXT,
    alternate_phone_number TEXT,
    phone_extension TEXT,
    -- public email, website, ePUAP inbox (ESP), and e-delivery address (ADE).
    email TEXT,
    website TEXT,
    electronic_inbox TEXT,
    electronic_delivery_address TEXT
);

-- specialized civic service entities keep infrastructure managers separate from service operators.
CREATE TABLE service_entities (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT,
    entity_type TEXT NOT NULL,
    -- related locality, not a service area or routing rule.
    teryt_code TEXT,
    locality TEXT,
    postal_code TEXT,
    street TEXT,
    house_number TEXT,
    phone_number TEXT,
    email TEXT,
    website TEXT,
    bip_url TEXT,
    reporting_channel TEXT,
    reporting_channel_description TEXT,
    source_urls TEXT[] NOT NULL,
    verified_on DATE NOT NULL
);

CREATE INDEX service_entities_teryt_code_idx ON service_entities (teryt_code);
CREATE INDEX service_entities_entity_type_idx ON service_entities (entity_type);

-- migrate:down
DROP TABLE service_entities;
DROP TABLE local_government_offices;
