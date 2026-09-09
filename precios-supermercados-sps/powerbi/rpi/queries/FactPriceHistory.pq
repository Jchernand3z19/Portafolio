let
    Source = BusinessMart,
    Rows = Source[facts][fact_price_history],
    Table = Table.FromRecords(Rows, type table [
        canonical_product_id = text, canonical_gtin = text, source_product_id = text,
        supermarket_id = text, location_id = text, category = nullable text,
        product_type = nullable text, product_name = text, brand = nullable text,
        variant = nullable text, presentation = nullable text, period_start = datetimezone,
        current_price = number, reported_regular_price = nullable number,
        is_promotion = logical, previous_price = nullable number, change_abs = nullable number,
        change_pct = nullable number, direction = text, is_current = logical,
        source_last_successful_at = nullable datetimezone, freshness_status = text
    ], MissingField.UseNull)
in
    Table
