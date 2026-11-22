select month
from {{ ref('mart_monthly') }}
where month like '2024-%'
  and (fee_reporting_status <> 'not_available' or reported_congestion_fee_total is not null)
