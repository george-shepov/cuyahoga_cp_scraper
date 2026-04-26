import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import { oviRoutes } from "./router/oviRoutes";
import { isAuthenticated } from "./services/auth";
import App from "./App.vue";
import "./assets/main.css";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/ovi-lawyer-cleveland" },
    ...oviRoutes,
  ],
  scrollBehavior: () => ({ top: 0 }),
});

// Navigation guard — redirect unauthenticated users to /login
router.beforeEach((to, _from, next) => {
  if (to.meta.requiresAuth && !isAuthenticated()) {
    next({ path: "/login", query: { redirect: to.fullPath } });
  } else if (to.path === "/login" && isAuthenticated()) {
    // Already logged in — bounce to admin home
    next("/content-strategy");
  } else {
    next();
  }
});

createApp(App).use(router).mount("#app");
