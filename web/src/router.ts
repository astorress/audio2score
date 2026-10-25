import { createRouter, createWebHistory } from 'vue-router'
import UploadView from './views/UploadView.vue'

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'upload',
      component: UploadView,
      meta: { title: 'Subir audio' },
    },
    {
      path: '/jobs/:jobId',
      name: 'job',
      component: () => import('./views/JobView.vue'),
      props: true,
      meta: { title: 'Resultado' },
    },
    {
      path: '/como-funciona',
      name: 'how',
      component: () => import('./views/HowItWorksView.vue'),
      meta: { title: 'Cómo funciona' },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('./views/NotFoundView.vue'),
      meta: { title: 'Página no encontrada' },
    },
  ],
  scrollBehavior(to, _from, saved) {
    if (saved) return saved
    if (to.hash) return { el: to.hash, top: 90 }
    return { top: 0 }
  },
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${title} · audio2score` : 'audio2score'
})
