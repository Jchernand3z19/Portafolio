let
    Source = BusinessMart,
    Rows = Source[facts][fact_metric_coverage],
    Table = Table.FromRecords(Rows, type table [comparable_count = Int64.Type, valid_price_count = Int64.Type, excluded_count = Int64.Type, coverage_pct = number, as_of = datetimezone, freshness_window_hours = Int64.Type], MissingField.UseNull)
in
    Table
