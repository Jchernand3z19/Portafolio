let
    Source = StaticDataset,
    Rows = Record.Field(Source, "source_descriptors"),
    RawTable = Table.FromRecords(
        Rows,
        {"canonical_product_id", "canonical_gtin", "source_record_id", "supermarket_id", "source_name", "source_brand", "source_presentation", "source_category"},
        MissingField.UseNull
    ),
    Typed = Table.TransformColumnTypes(
        RawTable,
        {
            {"canonical_product_id", type text},
            {"canonical_gtin", type text},
            {"source_record_id", type text},
            {"supermarket_id", type text},
            {"source_name", type text},
            {"source_brand", type text},
            {"source_presentation", type text},
            {"source_category", type text}
        },
        "es-HN"
    )
in
    Typed
