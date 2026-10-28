select o.*, o.snapshot_id || ':' || o.product_key as observation_id, s.observed_at
from {{ source('operational', 'observations') }} o
join {{ ref('dim_snapshot') }} s using (snapshot_id)
