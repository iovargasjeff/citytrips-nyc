import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import App from './App'
import { loadDashboardData, type DashboardData } from './data'

vi.mock('./data', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./data')>()
  return { ...actual, loadDashboardData: vi.fn() }
})

vi.mock('./Chart', () => ({
  default: ({ label }: { label: string }) => <div role="img" aria-label={label} />,
}))

const dashboardFixture: DashboardData = {
  manifest: {
    schema_version: 1,
    dataset_type: 'sample',
    built_at: '2026-11-22T00:00:00Z',
    latest_month: '2025-01',
    source_month_count: 2,
    source_file_count: 2,
    source_total_rows: 370,
    published_months: ['2024-01', '2025-01'],
    files: [],
    source: {
      name: 'NYC Taxi and Limousine Commission Yellow Taxi Trip Records',
      url: 'https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page',
    },
  },
  monthly: [
    {
      month: '2024-01',
      trip_count: 100,
      active_days: 31,
      trips_per_calendar_day: 3.2,
      median_duration_minutes: 14,
      p90_duration_minutes: 29,
      median_distance_miles: 1.5,
      reported_congestion_fee_total: null,
      average_reported_congestion_fee: null,
      fee_reporting_coverage: 0,
      fee_reporting_status: 'not_available',
    },
    {
      month: '2025-01',
      trip_count: 200,
      active_days: 31,
      trips_per_calendar_day: 6.5,
      median_duration_minutes: 16,
      p90_duration_minutes: 31,
      median_distance_miles: 1.7,
      reported_congestion_fee_total: 50,
      average_reported_congestion_fee: 0.5,
      fee_reporting_coverage: 1,
      fee_reporting_status: 'reported',
    },
  ],
  monthlyHour: [
    { month: '2025-01', borough: 'Manhattan', weekday: 1, hour: 8, trip_count: 20, median_duration_minutes: 15 },
  ],
  zoneMonth: [
    { month: '2025-01', location_id: 1, borough: 'Manhattan', zone_name: 'Battery Park', trip_count: 20, median_duration_minutes: 15, median_distance_miles: 1.4 },
  ],
  quality: [
    { month: '2024-01', source_rows: 120, accepted_rows: 100, rejected_rows: 20, missing_pickup_timestamp: 0, missing_dropoff_timestamp: 0, pickup_month_mismatch: 0, non_positive_duration: 0, duration_over_24_hours: 0, invalid_trip_distance: 0, unknown_pickup_zone: 0, unknown_dropoff_zone: 0 },
    { month: '2025-01', source_rows: 250, accepted_rows: 200, rejected_rows: 50, missing_pickup_timestamp: 0, missing_dropoff_timestamp: 0, pickup_month_mismatch: 0, non_positive_duration: 0, duration_over_24_hours: 0, invalid_trip_distance: 0, unknown_pickup_zone: 0, unknown_dropoff_zone: 0 },
  ],
  zones: {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { name: '1', LocationID: 1, borough: 'Manhattan', zone: 'Battery Park' },
        geometry: { type: 'MultiPolygon', coordinates: [] },
      },
    ],
  },
}

describe('CityTrips dashboard', () => {
  beforeEach(() => {
    vi.mocked(loadDashboardData).mockResolvedValue(dashboardFixture)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('loads a snapshot, labels local samples, and filters quality by year', async () => {
    render(<App />)

    expect(await screen.findByText('300')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Illustrative local sample data')

    fireEvent.click(screen.getByRole('button', { name: 'Data quality' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'Year' }), { target: { value: '2025' } })

    const qualityTable = screen.getByRole('table')
    expect(within(qualityTable).getByText('2025-01')).toBeInTheDocument()
    expect(within(qualityTable).queryByText('2024-01')).not.toBeInTheDocument()
    expect(qualityTable).toHaveTextContent('200')
  })

  it('shows a retry path when snapshot loading fails', async () => {
    vi.mocked(loadDashboardData).mockRejectedValueOnce(new Error('Snapshot unavailable'))
    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Snapshot unavailable')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('300')).toBeInTheDocument()
  })
})
