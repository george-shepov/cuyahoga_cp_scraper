<script setup lang="ts">
defineProps<{
  meter: {
    meter_key: string;
    included: number;
    used: number;
    overage: number;
  };
}>();
</script>

<template>
  <article class="rounded-xl border p-4 shadow-sm">
    <h3 class="text-lg font-semibold">{{ meter.meter_key }}</h3>
    <dl class="mt-3 space-y-1 text-sm">
      <div class="flex items-center justify-between">
        <dt class="text-gray-500">Included</dt>
        <dd class="font-medium">{{ meter.included }}</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-gray-500">Used</dt>
        <dd class="font-medium">{{ meter.used }}</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-gray-500">Overage</dt>
        <dd :class="meter.overage > 0 ? 'font-semibold text-red-600' : 'font-medium'">{{ meter.overage }}</dd>
      </div>
    </dl>
  </article>
</template>
