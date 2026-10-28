select snapshot_id, observed_at, source_sha256, source_url
from {{ source('operational', 'snapshots') }}
