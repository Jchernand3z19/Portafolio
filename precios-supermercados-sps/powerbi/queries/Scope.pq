let
    Source = StaticDataset,
    Rows = Record.Field(Source, "scope"),
    RawTable = Table.FromRecords(
        Rows,
        {"supermarket_id", "location_id"},
        MissingField.UseNull
    ),
    Typed = Table.TransformColumnTypes(
        RawTable,
        {
            {"supermarket_id", type text},
            {"location_id", type text}
        },
        "es-HN"
    ),
    WithScopeKey = Table.AddColumn(
        Typed,
        "scope_key",
        each [supermarket_id] & "|" & [location_id],
        type text
    )
in
    WithScopeKey
