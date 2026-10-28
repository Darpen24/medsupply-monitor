# Data contract and counting rules

## Source and scope

- Publisher: BfArM/PharmNet Bund public reported shortage feed.
- URL: `https://anwendungen.pharmnet-bund.de/lieferengpassmeldungen/public/csv`.
- Observed baseline: 28 October 2026; exact acquisition timestamp, byte hash and source attribution are in `data/sample/manifest.json`.
- Format: semicolon-delimited CSV. The baseline uses Windows-1252; UTF-8 with optional BOM is also accepted. CSV quoting and embedded newlines are handled by the standard CSV parser.
- The source includes spelling `Arzneimittlbezeichnung`; the parser deliberately maps that exact header rather than assuming a corrected spelling.

## Tables

| Table | Grain | Role |
|---|---|---|
| `runs` | One attempted timestamp/content combination | Status, candidate/invalid counts, errors and source hash |
| `snapshots` | One accepted observation timestamp | Immutable source lineage and chronological publication |
| `observations` | One accepted product key per snapshot | Reported source fields and normalized types |
| `quarantine` | One rejected source row per attempted run | Row number, issue and original row values |
| `changes` | One changed field or membership event per product key and snapshot | Comparison of consecutive accepted snapshots |
| `current_observations` | Latest accepted snapshot's observations | Safe current reporting surface |

For a successful parsed run, source rows = accepted candidate rows + rejected rows. On a >5% quality-gate failure, accepted candidate rows are **not published**. Parse-level errors can occur before row counts are known; their counts are recorded as zero with the parse error, not as evidence the upstream source is empty.

## Identity

`product_key` is the first 24 hex characters of SHA-256 over the JSON array `[ENR, PZN, product label]`. It is a project observation identity, not an official medicine or shortage-episode identifier.

- PZN remains eight-digit text. Placeholder source values such as `00000000` and `99999999` are retained, not assumed to identify unique real packages.
- ENR and the source product label reduce collisions involving placeholder PZNs.
- Different records with the same computed identity within one snapshot are all quarantined. The project does not arbitrarily choose the newest row.
- A product-label or ENR change creates a different key and appears as a membership change. This is a known identity limitation.
- `report_id` preserves `Bearbeitungsnummer`. It can change across updates and can be shared by multiple packages. It is not used as the stable product key.
- `referenced_report` is preserved for investigation. Missing linked history is not invented, and referenced IDs are not assumed to reconstruct a complete episode chain.

## Important columns

| Column | Meaning / type |
|---|---|
| `pzn`, `enr`, `report_id` | Source identifiers, text |
| `start_date` | Source reported beginning, ISO date or empty |
| `expected_end_date` | Source expected end, ISO date or empty; not a confirmed resolution |
| `source_updated`, `first_reported` | Source dates, distinct from acquisition timestamp |
| `ingredient` | Raw ingredient label; combinations and salt forms are not normalized |
| `manufacturer` | Source authorization-holder label, not necessarily the physical factory |
| `hospital_relevant` | Source `ja`/`nein`; not a hospital's actual exposure |
| `classification` | Source supply relevance classification |
| `critical_flag` | 1 only for exact source value `verskri (auch versrel)` |
| `reason_type`, `reason`, `reason_note` | Published reported explanation; no inferred causation |
| `observed_at` | Acquisition timestamp normalized to UTC, with timezone |
| `content_hash` | Deterministic normalized record hash |

The critical flag comes from the feed's classification. The project does not fuzzy-match the BfArM PDF and falsely assume every formulation of an ingredient has the same critical designation. The PDF is a reference, not an independent automatic classifier.

## Baseline exclusions

The parser's CSV record numbering includes the header as row 1. One structurally incomplete source record (Xenpozyme) is missing its final classification field. Two Scintimun records share ENR, PZN and product label but have different report IDs and expected ends. All three are retained in quarantine and excluded from accepted metrics. Original unmodified bytes remain available for manual interpretation.

## Metrics

- **Package observations:** accepted product keys in the selected/latest snapshot.
- **Source reports:** distinct source report IDs among accepted observations; not shortage episodes.
- **Ingredient labels:** distinct raw strings, not normalized active substances.
- **Supply-critical observations:** accepted package rows whose source classification is `verskri (auch versrel)`.
- **Hospital-relevant observations:** accepted package rows with source flag `ja`.
- **Extensions:** accepted keys whose expected end date increased between the two latest accepted snapshots. Counts are package observations, not affected patients or report episodes.

## Source coverage limits

The public feed reports selected disruptions. It is not complete inventory, purchasing, manufacturer-capacity, medication-demand, price or clinical-outcome data. A past expected end, a missing record, or unchanged bytes does not prove resolution, continued disruption or absence of unreported problems. Source dates and classifications must be interpreted within the publisher's reporting scope.
