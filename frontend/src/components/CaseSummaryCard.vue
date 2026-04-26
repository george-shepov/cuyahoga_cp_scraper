<script setup lang="ts">
defineProps<{
  summary: {
    primary_case_type: string;
    confidence: number;
    urgency: string;
    timeline_stage: string;
  };
}>();
</script>

<template>
  <section class="rounded-2xl border p-5 shadow-sm">
    <h2 class="text-xl font-semibold">Case Snapshot</h2>
    <dl class="mt-4 grid gap-3 sm:grid-cols-2">
      <div>
        <dt class="text-sm text-gray-500">Likely category</dt>
        <dd class="font-medium">{{ summary.primary_case_type }}</dd>
      </div>
      <div>
        <dt class="text-sm text-gray-500">Urgency</dt>
        <dd class="font-medium">{{ summary.urgency }}</dd>
      </div>
      <div>
        <dt class="text-sm text-gray-500">Timeline stage</dt>
        <dd class="font-medium">{{ summary.timeline_stage }}</dd>
      </div>
      <div>
        <dt class="text-sm text-gray-500">Confidence</dt>
        <dd class="font-medium">{{ Math.round(summary.confidence * 100) }}%</dd>
      </div>
    </dl>
  </section>
</template>
