<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import * as echarts from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import * as XLSX from 'xlsx'

import { getAnalytics, getCodeOptions } from '../api'

echarts.use([LineChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent, CanvasRenderer])

const selectedOriginal = ref('')
const selectedCode = ref('')

const allOptions = ref([])
const loadingMain = ref(false)

const originalOptions = computed(() => {
  const map = new Map()
  for (const o of allOptions.value || []) {
    if (!o.original_url) continue
    if (!map.has(o.original_url)) {
      map.set(o.original_url, { value: o.original_url, label: o.original_url })
    }
  }
  return Array.from(map.values())
})

const codeOptionsForSelectedOriginal = computed(() => {
  if (!selectedOriginal.value) return []
  return (allOptions.value || [])
    .filter(o => o.original_url === selectedOriginal.value)
    .map(o => ({
      ...o,
      value: o.value,
      label: `${o.title || '(未命名)'} · ${o.value}`,
    }))
})

const range = ref('24h')
const custom = ref({ start: '', end: '' })
const chartType = ref('line')

const hourlyData = ref([])
const dailyData = ref([])
const siblingsData = ref([])
const siblingsDailyData = ref([])
const siblingsHourlyData = ref([])

const hourlyOpt = ref({})
const dailyOpt = ref({})
const siblingsOpt = ref({})

const loading = ref(false)

function toISO(dt) {
  if (!dt) return ''
  if (typeof dt === 'string') return dt
  try { return new Date(dt).toISOString() } catch { return '' }
}

function normalizeHourLabel(s) {
  if (!s) return ''
  if (/^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}$/.test(s)) {
    return s.replace(' ', 'T') + ':00'
  }
  if (/^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}$/.test(s)) {
    return s.replace(' ', 'T')
  }
  return s
}

function formatHourTick(s) {
  const v = normalizeHourLabel(s)
  try {
    const d = new Date(v)
    if (Number.isNaN(d.getTime())) return s
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    return `${mm}-${dd} ${hh}`
  } catch {
    return s
  }
}

function formatHourTooltip(s) {
  const v = normalizeHourLabel(s)
  try {
    const d = new Date(v)
    if (Number.isNaN(d.getTime())) return s
    const yyyy = d.getFullYear()
    const MM = String(d.getMonth() + 1).padStart(2, '0')
    const DD = String(d.getDate()).padStart(2, '0')
    const HH = String(d.getHours()).padStart(2, '0')
    return `${yyyy}-${MM}-${DD} ${HH}:00`
  } catch {
    return s
  }
}

function formatDateTick(s) {
  if (!s) return ''
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return String(s)
  return `${m[2]}-${m[3]}`
}

async function refresh() {
  if (!selectedCode.value) { return }
  const params = {}
  if (range.value === 'custom') {
    if (!custom.value.start || !custom.value.end) {
      ElMessage.warning('请选择自定义起止时间')
      return
    }
    params.range = 'custom'
    params.start = toISO(custom.value.start)
    params.end = toISO(custom.value.end)
  } else {
    params.range = range.value
  }

  loading.value = true
  try {
    const res = await getAnalytics(selectedCode.value, params)
    const hourly = res.data.hourly || []
    const daily = res.data.daily || []
    const siblings = res.data.siblings_top || []
    const siblingsDaily = res.data.siblings_daily || []
    const siblingsHourly = res.data.siblings_hourly || []

    hourlyData.value = hourly
    dailyData.value = daily
    siblingsData.value = siblings
    siblingsDailyData.value = siblingsDaily
    siblingsHourlyData.value = siblingsHourly

    hourlyOpt.value = buildSeriesOption(
      (chartType.value === 'line') ? 'line' : 'bar',
      '最近分时趋势',
      hourly.map(i => i.hour),
      hourly.map(i => Number(i.clicks || 0)),
      {
        xTickFormatter: formatHourTick,
        tooltipLabelFormatter: (axisValue) => formatHourTooltip(axisValue),
      }
    )

    dailyOpt.value = buildSeriesOption(
      (chartType.value === 'line') ? 'line' : 'bar',
      '按天历史趋势',
      daily.map(i => i.date),
      daily.map(i => Number(i.clicks || 0)),
      {
        xTickFormatter: formatDateTick,
        tooltipLabelFormatter: (axisValue) => String(axisValue || ''),
      }
    )

    siblingsOpt.value = buildBarOption(
      '同原链接不同短链（按标题）Top',
      siblings.map(i => `${i.title || '(未命名)'} · ${i.short_code}`),
      siblings.map(i => Number(i.clicks || 0))
    )
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.error || '获取统计失败')
  } finally { loading.value = false }
}

function buildSeriesOption(type, title, x, y, opts = {}) {
  return {
    backgroundColor: 'transparent',
    title: { text: title, left: 'center' },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        if (!params || !params.length) return ''
        const p0 = params[0]
        const label = opts.tooltipLabelFormatter
          ? opts.tooltipLabelFormatter(p0?.axisValue)
          : String(p0?.axisValue || '')
        const lines = [label]
        for (const p of params) {
          lines.push(`${p.marker || ''}${p.seriesName || ''}：${p.data}`)
        }
        return lines.join('<br/>')
      },
    },
    grid: { left: 40, right: 20, top: 50, bottom: 40 },
    xAxis: {
      type: 'category',
      data: x,
      boundaryGap: type === 'bar',
      axisLabel: opts.xTickFormatter ? { formatter: opts.xTickFormatter } : undefined,
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      name: '点击量',
      type,
      data: y,
      smooth: type === 'line',
      areaStyle: (type === 'line') ? {} : undefined,
      lineStyle: { width: 2 },
      itemStyle: { color: '#409eff' }
    }]
  }
}

function buildBarOption(title, labels, values) {
  const maxVal = values && values.length ? Math.max(...values) : 0
  return {
    backgroundColor: 'transparent',
    title: { text: title, left: 'center' },
    tooltip: { trigger: 'axis' },
    grid: { left: 120, right: 20, top: 50, bottom: 40 },
    xAxis: {
      type: 'value',
      min: 0,
      max: maxVal < 1 ? 1 : undefined,
      minInterval: 1,
    },
    yAxis: { type: 'category', data: labels },
    series: [{
      type: 'bar',
      data: values,
      barMaxWidth: 40,
      itemStyle: {
        borderRadius: [4, 4, 4, 4],
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 1,
          y2: 0,
          colorStops: [
            { offset: 0, color: '#67c23a' },
            { offset: 1, color: '#a0e75a' },
          ],
        },
      },
      label: { show: true, position: 'right', formatter: '{c}' },
    }],
  }
}

function downloadBlob(filename, mime, content) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function toCSV(headers, rows) {
  const esc = (v) => {
    if (v == null) return ''
    const s = String(v)
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
  }
  const lines = []
  lines.push(headers.map(esc).join(','))
  rows.forEach(r => lines.push(r.map(esc).join(',')))
  return lines.join('\n')
}

function exportCSV() {
  if (!selectedOriginal.value) return ElMessage.warning('请先选择原始链接')
  const orig = encodeURIComponent(selectedOriginal.value)
  const rng = range.value

  const csvS = toCSV(
    ['original_url', 'title', 'short_code', 'clicks'],
    siblingsData.value.map(i => [selectedOriginal.value, i.title, i.short_code, i.clicks])
  )
  downloadBlob(`analytics_${orig}_${rng}_siblings_all.csv`, 'text/csv;charset=utf-8', csvS)
}

function exportExcel() {
  if (!selectedOriginal.value) return ElMessage.warning('请先选择原始链接')
  if (!siblingsHourlyData.value?.length && !siblingsDailyData.value?.length) {
    return ElMessage.warning('请先选择一个短码并点击“刷新”加载统计数据')
  }

  const orig = selectedOriginal.value
  const rng = range.value

  const dateMap = new Map()
  for (const r of siblingsHourlyData.value || []) {
    if (!r.date) continue
    if (!dateMap.has(r.date)) dateMap.set(r.date, { byCode: new Map(), titleByCode: new Map() })
    const bucket = dateMap.get(r.date)

    if (!bucket.byCode.has(r.short_code)) bucket.byCode.set(r.short_code, new Array(24).fill(0))
    if (!bucket.titleByCode.has(r.short_code)) bucket.titleByCode.set(r.short_code, r.title || r.short_code)

    const h = Number(r.hour)
    if (Number.isFinite(h) && h >= 0 && h <= 23) {
      bucket.byCode.get(r.short_code)[h] = Number(r.clicks || 0)
    }
  }

  const dailyClicks = new Map()
  for (const r of siblingsDailyData.value || []) {
    if (!r.date || !r.short_code) continue
    dailyClicks.set(`${r.date}|${r.short_code}`, Number(r.clicks || 0))
    if (!dateMap.has(r.date)) dateMap.set(r.date, { byCode: new Map(), titleByCode: new Map() })
    const bucket = dateMap.get(r.date)
    if (!bucket.byCode.has(r.short_code)) bucket.byCode.set(r.short_code, new Array(24).fill(0))
    if (!bucket.titleByCode.has(r.short_code)) bucket.titleByCode.set(r.short_code, r.title || r.short_code)
  }

  const wb = XLSX.utils.book_new()
  const dates = Array.from(dateMap.keys()).sort()

  // 强制列顺序：标题、短码、点击量、0..23
  const hourHeaders = Array.from({ length: 24 }, (_, i) => String(i))
  const header = ['标题', '短码', '点击量', ...hourHeaders]

  for (const date of dates) {
    const bucket = dateMap.get(date)
    const rows = []

    for (const [shortCode, hoursArr] of bucket.byCode.entries()) {
      const title = bucket.titleByCode.get(shortCode) || shortCode

      const row = {
        标题: title,
        短码: shortCode,
        点击量: dailyClicks.get(`${date}|${shortCode}`) ?? hoursArr.reduce((a, b) => a + b, 0),
      }
      for (let h = 0; h < 24; h++) {
        row[String(h)] = hoursArr[h]
      }
      rows.push(row)
    }

    rows.sort((a, b) => (Number(b['点击量'] || 0) - Number(a['点击量'] || 0)))

    const sheet = XLSX.utils.json_to_sheet(rows, { header })
    XLSX.utils.book_append_sheet(wb, sheet, date)
  }

  XLSX.writeFile(wb, `analytics_${orig}_${rng}.xlsx`)
}

watch(selectedOriginal, () => {
  selectedCode.value = ''
})

watch([chartType, range], () => {
  if (selectedCode.value) refresh()
})

onMounted(async () => {
  try {
    loadingMain.value = true
    const res = await getCodeOptions('')
    allOptions.value = res.data.options || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载短码列表失败')
  } finally {
    loadingMain.value = false
  }
})
</script>

<template>
  <div class="page" v-loading="loading">
    <el-card class="glass" shadow="hover" style="margin-bottom:12px">
      <template #header>
        <div class="head">
          <span>数据分析</span>
          <div class="tools">
            <div class="row2">
              <el-select
                v-model="selectedOriginal"
                filterable
                clearable
                placeholder="请选择或搜索原始链接"
                :loading="loadingMain"
                style="min-width:260px"
              >
                <el-option v-for="o in originalOptions" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </div>

            <div class="row2">
              <el-select
                v-model="selectedCode"
                :disabled="!selectedOriginal"
                placeholder="请选择该原始链接下的短码（标题 · 短码）"
                style="min-width:260px"
              >
                <el-option v-for="o in codeOptionsForSelectedOriginal" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>

              <el-select v-model="range" style="width:140px">
                <el-option label="近24小时" value="24h" />
                <el-option label="近7天" value="7d" />
                <el-option label="近30天" value="30d" />
                <el-option label="自定义" value="custom" />
              </el-select>
              <template v-if="range==='custom'">
                <el-date-picker v-model="custom.start" type="datetime" placeholder="开始时间" style="width:180px" />
                <el-date-picker v-model="custom.end" type="datetime" placeholder="结束时间" style="width:180px" />
              </template>

              <el-select v-model="chartType" style="width:120px">
                <el-option label="折线" value="line" />
                <el-option label="柱状" value="bar" />
              </el-select>

              <el-button type="primary" @click="refresh" :disabled="!selectedCode">刷新</el-button>
              <el-button @click="exportCSV" :disabled="!selectedOriginal">导出CSV</el-button>
              <el-button @click="exportExcel" :disabled="!selectedOriginal">导出Excel</el-button>
            </div>
          </div>
        </div>
      </template>

      <div v-if="!selectedCode" class="empty">请选择原始链接和其下的短码以查看趋势</div>
      <div v-else>
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-card shadow="hover" class="glass">
              <VChart :option="hourlyOpt" autoresize style="height:360px" />
              <div v-if="!(hourlyOpt?.series?.[0]?.data?.length)" class="empty">暂无分时数据</div>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card shadow="hover" class="glass">
              <VChart :option="dailyOpt" autoresize style="height:360px" />
              <div v-if="!(dailyOpt?.series?.[0]?.data?.length)" class="empty">暂无按天数据</div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="margin-top:12px">
          <el-col :xs="24" :md="24">
            <el-card shadow="hover" class="glass">
              <VChart :option="siblingsOpt" autoresize style="height:380px" />
              <div v-if="!(siblingsOpt?.series?.[0]?.data?.length)" class="empty">暂无同原链接不同短链排行数据</div>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.page { padding: 12px; }
.glass { backdrop-filter: blur(6px); }
.head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.head > span { white-space: nowrap; }
.tools { display:flex; flex-direction:column; gap:6px; width:100%; }
.row2 { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.empty { text-align:center; color: var(--el-text-color-secondary); padding: 12px 0; }
</style>
