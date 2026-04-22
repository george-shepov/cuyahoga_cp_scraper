<script setup lang="ts">
defineProps<{
  cta: {
    type: string;
    label: string;
    target: string;
  };
}>();
</script>

<template>
  <section class="rounded-2xl border p-5 shadow-sm">
    <h2 class="text-xl font-semibold">Talk to a Lawyer</h2>
    <p class="mt-2 leading-7">When the case is time-sensitive, a simple next step is better than waiting.</p>
    <a :href="cta.target" class="mt-4 inline-block rounded-xl border px-4 py-2 font-medium">
      {{ cta.label }}
    </a>
  </section>
</template>
