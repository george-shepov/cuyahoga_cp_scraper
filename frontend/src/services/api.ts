import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
});

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
