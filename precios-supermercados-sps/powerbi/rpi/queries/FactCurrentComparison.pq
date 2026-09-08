let
    Source = BusinessMart,
    Rows = Source[facts][fact_current_comparison],
    Table = Table.FromRecords(Rows, type table [
        canonical_product_id = text, canonical_gtin = text, source_product_id = text,
        supermarket_id = text, location_id = text, category = nullable text,
        product_type = nullable text, product_name = text, brand = nullable text,
        variant = nullable text, presentation = nullable text, current_price = number,
        reported_regular_price = nullable number, is_promotion = logical, availability = text,
        observed_at = datetimezone, last_successful_run = nullable text,
        source_last_successful_at = nullable datetimezone, data_age_hours = nullable number,
        freshness_status = text, rank = nullable number, pci = nullable number,
        market_min = nullable number, market_max = nullable number, market_mean = nullable number,
        market_median = nullable number, spread_abs = nullable number, spread_pct = nullable number
    ], MissingField.UseNull)
in
    Table
