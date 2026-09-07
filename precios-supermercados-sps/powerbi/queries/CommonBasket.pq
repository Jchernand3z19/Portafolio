let
    Source = StaticDataset,
    Publication = Record.Field(Source, "publication"),
    Rows = Record.Field(Publication, "common_basket"),
    RawTable = Table.FromRecords(
        Rows,
        {"supermarket_id", "location_id", "total", "is_cheapest", "product_count", "denominator_definition"},
        MissingField.UseNull
    ),
    Typed = Table.TransformColumnTypes(
        RawTable,
        {
            {"supermarket_id", type text},
            {"location_id", type text},
            {"total", Currency.Type},
            {"is_cheapest", type logical},
            {"product_count", Int64.Type},
            {"denominator_definition", type text}
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
