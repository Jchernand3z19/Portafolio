let
    Source = BusinessMart,
    Rows = Source[dimensions][dim_product],
    Table = Table.FromRecords(Rows, type table [canonical_product_id = text, canonical_gtin = text], MissingField.UseNull)
in
    Table
