with ranked as (
    select o.*, row_number() over (partition by product_key order by s.observed_at desc) as rank_number
    from {{ source('operational', 'observations') }} o
    join {{ source('operational', 'snapshots') }} s using (snapshot_id)
)
select product_key, pzn, enr, product, ingredient, manufacturer, atc, dosage_form
from ranked where rank_number = 1
