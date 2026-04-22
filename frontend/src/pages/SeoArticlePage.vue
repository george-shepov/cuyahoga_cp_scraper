<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { getSeoPage } from "@/services/api";
import HeroBlock from "@/components/HeroBlock.vue";
import FAQAccordion from "@/components/FAQAccordion.vue";

const route = useRoute();
const page = ref<any>(null);

onMounted(async () => {
  const slug = String(route.params.slug || "ovi-lawyer-cleveland");
  page.value = await getSeoPage(slug);
  document.title = page.value.title;
});
</script>

<template>
  <main v-if="page" class="mx-auto max-w-4xl space-y-8 p-6">
    <HeroBlock :title="page.h1" :body="page.intro" />

    <section v-for="section in page.sections" :key="section.heading" class="rounded-2xl border p-6 shadow-sm">
      <h2 class="text-2xl font-semibold">{{ section.heading }}</h2>
      <p class="mt-3 leading-7">{{ section.body }}</p>
      <ul v-if="section.bullets?.length" class="mt-4 list-disc pl-6 space-y-1">
        <li v-for="bullet in section.bullets" :key="bullet">{{ bullet }}</li>
      </ul>
    </section>

    <section class="rounded-2xl border p-6 shadow-sm">
      <h2 class="text-2xl font-semibold">Frequently Asked Questions</h2>
      <div class="mt-4">
        <FAQAccordion :items="page.faq" />
      </div>
    </section>

    <section class="rounded-2xl border p-6 shadow-sm">
      <h2 class="text-2xl font-semibold">{{ page.cta.heading }}</h2>
      <p class="mt-3 leading-7">{{ page.cta.body }}</p>
      <div class="mt-4 flex flex-wrap gap-3">
        <a :href="page.cta.primary_href" class="rounded-xl border px-4 py-2 font-medium">
          {{ page.cta.primary_label }}
        </a>
        <a
          v-if="page.cta.secondary_href"
          :href="page.cta.secondary_href"
          class="rounded-xl border px-4 py-2 font-medium"
        >
          {{ page.cta.secondary_label }}
        </a>
      </div>
    </section>
  </main>
</template>
