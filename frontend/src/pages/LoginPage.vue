<template>
  <div class="min-h-screen bg-[#12151a] flex items-center justify-center px-4">
    <div class="w-full max-w-sm">
      <!-- Brand -->
      <div class="text-center mb-8">
        <p class="text-[#b56a34] text-sm font-semibold tracking-widest uppercase mb-1">
          Brockler Law
        </p>
        <h1 class="text-white text-2xl font-bold">Admin Access</h1>
        <p class="text-slate-400 text-sm mt-1">Password + Authenticator required</p>
      </div>

      <!-- Card -->
      <div
        class="bg-[#1c2330] border border-white/10 rounded-2xl p-8 shadow-xl"
        role="main"
        aria-label="Login form"
      >
        <form @submit.prevent="handleSubmit" novalidate>
          <!-- Username -->
          <label class="block mb-4">
            <span class="text-slate-300 text-sm font-semibold">Username</span>
            <input
              v-model="form.username"
              type="text"
              name="username"
              autocomplete="username"
              required
              class="mt-1 block w-full bg-[#263342]/60 border border-white/10 rounded-xl
                     px-4 py-3 text-white placeholder-slate-500 focus:outline-none
                     focus:ring-2 focus:ring-[#b56a34] text-sm"
              placeholder="Username"
              :disabled="loading"
            />
          </label>

          <!-- Password -->
          <label class="block mb-4">
            <span class="text-slate-300 text-sm font-semibold">Password</span>
            <div class="relative mt-1">
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                name="password"
                autocomplete="current-password"
                required
                class="block w-full bg-[#263342]/60 border border-white/10 rounded-xl
                       px-4 py-3 text-white placeholder-slate-500 focus:outline-none
                       focus:ring-2 focus:ring-[#b56a34] text-sm pr-12"
                placeholder="Password"
                :disabled="loading"
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400
                       hover:text-white transition-colors text-xs"
                :aria-label="showPassword ? 'Hide password' : 'Show password'"
              >
                {{ showPassword ? "Hide" : "Show" }}
              </button>
            </div>
          </label>

          <!-- TOTP -->
          <!-- TOTP — only shown when backend has a secret configured -->
          <label v-if="totpRequired" class="block mb-6">
            <span class="text-slate-300 text-sm font-semibold">Authenticator Code</span>
            <p class="text-slate-500 text-xs mt-0.5 mb-1">
              6-digit code from Google Authenticator or Authy
            </p>
            <input
              v-model="form.totpCode"
              type="text"
              inputmode="numeric"
              name="totp_code"
              autocomplete="one-time-code"
              maxlength="6"
              pattern="[0-9]{6}"
              required
              class="mt-1 block w-full bg-[#263342]/60 border border-white/10 rounded-xl
                     px-4 py-3 text-white placeholder-slate-500 focus:outline-none
                     focus:ring-2 focus:ring-[#b56a34] text-sm tracking-[0.3em]"
              placeholder="000000"
              :disabled="loading"
              @input="form.totpCode = form.totpCode.replace(/\D/g, '').slice(0, 6)"
            />
          </label>

          <!-- Error -->
          <p
            v-if="error"
            role="alert"
            class="text-red-400 text-sm mb-4 bg-red-900/20 border border-red-800/30
                   rounded-lg px-3 py-2"
          >
            {{ error }}
          </p>

          <!-- Submit -->
          <button
            type="submit"
            :disabled="loading || !canSubmit"
            class="w-full bg-gradient-to-b from-[#d7874d] to-[#b56a34] text-white
                   font-bold py-3 rounded-xl transition-opacity disabled:opacity-50
                   disabled:cursor-not-allowed hover:opacity-90 text-sm"
          >
            <span v-if="loading" class="opacity-75">Verifying…</span>
            <span v-else>Sign in</span>
          </button>
        </form>
      </div>

      <p class="text-center text-slate-600 text-xs mt-6">
        Not indexed &nbsp;·&nbsp; Internal use only
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { login } from "@/services/api";
import { saveToken } from "@/services/auth";

const router = useRouter();
const route = useRoute();

const form = ref({ username: "", password: "", totpCode: "" });
const loading = ref(false);
const error = ref("");
const showPassword = ref(false);
const totpRequired = ref(false);

onMounted(async () => {
  try {
    const res = await fetch("/api/auth/config");
    const cfg = await res.json();
    totpRequired.value = cfg.totp_required ?? false;
  } catch {
    // If config endpoint unreachable, keep TOTP hidden
  }
});

const canSubmit = computed(
  () =>
    form.value.username.trim().length > 0 &&
    form.value.password.length > 0 &&
    (!totpRequired.value || form.value.totpCode.length === 6),
);

async function handleSubmit() {
  if (!canSubmit.value) return;
  error.value = "";
  loading.value = true;
  try {
    const data = await login(
      form.value.username.trim(),
      form.value.password,
      form.value.totpCode,
    );
    // JWT is valid for 8 hours (28800 s)
    saveToken(data.access_token, 28800);
    const next = (route.query.redirect as string) || "/content-strategy";
    await router.push(next);
  } catch {
    error.value = "Invalid credentials or authenticator code.";
  } finally {
    loading.value = false;
    form.value.totpCode = "";
  }
}
</script>
