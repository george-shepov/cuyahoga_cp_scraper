/**
 * Tiny auth store — stores the JWT in localStorage under "ovi_admin_token".
 * No external state library needed for a single-user admin.
 */

const TOKEN_KEY = "ovi_admin_token";
const EXPIRES_KEY = "ovi_admin_token_exp";

export function saveToken(token: string, expiresInSeconds = 28800): void {
  localStorage.setItem(TOKEN_KEY, token);
  const exp = Date.now() + expiresInSeconds * 1000;
  localStorage.setItem(EXPIRES_KEY, String(exp));
}

export function getToken(): string | null {
  const exp = Number(localStorage.getItem(EXPIRES_KEY) ?? "0");
  if (Date.now() > exp) {
    clearToken();
    return null;
  }
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EXPIRES_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}
