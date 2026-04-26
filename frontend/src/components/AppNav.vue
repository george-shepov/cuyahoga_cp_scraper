<script setup lang="ts">
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { isAuthenticated, clearToken } from "@/services/auth";

const router = useRouter();
const menuOpen = ref(false);

const authed = computed(() => isAuthenticated());

const navLinks = [
  { label: "OVI Info", href: "/ovi-lawyer-cleveland" },
  { label: "Case Intelligence", href: "/case-intelligence" },
  { label: "Check My Case", href: "/check-my-case" },
  { label: "Content Strategy", href: "/content-strategy" },
  { label: "FAQ", href: "/ohio-ovi-faq" },
  { label: "Billing", href: "/billing" },
];

function closeMenu() {
  menuOpen.value = false;
}

function logout() {
  clearToken();
  router.push("/login");
}
</script>

<template>
  <header class="sticky top-0 z-50 border-b border-stone-200 bg-white/90 backdrop-blur-sm">
    <div class="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
      <!-- Brand -->
      <a href="/brocklerlaw" class="flex items-center gap-2 font-serif text-lg font-bold text-steel hover:opacity-80">
        <span class="inline-block h-8 w-8 rounded-full bg-steel text-white text-xs font-bold leading-8 text-center flex-shrink-0">AB</span>
        <span>Brockler<span class="text-accent">Law</span></span>
      </a>

      <!-- Desktop nav -->
      <nav class="hidden items-center gap-1 md:flex">
        <a
          v-for="link in navLinks"
          :key="link.href"
          :href="link.href"
          class="rounded-lg px-3 py-1.5 text-sm font-medium text-stone-600 transition-colors hover:bg-stone-100 hover:text-stone-900"
        >
          {{ link.label }}
        </a>
        <a
          href="tel:2163706700"
          class="ml-2 rounded-xl bg-steel px-4 py-1.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
        >
          (216) 370-6700
        </a>
        <button
          v-if="authed"
          @click="logout"
          class="ml-1 rounded-xl border border-stone-200 px-3 py-1.5 text-sm font-medium
                 text-stone-500 transition-colors hover:bg-stone-100 hover:text-red-600"
          title="Log out of admin"
        >
          Log out
        </button>
      </nav>

      <!-- Mobile hamburger -->
      <button
        class="rounded-lg p-2 text-stone-600 hover:bg-stone-100 md:hidden"
        @click="menuOpen = !menuOpen"
        aria-label="Toggle menu"
      >
        <svg v-if="!menuOpen" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
        <svg v-else class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Mobile menu -->
    <nav v-if="menuOpen" class="border-t border-stone-100 bg-white px-4 pb-4 md:hidden">
      <a
        v-for="link in navLinks"
        :key="link.href"
        :href="link.href"
        class="block rounded-lg px-3 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-50"
        @click="closeMenu"
      >
        {{ link.label }}
      </a>
      <a
        href="tel:2163706700"
        class="mt-2 block rounded-xl bg-steel px-4 py-2 text-center text-sm font-semibold text-white"
        @click="closeMenu"
      >
        Call (216) 370-6700
      </a>
    </nav>
  </header>
</template>
