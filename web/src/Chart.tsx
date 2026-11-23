import { useEffect, useRef } from 'react'
import type { EChartsOption } from 'echarts'
import { init } from './charts'

type ChartProps = {
  option: EChartsOption
  label: string
  height?: number
  mapName?: string
  mapData?: unknown
}

export default function Chart({ option, label, height = 320, mapName, mapData }: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    let disposed = false
    let instance: ReturnType<typeof init> | undefined
    let resizeObserver: ResizeObserver | undefined

    const render = async () => {
      if (mapName && mapData) {
        const mapCharts = await import('./mapCharts')
        mapCharts.registerTaxiZoneMap(mapName, mapData)
      }
      if (disposed || !containerRef.current) return
      instance = init(containerRef.current, undefined, { renderer: 'canvas' })
      instance.setOption(option, { notMerge: true })
      resizeObserver = new ResizeObserver(() => instance?.resize())
      resizeObserver.observe(containerRef.current)
    }

    void render()

    return () => {
      disposed = true
      resizeObserver?.disconnect()
      instance?.dispose()
    }
  }, [mapData, mapName, option])

  return (
    <div
      ref={containerRef}
      className="chart-canvas"
      role="img"
      aria-label={label}
      style={{ height }}
    />
  )
}
