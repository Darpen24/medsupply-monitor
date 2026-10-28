select s.snapshot_id
from {{ ref('dim_snapshot') }} s
join {{ source('operational', 'runs') }} r on r.run_id=s.snapshot_id
left join {{ ref('fact_observation') }} o on o.snapshot_id=s.snapshot_id
group by s.snapshot_id,r.accepted_rows
having count(o.product_key) <> r.accepted_rows
