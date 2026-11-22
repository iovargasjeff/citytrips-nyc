{{ config(materialized='table') }}

with monthly as (
    select
        source_month as month,
        count(*) as trip_count,
        count(distinct cast(pickup_at as date)) as active_days,
        median(trip_duration_minutes) as median_duration_minutes,
        quantile_cont(trip_duration_minutes, 0.9) as p90_duration_minutes,
        median(trip_distance_miles) as median_distance_miles,
        sum(cbd_congestion_fee) as reported_congestion_fee_total,
        avg(cbd_congestion_fee) as average_reported_congestion_fee,
        count(cbd_congestion_fee) as fee_reported_trips,
        count(*) as fee_eligible_rows
    from {{ ref('int_yellow_trips') }}
    where is_valid
    group by source_month
)
select
    month,
    trip_count,
    active_days,
    round(trip_count / nullif(date_part('day', last_day(cast(month || '-01' as date))), 0), 2)
        as trips_per_calendar_day,
    round(median_duration_minutes, 2) as median_duration_minutes,
    round(p90_duration_minutes, 2) as p90_duration_minutes,
    round(median_distance_miles, 2) as median_distance_miles,
    round(reported_congestion_fee_total, 2) as reported_congestion_fee_total,
    round(average_reported_congestion_fee, 2) as average_reported_congestion_fee,
    round(fee_reported_trips / nullif(fee_eligible_rows, 0), 4) as fee_reporting_coverage,
    case
        when fee_reported_trips = 0 then 'not_available'
        when fee_reported_trips = fee_eligible_rows then 'reported'
        else 'partially_reported'
    end as fee_reporting_status
from monthly
