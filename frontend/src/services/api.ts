import axios from "axios";
import { getToken, clearToken } from "./auth";

export const api = axios.create({
  baseURL: "/api",
});

// Attach JWT on every request if present
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

// Auto-logout on 401 (expired / revoked token)
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      clearToken();
      window.location.href = "/login";
    }
    return Promise.reject(err);
  },
);

// ── Auth ─────────────────────────────────────────────────────────────────────
export async function login(username: string, password: string, totpCode: string) {
  const { data } = await api.post("/auth/login", {
    username,
    password,
    totp_code: totpCode,
  });
  return data as { access_token: string; token_type: string };
}

export async function getSeoPage(slug: string) {
  const { data } = await api.get(`/pages/${slug}`);
  return data;
}

export async function analyzeCase(payload: unknown) {
  const { data } = await api.post("/case-analysis", payload);
  return data;
}

export async function scanAlerts(payload: unknown) {
  const { data } = await api.post("/alerts/scan", payload);
  return data;
}

export async function getBillingSummary(accountId = "demo-account", month?: string) {
  const { data } = await api.get("/billing/summary", {
    params: {
      account_id: accountId,
      ...(month ? { month } : {}),
    },
  });
  return data;
}

export async function getCaseIntelligence(attorneyName: string, daysBack = 30, limit = 100) {
  const { data } = await api.get("/cases/intelligence", {
    params: {
      attorney_name: attorneyName,
      days_back: daysBack,
      limit,
    },
  });
  return data;
}

export async function getContent(status?: string, contentType?: string) {
  const { data } = await api.get("/content", {
    params: {
      ...(status ? { status } : {}),
      ...(contentType ? { content_type: contentType } : {}),
    },
  });
  return data;
}

export async function updateContent(itemId: number, patch: Record<string, unknown>) {
  const { data } = await api.patch(`/content/${itemId}`, patch);
  return data;
}

export async function createContent(payload: Record<string, unknown>) {
  const { data } = await api.post("/content", payload);
  return data;
}

export async function seedContent() {
  const { data } = await api.post("/content/seed");
  return data;
}
