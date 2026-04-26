<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { getCaseIntelligence } from "@/services/api";

// ── State ────────────────────────────────────────────────────────────────────
const STORAGE_KEY = "ci_attorney_name";
const attorneyName = ref(localStorage.getItem(STORAGE_KEY) ?? "");
const daysBack = ref(30);

const loading = ref(false);
const lastSync = ref<string | null>(null);
const myCases = ref<any[]>([]);
const unassigned = ref<any[]>([]);
const error = ref<string | null>(null);

// ── Computed ─────────────────────────────────────────────────────────────────
const isSignedIn = computed(() => attorneyName.value.trim().length > 0);

// ── Methods ──────────────────────────────────────────────────────────────────
async function sync() {
  if (!isSignedIn.value) return;
  loading.value = true;
  error.value = null;
  try {
    const data = await getCaseIntelligence(attorneyName.value.trim(), daysBack.value);
    myCases.value = data.my_cases;
    unassigned.value = data.unassigned_filings;
    lastSync.value = new Date().toLocaleTimeString();
    localStorage.setItem(STORAGE_KEY, attorneyName.value.trim());
  } catch (e: any) {
    error.value = e?.message ?? "Sync failed";
  } finally {
    loading.value = false;
  }
}

function signOut() {
  attorneyName.value = "";
  myCases.value = [];
  unassigned.value = [];
  lastSync.value = null;
  localStorage.removeItem(STORAGE_KEY);
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function statusClass(status: string) {
  const s = status?.toUpperCase();
  if (s === "ACTIVE" || s === "PENDING") return "bg-amber-100 text-amber-800";
  if (s === "DISPOSED" || s === "CLOSED") return "bg-stone-100 text-stone-600";
  return "bg-blue-100 text-blue-700";
}

function hasCaseSuffix(caseNumber?: string) {
  return /^CR-\d{2}-\d{6}-[A-Z]+$/i.test(caseNumber || "");
}

function primaryCaseRef(row: any) {
  if (hasCaseSuffix(row?.case_number)) return row.case_number;
  const candidates = Array.isArray(row?.candidate_case_ids) ? row.candidate_case_ids : [];
  if (candidates.length > 0) return candidates[0];
  return row?.case_number || "";
}

function docketUrl(caseRef?: string) {
  return `https://cpdocket.cp.cuyahogacounty.gov/CR_CaseInformation.aspx?q=${encodeURIComponent(caseRef || "")}`;
}

function fmtDate(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString();
}

function fmtDateTime(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

// Auto-sync if already signed in
onMounted(() => {
  if (isSignedIn.value) sync();
});
</script>

<template>
  <main class="mx-auto max-w-5xl space-y-8 px-4 py-10">

    <!-- Header -->
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-bold text-steel">Case Intelligence</h1>
        <p class="mt-1 text-stone-500">My active cases and new county filings.</p>
      </div>

      <!-- Sync controls -->
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-xs text-stone-400">
          Last sync: {{ lastSync ?? "—" }}
        </span>
        <button
          v-if="isSignedIn"
          :disabled="loading"
          class="rounded-xl bg-steel px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          @click="sync"
        >
          {{ loading ? "Syncing…" : "Sync Cases" }}
        </button>
        <button
          v-if="isSignedIn"
          class="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-600 hover:bg-stone-50"
          @click="signOut"
        >
          Sign Out
        </button>
      </div>
    </div>

    <!-- Sign-in panel -->
    <section v-if="!isSignedIn" class="rounded-2xl border border-dashed border-stone-300 bg-stone-50 p-8 text-center">
      <p class="text-stone-500">Enter your name as it appears on case filings to load your cases.</p>
      <div class="mt-4 flex flex-wrap justify-center gap-3">
        <input
          v-model="attorneyName"
          type="text"
          placeholder="e.g. BROCKLER"
          class="rounded-xl border border-stone-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-steel/40"
          @keyup.enter="sync"
        />
        <select v-model="daysBack" class="rounded-xl border border-stone-300 px-3 py-2 text-sm">
          <option :value="7">Last 7 days</option>
          <option :value="14">Last 14 days</option>
          <option :value="30">Last 30 days</option>
          <option :value="60">Last 60 days</option>
        </select>
        <button
          :disabled="!attorneyName.trim()"
          class="rounded-xl bg-steel px-5 py-2 text-sm font-semibold text-white disabled:opacity-40"
          @click="sync"
        >
          Sign In &amp; Sync
        </button>
      </div>
    </section>

    <!-- Error -->
    <div v-if="error" class="rounded-xl bg-red-50 px-5 py-3 text-sm text-red-700">
      {{ error }}
    </div>

    <!-- My Active Cases -->
    <section v-if="isSignedIn">
      <div class="mb-3 flex items-center gap-3">
        <h2 class="font-serif text-2xl font-bold text-steel">My Active Cases</h2>
        <span class="rounded-full bg-steel px-3 py-0.5 text-sm font-bold text-white">
          {{ myCases.length }}
        </span>
      </div>
      <p class="mb-4 text-sm text-stone-500">
        Cases where <span class="font-medium">{{ attorneyName }}</span> is the attorney of record.
      </p>

      <div v-if="loading && myCases.length === 0" class="rounded-2xl border bg-white p-8 text-center text-stone-400">
        Loading…
      </div>

      <div v-else-if="myCases.length === 0 && !loading" class="rounded-2xl border bg-stone-50 p-8 text-center text-stone-400">
        No active cases found. Sync or check the attorney name spelling.
      </div>

      <div v-else class="space-y-4">
        <div class="hidden overflow-x-auto rounded-xl border border-stone-200 bg-white md:block">
          <table class="min-w-full text-sm">
            <thead class="bg-stone-50 text-left text-xs font-semibold uppercase tracking-wide text-stone-500">
              <tr>
                <th class="px-4 py-3">Case</th>
                <th class="px-4 py-3">Defendant</th>
                <th class="px-4 py-3">Judge</th>
                <th class="px-4 py-3">Case Date</th>
                <th class="px-4 py-3">Changed Last</th>
                <th class="px-4 py-3">Updated Last</th>
                <th class="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in myCases" :key="`my-${row.case_number}`" class="border-t border-stone-100 align-top">
                <td class="px-4 py-3">
                  <a :href="docketUrl(primaryCaseRef(row))" target="_blank" rel="noopener" class="font-mono font-semibold text-steel hover:underline">
                    {{ row.case_number }}
                  </a>
                  <div v-if="row.candidate_case_ids?.length > 1" class="mt-1 flex flex-wrap gap-1">
                    <a
                      v-for="cid in row.candidate_case_ids"
                      :key="cid"
                      :href="docketUrl(cid)"
                      target="_blank"
                      rel="noopener"
                      class="rounded border border-stone-300 px-1.5 py-0.5 text-[10px] font-medium text-stone-700 hover:bg-stone-100"
                    >{{ cid.split('-').slice(-1)[0] }}</a>
                  </div>
                </td>
                <td class="px-4 py-3 font-medium text-stone-800">{{ row.defendant_name || "Unknown Defendant" }}</td>
                <td class="px-4 py-3 text-stone-600">{{ row.judge_name || "—" }}</td>
                <td class="px-4 py-3 text-stone-600">{{ fmtDate(row.case_date || row.filed_date) }}</td>
                <td class="px-4 py-3 text-stone-600">{{ fmtDateTime(row.last_changed_at) }}</td>
                <td class="px-4 py-3 text-stone-600">{{ fmtDateTime(row.last_updated_at) }}</td>
                <td class="px-4 py-3">
                  <span :class="['rounded-full px-2 py-0.5 text-xs font-semibold', statusClass(row.status)]">{{ row.status }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="space-y-3 md:hidden">
        <div
          v-for="row in myCases"
          :key="row.case_number"
          class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow"
        >
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div>
              <a
                :href="docketUrl(primaryCaseRef(row))"
                target="_blank"
                rel="noopener"
                class="font-mono text-sm font-bold text-steel hover:underline"
              >
                {{ row.case_number }}
              </a>
              <div v-if="row.candidate_case_ids?.length > 1" class="mt-1 flex flex-wrap gap-1">
                <a
                  v-for="cid in row.candidate_case_ids"
                  :key="cid"
                  :href="docketUrl(cid)"
                  target="_blank"
                  rel="noopener"
                  class="rounded border border-stone-300 px-1.5 py-0.5 text-[10px] font-medium text-stone-700 hover:bg-stone-100"
                >{{ cid.split('-').slice(-1)[0] }}</a>
              </div>
              <p v-if="row.defendant_name" class="mt-0.5 text-base font-semibold text-stone-800">
                {{ row.defendant_name }}
              </p>
            </div>
            <span :class="['rounded-full px-2.5 py-0.5 text-xs font-semibold', statusClass(row.status)]">
              {{ row.status }}
            </span>
          </div>

          <div class="mt-3 flex flex-wrap gap-4 text-sm text-stone-500">
            <span v-if="row.judge_name">
              <span class="font-medium text-stone-700">Judge:</span> {{ row.judge_name }}
            </span>
            <span>
              <span class="font-medium text-stone-700">Case Date:</span> {{ fmtDate(row.case_date || row.filed_date) }}
            </span>
            <span>
              <span class="font-medium text-stone-700">Changed:</span> {{ fmtDateTime(row.last_changed_at) }}
            </span>
            <span>
              <span class="font-medium text-stone-700">Updated:</span> {{ fmtDateTime(row.last_updated_at) }}
            </span>
          </div>

          <div v-if="row.charges?.length" class="mt-2 flex flex-wrap gap-1.5">
            <span
              v-for="charge in row.charges"
              :key="charge"
              class="rounded-lg bg-stone-100 px-2 py-0.5 text-xs text-stone-600"
            >
              {{ charge }}
            </span>
          </div>
        </div>
        </div>
      </div>
    </section>

    <!-- New Filings — No Defense Attorney -->
    <section v-if="isSignedIn">
      <div class="mb-3 flex items-center gap-3">
        <h2 class="font-serif text-2xl font-bold text-steel">New Filings — No Defense Attorney</h2>
        <span class="rounded-full bg-amber-500 px-3 py-0.5 text-sm font-bold text-white">
          {{ unassigned.length }}
        </span>
      </div>
      <p class="mb-4 text-sm text-stone-500">
        Cases filed in the last {{ daysBack }} days with no defense attorney assigned yet.
        <a href="/check-my-case" class="font-medium text-accent hover:underline">Run a case check →</a>
      </p>

      <div v-if="loading && unassigned.length === 0" class="rounded-2xl border bg-white p-8 text-center text-stone-400">
        Loading…
      </div>

      <div v-else-if="unassigned.length === 0 && !loading" class="rounded-2xl border bg-stone-50 p-8 text-center text-stone-400">
        No unassigned filings in the last {{ daysBack }} days.
      </div>

      <div v-else class="space-y-4">
        <div class="hidden overflow-x-auto rounded-xl border border-amber-200 bg-white md:block">
          <table class="min-w-full text-sm">
            <thead class="bg-amber-50 text-left text-xs font-semibold uppercase tracking-wide text-amber-800">
              <tr>
                <th class="px-4 py-3">Case</th>
                <th class="px-4 py-3">Defendant</th>
                <th class="px-4 py-3">Judge</th>
                <th class="px-4 py-3">Case Date</th>
                <th class="px-4 py-3">Changed Last</th>
                <th class="px-4 py-3">Updated Last</th>
                <th class="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in unassigned" :key="`vac-${row.case_number}`" class="border-t border-amber-100 align-top">
                <td class="px-4 py-3">
                  <a :href="docketUrl(primaryCaseRef(row))" target="_blank" rel="noopener" class="font-mono font-semibold text-steel hover:underline">
                    {{ row.case_number }}
                  </a>
                  <div v-if="row.candidate_case_ids?.length > 1" class="mt-1 flex flex-wrap gap-1">
                    <a
                      v-for="cid in row.candidate_case_ids"
                      :key="cid"
                      :href="docketUrl(cid)"
                      target="_blank"
                      rel="noopener"
                      class="rounded border border-amber-300 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 hover:bg-amber-100"
                    >{{ cid.split('-').slice(-1)[0] }}</a>
                  </div>
                </td>
                <td class="px-4 py-3 font-medium text-stone-800">{{ row.defendant_name || "Unknown Defendant" }}</td>
                <td class="px-4 py-3 text-stone-600">{{ row.judge_name || "—" }}</td>
                <td class="px-4 py-3 text-stone-600">{{ fmtDate(row.case_date || row.filed_date) }}</td>
                <td class="px-4 py-3 text-stone-600">{{ fmtDateTime(row.last_changed_at) }}</td>
                <td class="px-4 py-3 text-stone-600">{{ fmtDateTime(row.last_updated_at) }}</td>
                <td class="px-4 py-3">
                  <a href="/check-my-case" class="text-xs font-medium text-accent hover:underline">Analyze</a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="space-y-3 md:hidden">
        <div
          v-for="row in unassigned"
          :key="row.case_number"
          class="rounded-2xl border border-amber-200 bg-amber-50/40 p-5 shadow-sm hover:shadow-md transition-shadow"
        >
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div>
              <a
                :href="docketUrl(primaryCaseRef(row))"
                target="_blank"
                rel="noopener"
                class="font-mono text-sm font-bold text-steel hover:underline"
              >
                {{ row.case_number }}
              </a>
              <div v-if="row.candidate_case_ids?.length > 1" class="mt-1 flex flex-wrap gap-1">
                <a
                  v-for="cid in row.candidate_case_ids"
                  :key="cid"
                  :href="docketUrl(cid)"
                  target="_blank"
                  rel="noopener"
                  class="rounded border border-amber-300 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 hover:bg-amber-100"
                >{{ cid.split('-').slice(-1)[0] }}</a>
              </div>
              <p v-if="row.defendant_name" class="mt-0.5 text-base font-semibold text-stone-800">
                {{ row.defendant_name }}
              </p>
            </div>
            <span class="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
              No Attorney
            </span>
          </div>

          <div class="mt-3 flex flex-wrap gap-4 text-sm text-stone-500">
            <span v-if="row.judge_name">
              <span class="font-medium text-stone-700">Judge:</span> {{ row.judge_name }}
            </span>
            <span>
              <span class="font-medium text-stone-700">Case Date:</span> {{ fmtDate(row.case_date || row.filed_date) }}
            </span>
            <span>
              <span class="font-medium text-stone-700">Changed:</span> {{ fmtDateTime(row.last_changed_at) }}
            </span>
            <span>
              <span class="font-medium text-stone-700">Updated:</span> {{ fmtDateTime(row.last_updated_at) }}
            </span>
          </div>

          <div v-if="row.charges?.length" class="mt-2 flex flex-wrap gap-1.5">
            <span
              v-for="charge in row.charges"
              :key="charge"
              class="rounded-lg bg-amber-100 px-2 py-0.5 text-xs text-amber-700"
            >
              {{ charge }}
            </span>
          </div>

          <div class="mt-3 border-t border-amber-200 pt-3">
            <a
              href="/check-my-case"
              class="text-xs font-medium text-accent hover:underline"
            >
              Analyze this case →
            </a>
          </div>
        </div>
        </div>
      </div>
    </section>

  </main>
</template>
