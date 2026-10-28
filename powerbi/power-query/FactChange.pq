let
    Source = Csv.Document(File.Contents(SourceFolder & "/FactChange.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"snapshot_id", type text}, {"product_key", type text}, {"change_type", type text}, {"field", type text}, {"old_value", type text}, {"new_value", type text}, {"observed_at", type text}}, "en-GB")
in
    Typed