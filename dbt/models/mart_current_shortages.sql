select * from {{ ref('fact_observation') }}
where observed_at = (select max(observed_at) from {{ ref('dim_snapshot') }})
