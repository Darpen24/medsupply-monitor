let
    Source = Csv.Document(File.Contents(SourceFolder & "/QualityAudit.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"run_id", type text}, {"observed_at", type text}, {"source_sha256", type text}, {"status", type text}, {"source_rows", Int64.Type}, {"accepted_rows", Int64.Type}, {"rejected_rows", Int64.Type}, {"error", type text}, {"source_url", type text}}, "en-GB")
in
    Typed