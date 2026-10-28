select * from {{ ref('mart_quality') }} where reconciliation_difference <> 0
