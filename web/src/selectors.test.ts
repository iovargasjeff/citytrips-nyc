import { describe, expect, it } from 'vitest'
import type { MonthlyHourMetric, MonthlyMetric, ZoneMonthMetric } from './data'
import { aggregateHeatmap, filterHourly, filterMonthly, filterZones, summarizeMonthly } from './selectors'

const monthly: MonthlyMetric[] = [
  {
    month: '2024-01',
    trip_count: 310,
    active_days: 31,
    trips_per_calendar_day: 10,
    median_duration_minutes: 14,
    p90_duration_minutes: 29,
    median_distance_miles: 2,
    reported_congestion_fee_total: null,
    average_reported_congestion_fee: null,
    fee_reporting_coverage: 0,
    fee_reporting_status: 'not_available',
  },
  {
    month: '2025-01',
    trip_count: 620,
    active_days: 31,
    trips_per_calendar_day: 20,
    median_duration_minutes: 16,
    p90_duration_minutes: 33,
    median_distance_miles: 2.2,
    reported_congestion_fee_total: 310,
    average_reported_congestion_fee: 0.5,
    fee_reporting_coverage: 1,
    fee_reporting_status: 'reported',
  },
]

describe('dashboard selectors', () => {
  it('filters calendar periods without losing the historical fee state', () => {
    expect(filterMonthly(monthly, { year: '2024', month: 'all', borough: 'all' })).toEqual([
      monthly[0],
    ])
    expect(monthly[0].reported_congestion_fee_total).toBeNull()
  })

  it('orders monthly data chronologically for the trend chart', () => {
    expect(filterMonthly([...monthly].reverse(), { year: 'all', month: 'all', borough: 'all' })).toEqual(monthly)
  })

  it('summarizes trips per calendar day and weighted fee coverage', () => {
    const summary = summarizeMonthly(monthly)
    expect(summary.tripCount).toBe(930)
    expect(summary.tripsPerCalendarDay).toBe(15)
    expect(summary.feeReportingCoverage).toBeCloseTo(2 / 3)
    expect(summary.congestionFeeTotal).toBe(310)
  })

  it('filters borough demand and aggregates weekday-hour buckets', () => {
    const hourly: MonthlyHourMetric[] = [
      { month: '2025-01', borough: 'Manhattan', weekday: 1, hour: 8, trip_count: 5, median_duration_minutes: 12 },
      { month: '2025-02', borough: 'Manhattan', weekday: 1, hour: 8, trip_count: 7, median_duration_minutes: 13 },
      { month: '2025-01', borough: 'Brooklyn', weekday: 1, hour: 8, trip_count: 3, median_duration_minutes: 14 },
    ]
    const filtered = filterHourly(hourly, { year: '2025', month: 'all', borough: 'Manhattan' })
    expect(aggregateHeatmap(filtered)).toEqual([{ weekday: 1, hour: 8, tripCount: 12 }])
  })

  it('filters zone records consistently with the selected district', () => {
    const zones: ZoneMonthMetric[] = [
      { month: '2025-01', location_id: 1, borough: 'Manhattan', zone_name: 'Midtown', trip_count: 10, median_duration_minutes: 12, median_distance_miles: 2 },
      { month: '2025-01', location_id: 2, borough: 'Brooklyn', zone_name: 'DUMBO', trip_count: 5, median_duration_minutes: 15, median_distance_miles: 3 },
    ]
    expect(filterZones(zones, { year: 'all', month: '01', borough: 'Brooklyn' })).toEqual([zones[1]])
  })
})
