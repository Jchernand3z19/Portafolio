let
    Source = StaticDataset,
    Publication = Record.Field(Source, "publication"),
    Rows = Record.Field(Publication, "products"),
    RawTable = Table.FromRecords(
        Rows,
        {"canonical_product_id", "canonical_gtin", "best_supermarket_id", "best_location_id", "best_price", "highest_price", "savings_vs_highest", "savings_vs_highest_pct", "supermarket_count"},
        MissingField.UseNull
    ),
    Typed = Table.TransformColumnTypes(
        RawTable,
        {
            {"canonical_product_id", type text},
            {"canonical_gtin", type text},
            {"best_supermarket_id", type text},
            {"best_location_id", type text},
            {"best_price", Currency.Type},
            {"highest_price", Currency.Type},
            {"savings_vs_highest", Currency.Type},
            {"savings_vs_highest_pct", type number},
            {"supermarket_count", Int64.Type}
        },
        "es-HN"
    )
in
    Typed
