let
    Source = BusinessMart,
    Rows = Source[dimensions][dim_category],
    Table = Table.FromRecords(Rows, type table [category = nullable text], MissingField.UseNull)
in
    Table
