-- migrate:up
CREATE TABLE institution_contacts (
    id BIGSERIAL PRIMARY KEY,
    -- seven-digit TERYT code, authority name, province, county, and office name.
    teryt_code TEXT NOT NULL UNIQUE CHECK (teryt_code ~ '^[0-9]{7}$'),
    local_government_name TEXT NOT NULL CHECK (BTRIM(local_government_name) <> ''),
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
    -- fax area code, number, and extension, as provided by the source.
    fax_area_code TEXT,
    fax_number TEXT,
    fax_extension TEXT,
    -- public email, website, ePUAP inbox (ESP), and e-delivery address (ADE).
    email TEXT,
    website TEXT,
    electronic_inbox TEXT,
    electronic_delivery_address TEXT
);


-- migrate:down
DROP TABLE institution_contacts;
