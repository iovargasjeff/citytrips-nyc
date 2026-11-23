import { lazy, Suspense, useEffect, useMemo, useState, type ComponentProps } from 'react'
import type { EChartsOption } from './charts'
import {
  formatCount,
  formatCoverage,
  formatDollars,
  formatMinutes,
  loadDashboardData,
  type DashboardData,
} from './data'
import {
  aggregateHeatmap,
  filterHourly,
  filterMonthly,
  filterQuality,
  filterZones,
  summarizeMonthly,
  topZones,
  type Filters,
} from './selectors'

type Page = 'overview' | 'zones' | 'quality'

const EMPTY_FILTERS: Filters = { year: 'all', month: 'all', borough: 'all' }
const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DeferredChart = lazy(() => import('./Chart'))

function Chart(props: ComponentProps<typeof DeferredChart>) {
  return (
    <Suspense fallback={<div className="chart-canvas chart-loading" aria-hidden="true" style={{ height: props.height ?? 320 }} />}>
      <DeferredChart {...props} />
    </Suspense>
  )
}

function useDashboardData() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const retry = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await loadDashboardData()
      setData(result)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The dashboard data could not be loaded.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    loadDashboardData()
      .then((result) => {
        if (!active) return
        setData(result)
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : 'The dashboard data could not be loaded.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  return { data, error, loading, retry }
}

function App() {
  const { data, error, loading, retry } = useDashboardData()
  const [page, setPage] = useState<Page>('overview')
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)

  const months = useMemo(() => data?.monthly.map((record) => record.month) ?? [], [data])
  const years = useMemo(
    () => [...new Set(months.map((month) => month.slice(0, 4)))].sort(),
    [months],
  )
  const availableMonths = useMemo(
    () => [...new Set(months.map((month) => month.slice(5, 7)))].sort(),
    [months],
  )

  const visibleMonthly = data ? filterMonthly(data.monthly, filters) : []
  const summary = summarizeMonthly(visibleMonthly)
  const visibleHourly = data ? filterHourly(data.monthlyHour, filters) : []
  const heatmap = aggregateHeatmap(visibleHourly)
  const visibleZones = data ? filterZones(data.zoneMonth, filters) : []
  const visibleQuality = data ? filterQuality(data.quality, filters) : []

  const pageTitle = page === 'overview' ? 'City overview' : page === 'zones' ? 'Neighborhoods' : 'Data quality'
  const subtitle =
    page === 'overview'
      ? 'A monthly read on how New York moves.'
      : page === 'zones'
        ? 'Where trips begin, and how demand shifts across the five boroughs.'
        : 'Every published month comes with a source trail and row-level checks.'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" onClick={() => setPage('overview')}>
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
          <span><strong>CityTrips</strong><small>NYC MOBILITY INTELLIGENCE</small></span>
        </a>

        <div className="nav-label">Explore</div>
        <nav aria-label="Dashboard pages" className="primary-nav">
          <NavButton active={page === 'overview'} onClick={() => setPage('overview')} icon="◌">
            Overview
          </NavButton>
          <NavButton active={page === 'zones'} onClick={() => setPage('zones')} icon="⌖">
            Taxi zones
          </NavButton>
          <NavButton active={page === 'quality'} onClick={() => setPage('quality')} icon="⌁">
            Data quality
          </NavButton>
        </nav>

        <div className="sidebar-bottom">
          <div className="source-status">
            <span className="status-dot" />
            <span><strong>Data pipeline</strong><small>{data ? 'Latest snapshot loaded' : 'Checking public data'}</small></span>
          </div>
          <a href="https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page" target="_blank" rel="noreferrer">
            NYC TLC data source <span aria-hidden="true">↗</span>
          </a>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <div className="page-heading">
            <p className="eyebrow">NYC YELLOW TAXI · PUBLIC DATA</p>
            <h1>{pageTitle}</h1>
            {data?.manifest.dataset_type === 'sample' && (
              <p className="sample-indicator" role="status">Illustrative local sample data</p>
            )}
            <p className="page-subtitle">{subtitle}</p>
          </div>
          <div className="filter-bar" aria-label="Dashboard filters">
            <FilterSelect label="Year" value={filters.year} onChange={(year) => setFilters({ ...filters, year, month: 'all' })}>
              <option value="all">All years</option>
              {years.map((year) => <option key={year} value={year}>{year}</option>)}
            </FilterSelect>
            <FilterSelect label="Month" value={filters.month} onChange={(month) => setFilters({ ...filters, month })}>
              <option value="all">All months</option>
              {availableMonths.map((month) => <option key={month} value={month}>{MONTH_NAMES[Number(month) - 1]}</option>)}
            </FilterSelect>
            <FilterSelect label="Borough" value={filters.borough} onChange={(borough) => setFilters({ ...filters, borough })}>
              <option value="all">All boroughs</option>
              {['Bronx', 'Brooklyn', 'Manhattan', 'Queens', 'Staten Island'].map((borough) => (
                <option key={borough} value={borough}>{borough}</option>
              ))}
            </FilterSelect>
          </div>
        </header>

        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={() => void retry()} />}
        {!loading && data && (
          <div className="dashboard-content">
            {page === 'overview' && (
              <OverviewPage
                data={data}
                filters={filters}
                monthly={visibleMonthly}
                hourly={visibleHourly}
                heatmap={heatmap}
                summary={summary}
                onOpenZones={() => setPage('zones')}
              />
            )}
            {page === 'zones' && <ZonesPage data={data} zones={visibleZones} />}
            {page === 'quality' && <QualityPage data={data} quality={visibleQuality} />}
          </div>
        )}
      </main>
    </div>
  )
}

function NavButton({
  active,
  children,
  icon,
  onClick,
}: {
  active: boolean
  children: string
  icon: string
  onClick: () => void
}) {
  return (
    <button className={`nav-button${active ? ' active' : ''}`} onClick={onClick} aria-current={active ? 'page' : undefined}>
      <span className="nav-icon" aria-hidden="true">{icon}</span>{children}
      {active && <span className="nav-active-mark" aria-hidden="true" />}
    </button>
  )
}

function FilterSelect({
  label,
  value,
  children,
  onChange,
}: {
  label: string
  value: string
  children: React.ReactNode
  onChange: (value: string) => void
}) {
  return (
    <label className="filter-select">
      <span>{label}</span>
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  )
}

function OverviewPage({
  data,
  filters,
  monthly,
  hourly,
  heatmap,
  summary,
  onOpenZones,
}: {
  data: DashboardData
  filters: Filters
  monthly: DashboardData['monthly']
  hourly: DashboardData['monthlyHour']
  heatmap: Array<{ weekday: number; hour: number; tripCount: number }>
  summary: ReturnType<typeof summarizeMonthly>
  onOpenZones: () => void
}) {
  const monthNames = monthly.map((record) => record.month)
  const dailyOption: EChartsOption = {
    animationDuration: 700,
    grid: { top: 20, right: 24, bottom: 52, left: 68 },
    tooltip: { trigger: 'axis', backgroundColor: '#202c3a', borderWidth: 0, textStyle: { color: '#f4f2ed' } },
    xAxis: {
      type: 'category',
      data: monthNames,
      axisLabel: { color: '#91a0b0', rotate: monthNames.length > 12 ? 45 : 0 },
      axisLine: { lineStyle: { color: '#344252' } },
    },
    yAxis: {
      type: 'value',
      name: 'Trips per day',
      nameTextStyle: { color: '#91a0b0' },
      axisLabel: { color: '#91a0b0', formatter: (value: number) => formatCount(value) },
      splitLine: { lineStyle: { color: '#263343' } },
    },
    series: [{
      type: 'line',
      data: monthly.map((record) => record.trips_per_calendar_day),
      smooth: 0.28,
      showSymbol: monthly.length < 18,
      symbolSize: 6,
      lineStyle: { color: '#88e0d0', width: 3 },
      itemStyle: { color: '#88e0d0', borderColor: '#111925', borderWidth: 2 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(136,224,208,.24)' }, { offset: 1, color: 'rgba(136,224,208,0)' }] } },
      markLine: {
        symbol: 'none',
        lineStyle: { color: '#f7b85c', type: 'dashed', width: 1.5 },
        label: { color: '#f7b85c', formatter: 'Congestion pricing · Jan 2025', position: 'insideEndTop' },
        data: [{ xAxis: '2025-01' }],
      },
    }],
  }

  const heatmapOption: EChartsOption = {
    grid: { top: 14, right: 22, bottom: 42, left: 96 },
    tooltip: {
      position: 'top',
      backgroundColor: '#202c3a',
      borderWidth: 0,
      textStyle: { color: '#f4f2ed' },
      formatter: (params) => {
        const point = (Array.isArray(params) ? params[0] : params) as unknown as {
          value: [number, number, number]
        }
        return `${DAY_NAMES[point.value[1]]} at ${String(point.value[0]).padStart(2, '0')}:00<br/><strong>${formatCount(point.value[2])} trips</strong>`
      },
    },
    xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, '0')), axisLabel: { color: '#91a0b0' }, splitArea: { show: true } },
    yAxis: { type: 'category', data: DAY_NAMES, axisLabel: { color: '#91a0b0' }, splitArea: { show: true } },
    visualMap: {
      min: 0,
      max: Math.max(1, ...heatmap.map((point) => point.tripCount)),
      orient: 'horizontal',
      left: 'center',
      bottom: 4,
      itemWidth: 180,
      itemHeight: 12,
      text: ['High', 'Low'],
      calculable: false,
      textStyle: { color: '#91a0b0' },
      inRange: { color: ['#202b39', '#387f82', '#88e0d0'] },
    },
    series: [{
      type: 'heatmap',
      data: heatmap.map((point) => [point.hour, point.weekday, point.tripCount]),
      emphasis: { itemStyle: { borderColor: '#f4f2ed', borderWidth: 1 } },
    }],
  }

  const top = topZones(filterZones(data.zoneMonth, filters), 5)
  const topList = top.length ? top.map((zone) => `${zone.zone_name}, ${zone.borough}`).join(' · ') : 'No zone data for this period.'

  return (
    <>
      <section className="snapshot-row" aria-label="Selected period summary">
        <MetricCard label="Recorded trips" value={formatCount(summary.tripCount)} detail={`${monthly.length} published months`} accent="mint" />
        <MetricCard label="Average trips / day" value={formatCount(summary.tripsPerCalendarDay)} detail="Normalized by calendar days" accent="blue" />
        <MetricCard label="Typical trip duration" value={formatMinutes(summary.typicalDuration)} detail="Average of monthly medians" accent="amber" />
        <MetricCard label="Fee reporting coverage" value={formatCoverage(summary.feeReportingCoverage)} detail={formatDollars(summary.congestionFeeTotal) + ' reported'} accent="violet" />
      </section>

      <section className="insight-strip">
        <div className="insight-icon" aria-hidden="true">↗</div>
        <div><strong>Read the city by the day, not just the month.</strong><p>Daily trip rates account for different month lengths. January 2025 marks the start of the MTA congestion relief toll program.</p></div>
        <button className="text-button" onClick={onOpenZones}>Explore zone demand <span aria-hidden="true">→</span></button>
      </section>

      <section className="chart-grid">
        <Panel title="Monthly ride demand" eyebrow="TRIPS PER CALENDAR DAY" className="wide-panel" action={`${monthly.length} months`}>
          {monthly.length ? <Chart option={dailyOption} label="Line chart of average taxi trips per calendar day by month" height={350} /> : <EmptyChart />}
        </Panel>
        <Panel title="When New York rides" eyebrow="PICKUP HOUR · DAY OF WEEK" action={filters.borough === 'all' ? 'All boroughs' : filters.borough}>
          {hourly.length ? <Chart option={heatmapOption} label="Heatmap of trip counts by weekday and pickup hour" height={350} /> : <EmptyChart />}
        </Panel>
      </section>

      <section className="bottom-insights">
        <div className="bottom-insight-card">
          <span className="eyebrow">MOST ACTIVE PICKUP ZONES</span>
          <p>{topList}</p>
        </div>
        <div className="bottom-insight-card policy-note">
          <span className="eyebrow">HOW TO READ THE FEE</span>
          <p>2024 records predate the fee field. “No data” means the source did not report the field, while 0 is a reported value.</p>
        </div>
      </section>
      <DataFootnote data={data} />
    </>
  )
}

function ZonesPage({ data, zones }: { data: DashboardData; zones: DashboardData['zoneMonth'] }) {
  const totals = topZones(zones, 12)
  const valueByZone = new Map<number, number>()
  for (const zone of zones) valueByZone.set(zone.location_id, (valueByZone.get(zone.location_id) ?? 0) + zone.trip_count)
  const geoOption: EChartsOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: '#202c3a',
      borderWidth: 0,
      textStyle: { color: '#f4f2ed' },
      formatter: (params) => {
        const point = params as { name: string; value: number }
        const feature = data.zones.features.find((zone) => zone.properties.name === point.name)
        return `<strong>${feature?.properties.zone ?? 'Taxi zone'}</strong><br/>${feature?.properties.borough ?? ''}<br/>${formatCount(point.value ?? 0)} trips`
      },
    },
    visualMap: {
      min: 0,
      max: Math.max(1, ...valueByZone.values()),
      left: 18,
      bottom: 18,
      text: ['High', 'Low'],
      textStyle: { color: '#9da9b8' },
      inRange: { color: ['#233143', '#336f79', '#89dfcf'] },
      calculable: false,
    },
    series: [{
      type: 'map',
      map: 'nyc-taxi-zones',
      nameProperty: 'name',
      roam: true,
      data: [...valueByZone.entries()].map(([locationId, value]) => ({ name: String(locationId), value })),
      itemStyle: { borderColor: '#536171', borderWidth: 0.7 },
      emphasis: { label: { show: false }, itemStyle: { borderColor: '#f4f2ed', borderWidth: 1.5 } },
    }],
  }

  const barOption: EChartsOption = {
    grid: { top: 8, right: 54, bottom: 8, left: 156 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: '#202c3a', borderWidth: 0, textStyle: { color: '#f4f2ed' } },
    xAxis: { type: 'value', axisLabel: { color: '#91a0b0', formatter: (value: number) => formatCount(value) }, splitLine: { lineStyle: { color: '#263343' } } },
    yAxis: { type: 'category', data: totals.map((zone) => `${zone.zone_name} · ${zone.borough}`).reverse(), axisLabel: { color: '#b5c0cc', width: 145, overflow: 'truncate' } },
    series: [{ type: 'bar', data: totals.map((zone) => zone.trip_count).reverse(), barMaxWidth: 22, itemStyle: { color: '#88e0d0', borderRadius: [0, 6, 6, 0] } }],
  }

  return (
    <>
      <section className="zone-map-layout">
        <Panel title="Trip origins by TLC zone" eyebrow="PICKUP VOLUME · FILTERABLE PERIOD" className="map-panel" action={`${data.zones.features.length} mapped zones`}>
          {zones.length ? <Chart option={geoOption} label="Map of NYC taxi zones shaded by pickup trip volume" height={520} mapName="nyc-taxi-zones" mapData={data.zones} /> : <EmptyChart />}
        </Panel>
        <Panel title="Top pickup zones" eyebrow="RANKED BY RECORDED TRIPS" className="ranking-panel" action="Top 12">
          {totals.length ? <Chart option={barOption} label="Bar chart of the twelve taxi zones with the most pickup trips" height={520} /> : <EmptyChart />}
        </Panel>
      </section>
      <DataFootnote data={data} />
    </>
  )
}

function QualityPage({ data, quality }: { data: DashboardData; quality: DashboardData['quality'] }) {
  const totals = quality.reduce(
    (result, month) => ({
      source: result.source + month.source_rows,
      accepted: result.accepted + month.accepted_rows,
      rejected: result.rejected + month.rejected_rows,
    }),
    { source: 0, accepted: 0, rejected: 0 },
  )
  const rejectionRate = totals.source ? totals.rejected / totals.source : 0

  return (
    <>
      <section className="quality-summary-grid">
        <MetricCard label="Source rows" value={formatCount(totals.source)} detail="Rows in selected months" accent="blue" />
        <MetricCard label="Rows accepted" value={formatCount(totals.accepted)} detail="Passed the trip quality rules" accent="mint" />
        <MetricCard label="Rows quarantined" value={formatCount(totals.rejected)} detail={`${formatCoverage(rejectionRate)} of source rows`} accent="amber" />
        <MetricCard label="Latest source month" value={data.manifest.latest_month} detail={`${data.manifest.source_month_count} months in snapshot`} accent="violet" />
      </section>

      <section className="quality-layout">
        <Panel title="Monthly validation results" eyebrow="SOURCE ROWS = ACCEPTED + QUARANTINED" className="quality-table-panel" action={`${quality.length} months`}>
          <div className="table-scroll">
            <table className="quality-table">
              <thead><tr><th>Month</th><th>Source</th><th>Accepted</th><th>Quarantined</th><th>Rejection rate</th></tr></thead>
              <tbody>
                {[...quality].reverse().map((month) => (
                  <tr key={month.month}>
                    <th scope="row">{month.month}</th>
                    <td>{formatCount(month.source_rows)}</td>
                    <td><span className="accepted-dot" />{formatCount(month.accepted_rows)}</td>
                    <td>{formatCount(month.rejected_rows)}</td>
                    <td><RateBar accepted={month.accepted_rows} rejected={month.rejected_rows} /></td>
                  </tr>
                ))}
                {!quality.length && <tr><td colSpan={5} className="empty-cell">No source months match these filters.</td></tr>}
              </tbody>
            </table>
          </div>
        </Panel>
        <aside className="quality-side-panel">
          <div className="side-panel-heading"><span className="eyebrow">RUN MANIFEST</span><span className="manifest-badge">Schema v{data.manifest.schema_version}</span></div>
          <h2>Every refresh leaves a trail.</h2>
          <p>Source files carry a SHA-256 checksum and row count. CI runs quality tests before the new snapshot reaches the public dashboard.</p>
          <dl className="manifest-details">
            <div><dt>Last snapshot</dt><dd>{new Date(data.manifest.built_at).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' })} UTC</dd></div>
            <div><dt>Files in snapshot</dt><dd>{formatCount(data.manifest.source_file_count)}</dd></div>
            <div><dt>Source rows</dt><dd>{formatCount(data.manifest.source_total_rows)}</dd></div>
            <div><dt>Published through</dt><dd>{data.manifest.latest_month}</dd></div>
          </dl>
        </aside>
      </section>
      <DataFootnote data={data} />
    </>
  )
}

function MetricCard({ label, value, detail, accent }: { label: string; value: string; detail: string; accent: string }) {
  return (
    <article className={`metric-card accent-${accent}`}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      <span className="metric-detail">{detail}</span>
    </article>
  )
}

function Panel({
  title,
  eyebrow,
  children,
  className = '',
  action,
}: {
  title: string
  eyebrow: string
  children: React.ReactNode
  className?: string
  action?: string
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div>
        {action && <span className="panel-action">{action}</span>}
      </div>
      {children}
    </section>
  )
}

function DataFootnote({ data }: { data: DashboardData }) {
  return (
    <footer className="data-footnote">
      <span>Source: NYC Taxi and Limousine Commission</span>
      <span>Snapshot through {data.manifest.latest_month}</span>
      <a href={data.manifest.source.url} target="_blank" rel="noreferrer">Open source catalog ↗</a>
    </footer>
  )
}

function RateBar({ accepted, rejected }: { accepted: number; rejected: number }) {
  const total = accepted + rejected
  const rate = total ? rejected / total : 0
  return (
    <span className="rate-bar-wrap" aria-label={`${formatCoverage(rate)} rejected`}>
      <span className="rate-bar"><i style={{ width: `${Math.max(1, rate * 100)}%` }} /></span>
      <span>{formatCoverage(rate)}</span>
    </span>
  )
}

function LoadingState() {
  return <section className="state-panel" role="status"><span className="loading-spinner" /><h2>Loading the latest snapshot</h2><p>Reading public taxi demand and quality data.</p></section>
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <section className="state-panel error-state" role="alert"><span className="error-mark">!</span><h2>We could not load this snapshot</h2><p>{message}</p><button className="retry-button" onClick={onRetry}>Try again</button></section>
}

function EmptyChart() {
  return <div className="empty-chart">No records match these filters.</div>
}

export default App
