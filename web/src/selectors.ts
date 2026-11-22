import type {
  MonthlyHourMetric,
  MonthlyMetric,
  QualityMetric,
  ZoneMonthMetric,
} from './data'

export type Filters = { year: string; month: string; borough: string }

function matchesPeriod(month: string, filters: Filters): boolean {
  return (
    (filters.year === 'all' || month.startsWith(`${filters.year}-`)) &&
    (filters.month === 'all' || month.endsWith(`-${filters.month}`))
  )
}

export function filterMonthly(records: MonthlyMetric[], filters: Filters): MonthlyMetric[] {
  return records.filter((record) => matchesPeriod(record.month, filters))
}

export function filterHourly(records: MonthlyHourMetric[], filters: Filters): MonthlyHourMetric[] {
  return records.filter(
    (record) =>
      matchesPeriod(record.month, filters) &&
      (filters.borough === 'all' || record.borough === filters.borough),
  )
}

export function filterZones(records: ZoneMonthMetric[], filters: Filters): ZoneMonthMetric[] {
  return records.filter(
    (record) =>
      matchesPeriod(record.month, filters) &&
      (filters.borough === 'all' || record.borough === filters.borough),
  )
}

export function filterQuality(records: QualityMetric[], filters: Filters): QualityMetric[] {
  return records.filter((record) => matchesPeriod(record.month, filters))
}

export function summarizeMonthly(records: MonthlyMetric[]) {
  const tripCount = records.reduce((total, record) => total + record.trip_count, 0)
  const calendarDays = records.reduce((total, record) => {
    const [year, month] = record.month.split('-').map(Number)
    return total + new Date(Date.UTC(year, month, 0)).getUTCDate()
  }, 0)
  const weightedCoverage = tripCount
    ? records.reduce(
        (total, record) => total + record.trip_count * record.fee_reporting_coverage,
        0,
      ) / tripCount
    : 0
  const feeValues = records
    .map((record) => record.reported_congestion_fee_total)
    .filter((value): value is number => value !== null)
  const durationValues = records
    .map((record) => record.median_duration_minutes)
    .filter(Number.isFinite)
  const typicalDuration = durationValues.length
    ? durationValues.reduce((total, value) => total + value, 0) / durationValues.length
    : 0

  return {
    tripCount,
    tripsPerCalendarDay: calendarDays ? tripCount / calendarDays : 0,
    typicalDuration,
    congestionFeeTotal: feeValues.length ? feeValues.reduce((total, value) => total + value, 0) : null,
    feeReportingCoverage: weightedCoverage,
  }
}

export function aggregateHeatmap(records: MonthlyHourMetric[]) {
  const totals = new Map<string, number>()
  for (const record of records) {
    const key = `${record.weekday}-${record.hour}`
    totals.set(key, (totals.get(key) ?? 0) + record.trip_count)
  }
  return [...totals.entries()].map(([key, tripCount]) => {
    const [weekday, hour] = key.split('-').map(Number)
    return { weekday, hour, tripCount }
  })
}

export function topZones(records: ZoneMonthMetric[], limit = 10): ZoneMonthMetric[] {
  const totals = new Map<number, ZoneMonthMetric>()
  for (const record of records) {
    const existing = totals.get(record.location_id)
    totals.set(record.location_id, {
      ...record,
      trip_count: record.trip_count + (existing?.trip_count ?? 0),
    })
  }
  return [...totals.values()].sort((left, right) => right.trip_count - left.trip_count).slice(0, limit)
}
