let
    Source = Csv.Document(File.Contents(SourceFolder & "/Snapshot.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"snapshot_id", type text}, {"observed_at", type text}, {"source_sha256", type text}, {"raw_path", type text}, {"source_url", type text}}, "en-GB")
in
    Typed