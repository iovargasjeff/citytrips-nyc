{{ config(materialized='table') }}

select
    try_cast(LocationID as integer) as location_id,
    coalesce(nullif(trim(Borough), ''), 'Unknown') as borough,
    coalesce(nullif(trim(Zone), ''), 'Unknown') as zone_name,
    coalesce(nullif(trim(service_zone), ''), 'Unknown') as service_zone
from read_csv_auto('{{ var("zone_lookup_path") }}', header = true, sample_size = -1)
where try_cast(LocationID as integer) is not null
