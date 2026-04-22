import type { RouteRecordRaw } from "vue-router";

export const billingRoutes: RouteRecordRaw[] = [
  {
    path: "/billing",
    component: () => import("@/pages/BillingPage.vue"),
  },
];
