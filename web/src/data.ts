export type MonthlyMetric = {
  month: string
  trip_count: number
  active_days: number
  trips_per_calendar_day: number
  median_duration_minutes: number
  p90_duration_minutes: number
  median_distance_miles: number
  reported_congestion_fee_total: number | null
  average_reported_congestion_fee: number | null
  fee_reporting_coverage: number
  fee_reporting_status: 'not_available' | 'reported' | 'partially_reported'
}

export type MonthlyHourMetric = {
  month: string
  borough: string
  weekday: number
  hour: number
  trip_count: number
  median_duration_minutes: number
}

export type ZoneMonthMetric = {
  month: string
  location_id: number
  borough: string
  zone_name: string
  trip_count: number
  median_duration_minutes: number
  median_distance_miles: number
}

export type QualityMetric = {
  month: string
  source_rows: number
  accepted_rows: number
  rejected_rows: number
  missing_pickup_timestamp: number
  missing_dropoff_timestamp: number
  pickup_month_mismatch: number
  non_positive_duration: number
  duration_over_24_hours: number
  invalid_trip_distance: number
  unknown_pickup_zone: number
  unknown_dropoff_zone: number
}

export type GeoFeatureCollection = {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    properties: { name: string; LocationID: number; borough: string; zone: string }
    geometry: { type: string; coordinates: unknown }
  }>
}

export type PublicManifest = {
  schema_version: number
  dataset_type: 'sample' | 'published'
  built_at: string
  latest_month: string
  source_month_count: number
  source_file_count: number
  source_total_rows: number
  published_months: string[]
  files: Array<{ month: string; sha256: string; rows: number; url: string }>
  source: { name: string; url: string }
}

export type DashboardData = {
  manifest: PublicManifest
  monthly: MonthlyMetric[]
  monthlyHour: MonthlyHourMetric[]
  zoneMonth: ZoneMonthMetric[]
  quality: QualityMetric[]
  zones: GeoFeatureCollection
}

async function fetchJson<T>(filename: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/${filename}`)
  if (!response.ok) {
    throw new Error(`Could not load ${filename} (${response.status})`)
  }
  return response.json() as Promise<T>
}

export async function loadDashboardData(): Promise<DashboardData> {
  const [manifest, monthly, monthlyHour, zoneMonth, quality, zones] = await Promise.all([
    fetchJson<PublicManifest>('manifest.json'),
    fetchJson<MonthlyMetric[]>('monthly.json'),
    fetchJson<MonthlyHourMetric[]>('monthly_hour.json'),
    fetchJson<ZoneMonthMetric[]>('zone_month.json'),
    fetchJson<QualityMetric[]>('quality.json'),
    fetchJson<GeoFeatureCollection>('taxi_zones.geojson'),
  ])

  if (manifest.schema_version !== 1) {
    throw new Error(`Unsupported dashboard data version ${manifest.schema_version}`)
  }

  return { manifest, monthly, monthlyHour, zoneMonth, quality, zones }
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value)
}

export function formatMinutes(value: number): string {
  return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(value)} min`
}

export function formatDollars(value: number | null): string {
  if (value === null) return 'No data'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatCoverage(value: number): string {
  return `${new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 1 }).format(value)}`
}
