let
    Source = BusinessMart,
    Rows = Source[dimensions][dim_retailer],
    Table = Table.FromRecords(Rows, type table [supermarket_id = text], MissingField.UseNull)
in
    Table
