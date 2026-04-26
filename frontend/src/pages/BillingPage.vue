<script setup lang="ts">
import { onMounted, ref } from "vue";
import { getBillingSummary } from "@/services/api";
import UsageMeterCard from "@/components/UsageMeterCard.vue";

const loading = ref(false);
const summary = ref<any>(null);
const accountId = ref("demo-account");

async function loadSummary() {
  loading.value = true;
  try {
    summary.value = await getBillingSummary(accountId.value);
  } finally {
    loading.value = false;
  }
}

onMounted(loadSummary);
</script>

<template>
  <main class="mx-auto max-w-5xl space-y-8 p-6">
    <section class="rounded-2xl border p-6 shadow-sm">
      <h1 class="text-3xl font-bold">Billing and Metering</h1>
      <p class="mt-2 leading-7">Usage from the ledger is summarized by meter and compared against plan limits.</p>

      <div class="mt-4 flex flex-wrap items-end gap-3">
        <label class="space-y-2">
          <span class="text-sm font-medium">Account ID</span>
          <input v-model="accountId" class="w-72 rounded-xl border px-3 py-2" />
        </label>
        <button @click="loadSummary" class="rounded-xl border px-4 py-2 font-medium" :disabled="loading">
          {{ loading ? 'Loading...' : 'Refresh Summary' }}
        </button>
      </div>
    </section>

    <section v-if="summary" class="rounded-2xl border p-6 shadow-sm">
      <h2 class="text-2xl font-semibold">Account Summary</h2>
      <p class="mt-2 text-sm text-gray-600">Plan: {{ summary.plan_code }} | Projected overage units: {{ summary.projected_overage_units }}</p>
      <div class="mt-4 grid gap-4 md:grid-cols-2">
        <UsageMeterCard v-for="meter in summary.meters" :key="meter.meter_key" :meter="meter" />
      </div>
      <ul class="mt-4 list-disc space-y-1 pl-6 text-sm text-gray-600">
        <li v-for="note in summary.notes" :key="note">{{ note }}</li>
      </ul>
    </section>
  </main>
</template>
