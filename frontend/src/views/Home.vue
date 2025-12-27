<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listLinks, createLink, deleteLink, verifyPassword, createBatchLinks, me } from '../api'
import { Lock } from '@element-plus/icons-vue'

// 表单
const formRef = ref()
const form = ref({
  original_url: '',
  title: '',
  short_code: '',
  password: '',
  expires_at: ''
})
const rules = {
  original_url: [
    { required: true, message: '请输入原始链接', trigger: 'blur' },
    { validator: (_, v, cb) => {
        try { const u = new URL(v); (u.protocol === 'http:'||u.protocol==='https:') ? cb() : cb(new Error('必须以 http/https 开头')) }
        catch { cb(new Error('请输入合法链接')) }
      }, trigger: 'blur' }
  ],
}

// 列表与分页
const loading = ref(false)
const rows = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

async function fetchData(p=1){
  loading.value = true
  try{
    const res = await listLinks(p)
    rows.value = res.data.results || []
    total.value = res.data.count || (rows.value?.length || 0)
    page.value = p
  }catch(e){
    console.error(e)
    ElMessage.error('获取列表失败')
  }finally{ loading.value=false }
}

async function onSubmit(){
  await formRef.value?.validate()
  try{
    await createLink({
      original_url: form.value.original_url,
      title: form.value.title || undefined,
      short_code: form.value.short_code || undefined,
      password: form.value.password || undefined,
      expires_at: form.value.expires_at || undefined,
    })
    ElMessage.success('创建成功')
    form.value = { original_url:'', title:'', short_code:'', password:'', expires_at:'' }
    fetchData(1)
  }catch(e){
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  }
}

async function onDelete(row){
  try{
    await ElMessageBox.confirm(`确定删除短链 ${row.short_code} ?`, '确认', { type:'warning' })
    await deleteLink(row.short_code)
    ElMessage.success('删除成功')
    fetchData(page.value)
  }catch(e){
    if(e !== 'cancel'){
      console.error(e)
      ElMessage.error('删除失败')
    }
  }
}

// 分组：按原始地址分组，名称（标题）区分不同平台
const grouped = computed(()=>{
  const map = new Map()
  for (const r of rows.value){
    const key = r.original_url
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(r)
  }
  // 排序：组内按创建时间倒序
  const list = []
  for (const [original_url, items] of map.entries()){
    items.sort((a,b)=> String(b.created_at).localeCompare(String(a.created_at)))
    list.push({ original_url, items })
  }
  // 组排序：总点击降序
  list.sort((a,b)=> (sumClicks(b.items) - sumClicks(a.items)))
  return list
})

function sumClicks(items){
  return items.reduce((acc,x)=> acc + (x.click_count||0), 0)
}

// 展开/收起控制
const activePanels = ref([]) // 保存展开的 original_url 列表

// 密码访问对话框
const pwdDialog = ref(false)
const pwdCode = ref('')
const pwdInput = ref('')

async function openShort(row){
  if(row.has_password){
    pwdCode.value = row.short_code
    pwdInput.value = ''
    pwdDialog.value = true
    return
  }
  window.open(row.short_url, '_blank')
}

async function confirmPwd(){
  try{
    const res = await verifyPassword(pwdCode.value, pwdInput.value)
    const url = res?.data?.original_url
    if(url){
      ElMessage.success('验证通过，正在跳转')
      pwdDialog.value = false
      window.open(url, '_blank')
      fetchData(page.value)
    }else{
      ElMessage.error('验证失败')
    }
  }catch(e){
    ElMessage.error(e?.response?.data?.error || '密码错误')
  }
}

function copyLink(text){
  if(!text){ ElMessage.warning('无效链接'); return }
  // 优先使用异步剪贴板API
  if (navigator.clipboard && window.isSecureContext !== false) {
    navigator.clipboard.writeText(text)
      .then(()=> ElMessage.success('已复制到剪贴板'))
      .catch(()=> fallbackCopy(text))
  } else {
    fallbackCopy(text)
  }
}
function fallbackCopy(text){
  try{
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    ok ? ElMessage.success('已复制到剪贴板') : ElMessage.warning('复制失败，请手动复制')
  }catch{
    ElMessage.warning('复制失败，请手动复制')
  }
}

// 批量创建对话框
const batchDialog = ref(false)
const batchRef = ref()
const batch = ref({
  original_url: '',
  titles_text: '', // 多个平台名称，每行一个
  password: '',
  expires_at: ''
})
const batchRules = {
  original_url: [
    { required: true, message: '请输入原始链接', trigger: 'blur' },
    { validator: (_, v, cb) => {
        try { const u = new URL(v); (u.protocol === 'http:'||u.protocol==='https:') ? cb() : cb(new Error('必须以 http/https 开头')) }
        catch { cb(new Error('请输入合法链接')) }
      }, trigger: 'blur' }
  ],
  titles_text: [ { required: true, message: '请输入平台名称（每行一个）', trigger: 'blur' } ]
}

async function onBatchSubmit(){
  await batchRef.value?.validate()
  const titles = (batch.value.titles_text || '')
    .split(/\r?\n/)
    .map(s => s.trim())
    .filter(Boolean)
  if (!titles.length){ ElMessage.warning('请至少填写一个平台名称'); return }
  try{
    const payload = {
      original_url: batch.value.original_url,
      titles,
      password: batch.value.password || undefined,
      expires_at: batch.value.expires_at || undefined,
    }
    const res = await createBatchLinks(payload)
    const cnt = res?.data?.count || titles.length
    ElMessage.success(`批量创建成功，共 ${cnt} 条`)
    batchDialog.value = false
    // 重置
    batch.value = { original_url:'', titles_text:'', password:'', expires_at:'' }
    fetchData(1)
  }catch(e){
    console.error(e)
    ElMessage.error(e?.response?.data?.error || '批量创建失败')
  }
}

onMounted(()=>fetchData(1))
</script>

<template>
  <div class="page" v-motion :initial="{opacity:0, y:10}" :enter="{opacity:1, y:0, transition:{duration:400}}">
    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="glass">
          <template #header>
            <div class="card-header">
              <span>创建短链接</span>
            </div>
          </template>
          <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
            <el-form-item label="原始地址" prop="original_url">
              <el-input v-model="form.original_url" placeholder="https://example.com/very/long/url" clearable />
            </el-form-item>
            <el-form-item label="名称/标题（用来区分平台）">
              <el-input v-model="form.title" placeholder="如 Weibo / WeChat / Douyin" clearable />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="自定义码（可选）">
                  <el-input v-model="form.short_code" placeholder="如 weibo-2025" clearable />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="访问密码（可选）">
                  <el-input v-model="form.password" type="password" placeholder="设置访问密码" show-password />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="过期时间（可选，ISO8601）">
              <el-input v-model="form.expires_at" placeholder="2025-12-31T23:59:59" clearable />
            </el-form-item>
            <el-button type="primary" @click="onSubmit">创建</el-button>
            <el-button type="success" plain @click="batchDialog=true" style="margin-left:8px">批量创建</el-button>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="glass">
          <template #header>
            <div class="card-header">
              <span>概览</span>
            </div>
          </template>
          <el-space wrap>
            <el-statistic title="总链接" :value="total" />
            <el-statistic title="本页" :value="rows.length" />
          </el-space>
          <div class="hint">用“标题”区分不同平台；同一原始地址的短链会自动分组</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" class="list-card" v-motion :initial="{opacity:0}" :enter="{opacity:1, transition:{delay:200}}">
      <template #header>
        <div class="card-header">
          <span>短链接列表（按原始地址分组）</span>
        </div>
      </template>

      <!-- 分组展开/收起：原始地址在前，子表格显示各平台（标题）对应短链 -->
      <el-collapse v-model="activePanels" accordion>
        <el-collapse-item v-for="g in grouped" :key="g.original_url" :name="g.original_url">
          <template #title>
            <div class="group-title">
              <span class="origin-url" :title="g.original_url">{{ g.original_url }}</span>
              <el-tag type="success" effect="plain" size="small" style="margin-left:8px">合计点击 {{ sumClicks(g.items) }}</el-tag>
              <el-tag type="info" effect="plain" size="small" style="margin-left:6px">短链数 {{ g.items.length }}</el-tag>
            </div>
          </template>

          <el-table :data="g.items" size="small" class="glass-table" stripe>
            <el-table-column prop="title" label="名称/平台" min-width="160">
              <template #default="{row}">
                {{ row.title || '(未命名)' }}
              </template>
            </el-table-column>
            <el-table-column prop="short_code" label="短码" width="160">
              <template #default="{row}">
                <el-tag type="info">{{ row.short_code }}</el-tag>
                <el-icon v-if="row.has_password" title="受密码保护" style="margin-left:6px;color:#f59e0b">
                  <Lock />
                </el-icon>
              </template>
            </el-table-column>
            <el-table-column label="短链" min-width="200">
              <template #default="{row}">
                <el-link type="primary" @click="openShort(row)">打开</el-link>
                <el-divider direction="vertical" />
                <el-link type="success" @click="copyLink(row.short_url)">复制</el-link>
              </template>
            </el-table-column>
            <el-table-column prop="click_count" label="点击" width="100" />
            <el-table-column prop="created_at" label="创建时间" width="180" />
            <el-table-column label="操作" width="120">
              <template #default="{row}">
                <el-button size="small" type="danger" @click="onDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>
      </el-collapse>

      <div class="pager">
        <el-pagination background layout="prev, pager, next" :page-size="pageSize" :total="total" :current-page="page" @current-change="fetchData" />
      </div>
    </el-card>

    <el-dialog v-model="pwdDialog" title="密码验证" width="360px" append-to-body :lock-scroll="true" :close-on-click-modal="false" :align-center="true">
      <el-input v-model="pwdInput" type="password" placeholder="请输入访问密码" show-password @keyup.enter.native="confirmPwd" />
      <template #footer>
        <el-button @click="pwdDialog=false">取消</el-button>
        <el-button type="primary" @click="confirmPwd">确定</el-button>
      </template>
    </el-dialog>

    <!-- 批量创建对话框 -->
    <el-dialog v-model="batchDialog" title="批量创建多平台短链" width="520px" append-to-body :lock-scroll="true" :close-on-click-modal="false" :align-center="true">
      <el-form ref="batchRef" :model="batch" :rules="batchRules" label-position="top">
        <el-form-item label="原始地址" prop="original_url">
          <el-input v-model="batch.original_url" placeholder="https://example.com/landing" clearable />
        </el-form-item>
        <el-form-item label="平台名称（每行一个）" prop="titles_text">
          <el-input v-model="batch.titles_text" type="textarea" :rows="6" placeholder="示例：\nWeibo\nWeChat\nDouyin" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="访问密码（可选）">
              <el-input v-model="batch.password" type="password" placeholder="为所有平台统一设置" show-password />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="过期时间（可选，ISO8601）">
              <el-input v-model="batch.expires_at" placeholder="2025-12-31T23:59:59" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="batchDialog=false">取消</el-button>
        <el-button type="primary" @click="onBatchSubmit">批量创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page { padding: 12px; }
.card-header { display:flex; align-items:center; justify-content:space-between; font-weight:600; }
.glass { backdrop-filter: blur(6px); background: var(--el-fill-color-blank); }
.glass-table { border-radius: 8px; overflow: hidden; }
.hint { margin-top: 12px; color: var(--el-text-color-secondary); }
.list-card { margin-top: 16px; }
.pager { display:flex; justify-content:center; padding: 12px 0; }
.group-title { display:flex; align-items:center; gap:6px; }
.origin-url { max-width: 60vw; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
</style>
