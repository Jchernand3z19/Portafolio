let
    Source = BusinessMart,
    Rows = Source[dimensions][dim_brand],
    Table = Table.FromRecords(Rows, type table [brand = nullable text], MissingField.UseNull)
in
    Table
