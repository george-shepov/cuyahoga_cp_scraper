<script setup lang="ts">
defineProps<{
  result: {
    totals: Record<string, number>;
    killer_events: Array<{ title: string; severity: string; detail: string }>;
    events: Array<{ code: string; title: string; tier: string; severity: string; detail: string }>;
  };
}>();
</script>

<template>
  <section class="rounded-2xl border p-6 shadow-sm">
    <h2 class="text-2xl font-semibold">Change Alerts</h2>
    <div class="mt-3 text-sm text-gray-600">
      Total: {{ result.totals.all }} | Killer: {{ result.totals.killer }} | Critical: {{ result.totals.critical }}
    </div>

    <div v-if="result.killer_events?.length" class="mt-4 space-y-3">
      <h3 class="font-semibold">Killer Alerts</h3>
      <article v-for="(event, idx) in result.killer_events" :key="`killer-${idx}`" class="rounded-xl border border-red-300 bg-red-50 p-4">
        <div class="text-xs uppercase tracking-wide text-red-700">{{ event.severity }}</div>
        <div class="mt-1 font-semibold">{{ event.title }}</div>
        <p class="mt-1 text-sm leading-6">{{ event.detail }}</p>
      </article>
    </div>

    <div class="mt-5 space-y-2">
      <h3 class="font-semibold">All Detected Events</h3>
      <article v-for="event in result.events" :key="`${event.code}-${event.detail}`" class="rounded-xl border p-3">
        <div class="text-xs uppercase tracking-wide text-gray-500">{{ event.tier }} | {{ event.severity }}</div>
        <div class="font-medium">{{ event.title }}</div>
        <p class="mt-1 text-sm leading-6">{{ event.detail }}</p>
      </article>
    </div>
  </section>
</template>
