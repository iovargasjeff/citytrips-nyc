select month, location_id
from {{ ref('mart_zone_month') }}
group by month, location_id
having count(*) > 1
