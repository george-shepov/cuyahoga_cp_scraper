<script setup lang="ts">
defineProps<{
  items: Array<{ question: string; answer: string }>;
}>();
</script>

<template>
  <section class="space-y-3">
    <details v-for="item in items" :key="item.question" class="rounded-xl border p-4">
      <summary class="cursor-pointer font-semibold">{{ item.question }}</summary>
      <p class="mt-3 leading-7">{{ item.answer }}</p>
    </details>
  </section>
</template>
