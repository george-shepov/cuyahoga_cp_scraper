<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { getContent, updateContent, createContent, seedContent } from "@/services/api";

// ── State ────────────────────────────────────────────────────────────────────
const loading = ref(false);
const saving = ref<number | null>(null);
const allItems = ref<any[]>([]);
const counts = ref({ draft: 0, review: 0, approved: 0, archived: 0 });
const error = ref<string | null>(null);
const successMsg = ref<string | null>(null);

// New-item form
const showNewForm = ref(false);
const newItem = ref({ title: "", question: "", body: "", content_type: "FAQ" });

// Editing state: item_id → field edits
const edits = ref<Record<number, any>>({});

// ── Computed ──────────────────────────────────────────────────────────────────
const reviewBank = computed(() =>
  allItems.value.filter((i) => i.status === "DRAFT" || i.status === "UNDER_REVIEW")
);
const approvedItems = computed(() =>
  allItems.value.filter((i) => i.status === "APPROVED")
);
const archivedItems = computed(() =>
  allItems.value.filter((i) => i.status === "ARCHIVED")
);

// ── Load ──────────────────────────────────────────────────────────────────────
async function load() {
  loading.value = true;
  error.value = null;
  try {
    const data = await getContent();
    allItems.value = data.items;
    counts.value = {
      draft: data.draft_count,
      review: data.review_count,
      approved: data.approved_count,
      archived: data.archived_count,
    };
  } catch (e: any) {
    error.value = e?.message ?? "Load failed";
  } finally {
    loading.value = false;
  }
}

// ── Mutations ─────────────────────────────────────────────────────────────────
async function setStatus(item: any, status: string) {
  saving.value = item.id;
  try {
    const patch: any = { status };
    // Also apply any in-progress text edits
    if (edits.value[item.id]) {
      Object.assign(patch, edits.value[item.id]);
      delete edits.value[item.id];
    }
    const updated = await updateContent(item.id, patch);
    const idx = allItems.value.findIndex((i) => i.id === item.id);
    if (idx !== -1) allItems.value[idx] = updated;
    flash(`"${updated.title}" → ${status}`);
  } finally {
    saving.value = null;
  }
}

async function saveEdits(item: any) {
  const patch = edits.value[item.id];
  if (!patch) return;
  saving.value = item.id;
  try {
    const updated = await updateContent(item.id, patch);
    const idx = allItems.value.findIndex((i) => i.id === item.id);
    if (idx !== -1) allItems.value[idx] = updated;
    delete edits.value[item.id];
    flash("Saved");
  } finally {
    saving.value = null;
  }
}

async function addNew() {
  if (!newItem.value.title.trim() || !newItem.value.body.trim()) return;
  saving.value = -1;
  try {
    const slug = newItem.value.title
      .toLowerCase()
      .replace(/[^\w\s-]/g, "")
      .replace(/[\s_-]+/g, "-")
      .slice(0, 160);
    const created = await createContent({ ...newItem.value, slug });
    allItems.value.unshift(created);
    counts.value.draft += 1;
    showNewForm.value = false;
    newItem.value = { title: "", question: "", body: "", content_type: "FAQ" };
    flash("Draft created");
  } finally {
    saving.value = null;
  }
}

async function runSeed() {
  saving.value = -2;
  try {
    const result = await seedContent();
    flash(`Seed complete — ${result.inserted} items inserted`);
    await load();
  } finally {
    saving.value = null;
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function edit(item: any, field: string, value: string) {
  if (!edits.value[item.id]) edits.value[item.id] = {};
  edits.value[item.id][field] = value;
}

function isDirty(item: any) {
  return !!edits.value[item.id] && Object.keys(edits.value[item.id]).length > 0;
}

function flash(msg: string) {
  successMsg.value = msg;
  setTimeout(() => (successMsg.value = null), 3000);
}

function statusBadge(status: string) {
  switch (status) {
    case "APPROVED":   return "bg-emerald-100 text-emerald-800";
    case "UNDER_REVIEW": return "bg-blue-100 text-blue-700";
    case "DRAFT":      return "bg-stone-100 text-stone-600";
    case "ARCHIVED":   return "bg-zinc-100 text-zinc-500";
    default:           return "bg-stone-100 text-stone-600";
  }
}

onMounted(load);
</script>

<template>
  <main class="mx-auto max-w-6xl space-y-8 px-4 py-10">

    <!-- Header -->
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="font-serif text-3xl font-bold text-steel">Content Strategy</h1>
        <p class="mt-1 text-stone-500">Public content should be selective, not exhaustive.</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          class="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-600 hover:bg-stone-50"
          :disabled="saving === -2"
          @click="runSeed"
        >
          {{ saving === -2 ? "Seeding…" : "Seed Defaults" }}
        </button>
        <button
          class="rounded-xl bg-steel px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          @click="showNewForm = !showNewForm"
        >
          + New Draft
        </button>
      </div>
    </div>

    <!-- Strategy pillars -->
    <section class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
        <p class="text-xs font-bold uppercase tracking-widest text-accent">SEO-first</p>
        <p class="mt-2 text-sm leading-6 text-stone-600">Only approved questions belong on the public page.</p>
      </div>
      <div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
        <p class="text-xs font-bold uppercase tracking-widest text-steel">Review Bank</p>
        <p class="mt-2 text-sm leading-6 text-stone-600">All candidate questions remain editable here until approved.</p>
      </div>
      <div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
        <p class="text-xs font-bold uppercase tracking-widest text-emerald-700">Fast Public Page</p>
        <p class="mt-2 text-sm leading-6 text-stone-600">Less clutter means cleaner crawl paths and tighter intent matching.</p>
      </div>
      <div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
        <p class="text-xs font-bold uppercase tracking-widest text-blue-600">AI Alignment</p>
        <p class="mt-2 text-sm leading-6 text-stone-600">Focused answers improve the odds of being cited or recommended.</p>
      </div>
    </section>

    <!-- Stats bar -->
    <section class="flex flex-wrap gap-3">
      <div class="rounded-xl bg-stone-100 px-4 py-2 text-sm">
        <span class="font-bold text-stone-700">{{ counts.draft }}</span>
        <span class="ml-1 text-stone-500">Draft</span>
      </div>
      <div class="rounded-xl bg-blue-50 px-4 py-2 text-sm">
        <span class="font-bold text-blue-700">{{ counts.review }}</span>
        <span class="ml-1 text-blue-500">In Review</span>
      </div>
      <div class="rounded-xl bg-emerald-50 px-4 py-2 text-sm">
        <span class="font-bold text-emerald-700">{{ counts.approved }}</span>
        <span class="ml-1 text-emerald-500">Live / Approved</span>
      </div>
      <div class="rounded-xl bg-zinc-100 px-4 py-2 text-sm">
        <span class="font-bold text-zinc-500">{{ counts.archived }}</span>
        <span class="ml-1 text-zinc-400">Archived</span>
      </div>
    </section>

    <!-- Toast -->
    <div
      v-if="successMsg"
      class="rounded-xl bg-emerald-50 px-5 py-2.5 text-sm font-medium text-emerald-700"
    >
      {{ successMsg }}
    </div>
    <div v-if="error" class="rounded-xl bg-red-50 px-5 py-3 text-sm text-red-700">
      {{ error }}
    </div>

    <!-- New item form -->
    <section v-if="showNewForm" class="rounded-2xl border border-dashed border-stone-300 bg-stone-50 p-6">
      <h2 class="mb-4 font-semibold text-stone-800">New Draft</h2>
      <div class="grid gap-4 sm:grid-cols-2">
        <div>
          <label class="block text-xs font-medium text-stone-600 mb-1">Title / Question (public)</label>
          <input
            v-model="newItem.title"
            type="text"
            class="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-steel/30"
            placeholder="What happens after an OVI arrest?"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-stone-600 mb-1">Type</label>
          <select v-model="newItem.content_type" class="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm">
            <option value="FAQ">FAQ</option>
            <option value="GUIDE">Guide</option>
          </select>
        </div>
        <div class="sm:col-span-2">
          <label class="block text-xs font-medium text-stone-600 mb-1">Answer / Body</label>
          <textarea
            v-model="newItem.body"
            rows="3"
            class="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-steel/30"
            placeholder="Clear, direct answer…"
          />
        </div>
      </div>
      <div class="mt-4 flex gap-2">
        <button
          :disabled="!newItem.title.trim() || !newItem.body.trim() || saving === -1"
          class="rounded-xl bg-steel px-5 py-2 text-sm font-semibold text-white disabled:opacity-40 hover:opacity-90"
          @click="addNew"
        >
          {{ saving === -1 ? "Creating…" : "Save as Draft" }}
        </button>
        <button
          class="rounded-xl border border-stone-300 px-4 py-2 text-sm text-stone-600 hover:bg-stone-100"
          @click="showNewForm = false"
        >
          Cancel
        </button>
      </div>
    </section>

    <!-- ── Review Bank ──────────────────────────────────────────────────────── -->
    <section>
      <div class="mb-3 flex items-center gap-3">
        <h2 class="font-serif text-2xl font-bold text-steel">Review Bank</h2>
        <span class="rounded-full bg-blue-100 px-3 py-0.5 text-sm font-bold text-blue-700">
          {{ reviewBank.length }}
        </span>
      </div>
      <p class="mb-4 text-sm text-stone-500">
        All candidate questions remain editable here until approved. The admin page is where broader drafts and
        pending ideas live until they are worth publishing.
      </p>

      <div v-if="loading" class="rounded-2xl border bg-white p-8 text-center text-stone-400">Loading…</div>
      <div v-else-if="reviewBank.length === 0" class="rounded-2xl border bg-stone-50 p-8 text-center text-stone-400">
        No items in draft or review.
        <button class="ml-2 text-accent underline" @click="runSeed">Seed defaults</button>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="item in reviewBank"
          :key="item.id"
          class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm"
        >
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div class="flex items-center gap-2 flex-wrap">
              <span :class="['rounded-full px-2.5 py-0.5 text-xs font-semibold', statusBadge(item.status)]">
                {{ item.status }}
              </span>
              <span class="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-500">
                {{ item.content_type }}
              </span>
            </div>
            <div class="flex gap-1.5">
              <button
                v-if="item.status === 'DRAFT'"
                :disabled="saving === item.id"
                class="rounded-lg bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-50"
                @click="setStatus(item, 'UNDER_REVIEW')"
              >
                → Review
              </button>
              <button
                :disabled="saving === item.id"
                class="rounded-lg bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                @click="setStatus(item, 'APPROVED')"
              >
                ✓ Approve
              </button>
              <button
                :disabled="saving === item.id"
                class="rounded-lg bg-zinc-50 px-3 py-1 text-xs font-semibold text-zinc-500 hover:bg-zinc-100 disabled:opacity-50"
                @click="setStatus(item, 'ARCHIVED')"
              >
                Archive
              </button>
            </div>
          </div>

          <!-- Editable title -->
          <input
            :value="edits[item.id]?.title ?? item.title"
            class="mt-3 w-full rounded-lg border border-transparent bg-transparent px-1 py-0.5 text-base font-semibold text-stone-800 hover:border-stone-200 focus:border-stone-300 focus:bg-stone-50 focus:outline-none"
            @input="edit(item, 'title', ($event.target as HTMLInputElement).value)"
          />

          <!-- Editable body -->
          <textarea
            :value="edits[item.id]?.body ?? item.body"
            rows="2"
            class="mt-1 w-full rounded-lg border border-transparent bg-transparent px-1 py-0.5 text-sm leading-6 text-stone-600 hover:border-stone-200 focus:border-stone-300 focus:bg-stone-50 focus:outline-none resize-none"
            @input="edit(item, 'body', ($event.target as HTMLTextAreaElement).value)"
          />

          <div v-if="isDirty(item)" class="mt-2 flex gap-2">
            <button
              :disabled="saving === item.id"
              class="rounded-lg bg-steel px-3 py-1 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
              @click="saveEdits(item)"
            >
              {{ saving === item.id ? "Saving…" : "Save edits" }}
            </button>
            <button
              class="rounded-lg border border-stone-200 px-3 py-1 text-xs text-stone-500 hover:bg-stone-50"
              @click="delete edits[item.id]"
            >
              Discard
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- ── Live / Approved ────────────────────────────────────────────────── -->
    <section>
      <div class="mb-3 flex items-center gap-3">
        <h2 class="font-serif text-2xl font-bold text-steel">Live on Public Page</h2>
        <span class="rounded-full bg-emerald-100 px-3 py-0.5 text-sm font-bold text-emerald-700">
          {{ approvedItems.length }}
        </span>
      </div>
      <p class="mb-4 text-sm text-stone-500">
        These are the only questions rendered on the public SEO pages. Less clutter = cleaner crawl paths.
      </p>

      <div v-if="approvedItems.length === 0" class="rounded-2xl border bg-stone-50 p-8 text-center text-stone-400">
        No approved items yet. Approve items from the review bank above.
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="item in approvedItems"
          :key="item.id"
          class="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-5 shadow-sm"
        >
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p class="font-semibold text-stone-800">{{ item.title }}</p>
              <p class="mt-1 text-sm leading-6 text-stone-600">{{ item.body }}</p>
            </div>
            <button
              :disabled="saving === item.id"
              class="rounded-lg bg-zinc-50 px-3 py-1 text-xs font-semibold text-zinc-500 hover:bg-zinc-100 disabled:opacity-50"
              @click="setStatus(item, 'ARCHIVED')"
            >
              Archive
            </button>
          </div>
          <p v-if="item.approved_at" class="mt-2 text-xs text-stone-400">
            Approved {{ new Date(item.approved_at).toLocaleDateString() }}
          </p>
        </div>
      </div>
    </section>

    <!-- ── Archived (collapsed) ───────────────────────────────────────────── -->
    <section v-if="archivedItems.length > 0">
      <details class="rounded-2xl border border-stone-200 bg-white">
        <summary class="cursor-pointer px-5 py-4 text-sm font-medium text-stone-500 hover:text-stone-700">
          Archived ({{ archivedItems.length }})
        </summary>
        <div class="divide-y divide-stone-100 px-5 pb-4">
          <div v-for="item in archivedItems" :key="item.id" class="flex items-center justify-between gap-2 py-3">
            <p class="text-sm text-stone-500 line-through">{{ item.title }}</p>
            <button
              :disabled="saving === item.id"
              class="rounded-lg bg-stone-50 px-3 py-1 text-xs text-stone-600 hover:bg-stone-100"
              @click="setStatus(item, 'DRAFT')"
            >
              Restore
            </button>
          </div>
        </div>
      </details>
    </section>

  </main>
</template>
