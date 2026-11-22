{{ config(materialized='table') }}

select
    source_month as month,
    pickup_borough as borough,
    date_part('dow', pickup_at)::integer as weekday,
    date_part('hour', pickup_at)::integer as hour,
    count(*) as trip_count,
    round(median(trip_duration_minutes), 2) as median_duration_minutes
from {{ ref('int_yellow_trips') }}
where is_valid
group by source_month, pickup_borough, weekday, hour
