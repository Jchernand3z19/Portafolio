let
    Source = BusinessMart,
    Rows = Source[facts][fact_basket_cost],
    Table = Table.FromRecords(Rows, type table [supermarket_id = text, location_id = text, total = nullable number, product_count = Int64.Type, is_complete = logical], MissingField.UseNull)
in
    Table
