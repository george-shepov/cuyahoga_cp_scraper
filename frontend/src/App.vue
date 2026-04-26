<script setup lang="ts">
import AppNav from "@/components/AppNav.vue";
</script>

<template>
  <div class="min-h-screen bg-stone-50 font-sans text-stone-900">
    <AppNav />
    <RouterView />
    <footer class="mt-16 border-t border-stone-200 py-8 text-center text-sm text-stone-500">
      <p>
        &copy; {{ new Date().getFullYear() }}
        <a href="/brocklerlaw" class="font-medium hover:text-stone-800">Aaron Brockler</a>
        &mdash; Cleveland OVI &amp; Criminal Defense
      </p>
      <p class="mt-1">
        This site is for informational purposes only and does not constitute legal advice.
      </p>
    </footer>
  </div>
</template>
