import type { RouteRecordRaw } from "vue-router";

export const oviRoutes: RouteRecordRaw[] = [
  // ── public ────────────────────────────────────────────────────────────────
  {
    path: "/login",
    component: () => import("@/pages/LoginPage.vue"),
    meta: { public: true },
  },
  {
    path: "/brocklerlaw",
    component: () => import("@/pages/BrocklerLawPage.vue"),
    meta: { public: true },
  },
  {
    path: "/check-my-case",
    component: () => import("@/pages/CaseCheckPage.vue"),
    meta: { public: true },
  },
  // ── admin (require JWT) ────────────────────────────────────────────────────
  {
    path: "/billing",
    component: () => import("@/pages/BillingPage.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/case-intelligence",
    component: () => import("@/pages/CaseIntelligencePage.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/content-strategy",
    component: () => import("@/pages/ContentStrategyPage.vue"),
    meta: { requiresAuth: true },
  },
  // ── public SEO slug (catch-all) ────────────────────────────────────────────
  {
    path: "/:slug",
    component: () => import("@/pages/SeoArticlePage.vue"),
  },
];
