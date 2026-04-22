<script setup lang="ts">
import { routeTitles } from "@/data/routeTitles";

defineProps<{
  routes: string[];
}>();
</script>

<template>
  <section class="rounded-2xl border p-5 shadow-sm">
    <h2 class="text-xl font-semibold">Recommended Reading</h2>
    <ul class="mt-4 space-y-2">
      <li v-for="route in routes" :key="route">
        <a :href="route" class="underline">
          {{ routeTitles[route] || route }}
        </a>
      </li>
    </ul>
  </section>
</template>
