let
    Source = StaticDataset,
    Publication = Record.Field(Source, "publication"),
    Rows = Record.Field(Publication, "offers"),
    RawTable = Table.FromRecords(
        Rows,
        {"canonical_product_id", "canonical_gtin", "supermarket_id", "location_id", "source_record_id", "current_price", "is_best_price"},
        MissingField.UseNull
    ),
    Typed = Table.TransformColumnTypes(
        RawTable,
        {
            {"canonical_product_id", type text},
            {"canonical_gtin", type text},
            {"supermarket_id", type text},
            {"location_id", type text},
            {"source_record_id", type text},
            {"current_price", Currency.Type},
            {"is_best_price", type logical}
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
