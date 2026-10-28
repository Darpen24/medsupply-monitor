select c.*, s.observed_at,
    case when c.field = 'expected_end_date' and c.old_value <> '' and c.new_value <> ''
         and c.new_value > c.old_value then 1 else 0 end as end_date_extended
from {{ source('operational', 'changes') }} c
join {{ ref('dim_snapshot') }} s using (snapshot_id)
