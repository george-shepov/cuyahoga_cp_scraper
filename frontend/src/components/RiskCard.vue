<script setup lang="ts">
defineProps<{
  risk: {
    type: string;
    severity: string;
    title: string;
    detail: string;
  };
}>();
</script>

<template>
  <article class="rounded-xl border p-4 shadow-sm">
    <div class="text-sm font-medium uppercase tracking-wide">{{ risk.severity }}</div>
    <h3 class="mt-1 text-lg font-semibold">{{ risk.title }}</h3>
    <p class="mt-2 leading-7">{{ risk.detail }}</p>
  </article>
</template>
