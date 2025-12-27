<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import * as echarts from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import * as XLSX from 'xlsx'

import { getAnalytics, getCodeOptions } from '../api'

echarts.use([LineChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent, CanvasRenderer])

// 短码远程搜索
const code = ref('')
const codeOptions = ref([])
const loadingCodes = ref(false)
const fetchCodes = async (q = '') => {
  loadingCodes.value = true
  try {
    const res = await getCodeOptions(q)
    codeOptions.value = res.data.options || []
  } catch (e) {
    console.error(e); ElMessage.error('加载短码失败')
  } finally { loadingCodes.value = false }
}

// 范围与图表控制
const range = ref('24h') // 24h | 7d | 30d | custom
const custom = ref({ start: '', end: '' }) // ISO
const chartType = ref('line') // line | bar

// 数据缓存（导出用）
const hourlyData = ref([])
const dailyData = ref([])
const siblingsData = ref([]) // 同一原链接下，不同短链排行

// 图表配置
const hourlyOpt = ref({})
const dailyOpt = ref({})
const siblingsOpt = ref({})
const loading = ref(false)

function toISO(dt) {
  if (!dt) return ''
  if (typeof dt === 'string') return dt
  try { return new Date(dt).toISOString() } catch { return '' }
}

async function refresh() {
  if (!code.value) { ElMessage.warning('请先选择短码'); return }
  const params = {}
  if (range.value === 'custom') {
    if (!custom.value.start || !custom.value.end) {
      ElMessage.warning('请选择自定义起止时间');
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
    const res = await getAnalytics(code.value, params)
    const hourly = res.data.hourly || []
    const daily = res.data.daily || []
    const siblings = res.data.siblings_top || []

    hourlyData.value = hourly
    dailyData.value = daily
    siblingsData.value = siblings

    hourlyOpt.value = buildSeriesOption(
      (chartType.value === 'line') ? 'line' : 'bar',
      '最近分时趋势',
      hourly.map(i => i.hour),
      hourly.map(i => Number(i.clicks || 0))
    )

    dailyOpt.value = buildSeriesOption(
      (chartType.value === 'line') ? 'line' : 'bar',
      '按天历史趋势',
      daily.map(i => i.date),
      daily.map(i => Number(i.clicks || 0))
    )

    siblingsOpt.value = buildBarOption(
      '同原链接不同短链（按标题）Top',
      siblings.map(i => i.title),
      siblings.map(i => Number(i.clicks || 0))
    )
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.error || '获取统计失败')
  } finally { loading.value = false }
}

function buildSeriesOption(type, title, x, y) {
  return {
    backgroundColor: 'transparent',
    title: { text: title, left: 'center' },
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 50, bottom: 40 },
    xAxis: { type: 'category', data: x, boundaryGap: type === 'bar' },
    yAxis: { type: 'value' },
    series: [{
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
  return {
    backgroundColor: 'transparent',
    title: { text: title, left: 'center' },
    tooltip: { trigger: 'axis' },
    grid: { left: 120, right: 20, top: 50, bottom: 40 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: labels },
    series: [{ type: 'bar', data: values, itemStyle: { color: '#67c23a' } }]
  }
}

// 导出 CSV / Excel
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
  if (!code.value) return ElMessage.warning('请选择短码')
  const id = code.value
  const rng = range.value
  const csvH = toCSV(['hour','clicks'], hourlyData.value.map(i => [i.hour, i.clicks]))
  downloadBlob(`analytics_${id}_${rng}_hourly.csv`, 'text/csv;charset=utf-8', csvH)
  const csvD = toCSV(['date','clicks'], dailyData.value.map(i => [i.date, i.clicks]))
  downloadBlob(`analytics_${id}_${rng}_daily.csv`, 'text/csv;charset=utf-8', csvD)
  const csvS = toCSV(['title','short_code','clicks'], siblingsData.value.map(i => [i.title, i.short_code, i.clicks]))
  downloadBlob(`analytics_${id}_${rng}_siblings.csv`, 'text/csv;charset=utf-8', csvS)
}

function exportExcel() {
  if (!code.value) return ElMessage.warning('请选择短码')
  const id = code.value
  const rng = range.value
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(hourlyData.value), 'Hourly')
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(dailyData.value), 'Daily')
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(siblingsData.value), 'SiblingsTop')
  XLSX.writeFile(wb, `analytics_${id}_${rng}.xlsx`)
}

onMounted(async () => {
  await fetchCodes('')
})

watch([chartType, range], () => refresh())
</script>

<template>
  <div class="page" v-loading="loading">
    <el-card class="glass" shadow="hover" style="margin-bottom:12px">
      <template #header>
        <div class="head">
          <span>数据分析</span>
          <div class="tools">
            <el-select v-model="code" filterable remote reserve-keyword placeholder="请输入短码/标题搜索"
                       :remote-method="fetchCodes" :loading="loadingCodes" style="min-width:320px">
              <el-option v-for="o in codeOptions" :key="o.value" :label="o.label" :value="o.value" />
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

            <el-button type="primary" @click="refresh">刷新</el-button>
            <el-button @click="exportCSV" :disabled="!code">导出CSV</el-button>
            <el-button @click="exportExcel" :disabled="!code">导出Excel</el-button>
          </div>
        </div>
      </template>

      <div v-if="!code" class="empty">请选择短码以查看趋势</div>
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
.tools { display:flex; align-items:center; gap:8px; flex-wrap: wrap; }
.empty { text-align:center; color: var(--el-text-color-secondary); padding: 12px 0; }
</style>
