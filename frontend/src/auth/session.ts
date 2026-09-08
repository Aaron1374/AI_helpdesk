import type { AuthUser } from '../api/types';

const tokenKey = 'helpdesk_access_token';
const userKey = 'helpdesk_user';

export function getToken(): string | null {
  return sessionStorage.getItem(tokenKey);
}

export function getSessionUser(): AuthUser | null {
  const value = sessionStorage.getItem(userKey);
  if (!value) return null;
  try {
    return JSON.parse(value) as AuthUser;
  } catch {
    clearSession();
    return null;
  }
}

export function saveSession(token: string, user: AuthUser): void {
  sessionStorage.setItem(tokenKey, token);
  sessionStorage.setItem(userKey, JSON.stringify(user));
}

export function clearSession(): void {
  sessionStorage.removeItem(tokenKey);
  sessionStorage.removeItem(userKey);
}