import { useEffect, useRef } from 'react'
import { init, type EChartsOption } from './charts'

type ChartProps = {
  option: EChartsOption
  label: string
  height?: number
}

export default function Chart({ option, label, height = 320 }: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const instance = init(containerRef.current, undefined, { renderer: 'canvas' })
    instance.setOption(option, { notMerge: true })
    const resizeObserver = new ResizeObserver(() => instance.resize())
    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      instance.dispose()
    }
  }, [option])

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
