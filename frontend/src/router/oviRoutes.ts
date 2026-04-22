import type { RouteRecordRaw } from "vue-router";

export const oviRoutes: RouteRecordRaw[] = [
  {
    path: "/billing",
    component: () => import("@/pages/BillingPage.vue"),
  },
  {
    path: "/check-my-case",
    component: () => import("@/pages/CaseCheckPage.vue"),
  },
  {
    path: "/:slug",
    component: () => import("@/pages/SeoArticlePage.vue"),
  },
];
