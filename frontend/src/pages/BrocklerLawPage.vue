<script setup lang="ts">
import { ref } from "vue";

const stats = [
  { value: "20+", label: "Years in Cuyahoga County courts" },
  { value: "3,000+", label: "OVI & criminal cases handled" },
  { value: "Former", label: "Cuyahoga County Prosecutor" },
  { value: "Direct", label: "Access — no hand-offs to junior staff" },
];

const services = [
  {
    title: "OVI / DUI Defense",
    body:
      "First offense, high-BAC, refusal, and multiple-prior OVI cases. Aaron challenges breath-test calibration, field sobriety procedure, and ALS suspension hearings.",
    href: "/ovi-lawyer-cleveland",
    linkLabel: "OVI defense overview →",
  },
  {
    title: "License Suspension & ALS",
    body:
      "An Administrative License Suspension kicks in within 15 days of arrest. Aaron files ALS appeals and negotiates limited driving privileges so you keep getting to work.",
    href: "/als-suspension-ohio",
    linkLabel: "ALS suspension guide →",
  },
  {
    title: "Breath & Chemical Test Issues",
    body:
      "Refusing a test has consequences; so does a failed one. Aaron understands both paths and builds the strongest possible defense around whichever situation you're in.",
    href: "/refusal-vs-failed-test-ohio-ovi",
    linkLabel: "Refusal vs. failed test →",
  },
  {
    title: "Criminal & Traffic Defense",
    body:
      "Assault, drug charges, domestic violence, and serious traffic violations. Same hands-on approach that has worked across thousands of Cuyahoga County cases.",
    href: "/check-my-case",
    linkLabel: "Check your case →",
  },
];

const faqs = [
  {
    q: "Do I actually talk to Aaron, or does a paralegal handle my case?",
    a: "You talk directly to Aaron. He handles strategy, court appearances, and all key decisions himself.",
  },
  {
    q: "How quickly can Aaron take my OVI case?",
    a: "Call the same day as your arrest if possible — the ALS appeal window is only 15 days. Aaron can usually meet within 24 hours.",
  },
  {
    q: "What does it cost to hire Aaron?",
    a: "Fees depend on case complexity. Aaron offers flat-fee arrangements for most OVI matters so you know the cost upfront.",
  },
  {
    q: "Does being a former prosecutor actually help?",
    a: "Yes. Aaron knows how the other side thinks, what evidence they rely on, and where cases are most beatable — because he built those cases himself.",
  },
];

const openIndex = ref<number | null>(null);

function toggle(i: number) {
  openIndex.value = openIndex.value === i ? null : i;
}
</script>

<template>
  <!-- Hero -->
  <section
    class="relative isolate overflow-hidden rounded-b-3xl bg-steel px-6 py-16 text-white md:py-24"
    style="background: linear-gradient(135deg, #12151a 0%, #263342 60%, #1a2230 100%)"
  >
    <!-- Amber glow -->
    <div
      class="pointer-events-none absolute -right-24 -top-32 h-96 w-96 rounded-full opacity-40"
      style="background: radial-gradient(circle, #b56a34 0%, transparent 70%); filter: blur(60px)"
    />

    <div class="relative mx-auto max-w-4xl">
      <p class="text-sm font-semibold uppercase tracking-widest text-amber-400">Cleveland OVI &amp; Criminal Defense</p>
      <h1 class="mt-4 font-serif text-4xl font-bold leading-tight md:text-5xl">
        Aaron Brockler<br />
        <span class="text-amber-400">Former Prosecutor.</span><br />
        Now On Your Side.
      </h1>
      <p class="mt-6 max-w-2xl text-lg leading-8 text-stone-300">
        Aaron spent years inside the Cuyahoga County Prosecutor's Office learning exactly how OVI and criminal cases are
        built — and where they fall apart. Now he uses that knowledge to defend you.
      </p>

      <div class="mt-8 flex flex-wrap gap-4">
        <a
          href="tel:2163706700"
          class="rounded-xl bg-amber-500 px-6 py-3 font-bold text-white shadow-lg transition-opacity hover:opacity-90"
        >
          Call (216) 370-6700
        </a>
        <a
          href="/check-my-case"
          class="rounded-xl border border-white/30 px-6 py-3 font-semibold text-white transition-colors hover:bg-white/10"
        >
          Check My Case →
        </a>
      </div>
    </div>
  </section>

  <!-- Stats bar -->
  <section class="border-b border-stone-200 bg-white">
    <div class="mx-auto grid max-w-4xl grid-cols-2 divide-x divide-stone-100 md:grid-cols-4">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="flex flex-col items-center gap-1 px-4 py-6 text-center"
      >
        <span class="font-serif text-3xl font-bold text-steel">{{ stat.value }}</span>
        <span class="text-xs leading-5 text-stone-500">{{ stat.label }}</span>
      </div>
    </div>
  </section>

  <!-- Services -->
  <section class="mx-auto max-w-4xl space-y-4 px-6 py-12">
    <h2 class="font-serif text-3xl font-bold">How Aaron Can Help</h2>
    <p class="leading-7 text-stone-600">
      Every case is different. Here's what Aaron handles — and where to learn more before you call.
    </p>

    <div class="mt-6 grid gap-4 md:grid-cols-2">
      <div
        v-for="svc in services"
        :key="svc.title"
        class="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
      >
        <h3 class="text-lg font-semibold text-steel">{{ svc.title }}</h3>
        <p class="mt-2 text-sm leading-6 text-stone-600">{{ svc.body }}</p>
        <a :href="svc.href" class="mt-4 inline-block text-sm font-medium text-accent hover:underline">
          {{ svc.linkLabel }}
        </a>
      </div>
    </div>
  </section>

  <!-- Case check CTA -->
  <section class="mx-4 my-4 overflow-hidden rounded-3xl bg-steel px-8 py-10 text-white md:mx-auto md:max-w-4xl">
    <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <h2 class="font-serif text-2xl font-bold">Not sure where your case stands?</h2>
        <p class="mt-2 text-stone-300">
          Enter your charges and facts. The engine surfaces risks, timelines, and what to ask your lawyer.
        </p>
      </div>
      <a
        href="/check-my-case"
        class="flex-shrink-0 rounded-xl bg-amber-500 px-6 py-3 text-center font-bold text-white shadow transition-opacity hover:opacity-90"
      >
        Check My Case
      </a>
    </div>
  </section>

  <!-- FAQ -->
  <section class="mx-auto max-w-4xl px-6 py-12">
    <h2 class="font-serif text-3xl font-bold">Common Questions</h2>
    <div class="mt-6 divide-y divide-stone-200 rounded-2xl border border-stone-200 bg-white shadow-sm">
      <div v-for="(item, i) in faqs" :key="item.q" class="px-6">
        <button
          class="flex w-full items-center justify-between gap-4 py-5 text-left text-sm font-semibold text-stone-800 hover:text-steel"
          @click="toggle(i)"
        >
          <span>{{ item.q }}</span>
          <span class="text-lg text-stone-400">{{ openIndex === i ? "−" : "+" }}</span>
        </button>
        <p v-if="openIndex === i" class="pb-5 text-sm leading-6 text-stone-600">{{ item.a }}</p>
      </div>
    </div>
  </section>

  <!-- Bottom CTA -->
  <section class="border-t border-stone-200 bg-stone-100 px-6 py-12 text-center">
    <p class="text-sm font-semibold uppercase tracking-widest text-amber-600">Time matters</p>
    <h2 class="mt-3 font-serif text-3xl font-bold text-steel">Call today. The ALS clock starts now.</h2>
    <p class="mx-auto mt-4 max-w-xl leading-7 text-stone-600">
      Ohio's Administrative License Suspension kicks in automatically after an OVI arrest. You have 15 days to request a
      hearing. Don't wait.
    </p>
    <div class="mt-8 flex flex-wrap justify-center gap-4">
      <a
        href="tel:2163706700"
        class="rounded-xl bg-steel px-8 py-3 font-bold text-white shadow-lg transition-opacity hover:opacity-90"
      >
        (216) 370-6700
      </a>
      <a
        href="/als-suspension-ohio"
        class="rounded-xl border border-steel px-8 py-3 font-semibold text-steel transition-colors hover:bg-stone-200"
      >
        Learn About ALS →
      </a>
    </div>
  </section>
</template>
