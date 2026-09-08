let
    Source = BusinessMart,
    Rows = Source[dimensions][dim_location],
    Table = Table.FromRecords(Rows, type table [supermarket_id = text, location_id = text], MissingField.UseNull)
in
    Table
