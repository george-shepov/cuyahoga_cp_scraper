<script setup lang="ts">
defineProps<{
  title: string;
  body: string;
}>();
</script>

<template>
  <section class="rounded-2xl border p-6 shadow-sm">
    <h1 class="text-3xl font-bold">{{ title }}</h1>
    <p class="mt-3 text-base leading-7">{{ body }}</p>
  </section>
</template>
