let
    Source = BusinessMart,
    Rows = Source[source_freshness],
    Table = Table.FromRecords(Rows, type table [supermarket_id = text, location_id = text, last_successful_run = nullable text, observed_at = nullable datetimezone, data_age_hours = nullable number, freshness_status = text], MissingField.UseNull)
in
    Table
