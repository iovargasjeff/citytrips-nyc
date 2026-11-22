{{ config(materialized='view') }}

select
    cast(VendorID as integer) as vendor_id,
    cast(tpep_pickup_datetime as timestamp) as pickup_at,
    cast(tpep_dropoff_datetime as timestamp) as dropoff_at,
    cast(PULocationID as integer) as pickup_location_id,
    cast(DOLocationID as integer) as dropoff_location_id,
    try_cast(passenger_count as integer) as passenger_count,
    try_cast(trip_distance as double) as trip_distance_miles,
    try_cast(fare_amount as double) as fare_amount,
    try_cast(tip_amount as double) as tip_amount,
    try_cast(total_amount as double) as total_amount,
    try_cast(cbd_congestion_fee as double) as cbd_congestion_fee,
    regexp_extract(filename, 'yellow_tripdata_([0-9]{4}-[0-9]{2})[.]parquet$', 1) as source_month
from read_parquet('{{ var("raw_glob") }}', union_by_name = true, filename = true)
