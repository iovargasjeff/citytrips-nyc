select month
from {{ ref('mart_quality_monthly') }}
where source_rows <> accepted_rows + rejected_rows
