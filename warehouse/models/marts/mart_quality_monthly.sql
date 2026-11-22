{{ config(materialized='table') }}

select
    source_month as month,
    count(*) as source_rows,
    count(*) filter (where is_valid) as accepted_rows,
    count(*) filter (where not is_valid) as rejected_rows,
    count(*) filter (where rejection_reason = 'missing_pickup_timestamp') as missing_pickup_timestamp,
    count(*) filter (where rejection_reason = 'missing_dropoff_timestamp') as missing_dropoff_timestamp,
    count(*) filter (where rejection_reason = 'pickup_month_mismatch') as pickup_month_mismatch,
    count(*) filter (where rejection_reason = 'non_positive_duration') as non_positive_duration,
    count(*) filter (where rejection_reason = 'duration_over_24_hours') as duration_over_24_hours,
    count(*) filter (where rejection_reason = 'invalid_trip_distance') as invalid_trip_distance,
    count(*) filter (where rejection_reason = 'unknown_pickup_zone') as unknown_pickup_zone,
    count(*) filter (where rejection_reason = 'unknown_dropoff_zone') as unknown_dropoff_zone
from {{ ref('int_yellow_trips') }}
group by source_month
