let
    Source = StaticDataset,
    Manifest = Record.Field(Source, "manifest"),
    Row = [
        schema = Record.Field(Source, "schema"),
        comparison_policy = Record.Field(Source, "comparison_policy"),
        published_at_utc = Record.FieldOrDefault(Source, "published_at_utc", null),
        source_workflow_run_id = Record.FieldOrDefault(Source, "source_workflow_run_id", null),
        source_head_sha = Record.FieldOrDefault(Source, "source_head_sha", null),
        source_publication_generated_at_utc = Record.FieldOrDefault(Source, "source_publication_generated_at_utc", null),
        safe_products_published = Record.FieldOrDefault(Manifest, "safe_products_published", null),
        safe_offers_published = Record.FieldOrDefault(Manifest, "safe_offers_published", null),
        common_basket_product_count = Record.FieldOrDefault(Manifest, "common_basket_product_count", null)
    ],
    RawTable = Table.FromRecords({Row}),
    Typed = Table.TransformColumnTypes(
        RawTable,
        {
            {"schema", type text},
            {"comparison_policy", type text},
            {"published_at_utc", type datetimezone},
            {"source_workflow_run_id", Int64.Type},
            {"source_head_sha", type text},
            {"source_publication_generated_at_utc", type datetimezone},
            {"safe_products_published", Int64.Type},
            {"safe_offers_published", Int64.Type},
            {"common_basket_product_count", Int64.Type}
        },
        "es-HN"
    )
in
    Typed
