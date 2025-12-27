import { createRouter, createWebHistory } from 'vue-router'

const Home = () => import('../views/Home.vue')
const Analytics = () => import('../views/Analytics.vue')

const routes = [
  { path: '/', name: 'home', component: Home, meta: { title: '短链管理' } },
  { path: '/analytics', name: 'analytics', component: Analytics, meta: { title: '数据分析' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() { return { top: 0 } },
})

router.afterEach((to) => {
  if (to.meta?.title) document.title = `${to.meta.title} · ShortURL`
})

export default router

