{{ config(materialized='table') }}

select
    source_month as month,
    pickup_location_id as location_id,
    pickup_borough as borough,
    pickup_zone as zone_name,
    count(*) as trip_count,
    round(median(trip_duration_minutes), 2) as median_duration_minutes,
    round(median(trip_distance_miles), 2) as median_distance_miles
from {{ ref('int_yellow_trips') }}
where is_valid
group by source_month, pickup_location_id, pickup_borough, pickup_zone
