import { use as registerEChartsModules } from 'echarts/core'
import {
  BarChart,
  HeatmapChart,
  LineChart,
} from 'echarts/charts'
import {
  GridComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

registerEChartsModules([
  BarChart,
  CanvasRenderer,
  GridComponent,
  HeatmapChart,
  LineChart,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
])

export { init, registerMap } from 'echarts/core'
export type { EChartsOption } from 'echarts'
