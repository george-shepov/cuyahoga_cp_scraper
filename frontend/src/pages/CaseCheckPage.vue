<script setup lang="ts">
import { ref } from "vue";
import { analyzeCase, scanAlerts } from "@/services/api";
import CaseSummaryCard from "@/components/CaseSummaryCard.vue";
import RiskCard from "@/components/RiskCard.vue";
import RecommendedRoutes from "@/components/RecommendedRoutes.vue";
import LeadCaptureForm from "@/components/LeadCaptureForm.vue";
import AlertFeed from "@/components/AlertFeed.vue";

const form = ref({
  charges: [
    { code: "4511.19(A)(1)(a)", label: "OVI - impaired" },
  ],
  facts: {
    chemical_test: "unknown",
    prior_ovi_within_10y: 0,
    cdl: false,
  },
});

const result = ref<any>(null);
const loading = ref(false);
const alertResult = ref<any>(null);
const alertLoading = ref(false);
const alertForm = ref({
  previous_text: "ARRAIGNMENT HELD\nBOND SET",
  current_text: "ARRAIGNMENT HELD\nBOND SET\nMOTION TO SUPPRESS FILED\nATTORNEY APPEARANCE FILED",
});

async function submit() {
  loading.value = true;
  try {
    result.value = await analyzeCase(form.value);
  } finally {
    loading.value = false;
  }
}

async function scanCaseAlerts() {
  alertLoading.value = true;
  try {
    const previousEntries = alertForm.value.previous_text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((text, i) => ({ entry_id: `prev-${i + 1}`, text }));

    const currentEntries = alertForm.value.current_text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((text, i) => ({ entry_id: `cur-${i + 1}`, text }));

    alertResult.value = await scanAlerts({
      case_number: "Demo-Case",
      court: "Cuyahoga CP",
      previous_entries: previousEntries,
      current_entries: currentEntries,
    });
  } finally {
    alertLoading.value = false;
  }
}
</script>

<template>
  <main class="mx-auto max-w-5xl space-y-8 p-6">
    <section class="rounded-2xl border p-6 shadow-sm">
      <h1 class="text-3xl font-bold">Check My OVI Case</h1>
      <p class="mt-3 leading-7">
        Start with the charge, test status, and whether this is a first offense. The tool will return the best reading path and intake questions.
      </p>

      <div class="mt-6 grid gap-4 md:grid-cols-2">
        <label class="space-y-2">
          <span class="text-sm font-medium">Primary charge code</span>
          <input v-model="form.charges[0].code" class="w-full rounded-xl border px-3 py-2" />
        </label>

        <label class="space-y-2">
          <span class="text-sm font-medium">Primary charge label</span>
          <input v-model="form.charges[0].label" class="w-full rounded-xl border px-3 py-2" />
        </label>

        <label class="space-y-2">
          <span class="text-sm font-medium">Chemical test</span>
          <select v-model="form.facts.chemical_test" class="w-full rounded-xl border px-3 py-2">
            <option value="unknown">Unknown</option>
            <option value="refused">Refused</option>
            <option value="failed">Failed</option>
            <option value="pending">Pending</option>
          </select>
        </label>

        <label class="space-y-2">
          <span class="text-sm font-medium">Prior OVI within 10 years</span>
          <input v-model.number="form.facts.prior_ovi_within_10y" type="number" min="0" class="w-full rounded-xl border px-3 py-2" />
        </label>
      </div>

      <label class="mt-4 flex items-center gap-2">
        <input v-model="form.facts.cdl" type="checkbox" />
        <span>Commercial driver / CDL</span>
      </label>

      <button @click="submit" class="mt-6 rounded-xl border px-4 py-2 font-medium" :disabled="loading">
        {{ loading ? 'Analyzing...' : 'Analyze Case' }}
      </button>
    </section>

    <section class="rounded-2xl border p-6 shadow-sm">
      <h2 class="text-2xl font-semibold">Docket Diff Alert Scanner</h2>
      <p class="mt-2 leading-7">
        Paste prior and current docket lines to detect monetizable changes like counsel changes, capias, suppression motions, and anomalies.
      </p>

      <div class="mt-4 grid gap-4 md:grid-cols-2">
        <label class="space-y-2">
          <span class="text-sm font-medium">Previous snapshot (one line per entry)</span>
          <textarea v-model="alertForm.previous_text" rows="8" class="w-full rounded-xl border px-3 py-2" />
        </label>

        <label class="space-y-2">
          <span class="text-sm font-medium">Current snapshot (one line per entry)</span>
          <textarea v-model="alertForm.current_text" rows="8" class="w-full rounded-xl border px-3 py-2" />
        </label>
      </div>

      <button @click="scanCaseAlerts" class="mt-4 rounded-xl border px-4 py-2 font-medium" :disabled="alertLoading">
        {{ alertLoading ? 'Scanning...' : 'Scan Docket Alerts' }}
      </button>
    </section>

    <template v-if="result">
      <CaseSummaryCard :summary="result.summary" />

      <section class="grid gap-4 md:grid-cols-2">
        <RiskCard v-for="risk in result.risk_flags" :key="risk.title" :risk="risk" />
      </section>

      <section class="rounded-2xl border p-6 shadow-sm">
        <h2 class="text-2xl font-semibold">Likely Questions</h2>
        <ul class="mt-4 list-disc pl-6 space-y-2">
          <li v-for="question in result.likely_questions" :key="question">{{ question }}</li>
        </ul>
      </section>

      <RecommendedRoutes :routes="result.content_routes" />
      <LeadCaptureForm :cta="result.cta" />
    </template>

    <AlertFeed v-if="alertResult" :result="alertResult" />
  </main>
</template>
