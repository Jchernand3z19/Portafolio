let
    Source = BusinessMart,
    Rows = Source[facts][fact_promotion_analysis],
    Table = Table.FromRecords(Rows, type table [
        canonical_product_id = text, canonical_gtin = text, source_product_id = text,
        supermarket_id = text, location_id = text, category = nullable text,
        product_type = nullable text, product_name = text, brand = nullable text,
        variant = nullable text, presentation = nullable text, as_of = datetimezone,
        history_observation_count = Int64.Type, current_price = number,
        previous_price = nullable number, reported_regular_price = nullable number,
        source_reports_promotion = logical, historical_price_reduction = nullable logical,
        source_discount_depth_pct = nullable number, current_vs_previous_pct = nullable number,
        current_vs_average_30d_pct = nullable number, current_vs_average_90d_pct = nullable number,
        current_vs_minimum_90d_pct = nullable number, promotion_duration_days = nullable number,
        promotion_event_count = Int64.Type, promotion_share_pct = number,
        historical_position = text, source_last_successful_at = nullable datetimezone,
        freshness_status = text
    ], MissingField.UseNull)
in
    Table
