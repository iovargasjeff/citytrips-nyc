import { MapChart } from 'echarts/charts'
import { use as registerEChartsModules, registerMap } from 'echarts/core'

registerEChartsModules([MapChart])

export function registerTaxiZoneMap(name: string, geoJson: unknown) {
  registerMap(name, geoJson as Parameters<typeof registerMap>[1])
}
