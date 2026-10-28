select *, source_rows - accepted_rows - rejected_rows as reconciliation_difference
from {{ source('operational', 'runs') }}
