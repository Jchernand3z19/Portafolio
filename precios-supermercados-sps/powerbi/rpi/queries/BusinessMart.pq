let
    Bytes = File.Contents(BusinessMartPath),
    Source = Json.Document(Bytes),
    Schema = Record.FieldOrDefault(Source, "schema", null),
    Policy = Record.FieldOrDefault(Source, "comparison_policy", null),
    ValidSchema = if Schema = "rpi-business-mart/v1" then Source else error "rpi_business_schema_invalid",
    ValidPolicy = if Policy = "fail_closed_strong_identity_and_commercial_consistency" then ValidSchema else error "rpi_business_policy_invalid"
in
    ValidPolicy
