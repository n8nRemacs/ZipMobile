import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LandingView from '../views/LandingView.vue'
import DashboardView from '../views/DashboardView.vue'
import ProfileView from '../views/ProfileView.vue'
import VerifyPhoneView from '../views/VerifyPhoneView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: LandingView, meta: { guest: true } },
    { path: '/dashboard', name: 'dashboard', component: DashboardView, meta: { auth: true } },
    { path: '/profile', name: 'profile', component: ProfileView, meta: { auth: true } },
    { path: '/verify-phone', name: 'verify-phone', component: VerifyPhoneView, meta: { auth: true } },
  ],
})

router.beforeEach((to) => {
  const authStore = useAuthStore()

  if (to.meta.auth && !authStore.isAuthenticated) {
    return { name: 'landing' }
  }

  if (to.meta.guest && authStore.isAuthenticated) {
    if (!authStore.phoneVerified) {
      return { name: 'verify-phone' }
    }
    return { name: 'dashboard' }
  }

  // Redirect to verify-phone if authenticated but not verified (except on verify-phone itself)
  if (to.meta.auth && to.name !== 'verify-phone' && authStore.isAuthenticated && !authStore.phoneVerified) {
    return { name: 'verify-phone' }
  }
})

export default router
