CREATE TABLE supermarkets (
            supermarket_id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            country_code TEXT NOT NULL CHECK (length(country_code) = 2)
        ) STRICT;

CREATE TABLE locations (
            location_id TEXT PRIMARY KEY,
            supermarket_id TEXT NOT NULL,
            city_name TEXT NOT NULL,
            country_code TEXT NOT NULL CHECK (length(country_code) = 2),
            FOREIGN KEY (supermarket_id) REFERENCES supermarkets(supermarket_id),
            UNIQUE (supermarket_id, city_name),
            UNIQUE (location_id, supermarket_id)
        ) STRICT;

CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            supermarket_id TEXT NOT NULL,
            source_key_type TEXT NOT NULL,
            source_key TEXT NOT NULL,
            source_catalog_product_id TEXT NOT NULL,
            source_item_id TEXT NOT NULL,
            reference TEXT,
            ean TEXT,
            name TEXT NOT NULL,
            brand TEXT,
            presentation TEXT,
            category TEXT,
            FOREIGN KEY (supermarket_id) REFERENCES supermarkets(supermarket_id),
            UNIQUE (supermarket_id, source_key_type, source_key),
            UNIQUE (product_id, supermarket_id)
        ) STRICT;

CREATE TABLE scrape_runs (
            scrape_run_id TEXT PRIMARY KEY,
            supermarket_id TEXT NOT NULL,
            location_id TEXT NOT NULL,
            observed_at_utc TEXT NOT NULL,
            run_status TEXT NOT NULL CHECK (run_status IN ('success', 'rejected', 'failed')),
            sku_count INTEGER NOT NULL CHECK (sku_count >= 0),
            catalog_product_count INTEGER NOT NULL CHECK (catalog_product_count >= 0),
            source_artifact_id TEXT,
            source_json_sha256 TEXT,
            error_reason TEXT,
            FOREIGN KEY (supermarket_id) REFERENCES supermarkets(supermarket_id),
            FOREIGN KEY (location_id, supermarket_id)
                REFERENCES locations(location_id, supermarket_id)
        ) STRICT;

CREATE TABLE price_history (
            product_id INTEGER NOT NULL,
            supermarket_id TEXT NOT NULL,
            location_id TEXT NOT NULL,
            current_price_minor INTEGER NOT NULL CHECK (current_price_minor >= 0),
            reported_regular_price_minor INTEGER CHECK (
                reported_regular_price_minor IS NULL
                OR reported_regular_price_minor >= 0
            ),
            is_promotion INTEGER NOT NULL CHECK (is_promotion IN (0, 1)),
            availability TEXT NOT NULL CHECK (
                availability IN ('in_stock', 'out_of_stock', 'unknown')
            ),
            currency TEXT NOT NULL CHECK (currency = 'HNL'),
            valid_from_utc TEXT NOT NULL,
            valid_to_utc TEXT,
            scrape_run_id TEXT NOT NULL,
            PRIMARY KEY (product_id, location_id, valid_from_utc),
            FOREIGN KEY (product_id, supermarket_id)
                REFERENCES products(product_id, supermarket_id),
            FOREIGN KEY (location_id, supermarket_id)
                REFERENCES locations(location_id, supermarket_id),
            FOREIGN KEY (scrape_run_id) REFERENCES scrape_runs(scrape_run_id)
        ) STRICT;

CREATE INDEX idx_products_name ON products(name);

CREATE INDEX idx_price_history_current
            ON price_history(location_id, product_id)
            WHERE valid_to_utc IS NULL;
