{{ config(materialized='table') }}

with enriched as (
    select
        trips.*,
        pickup_zone.borough as pickup_borough,
        pickup_zone.zone_name as pickup_zone,
        dropoff_zone.borough as dropoff_borough,
        dropoff_zone.zone_name as dropoff_zone,
        date_diff('second', trips.pickup_at, trips.dropoff_at) / 60.0 as trip_duration_minutes
    from {{ ref('stg_yellow_trips') }} as trips
    left join {{ ref('stg_taxi_zones') }} as pickup_zone
        on trips.pickup_location_id = pickup_zone.location_id
    left join {{ ref('stg_taxi_zones') }} as dropoff_zone
        on trips.dropoff_location_id = dropoff_zone.location_id
),
classified as (
    select
        *,
        case
            when pickup_at is null then 'missing_pickup_timestamp'
            when dropoff_at is null then 'missing_dropoff_timestamp'
            when strftime(pickup_at, '%Y-%m') <> source_month then 'pickup_month_mismatch'
            when dropoff_at <= pickup_at then 'non_positive_duration'
            when trip_duration_minutes > 1440 then 'duration_over_24_hours'
            when trip_distance_miles is null or trip_distance_miles < 0 then 'invalid_trip_distance'
            when pickup_zone is null then 'unknown_pickup_zone'
            when dropoff_zone is null then 'unknown_dropoff_zone'
            else null
        end as rejection_reason
    from enriched
)
select
    *,
    rejection_reason is null as is_valid
from classified
