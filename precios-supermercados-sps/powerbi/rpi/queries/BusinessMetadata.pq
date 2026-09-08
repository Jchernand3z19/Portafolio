let
    Source = BusinessMart,
    Row = [
        schema = Source[schema],
        comparison_policy = Source[comparison_policy],
        comparison_status = Source[comparison_status],
        currency = Source[currency],
        blocked_reasons = Text.Combine(Source[blocked_reasons], ", ")
    ],
    Table = Table.FromRecords({Row}, type table [schema = text, comparison_policy = text, comparison_status = text, currency = text, blocked_reasons = text], MissingField.UseNull)
in
    Table
